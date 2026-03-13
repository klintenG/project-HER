"""
Project HER v2.0 – Video Compositor
Next-gen video assembly with themes, animated captions, transitions,
background music, sound effects, and cinematic scene layouts.
(MoviePy v2 compatible — Pillow rendering, no ImageMagick)
"""

from __future__ import annotations

import logging
import random
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
    CompositeAudioClip,
    ImageClip,
    VideoClip,
    VideoFileClip,
    ColorClip,
    concatenate_videoclips,
    vfx,
)

import config
from agent.analyzer import KeyPoint
from agent.visuals import ImageAsset
from agent.narration import NarrationClip
from agent.audio_engine import AudioEngine, select_mood_for_tone
from utils.helpers import wrap_text, ensure_dir, generate_srt

logger = logging.getLogger(__name__)


class VideoCompositor:
    """
    Next-gen video compositor with:
    - Theme-aware styling (cinematic, neon, minimal, playful, etc.)
    - Karaoke-style word-level animated captions
    - Multiple transition types (fade, slide, zoom, wipe)
    - Procedural background music & sound effects
    - Cinematic vignette and gradient overlays
    - Dynamic scene layouts
    """

    def __init__(
        self,
        video_format: str = "vertical",
        theme: str = "cinematic",
        caption_style: str = "karaoke",
        transition: str = "fade",
    ):
        fmt = config.VIDEO_FORMATS.get(video_format, config.VIDEO_FORMATS["vertical"])
        self.width = fmt["width"]
        self.height = fmt["height"]
        self.format_name = video_format
        self.fps = config.FPS

        # Theme configuration
        self.theme = config.THEMES.get(theme, config.THEMES["cinematic"])
        self.theme_name = theme

        # Caption style
        self.caption_config = config.CAPTION_STYLES.get(
            caption_style, config.CAPTION_STYLES["karaoke"]
        )
        self.caption_style = caption_style

        # Transition type
        self.transition = transition if transition in config.AVAILABLE_TRANSITIONS else "fade"

        # Audio engine
        self.audio_engine = AudioEngine()

    def compose(
        self,
        title: str,
        key_points: list[KeyPoint],
        images: list[ImageAsset],
        narrations: list[NarrationClip],
        output_dir: Path,
        output_filename: str = "output_video.mp4",
        include_subtitles: bool = True,
        tone: str = "informative",
        hook_text: Optional[str] = None,
        cta_text: Optional[str] = None,
        color_grade: str = "none",
    ) -> dict:
        """Compose the final video with all v2.0 enhancements."""
        ensure_dir(output_dir)

        image_map = {img.key_point_index: img for img in images}
        narration_map = {n.key_point_index: n for n in narrations}

        scenes = []
        transition_list = self._get_transition_sequence(len(key_points))

        # ── 1. Hook Card / Custom Intro ──────────────────
        hook_duration = 3.5
        custom_intro = self._try_custom_intro()
        if custom_intro is not None:
            hook_scene = custom_intro
            hook_duration = custom_intro.duration
            logger.info("Using custom intro (%.1fs)", hook_duration)
        elif self.theme.get("explainer_mode"):
            hook_scene = self._create_explainer_hook_card(
                title=title,
                hook_text=hook_text,
                duration=hook_duration,
            )
        else:
            hook_scene = self._create_hook_card(
                title=title,
                hook_text=hook_text,
                duration=hook_duration,
            )
        scenes.append(hook_scene)

        # ── 2. Content Scenes ─────────────────────────────
        for idx, kp in enumerate(key_points):
            image_asset = image_map.get(kp.index)
            narration_clip = narration_map.get(kp.index)

            if not image_asset or not narration_clip:
                logger.warning("Missing assets for key point %d, skipping", kp.index)
                continue

            scene = self._create_content_scene(
                key_point=kp,
                image_asset=image_asset,
                narration=narration_clip,
                include_subtitles=include_subtitles,
                transition_type=transition_list[idx % len(transition_list)],
                scene_index=idx,
            )
            scenes.append(scene)

        if len(scenes) <= 1:
            raise RuntimeError("No content scenes were created.")

        # ── 3. Outro Card / Custom Outro ──────────────────
        outro_duration = 2.5
        custom_outro = self._try_custom_outro(cta_text=cta_text)
        if custom_outro is not None:
            outro_scene = custom_outro
            outro_duration = custom_outro.duration
            logger.info("Using custom outro (%.1fs)", outro_duration)
        elif self.theme.get("explainer_mode"):
            outro_scene = self._create_explainer_outro_card(
                duration=outro_duration, cta_text=cta_text
            )
        else:
            outro_scene = self._create_outro_card(
                duration=outro_duration, cta_text=cta_text
            )
        scenes.append(outro_scene)

        # ── 4. Concatenate Scenes ─────────────────────────
        logger.info("Concatenating %d scenes...", len(scenes))
        final_video = concatenate_videoclips(scenes, method="compose")

        # ── 5. Background Music (custom file or procedural) ─
        try:
            custom_bgm = config.CUSTOM_BGM_PATH
            if custom_bgm and Path(custom_bgm).exists():
                bgm_audio = (
                    AudioFileClip(str(custom_bgm))
                    .with_effects([
                        vfx.MultiplyVolume(config.BGM_VOLUME / 0.12),
                    ])
                )
                # Loop or trim to match video length
                if bgm_audio.duration < final_video.duration:
                    loops_needed = int(final_video.duration / bgm_audio.duration) + 1
                    bgm_clips = [
                        bgm_audio.with_start(i * bgm_audio.duration)
                        for i in range(loops_needed)
                    ]
                    bgm_audio = CompositeAudioClip(bgm_clips).with_duration(final_video.duration)
                else:
                    bgm_audio = bgm_audio.with_duration(final_video.duration)
                logger.info("Custom BGM loaded: %s", custom_bgm)
            else:
                mood = select_mood_for_tone(tone)
                bgm_path = self.audio_engine.generate_background_music(
                    duration=final_video.duration,
                    mood=mood,
                    output_dir=output_dir,
                )
                bgm_audio = AudioFileClip(str(bgm_path)).with_duration(final_video.duration)
                logger.info("Background music mixed: mood=%s", mood)

            # Mix BGM with existing narration audio
            if final_video.audio is not None:
                mixed_audio = CompositeAudioClip([final_video.audio, bgm_audio])
                final_video = final_video.with_audio(mixed_audio)
            else:
                final_video = final_video.with_audio(bgm_audio)

        except Exception as e:
            logger.warning("Could not add background music: %s", e)

        # ── 5b. Transition SFX ────────────────────────────
        if config.SFX_ENABLED:
            try:
                sfx_clips = self._generate_transition_sfx(
                    scenes=scenes,
                    transition_list=transition_list,
                    hook_duration=hook_duration,
                    output_dir=output_dir,
                )
                if sfx_clips:
                    audio_layers = [final_video.audio] if final_video.audio else []
                    audio_layers.extend(sfx_clips)
                    final_video = final_video.with_audio(
                        CompositeAudioClip(audio_layers)
                    )
                    logger.info("Transition SFX mixed: %d clips", len(sfx_clips))
            except Exception as e:
                logger.warning("Could not add transition SFX: %s", e)

        # ── 5c. Color Grading ─────────────────────────────
        grade_key = color_grade or config.DEFAULT_COLOR_GRADE
        if grade_key != "none" and grade_key in config.COLOR_GRADES:
            try:
                final_video = self._apply_color_grade(final_video, grade_key)
                logger.info("Color grade applied: %s", grade_key)
            except Exception as e:
                logger.warning("Color grading failed: %s", e)

        # ── 6. Render ─────────────────────────────────────
        output_path = output_dir / output_filename
        logger.info(
            "Rendering video: %s (%.1fs @ %dx%d)",
            output_path.name,
            final_video.duration,
            self.width,
            self.height,
        )

        final_video.write_videofile(
            str(output_path),
            fps=self.fps,
            codec=config.VIDEO_CODEC,
            audio_codec=config.AUDIO_CODEC,
            bitrate=config.VIDEO_BITRATE,
            logger="bar",
            threads=config.RENDER_THREADS,
        )

        # ── 7. Generate SRT file ─────────────────────────
        srt_path = None
        if include_subtitles:
            srt_path = self._generate_srt_file(
                narrations, output_dir, title_duration=hook_duration
            )

        # ── 8. Generate Thumbnail ─────────────────────────
        thumbnail_path = self._generate_thumbnail(
            title=title,
            first_image=images[0] if images else None,
            output_dir=output_dir,
        )

        # Clean up
        final_video.close()
        for scene in scenes:
            scene.close()

        total_duration = sum(n.duration for n in narrations) + hook_duration + outro_duration

        result = {
            "video_path": output_path,
            "srt_path": srt_path,
            "thumbnail_path": thumbnail_path,
            "duration": total_duration,
            "resolution": f"{self.width}x{self.height}",
            "format": self.format_name,
        }
        logger.info("Video rendered successfully: %s", output_path)
        return result

    # ══════════════════════════════════════════════════════
    # SCENE BUILDERS
    # ══════════════════════════════════════════════════════

    def _create_hook_card(
        self,
        title: str,
        hook_text: Optional[str],
        duration: float = 3.5,
    ) -> CompositeVideoClip:
        """
        Create a cinematic hook/intro card.
        Uses theme colors, gradient background, and animated title.
        """
        bg_color = self.theme["bg_color"]
        accent = self.theme["accent_color"]
        text_color = self.theme["text_color"]
        title_size = self.theme["title_font_size"]

        # Animated gradient background
        bg_clip = self._create_gradient_bg(duration, bg_color, accent)

        layers = [bg_clip]

        # Vignette overlay
        if self.theme.get("vignette"):
            vig = self._create_vignette(duration)
            layers.append(vig)

        # Accent line / bar
        bar_img = self._render_accent_bar(accent)
        bar_clip = (
            ImageClip(np.array(bar_img))
            .with_duration(duration)
            .with_position(("center", int(self.height * 0.38)))
            .with_effects([vfx.CrossFadeIn(0.4)])
        )
        layers.append(bar_clip)

        # Title text
        title_img = self._render_text_image(
            text=title,
            font_size=title_size,
            max_width=self.width - 2 * config.TEXT_MARGIN - 40,
            color=text_color,
            stroke_color=(0, 0, 0),
            stroke_width=3,
        )
        title_clip = (
            ImageClip(np.array(title_img))
            .with_duration(duration)
            .with_position(("center", int(self.height * 0.42)))
            .with_effects([vfx.CrossFadeIn(0.6)])
        )
        layers.append(title_clip)

        # Hook text (if provided)
        if hook_text:
            hook_img = self._render_text_image(
                text=hook_text,
                font_size=int(title_size * 0.6),
                max_width=self.width - 2 * config.TEXT_MARGIN - 60,
                color=accent,
            )
            hook_clip = (
                ImageClip(np.array(hook_img))
                .with_duration(duration - 0.5)
                .with_start(0.5)
                .with_position(("center", int(self.height * 0.58)))
                .with_effects([vfx.CrossFadeIn(0.5)])
            )
            layers.append(hook_clip)

        scene = CompositeVideoClip(
            layers, size=(self.width, self.height)
        ).with_duration(duration)
        scene = scene.with_effects([vfx.FadeIn(0.3), vfx.FadeOut(0.4)])
        return scene

    # Available scene layouts that rotate per scene
    SCENE_LAYOUTS = ["full_bleed", "split_screen", "lower_third", "side_panel"]

    # Emotion → visual adjustments mapping
    EMOTION_STYLES = {
        "curious": {
            "tint": (0, 50, 120),       # cool blue tint
            "tint_opacity": 0.10,
            "overlay_adjust": 0.0,       # no change
            "kb_preference": "pan_left", # slow pan = exploration
        },
        "excited": {
            "tint": (255, 180, 0),       # warm gold
            "tint_opacity": 0.08,
            "overlay_adjust": -0.05,     # slightly brighter
            "kb_preference": "zoom_in",  # energy
        },
        "serious": {
            "tint": (30, 30, 60),        # dark blue-grey
            "tint_opacity": 0.12,
            "overlay_adjust": 0.08,      # darker
            "kb_preference": "zoom_out", # wide, observational
        },
        "hopeful": {
            "tint": (255, 220, 100),     # warm sunrise
            "tint_opacity": 0.08,
            "overlay_adjust": -0.05,
            "kb_preference": "zoom_in",
        },
        "dramatic": {
            "tint": (80, 0, 0),          # deep red
            "tint_opacity": 0.12,
            "overlay_adjust": 0.10,      # much darker
            "kb_preference": "zoom_in",  # intense close-up
        },
        "playful": {
            "tint": (255, 100, 200),     # pink/magenta
            "tint_opacity": 0.06,
            "overlay_adjust": -0.08,     # brighter
            "kb_preference": "pan_right",
        },
        "calm": {
            "tint": (100, 180, 200),     # soft teal
            "tint_opacity": 0.08,
            "overlay_adjust": -0.03,
            "kb_preference": "pan_left", # slow, peaceful
        },
    }

    def _get_emotion_style(self, emotion: str) -> dict:
        """Get visual style adjustments for a given emotion."""
        return self.EMOTION_STYLES.get(
            emotion,
            {"tint": (0, 0, 0), "tint_opacity": 0.0, "overlay_adjust": 0.0, "kb_preference": None},
        )

    def _create_content_scene(
        self,
        key_point: KeyPoint,
        image_asset: ImageAsset,
        narration: NarrationClip,
        include_subtitles: bool,
        transition_type: str = "fade",
        scene_index: int = 0,
    ) -> CompositeVideoClip:
        """Create a content scene with themed visuals and animated captions."""
        # Route to explainer scene builder if explainer theme is active
        if self.theme.get("explainer_mode"):
            return self._create_explainer_scene(
                key_point=key_point,
                image_asset=image_asset,
                narration=narration,
                include_subtitles=include_subtitles,
                scene_index=scene_index,
            )

        duration = narration.duration + config.SCENE_PADDING
        layout = self.SCENE_LAYOUTS[scene_index % len(self.SCENE_LAYOUTS)]
        emotion = key_point.emotion or "neutral"
        emotion_style = self._get_emotion_style(emotion)
        logger.debug(
            "Scene %d using layout=%s, emotion=%s", scene_index, layout, emotion
        )

        layers = self._build_layout_layers(
            layout=layout,
            key_point=key_point,
            image_asset=image_asset,
            duration=duration,
            scene_index=scene_index,
            emotion_style=emotion_style,
        )

        # ── Animated Captions (Karaoke-style) ─────────────
        if include_subtitles and narration.word_timings:
            caption_clips = self._create_animated_captions(
                narration, duration
            )
            layers.extend(caption_clips)
        elif include_subtitles and narration.subtitle_data:
            subtitle_clips = self._create_subtitle_clips(
                narration.subtitle_data, duration
            )
            layers.extend(subtitle_clips)

        # ── Watermark ─────────────────────────────────────
        wm_clip = self._create_watermark(duration)
        if wm_clip:
            layers.append(wm_clip)

        # ── Audio ─────────────────────────────────────────
        audio = AudioFileClip(str(narration.audio_path))
        if audio.duration > duration:
            audio = audio.with_duration(duration)

        scene = CompositeVideoClip(
            layers, size=(self.width, self.height)
        ).with_duration(duration).with_audio(audio)

        # Apply transition
        scene = self._apply_transition(scene, transition_type)
        return scene

    # ── Layout Builders ───────────────────────────────────

    def _build_layout_layers(
        self,
        layout: str,
        key_point: KeyPoint,
        image_asset: ImageAsset,
        duration: float,
        scene_index: int,
        emotion_style: Optional[dict] = None,
    ) -> list:
        """Route to the correct layout builder."""
        es = emotion_style or {}
        if layout == "split_screen":
            return self._layout_split_screen(key_point, image_asset, duration, scene_index, es)
        elif layout == "lower_third":
            return self._layout_lower_third(key_point, image_asset, duration, scene_index, es)
        elif layout == "side_panel":
            return self._layout_side_panel(key_point, image_asset, duration, scene_index, es)
        else:
            return self._layout_full_bleed(key_point, image_asset, duration, scene_index, es)

    def _layout_full_bleed(
        self, key_point: KeyPoint, image_asset: ImageAsset, duration: float,
        scene_index: int, emotion_style: dict = None,
    ) -> list:
        """Original full-bleed layout: image fills entire frame, headline at top."""
        es = emotion_style or {}
        accent = self.theme["accent_color"]
        text_color = self.theme["text_color"]
        headline_size = self.theme["headline_font_size"]
        overlay_opacity = self.theme["overlay_opacity"] + es.get("overlay_adjust", 0.0)
        overlay_opacity = max(0.0, min(1.0, overlay_opacity))

        if image_asset.asset_type == "video":
            bg_clip = self._create_broll_clip(image_asset.local_path, duration)
        else:
            bg_clip = self._create_ken_burns_clip(
                image_asset.local_path, duration, scene_index,
                kb_direction=es.get("kb_preference"),
            )

        if self.theme.get("gradient_overlay"):
            grad = self._create_gradient_overlay(duration, overlay_opacity)
        else:
            grad = (
                ColorClip(size=(self.width, self.height), color=(0, 0, 0))
                .with_duration(duration)
                .with_opacity(overlay_opacity)
            )

        layers = [bg_clip, grad]

        # Emotion color tint overlay
        tint_color = es.get("tint")
        tint_opacity = es.get("tint_opacity", 0.0)
        if tint_color and tint_opacity > 0:
            tint = (
                ColorClip(size=(self.width, self.height), color=tint_color)
                .with_duration(duration)
                .with_opacity(tint_opacity)
            )
            layers.append(tint)

        if self.theme.get("vignette"):
            layers.append(self._create_vignette(duration))

        headline_bar = self._render_headline_with_bar(
            key_point.headline, headline_size, accent, text_color
        )
        headline_clip = (
            ImageClip(np.array(headline_bar))
            .with_duration(duration)
            .with_position(("center", int(self.height * 0.10)))
            .with_effects([vfx.CrossFadeIn(0.3)])
        )
        layers.append(headline_clip)
        return layers

    def _layout_split_screen(
        self, key_point: KeyPoint, image_asset: ImageAsset, duration: float,
        scene_index: int, emotion_style: dict = None,
    ) -> list:
        """Split-screen: image top 55%, themed panel bottom 45% with headline."""
        es = emotion_style or {}
        accent = self.theme["accent_color"]
        text_color = self.theme["text_color"]
        bg_color = self.theme["bg_color"]
        headline_size = self.theme["headline_font_size"]
        split_y = int(self.height * 0.55)

        # Top half: image/video cropped
        if image_asset.asset_type == "video":
            bg_clip = self._create_broll_clip(image_asset.local_path, duration)
        else:
            bg_clip = self._create_ken_burns_clip(
                image_asset.local_path, duration, scene_index,
                kb_direction=es.get("kb_preference"),
            )

        # Bottom panel: solid colored background
        panel_h = self.height - split_y
        panel_img = Image.new("RGB", (self.width, panel_h), bg_color)
        # Accent stripe at the top of the panel
        stripe_h = 4
        draw = ImageDraw.Draw(panel_img)
        draw.rectangle([(0, 0), (self.width, stripe_h)], fill=accent)

        panel_clip = (
            ImageClip(np.array(panel_img))
            .with_duration(duration)
            .with_position((0, split_y))
        )

        # Headline inside the panel area
        headline_bar = self._render_headline_with_bar(
            key_point.headline, headline_size - 2, accent, text_color
        )
        headline_clip = (
            ImageClip(np.array(headline_bar))
            .with_duration(duration)
            .with_position(("center", split_y + int(panel_h * 0.15)))
            .with_effects([vfx.CrossFadeIn(0.3)])
        )

        layers = [bg_clip, panel_clip, headline_clip]
        return layers

    def _layout_lower_third(
        self, key_point: KeyPoint, image_asset: ImageAsset, duration: float,
        scene_index: int, emotion_style: dict = None,
    ) -> list:
        """Lower-third: image fills frame, thick bar at bottom with headline."""
        es = emotion_style or {}
        accent = self.theme["accent_color"]
        text_color = self.theme["text_color"]
        headline_size = self.theme["headline_font_size"]
        overlay_opacity = self.theme["overlay_opacity"]

        if image_asset.asset_type == "video":
            bg_clip = self._create_broll_clip(image_asset.local_path, duration)
        else:
            bg_clip = self._create_ken_burns_clip(
                image_asset.local_path, duration, scene_index,
                kb_direction=es.get("kb_preference"),
            )

        # Lower-third bar (bottom 20%)
        bar_h = int(self.height * 0.20)
        bar_y = self.height - bar_h
        bar_img = Image.new("RGBA", (self.width, bar_h), (*accent, 220))
        bar_clip = (
            ImageClip(np.array(bar_img))
            .with_duration(duration)
            .with_position((0, bar_y))
        )

        # Gradient above bar for smoother blend
        grad_h = int(self.height * 0.10)
        grad_img = Image.new("RGBA", (self.width, grad_h), (0, 0, 0, 0))
        for y in range(grad_h):
            alpha = int(180 * (y / grad_h))
            for x in range(self.width):
                grad_img.putpixel((x, y), (*accent, alpha))
        grad_clip = (
            ImageClip(np.array(grad_img))
            .with_duration(duration)
            .with_position((0, bar_y - grad_h))
        )

        # Headline inside the lower-third bar
        headline_bar = self._render_headline_with_bar(
            key_point.headline, headline_size - 4, accent, text_color
        )
        headline_clip = (
            ImageClip(np.array(headline_bar))
            .with_duration(duration)
            .with_position(("center", bar_y + int(bar_h * 0.15)))
            .with_effects([vfx.CrossFadeIn(0.4)])
        )

        layers = [bg_clip, grad_clip, bar_clip, headline_clip]

        # Emotion tint overlay (behind the bar, over the image)
        tint_color = es.get("tint")
        tint_opacity = es.get("tint_opacity", 0.0)
        if tint_color and tint_opacity > 0:
            tint = (
                ColorClip(size=(self.width, self.height), color=tint_color)
                .with_duration(duration)
                .with_opacity(tint_opacity)
            )
            layers.insert(1, tint)

        if self.theme.get("vignette"):
            layers.insert(1, self._create_vignette(duration))

        return layers

    def _layout_side_panel(
        self, key_point: KeyPoint, image_asset: ImageAsset, duration: float,
        scene_index: int, emotion_style: dict = None,
    ) -> list:
        """Side-panel: colored panel left 40%, image right 60%."""
        es = emotion_style or {}
        accent = self.theme["accent_color"]
        text_color = self.theme["text_color"]
        bg_color = self.theme["bg_color"]
        headline_size = self.theme["headline_font_size"]
        panel_w = int(self.width * 0.40)
        img_w = self.width - panel_w

        # Left panel — subtly tinted by emotion
        tint_color = es.get("tint")
        if tint_color:
            blended = tuple(
                int(bg_color[i] * 0.85 + tint_color[i] * 0.15) for i in range(3)
            )
        else:
            blended = bg_color
        panel_img = Image.new("RGB", (panel_w, self.height), blended)
        # Accent line on the right edge
        draw = ImageDraw.Draw(panel_img)
        draw.rectangle(
            [(panel_w - 4, 0), (panel_w, self.height)], fill=accent
        )
        panel_clip = (
            ImageClip(np.array(panel_img))
            .with_duration(duration)
            .with_position((0, 0))
        )

        # Right side: image/video sized to fill right portion
        if image_asset.asset_type == "video":
            right_clip = self._create_broll_clip(
                image_asset.local_path, duration, target_w=img_w, target_h=self.height
            )
        else:
            right_clip = self._create_ken_burns_clip(
                image_asset.local_path, duration, scene_index,
                target_w=img_w, target_h=self.height,
                kb_direction=es.get("kb_preference"),
            )
        right_clip = right_clip.with_position((panel_w, 0))

        # Headline in the left panel
        headline_bar = self._render_headline_with_bar(
            key_point.headline, headline_size - 6, accent, text_color,
            max_width=panel_w - 40,
        )
        headline_clip = (
            ImageClip(np.array(headline_bar))
            .with_duration(duration)
            .with_position((20, int(self.height * 0.15)))
            .with_effects([vfx.CrossFadeIn(0.3)])
        )

        layers = [panel_clip, right_clip, headline_clip]
        return layers

    def _create_outro_card(
        self, duration: float = 2.5, cta_text: Optional[str] = None,
    ) -> CompositeVideoClip:
        """Create themed outro card with optional CTA."""
        bg_color = self.theme["bg_color"]
        accent = self.theme["accent_color"]
        text_color = self.theme["text_color"]

        bg_clip = self._create_gradient_bg(duration, bg_color, accent)
        layers = [bg_clip]

        # Smart CTA (shown above branding if available)
        if cta_text:
            cta_img = self._render_text_image(
                text=cta_text,
                font_size=42,
                max_width=self.width - 100,
                color=accent,
                stroke_color=(0, 0, 0),
                stroke_width=2,
            )
            cta_clip = (
                ImageClip(np.array(cta_img))
                .with_duration(duration - 0.2)
                .with_start(0.2)
                .with_position(("center", int(self.height * 0.32)))
                .with_effects([vfx.CrossFadeIn(0.3)])
            )
            layers.append(cta_clip)

        # "Project HER" branding
        brand_y = 0.46 if cta_text else 0.42
        brand_img = self._render_text_image(
            text="Project HER",
            font_size=52,
            max_width=self.width - 120,
            color=accent,
            stroke_color=(0, 0, 0),
            stroke_width=2,
        )
        brand_clip = (
            ImageClip(np.array(brand_img))
            .with_duration(duration)
            .with_position(("center", int(self.height * brand_y)))
        )
        layers.append(brand_clip)

        # Tagline
        tag_y = 0.56 if cta_text else 0.52
        tag_img = self._render_text_image(
            text="AI-Powered Video Generation",
            font_size=28,
            max_width=self.width - 120,
            color=text_color,
        )
        tag_clip = (
            ImageClip(np.array(tag_img))
            .with_duration(duration - 0.3)
            .with_start(0.3)
            .with_position(("center", int(self.height * tag_y)))
            .with_effects([vfx.CrossFadeIn(0.4)])
        )
        layers.append(tag_clip)

        scene = CompositeVideoClip(
            layers, size=(self.width, self.height)
        ).with_duration(duration)
        scene = scene.with_effects([vfx.FadeIn(0.4), vfx.FadeOut(0.8)])
        return scene

    # ══════════════════════════════════════════════════════
    # ANIMATED CAPTIONS (Karaoke-style word highlighting)
    # ══════════════════════════════════════════════════════

    def _create_animated_captions(
        self,
        narration: NarrationClip,
        scene_duration: float,
    ) -> list[ImageClip]:
        """
        Create karaoke-style animated caption clips.
        Each word group shows with the active word highlighted.
        """
        caption_clips = []
        style = self.caption_config
        position_y = int(self.height * style["position"])
        words_per_group = style.get("words_per_group", 4)

        # Use grouped subtitle data with individual word timings
        for group in narration.subtitle_data:
            group_start = group["start"]
            group_end = min(group["end"], scene_duration)
            group_words = group.get("words", [])
            group_text = group["text"]

            if group_end <= group_start:
                continue

            if group_words:
                # Create per-word highlighting within this group
                caption_clips.extend(
                    self._render_karaoke_group(
                        group_words, group_text, group_start, group_end,
                        position_y, scene_duration
                    )
                )
            else:
                # Fallback: static text for this group
                img = self._render_caption_text(
                    group_text,
                    active_word_index=-1,
                    words=[],
                )
                clip = (
                    ImageClip(np.array(img))
                    .with_duration(group_end - group_start)
                    .with_start(group_start)
                    .with_position(("center", position_y))
                )
                caption_clips.append(clip)

        return caption_clips

    def _render_karaoke_group(
        self,
        words: list[dict],
        full_text: str,
        group_start: float,
        group_end: float,
        position_y: int,
        scene_duration: float,
    ) -> list[ImageClip]:
        """Render a word group with sequential word highlighting."""
        clips = []
        word_texts = [w["word"] for w in words]

        for i, word_info in enumerate(words):
            w_start = max(word_info["start"], group_start)
            # End at next word start or group end
            if i + 1 < len(words):
                w_end = words[i + 1]["start"]
            else:
                w_end = group_end

            w_end = min(w_end, scene_duration)
            if w_end <= w_start:
                continue

            # Render with current word highlighted
            img = self._render_caption_text(
                full_text,
                active_word_index=i,
                words=word_texts,
            )
            clip = (
                ImageClip(np.array(img))
                .with_duration(w_end - w_start)
                .with_start(w_start)
                .with_position(("center", position_y))
            )
            clips.append(clip)

        return clips

    def _render_caption_text(
        self,
        full_text: str,
        active_word_index: int,
        words: list[str],
    ) -> Image.Image:
        """
        Render caption text with one word highlighted (karaoke style).
        Returns an RGBA PIL Image.
        """
        style = self.caption_config
        font_size = style["font_size"]
        active_color = style["active_color"]
        inactive_color = style["inactive_color"]
        bg_opacity = style["bg_opacity"]

        font = self._get_font(font_size)
        bold_font = self._get_font(int(font_size * 1.05))

        # Measure full text
        dummy = Image.new("RGBA", (1, 1))
        draw = ImageDraw.Draw(dummy)

        if not words:
            words = full_text.split()

        # Measure each word
        word_widths = []
        space_width = draw.textbbox((0, 0), " ", font=font)[2]
        for w in words:
            bbox = draw.textbbox((0, 0), w, font=font)
            word_widths.append(bbox[2] - bbox[0])

        total_width = sum(word_widths) + space_width * (len(words) - 1)
        text_bbox = draw.textbbox((0, 0), full_text, font=font)
        text_height = text_bbox[3] - text_bbox[1]

        # Image dimensions with padding
        padding_x = 28
        padding_y = 16
        img_width = total_width + 2 * padding_x
        img_height = text_height + 2 * padding_y

        # Clamp to video width
        max_w = self.width - 40
        if img_width > max_w:
            img_width = max_w

        # Create image with rounded-rect background
        img = Image.new("RGBA", (img_width, img_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Draw rounded rectangle background
        self._draw_rounded_rect(
            draw, (0, 0, img_width, img_height),
            radius=14,
            fill=(10, 10, 10, bg_opacity),
        )

        # Draw each word with appropriate color
        x = padding_x
        y = padding_y
        for i, word in enumerate(words):
            is_active = (i == active_word_index)
            color = active_color if is_active else inactive_color
            f = bold_font if is_active else font

            # Draw stroke for active word
            if is_active:
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        if dx != 0 or dy != 0:
                            draw.text((x + dx, y + dy), word, font=f, fill=(0, 0, 0, 200))

            draw.text((x, y), word, font=f, fill=color)
            x += word_widths[i] + space_width

        return img

    # ══════════════════════════════════════════════════════
    # VISUAL EFFECTS
    # ══════════════════════════════════════════════════════

    def _create_ken_burns_clip(
        self,
        image_path: Path,
        duration: float,
        scene_index: int = 0,
        target_w: Optional[int] = None,
        target_h: Optional[int] = None,
        kb_direction: Optional[str] = None,
    ) -> VideoClip:
        """Ken Burns with varied direction per scene. Emotion can override direction."""
        img = Image.open(image_path).convert("RGB")

        vid_w = target_w or self.width
        vid_h = target_h or self.height

        zoom = config.ZOOM_FACTOR
        zoom_w = int(vid_w * zoom)
        zoom_h = int(vid_h * zoom)

        img_ratio = img.width / img.height
        zoom_ratio = zoom_w / zoom_h

        if img_ratio > zoom_ratio:
            new_h = zoom_h
            new_w = int(new_h * img_ratio)
        else:
            new_w = zoom_w
            new_h = int(new_w / img_ratio)

        img = img.resize((new_w, new_h), Image.LANCZOS)
        img_array = np.array(img)

        # Use emotion-driven direction if given, else rotate by scene index
        directions = ["zoom_in", "zoom_out", "pan_left", "pan_right"]
        if kb_direction and kb_direction in directions:
            direction = kb_direction
        else:
            direction = directions[scene_index % len(directions)]

        def make_frame(t):
            progress = t / max(duration, 0.01)

            if direction == "zoom_in":
                current_zoom = 1.0 + (zoom - 1.0) * progress
                x_shift, y_shift = 0, 0
            elif direction == "zoom_out":
                current_zoom = zoom - (zoom - 1.0) * progress
                x_shift, y_shift = 0, 0
            elif direction == "pan_left":
                current_zoom = 1.0 + (zoom - 1.0) * 0.5
                x_shift = int((new_w - vid_w * current_zoom) * 0.3 * progress)
                y_shift = 0
            else:  # pan_right
                current_zoom = 1.0 + (zoom - 1.0) * 0.5
                x_shift = int((new_w - vid_w * current_zoom) * 0.3 * (1 - progress))
                y_shift = 0

            crop_w = int(vid_w * current_zoom)
            crop_h = int(vid_h * current_zoom)
            crop_w = min(crop_w, new_w)
            crop_h = min(crop_h, new_h)

            x_offset = max(0, (new_w - crop_w) // 2 + x_shift)
            y_offset = max(0, (new_h - crop_h) // 2 + y_shift)

            # Clamp
            x_offset = min(x_offset, new_w - crop_w)
            y_offset = min(y_offset, new_h - crop_h)

            cropped = img_array[
                y_offset:y_offset + crop_h,
                x_offset:x_offset + crop_w,
            ]

            frame_img = Image.fromarray(cropped).resize(
                (vid_w, vid_h), Image.LANCZOS
            )
            return np.array(frame_img)

        clip = VideoClip(make_frame, duration=duration).with_fps(self.fps)
        return clip

    def _create_broll_clip(
        self,
        video_path: Path,
        duration: float,
        target_w: Optional[int] = None,
        target_h: Optional[int] = None,
    ) -> VideoClip:
        """
        Create a background clip from a B-roll video file.
        Resizes/crops to fill the frame and loops if needed.
        """
        out_w = target_w or self.width
        out_h = target_h or self.height
        try:
            raw = VideoFileClip(str(video_path))

            # Resize to fill the frame (cover mode)
            vid_ratio = raw.w / raw.h
            frame_ratio = out_w / out_h

            if vid_ratio > frame_ratio:
                scale = out_h / raw.h
            else:
                scale = out_w / raw.w

            new_w = int(raw.w * scale)
            new_h = int(raw.h * scale)
            resized = raw.resized((new_w, new_h))

            # Center crop to exact dimensions
            x_offset = (new_w - out_w) // 2
            y_offset = (new_h - out_h) // 2
            cropped = resized.cropped(
                x1=x_offset, y1=y_offset,
                x2=x_offset + out_w, y2=y_offset + out_h,
            )

            # Loop if video is shorter than scene duration
            if cropped.duration < duration:
                loops = int(duration / cropped.duration) + 1
                cropped = concatenate_videoclips([cropped] * loops)

            clip = cropped.with_duration(duration).without_audio()
            return clip

        except Exception as e:
            logger.warning("B-roll clip failed, falling back to black: %s", e)
            return (
                ColorClip(size=(out_w, out_h), color=(0, 0, 0))
                .with_duration(duration)
                .with_fps(self.fps)
            )

    def _create_gradient_bg(
        self, duration: float, color1: tuple, color2: tuple
    ) -> VideoClip:
        """Create an animated gradient background."""
        w, h = self.width, self.height

        # Pre-render gradient as static image (much faster)
        img = Image.new("RGB", (w, h))
        draw = ImageDraw.Draw(img)

        for y in range(h):
            ratio = y / h
            r = int(color1[0] + (color2[0] - color1[0]) * ratio * 0.3)
            g = int(color1[1] + (color2[1] - color1[1]) * ratio * 0.3)
            b = int(color1[2] + (color2[2] - color1[2]) * ratio * 0.3)
            r = max(0, min(255, r))
            g = max(0, min(255, g))
            b = max(0, min(255, b))
            draw.line([(0, y), (w, y)], fill=(r, g, b))

        img_array = np.array(img)
        clip = ImageClip(img_array).with_duration(duration).with_fps(self.fps)
        return clip

    def _create_gradient_overlay(
        self, duration: float, opacity: float
    ) -> ImageClip:
        """Create a gradient overlay (dark at top and bottom, transparent center)."""
        w, h = self.width, self.height
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Top gradient (dark to transparent)
        for y in range(h // 3):
            alpha = int(255 * opacity * (1 - y / (h // 3)))
            draw.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))

        # Bottom gradient (transparent to dark)
        for y in range(h * 2 // 3, h):
            alpha = int(255 * opacity * ((y - h * 2 // 3) / (h // 3)))
            draw.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))

        img_array = np.array(img)
        clip = ImageClip(img_array).with_duration(duration)
        return clip

    def _create_vignette(self, duration: float) -> ImageClip:
        """Create a cinematic vignette overlay."""
        w, h = self.width, self.height
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))

        # Create radial gradient for vignette
        center_x, center_y = w // 2, h // 2
        max_dist = (center_x ** 2 + center_y ** 2) ** 0.5

        pixels = np.zeros((h, w, 4), dtype=np.uint8)
        y_coords, x_coords = np.mgrid[0:h, 0:w]
        distances = np.sqrt((x_coords - center_x) ** 2 + (y_coords - center_y) ** 2)
        normalized = distances / max_dist

        # Vignette: transparent in center, dark at edges
        alpha = np.clip((normalized - 0.4) * 200, 0, 130).astype(np.uint8)
        pixels[:, :, 3] = alpha

        img = Image.fromarray(pixels, "RGBA")
        img_array = np.array(img)
        clip = ImageClip(img_array).with_duration(duration)
        return clip

    def _render_accent_bar(self, accent_color: tuple) -> Image.Image:
        """Render a thin accent bar / divider line."""
        bar_width = self.width // 3
        bar_height = 4
        img = Image.new("RGBA", (bar_width, bar_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rectangle(
            [0, 0, bar_width, bar_height],
            fill=(*accent_color, 200),
        )
        return img

    def _render_headline_with_bar(
        self,
        text: str,
        font_size: int,
        accent_color: tuple,
        text_color: tuple,
        max_width: Optional[int] = None,
    ) -> Image.Image:
        """Render headline text with a small accent bar above it."""
        font = self._get_font(font_size)
        max_w = max_width or (self.width - 2 * config.TEXT_MARGIN - 40)

        wrapped = wrap_text(text, max_chars=max(max_w // (font_size // 2), 12))
        lines = wrapped.split("\n")

        dummy = Image.new("RGBA", (1, 1))
        draw = ImageDraw.Draw(dummy)
        line_heights = []
        line_widths = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_widths.append(bbox[2] - bbox[0])
            line_heights.append(bbox[3] - bbox[1])

        total_height = sum(line_heights) + (len(lines) - 1) * 10
        total_width = max(line_widths) if line_widths else 100

        padding = 20
        bar_height = 4
        bar_gap = 12

        img_width = total_width + 2 * padding
        img_height = bar_height + bar_gap + total_height + 2 * padding

        img = Image.new("RGBA", (img_width, img_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Accent bar
        bar_width = min(total_width, 80)
        bar_x = (img_width - bar_width) // 2
        draw.rectangle(
            [bar_x, padding, bar_x + bar_width, padding + bar_height],
            fill=(*accent_color, 220),
        )

        # Text
        y = padding + bar_height + bar_gap
        for i, line in enumerate(lines):
            x = (img_width - line_widths[i]) // 2
            # Shadow
            draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 150))
            draw.text((x, y), line, font=font, fill=text_color,
                       stroke_width=2, stroke_fill=(0, 0, 0))
            y += line_heights[i] + 10

        return img

    # ══════════════════════════════════════════════════════
    # EXPLAINER MODE – Clean, Minimal, Educational Video
    # ══════════════════════════════════════════════════════

    def _create_explainer_scene(
        self,
        key_point: KeyPoint,
        image_asset: ImageAsset,
        narration: NarrationClip,
        include_subtitles: bool,
        scene_index: int = 0,
    ) -> CompositeVideoClip:
        """
        Create an explainer-style scene with:
        - Off-white/ivory solid canvas background
        - Centered illustration with muted treatment
        - Progressive text reveal with gentle fade
        - Narration-aware dynamic vertical text positioning
        - Minimal motion (slow pan only), no flashy effects
        """
        duration = narration.duration + config.SCENE_PADDING
        bg_color = self.theme["bg_color"]
        text_color = self.theme["text_color"]
        accent = self.theme["accent_color"]
        secondary_color = self.theme.get("secondary_text_color", (100, 100, 110))
        divider_color = self.theme.get("divider_color", (200, 195, 185))
        padding = self.theme.get("canvas_padding", 80)
        image_ratio = self.theme.get("image_max_ratio", 0.45)
        fade_dur = self.theme.get("text_reveal_fade", 0.4)

        layers = []

        # ── 1. Solid off-white canvas background ─────────
        bg_clip = (
            ColorClip(size=(self.width, self.height), color=bg_color)
            .with_duration(duration)
            .with_fps(self.fps)
        )
        layers.append(bg_clip)

        # ── 2. Illustration image (muted, centered) ──────
        content_w = int(self.width * self.theme.get("content_area_ratio", 0.85))
        img_display_h = int(self.height * image_ratio)
        img_y_start = int(self.height * 0.08)

        img_clip = self._create_explainer_image(
            image_asset, duration, scene_index,
            target_w=content_w - 2 * 20,
            target_h=img_display_h,
        )
        img_x = (self.width - (content_w - 40)) // 2
        img_clip = img_clip.with_position((img_x, img_y_start))
        img_clip = img_clip.with_effects([vfx.CrossFadeIn(fade_dur + 0.2)])
        layers.append(img_clip)

        # ── 3. Thin divider line below image ──────────────
        divider_y = img_y_start + img_display_h + 15
        divider_img = Image.new("RGBA", (content_w - 80, 2), (0, 0, 0, 0))
        draw = ImageDraw.Draw(divider_img)
        draw.rectangle(
            [(0, 0), (content_w - 80, 2)],
            fill=(*divider_color, 150),
        )
        divider_clip = (
            ImageClip(np.array(divider_img))
            .with_duration(duration)
            .with_position(((self.width - (content_w - 80)) // 2, divider_y))
            .with_effects([vfx.CrossFadeIn(fade_dur + 0.3)])
        )
        layers.append(divider_clip)

        # ── 4. Headline text (progressive reveal) ────────
        text_area_top = divider_y + 25
        headline_font_size = self.theme["headline_font_size"]

        # Narration-aware positioning: adjust vertical position
        # based on scene progression (earlier scenes = higher text)
        y_offset = self._get_narration_aware_y(scene_index, total_scenes=6)
        text_y = text_area_top + y_offset

        headline_img = self._render_explainer_text(
            text=key_point.headline,
            font_size=headline_font_size,
            color=text_color,
            max_width=content_w - 2 * padding,
            bold=True,
        )
        headline_clip = (
            ImageClip(np.array(headline_img))
            .with_duration(duration - 0.3)
            .with_start(0.3)
            .with_position(("center", text_y))
            .with_effects([vfx.CrossFadeIn(fade_dur)])
        )
        layers.append(headline_clip)

        # ── 5. Narration text (progressive reveal, staggered) ─
        narration_text = key_point.narration
        narration_font_size = int(headline_font_size * 0.68)
        narration_y = text_y + headline_img.height + 18

        # Split narration into segments for progressive reveal
        segments = self._split_narration_segments(narration_text, max_words=8)
        segment_duration = max(0.5, (duration - 1.0) / max(len(segments), 1))

        for seg_idx, segment_text in enumerate(segments):
            seg_start = 0.6 + seg_idx * segment_duration * 0.7
            seg_end = duration
            if seg_start >= duration:
                break

            seg_img = self._render_explainer_text(
                text=segment_text,
                font_size=narration_font_size,
                color=secondary_color,
                max_width=content_w - 2 * padding,
                bold=False,
            )
            seg_y = narration_y + seg_idx * (seg_img.height + 10)

            # Don't overflow below visible area
            if seg_y + seg_img.height > self.height - 60:
                break

            seg_clip = (
                ImageClip(np.array(seg_img))
                .with_duration(seg_end - seg_start)
                .with_start(seg_start)
                .with_position(("center", seg_y))
                .with_effects([vfx.CrossFadeIn(fade_dur)])
            )
            layers.append(seg_clip)

        # ── 6. Animated captions (reveal style) ──────────
        if include_subtitles and narration.word_timings:
            caption_clips = self._create_explainer_captions(narration, duration)
            layers.extend(caption_clips)
        elif include_subtitles and narration.subtitle_data:
            caption_clips = self._create_subtitle_clips(narration.subtitle_data, duration)
            layers.extend(caption_clips)

        # ── 7. Watermark ──────────────────────────────────
        wm_clip = self._create_watermark(duration)
        if wm_clip:
            layers.append(wm_clip)

        # ── 8. Audio ──────────────────────────────────────
        audio = AudioFileClip(str(narration.audio_path))
        if audio.duration > duration:
            audio = audio.with_duration(duration)

        scene = CompositeVideoClip(
            layers, size=(self.width, self.height)
        ).with_duration(duration).with_audio(audio)

        # Cross-fade only for explainer mode
        scene = scene.with_effects([vfx.CrossFadeIn(0.5)])

        return scene

    def _create_explainer_hook_card(
        self,
        title: str,
        hook_text: Optional[str],
        duration: float = 3.5,
    ) -> CompositeVideoClip:
        """Create a clean, minimal hook card for explainer videos."""
        bg_color = self.theme["bg_color"]
        accent = self.theme["accent_color"]
        text_color = self.theme["text_color"]
        title_size = self.theme["title_font_size"]

        layers = []

        # Solid off-white background
        bg_clip = (
            ColorClip(size=(self.width, self.height), color=bg_color)
            .with_duration(duration)
            .with_fps(self.fps)
        )
        layers.append(bg_clip)

        # Thin accent line (centered)
        line_w = int(self.width * 0.15)
        line_img = Image.new("RGBA", (line_w, 3), (0, 0, 0, 0))
        draw = ImageDraw.Draw(line_img)
        draw.rectangle([(0, 0), (line_w, 3)], fill=(*accent, 180))
        line_clip = (
            ImageClip(np.array(line_img))
            .with_duration(duration)
            .with_position(("center", int(self.height * 0.38)))
            .with_effects([vfx.CrossFadeIn(0.3)])
        )
        layers.append(line_clip)

        # Title text — clean, centered, no stroke
        title_img = self._render_explainer_text(
            text=title,
            font_size=title_size,
            color=text_color,
            max_width=self.width - 160,
            bold=True,
        )
        title_clip = (
            ImageClip(np.array(title_img))
            .with_duration(duration)
            .with_position(("center", int(self.height * 0.42)))
            .with_effects([vfx.CrossFadeIn(0.5)])
        )
        layers.append(title_clip)

        # Hook text — muted accent color
        if hook_text:
            hook_img = self._render_explainer_text(
                text=hook_text,
                font_size=int(title_size * 0.58),
                color=accent,
                max_width=self.width - 200,
                bold=False,
            )
            hook_clip = (
                ImageClip(np.array(hook_img))
                .with_duration(duration - 0.5)
                .with_start(0.5)
                .with_position(("center", int(self.height * 0.56)))
                .with_effects([vfx.CrossFadeIn(0.4)])
            )
            layers.append(hook_clip)

        scene = CompositeVideoClip(
            layers, size=(self.width, self.height)
        ).with_duration(duration)
        scene = scene.with_effects([vfx.FadeIn(0.4), vfx.FadeOut(0.5)])
        return scene

    def _create_explainer_outro_card(
        self,
        duration: float = 2.5,
        cta_text: Optional[str] = None,
    ) -> CompositeVideoClip:
        """Create a clean explainer-style outro card."""
        bg_color = self.theme["bg_color"]
        accent = self.theme["accent_color"]
        text_color = self.theme["text_color"]

        layers = []

        # Solid background
        bg_clip = (
            ColorClip(size=(self.width, self.height), color=bg_color)
            .with_duration(duration)
            .with_fps(self.fps)
        )
        layers.append(bg_clip)

        # CTA if provided
        if cta_text:
            cta_img = self._render_explainer_text(
                text=cta_text,
                font_size=36,
                color=accent,
                max_width=self.width - 160,
                bold=False,
            )
            cta_clip = (
                ImageClip(np.array(cta_img))
                .with_duration(duration - 0.2)
                .with_start(0.2)
                .with_position(("center", int(self.height * 0.34)))
                .with_effects([vfx.CrossFadeIn(0.3)])
            )
            layers.append(cta_clip)

        # Branding
        brand_y = 0.44 if cta_text else 0.42
        brand_img = self._render_explainer_text(
            text="Project HER",
            font_size=44,
            color=text_color,
            max_width=self.width - 160,
            bold=True,
        )
        brand_clip = (
            ImageClip(np.array(brand_img))
            .with_duration(duration)
            .with_position(("center", int(self.height * brand_y)))
        )
        layers.append(brand_clip)

        # Tagline
        tag_y = 0.54 if cta_text else 0.52
        tag_img = self._render_explainer_text(
            text="AI-Powered Video Generation",
            font_size=24,
            color=self.theme.get("secondary_text_color", (100, 100, 110)),
            max_width=self.width - 160,
            bold=False,
        )
        tag_clip = (
            ImageClip(np.array(tag_img))
            .with_duration(duration - 0.3)
            .with_start(0.3)
            .with_position(("center", int(self.height * tag_y)))
            .with_effects([vfx.CrossFadeIn(0.4)])
        )
        layers.append(tag_clip)

        scene = CompositeVideoClip(
            layers, size=(self.width, self.height)
        ).with_duration(duration)
        scene = scene.with_effects([vfx.FadeIn(0.4), vfx.FadeOut(0.8)])
        return scene

    # ── Explainer Helper Methods ──────────────────────────

    def _create_explainer_image(
        self,
        image_asset: ImageAsset,
        duration: float,
        scene_index: int,
        target_w: int = 800,
        target_h: int = 450,
    ) -> VideoClip:
        """
        Create an illustration-style image clip for explainer mode.
        Applies desaturation, slight blur softening, and rounded corners
        to make stock photos look more like flat vector illustrations.
        """
        if image_asset.asset_type == "video":
            clip = self._create_broll_clip(
                image_asset.local_path, duration,
                target_w=target_w, target_h=target_h,
            )
            # Apply illustration treatment to video frames
            def illustrate_frame(frame):
                return self._apply_illustration_treatment(frame)
            return clip.image_transform(illustrate_frame)

        # Process static image
        try:
            img = Image.open(image_asset.local_path).convert("RGB")
        except Exception as e:
            logger.warning("Failed to open image for explainer: %s", e)
            placeholder = Image.new("RGB", (target_w, target_h), self.theme["bg_color"])
            return (
                ImageClip(np.array(placeholder))
                .with_duration(duration)
                .with_fps(self.fps)
            )

        # Resize to cover target area
        img_ratio = img.width / img.height
        target_ratio = target_w / target_h
        if img_ratio > target_ratio:
            new_h = target_h
            new_w = int(new_h * img_ratio)
        else:
            new_w = target_w
            new_h = int(new_w / img_ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)

        # Center crop
        x_off = (new_w - target_w) // 2
        y_off = (new_h - target_h) // 2
        img = img.crop((x_off, y_off, x_off + target_w, y_off + target_h))

        # Apply illustration treatment
        img = self._apply_illustration_treatment_pil(img)

        # Add rounded corners
        img = self._add_rounded_corners(img, radius=16)

        # Add subtle shadow
        final_img = self._add_subtle_shadow(img, shadow_offset=6, shadow_blur=12)

        # Gentle slow pan (minimal motion)
        img_array = np.array(final_img.convert("RGB"))
        fw, fh = final_img.size

        # Slow pan: very gentle horizontal drift
        drift_px = int(fw * 0.015)  # only 1.5% drift

        def make_frame(t):
            progress = t / max(duration, 0.01)
            # Alternate direction per scene
            if scene_index % 2 == 0:
                x_shift = int(drift_px * progress)
            else:
                x_shift = int(drift_px * (1 - progress))

            # Ensure we stay in bounds
            x_shift = max(0, min(x_shift, fw - target_w))
            cropped = img_array[:target_h, x_shift:x_shift + target_w]
            if cropped.shape[1] < target_w:
                cropped = img_array[:target_h, :target_w]
            return cropped

        # If the image is exactly target size (after crop), just use static
        if fw <= target_w + drift_px:
            clip = ImageClip(np.array(img.convert("RGB"))).with_duration(duration).with_fps(self.fps)
        else:
            clip = VideoClip(make_frame, duration=duration).with_fps(self.fps)

        return clip

    def _apply_illustration_treatment_pil(self, img: Image.Image) -> Image.Image:
        """
        Apply illustration-style treatment to a PIL Image:
        - Reduce saturation for muted, historically appropriate colors
        - Slightly increase contrast for a graphic look
        - Apply subtle blur for softness
        """
        # Desaturate (keep ~55% color for muted look)
        img = ImageEnhance.Color(img).enhance(0.55)
        # Bump contrast slightly for a graphic/flat feel
        img = ImageEnhance.Contrast(img).enhance(1.12)
        # Very slight brightness boost
        img = ImageEnhance.Brightness(img).enhance(1.05)
        # Subtle blur for softness (illustration style)
        img = img.filter(ImageFilter.GaussianBlur(radius=0.6))
        return img

    def _apply_illustration_treatment(self, frame: np.ndarray) -> np.ndarray:
        """Apply illustration treatment to a numpy frame (for video clips)."""
        img = Image.fromarray(frame)
        img = self._apply_illustration_treatment_pil(img)
        return np.array(img)

    def _add_rounded_corners(
        self, img: Image.Image, radius: int = 16
    ) -> Image.Image:
        """Add rounded corners to an image using an alpha mask."""
        img = img.convert("RGBA")
        w, h = img.size
        mask = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([(0, 0), (w, h)], radius=radius, fill=255)
        img.putalpha(mask)
        # Composite onto canvas background color
        bg = Image.new("RGBA", (w, h), (*self.theme["bg_color"], 255))
        bg.paste(img, (0, 0), img)
        return bg

    def _add_subtle_shadow(
        self, img: Image.Image, shadow_offset: int = 6, shadow_blur: int = 12
    ) -> Image.Image:
        """Add a subtle drop shadow behind the image."""
        w, h = img.size
        canvas_w = w + shadow_offset * 2 + shadow_blur
        canvas_h = h + shadow_offset * 2 + shadow_blur
        canvas = Image.new("RGBA", (canvas_w, canvas_h), (*self.theme["bg_color"], 255))

        # Shadow
        shadow = Image.new("RGBA", (w, h), (0, 0, 0, 40))
        canvas.paste(shadow, (shadow_offset + shadow_blur // 2, shadow_offset + shadow_blur // 2))
        canvas = canvas.filter(ImageFilter.GaussianBlur(radius=shadow_blur // 2))

        # Re-paint background over blurred area, then paste image
        bg_layer = Image.new("RGBA", (canvas_w, canvas_h), (*self.theme["bg_color"], 255))
        bg_layer = Image.alpha_composite(bg_layer, canvas)
        img_rgba = img.convert("RGBA")
        bg_layer.paste(img_rgba, (shadow_blur // 2, shadow_blur // 2), img_rgba)
        return bg_layer

    def _get_narration_aware_y(self, scene_index: int, total_scenes: int = 6) -> int:
        """
        Calculate narration-aware vertical text offset.
        Earlier scenes (setup/context) → text slightly higher.
        Later scenes (conclusion/outcome) → text slightly lower.
        This creates dynamic visual flow tied to the narrative arc.
        """
        if total_scenes <= 1:
            return 0
        # Normalize scene position (0.0 = start, 1.0 = end)
        progress = scene_index / max(total_scenes - 1, 1)
        # Map to a gentle vertical range: -15px to +25px
        y_shift = int(-15 + 40 * progress)
        return y_shift

    def _split_narration_segments(
        self, text: str, max_words: int = 8
    ) -> list[str]:
        """
        Split narration text into display segments for progressive reveal.
        Tries to split at natural phrase boundaries.
        """
        words = text.split()
        if len(words) <= max_words:
            return [text]

        segments = []
        # Try splitting at punctuation first
        import re
        sentences = re.split(r'(?<=[.!?,;:—–])\s+', text)
        if len(sentences) >= 2:
            for s in sentences:
                s = s.strip()
                if s:
                    # Further split long sentences
                    s_words = s.split()
                    if len(s_words) > max_words:
                        mid = len(s_words) // 2
                        segments.append(" ".join(s_words[:mid]))
                        segments.append(" ".join(s_words[mid:]))
                    else:
                        segments.append(s)
        else:
            # No punctuation — split by word count
            for i in range(0, len(words), max_words):
                segment = " ".join(words[i:i + max_words])
                if segment:
                    segments.append(segment)

        return segments if segments else [text]

    def _render_explainer_text(
        self,
        text: str,
        font_size: int,
        color: tuple,
        max_width: int = 800,
        bold: bool = False,
    ) -> Image.Image:
        """
        Render clean text for explainer mode — no stroke, no shadow,
        just clear typography on transparent background.
        """
        font = self._get_font(int(font_size * 1.05) if bold else font_size)
        wrapped = wrap_text(text, max_chars=max(max_width // (font_size // 2), 12))
        lines = wrapped.split("\n")

        dummy = Image.new("RGBA", (1, 1))
        draw = ImageDraw.Draw(dummy)
        line_heights = []
        line_widths = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_widths.append(bbox[2] - bbox[0])
            line_heights.append(bbox[3] - bbox[1])

        total_height = sum(line_heights) + (len(lines) - 1) * 8
        total_width = max(line_widths) if line_widths else 100

        padding = 12
        img_width = total_width + 2 * padding
        img_height = total_height + 2 * padding

        img = Image.new("RGBA", (img_width, img_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        y = padding
        for i, line in enumerate(lines):
            x = (img_width - line_widths[i]) // 2
            draw.text((x, y), line, font=font, fill=color)
            y += line_heights[i] + 8

        return img

    def _create_explainer_captions(
        self,
        narration: NarrationClip,
        scene_duration: float,
    ) -> list[ImageClip]:
        """
        Create clean, minimal caption clips for explainer mode.
        No background box, just clean dark text on the off-white canvas.
        Uses progressive reveal style — each word group fades in gently.
        """
        caption_clips = []
        style = self.caption_config
        position_y = int(self.height * style["position"])
        text_color = self.theme["text_color"]
        accent = self.theme["accent_color"]
        font_size = style["font_size"]
        fade_dur = self.theme.get("text_reveal_fade", 0.4)

        for group in narration.subtitle_data:
            group_start = group["start"]
            group_end = min(group["end"], scene_duration)
            group_text = group["text"]

            if group_end <= group_start:
                continue

            # Render clean text (no background, no stroke)
            font = self._get_font(font_size)
            dummy = Image.new("RGBA", (1, 1))
            draw = ImageDraw.Draw(dummy)
            bbox = draw.textbbox((0, 0), group_text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]

            padding = 10
            img = Image.new("RGBA", (tw + 2 * padding, th + 2 * padding), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.text((padding, padding), group_text, font=font, fill=text_color)

            clip = (
                ImageClip(np.array(img))
                .with_duration(group_end - group_start)
                .with_start(group_start)
                .with_position(("center", position_y))
                .with_effects([vfx.CrossFadeIn(fade_dur)])
            )
            caption_clips.append(clip)

        return caption_clips

    # ══════════════════════════════════════════════════════
    # TRANSITIONS
    # ══════════════════════════════════════════════════════

    def _get_transition_sequence(self, num_scenes: int) -> list[str]:
        """Generate a varied sequence of transitions for visual variety."""
        # Explainer mode: cross-fade only for layout continuity
        if self.theme.get("explainer_mode"):
            return ["fade"] * num_scenes

        if self.transition != "fade":
            return [self.transition] * num_scenes

        # Auto-vary transitions for maximum visual interest
        transitions = config.AVAILABLE_TRANSITIONS.copy()
        sequence = []
        for i in range(num_scenes):
            sequence.append(transitions[i % len(transitions)])
        return sequence

    def _apply_transition(
        self, scene: CompositeVideoClip, transition_type: str
    ) -> CompositeVideoClip:
        """Apply a real transition effect to a scene."""
        td = config.TRANSITION_DURATION

        if transition_type == "fade":
            scene = scene.with_effects([vfx.FadeIn(td)])

        elif transition_type == "slide_left":
            scene = self._wrap_with_slide(scene, td, direction="left")

        elif transition_type == "slide_up":
            scene = self._wrap_with_slide(scene, td, direction="up")

        elif transition_type == "zoom_in":
            scene = self._wrap_with_zoom_transition(scene, td)

        elif transition_type == "wipe":
            scene = self._wrap_with_wipe(scene, td)

        else:
            scene = scene.with_effects([vfx.FadeIn(td)])

        return scene

    def _wrap_with_slide(
        self,
        scene: CompositeVideoClip,
        duration: float,
        direction: str = "left",
    ) -> CompositeVideoClip:
        """
        Slide-in transition: the scene slides in from an edge.
        The clip starts off-screen and moves to its final position.
        """
        w, h = self.width, self.height
        scene_dur = scene.duration
        fps = self.fps

        def position_func(t):
            if t >= duration:
                return (0, 0)
            progress = t / duration
            ease = progress * progress * (3 - 2 * progress)  # smoothstep
            if direction == "left":
                return (int(w * (1 - ease)), 0)
            elif direction == "right":
                return (int(-w * (1 - ease)), 0)
            elif direction == "up":
                return (0, int(h * (1 - ease)))
            else:  # down
                return (0, int(-h * (1 - ease)))

        bg = ColorClip(size=(w, h), color=(0, 0, 0)).with_duration(scene_dur).with_fps(fps)
        sliding = scene.with_position(position_func)
        return CompositeVideoClip([bg, sliding], size=(w, h)).with_duration(scene_dur).with_audio(scene.audio)

    def _wrap_with_zoom_transition(
        self,
        scene: CompositeVideoClip,
        duration: float,
    ) -> CompositeVideoClip:
        """
        Zoom-in transition: the scene starts small at center and scales up.
        """
        w, h = self.width, self.height
        scene_dur = scene.duration
        fps = self.fps

        def make_frame(t):
            frame = scene.get_frame(t)
            if t >= duration:
                return frame
            progress = t / duration
            ease = progress * progress * (3 - 2 * progress)
            scale = 0.3 + 0.7 * ease  # 0.3 -> 1.0

            frame_img = Image.fromarray(frame)
            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))
            resized = frame_img.resize((new_w, new_h), Image.LANCZOS)

            canvas = Image.new("RGB", (w, h), (0, 0, 0))
            paste_x = (w - new_w) // 2
            paste_y = (h - new_h) // 2
            canvas.paste(resized, (paste_x, paste_y))
            return np.array(canvas)

        result = VideoClip(make_frame, duration=scene_dur).with_fps(fps)
        if scene.audio:
            result = result.with_audio(scene.audio)
        return result

    def _wrap_with_wipe(
        self,
        scene: CompositeVideoClip,
        duration: float,
    ) -> CompositeVideoClip:
        """
        Wipe transition: a horizontal wipe reveals the scene from left to right.
        """
        w, h = self.width, self.height
        scene_dur = scene.duration
        fps = self.fps

        def make_frame(t):
            frame = scene.get_frame(t)
            if t >= duration:
                return frame
            progress = t / duration
            ease = progress * progress * (3 - 2 * progress)
            reveal_x = int(w * ease)

            canvas = np.zeros_like(frame)
            if reveal_x > 0:
                canvas[:, :reveal_x] = frame[:, :reveal_x]
            return canvas

        result = VideoClip(make_frame, duration=scene_dur).with_fps(fps)
        if scene.audio:
            result = result.with_audio(scene.audio)
        return result

    # ══════════════════════════════════════════════════════
    # TRANSITION SFX
    # ══════════════════════════════════════════════════════

    _SFX_FOR_TRANSITION = {
        "fade": "rise",
        "slide_left": "whoosh",
        "slide_up": "whoosh",
        "zoom_in": "rise",
        "wipe": "pop",
    }

    def _generate_transition_sfx(
        self,
        scenes: list,
        transition_list: list[str],
        hook_duration: float,
        output_dir: Path,
    ) -> list[AudioFileClip]:
        """
        Generate SFX audio clips positioned at each scene transition point.
        Returns a list of AudioFileClips with correct start offsets.
        """
        sfx_clips: list[AudioFileClip] = []

        # Calculate cumulative timestamps where each content scene starts
        # (scene 0 = hook card, scene 1.. = content scenes)
        cumulative_time = 0.0
        for i, scene in enumerate(scenes):
            if i == 0:
                # Hook card — skip SFX here
                cumulative_time += scene.duration
                continue
            # This scene starts at cumulative_time → add SFX at that point
            transition_idx = (i - 1) % len(transition_list)
            t_type = transition_list[transition_idx]
            sfx_type = self._SFX_FOR_TRANSITION.get(t_type, "whoosh")

            try:
                sfx_path = self.audio_engine.generate_transition_sfx(
                    sfx_type=sfx_type,
                    output_dir=output_dir,
                )
                sfx_clip = (
                    AudioFileClip(str(sfx_path))
                    .with_start(cumulative_time)
                )
                sfx_clips.append(sfx_clip)
            except Exception as e:
                logger.warning("SFX generation failed for scene %d: %s", i, e)

            cumulative_time += scene.duration

        return sfx_clips

    # ══════════════════════════════════════════════════════
    # SUBTITLE FALLBACK
    # ══════════════════════════════════════════════════════

    def _create_subtitle_clips(
        self,
        subtitle_data: list[dict],
        scene_duration: float,
    ) -> list[ImageClip]:
        """Create fallback subtitle clips (when word timings unavailable)."""
        clips = []
        style = self.caption_config
        position_y = int(self.height * style["position"])

        for sub in subtitle_data:
            start = sub["start"]
            end = min(sub["end"], scene_duration)
            text = sub["text"]

            if end <= start:
                continue

            sub_img = self._render_caption_text(
                text, active_word_index=-1, words=[]
            )
            sub_clip = (
                ImageClip(np.array(sub_img))
                .with_duration(end - start)
                .with_start(start)
                .with_position(("center", position_y))
            )
            clips.append(sub_clip)

        return clips

    # ══════════════════════════════════════════════════════
    # TEXT RENDERING
    # ══════════════════════════════════════════════════════

    def _render_text_image(
        self,
        text: str,
        font_size: int = 48,
        max_width: int = 900,
        color="white",
        stroke_color="black",
        stroke_width: int = 0,
    ) -> Image.Image:
        """Render text as a transparent RGBA image using Pillow."""
        font = self._get_font(font_size)
        wrapped = wrap_text(text, max_chars=max(max_width // (font_size // 2), 15))
        lines = wrapped.split("\n")

        dummy_img = Image.new("RGBA", (1, 1))
        draw = ImageDraw.Draw(dummy_img)
        line_heights = []
        line_widths = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_widths.append(bbox[2] - bbox[0])
            line_heights.append(bbox[3] - bbox[1])

        total_height = sum(line_heights) + (len(lines) - 1) * 10
        total_width = max(line_widths) if line_widths else 100

        padding = 20
        img_width = total_width + 2 * padding
        img_height = total_height + 2 * padding

        img = Image.new("RGBA", (img_width, img_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        y = padding
        for i, line in enumerate(lines):
            x = (img_width - line_widths[i]) // 2
            if stroke_width > 0:
                draw.text(
                    (x, y), line, font=font, fill=stroke_color,
                    stroke_width=stroke_width, stroke_fill=stroke_color,
                )
            draw.text((x, y), line, font=font, fill=color)
            y += line_heights[i] + 10

        return img

    def _render_subtitle_image(
        self,
        text: str,
        font_size: int = 36,
        max_width: int = 900,
    ) -> Image.Image:
        """Render subtitle with semi-transparent background."""
        font = self._get_font(font_size)
        wrapped = wrap_text(text, max_chars=max(max_width // (font_size // 2), 15))
        lines = wrapped.split("\n")

        dummy_img = Image.new("RGBA", (1, 1))
        draw = ImageDraw.Draw(dummy_img)
        line_heights = []
        line_widths = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_widths.append(bbox[2] - bbox[0])
            line_heights.append(bbox[3] - bbox[1])

        total_height = sum(line_heights) + (len(lines) - 1) * 8
        total_width = max(line_widths) if line_widths else 100

        padding = 16
        img_width = total_width + 2 * padding
        img_height = total_height + 2 * padding

        img = Image.new("RGBA", (img_width, img_height), (0, 0, 0, 160))
        draw = ImageDraw.Draw(img)

        y = padding
        for i, line in enumerate(lines):
            x = (img_width - line_widths[i]) // 2
            draw.text(
                (x, y), line, font=font, fill="white",
                stroke_width=1, stroke_fill="black",
            )
            y += line_heights[i] + 8

        return img

    @staticmethod
    def _draw_rounded_rect(
        draw: ImageDraw.Draw,
        bounds: tuple,
        radius: int,
        fill: tuple,
    ) -> None:
        """Draw a rounded rectangle."""
        x0, y0, x1, y1 = bounds
        draw.rounded_rectangle(bounds, radius=radius, fill=fill)

    @staticmethod
    def _get_font(size: int) -> ImageFont.FreeTypeFont:
        """Get a font with fallback chain: custom → assets/fonts/ → system."""
        # 1. Custom font path from config/env
        if config.CUSTOM_FONT_PATH:
            custom = Path(config.CUSTOM_FONT_PATH)
            if custom.exists():
                try:
                    return ImageFont.truetype(str(custom), size)
                except (OSError, IOError):
                    logger.warning("Custom font '%s' failed to load", custom)

        # 2. Fonts in assets/fonts/ directory
        custom_fonts = list(config.FONTS_DIR.glob("*.ttf")) + list(config.FONTS_DIR.glob("*.otf"))
        if custom_fonts:
            try:
                return ImageFont.truetype(str(custom_fonts[0]), size)
            except (OSError, IOError):
                pass

        # 3. System font fallbacks
        font_paths = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/SFNSText.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "C:\\Windows\\Fonts\\arial.ttf",
            "C:\\Windows\\Fonts\\segoeui.ttf",
        ]
        for fp in font_paths:
            try:
                return ImageFont.truetype(fp, size)
            except (OSError, IOError):
                continue
        return ImageFont.load_default()

    # ══════════════════════════════════════════════════════
    # WATERMARK
    # ══════════════════════════════════════════════════════

    def _create_watermark(self, duration: float) -> Optional[ImageClip]:
        """
        Create a semi-transparent watermark clip (text or image).
        Returns None if no watermark is configured.
        """
        wm_text = config.WATERMARK_TEXT
        wm_image = config.WATERMARK_IMAGE
        opacity = config.WATERMARK_OPACITY
        position = config.WATERMARK_POSITION
        margin = config.WATERMARK_MARGIN

        wm_img = None

        if wm_image and Path(wm_image).exists():
            try:
                logo = Image.open(wm_image).convert("RGBA")
                # Scale logo to max 15% of frame width
                max_w = int(self.width * 0.15)
                if logo.width > max_w:
                    ratio = max_w / logo.width
                    logo = logo.resize(
                        (max_w, int(logo.height * ratio)), Image.LANCZOS
                    )
                wm_img = logo
            except Exception as e:
                logger.warning("Could not load watermark image: %s", e)

        if wm_img is None and wm_text:
            font = self._get_font(config.WATERMARK_FONT_SIZE)
            dummy = Image.new("RGBA", (1, 1))
            draw = ImageDraw.Draw(dummy)
            bbox = draw.textbbox((0, 0), wm_text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            padding = 8
            wm_img = Image.new(
                "RGBA", (tw + 2 * padding, th + 2 * padding), (0, 0, 0, 80)
            )
            draw = ImageDraw.Draw(wm_img)
            draw.text((padding, padding), wm_text, font=font, fill=(255, 255, 255, 200))

        if wm_img is None:
            return None

        # Calculate position
        iw, ih = wm_img.size
        positions = {
            "top_left": (margin, margin),
            "top_right": (self.width - iw - margin, margin),
            "bottom_left": (margin, self.height - ih - margin),
            "bottom_right": (self.width - iw - margin, self.height - ih - margin),
        }
        pos = positions.get(position, positions["bottom_right"])

        clip = (
            ImageClip(np.array(wm_img))
            .with_duration(duration)
            .with_position(pos)
            .with_opacity(opacity)
        )
        return clip

    # ══════════════════════════════════════════════════════
    # THUMBNAIL GENERATION
    # ══════════════════════════════════════════════════════

    def _generate_thumbnail(
        self,
        title: str,
        first_image: Optional[ImageAsset] = None,
        output_dir: Optional[Path] = None,
    ) -> Optional[Path]:
        """
        Generate a thumbnail image for the video.
        Uses the first scene image as background with title overlay.
        """
        try:
            w, h = self.width, self.height
            accent = self.theme["accent_color"]
            text_color = self.theme["text_color"]
            bg_color = self.theme["bg_color"]

            # Background: use first image if available, else gradient
            if first_image and first_image.local_path and first_image.local_path.exists():
                img_path = first_image.local_path
                # Handle video files: extract a frame
                if img_path.suffix.lower() in (".mp4", ".mov", ".avi", ".webm", ".mkv"):
                    try:
                        clip = VideoFileClip(str(img_path))
                        # Grab frame at 1 second (or midpoint for short clips)
                        t = min(1.0, clip.duration / 2)
                        frame = clip.get_frame(t)
                        bg = Image.fromarray(frame).convert("RGB")
                        clip.close()
                    except Exception as ve:
                        logger.warning("Failed to extract video frame for thumbnail: %s", ve)
                        bg = Image.new("RGB", (w, h), bg_color)
                else:
                    bg = Image.open(img_path).convert("RGB")
                # Resize to cover
                bg_ratio = bg.width / bg.height
                target_ratio = w / h
                if bg_ratio > target_ratio:
                    new_h = h
                    new_w = int(new_h * bg_ratio)
                else:
                    new_w = w
                    new_h = int(new_w / bg_ratio)
                bg = bg.resize((new_w, new_h), Image.LANCZOS)
                # Center crop
                x_off = (new_w - w) // 2
                y_off = (new_h - h) // 2
                bg = bg.crop((x_off, y_off, x_off + w, y_off + h))
            else:
                bg = Image.new("RGB", (w, h), bg_color)

            # Darken overlay for text readability
            overlay = Image.new("RGBA", (w, h), (0, 0, 0, 140))
            bg = bg.convert("RGBA")
            bg = Image.alpha_composite(bg, overlay).convert("RGB")

            draw = ImageDraw.Draw(bg)

            # Title text
            font_size = self.theme.get("title_font_size", 60)
            font = self._get_font(font_size)
            max_chars = max(w // (font_size // 2), 10)
            wrapped = wrap_text(title, max_chars=max_chars)
            lines = wrapped.split("\n")

            # Calculate total text height
            line_heights = []
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                line_heights.append(bbox[3] - bbox[1])
            total_text_h = sum(line_heights) + (len(lines) - 1) * 12

            # Center vertically
            y = (h - total_text_h) // 2

            for i, line in enumerate(lines):
                bbox = draw.textbbox((0, 0), line, font=font)
                line_w = bbox[2] - bbox[0]
                x = (w - line_w) // 2

                # Text stroke/shadow
                for dx in range(-2, 3):
                    for dy in range(-2, 3):
                        if abs(dx) + abs(dy) > 0:
                            draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0))

                draw.text((x, y), line, font=font, fill=text_color)
                y += line_heights[i] + 12

            # Accent bar under title
            bar_w = min(w - 80, 200)
            bar_x = (w - bar_w) // 2
            bar_y = y + 10
            draw.rectangle(
                [(bar_x, bar_y), (bar_x + bar_w, bar_y + 5)],
                fill=accent,
            )

            # "Project HER" small branding at bottom
            small_font = self._get_font(24)
            brand = "Project HER"
            brand_bbox = draw.textbbox((0, 0), brand, font=small_font)
            brand_w = brand_bbox[2] - brand_bbox[0]
            draw.text(
                ((w - brand_w) // 2, h - 60),
                brand, font=small_font, fill=(*accent, ),
            )

            # Save
            thumb_path = output_dir / "thumbnail.jpg"
            bg.save(str(thumb_path), "JPEG", quality=92)
            logger.info("Thumbnail generated: %s", thumb_path)
            return thumb_path

        except Exception as e:
            logger.warning("Thumbnail generation failed: %s", e)
            return None

    # ══════════════════════════════════════════════════════
    # CUSTOM INTRO / OUTRO
    # ══════════════════════════════════════════════════════

    def _try_custom_intro(self) -> Optional[CompositeVideoClip]:
        """
        Load a custom intro image or video from CUSTOM_INTRO_PATH.
        Returns None if no custom intro is configured or the file is missing.
        """
        intro_path = config.CUSTOM_INTRO_PATH
        if not intro_path or not Path(intro_path).exists():
            return None

        p = Path(intro_path)
        try:
            if p.suffix.lower() in (".mp4", ".mov", ".avi", ".webm"):
                clip = VideoFileClip(str(p))
                # Resize to match video dimensions
                clip = clip.resized((self.width, self.height))
                return clip
            else:
                # Image intro
                dur = config.CUSTOM_INTRO_DURATION
                img = Image.open(str(p)).convert("RGB")
                img = img.resize((self.width, self.height), Image.LANCZOS)
                clip = (
                    ImageClip(np.array(img))
                    .with_duration(dur)
                    .with_effects([vfx.CrossFadeIn(0.3), vfx.CrossFadeOut(0.3)])
                )
                return CompositeVideoClip(
                    [clip], size=(self.width, self.height)
                ).with_duration(dur)
        except Exception as e:
            logger.warning("Custom intro failed to load: %s", e)
            return None

    def _try_custom_outro(self, cta_text: Optional[str] = None) -> Optional[CompositeVideoClip]:
        """
        Load a custom outro image or video from CUSTOM_OUTRO_PATH.
        Returns None if no custom outro is configured or the file is missing.
        """
        outro_path = config.CUSTOM_OUTRO_PATH
        if not outro_path or not Path(outro_path).exists():
            return None

        p = Path(outro_path)
        try:
            if p.suffix.lower() in (".mp4", ".mov", ".avi", ".webm"):
                clip = VideoFileClip(str(p))
                clip = clip.resized((self.width, self.height))
                return clip
            else:
                dur = config.CUSTOM_OUTRO_DURATION
                img = Image.open(str(p)).convert("RGB")
                img = img.resize((self.width, self.height), Image.LANCZOS)
                clip = (
                    ImageClip(np.array(img))
                    .with_duration(dur)
                    .with_effects([vfx.CrossFadeIn(0.3), vfx.CrossFadeOut(0.5)])
                )
                return CompositeVideoClip(
                    [clip], size=(self.width, self.height)
                ).with_duration(dur)
        except Exception as e:
            logger.warning("Custom outro failed to load: %s", e)
            return None

    # ══════════════════════════════════════════════════════
    # COLOR GRADING
    # ══════════════════════════════════════════════════════

    def _apply_color_grade(self, clip: CompositeVideoClip, grade_name: str):
        """
        Apply a color grading filter to the final video.
        Adjusts brightness, contrast, saturation, and optional color tint.
        """
        grade = config.COLOR_GRADES.get(grade_name)
        if not grade:
            return clip

        brightness = grade["brightness"]
        contrast = grade["contrast"]
        saturation = grade["saturation"]
        tint = grade.get("tint")

        def grade_frame(frame):
            """Apply color grading to a single frame (numpy array)."""
            img = Image.fromarray(frame)

            # Brightness
            if brightness != 1.0:
                from PIL import ImageEnhance
                img = ImageEnhance.Brightness(img).enhance(brightness)

            # Contrast
            if contrast != 1.0:
                from PIL import ImageEnhance
                img = ImageEnhance.Contrast(img).enhance(contrast)

            # Saturation
            if saturation != 1.0:
                from PIL import ImageEnhance
                img = ImageEnhance.Color(img).enhance(saturation)

            # Tint overlay
            if tint:
                r, g, b, a = tint
                overlay = Image.new("RGBA", img.size, (r, g, b, a))
                img = img.convert("RGBA")
                img = Image.alpha_composite(img, overlay).convert("RGB")

            return np.array(img)

        return clip.image_transform(grade_frame)

    # ══════════════════════════════════════════════════════
    # SRT GENERATION
    # ══════════════════════════════════════════════════════

    def _generate_srt_file(
        self,
        narrations: list[NarrationClip],
        output_dir: Path,
        title_duration: float = 3.5,
    ) -> Path:
        """Generate an SRT subtitle file with word-level timing."""
        all_subtitles = []
        time_offset = title_duration

        for narration in narrations:
            # Use word timings for precise SRT if available
            if narration.word_timings:
                # Group words for SRT display
                words = narration.word_timings
                group_size = 5
                for i in range(0, len(words), group_size):
                    group = words[i:i + group_size]
                    all_subtitles.append({
                        "start": group[0].start + time_offset,
                        "end": group[-1].end + time_offset,
                        "text": " ".join(w.word for w in group),
                    })
            else:
                for sub in narration.subtitle_data:
                    all_subtitles.append({
                        "start": sub["start"] + time_offset,
                        "end": sub["end"] + time_offset,
                        "text": sub["text"],
                    })
            time_offset += narration.duration + config.SCENE_PADDING

        srt_path = output_dir / "subtitles.srt"
        generate_srt(all_subtitles, srt_path)
        logger.info("SRT file generated: %s", srt_path)
        return srt_path
