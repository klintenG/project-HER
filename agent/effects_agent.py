"""
Project HER v2.0 – VFX Decision Agent
======================================
AI agent powered by Claude Opus 4.6 (via Copilot Bridge) that
intelligently decides which effects to apply to each scene in the video.

For every screen segment, the agent analyses:
  - Emotion / mood of the content
  - Scene type (intro, action, reveal, etc.)
  - Visual type (image, text_only, multi_image)
  - Text content (detects keywords like "explosion", "calm", "mystery")
  - Narrative position in the video (beginning, middle, end)

And outputs a structured effects plan:
  - Text entry effect + params
  - Text exit effect + params
  - Text continuous effect + params
  - Image entry effect + params
  - Image treatment during display
  - Image exit effect + params
  - Scene transition to next scene
  - Overlay effects
  - Background effects
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("effects_agent")

# Model for VFX decisions — Claude Opus 4.6 via Copilot Bridge
VFX_AGENT_MODEL = "claude-opus-4.6"


# ── Data Classes ──────────────────────────────────────

@dataclass
class SceneEffectsPlan:
    """Complete effects plan for a single screen/scene."""
    screen_index: int

    # Text effects
    text_entry: str = "fade_in"
    text_entry_params: dict = field(default_factory=dict)
    text_exit: str = "fade_out"
    text_exit_params: dict = field(default_factory=dict)
    text_continuous: str = "none"
    text_continuous_params: dict = field(default_factory=dict)

    # Image effects
    image_entry: str = "img_fade_in"
    image_entry_params: dict = field(default_factory=dict)
    image_treatment: str = "ken_burns"
    image_treatment_params: dict = field(default_factory=dict)
    image_exit: str = "img_fade_out"
    image_exit_params: dict = field(default_factory=dict)

    # Scene transition (to next scene)
    scene_transition: str = "crossfade"
    scene_transition_params: dict = field(default_factory=dict)

    # Overlays
    overlay_effect: str = "overlay_none"
    overlay_params: dict = field(default_factory=dict)

    # Background
    background_effect: str = "bg_none"
    background_params: dict = field(default_factory=dict)

    # Emphasis word animation
    emphasis_style: str = "scale_bounce"
    emphasis_params: dict = field(default_factory=dict)

    # Agent reasoning (for debugging)
    reasoning: str = ""


@dataclass
class VideoEffectsPlan:
    """Complete effects plan for the entire video."""
    scenes: list[SceneEffectsPlan] = field(default_factory=list)
    overall_mood: str = "neutral"
    visual_theme: str = "dynamic"


# ── Emotion-to-Effect Mapping (Fallback) ─────────────

EMOTION_PRESETS: dict[str, dict] = {
    "excitement": {
        "text_entry": "scale_bounce",
        "text_exit": "explode_out",
        "text_continuous": "shake",
        "image_entry": "img_scale_bounce",
        "image_treatment": "zoom_pulse",
        "scene_transition": "flash_transition",
        "overlay_effect": "sparkle_overlay",
        "background_effect": "bg_pulse",
    },
    "suspense": {
        "text_entry": "blur_reveal",
        "text_exit": "evaporate",
        "text_continuous": "flicker",
        "image_entry": "img_blur_reveal",
        "image_treatment": "ken_burns",
        "scene_transition": "blur_transition",
        "overlay_effect": "subtle_grain",
        "background_effect": "bg_color_breathe",
    },
    "dramatic": {
        "text_entry": "stamp_in",
        "text_exit": "swipe_wipe",
        "text_continuous": "glow_pulse",
        "image_entry": "img_scale_bounce",
        "image_treatment": "zoom_pulse",
        "scene_transition": "flash_transition",
        "overlay_effect": "fire_embers",
        "background_effect": "bg_pulse",
    },
    "thoughtful": {
        "text_entry": "fade_in",
        "text_exit": "dissolve_out",
        "text_continuous": "breathe",
        "image_entry": "img_fade_in",
        "image_treatment": "ken_burns",
        "scene_transition": "crossfade",
        "overlay_effect": "bokeh_overlay",
        "background_effect": "bg_color_breathe",
    },
    "informative": {
        "text_entry": "slide_up",
        "text_exit": "slide_out_down",
        "text_continuous": "none",
        "image_entry": "img_fade_in",
        "image_treatment": "ken_burns",
        "scene_transition": "slide_horizontal",
        "overlay_effect": "subtle_grain",
        "background_effect": "bg_gradient_shift",
    },
    "urgent": {
        "text_entry": "glitch_in",
        "text_exit": "explode_out",
        "text_continuous": "shake",
        "image_entry": "img_scale_bounce",
        "image_treatment": "color_shift",
        "scene_transition": "flash_transition",
        "overlay_effect": "chromatic_aberration",
        "background_effect": "bg_pulse",
    },
    "calm": {
        "text_entry": "fade_in",
        "text_exit": "fade_out",
        "text_continuous": "breathe",
        "image_entry": "img_fade_in",
        "image_treatment": "ken_burns",
        "scene_transition": "crossfade",
        "overlay_effect": "bokeh_overlay",
        "background_effect": "bg_color_breathe",
    },
    "sadness": {
        "text_entry": "slide_up",
        "text_exit": "evaporate",
        "text_continuous": "wave_motion",
        "image_entry": "img_fade_in",
        "image_treatment": "desaturate_to_color",
        "scene_transition": "crossfade",
        "overlay_effect": "rain_overlay",
        "background_effect": "bg_color_breathe",
    },
    "anger": {
        "text_entry": "stamp_in",
        "text_exit": "explode_out",
        "text_continuous": "shake",
        "image_entry": "img_scale_bounce",
        "image_treatment": "color_shift",
        "scene_transition": "flash_transition",
        "overlay_effect": "fire_embers",
        "background_effect": "bg_pulse",
    },
    "awe": {
        "text_entry": "grow_from_center",
        "text_exit": "dissolve_out",
        "text_continuous": "glow_pulse",
        "image_entry": "img_zoom_in",
        "image_treatment": "ken_burns",
        "scene_transition": "zoom_in",
        "overlay_effect": "sparkle_overlay",
        "background_effect": "bg_particle_float",
    },
    "mystery": {
        "text_entry": "smoke_reveal",
        "text_exit": "dissolve_out",
        "text_continuous": "flicker",
        "image_entry": "img_blur_reveal",
        "image_treatment": "vignette",
        "scene_transition": "blur_transition",
        "overlay_effect": "dust_particles",
        "background_effect": "bg_color_breathe",
    },
    "joy": {
        "text_entry": "elastic_drop",
        "text_exit": "flick_off",
        "text_continuous": "bounce",
        "image_entry": "img_scale_bounce",
        "image_treatment": "brightness_pulse",
        "scene_transition": "elastic_bounce",
        "overlay_effect": "bokeh_overlay",
        "background_effect": "bg_pulse",
    },
    "tension": {
        "text_entry": "glitch_in",
        "text_exit": "glitch_out",
        "text_continuous": "shake",
        "image_entry": "img_fade_in",
        "image_treatment": "color_shift",
        "scene_transition": "pixelate_transition",
        "overlay_effect": "scan_lines",
        "background_effect": "bg_pulse",
    },
    "nostalgia": {
        "text_entry": "fade_in",
        "text_exit": "fade_out",
        "text_continuous": "breathe",
        "image_entry": "img_fade_in",
        "image_treatment": "sepia_blend",
        "scene_transition": "crossfade",
        "overlay_effect": "subtle_grain",
        "background_effect": "bg_gradient_shift",
    },
    "triumph": {
        "text_entry": "zoom_blur_in",
        "text_exit": "vortex_out",
        "text_continuous": "glow_pulse",
        "image_entry": "img_zoom_in",
        "image_treatment": "ken_burns",
        "scene_transition": "flash_transition",
        "overlay_effect": "sparkle_overlay",
        "background_effect": "bg_pulse",
    },
    "horror": {
        "text_entry": "glitch_in",
        "text_exit": "crumble",
        "text_continuous": "flicker",
        "image_entry": "img_scale_bounce",
        "image_treatment": "vignette",
        "scene_transition": "pixelate_transition",
        "overlay_effect": "vhs_distortion",
        "background_effect": "bg_color_breathe",
    },
    "wonder": {
        "text_entry": "spiral_in",
        "text_exit": "dissolve_out",
        "text_continuous": "float_drift",
        "image_entry": "img_zoom_in",
        "image_treatment": "ken_burns",
        "scene_transition": "circle_wipe",
        "overlay_effect": "bokeh_overlay",
        "background_effect": "bg_particle_float",
    },
    "neutral": {
        "text_entry": "slide_up",
        "text_exit": "fade_out",
        "text_continuous": "breathe",
        "image_entry": "img_fade_in",
        "image_treatment": "ken_burns",
        "scene_transition": "crossfade",
        "overlay_effect": "subtle_grain",
        "background_effect": "bg_color_breathe",
    },
}

# Scene-type overrides
SCENE_TYPE_MODIFIERS: dict[str, dict] = {
    "A": {"text_entry": "zoom_blur_in", "scene_transition": "flash_transition"},  # impact
    "B": {},  # standard — uses emotion preset
    "C": {"text_entry": "blur_reveal", "scene_transition": "blur_transition"},     # reveal
    "D": {"text_continuous": "shake"},                                              # tension
    "E": {"text_entry": "slide_up", "scene_transition": "crossfade"},             # transition
    "F": {"text_entry": "elastic_drop", "text_continuous": "bounce"},             # upbeat
    "G": {"text_entry": "fade_in", "scene_transition": "crossfade"},              # contemplative
    "H": {"text_entry": "grow_from_center", "scene_transition": "flash_transition"},  # finale
}


# ── Content Keyword Detection ────────────────────────

KEYWORD_EFFECT_MAP: dict[str, dict] = {
    # Words → effect overrides
    "explod": {"text_entry": "explode_in", "text_exit": "explode_out", "overlay_effect": "fire_embers"},
    "fire": {"overlay_effect": "fire_embers", "text_continuous": "fire_flicker"},
    "water": {"overlay_effect": "rain_overlay", "text_continuous": "wave_motion"},
    "rain": {"overlay_effect": "rain_overlay"},
    "ocean": {"text_continuous": "wave_motion", "overlay_effect": "bokeh_overlay"},
    "space": {"overlay_effect": "sparkle_overlay", "text_entry": "spiral_in", "background_effect": "bg_particle_float"},
    "star": {"overlay_effect": "sparkle_overlay", "text_continuous": "glow_pulse"},
    "fast": {"text_entry": "stamp_in", "scene_transition": "slide_horizontal"},
    "slow": {"text_entry": "fade_in", "text_continuous": "breathe"},
    "crash": {"text_entry": "stamp_in", "text_exit": "crumble", "overlay_effect": "chromatic_aberration"},
    "break": {"text_exit": "crumble", "scene_transition": "pixelate_transition"},
    "shatter": {"text_exit": "explode_out", "scene_transition": "pixelate_transition"},
    "magic": {"overlay_effect": "sparkle_overlay", "text_continuous": "glow_pulse"},
    "dream": {"overlay_effect": "bokeh_overlay", "text_continuous": "float_drift", "scene_transition": "blur_transition"},
    "night": {"text_continuous": "flicker", "overlay_effect": "dust_particles"},
    "snow": {"overlay_effect": "snow_overlay"},
    "glitch": {"text_entry": "glitch_in", "text_exit": "glitch_out", "overlay_effect": "vhs_distortion"},
    "hack": {"text_entry": "glitch_in", "overlay_effect": "scan_lines"},
    "matrix": {"text_entry": "matrix_rain", "overlay_effect": "scan_lines"},
    "reveal": {"text_entry": "curtain_reveal", "scene_transition": "circle_wipe"},
    "secret": {"text_entry": "blur_reveal", "scene_transition": "blur_transition"},
    "speed": {"text_entry": "stamp_in", "scene_transition": "slide_horizontal"},
    "power": {"text_entry": "zoom_blur_in", "text_continuous": "glow_pulse"},
    "gentle": {"text_entry": "fade_in", "text_continuous": "breathe"},
    "storm": {"text_continuous": "shake", "overlay_effect": "rain_overlay"},
    "thunder": {"text_entry": "stamp_in", "overlay_effect": "fire_embers", "scene_transition": "flash_transition"},
    "war": {"text_continuous": "shake", "overlay_effect": "fire_embers", "scene_transition": "flash_transition"},
    "battle": {"text_entry": "stamp_in", "text_continuous": "shake", "overlay_effect": "fire_embers"},
    "peace": {"text_entry": "fade_in", "text_continuous": "breathe", "overlay_effect": "bokeh_overlay"},
    "love": {"text_continuous": "heartbeat", "overlay_effect": "bokeh_overlay"},
    "death": {"text_exit": "dissolve_out", "text_continuous": "flicker", "overlay_effect": "dust_particles"},
    "ghost": {"text_entry": "smoke_reveal", "text_continuous": "flicker", "overlay_effect": "dust_particles"},
    "robot": {"text_entry": "glitch_in", "overlay_effect": "scan_lines"},
    "cyber": {"text_entry": "glitch_in", "overlay_effect": "scan_lines"},
    "ancient": {"text_continuous": "breathe", "image_treatment": "sepia_blend"},
    "history": {"image_treatment": "sepia_blend", "overlay_effect": "subtle_grain"},
    "futur": {"text_entry": "glitch_in", "overlay_effect": "scan_lines", "text_continuous": "glow_pulse"},
    "fly": {"text_entry": "slide_up", "text_continuous": "float_drift"},
    "fall": {"text_entry": "elastic_drop", "text_exit": "crumble"},
    "spin": {"text_entry": "spiral_in", "text_exit": "vortex_out"},
    "zoom": {"text_entry": "zoom_blur_in", "image_entry": "img_zoom_in"},
    "tiny": {"text_entry": "grow_from_center"},
    "huge": {"text_entry": "zoom_blur_in"},
    "vibra": {"text_continuous": "shake"},
    "pulse": {"text_continuous": "heartbeat"},
}


# ── VFX Decision Agent ───────────────────────────────

class VFXDecisionAgent:
    """
    AI-powered agent that decides the best visual effects for each scene.

    Uses Claude Opus 4.6 via the Copilot Bridge for intelligent decisions,
    with a comprehensive fallback system using emotion presets + keyword
    detection when the bridge is unavailable.
    """

    def __init__(self, use_ai: bool = True):
        """
        Args:
            use_ai: If True, use Claude Opus 4.6 for decisions. If False, use
                    the rule-based fallback (emotion + keyword maps).
        """
        self.use_ai = use_ai
        self._bridge_available: Optional[bool] = None

    def plan_effects(
        self,
        screens: list[dict],
        mood: str = "neutral",
        content_mode: str = "article",
        visual_style: str = "claymorphism",
    ) -> VideoEffectsPlan:
        """
        Generate a complete effects plan for all screens.

        Args:
            screens: List of screen dicts with keys like:
                     text, emotion, scene_type, visual_type, is_intro, is_outro,
                     emphasis_words, duration, image_prompt, speaker
            mood: Overall video mood
            content_mode: article | thought_experiment | ghost_collab | deep_dive
            visual_style: claymorphism | glassmorphism | etc.

        Returns:
            VideoEffectsPlan with per-scene effect decisions.
        """
        plan = VideoEffectsPlan(overall_mood=mood)

        # Try AI-powered decisions first
        if self.use_ai:
            try:
                ai_plan = self._ai_decide(screens, mood, content_mode, visual_style)
                if ai_plan and len(ai_plan.scenes) == len(screens):
                    logger.info(f"[VFX Agent] AI decisions ready for {len(screens)} scenes")
                    return ai_plan
                elif ai_plan and ai_plan.scenes:
                    logger.warning(f"[VFX Agent] AI returned {len(ai_plan.scenes)} plans for {len(screens)} screens, padding with fallback")
                    plan = ai_plan
            except Exception as e:
                logger.warning(f"[VFX Agent] AI decision failed: {e}, using fallback")

        # Fallback: rule-based decisions for any missing scenes
        existing_indices = {s.screen_index for s in plan.scenes}
        for i, screen in enumerate(screens):
            if i not in existing_indices:
                scene_plan = self._rule_based_decide(i, screen, mood, len(screens))
                plan.scenes.append(scene_plan)

        # Sort by screen index
        plan.scenes.sort(key=lambda s: s.screen_index)

        logger.info(f"[VFX Agent] Effects plan ready: {len(plan.scenes)} scenes")
        return plan

    def _ai_decide(
        self,
        screens: list[dict],
        mood: str,
        content_mode: str,
        visual_style: str,
    ) -> Optional[VideoEffectsPlan]:
        """Use Claude Opus 4.6 for intelligent effect selection."""
        try:
            from utils.copilot_bridge import CopilotBridgeClient
        except ImportError:
            logger.error("[VFX Agent] Cannot import CopilotBridgeClient")
            return None

        client = CopilotBridgeClient()

        # Check bridge health
        if self._bridge_available is None:
            self._bridge_available = client.check_health()
        if not self._bridge_available:
            logger.warning("[VFX Agent] Copilot Bridge not available")
            return None

        # Build the prompt
        system_prompt = self._build_system_prompt(visual_style)
        user_prompt = self._build_user_prompt(screens, mood, content_mode)

        try:
            response = client.chat(
                model=VFX_AGENT_MODEL,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if not content:
                return None

            return self._parse_ai_response(content, len(screens))

        except Exception as e:
            logger.error(f"[VFX Agent] Bridge call failed: {e}")
            self._bridge_available = False
            return None

    def _build_system_prompt(self, visual_style: str) -> str:
        """Build the system prompt for Claude Opus 4.6."""
        return f"""You are a professional Video Effects Director for an AI video generation system.
