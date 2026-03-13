#!/usr/bin/env python3
"""
test_remotion.py – Test Remotion rendering with "The Lion and the Mouse" story.
================================================================================
Builds manual screenplay + narration + effects plan, then renders via Remotion.
No external APIs needed (uses edge-tts for narration, text_only scenes for images).
"""

import asyncio
import logging
import sys
import time
from pathlib import Path
from dataclasses import dataclass, field

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import edge_tts

import config
from agent.story_splitter import StoryScreenplay, ScreenSegment, EmphasisWord
from agent.narration import NarrationClip, WordTiming
from agent.ai_visuals import AIImageAsset
from agent.effects_agent import SceneEffectsPlan, VideoEffectsPlan
from agent.remotion_renderer import RemotionRenderer
from utils.helpers import ensure_dir

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("test_remotion")


# ── The Story ─────────────────────────────────────────

SCREENS = [
    {
        "text": "The Lion and the Mouse",
        "emotion": "wonder",
        "is_intro": True,
        "duration": 3.5,
        "visual_type": "text_only",
        "scene_type": "A",
        "setup_text": "Aesop's Famous Fable",
        "emphasis_words": [("Lion", "bold"), ("Mouse", "bold")],
        "narration_position": "top",
    },
    {
        "text": "One day, a lion was sleeping peacefully in the forest. A little mouse ran across his paw and woke him up.",
        "emotion": "calm",
        "duration": 5.0,
        "visual_type": "text_only",
        "scene_type": "B",
        "emphasis_words": [("lion", "bold"), ("peacefully", "color"), ("mouse", "bold")],
        "narration_position": "top",
    },
    {
        "text": "The lion became angry and caught the tiny mouse. \"I should eat you for disturbing my sleep!\"",
        "emotion": "anger",
        "duration": 5.0,
        "visual_type": "text_only",
        "scene_type": "C",
        "emphasis_words": [("angry", "color"), ("eat you", "scale")],
        "narration_position": "bottom",
    },
    {
        "text": "\"Please forgive me, mighty lion. If you let me go, maybe one day I can help you.\"",
        "emotion": "fear",
        "duration": 5.0,
        "visual_type": "text_only",
        "scene_type": "D",
        "emphasis_words": [("forgive", "color"), ("help you", "pulse")],
        "narration_position": "top",
    },
    {
        "text": "The lion laughed loudly. \"You? Help me? You are too small!\" But he felt generous and let the mouse go.",
        "emotion": "amusement",
        "duration": 5.5,
        "visual_type": "text_only",
        "scene_type": "E",
        "emphasis_words": [("laughed", "color"), ("too small", "scale"), ("generous", "bold")],
        "narration_position": "bottom",
    },
    {
        "text": "A few days later, the lion got caught in a hunter's net. No matter how hard he tried, he could not escape.",
        "emotion": "suspense",
        "duration": 5.5,
        "visual_type": "text_only",
        "scene_type": "F",
        "emphasis_words": [("hunter's net", "color"), ("could not escape", "pulse")],
        "narration_position": "top",
    },
    {
        "text": "The lion roared loudly for help. The little mouse heard the roar and quickly ran to him.",
        "emotion": "dramatic",
        "duration": 5.0,
        "visual_type": "text_only",
        "scene_type": "G",
        "emphasis_words": [("roared", "scale"), ("quickly ran", "bold")],
        "narration_position": "bottom",
    },
    {
        "text": "The mouse gnawed the ropes with his sharp teeth. Soon the net broke and the lion was free!",
        "emotion": "triumph",
        "duration": 5.0,
        "visual_type": "text_only",
        "scene_type": "B",
        "emphasis_words": [("gnawed", "color"), ("free", "scale")],
        "narration_position": "top",
    },
    {
        "text": "\"I was wrong. Even a small friend can be a great help.\"",
        "emotion": "warmth",
        "duration": 4.0,
        "visual_type": "text_only",
        "scene_type": "C",
        "emphasis_words": [("small friend", "color"), ("great help", "bold")],
        "narration_position": "bottom",
    },
    {
        "text": "Kindness is never wasted. 🐭🦁",
        "emotion": "joy",
        "is_outro": True,
        "duration": 3.5,
        "visual_type": "text_only",
        "scene_type": "H",
        "setup_text": "Moral of the Story",
        "emphasis_words": [("Kindness", "pulse"), ("never wasted", "scale")],
        "narration_position": "top",
    },
]

