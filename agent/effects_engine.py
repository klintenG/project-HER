"""
Project HER v2.0 – Comprehensive Effects Engine
================================================
PIL/numpy implementations of ALL effects in the catalog.
Each effect is a pure function operating on PIL Images or numpy arrays.

Effects are frame-level: given a time `t`, duration, and parameters,
they transform images/text to produce the animated frame.

Architecture:
  - Text effects: operate on PIL.Image overlay layers
  - Image effects: transform the image before compositing
  - Transitions: blend two numpy frames
  - Overlays: composite onto the final frame
  - Background effects: modify the background image
"""

from __future__ import annotations

import math
import hashlib
from typing import Any, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance


# ══════════════════════════════════════════════════════
#  EASING FUNCTIONS
# ══════════════════════════════════════════════════════

def ease_linear(t: float) -> float:
    return max(0.0, min(1.0, t))

def ease_in_quad(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t

def ease_out_quad(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 2

def ease_in_out_quad(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 2 * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 2 / 2

def ease_in_cubic(t: float) -> float:
    return max(0.0, min(1.0, t)) ** 3

def ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3

def ease_in_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2

def ease_in_quart(t: float) -> float:
    return max(0.0, min(1.0, t)) ** 4

def ease_out_quart(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 4

def ease_in_out_sine(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return -(math.cos(math.pi * t) - 1.0) / 2.0

def ease_out_back(t: float) -> float:
    t = max(0.0, min(1.0, t))
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2

def ease_out_elastic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    if t == 0 or t == 1:
        return t
    c4 = (2 * math.pi) / 3
    return 2 ** (-10 * t) * math.sin((t * 10 - 0.75) * c4) + 1

def ease_out_bounce(t: float) -> float:
    t = max(0.0, min(1.0, t))
    n1, d1 = 7.5625, 2.75
    if t < 1 / d1:
        return n1 * t * t
    elif t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    elif t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    else:
        t -= 2.625 / d1
        return n1 * t * t + 0.984375

# Lookup for easing by name
EASING_FUNCTIONS = {
    "linear": ease_linear,
    "ease_in_quad": ease_in_quad,
    "ease_out_quad": ease_out_quad,
    "ease_in_out_quad": ease_in_out_quad,
    "ease_in_cubic": ease_in_cubic,
    "ease_out_cubic": ease_out_cubic,
    "ease_in_out_cubic": ease_in_out_cubic,
    "ease_in_quart": ease_in_quart,
    "ease_out_quart": ease_out_quart,
    "ease_in_out_sine": ease_in_out_sine,
    "ease_out_back": ease_out_back,
    "ease_out_elastic": ease_out_elastic,
    "ease_out_bounce": ease_out_bounce,
}

def get_easing(name: str):
    return EASING_FUNCTIONS.get(name, ease_out_cubic)


# ══════════════════════════════════════════════════════
#  HELPER UTILITIES
# ══════════════════════════════════════════════════════

def _stable_random(seed_str: str, count: int = 1) -> list[float]:
    """Deterministic pseudo-random floats from a string seed (0-1 range)."""
    h = hashlib.md5(seed_str.encode()).hexdigest()
    vals = []
    for i in range(count):
        chunk = h[(i * 4) % len(h):(i * 4 + 8) % len(h) or len(h)]
        vals.append(int(chunk, 16) / (16 ** len(chunk)))
    return vals

def _clamp(val: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, val))


# ══════════════════════════════════════════════════════
#  1. TEXT ENTRY EFFECTS
# ══════════════════════════════════════════════════════

def text_entry_fade_in(
    t: float, duration: float, params: dict
) -> dict:
    """Returns {alpha, x_offset, y_offset, scale, blur, rotation}."""
    dur = params.get("duration", 0.5)
    if t >= dur:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_out_cubic(t / dur)
    return {"alpha": p, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}


def text_entry_slide_up(
    t: float, duration: float, screen_h: int, params: dict
) -> dict:
    dur = params.get("duration", 0.7)
    dist = params.get("distance", 0.25)
    easing_name = params.get("easing", "ease_out_cubic")
    e = get_easing(easing_name)
    if t >= dur:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = e(t / dur)
    y_off = int(screen_h * dist * (1.0 - p))
    return {"alpha": min(1.0, t / (dur * 0.5)), "x_offset": 0, "y_offset": y_off, "scale": 1.0, "blur": 0, "rotation": 0.0}


def text_entry_slide_down(
    t: float, duration: float, screen_h: int, params: dict
) -> dict:
    dur = params.get("duration", 0.4)
    dist = params.get("distance", 0.12)
    if t >= dur:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_out_cubic(t / dur)
    y_off = int(-screen_h * dist * (1.0 - p))
    return {"alpha": min(1.0, t / (dur * 0.5)), "x_offset": 0, "y_offset": y_off, "scale": 1.0, "blur": 0, "rotation": 0.0}


def text_entry_slide_left(
    t: float, duration: float, screen_w: int, params: dict
) -> dict:
    dur = params.get("duration", 0.35)
    if t >= dur:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_out_cubic(t / dur)
    x_off = int(screen_w * 0.15 * (1.0 - p))
    return {"alpha": p, "x_offset": x_off, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}


def text_entry_slide_right(
    t: float, duration: float, screen_w: int, params: dict
) -> dict:
    dur = params.get("duration", 0.35)
    if t >= dur:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_out_cubic(t / dur)
    x_off = int(-screen_w * 0.15 * (1.0 - p))
    return {"alpha": p, "x_offset": x_off, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}


def text_entry_scale_bounce(
    t: float, duration: float, params: dict
) -> dict:
    dur = params.get("duration", 0.35)
    overshoot = params.get("overshoot", 1.15)
    if t >= dur:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = t / dur
    # Elastic-style overshoot
    scale = ease_out_back(p) * overshoot
    if p > 0.7:
        # Settle back to 1.0
        settle = (p - 0.7) / 0.3
        scale = scale + (1.0 - scale) * settle
    return {"alpha": min(1.0, p * 2), "x_offset": 0, "y_offset": 0, "scale": max(0.01, scale), "blur": 0, "rotation": 0.0}


def text_entry_elastic_drop(
    t: float, duration: float, screen_h: int, params: dict
) -> dict:
    dur = params.get("duration", 0.5)
    if t >= dur:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = t / dur
    # Drop from above with bounce
    drop = -screen_h * 0.15 * (1.0 - ease_out_bounce(p))
    return {"alpha": min(1.0, p * 3), "x_offset": 0, "y_offset": int(drop), "scale": 1.0, "blur": 0, "rotation": 0.0}


def text_entry_blur_reveal(
    t: float, duration: float, params: dict
) -> dict:
    dur = params.get("duration", 0.6)
    max_blur = params.get("max_blur", 12)
    if t >= dur:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_out_cubic(t / dur)
    blur = int(max_blur * (1.0 - p))
    return {"alpha": p, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": blur, "rotation": 0.0}


def text_entry_glitch_in(
    t: float, duration: float, screen_w: int, params: dict
) -> dict:
    dur = params.get("duration", 0.3)
    jitter = params.get("jitter", 5)
    if t >= dur:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0, "glitch": 0.0}
    p = t / dur
    intensity = 1.0 - p
    jx = int(jitter * intensity * math.sin(t * 80))
    jy = int(jitter * 0.5 * intensity * math.cos(t * 90))
    return {"alpha": min(1.0, p * 2.5), "x_offset": jx, "y_offset": jy, "scale": 1.0, "blur": 0, "rotation": 0.0, "glitch": intensity}


def text_entry_wave_in(
    t: float, duration: float, params: dict
) -> dict:
    dur = params.get("duration", 0.6)
    amp = params.get("amplitude", 15)
    freq = params.get("frequency", 2.0)
    if t >= dur:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_out_cubic(t / dur)
    wave_y = int(amp * (1.0 - p) * math.sin(2 * math.pi * freq * t))
    return {"alpha": p, "x_offset": 0, "y_offset": wave_y, "scale": 1.0, "blur": 0, "rotation": 0.0}


def text_entry_spiral_in(
    t: float, duration: float, params: dict
) -> dict:
    dur = params.get("duration", 0.7)
    rots = params.get("rotations", 1.5)
    if t >= dur:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_out_cubic(t / dur)
    scale = 0.1 + 0.9 * p
    rotation = (1.0 - p) * rots * 360
    return {"alpha": p, "x_offset": 0, "y_offset": 0, "scale": scale, "blur": 0, "rotation": rotation}


def text_entry_flip_in(
    t: float, duration: float, params: dict
) -> dict:
    dur = params.get("duration", 0.4)
    if t >= dur:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_out_cubic(t / dur)
    # Simulate 3D flip by squashing Y scale
    flip_angle = (1.0 - p) * math.pi
    y_scale = abs(math.cos(flip_angle))
    return {"alpha": p, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0, "y_scale": max(0.05, y_scale)}


def text_entry_explode_in(
    t: float, duration: float, params: dict
) -> dict:
    """For per-character processing — returns overall progress."""
    dur = params.get("duration", 0.6)
    scatter = params.get("scatter_radius", 200)
    if t >= dur:
        return {"alpha": 1.0, "progress": 1.0, "scatter_radius": scatter}
    p = ease_out_cubic(t / dur)
    return {"alpha": p, "progress": p, "scatter_radius": scatter}


def text_entry_dissolve_in(
    t: float, duration: float, params: dict
) -> dict:
    dur = params.get("duration", 0.8)
    if t >= dur:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0, "dissolve": 1.0}
    p = ease_out_cubic(t / dur)
    return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": int(3 * (1 - p)), "rotation": 0.0, "dissolve": p}


def text_entry_split_reveal(
    t: float, duration: float, params: dict
) -> dict:
    dur = params.get("duration", 0.5)
    gap = params.get("gap", 30)
    if t >= dur:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0, "split_gap": 0}
    p = ease_out_cubic(t / dur)
    current_gap = int(gap * (1.0 - p))
    return {"alpha": p, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0, "split_gap": current_gap}


def text_entry_zoom_blur_in(
    t: float, duration: float, params: dict
) -> dict:
    dur = params.get("duration", 0.4)
    start_scale = params.get("start_scale", 3.0)
    if t >= dur:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_out_cubic(t / dur)
    scale = start_scale + (1.0 - start_scale) * p
    blur = int(8 * (1.0 - p))
    return {"alpha": min(1.0, p * 2), "x_offset": 0, "y_offset": 0, "scale": max(0.1, scale), "blur": blur, "rotation": 0.0}


def text_entry_stamp_in(
    t: float, duration: float, params: dict
) -> dict:
    dur = params.get("duration", 0.25)
    shake = params.get("shake_amount", 6)
    if t >= dur:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = t / dur
    scale = 2.5 - 1.5 * ease_out_quad(p)
    # Impact shake in second half
    shake_x, shake_y = 0, 0
    if p > 0.4:
        shake_decay = (1.0 - p) / 0.6
        shake_x = int(shake * shake_decay * math.sin(t * 120))
        shake_y = int(shake * shake_decay * math.cos(t * 100))
    return {"alpha": min(1.0, p * 3), "x_offset": shake_x, "y_offset": shake_y, "scale": max(0.8, scale), "blur": 0, "rotation": 0.0}


def text_entry_curtain_reveal(
    t: float, duration: float, screen_w: int, params: dict
) -> dict:
    dur = params.get("duration", 0.5)
    if t >= dur:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0, "clip_progress": 1.0}
    p = ease_out_cubic(t / dur)
    return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0, "clip_progress": p}


