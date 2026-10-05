"""
Project HER – Story Curator Agent
Uses LLM to generate compelling short stories optimised for viral short-form video.
Produces more candidates than needed so the Validator can filter.
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


# ── Data ──────────────────────────────────────────────

@dataclass
class StoryCandidate:
    """A single story idea produced by the Curator."""
    title: str
    hook: str                          # first 1-2 sentences (pattern interrupt)
    full_story: str                    # complete narration-ready text (~80-130 words)
    moral: str                         # takeaway / life lesson
    genre: str                         # drama, sci-fi, historical, fable, thriller, mythology, etc.
    tags: list[str] = field(default_factory=list)
    synopsis: str = ""                 # 2-3 sentence summary
    viral_angle: str = ""              # why this would work as short-form video
    target_emotion: str = "curiosity"  # primary emotion: curiosity, awe, shock, warmth, etc.


# ── Agent ─────────────────────────────────────────────

class StoryCuratorAgent:
    """
    Agent 1 in the daily pipeline.
    Generates N story candidates per batch, each optimised for short video.
    """

    GENRES = [
        "historical drama", "mythology retelling", "moral fable",
        "sci-fi thought experiment", "psychological thriller", "real-world mystery",
        "inspirational true story", "philosophical parable", "dark fairytale",
        "survival story", "heist / con", "cosmic horror lite",
        "underdog story", "twist ending", "cultural legend",
    ]

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        self.client, self.model = get_llm_client(provider=provider, model=model)

    def generate_batch(
        self,
        count: int = 7,
        avoid_titles: list[str] | None = None,
        avoid_synopses: list[str] | None = None,
        feedback: str = "",
        preferred_genres: list[str] | None = None,
    ) -> list[StoryCandidate]:
        """
        Generate a batch of story candidates.

        Args:
            count: How many candidates to generate (request more than needed).
            avoid_titles: Titles of previously published stories to avoid duplicating.
            avoid_synopses: Synopses of recent stories for duplicate detection.
            feedback: Optional feedback from the Validator on what to improve.
            preferred_genres: Optional list of genres to focus on.

        Returns:
            List of StoryCandidate objects.
        """
        logger.info("Curator: generating %d story candidates", count)

        prompt = self._build_prompt(
            count=count,
            avoid_titles=avoid_titles or [],
            avoid_synopses=avoid_synopses or [],
            feedback=feedback,
            preferred_genres=preferred_genres or [],
        )

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.9,  # high creativity
                max_tokens=4000,
            )
            raw = resp.choices[0].message.content.strip()
            candidates = self._parse_response(raw)
            logger.info("Curator: parsed %d candidates from LLM response", len(candidates))
            return candidates

        except Exception as e:
            logger.error("Curator failed: %s", e, exc_info=True)
            return []

    def generate_replacement(
        self,
        feedback: str,
        avoid_titles: list[str] | None = None,
        avoid_synopses: list[str] | None = None,
    ) -> list[StoryCandidate]:
        """Generate 1-2 replacement stories based on validator feedback."""
        return self.generate_batch(
            count=2,
            avoid_titles=avoid_titles,
            avoid_synopses=avoid_synopses,
            feedback=feedback,
        )

    # ── Prompts ───────────────────────────────────────

    def _system_prompt(self) -> str:
        return (
            "You are the world's best viral short-story writer for TikTok, YouTube Shorts, and Instagram Reels. "
            "You specialise in stories that are 80-130 words — short enough for a 50-60 second video. "
            "BREVITY IS EVERYTHING. Every word must earn its place. No filler, no padding. "
            "You tell complete, compelling stories in under 130 words — that's your superpower. "
            "Your stories go VIRAL because they: "
            "(1) Start with a hook that stops the scroll in 2 seconds. "
            "(2) Build tension quickly — no slow setup. "
            "(3) Have a satisfying twist or emotional payoff. "
            "(4) Leave viewers thinking about a deeper message. "
            "(5) Work across cultures — universal human themes. "
            "\n"
            "You draw from: mythology, real history, philosophy, science, folklore, and pure imagination. "
            "Your tone is cinematic, not academic. You write stories people RETELL to their friends. "
            "\n"
            "You always respond with a valid JSON array. No markdown, no extra text."
        )

    def _build_prompt(
        self,
        count: int,
        avoid_titles: list[str],
        avoid_synopses: list[str],
        feedback: str,
        preferred_genres: list[str],
    ) -> str:
        avoidance_block = ""
        if avoid_titles:
            titles_str = "\n".join(f"  - {t}" for t in avoid_titles[-30:])
            avoidance_block += f"\n\nALREADY PUBLISHED (DO NOT repeat or closely resemble these):\n{titles_str}"
        if avoid_synopses:
            synopses_str = "\n".join(f"  - {s[:120]}" for s in avoid_synopses[-20:])
            avoidance_block += f"\n\nRECENT STORY SYNOPSES (avoid similar plots):\n{synopses_str}"

        feedback_block = ""
        if feedback:
            feedback_block = (
                f"\n\nVALIDATOR FEEDBACK (the quality reviewer sent this back — address it):\n"
                f"{feedback}\n"
            )

        genre_block = ""
        if preferred_genres:
            genre_block = f"\n\nFOCUS ON THESE GENRES: {', '.join(preferred_genres)}"
        else:
            genre_block = (
                f"\n\nMIX GENRES from this list (use at least 3 different genres across your {count} stories): "
                f"{', '.join(self.GENRES)}"
            )

        return f"""Generate exactly {count} short stories for viral short-form video.

