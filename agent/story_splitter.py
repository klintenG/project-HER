"""
Project HER v2.0 – Story Splitter (AI Image Mode)
Splits article/story text into screen-based story segments using AI.
Supports multiple LLM providers: Groq (free) and GitHub Models (Copilot).
Each segment is a focused story beat with metadata for visual decisions.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from openai import OpenAI

import config
from utils.llm_client import get_llm_client

logger = logging.getLogger("story_splitter")


# ── Data Classes ──────────────────────────────────────

@dataclass
class EmphasisWord:
    """A word/phrase within a screen that should be visually emphasised."""
    text: str
    style: str = "bold"  # bold | color | scale | pulse


@dataclass
class ScreenSegment:
    """One screen in the final video – a focused story beat."""
    index: int
    text: str                           # full narrative text for this screen
    duration: float = 3.5               # target seconds on screen
    visual_type: str = "image"          # "image" | "text_only" | "multi_image"
    scene_type: str = "B"               # Universal Style Guide scene type A–H
    image_prompt: str = ""              # prompt for AI image generation
    image_prompts: list[str] = field(default_factory=list)  # for multi_image
    image_subject: str = ""             # primary subject (e.g. "Queen Elizabeth")
    emphasis_words: list[EmphasisWord] = field(default_factory=list)
    narration_position: str = "top"     # "top" | "bottom" (alternates)
    emotion: str = "neutral"            # emotional tone for styling
    is_intro: bool = False
    is_outro: bool = False
    # Progressive text reveal (documentary style)
    setup_text: str = ""                # regular weight context line ("For a long time")
    subject_text: str = ""              # bold weight reveal line ("the Maratha rulers")
    caption_text: str = ""              # small label below image (optional)
    # Ghost Collaboration fields
    speaker: str = ""                   # "narrator" | "character" — who speaks this line
    character_name: str = ""            # e.g. "Nikola Tesla" — for display


@dataclass
class StoryScreenplay:
    """Complete screen breakdown for a story."""
    title: str
    brand_text: str = ""
    screens: list[ScreenSegment] = field(default_factory=list)
    total_duration: float = 0.0
    mood: str = "neutral"
    hook: str = ""
    cta: str = ""
    # New fields for content modes
    content_mode: str = "article"       # "article" | "thought_experiment" | "ghost_collab"
    character_name: str = ""            # Ghost Collaboration: primary character
    series_id: str = ""                 # Series mode: series identifier
    episode_number: int = 0             # Series mode: episode index
    cliffhanger: str = ""              # Series mode: unresolved question for next episode
    next_episode_hint: str = ""        # Series mode: teaser for next episode


# ── Story Splitter ────────────────────────────────────

class StorySplitter:
    """
    Uses AI to intelligently split a story into screen-based segments.
    Determines for each segment whether to use an AI image, animated text,
    or multiple images.
    Supports Groq (free) and GitHub Models (Copilot) as LLM providers.
    """

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        self.client, self.model = get_llm_client(provider=provider, model=model)

    def split(
        self,
        text: str,
        title: str = "",
        tone: str = "informative",
        brand_text: str = "",
        content_mode: str = "article",
        question: str = "",
        character_name: str = "",
        modern_topic: str = "",
        series_id: str = "",
        episode_number: int = 0,
        previous_cliffhanger: str = "",
    ) -> StoryScreenplay:
        """Split story text into screen segments using AI analysis.

        Args:
            text: Article/story text (for article mode) or ignored for other modes.
            title: Optional title override.
            tone: Content tone preset.
            brand_text: Brand overlay text.
            content_mode: "article" | "thought_experiment" | "ghost_collab"
            question: The philosophical question (thought_experiment mode).
            character_name: Historical/fictional figure (ghost_collab mode).
            modern_topic: Modern topic to discuss (ghost_collab mode).
            series_id: Series identifier for chain mode.
            episode_number: Current episode number in series.
            previous_cliffhanger: Unresolved question from previous episode.
        """
        logger.info(
            "Splitting story into screen segments (mode=%s, tone=%s)",
            content_mode, tone,
        )

        # Route to the appropriate prompt builder
        if content_mode == "deep_dive":
            return self._run_deep_dive_pipeline(
                text=text,
                title=title,
                tone=tone,
                brand_text=brand_text,
                series_context=previous_cliffhanger,
            )
        elif content_mode == "thought_experiment":
            prompt = self._build_thought_experiment_prompt(
                question=question or text,
                tone=tone,
                series_context=previous_cliffhanger,
            )
        elif content_mode == "ghost_collab":
            prompt = self._build_ghost_collab_prompt(
                character_name=character_name,
                modern_topic=modern_topic or text,
                tone=tone,
            )
        else:
            prompt = self._build_prompt(
                text, title, tone,
                series_context=previous_cliffhanger,
            )

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._system_prompt(content_mode)},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.75,
                max_tokens=config.LLM_MAX_TOKENS,
            )
            raw = resp.choices[0].message.content.strip()
            screenplay = self._parse_response(raw, title, brand_text)

            # Set content mode metadata
            screenplay.content_mode = content_mode
            if content_mode == "ghost_collab":
                screenplay.character_name = character_name

            # Series metadata
            if series_id:
                screenplay.series_id = series_id
                screenplay.episode_number = episode_number

            # Post-process: assign alternating narration positions
            self._assign_narration_positions(screenplay)
            # Compute total duration
            screenplay.total_duration = sum(s.duration for s in screenplay.screens)

            logger.info(
                "Story split into %d screens (%.1fs total)",
                len(screenplay.screens), screenplay.total_duration,
            )
            return screenplay

        except Exception as e:
            logger.error("Story splitting failed: %s", e, exc_info=True)
            # Fallback: simple sentence-based split
            return self._fallback_split(text, title, brand_text)

    # ── Prompts ───────────────────────────────────────

    def _system_prompt(self, content_mode: str = "article") -> str:
        # Shared human-voice directive injected into every mode
        human_voice = (
            "VOICE & PERSONALITY: "
            "Write every narration line exactly how a sharp, curious friend would TELL this story out loud — not how a journalist would write it. "
            "Use contractions (don't, it's, they'd). Use filler beats that real people say: 'So here's the thing…', 'And honestly?', 'Which… yeah.', 'Okay wait—'. "
            "Vary your rhythm: a long sentence, then a short punch. A question, then a blunt answer. "
            "React to the material — if something is wild, SAY it's wild ('That's… kind of insane.'). "
            "Never sound like a textbook, a press release, or a corporate script. Sound like a person who just found out something fascinating and can't wait to tell someone. "
            "You always respond with valid JSON only, no markdown, no extra text."
        )

        if content_mode == "deep_dive":
            return (
                "You are TWO podcast hosts having a genuinely fascinating conversation about source material — "
                "like NotebookLM's 'Deep Dive' but for short-form video. "
                "Host A (the 'explainer') has read the sources deeply and is excited to share what they found. "
                "Host B (the 'reactor') asks great questions, makes connections, expresses surprise, and pushes for clearer explanations. "
                "The conversation should feel REAL — hosts interrupt each other, laugh, say 'wait what?', go on brief tangents, "
                "then snap back. They are enthusiastic nerds who genuinely find this stuff interesting. "
                "Think of your favorite podcast: the hosts who make you feel like you're eavesdropping on a brilliant conversation. "
                "NEVER sound scripted or like a news broadcast. This is two smart friends geeking out. "
                + human_voice
            )
        elif content_mode == "thought_experiment":
            return (
                "You are a late-night-conversation philosopher — the friend who asks a question at 2 AM that keeps everyone awake for another hour. "
                "Your style is 'Black Mirror meets your smartest friend after two drinks': eerie, fascinating, intimate. "
                "You explore hypotheticals by making them PERSONAL — 'imagine YOU wake up and…' — not academic. "
                + human_voice
            )
        elif content_mode == "ghost_collab":
            return (
                "You are a witty, warm interviewer hosting an imaginary conversation between "
                "a modern narrator and a historical or fictional figure. "
                "The narrator sounds like a real podcast host — casual, curious, sometimes funny. "
                "The character speaks in a style true to their era and personality, but translated so a modern listener gets it instantly. "
                "The vibe is two interesting people having a surprisingly great conversation, not a history lecture. "
                "You NEVER claim the character actually said these things — this is clearly AI-generated creative content. "
                + human_voice
            )
        else:
            return (
                "You are a gifted storyteller who turns articles and raw information into compelling spoken-word video scripts. "
                "You think like a documentary narrator meets a great podcast host: clear, vivid, human. "
                "You split stories into screen-by-screen segments for short-form video (3-4 seconds each). "
                "You decide whether each screen needs a visual image, animated text only, or multiple images. "
                "Your MOST IMPORTANT job is making the narration sound like a REAL PERSON talking — not a Wikipedia summary read aloud. "
                + human_voice
            )

    def _build_prompt(self, text: str, title: str, tone: str, series_context: str = "") -> str:
        tone_instruction = config.TONE_PRESETS.get(tone, config.TONE_PRESETS["informative"])

        series_block = ""
        if series_context:
            series_block = f"""