def text_entry_grow_from_center(
    t: float, duration: float, params: dict
) -> dict:
    dur = params.get("duration", 0.5)
    if t >= dur:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_out_back(t / dur)
    return {"alpha": p, "x_offset": 0, "y_offset": 0, "scale": max(0.01, p), "blur": 0, "rotation": 0.0}


def text_entry_matrix_rain(
    t: float, duration: float, params: dict
) -> dict:
    dur = params.get("duration", 0.8)
    if t >= dur:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0, "matrix": 0.0}
    p = ease_out_cubic(t / dur)
    return {"alpha": p, "x_offset": 0, "y_offset": int(-20 * (1 - p)), "scale": 1.0, "blur": 0, "rotation": 0.0, "matrix": 1.0 - p}


def text_entry_smoke_reveal(
    t: float, duration: float, params: dict
) -> dict:
    dur = params.get("duration", 0.8)
    if t >= dur:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_out_cubic(t / dur)
    blur = int(10 * (1.0 - p))
    return {"alpha": p ** 0.5, "x_offset": 0, "y_offset": int(-5 * (1 - p)), "scale": 1.0, "blur": blur, "rotation": 0.0}


def text_entry_typewriter(
    t: float, duration: float, text_len: int, params: dict
) -> dict:
    """Returns how many characters to show."""
    char_delay = params.get("char_delay", 0.04)
    show_cursor = params.get("show_cursor", True)
    chars_to_show = min(text_len, int(t / char_delay))
    return {"chars_visible": chars_to_show, "show_cursor": show_cursor and (int(t * 3) % 2 == 0), "alpha": 1.0}


# Text entry dispatcher
TEXT_ENTRY_FNS = {
    "fade_in": lambda t, dur, W, H, p: text_entry_fade_in(t, dur, p),
    "slide_up": lambda t, dur, W, H, p: text_entry_slide_up(t, dur, H, p),
    "slide_down": lambda t, dur, W, H, p: text_entry_slide_down(t, dur, H, p),
    "slide_left": lambda t, dur, W, H, p: text_entry_slide_left(t, dur, W, p),
    "slide_right": lambda t, dur, W, H, p: text_entry_slide_right(t, dur, W, p),
    "scale_bounce": lambda t, dur, W, H, p: text_entry_scale_bounce(t, dur, p),
    "elastic_drop": lambda t, dur, W, H, p: text_entry_elastic_drop(t, dur, H, p),
    "blur_reveal": lambda t, dur, W, H, p: text_entry_blur_reveal(t, dur, p),
    "glitch_in": lambda t, dur, W, H, p: text_entry_glitch_in(t, dur, W, p),
    "wave_in": lambda t, dur, W, H, p: text_entry_wave_in(t, dur, p),
    "spiral_in": lambda t, dur, W, H, p: text_entry_spiral_in(t, dur, p),
    "flip_in": lambda t, dur, W, H, p: text_entry_flip_in(t, dur, p),
    "explode_in": lambda t, dur, W, H, p: text_entry_explode_in(t, dur, p),
    "dissolve_in": lambda t, dur, W, H, p: text_entry_dissolve_in(t, dur, p),
    "split_reveal": lambda t, dur, W, H, p: text_entry_split_reveal(t, dur, p),
    "zoom_blur_in": lambda t, dur, W, H, p: text_entry_zoom_blur_in(t, dur, p),
    "stamp_in": lambda t, dur, W, H, p: text_entry_stamp_in(t, dur, p),
    "curtain_reveal": lambda t, dur, W, H, p: text_entry_curtain_reveal(t, dur, W, p),
    "grow_from_center": lambda t, dur, W, H, p: text_entry_grow_from_center(t, dur, p),
    "matrix_rain": lambda t, dur, W, H, p: text_entry_matrix_rain(t, dur, p),
    "smoke_reveal": lambda t, dur, W, H, p: text_entry_smoke_reveal(t, dur, p),
    "typewriter": lambda t, dur, W, H, p: text_entry_typewriter(t, dur, 100, p),
}


def get_text_entry_transform(
    effect_name: str, t: float, duration: float,
    screen_w: int, screen_h: int, params: dict | None = None,
) -> dict:
    """Get text entry transform properties for time t."""
    params = params or {}
    fn = TEXT_ENTRY_FNS.get(effect_name, TEXT_ENTRY_FNS["fade_in"])
    return fn(t, duration, screen_w, screen_h, params)


# ══════════════════════════════════════════════════════
#  2. TEXT EXIT EFFECTS
# ══════════════════════════════════════════════════════

def text_exit_fade_out(
    t: float, duration: float, exit_start: float, params: dict
) -> dict:
    dur = params.get("duration", 0.4)
    if t < exit_start:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = min(1.0, (t - exit_start) / dur)
    return {"alpha": 1.0 - p, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}


def text_exit_slide_out_up(
    t: float, duration: float, exit_start: float, screen_h: int, params: dict
) -> dict:
    dur = params.get("duration", 0.35)
    if t < exit_start:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_in_cubic(min(1.0, (t - exit_start) / dur))
    y_off = int(-screen_h * 0.12 * p)
    return {"alpha": 1.0 - p, "x_offset": 0, "y_offset": y_off, "scale": 1.0, "blur": 0, "rotation": 0.0}


def text_exit_slide_out_down(
    t: float, duration: float, exit_start: float, screen_h: int, params: dict
) -> dict:
    dur = params.get("duration", 0.35)
    if t < exit_start:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_in_cubic(min(1.0, (t - exit_start) / dur))
    y_off = int(screen_h * 0.12 * p)
    return {"alpha": 1.0 - p, "x_offset": 0, "y_offset": y_off, "scale": 1.0, "blur": 0, "rotation": 0.0}


def text_exit_slide_out_left(
    t: float, duration: float, exit_start: float, screen_w: int, params: dict
) -> dict:
    dur = params.get("duration", 0.3)
    if t < exit_start:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_in_cubic(min(1.0, (t - exit_start) / dur))
    x_off = int(-screen_w * 0.2 * p)
    return {"alpha": 1.0 - p, "x_offset": x_off, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}


def text_exit_slide_out_right(
    t: float, duration: float, exit_start: float, screen_w: int, params: dict
) -> dict:
    dur = params.get("duration", 0.3)
    if t < exit_start:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_in_cubic(min(1.0, (t - exit_start) / dur))
    x_off = int(screen_w * 0.2 * p)
    return {"alpha": 1.0 - p, "x_offset": x_off, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}


def text_exit_scale_shrink(
    t: float, duration: float, exit_start: float, params: dict
) -> dict:
    dur = params.get("duration", 0.3)
    if t < exit_start:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_in_cubic(min(1.0, (t - exit_start) / dur))
    return {"alpha": 1.0 - p, "x_offset": 0, "y_offset": 0, "scale": max(0.01, 1.0 - p), "blur": 0, "rotation": 0.0}