# Effects variety per scene
EFFECTS_PLAN = [
    SceneEffectsPlan(screen_index=0, text_entry="scale_bounce", text_exit="fade_out",
                     text_continuous="glow_pulse", scene_transition="crossfade",
                     overlay_effect="subtle_grain", background_effect="bg_gradient_shift"),
    SceneEffectsPlan(screen_index=1, text_entry="slide_up", text_exit="dissolve_out",
                     text_continuous="breathe", scene_transition="blur_transition",
                     overlay_effect="bokeh_overlay", background_effect="bg_color_breathe"),
    SceneEffectsPlan(screen_index=2, text_entry="stamp_in", text_exit="flick_off",
                     text_continuous="shake", scene_transition="flash_transition",
                     overlay_effect="fire_embers", background_effect="bg_pulse"),
    SceneEffectsPlan(screen_index=3, text_entry="elastic_drop", text_exit="evaporate",
                     text_continuous="wave_motion", scene_transition="circle_wipe",
                     overlay_effect="dust_particles", background_effect="bg_particle_float"),
    SceneEffectsPlan(screen_index=4, text_entry="grow_from_center", text_exit="swipe_wipe",
                     text_continuous="float_drift", scene_transition="slide_horizontal",
                     overlay_effect="subtle_grain", background_effect="bg_aurora"),
    SceneEffectsPlan(screen_index=5, text_entry="curtain_reveal", text_exit="blur_exit",
                     text_continuous="flicker", scene_transition="glitch_transition",
                     overlay_effect="scan_lines", background_effect="bg_radial_pulse"),
    SceneEffectsPlan(screen_index=6, text_entry="zoom_blur_in", text_exit="scale_shrink",
                     text_continuous="heartbeat", scene_transition="cube_rotate_3d",
                     overlay_effect="chromatic_aberration", background_effect="bg_pulse"),
    SceneEffectsPlan(screen_index=7, text_entry="split_reveal", text_exit="flip_out",
                     text_continuous="fire_flicker", scene_transition="page_flip_3d",
                     overlay_effect="sparkle_overlay", background_effect="bg_gradient_shift"),
    SceneEffectsPlan(screen_index=8, text_entry="fade_in", text_exit="fade_out",
                     text_continuous="pendulum", scene_transition="morph",
                     overlay_effect="bokeh_overlay", background_effect="bg_color_breathe"),
    SceneEffectsPlan(screen_index=9, text_entry="slide_up", text_exit="dissolve_out",
                     text_continuous="glow_pulse", scene_transition="dissolve",
                     overlay_effect="subtle_grain", background_effect="bg_aurora"),
]


def build_screenplay() -> StoryScreenplay:
    """Build the manually crafted screenplay."""
    screens = []
    for i, s in enumerate(SCREENS):
        screens.append(ScreenSegment(
            index=i,
            text=s["text"],
            duration=s["duration"],
            visual_type=s["visual_type"],
            scene_type=s["scene_type"],
            emotion=s["emotion"],
            is_intro=s.get("is_intro", False),
            is_outro=s.get("is_outro", False),
            setup_text=s.get("setup_text", ""),
            narration_position=s.get("narration_position", "top"),
            emphasis_words=[EmphasisWord(text=w, style=st) for w, st in s.get("emphasis_words", [])],
        ))
    return StoryScreenplay(
        title="The Lion and the Mouse",
        brand_text="Project HER",
        screens=screens,
        mood="storytelling",
        hook="An ancient fable about kindness",
        cta="Kindness is never wasted 🐭🦁",
        content_mode="article",
    )


