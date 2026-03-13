"""
Project HER v2.0 – Comprehensive Effects Catalog
================================================
Complete registry of ALL visual effects available for video generation.
This catalog is the "menu" that the AI VFX Agent selects from.

Every effect is registered with:
  - name: unique identifier
  - category: text_entry | text_exit | text_continuous | text_per_char |
              text_style | scene_transition | image_effect | image_entry |
              image_exit | background_effect | overlay_effect | motion_graphic
  - description: what it does (used by the AI agent for decision-making)
  - mood_tags: emotions/contexts where this effect fits best
  - intensity: 1-5 scale (1 = subtle, 5 = dramatic)
  - parameters: tunable params with defaults
  - compatible_with: what it can be combined with

Inspired by Remotion (React video) capabilities, implemented natively in
Python using PIL, numpy, and math for our MoviePy frame-by-frame renderer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ══════════════════════════════════════════════════════
#  EFFECT DEFINITION
# ══════════════════════════════════════════════════════

@dataclass
class EffectParam:
    """A tunable parameter for an effect."""
    name: str
    description: str
    default: Any
    min_val: Any = None
    max_val: Any = None
    param_type: str = "float"  # float | int | str | bool | color


@dataclass
class EffectDefinition:
    """Complete definition of a visual effect."""
    name: str
    category: str
    description: str
    mood_tags: list[str] = field(default_factory=list)
    intensity: int = 3                  # 1=subtle, 5=dramatic
    parameters: list[EffectParam] = field(default_factory=list)
    compatible_with: list[str] = field(default_factory=list)
    performance_cost: int = 2           # 1=cheap, 5=expensive


@dataclass
class ScreenEffectsPlan:
    """Effects plan for a single screen — output of the VFX Agent."""
    screen_index: int
    text_entry: str = "fade_in"
    text_exit: str = "fade_out"
    text_continuous: str = "none"
    text_per_char: str = "none"
    text_style: str = "none"
    image_entry: str = "scale_bounce"
    image_exit: str = "fade_out"
    image_effect: str = "ken_burns"
    transition_in: str = "crossfade"
    transition_out: str = "crossfade"
    background_effect: str = "none"
    overlay_effect: str = "none"
    motion_graphic: str = "none"
    # Parameter overrides for each effect (effect_name → {param: value})
    params: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Agent reasoning (for debugging / logging)
    reasoning: str = ""


@dataclass
class VideoEffectsPlan:
    """Complete effects plan for the entire video."""
    screens: list[ScreenEffectsPlan] = field(default_factory=list)
    global_overlay: str = "subtle_grain"
    global_color_mood: str = "neutral"   # warm | cool | neutral | dramatic | vintage
    pacing: str = "medium"               # slow | medium | fast | dynamic
    overall_reasoning: str = ""


# ══════════════════════════════════════════════════════
#  EFFECT REGISTRY
# ══════════════════════════════════════════════════════

class EffectsCatalog:
    """
    Central registry of all available effects.
    The AI VFX Agent queries this to understand what's available
    and make intelligent choices.
    """

    def __init__(self):
        self._effects: dict[str, EffectDefinition] = {}
        self._register_all()

    def get(self, name: str) -> EffectDefinition | None:
        return self._effects.get(name)

    def get_by_category(self, category: str) -> list[EffectDefinition]:
        return [e for e in self._effects.values() if e.category == category]

    def get_by_mood(self, mood: str) -> list[EffectDefinition]:
        return [e for e in self._effects.values() if mood in e.mood_tags]

    def get_names_by_category(self, category: str) -> list[str]:
        return [e.name for e in self._effects.values() if e.category == category]

    def all_effects(self) -> list[EffectDefinition]:
        return list(self._effects.values())

    def categories(self) -> list[str]:
        return sorted(set(e.category for e in self._effects.values()))

    def to_agent_prompt(self) -> str:
        """Generate a structured prompt describing all effects for the AI agent."""
        lines = ["# Available Visual Effects Library\n"]
        for cat in self.categories():
            effects = self.get_by_category(cat)
            lines.append(f"\n## {cat.replace('_', ' ').title()} ({len(effects)} effects)")
            for e in effects:
                moods = ", ".join(e.mood_tags[:5]) if e.mood_tags else "general"
                lines.append(f"  - **{e.name}**: {e.description} [intensity: {e.intensity}/5, moods: {moods}]")
        return "\n".join(lines)

    def _register(self, effect: EffectDefinition):
        self._effects[effect.name] = effect

    def _register_all(self):
        """Register every single effect in the library."""
        self._register_text_entry_effects()
        self._register_text_exit_effects()
        self._register_text_continuous_effects()
        self._register_text_per_char_effects()
        self._register_text_style_effects()
        self._register_scene_transitions()
        self._register_image_entry_effects()
        self._register_image_exit_effects()
        self._register_image_effects()
        self._register_background_effects()
        self._register_overlay_effects()
        self._register_motion_graphics()

    # ──────────────────────────────────────────────────
    #  1. TEXT ENTRY ANIMATIONS (how text appears)
    # ──────────────────────────────────────────────────

    def _register_text_entry_effects(self):
        self._register(EffectDefinition(
            name="fade_in",
            category="text_entry",
            description="Text fades in from transparent to full opacity",
            mood_tags=["calm", "elegant", "neutral", "professional", "sad"],
            intensity=1,
            parameters=[
                EffectParam("duration", "Fade duration in seconds", 0.5, 0.1, 2.0),
            ],
        ))
        self._register(EffectDefinition(
            name="slide_up",
            category="text_entry",
            description="Text slides upward into position from below the frame",
            mood_tags=["modern", "energetic", "news", "informative"],
            intensity=2,
            parameters=[
                EffectParam("duration", "Slide duration", 0.4, 0.1, 1.5),
                EffectParam("distance", "Slide distance multiplier", 0.12, 0.05, 0.3),
                EffectParam("easing", "Easing function", "ease_out_cubic", param_type="str"),
            ],
        ))
        self._register(EffectDefinition(
            name="slide_down",
            category="text_entry",
            description="Text descends from above into position",
            mood_tags=["ominous", "dramatic", "casual", "playful"],
            intensity=2,
            parameters=[
                EffectParam("duration", "Slide duration", 0.4, 0.1, 1.5),
                EffectParam("distance", "Slide distance multiplier", 0.12, 0.05, 0.3),
            ],
        ))
        self._register(EffectDefinition(
            name="slide_left",
            category="text_entry",
            description="Text enters from the right side of the screen",
            mood_tags=["action", "fast", "modern", "tech"],
            intensity=2,
            parameters=[
                EffectParam("duration", "Slide duration", 0.35, 0.1, 1.0),
            ],
        ))
        self._register(EffectDefinition(
            name="slide_right",
            category="text_entry",
            description="Text enters from the left side of the screen",
            mood_tags=["action", "fast", "modern", "tech"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="scale_bounce",
            category="text_entry",
            description="Text pops in from 0% scale with elastic overshoot (bouncy entrance)",
            mood_tags=["playful", "energetic", "fun", "surprising", "exciting"],
            intensity=3,
            parameters=[
                EffectParam("duration", "Bounce duration", 0.35, 0.15, 0.8),
                EffectParam("overshoot", "Overshoot amount (1.0 = no overshoot)", 1.15, 1.0, 1.4),
            ],
        ))
        self._register(EffectDefinition(
            name="elastic_drop",
            category="text_entry",
            description="Text drops in from above with elastic bounce at landing",
            mood_tags=["playful", "fun", "impact", "surprise", "cartoon"],
            intensity=4,
            parameters=[
                EffectParam("duration", "Drop duration", 0.5, 0.2, 1.0),
                EffectParam("bounce_count", "Number of bounces", 2, 1, 4, "int"),
            ],
        ))
        self._register(EffectDefinition(
            name="blur_reveal",
            category="text_entry",
            description="Text starts blurry and sharpens into focus (depth-of-field effect)",
            mood_tags=["cinematic", "dreamy", "mysterious", "elegant", "documentary"],
            intensity=2,
            parameters=[
                EffectParam("duration", "Reveal duration", 0.6, 0.2, 1.5),
                EffectParam("max_blur", "Starting blur radius", 12, 4, 30, "int"),
            ],
        ))
        self._register(EffectDefinition(
            name="typewriter",
            category="text_entry",
            description="Characters appear one by one like being typed, with cursor blink",
            mood_tags=["tech", "hacker", "retro", "documentary", "news", "mysterious"],
            intensity=2,
            parameters=[
                EffectParam("char_delay", "Delay between characters (seconds)", 0.04, 0.01, 0.15),
                EffectParam("show_cursor", "Show blinking cursor", True, param_type="bool"),
            ],
        ))
        self._register(EffectDefinition(
            name="glitch_in",
            category="text_entry",
            description="Text appears with digital glitch/distortion effect — RGB split, scanlines, jitter",
            mood_tags=["tech", "cyberpunk", "hacker", "error", "dramatic", "digital", "intense"],
            intensity=4,
            parameters=[
                EffectParam("duration", "Glitch duration", 0.3, 0.1, 0.8),
                EffectParam("rgb_offset", "RGB channel offset in pixels", 8, 2, 20, "int"),
                EffectParam("jitter", "Position jitter amount", 5, 1, 15, "int"),
            ],
        ))
        self._register(EffectDefinition(
            name="wave_in",
            category="text_entry",
            description="Text enters with a wave/ripple motion — letters undulate into place",
            mood_tags=["fluid", "ocean", "dreamy", "calm", "organic", "nature"],
            intensity=3,
            parameters=[
                EffectParam("duration", "Wave animation duration", 0.6, 0.2, 1.5),
                EffectParam("amplitude", "Wave height in pixels", 15, 5, 40, "int"),
                EffectParam("frequency", "Wave cycles", 2.0, 0.5, 5.0),
            ],
        ))
        self._register(EffectDefinition(
            name="spiral_in",
            category="text_entry",
            description="Text spirals inward from a large orbit to its final position",
            mood_tags=["magical", "fantasy", "cosmic", "dramatic", "creative"],
            intensity=4,
            parameters=[
                EffectParam("duration", "Spiral duration", 0.7, 0.3, 1.5),
                EffectParam("rotations", "Number of spiral rotations", 1.5, 0.5, 3.0),
            ],
        ))
        self._register(EffectDefinition(
            name="flip_in",
            category="text_entry",
            description="Text flips in like a card turning over (3D rotation around X axis)",
            mood_tags=["playful", "reveal", "surprise", "modern", "sleek"],
            intensity=3,
            parameters=[
                EffectParam("duration", "Flip duration", 0.4, 0.2, 1.0),
                EffectParam("axis", "Rotation axis (x or y)", "x", param_type="str"),
            ],
        ))
        self._register(EffectDefinition(
            name="explode_in",
            category="text_entry",
            description="Text characters fly in from random directions and assemble into words",
            mood_tags=["explosion", "action", "war", "impact", "chaotic", "energetic", "intense"],
            intensity=5,
            parameters=[
                EffectParam("duration", "Assembly duration", 0.6, 0.3, 1.2),
                EffectParam("scatter_radius", "How far chars scatter from", 200, 50, 500, "int"),
            ],
        ))
        self._register(EffectDefinition(
            name="dissolve_in",
            category="text_entry",
            description="Text materializes from pixel dust/particles",
            mood_tags=["magical", "mystical", "sci-fi", "transformation", "fantasy"],
            intensity=3,
            parameters=[
                EffectParam("duration", "Dissolve duration", 0.8, 0.3, 2.0),
                EffectParam("particle_size", "Size of dissolve particles", 3, 1, 8, "int"),
            ],
        ))
        self._register(EffectDefinition(
            name="split_reveal",
            category="text_entry",
            description="Text is split horizontally — top half slides up, bottom half slides down to reveal",
            mood_tags=["dramatic", "cinematic", "reveal", "epic", "movie"],
            intensity=3,
            parameters=[
                EffectParam("duration", "Split animation duration", 0.5, 0.2, 1.0),
                EffectParam("gap", "Max gap between halves in pixels", 30, 10, 60, "int"),
            ],
        ))
        self._register(EffectDefinition(
            name="zoom_blur_in",
            category="text_entry",
            description="Text zooms in from far away with radial motion blur",
            mood_tags=["impact", "dramatic", "action", "speed", "intense"],
            intensity=4,
            parameters=[
                EffectParam("duration", "Zoom duration", 0.4, 0.2, 1.0),
                EffectParam("start_scale", "Starting scale factor", 3.0, 1.5, 8.0),
            ],
        ))
        self._register(EffectDefinition(
            name="stamp_in",
            category="text_entry",
            description="Text stamps down hard with impact shake — like a rubber stamp hitting paper",
            mood_tags=["impact", "authority", "news", "announcement", "important", "bold"],
            intensity=4,
            parameters=[
                EffectParam("duration", "Stamp duration", 0.25, 0.1, 0.5),
                EffectParam("shake_amount", "Screen shake pixels", 6, 2, 15, "int"),
            ],
        ))
        self._register(EffectDefinition(
            name="curtain_reveal",
            category="text_entry",
            description="Text revealed by a curtain/wipe from one side",
            mood_tags=["theatrical", "reveal", "dramatic", "elegant", "announcement"],
            intensity=2,
            parameters=[
                EffectParam("duration", "Wipe duration", 0.5, 0.2, 1.2),
                EffectParam("direction", "Wipe direction", "left_to_right", param_type="str"),
            ],
        ))
        self._register(EffectDefinition(
            name="grow_from_center",
            category="text_entry",
            description="Text grows outward from center point like expanding from a seed",
            mood_tags=["organic", "growth", "science", "nature", "life"],
            intensity=2,
            parameters=[
                EffectParam("duration", "Growth duration", 0.5, 0.2, 1.0),
            ],
        ))
        self._register(EffectDefinition(
            name="matrix_rain",
            category="text_entry",
            description="Characters rain down from top in Matrix-style digital rain before forming words",
            mood_tags=["tech", "hacker", "cyber", "digital", "sci-fi", "matrix"],
            intensity=5,
            parameters=[
                EffectParam("duration", "Rain formation duration", 0.8, 0.4, 2.0),
                EffectParam("rain_speed", "Speed of falling characters", 1.5, 0.5, 3.0),
            ],
        ))
        self._register(EffectDefinition(
            name="smoke_reveal",
            category="text_entry",
            description="Text appears through dispersing smoke/fog",
            mood_tags=["mysterious", "dramatic", "horror", "dark", "atmospheric"],
            intensity=3,
            parameters=[
                EffectParam("duration", "Smoke dissipation time", 0.8, 0.3, 2.0),
            ],
        ))

    # ──────────────────────────────────────────────────
    #  2. TEXT EXIT ANIMATIONS (how text disappears)
    # ──────────────────────────────────────────────────

    def _register_text_exit_effects(self):
        self._register(EffectDefinition(
            name="fade_out",
            category="text_exit",
            description="Text fades from full opacity to transparent",
            mood_tags=["calm", "elegant", "neutral", "sad", "gentle"],
            intensity=1,
            parameters=[
                EffectParam("duration", "Fade duration", 0.4, 0.1, 1.5),
            ],
        ))
        self._register(EffectDefinition(
            name="slide_out_up",
            category="text_exit",
            description="Text slides upward and off screen",
            mood_tags=["modern", "clean", "news", "informative"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="slide_out_down",
            category="text_exit",
            description="Text drops downward off screen",
            mood_tags=["casual", "playful", "gravity"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="slide_out_left",
            category="text_exit",
            description="Text flies off to the left",
            mood_tags=["action", "fast", "departure"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="slide_out_right",
            category="text_exit",
            description="Text flies off to the right",
            mood_tags=["action", "fast", "departure"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="scale_shrink",
            category="text_exit",
            description="Text shrinks down to nothing at center",
            mood_tags=["clean", "minimalist", "tech"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="blur_exit",
            category="text_exit",
            description="Text blurs out of focus and fades — like defocusing a camera",
            mood_tags=["cinematic", "dreamy", "transition", "elegant"],
            intensity=2,
            parameters=[
                EffectParam("duration", "Blur-out duration", 0.4, 0.1, 1.0),
                EffectParam("max_blur", "Final blur radius", 15, 5, 30, "int"),
            ],
        ))
        self._register(EffectDefinition(
            name="explode_out",
            category="text_exit",
            description="Text shatters/explodes — characters fly apart in random directions",
            mood_tags=["explosion", "destruction", "chaotic", "action", "intense", "war"],
            intensity=5,
            parameters=[
                EffectParam("duration", "Explosion duration", 0.4, 0.2, 1.0),
                EffectParam("scatter_radius", "How far chars scatter", 300, 50, 600, "int"),
            ],
        ))
        self._register(EffectDefinition(
            name="dissolve_out",
            category="text_exit",
            description="Text breaks apart into fading pixels/particles",
            mood_tags=["magical", "sci-fi", "transformation", "vanish"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="flip_out",
            category="text_exit",
            description="Text flips away like a card turning over",
            mood_tags=["playful", "sleek", "modern"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="flick_off",
            category="text_exit",
            description="Text is flicked sideways with directional blur — snappy exit",
            mood_tags=["energetic", "snappy", "fun", "fast"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="evaporate",
            category="text_exit",
            description="Text rises and dissolves upward like steam evaporating",
            mood_tags=["ethereal", "spiritual", "dreamy", "heat", "transformation"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="crumble",
            category="text_exit",
            description="Text crumbles/collapses downward like a building demolition",
            mood_tags=["destruction", "heavy", "dramatic", "war", "collapse"],
            intensity=4,
        ))
        self._register(EffectDefinition(
            name="swipe_wipe",
            category="text_exit",
            description="A wipe bar sweeps across erasing the text",
            mood_tags=["clean", "professional", "transition", "news"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="vortex_out",
            category="text_exit",
            description="Text spirals outward and vanishes into a vortex",
            mood_tags=["cosmic", "magical", "fantasy", "portal", "space"],
            intensity=4,
        ))
        self._register(EffectDefinition(
            name="glitch_out",
            category="text_exit",
            description="Text exits with digital glitch distortion — RGB split, scanline corruption",
            mood_tags=["tech", "cyberpunk", "error", "digital", "intense"],
            intensity=4,
        ))

    # ──────────────────────────────────────────────────
    #  3. TEXT CONTINUOUS ANIMATIONS (while text is visible)
    # ──────────────────────────────────────────────────

    def _register_text_continuous_effects(self):
        self._register(EffectDefinition(
            name="none",
            category="text_continuous",
            description="No continuous animation — text stays perfectly still",
            mood_tags=["calm", "professional", "news", "serious"],
            intensity=0,
        ))
        self._register(EffectDefinition(
            name="glow_pulse",
            category="text_continuous",
            description="Text gently pulses with a soft glow — like breathing light",
            mood_tags=["magical", "spiritual", "ethereal", "calm", "dreamy", "ambient"],
            intensity=1,
            parameters=[
                EffectParam("frequency", "Pulse cycles per second", 0.8, 0.2, 3.0),
                EffectParam("min_glow", "Minimum glow opacity", 0.0),
                EffectParam("max_glow", "Maximum glow opacity", 0.4),
            ],
        ))
        self._register(EffectDefinition(
            name="wave_motion",
            category="text_continuous",
            description="Text gently undulates with a wave motion — letters bob up and down",
            mood_tags=["ocean", "fluid", "calm", "dreamy", "whimsical", "water"],
            intensity=2,
            parameters=[
                EffectParam("amplitude", "Wave height in pixels", 4, 1, 15, "int"),
                EffectParam("frequency", "Wave speed", 1.5, 0.3, 4.0),
            ],
        ))
        self._register(EffectDefinition(
            name="wobble",
            category="text_continuous",
            description="Text wobbles/wiggles continuously — jelly-like motion",
            mood_tags=["playful", "fun", "cartoon", "silly", "whimsical"],
            intensity=2,
            parameters=[
                EffectParam("amount", "Wobble amount", 3, 1, 10, "int"),
                EffectParam("frequency", "Wobble speed", 2.0, 0.5, 5.0),
            ],
        ))
        self._register(EffectDefinition(
            name="color_cycle",
            category="text_continuous",
            description="Text color smoothly cycles through a palette",
            mood_tags=["creative", "artistic", "psychedelic", "party", "celebration"],
            intensity=3,
            parameters=[
                EffectParam("speed", "Cycle speed in Hz", 0.3, 0.1, 2.0),
                EffectParam("palette", "Color palette name", "rainbow", param_type="str"),
            ],
        ))
        self._register(EffectDefinition(
            name="bounce",
            category="text_continuous",
            description="Text bounces up and down rhythmically",
            mood_tags=["energetic", "fun", "music", "playful", "exciting"],
            intensity=2,
            parameters=[
                EffectParam("height", "Bounce height in pixels", 6, 2, 20, "int"),
                EffectParam("frequency", "Bounce speed in Hz", 2.0, 0.5, 5.0),
            ],
        ))
        self._register(EffectDefinition(
            name="float_drift",
            category="text_continuous",
            description="Text gently floats/drifts like an object in zero gravity",
            mood_tags=["space", "dreamy", "weightless", "ethereal", "sci-fi", "calm"],
            intensity=1,
            parameters=[
                EffectParam("range_x", "Horizontal drift range", 5, 1, 15, "int"),
                EffectParam("range_y", "Vertical drift range", 3, 1, 10, "int"),
                EffectParam("speed", "Drift speed", 0.5, 0.1, 2.0),
            ],
        ))
        self._register(EffectDefinition(
            name="shake",
            category="text_continuous",
            description="Text shakes/vibrates intensely — conveying urgency or fear",
            mood_tags=["fear", "urgent", "earthquake", "danger", "intense", "horror", "anger"],
            intensity=4,
            parameters=[
                EffectParam("intensity", "Shake strength", 3, 1, 10, "int"),
                EffectParam("frequency", "Shake frequency", 20, 5, 60, "int"),
            ],
        ))
        self._register(EffectDefinition(
            name="heartbeat",
            category="text_continuous",
            description="Text pulses with a heartbeat rhythm — two quick beats then pause",
            mood_tags=["suspense", "horror", "health", "emotional", "intense", "life"],
            intensity=3,
            parameters=[
                EffectParam("bpm", "Beats per minute", 72, 40, 180, "int"),
                EffectParam("scale_amount", "Scale change per beat", 0.05, 0.02, 0.15),
            ],
        ))
        self._register(EffectDefinition(
            name="flicker",
            category="text_continuous",
            description="Text flickers on/off like a broken neon sign",
            mood_tags=["horror", "dark", "broken", "urban", "noir", "tension"],
            intensity=3,
            parameters=[
                EffectParam("frequency", "Flicker rate Hz", 8, 2, 30, "int"),
                EffectParam("min_alpha", "Minimum visibility", 0.3, 0.0, 0.8),
            ],
        ))
        self._register(EffectDefinition(
            name="pendulum",
            category="text_continuous",
            description="Text swings side to side like a pendulum",
            mood_tags=["hypnotic", "mysterious", "time", "tick-tock", "elegant"],
            intensity=2,
            parameters=[
                EffectParam("angle", "Maximum swing angle in degrees", 5, 1, 20, "int"),
                EffectParam("speed", "Swing speed", 1.0, 0.3, 3.0),
            ],
        ))
        self._register(EffectDefinition(
            name="breathe",
            category="text_continuous",
            description="Text slowly scales up and down like breathing — very subtle",
            mood_tags=["calm", "meditation", "organic", "gentle", "relaxing"],
            intensity=1,
            parameters=[
                EffectParam("scale_range", "Scale variation (e.g. 0.03 = ±3%)", 0.03, 0.01, 0.1),
                EffectParam("speed", "Breathing rate", 0.4, 0.1, 1.5),
            ],
        ))
        self._register(EffectDefinition(
            name="scan_line",
            category="text_continuous",
            description="A light scan line moves across the text periodically",
            mood_tags=["tech", "sci-fi", "futuristic", "digital", "hacker"],
            intensity=2,
            parameters=[
                EffectParam("speed", "Scan speed", 1.0, 0.3, 3.0),
                EffectParam("width", "Scan line width", 30, 10, 80, "int"),
            ],
        ))
        self._register(EffectDefinition(
            name="fire_flicker",
            category="text_continuous",
            description="Text colors shift between warm fire tones with flickering",
            mood_tags=["fire", "warm", "cozy", "danger", "passion", "intense"],
            intensity=3,
            parameters=[
                EffectParam("intensity", "Flicker strength", 0.5, 0.1, 1.0),
            ],
        ))
        self._register(EffectDefinition(
            name="electric_arc",
            category="text_continuous",
            description="Electric sparks/arcs occasionally jump across and along the text",
            mood_tags=["electric", "energy", "power", "storm", "tech", "intense"],
            intensity=4,
        ))

    # ──────────────────────────────────────────────────
    #  4. TEXT PER-CHARACTER ANIMATIONS
    # ──────────────────────────────────────────────────

    def _register_text_per_char_effects(self):
        self._register(EffectDefinition(
            name="cascade",
            category="text_per_char",
            description="Characters appear one by one in a cascading wave from left to right",
            mood_tags=["elegant", "reveal", "documentary", "cinematic"],
            intensity=2,
            parameters=[
                EffectParam("delay", "Delay between each character", 0.03, 0.01, 0.1),
            ],
        ))
        self._register(EffectDefinition(
            name="wave_propagation",
            category="text_per_char",
            description="Each character bounces in a ripple wave — one triggers the next",
            mood_tags=["fluid", "dynamic", "ocean", "fun"],
            intensity=3,
            parameters=[
                EffectParam("wave_height", "Height of wave", 8, 2, 20, "int"),
                EffectParam("speed", "Propagation speed", 15, 5, 40, "int"),
            ],
        ))
        self._register(EffectDefinition(
            name="random_fade",
            category="text_per_char",
            description="Characters fade in at random times — scattered reveal",
            mood_tags=["mysterious", "magical", "constellation", "dreamy"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="domino",
            category="text_per_char",
            description="Characters fall in like dominoes — each pushes the next",
            mood_tags=["chain-reaction", "playful", "energetic", "mechanical"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="spin_in",
            category="text_per_char",
            description="Each character spins into place individually, staggered",
            mood_tags=["energetic", "playful", "dynamic", "fun"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="gravity_drop",
            category="text_per_char",
            description="Characters drop from above one by one with gravity physics",
            mood_tags=["physical", "impact", "mechanical", "rain"],
            intensity=3,
            parameters=[
                EffectParam("stagger", "Time between drops", 0.05, 0.02, 0.15),
            ],
        ))
        self._register(EffectDefinition(
            name="stretch_in",
            category="text_per_char",
            description="Each character stretches from zero width to normal",
            mood_tags=["abstract", "creative", "artistic", "modern"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="pop_individual",
            category="text_per_char",
            description="Each character pops in with its own bounce, staggered timing",
            mood_tags=["fun", "playful", "energetic", "celebration"],
            intensity=3,
        ))

    # ──────────────────────────────────────────────────
    #  5. TEXT STYLE EFFECTS (visual styling of text)
    # ──────────────────────────────────────────────────

    def _register_text_style_effects(self):
        self._register(EffectDefinition(
            name="gradient_fill",
            category="text_style",
            description="Text filled with a gradient color (top→bottom or left→right)",
            mood_tags=["modern", "creative", "vibrant", "stylish"],
            intensity=2,
            parameters=[
                EffectParam("color_start", "Gradient start color", (255, 100, 50), param_type="color"),
                EffectParam("color_end", "Gradient end color", (100, 50, 255), param_type="color"),
                EffectParam("direction", "Gradient direction", "vertical", param_type="str"),
            ],
        ))
        self._register(EffectDefinition(
            name="outline",
            category="text_style",
            description="Text with a colored outline/stroke around each character",
            mood_tags=["bold", "impact", "street", "comic", "modern"],
            intensity=2,
            parameters=[
                EffectParam("width", "Outline width", 2, 1, 6, "int"),
                EffectParam("color", "Outline color", (0, 0, 0), param_type="color"),
            ],
        ))
        self._register(EffectDefinition(
            name="shadow_3d",
            category="text_style",
            description="Text with deep 3D shadow giving a raised/embossed appearance",
            mood_tags=["bold", "cinematic", "dramatic", "retro"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="neon_glow",
            category="text_style",
            description="Text with neon light glow effect — bright core with colored aura",
            mood_tags=["night", "urban", "party", "cyberpunk", "neon", "nightlife"],
            intensity=3,
            parameters=[
                EffectParam("glow_color", "Neon glow color", (0, 255, 200), param_type="color"),
                EffectParam("glow_radius", "Glow spread", 8, 3, 20, "int"),
            ],
        ))
        self._register(EffectDefinition(
            name="emboss",
            category="text_style",
            description="Text with embossed/pressed effect — light on top, shadow below",
            mood_tags=["elegant", "classic", "premium", "luxury"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="metallic",
            category="text_style",
            description="Text with metallic/chrome-like gradient sheen",
            mood_tags=["premium", "luxury", "tech", "futuristic", "bold"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="retro_shadow",
            category="text_style",
            description="Text with thick retro-style offset shadow (comic book / pop art)",
            mood_tags=["retro", "comic", "pop_art", "vintage", "fun"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="frosted",
            category="text_style",
            description="Text with frosted/ice glass appearance — semi-transparent with blur",
            mood_tags=["cold", "winter", "ice", "clean", "modern", "glass"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="fire_text",
            category="text_style",
            description="Text styled with fire/flame color gradient and flicker",
            mood_tags=["fire", "hot", "danger", "explosion", "passion", "intense"],
            intensity=4,
        ))
        self._register(EffectDefinition(
            name="handwritten",
            category="text_style",
            description="Text appears with a hand-drawn/sketch style (roughened edges)",
            mood_tags=["personal", "casual", "creative", "organic", "notebook"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="hologram",
            category="text_style",
            description="Text with holographic scan lines and blue-shift transparency",
            mood_tags=["sci-fi", "futuristic", "tech", "space", "digital"],
            intensity=3,
        ))

    # ──────────────────────────────────────────────────
    #  6. SCENE TRANSITIONS (between screens)
    # ──────────────────────────────────────────────────

    def _register_scene_transitions(self):
        self._register(EffectDefinition(
            name="crossfade",
            category="scene_transition",
            description="Classic cross-dissolve — smooth blend between outgoing and incoming",
            mood_tags=["calm", "elegant", "neutral", "professional", "documentary"],
            intensity=1,
        ))
        self._register(EffectDefinition(
            name="hard_cut",
            category="scene_transition",
            description="Instant jump cut — no transition effect, immediate switch",
            mood_tags=["fast", "urgent", "news", "action", "intense"],
            intensity=1,
        ))
        self._register(EffectDefinition(
            name="slide_horizontal",
            category="scene_transition",
            description="New scene slides in from the side, pushing old scene away",
            mood_tags=["modern", "clean", "news", "informative"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="slide_vertical",
            category="scene_transition",
            description="New scene slides in from top/bottom",
            mood_tags=["modern", "social_media", "scroll"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="wipe_left",
            category="scene_transition",
            description="A wipe bar moves left-to-right revealing the new scene",
            mood_tags=["classic", "professional", "movie", "documentary"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="wipe_right",
            category="scene_transition",
            description="Wipe bar moves right-to-left",
            mood_tags=["classic", "professional", "movie", "documentary"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="wipe_diagonal",
            category="scene_transition",
            description="Diagonal wipe across the frame",
            mood_tags=["dynamic", "creative", "modern"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="circle_wipe",
            category="scene_transition",
            description="Circular iris wipe — expanding circle reveals new scene from center",
            mood_tags=["classic", "retro", "dramatic", "reveal", "cartoon"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="diamond_wipe",
            category="scene_transition",
            description="Diamond-shaped mask wipe from center",
            mood_tags=["creative", "geometric", "elegant", "modern"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="clock_wipe",
            category="scene_transition",
            description="Rotational wipe like a clock hand sweeping around",
            mood_tags=["time", "historical", "retro", "classic"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="zoom_in",
            category="scene_transition",
            description="Camera zooms into the scene, old scene falls behind",
            mood_tags=["dramatic", "focus", "close-up", "investigation", "reveal"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="zoom_out",
            category="scene_transition",
            description="Camera pulls back/zooms out revealing the new wider scene",
            mood_tags=["establishing", "reveal", "epic", "discovery"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="spin_transition",
            category="scene_transition",
            description="Frame spins/rotates switching to new scene mid-rotation",
            mood_tags=["energetic", "fun", "dynamic", "dizzy", "party"],
            intensity=4,
        ))
        self._register(EffectDefinition(
            name="flip_page",
            category="scene_transition",
            description="Page flip/turn effect — like turning a book page",
            mood_tags=["story", "book", "narrative", "documentary", "educational"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="cube_rotate",
            category="scene_transition",
            description="3D cube rotation — scene is on one face of a cube rotating to show next face",
            mood_tags=["3d", "tech", "futuristic", "creative", "modern"],
            intensity=4,
        ))
        self._register(EffectDefinition(
            name="morph",
            category="scene_transition",
            description="Organic morph/blend between scenes using displacement",
            mood_tags=["dreamy", "creative", "artistic", "fluid", "organic"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="glitch_transition",
            category="scene_transition",
            description="Digital glitch distortion with RGB split and jitter between scenes",
            mood_tags=["tech", "cyberpunk", "error", "intense", "digital"],
            intensity=4,
        ))
        self._register(EffectDefinition(
            name="whip_pan",
            category="scene_transition",
            description="Fast camera whip pan with motion blur — sweeps to next scene",
            mood_tags=["fast", "action", "energetic", "documentary", "travel"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="blur_transition",
            category="scene_transition",
            description="Current scene blurs out, new scene blurs in — cinematic focus pull",
            mood_tags=["cinematic", "dreamy", "elegant", "artistic"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="pixelate_transition",
            category="scene_transition",
            description="Scene pixelates/mosaic before revealing next scene",
            mood_tags=["retro", "game", "digital", "creative", "8bit"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="shatter_transition",
            category="scene_transition",
            description="Scene shatters into pieces revealing the next scene behind",
            mood_tags=["dramatic", "destruction", "impact", "action", "intense"],
            intensity=5,
        ))
        self._register(EffectDefinition(
            name="ripple_transition",
            category="scene_transition",
            description="Water ripple effect — scene dissolves with concentric ripples",
            mood_tags=["water", "dreamy", "fluid", "calm", "nature"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="burn_transition",
            category="scene_transition",
            description="Old scene burns away revealing new scene",
            mood_tags=["fire", "dramatic", "destruction", "intense", "dark"],
            intensity=5,
        ))
        self._register(EffectDefinition(
            name="flash_transition",
            category="scene_transition",
            description="Bright white flash between scenes — camera flash / lightning",
            mood_tags=["impact", "photo", "lightning", "bright", "dramatic"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="ink_bleed",
            category="scene_transition",
            description="Ink bleeding/spreading across frame revealing new scene",
            mood_tags=["artistic", "dramatic", "creative", "painting", "Japanese"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="blinds_horizontal",
            category="scene_transition",
            description="Horizontal venetian blinds effect revealing new scene",
            mood_tags=["modern", "tech", "professional", "sleek"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="blinds_vertical",
            category="scene_transition",
            description="Vertical venetian blinds effect",
            mood_tags=["modern", "tech", "professional", "sleek"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="elastic_bounce",
            category="scene_transition",
            description="New scene bounces in with elastic overshoot",
            mood_tags=["playful", "fun", "bouncy", "energetic", "cartoon"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="swirl_transition",
            category="scene_transition",
            description="Scenes swirl into each other like a whirlpool",
            mood_tags=["magical", "fantasy", "portal", "cosmic", "dream"],
            intensity=4,
        ))

    # ──────────────────────────────────────────────────
    #  7. IMAGE ENTRY EFFECTS
    # ──────────────────────────────────────────────────

    def _register_image_entry_effects(self):
        self._register(EffectDefinition(
            name="img_fade_in",
            category="image_entry",
            description="Image fades in from transparent",
            mood_tags=["calm", "elegant", "gentle", "neutral"],
            intensity=1,
        ))
        self._register(EffectDefinition(
            name="img_scale_bounce",
            category="image_entry",
            description="Image pops in with elastic scale overshoot",
            mood_tags=["playful", "fun", "energetic", "surprise"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="img_slide_in",
            category="image_entry",
            description="Image slides in from a side of the screen",
            mood_tags=["modern", "clean", "news", "documentary"],
            intensity=2,
            parameters=[
                EffectParam("direction", "Slide direction", "right", param_type="str"),
            ],
        ))
        self._register(EffectDefinition(
            name="img_zoom_in",
            category="image_entry",
            description="Image starts zoomed out/small and zooms to full size",
            mood_tags=["dramatic", "reveal", "focus", "cinematic"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="img_rotate_in",
            category="image_entry",
            description="Image spins into place with decreasing rotation",
            mood_tags=["playful", "dynamic", "fun", "creative"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="img_flip_in",
            category="image_entry",
            description="Image flips in from edge like a card reveal",
            mood_tags=["reveal", "surprise", "modern", "sleek"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="img_blur_reveal",
            category="image_entry",
            description="Image starts blurry and comes into sharp focus",
            mood_tags=["cinematic", "dreamy", "atmospheric", "documentary"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="img_shutter",
            category="image_entry",
            description="Image revealed through shutters/slats opening",
            mood_tags=["dramatic", "reveal", "photography", "elegant"],
            intensity=3,
        ))

    # ──────────────────────────────────────────────────
    #  8. IMAGE EXIT EFFECTS
    # ──────────────────────────────────────────────────

    def _register_image_exit_effects(self):
        self._register(EffectDefinition(
            name="img_fade_out",
            category="image_exit",
            description="Image fades out to transparent",
            mood_tags=["calm", "gentle", "neutral", "elegant"],
            intensity=1,
        ))
        self._register(EffectDefinition(
            name="img_slide_out",
            category="image_exit",
            description="Image slides off screen to one side",
            mood_tags=["modern", "clean", "departure"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="img_scale_out",
            category="image_exit",
            description="Image shrinks down to nothing",
            mood_tags=["clean", "minimalist", "tech"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="img_blur_out",
            category="image_exit",
            description="Image goes out of focus and fades away",
            mood_tags=["cinematic", "dreamy", "transition"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="img_shatter_out",
            category="image_exit",
            description="Image shatters into fragments that scatter",
            mood_tags=["dramatic", "destruction", "action", "intense"],
            intensity=5,
        ))
        self._register(EffectDefinition(
            name="img_dissolve_out",
            category="image_exit",
            description="Image dissolves into particles/pixels",
            mood_tags=["magical", "sci-fi", "vanish", "transformation"],
            intensity=3,
        ))

    # ──────────────────────────────────────────────────
    #  9. IMAGE TREATMENT EFFECTS (during display)
    # ──────────────────────────────────────────────────

    def _register_image_effects(self):
        self._register(EffectDefinition(
            name="ken_burns",
            category="image_effect",
            description="Slow zoom + pan across image (classic documentary effect, adds life)",
            mood_tags=["documentary", "cinematic", "narrative", "historical", "calm", "elegant"],
            intensity=2,
            parameters=[
                EffectParam("zoom_range", "Zoom amount (0.05 = 5%)", 0.08, 0.02, 0.2),
                EffectParam("pan_range", "Pan distance ratio", 0.04, 0.01, 0.1),
            ],
        ))
        self._register(EffectDefinition(
            name="parallax_2d",
            category="image_effect",
            description="2D parallax — image moves slightly opposite to text for depth",
            mood_tags=["cinematic", "depth", "immersive", "modern"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="zoom_pulse",
            category="image_effect",
            description="Image subtly pulses with zoom in/out — breathing effect",
            mood_tags=["dramatic", "suspense", "intense", "emotional"],
            intensity=2,
            parameters=[
                EffectParam("amount", "Zoom pulse amount", 0.03, 0.01, 0.1),
                EffectParam("speed", "Pulse speed Hz", 0.5, 0.1, 2.0),
            ],
        ))
        self._register(EffectDefinition(
            name="tilt_shift",
            category="image_effect",
            description="Fake tilt-shift — blurs edges while keeping center sharp (miniature look)",
            mood_tags=["creative", "miniature", "cute", "dreamy", "artistic"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="vignette",
            category="image_effect",
            description="Dark vignette around image edges — draws focus to center",
            mood_tags=["cinematic", "dramatic", "focus", "vintage", "dark"],
            intensity=1,
        ))
        self._register(EffectDefinition(
            name="color_shift",
            category="image_effect",
            description="Gradual color temperature shift over the screen duration",
            mood_tags=["atmospheric", "mood", "time_passing", "artistic"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="sepia_blend",
            category="image_effect",
            description="Blend toward sepia/vintage tones over time or from edges",
            mood_tags=["vintage", "historical", "nostalgic", "old", "classic"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="glitch_overlay",
            category="image_effect",
            description="Periodic glitch artifacts on the image — digital distortion",
            mood_tags=["tech", "digital", "cyberpunk", "error", "intense"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="static_image",
            category="image_effect",
            description="No image animation — static display (saves performance)",
            mood_tags=["calm", "professional", "minimal", "serious"],
            intensity=0,
        ))
        self._register(EffectDefinition(
            name="rotation_slow",
            category="image_effect",
            description="Image very slowly rotates  — subtle continuous motion",
            mood_tags=["cosmic", "hypnotic", "dreamy", "space"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="brightness_pulse",
            category="image_effect",
            description="Image brightness subtly pulses up and down",
            mood_tags=["ethereal", "magical", "dreamy", "atmospheric"],
            intensity=1,
        ))
        self._register(EffectDefinition(
            name="desaturate_to_color",
            category="image_effect",
            description="Image starts desaturated (grayscale) and gradually gains color",
            mood_tags=["reveal", "awakening", "transformation", "dramatic", "artistic"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="split_tone",
            category="image_effect",
            description="Apply split-toning — warm highlights, cool shadows",
            mood_tags=["cinematic", "film", "artistic", "mood"],
            intensity=2,
        ))

    # ──────────────────────────────────────────────────
    #  10. BACKGROUND EFFECTS
    # ──────────────────────────────────────────────────

    def _register_background_effects(self):
        self._register(EffectDefinition(
            name="bg_none",
            category="background_effect",
            description="Static background with no animation",
            mood_tags=["calm", "professional", "minimal"],
            intensity=0,
        ))
        self._register(EffectDefinition(
            name="bg_gradient_shift",
            category="background_effect",
            description="Background gradient slowly shifts colors over time",
            mood_tags=["modern", "creative", "ambient", "calm"],
            intensity=1,
        ))
        self._register(EffectDefinition(
            name="bg_color_breathe",
            category="background_effect",
            description="Background subtly breathes between two shades",
            mood_tags=["calm", "gentle", "organic", "meditation"],
            intensity=1,
        ))
        self._register(EffectDefinition(
            name="bg_noise_movement",
            category="background_effect",
            description="Subtle noise/grain that shifts creating a living texture",
            mood_tags=["film", "vintage", "atmospheric", "dark"],
            intensity=1,
        ))
        self._register(EffectDefinition(
            name="bg_pulse",
            category="background_effect",
            description="Background subtly pulses brighter/darker with content",
            mood_tags=["dramatic", "music", "emotional", "intense"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="bg_aurora",
            category="background_effect",
            description="Slow aurora borealis-like color waves across the background",
            mood_tags=["magical", "beautiful", "nature", "cosmic", "dreamy"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="bg_particle_float",
            category="background_effect",
            description="Small glowing particles floating slowly across the background",
            mood_tags=["magical", "ethereal", "space", "dreamy", "underwater"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="bg_grid_pattern",
            category="background_effect",
            description="Animated grid/matrix pattern subtly moving behind content",
            mood_tags=["tech", "digital", "futuristic", "sci-fi"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="bg_radial_pulse",
            category="background_effect",
            description="Concentric rings pulsing outward from center",
            mood_tags=["impact", "dramatic", "radio", "sound", "energy"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="bg_wave_pattern",
            category="background_effect",
            description="Smooth wave patterns flowing across the background",
            mood_tags=["ocean", "fluid", "natural", "calm", "serene"],
            intensity=2,
        ))

    # ──────────────────────────────────────────────────
    #  11. OVERLAY EFFECTS
    # ──────────────────────────────────────────────────

    def _register_overlay_effects(self):
        self._register(EffectDefinition(
            name="overlay_none",
            category="overlay_effect",
            description="No overlay effect",
            mood_tags=["clean", "minimal", "professional"],
            intensity=0,
        ))
        self._register(EffectDefinition(
            name="subtle_grain",
            category="overlay_effect",
            description="Subtle film grain texture for cinematic feel",
            mood_tags=["cinematic", "film", "vintage", "documentary", "classic"],
            intensity=1,
        ))
        self._register(EffectDefinition(
            name="heavy_grain",
            category="overlay_effect",
            description="Heavy film grain — gritty, raw documentary look",
            mood_tags=["gritty", "raw", "documentary", "war", "intense"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="light_leak",
            category="overlay_effect",
            description="Warm light leak glow — anamorphic lens flare feel",
            mood_tags=["warm", "nostalgic", "film", "dreamy", "vintage"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="bokeh_overlay",
            category="overlay_effect",
            description="Floating bokeh (out-of-focus light circles) overlay",
            mood_tags=["dreamy", "romantic", "night", "celebration", "party"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="rain_overlay",
            category="overlay_effect",
            description="Rain drops falling across the frame",
            mood_tags=["rain", "sad", "dramatic", "storm", "dark", "noir"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="snow_overlay",
            category="overlay_effect",
            description="Snowflakes gently falling across the frame",
            mood_tags=["winter", "cold", "peaceful", "Christmas", "festive"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="dust_particles",
            category="overlay_effect",
            description="Floating dust particles catching light — old room / sunbeam effect",
            mood_tags=["nostalgic", "old", "abandoned", "atmospheric", "warm"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="smoke_overlay",
            category="overlay_effect",
            description="Wisps of smoke drifting across the frame",
            mood_tags=["mysterious", "dark", "atmospheric", "noir", "tense"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="scan_lines",
            category="overlay_effect",
            description="CRT scan line overlay — retro TV/monitor look",
            mood_tags=["retro", "80s", "VHS", "nostalgia", "tech", "vintage"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="vhs_distortion",
            category="overlay_effect",
            description="VHS tape distortion — tracking lines, color bleeding, noise",
            mood_tags=["retro", "VHS", "80s", "90s", "nostalgia", "found_footage"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="chromatic_aberration",
            category="overlay_effect",
            description="Subtle color fringing at edges — cinematic lens imperfection",
            mood_tags=["cinematic", "dramatic", "intense", "action"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="lens_flare",
            category="overlay_effect",
            description="Animated lens flare moving through the frame",
            mood_tags=["epic", "cinematic", "bright", "space", "heroic"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="sparkle_overlay",
            category="overlay_effect",
            description="Twinkling sparkle/star effects scattered across the frame",
            mood_tags=["magical", "celebration", "fantasy", "luxury", "festive"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="fire_embers",
            category="overlay_effect",
            description="Glowing embers/sparks floating upward — fire scene atmosphere",
            mood_tags=["fire", "warm", "dramatic", "destruction", "campfire"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="underwater_caustics",
            category="overlay_effect",
            description="Light caustic patterns like sun through water",
            mood_tags=["underwater", "ocean", "pool", "dreamy", "aquatic"],
            intensity=2,
        ))

    # ──────────────────────────────────────────────────
    #  12. MOTION GRAPHICS
    # ──────────────────────────────────────────────────

    def _register_motion_graphics(self):
        self._register(EffectDefinition(
            name="mg_none",
            category="motion_graphic",
            description="No motion graphic overlay",
            mood_tags=["minimal", "clean"],
            intensity=0,
        ))
        self._register(EffectDefinition(
            name="Lower_third",
            category="motion_graphic",
            description="Animated lower-third name/topic banner sliding in",
            mood_tags=["news", "documentary", "professional", "informative"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="progress_bar",
            category="motion_graphic",
            description="A progress indicator showing position in the video",
            mood_tags=["informative", "tutorial", "educational"],
            intensity=1,
        ))
        self._register(EffectDefinition(
            name="animated_border",
            category="motion_graphic",
            description="Animated decorative border or frame around the content",
            mood_tags=["elegant", "decorative", "premium", "vintage"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="floating_icons",
            category="motion_graphic",
            description="Small thematic icons floating in the background (stars, hearts, etc)",
            mood_tags=["fun", "social_media", "celebration", "casual"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="kinetic_lines",
            category="motion_graphic",
            description="Speed/motion lines radiating from center — manga/anime style impact",
            mood_tags=["action", "impact", "anime", "energetic", "dramatic"],
            intensity=3,
        ))
        self._register(EffectDefinition(
            name="pulse_rings",
            category="motion_graphic",
            description="Concentric circles pulsing outward from speaker/content",
            mood_tags=["podcast", "speech", "music", "radio", "waves"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="countdown_timer",
            category="motion_graphic",
            description="Visible countdown or timer display",
            mood_tags=["urgency", "countdown", "suspense", "competition"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="geometric_shapes",
            category="motion_graphic",
            description="Animated geometric shapes (circles, triangles) as decorative elements",
            mood_tags=["modern", "abstract", "creative", "tech", "design"],
            intensity=2,
        ))
        self._register(EffectDefinition(
            name="wave_equalizer",
            category="motion_graphic",
            description="Audio wave/equalizer visualization at bottom of screen",
            mood_tags=["music", "podcast", "audio", "beats", "radio"],
            intensity=2,
        ))


# ══════════════════════════════════════════════════════
#  SINGLETON INSTANCE
# ══════════════════════════════════════════════════════

# Global catalog instance — initialized once, used by the VFX agent
EFFECTS_CATALOG = EffectsCatalog()
