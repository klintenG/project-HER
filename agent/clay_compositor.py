"""
Project HER v2.0 – Claymorphism Video Compositor
Renders polished videos using Claymorphism design style with AI-generated images.

Screen Layout (9:16 vertical):
  ┌─────────────────────────┐
  │    BRAND / LOGO (15%)   │
  ├─────────────────────────┤
  │  NARRATIVE TEXT (10%)   │  ← alternates top / bottom
  ├─────────────────────────┤
  │                         │
  │   MAIN CONTENT (50%)    │  ← AI image or animated text
  │                         │
  ├─────────────────────────┤
  │ WATERMARK / BOTTOM(15%) │
  └─────────────────────────┘
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import config
from agent.story_splitter import ScreenSegment, StoryScreenplay, EmphasisWord
from agent.ai_visuals import AIImageAsset
from agent.narration import NarrationClip, WordTiming
from agent.vfx_engine import (
    VFXConfig, VFX_DEFAULTS,
    text_bounce_scale, text_jiggle_offset, text_exit_progress,
    image_entrance_scale,
    generate_paper_grain, apply_paper_texture, apply_flash_frame,
    whip_pan_transition, mask_wipe_transition, z_zoom_transition,
    glitch_wipe_transition,
    parallax_transform,
    generate_light_leak, apply_light_leak,
    beat_pulse_scale,
    is_keyword, should_flash_reveal, apply_warm_flash,
    image_transition_offset, get_image_transition_for_scene,
    text_enter_offset, text_exit_offset,
    TRANSITION_SEQUENCE, get_transition_for_scene, apply_transition_blend,
    ease_out_back, ease_out_cubic, ease_in_cubic, ease_in_out_sine,
)
from agent.effects_engine import (
    get_text_entry_transform,
    get_text_exit_transform,
    get_text_continuous_transform,
    get_image_entry_transform,
    get_image_exit_transform,
    apply_image_effect,
    apply_scene_transition,
    apply_overlay_effect,
    apply_background_effect,
    apply_text_layer_transform,
)
from agent.effects_agent import SceneEffectsPlan, VideoEffectsPlan

logger = logging.getLogger("clay_compositor")

# Try to import moviepy v2 API
from moviepy import (
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    TextClip,
    VideoClip,
    concatenate_videoclips,
    vfx,
)


# ── Helper: Font Resolution ──────────────────────────

def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Get a solid, highly readable sans-serif font at the given size.

    Priority order: bold weights preferred for solidity and on-screen readability.
    Montserrat Bold → Inter Bold → SF Pro Bold → system fallbacks.
    """
    font_candidates = [
        # ── Preferred solid sans-serif (install in assets/fonts/) ──
        # Montserrat — geometric, solid, great for video
        str(config.FONTS_DIR / ("Montserrat-Bold.ttf" if bold else "Montserrat-SemiBold.ttf")),
        str(config.FONTS_DIR / ("Montserrat-ExtraBold.ttf" if bold else "Montserrat-Bold.ttf")),
        # Inter — clean, readable
        str(config.FONTS_DIR / ("Inter-Bold.ttf" if bold else "Inter-SemiBold.ttf")),
        str(config.FONTS_DIR / ("Inter-Bold.otf" if bold else "Inter-SemiBold.otf")),
        # DM Sans
        str(config.FONTS_DIR / ("DMSans-Bold.ttf" if bold else "DMSans-SemiBold.ttf")),
        # Nunito Sans
        str(config.FONTS_DIR / ("NunitoSans-Bold.ttf" if bold else "NunitoSans-SemiBold.ttf")),
        # ── macOS system — use bold weights for solid look ──
        "/System/Library/Fonts/SFPro-Bold.otf" if bold else "/System/Library/Fonts/SFPro-Semibold.otf",
        "/System/Library/Fonts/SFPro-Heavy.otf" if bold else "/System/Library/Fonts/SFPro-Bold.otf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSText.ttf",
        # ── Linux fallbacks ──
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    # Also check any custom font files in assets/fonts/
    custom_fonts = list(config.FONTS_DIR.glob("*.ttf")) + list(config.FONTS_DIR.glob("*.otf"))
    for cf in custom_fonts:
        if str(cf) not in font_candidates:
            font_candidates.append(str(cf))

    for path in font_candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


# ── Claymorphism Renderer ─────────────────────────────

class ClayCompositor:
    """
    Renders styled videos from StoryScreenplay + AI images + narration.
    Supports multiple visual styles: claymorphism, glassmorphism, skeuomorphism,
    neo-brutalism, minimalism, liquid glass, hyper-realistic.
    """

    def __init__(
        self,
        video_format: str = "vertical",
        transition: str = "fade",
        platform: str = "",
        visual_style: str = "",
    ):
        fmt = config.VIDEO_FORMATS.get(video_format, config.VIDEO_FORMATS["vertical"])
        self.W = fmt["width"]
        self.H = fmt["height"]
        self.fps = config.FPS
        self.style = config.CLAY_STYLE
        self.transition = transition
        self.platform = platform.lower().strip()

        # Resolve visual style — merges style-specific colours into CLAY_STYLE
        self.visual_style_name = visual_style or config.DEFAULT_VISUAL_STYLE
        self._visual_style_config = config.VISUAL_STYLES.get(
            self.visual_style_name,
            config.VISUAL_STYLES.get("claymorphism", {}),
        )

        # Override background and colour tokens from the visual style
        vs = self._visual_style_config
        if vs:
            self.style = dict(self.style)  # shallow copy so we don't mutate global
            for key in (
                "bg_type", "bg_center_color", "bg_edge_color",
                "bg_vignette", "bg_vignette_strength",
                "text_dark", "text_medium", "text_light",
                "primary", "secondary", "accent",
                "card_bg", "card_radius", "image_corner_radius",
            ):
                if key in vs:
                    self.style[key] = vs[key]
            # Also copy gradient start/end for linear-type styles
            if "bg_gradient_start" in vs:
                self.style["bg_gradient_start"] = vs["bg_gradient_start"]
            if "bg_gradient_end" in vs:
                self.style["bg_gradient_end"] = vs["bg_gradient_end"]

        # Pre-compute zone boundaries
        # Brand strip .............. Y:  0%–10%
        # Upper text zone .......... Y: 12%–28%  (narration text when image present)
        # Content / image zone ..... Y: 28%–68%  (main visual asset — large)
        # Lower text zone .......... Y: 68%–82%  (narration text when image present)
        # Bottom strip ............. Y: 90%–100% (watermark)
        self._zone_brand_h = int(self.H * self.style["zone_brand_top"])
        self._zone_upper_text_h = int(self.H * self.style.get("zone_upper_text", 0.17))
        self._zone_narrative_h = self._zone_upper_text_h  # compat
        self._zone_content_h = int(self.H * self.style["zone_content"])
        self._zone_lower_text_h = int(self.H * self.style.get("zone_lower_text", 0.18))
        self._zone_bottom_h = int(self.H * self.style["zone_bottom"])

        # Zone Y positions
        self._brand_y = 0
        self._narrative_top_y = int(self.H * 0.12)       # upper zone starts at 12%
        self._upper_text_y = self._narrative_top_y        # alias
        self._content_y = int(self.H * 0.28)              # image zone starts at 28%
        self._narrative_bottom_y = int(self.H * 0.68)     # lower zone starts at 68%
        self._lower_text_y = self._narrative_bottom_y     # alias
        self._text_only_center_y = int(self.H * 0.45)     # text-only scenes centred at ~45%
        self._caption_y = int(self.H * 0.84)               # compat (unused now)
        self._bottom_y = self.H - self._zone_bottom_h

        # VFX engine configuration
        self._vfx = VFXConfig()
        self._grain_texture = None  # lazily initialised in compose()

        # Font sizes (increased for visual impact)
        self._title_size = max(36, int(self.H * self.style["title_size_ratio"]))
        self._body_size = max(28, int(self.H * self.style["body_size_ratio"]))
        self._emphasis_size = max(44, int(self.H * self.style["emphasis_size_ratio"]))
        self._brand_size = max(18, int(self.H * self.style["brand_size_ratio"]))

        # Documentary text sizes (progressive reveal) — solid and readable
        self._setup_size = max(34, int(self.H * self.style.get("setup_size_ratio", 0.040)))
        self._subject_size = max(42, int(self.H * self.style.get("subject_size_ratio", 0.054)))
        self._caption_size = max(24, int(self.H * self.style.get("caption_size_ratio", 0.030)))
        self._karaoke_size = max(30, int(self.H * self.style.get("karaoke_size_ratio", 0.035)))

    # ── Main Compose ──────────────────────────────────

    def compose(
        self,
        screenplay: StoryScreenplay,
        images: list[AIImageAsset],
        narrations: list[NarrationClip],
        output_dir: Path,
        output_filename: str = "output_video.mp4",
        include_subtitles: bool = True,
        color_grade: str = "none",
        watermark: str = "",
        brand_text: str = "",
        effects_plan: VideoEffectsPlan | None = None,
    ) -> dict:
        """
        Compose the final video from screenplay, AI images, and narration.
        Returns dict with video_path, srt_path, thumbnail_path, duration, resolution.
        """
        start_time = time.time()
        output_dir.mkdir(parents=True, exist_ok=True)

        brand = brand_text or screenplay.brand_text or ""
        wm = watermark or config.WATERMARK_TEXT or ""

        # Build lookup maps
        image_map: dict[int, list[AIImageAsset]] = {}
        for img in images:
            image_map.setdefault(img.screen_index, []).append(img)
        # Sort each by sub_index
        for k in image_map:
            image_map[k].sort(key=lambda x: x.sub_index)

        narration_map: dict[int, NarrationClip] = {}
        for n in narrations:
            narration_map[n.key_point_index] = n

        # ── Generate base background ──────────────────
        bg_img = self._create_background()

        # ── Pre-generate paper grain texture ──────────
        self._grain_texture = generate_paper_grain(self.W, self.H, cfg=self._vfx)

        # ── Pre-generate light leak overlay ───────────
        self._light_leak = generate_light_leak(self.W, self.H, cfg=self._vfx)

        # ── Store effects plan ────────────────────────
        self._effects_plan = effects_plan
        self._effects_map: dict[int, SceneEffectsPlan] = {}
        if effects_plan:
            for sp in effects_plan.scenes:
                self._effects_map[sp.screen_index] = sp

        # ── Build scenes ──────────────────────────────
        scenes: list[VideoClip] = []
        running_time = 0.0

        # Intro screen (Type A hook — image-only when possible)
        hero_image = images[0] if images else None
        intro_dur = self.style.get("intro_duration", 2.5)
        intro_scene = self._create_intro_scene(
            screenplay.title, screenplay.hook, brand, wm, bg_img,
            hero_image=hero_image, duration=intro_dur,
        )
        scenes.append(intro_scene)
        running_time += intro_scene.duration

        # Content screens
        for screen in screenplay.screens:
            screen_images = image_map.get(screen.index, [])
            screen_narration = narration_map.get(screen.index)

            # Use narration duration if available, else screen.duration
            duration = screen_narration.duration if screen_narration else screen.duration
            # Enforce min/max
            duration = max(config.CLAY_SCREEN_MIN_DURATION, duration)

            scene = self._create_screen_scene(
                screen, screen_images, screen_narration,
                duration, brand, wm, bg_img,
            )
            scenes.append(scene)
            running_time += duration

        # Outro screen (4-6s breathing room per guide §8)
        outro_dur = self.style.get("outro_duration", 5.0)
        outro_scene = self._create_outro_scene(
            screenplay.cta or "Thanks for watching!", brand, wm, bg_img,
            duration=outro_dur,
        )
        scenes.append(outro_scene)
        running_time += outro_scene.duration

        # ── Apply scene transitions (VFX agent or legacy rotation) ──
        scenes = self._add_transitions(scenes)

        # ── Concatenate ──────────────────────────────
        final_video = concatenate_videoclips(scenes, method="compose")

        # ── Mix audio ─────────────────────────────────
        audio_clips = []
        time_offset = scenes[0].duration  # after intro

        for screen in screenplay.screens:
            narr = narration_map.get(screen.index)
            if narr and narr.audio_path.exists():
                aclip = AudioFileClip(str(narr.audio_path))
                aclip = aclip.with_start(time_offset)
                audio_clips.append(aclip)
            time_offset += (narr.duration if narr else screen.duration)

        if audio_clips:
            mixed_audio = CompositeAudioClip(audio_clips)
            final_video = final_video.with_audio(mixed_audio)

        # ── Apply color grade ─────────────────────────
        if color_grade and color_grade != "none":
            final_video = self._apply_color_grade(final_video, color_grade)

        # ── Render ────────────────────────────────────
        video_path = output_dir / output_filename
        logger.info("Rendering video to %s", video_path)

        final_video.write_videofile(
            str(video_path),
            fps=self.fps,
            codec=config.VIDEO_CODEC,
            audio_codec=config.AUDIO_CODEC,
            bitrate=config.VIDEO_BITRATE,
            threads=config.RENDER_THREADS,
            logger=None,
        )

        # No separate SRT — narration text rendered directly in video
        srt_path = None

        # ── Thumbnail ─────────────────────────────────
        thumb_path = output_dir / "thumbnail.jpg"
        self._generate_thumbnail(screenplay, images, brand, wm, bg_img, thumb_path)

        # Clean up
        final_video.close()
        for clip in scenes:
            try:
                clip.close()
            except Exception:
                pass
        for ac in audio_clips:
            try:
                ac.close()
            except Exception:
                pass

        elapsed = time.time() - start_time
        logger.info("Video rendered in %.1fs: %s", elapsed, video_path)

        return {
            "video_path": video_path,
            "srt_path": srt_path,
            "thumbnail_path": thumb_path,
            "duration": round(final_video.duration, 1),
            "resolution": f"{self.W}x{self.H}",
            "format": f"{self.W}x{self.H}",
        }

    # ══════════════════════════════════════════════════
    #  BACKGROUND GENERATION
    # ══════════════════════════════════════════════════

    def _create_background(self) -> Image.Image:
        """Create the background — radial gradient with vignette (documentary) or linear (classic)."""
        bg = Image.new("RGB", (self.W, self.H))

        bg_type = self.style.get("bg_type", "radial")

        if bg_type == "radial":
            # Radial gradient: bright centre, darker edges
            center_c = self.style.get("bg_center_color", (240, 238, 236))
            edge_c = self.style.get("bg_edge_color", (200, 196, 192))
            cx = int(self.W * self.style.get("bg_gradient_center_x", 0.50))
            cy = int(self.H * self.style.get("bg_gradient_center_y", 0.45))
            # Max distance from centre to any corner
            max_dist = math.sqrt(max(cx, self.W - cx) ** 2 + max(cy, self.H - cy) ** 2)

            pixels = np.zeros((self.H, self.W, 3), dtype=np.uint8)
            yy, xx = np.mgrid[0:self.H, 0:self.W]
            dist = np.sqrt((xx - cx).astype(np.float64) ** 2 + (yy - cy).astype(np.float64) ** 2)
            t = np.clip(dist / max_dist, 0.0, 1.0)

            for c in range(3):
                pixels[:, :, c] = (center_c[c] + (edge_c[c] - center_c[c]) * t).astype(np.uint8)

            bg = Image.fromarray(pixels, "RGB")
        else:
            # Linear gradient (legacy fallback)
            draw = ImageDraw.Draw(bg)
            gs = self.style["bg_gradient_start"]
            ge = self.style["bg_gradient_end"]
            for y in range(self.H):
                t = y / self.H
                r = int(gs[0] + (ge[0] - gs[0]) * t)
                g = int(gs[1] + (ge[1] - gs[1]) * t)
                b = int(gs[2] + (ge[2] - gs[2]) * t)
                draw.line([(0, y), (self.W, y)], fill=(r, g, b))

        # Vignette overlay — darken edges by specified strength
        if self.style.get("bg_vignette", False):
            strength = self.style.get("bg_vignette_strength", 0.20)
            vignette = Image.new("L", (self.W, self.H), 255)
            vig_cx, vig_cy = self.W // 2, self.H // 2
            max_vig_dist = math.sqrt(vig_cx ** 2 + vig_cy ** 2)

            yy, xx = np.mgrid[0:self.H, 0:self.W]
            vdist = np.sqrt((xx - vig_cx).astype(np.float64) ** 2 + (yy - vig_cy).astype(np.float64) ** 2)
            vt = np.clip(vdist / max_vig_dist, 0.0, 1.0)
            # Smooth falloff: vignette is darker at edges
            vig_arr = (255 * (1.0 - strength * vt ** 1.5)).astype(np.uint8)
            vignette = Image.fromarray(vig_arr, "L")

            # Apply vignette as brightness mask
            from PIL import ImageEnhance
            bg_rgba = bg.convert("RGBA")
            dark = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 255))
            # Use vignette as composite mask — dark overlay where vignette is dark
            inv_vig = Image.fromarray(255 - vig_arr, "L")
            bg_rgba = Image.composite(dark, bg_rgba, inv_vig)
            bg = bg_rgba.convert("RGB")

        # Subtle warm accent blob (optional, disabled by default for documentary)
        if self.style.get("bg_accent_blob"):
            blob_color = self.style["bg_accent_blob"]
            if isinstance(blob_color, tuple) and len(blob_color) == 4:
                blob = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
                blob_draw = ImageDraw.Draw(blob)
                bcx, bcy = int(self.W * 0.75), int(self.H * 0.2)
                blob_r = int(min(self.W, self.H) * 0.35)
                blob_draw.ellipse(
                    [bcx - blob_r, bcy - blob_r, bcx + blob_r, bcy + blob_r],
                    fill=blob_color,
                )
                blob = blob.filter(ImageFilter.GaussianBlur(radius=blob_r // 2))
                bg.paste(Image.alpha_composite(
                    bg.convert("RGBA"), blob
                ).convert("RGB"))

        return bg

    # ══════════════════════════════════════════════════
    #  INTRO / OUTRO SCREENS
    # ══════════════════════════════════════════════════

    def _create_intro_scene(
        self, title: str, hook: str, brand: str, watermark: str,
        bg: Image.Image, hero_image: Optional[AIImageAsset] = None,
        duration: float = 2.5,
    ) -> VideoClip:
        """Scene Type A — Hook Opener with hero image + title.

        Always shows both the hero image AND the title text so viewers
        immediately understand what the video is about.
        """
        fade_dur = self.style["fade_duration"]
        entry_start = self.style.get("entry_scale_start", 0.95)
        entry_end = self.style.get("entry_scale_end", 1.0)
        entry_range = entry_end - entry_start

        # Prepare hero image if available
        clay_hero = None
        if hero_image:
            try:
                clay_hero = self._prepare_clay_image(hero_image.local_path)
            except Exception:
                clay_hero = None

        def make_frame(t):
            frame = bg.copy()
            draw = ImageDraw.Draw(frame)

            # Brand bar (always visible)
            self._draw_brand_bar(draw, brand)

            # Hero image in centre zone (if available) — elastic entrance + wiggle
            if clay_hero:
                self._draw_clay_image(
                    frame, clay_hero,
                    y_center=self._content_y + int(self._zone_content_h * 0.45),
                    alpha=1.0, scale=1.0, t=t,
                    image_index=0, appear_time=0.0,
                )

            # Title text — always shown (upper zone for image, centre for text-only)
            title_alpha = min(1.0, t / fade_dur) if t < fade_dur else 1.0
            title_font = _get_font(self._title_size + 8, bold=True)
            title_y = (
                self._upper_text_y + self._zone_upper_text_h // 2
                if clay_hero
                else self._content_y + self._zone_content_h // 3
            )
            self._draw_text_centered(
                frame, draw, self._safe_text(title),
                y_center=title_y,
                font=title_font,
                color=self.style["text_dark"],
                alpha=title_alpha,
                max_width=int(self.W * 0.82),
            )

            # Hook text below title or in lower zone
            if hook:
                hook_delay = 0.4
                hook_alpha = max(0, min(1.0, (t - hook_delay) / fade_dur))
                hook_font = _get_font(self._body_size + 2)
                hook_y = (
                    self._lower_text_y + self._zone_lower_text_h // 2
                    if clay_hero
                    else self._content_y + int(self._zone_content_h * 0.6)
                )
                self._draw_text_centered(
                    frame, draw, self._safe_text(f'"{hook}"'),
                    y_center=hook_y,
                    font=hook_font,
                    color=self.style["text_medium"],
                    alpha=hook_alpha,
                    max_width=int(self.W * 0.78),
                )

            self._draw_watermark(draw, watermark)
            return np.array(frame)

        return VideoClip(make_frame, duration=duration).with_fps(self.fps)

    def _create_outro_scene(
        self, cta: str, brand: str, watermark: str,
        bg: Image.Image, duration: float = 5.0
    ) -> VideoClip:
        """Create outro screen with platform-specific CTA button animation.

        YouTube → "Subscribe for more"
        Instagram/TikTok/Twitter → "Follow for more"
        Generic → story CTA text
        Includes animated pill-shaped button with scale/color pulse.
        """
        fade_dur = self.style["fade_duration"]
        platform = self.platform

        # Determine CTA texts based on platform
        if platform in ("youtube", "youtube_shorts"):
            button_text = "Subscribe for More"
            sub_text = "Hit the bell for updates!"
        elif platform in ("instagram", "instagram_reels", "tiktok"):
            button_text = "Follow for More"
            sub_text = "Double tap if you enjoyed!"
        elif platform in ("twitter", "x", "linkedin"):
            button_text = "Follow for More"
            sub_text = "Share with your network!"
        else:
            button_text = "Follow for More"
            sub_text = ""

        cta_display = self._safe_text(cta) if cta and cta != "Thanks for watching!" else ""

        # Button styling
        btn_color_base = self.style.get("secondary", (200, 130, 160))
        btn_text_color = (255, 255, 255)
        btn_radius = 30

        def make_frame(t):
            frame = bg.copy()
            draw = ImageDraw.Draw(frame)
            self._draw_brand_bar(draw, brand)

            overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
            odraw = ImageDraw.Draw(overlay)

            # CTA text (story-specific) — fades in first
            if cta_display:
                cta_alpha = min(1.0, t / fade_dur)
                cta_font = _get_font(self._body_size + 4, bold=True)
                a = int(cta_alpha * 255)
                cta_lines = self._wrap_text(cta_display, cta_font, int(self.W * 0.8))
                cta_lh = cta_font.getbbox("Ag")[3] - cta_font.getbbox("Ag")[1]
                cta_y = self._content_y + self._zone_content_h // 4
                for line in cta_lines:
                    bbox = cta_font.getbbox(line)
                    tw = bbox[2] - bbox[0]
                    x = (self.W - tw) // 2
                    odraw.text((x + 1, cta_y + 1), line, fill=(0, 0, 0, 30), font=cta_font)
                    odraw.text((x, cta_y), line, fill=(*self.style["text_dark"][:3], a), font=cta_font)
                    cta_y += cta_lh + 6

            # Animated pill button — appears after 0.8s with scale pop
            btn_delay = 0.8
            if t > btn_delay:
                btn_t = t - btn_delay
                btn_alpha = min(1.0, btn_t / 0.4)
                # Scale pop: 0.0 → 1.08 → 1.0
                if btn_t < 0.3:
                    btn_scale = (btn_t / 0.3) * 1.08
                elif btn_t < 0.5:
                    btn_scale = 1.08 - 0.08 * ((btn_t - 0.3) / 0.2)
                else:
                    btn_scale = 1.0
                    # Subtle pulse after settled
                    btn_scale = 1.0 + 0.02 * math.sin(btn_t * 3)

                # Skip rendering when scale is too small to produce a valid font
                btn_font_size = max(12, int((self._body_size + 8) * btn_scale))
                if btn_scale >= 0.15:
                    btn_font = _get_font(btn_font_size, bold=True)
                    bbox = btn_font.getbbox(button_text)
                    text_w = bbox[2] - bbox[0]
                    text_h = bbox[3] - bbox[1]
                    pad_x, pad_y = 50, 22

                    btn_x = (self.W - text_w - pad_x * 2) // 2
                    btn_y_pos = self._content_y + int(self._zone_content_h * 0.58)
                    ba = int(btn_alpha * 230)

                    # Pill button background with colour pulse
                    pulse_shift = int(20 * math.sin(btn_t * 2))
                    btn_color = (
                        min(255, btn_color_base[0] + pulse_shift),
                        min(255, btn_color_base[1] + pulse_shift // 2),
                        min(255, btn_color_base[2] + pulse_shift // 3),
                        ba,
                    )
                    odraw.rounded_rectangle(
                        [btn_x, btn_y_pos, btn_x + text_w + pad_x * 2, btn_y_pos + text_h + pad_y * 2],
                        radius=max(1, int(btn_radius * btn_scale)),
                        fill=btn_color,
                    )
                    # Button text
                    tx = btn_x + pad_x
                    ty = btn_y_pos + pad_y
                    odraw.text((tx, ty), button_text, fill=(*btn_text_color, ba), font=btn_font)

                    # Sub-text below button
                    if sub_text:
                        sub_delay = btn_delay + 0.6
                        if t > sub_delay:
                            sub_alpha = min(1.0, (t - sub_delay) / 0.3)
                            sub_font = _get_font(self._caption_size + 2)
                            sa = int(sub_alpha * 200)
                            sub_bbox = sub_font.getbbox(sub_text)
                            sw = sub_bbox[2] - sub_bbox[0]
                            sx = (self.W - sw) // 2
                            sy = btn_y_pos + text_h + pad_y * 2 + 20
                            odraw.text((sx, sy), sub_text, fill=(*self.style["text_medium"][:3], sa), font=sub_font)

            comp = Image.alpha_composite(frame.convert("RGBA"), overlay)
            frame = comp.convert("RGB")
            draw = ImageDraw.Draw(frame)
            self._draw_watermark(draw, watermark)
            return np.array(frame)

        return VideoClip(make_frame, duration=duration).with_fps(self.fps)

    # ══════════════════════════════════════════════════
    #  SCREEN SCENE CREATION
    # ══════════════════════════════════════════════════

    def _create_screen_scene(
        self,
        screen: ScreenSegment,
        images: list[AIImageAsset],
        narration: Optional[NarrationClip],
        duration: float,
        brand: str,
        watermark: str,
        bg: Image.Image,
    ) -> VideoClip:
        """Create a scene for one screen segment with VFX overlays."""
        if screen.visual_type == "text_only":
            base_clip = self._create_text_only_scene(
                screen, narration, duration, brand, watermark, bg
            )
        elif screen.visual_type == "multi_image" and len(images) > 1:
            base_clip = self._create_multi_image_scene(
                screen, images, narration, duration, brand, watermark, bg
            )
        elif images:
            base_clip = self._create_single_image_scene(
                screen, images[0], narration, duration, brand, watermark, bg
            )
        else:
            # Fallback: treat as text_only if no image generated
            base_clip = self._create_text_only_scene(
                screen, narration, duration, brand, watermark, bg
            )

        # Add speaker indicator for Ghost Collaboration dialogue mode
        if screen.speaker and screen.speaker in ("narrator", "character"):
            base_clip = self._add_speaker_indicator(
                base_clip, screen, duration, bg,
            )

        # ── VFX Post-Processing: Paper texture + Smart Flash + Light Leaks + Effects Plan ──
        grain = self._grain_texture
        leak = self._light_leak
        vfx_cfg = self._vfx
        word_timings = narration.word_timings if narration else []
        fade_dur = self.style["fade_duration"]
        # Get the effects plan for this screen (from the AI agent)
        scene_fx = self._effects_map.get(screen.index)

        def vfx_post(get_frame, t):
            frame = get_frame(t)
            # Paper texture overlay (subtle grain)
            if grain is not None and vfx_cfg.paper_texture_opacity > 0:
                frame = apply_paper_texture(frame, grain, vfx_cfg)
            # Smart flash frame: only on reveal moments (first word of screen)
            if word_timings and should_flash_reveal(t, 0.0, word_timings, self.fps, vfx_cfg):
                frame = apply_warm_flash(frame, vfx_cfg)
            # Light leaks: warm glow near transition edges (fade in at start, out at end)
            if leak is not None and vfx_cfg.light_leak_opacity > 0:
                leak_intensity = 0.0
                if t < fade_dur:
                    leak_intensity = 1.0 - (t / fade_dur)
                elif t > duration - fade_dur:
                    leak_intensity = (t - (duration - fade_dur)) / fade_dur
                if leak_intensity > 0.01:
                    frame = apply_light_leak(frame, leak, leak_intensity, vfx_cfg)
            # ── NEW: Apply overlay effects from the VFX agent ──
            if scene_fx and scene_fx.overlay_effect and scene_fx.overlay_effect != "overlay_none":
                try:
                    frame = apply_overlay_effect(
                        scene_fx.overlay_effect, frame, t, scene_fx.overlay_params,
                    )
                except Exception as exc:
                    logger.debug("Overlay effect error in scene %d: %s", screen.index, exc)
            return frame

        return base_clip.transform(vfx_post)

    def _add_speaker_indicator(
        self,
        base_clip: VideoClip,
        screen: ScreenSegment,
        duration: float,
        bg: Image.Image,
    ) -> VideoClip:
        """Overlay a speaker label pill at the top of the scene for dialogue mode.
        
        Shows who is speaking: "Narrator" or the character's name.
        Uses different icon and colour for narrator vs character.
        """
        is_character = screen.speaker == "character"
        speaker_name = screen.character_name if is_character and screen.character_name else (
            "Character" if is_character else "Narrator"
        )
        icon = "\u2728" if is_character else "\U0001f399\ufe0f"  # sparkles / microphone
        label_text = f"{speaker_name}"

        # Label styling
        label_font = _get_font(self._caption_size + 4, bold=True)
        label_color = (
            self.style.get("accent", (255, 136, 0))
            if is_character
            else self.style.get("text_medium", (120, 120, 120))
        )
        pill_bg_color = (
            (*label_color[:3], 40)
            if isinstance(label_color, tuple) and len(label_color) >= 3
            else (255, 136, 0, 40)
        )

        def make_frame(t):
            # Get the base frame
            base_frame = base_clip.get_frame(t)
            frame = Image.fromarray(base_frame)
            
            # Fade in the label
            fade_dur = 0.3
            label_alpha = min(1.0, t / fade_dur) if t < fade_dur else 1.0
            # Fade out near end
            if t > duration - 0.5:
                label_alpha = max(0.0, (duration - t) / 0.5)

            if label_alpha <= 0:
                return base_frame

            overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
            odraw = ImageDraw.Draw(overlay)

            # Measure label
            bbox = label_font.getbbox(label_text)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            pad_x, pad_y = 20, 8

            # Position: top-left, below brand bar
            label_y = self._zone_brand_h + 12
            label_x = int(self.W * 0.06)

            a = int(label_alpha * 200)

            # Pill background
            odraw.rounded_rectangle(
                [label_x, label_y, label_x + text_w + pad_x * 2, label_y + text_h + pad_y * 2],
                radius=12,
                fill=(*pill_bg_color[:3], min(a, 60)),
            )

            # Label text
            odraw.text(
                (label_x + pad_x, label_y + pad_y),
                label_text,
                fill=(*label_color[:3], a),
                font=label_font,
            )

            comp = Image.alpha_composite(frame.convert("RGBA"), overlay)
            return np.array(comp.convert("RGB"))

        return VideoClip(make_frame, duration=duration).with_fps(self.fps)

    # ── Single Image Screen ───────────────────────────

    def _create_single_image_scene(
        self,
        screen: ScreenSegment,
        image: AIImageAsset,
        narration: Optional[NarrationClip],
        duration: float,
        brand: str,
        watermark: str,
        bg: Image.Image,
    ) -> VideoClip:
        """Image scene — big image with content-level transitions.

        Background stays static. Image slides/swipes in and out.
        Narration text enters from below and exits upward.
        Enhanced with AI-selected effects from the VFX agent.
        """
        # Pre-process the image
        clay_img = self._prepare_clay_image(image.local_path)

        # Word timings from narration engine
        word_timings = narration.word_timings if narration else []

        # Decide text position: alternate between upper and lower
        text_above = (screen.narration_position == "top")

        # Image transition type for this screen
        img_trans_type = get_image_transition_for_scene(screen.index)

        # Get effects plan for this screen from the AI agent
        scene_fx = self._effects_map.get(screen.index)
        W, H = self.W, self.H

        def make_frame(t):
            frame = bg.copy()

            # ── NEW: Apply background effect from VFX agent ──
            if scene_fx and scene_fx.background_effect and scene_fx.background_effect != "bg_none":
                try:
                    frame = apply_background_effect(
                        scene_fx.background_effect, frame, t, scene_fx.background_params,
                    )
                except Exception as exc:
                    logger.debug("BG effect error in image scene %d: %s", screen.index, exc)

            draw = ImageDraw.Draw(frame)

            # Brand bar
            self._draw_brand_bar(draw, brand)

            # Image — with content-level transition (slide/swipe/fast-slow-fast)
            img_x_off, img_y_off, img_alpha = image_transition_offset(
                t, duration, self.W, self.H, img_trans_type, screen.index,
            )

            if img_alpha > 0.01:
                # ── NEW: Apply image treatment from VFX agent ──
                display_img = clay_img
                if scene_fx and scene_fx.image_treatment and scene_fx.image_treatment != "static_image":
                    try:
                        display_img = apply_image_effect(
                            scene_fx.image_treatment, clay_img.copy(),
                            t, duration, scene_fx.image_treatment_params,
                        )
                    except Exception as exc:
                        display_img = clay_img
                        logger.debug("Image treatment error in scene %d: %s", screen.index, exc)

                self._draw_clay_image(
                    frame, display_img,
                    y_center=self._content_y + self._zone_content_h // 2 + img_y_off,
                    x_center=self.W // 2 + img_x_off,
                    alpha=img_alpha,
                    scale=1.0,
                    t=t,
                    image_index=0,
                    appear_time=0.0,
                    screen_duration=duration,
                )

            # Narration text — with enter/exit transitions
            if text_above:
                base_text_y = self._upper_text_y + self._zone_upper_text_h // 2
            else:
                base_text_y = self._lower_text_y + self._zone_lower_text_h // 2

            # Text enter/exit offsets (legacy system)
            enter_y, enter_alpha = text_enter_offset(t, duration, self.H)
            exit_y, exit_alpha = text_exit_offset(t, duration, self.H)
            text_y = base_text_y + enter_y + exit_y
            text_alpha = min(enter_alpha, exit_alpha)

            # ── NEW: Overlay enhanced text entry/exit/continuous from VFX agent ──
            text_x_off = 0
            text_scale = 1.0
            text_glow = 0.0
            if scene_fx:
                try:
                    entry_tx = get_text_entry_transform(
                        scene_fx.text_entry, t, duration, W, H,
                        scene_fx.text_entry_params,
                    )
                    text_alpha = min(text_alpha, entry_tx.get("alpha", 1.0))
                    text_y += entry_tx.get("y_offset", 0)
                    text_x_off += entry_tx.get("x_offset", 0)
                    text_scale *= entry_tx.get("scale", 1.0)
                except Exception as exc:
                    logger.debug("Text entry error in image scene %d: %s", screen.index, exc)
                try:
                    exit_start = max(0, duration - 0.5)
                    exit_tx = get_text_exit_transform(
                        scene_fx.text_exit, t, duration, exit_start, W, H,
                        scene_fx.text_exit_params,
                    )
                    text_alpha = min(text_alpha, exit_tx.get("alpha", 1.0))
                    text_y += exit_tx.get("y_offset", 0)
                    text_x_off += exit_tx.get("x_offset", 0)
                    text_scale *= exit_tx.get("scale", 1.0)
                except Exception as exc:
                    logger.debug("Text exit error in image scene %d: %s", screen.index, exc)
                try:
                    if scene_fx.text_continuous and scene_fx.text_continuous != "none":
                        cont_tx = get_text_continuous_transform(
                            scene_fx.text_continuous, t, scene_fx.text_continuous_params,
                        )
                        text_y += cont_tx.get("y_offset", 0)
                        text_x_off += cont_tx.get("x_offset", 0)
                        text_alpha *= cont_tx.get("alpha", 1.0)
                        text_scale *= cont_tx.get("scale", 1.0)
                        text_glow = max(text_glow, cont_tx.get("glow_intensity", 0.0))
                except Exception as exc:
                    logger.debug("Text cont error in image scene %d: %s", screen.index, exc)

            if text_alpha > 0.01:
                self._draw_narration_text(
                    frame, draw, screen.text, word_timings,
                    y_center=text_y, t=t, duration=duration,
                    text_alpha=text_alpha,
                    x_offset=text_x_off,
                    text_scale=text_scale,
                    glow_intensity=text_glow,
                )

            # Watermark
            self._draw_watermark(draw, watermark)

            return np.array(frame)

        return VideoClip(make_frame, duration=duration).with_fps(self.fps)

    # ── Multi-Image Screen ────────────────────────────

    def _create_multi_image_scene(
        self,
        screen: ScreenSegment,
        images: list[AIImageAsset],
        narration: Optional[NarrationClip],
        duration: float,
        brand: str,
        watermark: str,
        bg: Image.Image,
    ) -> VideoClip:
        """Multi-image scene with quadrant grid layout.

        Screen divided into 4 quadrants: TL, TR, BL, BR.
        - 2 images: top-left + bottom-right (text in top-right + bottom-left)
        - 3 images: any 3 quadrants (text in remaining)
        - 4 images: all 4 quadrants (text overlaid in center)
        Background animated via VFX agent. Images have content-level transitions.
        """
        num_images = len(images)

        # Pre-process images (smaller for grid — use 0.42 ratio for quadrant fit)
        clay_images = []
        for img in images:
            clay_images.append(self._prepare_clay_image(img.local_path, max_ratio=0.42))

        word_timings = narration.word_timings if narration else []
        stagger_interval = min(0.8, (duration - 1.0) / max(num_images, 1))

        # Get effects plan for this screen from the AI agent
        scene_fx = self._effects_map.get(screen.index)
        W, H = self.W, self.H

        # Quadrant positions: (x_center, y_center)
        # Screen divided from content zone into 4 areas
        content_y = self._content_y
        content_h = self._zone_content_h
        q_left_x = int(self.W * 0.27)
        q_right_x = int(self.W * 0.73)
        q_top_y = content_y + int(content_h * 0.28)
        q_bottom_y = content_y + int(content_h * 0.72)

        # Quadrant assignments: TL, TR, BL, BR
        all_quadrants = [
            (q_left_x, q_top_y),    # TL
            (q_right_x, q_top_y),   # TR
            (q_left_x, q_bottom_y), # BL
            (q_right_x, q_bottom_y),# BR
        ]

        if num_images == 2:
            # Images in TL and BR; text in TR and BL
            image_slots = [0, 3]  # TL, BR
            text_quadrants = [1, 2]  # TR, BL
        elif num_images == 3:
            # Images in TL, TR, BL; text in BR
            image_slots = [0, 1, 2]
            text_quadrants = [3]
        else:
            # All 4 quadrants for images; text in center overlay
            image_slots = list(range(min(num_images, 4)))
            text_quadrants = []

        def make_frame(t):
            frame = bg.copy()

            # ── VFX Agent: Background effect ──
            if scene_fx and scene_fx.background_effect and scene_fx.background_effect != "bg_none":
                try:
                    frame = apply_background_effect(
                        scene_fx.background_effect, frame, t, scene_fx.background_params,
                    )
                except Exception as exc:
                    logger.debug("BG effect error in multi_image scene %d: %s", screen.index, exc)

            draw = ImageDraw.Draw(frame)
            self._draw_brand_bar(draw, brand)

            # Draw images in their assigned quadrants with staggered entrance
            for slot_idx, img_idx in enumerate(image_slots):
                if img_idx >= len(clay_images):
                    break
                clay_img = clay_images[img_idx]
                appear_t = slot_idx * stagger_interval + 0.2
                qx, qy = all_quadrants[image_slots[slot_idx]]

                self._draw_clay_image(
                    frame, clay_img,
                    y_center=qy, x_center=qx,
                    alpha=1.0, scale=1.0,
                    t=t,
                    image_index=slot_idx,
                    appear_time=appear_t,
                    screen_duration=duration,
                )

            # Narration text in text quadrant(s) or center overlay
            enter_y, enter_alpha = text_enter_offset(t, duration, self.H)
            exit_y, exit_alpha = text_exit_offset(t, duration, self.H)
            text_y_off = enter_y + exit_y
            text_alpha_val = min(enter_alpha, exit_alpha)

            # ── VFX Agent: Enhanced text entry/exit/continuous ──
            text_x_off = 0
            text_scale = 1.0
            text_glow = 0.0
            if scene_fx:
                try:
                    entry_tx = get_text_entry_transform(
                        scene_fx.text_entry, t, duration, W, H,
                        scene_fx.text_entry_params,
                    )
                    text_alpha_val = min(text_alpha_val, entry_tx.get("alpha", 1.0))
                    text_y_off += entry_tx.get("y_offset", 0)
                    text_x_off += entry_tx.get("x_offset", 0)
                    text_scale *= entry_tx.get("scale", 1.0)
                except Exception as exc:
                    logger.debug("Text entry error in multi_image scene %d: %s", screen.index, exc)
                try:
                    exit_start = max(0, duration - 0.5)
                    exit_tx = get_text_exit_transform(
                        scene_fx.text_exit, t, duration, exit_start, W, H,
                        scene_fx.text_exit_params,
                    )
                    text_alpha_val = min(text_alpha_val, exit_tx.get("alpha", 1.0))
                    text_y_off += exit_tx.get("y_offset", 0)
                    text_x_off += exit_tx.get("x_offset", 0)
                    text_scale *= exit_tx.get("scale", 1.0)
                except Exception as exc:
                    logger.debug("Text exit error in multi_image scene %d: %s", screen.index, exc)
                try:
                    if scene_fx.text_continuous and scene_fx.text_continuous != "none":
                        cont_tx = get_text_continuous_transform(
                            scene_fx.text_continuous, t, scene_fx.text_continuous_params,
                        )
                        text_y_off += cont_tx.get("y_offset", 0)
                        text_x_off += cont_tx.get("x_offset", 0)
                        text_alpha_val *= cont_tx.get("alpha", 1.0)
                        text_scale *= cont_tx.get("scale", 1.0)
                        text_glow = max(text_glow, cont_tx.get("glow_intensity", 0.0))
                except Exception as exc:
                    logger.debug("Text cont error in multi_image scene %d: %s", screen.index, exc)

            if text_alpha_val > 0.01:
                if text_quadrants:
                    # Place text in the first text quadrant
                    tx, ty = all_quadrants[text_quadrants[0]]
                    self._draw_narration_text(
                        frame, draw, screen.text, word_timings,
                        y_center=ty + text_y_off, t=t, duration=duration,
                        text_alpha=text_alpha_val,
                        x_offset=text_x_off,
                        text_scale=text_scale,
                        glow_intensity=text_glow,
                    )
                else:
                    # 4 images: center overlay with bold text
                    center_y = content_y + content_h // 2
                    self._draw_narration_text(
                        frame, draw, screen.text, word_timings,
                        y_center=center_y + text_y_off, t=t, duration=duration,
                        larger=True, text_alpha=text_alpha_val,
                        x_offset=text_x_off,
                        text_scale=text_scale,
                        glow_intensity=text_glow,
                    )

            self._draw_watermark(draw, watermark)
            return np.array(frame)

        return VideoClip(make_frame, duration=duration).with_fps(self.fps)

    # ── Text-Only Screen ──────────────────────────────

    def _create_text_only_scene(
        self,
        screen: ScreenSegment,
        narration: Optional[NarrationClip],
        duration: float,
        brand: str,
        watermark: str,
        bg: Image.Image,
    ) -> VideoClip:
        """Text-only scene — narration words appear centred with enter/exit transitions.

        Background is static (or animated via VFX agent).
        Text slides in from below and exits upward, enhanced by VFX agent effects.
        """
        word_timings = narration.word_timings if narration else []
        scene_fx = self._effects_map.get(screen.index)
        W, H = self.W, self.H

        def make_frame(t):
            frame = bg.copy()

            # ── VFX Agent: Background effect ──
            if scene_fx and scene_fx.background_effect and scene_fx.background_effect != "bg_none":
                try:
                    frame = apply_background_effect(
                        scene_fx.background_effect, frame, t, scene_fx.background_params,
                    )
                except Exception as exc:
                    logger.debug("BG effect error in text_only scene %d: %s", screen.index, exc)

            draw = ImageDraw.Draw(frame)
            self._draw_brand_bar(draw, brand)

            # Text enter/exit transitions (legacy system)
            content_center = self._content_y + self._zone_content_h // 2
            enter_y, enter_alpha = text_enter_offset(t, duration, self.H)
            exit_y, exit_alpha = text_exit_offset(t, duration, self.H)
            text_y = content_center + enter_y + exit_y
            text_alpha = min(enter_alpha, exit_alpha)

            # ── VFX Agent: Enhanced text entry/exit/continuous ──
            text_x_off = 0
            text_scale = 1.0
            text_glow = 0.0
            if scene_fx:
                try:
                    entry_tx = get_text_entry_transform(
                        scene_fx.text_entry, t, duration, W, H,
                        scene_fx.text_entry_params,
                    )
                    text_alpha = min(text_alpha, entry_tx.get("alpha", 1.0))
                    text_y += entry_tx.get("y_offset", 0)
                    text_x_off += entry_tx.get("x_offset", 0)
                    text_scale *= entry_tx.get("scale", 1.0)
                except Exception as exc:
                    logger.debug("Text entry error in text_only scene %d: %s", screen.index, exc)
                try:
                    exit_start = max(0, duration - 0.5)
                    exit_tx = get_text_exit_transform(
                        scene_fx.text_exit, t, duration, exit_start, W, H,
                        scene_fx.text_exit_params,
                    )
                    text_alpha = min(text_alpha, exit_tx.get("alpha", 1.0))
                    text_y += exit_tx.get("y_offset", 0)
                    text_x_off += exit_tx.get("x_offset", 0)
                    text_scale *= exit_tx.get("scale", 1.0)
                except Exception as exc:
                    logger.debug("Text exit error in text_only scene %d: %s", screen.index, exc)
                try:
                    if scene_fx.text_continuous and scene_fx.text_continuous != "none":
                        cont_tx = get_text_continuous_transform(
                            scene_fx.text_continuous, t, scene_fx.text_continuous_params,
                        )
                        text_y += cont_tx.get("y_offset", 0)
                        text_x_off += cont_tx.get("x_offset", 0)
                        text_alpha *= cont_tx.get("alpha", 1.0)
                        text_scale *= cont_tx.get("scale", 1.0)
                        text_glow = max(text_glow, cont_tx.get("glow_intensity", 0.0))
                except Exception as exc:
                    logger.debug("Text cont error in text_only scene %d: %s", screen.index, exc)

            if text_alpha > 0.01:
                self._draw_narration_text(
                    frame, draw, screen.text, word_timings,
                    y_center=text_y, t=t, duration=duration,
                    larger=True, text_alpha=text_alpha,
                    x_offset=text_x_off,
                    text_scale=text_scale,
                    glow_intensity=text_glow,
                )

            self._draw_watermark(draw, watermark)
            return np.array(frame)

        return VideoClip(make_frame, duration=duration).with_fps(self.fps)

    def _draw_progressive_reveal(
        self,
        frame: Image.Image,
        setup_text: str,
        subject_text: str,
        y_center: int,
        t: float,
        fade_dur: float = 0.4,
        stagger: float = 0.5,
    ):
        """
        Documentary two-line reveal: regular-weight setup line fades in first,
        bold-weight subject line follows after stagger delay.
        """
        text_color = self.style.get("text_dark", (61, 61, 61))
        setup_font = _get_font(self._setup_size)
        subject_font = _get_font(self._subject_size, bold=True)
        max_w = int(self.W * 0.80)

        # Wrap both lines
        setup_lines = self._wrap_text(setup_text, setup_font, max_w)
        subject_lines = self._wrap_text(subject_text, subject_font, max_w)

        # Measure heights
        setup_lh = setup_font.getbbox("Ag")[3] - setup_font.getbbox("Ag")[1]
        subject_lh = subject_font.getbbox("Ag")[3] - subject_font.getbbox("Ag")[1]
        gap = 20  # space between setup and subject
        total_h = (
            setup_lh * len(setup_lines)
            + gap
            + subject_lh * len(subject_lines)
        )
        y = y_center - total_h // 2

        # Alpha for each block
        setup_alpha = min(1.0, t / fade_dur) if fade_dur > 0 else 1.0
        subject_alpha = (
            min(1.0, (t - stagger) / fade_dur) if t > stagger and fade_dur > 0 else 0.0
        )

        overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)

        # 3D depth colours
        shadow_3d = (0, 0, 0, 35)       # dark shadow below text
        highlight_3d = (255, 255, 255, 50)  # light highlight above text

        # Draw setup lines (regular weight) with 3D depth
        if setup_alpha > 0:
            a = int(setup_alpha * 255)
            for line in setup_lines:
                bbox = setup_font.getbbox(line)
                tw = bbox[2] - bbox[0]
                x = (self.W - tw) // 2
                # 3D shadow (below & right)
                odraw.text((x + 1, y + 2), line, fill=(*shadow_3d[:3], min(a, shadow_3d[3])), font=setup_font)
                # 3D highlight (above & left)
                odraw.text((x - 1, y - 1), line, fill=(*highlight_3d[:3], min(a, highlight_3d[3])), font=setup_font)
                # Main text
                odraw.text((x, y), line, fill=(*text_color[:3], a), font=setup_font)
                y += setup_lh + 4

        y += gap

        # Draw subject lines (bold weight) with 3D depth
        if subject_alpha > 0:
            a = int(subject_alpha * 255)
            for line in subject_lines:
                bbox = subject_font.getbbox(line)
                tw = bbox[2] - bbox[0]
                x = (self.W - tw) // 2
                # 3D shadow (stronger for bold text)
                odraw.text((x + 2, y + 3), line, fill=(*shadow_3d[:3], min(a, 50)), font=subject_font)
                # 3D highlight
                odraw.text((x - 1, y - 1), line, fill=(*highlight_3d[:3], min(a, highlight_3d[3])), font=subject_font)
                # Main text
                odraw.text((x, y), line, fill=(*text_color[:3], a), font=subject_font)
                y += subject_lh + 4

        comp = Image.alpha_composite(frame.convert("RGBA"), overlay)
        frame.paste(comp.convert("RGB"))

    # ══════════════════════════════════════════════════
    #  DRAWING PRIMITIVES
    # ══════════════════════════════════════════════════

    def _draw_brand_bar(self, draw: ImageDraw.Draw, brand: str):
        """Draw persistent brand bar at top of screen."""
        if not brand:
            return
        font = _get_font(self._brand_size, bold=True)
        color = self.style["text_medium"]
        bbox = font.getbbox(brand)
        tw = bbox[2] - bbox[0]
        x = (self.W - tw) // 2
        y = self._brand_y + self._zone_brand_h // 2 - (bbox[3] - bbox[1]) // 2
        draw.text((x, y), brand, fill=color, font=font)

    def _draw_watermark(self, draw: ImageDraw.Draw, watermark: str):
        """
        Draw anti-crop watermark in two locations:
        1. Right-center: rotated -90°, overlaps content (impossible to crop)
        2. Bottom-center: above platform UI (~120px from bottom)

        Both render semi-transparent so they're subtle but visible.
        """
        if not watermark:
            return

        frame_img = draw._image  # access the underlying PIL Image

        # ── Right-side vertical watermark ──
        side_font = _get_font(14, bold=True)
        side_text = watermark.upper()
        side_bbox = side_font.getbbox(side_text)
        tw = side_bbox[2] - side_bbox[0]
        th = side_bbox[3] - side_bbox[1]

        # Render text on a temporary image, then rotate
        txt_img = Image.new("RGBA", (tw + 20, th + 10), (0, 0, 0, 0))
        txt_draw = ImageDraw.Draw(txt_img)
        # Shadow for readability
        txt_draw.text((11, 6), side_text, fill=(0, 0, 0, 80), font=side_font)
        txt_draw.text((10, 5), side_text, fill=(255, 255, 255, 50), font=side_font)
        rotated = txt_img.rotate(90, expand=True, resample=Image.BICUBIC)

        # Position: right edge, vertically centered
        rx = self.W - rotated.width - int(self.W * 0.02)
        ry = (self.H - rotated.height) // 2
        if frame_img.mode == "RGBA":
            frame_img.alpha_composite(rotated, (rx, ry))
        else:
            frame_img.paste(rotated, (rx, ry), rotated)

        # ── Bottom-center watermark (above platform UI) ──
        bot_font = _get_font(11, bold=True)
        bot_text = watermark.upper()
        bot_bbox = bot_font.getbbox(bot_text)
        btw = bot_bbox[2] - bot_bbox[0]
        bth = bot_bbox[3] - bot_bbox[1]

        bot_img = Image.new("RGBA", (btw + 10, bth + 6), (0, 0, 0, 0))
        bot_draw = ImageDraw.Draw(bot_img)
        bot_draw.text((6, 4), bot_text, fill=(0, 0, 0, 60), font=bot_font)
        bot_draw.text((5, 3), bot_text, fill=(255, 255, 255, 40), font=bot_font)

        bx = (self.W - bot_img.width) // 2
        by = self.H - 120
        if frame_img.mode == "RGBA":
            frame_img.alpha_composite(bot_img, (bx, by))
        else:
            frame_img.paste(bot_img, (bx, by), bot_img)

    def _draw_text_centered(
        self,
        frame: Image.Image,
        draw: ImageDraw.Draw,
        text: str,
        y_center: int,
        font: ImageFont.FreeTypeFont,
        color: tuple,
        alpha: float = 1.0,
        max_width: int = 0,
    ):
        """Draw centered text with 3D depth, optional alpha, and word-wrapping."""
        if not text:
            return
        if alpha <= 0:
            return

        max_w = max_width or int(self.W * 0.85)
        lines = self._wrap_text(text, font, max_w)

        # Calculate total height
        line_heights = []
        for line in lines:
            bbox = font.getbbox(line)
            line_heights.append(bbox[3] - bbox[1])

        spacing = 8
        total_h = sum(line_heights) + spacing * (len(lines) - 1)
        y = y_center - total_h // 2

        # Always use overlay for 3D effect
        overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        a = int(alpha * 255)

        for i, line in enumerate(lines):
            bbox = font.getbbox(line)
            tw = bbox[2] - bbox[0]
            x = (self.W - tw) // 2
            # 3D shadow
            odraw.text((x + 1, y + 2), line, fill=(0, 0, 0, min(a, 30)), font=font)
            # 3D highlight
            odraw.text((x - 1, y - 1), line, fill=(255, 255, 255, min(a, 40)), font=font)
            # Main text
            odraw.text((x, y), line, fill=(*color[:3], a), font=font)
            y += line_heights[i] + spacing

        comp = Image.alpha_composite(frame.convert("RGBA"), overlay)
        frame.paste(comp.convert("RGB"))

    def _draw_narration_text(
        self,
        frame: Image.Image,
        draw: ImageDraw.Draw,
        text: str,
        word_timings: list[WordTiming],
        y_center: int,
        t: float,
        duration: float,
        larger: bool = False,
        text_alpha: float = 1.0,
        x_offset: int = 0,
        text_scale: float = 1.0,
        glow_intensity: float = 0.0,
    ):
        """Unified narration text with karaoke highlighting + Pop & Jiggle animation.

        Words are revealed progressively as the narrator speaks them.
        Each word gets:
          - Entrance: scale bounce (0% → 110% → 100%) over 0.22s
          - Hold: continuous micro-jiggle / vibration
          - Exit: directional blur + horizontal flick off screen
          - Mixed formatting: keywords get accent colour + scale boost
          - Beat-sync pulse: active word throbs on beat
        The currently spoken word gets a prominent highlight pill.
        """
        if not text:
            return

        vfx = self._vfx

        # Use a larger font for text-only scenes (no image competing)
        font_size = self._subject_size if larger else self._karaoke_size
        font = _get_font(font_size, bold=True)
        max_w = int(self.W * 0.85)
        words = text.split()

        if not words:
            return

        # Build word timing mapping
        if word_timings and len(word_timings) >= len(words):
            timings = word_timings[:len(words)]
        else:
            # Estimate even distribution
            per_word = duration / max(len(words), 1)
            timings = [
                WordTiming(word=w, start=i * per_word, end=(i + 1) * per_word)
                for i, w in enumerate(words)
            ]

        # Only show words that have been spoken (start time <= t)
        spoken_words = [(wt.word, wt.start, wt.end) for wt in timings if wt.start <= t]
        if not spoken_words:
            return

        # Wrap spoken words into lines
        space_w = font.getbbox(" ")[2] - font.getbbox(" ")[0]
        line_h = font.getbbox("Ag")[3] - font.getbbox("Ag")[1]
        spacing = 10

        vis_lines: list[list[tuple[str, float, float]]] = [[]]
        vis_w = 0
        for w_tuple in spoken_words:
            word_w = font.getbbox(w_tuple[0])[2] - font.getbbox(w_tuple[0])[0]
            if vis_w + word_w > max_w and vis_lines[-1]:
                vis_lines.append([])
                vis_w = 0
            vis_lines[-1].append(w_tuple)
            vis_w += word_w + space_w

        # Keep only the last 2 visible lines (scroll up naturally)
        max_visible_lines = 2
        if len(vis_lines) > max_visible_lines:
            vis_lines = vis_lines[-max_visible_lines:]

        total_h = line_h * len(vis_lines) + spacing * (len(vis_lines) - 1)
        y = y_center - total_h // 2

        # Karaoke highlight colours from the active visual style
        text_color = self.style["text_dark"]
        highlight_bg_color = self._visual_style_config.get("highlight_color", (255, 136, 0))
        highlight_text_color = self._visual_style_config.get("highlight_text", (255, 255, 255))
        keyword_accent = vfx.keyword_color_accent  # mixed formatting colour
        total_words = len(words)

        overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)

        pill_pad_x = 6
        pill_pad_y = 3
        pill_radius = 8

        # Track word index across lines for keyword detection
        global_word_idx = 0

        for line in vis_lines:
            # Center the line (including pill padding for active words)
            line_width = sum(
                font.getbbox(w)[2] - font.getbbox(w)[0] for w, _, _ in line
            ) + space_w * (len(line) - 1)
            x = (self.W - line_width) // 2 + x_offset

            for word, ws, we in line:
                word_bbox = font.getbbox(word)
                word_w = word_bbox[2] - word_bbox[0]

                is_active = ws <= t < we
                word_age = t - ws  # how long since this word appeared

                # ── Mixed Formatting: keyword detection ──
                kw = (vfx.keyword_highlight_enabled
                      and is_keyword(word, global_word_idx, total_words))
                global_word_idx += 1

                # ── Pop & Jiggle: Entrance bounce scale ──
                bounce_scale = text_bounce_scale(word_age, duration, vfx)
                if bounce_scale <= 0.01:
                    x += word_w + space_w
                    continue

                # ── Beat-sync pulse: subtle throb on active word ──
                if is_active:
                    pulse_s = beat_pulse_scale(t, timings, vfx)
                    bounce_scale *= pulse_s

                # ── Keyword scale boost ──
                if kw and not is_active:
                    bounce_scale *= vfx.keyword_scale_boost

                # ── Pop & Jiggle: Jiggle offset (after entrance settles) ──
                if word_age > vfx.text_bounce_duration:
                    jx, jy, jrot = text_jiggle_offset(word_age, vfx)
                else:
                    jx, jy, jrot = 0.0, 0.0, 0.0

                # ── Pop & Jiggle: Exit flick (near end of screen) ──
                exit_alpha, x_slide, blur_amt = text_exit_progress(t, duration, vfx)

                # Combined position offsets
                draw_x = int(x + jx + x_slide)
                draw_y = int(y + jy)

                # Render word to temporary RGBA image for scale/rotation
                if abs(bounce_scale - 1.0) > 0.02 or abs(jrot) > 0.05:
                    # Create a mini canvas for this word
                    pad = 8
                    wimg = Image.new("RGBA", (word_w + pad * 2, line_h + pad * 2), (0, 0, 0, 0))
                    wdraw = ImageDraw.Draw(wimg)

                    if is_active:
                        # Pill background
                        wdraw.rounded_rectangle(
                            [0, 0, word_w + pad * 2, line_h + pad * 2],
                            radius=pill_radius,
                            fill=(*highlight_bg_color[:3], 230),
                        )
                        wdraw.text((pad, pad), word, fill=(*highlight_text_color[:3], 255), font=font)
                    elif kw:
                        # Keyword: accent colour for mixed formatting
                        wdraw.text((pad, pad), word, fill=(*keyword_accent[:3], 255), font=font)
                    else:
                        wdraw.text((pad, pad), word, fill=(*text_color[:3], 230), font=font)

                    # Apply scale
                    if abs(bounce_scale - 1.0) > 0.02:
                        nw = max(1, int(wimg.width * bounce_scale))
                        nh = max(1, int(wimg.height * bounce_scale))
                        wimg = wimg.resize((nw, nh), Image.LANCZOS)
                        # Adjust position for scale
                        draw_x -= (nw - word_w - pad * 2) // 2
                        draw_y -= (nh - line_h - pad * 2) // 2

                    # Apply rotation (jiggle)
                    if abs(jrot) > 0.05:
                        wimg = wimg.rotate(-jrot, resample=Image.BICUBIC, expand=False)

                    # Apply exit blur
                    if blur_amt > 1.0:
                        wimg = wimg.filter(ImageFilter.GaussianBlur(radius=int(blur_amt)))

                    # Apply exit alpha
                    if exit_alpha < 1.0:
                        r, g, b, a = wimg.split()
                        a_arr = np.array(a, dtype=np.float32) * exit_alpha
                        wimg.putalpha(Image.fromarray(a_arr.astype(np.uint8)))

                    try:
                        overlay.paste(wimg, (draw_x - 8, draw_y - 8), wimg)
                    except (ValueError, Exception):
                        pass
                else:
                    # No scale/rotation needed — draw directly on overlay (fast path)
                    final_a = int(exit_alpha * 255)
                    if is_active:
                        pill_x0 = draw_x - pill_pad_x
                        pill_y0 = draw_y - pill_pad_y
                        pill_x1 = draw_x + word_w + pill_pad_x
                        pill_y1 = draw_y + line_h + pill_pad_y
                        odraw.rounded_rectangle(
                            [pill_x0, pill_y0, pill_x1, pill_y1],
                            radius=pill_radius,
                            fill=(*highlight_bg_color[:3], min(230, final_a)),
                        )
                        odraw.text(
                            (draw_x, draw_y), word,
                            fill=(*highlight_text_color[:3], final_a),
                            font=font,
                        )
                    elif kw:
                        # Keyword: accent colour for mixed formatting
                        odraw.text(
                            (draw_x, draw_y), word,
                            fill=(*keyword_accent[:3], min(255, final_a)),
                            font=font,
                        )
                    else:
                        odraw.text(
                            (draw_x, draw_y), word,
                            fill=(*text_color[:3], min(230, final_a)),
                            font=font,
                        )

                x += word_w + space_w

            y += line_h + spacing

        # Apply text_alpha to the entire overlay if < 1
        if text_alpha < 1.0:
            r_o, g_o, b_o, a_o = overlay.split()
            a_arr = np.array(a_o, dtype=np.float32) * text_alpha
            overlay.putalpha(Image.fromarray(a_arr.astype(np.uint8)))

        # ── VFX: Glow effect behind text ──
        if glow_intensity > 0.05:
            glow_layer = overlay.copy()
            glow_radius = max(3, int(glow_intensity * 20))
            glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=glow_radius))
            # Brighten the glow alpha
            r_g, g_g, b_g, a_g = glow_layer.split()
            a_bright = np.clip(np.array(a_g, dtype=np.float32) * (1.0 + glow_intensity), 0, 255)
            glow_layer.putalpha(Image.fromarray(a_bright.astype(np.uint8)))
            frame_rgba = frame.convert("RGBA")
            frame_rgba = Image.alpha_composite(frame_rgba, glow_layer)
            frame.paste(frame_rgba.convert("RGB"))

        # ── VFX: Scale the text overlay ──
        if abs(text_scale - 1.0) > 0.02:
            ow, oh = overlay.size
            nw = max(1, int(ow * text_scale))
            nh = max(1, int(oh * text_scale))
            scaled = overlay.resize((nw, nh), Image.LANCZOS)
            # Re-center on the frame
            canvas = Image.new("RGBA", overlay.size, (0, 0, 0, 0))
            paste_x = (ow - nw) // 2
            paste_y = (oh - nh) // 2
            canvas.paste(scaled, (paste_x, paste_y), scaled)
            overlay = canvas

        comp = Image.alpha_composite(frame.convert("RGBA"), overlay)
        frame.paste(comp.convert("RGB"))

    def _draw_emphasis_text(
        self,
        frame: Image.Image,
        draw: ImageDraw.Draw,
        text: str,
        emphasis_set: set,
        y_center: int,
        alpha: float,
        t: float,
    ):
        """Draw large animated text for text-only screens with word-by-word reveal.

        Words fade in sequentially (staggered). Emphasis words pulse with a subtle
        scale animation and use a bolder font + slight colour accent for visual pop.
        All text gets a soft shadow for depth.
        """
        if not text:
            return

        words = text.split()
        if not words:
            return

        font_normal = _get_font(self._emphasis_size, bold=True)
        font_emphasis = _get_font(self._emphasis_size + 14, bold=True)

        # Colors
        text_color = self.style.get("text_dark", (61, 61, 61))
        emphasis_color = self.style.get("secondary", (200, 130, 160))
        shadow_color = (0, 0, 0, 40)
        max_w = int(self.W * 0.80)

        # Per-word stagger timing: each word fades in after 0.12s delay
        word_stagger = 0.12
        word_fade_dur = 0.25

        overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)

        space_w = font_normal.getbbox(" ")[2]

        # Word wrap with mixed sizes
        lines: list[list[tuple[str, bool, int]]] = [[]]  # (word, is_emphasis, word_index)
        current_w = 0
        for i, w in enumerate(words):
            is_emp = w.lower().strip(".,!?;:\"'") in emphasis_set
            f = font_emphasis if is_emp else font_normal
            ww = f.getbbox(w)[2] - f.getbbox(w)[0]
            if current_w + ww > max_w and lines[-1]:
                lines.append([])
                current_w = 0
            lines[-1].append((w, is_emp, i))
            current_w += ww + space_w

        # Layout
        line_h = font_emphasis.getbbox("Ag")[3] - font_emphasis.getbbox("Ag")[1]
        spacing = 14
        total_h = line_h * len(lines) + spacing * (len(lines) - 1)
        y = y_center - total_h // 2

        for line in lines:
            # Calculate line width for centering
            lw = 0
            for w, is_emp, _ in line:
                f = font_emphasis if is_emp else font_normal
                lw += f.getbbox(w)[2] - f.getbbox(w)[0] + space_w
            lw -= space_w
            x = (self.W - lw) // 2

            for w, is_emp, word_idx in line:
                f = font_emphasis if is_emp else font_normal

                # Per-word fade-in based on staggered timing
                word_appear = word_idx * word_stagger
                if t < word_appear:
                    word_alpha = 0.0
                elif t < word_appear + word_fade_dur:
                    word_alpha = (t - word_appear) / word_fade_dur
                else:
                    word_alpha = 1.0

                word_alpha *= alpha  # overall scene alpha
                a = int(word_alpha * 255)

                if a > 0:
                    ww = f.getbbox(w)[2] - f.getbbox(w)[0]

                    # Emphasis words: pulse scale + accent colour
                    if is_emp and word_alpha >= 1.0:
                        # Subtle pulse: scale oscillates between 1.0 and 1.06
                        pulse = 1.0 + 0.06 * abs(math.sin(t * 2.5))
                        # Draw at slightly larger scale using a bigger temp canvas
                        pulse_font = _get_font(int((self._emphasis_size + 14) * pulse), bold=True)
                        pw = pulse_font.getbbox(w)[2] - pulse_font.getbbox(w)[0]
                        px = x + (ww - pw) // 2  # centre the pulsed word
                        # Shadow
                        odraw.text((px + 2, y + 3), w, fill=shadow_color, font=pulse_font)
                        # Accent colour for emphasis words
                        odraw.text((px, y), w, fill=(*emphasis_color[:3], a), font=pulse_font)
                    else:
                        # Shadow
                        odraw.text((x + 2, y + 2), w, fill=(*shadow_color[:3], min(a, 40)), font=f)
                        # Normal text
                        odraw.text((x, y), w, fill=(*text_color[:3], a), font=f)

                    x += ww + space_w
                else:
                    ww = f.getbbox(w)[2] - f.getbbox(w)[0]
                    x += ww + space_w

            y += line_h + spacing

        comp = Image.alpha_composite(frame.convert("RGBA"), overlay)
        frame.paste(comp.convert("RGB"))

    # ══════════════════════════════════════════════════
    #  IMAGE PROCESSING
    # ══════════════════════════════════════════════════

    def _prepare_clay_image(
        self, path: Path, max_ratio: float = 0.0,
    ) -> Image.Image:
        """Load and prepare an AI image with claymorphism styling.

        Adds generous rounded corners + chubby clay border (soft, puffy 3D feel).
        Images sized to 1.2x content zone.
        """
        img = Image.open(path).convert("RGBA")

        # Scale to fit content zone
        ratio = max_ratio or self.style["image_max_ratio"]
        max_w = int(self.W * ratio)
        max_h = int(self._zone_content_h * 1.2) if not max_ratio else int(self._zone_content_h * ratio)
        img.thumbnail((max_w, max_h), Image.LANCZOS)

        # Generous rounded corners (bigger radius for a soft clay feel)
        corner_r = self.style.get("image_corner_radius", 32)
        img = self._add_rounded_corners(img, corner_r)

        # Chubby claymorphism border (replaces old stroke + shadow)
        img = self._add_clay_border(img, corner_r)

        return img

    def _add_rounded_corners(
        self, img: Image.Image, radius: int
    ) -> Image.Image:
        """Add rounded corners to an image."""
        mask = Image.new("L", img.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle(
            [0, 0, img.width - 1, img.height - 1],
            radius=radius,
            fill=255,
        )
        result = img.copy()
        result.putalpha(mask)
        return result

    def _add_clay_border(
        self, img: Image.Image, corner_r: int
    ) -> Image.Image:
        """Add a chubby claymorphism border — soft, puffy, 3D clay frame.

        Creates the illusion of an image pressed into soft clay / placed on a
        table.  Multiple concentric soft layers give depth:
          1. Outer soft shadow (the "table" shadow)
          2. Thick clay-coloured border with soft inner highlight
          3. Subtle inner shadow (image recessed into frame)
        """
        border_w = 12           # thick clay border
        outer_glow = 10         # soft spread behind the border
        inner_shadow = 4        # recessed inner edge
        pad = border_w + outer_glow + 6

        canvas_w = img.width + pad * 2
        canvas_h = img.height + pad * 2
        canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

        # ── 1. Outer soft shadow (depth on the background) ──
        shadow = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.rounded_rectangle(
            [pad - border_w, pad - border_w,
             pad + img.width + border_w - 1, pad + img.height + border_w - 1],
            radius=corner_r + border_w,
            fill=(0, 0, 0, 50),
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=outer_glow))
        canvas = Image.alpha_composite(canvas, shadow)

        # ── 2. Clay border (thick, warm, slightly lighter at top) ──
        border_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        bd = ImageDraw.Draw(border_layer)
        # Main border fill — warm off-white / light clay
        bd.rounded_rectangle(
            [pad - border_w, pad - border_w,
             pad + img.width + border_w - 1, pad + img.height + border_w - 1],
            radius=corner_r + border_w,
            fill=(245, 240, 235, 255),   # warm clay base
        )
        canvas = Image.alpha_composite(canvas, border_layer)

        # Top-edge highlight (makes it look puffy / lit from above)
        highlight = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        hd = ImageDraw.Draw(highlight)
        hd.rounded_rectangle(
            [pad - border_w + 2, pad - border_w + 1,
             pad + img.width + border_w - 3, pad + img.height + border_w // 2],
            radius=corner_r + border_w - 2,
            fill=(255, 255, 255, 60),   # soft white highlight
        )
        highlight = highlight.filter(ImageFilter.GaussianBlur(radius=5))
        canvas = Image.alpha_composite(canvas, highlight)

        # Bottom-edge soft shadow (clay curvature)
        bot_shadow = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        bsd = ImageDraw.Draw(bot_shadow)
        bsd.rounded_rectangle(
            [pad - border_w + 2, pad + img.height - border_w // 2,
             pad + img.width + border_w - 3, pad + img.height + border_w - 1],
            radius=corner_r + border_w - 2,
            fill=(0, 0, 0, 35),          # soft dark at bottom
        )
        bot_shadow = bot_shadow.filter(ImageFilter.GaussianBlur(radius=4))
        canvas = Image.alpha_composite(canvas, bot_shadow)

        # ── 3. Inner recess shadow (image sits INTO the clay) ──
        inset = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        ind = ImageDraw.Draw(inset)
        # Dark ring just inside the image area
        ind.rounded_rectangle(
            [pad - inner_shadow, pad - inner_shadow,
             pad + img.width + inner_shadow - 1, pad + img.height + inner_shadow - 1],
            radius=corner_r + inner_shadow,
            fill=(0, 0, 0, 30),
        )
        # Cut out the inner area so only the ring remains
        ind.rounded_rectangle(
            [pad + 1, pad + 1,
             pad + img.width - 2, pad + img.height - 2],
            radius=max(1, corner_r - 1),
            fill=(0, 0, 0, 0),
        )
        inset = inset.filter(ImageFilter.GaussianBlur(radius=3))
        canvas = Image.alpha_composite(canvas, inset)

        # ── 4. Paste original image on top ──
        canvas.paste(img, (pad, pad), img)

        return canvas

    def _create_shadow(self, size: tuple[int, int]) -> Image.Image:
        """Create a deep, soft shadow — claymorphism grade (objects float above surface)."""
        shadow_color = self.style.get("image_shadow_color", (80, 80, 80))
        opacity = self.style.get("image_shadow_opacity", 0.38)
        blur_r = self.style.get("image_shadow_blur", 42)
        rgba = (*shadow_color, int(255 * opacity))
        shadow = Image.new("RGBA", size, rgba)
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=blur_r))
        return shadow

    def _draw_clay_image(
        self,
        frame: Image.Image,
        clay_img: Image.Image,
        y_center: int,
        x_center: int = 0,
        alpha: float = 1.0,
        scale: float = 1.0,
        t: float = 0.0,
        image_index: int = 0,
        appear_time: float = 0.0,
        screen_duration: float = 3.0,
        word_timings: list = None,
    ):
        """Paste a clay-styled image onto the frame.

        Combines:
          - Elastic entrance pop (overshoot → settle)
        Clean and stable — no wiggle, float, or parallax.
        """
        if alpha <= 0:
            return

        vfx = self._vfx
        img = clay_img

        # Elastic entrance scale (overrides basic linear scale)
        entrance_s = image_entrance_scale(t, appear_time, vfx)
        if entrance_s <= 0.01:
            return

        effective_scale = scale * entrance_s

        if abs(effective_scale - 1.0) > 0.01:
            new_w = max(1, int(img.width * effective_scale))
            new_h = max(1, int(img.height * effective_scale))
            img = img.resize((new_w, new_h), Image.LANCZOS)

        cx = x_center or self.W // 2
        x = cx - img.width // 2
        y = y_center - img.height // 2

        if alpha < 1.0:
            a_channel = img.split()[3] if img.mode == "RGBA" else None
            if a_channel:
                a_arr = np.array(a_channel, dtype=np.float32)
                a_arr *= alpha
                new_a = Image.fromarray(a_arr.astype(np.uint8))
                img = img.copy()
                img.putalpha(new_a)

        frame_rgba = frame.convert("RGBA")
        try:
            frame_rgba.paste(img, (x, y), img)
        except (ValueError, Exception):
            pass
        frame.paste(frame_rgba.convert("RGB"))

    # ══════════════════════════════════════════════════
    #  TRANSITIONS (VFX Engine — whip pan, mask wipe, z-zoom, pop)
    # ══════════════════════════════════════════════════

    # Transition sequence cycles through the VFX engine types
    _TRANSITION_TYPES = TRANSITION_SEQUENCE

    def _add_transitions(self, scenes: list[VideoClip]) -> list[VideoClip]:
        """Add varied transitions between scenes.

        Uses VFX agent scene_transition choices when available,
        falls back to legacy VFX engine rotation otherwise.
        """
        fade = self.style["fade_duration"]
        result = []

        for i, scene in enumerate(scenes):
            # Prefer VFX agent's transition choice for this scene
            scene_fx = self._effects_map.get(i)
            if scene_fx and scene_fx.scene_transition:
                trans_type = self._map_agent_transition(scene_fx.scene_transition)
            else:
                trans_type = get_transition_for_scene(i)

            if i > 0:
                scene = self._apply_transition_in(scene, trans_type, fade)
            if i < len(scenes) - 1:
                scene = self._apply_transition_out(scene, trans_type, fade)
            result.append(scene)
        return result

    @staticmethod
    def _map_agent_transition(agent_trans: str) -> str:
        """Map VFX agent transition names to legacy VFX engine names."""
        mapping = {
            "crossfade": "fade",
            "flash_transition": "flash",
            "blur_transition": "z_zoom",
            "slide_horizontal": "whip_horizontal",
            "slide_vertical": "whip_vertical",
            "wipe_left": "mask_circle",
            "wipe_right": "mask_circle",
            "circle_wipe": "mask_circle",
            "diamond_wipe": "mask_diamond",
            "pixelate_transition": "glitch",
            "glitch_transition": "glitch",
            "ink_bleed": "mask_circle",
            "zoom_in_transition": "z_zoom",
            "zoom_out_transition": "z_zoom",
            "spin_transition": "pop",
        }
        # Direct mapping or fall back to the agent name itself
        # (some agent names like 'whip_horizontal' already match)
        return mapping.get(agent_trans, agent_trans)

    def _apply_transition_in(
        self, clip: VideoClip, trans_type: str, duration: float
    ) -> VideoClip:
        """Apply an entry transition using the VFX engine."""
        W, H = self.W, self.H
        vfx_cfg = self._vfx

        if trans_type.startswith("whip_"):
            direction = "vertical" if "vertical" in trans_type else "horizontal"
            def whip_in(get_frame, t):
                frame = get_frame(t)
                if t < duration:
                    progress = t / duration
                    # Create a black frame for incoming transition
                    black = np.zeros_like(frame)
                    return whip_pan_transition(black, frame, progress, direction, vfx_cfg)
                return frame
            return clip.transform(whip_in)

        elif trans_type.startswith("mask_"):
            shape = trans_type.split("_")[1] if "_" in trans_type else "circle"
            def mask_in(get_frame, t):
                frame = get_frame(t)
                if t < duration:
                    progress = t / duration
                    # Mask reveals the new scene
                    black = np.zeros_like(frame)
                    return mask_wipe_transition(black, frame, 0.5 + progress * 0.5, shape, vfx_cfg)
                return frame
            return clip.transform(mask_in)

        elif trans_type == "z_zoom":
            def z_in(get_frame, t):
                frame = get_frame(t)
                if t < duration:
                    progress = t / duration
                    p = ease_out_cubic(progress)
                    scale = vfx_cfg.z_zoom_max_scale - (vfx_cfg.z_zoom_max_scale - 1.0) * p
                    pil = Image.fromarray(frame)
                    new_w = int(W * scale)
                    new_h = int(H * scale)
                    pil = pil.resize((new_w, new_h), Image.LANCZOS)
                    left = (new_w - W) // 2
                    top = (new_h - H) // 2
                    pil = pil.crop((left, top, left + W, top + H))
                    result = np.array(pil)
                    alpha = min(1.0, progress / 0.3)
                    result = (result * alpha).astype(np.uint8)
                    return result
                return frame
            return clip.transform(z_in)

        elif trans_type == "glitch":
            def glitch_in(get_frame, t):
                frame = get_frame(t)
                if t < duration:
                    progress = t / duration
                    black = np.zeros_like(frame)
                    return glitch_wipe_transition(black, frame, progress, vfx_cfg)
                return frame
            return clip.transform(glitch_in)

        elif trans_type == "pop":
            def pop_in(get_frame, t):
                frame = get_frame(t)
                if t < duration:
                    progress = t / duration
                    # Elastic overshoot
                    p = ease_out_back(progress)
                    scale = 0.7 + 0.3 * p
                    pil = Image.fromarray(frame)
                    new_w = int(W * scale)
                    new_h = int(H * scale)
                    pil = pil.resize((new_w, new_h), Image.LANCZOS)
                    left = (new_w - W) // 2
                    top = (new_h - H) // 2
                    pil = pil.crop((max(0, left), max(0, top), max(0, left) + W, max(0, top) + H))
                    if pil.size != (W, H):
                        pil = pil.resize((W, H), Image.LANCZOS)
                    result = np.array(pil)
                    alpha = min(1.0, progress / 0.3)
                    result = (result * alpha).astype(np.uint8)
                    return result
                return frame
            return clip.transform(pop_in)

        else:  # fade (default)
            return clip.with_effects([vfx.CrossFadeIn(duration)])

    def _apply_transition_out(
        self, clip: VideoClip, trans_type: str, duration: float
    ) -> VideoClip:
        """Apply an exit transition using the VFX engine."""
        clip_dur = clip.duration
        W, H = self.W, self.H
        vfx_cfg = self._vfx

        if trans_type.startswith("whip_"):
            direction = "vertical" if "vertical" in trans_type else "horizontal"
            def whip_out(get_frame, t):
                frame = get_frame(t)
                remaining = clip_dur - t
                if remaining < duration:
                    progress = 1 - remaining / duration
                    black = np.zeros_like(frame)
                    return whip_pan_transition(frame, black, progress, direction, vfx_cfg)
                return frame
            return clip.transform(whip_out)

        elif trans_type.startswith("mask_"):
            shape = trans_type.split("_")[1] if "_" in trans_type else "circle"
            def mask_out(get_frame, t):
                frame = get_frame(t)
                remaining = clip_dur - t
                if remaining < duration:
                    progress = 1 - remaining / duration
                    black = np.zeros_like(frame)
                    return mask_wipe_transition(frame, black, progress * 0.5, shape, vfx_cfg)
                return frame
            return clip.transform(mask_out)

        elif trans_type == "z_zoom":
            def z_out(get_frame, t):
                frame = get_frame(t)
                remaining = clip_dur - t
                if remaining < duration:
                    progress = 1 - remaining / duration
                    p = progress ** 2
                    scale = 1.0 + (vfx_cfg.z_zoom_max_scale - 1.0) * p
                    pil = Image.fromarray(frame)
                    new_w = int(W * scale)
                    new_h = int(H * scale)
                    pil = pil.resize((new_w, new_h), Image.LANCZOS)
                    left = (new_w - W) // 2
                    top = (new_h - H) // 2
                    pil = pil.crop((left, top, left + W, top + H))
                    result = np.array(pil)
                    alpha = 1 - p
                    result = (result * alpha).astype(np.uint8)
                    return result
                return frame
            return clip.transform(z_out)

        elif trans_type == "glitch":
            def glitch_out(get_frame, t):
                frame = get_frame(t)
                remaining = clip_dur - t
                if remaining < duration:
                    progress = 1 - remaining / duration
                    black = np.zeros_like(frame)
                    return glitch_wipe_transition(frame, black, progress, vfx_cfg)
                return frame
            return clip.transform(glitch_out)

        elif trans_type == "pop":
            def pop_out(get_frame, t):
                frame = get_frame(t)
                remaining = clip_dur - t
                if remaining < duration:
                    progress = 1 - remaining / duration
                    alpha = 1 - progress ** 2
                    result = (frame * alpha).astype(np.uint8)
                    return result
                return frame
            return clip.transform(pop_out)

        else:  # fade
            existing = []
            if hasattr(clip, 'effects') and clip.effects:
                existing = list(clip.effects)
            return clip.with_effects([*existing, vfx.CrossFadeOut(duration)])

    # ══════════════════════════════════════════════════
    #  UTILITIES
    # ══════════════════════════════════════════════════

    def _safe_text(self, text: str) -> str:
        """Enforce Universal Style Guide §9 text rules.

        - Convert ALL CAPS → Title Case (never ALL CAPS per guide)
        - Strip leading/trailing whitespace
        """
        if not text:
            return text
        text = text.strip()
        if self.style.get("prevent_all_caps", True) and text == text.upper() and len(text) > 2:
            text = text.title()
        return text

    def _wrap_text(
        self, text: str, font: ImageFont.FreeTypeFont, max_width: int
    ) -> list[str]:
        """Word-wrap text to fit within max_width, enforcing max line limit."""
        words = text.split()
        lines = []
        current_line = ""
        max_lines = self.style.get("max_text_lines", 3)

        for word in words:
            test = f"{current_line} {word}".strip()
            bbox = font.getbbox(test)
            if bbox[2] - bbox[0] <= max_width:
                current_line = test
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        # Enforce max lines — truncate with ellipsis if needed (guide §9)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            if lines[-1] and not lines[-1].endswith("…"):
                words_last = lines[-1].split()
                if len(words_last) > 1:
                    lines[-1] = " ".join(words_last[:-1]) + "…"
                else:
                    lines[-1] = words_last[0] + "…"

        return lines or [""]

    def _apply_color_grade(
        self, clip: VideoClip, grade: str
    ) -> VideoClip:
        """Apply color grading to the final video."""
        grade_config = config.COLOR_GRADES.get(grade)
        if not grade_config or grade == "none":
            return clip

        brightness = grade_config["brightness"]
        contrast = grade_config["contrast"]
        saturation = grade_config["saturation"]

        def grade_frame(get_frame, t):
            frame = get_frame(t)
            from PIL import ImageEnhance
            pil = Image.fromarray(frame)
            if brightness != 1.0:
                pil = ImageEnhance.Brightness(pil).enhance(brightness)
            if contrast != 1.0:
                pil = ImageEnhance.Contrast(pil).enhance(contrast)
            if saturation != 1.0:
                pil = ImageEnhance.Color(pil).enhance(saturation)
            return np.array(pil)

        return clip.transform(grade_frame)

    def _write_srt(self, entries: list[dict], path: Path):
        """Write SRT subtitle file."""
        def fmt(seconds: float) -> str:
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            ms = int((seconds % 1) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        with open(path, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(f"{e['index']}\n")
                f.write(f"{fmt(e['start'])} --> {fmt(e['end'])}\n")
                f.write(f"{e['text']}\n\n")

        logger.info("SRT saved: %s (%d entries)", path, len(entries))

    def _generate_thumbnail(
        self,
        screenplay: StoryScreenplay,
        images: list[AIImageAsset],
        brand: str,
        watermark: str,
        bg: Image.Image,
        path: Path,
    ):
        """Generate a compelling thumbnail that covers the entire story.

        Layout: large hero image filling most of the frame, with a gradient
        overlay at the bottom carrying the title in bold text. Brand bar at top.
        This gives viewers an immediate sense of the video content.
        """
        thumb = bg.copy()
        draw = ImageDraw.Draw(thumb)

        # Hero image — use the first (most relevant) image, drawn large
        if images:
            try:
                hero = self._prepare_clay_image(images[0].local_path, max_ratio=0.90)
                self._draw_clay_image(
                    thumb, hero,
                    y_center=int(self.H * 0.42),  # slightly above centre
                )
            except Exception:
                pass

        # Bottom gradient overlay for text legibility
        gradient = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        g_draw = ImageDraw.Draw(gradient)
        for row in range(int(self.H * 0.55), self.H):
            progress = (row - int(self.H * 0.55)) / (self.H * 0.45)
            alpha = int(180 * progress ** 1.5)
            g_draw.line([(0, row), (self.W, row)], fill=(30, 30, 30, min(alpha, 200)))
        thumb_rgba = Image.alpha_composite(thumb.convert("RGBA"), gradient)
        thumb = thumb_rgba.convert("RGB")
        draw = ImageDraw.Draw(thumb)

        # Brand bar
        self._draw_brand_bar(draw, brand)

        # Title — large bold white text over the gradient
        title_font = _get_font(self._title_size + 12, bold=True)
        title_text = self._safe_text(screenplay.title)
        lines = self._wrap_text(title_text, title_font, int(self.W * 0.85))
        lh = title_font.getbbox("Ag")[3] - title_font.getbbox("Ag")[1]
        title_y = int(self.H * 0.74)
        for line in lines:
            bbox = title_font.getbbox(line)
            tw = bbox[2] - bbox[0]
            x = (self.W - tw) // 2
            # Text shadow
            draw.text((x + 2, title_y + 2), line, fill=(0, 0, 0), font=title_font)
            draw.text((x, title_y), line, fill=(255, 255, 255), font=title_font)
            title_y += lh + 8

        # Hook text (smaller, below title)
        if screenplay.hook:
            hook_font = _get_font(self._body_size + 4, bold=False)
            hook_text = self._safe_text(screenplay.hook)
            hlines = self._wrap_text(hook_text, hook_font, int(self.W * 0.80))
            hlh = hook_font.getbbox("Ag")[3] - hook_font.getbbox("Ag")[1]
            for hl in hlines[:2]:
                bbox = hook_font.getbbox(hl)
                tw = bbox[2] - bbox[0]
                x = (self.W - tw) // 2
                draw.text((x, title_y), hl, fill=(220, 220, 220), font=hook_font)
                title_y += hlh + 4

        # Watermark
        self._draw_watermark(draw, watermark)

        thumb.save(path, "JPEG", quality=92)
        logger.info("Thumbnail saved: %s", path)