async def generate_narration(screenplay: StoryScreenplay, output_dir: Path) -> list[NarrationClip]:
    """Generate real narration using edge-tts with word-level timestamps."""
    audio_dir = ensure_dir(output_dir / "audio")
    clips = []

    for screen in screenplay.screens:
        communicate = edge_tts.Communicate(
            text=screen.text,
            voice=config.DEFAULT_VOICE,
            rate=config.NARRATION_RATE,
            boundary="WordBoundary",
        )

        audio_path = audio_dir / f"narration_{screen.index:02d}.mp3"
        audio_chunks = []
        word_timings = []

        # Stream: collect audio bytes AND word boundaries
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                offset = chunk.get("offset", 0)
                duration_ns = chunk.get("duration", 0)
                text = chunk.get("text", "")
                start_sec = offset / 10_000_000
                dur_sec = duration_ns / 10_000_000
                if text.strip():
                    word_timings.append(WordTiming(
                        word=text.strip(),
                        start=round(start_sec, 3),
                        end=round(start_sec + dur_sec, 3),
                    ))

        # Write audio file
        audio_path.write_bytes(b"".join(audio_chunks))

        # Get duration from last word timing (with small pad)
        duration = word_timings[-1].end + 0.3 if word_timings else screen.duration

        clips.append(NarrationClip(
            key_point_index=screen.index,
            audio_path=audio_path,
            duration=duration,
            word_timings=word_timings,
        ))

        logger.info(
            "  [%d] Narration: %.1fs, %d words → %s",
            screen.index, duration, len(word_timings), audio_path.name,
        )

    return clips


def main():
    start = time.time()
    output_dir = Path(config.OUTPUT_DIR) / "test_remotion_lion"
    ensure_dir(output_dir)

    logger.info("=" * 60)
    logger.info("  REMOTION TEST: The Lion and the Mouse")
    logger.info("=" * 60)

    # 1. Build screenplay
    logger.info("\n[1/4] Building screenplay...")
    screenplay = build_screenplay()
    logger.info("  → %d screens, mood=%s", len(screenplay.screens), screenplay.mood)

    # 2. Generate narration (real TTS)
    logger.info("\n[2/4] Generating narration (edge-tts)...")
    narrations = asyncio.run(generate_narration(screenplay, output_dir))
    total_duration = sum(n.duration for n in narrations)
    logger.info("  → Total narration: %.1fs across %d clips", total_duration, len(narrations))

    # 3. Build effects plan
    logger.info("\n[3/4] Building VFX effects plan...")
    effects_plan = VideoEffectsPlan(
        scenes=EFFECTS_PLAN,
        overall_mood="storytelling",
        visual_theme="cinematic",
    )
    for sp in effects_plan.scenes:
        logger.info(
            "  [%d] entry=%s exit=%s transition=%s overlay=%s bg=%s",
            sp.screen_index, sp.text_entry, sp.text_exit,
            sp.scene_transition, sp.overlay_effect, sp.background_effect,
        )

    # 4. Render with Remotion
    logger.info("\n[4/4] Rendering with Remotion...")
    renderer = RemotionRenderer(
        video_format="vertical",
        visual_style="claymorphism",
    )

    # No AI images for this test — all text_only scenes
    images: list[AIImageAsset] = []

    result = renderer.render(
        screenplay=screenplay,
        images=images,
        narrations=narrations,
        output_dir=output_dir,
        output_filename="lion_and_mouse.mp4",
        effects_plan=effects_plan,
        brand_text="Project HER",
    )

    elapsed = time.time() - start

    logger.info("\n" + "=" * 60)
    logger.info("  RENDER COMPLETE!")
    logger.info("=" * 60)
    logger.info("  Video: %s", result["video_path"])
    logger.info("  Duration: %.1fs", result["duration"])
    logger.info("  Resolution: %s", result["resolution"])
    logger.info("  Total time: %.1fs", elapsed)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
