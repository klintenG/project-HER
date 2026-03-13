"""
Project HER v2.0 – Visual Effects Engine
Advanced motion effects for stunning short-form videos.

Effects:
  1. Text Animation: Pop entrance, word-sync, mixed formatting (keywords)
  2. Image Motion: Paper Cutout (stroke, stagger, wiggle) + 2.5D Parallax
  3. Transitions: Whip Pan, Z-Axis Zoom, Glitch Wipe, Pop
  4. Overlays: Paper Texture, Light Leaks/Film Burns, Smart Flash
  5. Rhythm: Beat-sync pulse, 1-second rule pacing, ease-in/ease-out
"""

from __future__ import annotations

import math
import random
import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger("vfx_engine")


# ══════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════

@dataclass
class VFXConfig:
    """All visual effects parameters — tweak these to change the feel."""

    # ── Text Animation: "Pop & Jiggle" ──
    text_bounce_duration: float = 0.22         # seconds for scale 0→110→100%
    text_overshoot: float = 1.10               # peak scale before settling
    text_settle: float = 1.0                   # final resting scale
    text_jiggle_amplitude: float = 0.0         # disabled — vibration not suitable for text
    text_jiggle_freq: float = 12.0             # cycles per second (unused when amplitude=0)
    text_jiggle_rotation: float = 0.0          # disabled — no rotation jitter on text
    text_exit_duration: float = 0.18           # seconds for flick-off exit
    text_exit_blur_strength: int = 12          # directional blur pixels on exit
    text_exit_slide_px: int = 80               # horizontal slide on exit

    # ── Image Motion: "Paper Cutout" ──
    image_stroke_width: int = 3                # clean white outline
    image_stroke_color: tuple = (255, 255, 255, 240)
    image_shadow_offset: tuple = (4, 6)        # drop shadow x, y — consistent direction
    image_shadow_blur: int = 14                # crisp shadow (was 18)
    image_shadow_opacity: int = 70             # subtle, not heavy (was 90)
    image_stagger_delay: float = 0.12          # seconds between multi-image reveals
    image_wiggle_rotation: float = 1.5         # degrees of idle rotation
    image_wiggle_freq: float = 0.8             # cycles per second
    image_wiggle_translate: float = 3.0        # pixels of position wiggle
    image_entrance_duration: float = 0.25      # pop-in time
    image_entrance_overshoot: float = 1.08     # scale overshoot

    # ── Transitions ──
    whip_pan_duration: float = 0.30            # seconds for whip pan
    whip_pan_blur: int = 40                    # motion blur strength
    mask_wipe_duration: float = 0.35           # seconds for mask wipe
    mask_wipe_shape: str = "circle"            # "circle" | "diamond" | "square"
    z_zoom_duration: float = 0.40              # seconds for z-axis zoom
    z_zoom_max_scale: float = 3.0              # how far we zoom in
    glitch_duration: float = 0.12              # 0.1s digital distortion
    glitch_rgb_offset: int = 12                # pixel offset for RGB split
    glitch_noise_opacity: float = 0.25         # scanline / noise intensity
    glitch_color_shift: bool = True            # enable RGB channel separation

    # ── Overlays ──
    paper_texture_opacity: float = 0.05        # grain overlay (5% per friend spec)
    paper_texture_grain_size: int = 2          # upscale factor for grain
    flash_frame_opacity: float = 0.35          # warm flash on reveal moments only
    flash_frame_duration_frames: int = 2       # how many frames the flash lasts
    flash_on_reveals_only: bool = True         # only flash on first word of screen
    light_leak_opacity: float = 0.15           # warm light leak on edges
    light_leak_warmth: tuple = (255, 180, 80)  # warm orange-gold colour
    light_leak_duration: float = 0.5           # how long the leak persists during transitions

    # ── 2.5D Parallax (depth for static images) ──
    parallax_enabled: bool = True              # add Ken Burns-style motion to images
    parallax_zoom_range: float = 0.06          # max zoom delta (6% — subtle)
    parallax_pan_range: float = 0.03           # max horizontal pan (3% of width)
    parallax_speed: float = 0.15               # how fast the pan/zoom moves per second

    # ── Beat-Sync Pulse ──
    beat_pulse_enabled: bool = True            # 5% scale throb on word beats
    beat_pulse_scale: float = 0.05             # 5% scale-up on beat
    beat_pulse_decay: float = 0.15             # seconds for pulse to decay back

    # ── Mixed Formatting (Key Keywords) ──
    keyword_highlight_enabled: bool = True     # style nouns/verbs differently
    keyword_color_accent: tuple = (255, 136, 0)  # accent colour for keywords
    keyword_scale_boost: float = 1.08          # 8% larger for keywords

    # ── Timeline Pacing (1-Second Rule) ──
    min_change_interval: float = 0.8           # something changes every 0.8s
    max_change_interval: float = 1.2           # max 1.2s between visual changes
    target_images_per_50s: int = 12            # density guideline


# Global default config
VFX_DEFAULTS = VFXConfig()


# ══════════════════════════════════════════════════════
#  EASING FUNCTIONS
# ══════════════════════════════════════════════════════

def ease_out_back(t: float, overshoot: float = 1.70158) -> float:
    """Ease-out with overshoot — bouncy settle."""
    t = max(0.0, min(1.0, t))
    return 1 + (overshoot + 1) * (t - 1) ** 3 + overshoot * (t - 1) ** 2


def ease_out_elastic(t: float) -> float:
    """Elastic ease-out — springy entrance."""
    if t <= 0:
        return 0.0
    if t >= 1:
        return 1.0
    p = 0.3
    return math.pow(2, -10 * t) * math.sin((t - p / 4) * (2 * math.pi) / p) + 1


def ease_in_cubic(t: float) -> float:
    """Ease-in cubic — accelerating exit."""
    return max(0.0, min(1.0, t)) ** 3


