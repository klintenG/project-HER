/**
 * Project HER v2.0 – Image Animation Library
 * ============================================
 * Cinematic image effects using CSS transforms &amp; Remotion spring physics.
 * Ken Burns, zoom pulse, parallax, 3D rotations, and more.
 */

import { interpolate, spring, Easing } from "remotion";
import {
  SPRING_SNAPPY, SPRING_BOUNCY, SPRING_SMOOTH, SPRING_GENTLE,
  SPRING_POP, SPRING_DRAMATIC,
} from "./springs";

// ═══════════════════════════════════════════════════
//  IMAGE ENTRY ANIMATIONS
// ═══════════════════════════════════════════════════

export const imageEntry = {
  /** Fade in */
  img_fade_in(frame: number, fps: number, durationFrames = 20): React.CSSProperties {
    const opacity = interpolate(frame, [0, durationFrames], [0, 1], {
      extrapolateRight: "clamp",
    });
    return { opacity };
  },

  /** Scale bounce in */
  img_scale_bounce(frame: number, fps: number): React.CSSProperties {
    const s = spring({ frame, fps, config: SPRING_BOUNCY, durationInFrames: 30 });
    return {
      opacity: interpolate(s, [0, 0.3], [0, 1], { extrapolateRight: "clamp" }),
      transform: `scale(${interpolate(s, [0, 1], [0.5, 1])})`,
    };
  },

  /** Zoom in from far */
  img_zoom_in(frame: number, fps: number): React.CSSProperties {
    const s = spring({ frame, fps, config: SPRING_DRAMATIC, durationInFrames: 35 });
    return {
      opacity: interpolate(s, [0, 0.4], [0, 1], { extrapolateRight: "clamp" }),
      transform: `scale(${interpolate(s, [0, 1], [0.1, 1])})`,
      filter: `blur(${interpolate(s, [0, 1], [8, 0])}px)`,
    };
  },

  /** Blur reveal */
  img_blur_reveal(frame: number, fps: number, durationFrames = 25): React.CSSProperties {
    const p = interpolate(frame, [0, durationFrames], [0, 1], { extrapolateRight: "clamp" });
    return {
      opacity: p,
      filter: `blur(${interpolate(p, [0, 1], [25, 0])}px)`,
    };
  },

  /** Slide in from left */
  img_slide_left(frame: number, fps: number): React.CSSProperties {
    const s = spring({ frame, fps, config: SPRING_SNAPPY, durationInFrames: 25 });
    return {
      opacity: interpolate(s, [0, 0.5], [0, 1], { extrapolateRight: "clamp" }),
      transform: `translateX(${interpolate(s, [0, 1], [-300, 0])}px)`,
    };
  },

  /** 3D perspective entrance */
  img_3d_entrance(frame: number, fps: number): React.CSSProperties {
    const s = spring({ frame, fps, config: SPRING_DRAMATIC, durationInFrames: 35 });
    return {
      opacity: interpolate(s, [0, 0.3], [0, 1], { extrapolateRight: "clamp" }),
      transform: `perspective(1200px) rotateY(${interpolate(s, [0, 1], [-45, 0])}deg) translateZ(${interpolate(s, [0, 1], [-200, 0])}px)`,
    };
  },
};

// ═══════════════════════════════════════════════════
//  IMAGE TREATMENT (during display)
// ═══════════════════════════════════════════════════

