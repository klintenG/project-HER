/**
 * Project HER v2.0 – Scene Transition Library
 * =============================================
 * Cinematic scene transitions using @remotion/transitions
 * and custom CSS-powered transition presentations.
 *
 * Available transitions:
 * - crossfade, flash_transition, circle_wipe, slide_horizontal
 * - wipe_left, ink_bleed, blur_transition, pixelate_transition
 * - zoom_in, zoom_out, elastic_bounce, glitch_transition
 * - 3D cube rotate, 3D page flip, dissolve
 */

import { interpolate, Easing } from "remotion";

/** Transition timing configuration */
export interface TransitionTiming {
  durationInFrames: number;
  enterStyle: (progress: number) => React.CSSProperties;
  exitStyle: (progress: number) => React.CSSProperties;
}

// ═══════════════════════════════════════════════════
//  TRANSITION DEFINITIONS
// ═══════════════════════════════════════════════════

export const transitions = {
  /** Simple crossfade */
  crossfade(durationInFrames = 15): TransitionTiming {
    return {
      durationInFrames,
      enterStyle: (p) => ({ opacity: p }),
      exitStyle: (p) => ({ opacity: 1 - p }),
    };
  },

  /** Flash — white flash between scenes */
  flash_transition(durationInFrames = 12): TransitionTiming {
    return {
      durationInFrames,
      enterStyle: (p) => ({
        opacity: interpolate(p, [0, 0.3, 1], [0, 0, 1]),
        filter: `brightness(${interpolate(p, [0, 0.3, 0.5, 1], [3, 3, 1.5, 1])})`,
      }),
      exitStyle: (p) => ({
        opacity: interpolate(p, [0, 0.3, 1], [1, 0.5, 0]),
        filter: `brightness(${interpolate(p, [0, 0.3, 1], [1, 3, 3])})`,
      }),
    };
  },

  /** Circle wipe — expanding circle reveals next scene */
  circle_wipe(durationInFrames = 20): TransitionTiming {
    return {
      durationInFrames,
      enterStyle: (p) => ({
        clipPath: `circle(${p * 150}% at 50% 50%)`,
      }),
      exitStyle: (p) => ({
        clipPath: `circle(${(1 - p) * 150}% at 50% 50%)`,
      }),
    };
  },

  /** Horizontal slide — next scene pushes in from right */
  slide_horizontal(durationInFrames = 18): TransitionTiming {
    const ease = (p: number) => {
      const t = p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
      return t;
    };
    return {
      durationInFrames,
      enterStyle: (p) => ({
        transform: `translateX(${(1 - ease(p)) * 100}%)`,
      }),
      exitStyle: (p) => ({
        transform: `translateX(${-ease(p) * 100}%)`,
      }),
    };
  },

  /** Wipe left — hard edge wipe from right to left */
  wipe_left(durationInFrames = 15): TransitionTiming {
    return {
      durationInFrames,
      enterStyle: (p) => ({
        clipPath: `inset(0 ${(1 - p) * 100}% 0 0)`,
      }),
      exitStyle: () => ({}),
    };
  },

  /** Wipe right */
  wipe_right(durationInFrames = 15): TransitionTiming {
    return {
      durationInFrames,
      enterStyle: (p) => ({
        clipPath: `inset(0 0 0 ${(1 - p) * 100}%)`,
      }),
      exitStyle: () => ({}),
    };
  },

  /** Ink bleed — organic blob-like mask expansion */
  ink_bleed(durationInFrames = 22): TransitionTiming {
    return {
      durationInFrames,
      enterStyle: (p) => {
        const r1 = p * 80;
        const r2 = p * 60;
        const r3 = p * 90;
        return {
          clipPath: `polygon(
            ${50 - r1}% ${50 - r2}%,
            ${50 + r2}% ${50 - r3}%,
            ${50 + r1}% ${50 + r2}%,
            ${50 - r3}% ${50 + r1}%
          )`,
        };
      },
      exitStyle: (p) => ({ opacity: 1 - p }),
    };
  },

  /** Blur transition — blur out / blur in */
  blur_transition(durationInFrames = 16): TransitionTiming {
    return {
      durationInFrames,
      enterStyle: (p) => ({
        opacity: interpolate(p, [0.3, 1], [0, 1], { extrapolateLeft: "clamp" }),
        filter: `blur(${interpolate(p, [0.3, 1], [20, 0])}px)`,
      }),
      exitStyle: (p) => ({
        opacity: interpolate(p, [0, 0.7], [1, 0], { extrapolateRight: "clamp" }),
        filter: `blur(${interpolate(p, [0, 0.7], [0, 20])}px)`,
      }),
    };
  },

  /** Pixelate transition — pixelates out, sharpens in */
  pixelate_transition(durationInFrames = 16): TransitionTiming {
    return {
      durationInFrames,
      // Using CSS filter: can't truly pixelate, but we can simulate with blur + contrast
      enterStyle: (p) => ({
        opacity: interpolate(p, [0.3, 1], [0, 1], { extrapolateLeft: "clamp" }),
        filter: `blur(${interpolate(p, [0, 0.5, 1], [8, 3, 0])}px) contrast(${interpolate(p, [0, 0.5, 1], [1.5, 1.2, 1])})`,
      }),
      exitStyle: (p) => ({
        opacity: interpolate(p, [0, 0.7], [1, 0], { extrapolateRight: "clamp" }),
        filter: `blur(${interpolate(p, [0, 0.5, 0.7], [0, 5, 8])}px)`,
      }),
    };
  },

  /** Zoom in — next scene zooms in from big */
  zoom_in(durationInFrames = 18): TransitionTiming {
    return {
      durationInFrames,
      enterStyle: (p) => ({
        opacity: interpolate(p, [0, 0.5], [0, 1], { extrapolateRight: "clamp" }),
        transform: `scale(${interpolate(p, [0, 1], [0.3, 1])})`,
      }),
      exitStyle: (p) => ({
        opacity: interpolate(p, [0, 0.5], [1, 0], { extrapolateRight: "clamp" }),
        transform: `scale(${interpolate(p, [0, 1], [1, 1.5])})`,
      }),
    };
  },

  /** Zoom out */
  zoom_out(durationInFrames = 18): TransitionTiming {
    return {
      durationInFrames,
      enterStyle: (p) => ({
        opacity: interpolate(p, [0, 0.5], [0, 1], { extrapolateRight: "clamp" }),
        transform: `scale(${interpolate(p, [0, 1], [1.5, 1])})`,
      }),
      exitStyle: (p) => ({
        opacity: interpolate(p, [0, 0.5], [1, 0], { extrapolateRight: "clamp" }),
        transform: `scale(${interpolate(p, [0, 1], [1, 0.3])})`,
      }),
    };
  },

  /** Elastic bounce — scene bounces into place */
  elastic_bounce(durationInFrames = 25): TransitionTiming {
    return {
      durationInFrames,
      enterStyle: (p) => {
        // Elastic easing
        const elastic = p === 0 ? 0 : p === 1 ? 1
          : Math.pow(2, -10 * p) * Math.sin((p * 10 - 0.75) * (2 * Math.PI / 3)) + 1;
        return {
          transform: `translateY(${(1 - elastic) * 100}%)`,
        };
      },
      exitStyle: (p) => ({ opacity: 1 - p }),
    };
  },

  /** Glitch transition — digital break between scenes */
  glitch_transition(durationInFrames = 14): TransitionTiming {
    return {
      durationInFrames,
      enterStyle: (p) => {
        const sliceOffset = Math.sin(p * 50) * (1 - p) * 20;
        return {
          opacity: interpolate(p, [0, 0.5, 1], [0, 0.7, 1]),
          transform: `translateX(${sliceOffset}px) skewX(${(1 - p) * 5}deg)`,
        };
      },
      exitStyle: (p) => {
        const sliceOffset = Math.sin(p * 50) * p * 15;
        return {
          opacity: interpolate(p, [0, 0.5, 1], [1, 0.5, 0]),
          transform: `translateX(${sliceOffset}px) skewX(${p * 5}deg)`,
        };
      },
    };
  },

  /** 3D Cube Rotate — rotates on Y axis like a cube face */
  cube_rotate_3d(durationInFrames = 22): TransitionTiming {
    return {
      durationInFrames,
      enterStyle: (p) => ({
        transform: `perspective(1200px) rotateY(${(1 - p) * -90}deg)`,
        transformOrigin: "right center",
        opacity: interpolate(p, [0, 0.3], [0, 1], { extrapolateRight: "clamp" }),
      }),
      exitStyle: (p) => ({
        transform: `perspective(1200px) rotateY(${p * 90}deg)`,
        transformOrigin: "left center",
        opacity: interpolate(p, [0.7, 1], [1, 0], { extrapolateLeft: "clamp" }),
      }),
    };
  },

  /** 3D page flip — flips like a book page */
  page_flip_3d(durationInFrames = 22): TransitionTiming {
    return {
      durationInFrames,
      enterStyle: (p) => ({
        transform: `perspective(1500px) rotateY(${(1 - p) * 180}deg)`,
        transformOrigin: "left center",
        backfaceVisibility: "hidden" as const,
      }),
      exitStyle: (p) => ({
        transform: `perspective(1500px) rotateY(${-p * 180}deg)`,
        transformOrigin: "left center",
        backfaceVisibility: "hidden" as const,
      }),
    };
  },

  /** Dissolve — granular dissolve using CSS gradient masks */
  dissolve(durationInFrames = 20): TransitionTiming {
    return {
      durationInFrames,
      enterStyle: (p) => ({
        opacity: p,
        filter: `blur(${(1 - p) * 3}px)`,
      }),
      exitStyle: (p) => ({
        opacity: 1 - p,
        filter: `blur(${p * 3}px)`,
        mixBlendMode: "normal" as const,
      }),
    };
  },

  /** Vertical wipe — wipes from top to bottom */
  wipe_down(durationInFrames = 15): TransitionTiming {
    return {
      durationInFrames,
      enterStyle: (p) => ({
        clipPath: `inset(0 0 ${(1 - p) * 100}% 0)`,
      }),
      exitStyle: () => ({}),
    };
  },

  /** Morph — scale + blur + crossfade */
  morph(durationInFrames = 20): TransitionTiming {
    return {
      durationInFrames,
      enterStyle: (p) => ({
        opacity: interpolate(p, [0.2, 1], [0, 1], { extrapolateLeft: "clamp" }),
        transform: `scale(${interpolate(p, [0, 1], [0.8, 1])})`,
        filter: `blur(${(1 - p) * 10}px)`,
      }),
      exitStyle: (p) => ({
        opacity: interpolate(p, [0, 0.8], [1, 0], { extrapolateRight: "clamp" }),
        transform: `scale(${interpolate(p, [0, 1], [1, 1.2])})`,
        filter: `blur(${p * 10}px)`,
      }),
    };
  },
};

// ═══════════════════════════════════════════════════
//  DISPATCHER
// ═══════════════════════════════════════════════════

export function getTransition(name: string, durationInFrames?: number): TransitionTiming {
  const fn = (transitions as Record<string, (d?: number) => TransitionTiming>)[name];
  if (fn) return fn(durationInFrames);
  return transitions.crossfade(durationInFrames);
}
