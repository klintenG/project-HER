"""
Project HER v2.0 – AI Image Generator (Claymorphism Mode)
Generates AI images using Replicate (primary, paid, unlimited)
with HuggingFace + Pollinations.ai as free fallbacks.
All prompts are augmented with Claymorphism style directives.

Providers (priority order):
  • Replicate  – FLUX Schnell/Pro via API ($0.003–$0.04/image, unlimited)
  • HuggingFace – FLUX.1-schnell via Inference API (free HF token required)
  • Pollinations – URL-based generation (no key, less reliable)
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import logging
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx
try:
    import replicate as replicate_sdk
except ImportError:
    replicate_sdk = None

import config
from agent.story_splitter import ScreenSegment

logger = logging.getLogger("ai_visuals")


# ── Data Classes ──────────────────────────────────────

@dataclass
class AIImageAsset:
    """An AI-generated image for a screen segment."""
    screen_index: int
    local_path: Path
    prompt: str
    sub_index: int = 0   # for multi_image screens (0, 1, 2, ...)
    width: int = 1024
    height: int = 1024


# ── AI Image Generator ───────────────────────────────

class AIImageGenerator:
    """
    Generates images via Replicate (primary, paid, unlimited),
    HuggingFace (free fallback), or Pollinations.ai (final fallback)
    with Claymorphism style.

    Enhanced mode (Generate tab): 9:16 portrait images with negative prompts.
    Kids Story mode: original 1024×1024 square images.
    """

    def __init__(self, provider: str = "", visual_style: str = "", portrait_mode: bool = False):
        self.provider = provider or config.AI_IMAGE_PROVIDER
        self.portrait_mode = portrait_mode
        if portrait_mode and getattr(config, 'ENHANCED_IMAGE_PORTRAIT', False):
            self.width = getattr(config, 'AI_IMAGE_PORTRAIT_WIDTH', 768)
            self.height = getattr(config, 'AI_IMAGE_PORTRAIT_HEIGHT', 1344)
        else:
            self.width = config.AI_IMAGE_WIDTH
            self.height = config.AI_IMAGE_HEIGHT
        self.timeout = config.AI_IMAGE_TIMEOUT
        self.max_retries = config.AI_IMAGE_MAX_RETRIES
        self._concurrency = config.AI_IMAGE_CONCURRENT

        # Resolve visual style and its prompt suffix
        self.visual_style = visual_style or config.DEFAULT_VISUAL_STYLE
        vs_config = config.VISUAL_STYLES.get(self.visual_style, {})
        self.style_suffix = vs_config.get(
            "image_prompt_suffix",
            config.CLAY_IMAGE_STYLE_SUFFIX,
        )

        # Replicate settings (paid, primary)
        self.replicate_token = config.REPLICATE_API_TOKEN
        self.replicate_model = (
            config.REPLICATE_SCHNELL_MODEL
            if config.REPLICATE_USE_SCHNELL
            else config.REPLICATE_MODEL
        )

        # HuggingFace settings (free fallback)
        self.hf_token = config.HF_API_TOKEN
        self.hf_model = config.HF_IMAGE_MODEL
        self.hf_api_url = config.HF_IMAGE_API_URL

        # Pollinations settings (final fallback)
        self.pollinations_url = config.AI_IMAGE_BASE_URL
        self.pollinations_model = config.AI_IMAGE_POLLINATIONS_MODEL

        # Early-abort flags
        self._hf_credits_depleted = False

        # Auto-select provider with cascading fallback
        if self.provider == "replicate" and not self.replicate_token:
            logger.warning(
                "REPLICATE_API_TOKEN not set — falling back to HuggingFace. "
                "Get a token at https://replicate.com/account/api-tokens"
            )
            self.provider = "huggingface"

        if self.provider == "huggingface" and not self.hf_token:
            logger.warning(
                "HF_API_TOKEN not set — falling back to Pollinations.ai. "
                "Get a free token at https://huggingface.co/settings/tokens"
            )
            self.provider = "pollinations"

        logger.info("AI image provider: %s", self.provider)

    # ── Public API ────────────────────────────────────

    def generate_images(
        self,
        screens: list[ScreenSegment],
        output_dir: Path,
    ) -> list[AIImageAsset]:
        """
        Generate AI images for all screens that need them.
        Returns list of AIImageAsset with downloaded image paths.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Collect generation tasks
        tasks: list[dict] = []
        for screen in screens:
            if screen.visual_type == "image" and screen.image_prompt:
                tasks.append({
                    "screen_index": screen.index,
                    "prompt": screen.image_prompt,
                    "sub_index": 0,
                })
            elif screen.visual_type == "multi_image" and screen.image_prompts:
                for j, prompt in enumerate(screen.image_prompts):
                    tasks.append({
                        "screen_index": screen.index,
                        "prompt": prompt,
                        "sub_index": j,
                    })

        if not tasks:
            logger.warning("No image generation tasks found")
            return []

        provider_label = {
            "replicate": f"Replicate ({self.replicate_model.split('/')[-1]})",
            "huggingface": f"HuggingFace ({self.hf_model.split('/')[-1]})",
            "pollinations": "Pollinations.ai",
        }.get(self.provider, self.provider)
        logger.info("Generating %d AI images via %s", len(tasks), provider_label)
        start = time.time()

        results = asyncio.run(self._generate_all(tasks, output_dir))

        elapsed = time.time() - start
        success = [r for r in results if r is not None]
        logger.info(
            "Generated %d/%d images in %.1fs",
            len(success), len(tasks), elapsed,
        )
        return success

    # ── Async Engine ──────────────────────────────────

    async def _generate_all(
        self, tasks: list[dict], output_dir: Path
    ) -> list[Optional[AIImageAsset]]:
        """Generate all images with concurrency control."""
        # Create semaphore inside the running loop (Python 3.9 compat)
        self.semaphore = asyncio.Semaphore(self._concurrency)

        # Configure Replicate SDK token if using Replicate
        if self.provider == "replicate" and self.replicate_token:
            import os
            os.environ["REPLICATE_API_TOKEN"] = self.replicate_token

        headers = {}
        if self.provider == "huggingface":
            headers["Authorization"] = f"Bearer {self.hf_token}"

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout, connect=30.0),
            follow_redirects=True,
            headers=headers,
        ) as client:
            coros = [
                self._generate_one(client, task, output_dir)
                for task in tasks
            ]
            return await asyncio.gather(*coros, return_exceptions=False)

    async def _generate_one(
        self,
        client: httpx.AsyncClient,
        task: dict,
        output_dir: Path,
    ) -> Optional[AIImageAsset]:
        """Generate a single image with retry logic + cascading fallback."""
        async with self.semaphore:
            prompt = task["prompt"]
            screen_idx = task["screen_index"]
            sub_idx = task["sub_index"]

            # Build Claymorphism-styled prompt
            styled_prompt = self._build_styled_prompt(prompt)

            # Output filename
            prompt_hash = hashlib.md5(styled_prompt.encode()).hexdigest()[:8]
            filename = f"ai_img_{screen_idx}_{sub_idx}_{prompt_hash}.png"
            filepath = output_dir / filename

            # Check cache
            if filepath.exists() and filepath.stat().st_size > 1000:
                logger.info("  [%d.%d] Using cached: %s", screen_idx, sub_idx, filename)
                return AIImageAsset(
                    screen_index=screen_idx,
                    local_path=filepath,
                    prompt=prompt,
                    sub_index=sub_idx,
                    width=self.width,
                    height=self.height,
                )

            # Build fallback chain based on primary provider
            fallback_chain = self._build_fallback_chain()

            for provider in fallback_chain:
                # Skip HuggingFace if credits depleted
                if provider == "huggingface" and self._hf_credits_depleted:
                    logger.info(
                        "  [%d.%d] HF credits depleted — skipping",
                        screen_idx, sub_idx,
                    )
                    continue

                result = await self._try_provider(
                    client, provider, styled_prompt,
                    screen_idx, sub_idx, filepath,
                )
                if result:
                    return result

                # Log fallback
                logger.info(
                    "  [%d.%d] %s failed — trying next fallback",
                    screen_idx, sub_idx, provider,
                )

            logger.error(
                "  [%d.%d] All providers failed for: %s",
                screen_idx, sub_idx, prompt[:50],
            )
            return None

    def _build_fallback_chain(self) -> list[str]:
        """Build ordered list of providers to try."""
        all_providers = ["replicate", "huggingface", "pollinations"]
        # Start with the selected provider, then try the rest in order
        chain = [self.provider]
        for p in all_providers:
            if p not in chain:
                # Skip replicate in fallback if no token
                if p == "replicate" and not self.replicate_token:
                    continue
                # Skip huggingface in fallback if no token
                if p == "huggingface" and not self.hf_token:
                    continue
                chain.append(p)
        return chain

    async def _try_provider(
        self,
        client: httpx.AsyncClient,
        provider: str,
        styled_prompt: str,
        screen_idx: int,
        sub_idx: int,
        filepath: Path,
    ) -> Optional[AIImageAsset]:
        """Attempt image generation with a specific provider.

        Rate-limit-aware: when Replicate returns 429, parses the retry
        delay from the error message and waits accordingly instead of
        giving up after 3 fast retries.
        """
        # Use more retries for rate-limited providers (Replicate 429 with burst=1)
        max_attempts = self.max_retries + 4  # 7 total — enough for ~10s resets

        for attempt in range(1, max_attempts + 1):
            # Abort immediately if HF credits depleted mid-retry
            if provider == "huggingface" and self._hf_credits_depleted:
                logger.info(
                    "  [%d.%d] HF credits depleted — aborting retries",
                    screen_idx, sub_idx,
                )
                return None

            try:
                logger.info(
                    "  [%d.%d] %s attempt %d: %s",
                    screen_idx, sub_idx, provider, attempt,
                    styled_prompt[:55] + ("..." if len(styled_prompt) > 55 else ""),
                )

                if provider == "huggingface":
                    image_bytes = await self._call_huggingface(
                        client, styled_prompt
                    )
                elif provider == "replicate":
                    image_bytes = await self._call_replicate(
                        client, styled_prompt
                    )
                else:
                    image_bytes = await self._call_pollinations(
                        client, styled_prompt
                    )

                if image_bytes and len(image_bytes) > 1000:
                    filepath.write_bytes(image_bytes)
                    logger.info(
                        "  [%d.%d] Saved: %s (%d KB) via %s",
                        screen_idx, sub_idx, filepath.name,
                        len(image_bytes) // 1024, provider,
                    )
                    return AIImageAsset(
                        screen_index=screen_idx,
                        local_path=filepath,
                        prompt=styled_prompt,
                        sub_index=sub_idx,
                        width=self.width,
                        height=self.height,
                    )
                else:
                    logger.warning(
                        "  [%d.%d] %s returned empty/tiny response on attempt %d",
                        screen_idx, sub_idx, provider, attempt,
                    )

            except Exception as e:
                error_msg = str(e)
                logger.warning(
                    "  [%d.%d] %s error (attempt %d): %s",
                    screen_idx, sub_idx, provider, attempt, e,
                )

                # Rate-limit-aware backoff for Replicate 429
                if provider == "replicate" and "429" in error_msg:
                    # Parse retry delay from error: "resets in ~Ns"
                    retry_wait = 12  # safe default
                    import re as _re
                    m = _re.search(r"resets in ~(\d+)s", error_msg)
                    if m:
                        retry_wait = int(m.group(1)) + 2  # add buffer
                    logger.info(
                        "  [%d.%d] Replicate rate-limited — waiting %ds before retry",
                        screen_idx, sub_idx, retry_wait,
                    )
                    if attempt < max_attempts:
                        await asyncio.sleep(retry_wait)
                    continue

            # Standard back off before retry (non-429 errors)
            if attempt < max_attempts:
                await asyncio.sleep(2 * attempt)

        return None

    # ── Replicate API (Primary, Paid) ───────────────────

    async def _call_replicate(
        self,
        client: httpx.AsyncClient,
        prompt: str,
    ) -> Optional[bytes]:
        """
        Call Replicate API for image generation using FLUX models via REST API.
        Creates a prediction and polls for completion, avoiding SDK socket timeouts.
        Returns raw image bytes.
        """
        aspect = "9:16" if self.portrait_mode else "1:1"
        headers = {
            "Authorization": f"Bearer {self.replicate_token}",
            "Content-Type": "application/json",
        }
        create_url = f"https://api.replicate.com/v1/models/{self.replicate_model}/predictions"
        payload = {
            "input": {
                "prompt": prompt,
                "num_outputs": 1,
                "aspect_ratio": aspect,
                "output_format": "png",
                "output_quality": 90,
            }
        }

        try:
            # 1. Create prediction
            create_resp = await client.post(create_url, headers=headers, json=payload, timeout=20.0)
            if create_resp.status_code not in (200, 201, 202):
                logger.warning("  Replicate create prediction HTTP %d: %s", create_resp.status_code, create_resp.text[:120])
                return None

            data = create_resp.json()
            pred_id = data.get("id")
            if not pred_id:
                logger.warning("  Replicate returned no prediction ID")
                return None

            poll_url = f"https://api.replicate.com/v1/predictions/{pred_id}"

            # 2. Poll until finished (up to 45 seconds)
            for _ in range(30):
                await asyncio.sleep(1.5)
                poll_resp = await client.get(poll_url, headers=headers, timeout=15.0, follow_redirects=True)
                if poll_resp.status_code != 200:
                    continue
                poll_data = poll_resp.json()
                status = poll_data.get("status")
                if status == "succeeded":
                    output = poll_data.get("output")
                    if isinstance(output, list) and output:
                        image_url = str(output[0])
                    elif hasattr(output, "url"):
                        image_url = output.url
                    else:
                        image_url = str(output)

                    # 3. Download the image bytes (follow redirect for R2/S3 signed URLs)
                    img_resp = await client.get(image_url, timeout=30.0, follow_redirects=True)
                    if img_resp.status_code == 200 and len(img_resp.content) > 1000:
                        return img_resp.content
                    else:
                        logger.warning("  Replicate image download failed: HTTP %d (size: %d)", img_resp.status_code, len(img_resp.content))
                    break
                elif status in ("failed", "canceled"):
                    logger.warning("  Replicate prediction %s %s: %s", pred_id, status, poll_data.get("error"))
                    return None

            logger.warning("  Replicate prediction %s timed out polling", pred_id)
            return None

        except Exception as e:
            error_msg = str(e)
            logger.warning("  Replicate API error: %s", error_msg)
            raise

    # ── HuggingFace Inference API ─────────────────────

    async def _call_huggingface(
        self,
        client: httpx.AsyncClient,
        prompt: str,
    ) -> Optional[bytes]:
        """
        Call HuggingFace Inference API for image generation.
        POST https://api-inference.huggingface.co/models/{model}
        Body: {"inputs": "prompt"}
        Returns raw image bytes.
        """
        url = f"{self.hf_api_url}{self.hf_model}"

        resp = await client.post(
            url,
            json={"inputs": prompt},
        )

        # Handle model loading (503 = model is loading)
        if resp.status_code == 503:
            body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            wait_time = body.get("estimated_time", 30)
            logger.info(
                "  HuggingFace model loading, waiting %.0fs...",
                min(wait_time, 60),
            )
            await asyncio.sleep(min(wait_time, 60))
            # Retry once after model loads
            resp = await client.post(
                url,
                json={"inputs": prompt},
            )

        if resp.status_code == 200:
            content_type = resp.headers.get("content-type", "")
            if "image" in content_type:
                return resp.content
            else:
                logger.warning(
                    "  HuggingFace returned non-image: %s (%d bytes)",
                    content_type, len(resp.content),
                )
                return None

        # Log error details
        error_msg = ""
        try:
            err_body = resp.json()
            error_msg = err_body.get("error", str(err_body))
        except Exception:
            error_msg = resp.text[:200]

        logger.warning(
            "  HuggingFace HTTP %d: %s", resp.status_code, error_msg
        )

        # 402 = credits depleted — set flag to skip ALL remaining HF requests
        if resp.status_code == 402:
            self._hf_credits_depleted = True
            logger.error(
                "  HuggingFace credits DEPLETED — all remaining images "
                "will use Pollinations fallback only"
            )

        return None

    # ── Pollinations.ai (Fallback) ────────────────────

    async def _call_pollinations(
        self,
        client: httpx.AsyncClient,
        prompt: str,
    ) -> Optional[bytes]:
        """
        Call Pollinations.ai for image generation (no API key).
        GET https://image.pollinations.ai/prompt/{encoded_prompt}?params
        Returns raw image bytes.
        """
        encoded = urllib.parse.quote(prompt, safe="")
        url = (
            f"{self.pollinations_url}/{encoded}"
            f"?width={self.width}"
            f"&height={self.height}"
            f"&model={self.pollinations_model}"
            f"&nologo=true"
            f"&seed={hash(prompt) % 100000}"
        )

        resp = await client.get(url)

        if resp.status_code == 200:
            content_type = resp.headers.get("content-type", "")
            if "image" in content_type:
                return resp.content
            else:
                logger.warning(
                    "  Pollinations returned non-image: %s (%d bytes)",
                    content_type, len(resp.content),
                )
                return None

        logger.warning("  Pollinations HTTP %d", resp.status_code)
        return None

    # ── Prompt Engineering ────────────────────────────

    def _build_styled_prompt(self, raw_prompt: str) -> str:
        """Augment a raw image prompt with the active visual style suffix."""
        cleaned = raw_prompt.strip().rstrip(".")
        styled = f"{cleaned}, {self.style_suffix}"
        # Add negative prompt guidance for enhanced pipeline
        if self.portrait_mode:
            neg = getattr(config, 'AI_IMAGE_NEGATIVE_PROMPT', '')
            if neg:
                styled += f". Avoid: {neg}"
        return styled


# ── Utility ───────────────────────────────────────────

def generate_ai_images(
    screens: list[ScreenSegment],
    output_dir: Path,
    visual_style: str = "",
    portrait_mode: bool = False,
) -> list[AIImageAsset]:
    """Convenience function for generating AI images."""
    generator = AIImageGenerator(visual_style=visual_style, portrait_mode=portrait_mode)
    return generator.generate_images(screens, output_dir)