Your job is to intelligently select visual effects for each scene of a video.

The video uses a "{visual_style}" visual style and renders at 1080x1920 (vertical/mobile).

AVAILABLE TEXT ENTRY EFFECTS:
- fade_in: Gentle opacity fade (calm, professional)
- slide_up / slide_down / slide_left / slide_right: Directional slide entrances
- scale_bounce: Pop in with overshoot bounce (energetic, playful)
- elastic_drop: Drop from above with elastic bounce (fun, dynamic)
- blur_reveal: Emerge from blur (mysterious, revealing)
- glitch_in: Digital glitch entrance (tech, sci-fi, chaos)
- wave_in: Wave motion entrance (water, flow, organic)
- spiral_in: Spin in from distance (whimsical, magical)
- flip_in: 3D flip reveal (dramatic, tech)
- explode_in: Scatter from explosion to form (explosive, impactful)
- dissolve_in: Pixel dissolve reveal (elegant, digital)
- split_reveal: Split apart to reveal (dramatic, revealing)
- zoom_blur_in: Zoom from far with blur (powerful, impact)
- stamp_in: Slam down with impact shake (forceful, authoritative)
- curtain_reveal: Curtain opening reveal (theatrical, grand)
- grow_from_center: Grow outward from center point (organic, birth)
- matrix_rain: Fall in like matrix characters (digital, hacker)
- smoke_reveal: Emerge from smoke/fog (mystery, atmospheric)
- typewriter: Character-by-character reveal (narrative, documentary)