SERIES CONTINUATION (IMPORTANT):
This video is part of a series. The previous episode ended with this unresolved question:
  "{series_context}"
- Start THIS video by briefly referencing or answering the previous cliffhanger.
- End THIS video with a NEW cliffhanger / unresolved question for the next episode.
- Include a "cliffhanger" field in the JSON response with the new unresolved question.
"""

        return f"""You just read an amazing story and now you're telling a friend about it on camera.
Your job: turn this article into a SPOKEN video script — screen by screen — that sounds like
a real person narrating, not a robot summarizing.

STORY TITLE: {title or '(untitled)'}
STORY TEXT: {text[:3000]}

TONE: {tone_instruction}
{series_block}

═══════════════════════════════════════════════════════
HUMAN NARRATION STYLE — THE MOST IMPORTANT SECTION
═══════════════════════════════════════════════════════

Every "text" field is what will be SPOKEN ALOUD. Write it exactly like a person talks:

✓ Use contractions always: "it's", "didn't", "they're", "wouldn't", "here's"
✓ Use casual transitions real people say:
  - "So here's the thing…"
  - "And honestly? Nobody expected what happened next."
  - "Okay, but wait—"
  - "Now, this is where it gets interesting."
  - "Which… yeah. That's a lot."
  - "And I mean—"
