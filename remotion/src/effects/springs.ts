/**
 * Project HER v2.0 – Remotion Spring Physics Library
 * ===================================================
 * Pre-configured spring physics for every animation type.
 * Uses Remotion's spring() for natural, physically-based motion.
 */

import { spring, SpringConfig } from "remotion";

// Helper type: Remotion's SpringConfig requires overshootClamping,
// but we usually just want damping/mass/stiffness as a partial.
type SpringPreset = Partial<SpringConfig>;

// ── Spring Presets ──

/** Snappy entrance — like a card flipping into view */
export const SPRING_SNAPPY: SpringPreset = { damping: 12, mass: 0.4, stiffness: 200 };

/** Bouncy entrance — playful overshoot */
export const SPRING_BOUNCY: SpringPreset = { damping: 8, mass: 0.6, stiffness: 180 };

/** Smooth glide — no overshoot, elegant */
export const SPRING_SMOOTH: SpringPreset = { damping: 20, mass: 1, stiffness: 100 };

/** Heavy slam — big impact, minimal bounce */
export const SPRING_HEAVY: SpringPreset = { damping: 15, mass: 2, stiffness: 200 };

/** Elastic wobble — jello-like squash and stretch */
export const SPRING_ELASTIC: SpringPreset = { damping: 6, mass: 0.5, stiffness: 280 };

/** Gentle float — dreamy, slow arrival */
export const SPRING_GENTLE: SpringPreset = { damping: 18, mass: 1.5, stiffness: 60 };

/** Quick pop — instant attention grab */
export const SPRING_POP: SpringPreset = { damping: 10, mass: 0.3, stiffness: 350 };

/** Dramatic entrance — slow, weighty, cinematic */
export const SPRING_DRAMATIC: SpringPreset = { damping: 14, mass: 2.5, stiffness: 150 };

/** Tension tremor — nervous, jittery */
export const SPRING_TREMOR: SpringPreset = { damping: 5, mass: 0.3, stiffness: 400 };

/** Soft landing — gentle deceleration */
export const SPRING_SOFT_LAND: SpringPreset = { damping: 22, mass: 1.2, stiffness: 80 };

// ── Spring-Based Animation Generators ──

export function springValue(
  frame: number,
  fps: number,
  config: SpringPreset = SPRING_SNAPPY,
  from = 0,
  to = 1,
  delay = 0,
): number {
  const s = spring({
    frame: frame - delay,
    fps,
    config,
    durationInFrames: 60,
  });
  return from + (to - from) * s;
}

/** Map emotion string to a spring preset */
export function emotionSpring(emotion: string): SpringPreset {
  const map: Record<string, SpringPreset> = {
    excitement: SPRING_BOUNCY,
    dramatic: SPRING_DRAMATIC,
    suspense: SPRING_TREMOR,
    calm: SPRING_GENTLE,
    sadness: SPRING_SOFT_LAND,
    anger: SPRING_HEAVY,
    awe: SPRING_SMOOTH,
    mystery: SPRING_GENTLE,
    joy: SPRING_ELASTIC,
    tension: SPRING_TREMOR,
    nostalgia: SPRING_SOFT_LAND,
    triumph: SPRING_POP,
    horror: SPRING_TREMOR,
    wonder: SPRING_BOUNCY,
    urgent: SPRING_POP,
    thoughtful: SPRING_SMOOTH,
    informative: SPRING_SNAPPY,
    neutral: SPRING_SNAPPY,
  };
  return map[emotion] ?? SPRING_SNAPPY;
}
