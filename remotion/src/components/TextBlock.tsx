/**
 * Project HER v2.0 – TextBlock Component
 * ========================================
 * Renders narration text with karaoke word highlighting,
 * animated entry/exit/continuous effects, and emphasis styling.
 */

import React, { useMemo } from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Easing,
} from "remotion";
import { getTextEntryStyle, getTextExitStyle, getTextContinuousStyle } from "../effects/textAnimations";
import { ScreenData, SceneEffectsPlan, rgbToCSS, VisualStyle, WordTiming } from "../types";

// ═══════════════════════════════════════════════════
//  KARAOKE WORD
// ═══════════════════════════════════════════════════

interface KaraokeWordProps {
  word: string;
  timing: WordTiming;
  isEmphasis: boolean;
  emphasisStyle: string;
  highlightColor: string;
  highlightText: string;
  baseColor: string;
  fontSize: number;
  sceneStartFrame: number;
}

const KaraokeWord: React.FC<KaraokeWordProps> = ({
  word,
  timing,
  isEmphasis,
  emphasisStyle,
  highlightColor,
  highlightText,
  baseColor,
  fontSize,
  sceneStartFrame,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // useCurrentFrame() inside <Sequence> already returns the local frame
  const localFrame = frame;
  const currentTime = localFrame / fps;

  // Is this word currently being spoken?
  const isActive = currentTime >= timing.start && currentTime <= timing.end;
  const isPast = currentTime > timing.end;
  const wordProgress = isActive
    ? interpolate(currentTime, [timing.start, timing.end], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
    : isPast ? 1 : 0;

  // ── Smooth highlight animation using interpolate (NOT CSS transitions) ──
  // CSS transitions don't work in Remotion's frame-by-frame rendering.
  // Use frame-based interpolation for smooth karaoke effect.
  const wordStartFrame = Math.round(timing.start * fps);
  const wordEndFrame = Math.round(timing.end * fps);
  const fadeInFrames = 4; // ~133ms smooth fade-in
  const fadeOutFrames = 6; // ~200ms smooth fade-out

  // Highlight intensity: 0 = inactive, 1 = fully active
  let highlightIntensity = 0;
  if (isActive) {
    // Fade in at the start of the word
    highlightIntensity = interpolate(
      localFrame,
      [wordStartFrame, wordStartFrame + fadeInFrames],
      [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
    );
  } else if (isPast) {
    // Fade out after the word ends
    highlightIntensity = interpolate(
      localFrame,
      [wordEndFrame, wordEndFrame + fadeOutFrames],
      [1, 0],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
    );
  }

  // Scale animation using spring (already works since it's frame-based)
  const highlightSpring = spring({
    frame: isActive ? Math.floor((currentTime - timing.start) * fps) : 0,
    fps,
    config: { damping: 12, mass: 0.5, stiffness: 200 },
  });

  const scaleVal = isActive
    ? 1 + highlightSpring * 0.08
    : isEmphasis && isPast ? 1.02 : 1;

  // Interpolated colors and background
  const bgOpacity = highlightIntensity;
  const textOpacity = isPast ? 1 : (0.65 + 0.35 * highlightIntensity);

  const style: React.CSSProperties = {
    display: "inline-block",
    fontFamily: "'Inter', 'SF Pro Display', sans-serif",
    fontSize,
    fontWeight: isEmphasis ? 800 : 600,
    lineHeight: 1.4,
    margin: "0 3px",
    padding: "2px 6px",
    borderRadius: 6,
    // NO CSS transition — use frame-interpolated values instead
    color: highlightIntensity > 0.5 ? highlightText : baseColor,
    opacity: textOpacity,
    backgroundColor: `rgba(${highlightColor.replace(/[^\d,]/g, '')}, ${bgOpacity * 0.9})`,
    transform: `scale(${scaleVal})`,
    textShadow: highlightIntensity > 0.3
      ? `0 0 ${20 * highlightIntensity}px ${highlightColor}88`
      : "none",
  };

  // Emphasis styling
  if (isEmphasis && !isActive) {
    switch (emphasisStyle) {
      case "bold":
        style.fontWeight = 900;
        break;
      case "color":
        style.color = highlightColor;
        break;
      case "scale":
        style.transform = "scale(1.1)";
        break;
      case "pulse":
        style.animation = "emphasisPulse 1s ease-in-out infinite";
        break;
    }
  }

  return <span style={style}>{word} </span>;
};

// ═══════════════════════════════════════════════════
//  TEXT BLOCK
// ═══════════════════════════════════════════════════

interface TextBlockProps {
  screen: ScreenData;
  effects: SceneEffectsPlan;
  style: VisualStyle;
  sceneStartFrame: number;
  sceneDurationFrames: number;
  layoutMode?: "classic" | "fullbleed";
}

export const TextBlock: React.FC<TextBlockProps> = ({
  screen,
  effects,
  style: vs,
  sceneStartFrame,
  sceneDurationFrames,
  layoutMode = "classic",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // useCurrentFrame() inside <Sequence> already returns the local frame
  const localFrame = frame;
  const progress = localFrame / sceneDurationFrames;

  // Effect timings: entry for first 15%, exit for last 15%
  const entryEnd = 0.15;
  const exitStart = 0.85;

  const entryProgress = interpolate(progress, [0, entryEnd], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const exitProgress = interpolate(progress, [exitStart, 1], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Get CSS styles from effects
  // Frame-based calculations: map progress to frame-within-effect
  const entryFrames = Math.round(sceneDurationFrames * entryEnd);
  const entryFrame = Math.min(localFrame, entryFrames);
  const exitFrames = Math.round(sceneDurationFrames * (1 - exitStart));
  const exitFrame = progress > exitStart ? localFrame - Math.round(sceneDurationFrames * exitStart) : 0;

  const entryStyle = getTextEntryStyle(effects.text_entry, entryFrame, fps, screen.text);
  const exitStyle = progress > exitStart
    ? getTextExitStyle(effects.text_exit, exitFrame, fps)
    : {};
  const continuousStyle = getTextContinuousStyle(
    effects.text_continuous,
    localFrame,
    fps,
  );

  // Merge effect styles
  const mergedEffectStyle: React.CSSProperties = {
    ...continuousStyle,
    ...entryStyle,
    ...(progress > exitStart ? exitStyle : {}),
  };

  // Emphasis words lookup
  const emphasisSet = useMemo(() => {
    const set = new Set<string>();
    for (const ew of screen.emphasis_words || []) {
      set.add(ew.text.toLowerCase());
    }
    return set;
  }, [screen.emphasis_words]);

  const emphasisStyleMap = useMemo(() => {
    const map: Record<string, string> = {};
    for (const ew of screen.emphasis_words || []) {
      map[ew.text.toLowerCase()] = ew.style;
    }
    return map;
  }, [screen.emphasis_words]);

  // Colors — fix: use text_dark for top (over light bg), text_light for bottom
  const highlightColor = rgbToCSS(vs.highlight_color);
  const highlightTextColor = rgbToCSS(vs.highlight_text);

  const isFullBleed = layoutMode === "fullbleed";

  // In full-bleed mode, text is always white (over dark gradient scrim)
  // In classic mode, use proper contrast colors based on position
  const baseTextColor = isFullBleed
    ? rgbToCSS(vs.text_light)
    : screen.narration_position === "top"
      ? rgbToCSS(vs.text_dark)    // top text over light background
      : rgbToCSS(vs.text_light);  // bottom text over darker area

  const fontSize = screen.text.length > 120 ? 36 : screen.text.length > 60 ? 42 : 48;

  // Position — reserve top ~140px and bottom ~160px for branding/watermarks
  // Text is the dynamic element (top/bottom), image stays fixed center
  const positionStyle: React.CSSProperties = {
    position: "absolute",
    left: isFullBleed ? 32 : 40,
    right: isFullBleed ? 32 : 40,
    zIndex: 20,
    ...(screen.narration_position === "top"
      ? { top: isFullBleed ? 220 : 220 }
      : screen.narration_position === "bottom"
        ? { bottom: isFullBleed ? 140 : 180 }
        : { bottom: isFullBleed ? 140 : 180 }),
  };

  // Card background — transparent in full-bleed mode (text reads over gradient scrim)
  const cardStyle: React.CSSProperties = isFullBleed
    ? {
        padding: "20px 24px",
        borderRadius: vs.card_radius,
      }
    : {
        backgroundColor: rgbToCSS(
          [vs.card_bg[0], vs.card_bg[1], vs.card_bg[2]],
          vs.card_bg[3] / 255,
        ),
        borderRadius: vs.card_radius,
        padding: "28px 32px",
        boxShadow: "0 8px 32px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.08)",
      };

  const hasWordTimings = screen.word_timings && screen.word_timings.length > 0;

  return (
    <div style={{ ...positionStyle, ...mergedEffectStyle }}>
      <div style={cardStyle}>
        {/* Setup text (small label above main text) */}
        {screen.setup_text && (
          <div
            style={{
              fontSize: 22,
              fontWeight: 500,
              color: rgbToCSS(vs.secondary),
              marginBottom: 8,
              fontFamily: "'Inter', sans-serif",
              letterSpacing: 1,
              textTransform: "uppercase",
            }}
          >
            {screen.setup_text}
          </div>
        )}

        {/* Main narration text */}
        <div style={{ textAlign: "center" }}>
          {hasWordTimings ? (
            screen.word_timings.map((wt, i) => {
              const isEmphasis = emphasisSet.has(wt.word.toLowerCase());
              return (
                <KaraokeWord
                  key={i}
                  word={wt.word}
                  timing={wt}
                  isEmphasis={isEmphasis}
                  emphasisStyle={emphasisStyleMap[wt.word.toLowerCase()] || "bold"}
                  highlightColor={highlightColor}
                  highlightText={highlightTextColor}
                  baseColor={baseTextColor}
                  fontSize={fontSize}
                  sceneStartFrame={sceneStartFrame}
                />
              );
            })
          ) : (
            <span
              style={{
                fontFamily: "'Inter', 'SF Pro Display', sans-serif",
                fontSize,
                fontWeight: 600,
                color: baseTextColor,
                lineHeight: 1.4,
                textShadow: isFullBleed
                  ? "0 2px 12px rgba(0,0,0,0.8), 0 0px 4px rgba(0,0,0,0.6), 0 0 20px rgba(0,0,0,0.3)"
                  : "none",
              }}
            >
              {screen.text}
            </span>
          )}
        </div>

        {/* Speaker / character label */}
        {screen.speaker && (
          <div
            style={{
              fontSize: 18,
              fontWeight: 600,
              color: rgbToCSS(vs.primary),
              marginTop: 12,
              textAlign: "right",
              fontFamily: "'Inter', sans-serif",
            }}
          >
            — {screen.speaker}
          </div>
        )}
      </div>
    </div>
  );
};

export default TextBlock;