✓ React to the material like a human would:
  - "That's actually kind of wild when you think about it."
  - "Crazy, right?"
  - "I know — it sounds impossible."
✓ Use rhythm: long sentence, then a SHORT punch. Then a question.
  Example: "For over two hundred years, this diamond passed through the hands of emperors,
  warlords, and colonial governors. And nobody questioned it. Not once."
✓ Use "you" to pull the viewer in: "You'd think someone would've noticed, right?"
✓ Use sentence fragments for emphasis: "Gone. Just like that." / "Every. Single. One."
✓ Add micro-pauses with em dashes and ellipses: "And then — silence."

✗ NEVER write like a textbook: "The significance of this event cannot be overstated."
✗ NEVER write like a press release: "This groundbreaking development represents…"
✗ NEVER write clinical summaries: "The article discusses the impact of…"
✗ NEVER use formal connectors: "Furthermore", "Moreover", "Additionally", "In conclusion"
✗ NEVER start a sentence with "This" referring to an abstract concept.
✗ NEVER use passive voice when active is possible.

Your narration should make the viewer feel like they're hearing a STORY from a friend,
not reading a report. If the text could appear in a school essay, rewrite it.

═══════════════════════════════════════════════════════
STORY CUTTING — HOW TO SPLIT THE CONTENT
═══════════════════════════════════════════════════════

Do NOT mechanically extract bullet points from the article.
Instead, RETELL the story in your own words. Reimagine it as a spoken narrative:

1. Each screen = ONE conversational beat (1-2 sentences max, spoken naturally).
2. Cut at natural pause points — where a real speaker would take a breath or let something land.
3. Leave emotional space: after a big reveal, give the viewer a beat to absorb it.
4. Build MOMENTUM: each screen should make the viewer curious about the NEXT screen.
5. Default screen duration: 3.5 seconds. Dense/list screens: 5-7 seconds.

═══════════════════════════════════════════════════════
VISUAL DECISIONS
═══════════════════════════════════════════════════════

EVERY SCREEN MUST HAVE AN IMAGE. No exceptions.

For each screen, set visual_type to "image" and provide an image_prompt.
The only other option is "multi_image" (for lists) with image_prompts array.
There is NO valid reason to use "text_only" — even abstract or emotional beats
can be visualized with atmospheric photography or conceptual imagery.

For abstract/emotional text:
  - "A dimly lit empty hallway stretching into shadows, moody cinematic lighting"
  - "Close-up of hands gripping a weathered journal, dramatic side lighting"
  - "A lone figure silhouetted against a vast sunset sky, wide shot"

For conceptual/transitional text:
  - "Aerial view of a city at night with lights spreading like neurons"
  - "Time-lapse of clouds racing over a mountain peak"
  - "Abstract swirl of warm and cool colors representing change"

Always provide a descriptive image_prompt — NEVER leave it empty.
Keep image_prompt focused on ONE subject per image.
Provide an emotion tag: neutral, excited, warm, dramatic, thoughtful, playful.

IMAGE COVERAGE (MANDATORY):
- 100% of screens MUST have visual_type "image" or "multi_image".
- Do NOT use "text_only" for ANY screen. Zero text_only screens.
- Every single second of the video must have a background image.
- Viewers LOSE INTEREST at blank/text-only screens — always show something visual.

TEXT REVEAL PATTERN:
For EVERY screen, split the text into TWO lines:
  - "setup_text": A casual context line ("So for the longest time", "And she just kept", "Right there, inside a bank vault")
  - "subject_text": The key reveal in bold ("the Maratha rulers", "the Kohinoor", "in Bangladesh")

HOOK ENGINEERING (CRITICAL):
- The hook MUST start MID-THOUGHT. Never start with "Did you know" or "Hey guys".
- Examples: "...and that's why nobody talks about this." / "They found it buried under..."
- It creates an instant knowledge gap.

NARRATIVE ARC — DELAYED REVEAL:
- Save the MOST interesting fact for the LAST 2-3 screens.
- Build curiosity through the middle — hint but don't reveal.
- First screen creates a question. Last screen answers it.

CTA / ENDING:
- CTA should feel like a cliffhanger: "But here's what they didn't tell you — next video."
- Not: "Follow for more!"

SCENE TYPES (assign one per screen):
  "A" — HOOK OPENER: First scene only. Image-only. Most striking subject. 2-3 seconds.
  "B" — NARRATIVE + IMAGE: Setup text + image + subject text. Core type. 3-5 seconds.
  "C" — TEXT-ONLY BRIDGE: No images. 1-2 lines. Palette cleanser. Max 1-2 per video. 1.5-3 seconds.
  "D" — FIGURE REVEAL: Introducing a person. Role + image + name. 3-5 seconds.
  "G" — COMPARISON: Two items compared. Setup question + two items. 4-6 seconds.

