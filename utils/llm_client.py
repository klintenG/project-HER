"""
Project HER v2.0 – LLM Client Factory
Creates a configured OpenAI-compatible client based on the active LLM provider.

Supports:
- Google AI Studio / Gemini Pro (recommended, high-intelligence reasoning & story writing)
- Groq AI (Llama 3.1 8B, fast fallback)
"""

from __future__ import annotations

import logging
from typing import Optional

from openai import OpenAI, RateLimitError, APIStatusError

import config

logger = logging.getLogger(__name__)


def get_llm_client(
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> tuple[OpenAI, str]:
    """
    Create an OpenAI-compatible LLM client for the given provider.

    Args:
        provider: Override the default provider ("gemini" or "groq").
                  If None, uses config.LLM_PROVIDER.
        model: Override the default model name.
               If None, uses the model configured for the chosen provider.

    Returns:
        Tuple of (client, model_name) ready to call .chat.completions.create().

    Raises:
        ValueError: If the required API key is missing for the chosen provider.
    """
    provider = provider or config.LLM_PROVIDER

    if provider in ("gemini", "google"):
        api_key = config.GEMINI_API_KEY
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY (or GOOGLE_API_KEY / GOOGLE_TTS_API_KEY) required. "
                "Set it in your .env file. Get a key at https://aistudio.google.com/apikey"
            )
        base_url = config.GEMINI_BASE_URL
        model_name = model or config.GEMINI_MODEL
        logger.info(
            "Using Google AI (Gemini): model=%s, endpoint=%s",
            model_name, base_url,
        )
    elif provider == "groq":
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
    else:
        # Default fallback to Gemini
        api_key = config.GEMINI_API_KEY
        if not api_key:
            raise ValueError(
                f"Unknown LLM provider '{provider}' and GEMINI_API_KEY is not set in .env."
            )
        base_url = config.GEMINI_BASE_URL
        model_name = model or config.GEMINI_MODEL
        logger.info(
            "Falling back to Google AI (Gemini): model=%s, endpoint=%s",
            model_name, base_url,
        )

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    # If Gemini is the primary and a Groq key exists, fall back to Groq on rate limits
    if base_url == config.GEMINI_BASE_URL and config.GROQ_API_KEY:
        client = _FallbackClient(client)

    return client, model_name


class _FallbackCompletions:
    """Mimics client.chat.completions; retries on Groq if Gemini is rate-limited."""

    def __init__(self, primary: OpenAI):
        self._primary = primary
        self._groq: Optional[OpenAI] = None

    def create(self, **kwargs):
        try:
            return self._primary.chat.completions.create(**kwargs)
        except RateLimitError as exc:
            logger.warning("Gemini rate-limited (%s) - falling back to Groq", exc)
        except APIStatusError as exc:
            if exc.status_code != 429:
                raise
            logger.warning("Gemini quota error 429 - falling back to Groq")

        if self._groq is None:
            self._groq = OpenAI(api_key=config.GROQ_API_KEY, base_url=config.GROQ_BASE_URL)
        kwargs["model"] = config.GROQ_MODEL
        return self._groq.chat.completions.create(**kwargs)


class _FallbackChat:
    def __init__(self, primary: OpenAI):
        self.completions = _FallbackCompletions(primary)


class _FallbackClient:
    """Drop-in replacement for the OpenAI client exposing .chat.completions.create()."""

    def __init__(self, primary: OpenAI):
        self.chat = _FallbackChat(primary)


def get_provider_info(provider: Optional[str] = None) -> dict:
    """Get human-readable info about the active LLM provider."""
    provider = provider or config.LLM_PROVIDER
    info = config.LLM_PROVIDERS.get(provider, {})

    if provider in ("gemini", "google"):
        model = config.GEMINI_MODEL
        model_label = f"Google Gemini ({model})"
        has_key = bool(config.GEMINI_API_KEY)
    elif provider == "groq":
        model = config.GROQ_MODEL
        model_label = "Llama 3.1 8B Instant"
        has_key = bool(config.GROQ_API_KEY)
    else:
        model = config.GEMINI_MODEL
        model_label = f"Google Gemini ({model})"
        has_key = bool(config.GEMINI_API_KEY)

    return {
        "provider": provider,
        "label": info.get("label", provider),
        "description": info.get("description", ""),
        "model": model,
        "model_label": model_label,
        "has_key": has_key,
        "ready": has_key,
    }
