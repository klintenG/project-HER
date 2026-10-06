/**
 * Project HER v2.0 – Anti-Crop Watermark Component
 * ==================================================
 * Persistent, semi-transparent brand watermark positioned in the
 * content zone so it cannot be cropped out without destroying the video.
 *
 * Placement strategy:
 *   - Right-center: overlaps content area (uncrop-able)
 *   - Semi-transparent + subtle blur: visible but not distracting
 *   - Rotated -90°: reads vertically, stays out of text flow
 *   - Also small centered bottom text above platform UI
 *
 * The text overlaps actual video content so any crop/mask attempt
 * ruins the underlying imagery and narration text.
 */

import React from "react";
import { useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";

interface WatermarkProps {
  text: string;
  opacity?: number;
}

export const Watermark: React.FC<WatermarkProps> = ({
  text,
  opacity = 0.35,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();

  if (!text) return null;

  // Gentle fade-in on first appearance
  const fadeIn = spring({
    frame: Math.max(0, frame - 8),
    fps,
    config: { damping: 30, mass: 1.2 },
  });

  // Subtle breathing pulse (very slow, barely noticeable)
  const breathe = interpolate(
    Math.sin(frame / fps * 0.4),
    [-1, 1],
    [opacity * 0.9, opacity],
  );

  // Split "CREATIONS" into individual chars for exact width matching
  const creationsChars = "CREATIONS".split("");

  return (
    <>
      {/* ── Right-side horizontal watermark (anti-crop: overlaps content) ── */}
      <div
        style={{
          position: "absolute",
          right: width * 0.04,
          top: "50%",
          transform: "translateY(-50%)",
          opacity: breathe * fadeIn,
          zIndex: 90,
          pointerEvents: "none",
          display: "inline-flex",
          flexDirection: "column",
          alignItems: "stretch",
        }}
      >
        <span
          style={{
            fontFamily: "'Inter', 'SF Pro Display', 'Helvetica Neue', sans-serif",
            fontSize: 40,
            fontWeight: 700,
            color: "rgba(255,255,255,0.95)",
            letterSpacing: 4,
            textShadow: "0 2px 10px rgba(0,0,0,0.7), 0 0px 4px rgba(0,0,0,0.4)",
            lineHeight: 1,
            whiteSpace: "nowrap",
          }}
        >
          {text}
        </span>
        {/* CREATIONS — each letter spaced evenly to match Klin10 width exactly */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            marginTop: 3,
          }}
        >
          {creationsChars.map((char, i) => (
            <span
              key={i}
              style={{
                fontFamily: "'Inter', 'SF Pro Display', 'Helvetica Neue', sans-serif",
                fontSize: 12,
                fontWeight: 600,
                color: "rgba(255,255,255,0.85)",
                textShadow: "0 1px 6px rgba(0,0,0,0.6), 0 0px 3px rgba(0,0,0,0.3)",
                lineHeight: 1,
              }}
            >
              {char}
            </span>
          ))}
        </div>
      </div>

      {/* ── Bottom-center watermark (above platform UI, ~120px from bottom) ── */}
      <div
        style={{
          position: "absolute",
          bottom: 120,
          left: 0,
          right: 0,
          display: "flex",
          justifyContent: "center",
          opacity: breathe * fadeIn * 0.8,
          zIndex: 90,
          pointerEvents: "none",
        }}
      >
        <div
          style={{
            display: "inline-flex",
            flexDirection: "column",
            alignItems: "stretch",
          }}
        >
          <span
            style={{
              fontFamily: "'Inter', 'SF Pro Display', sans-serif",
              fontSize: 27,
              fontWeight: 600,
              color: "rgba(255,255,255,0.95)",
              letterSpacing: 3,
              textShadow: "0 2px 8px rgba(0,0,0,0.7), 0 0px 3px rgba(0,0,0,0.4)",
              lineHeight: 1,
              textAlign: "center",
              whiteSpace: "nowrap",
            }}
          >
            {text}
          </span>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              marginTop: 2,
            }}
          >
            {creationsChars.map((char, i) => (
              <span
                key={i}
                style={{
                  fontFamily: "'Inter', 'SF Pro Display', sans-serif",
                  fontSize: 8,
                  fontWeight: 600,
                  color: "rgba(255,255,255,0.8)",
                  textShadow: "0 1px 5px rgba(0,0,0,0.6)",
                  lineHeight: 1,
                }}
              >
                {char}
              </span>
            ))}
          </div>
        </div>
      </div>
    </>
  );
};

export default Watermark;