PACING:
- Aim for 55-65 seconds total.
- Each idea gets space to land. Never rushed.
- Start with a Type A hook, end with a reveal or conclusion.

RESPOND WITH THIS EXACT JSON STRUCTURE:
{{
  "title": "video title",
  "hook": "attention-grabbing opening line (mid-thought style)",
  "mood": "overall mood (calm/upbeat/dramatic/warm/neutral)",
  "cta": "cliffhanger-style call to action",
  "cliffhanger": "unresolved question for the next video (optional, for series)",
  "screens": [
    {{
      "text": "full narrative text for this screen",
      "setup_text": "context/setup phrase (regular weight)",
      "subject_text": "subject/key fact (bold weight)",
      "caption_text": "",
      "scene_type": "B",
      "duration": 3.5,
      "visual_type": "image",
      "image_prompt": "a clear description of what to show",
      "image_subject": "primary subject name",
      "emotion": "neutral",
      "emphasis_words": []
    }}
  ]
}}

Return ONLY valid JSON. No markdown code fences. No extra text."""

    # ── Deep Dive Pipeline (NotebookLM-inspired) ────

    def _run_deep_dive_pipeline(
        self, text: str, title: str, tone: str, brand_text: str,
        series_context: str = "",
    ) -> StoryScreenplay:
        """
        Multi-pass NotebookLM-style pipeline:
          Pass 1: Deep understanding — extract key insights, surprising facts, connections
          Pass 2: Generate natural two-host podcast conversation as screen segments

        This produces significantly better output because the LLM first THINKS about
        the content before writing the script — like how NotebookLM processes sources
        before generating its audio overview.
        """
        logger.info("Deep Dive pipeline: starting multi-pass analysis")
        max_context = config.DEEP_DIVE_MAX_CONTEXT_CHARS
        truncated_text = text[:max_context]

        # ── Pass 1: Deep Understanding ─────────────────
        # Ask the LLM to deeply analyze the source material first
        understanding_prompt = f"""Read this source material carefully. Your job is to extract a DEEP understanding
— not a surface summary, but the stuff that makes someone go "wait, really?"

SOURCE TITLE: {title or '(untitled)'}
SOURCE TEXT:
{truncated_text}

Analyze this material and return a JSON object with:
{{
  "core_thesis": "The single most important idea in 1-2 sentences",
  "surprising_facts": ["5-7 specific facts/details that would genuinely surprise someone"],
  "key_connections": ["3-4 non-obvious connections between ideas in the source"],
  "emotional_hooks": ["3-4 moments that provoke strong reactions (awe, disbelief, curiosity)"],
  "unanswered_questions": ["2-3 questions the source raises but doesn't fully answer"],
  "quotable_lines": ["2-3 specific phrases/data points worth quoting exactly"],
  "analogy_opportunities": ["2-3 places where a good analogy would make a concept click"],
  "one_line_hook": "The single most scroll-stopping thing about this content — mid-thought, provocative"
}}

