"""
Project HER – Copilot Bridge Client
Wraps the local VS Code Copilot Bridge HTTP server into an OpenAI-compatible
interface so it plugs seamlessly into the existing LLM client factory.

The bridge runs at http://127.0.0.1:18945 and is started by the
vscode-copilot-bridge extension when VS Code is open.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Read port/URL from env so it stays in sync with .env / config.py
BRIDGE_URL = os.getenv("COPILOT_BRIDGE_URL", "http://127.0.0.1:18945")
BRIDGE_TIMEOUT = 180  # seconds — Copilot LLM calls can be slow for long prompts


# ── Shim classes that mimic the OpenAI SDK response shape ──────────

@dataclass
class _Message:
    content: str
    role: str = "assistant"


@dataclass
class _Choice:
    message: _Message
    index: int = 0
    finish_reason: str = "stop"


@dataclass
class _Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    elapsed_ms: int = 0


@dataclass
class _ChatCompletion:
    """Mimics openai.types.chat.ChatCompletion just enough for our callers."""
    choices: list[_Choice] = field(default_factory=list)
    model: str = ""
    usage: _Usage = field(default_factory=_Usage)


class _Completions:
    """Mimics client.chat.completions with a .create() method."""

    def create(self, *, model: str = "", messages: list = None,
               temperature: float = 0.7, max_tokens: int = 3000,
               **kwargs) -> _ChatCompletion:
        """Send a chat completion request to the Copilot Bridge.

        Translates OpenAI SDK call into the bridge's legacy format:
        {"system_prompt": ..., "user_prompt": ..., "model": ...}

        If response_format={"type": "json_object"} is passed, the bridge
        injects a JSON formatting instruction into the system prompt so
        models reliably return valid JSON (since the bridge API doesn't
        support response_format natively).
        """
        msgs = messages or []

        # Detect response_format request
        response_format = kwargs.get("response_format", {})
        wants_json = (
            isinstance(response_format, dict)
            and response_format.get("type") == "json_object"
        )

        # Extract system + user prompts for legacy format
        system_prompt = ""
        user_prompt = ""
        for m in msgs:
            if m.get("role") == "system":
                system_prompt += m.get("content", "") + "\n"
            elif m.get("role") == "user":
                user_prompt += m.get("content", "") + "\n"
        system_prompt = system_prompt.strip()
        user_prompt = user_prompt.strip()

        # If caller asked for JSON output, reinforce the instruction in the
        # system prompt so the LLM doesn't add markdown fences or commentary
        if wants_json and "json" not in system_prompt.lower():
            system_prompt += (
                "\n\nIMPORTANT: You MUST respond with valid JSON only. "
                "No markdown code fences, no extra commentary, no explanation — "
                "just raw JSON."
            )

        # Use the legacy format (system_prompt / user_prompt) which is
        # compatible with the existing bridge extension
        payload = {
            "model": model,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
        }

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{BRIDGE_URL}/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=BRIDGE_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            # Read the error body for details
            err_body = ""
            try:
                err_body = e.read().decode("utf-8")
            except Exception:
                pass
            raise RuntimeError(
                f"Copilot Bridge returned HTTP {e.code}: {err_body or e.reason}"
            ) from e
        except urllib.error.URLError as e:
            raise ConnectionError(
                f"Copilot Bridge not reachable at {BRIDGE_URL}. "
                "Make sure VS Code is open with the Copilot Bridge extension active. "
                f"Error: {e}"
            ) from e
        except Exception as e:
            raise RuntimeError(f"Copilot Bridge request failed: {e}") from e

        if "error" in data:
            raise RuntimeError(f"Copilot Bridge error: {data['error']}")

        content = data.get("content", "")
        resp_model = data.get("model", model)
        elapsed = data.get("usage", {}).get("elapsed_ms", 0)

        return _ChatCompletion(
            choices=[_Choice(message=_Message(content=content))],
            model=resp_model,
            usage=_Usage(elapsed_ms=elapsed),
        )


class _Chat:
    """Mimics client.chat — just holds .completions."""

    def __init__(self):
        self.completions = _Completions()


class CopilotBridgeClient:
    """
    Drop-in replacement for openai.OpenAI that routes requests through
    the local VS Code Copilot Bridge.

    Usage:
        client = CopilotBridgeClient()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[...],
        )
        print(response.choices[0].message.content)
    """

    def __init__(self, **kwargs):
        self.chat = _Chat()


def is_bridge_available() -> bool:
    """Check if the Copilot Bridge HTTP server is reachable."""
    try:
        req = urllib.request.Request(
            f"{BRIDGE_URL}/health",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("status") == "ok"
    except Exception:
        return False


def get_bridge_models() -> list[dict]:
    """Get list of available models from the bridge."""
    try:
        req = urllib.request.Request(
            f"{BRIDGE_URL}/models",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("models", [])
    except Exception:
        return []
