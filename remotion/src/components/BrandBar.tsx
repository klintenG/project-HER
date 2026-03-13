/**
 * Project HER v2.0 – BrandBar Component
 * =======================================
 * Sticky bottom brand bar with subtle animation.
 */

import React from "react";
import { useCurrentFrame, useVideoConfig, spring } from "remotion";

interface BrandBarProps {
  text: string;
  color?: string;
  textColor?: string;
}

export const BrandBar: React.FC<BrandBarProps> = ({
  text,
  color = "rgba(0,0,0,0.08)",
  textColor = "#333",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const slideUp = spring({
    frame: Math.max(0, frame - 5),
    fps,
    config: { damping: 18, mass: 0.6 },
  });

  if (!text) return null;

  return (
    <div
      style={{
        position: "absolute",
        bottom: 0,
        left: 0,
        right: 0,
        height: 60,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: color,
        backdropFilter: "blur(8px)",
        transform: `translateY(${(1 - slideUp) * 60}px)`,
        zIndex: 50,
      }}
    >
      <span
        style={{
          fontFamily: "'Inter', 'SF Pro Display', sans-serif",
          fontSize: 16,
          fontWeight: 700,
          color: textColor,
          letterSpacing: 2,
          textTransform: "uppercase",
        }}
      >
        {text}
      </span>
    </div>
  );
};

export default BrandBar;
