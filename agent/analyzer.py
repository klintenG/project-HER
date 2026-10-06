"""
Project HER v2.0 – Content Analyzer
Uses LLM to extract key points, generate hooks, detect content type,
and structure narrative arcs for maximum engagement.
Supports multiple LLM providers: Groq (free) and GitHub Models (Copilot).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from openai import OpenAI

import config
from agent.scraper import ArticleData
from utils.llm_client import get_llm_client

logger = logging.getLogger(__name__)


@dataclass
class KeyPoint:
    """A single key point / scene extracted from the article."""
    index: int
    headline: str
    narration: str
    visual_query: str
    duration: float = 0.0
    emotion: str = ""  # emotional tag for the scene


@dataclass
class AnalysisResult:
    """Output of content analysis."""
    title: str
    key_points: list[KeyPoint] = field(default_factory=list)
    tone: str = "informative"
    summary: str = ""
    source_url: Optional[str] = None
    hook: str = ""  # attention-grabbing opening line
    content_type: str = "general"  # news / story / tutorial / opinion / general
    mood: str = "neutral"  # suggested music mood
    cta: str = ""  # call-to-action for outro


class ContentAnalyzer:
    """
    Analyzes article content and extracts structured key points using an LLM.
    
    v2.0 enhancements:
    - Hook generation for attention-grabbing openers
    - Content type detection (news, story, tutorial, opinion)
    - Narrative arc structuring (setup → conflict → resolution)
    - Emotional tagging per scene for visual/audio mood matching
    - Retry logic with exponential backoff
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None,
                 provider: Optional[str] = None):
        self.client, self.model = get_llm_client(provider=provider, model=model)

    def analyze(
        self,
        article: ArticleData,
        tone: str = "informative",
        num_points: Optional[int] = None,
    ) -> AnalysisResult:
        """
        Analyze an article and extract key points with hooks and narrative arc.

        Returns:
            AnalysisResult with structured key points, hook, content type, and mood.
        """
        if num_points is None:
            word_count = article.word_count
            if word_count < 200:
                num_points = 3
            elif word_count < 500:
                num_points = 4
            elif word_count < 1000:
                num_points = 5
            else:
                num_points = 6

        num_points = max(config.MIN_KEY_POINTS, min(config.MAX_KEY_POINTS, num_points))

        tone_instruction = config.TONE_PRESETS.get(tone, config.TONE_PRESETS["informative"])

        prompt = self._build_prompt(article, tone_instruction, num_points)
        result = self._call_llm_with_retry(prompt)

        # Build key points with emotion tags
        key_points = []
        for i, kp in enumerate(result.get("key_points", [])):
            key_points.append(KeyPoint(
                index=i,
                headline=kp["headline"],
                narration=kp["narration"],
                visual_query=kp["visual_query"],
                emotion=kp.get("emotion", "neutral"),
            ))

        return AnalysisResult(
            title=result.get("title", article.title),
            key_points=key_points,
            tone=tone,
            summary=result.get("summary", ""),
            source_url=article.source_url,
            hook=result.get("hook", ""),
            content_type=result.get("content_type", "general"),
            mood=result.get("mood", "neutral"),
            cta=result.get("cta", ""),
        )

    def _build_prompt(
        self, article: ArticleData, tone_instruction: str, num_points: int
    ) -> str:
        """Build the enhanced LLM prompt with hook and narrative arc."""

        # Process article text in chunks for long articles
        article_text = article.text
        if len(article_text) > 6000:
            # Take beginning and end for context
            article_text = article_text[:4000] + "\n\n[...]\n\n" + article_text[-1500:]

        topic_directive = ""
        if article.word_count < 50:
            topic_directive = """
TOPIC PROMPT DIRECTIVE:
The user provided a concise topic prompt rather than a full article.
Expand this topic into 3 captivating scenes from scratch, covering the background, main conflict/breakthrough, and takeaway.
"""

        return f"""You just read something fascinating and you're turning it into a short video script.
Your job is NOT to summarize the article — it's to RETELL the story the way a real human would tell a friend.

ARTICLE TITLE: {article.title}

ARTICLE TEXT:
{article_text}

TONE INSTRUCTION: {tone_instruction}
{topic_directive}

═══════════════════════════════════════════════════════
HUMAN NARRATION STYLE — THE MOST IMPORTANT SECTION
═══════════════════════════════════════════════════════

Every "narration" field is what will be SPOKEN ALOUD in the video.
Write it exactly how a person talks — not how a journalist writes:

✓ ALWAYS use contractions: "it's", "didn't", "they're", "wouldn't", "here's", "that's"
✓ Use casual spoken transitions:
  - "So here's the thing…"
  - "And honestly? Nobody saw this coming."
  - "Okay, but wait—"
  - "Now, this is where it gets really interesting."
  - "Which… yeah. That changes everything."
✓ React to the material like a real person:
  - "That's actually kind of insane when you think about it."
  - "I know — it sounds made up. But it's not."
  - "Wild, right?"
✓ Use rhythm: a longer sentence, then a SHORT punch. Then a question.
  Example: "For over two hundred years, this diamond passed through the hands of emperors,
  warlords, and colonial governors. And nobody questioned it. Not once."
✓ Use "you" to pull the viewer in: "You'd think someone would've noticed, right?"
✓ Use sentence fragments for emphasis: "Gone. Just like that."
✓ Add pauses with em dashes and ellipses: "And then — silence."

✗ NEVER write like a textbook: "The significance of this event cannot be overstated."
✗ NEVER write like a press release: "This groundbreaking development represents…"
✗ NEVER write clinical summaries: "The article discusses the impact of…"
✗ NEVER use formal connectors: "Furthermore", "Moreover", "Additionally", "In conclusion"
✗ NEVER start with "This" referring to an abstract concept
✗ NEVER use passive voice when active is possible

If the narration could appear in a school essay, you MUST rewrite it.
The viewer should feel like they're hearing a STORY from a friend.

═══════════════════════════════════════════════════════
CONTENT RULES
═══════════════════════════════════════════════════════

1. Create a "hook" — the FIRST sentence shown in the video (first 3 seconds).
   CRITICAL HOOK RULES:
   - NEVER start with "Did you know" or a generic question.
   - NEVER start with a definition.
   - START MID-THOUGHT — drop the viewer into the middle of a conclusion.
     Good: "They found it buried 40 feet underground.",
     "She was 14 when she changed the entire industry.", "This was banned in 38 countries."
   - Max 12 words. Pattern disruptor, not a question.

2. Detect content type: "news", "story", "tutorial", "opinion", or "general".

3. Suggest a music mood: "upbeat", "dramatic", "calm", "suspenseful", "playful", "inspirational", or "neutral".

4. Create exactly {num_points} key points as a DELAYED-REVEAL NARRATIVE ARC:
   - Point 1: DISORIENTING HOOK — Start with the conclusion or most shocking element.
   - Points 2-{max(2, num_points-2)}: PROGRESSIVE REVELATION — Unveil context piece by piece.
     Each answers ONE question while raising ANOTHER.
   - Point {num_points-1}: TWIST OR ESCALATION — The "wait, it gets crazier" moment.
   - Point {num_points}: PAYOFF + OPEN LOOP — Resolve the thread but plant a seed.

5. For each key point:
   - "headline": SHORT on-screen text (max 6 words, punchy)
   - "narration": 1-2 SPOKEN sentences (15-30 words, written exactly as someone would SAY it)
   - "visual_query": descriptive image search query
   - "emotion": one of "curious", "excited", "serious", "hopeful", "dramatic", "playful", "calm"

6. The narration must flow as a STORY with momentum, NOT a list of facts.
7. Combined narration: 25-35 seconds when spoken at normal pace.
8. Stay factually accurate — don't invent information, just retell it in human words.
9. Title: catchy, 4-8 words, thumbnail-worthy. Prefer incomplete phrases.
10. CTA: a cliffhanger that teases a follow-up or asks a real question.
    Good: "Part 2 reveals the worst part…", "Which detail shocked you most?"
    Bad: "Follow for more!", "Like and subscribe!"

Respond ONLY with valid JSON in this exact format:
{{
    "title": "Catchy Video Title Here",
    "hook": "They found it buried 40 feet underground.",
    "content_type": "news",
    "mood": "dramatic",
    "cta": "Part 2 reveals the worst part…",
    "summary": "One-sentence summary of the article",
    "key_points": [
        {{
            "headline": "Short Headline",
            "narration": "Engaging, spoken-aloud narration that sounds like a real person talking.",
            "visual_query": "descriptive image search query",
            "emotion": "curious"
        }}
    ]
}}"""

    def _call_llm_with_retry(self, prompt: str) -> dict:
        """Call the LLM with exponential backoff retry logic."""
        last_error = None

        for attempt in range(config.MAX_RETRIES):
            try:
                return self._call_llm(prompt)
            except Exception as e:
                last_error = e
                if attempt < config.MAX_RETRIES - 1:
                    wait = config.RETRY_BACKOFF ** attempt
                    logger.warning(
                        "LLM call failed (attempt %d/%d): %s. Retrying in %.1fs...",
                        attempt + 1, config.MAX_RETRIES, e, wait,
                    )
                    time.sleep(wait)
                else:
                    logger.error("LLM call failed after %d attempts: %s", config.MAX_RETRIES, e)

        raise RuntimeError(f"LLM failed after {config.MAX_RETRIES} attempts: {last_error}")

    def _call_llm(self, prompt: str) -> dict:
        """Call the LLM API and parse the JSON response."""
        logger.info("Calling LLM (%s) via %s for content analysis...", self.model, config.LLM_PROVIDER)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": (
                        "You are a gifted storyteller who turns articles into spoken-word video scripts. "
                        "You write like a real person TALKS — casual, vivid, emotionally honest. "
                        "Use contractions (don't, it's, they'd). React to the material ('That's wild.', 'I know, right?'). "
                        "Vary your rhythm: long sentence, then a short punch. A question, then a blunt answer. "
                        "Never sound like a textbook, press release, or Wikipedia summary. "
                        "Sound like a person who just found out something incredible and can't wait to tell someone. "
                        "Always respond with valid JSON only. No markdown. No extra text."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=config.LLM_TEMPERATURE,
            max_tokens=config.LLM_MAX_TOKENS,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content.strip()
        logger.debug("LLM raw response: %s", content[:500])

        # Strip markdown code fences if wrapped
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

        result = json.loads(content)

        # Validate structure
        if "key_points" not in result or not result["key_points"]:
            raise ValueError("LLM response missing 'key_points'")

        for kp in result["key_points"]:
            if not all(k in kp for k in ("headline", "narration", "visual_query")):
                raise ValueError(f"Key point missing required fields: {kp}")

        logger.info(
            "Content analysis complete: %d key points, hook='%s', type=%s, mood=%s",
            len(result["key_points"]),
            result.get("hook", "")[:50],
            result.get("content_type", "?"),
            result.get("mood", "?"),
        )
        return result
