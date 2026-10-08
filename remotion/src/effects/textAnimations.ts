/**
 * Project HER v2.0 – Text Animation Library
 * ==========================================
 * 30+ text entry/exit/continuous animations using Remotion's
 * interpolate(), spring(), and CSS transforms.
 *
 * Each function returns a React.CSSProperties object for a given
 * frame, making it trivial to apply in JSX: style={textEntry.stampIn(frame, fps)}
 */

import { interpolate, spring, Easing } from "remotion";
import type { SpringConfig } from "remotion";
import {
  SPRING_SNAPPY, SPRING_BOUNCY, SPRING_HEAVY, SPRING_ELASTIC,
  SPRING_POP, SPRING_DRAMATIC, SPRING_TREMOR, SPRING_GENTLE,
  SPRING_SMOOTH,
} from "./springs";

// ═══════════════════════════════════════════════════
//  TEXT ENTRY ANIMATIONS
// ═══════════════════════════════════════════════════

export const textEntry = {
  /** Fade in from transparent */
  fade_in(frame: number, fps: number, durationFrames = 15): React.CSSProperties {
    const dur = typeof durationFrames === "number" && !isNaN(durationFrames) && durationFrames > 0 ? durationFrames : 15;
    const opacity = interpolate(frame, [0, dur], [0, 1], {
      extrapolateRight: "clamp",
    });
    return { opacity };
  },

  /** Slide up from below with spring physics */
  slide_up(frame: number, fps: number): React.CSSProperties {
    const progress = spring({ frame, fps, config: SPRING_SNAPPY, durationInFrames: 30 });
    return {
      opacity: interpolate(progress, [0, 0.5], [0, 1], { extrapolateRight: "clamp" }),
      transform: `translateY(${interpolate(progress, [0, 1], [120, 0])}px)`,
    };
  },

  /** Slide down from above */
  slide_down(frame: number, fps: number): React.CSSProperties {
    const progress = spring({ frame, fps, config: SPRING_SNAPPY, durationInFrames: 30 });
    return {
      opacity: interpolate(progress, [0, 0.5], [0, 1], { extrapolateRight: "clamp" }),
      transform: `translateY(${interpolate(progress, [0, 1], [-120, 0])}px)`,
    };
  },

  /** Scale bounce — starts big, bounces to normal */
  scale_bounce(frame: number, fps: number): React.CSSProperties {
    const s = spring({ frame, fps, config: SPRING_BOUNCY, durationInFrames: 30 });
    const scale = interpolate(s, [0, 1], [0.3, 1]);
    return {
      opacity: interpolate(s, [0, 0.3], [0, 1], { extrapolateRight: "clamp" }),
      transform: `scale(${scale})`,
    };
  },

  /** Stamp in — large to normal with impact shake */
  stamp_in(frame: number, fps: number): React.CSSProperties {
    const s = spring({ frame, fps, config: SPRING_HEAVY, durationInFrames: 25 });
    const scale = interpolate(s, [0, 1], [2.5, 1]);
    const shake = frame < 12
      ? Math.sin(frame * 15) * interpolate(frame, [0, 12], [8, 0], { extrapolateRight: "clamp" })
      : 0;
    return {
      opacity: interpolate(s, [0, 0.2], [0, 1], { extrapolateRight: "clamp" }),
      transform: `scale(${scale}) translate(${shake}px, ${shake * 0.7}px)`,
    };
  },

  /** Elastic drop — falls from top with elastic bounce */
  elastic_drop(frame: number, fps: number): React.CSSProperties {
    const s = spring({ frame, fps, config: SPRING_ELASTIC, durationInFrames: 35 });
    return {
      opacity: interpolate(s, [0, 0.3], [0, 1], { extrapolateRight: "clamp" }),
      transform: `translateY(${interpolate(s, [0, 1], [-200, 0])}px)`,
    };
  },

  /** Blur reveal — from blurry to sharp */
  blur_reveal(frame: number, fps: number, durationFrames = 20): React.CSSProperties {
    const dur = typeof durationFrames === "number" && !isNaN(durationFrames) && durationFrames > 0 ? durationFrames : 20;
    const p = interpolate(frame, [0, dur], [0, 1], { extrapolateRight: "clamp" });
    return {
      opacity: p,
      filter: `blur(${interpolate(p, [0, 1], [20, 0])}px)`,
    };
  },

  /** Zoom blur in — zooms from distance with blur */
  zoom_blur_in(frame: number, fps: number): React.CSSProperties {
    const s = spring({ frame, fps, config: SPRING_POP, durationInFrames: 25 });
    return {
      opacity: interpolate(s, [0, 0.4], [0, 1], { extrapolateRight: "clamp" }),
      transform: `scale(${interpolate(s, [0, 1], [0.1, 1])})`,
      filter: `blur(${interpolate(s, [0, 1], [15, 0])}px)`,
    };
  },

  /** Grow from center — expands outward */
  grow_from_center(frame: number, fps: number): React.CSSProperties {
    const s = spring({ frame, fps, config: SPRING_BOUNCY, durationInFrames: 28 });
    return {
      opacity: interpolate(s, [0, 0.3], [0, 1], { extrapolateRight: "clamp" }),
      transform: `scale(${interpolate(s, [0, 1], [0, 1])})`,
      transformOrigin: "center center",
    };
  },

  /** Curtain reveal — clip from center outward */
  curtain_reveal(frame: number, fps: number, durationFrames = 20): React.CSSProperties {
    const dur = typeof durationFrames === "number" && !isNaN(durationFrames) && durationFrames > 0 ? durationFrames : 20;
    const p = interpolate(frame, [0, dur], [0, 1], {
      extrapolateRight: "clamp",
      easing: Easing.out(Easing.cubic),
    });
    return {
      clipPath: `inset(0 ${interpolate(p, [0, 1], [50, 0])}% 0 ${interpolate(p, [0, 1], [50, 0])}%)`,
    };
  },

  /** Smoke reveal — opacity pulse with blur */
  smoke_reveal(frame: number, fps: number, durationFrames = 24): React.CSSProperties {
    const dur = typeof durationFrames === "number" && !isNaN(durationFrames) && durationFrames > 0 ? durationFrames : 24;
    const p = interpolate(frame, [0, dur], [0, 1], { extrapolateRight: "clamp" });
    const wobble = Math.sin(frame * 0.5) * interpolate(p, [0, 0.5, 1], [3, 1, 0]);
    return {
      opacity: interpolate(p, [0, 0.5, 1], [0, 0.7, 1]),
      filter: `blur(${interpolate(p, [0, 1], [12, 0])}px)`,
      transform: `translateX(${wobble}px)`,
    };
  },

  /** Spiral in — rotation + scale */
  spiral_in(frame: number, fps: number): React.CSSProperties {
    const s = spring({ frame, fps, config: SPRING_SNAPPY, durationInFrames: 30 });
    return {
      opacity: interpolate(s, [0, 0.5], [0, 1], { extrapolateRight: "clamp" }),
      transform: `scale(${interpolate(s, [0, 1], [0, 1])}) rotate(${interpolate(s, [0, 1], [180, 0])}deg)`,
    };
  },

  /** Glitch in — digital distortion entrance */
  glitch_in(frame: number, fps: number, durationFrames = 18): React.CSSProperties {
    const dur = typeof durationFrames === "number" && !isNaN(durationFrames) && durationFrames > 0 ? durationFrames : 18;
    const p = interpolate(frame, [0, dur], [0, 1], { extrapolateRight: "clamp" });
    const glitchX = frame < dur * 0.7
      ? Math.sin(frame * 30) * interpolate(p, [0, 0.7], [15, 0], { extrapolateRight: "clamp" })
      : 0;
    const skew = frame < dur * 0.5
      ? Math.sin(frame * 20) * interpolate(p, [0, 0.5], [8, 0], { extrapolateRight: "clamp" })
      : 0;
    return {
      opacity: interpolate(p, [0, 0.3, 0.5, 1], [0, 1, 0.8, 1]),
      transform: `translateX(${glitchX}px) skewX(${skew}deg)`,
    };
  },

  /** 3D flip in — rotates from behind on Y axis */
  flip_in_3d(frame: number, fps: number): React.CSSProperties {
    const s = spring({ frame, fps, config: SPRING_SNAPPY, durationInFrames: 25 });
    return {
      opacity: interpolate(s, [0, 0.5], [0, 1], { extrapolateRight: "clamp" }),
      transform: `perspective(600px) rotateY(${interpolate(s, [0, 1], [-90, 0])}deg)`,
      transformOrigin: "left center",
    };
  },

  /** 3D tilt in — rotates from below on X axis */
  tilt_in_3d(frame: number, fps: number): React.CSSProperties {
    const s = spring({ frame, fps, config: SPRING_DRAMATIC, durationInFrames: 30 });
    return {
      opacity: interpolate(s, [0, 0.3], [0, 1], { extrapolateRight: "clamp" }),
      transform: `perspective(800px) rotateX(${interpolate(s, [0, 1], [60, 0])}deg)`,
      transformOrigin: "center bottom",
    };
  },

  /** Typewriter reveal — progressively reveals text horizontally */
  typewriter(frame: number, fps: number, text?: string): React.CSSProperties {
    const textLen = (typeof text === "string" && text.length > 0) ? text.length : 30;
    const durationFrames = Math.min(Math.max(Math.round(textLen * 0.7), 15), 45);
    const p = interpolate(frame, [0, durationFrames], [0, 1], {
      extrapolateRight: "clamp",
      easing: Easing.linear,
    });
    return {
      clipPath: `inset(0 ${(1 - p) * 100}% 0 0)`,
      opacity: interpolate(p, [0, 0.05], [0, 1], { extrapolateRight: "clamp" }),
    };
  },

  /** Slide from left */
  slide_left(frame: number, fps: number): React.CSSProperties {
    const s = spring({ frame, fps, config: SPRING_SNAPPY, durationInFrames: 25 });
    return {
      opacity: interpolate(s, [0, 0.5], [0, 1], { extrapolateRight: "clamp" }),
      transform: `translateX(${interpolate(s, [0, 1], [-200, 0])}px)`,
    };
  },

  /** Slide from right */
  slide_right(frame: number, fps: number): React.CSSProperties {
    const s = spring({ frame, fps, config: SPRING_SNAPPY, durationInFrames: 25 });
    return {
      opacity: interpolate(s, [0, 0.5], [0, 1], { extrapolateRight: "clamp" }),
      transform: `translateX(${interpolate(s, [0, 1], [200, 0])}px)`,
    };
  },

  /** 3D card flip — like flipping a card face-up */
  card_flip_3d(frame: number, fps: number): React.CSSProperties {
    const s = spring({ frame, fps, config: SPRING_BOUNCY, durationInFrames: 30 });
    return {
      opacity: interpolate(s, [0.3, 0.5], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
      transform: `perspective(1000px) rotateX(${interpolate(s, [0, 1], [180, 0])}deg)`,
      backfaceVisibility: "hidden" as const,
    };
  },

  /** Whip pan in — fast horizontal whip entry with motion blur */
  whip_in(frame: number, fps: number): React.CSSProperties {
    const s = spring({ frame, fps, config: SPRING_DRAMATIC, durationInFrames: 18 });
    const blur = interpolate(s, [0, 0.6], [12, 0], { extrapolateRight: "clamp" });
    return {
      opacity: interpolate(s, [0, 0.3], [0, 1], { extrapolateRight: "clamp" }),
      transform: `translateX(${interpolate(s, [0, 1], [600, 0])}px) scaleX(${interpolate(s, [0, 1], [1.4, 1])})`,
      filter: `blur(${blur}px)`,
    };
  },

  /** Pop scatter — burst in from random direction (per-word) */
  pop_in(frame: number, fps: number): React.CSSProperties {
    const s = spring({ frame, fps, config: SPRING_POP, durationInFrames: 20 });
    return {
      opacity: interpolate(s, [0, 0.2], [0, 1], { extrapolateRight: "clamp" }),
      transform: `scale(${interpolate(s, [0, 1], [0, 1])}) rotate(${interpolate(s, [0, 1], [-15, 0])}deg)`,
    };
  },

  /** Cinema title — dramatic slow zoom-in with glow */
  cinema_title(frame: number, fps: number): React.CSSProperties {
    const s = spring({ frame, fps, config: SPRING_GENTLE, durationInFrames: 40 });
    return {
      opacity: interpolate(s, [0, 0.4], [0, 1], { extrapolateRight: "clamp" }),
      transform: `scale(${interpolate(s, [0, 1], [0.7, 1])})`,
      letterSpacing: `${interpolate(s, [0, 1], [20, 0])}px`,
      textShadow: `0 0 ${interpolate(s, [0, 1], [30, 0])}px rgba(255,200,100,0.6)`,
    };
  },

  /** Rise and settle — float up with deceleration */
  rise_settle(frame: number, fps: number): React.CSSProperties {
    const s = spring({ frame, fps, config: SPRING_SMOOTH, durationInFrames: 35 });
    return {
      opacity: interpolate(s, [0, 0.4], [0, 1], { extrapolateRight: "clamp" }),
      transform: `translateY(${interpolate(s, [0, 1], [80, 0])}px) scale(${interpolate(s, [0, 1], [0.95, 1])})`,
    };
  },

  /** Split reveal horizontal — text clips in from center outward */
  split_reveal(frame: number, fps: number, durationFrames = 20): React.CSSProperties {
    const dur = typeof durationFrames === "number" && !isNaN(durationFrames) && durationFrames > 0 ? durationFrames : 20;
    const p = interpolate(frame, [0, dur], [0, 1], { extrapolateRight: "clamp" });
    return {
      opacity: 1,
      clipPath: `inset(0 ${50 - p * 50}% 0 ${50 - p * 50}%)`,
    };
  },
};

// ═══════════════════════════════════════════════════
//  TEXT EXIT ANIMATIONS
// ═══════════════════════════════════════════════════

export const textExit = {
  /** Simple fade out */
  fade_out(frame: number, fps: number, durationFrames = 15): React.CSSProperties {
    const opacity = interpolate(frame, [0, durationFrames], [1, 0], {
      extrapolateRight: "clamp",
    });
    return { opacity };
  },

  /** Slide out upward */
  slide_out_up(frame: number, fps: number, durationFrames = 18): React.CSSProperties {
    const p = interpolate(frame, [0, durationFrames], [0, 1], {
      extrapolateRight: "clamp",
      easing: Easing.in(Easing.cubic),
    });
    return {
      opacity: 1 - p,
      transform: `translateY(${interpolate(p, [0, 1], [0, -150])}px)`,
    };
  },

  /** Slide out downward */
  slide_out_down(frame: number, fps: number, durationFrames = 18): React.CSSProperties {
    const p = interpolate(frame, [0, durationFrames], [0, 1], {
      extrapolateRight: "clamp",
      easing: Easing.in(Easing.cubic),
    });
    return {
      opacity: 1 - p,
      transform: `translateY(${interpolate(p, [0, 1], [0, 150])}px)`,
    };
  },

  /** Dissolve out — fade + slight scale */
  dissolve_out(frame: number, fps: number, durationFrames = 20): React.CSSProperties {
    const p = interpolate(frame, [0, durationFrames], [0, 1], {
      extrapolateRight: "clamp",
    });
    return {
      opacity: 1 - p,
      transform: `scale(${1 + p * 0.1})`,
      filter: `blur(${p * 5}px)`,
    };
  },

  /** Evaporate — drifts up and fades */
  evaporate(frame: number, fps: number, durationFrames = 22): React.CSSProperties {
    const p = interpolate(frame, [0, durationFrames], [0, 1], {
      extrapolateRight: "clamp",
      easing: Easing.in(Easing.quad),
    });
    return {
      opacity: 1 - p,
      transform: `translateY(${-p * 60}px) scale(${1 + p * 0.15})`,
      filter: `blur(${p * 8}px)`,
    };
  },

  /** Explode out — scale up rapidly */
  explode_out(frame: number, fps: number, durationFrames = 12): React.CSSProperties {
    const p = interpolate(frame, [0, durationFrames], [0, 1], {
      extrapolateRight: "clamp",
      easing: Easing.in(Easing.cubic),
    });
    return {
      opacity: interpolate(p, [0, 0.5, 1], [1, 0.5, 0]),
      transform: `scale(${1 + p * 3})`,
    };
  },

  /** Swipe wipe — clips away from side */
  swipe_wipe(frame: number, fps: number, durationFrames = 15): React.CSSProperties {
    const p = interpolate(frame, [0, durationFrames], [0, 1], {
      extrapolateRight: "clamp",
      easing: Easing.in(Easing.cubic),
    });
    return {
      clipPath: `inset(0 ${p * 100}% 0 0)`,
    };
  },

  /** Scale shrink — shrinks to nothing */
  scale_shrink(frame: number, fps: number, durationFrames = 15): React.CSSProperties {
    const p = interpolate(frame, [0, durationFrames], [0, 1], {
      extrapolateRight: "clamp",
    });
    return {
      opacity: 1 - p,
      transform: `scale(${1 - p})`,
    };
  },

  /** Blur exit — blur + fade */
  blur_exit(frame: number, fps: number, durationFrames = 15): React.CSSProperties {
    const p = interpolate(frame, [0, durationFrames], [0, 1], {
      extrapolateRight: "clamp",
    });
    return {
      opacity: 1 - p * 0.6,
      filter: `blur(${p * 15}px)`,
    };
  },

  /** Flick off — slides out to right quickly */
  flick_off(frame: number, fps: number, durationFrames = 12): React.CSSProperties {
    const p = interpolate(frame, [0, durationFrames], [0, 1], {
      extrapolateRight: "clamp",
      easing: Easing.in(Easing.cubic),
    });
    return {
      opacity: interpolate(p, [0.5, 1], [1, 0], { extrapolateLeft: "clamp" }),
      transform: `translateX(${p * 300}px) rotate(${p * 5}deg)`,
    };
  },

  /** Glitch out — digital distortion exit */
  glitch_out(frame: number, fps: number, durationFrames = 15): React.CSSProperties {
    const p = interpolate(frame, [0, durationFrames], [0, 1], {
      extrapolateRight: "clamp",
    });
    const glitch = Math.sin(frame * 25) * (1 - p) * 10;
    return {
      opacity: interpolate(p, [0, 0.5, 0.7, 1], [1, 0.8, 1, 0]),
      transform: `translateX(${glitch}px) skewX(${p * 10}deg)`,
    };
  },

  /** Vortex out — spins away */
  vortex_out(frame: number, fps: number, durationFrames = 18): React.CSSProperties {
    const p = interpolate(frame, [0, durationFrames], [0, 1], {
      extrapolateRight: "clamp",
      easing: Easing.in(Easing.cubic),
    });
    return {
      opacity: 1 - p,
      transform: `scale(${1 - p * 0.8}) rotate(${p * 360}deg)`,
    };
  },

  /** 3D flip out — flips away on Y axis */
  flip_out_3d(frame: number, fps: number, durationFrames = 18): React.CSSProperties {
    const p = interpolate(frame, [0, durationFrames], [0, 1], {
      extrapolateRight: "clamp",
      easing: Easing.in(Easing.cubic),
    });
    return {
      opacity: interpolate(p, [0, 0.5], [1, 0], { extrapolateRight: "clamp" }),
      transform: `perspective(600px) rotateY(${p * 90}deg)`,
      transformOrigin: "right center",
    };
  },

  /** Crumble — breaks apart */
  crumble(frame: number, fps: number, durationFrames = 20): React.CSSProperties {
    const p = interpolate(frame, [0, durationFrames], [0, 1], {
      extrapolateRight: "clamp",
    });
    return {
      opacity: 1 - p,
      transform: `translateY(${p * 80}px) scaleX(${1 + p * 0.3})`,
      filter: `blur(${p * 4}px)`,
    };
  },
};

// ═══════════════════════════════════════════════════
//  TEXT CONTINUOUS ANIMATIONS
// ═══════════════════════════════════════════════════

export const textContinuous = {
  /** No continuous effect */
  none(): React.CSSProperties {
    return {};
  },

  /** Gentle breathing — subtle scale pulse */
  breathe(frame: number, fps: number): React.CSSProperties {
    const t = frame / fps;
    const scale = 1 + 0.02 * Math.sin(2 * Math.PI * 0.4 * t);
    return { transform: `scale(${scale})` };
  },

  /** Glow pulse — text shadow intensity cycles */
  glow_pulse(frame: number, fps: number): React.CSSProperties {
    const t = frame / fps;
    const intensity = 0.3 + 0.4 * Math.sin(2 * Math.PI * 0.5 * t);
    return {
      textShadow: `0 0 ${intensity * 20}px rgba(255,136,0,${intensity}), 0 0 ${intensity * 40}px rgba(255,136,0,${intensity * 0.5})`,
    };
  },

  /** Shake — nervous tremor */
  shake(frame: number, fps: number): React.CSSProperties {
    const t = frame / fps;
    const x = 3 * Math.sin(t * 40) * Math.sin(t * 2);
    const y = 2 * Math.cos(t * 35) * Math.sin(t * 2);
    return { transform: `translate(${x}px, ${y}px)` };
  },

  /** Wave motion — gentle up/down oscillation */
  wave_motion(frame: number, fps: number): React.CSSProperties {
    const t = frame / fps;
    const y = 5 * Math.sin(2 * Math.PI * 0.8 * t);
    return { transform: `translateY(${y}px)` };
  },

  /** Float drift — slow horizontal/vertical drift */
  float_drift(frame: number, fps: number): React.CSSProperties {
    const t = frame / fps;
    const x = 4 * Math.sin(2 * Math.PI * 0.3 * t);
    const y = 3 * Math.cos(2 * Math.PI * 0.2 * t);
    return { transform: `translate(${x}px, ${y}px)` };
  },

  /** Flicker — horror/suspense strobe */
  flicker(frame: number, fps: number): React.CSSProperties {
    const t = frame / fps;
    const d = Math.sin(t * 20) * Math.sin(t * 7);
    const opacity = 0.7 + 0.3 * d;
    return { opacity };
  },

  /** Heartbeat — rhythmic scale pulse */
  heartbeat(frame: number, fps: number): React.CSSProperties {
    const t = frame / fps;
    const beat = Math.pow(Math.sin(Math.PI * t * 1.2), 2);
    const scale = 1 + 0.05 * beat;
    return { transform: `scale(${scale})` };
  },

  /** Pendulum — gentle rotation swing */
  pendulum(frame: number, fps: number): React.CSSProperties {
    const t = frame / fps;
    const angle = 3 * Math.sin(2 * Math.PI * 0.5 * t);
    return { transform: `rotate(${angle}deg)`, transformOrigin: "center top" };
  },

  /** Bounce — rhythmic vertical bounce */
  bounce(frame: number, fps: number): React.CSSProperties {
    const t = frame / fps;
    const y = -Math.abs(8 * Math.sin(2 * Math.PI * 0.8 * t));
    return { transform: `translateY(${y}px)` };
  },

  /** Fire flicker — warm color shift with opacity */
  fire_flicker(frame: number, fps: number): React.CSSProperties {
    const t = frame / fps;
    const opacity = 0.85 + 0.15 * Math.sin(t * 12);
    const hue = Math.sin(t * 5) * 10;
    return {
      opacity,
      filter: `hue-rotate(${hue}deg) brightness(${1 + 0.1 * Math.sin(t * 8)})`,
    };
  },

  /** 3D wobble — rotation on multiple axes */
  wobble_3d(frame: number, fps: number): React.CSSProperties {
    const t = frame / fps;
    const rx = 2 * Math.sin(2 * Math.PI * 0.4 * t);
    const ry = 3 * Math.cos(2 * Math.PI * 0.3 * t);
    return {
      transform: `perspective(500px) rotateX(${rx}deg) rotateY(${ry}deg)`,
    };
  },

  /** Neon flash — pulsing neon glow */
  neon_flash(frame: number, fps: number): React.CSSProperties {
    const t = frame / fps;
    const intensity = 0.5 + 0.5 * Math.pow(Math.sin(Math.PI * t * 2), 2);
    return {
      textShadow: `
        0 0 ${intensity * 10}px #ff00ff,
        0 0 ${intensity * 20}px #ff00ff,
        0 0 ${intensity * 40}px #ff0080,
        0 0 ${intensity * 80}px #ff0080
      `,
    };
  },

  /** Kinetic bounce — rhythmic vertical bounce like music video text */
  kinetic_bounce(frame: number, fps: number): React.CSSProperties {
    const t = frame / fps;
    const bounce = Math.abs(Math.sin(Math.PI * t * 1.5)) * 8;
    const squash = 1 + 0.03 * Math.sin(Math.PI * t * 3);
    return {
      transform: `translateY(${-bounce}px) scaleX(${squash}) scaleY(${2 - squash})`,
    };
  },

  /** Energy pulse — scale + brightness surge for impact moments */
  energy_pulse(frame: number, fps: number): React.CSSProperties {
    const t = frame / fps;
    const pulse = 1 + 0.04 * Math.sin(Math.PI * t * 3);
    const glow = 0.3 + 0.3 * Math.sin(Math.PI * t * 2);
    return {
      transform: `scale(${pulse})`,
      textShadow: `0 0 ${glow * 20}px rgba(255,180,0,${glow}), 0 2px 8px rgba(0,0,0,0.3)`,
    };
  },

  /** Magnetic drift — text subtly drifts left-right like floating in space */
  magnetic_drift(frame: number, fps: number): React.CSSProperties {
    const t = frame / fps;
    const dx = Math.sin(t * 0.8) * 6;
    const dy = Math.cos(t * 0.5) * 3;
    return {
      transform: `translate(${dx}px, ${dy}px)`,
    };
  },

  /** Cinematic letterpress — very subtle emboss/press effect */
  letterpress(frame: number, fps: number): React.CSSProperties {
    const t = frame / fps;
    const depth = 1 + 0.5 * Math.sin(t * 0.7);
    return {
      textShadow: `0 ${depth}px ${depth}px rgba(0,0,0,0.4), 0 -${depth * 0.3}px 0 rgba(255,255,255,0.15)`,
    };
  },

  /** Vibrate — quick shake for tension/suspense */
  vibrate(frame: number, fps: number): React.CSSProperties {
    const intensity = 2.5;
    const x = Math.sin(frame * 19) * intensity;
    const y = Math.cos(frame * 23) * intensity * 0.6;
    return {
      transform: `translate(${x}px, ${y}px)`,
    };
  },

  /** Spotlight sweep — text shadow moves across as if a light is passing */
  spotlight_sweep(frame: number, fps: number): React.CSSProperties {
    const t = frame / fps;
    const pos = Math.sin(t * 0.6) * 30;
    return {
      textShadow: `${pos}px 4px 16px rgba(255,200,100,0.5), 0 2px 6px rgba(0,0,0,0.3)`,
    };
  },
};

// ═══════════════════════════════════════════════════
//  DISPATCHER — maps effect name to function
// ═══════════════════════════════════════════════════

export type TextAnimFn = (frame: number, fps: number, ...args: any[]) => React.CSSProperties;

export function getTextEntryStyle(
  effectName: string,
  frame: number,
  fps: number,
  text?: string,
): React.CSSProperties {
  if (effectName === "typewriter") {
    return textEntry.typewriter(frame, fps, text);
  }
  const fn = (textEntry as Record<string, TextAnimFn>)[effectName];
  if (fn) return fn(frame, fps);
  // Fallback
  return textEntry.fade_in(frame, fps);
}

export function getTextExitStyle(
  effectName: string,
  frame: number,
  fps: number,
  durationFrames?: number,
): React.CSSProperties {
  const fn = (textExit as Record<string, TextAnimFn>)[effectName];
  if (fn) return fn(frame, fps, durationFrames);
  return textExit.fade_out(frame, fps);
}

export function getTextContinuousStyle(
  effectName: string,
  frame: number,
  fps: number,
): React.CSSProperties {
  if (effectName === "none") return {};
  const fn = (textContinuous as Record<string, TextAnimFn>)[effectName];
  if (fn) return fn(frame, fps);
  return {};
}