def ease_out_cubic(t: float) -> float:
    """Ease-out cubic — decelerating entrance."""
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def ease_in_out_sine(t: float) -> float:
    """Smooth sine ease — natural motion."""
    t = max(0.0, min(1.0, t))
    return -(math.cos(math.pi * t) - 1) / 2


# ══════════════════════════════════════════════════════
#  1. TEXT ANIMATION: "POP & JIGGLE"
# ══════════════════════════════════════════════════════

def text_bounce_scale(t: float, duration: float, cfg: VFXConfig = VFX_DEFAULTS) -> float:
    """
    Scale factor for text entrance: 0% → overshoot → 100%.
    Returns scale multiplier at time t.
    """
    bounce_dur = cfg.text_bounce_duration
    if t < 0:
        return 0.0
    if t >= bounce_dur:
        return cfg.text_settle

    progress = t / bounce_dur
    # Phase 1 (0→70%): scale from 0 to overshoot
    if progress < 0.7:
        p = progress / 0.7
        return cfg.text_overshoot * ease_out_cubic(p)
    # Phase 2 (70→100%): settle from overshoot to 1.0
    else:
        p = (progress - 0.7) / 0.3
        return cfg.text_overshoot - (cfg.text_overshoot - cfg.text_settle) * ease_in_out_sine(p)


def text_jiggle_offset(t: float, cfg: VFXConfig = VFX_DEFAULTS) -> tuple[float, float, float]:
    """
    Returns (dx, dy, rotation_degrees) for the continuous jiggle/vibrate effect.
    Mimics hand-drawn or Turbulent Displace look.
    """
    freq = cfg.text_jiggle_freq
    amp = cfg.text_jiggle_amplitude
    rot_amp = cfg.text_jiggle_rotation

    # Use multiple frequencies for organic feel (not a clean sine)
    dx = amp * (
        0.6 * math.sin(2 * math.pi * freq * t)
        + 0.3 * math.sin(2 * math.pi * freq * 1.7 * t + 0.5)
        + 0.1 * math.sin(2 * math.pi * freq * 3.1 * t + 1.2)
    )
    dy = amp * (
        0.5 * math.sin(2 * math.pi * freq * t + 1.0)
        + 0.3 * math.sin(2 * math.pi * freq * 2.3 * t + 0.8)
        + 0.2 * math.sin(2 * math.pi * freq * 0.7 * t + 2.1)
    )
    rot = rot_amp * math.sin(2 * math.pi * freq * 0.5 * t + 0.3)

    return dx, dy, rot


def text_exit_progress(
    t: float, screen_duration: float, cfg: VFXConfig = VFX_DEFAULTS
) -> tuple[float, float, float]:
    """
    Returns (alpha, x_offset, blur_amount) for the flick-off exit.
    Active only in the last `text_exit_duration` seconds of the screen.
    """
    exit_start = screen_duration - cfg.text_exit_duration
    if t < exit_start:
        return 1.0, 0.0, 0.0

    progress = (t - exit_start) / cfg.text_exit_duration
    progress = min(1.0, progress)
    p = ease_in_cubic(progress)

    alpha = 1.0 - p
    x_offset = cfg.text_exit_slide_px * p
    blur = cfg.text_exit_blur_strength * p

    return alpha, x_offset, blur


def apply_text_animation(
    overlay: Image.Image,
    text_img: Image.Image,
    x: int,
    y: int,
    t: float,
    screen_duration: float,
    cfg: VFXConfig = VFX_DEFAULTS,
) -> None:
    """
    Composite a text image onto the overlay with full Pop & Jiggle animation.
    - Entrance: scale bounce (0→110→100%)
    - Hold: continuous jiggle/vibrate
    - Exit: directional blur + horizontal flick
    """
    # Entrance scale
    scale = text_bounce_scale(t, screen_duration, cfg)
    if scale <= 0.01:
        return

    # Jiggle offset (active after entrance settles)
    if t > cfg.text_bounce_duration:
        dx, dy, rot = text_jiggle_offset(t, cfg)
    else:
        dx, dy, rot = 0.0, 0.0, 0.0

    # Exit values
    alpha, x_slide, blur_amount = text_exit_progress(t, screen_duration, cfg)
    if alpha <= 0.01:
        return

    # Apply transforms
    w, h = text_img.size
    if abs(scale - 1.0) > 0.02:
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        text_img = text_img.resize((new_w, new_h), Image.LANCZOS)
        # Re-center after scale
        x = x - (new_w - w) // 2
        y = y - (new_h - h) // 2
        w, h = new_w, new_h

    # Rotation (jiggle)
    if abs(rot) > 0.05:
        text_img = text_img.rotate(-rot, resample=Image.BICUBIC, expand=False)

    # Position offsets (jiggle + exit slide)
    final_x = int(x + dx + x_slide)
    final_y = int(y + dy)

    # Exit blur
    if blur_amount > 1.0:
        # Horizontal motion blur via box blur in X direction
        blur_kernel = max(1, int(blur_amount))
        text_img = text_img.filter(ImageFilter.GaussianBlur(radius=blur_kernel))

    # Alpha
    if alpha < 1.0:
        if text_img.mode == "RGBA":
            r, g, b, a = text_img.split()
            a_arr = np.array(a, dtype=np.float32) * alpha
            text_img.putalpha(Image.fromarray(a_arr.astype(np.uint8)))
        else:
            text_img.putalpha(int(255 * alpha))

    # Paste onto overlay
    try:
        overlay.paste(text_img, (final_x, final_y), text_img)
    except (ValueError, Exception):
        pass  # Out of bounds — skip gracefully


# ══════════════════════════════════════════════════════
#  2. IMAGE MOTION: "PAPER CUTOUT"
# ══════════════════════════════════════════════════════

