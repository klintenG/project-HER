"""
Project HER v2.0 – LLM Client Factory
Creates a configured OpenAI-compatible client based on the active LLM provider.

Supports:
- Groq AI (free, Llama 3.1 8B)
- VS Code Copilot Bridge (Claude Sonnet 4.6 via VS Code — no API key needed)
"""

from __future__ import annotations

import logging
from typing import Optional

from openai import OpenAI

import config
from utils.copilot_bridge import CopilotBridgeClient, is_bridge_available

logger = logging.getLogger(__name__)


def get_llm_client(
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> tuple[OpenAI, str]:
    """
    Create an OpenAI-compatible LLM client for the given provider.

    Args:
        provider: Override the default provider ("groq" or "copilot_bridge").
                  If None, uses config.LLM_PROVIDER.
        model: Override the default model name.
               If None, uses the model configured for the chosen provider.

    Returns:
        Tuple of (client, model_name) ready to call .chat.completions.create().

    Raises:
        ValueError: If the required API key is missing for the chosen provider.
    """
    provider = provider or config.LLM_PROVIDER

    if provider == "copilot_bridge":
        # Use the local VS Code Copilot Bridge — no API key needed
        if not is_bridge_available():
            raise ConnectionError(
                "Copilot Bridge not reachable. Make sure VS Code is open "
                "with the Copilot Bridge extension active. "
                "Falling back is handled by the caller."
            )
        model_name = model or config.COPILOT_BRIDGE_MODEL
        logger.info(
            "Using VS Code Copilot Bridge: model_hint=%s, endpoint=%s",
            model_name, config.COPILOT_BRIDGE_URL,
        )
        return CopilotBridgeClient(), model_name

    else:
        # Default: Groq
        api_key = config.GROQ_API_KEY
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY required. Set it in your .env file."
            )
        base_url = config.GROQ_BASE_URL
        model_name = model or config.GROQ_MODEL
        logger.info(
            "Using Groq AI: model=%s, endpoint=%s",
            model_name, base_url,
        )

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    return client, model_name


def get_provider_info(provider: Optional[str] = None) -> dict:
    """Get human-readable info about the active LLM provider."""
    provider = provider or config.LLM_PROVIDER
    info = config.LLM_PROVIDERS.get(provider, {})

    if provider == "copilot_bridge":
        model = config.COPILOT_BRIDGE_MODEL
        model_label = f"Copilot via VS Code ({model})"
        has_key = is_bridge_available()
    else:
        model = config.GROQ_MODEL
        model_label = "Llama 3.1 8B Instant"
        has_key = bool(config.GROQ_API_KEY)

    return {
        "provider": provider,
        "label": info.get("label", provider),
        "description": info.get("description", ""),
        "model": model,
        "model_label": model_label,
        "has_key": has_key,
        "ready": has_key,
    }