AVAILABLE TEXT EXIT EFFECTS:
- fade_out: Simple opacity fade (clean, neutral)
- slide_out_up / slide_out_down / slide_out_left / slide_out_right: Directional exits
- scale_shrink: Shrink to nothing (disappearing)
- blur_exit: Blur out to nothing (dreamy, fading)
- explode_out: Explode apart (dramatic, explosive)
- dissolve_out: Pixel dissolve away (elegant)
- flip_out: 3D flip away (tech, dramatic)
- flick_off: Quick flick to side (casual, fast)
- evaporate: Float up and dissolve (spiritual, ethereal)
- crumble: Break apart and fall (destruction, age)
- swipe_wipe: Wipe away (clean, editorial)
- vortex_out: Spin into vortex (chaotic, magical)
- glitch_out: Glitch and disappear (digital, error)

AVAILABLE TEXT CONTINUOUS EFFECTS (during display):
- none: No continuous animation
- glow_pulse: Soft pulsing glow (magical, ethereal)
- wave_motion: Gentle wave movement (water, calm)
- wobble: Slight wobble (playful, unstable)
- color_cycle: Slowly cycle colors (psychedelic, creative)
- bounce: Gentle bouncing (playful, energetic)
- float_drift: Slow floating drift (dreamy, space)
- shake: Vibration/shake (tension, earthquake, anger)
- heartbeat: Pulse like a heartbeat (emotional, love)
- flicker: Light flicker (suspense, horror, old)
- pendulum: Swing like pendulum (hypnotic, time)
- breathe: Slow scale breathing (calm, alive)
- scan_line: Scanning light line (tech, sci-fi)
- fire_flicker: Warm fire-like brightness shifts (fire, warmth)
- electric_arc: Occasional electric sparks (energy, power)

