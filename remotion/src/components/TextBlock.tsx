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

  // Highlight animation
  const highlightSpring = spring({
    frame: isActive ? Math.floor((currentTime - timing.start) * fps) : 0,
    fps,
    config: { damping: 12, mass: 0.5, stiffness: 200 },
  });

  const style: React.CSSProperties = {
    display: "inline-block",
    fontFamily: "'Inter', 'SF Pro Display', sans-serif",
    fontSize,
    fontWeight: isEmphasis ? 800 : 600,
    lineHeight: 1.4,
    margin: "0 3px",
    padding: "2px 6px",
    borderRadius: 6,
    transition: "all 0.15s ease",
    color: isActive ? highlightText : isPast ? baseColor : `${baseColor}aa`,
    backgroundColor: isActive ? highlightColor : "transparent",
    transform: isActive
      ? `scale(${1 + highlightSpring * 0.08})`
      : isEmphasis && isPast
        ? "scale(1.02)"
        : "scale(1)",
    textShadow: isActive
      ? `0 0 20px ${highlightColor}88`
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
}

export const TextBlock: React.FC<TextBlockProps> = ({
  screen,
  effects,
  style: vs,
  sceneStartFrame,
  sceneDurationFrames,
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

  const entryStyle = getTextEntryStyle(effects.text_entry, entryFrame, fps);
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

  // Colors
  const highlightColor = rgbToCSS(vs.highlight_color);
  const highlightTextColor = rgbToCSS(vs.highlight_text);
  const baseTextColor = screen.narration_position === "top"
    ? rgbToCSS(vs.text_dark)
    : rgbToCSS(vs.text_light);

  const fontSize = screen.text.length > 120 ? 36 : screen.text.length > 60 ? 42 : 48;

  // Position — reserve top ~140px and bottom ~160px for branding/watermarks
  // Text is the dynamic element (top/bottom), image stays fixed center
  const positionStyle: React.CSSProperties = {
    position: "absolute",
    left: 40,
    right: 40,
    zIndex: 20,
    ...(screen.narration_position === "top"
      ? { top: 160 }        // below top branding zone
      : screen.narration_position === "bottom"
        ? { bottom: 180 }   // above bottom branding zone
        : { bottom: 180 }), // default to bottom safe zone
  };

  // Card background
  const cardStyle: React.CSSProperties = {
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