Be SPECIFIC. Don't give generic observations. Pull actual details, numbers, names, and findings from the text.
Return ONLY valid JSON. No markdown."""

        try:
            logger.info("Deep Dive Pass 1: Extracting deep understanding...")
            resp1 = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": (
                        "You are a research analyst with a gift for finding the most interesting, "
                        "surprising, and shareable insights in any material. "
                        "You think like a podcast producer scouring sources for 'the good bits'. "
                        "Return only valid JSON."
                    )},
                    {"role": "user", "content": understanding_prompt},
                ],
                temperature=0.5,  # Lower temp for factual extraction
                max_tokens=2000,
            )
            raw_understanding = resp1.choices[0].message.content.strip()

            # Clean potential markdown wrapping
            cleaned = raw_understanding
            if cleaned.startswith("```"):
                import re as _re
                cleaned = _re.sub(r"^```(?:json)?\s*", "", cleaned)
                cleaned = _re.sub(r"\s*```$", "", cleaned)

            understanding = json.loads(cleaned)
            logger.info(
                "Deep Dive Pass 1 complete: %d surprising facts, %d connections, hook='%s'",
                len(understanding.get("surprising_facts", [])),
                len(understanding.get("key_connections", [])),
                understanding.get("one_line_hook", "")[:60],
            )

        except Exception as e:
            logger.warning("Deep Dive Pass 1 failed: %s — using source text directly", e)
            understanding = {
                "core_thesis": title or "An interesting topic",
                "surprising_facts": [],
                "key_connections": [],
                "emotional_hooks": [],
                "unanswered_questions": [],
                "quotable_lines": [],
                "analogy_opportunities": [],
                "one_line_hook": title or "Something fascinating",
            }

        # ── Pass 2: Generate Podcast Conversation ──────
        conversation_prompt = self._build_deep_dive_prompt(
            text=truncated_text,
            title=title,
            tone=tone,
            understanding=understanding,
            series_context=series_context,
        )

        logger.info("Deep Dive Pass 2: Generating two-host conversation...")
        try:
            resp2 = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._system_prompt("deep_dive")},
                    {"role": "user", "content": conversation_prompt},
                ],
                temperature=0.80,  # Higher temp for natural conversation
                max_tokens=config.LLM_MAX_TOKENS,
            )
            raw = resp2.choices[0].message.content.strip()
            screenplay = self._parse_response(raw, title, brand_text)
            screenplay.content_mode = "deep_dive"

            # Assign narration positions
            self._assign_narration_positions(screenplay)
            screenplay.total_duration = sum(s.duration for s in screenplay.screens)

            logger.info(
                "Deep Dive complete: %d screens (%.1fs total)",
                len(screenplay.screens), screenplay.total_duration,
            )
            return screenplay

        except Exception as e:
            logger.error("Deep Dive Pass 2 failed: %s", e, exc_info=True)
            return self._fallback_split(text, title, brand_text)

    def _build_deep_dive_prompt(
        self, text: str, title: str, tone: str,
        understanding: dict, series_context: str = "",
    ) -> str:
        """Build the Deep Dive conversation prompt using Pass 1 insights."""
        tone_instruction = config.TONE_PRESETS.get(tone, config.TONE_PRESETS["informative"])

        # Format the understanding insights for the prompt
        surprising = "\n".join(f"  • {f}" for f in understanding.get("surprising_facts", []))
        connections = "\n".join(f"  • {c}" for c in understanding.get("key_connections", []))
        hooks = "\n".join(f"  • {h}" for h in understanding.get("emotional_hooks", []))
        questions = "\n".join(f"  • {q}" for q in understanding.get("unanswered_questions", []))
        quotable = "\n".join(f"  • {q}" for q in understanding.get("quotable_lines", []))
        analogies = "\n".join(f"  • {a}" for a in understanding.get("analogy_opportunities", []))

        series_block = ""
        if series_context:
            series_block = f"""
SERIES CONTINUATION:
Previous episode ended with: "{series_context}"
Reference this briefly at the start, then explore the new material.
Include a "cliffhanger" for the next episode.
"""

        min_screens, max_screens = config.DEEP_DIVE_SCREENS

        return f"""You're writing a two-host podcast conversation about source material — think NotebookLM's
"Deep Dive" but formatted for short-form video. Two hosts (Host A and Host B) discuss what they found.

═══════════════════════════════════════════════════════
SOURCE MATERIAL
═══════════════════════════════════════════════════════

TITLE: {title or '(untitled)'}
CORE THESIS: {understanding.get('core_thesis', 'See source text')}

ORIGINAL TEXT (for reference):
{text[:2500]}

═══════════════════════════════════════════════════════
DEEP ANALYSIS (from our research pass)
═══════════════════════════════════════════════════════

MOST SURPRISING FACTS:
{surprising or '  (none extracted — find your own from the text)'}

NON-OBVIOUS CONNECTIONS:
{connections or '  (none extracted)'}

EMOTIONAL HOOKS (moments that provoke reactions):
{hooks or '  (none extracted)'}

UNANSWERED QUESTIONS:
{questions or '  (none extracted)'}

QUOTABLE DETAILS:
{quotable or '  (none extracted)'}

ANALOGY OPPORTUNITIES:
{analogies or '  (none extracted)'}

SCROLL-STOPPING HOOK: {understanding.get('one_line_hook', 'Something fascinating')}

TONE: {tone_instruction}
{series_block}

═══════════════════════════════════════════════════════
TWO-HOST CONVERSATION RULES
═══════════════════════════════════════════════════════

HOST A ("the explainer"): Has read the sources. Excited to share. Uses phrases like:
  - "Okay so I was reading this and—"
  - "And here's the part that really got me."
  - "No no, it gets better."
  - "So basically what they found is…"

HOST B ("the reactor"): Hasn't read it (represents the viewer). Asks questions, reacts:
  - "Wait, seriously?"
  - "Okay but how does that even work?"
  - "That's insane. So what happened next?"
  - "Hold on — say that again?"
  - "Oh that's actually kind of brilliant."

CONVERSATION DYNAMICS:
✓ Hosts should INTERRUPT each other naturally: "—and that's exactly—" / "Wait wait wait—"
✓ Host B should ask the questions the VIEWER is thinking
✓ Host A should build excitement before reveals: "Okay so you're not gonna believe this but—"
✓ Include micro-reactions: laughing, "huh", "wow", "oh man"
✓ Host B sometimes makes CONNECTIONS Host A didn't think of
✓ Use the surprising facts and emotional hooks from the analysis above — those are gold
✓ One host should use an ANALOGY to explain a complex concept: "It's like if you..."
✓ Quote specific details/numbers from the source — grounded, not generic

✗ NEVER sound scripted or rehearsed
✗ NEVER have both hosts agree immediately — one should push back at least once
✗ NEVER use formal language or transitions
✗ NEVER have a host say something generic that could apply to any topic