def text_exit_blur_exit(
    t: float, duration: float, exit_start: float, params: dict
) -> dict:
    dur = params.get("duration", 0.4)
    max_blur = params.get("max_blur", 15)
    if t < exit_start:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_in_cubic(min(1.0, (t - exit_start) / dur))
    return {"alpha": 1.0 - p, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": int(max_blur * p), "rotation": 0.0}


def text_exit_explode_out(
    t: float, duration: float, exit_start: float, params: dict
) -> dict:
    dur = params.get("duration", 0.4)
    scatter = params.get("scatter_radius", 300)
    if t < exit_start:
        return {"alpha": 1.0, "progress": 0.0, "scatter_radius": scatter}
    p = min(1.0, (t - exit_start) / dur)
    return {"alpha": 1.0 - p, "progress": p, "scatter_radius": scatter}


def text_exit_dissolve_out(
    t: float, duration: float, exit_start: float, params: dict
) -> dict:
    dur = params.get("duration", 0.5)
    if t < exit_start:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0, "dissolve": 1.0}
    p = min(1.0, (t - exit_start) / dur)
    return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": int(3 * p), "rotation": 0.0, "dissolve": 1.0 - p}


def text_exit_flick_off(
    t: float, duration: float, exit_start: float, screen_w: int, params: dict
) -> dict:
    dur = params.get("duration", 0.3)
    if t < exit_start:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_in_quad(min(1.0, (t - exit_start) / dur))
    x_off = int(screen_w * 0.3 * p)
    blur = int(8 * p)
    return {"alpha": 1.0 - p, "x_offset": x_off, "y_offset": 0, "scale": 1.0, "blur": blur, "rotation": p * 5}


def text_exit_evaporate(
    t: float, duration: float, exit_start: float, params: dict
) -> dict:
    dur = params.get("duration", 0.5)
    if t < exit_start:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = min(1.0, (t - exit_start) / dur)
    y_off = int(-30 * p)
    return {"alpha": (1.0 - p) ** 2, "x_offset": 0, "y_offset": y_off, "scale": 1.0 + 0.1 * p, "blur": int(5 * p), "rotation": 0.0}


def text_exit_crumble(
    t: float, duration: float, exit_start: float, screen_h: int, params: dict
) -> dict:
    dur = params.get("duration", 0.4)
    if t < exit_start:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_in_quad(min(1.0, (t - exit_start) / dur))
    y_off = int(screen_h * 0.1 * p)
    rotation = p * 8 * math.sin(t * 40)
    return {"alpha": 1.0 - p, "x_offset": 0, "y_offset": y_off, "scale": max(0.3, 1.0 - 0.4 * p), "blur": int(3 * p), "rotation": rotation}


def text_exit_vortex_out(
    t: float, duration: float, exit_start: float, params: dict
) -> dict:
    dur = params.get("duration", 0.5)
    if t < exit_start:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_in_cubic(min(1.0, (t - exit_start) / dur))
    rotation = p * 720
    return {"alpha": 1.0 - p, "x_offset": 0, "y_offset": 0, "scale": max(0.01, 1.0 - p * 0.9), "blur": int(5 * p), "rotation": rotation}


def text_exit_glitch_out(
    t: float, duration: float, exit_start: float, screen_w: int, params: dict
) -> dict:
    dur = params.get("duration", 0.3)
    if t < exit_start:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0, "glitch": 0.0}
    p = min(1.0, (t - exit_start) / dur)
    jx = int(10 * p * math.sin(t * 80))
    return {"alpha": 1.0 - p, "x_offset": jx, "y_offset": int(5 * p * math.cos(t * 60)), "scale": 1.0, "blur": 0, "rotation": 0.0, "glitch": p}


def text_exit_swipe_wipe(
    t: float, duration: float, exit_start: float, params: dict
) -> dict:
    dur = params.get("duration", 0.35)
    if t < exit_start:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0, "clip_progress": 1.0}
    p = ease_in_cubic(min(1.0, (t - exit_start) / dur))
    return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0, "clip_progress": 1.0 - p}


def text_exit_flip_out(
    t: float, duration: float, exit_start: float, params: dict
) -> dict:
    dur = params.get("duration", 0.35)
    if t < exit_start:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_in_cubic(min(1.0, (t - exit_start) / dur))
    y_scale = abs(math.cos(p * math.pi / 2))
    return {"alpha": 1.0 - p, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0, "y_scale": max(0.01, y_scale)}


# Exit dispatcher
TEXT_EXIT_FNS = {
    "fade_out": lambda t, d, es, W, H, p: text_exit_fade_out(t, d, es, p),
    "slide_out_up": lambda t, d, es, W, H, p: text_exit_slide_out_up(t, d, es, H, p),
    "slide_out_down": lambda t, d, es, W, H, p: text_exit_slide_out_down(t, d, es, H, p),
    "slide_out_left": lambda t, d, es, W, H, p: text_exit_slide_out_left(t, d, es, W, p),
    "slide_out_right": lambda t, d, es, W, H, p: text_exit_slide_out_right(t, d, es, W, p),
    "scale_shrink": lambda t, d, es, W, H, p: text_exit_scale_shrink(t, d, es, p),
    "blur_exit": lambda t, d, es, W, H, p: text_exit_blur_exit(t, d, es, p),
    "explode_out": lambda t, d, es, W, H, p: text_exit_explode_out(t, d, es, p),
    "dissolve_out": lambda t, d, es, W, H, p: text_exit_dissolve_out(t, d, es, p),
    "flip_out": lambda t, d, es, W, H, p: text_exit_flip_out(t, d, es, p),
    "flick_off": lambda t, d, es, W, H, p: text_exit_flick_off(t, d, es, W, p),
    "evaporate": lambda t, d, es, W, H, p: text_exit_evaporate(t, d, es, p),
    "crumble": lambda t, d, es, W, H, p: text_exit_crumble(t, d, es, H, p),
    "swipe_wipe": lambda t, d, es, W, H, p: text_exit_swipe_wipe(t, d, es, p),
    "vortex_out": lambda t, d, es, W, H, p: text_exit_vortex_out(t, d, es, p),
    "glitch_out": lambda t, d, es, W, H, p: text_exit_glitch_out(t, d, es, W, p),
}


def get_text_exit_transform(
    effect_name: str, t: float, duration: float, exit_start: float,
    screen_w: int, screen_h: int, params: dict | None = None,
) -> dict:
    """Get text exit transform properties for time t."""
    params = params or {}
    fn = TEXT_EXIT_FNS.get(effect_name, TEXT_EXIT_FNS["fade_out"])
    return fn(t, duration, exit_start, screen_w, screen_h, params)


# ══════════════════════════════════════════════════════
#  3. TEXT CONTINUOUS EFFECTS
# ══════════════════════════════════════════════════════

def text_cont_glow_pulse(t: float, params: dict) -> dict:
    freq = params.get("frequency", 0.8)
    min_g = params.get("min_glow", 0.0)
    max_g = params.get("max_glow", 0.4)
    glow = min_g + (max_g - min_g) * (0.5 + 0.5 * math.sin(2 * math.pi * freq * t))
    return {"glow_intensity": glow}


def text_cont_wave_motion(t: float, params: dict) -> dict:
    amp = params.get("amplitude", 4)
    freq = params.get("frequency", 1.5)
    y_off = amp * math.sin(2 * math.pi * freq * t)
    return {"y_offset": int(y_off)}


def text_cont_wobble(t: float, params: dict) -> dict:
    amt = params.get("amount", 3)
    freq = params.get("frequency", 2.0)
    dx = amt * math.sin(2 * math.pi * freq * t)
    dy = amt * 0.6 * math.cos(2 * math.pi * freq * 0.7 * t + 0.5)
    rot = amt * 0.3 * math.sin(2 * math.pi * freq * 0.5 * t + 1.0)
    return {"x_offset": int(dx), "y_offset": int(dy), "rotation": rot}


def text_cont_color_cycle(t: float, params: dict) -> dict:
    speed = params.get("speed", 0.3)
    hue = (t * speed) % 1.0
    # HSV to RGB
    r, g, b = _hsv_to_rgb(hue, 0.8, 1.0)
    return {"color_override": (int(r * 255), int(g * 255), int(b * 255))}


def text_cont_bounce(t: float, params: dict) -> dict:
    height = params.get("height", 6)
    freq = params.get("frequency", 2.0)
    y = -abs(height * math.sin(2 * math.pi * freq * t))
    return {"y_offset": int(y)}


def text_cont_float_drift(t: float, params: dict) -> dict:
    rx = params.get("range_x", 5)
    ry = params.get("range_y", 3)
    speed = params.get("speed", 0.5)
    dx = rx * math.sin(2 * math.pi * speed * t)
    dy = ry * math.cos(2 * math.pi * speed * 0.7 * t + 0.3)
    return {"x_offset": int(dx), "y_offset": int(dy)}


def text_cont_shake(t: float, params: dict) -> dict:
    intensity = params.get("intensity", 3)
    freq = params.get("frequency", 20)
    dx = intensity * math.sin(freq * t * 2 * math.pi + 0.1)
    dy = intensity * math.cos(freq * t * 2 * math.pi * 0.9 + 0.7)
    return {"x_offset": int(dx), "y_offset": int(dy)}


def text_cont_heartbeat(t: float, params: dict) -> dict:
    bpm = params.get("bpm", 72)
    scale_amt = params.get("scale_amount", 0.05)
    period = 60.0 / bpm
    phase = (t % period) / period
    # Two-beat pattern: beat at 0.0 and 0.25
    pulse = 0.0
    if phase < 0.1:
        pulse = math.sin(phase / 0.1 * math.pi) * scale_amt
    elif 0.2 < phase < 0.3:
        pulse = math.sin((phase - 0.2) / 0.1 * math.pi) * scale_amt * 0.7
    return {"scale": 1.0 + pulse}