Each story must be:
- 80-130 words MAXIMUM (narration-ready — this text will be spoken aloud by TTS)
- This is CRITICAL: stories over 130 words will be REJECTED. Aim for 100-110 words.
- Written in a SPOKEN, conversational style (contractions, casual transitions, reactions)
- Start with an irresistible hook (the first line = the viewer's reason to stay)
- Have a clear dramatic arc: hook → tension → twist/climax → moral/resolution
- Include a moral, life lesson, or thought-provoking takeaway
- Be ORIGINAL — not a word-for-word retelling of a famous story
  (you can REIMAGINE myths/history in fresh ways, but add your unique spin)
- Keep it TIGHT: 8-12 sentences max. Every sentence must advance the story.
  If a sentence doesn't add tension, emotion, or plot — cut it.
{avoidance_block}
{feedback_block}
{genre_block}

Respond with a JSON array of {count} objects, each with these fields:
{{
  "title": "Compelling title (5-10 words)",
  "hook": "First 1-2 sentences — the scroll-stopper",
  "full_story": "Complete narration text, 80-130 words MAX, spoken style",
  "moral": "The takeaway / life lesson (1-2 sentences)",
  "genre": "One of: {', '.join(self.GENRES)}",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "synopsis": "2-3 sentence summary of the plot",
  "viral_angle": "Why this works as a short video (1 sentence)",
  "target_emotion": "Primary emotion: curiosity | awe | shock | warmth | dread | inspiration | wonder"
}}

IMPORTANT:
- Write the full_story as if speaking to camera — use "you", contractions, pauses (— / …)
- Make each story DIFFERENT in genre, setting, and tone
- The hook must be the kind of line that makes someone STOP scrolling
- Every story must have a clear TWIST or unexpected turn
- JSON only. No markdown, no code fences, no extra text."""

    # ── Parsing ───────────────────────────────────────

    def _parse_response(self, raw: str) -> list[StoryCandidate]:
        """Parse LLM JSON response into StoryCandidate objects."""
        # Strip markdown code fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*\n?", "", raw)
            raw = re.sub(r"\n?```\s*$", "", raw)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Try to find JSON array in the response
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    logger.error("Could not parse curator response as JSON")
                    return []
            else:
                logger.error("No JSON array found in curator response")
                return []

        if not isinstance(data, list):
            data = [data]

        candidates = []
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                candidates.append(StoryCandidate(
                    title=item.get("title", "Untitled"),
                    hook=item.get("hook", ""),
                    full_story=item.get("full_story", ""),
                    moral=item.get("moral", ""),
                    genre=item.get("genre", "general"),
                    tags=item.get("tags", []),
                    synopsis=item.get("synopsis", ""),
                    viral_angle=item.get("viral_angle", ""),
                    target_emotion=item.get("target_emotion", "curiosity"),
                ))
            except Exception as e:
                logger.warning("Skipping malformed story candidate: %s", e)
                continue

        # Post-filter: enforce word count limits
        MAX_WORDS = 140  # hard cap — allows slight overshoot from 130 target
        filtered = []
        for c in candidates:
            wc = len(c.full_story.split())
            if wc > MAX_WORDS:
                logger.warning(
                    "Trimming story '%s' — %d words exceeds %d limit",
                    c.title, wc, MAX_WORDS,
                )
                # Trim to ~MAX_WORDS by keeping first N sentences
                sentences = re.split(r'(?<=[.!?…])\s+', c.full_story)
                trimmed = []
                word_count = 0
                for sent in sentences:
                    sent_words = len(sent.split())
                    if word_count + sent_words > MAX_WORDS:
                        break
                    trimmed.append(sent)
                    word_count += sent_words
                c.full_story = " ".join(trimmed)
                logger.info("  Trimmed to %d words", len(c.full_story.split()))
            filtered.append(c)

        return filtered
