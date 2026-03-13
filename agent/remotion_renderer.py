"""
Project HER v2.0 – Remotion Renderer Bridge
=============================================
Converts Python pipeline data to Remotion-compatible JSON,
invokes the Remotion CLI to render, and returns the output video path.

Usage (from orchestrator):
    from agent.remotion_renderer import RemotionRenderer
    renderer = RemotionRenderer()
    result = renderer.render(
        screenplay=screenplay,
        images=images,
        narrations=narrations,
        effects_plan=effects_plan,
        output_dir=output_dir,
        output_filename="output.mp4",
    )
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import config

logger = logging.getLogger("remotion_renderer")

# ── Locate Remotion project ──────────────────────────

REMOTION_DIR = Path(__file__).resolve().parent.parent / "remotion"
REMOTION_ENTRY = REMOTION_DIR / "src" / "index.ts"


class RemotionRenderer:
    """
    Renders video using the Remotion Node.js/React pipeline.

    Flow:
    1. Convert Python dataclasses (StoryScreenplay, AIImageAsset,
       NarrationClip, VideoEffectsPlan) to a single JSON blob
       matching Remotion's VideoProps schema.
    2. Write JSON to a temp file in output_dir.
    3. Invoke `npx remotion render` via subprocess.
    4. Return the rendered MP4 path.
    """

    def __init__(
        self,
        video_format: str = "vertical",
        platform: str = "",
        visual_style: str = "",
    ):
        self.video_format = video_format
        self.platform = platform
        self.visual_style = visual_style or config.DEFAULT_VISUAL_STYLE

        # Resolution — accept 'portrait' as alias for 'vertical'
        fmt_key = "vertical" if video_format == "portrait" else video_format
        fmt = config.VIDEO_FORMATS.get(fmt_key, config.VIDEO_FORMATS["vertical"])
        self.W = fmt["width"]
        self.H = fmt["height"]
        self.FPS = config.FPS

        # Style tokens
        self._vs = config.VISUAL_STYLES.get(self.visual_style, config.VISUAL_STYLES["claymorphism"])

    # ──────────────────────────────────────────────────
    #  PUBLIC API
    # ──────────────────────────────────────────────────

    def render(
        self,
        screenplay,   # StoryScreenplay
        images: list,  # list[AIImageAsset]
        narrations: list,  # list[NarrationClip]
        output_dir: Path,
        output_filename: str = "output_video.mp4",
        effects_plan=None,  # VideoEffectsPlan | None
        include_subtitles: bool = True,
        color_grade: str = "none",
        watermark: str = "",
        brand_text: str = "",
    ) -> dict:
        """
        Render video using Remotion. Returns dict with:
        - video_path, duration, resolution, srt_path, thumbnail_path
        """
        start_time = time.time()
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Step 0: Stage assets into remotion/public/ so Remotion can serve them
        self._stage_assets(narrations, images)

        # Step 1: Build Remotion-compatible JSON props
        props = self._build_props(
            screenplay=screenplay,
            images=images,
            narrations=narrations,
            effects_plan=effects_plan,
            watermark=watermark or config.WATERMARK_TEXT or "",
            brand_text=brand_text or screenplay.brand_text or "",
        )

        # Step 2: Write props to JSON file
        props_path = output_dir / "remotion_props.json"
        with open(props_path, "w", encoding="utf-8") as f:
            json.dump(props, f, indent=2, default=str)
        logger.info("Remotion props written to %s (%d screens)", props_path, len(props["screens"]))

        # Step 3: Ensure node_modules exist
        self._ensure_installed()

        # Step 4: Invoke Remotion render
        output_path = output_dir / output_filename
        self._invoke_remotion(props_path, output_path)

        elapsed = time.time() - start_time
        total_duration = sum(s.get("duration", 0) for s in props["screens"])
        logger.info("Remotion render complete in %.1fs → %s", elapsed, output_path)

        return {
            "video_path": output_path,
            "srt_path": None,  # TODO: generate SRT from word timings
            "thumbnail_path": None,
            "duration": total_duration,
            "resolution": f"{self.W}x{self.H}",
        }

    # ──────────────────────────────────────────────────
    #  STAGE ASSETS INTO remotion/public/
    # ──────────────────────────────────────────────────

    def _stage_assets(self, narrations: list, images: list) -> None:
        """
        Copy audio and image files into remotion/public/ so Remotion's
        static file server can serve them. Sets _audio_map and _image_map
        for path lookups in _build_props.
        """
        public_dir = REMOTION_DIR / "public"
        audio_dir = public_dir / "audio"
        img_dir = public_dir / "images"
        audio_dir.mkdir(parents=True, exist_ok=True)
        img_dir.mkdir(parents=True, exist_ok=True)

        self._audio_map: dict[str, str] = {}
        self._image_map: dict[str, str] = {}

        for n in narrations:
            src = Path(n.audio_path)
            if src.exists():
                dst_name = f"narration_{n.key_point_index:02d}{src.suffix}"
                dst = audio_dir / dst_name
                shutil.copy2(str(src), str(dst))
                # staticFile path (relative to public/)
                self._audio_map[str(src.resolve())] = f"audio/{dst_name}"

        for img in images:
            src = Path(img.local_path)
            if src.exists():
                dst_name = f"img_{img.screen_index:02d}_{img.sub_index}{src.suffix}"
                dst = img_dir / dst_name
                shutil.copy2(str(src), str(dst))
                self._image_map[str(src.resolve())] = f"images/{dst_name}"

        logger.info(
            "Staged %d audio + %d image assets into remotion/public/",
            len(self._audio_map), len(self._image_map),
        )

    # ──────────────────────────────────────────────────
    #  BUILD PROPS
    # ──────────────────────────────────────────────────

    def _build_props(
        self,
        screenplay,
        images: list,
        narrations: list,
        effects_plan,
        watermark: str,
        brand_text: str,
    ) -> dict:
        """Convert Python pipeline data to Remotion VideoProps JSON."""

        # Build lookup maps
        image_map: dict[int, list] = {}
        for img in images:
            image_map.setdefault(img.screen_index, []).append(img)
        for k in image_map:
            image_map[k].sort(key=lambda x: x.sub_index)

        narration_map: dict[int, object] = {}
        for n in narrations:
            narration_map[n.key_point_index] = n

        effects_map: dict[int, object] = {}
        if effects_plan:
            for sp in effects_plan.scenes:
                effects_map[sp.screen_index] = sp

        # Build screens
        screens = []
        for screen in screenplay.screens:
            idx = screen.index
            narr = narration_map.get(idx)
            imgs = image_map.get(idx, [])
            efx = effects_map.get(idx)

            # Resolve image paths via staged public/ directory
            image_paths = []
            for img in imgs:
                abs_path = str(Path(img.local_path).resolve())
                staged = self._image_map.get(abs_path, "")
                image_paths.append(staged if staged else abs_path)

            # Word timings
            word_timings = []
            if narr and hasattr(narr, "word_timings"):
                for wt in narr.word_timings:
                    word_timings.append({
                        "word": wt.word,
                        "start": wt.start,
                        "end": wt.end,
                    })

            # Emphasis words
            emphasis_words = []
            for ew in screen.emphasis_words:
                emphasis_words.append({
                    "text": ew.text,
                    "style": ew.style,
                })

            # Effects for this scene
            effects_data = None
            if efx:
                effects_data = {
                    "screen_index": efx.screen_index,
                    "text_entry": efx.text_entry,
                    "text_entry_params": efx.text_entry_params or {},
                    "text_exit": efx.text_exit,
                    "text_exit_params": efx.text_exit_params or {},
                    "text_continuous": efx.text_continuous,
                    "text_continuous_params": efx.text_continuous_params or {},
                    "image_entry": efx.image_entry,
                    "image_entry_params": efx.image_entry_params or {},
                    "image_treatment": efx.image_treatment,
                    "image_treatment_params": efx.image_treatment_params or {},
                    "image_exit": efx.image_exit,
                    "image_exit_params": efx.image_exit_params or {},
                    "scene_transition": efx.scene_transition,
                    "scene_transition_params": efx.scene_transition_params or {},
                    "overlay_effect": efx.overlay_effect,
                    "overlay_params": efx.overlay_params or {},
                    "background_effect": efx.background_effect,
                    "background_params": efx.background_params or {},
                    "emphasis_style": efx.emphasis_style,
                    "emphasis_params": efx.emphasis_params or {},
                    "reasoning": efx.reasoning or "",
                }

            # Audio path — use staged public/ path
            audio_path = ""
            audio_duration = 0.0
            if narr:
                abs_path = str(Path(narr.audio_path).resolve())
                staged = self._audio_map.get(abs_path, "")
                audio_path = staged if staged else abs_path
                audio_duration = narr.duration

            # Screen duration: use narration duration as primary source
            duration = audio_duration if audio_duration > 0 else screen.duration

            screen_data = {
                "index": idx,
                "text": screen.text,
                "duration": duration,
                "visual_type": screen.visual_type,
                "scene_type": screen.scene_type,
                "emotion": screen.emotion,
                "is_intro": screen.is_intro,
                "is_outro": screen.is_outro,
                "setup_text": screen.setup_text or "",
                "subject_text": screen.subject_text or "",
                "caption_text": screen.caption_text or "",
                "speaker": screen.speaker or "",
                "character_name": screen.character_name or "",
                "narration_position": screen.narration_position,
                "emphasis_words": emphasis_words,
                "image_paths": image_paths,
                "audio_path": audio_path,
                "audio_duration": audio_duration,
                "word_timings": word_timings,
                "effects": effects_data,
            }
            screens.append(screen_data)

        # Visual style tokens → Remotion format
        vs = self._vs
        visual_style = {
            "name": self.visual_style,
            "bg_center_color": list(vs.get("bg_center_color", (240, 235, 225))),
            "bg_edge_color": list(vs.get("bg_edge_color", (215, 206, 194))),
            "text_dark": list(vs.get("text_dark", (45, 35, 30))),
            "text_light": list(vs.get("text_light", (255, 255, 255))),
            "primary": list(vs.get("primary", (255, 136, 0))),
            "secondary": list(vs.get("secondary", (75, 140, 200))),
            "accent": list(vs.get("accent", (255, 87, 51))),
            "card_bg": list(vs.get("card_bg", (255, 255, 255))) + [200],  # add alpha
            "card_radius": vs.get("card_radius", 24),
            "image_corner_radius": vs.get("image_corner_radius", 20),
            "highlight_color": list(vs.get("highlight_color", (255, 136, 0))),
            "highlight_text": list(vs.get("highlight_text", (255, 255, 255))),
        }
        # Ensure card_bg has exactly 4 values
        if len(visual_style["card_bg"]) == 3:
            visual_style["card_bg"].append(200)
        elif len(visual_style["card_bg"]) > 4:
            visual_style["card_bg"] = visual_style["card_bg"][:4]

        return {
            "title": screenplay.title,
            "hook": screenplay.hook or "",
            "brand_text": brand_text,
            "watermark": watermark,
            "mood": screenplay.mood or "neutral",
            "content_mode": screenplay.content_mode or "article",
            "screens": screens,
            "visual_style": visual_style,
            "fps": self.FPS,
            "width": self.W,
            "height": self.H,
            "cta": screenplay.cta or "Thanks for watching!",
            "visual_theme": effects_plan.visual_theme if effects_plan else "dynamic",
        }

    # ──────────────────────────────────────────────────
    #  NODE.JS / REMOTION INVOCATION
    # ──────────────────────────────────────────────────

    def _ensure_installed(self) -> None:
        """Run npm install if node_modules doesn't exist."""
        node_modules = REMOTION_DIR / "node_modules"
        if not node_modules.exists():
            logger.info("Installing Remotion dependencies (first run)...")
            result = subprocess.run(
                ["npm", "install"],
                cwd=str(REMOTION_DIR),
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                logger.error("npm install failed:\n%s", result.stderr)
                raise RuntimeError(f"npm install failed: {result.stderr[:500]}")
            logger.info("Remotion dependencies installed successfully")

    def _invoke_remotion(self, props_path: Path, output_path: Path) -> None:
        """
        Call `npx remotion render` to produce the MP4.
        """
        cmd = [
            "npx", "remotion", "render",
            str(REMOTION_ENTRY),
            "ProjectHER",  # composition ID
            str(output_path),
            "--props", str(props_path),
            "--concurrency", str(min(os.cpu_count() or 4, 8)),
            "--image-format", "jpeg",
            "--jpeg-quality", "90",
            "--log", "verbose",
            "--overwrite",
        ]

        logger.info("Invoking Remotion render:\n  %s", " ".join(cmd))

        result = subprocess.run(
            cmd,
            cwd=str(REMOTION_DIR),
            capture_output=True,
            text=True,
            timeout=600,  # 10 min max
        )

        if result.stdout:
            for line in result.stdout.strip().split("\n")[-20:]:
                logger.info("  [remotion] %s", line)

        if result.returncode != 0:
            logger.error("Remotion render failed (code %d):\n%s", result.returncode, result.stderr[-1000:])
            raise RuntimeError(
                f"Remotion render failed (exit {result.returncode}): "
                f"{result.stderr[-300:]}"
            )

        if not output_path.exists():
            raise FileNotFoundError(f"Remotion did not produce output at {output_path}")

        logger.info("Remotion render successful → %s (%.1f MB)", output_path, output_path.stat().st_size / 1e6)


# ── Convenience function ─────────────────────────────

def render_with_remotion(
    screenplay,
    images: list,
    narrations: list,
    output_dir: Path,
    output_filename: str = "output_video.mp4",
    effects_plan=None,
    video_format: str = "portrait",
    visual_style: str = "",
    brand_text: str = "",
    watermark: str = "",
) -> dict:
    """
    One-shot convenience function for Remotion rendering.
    Can be used as a drop-in replacement for compositor.compose().
    """
    renderer = RemotionRenderer(
        video_format=video_format,
        visual_style=visual_style,
    )
    return renderer.render(
        screenplay=screenplay,
        images=images,
        narrations=narrations,
        output_dir=output_dir,
        output_filename=output_filename,
        effects_plan=effects_plan,
        brand_text=brand_text,
        watermark=watermark,
    )