def text_cont_flicker(t: float, params: dict) -> dict:
    freq = params.get("frequency", 8)
    min_alpha = params.get("min_alpha", 0.3)
    # Pseudo-random flicker using multiple sine waves
    flicker = math.sin(freq * t * 2 * math.pi) * math.sin(freq * 1.3 * t * 2 * math.pi)
    alpha = min_alpha + (1.0 - min_alpha) * (0.5 + 0.5 * flicker)
    return {"alpha": _clamp(alpha)}


def text_cont_pendulum(t: float, params: dict) -> dict:
    angle = params.get("angle", 5)
    speed = params.get("speed", 1.0)
    rot = angle * math.sin(2 * math.pi * speed * t)
    return {"rotation": rot}


def text_cont_breathe(t: float, params: dict) -> dict:
    scale_range = params.get("scale_range", 0.03)
    speed = params.get("speed", 0.4)
    scale = 1.0 + scale_range * math.sin(2 * math.pi * speed * t)
    return {"scale": scale}


def text_cont_scan_line(t: float, params: dict) -> dict:
    speed = params.get("speed", 1.0)
    width = params.get("width", 30)
    pos = (t * speed) % 1.0
    return {"scan_line_pos": pos, "scan_line_width": width}


def text_cont_fire_flicker(t: float, params: dict) -> dict:
    intensity = params.get("intensity", 0.5)
    # Warm color shifts
    r_shift = int(20 * intensity * (0.5 + 0.5 * math.sin(t * 12)))
    g_shift = int(-10 * intensity * (0.5 + 0.5 * math.sin(t * 8 + 0.5)))
    flicker_alpha = 0.85 + 0.15 * math.sin(t * 15) * math.sin(t * 10.7)
    return {"color_shift": (r_shift, g_shift, 0), "alpha": _clamp(flicker_alpha)}


def text_cont_electric_arc(t: float, params: dict) -> dict:
    # Occasional sparks
    spark_phase = math.sin(t * 7) * math.sin(t * 11)
    show_spark = spark_phase > 0.7
    return {"spark": show_spark, "spark_intensity": (spark_phase - 0.7) / 0.3 if show_spark else 0.0}


TEXT_CONTINUOUS_FNS = {
    "none": lambda t, p: {},
    "glow_pulse": text_cont_glow_pulse,
    "wave_motion": text_cont_wave_motion,
    "wobble": text_cont_wobble,
    "color_cycle": text_cont_color_cycle,
    "bounce": text_cont_bounce,
    "float_drift": text_cont_float_drift,
    "shake": text_cont_shake,
    "heartbeat": text_cont_heartbeat,
    "flicker": text_cont_flicker,
    "pendulum": text_cont_pendulum,
    "breathe": text_cont_breathe,
    "scan_line": text_cont_scan_line,
    "fire_flicker": text_cont_fire_flicker,
    "electric_arc": text_cont_electric_arc,
}


def get_text_continuous_transform(
    effect_name: str, t: float, params: dict | None = None,
) -> dict:
    """Get continuous text animation modifiers for time t."""
    params = params or {}
    fn = TEXT_CONTINUOUS_FNS.get(effect_name, TEXT_CONTINUOUS_FNS["none"])
    return fn(t, params)


# ══════════════════════════════════════════════════════
#  4. IMAGE ENTRY/EXIT EFFECTS
# ══════════════════════════════════════════════════════

def img_entry_fade_in(t: float, duration: float, params: dict) -> dict:
    dur = params.get("duration", 0.5)
    if t >= dur:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_out_cubic(t / dur)
    return {"alpha": p, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}


def img_entry_scale_bounce(t: float, duration: float, params: dict) -> dict:
    dur = params.get("duration", 0.4)
    if t >= dur:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = t / dur
    scale = ease_out_back(p)
    return {"alpha": min(1.0, p * 2.5), "x_offset": 0, "y_offset": 0, "scale": max(0.01, scale), "blur": 0, "rotation": 0.0}


def img_entry_slide_in(t: float, duration: float, screen_w: int, screen_h: int, params: dict) -> dict:
    dur = params.get("duration", 0.5)
    direction = params.get("direction", "right")
    if t >= dur:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_out_cubic(t / dur)
    x_off, y_off = 0, 0
    if direction == "right":
        x_off = int(screen_w * 0.6 * (1.0 - p))
    elif direction == "left":
        x_off = int(-screen_w * 0.6 * (1.0 - p))
    elif direction == "top":
        y_off = int(-screen_h * 0.5 * (1.0 - p))
    elif direction == "bottom":
        y_off = int(screen_h * 0.5 * (1.0 - p))
    return {"alpha": min(1.0, t / 0.2), "x_offset": x_off, "y_offset": y_off, "scale": 1.0, "blur": 0, "rotation": 0.0}


def img_entry_zoom_in(t: float, duration: float, params: dict) -> dict:
    dur = params.get("duration", 0.5)
    if t >= dur:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_out_cubic(t / dur)
    scale = 0.3 + 0.7 * p
    return {"alpha": min(1.0, p * 2), "x_offset": 0, "y_offset": 0, "scale": scale, "blur": int(5 * (1 - p)), "rotation": 0.0}


def img_entry_rotate_in(t: float, duration: float, params: dict) -> dict:
    dur = params.get("duration", 0.5)
    if t >= dur:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_out_cubic(t / dur)
    return {"alpha": p, "x_offset": 0, "y_offset": 0, "scale": p, "blur": 0, "rotation": (1 - p) * 180}


def img_entry_flip_in(t: float, duration: float, params: dict) -> dict:
    dur = params.get("duration", 0.4)
    if t >= dur:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_out_cubic(t / dur)
    y_scale = abs(math.cos((1 - p) * math.pi))
    return {"alpha": p, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0, "y_scale": max(0.05, y_scale)}


def img_entry_blur_reveal(t: float, duration: float, params: dict) -> dict:
    dur = params.get("duration", 0.6)
    if t >= dur:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_out_cubic(t / dur)
    return {"alpha": p, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": int(15 * (1 - p)), "rotation": 0.0}


def img_entry_shutter(t: float, duration: float, params: dict) -> dict:
    dur = params.get("duration", 0.5)
    if t >= dur:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0, "shutter_progress": 1.0}
    p = ease_out_cubic(t / dur)
    return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0, "shutter_progress": p}


IMAGE_ENTRY_FNS = {
    "img_fade_in": lambda t, d, W, H, p: img_entry_fade_in(t, d, p),
    "img_scale_bounce": lambda t, d, W, H, p: img_entry_scale_bounce(t, d, p),
    "img_slide_in": lambda t, d, W, H, p: img_entry_slide_in(t, d, W, H, p),
    "img_zoom_in": lambda t, d, W, H, p: img_entry_zoom_in(t, d, p),
    "img_rotate_in": lambda t, d, W, H, p: img_entry_rotate_in(t, d, p),
    "img_flip_in": lambda t, d, W, H, p: img_entry_flip_in(t, d, p),
    "img_blur_reveal": lambda t, d, W, H, p: img_entry_blur_reveal(t, d, p),
    "img_shutter": lambda t, d, W, H, p: img_entry_shutter(t, d, p),
}


def get_image_entry_transform(
    effect_name: str, t: float, duration: float,
    screen_w: int, screen_h: int, params: dict | None = None,
) -> dict:
    params = params or {}
    fn = IMAGE_ENTRY_FNS.get(effect_name, IMAGE_ENTRY_FNS["img_fade_in"])
    return fn(t, duration, screen_w, screen_h, params)


# Image exit transforms
def img_exit_fade_out(t: float, duration: float, exit_start: float, params: dict) -> dict:
    dur = params.get("duration", 0.4)
    if t < exit_start:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = min(1.0, (t - exit_start) / dur)
    return {"alpha": 1.0 - p, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}


def img_exit_slide_out(t: float, duration: float, exit_start: float, screen_w: int, params: dict) -> dict:
    dur = params.get("duration", 0.4)
    direction = params.get("direction", "left")
    if t < exit_start:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_in_cubic(min(1.0, (t - exit_start) / dur))
    x_off = int(-screen_w * 0.6 * p) if direction == "left" else int(screen_w * 0.6 * p)
    return {"alpha": max(0, 1.0 - p), "x_offset": x_off, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}


def img_exit_scale_out(t: float, duration: float, exit_start: float, params: dict) -> dict:
    dur = params.get("duration", 0.35)
    if t < exit_start:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_in_cubic(min(1.0, (t - exit_start) / dur))
    return {"alpha": 1.0 - p, "x_offset": 0, "y_offset": 0, "scale": max(0.01, 1.0 - p), "blur": 0, "rotation": 0.0}