═══════════════════════════════════════════════════════
STRUCTURE
═══════════════════════════════════════════════════════

1. Screen 1: HOST A opens mid-thought with the hook: "{understanding.get('one_line_hook', 'Something fascinating')}"
2. Screen 2: HOST B reacts — pulls viewer in with a question
3. Screens 3-{max_screens - 2}: Alternating conversation. Build through the surprising facts.
   Use the emotional hooks and connections from the analysis. Each turn = 1-2 sentences.
4. Second-to-last screen: HOST B makes a connection or asks the big unanswered question
5. Last screen: HOST A gives a mind-blow conclusion or cliffhanger

Total: {min_screens}-{max_screens} screens, 55-90 seconds.

VISUAL RULES:
- EVERY screen MUST have visual_type "image". Zero text_only screens.
- For HOST A screens: image related to what they're explaining
- For HOST B screens: image related to their reaction/question, or same topic from different angle
- Image prompts should be CINEMATIC and ATMOSPHERIC
- NEVER generate images of the hosts themselves — show the TOPIC

RESPOND WITH THIS EXACT JSON STRUCTURE:
{{
  "title": "A catchy 4-8 word title for the Deep Dive",
  "hook": "Host A's opening mid-thought line",
  "mood": "energetic/warm/fascinated/mind-blown",
  "cta": "Host B's closing question that makes viewers want more",
  "cliffhanger": "An angle left unexplored for a follow-up",
  "screens": [
    {{
      "text": "What Host A says — natural, excited, conversational",
      "setup_text": "context phrase",
      "subject_text": "key fact or reveal",
      "caption_text": "",
      "speaker": "host_a",
      "scene_type": "A",
      "duration": 3.5,
      "visual_type": "image",
      "image_prompt": "cinematic scene related to the content",
      "image_subject": "primary visual subject",
      "emotion": "excited",
      "emphasis_words": []
    }},
    {{
      "text": "What Host B says — reactive, curious, sometimes pushing back",
      "setup_text": "reaction context",
      "subject_text": "their question or insight",
      "caption_text": "",
      "speaker": "host_b",
      "scene_type": "B",
      "duration": 3.0,
      "visual_type": "image",
      "image_prompt": "visual related to the question being asked",
      "image_subject": "visual subject",
      "emotion": "curious",
      "emphasis_words": []
    }}
  ]
}}

IMPORTANT: speakers must be exactly "host_a" or "host_b" — no other values.
Return ONLY valid JSON. No markdown code fences. No extra text."""

    # ── Thought Experiment Prompt ─────────────────────

    def _build_thought_experiment_prompt(
        self, question: str, tone: str, series_context: str = ""
    ) -> str:
        tone_instruction = config.TONE_PRESETS.get(tone, config.TONE_PRESETS["dramatic"])

        series_block = ""
        if series_context:
            series_block = f"""
SERIES CONTINUATION:
The previous thought experiment ended with this unresolved angle:
  "{series_context}"
Reference it briefly in the opening, then explore the NEW question below.
Include a "cliffhanger" field with a new unresolved question for the next episode.
"""

        return f"""You're telling a friend about a mind-bending thought experiment — the kind that
keeps people up at 2 AM. Make it feel like a late-night conversation, not a TED talk.

QUESTION: {question}
TONE: {tone_instruction}
{series_block}

═══════════════════════════════════════════════════════
HUMAN NARRATION STYLE
═══════════════════════════════════════════════════════

Every "text" field is SPOKEN ALOUD. Write it like a real person thinks out loud:

✓ Use contractions: "it's", "you'd", "wouldn't", "that's"
✓ Think out loud: "Okay, so picture this.", "And here's the part that messes with me."
✓ React genuinely: "Which is… kind of terrifying, actually."
✓ Use fragments: "Gone. All of it." / "No memory. No proof."
✓ Use rhythm: long thought, short punch, question.
✓ Make it PERSONAL with "you": "You wake up, grab your phone — and it already knows."

✗ NEVER sound academic: "One might consider the implications of…"
✗ NEVER use formal language: "Furthermore", "Indeed", "Thus"
✗ If it could be in a textbook, rewrite it as something you'd actually SAY.

═══════════════════════════════════════════════════════
STRUCTURE
═══════════════════════════════════════════════════════

1. Start MID-THOUGHT — NOT "What if..." but rather:
   "...and nobody would ever know." or "You wake up tomorrow and something's just… off."
   The hook must create an INSTANT knowledge gap.

2. Structure: HOOK → SETUP → ESCALATION → TWIST → CONCLUSION
   - HOOK (screen 1): Most jarring consequence as fact. Image-only. 2-3 seconds.
   - SETUP (screens 2-3): Make the scenario visceral and specific. Not "imagine a world where" — instead
     "You're at breakfast. You pour your coffee. And then you notice your hands look… different."
   - ESCALATION (screens 4-7): 3-4 increasingly wild implications. Each more surprising than the last.
   - TWIST (screen 8-9): The angle nobody expects. Flip the question.
   - CONCLUSION (screen 10): Don't give a clean answer. Leave them thinking.

