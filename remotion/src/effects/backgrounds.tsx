/**
 * Project HER v2.0 – Background Effects Library
 * ===============================================
 * Animated backgrounds: gradient shifts, pulses, particle floats,
 * color breathing, aurora, and more.
 */

import React, { useMemo } from "react";
import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { rgbToCSS } from "../types";

const FILL: React.CSSProperties = {
  position: "absolute",
  top: 0,
  left: 0,
  width: "100%",
  height: "100%",
};

// ── Color Breathe Background ──
export const BgColorBreathe: React.FC<{
  baseColor: [number, number, number];
  amount?: number;
}> = ({ baseColor, amount = 0.08 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const shift = amount * Math.sin(2 * Math.PI * 0.3 * t);
  const r = Math.round(Math.min(255, Math.max(0, baseColor[0] * (1 + shift))));
  const g = Math.round(Math.min(255, Math.max(0, baseColor[1] * (1 + shift * 0.7))));
  const b = Math.round(Math.min(255, Math.max(0, baseColor[2] * (1 + shift * 0.4))));
  return <div style={{ ...FILL, backgroundColor: `rgb(${r},${g},${b})` }} />;
};

// ── Gradient Shift Background ──
export const BgGradientShift: React.FC<{
  color1: [number, number, number];
  color2: [number, number, number];
}> = ({ color1, color2 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const angle = 135 + 30 * Math.sin(2 * Math.PI * 0.2 * t);
  return (
    <div
      style={{
        ...FILL,
        background: `linear-gradient(${angle}deg, ${rgbToCSS(color1)}, ${rgbToCSS(color2)})`,
      }}
    />
  );
};

// ── Pulse Background ──
export const BgPulse: React.FC<{
  baseColor: [number, number, number];
  amount?: number;
}> = ({ baseColor, amount = 0.2 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const brightness = 1 + amount * Math.sin(2 * Math.PI * 0.6 * t);
  return (
    <div
      style={{
        ...FILL,
        backgroundColor: rgbToCSS(baseColor),
        filter: `brightness(${brightness})`,
      }}
    />
  );
};

// ── Particle Float Background ──
export const BgParticleFloat: React.FC<{
  baseColor: [number, number, number];
  count?: number;
}> = ({ baseColor, count = 20 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const particles = useMemo(
    () =>
      Array.from({ length: count }).map((_, i) => ({
        x: (i * 47.3) % 100,
        y: (i * 31.7) % 100,
        speedX: 0.3 * Math.sin(i * 2.1),
        speedY: 0.2 * Math.cos(i * 1.3),
        radius: 2 + (i % 4) * 1.5,
        opacity: 0.08 + (i % 3) * 0.04,
      })),
    [count],
  );

  return (
    <div style={{ ...FILL, backgroundColor: rgbToCSS(baseColor) }}>
      {particles.map((p, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            left: `${(p.x + p.speedX * t * 15 + 100) % 100}%`,
            top: `${(p.y + p.speedY * t * 15 + 100) % 100}%`,
            width: p.radius * 2,
            height: p.radius * 2,
            borderRadius: "50%",
            backgroundColor: `rgba(200, 200, 255, ${p.opacity + 0.03 * Math.sin(t + i)})`,
          }}
        />
      ))}
    </div>
  );
};

// ── Aurora Background ──
export const BgAurora: React.FC<{
  baseColor: [number, number, number];
}> = ({ baseColor }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const angle1 = 135 + 60 * Math.sin(2 * Math.PI * 0.1 * t);
  const angle2 = 225 + 45 * Math.cos(2 * Math.PI * 0.15 * t);
  return (
    <div
      style={{
        ...FILL,
        background: `
          linear-gradient(${angle1}deg, rgba(100,200,150,0.3), transparent 60%),
          linear-gradient(${angle2}deg, rgba(100,150,255,0.2), transparent 70%),
          ${rgbToCSS(baseColor)}
        `,
      }}
    />
  );
};

// ── Radial Pulse Background ──
export const BgRadialPulse: React.FC<{
  baseColor: [number, number, number];
}> = ({ baseColor }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const size = 50 + 20 * Math.sin(2 * Math.PI * 0.4 * t);
  return (
    <div
      style={{
        ...FILL,
        background: `radial-gradient(circle at 50% 50%, rgba(255,255,255,0.15) 0%, transparent ${size}%), ${rgbToCSS(baseColor)}`,
      }}
    />
  );
};

// ═══════════════════════════════════════════════════
//  BACKGROUND DISPATCHER
// ═══════════════════════════════════════════════════

const BG_MAP: Record<string, React.FC<any>> = {
  bg_color_breathe: BgColorBreathe,
  bg_gradient_shift: BgGradientShift,
  bg_pulse: BgPulse,
  bg_particle_float: BgParticleFloat,
  bg_aurora: BgAurora,
  bg_radial_pulse: BgRadialPulse,
  bg_none: ({ baseColor }: { baseColor: [number, number, number] }) =>
    React.createElement("div", { style: { ...FILL, backgroundColor: rgbToCSS(baseColor) } }),
};

export function getBackgroundComponent(name: string): React.FC<any> {
  return BG_MAP[name] ?? BG_MAP.bg_none;
}