def add_cutout_stroke(
    img: Image.Image, cfg: VFXConfig = VFX_DEFAULTS
) -> Image.Image:
    """
    Add a white stroke outline around the image — scrapbook separation effect.
    Also adds a soft drop shadow for depth.
    """
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    stroke_w = cfg.image_stroke_width
    sx, sy = cfg.image_shadow_offset
    shadow_blur = cfg.image_shadow_blur

    # New canvas with room for stroke + shadow
    pad = stroke_w + max(abs(sx), abs(sy)) + shadow_blur
    new_w = img.width + pad * 2
    new_h = img.height + pad * 2
    canvas = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))

    # Drop shadow
    shadow = Image.new("RGBA", img.size, (0, 0, 0, cfg.image_shadow_opacity))
    # Use the image alpha as mask for the shadow shape
    if img.mode == "RGBA":
        shadow.putalpha(img.split()[3])
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=shadow_blur))
    canvas.paste(shadow, (pad + sx, pad + sy), shadow)

    # White stroke — expand the image mask by stroke width
    if stroke_w > 0:
        alpha = img.split()[3]
        # Dilate the alpha mask to create the stroke
        stroke_mask = alpha.filter(ImageFilter.MaxFilter(size=stroke_w * 2 + 1))
        stroke_layer = Image.new("RGBA", img.size, cfg.image_stroke_color)
        stroke_layer.putalpha(stroke_mask)
        canvas.paste(stroke_layer, (pad, pad), stroke_layer)

    # Main image on top
    canvas.paste(img, (pad, pad), img)

    return canvas


def image_wiggle_transform(
    t: float, image_index: int = 0, cfg: VFXConfig = VFX_DEFAULTS
) -> tuple[float, float, float]:
    """
    Returns (dx, dy, rotation_degrees) for paper-cutout wiggle/float.
    Each image gets a unique phase offset based on its index.
    """
    freq = cfg.image_wiggle_freq
    amp = cfg.image_wiggle_translate
    rot_amp = cfg.image_wiggle_rotation
    phase = image_index * 1.37  # golden ratio offset for variety

    dx = amp * math.sin(2 * math.pi * freq * t + phase)
    dy = amp * 0.7 * math.cos(2 * math.pi * freq * 0.8 * t + phase + 0.5)
    rot = rot_amp * math.sin(2 * math.pi * freq * 0.6 * t + phase + 1.0)

    return dx, dy, rot


def image_entrance_scale(
    t: float, appear_time: float, cfg: VFXConfig = VFX_DEFAULTS
) -> float:
    """
    Scale factor for image pop-in with elastic overshoot.
    Returns 0 before appear_time, then bounces to 1.0.
    """
    local_t = t - appear_time
    if local_t < 0:
        return 0.0
    if local_t >= cfg.image_entrance_duration:
        return 1.0

    progress = local_t / cfg.image_entrance_duration
    return ease_out_back(progress) * cfg.image_entrance_overshoot


