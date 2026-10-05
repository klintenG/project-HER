"""
Project HER – Metadata Generator Agent
Generates platform-specific titles, descriptions, hashtags, and thumbnails
for each finished video, optimised for each social media platform.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import config
from utils.llm_client import get_llm_client

logger = logging.getLogger(__name__)


@dataclass
class PlatformMeta:
    """Metadata tailored for a single platform."""
    platform: str                   # youtube_shorts, tiktok, instagram_reels, facebook, twitter
    title: str                      # platform-specific title
    description: str                # full description with CTAs
    hashtags: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)           # YouTube tags (different from hashtags)
    thumbnail_text: str = ""        # text overlay for thumbnail
    first_comment: str = ""         # auto-comment to boost engagement


@dataclass
class VideoMetadata:
    """Complete metadata package for one video across all platforms."""
    story_title: str
    story_synopsis: str
    platforms: dict[str, PlatformMeta] = field(default_factory=dict)


PLATFORM_SPECS = {
    "youtube_shorts": {
        "max_title": 100,
        "max_description": 5000,
        "max_hashtags": 15,
        "hashtag_style": "in_description",  # YouTube puts hashtags in description
        "tips": "First 2 lines of description show above 'Show more'. Use keywords. End with CTA.",
    },
    "tiktok": {
        "max_title": 150,  # TikTok caption
        "max_description": 2200,
        "max_hashtags": 8,
        "hashtag_style": "in_caption",
        "tips": "Caption IS the description. Keep it punchy. Hashtag mix: 3 broad + 3 niche + 2 trending.",
    },
    "instagram_reels": {
        "max_title": 0,  # no separate title on Reels
        "max_description": 2200,
        "max_hashtags": 30,
        "hashtag_style": "in_caption_or_comment",
        "tips": "First line = hook. Hashtags can go in first comment to keep caption clean.",
    },
    "facebook": {
        "max_title": 255,
        "max_description": 63206,
        "max_hashtags": 5,
        "hashtag_style": "in_description",
        "tips": "Facebook deprioritises hashtag spam. 3-5 relevant ones max. Ask a question to boost comments.",
    },
    "twitter": {
        "max_title": 0,  # tweet IS the caption
        "max_description": 280,
        "max_hashtags": 3,
        "hashtag_style": "in_tweet",
        "tips": "280 chars max. Be punchy. 1-3 hashtags. Thread potential for longer stories.",
    },
}

TARGET_PLATFORMS = list(PLATFORM_SPECS.keys())


class MetadataGeneratorAgent:
    """
    Agent 3 in the daily pipeline.
    Generates optimised metadata for each finished video, per platform.
    """

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        self.client, self.model = get_llm_client(provider=provider, model=model)

    def generate(
        self,
        story_title: str,
        story_synopsis: str,
        story_moral: str,
        story_genre: str,
        story_tags: list[str],
        platforms: list[str] | None = None,
    ) -> VideoMetadata:
        """
        Generate platform-specific metadata for one video.

        Returns:
            VideoMetadata with per-platform titles, descriptions, hashtags.
        """
        platforms = platforms or TARGET_PLATFORMS
        logger.info("Metadata: generating for '%s' across %d platforms", story_title, len(platforms))

        prompt = self._build_prompt(
            story_title, story_synopsis, story_moral, story_genre, story_tags, platforms
        )

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=3000,
            )
            raw = resp.choices[0].message.content.strip()
            return self._parse_response(raw, story_title, story_synopsis, platforms)

        except Exception as e:
            logger.error("Metadata generation failed: %s", e, exc_info=True)
            return self._fallback_metadata(story_title, story_synopsis, story_tags, platforms)

    # ── Prompts ───────────────────────────────────────

    def _system_prompt(self) -> str:
        return (
            "You are a social media growth expert who writes VIRAL video titles, descriptions, and hashtags. "
            "You know the algorithm of every platform intimately. "
            "Your titles get 3x more clicks than average. Your hashtag strategy maximises discoverability. "
            "Your descriptions hook readers AND satisfy platform algorithms. "
            "\n"
            "You always respond with valid JSON. No markdown, no extra text."
        )

    def _build_prompt(
        self,
        title: str,
        synopsis: str,
        moral: str,
        genre: str,
        tags: list[str],
        platforms: list[str],
    ) -> str:
        platform_reqs = ""
        for p in platforms:
            spec = PLATFORM_SPECS.get(p, {})
            platform_reqs += f"""
{p.upper()}:
  Max title: {spec.get('max_title', 100)} chars
  Max description: {spec.get('max_description', 2200)} chars
  Max hashtags: {spec.get('max_hashtags', 10)}
  Style: {spec.get('hashtag_style', 'in_description')}
  Tips: {spec.get('tips', '')}