AVAILABLE IMAGE ENTRY EFFECTS:
- img_fade_in: Gentle fade in (default, clean)
- img_scale_bounce: Pop in with bounce (energetic)
- img_slide_in: Slide from direction (with direction param: left/right/top/bottom)
- img_zoom_in: Zoom from small with blur (cinematic)
- img_rotate_in: Rotate while scaling in (dramatic)
- img_flip_in: 3D flip reveal (tech, dramatic)
- img_blur_reveal: Emerge from blur (mysterious)
- img_shutter: Camera shutter opening (photography)

AVAILABLE IMAGE TREATMENTS (during display):
- ken_burns: Slow zoom and pan (documentary, cinematic) — most commonly used
- parallax_2d: Subtle depth-based shift (immersive)
- zoom_pulse: Rhythmic zoom pulsing (energetic, musical)
- tilt_shift: Miniature/toy effect (whimsical, artistic)
- vignette: Dark edge vignette (dramatic, cinematic)
- color_shift: Temperature/saturation shift (atmospheric)
- sepia_blend: Aged sepia tone (nostalgic, historical)
- rotation_slow: Gentle rotation (dream, disorientation)
- desaturate_to_color: Gray to color reveal (dramatic, revealing)
- brightness_pulse: Brightness pulsing (energetic)
- static_image: No movement (text focus, minimalist)