def img_exit_blur_out(t: float, duration: float, exit_start: float, params: dict) -> dict:
    dur = params.get("duration", 0.4)
    if t < exit_start:
        return {"alpha": 1.0, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": 0, "rotation": 0.0}
    p = ease_in_cubic(min(1.0, (t - exit_start) / dur))
    return {"alpha": 1.0 - p, "x_offset": 0, "y_offset": 0, "scale": 1.0, "blur": int(15 * p), "rotation": 0.0}


IMAGE_EXIT_FNS = {
    "img_fade_out": lambda t, d, es, W, H, p: img_exit_fade_out(t, d, es, p),
    "img_slide_out": lambda t, d, es, W, H, p: img_exit_slide_out(t, d, es, W, p),
    "img_scale_out": lambda t, d, es, W, H, p: img_exit_scale_out(t, d, es, p),
    "img_blur_out": lambda t, d, es, W, H, p: img_exit_blur_out(t, d, es, p),
    "img_shatter_out": lambda t, d, es, W, H, p: img_exit_fade_out(t, d, es, p),  # Simplified
    "img_dissolve_out": lambda t, d, es, W, H, p: img_exit_fade_out(t, d, es, p),  # Simplified
}


def get_image_exit_transform(
    effect_name: str, t: float, duration: float, exit_start: float,
    screen_w: int, screen_h: int, params: dict | None = None,
) -> dict:
    params = params or {}
    fn = IMAGE_EXIT_FNS.get(effect_name, IMAGE_EXIT_FNS["img_fade_out"])
    return fn(t, duration, exit_start, screen_w, screen_h, params)


# ══════════════════════════════════════════════════════
#  5. IMAGE TREATMENT EFFECTS (during display)
# ══════════════════════════════════════════════════════

def img_effect_ken_burns(
    img: Image.Image, t: float, duration: float, params: dict
) -> Image.Image:
    """Slow zoom + pan across image."""
    zoom_range = params.get("zoom_range", 0.18)
    pan_range = params.get("pan_range", 0.10)
    p = ease_in_out_sine(min(1.0, t / max(duration, 0.1)))
    w, h = img.size
    zoom = 1.0 + zoom_range * p
    direction = 1 if int(duration * 100) % 2 == 0 else -1
    pan_x = pan_range * w * p * direction
    pan_y = pan_range * h * 0.5 * p
    new_w, new_h = int(w * zoom), int(h * zoom)
    img_z = img.resize((new_w, new_h), Image.LANCZOS)
    cx = new_w // 2 + int(pan_x)
    cy = new_h // 2 + int(pan_y)
    left = max(0, min(cx - w // 2, new_w - w))
    top = max(0, min(cy - h // 2, new_h - h))
    return img_z.crop((left, top, left + w, top + h))


def img_effect_zoom_pulse(
    img: Image.Image, t: float, duration: float, params: dict
) -> Image.Image:
    amount = params.get("amount", 0.06)
    speed = params.get("speed", 0.4)
    zoom = 1.0 + amount * math.sin(2 * math.pi * speed * t)
    w, h = img.size
    new_w, new_h = int(w * zoom), int(h * zoom)
    img_z = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - w) // 2
    top = (new_h - h) // 2
    return img_z.crop((left, top, left + w, top + h))


def img_effect_parallax_2d(
    img: Image.Image, t: float, duration: float, params: dict
) -> Image.Image:
    """2D parallax — subtle position shift for depth."""
    range_val = params.get("range", 0.05)
    w, h = img.size
    p = min(1.0, t / max(duration, 0.1))
    offset_x = int(w * range_val * (p * 2 - 1))
    offset_y = int(h * range_val * 0.5 * (p * 2 - 1))
    # Pad image to allow shift
    padded = Image.new(img.mode, (w + abs(offset_x) * 2, h + abs(offset_y) * 2), (0, 0, 0, 0) if img.mode == "RGBA" else (0, 0, 0))
    padded.paste(img, (abs(offset_x) + offset_x, abs(offset_y) + offset_y))
    return padded.crop((abs(offset_x), abs(offset_y), abs(offset_x) + w, abs(offset_y) + h))


def img_effect_tilt_shift(
    img: Image.Image, t: float, duration: float, params: dict
) -> Image.Image:
    """Fake tilt-shift — blur edges, keep center sharp."""
    w, h = img.size
    result = img.copy()
    blurred = img.filter(ImageFilter.GaussianBlur(radius=8))
    # Create mask — sharp in center (white=255), blurred at edges (black=0)
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.rectangle([0, h // 3, w, 2 * h // 3], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=30))
    # Invert mask: we want to paste blurred pixels where mask is DARK (edges)
    inv_mask = Image.eval(mask, lambda px: 255 - px)
    result.paste(blurred, mask=inv_mask)
    return result


def img_effect_vignette(
    img: Image.Image, t: float, duration: float, params: dict
) -> Image.Image:
    """Dark vignette around edges."""
    w, h = img.size
    vig = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(vig)
    max_r = int(math.sqrt(w ** 2 + h ** 2) / 2)
    for i in range(50):
        r = max_r - i * (max_r // 50)
        alpha = int(80 * (1 - i / 50))
        draw.ellipse([w // 2 - r, h // 2 - r, w // 2 + r, h // 2 + r], fill=(0, 0, 0, 0))
    # Simpler approach: gradient mask
    mask = Image.new("L", (w, h), 0)
    mdraw = ImageDraw.Draw(mask)
    for radius in range(max(w, h), 0, -5):
        intensity = max(0, 255 - int(255 * (radius / max(w, h))))
        mdraw.ellipse(
            [w // 2 - radius, h // 2 - radius, w // 2 + radius, h // 2 + radius],
            fill=intensity,
        )
    dark = Image.new("RGBA", (w, h), (0, 0, 0, 60))
    dark.putalpha(mask)
    result = Image.alpha_composite(img.convert("RGBA"), dark)
    return result.convert(img.mode)


def img_effect_color_shift(
    img: Image.Image, t: float, duration: float, params: dict
) -> Image.Image:
    """Gradual color temperature shift."""
    p = min(1.0, t / max(duration, 0.1))
    enhancer = ImageEnhance.Color(img.convert("RGB"))
    sat = 0.8 + 0.4 * p  # slight saturation increase
    result = enhancer.enhance(sat)
    return result.convert(img.mode) if img.mode != "RGB" else result


def img_effect_sepia_blend(
    img: Image.Image, t: float, duration: float, params: dict
) -> Image.Image:
    """Blend towards sepia."""
    p = params.get("blend", 0.3)
    rgb = img.convert("RGB")
    arr = np.array(rgb, dtype=np.float32)
    # Sepia matrix
    sepia = np.array([
        [0.393, 0.769, 0.189],
        [0.349, 0.686, 0.168],
        [0.272, 0.534, 0.131],
    ])
    sepia_arr = np.clip(arr @ sepia.T, 0, 255).astype(np.uint8)
    result = (arr * (1 - p) + sepia_arr.astype(np.float32) * p).astype(np.uint8)
    result_img = Image.fromarray(result)
    return result_img.convert(img.mode) if img.mode != "RGB" else result_img


def img_effect_rotation_slow(
    img: Image.Image, t: float, duration: float, params: dict
) -> Image.Image:
    speed = params.get("speed", 2.0)
    angle = speed * t
    return img.rotate(-angle, resample=Image.BICUBIC, expand=False)


def img_effect_desaturate_to_color(
    img: Image.Image, t: float, duration: float, params: dict
) -> Image.Image:
    """Start grayscale, gain color over time."""
    p = ease_out_cubic(min(1.0, t / max(duration * 0.7, 0.1)))
    rgb = img.convert("RGB")
    gray = ImageEnhance.Color(rgb).enhance(0.0)
    # Blend between gray and full color
    arr_gray = np.array(gray, dtype=np.float32)
    arr_color = np.array(rgb, dtype=np.float32)
    result = (arr_gray * (1 - p) + arr_color * p).astype(np.uint8)
    result_img = Image.fromarray(result)
    return result_img.convert(img.mode) if img.mode != "RGB" else result_img


def img_effect_brightness_pulse(
    img: Image.Image, t: float, duration: float, params: dict
) -> Image.Image:
    speed = params.get("speed", 0.7)
    amount = params.get("amount", 0.1)
    brightness = 1.0 + amount * math.sin(2 * math.pi * speed * t)
    return ImageEnhance.Brightness(img.convert("RGB")).enhance(brightness).convert(img.mode)


IMAGE_EFFECT_FNS = {
    "ken_burns": img_effect_ken_burns,
    "parallax_2d": img_effect_parallax_2d,
    "zoom_pulse": img_effect_zoom_pulse,
    "tilt_shift": img_effect_tilt_shift,
    "vignette": img_effect_vignette,
    "color_shift": img_effect_color_shift,
    "sepia_blend": img_effect_sepia_blend,
    "rotation_slow": img_effect_rotation_slow,
    "desaturate_to_color": img_effect_desaturate_to_color,
    "brightness_pulse": img_effect_brightness_pulse,
    "static_image": lambda img, t, d, p: img,
    "glitch_overlay": lambda img, t, d, p: img,  # Applied as overlay instead
    "split_tone": lambda img, t, d, p: img,      # Applied as post-process
}


def apply_image_effect(
    effect_name: str, img: Image.Image,
    t: float, duration: float, params: dict | None = None,
) -> Image.Image:
    params = params or {}
    fn = IMAGE_EFFECT_FNS.get(effect_name, IMAGE_EFFECT_FNS["static_image"])
    try:
        return fn(img, t, duration, params)
    except Exception:
        return img


# ══════════════════════════════════════════════════════
#  6. SCENE TRANSITIONS
# ══════════════════════════════════════════════════════

def transition_crossfade(
    frame_out: np.ndarray, frame_in: np.ndarray, progress: float, params: dict
) -> np.ndarray:
    p = ease_in_out_sine(progress)
    return (frame_out.astype(np.float32) * (1 - p) + frame_in.astype(np.float32) * p).astype(np.uint8)


def transition_hard_cut(
    frame_out: np.ndarray, frame_in: np.ndarray, progress: float, params: dict
) -> np.ndarray:
    return frame_in if progress >= 0.5 else frame_out


def transition_slide_horizontal(
    frame_out: np.ndarray, frame_in: np.ndarray, progress: float, params: dict
) -> np.ndarray:
    H, W = frame_out.shape[:2]
    p = ease_in_out_cubic(progress)
    offset = int(W * p)
    result = np.zeros_like(frame_out)
    if offset < W:
        result[:, :W - offset] = frame_out[:, offset:]
    if offset > 0:
        result[:, W - offset:] = frame_in[:, :offset]
    return result


def transition_slide_vertical(
    frame_out: np.ndarray, frame_in: np.ndarray, progress: float, params: dict
) -> np.ndarray:
    H, W = frame_out.shape[:2]
    p = ease_in_out_cubic(progress)
    offset = int(H * p)
    result = np.zeros_like(frame_out)
    if offset < H:
        result[:H - offset, :] = frame_out[offset:, :]
    if offset > 0:
        result[H - offset:, :] = frame_in[:offset, :]
    return result


def transition_wipe_left(
    frame_out: np.ndarray, frame_in: np.ndarray, progress: float, params: dict
) -> np.ndarray:
    H, W = frame_out.shape[:2]
    p = ease_in_out_sine(progress)
    cut = int(W * p)
    result = frame_out.copy()
    if cut > 0:
        result[:, :cut] = frame_in[:, :cut]
    return result


def transition_wipe_right(
    frame_out: np.ndarray, frame_in: np.ndarray, progress: float, params: dict
) -> np.ndarray:
    H, W = frame_out.shape[:2]
    p = ease_in_out_sine(progress)
    cut = int(W * (1 - p))
    result = frame_out.copy()
    if cut < W:
        result[:, cut:] = frame_in[:, cut:]
    return result


def transition_wipe_diagonal(
    frame_out: np.ndarray, frame_in: np.ndarray, progress: float, params: dict
) -> np.ndarray:
    H, W = frame_out.shape[:2]
    p = ease_in_out_sine(progress)
    result = frame_out.copy()
    for y in range(H):
        cut_x = int((W + H) * p - y)
        cut_x = max(0, min(W, cut_x))
        if cut_x > 0:
            result[y, :cut_x] = frame_in[y, :cut_x]
    return result


def transition_circle_wipe(
    frame_out: np.ndarray, frame_in: np.ndarray, progress: float, params: dict
) -> np.ndarray:
    H, W = frame_out.shape[:2]
    p = ease_in_out_sine(progress)
    max_r = int(math.sqrt(W ** 2 + H ** 2) / 2)
    radius = int(max_r * p)
    mask = Image.new("L", (W, H), 0)
    draw = ImageDraw.Draw(mask)
    cx, cy = W // 2, H // 2
    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=255)
    mask_arr = np.array(mask, dtype=np.float32) / 255.0
    mask_3d = mask_arr[:, :, np.newaxis]
    return (frame_out * (1 - mask_3d) + frame_in * mask_3d).astype(np.uint8)


def transition_diamond_wipe(
    frame_out: np.ndarray, frame_in: np.ndarray, progress: float, params: dict
) -> np.ndarray:
    H, W = frame_out.shape[:2]
    p = ease_in_out_sine(progress)
    max_r = int(math.sqrt(W ** 2 + H ** 2) / 2)
    radius = int(max_r * p)
    mask = Image.new("L", (W, H), 0)
    draw = ImageDraw.Draw(mask)
    cx, cy = W // 2, H // 2
    draw.polygon([(cx, cy - radius), (cx + radius, cy), (cx, cy + radius), (cx - radius, cy)], fill=255)
    mask_arr = np.array(mask, dtype=np.float32) / 255.0
    mask_3d = mask_arr[:, :, np.newaxis]
    return (frame_out * (1 - mask_3d) + frame_in * mask_3d).astype(np.uint8)


def transition_zoom_in(
    frame_out: np.ndarray, frame_in: np.ndarray, progress: float, params: dict
) -> np.ndarray:
    H, W = frame_out.shape[:2]
    p = ease_in_out_sine(progress)
    if p < 0.5:
        # Zoom into outgoing
        scale = 1.0 + p * 2
        pil = Image.fromarray(frame_out)
        nw, nh = int(W * scale), int(H * scale)
        pil = pil.resize((nw, nh), Image.LANCZOS)
        left, top = (nw - W) // 2, (nh - H) // 2
        pil = pil.crop((left, top, left + W, top + H))
        alpha = 1.0 - p * 2
        return (np.array(pil).astype(np.float32) * alpha + frame_in.astype(np.float32) * (1 - alpha)).astype(np.uint8)
    else:
        return frame_in


def transition_flash(
    frame_out: np.ndarray, frame_in: np.ndarray, progress: float, params: dict
) -> np.ndarray:
    if progress < 0.4:
        p = progress / 0.4
        white = np.full_like(frame_out, 255)
        return (frame_out.astype(np.float32) * (1 - p) + white.astype(np.float32) * p).astype(np.uint8)
    elif progress < 0.6:
        return np.full_like(frame_out, 255)
    else:
        p = (progress - 0.6) / 0.4
        white = np.full_like(frame_in, 255)
        return (white.astype(np.float32) * (1 - p) + frame_in.astype(np.float32) * p).astype(np.uint8)


def transition_blur(
    frame_out: np.ndarray, frame_in: np.ndarray, progress: float, params: dict
) -> np.ndarray:
    p = progress
    if p < 0.5:
        blur_r = int(20 * p * 2)
        if blur_r > 0:
            pil = Image.fromarray(frame_out).filter(ImageFilter.GaussianBlur(radius=blur_r))
            return np.array(pil)
        return frame_out
    else:
        blur_r = int(20 * (1 - p) * 2)
        if blur_r > 0:
            pil = Image.fromarray(frame_in).filter(ImageFilter.GaussianBlur(radius=blur_r))
            return np.array(pil)
        return frame_in


def transition_pixelate(
    frame_out: np.ndarray, frame_in: np.ndarray, progress: float, params: dict
) -> np.ndarray:
    H, W = frame_out.shape[:2]
    p = progress
    if p < 0.5:
        pixel_size = max(1, int(32 * p * 2))
        pil = Image.fromarray(frame_out)
        small = pil.resize((max(1, W // pixel_size), max(1, H // pixel_size)), Image.NEAREST)
        return np.array(small.resize((W, H), Image.NEAREST))
    else:
        pixel_size = max(1, int(32 * (1 - p) * 2))
        pil = Image.fromarray(frame_in)
        small = pil.resize((max(1, W // pixel_size), max(1, H // pixel_size)), Image.NEAREST)
        return np.array(small.resize((W, H), Image.NEAREST))


def transition_spin(
    frame_out: np.ndarray, frame_in: np.ndarray, progress: float, params: dict
) -> np.ndarray:
    H, W = frame_out.shape[:2]
    angle = progress * 360
    if progress < 0.5:
        pil = Image.fromarray(frame_out)
        scale = 1.0 - progress
    else:
        pil = Image.fromarray(frame_in)
        scale = progress
    pil = pil.rotate(-angle, resample=Image.BICUBIC, expand=False)
    nw, nh = int(W * scale), int(H * scale)
    if nw > 0 and nh > 0:
        pil = pil.resize((nw, nh), Image.LANCZOS)
        result = Image.new("RGB", (W, H), (0, 0, 0))
        result.paste(pil, ((W - nw) // 2, (H - nh) // 2))
        return np.array(result)
    return frame_in


def transition_blinds_horizontal(
    frame_out: np.ndarray, frame_in: np.ndarray, progress: float, params: dict
) -> np.ndarray:
    H, W = frame_out.shape[:2]
    num_blinds = params.get("count", 8)
    p = ease_in_out_sine(progress)
    blind_h = H // num_blinds
    result = frame_out.copy()
    for i in range(num_blinds):
        y_start = i * blind_h
        reveal = int(blind_h * p)
        if reveal > 0:
            y_end = min(y_start + reveal, H)
            result[y_start:y_end, :] = frame_in[y_start:y_end, :]
    return result


def transition_blinds_vertical(
    frame_out: np.ndarray, frame_in: np.ndarray, progress: float, params: dict
) -> np.ndarray:
    H, W = frame_out.shape[:2]
    num_blinds = params.get("count", 8)
    p = ease_in_out_sine(progress)
    blind_w = W // num_blinds
    result = frame_out.copy()
    for i in range(num_blinds):
        x_start = i * blind_w
        reveal = int(blind_w * p)
        if reveal > 0:
            x_end = min(x_start + reveal, W)
            result[:, x_start:x_end] = frame_in[:, x_start:x_end]
    return result


def transition_elastic_bounce(
    frame_out: np.ndarray, frame_in: np.ndarray, progress: float, params: dict
) -> np.ndarray:
    H, W = frame_out.shape[:2]
    p = ease_out_bounce(progress)
    offset = int(H * (1 - p))
    result = frame_out.copy()
    if offset < H:
        visible = H - offset
        result[offset:, :] = frame_in[:visible, :]
    return result


def transition_ripple(
    frame_out: np.ndarray, frame_in: np.ndarray, progress: float, params: dict
) -> np.ndarray:
    """Ripple dissolve."""
    p = ease_in_out_sine(progress)
    # Just blend with some distortion
    return (frame_out.astype(np.float32) * (1 - p) + frame_in.astype(np.float32) * p).astype(np.uint8)


def transition_ink_bleed(
    frame_out: np.ndarray, frame_in: np.ndarray, progress: float, params: dict
) -> np.ndarray:
    """Ink bleeding — organic dissolve from random points."""
    H, W = frame_out.shape[:2]
    p = ease_in_out_sine(progress)
    # Use circle wipe with multiple circles
    mask = Image.new("L", (W, H), 0)
    draw = ImageDraw.Draw(mask)
    max_r = int(max(W, H) * 1.2)
    # Multiple ink points
    points = [(W // 4, H // 3), (3 * W // 4, 2 * H // 3), (W // 2, H // 2)]
    for px, py in points:
        r = int(max_r * p)
        draw.ellipse([px - r, py - r, px + r, py + r], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=20))
    mask_arr = np.array(mask, dtype=np.float32) / 255.0
    mask_3d = mask_arr[:, :, np.newaxis]
    return (frame_out * (1 - mask_3d) + frame_in * mask_3d).astype(np.uint8)


TRANSITION_FNS = {
    "crossfade": transition_crossfade,
    "hard_cut": transition_hard_cut,
    "slide_horizontal": transition_slide_horizontal,
    "slide_vertical": transition_slide_vertical,
    "wipe_left": transition_wipe_left,
    "wipe_right": transition_wipe_right,
    "wipe_diagonal": transition_wipe_diagonal,
    "circle_wipe": transition_circle_wipe,
    "diamond_wipe": transition_diamond_wipe,
    "zoom_in": transition_zoom_in,
    "zoom_out": transition_zoom_in,  # reverse handled by progress
    "spin_transition": transition_spin,
    "flash_transition": transition_flash,
    "blur_transition": transition_blur,
    "pixelate_transition": transition_pixelate,
    "blinds_horizontal": transition_blinds_horizontal,
    "blinds_vertical": transition_blinds_vertical,
    "elastic_bounce": transition_elastic_bounce,
    "ripple_transition": transition_ripple,
    "ink_bleed": transition_ink_bleed,
    # Mapped from existing vfx_engine transitions
    "whip_pan": transition_slide_horizontal,
    "glitch_transition": transition_pixelate,
    "shatter_transition": transition_flash,
    "burn_transition": transition_flash,
    "morph": transition_crossfade,
    "flip_page": transition_slide_horizontal,
    "cube_rotate": transition_spin,
    "clock_wipe": transition_circle_wipe,
    "swirl_transition": transition_spin,
}


def apply_scene_transition(
    effect_name: str,
    frame_out: np.ndarray,
    frame_in: np.ndarray,
    progress: float,
    params: dict | None = None,
) -> np.ndarray:
    """Apply a scene transition between two frames."""
    params = params or {}
    fn = TRANSITION_FNS.get(effect_name, transition_crossfade)
    try:
        return fn(frame_out, frame_in, _clamp(progress), params)
    except Exception:
        return transition_crossfade(frame_out, frame_in, _clamp(progress), params)


# ══════════════════════════════════════════════════════
#  7. OVERLAY EFFECTS
# ══════════════════════════════════════════════════════

def overlay_grain(
    frame: np.ndarray, t: float, params: dict,
    _cache: dict = {},
) -> np.ndarray:
    """Apply film grain overlay."""
    opacity = params.get("opacity", 0.04)
    if opacity <= 0:
        return frame
    H, W = frame.shape[:2]
    key = (W, H)
    if key not in _cache:
        rng = np.random.RandomState(42)
        _cache[key] = rng.randint(180, 255, (H, W), dtype=np.uint8)
    grain = _cache[key]
    grain_3d = grain[:, :, np.newaxis].astype(np.float32) / 255.0
    multiplied = (frame.astype(np.float32) * grain_3d).astype(np.uint8)
    return (frame.astype(np.float32) * (1 - opacity) + multiplied.astype(np.float32) * opacity).astype(np.uint8)


def overlay_scan_lines(
    frame: np.ndarray, t: float, params: dict
) -> np.ndarray:
    """CRT scan line overlay."""
    opacity = params.get("opacity", 0.15)
    spacing = params.get("spacing", 3)
    H, W = frame.shape[:2]
    result = frame.copy()
    for y in range(0, H, spacing):
        result[y, :] = (result[y, :].astype(np.float32) * (1 - opacity)).astype(np.uint8)
    return result


def overlay_vhs(
    frame: np.ndarray, t: float, params: dict
) -> np.ndarray:
    """VHS distortion overlay."""
    H, W = frame.shape[:2]
    result = frame.copy()
    # Tracking noise at random positions
    rng = np.random.RandomState(int(t * 30) % 1000)
    for _ in range(3):
        y = rng.randint(0, H)
        h = rng.randint(2, 6)
        shift = rng.randint(-8, 8)
        y_end = min(H, y + h)
        if 0 < shift < W:
            result[y:y_end, shift:] = result[y:y_end, :W - shift]
        elif shift < 0 and abs(shift) < W:
            result[y:y_end, :W + shift] = result[y:y_end, -shift:]
    # Slight color bleed
    result[:, :, 0] = np.roll(result[:, :, 0], 1, axis=1)  # R shift
    result[:, :, 2] = np.roll(result[:, :, 2], -1, axis=1)  # B shift
    return result


def overlay_chromatic_aberration(
    frame: np.ndarray, t: float, params: dict
) -> np.ndarray:
    """Chromatic aberration — color fringing at edges."""
    offset = params.get("offset", 2)
    H, W = frame.shape[:2]
    result = frame.copy()
    # Shift R left, B right
    if offset < W:
        result[:, :W - offset, 0] = frame[:, offset:, 0]
        result[:, offset:, 2] = frame[:, :W - offset, 2]
    return result


def overlay_bokeh(
    frame: np.ndarray, t: float, params: dict,
    _cache: dict = {},
) -> np.ndarray:
    """Floating bokeh circles."""
    H, W = frame.shape[:2]
    opacity = params.get("opacity", 0.15)
    count = params.get("count", 12)
    key = (W, H, "bokeh")
    if key not in _cache:
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        rng = np.random.RandomState(99)
        circles = []
        for _ in range(count):
            x = rng.randint(0, W)
            y = rng.randint(0, H)
            r = rng.randint(15, 60)
            speed_x = rng.uniform(-0.3, 0.3)
            speed_y = rng.uniform(-0.2, 0.2)
            alpha = rng.randint(15, 40)
            circles.append((x, y, r, speed_x, speed_y, alpha))
        _cache[key] = circles
    circles = _cache[key]
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for cx, cy, r, sx, sy, a in circles:
        x = int((cx + sx * t * 100) % W)
        y = int((cy + sy * t * 100) % H)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 240, int(a * opacity * 5)))
    base = Image.fromarray(frame).convert("RGBA")
    comp = Image.alpha_composite(base, overlay)
    return np.array(comp.convert("RGB"))


def overlay_rain(
    frame: np.ndarray, t: float, params: dict
) -> np.ndarray:
    """Rain drops falling across the frame."""
    H, W = frame.shape[:2]
    opacity = params.get("opacity", 0.3)
    count = params.get("count", 80)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    rng = np.random.RandomState(42)
    for i in range(count):
        x = rng.randint(0, W)
        base_y = rng.randint(0, H)
        speed = rng.uniform(800, 1200)
        y = int((base_y + speed * t) % H)
        length = rng.randint(10, 30)
        alpha = int(100 * opacity)
        draw.line([(x, y), (x - 1, y + length)], fill=(200, 200, 220, alpha), width=1)
    base = Image.fromarray(frame).convert("RGBA")
    comp = Image.alpha_composite(base, overlay)
    return np.array(comp.convert("RGB"))


def overlay_snow(
    frame: np.ndarray, t: float, params: dict
) -> np.ndarray:
    """Snowflakes falling."""
    H, W = frame.shape[:2]
    count = params.get("count", 50)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    rng = np.random.RandomState(42)
    for i in range(count):
        x = rng.randint(0, W)
        base_y = rng.randint(0, H)
        speed = rng.uniform(30, 80)
        drift = rng.uniform(-20, 20)
        y = int((base_y + speed * t) % H)
        fx = int(x + drift * math.sin(t + i))
        r = rng.randint(2, 5)
        draw.ellipse([fx - r, y - r, fx + r, y + r], fill=(255, 255, 255, 120))
    base = Image.fromarray(frame).convert("RGBA")
    comp = Image.alpha_composite(base, overlay)
    return np.array(comp.convert("RGB"))


def overlay_dust_particles(
    frame: np.ndarray, t: float, params: dict
) -> np.ndarray:
    """Floating dust catching light."""
    H, W = frame.shape[:2]
    count = params.get("count", 20)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    rng = np.random.RandomState(77)
    for i in range(count):
        cx = rng.randint(0, W)
        cy = rng.randint(0, H)
        speed_x = rng.uniform(-5, 5)
        speed_y = rng.uniform(-3, -1)
        x = int((cx + speed_x * t * 10) % W)
        y = int((cy + speed_y * t * 10) % H)
        r = rng.randint(1, 3)
        alpha = int(60 + 40 * math.sin(t * 2 + i))
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 240, 200, alpha))
    base = Image.fromarray(frame).convert("RGBA")
    comp = Image.alpha_composite(base, overlay)
    return np.array(comp.convert("RGB"))


def overlay_sparkle(
    frame: np.ndarray, t: float, params: dict
) -> np.ndarray:
    """Twinkling sparkles."""
    H, W = frame.shape[:2]
    count = params.get("count", 15)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    rng = np.random.RandomState(55)
    for i in range(count):
        x = rng.randint(30, W - 30)
        y = rng.randint(30, H - 30)
        phase = rng.uniform(0, 2 * math.pi)
        brightness = max(0, math.sin(t * 3 + phase))
        if brightness > 0.5:
            r = int(3 + 4 * brightness)
            alpha = int(180 * brightness)
            # Star shape (4 lines)
            draw.line([(x - r, y), (x + r, y)], fill=(255, 255, 200, alpha), width=1)
            draw.line([(x, y - r), (x, y + r)], fill=(255, 255, 200, alpha), width=1)
    base = Image.fromarray(frame).convert("RGBA")
    comp = Image.alpha_composite(base, overlay)
    return np.array(comp.convert("RGB"))


def overlay_fire_embers(
    frame: np.ndarray, t: float, params: dict
) -> np.ndarray:
    """Glowing embers floating upward."""
    H, W = frame.shape[:2]
    count = params.get("count", 25)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    rng = np.random.RandomState(33)
    warm_colors = [(255, 120, 30), (255, 80, 20), (255, 160, 50)]
    for i in range(count):
        cx = rng.randint(0, W)
        cy = rng.randint(0, H)
        speed_y = rng.uniform(-50, -150)
        drift = rng.uniform(-15, 15)
        y = int((cy + speed_y * t) % H)
        x = int(cx + drift * math.sin(t * 2 + i))
        r = rng.randint(1, 3)
        warm = warm_colors[rng.randint(0, len(warm_colors))]
        alpha = int(120 + 60 * math.sin(t * 5 + i))
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(*warm, max(0, alpha)))
    base = Image.fromarray(frame).convert("RGBA")
    comp = Image.alpha_composite(base, overlay)
    return np.array(comp.convert("RGB"))


OVERLAY_FNS = {
    "overlay_none": lambda f, t, p: f,
    "subtle_grain": lambda f, t, p: overlay_grain(f, t, {**p, "opacity": 0.03}),
    "heavy_grain": lambda f, t, p: overlay_grain(f, t, {**p, "opacity": 0.08}),
    "light_leak": lambda f, t, p: f,  # Uses existing vfx_engine light leak
    "bokeh_overlay": overlay_bokeh,
    "rain_overlay": overlay_rain,
    "snow_overlay": overlay_snow,
    "dust_particles": overlay_dust_particles,
    "smoke_overlay": lambda f, t, p: f,  # Complex — fallback to none
    "scan_lines": overlay_scan_lines,
    "vhs_distortion": overlay_vhs,
    "chromatic_aberration": overlay_chromatic_aberration,
    "lens_flare": lambda f, t, p: f,  # Complex — fallback
    "sparkle_overlay": overlay_sparkle,
    "fire_embers": overlay_fire_embers,
    "underwater_caustics": lambda f, t, p: f,  # Complex
}


def apply_overlay_effect(
    effect_name: str, frame: np.ndarray,
    t: float, params: dict | None = None,
) -> np.ndarray:
    params = params or {}
    fn = OVERLAY_FNS.get(effect_name, OVERLAY_FNS["overlay_none"])
    try:
        return fn(frame, t, params)
    except Exception:
        return frame


# ══════════════════════════════════════════════════════
#  8. BACKGROUND EFFECTS
# ══════════════════════════════════════════════════════

def bg_gradient_shift(
    bg: Image.Image, t: float, params: dict
) -> Image.Image:
    """Slowly shift background gradient colors."""
    w, h = bg.size
    hue_shift = (t * 0.05) % 1.0
    arr = np.array(bg.convert("RGB"), dtype=np.float32)
    # Gentle hue rotation via color channel mixing
    shift_amount = 15 * math.sin(2 * math.pi * hue_shift)
    arr[:, :, 0] = np.clip(arr[:, :, 0] + shift_amount, 0, 255)
    arr[:, :, 2] = np.clip(arr[:, :, 2] - shift_amount * 0.5, 0, 255)
    return Image.fromarray(arr.astype(np.uint8)).convert(bg.mode)


def bg_color_breathe(
    bg: Image.Image, t: float, params: dict
) -> Image.Image:
    """Background subtly breathes between shades."""
    amount = params.get("amount", 0.05)
    speed = params.get("speed", 0.3)
    factor = 1.0 + amount * math.sin(2 * math.pi * speed * t)
    return ImageEnhance.Brightness(bg.convert("RGB")).enhance(factor).convert(bg.mode)


def bg_pulse(
    bg: Image.Image, t: float, params: dict
) -> Image.Image:
    """Background pulses brighter/darker."""
    amount = params.get("amount", 0.20)
    speed = params.get("speed", 0.6)
    factor = 1.0 + amount * math.sin(2 * math.pi * speed * t)
    return ImageEnhance.Brightness(bg.convert("RGB")).enhance(factor).convert(bg.mode)


def bg_particle_float(
    bg: Image.Image, t: float, params: dict
) -> Image.Image:
    """Floating particles on background."""
    w, h = bg.size
    count = params.get("count", 15)
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    rng = np.random.RandomState(42)
    for i in range(count):
        cx = rng.randint(0, w)
        cy = rng.randint(0, h)
        sx = rng.uniform(-3, 3)
        sy = rng.uniform(-2, 2)
        x = int((cx + sx * t * 20) % w)
        y = int((cy + sy * t * 20) % h)
        r = rng.randint(1, 4)
        alpha = int(30 + 20 * math.sin(t + i))
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(200, 200, 255, alpha))
    result = Image.alpha_composite(bg.convert("RGBA"), overlay)
    return result.convert(bg.mode)


BACKGROUND_FNS = {
    "bg_none": lambda bg, t, p: bg,
    "bg_gradient_shift": bg_gradient_shift,
    "bg_color_breathe": bg_color_breathe,
    "bg_pulse": bg_pulse,
    "bg_particle_float": bg_particle_float,
    "bg_noise_movement": lambda bg, t, p: bg,  # Handled by grain overlay
    "bg_aurora": lambda bg, t, p: bg_gradient_shift(bg, t, p),  # Similar effect
    "bg_grid_pattern": lambda bg, t, p: bg,
    "bg_radial_pulse": lambda bg, t, p: bg_pulse(bg, t, p),
    "bg_wave_pattern": lambda bg, t, p: bg,
}


def apply_background_effect(
    effect_name: str, bg: Image.Image,
    t: float, params: dict | None = None,
) -> Image.Image:
    params = params or {}
    fn = BACKGROUND_FNS.get(effect_name, BACKGROUND_FNS["bg_none"])
    try:
        return fn(bg, t, params)
    except Exception:
        return bg


# ══════════════════════════════════════════════════════
#  HELPER: HSV to RGB
# ══════════════════════════════════════════════════════

def _hsv_to_rgb(h: float, s: float, v: float) -> tuple[float, float, float]:
    """Convert HSV (0-1 range) to RGB (0-1 range)."""
    if s == 0:
        return v, v, v
    i = int(h * 6.0)
    f = (h * 6.0) - i
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))
    i %= 6
    if i == 0: return v, t, p
    if i == 1: return q, v, p
    if i == 2: return p, v, t
    if i == 3: return p, q, v
    if i == 4: return t, p, v
    return v, p, q


# ══════════════════════════════════════════════════════
#  UNIFIED EFFECT APPLICATOR
# ══════════════════════════════════════════════════════

def apply_text_layer_transform(
    text_img: Image.Image,
    transform: dict,
    dest_x: int,
    dest_y: int,
) -> tuple[Image.Image, int, int]:
    """
    Apply transform dict to a text overlay image.
    Returns (transformed_image, final_x, final_y).
    """
    img = text_img
    x = dest_x + transform.get("x_offset", 0)
    y = dest_y + transform.get("y_offset", 0)

    alpha = transform.get("alpha", 1.0)
    scale = transform.get("scale", 1.0)
    rotation = transform.get("rotation", 0.0)
    blur = transform.get("blur", 0)
    y_scale = transform.get("y_scale", 1.0)

    # Scale
    if abs(scale - 1.0) > 0.02 or abs(y_scale - 1.0) > 0.02:
        nw = max(1, int(img.width * scale))
        nh = max(1, int(img.height * scale * y_scale))
        img = img.resize((nw, nh), Image.LANCZOS)
        # Adjust position for scale
        x -= (nw - text_img.width) // 2
        y -= (nh - text_img.height) // 2

    # Rotation
    if abs(rotation) > 0.5:
        img = img.rotate(-rotation, resample=Image.BICUBIC, expand=False)

    # Blur
    if blur > 0:
        img = img.filter(ImageFilter.GaussianBlur(radius=blur))

    # Alpha
    if alpha < 1.0:
        if img.mode == "RGBA":
            r, g, b, a = img.split()
            a_arr = np.array(a, dtype=np.float32) * alpha
            img.putalpha(Image.fromarray(a_arr.astype(np.uint8)))
        else:
            # Convert to RGBA and apply
            img = img.convert("RGBA")
            r, g, b, a = img.split()
            a_arr = np.array(a, dtype=np.float32) * alpha
            img.putalpha(Image.fromarray(a_arr.astype(np.uint8)))

    return img, x, y
