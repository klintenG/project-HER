/**
 * Project HER v2.0 – Overlay Effects Library
 * ============================================
 * Full-screen overlays: grain, bokeh, particles, embers, scan-lines,
 * chromatic aberration, VHS distortion, rain, etc.
 * All implemented as React components using CSS/SVG.
 */

import React, { useMemo } from "react";
import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";

// Shared absolute-fill style
const FILL: React.CSSProperties = {
  position: "absolute",
  top: 0,
  left: 0,
  width: "100%",
  height: "100%",
  pointerEvents: "none",
};

// ── Film Grain Overlay ──
export const GrainOverlay: React.FC<{ intensity?: number }> = ({ intensity = 0.3 }) => {
  const frame = useCurrentFrame();
  // Animate background-position to create grain movement
  const x = (frame * 17) % 200;
  const y = (frame * 13) % 200;
  return (
    <div
      style={{
        ...FILL,
        opacity: intensity,
        mixBlendMode: "overlay",
        backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Cfilter id='g'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23g)' opacity='0.5'/%3E%3C/svg%3E")`,
        backgroundPosition: `${x}px ${y}px`,
      }}
    />
  );
};

// ── Bokeh Overlay ──
export const BokehOverlay: React.FC<{ count?: number }> = ({ count = 15 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const circles = useMemo(
    () =>
      Array.from({ length: count }).map((_, i) => ({
        x: ((i * 137.5) % 100),
        y: ((i * 73.7) % 100),
        r: 20 + (i % 5) * 15,
        speedX: 0.3 * Math.sin(i),
        speedY: 0.2 * Math.cos(i * 0.7),
        opacity: 0.06 + (i % 3) * 0.03,
      })),
    [count],
  );

  return (
    <div style={FILL}>
      {circles.map((c, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            left: `${(c.x + c.speedX * t * 20) % 100}%`,
            top: `${(c.y + c.speedY * t * 20) % 100}%`,
            width: c.r,
            height: c.r,
            borderRadius: "50%",
            background: `radial-gradient(circle, rgba(255,255,255,${c.opacity}) 0%, transparent 70%)`,
          }}
        />
      ))}
    </div>
  );
};

// ── Fire Embers Overlay ──
export const FireEmbersOverlay: React.FC<{ count?: number }> = ({ count = 25 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const embers = useMemo(
    () =>
      Array.from({ length: count }).map((_, i) => ({
        x: (i * 41.3) % 100,
        startY: 80 + (i % 4) * 5,
        speed: 15 + (i % 5) * 8,
        drift: 0.5 * Math.sin(i * 2.3),
        size: 2 + (i % 3) * 2,
        hue: i % 2 === 0 ? 20 : 35,
      })),
    [count],
  );

  return (
    <div style={FILL}>
      {embers.map((e, i) => {
        const y = e.startY - (t * e.speed) % (e.startY + 20);
        const x = e.x + Math.sin(t * 2 + i) * e.drift * 5;
        const opacity = interpolate(
          y,
          [0, e.startY * 0.3, e.startY],
          [0, 0.8, 0.4],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
        );
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: `${x}%`,
              top: `${y}%`,
              width: e.size,
              height: e.size,
              borderRadius: "50%",
              backgroundColor: `hsla(${e.hue}, 100%, 60%, ${opacity})`,
              boxShadow: `0 0 ${e.size * 2}px hsla(${e.hue}, 100%, 50%, ${opacity * 0.5})`,
            }}
          />
        );
      })}
    </div>
  );
};

// ── Sparkle Overlay ──
export const SparkleOverlay: React.FC<{ count?: number }> = ({ count = 20 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const sparkles = useMemo(
    () =>
      Array.from({ length: count }).map((_, i) => ({
        x: (i * 51.7) % 100,
        y: (i * 37.3) % 100,
        phase: i * 1.3,
        size: 3 + (i % 4) * 2,
      })),
    [count],
  );

  return (
    <div style={FILL}>
      {sparkles.map((s, i) => {
        const brightness = 0.5 + 0.5 * Math.sin(t * 4 + s.phase);
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: `${s.x}%`,
              top: `${s.y}%`,
              width: s.size,
              height: s.size,
              borderRadius: "50%",
              backgroundColor: `rgba(255, 255, 200, ${brightness * 0.6})`,
              boxShadow: `0 0 ${s.size * 3}px rgba(255, 255, 150, ${brightness * 0.4})`,
            }}
          />
        );
      })}
    </div>
  );
};