AVAILABLE IMAGE EXIT EFFECTS:
- img_fade_out: Gentle fade (clean)
- img_slide_out: Slide out with direction (dynamic)
- img_scale_out: Scale down to nothing (dramatic)
- img_blur_out: Blur to nothing (dreamy)
- img_shatter_out: Break apart (destruction)
- img_dissolve_out: Dissolve (elegant)

AVAILABLE SCENE TRANSITIONS:
- crossfade: Smooth blend (default, clean)
- hard_cut: Instant cut (urgent, editorial)
- slide_horizontal / slide_vertical: Push slide (newscast, editorial)
- wipe_left / wipe_right / wipe_diagonal: Directional wipe (formal)
- circle_wipe: Circle opening (playful, theatrical)
- diamond_wipe: Diamond shape reveal (geometric, stylized)
- zoom_in / zoom_out: Zoom transition (cinematic, impactful)
- spin_transition: Spinning transition (dynamic, chaotic)
- flash_transition: White flash between scenes (dramatic, energetic)
- blur_transition: Blur dissolve (dreamy, mysterious)
- pixelate_transition: Pixelation transition (digital, glitch)
- blinds_horizontal / blinds_vertical: Window blind reveal (formal, presentation)
- elastic_bounce: Bouncy reveal (playful, fun)
- ripple_transition: Water ripple dissolve (water, dream)
- ink_bleed: Organic ink spread (artistic, editorial)
- whip_pan: Fast whip pan (Remotion-style) (fast, energetic)
- glitch_transition: Digital glitch between scenes (tech, chaos)

