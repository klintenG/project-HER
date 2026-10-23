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

from openai import (
    OpenAI,
    RateLimitError,
    APIStatusError,
    APITimeoutError,
    APIConnectionError,
    InternalServerError,
)

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
        max_retries=0,
    )

    # Wrap client with resilient retry, backoff, and model fallback
    gemini_fallbacks = []
    if base_url == config.GEMINI_BASE_URL:
        # Build fallback model chain for Gemini
        for candidate in ("gemini-flash-lite-latest", "gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3.8-flash"):
            if candidate != model_name and candidate not in gemini_fallbacks:
                gemini_fallbacks.append(candidate)

    client = _ResilientClient(
        primary=client,
        primary_model=model_name,
        fallback_models=gemini_fallbacks,
        groq_api_key=config.GROQ_API_KEY,
        groq_base_url=config.GROQ_BASE_URL,
        groq_model=config.GROQ_MODEL,
    )

    return client, model_name


class _ResilientCompletions:
    """Retries transient errors (503 high demand, 429 quota, 5xx, timeouts)

    with exponential backoff, and falls back to alternative Gemini models or Groq.
    """

    TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(
        self,
        primary: OpenAI,
        primary_model: str,
        fallback_models: list[str],
        groq_api_key: str = "",
        groq_base_url: str = "",
        groq_model: str = "",
    ):
        self._primary = primary
        self._primary_model = primary_model
        self._fallback_models = fallback_models
        self._groq_api_key = groq_api_key
        self._groq_base_url = groq_base_url
        self._groq_model = groq_model
        self._groq: Optional[OpenAI] = None

    def create(self, **kwargs):
        import time
        import random

        # Optional wall-clock budget across retries/models, not per attempt.
        budget = kwargs.pop("retry_budget_seconds", None)
        deadline = time.monotonic() + float(budget) if budget is not None else None
        def remaining():
            return None if deadline is None else deadline-time.monotonic()
        def bounded_kwargs(values):
            values=dict(values)
            if deadline is not None:
                left=remaining()
                if left<=0:
                    if last_error is not None:raise last_error
                    raise TimeoutError('LLM retry budget exhausted')
                timeout=values.get('timeout',left)
                values['timeout']=min(float(timeout),left) if isinstance(timeout,(int,float)) else left
            return values
        def backoff(seconds):
            time.sleep(seconds if deadline is None else max(0,min(seconds,remaining())))

        requested_model = kwargs.get("model") or self._primary_model
        # Construct model priority list starting with the requested model
        models_to_try = [requested_model]
        for m in self._fallback_models:
            if m not in models_to_try:
                models_to_try.append(m)

        last_error = None

        for model_idx, target_model in enumerate(models_to_try):
            call_kwargs = dict(kwargs)
            call_kwargs["model"] = target_model
            # For 503 high demand, retry up to 2 attempts before trying fallback model
            max_retries = 2 if len(models_to_try) > 1 else 3

            for attempt in range(max_retries):
                if deadline is not None and remaining()<=0:
                    if last_error is not None:raise last_error
                    raise TimeoutError("LLM retry budget exhausted")
                try:
                    return self._primary.chat.completions.create(**bounded_kwargs(call_kwargs))
                except (RateLimitError, APITimeoutError, APIConnectionError) as exc:
                    last_error = exc
                    wait_time = min(2.0 * (2 ** attempt) + random.uniform(0.2, 0.8), 8.0)
                    logger.warning(
                        "LLM transient error on model %s (%s). Retrying in %.1fs (attempt %d/%d)...",
                        target_model, exc, wait_time, attempt + 1, max_retries,
                    )
                    backoff(wait_time)
                except APIStatusError as exc:
                    last_error = exc
                    if exc.status_code in self.TRANSIENT_STATUS_CODES:
                        wait_time = min(2.0 * (2 ** attempt) + random.uniform(0.2, 0.8), 8.0)
                        logger.warning(
                            "LLM returned HTTP %d for model %s (%s). Retrying in %.1fs (attempt %d/%d)...",
                            exc.status_code, target_model, exc.message if hasattr(exc, "message") else exc,
                            wait_time, attempt + 1, max_retries,
                        )
                        backoff(wait_time)
                    elif exc.status_code == 404:
                        # Model not available / deprecated, immediately switch to next model
                        logger.warning(
                            "LLM model %s returned HTTP 404 (model not found/available). Switching to fallback...",
                            target_model,
                        )
                        break
                    else:
                        raise

            # If retries exhausted for this Gemini model, log and try next model
            if model_idx < len(models_to_try) - 1:
                next_model = models_to_try[model_idx + 1]
                logger.warning(
                    "Gemini model '%s' unavailable after %d attempts. Falling back to alternative model '%s'...",
                    target_model, max_retries, next_model,
                )

        # If all Gemini models failed, fall back to Groq if available
        if self._groq_api_key:
            logger.warning("All Gemini models unavailable. Falling back to Groq (%s)...", self._groq_model)
            try:
                if self._groq is None:
                    self._groq = OpenAI(api_key=self._groq_api_key, base_url=self._groq_base_url)
                groq_kwargs = dict(kwargs)
                groq_kwargs["model"] = self._groq_model
                return self._groq.chat.completions.create(**bounded_kwargs(groq_kwargs))
            except Exception as groq_exc:
                logger.error("Groq fallback also failed: %s", groq_exc)
                if last_error:
                    raise last_error from groq_exc
                raise

        if last_error:
            raise last_error
        raise RuntimeError("LLM request failed with no error details.")


class _ResilientChat:
    def __init__(self, completions: _ResilientCompletions, primary_chat):
        self.completions = completions
        self._primary_chat = primary_chat

    def __getattr__(self, name):
        return getattr(self._primary_chat, name)


class _ResilientClient:
    """Drop-in replacement for OpenAI client with retry & fallback."""

    def __init__(
        self,
        primary: OpenAI,
        primary_model: str,
        fallback_models: list[str],
        groq_api_key: str = "",
        groq_base_url: str = "",
        groq_model: str = "",
    ):
        self._primary = primary
        completions = _ResilientCompletions(
            primary=primary,
            primary_model=primary_model,
            fallback_models=fallback_models,
            groq_api_key=groq_api_key,
            groq_base_url=groq_base_url,
            groq_model=groq_model,
        )
        self.chat = _ResilientChat(completions, primary.chat)

    def __getattr__(self, name):
        return getattr(self._primary, name)


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