export const imageTreatment = {
  /** Ken Burns — slow zoom + pan */
  ken_burns(frame: number, fps: number, durationFrames: number, direction = 1): React.CSSProperties {
    const p = interpolate(frame, [0, durationFrames], [0, 1], { extrapolateRight: "clamp" });
    const zoom = 1 + 0.18 * p;
    const panX = direction * 5 * p;
    const panY = 3 * p;
    return {
      transform: `scale(${zoom}) translate(${panX}%, ${panY}%)`,
    };
  },

  /** Zoom pulse — rhythmic breathing zoom */
  zoom_pulse(frame: number, fps: number): React.CSSProperties {
    const t = frame / fps;
    const zoom = 1 + 0.06 * Math.sin(2 * Math.PI * 0.4 * t);
    return { transform: `scale(${zoom})` };
  },

  /** 2D parallax shift */
  parallax_2d(frame: number, fps: number, durationFrames: number): React.CSSProperties {
    const p = interpolate(frame, [0, durationFrames], [-1, 1], { extrapolateRight: "clamp" });
    return {
      transform: `translate(${p * 5}%, ${p * 3}%)`,
    };
  },

  /** Brightness pulse */
  brightness_pulse(frame: number, fps: number): React.CSSProperties {
    const t = frame / fps;
    const b = 1 + 0.15 * Math.sin(2 * Math.PI * 0.5 * t);
    return {
      filter: `brightness(${b})`,
    };
  },

  /** Color temperature shift over time */
  color_shift(frame: number, fps: number, durationFrames: number): React.CSSProperties {
    const p = interpolate(frame, [0, durationFrames], [0, 1], { extrapolateRight: "clamp" });
    const hue = interpolate(p, [0, 1], [0, 20]);
    const sat = interpolate(p, [0, 0.5, 1], [1, 1.2, 1]);
    return {
      filter: `hue-rotate(${hue}deg) saturate(${sat})`,
    };
  },

  /** Vignette — dark edges */
  vignette(_frame: number, _fps: number): React.CSSProperties {
    return {
      boxShadow: "inset 0 0 120px 60px rgba(0,0,0,0.5)",
    };
  },

  /** Tilt shift — blur top/bottom */
  tilt_shift(_frame: number, _fps: number): React.CSSProperties {
    return {
      // CSS tilt-shift approximation using mask
      maskImage: "linear-gradient(to bottom, transparent, black 30%, black 70%, transparent)",
      WebkitMaskImage: "linear-gradient(to bottom, transparent, black 30%, black 70%, transparent)",
    };
  },

  /** Sepia blend over time */
  sepia_blend(frame: number, fps: number, durationFrames: number): React.CSSProperties {
    const p = interpolate(frame, [0, durationFrames], [0, 1], { extrapolateRight: "clamp" });
    return {
      filter: `sepia(${0.3 + 0.3 * p})`,
    };
  },

  /** Desaturate to color — gradual color drain */
  desaturate_to_color(frame: number, fps: number, durationFrames: number): React.CSSProperties {
    const p = interpolate(frame, [0, durationFrames], [0, 1], { extrapolateRight: "clamp" });
    return {
      filter: `saturate(${1 - 0.6 * p})`,
    };
  },

  /** 3D gentle tilt — slow perspective rotation */
  gentle_3d_tilt(frame: number, fps: number, durationFrames: number): React.CSSProperties {
    const p = interpolate(frame, [0, durationFrames], [0, 1], { extrapolateRight: "clamp" });
    const rx = 5 * Math.sin(2 * Math.PI * p);
    const ry = 3 * Math.cos(2 * Math.PI * p);
    return {
      transform: `perspective(1000px) rotateX(${rx}deg) rotateY(${ry}deg) scale(${1 + 0.05 * Math.sin(Math.PI * p)})`,
    };
  },

  /** Film grain overlay via CSS */
  film_grain(_frame: number, _fps: number): React.CSSProperties {
    return {
      filter: "contrast(1.1) brightness(0.95)",
    };
  },

  /** Cinematic letterbox */
  cinematic_crop(_frame: number, _fps: number): React.CSSProperties {
    return {
      clipPath: "inset(8% 0 8% 0)",
    };
  },
};

// ═══════════════════════════════════════════════════
//  IMAGE EXIT ANIMATIONS
// ═══════════════════════════════════════════════════

export const imageExit = {
  /** Fade out */
  img_fade_out(frame: number, fps: number, durationFrames = 15): React.CSSProperties {
    const opacity = interpolate(frame, [0, durationFrames], [1, 0], {
      extrapolateRight: "clamp",
    });
    return { opacity };
  },

  /** Zoom out */
  img_zoom_out(frame: number, fps: number, durationFrames = 18): React.CSSProperties {
    const p = interpolate(frame, [0, durationFrames], [0, 1], {
      extrapolateRight: "clamp",
      easing: Easing.in(Easing.cubic),
    });
    return {
      opacity: 1 - p,
      transform: `scale(${1 + p * 0.5})`,
    };
  },

  /** Blur out */
  img_blur_out(frame: number, fps: number, durationFrames = 15): React.CSSProperties {
    const p = interpolate(frame, [0, durationFrames], [0, 1], {
      extrapolateRight: "clamp",
    });
    return {
      opacity: 1 - p * 0.5,
      filter: `blur(${p * 20}px)`,
    };
  },
};

// ═══════════════════════════════════════════════════
//  DISPATCHERS
// ═══════════════════════════════════════════════════

type ImageAnimFn = (frame: number, fps: number, ...args: any[]) => React.CSSProperties;

export function getImageEntryStyle(name: string, frame: number, fps: number): React.CSSProperties {
  const fn = (imageEntry as Record<string, ImageAnimFn>)[name];
  return fn ? fn(frame, fps) : imageEntry.img_fade_in(frame, fps);
}

export function getImageTreatmentStyle(
  name: string,
  frame: number,
  fps: number,
  durationFrames: number,
): React.CSSProperties {
  const fn = (imageTreatment as Record<string, ImageAnimFn>)[name];
  return fn ? fn(frame, fps, durationFrames) : {};
}

export function getImageExitStyle(name: string, frame: number, fps: number, durationFrames?: number): React.CSSProperties {
  const fn = (imageExit as Record<string, ImageAnimFn>)[name];
  return fn ? fn(frame, fps, durationFrames) : imageExit.img_fade_out(frame, fps);
}