"""

        return f"""Generate optimised metadata for this video across {len(platforms)} platforms.

VIDEO DETAILS:
  Title: {title}
  Genre: {genre}
  Synopsis: {synopsis}
  Moral/Takeaway: {moral}
  Content Tags: {', '.join(tags)}

PLATFORM REQUIREMENTS:
{platform_reqs}

Respond with a JSON object where each key is a platform name, containing:
{{
  "youtube_shorts": {{
    "title": "Clickable title under 100 chars — use curiosity gap or emotional hook",
    "description": "Full description with keywords, CTA, hashtags embedded",
    "hashtags": ["#story", "#viral", "#shorts"],
    "tags": ["story", "viral", "motivation", "short story"],
    "thumbnail_text": "Short punchy text for thumbnail overlay (5-8 words)",
    "first_comment": "Engagement-boosting first comment"
  }},
  "tiktok": {{ ... }},
  "instagram_reels": {{ ... }},
  "facebook": {{ ... }},
  "twitter": {{ ... }}
}}

TITLE RULES:
- YouTube: Curiosity gap ("She had 24 hours to save her kingdom — and no army")
- TikTok: Direct emotional punch + emoji ("This story broke me 💔")
- Instagram: Clean, aesthetic, with 1-2 emojis
- Facebook: Question or bold claim that triggers comments
- Twitter: Punchy, quotable, under 200 chars (leave room for hashtags)

HASHTAG RULES:
- Mix broad (#storytelling #viral) + niche (#mythologyretold #darkfairytale) + trending
- YouTube: Include as tags too (different from hashtags)
- Instagram: 20-30 relevant hashtags (mix sizes: 5 big + 10 medium + 10 small)
- TikTok: 5-8 focused hashtags
- Twitter: 1-3 only
- Facebook: 3-5 only

JSON only. No markdown."""

    # ── Parsing ───────────────────────────────────────

    def _parse_response(
        self,
        raw: str,
        story_title: str,
        story_synopsis: str,
        platforms: list[str],
    ) -> VideoMetadata:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*\n?", "", raw)
            raw = re.sub(r"\n?```\s*$", "", raw)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    logger.error("Could not parse metadata response")
                    return self._fallback_metadata(story_title, story_synopsis, [], platforms)
            else:
                logger.error("No JSON object in metadata response")
                return self._fallback_metadata(story_title, story_synopsis, [], platforms)

        meta = VideoMetadata(story_title=story_title, story_synopsis=story_synopsis)

        for platform in platforms:
            pdata = data.get(platform, {})
            if not pdata:
                # Try variations
                for key in data:
                    if platform.replace("_", "") in key.replace("_", "").replace(" ", "").lower():
                        pdata = data[key]
                        break

            meta.platforms[platform] = PlatformMeta(
                platform=platform,
                title=pdata.get("title", story_title),
                description=pdata.get("description", story_synopsis),
                hashtags=pdata.get("hashtags", []),
                tags=pdata.get("tags", []),
                thumbnail_text=pdata.get("thumbnail_text", ""),
                first_comment=pdata.get("first_comment", ""),
            )

        return meta

    def _fallback_metadata(
        self,
        title: str,
        synopsis: str,
        tags: list[str],
        platforms: list[str],
    ) -> VideoMetadata:
        """Basic fallback metadata if LLM fails."""
        meta = VideoMetadata(story_title=title, story_synopsis=synopsis)
        hashtags = [f"#{t.replace(' ', '')}" for t in tags[:5]] if tags else ["#story", "#viral"]

        for platform in platforms:
            meta.platforms[platform] = PlatformMeta(
                platform=platform,
                title=title,
                description=f"{synopsis}\n\n{' '.join(hashtags)}",
                hashtags=hashtags,
                tags=tags,
            )
        return meta