3. EVERY screen MUST have visual_type "image". Zero text_only screens.
   Image prompts: EERIE, ATMOSPHERIC, CINEMATIC. Not literal.
   Think: empty corridors, cosmic imagery, surreal landscapes.
   Even abstract thoughts get a visual — moody photography, atmospheric scenes, symbolic imagery.

4. Total: 8-12 screens, 45-70 seconds.

5. End CTA = a DEEPER question: "But here's what really messes with you — what if this already happened?"

6. Include a "cliffhanger" field — an unresolved angle for a follow-up.

VISUAL STYLE:
- Image prompts should be atmospheric and cinematic: moody lighting, surreal compositions,
  dystopian or ethereal settings, abstract visual metaphors.
- NEVER generate images of text, logos, or UI elements.
- Think: a lone figure in a vast empty space, a glowing orb in darkness,
  an impossible staircase, a mirror reflecting something different.

RESPOND WITH THIS EXACT JSON STRUCTURE:
{{
  "title": "A provocative 4-6 word title",
  "hook": "Mid-thought hook line that stops scrolling",
  "mood": "eerie/dramatic/thoughtful/suspenseful",
  "cta": "A deeper question that haunts the viewer",
  "cliffhanger": "An unresolved angle for a follow-up video",
  "screens": [
    {{
      "text": "full narrative text for this screen (use 'you' language)",
      "setup_text": "context/setup phrase",
      "subject_text": "key reveal/subject",
      "caption_text": "",
      "scene_type": "A",
      "duration": 2.5,
      "visual_type": "image",
      "image_prompt": "atmospheric cinematic description",
      "image_subject": "primary visual focus",
      "emotion": "eerie",
      "emphasis_words": []
    }}
  ]
}}

Return ONLY valid JSON. No markdown code fences. No extra text."""

    # ── Ghost Collaboration Prompt ────────────────────

    def _build_ghost_collab_prompt(
        self, character_name: str, modern_topic: str, tone: str
    ) -> str:
        tone_instruction = config.TONE_PRESETS.get(tone, config.TONE_PRESETS["storytelling"])
        max_turns = config.GHOST_COLLAB_MAX_TURNS

        return f"""You're a podcast host having a surprisingly great conversation with {character_name}.
It's playful, real, and a little surreal. Write it like two people actually TALKING — not a script reading.

CHARACTER: {character_name}
MODERN TOPIC: {modern_topic}
TONE: {tone_instruction}

═══════════════════════════════════════════════════════
HUMAN DIALOGUE STYLE
═══════════════════════════════════════════════════════

Every "text" field is SPOKEN ALOUD. Write real dialogue:

Narrator (modern host):
  ✓ Casual, curious, a bit cheeky: "Okay so I gotta ask you—"
  ✓ Reacts to the character: "Wait, seriously?" / "That's… actually kind of brilliant."
  ✓ Uses contractions, filler, modern slang (but not cringe)

{character_name} (the character):
  ✓ Authentic to their era and personality, but TRANSLATED so modern listeners get it
  ✓ Can be witty, surprising, even funny — they're a real person with personality
  ✓ Their lines should be QUOTABLE — the kind of thing people screenshot and share
  ✓ Adapt their known philosophy to the modern topic in a way that feels genuine

Both:
  ✓ Short turns: 1-2 sentences each, punchy
  ✓ The conversation has natural momentum — it doesn't feel scripted
  ✓ Occasional overlapping energy: "—and that's exactly—" / "Right, but here's the thing—"

✗ NEVER make dialog sound like a formal interview or press conference
✗ NEVER have the character speak in a way their historical self wouldn't recognize
✗ This is clearly AI-generated creative content — NOT a deepfake or impersonation.

═══════════════════════════════════════════════════════
STRUCTURE
═══════════════════════════════════════════════════════

1. {max_turns} total turns (alternating narrator and character).

2. Start MID-THOUGHT from narrator:
   "…so I actually asked {character_name} what they make of {modern_topic}."
   or "When {character_name} heard about {modern_topic}? They had thoughts."

3. Structure:
   - Screen 1: HOOK (narrator introduces {character_name}, casual and intriguing). Image of character.
   - Screens 2-7: Alternating dialogue. Character's lines should surprise — witty, profound, or unexpectedly modern.
   - Final screen: {character_name} drops a mic-drop quote that makes people share the video.

4. Each screen MUST have "speaker": "narrator" or "character".

5. EVERY screen MUST have visual_type "image".
   - Narrator screens: image of the modern topic.
   - Character screens: STYLIZED artistic portrait (never photorealistic).

6. Total: {max_turns} screens, 40-65 seconds.

7. End CTA: "Who should we talk to next?" or "What would YOU ask {character_name}?"

VISUAL STYLE FOR CHARACTER:
- NEVER use photorealistic depictions of real historical figures.
- Use: artistic portrait, oil painting style, animated/stylized illustration, clay sculpture,
  abstract representation with symbolic elements of their identity.
- Example: "An artistic clay sculpture of a wild-haired scientist in a vintage laboratory,
  holding a modern smartphone, warm studio lighting, stylized illustration"