AVAILABLE OVERLAYS:
- overlay_none: No overlay
- subtle_grain: Light film grain (cinematic, vintage)
- heavy_grain: Strong film grain (retro, gritty)
- bokeh_overlay: Floating bokeh lights (dreamy, beautiful)
- rain_overlay: Falling rain drops (sad, atmospheric)
- snow_overlay: Gentle snowfall (winter, peaceful)
- dust_particles: Floating dust motes (atmospheric, old)
- scan_lines: CRT scan lines (retro, tech)
- vhs_distortion: VHS tracking distortion (retro, chaotic)
- chromatic_aberration: Color fringing (glitch, intense)
- sparkle_overlay: Twinkling sparkles (magic, celebration)
- fire_embers: Rising ember particles (fire, warmth, danger)

AVAILABLE BACKGROUND EFFECTS:
- bg_none: Static background
- bg_gradient_shift: Slowly shifting gradient colors
- bg_color_breathe: Subtle brightness breathing
- bg_pulse: Brightness pulsing (musical, energetic)
- bg_particle_float: Floating ambient particles
- bg_aurora: Aurora-like color movement

RULES:
1. Match effects to the EMOTION and CONTENT of each scene
2. Intro scenes should be dramatic (zoom_blur_in, stamp_in, flash_transition)
3. Outro scenes should be conclusive (fade_out, crossfade, dissolve)
4. Vary effects between consecutive scenes — don't repeat the same effect
5. Intense effects (explode, glitch, stamp) only for high-energy emotions
6. Calm content (reflection, nature, peace) should use subtle effects
7. Match overlays to atmosphere (rain for sad, sparkles for magical, grain for vintage)
8. Keep image treatments mostly as ken_burns — it's the most cinematic
9. Text_only scenes need stronger text entry effects since text IS the visual
10. Multi_image scenes should use simple image entries to avoid chaos
11. Ghost_collab/thought_experiment modes should feel more dramatic
12. Don't overuse shake/glitch — save for genuinely intense moments
13. Use scene transitions that create rhythm — alternate between smooth and dynamic

Respond ONLY with valid JSON."""

    def _build_user_prompt(
        self,
        screens: list[dict],
        mood: str,
        content_mode: str,
    ) -> str:
        """Build the user prompt with all scene data."""
        scenes_summary = []
        for i, s in enumerate(screens):
            summary = {
                "index": i,
                "text": s.get("text", "")[:200],  # Truncate for prompt size
                "emotion": s.get("emotion", "neutral"),
                "scene_type": s.get("scene_type", "B"),
                "visual_type": s.get("visual_type", "image"),
                "is_intro": s.get("is_intro", False),
                "is_outro": s.get("is_outro", False),
                "duration": s.get("duration", 3.5),
                "speaker": s.get("speaker", "narrator"),
                "emphasis_words": [w.get("text", w) if isinstance(w, dict) else str(w)
                                   for w in s.get("emphasis_words", [])],
            }
            scenes_summary.append(summary)

        prompt = f"""Analyze these {len(screens)} video scenes and select the BEST visual effects for each one.

Overall mood: {mood}
Content mode: {content_mode}

SCENES:
{json.dumps(scenes_summary, indent=2)}

For each scene, return a JSON object with this structure:
{{
  "scenes": [
    {{
      "screen_index": 0,
      "text_entry": "effect_name",
      "text_exit": "effect_name",
      "text_continuous": "effect_name",
      "image_entry": "effect_name",
      "image_treatment": "effect_name",
      "image_exit": "effect_name",
      "scene_transition": "effect_name",
      "overlay_effect": "effect_name",
      "background_effect": "effect_name",
      "emphasis_style": "scale_bounce",
      "reasoning": "brief explanation of choices"
    }}
  ],
  "overall_mood": "{mood}",
  "visual_theme": "describe the visual theme"
}}