// ── Dust Particles ──
export const DustParticlesOverlay: React.FC<{ count?: number }> = ({ count = 30 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const particles = useMemo(
    () =>
      Array.from({ length: count }).map((_, i) => ({
        x: (i * 31.1) % 100,
        y: (i * 47.9) % 100,
        speedX: 0.2 * Math.sin(i * 1.7),
        speedY: -0.1 - (i % 3) * 0.05,
        size: 1 + (i % 3),
        opacity: 0.1 + (i % 4) * 0.05,
      })),
    [count],
  );

  return (
    <div style={FILL}>
      {particles.map((p, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            left: `${(p.x + p.speedX * t * 10 + 100) % 100}%`,
            top: `${(p.y + p.speedY * t * 10 + 100) % 100}%`,
            width: p.size,
            height: p.size,
            borderRadius: "50%",
            backgroundColor: `rgba(200, 190, 170, ${p.opacity})`,
          }}
        />
      ))}
    </div>
  );
};

// ── Scan Lines Overlay ──
export const ScanLinesOverlay: React.FC<{ spacing?: number; opacity?: number }> = ({
  spacing = 4,
  opacity = 0.15,
}) => {
  const frame = useCurrentFrame();
  const offset = (frame * 0.5) % spacing;
  return (
    <div
      style={{
        ...FILL,
        opacity,
        background: `repeating-linear-gradient(
          0deg,
          transparent,
          transparent ${spacing - 1}px,
          rgba(0,0,0,0.6) ${spacing - 1}px,
          rgba(0,0,0,0.6) ${spacing}px
        )`,
        backgroundPosition: `0 ${offset}px`,
        mixBlendMode: "multiply",
      }}
    />
  );
};

// ── Chromatic Aberration Overlay ──
export const ChromaticAberrationOverlay: React.FC<{ offset?: number }> = ({ offset = 3 }) => {
  return (
    <div
      style={{
        ...FILL,
        // CSS-based chromatic aberration using box-shadows on a transparent element
        // Applied as mix-blend-mode layers
      }}
    >
      <div
        style={{
          ...FILL,
          boxShadow: `${offset}px 0 0 rgba(255,0,0,0.1), ${-offset}px 0 0 rgba(0,0,255,0.1)`,
          mixBlendMode: "screen",
        }}
      />
    </div>
  );
};

// ── VHS Distortion Overlay ──
export const VHSDistortionOverlay: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const jitter = Math.sin(t * 30) * 2;
  const trackingLine = ((t * 200) % 110) - 5;

  return (
    <div style={FILL}>
      {/* Tracking line */}
      <div
        style={{
          position: "absolute",
          top: `${trackingLine}%`,
          left: 0,
          width: "100%",
          height: 3,
          backgroundColor: "rgba(255,255,255,0.1)",
          filter: "blur(1px)",
        }}
      />
      {/* Colour fringing */}
      <div
        style={{
          ...FILL,
          mixBlendMode: "screen",
          opacity: 0.1,
          background: `linear-gradient(${90 + jitter}deg, rgba(255,0,0,0.2), transparent, rgba(0,0,255,0.2))`,
        }}
      />
    </div>
  );
};

// ── Rain Overlay ──
export const RainOverlay: React.FC<{ count?: number }> = ({ count = 100 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const drops = useMemo(
    () =>
      Array.from({ length: count }).map((_, i) => ({
        x: (i * 13.7) % 100,
        speed: 30 + (i % 5) * 15,
        length: 10 + (i % 3) * 8,
        opacity: 0.15 + (i % 4) * 0.05,
      })),
    [count],
  );

  return (
    <div style={FILL}>
      {drops.map((d, i) => {
        const y = ((t * d.speed * 10) + d.x * 5) % 120 - 10;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: `${d.x}%`,
              top: `${y}%`,
              width: 1,
              height: d.length,
              backgroundColor: `rgba(180, 200, 220, ${d.opacity})`,
              transform: "rotate(10deg)",
            }}
          />
        );
      })}
    </div>
  );
};

// ═══════════════════════════════════════════════════
//  OVERLAY DISPATCHER
// ═══════════════════════════════════════════════════

const OVERLAY_MAP: Record<string, React.FC<any>> = {
  subtle_grain: GrainOverlay,
  bokeh_overlay: BokehOverlay,
  fire_embers: FireEmbersOverlay,
  sparkle_overlay: SparkleOverlay,
  dust_particles: DustParticlesOverlay,
  scan_lines: ScanLinesOverlay,
  chromatic_aberration: ChromaticAberrationOverlay,
  vhs_distortion: VHSDistortionOverlay,
  rain_overlay: RainOverlay,
  overlay_none: () => null,
};

export function getOverlayComponent(name: string): React.FC<any> {
  return OVERLAY_MAP[name] ?? (() => null);
}
