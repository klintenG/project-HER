"""
Project HER – Story Validator Agent
Reviews story candidates for quality, originality, and virality.
Approves or rejects with actionable feedback.
Checks against published history to prevent duplicates.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import config
from utils.llm_client import get_llm_client
from automation.story_curator import StoryCandidate

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validating a single story candidate."""
    story_title: str
    approved: bool
    score: float = 0.0            # 0-10 overall score
    scores: dict = field(default_factory=dict)  # detailed breakdown
    feedback: str = ""            # actionable feedback if rejected
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    is_duplicate: bool = False
    duplicate_of: str = ""        # title of the story it's too similar to


class StoryValidatorAgent:
    """
    Agent 2 in the daily pipeline.
    Reviews each story candidate on multiple criteria and returns
    APPROVE / REJECT with detailed feedback.
    """

    APPROVAL_THRESHOLD = 6.5  # minimum score to approve (out of 10)

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        self.client, self.model = get_llm_client(provider=provider, model=model)

    def validate_batch(
        self,
        candidates: list[StoryCandidate],
        history_summary: str = "",
    ) -> list[ValidationResult]:
        """
        Validate a batch of story candidates.

        Args:
            candidates: Stories to review.
            history_summary: Text summary of recently published stories (for duplicate detection).

        Returns:
            List of ValidationResult, one per candidate.
        """
        logger.info("Validator: reviewing %d candidates", len(candidates))

        # Validate in a single LLM call for efficiency
        prompt = self._build_batch_prompt(candidates, history_summary)

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,  # low temp for consistent judgment
                max_tokens=4000,
            )
            raw = resp.choices[0].message.content.strip()
            results = self._parse_response(raw, candidates)
            
            approved_count = sum(1 for r in results if r.approved)
            logger.info(
                "Validator: %d/%d approved (threshold=%.1f)",
                approved_count, len(results), self.APPROVAL_THRESHOLD,
            )
            return results

        except Exception as e:
            logger.error("Validator failed: %s", e, exc_info=True)
            # On failure, approve all (let the pipeline continue)
            return [
                ValidationResult(
                    story_title=c.title,
                    approved=True,
                    score=5.0,
                    feedback="Validation failed — auto-approved",
                )
                for c in candidates
            ]

    def get_rejection_feedback(self, results: list[ValidationResult]) -> str:
        """
        Compile feedback from all rejected stories into a single
        prompt for the Curator to generate replacements.
        """
        rejected = [r for r in results if not r.approved]
        if not rejected:
            return ""

        lines = ["The following stories were rejected. Generate BETTER replacements:\n"]
        for r in rejected:
            lines.append(f"REJECTED: \"{r.story_title}\" (score: {r.score}/10)")
            if r.weaknesses:
                lines.append(f"  Problems: {'; '.join(r.weaknesses)}")
            if r.feedback:
                lines.append(f"  Feedback: {r.feedback}")
            if r.is_duplicate:
                lines.append(f"  ⚠ Too similar to: \"{r.duplicate_of}\"")
            lines.append("")

        lines.append(
            "Create stories that AVOID these problems. "
            "Make them more original, more dramatic, with stronger hooks and clearer morals."
        )
        return "\n".join(lines)

    # ── Prompts ───────────────────────────────────────

    def _system_prompt(self) -> str:
        return (
            "You are a ruthless but fair content quality reviewer for a viral short-form video channel. "
            "Your job is to decide which stories are WORTH producing as 50-60 second videos. "
            "CRITICAL LENGTH RULE: Stories MUST be 80-130 words. Stories over 140 words are TOO LONG "
            "and must be rejected with feedback to cut them shorter. Aim for ~100-110 words. "
            "You've seen thousands of viral videos and know exactly what works. "
            "\n"
            "You evaluate stories on these criteria (each scored 1-10):\n"
            "1. HOOK POWER: Does the opening line stop the scroll? Would you keep watching?\n"
            "2. STORY ARC: Is there clear tension → escalation → satisfying payoff?\n"
            "3. MORAL DEPTH: Is there a genuine takeaway, not a cliché platitude?\n"
            "4. ORIGINALITY: Is this fresh? Not a retold story everyone's heard?\n"
            "5. EMOTIONAL IMPACT: Does it make you FEEL something?\n"
            "6. SPEAKABILITY: Does it sound natural when read aloud? (Not essay-like)\n"
            "7. BREVITY: Is it 80-130 words? Reject if over 140 words — say 'too long, cut to 100-110 words'.\n"
            "\n"
            "You are TOUGH. A score below 6.5/10 means REJECT. "
            "When rejecting, give specific, actionable feedback — not vague complaints. "
            "Also flag any story that's too similar to the published history. "
            "\n"
            "You always respond with valid JSON. No markdown, no extra text."
        )

    def _build_batch_prompt(
        self,
        candidates: list[StoryCandidate],
        history_summary: str,
    ) -> str:
        stories_block = ""
        for i, c in enumerate(candidates):
            stories_block += f"""
--- STORY {i + 1}: "{c.title}" ---
Genre: {c.genre}
Hook: {c.hook}
Synopsis: {c.synopsis}
Full Story ({len(c.full_story.split())} words):
{c.full_story[:800]}{'...' if len(c.full_story) > 800 else ''}
Moral: {c.moral}
"""

        history_block = ""
        if history_summary:
            history_block = f"""

PUBLISHED STORY HISTORY (check for duplicates / similar themes):
{history_summary}
"""

        return f"""Review these {len(candidates)} story candidates for our viral short-video channel.
{history_block}

{stories_block}

For EACH story, respond with a JSON array of objects:
{{
  "story_index": 1,
  "title": "Story title",
  "approved": true/false,
  "score": 7.5,
  "scores": {{
    "hook_power": 8,
    "story_arc": 7,
    "moral_depth": 7,
    "originality": 8,
    "emotional_impact": 7,
    "speakability": 8
  }},
  "strengths": ["Strength 1", "Strength 2"],
  "weaknesses": ["Weakness 1"],
  "feedback": "Specific actionable feedback if rejected, or brief praise if approved",
  "is_duplicate": false,
  "duplicate_of": ""
}}

RULES:
- Score each criterion 1-10, then average for the overall score
- APPROVE if overall score >= 6.5, REJECT if below
- Be SPECIFIC in feedback — "the hook is weak" is useless. Say "the hook starts with a statement instead of a question or mystery — try opening with an impossible scenario"
- Check each story against the published history for duplicate THEMES, not just titles
- If a story is essentially the same lesson/plot as a published one, flag is_duplicate=true
- A story can have great writing but still be rejected if it's too similar to published content

JSON array only. No markdown."""

    # ── Parsing ───────────────────────────────────────

    def _parse_response(
        self, raw: str, candidates: list[StoryCandidate]
    ) -> list[ValidationResult]:
        """Parse LLM validation response."""
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*\n?", "", raw)
            raw = re.sub(r"\n?```\s*$", "", raw)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    logger.error("Could not parse validator response")
                    return self._fallback_results(candidates)
            else:
                logger.error("No JSON array in validator response")
                return self._fallback_results(candidates)

        if not isinstance(data, list):
            data = [data]

        results = []
        for item in data:
            if not isinstance(item, dict):
                continue

            score = float(item.get("score", 5.0))
            approved = item.get("approved", score >= self.APPROVAL_THRESHOLD)

            results.append(ValidationResult(
                story_title=item.get("title", ""),
                approved=approved,
                score=score,
                scores=item.get("scores", {}),
                feedback=item.get("feedback", ""),
                strengths=item.get("strengths", []),
                weaknesses=item.get("weaknesses", []),
                is_duplicate=item.get("is_duplicate", False),
                duplicate_of=item.get("duplicate_of", ""),
            ))

        # If we got fewer results than candidates, fill in defaults
        while len(results) < len(candidates):
            idx = len(results)
            results.append(ValidationResult(
                story_title=candidates[idx].title if idx < len(candidates) else "Unknown",
                approved=True,
                score=5.0,
                feedback="Not reviewed — auto-approved",
            ))

        return results

    def _fallback_results(self, candidates: list[StoryCandidate]) -> list[ValidationResult]:
        """Fallback: approve all candidates if parsing fails."""
        return [
            ValidationResult(
                story_title=c.title,
                approved=True,
                score=5.0,
                feedback="Parsing failed — auto-approved",
            )
            for c in candidates
        ]