Return ONLY the JSON object. One entry per scene, indexed 0 to {len(screens) - 1}."""

        return prompt

    def _parse_ai_response(
        self, content: str, num_screens: int
    ) -> Optional[VideoEffectsPlan]:
        """Parse the AI response into a VideoEffectsPlan."""
        try:
            # Try direct JSON parse
            data = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown
            json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
            if json_match:
                try:
                    data = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    logger.error("[VFX Agent] Could not parse AI response as JSON")
                    return None
            else:
                # Try to find JSON object directly
                brace_start = content.find("{")
                brace_end = content.rfind("}") + 1
                if brace_start >= 0 and brace_end > brace_start:
                    try:
                        data = json.loads(content[brace_start:brace_end])
                    except json.JSONDecodeError:
                        logger.error("[VFX Agent] Could not extract JSON from AI response")
                        return None
                else:
                    return None

        plan = VideoEffectsPlan(
            overall_mood=data.get("overall_mood", "neutral"),
            visual_theme=data.get("visual_theme", "dynamic"),
        )

        scenes_data = data.get("scenes", [])
        for scene_data in scenes_data:
            scene_plan = SceneEffectsPlan(
                screen_index=scene_data.get("screen_index", 0),
                text_entry=scene_data.get("text_entry", "fade_in"),
                text_entry_params=scene_data.get("text_entry_params", {}),
                text_exit=scene_data.get("text_exit", "fade_out"),
                text_exit_params=scene_data.get("text_exit_params", {}),
                text_continuous=scene_data.get("text_continuous", "none"),
                text_continuous_params=scene_data.get("text_continuous_params", {}),
                image_entry=scene_data.get("image_entry", "img_fade_in"),
                image_entry_params=scene_data.get("image_entry_params", {}),
                image_treatment=scene_data.get("image_treatment", "ken_burns"),
                image_treatment_params=scene_data.get("image_treatment_params", {}),
                image_exit=scene_data.get("image_exit", "img_fade_out"),
                image_exit_params=scene_data.get("image_exit_params", {}),
                scene_transition=scene_data.get("scene_transition", "crossfade"),
                scene_transition_params=scene_data.get("scene_transition_params", {}),
                overlay_effect=scene_data.get("overlay_effect", "overlay_none"),
                overlay_params=scene_data.get("overlay_params", {}),
                background_effect=scene_data.get("background_effect", "bg_none"),
                background_params=scene_data.get("background_params", {}),
                emphasis_style=scene_data.get("emphasis_style", "scale_bounce"),
                emphasis_params=scene_data.get("emphasis_params", {}),
                reasoning=scene_data.get("reasoning", ""),
            )
            plan.scenes.append(scene_plan)

        return plan

    def _rule_based_decide(
        self,
        index: int,
        screen: dict,
        mood: str,
        total_scenes: int,
    ) -> SceneEffectsPlan:
        """Rule-based fallback using emotion presets + keyword detection."""
        emotion = screen.get("emotion", mood).lower()
        scene_type = screen.get("scene_type", "B")
        visual_type = screen.get("visual_type", "image")
        text = screen.get("text", "").lower()
        is_intro = screen.get("is_intro", False)
        is_outro = screen.get("is_outro", False)

        # Start with emotion preset
        preset = EMOTION_PRESETS.get(emotion, EMOTION_PRESETS["neutral"]).copy()

        # Apply scene-type modifiers
        scene_mods = SCENE_TYPE_MODIFIERS.get(scene_type, {})
        preset.update(scene_mods)

        # Apply keyword-based overrides (ADD or UPDATE keys)
        for keyword, overrides in KEYWORD_EFFECT_MAP.items():
            if keyword in text:
                for key, val in overrides.items():
                    preset[key] = val

        # Intro/outro overrides
        if is_intro:
            preset["text_entry"] = "zoom_blur_in"
            preset["scene_transition"] = "flash_transition"
            preset["image_entry"] = "img_zoom_in"
        if is_outro:
            preset["text_exit"] = "fade_out"
            preset["scene_transition"] = "crossfade"
            preset["text_continuous"] = "breathe"

        # Text-only scenes — need stronger text effects
        if visual_type == "text_only":
            if preset.get("text_entry") == "fade_in":
                preset["text_entry"] = "scale_bounce"
            preset["background_effect"] = "bg_color_breathe"

        # Multi-image — simpler image entries
        if visual_type == "multi_image":
            preset["image_entry"] = "img_fade_in"
            preset["image_treatment"] = "static_image"

        # ── Scene position variety ──
        # ALWAYS rotate effects based on scene index so no two consecutive
        # screens look identical, even if they share the same emotion preset.
        _entry_pool = ["scale_bounce", "slide_up", "elastic_drop", "blur_reveal",
                       "zoom_blur_in", "grow_from_center", "stamp_in", "curtain_reveal"]
        _exit_pool = ["fade_out", "swipe_wipe", "dissolve_out", "slide_out_up",
                      "evaporate", "flick_off", "scale_shrink", "blur_exit"]
        _overlay_pool = ["subtle_grain", "bokeh_overlay", "dust_particles",
                        "sparkle_overlay", "fire_embers", "scan_lines",
                        "chromatic_aberration", "vhs_distortion"]
        _bg_pool = ["bg_color_breathe", "bg_pulse", "bg_gradient_shift",
                    "bg_particle_float"]
        _img_pool = ["ken_burns", "zoom_pulse", "parallax_2d", "brightness_pulse",
                     "color_shift", "vignette"]
        _cont_pool = ["glow_pulse", "breathe", "wave_motion", "float_drift",
                      "heartbeat", "pendulum", "shake", "flicker"]
        _trans_pool = ["crossfade", "flash_transition", "circle_wipe",
                       "slide_horizontal", "wipe_left", "ink_bleed",
                       "blur_transition", "pixelate_transition"]

        # Use the preset's effect as a base, then pick the NEXT one in the
        # pool offset by scene index.  This keeps the emotion flavour while
        # guaranteeing consecutive screens differ.
        def _pick(pool, base, idx):
            """Return pool[(base_position + idx) % len(pool)]."""
            try:
                pos = pool.index(base)
            except ValueError:
                pos = 0
            return pool[(pos + idx) % len(pool)]

        # Always cycle text entry (skip index 0 to keep intro override)
        if index > 0 and not is_intro:
            preset["text_entry"] = _pick(
                _entry_pool, preset.get("text_entry", "fade_in"), index
            )

        # Always cycle text exit
        if not is_outro:
            preset["text_exit"] = _pick(
                _exit_pool, preset.get("text_exit", "fade_out"), index
            )

        # Always cycle text continuous — never leave it as 'none'
        base_cont = preset.get("text_continuous", "none")
        if base_cont == "none":
            base_cont = "glow_pulse"
        preset["text_continuous"] = _pick(_cont_pool, base_cont, index)

        # Always ensure a background effect is active and varied
        base_bg = preset.get("background_effect", "bg_none")
        if base_bg == "bg_none":
            base_bg = "bg_color_breathe"
        preset["background_effect"] = _pick(_bg_pool, base_bg, index)

        # Cycle image treatment
        preset["image_treatment"] = _pick(
            _img_pool, preset.get("image_treatment", "ken_burns"), index
        )

        # Cycle overlays
        preset["overlay_effect"] = _pick(
            _overlay_pool, preset.get("overlay_effect", "subtle_grain"), index
        )

        # Cycle transitions (skip intro which already has flash_transition)
        if index > 0:
            preset["scene_transition"] = _pick(
                _trans_pool, preset.get("scene_transition", "crossfade"), index
            )

        return SceneEffectsPlan(
            screen_index=index,
            text_entry=preset.get("text_entry", "fade_in"),
            text_exit=preset.get("text_exit", "fade_out"),
            text_continuous=preset.get("text_continuous", "none"),
            image_entry=preset.get("image_entry", "img_fade_in"),
            image_treatment=preset.get("image_treatment", "ken_burns"),
            image_exit=preset.get("image_exit", "img_fade_out"),
            scene_transition=preset.get("scene_transition", "crossfade"),
            overlay_effect=preset.get("overlay_effect", "overlay_none"),
            background_effect=preset.get("background_effect", "bg_none"),
            emphasis_style=preset.get("emphasis_style", "scale_bounce"),
            reasoning=f"Rule-based: emotion={emotion}, scene_type={scene_type}, keywords detected",
        )


# ── Convenience Function ─────────────────────────────

def generate_effects_plan(
    screens: list,
    mood: str = "neutral",
    content_mode: str = "article",
    visual_style: str = "claymorphism",
    use_ai: bool = True,
) -> VideoEffectsPlan:
    """
    Top-level function to generate an effects plan.

    Args:
        screens: List of ScreenSegment objects or dicts.
        mood: Overall video mood.
        content_mode: Content mode string.
        visual_style: Visual style string.
        use_ai: Whether to attempt AI decisions.

    Returns:
        VideoEffectsPlan with per-scene decisions.
    """
    # Convert ScreenSegments to dicts if needed
    screen_dicts = []
    for s in screens:
        if hasattr(s, "__dict__"):
            d = {}
            for attr in ["text", "emotion", "scene_type", "visual_type",
                         "is_intro", "is_outro", "emphasis_words",
                         "duration", "image_prompt", "speaker",
                         "character_name", "setup_text", "subject_text"]:
                if hasattr(s, attr):
                    val = getattr(s, attr)
                    if attr == "emphasis_words" and val:
                        val = [{"text": w.text, "style": w.style} if hasattr(w, "text") else str(w)
                               for w in val]
                    d[attr] = val
            screen_dicts.append(d)
        elif isinstance(s, dict):
            screen_dicts.append(s)
        else:
            screen_dicts.append({"text": str(s)})

    agent = VFXDecisionAgent(use_ai=use_ai)
    return agent.plan_effects(screen_dicts, mood, content_mode, visual_style)