def apply_image_cutout(
    frame: Image.Image,
    img: Image.Image,
    x_center: int,
    y_center: int,
    t: float,
    appear_time: float = 0.0,
    image_index: int = 0,
    cfg: VFXConfig = VFX_DEFAULTS,
) -> None:
    """
    Paste an image with full paper-cutout animation:
    - Entrance: elastic pop with overshoot
    - Hold: gentle wiggle/float rotation
    - Stroke and shadow already applied to img
    """
    # Entrance scale
    scale = image_entrance_scale(t, appear_time, cfg)
    if scale <= 0.01:
        return

    # Wiggle transform
    dx, dy, rot = image_wiggle_transform(t, image_index, cfg)

    # Scale
    w, h = img.size
    if abs(scale - 1.0) > 0.02:
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        img = img.resize((new_w, new_h), Image.LANCZOS)
        w, h = new_w, new_h

    # Rotation
    if abs(rot) > 0.1:
        img = img.rotate(-rot, resample=Image.BICUBIC, expand=True)
        w, h = img.size

    # Position
    final_x = int(x_center - w // 2 + dx)
    final_y = int(y_center - h // 2 + dy)

    # Composite
    frame_rgba = frame.convert("RGBA")
    try:
        frame_rgba.paste(img, (final_x, final_y), img)
    except (ValueError, Exception):
        pass
    frame.paste(frame_rgba.convert("RGB"))


# ══════════════════════════════════════════════════════
#  3. TRANSITIONS
# ══════════════════════════════════════════════════════

def whip_pan_transition(
    frame_out: np.ndarray,
    frame_in: np.ndarray,
    progress: float,
    direction: str = "horizontal",
    cfg: VFXConfig = VFX_DEFAULTS,
) -> np.ndarray:
    """
    Whip pan: fast-forward camera to next scene with motion blur.
    progress: 0.0 (showing frame_out) → 1.0 (showing frame_in)
    """
    H, W = frame_out.shape[:2]
    p = ease_in_out_sine(progress)

    # Motion blur strength peaks at midpoint
    blur_strength = int(cfg.whip_pan_blur * math.sin(math.pi * progress))

    if direction == "horizontal":
        # Slide out left, slide in from right
        offset_out = int(W * p)
        offset_in = int(W * (1 - p))

        result = np.zeros_like(frame_out)
        if offset_out < W:
            result[:, :W - offset_out] = frame_out[:, offset_out:]
        if offset_in < W:
            result[:, W - offset_in:] = frame_in[:, :offset_in]

    else:  # vertical
        offset_out = int(H * p)
        offset_in = int(H * (1 - p))

        result = np.zeros_like(frame_out)
        if offset_out < H:
            result[:H - offset_out, :] = frame_out[offset_out:, :]
        if offset_in < H:
            result[H - offset_in:, :] = frame_in[:offset_in, :]

    # Apply motion blur
    if blur_strength > 1:
        pil = Image.fromarray(result)
        if direction == "horizontal":
            # Horizontal motion blur via resize trick
            squash = pil.resize((max(1, W // blur_strength), H), Image.BILINEAR)
            pil = squash.resize((W, H), Image.BILINEAR)
        else:
            squash = pil.resize((W, max(1, H // blur_strength)), Image.BILINEAR)
            pil = squash.resize((W, H), Image.BILINEAR)
        result = np.array(pil)

    return result


def mask_wipe_transition(
    frame_out: np.ndarray,
    frame_in: np.ndarray,
    progress: float,
    shape: str = "circle",
    cfg: VFXConfig = VFX_DEFAULTS,
) -> np.ndarray:
    """
    Mask wipe: solid shape grows from center, reveals next scene.
    First half: shape grows over frame_out.
    Second half: shape shrinks to reveal frame_in.
    """
    H, W = frame_out.shape[:2]

    if progress < 0.5:
        # Growing mask over outgoing frame
        base = frame_out
        mask_progress = progress * 2  # 0→1
    else:
        # Shrinking mask reveals incoming frame
        base = frame_in
        mask_progress = (1.0 - progress) * 2  # 1→0

    p = ease_in_out_sine(mask_progress)
    max_radius = int(math.sqrt(W ** 2 + H ** 2) / 2)
    radius = int(max_radius * p)

    # Create mask
    mask = Image.new("L", (W, H), 255)
    draw = ImageDraw.Draw(mask)
    cx, cy = W // 2, H // 2

    if shape == "circle":
        draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=0,
        )
    elif shape == "diamond":
        draw.polygon(
            [(cx, cy - radius), (cx + radius, cy),
             (cx, cy + radius), (cx - radius, cy)],
            fill=0,
        )
    else:  # square
        draw.rectangle(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=0,
        )

    mask_arr = np.array(mask, dtype=np.float32) / 255.0

    # Use an accent color for the wipe shape (visible during transition)
    accent_color = np.array([40, 40, 40], dtype=np.uint8)

    if progress < 0.5:
        # Blend: base visible where mask=1, accent where mask=0
        result = base.copy()
        accent_frame = np.full_like(base, accent_color)
        mask_3d = mask_arr[:, :, np.newaxis]
        result = (base * mask_3d + accent_frame * (1 - mask_3d)).astype(np.uint8)
    else:
        # Reveal: incoming visible where mask=1, accent where mask=0
        result = base.copy()
        accent_frame = np.full_like(base, accent_color)
        mask_3d = mask_arr[:, :, np.newaxis]
        result = (base * mask_3d + accent_frame * (1 - mask_3d)).astype(np.uint8)

    return result


def z_zoom_transition(
    frame_out: np.ndarray,
    frame_in: np.ndarray,
    progress: float,
    zoom_point: tuple[float, float] = (0.5, 0.5),
    cfg: VFXConfig = VFX_DEFAULTS,
) -> np.ndarray:
    """
    Z-axis zoom: zoom into a point on frame_out until it becomes frame_in.
    zoom_point: (0-1, 0-1) relative position to zoom into.
    """
    H, W = frame_out.shape[:2]
    p = ease_in_out_sine(progress)
    max_scale = cfg.z_zoom_max_scale

    if progress < 0.5:
        # Zoom into outgoing frame
        scale = 1.0 + (max_scale - 1.0) * (p * 2)
        frame = frame_out
        alpha = 1.0
    else:
        # Zoom out from incoming frame
        scale = max_scale - (max_scale - 1.0) * ((p - 0.5) * 2)
        frame = frame_in
        alpha = 1.0

    # Scale and crop around zoom point
    pil = Image.fromarray(frame)
    new_w = int(W * scale)
    new_h = int(H * scale)
    pil = pil.resize((new_w, new_h), Image.LANCZOS)

    # Crop center around zoom point
    zx = int(zoom_point[0] * new_w)
    zy = int(zoom_point[1] * new_h)
    left = max(0, zx - W // 2)
    top = max(0, zy - H // 2)
    left = min(left, new_w - W)
    top = min(top, new_h - H)
    pil = pil.crop((left, top, left + W, top + H))

    result = np.array(pil)

    # Cross-dissolve at the midpoint
    if 0.35 < progress < 0.65:
        blend = (progress - 0.35) / 0.30
        result_in = frame_in
        result = (result * (1 - blend) + result_in * blend).astype(np.uint8)

    return result


# ══════════════════════════════════════════════════════
#  4. OVERLAYS
# ══════════════════════════════════════════════════════

_grain_cache: dict[tuple[int, int], np.ndarray] = {}


def generate_paper_grain(
    width: int, height: int, seed: int = 42, cfg: VFXConfig = VFX_DEFAULTS
) -> np.ndarray:
    """
    Generate a static paper/film grain texture.
    Returns uint8 array (H, W) that can be used as a multiply overlay.
    Cached per resolution for performance.
    """
    key = (width, height)
    if key in _grain_cache:
        return _grain_cache[key]

    rng = np.random.RandomState(seed)
    grain_size = cfg.paper_texture_grain_size

    # Generate at lower res, then upscale for coarser grain
    small_w = max(1, width // grain_size)
    small_h = max(1, height // grain_size)
    noise = rng.randint(180, 255, (small_h, small_w), dtype=np.uint8)

    grain = Image.fromarray(noise, "L")
    grain = grain.resize((width, height), Image.BILINEAR)
    result = np.array(grain)

    _grain_cache[key] = result
    return result


def apply_paper_texture(
    frame: np.ndarray, grain: np.ndarray, cfg: VFXConfig = VFX_DEFAULTS
) -> np.ndarray:
    """
    Apply paper texture overlay to a frame.
    Blending mode: multiply (darken), very low opacity.
    """
    opacity = cfg.paper_texture_opacity
    if opacity <= 0:
        return frame

    # Multiply blend: result = frame * (grain / 255)
    # But at very low opacity, blend between original and multiplied
    grain_3d = grain[:, :, np.newaxis].astype(np.float32) / 255.0
    multiplied = (frame.astype(np.float32) * grain_3d).astype(np.uint8)

    # Lerp between original and multiplied
    result = (
        frame.astype(np.float32) * (1 - opacity)
        + multiplied.astype(np.float32) * opacity
    ).astype(np.uint8)

    return result


def should_flash_frame(
    t: float,
    word_timings: list,
    fps: int = 30,
    cfg: VFXConfig = VFX_DEFAULTS,
) -> bool:
    """
    Returns True if the current time t falls on a flash frame
    (when a major word appears — first word of each line or emphasis words).
    """
    if not word_timings:
        return False

    flash_window = cfg.flash_frame_duration_frames / fps

    for i, wt in enumerate(word_timings):
        # Flash on the first word and every ~4th word (key beats)
        if i == 0 or i % 4 == 0:
            if wt.start <= t < wt.start + flash_window:
                return True

    return False


def apply_flash_frame(
    frame: np.ndarray, cfg: VFXConfig = VFX_DEFAULTS
) -> np.ndarray:
    """
    Apply a single-frame white flash (camera flash effect).
    Blends white at the configured opacity.
    """
    opacity = cfg.flash_frame_opacity
    white = np.full_like(frame, 255)
    result = (
        frame.astype(np.float32) * (1 - opacity)
        + white.astype(np.float32) * opacity
    ).astype(np.uint8)
    return result


# ══════════════════════════════════════════════════════
#  5. TRANSITION SEQUENCER
# ══════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════
#  6. GLITCH WIPE TRANSITION
# ══════════════════════════════════════════════════════

def glitch_wipe_transition(
    frame_out: np.ndarray,
    frame_in: np.ndarray,
    progress: float,
    cfg: VFXConfig = VFX_DEFAULTS,
) -> np.ndarray:
    """
    Glitch wipe: 0.1s digital distortion with RGB split + scanlines.
    Creates a tech/high-energy feel between clips.
    """
    H, W = frame_out.shape[:2]

    # Cross-dissolve base
    if progress < 0.5:
        base = frame_out.copy()
        blend = progress * 2
    else:
        base = frame_in.copy()
        blend = (1.0 - progress) * 2

    # Intensity peaks in the middle of the transition
    intensity = math.sin(math.pi * progress)
    rgb_offset = int(cfg.glitch_rgb_offset * intensity)

    result = base.copy()

    # RGB channel separation (chromatic aberration)
    if cfg.glitch_color_shift and rgb_offset > 0:
        r = result[:, :, 0]
        g = result[:, :, 1]
        b = result[:, :, 2]

        # Shift red channel left, blue channel right
        r_shifted = np.zeros_like(r)
        b_shifted = np.zeros_like(b)

        if rgb_offset < W:
            r_shifted[:, :W - rgb_offset] = r[:, rgb_offset:]
            b_shifted[:, rgb_offset:] = b[:, :W - rgb_offset]
        else:
            r_shifted = r
            b_shifted = b

        result[:, :, 0] = r_shifted
        result[:, :, 2] = b_shifted

    # Scanline noise (horizontal bands)
    if cfg.glitch_noise_opacity > 0:
        noise_intensity = cfg.glitch_noise_opacity * intensity
        # Random horizontal displacement of some scanlines
        rng = np.random.RandomState(int(progress * 1000) % 100)
        for _ in range(int(8 * intensity)):
            line_y = rng.randint(0, H)
            line_h = rng.randint(2, max(3, int(12 * intensity)))
            shift = rng.randint(-int(20 * intensity), int(20 * intensity))
            y_end = min(H, line_y + line_h)
            if shift > 0 and shift < W:
                result[line_y:y_end, shift:] = result[line_y:y_end, :W - shift]
            elif shift < 0 and abs(shift) < W:
                result[line_y:y_end, :W + shift] = result[line_y:y_end, -shift:]

    # Cross-blend with other frame at edges
    if progress < 0.5:
        result = (result.astype(np.float32) * (1 - blend * 0.3)
                  + frame_in.astype(np.float32) * (blend * 0.3)).astype(np.uint8)
    else:
        result = (result.astype(np.float32) * (1 - blend * 0.3)
                  + frame_out.astype(np.float32) * (blend * 0.3)).astype(np.uint8)

    return result


# ══════════════════════════════════════════════════════
#  7. 2.5D PARALLAX (Depth for Static Images)
# ══════════════════════════════════════════════════════

def parallax_transform(
    img: Image.Image,
    t: float,
    screen_duration: float,
    cfg: VFXConfig = VFX_DEFAULTS,
) -> Image.Image:
    """
    Apply 2.5D parallax Ken Burns effect — slow zoom + pan to add depth.
    Makes static AI images look like high-budget animations.

    The direction is randomised per-call but deterministic (based on duration).
    """
    if not cfg.parallax_enabled:
        return img

    w, h = img.size
    progress = min(1.0, t / max(screen_duration, 0.1))
    p = ease_in_out_sine(progress)

    # Slow zoom: 1.0 → 1.0 + zoom_range over the scene duration
    zoom = 1.0 + cfg.parallax_zoom_range * p

    # Slow pan: drift left-to-right (or reverse based on hash)
    direction = 1 if int(screen_duration * 100) % 2 == 0 else -1
    pan_x = cfg.parallax_pan_range * w * p * direction
    pan_y = cfg.parallax_pan_range * h * 0.5 * p  # slight vertical drift too

    # Apply zoom
    new_w = int(w * zoom)
    new_h = int(h * zoom)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    # Crop back to original size, offset by pan
    cx = new_w // 2 + int(pan_x)
    cy = new_h // 2 + int(pan_y)
    left = max(0, min(cx - w // 2, new_w - w))
    top = max(0, min(cy - h // 2, new_h - h))
    img = img.crop((left, top, left + w, top + h))

    return img


# ══════════════════════════════════════════════════════
#  8. LIGHT LEAKS / FILM BURNS
# ══════════════════════════════════════════════════════

_light_leak_cache: dict[tuple[int, int], Image.Image] = {}


def generate_light_leak(
    width: int, height: int, cfg: VFXConfig = VFX_DEFAULTS
) -> Image.Image:
    """
    Generate a warm light leak overlay (RGBA).
    Warm light on the edges — simulates film burns / anamorphic lens flare.
    Cached per resolution.
    """
    key = (width, height)
    if key in _light_leak_cache:
        return _light_leak_cache[key]

    leak = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(leak)
    r, g, b = cfg.light_leak_warmth

    # Top-right warm glow
    for i in range(80):
        alpha = int(40 * (1 - i / 80))
        radius = int(min(width, height) * 0.3) + i * 4
        cx, cy = int(width * 0.85), int(height * 0.1)
        draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=(r, g, b, max(0, alpha)),
        )

    # Bottom-left warm glow (dimmer)
    for i in range(60):
        alpha = int(25 * (1 - i / 60))
        radius = int(min(width, height) * 0.2) + i * 3
        cx, cy = int(width * 0.1), int(height * 0.9)
        draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=(r, g, b, max(0, alpha)),
        )

    # Soften
    leak = leak.filter(ImageFilter.GaussianBlur(radius=40))

    _light_leak_cache[key] = leak
    return leak


def apply_light_leak(
    frame: np.ndarray,
    leak: Image.Image,
    intensity: float = 1.0,
    cfg: VFXConfig = VFX_DEFAULTS,
) -> np.ndarray:
    """
    Blend warm light leak overlay onto a frame.
    intensity: 0→1, use for fading the effect in/out during transitions.
    """
    opacity = cfg.light_leak_opacity * intensity
    if opacity <= 0:
        return frame

    # Convert frame to PIL, composite, convert back
    base = Image.fromarray(frame).convert("RGBA")
    leak_rgba = leak.copy()

    # Scale opacity
    r_l, g_l, b_l, a_l = leak_rgba.split()
    a_arr = np.array(a_l, dtype=np.float32) * opacity
    leak_rgba.putalpha(Image.fromarray(a_arr.astype(np.uint8)))

    result = Image.alpha_composite(base, leak_rgba)
    return np.array(result.convert("RGB"))


# ══════════════════════════════════════════════════════
#  9. BEAT-SYNC PULSE
# ══════════════════════════════════════════════════════

def beat_pulse_scale(
    t: float,
    word_timings: list,
    cfg: VFXConfig = VFX_DEFAULTS,
) -> float:
    """
    Returns a scale multiplier (1.0 to 1.0 + beat_pulse_scale) based on
    proximity to word beats. Creates a subtle "throb" on every spoken word.
    """
    if not cfg.beat_pulse_enabled or not word_timings:
        return 1.0

    pulse = 0.0
    for wt in word_timings:
        dt = t - wt.start
        if 0 <= dt < cfg.beat_pulse_decay:
            # Sharp attack, exponential decay
            word_pulse = cfg.beat_pulse_scale * math.exp(-dt / (cfg.beat_pulse_decay * 0.3))
            pulse = max(pulse, word_pulse)

    return 1.0 + pulse


# ══════════════════════════════════════════════════════
#  10. MIXED FORMATTING (Key Keyword Detection)
# ══════════════════════════════════════════════════════

# Common short words that are NOT keywords (articles, prepositions, conjunctions)
_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "must", "need",
    "and", "but", "or", "nor", "for", "yet", "so",
    "in", "on", "at", "to", "of", "by", "up", "as", "if", "it",
    "from", "with", "into", "than", "that", "this", "these", "those",
    "not", "no", "all", "each", "every", "both", "few", "more", "most",
    "other", "some", "such", "only", "own", "same", "then", "too", "very",
    "just", "about", "over", "also", "after", "before", "between",
    "he", "she", "they", "we", "you", "i", "me", "my", "your", "his",
    "her", "its", "our", "their", "who", "what", "which", "when", "where",
    "how", "why", "there", "here", "out", "them",
})


def is_keyword(word: str, word_index: int = 0, total_words: int = 1) -> bool:
    """
    Detect if a word is a 'key keyword' (likely noun/verb) for mixed formatting.

    Heuristic: words that are 5+ characters and NOT in stop words are keywords.
    Also marks the first meaningful word of content and proper-noun-looking words.
    """
    clean = word.lower().strip(".,!?;:\"'()[]—–-")
    if not clean:
        return False

    # Stop words are never keywords
    if clean in _STOP_WORDS:
        return False

    # Short words (1-3 chars) rarely keywords unless they start with uppercase
    if len(clean) <= 3:
        return word[0].isupper() if word else False

    # 4-char words: only if they look like proper nouns
    if len(clean) == 4:
        return word[0].isupper() if word else False

    # 5+ characters and not a stop word → likely a keyword
    return True


# ══════════════════════════════════════════════════════
#  11. SMART FLASH FRAME (Reveal Moments Only)
# ══════════════════════════════════════════════════════

def should_flash_reveal(
    t: float,
    screen_start_offset: float,
    word_timings: list,
    fps: int = 30,
    cfg: VFXConfig = VFX_DEFAULTS,
) -> bool:
    """
    Returns True only on 'reveal' moments — the very first word of a screen.
    Much less frequent than the old every-4th-word approach.
    This creates an attention-grabbing "shock" without being distracting.
    """
    if cfg.flash_frame_opacity <= 0 or not cfg.flash_on_reveals_only:
        return False

    if not word_timings:
        return False

    flash_window = cfg.flash_frame_duration_frames / fps

    # Only flash on the very first word of this screen
    first_word = word_timings[0]
    if first_word.start <= t < first_word.start + flash_window:
        return True

    return False


def apply_warm_flash(
    frame: np.ndarray, cfg: VFXConfig = VFX_DEFAULTS
) -> np.ndarray:
    """
    Apply a warm flash (not pure white — warm light feel).
    More cinematic than plain white flash.
    """
    opacity = cfg.flash_frame_opacity
    # Warm white instead of pure white
    warm = np.full_like(frame, [255, 245, 220])  # warm amber-white
    result = (
        frame.astype(np.float32) * (1 - opacity)
        + warm.astype(np.float32) * opacity
    ).astype(np.uint8)
    return result


# ══════════════════════════════════════════════════════
#  12. IMAGE-LEVEL TRANSITIONS (content transitions, not screen)
# ══════════════════════════════════════════════════════

# Cycle through these for consecutive screens
IMAGE_TRANSITION_TYPES = [
    "paper_slide",       # Type 1: slide in from side, roll out
    "fast_slow_fast",    # Type 2: fast in → slow center → fast out
    "swipe_through",     # Type 3: swipe in from any dir, out opposite
]

# Swipe direction combos for Type 3 (cycles through)
_SWIPE_COMBOS = [
    ("right", "left"),    # in from right, out to left
    ("top", "bottom"),    # in from top, out to bottom
    ("left", "right"),    # in from left, out to right
    ("bottom", "top"),    # in from bottom, out to top
]


def get_image_transition_for_scene(scene_index: int) -> str:
    """Get the image transition type for a given scene index."""
    return IMAGE_TRANSITION_TYPES[scene_index % len(IMAGE_TRANSITION_TYPES)]


def get_swipe_direction(scene_index: int) -> tuple[str, str]:
    """Get (enter_dir, exit_dir) for swipe transitions."""
    return _SWIPE_COMBOS[scene_index % len(_SWIPE_COMBOS)]


def image_transition_offset(
    t: float,
    duration: float,
    screen_w: int,
    screen_h: int,
    trans_type: str,
    scene_index: int = 0,
) -> tuple[int, int, float]:
    """
    Calculate (x_offset, y_offset, alpha) for image-level transitions.

    Returns pixel offsets from centre position + alpha for the image.
    The background stays STATIC — only the image moves.
    """
    if duration <= 0:
        return 0, 0, 1.0

    # Entry/exit timing
    entry_dur = 0.5    # time for image to enter
    exit_dur = 0.5     # time for image to exit
    hold_start = entry_dur
    hold_end = duration - exit_dur

    if trans_type == "paper_slide":
        # Type 1: Slide in from right, stay, slide-roll out left
        # Alternate: even scenes from right, odd from left
        from_right = (scene_index % 2 == 0)
        slide_x = screen_w + 100  # offscreen distance

        if t < entry_dur:
            # Slide in
            p = ease_out_cubic(t / entry_dur)
            x_off = int(slide_x * (1 - p)) * (1 if from_right else -1)
            return x_off, 0, min(1.0, t / 0.2)
        elif t > hold_end:
            # Slide-roll out (opposite direction + slight rotation effect via shrink)
            exit_t = (t - hold_end) / exit_dur
            p = ease_in_cubic(min(1.0, exit_t))
            x_off = int(-slide_x * p) * (1 if from_right else -1)
            alpha = max(0.0, 1.0 - exit_t)
            return x_off, 0, alpha
        else:
            return 0, 0, 1.0

    elif trans_type == "fast_slow_fast":
        # Type 2: Fast from left → slow through center → fast exit right
        travel = screen_w * 0.35  # total horizontal travel range
        slow_dur = duration - entry_dur - exit_dur  # middle section

        if t < entry_dur:
            # Fast entry from left to near-center
            p = ease_out_cubic(t / entry_dur)
            x_off = int(-travel - 50 + (travel + 50) * p)
            return x_off, 0, min(1.0, t / 0.15)
        elif t > hold_end:
            # Fast exit to right
            exit_t = (t - hold_end) / exit_dur
            p = ease_in_cubic(min(1.0, exit_t))
            x_off = int(travel * p + 50 * p)
            alpha = max(0.0, 1.0 - exit_t ** 2)
            return x_off, 0, alpha
        else:
            # Slow drift through center (left-to-right drift)
            mid_t = (t - entry_dur) / max(slow_dur, 0.1)
            # Gentle sine drift from slightly left of center to slightly right
            x_off = int(travel * 0.3 * (mid_t * 2 - 1))
            return x_off, 0, 1.0

    elif trans_type == "swipe_through":
        # Type 3: Swipe in from one direction, out the opposite
        enter_dir, exit_dir = get_swipe_direction(scene_index)

        def _dir_vector(d: str) -> tuple[int, int]:
            if d == "right":
                return screen_w + 100, 0
            elif d == "left":
                return -(screen_w + 100), 0
            elif d == "top":
                return 0, -(screen_h + 100)
            else:  # bottom
                return 0, screen_h + 100

        enter_x, enter_y = _dir_vector(enter_dir)
        exit_x, exit_y = _dir_vector(exit_dir)

        if t < entry_dur:
            p = ease_out_cubic(t / entry_dur)
            x_off = int(enter_x * (1 - p))
            y_off = int(enter_y * (1 - p))
            return x_off, y_off, min(1.0, t / 0.2)
        elif t > hold_end:
            exit_t = (t - hold_end) / exit_dur
            p = ease_in_cubic(min(1.0, exit_t))
            x_off = int(exit_x * p)
            y_off = int(exit_y * p)
            alpha = max(0.0, 1.0 - exit_t)
            return x_off, y_off, alpha
        else:
            return 0, 0, 1.0

    # Default: no movement
    return 0, 0, 1.0


# ══════════════════════════════════════════════════════
#  13. TEXT-LEVEL TRANSITIONS (enter/exit for narration)
# ══════════════════════════════════════════════════════

def text_enter_offset(
    t: float, duration: float, screen_h: int
) -> tuple[int, float]:
    """
    Calculate (y_offset, alpha) for narration text entering the screen.
    Text slides up from below and fades in during the first 0.4s.
    """
    enter_dur = 0.4
    if t < enter_dur:
        p = ease_out_cubic(t / enter_dur)
        y_off = int(screen_h * 0.08 * (1 - p))  # slide up from 8% below
        alpha = p
        return y_off, alpha
    return 0, 1.0


def text_exit_offset(
    t: float, duration: float, screen_h: int
) -> tuple[int, float]:
    """
    Calculate (y_offset, alpha) for narration text exiting the screen.
    Text slides up and fades out during the last 0.3s.
    """
    exit_dur = 0.3
    exit_start = duration - exit_dur
    if t > exit_start and duration > exit_dur:
        exit_t = (t - exit_start) / exit_dur
        p = ease_in_cubic(min(1.0, exit_t))
        y_off = int(-screen_h * 0.06 * p)  # slide up
        alpha = max(0.0, 1.0 - p)
        return y_off, alpha
    return 0, 1.0


# Ordered transition types that cycle through scenes (legacy — kept for compat)
TRANSITION_SEQUENCE = [
    "whip_horizontal",    # Fast horizontal whip pan
    "z_zoom",             # Z-axis zoom into image
    "glitch",             # Digital distortion wipe
    "pop",                # Elastic scale pop
    "whip_vertical",      # Fast vertical whip pan
    "z_zoom",             # Z-axis zoom again
    "whip_horizontal",    # Repeat cycle
    "glitch",             # Another glitch
    "pop",                # Elastic pop again
    "fade",               # Classic cross-dissolve
]


def get_transition_for_scene(scene_index: int) -> str:
    """Get the transition type for a given scene index."""
    return TRANSITION_SEQUENCE[scene_index % len(TRANSITION_SEQUENCE)]


def apply_transition_blend(
    frame_out: np.ndarray,
    frame_in: np.ndarray,
    progress: float,
    transition_type: str,
    cfg: VFXConfig = VFX_DEFAULTS,
) -> np.ndarray:
    """Apply the appropriate transition between two frames."""
    if transition_type == "whip_horizontal":
        return whip_pan_transition(frame_out, frame_in, progress, "horizontal", cfg)
    elif transition_type == "whip_vertical":
        return whip_pan_transition(frame_out, frame_in, progress, "vertical", cfg)
    elif transition_type.startswith("mask_"):
        shape = transition_type.split("_")[1] if "_" in transition_type else "circle"
        return mask_wipe_transition(frame_out, frame_in, progress, shape, cfg)
    elif transition_type == "z_zoom":
        return z_zoom_transition(frame_out, frame_in, progress, cfg=cfg)
    elif transition_type == "pop":
        # Existing pop transition — scale-based
        return _pop_transition(frame_out, frame_in, progress)
    else:
        # Default cross-dissolve
        return _crossfade_transition(frame_out, frame_in, progress)


def _crossfade_transition(
    frame_out: np.ndarray, frame_in: np.ndarray, progress: float
) -> np.ndarray:
    """Simple cross-dissolve."""
    return (
        frame_out.astype(np.float32) * (1 - progress)
        + frame_in.astype(np.float32) * progress
    ).astype(np.uint8)


def _pop_transition(
    frame_out: np.ndarray, frame_in: np.ndarray, progress: float
) -> np.ndarray:
    """Pop/elastic scale transition."""
    H, W = frame_out.shape[:2]

    if progress < 0.5:
        # Scale down outgoing
        alpha = 1.0 - progress * 2
        return (frame_out.astype(np.float32) * alpha).astype(np.uint8)
    else:
        # Scale up incoming with elastic
        p = (progress - 0.5) * 2
        scale = ease_out_elastic(p)
        pil = Image.fromarray(frame_in)
        new_w = max(1, int(W * scale))
        new_h = max(1, int(H * scale))
        pil = pil.resize((new_w, new_h), Image.LANCZOS)
        # Center crop
        left = max(0, (new_w - W) // 2)
        top = max(0, (new_h - H) // 2)
        right = min(new_w, left + W)
        bottom = min(new_h, top + H)
        pil = pil.crop((left, top, right, bottom))
        if pil.size != (W, H):
            pil = pil.resize((W, H), Image.LANCZOS)
        return np.array(pil)


# ══════════════════════════════════════════════════════
#  HELPER: Render text to RGBA image for animation
# ══════════════════════════════════════════════════════

def render_text_to_image(
    text: str,
    font: ImageFont.FreeTypeFont,
    color: tuple,
    max_width: int,
    shadow: bool = True,
    shadow_offset: tuple = (2, 2),
    shadow_color: tuple = (0, 0, 0, 40),
) -> Image.Image:
    """
    Render text string to an RGBA Image for use with animation functions.
    Handles word-wrapping and returns a tight-cropped image.
    """
    if not text:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))

    # Word wrap
    words = text.split()
    lines = []
    current = ""
    for w in words:
        test = f"{current} {w}".strip()
        bbox = font.getbbox(test)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    if not lines:
        lines = [""]

    # Calculate size
    line_h = font.getbbox("Ag")[3] - font.getbbox("Ag")[1]
    spacing = 6
    total_h = line_h * len(lines) + spacing * (len(lines) - 1)
    total_w = max(
        font.getbbox(line)[2] - font.getbbox(line)[0] for line in lines
    )

    # Add padding for shadow
    pad = max(abs(shadow_offset[0]), abs(shadow_offset[1])) + 4
    canvas = Image.new("RGBA", (total_w + pad * 2, total_h + pad * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    y = pad
    for line in lines:
        bbox = font.getbbox(line)
        tw = bbox[2] - bbox[0]
        x = (total_w + pad * 2 - tw) // 2

        if shadow:
            draw.text(
                (x + shadow_offset[0], y + shadow_offset[1]),
                line, fill=shadow_color, font=font,
            )
        draw.text((x, y), line, fill=color, font=font)
        y += line_h + spacing

    return canvas