RESPOND WITH THIS EXACT JSON STRUCTURE:
{{
  "title": "I Asked {character_name} About {modern_topic}",
  "hook": "Mid-thought narrator hook",
  "mood": "warm/thoughtful/playful/dramatic",
  "cta": "Engaging question for viewers",
  "character_name": "{character_name}",
  "screens": [
    {{
      "text": "What the speaker says in this turn",
      "setup_text": "context line",
      "subject_text": "key quote or fact",
      "caption_text": "",
      "speaker": "narrator",
      "scene_type": "B",
      "duration": 4.0,
      "visual_type": "image",
      "image_prompt": "description of what to show",
      "image_subject": "primary subject",
      "emotion": "curious",
      "emphasis_words": []
    }},
    {{
      "text": "Character's response in their authentic voice",
      "setup_text": "{character_name} said",
      "subject_text": "their key insight or quote",
      "caption_text": "{character_name}",
      "speaker": "character",
      "scene_type": "D",
      "duration": 4.5,
      "visual_type": "image",
      "image_prompt": "stylized artistic portrait of {character_name} with modern elements",
      "image_subject": "{character_name}",
      "emotion": "thoughtful",
      "emphasis_words": []
    }}
  ]
}}

Return ONLY valid JSON. No markdown code fences. No extra text."""

    # ── Response Parsing ──────────────────────────────

    def _parse_response(
        self, raw: str, title: str, brand_text: str
    ) -> StoryScreenplay:
        """Parse AI response into StoryScreenplay."""
        # Clean potential markdown wrapping
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        data = json.loads(cleaned)

        screens: list[ScreenSegment] = []
        for i, s in enumerate(data.get("screens", [])):
            emphasis = []
            for w in s.get("emphasis_words", []):
                if isinstance(w, str):
                    emphasis.append(EmphasisWord(text=w))
                elif isinstance(w, dict):
                    emphasis.append(EmphasisWord(
                        text=w.get("text", ""),
                        style=w.get("style", "bold"),
                    ))

            duration = float(s.get("duration", config.CLAY_SCREEN_DEFAULT_DURATION))
            duration = max(config.CLAY_SCREEN_MIN_DURATION,
                          min(duration, config.CLAY_SCREEN_MAX_DURATION))

            segment = ScreenSegment(
                index=i,
                text=s.get("text", ""),
                duration=duration,
                visual_type=s.get("visual_type", "image"),
                image_prompt=s.get("image_prompt", ""),
                image_prompts=s.get("image_prompts", []),
                image_subject=s.get("image_subject", ""),
                emphasis_words=emphasis,
                emotion=s.get("emotion", "neutral"),
                setup_text=s.get("setup_text", ""),
                subject_text=s.get("subject_text", ""),
                caption_text=s.get("caption_text", ""),
                scene_type=s.get("scene_type", "B"),
                speaker=s.get("speaker", ""),
                character_name=s.get("character_name", data.get("character_name", "")),
            )
            screens.append(segment)

        screenplay = StoryScreenplay(
            title=data.get("title", title),
            brand_text=brand_text,
            screens=screens,
            mood=data.get("mood", "neutral"),
            hook=data.get("hook", ""),
            cta=data.get("cta", ""),
            character_name=data.get("character_name", ""),
            cliffhanger=data.get("cliffhanger", ""),
        )
        return screenplay

    # ── Post-processing ───────────────────────────────

    def _assign_narration_positions(self, screenplay: StoryScreenplay):
        """Alternate narration text position (top ↔ bottom) across screens."""
        position = "top"
        for screen in screenplay.screens:
            screen.narration_position = position
            position = "bottom" if position == "top" else "top"

    # ── Fallback (no AI) ──────────────────────────────

    def _fallback_split(
        self, text: str, title: str, brand_text: str
    ) -> StoryScreenplay:
        """Simple sentence-based split when AI fails."""
        import nltk
        try:
            sentences = nltk.sent_tokenize(text)
        except Exception:
            sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]

        screens = []
        for i, sent in enumerate(sentences):
            if not sent.strip():
                continue
            # Heuristic: short abstract sentences → text_only
            words = sent.split()
            has_noun = any(
                w[0].isupper() and i > 0 for i, w in enumerate(words)
            )
            visual_type = "image" if (has_noun and len(words) > 4) else "text_only"

            screens.append(ScreenSegment(
                index=i,
                text=sent.strip(),
                duration=config.CLAY_SCREEN_DEFAULT_DURATION,
                visual_type=visual_type,
                image_prompt=sent.strip() if visual_type == "image" else "",
                image_subject="",
                emphasis_words=[],
                emotion="neutral",
            ))

        # Cap at reasonable number
        if len(screens) > 15:
            screens = screens[:15]

        sp = StoryScreenplay(
            title=title or "Untitled",
            brand_text=brand_text,
            screens=screens,
            mood="neutral",
        )
        self._assign_narration_positions(sp)
        sp.total_duration = sum(s.duration for s in sp.screens)
        return sp
