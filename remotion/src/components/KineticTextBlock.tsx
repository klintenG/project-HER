/**
 * Project HER v2.0 – Kinetic Typography Component (v2)
 * ======================================================
 * Professional-grade word-by-word text rendering for short-form video.
 *
 * v2 improvements over v1:
 *  • Smart phrase grouping that respects sentence/clause boundaries
 *  • Forced-high-contrast colors (pure white base, orange emphasis)
 *  • Heavy text stroke + multi-shadow outline for ANY background
 *  • Responsive font sizing based on word count
 *  • Per-word micro-rotation & offset variation (hand-placed feel)
 *  • Impact pulse on emphasis words (screen-level shake)
 *  • Uppercase for emphasis words (visual punch)
 *  • More exit animation variety
 *  • Wider row gap for breathing room
 *  • Better emphasis heuristic (respects explicit list, smarter fallback)
 */

import React, { useMemo } from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
} from "remotion";
import { ScreenData, SceneEffectsPlan, VisualStyle, WordTiming, rgbToCSS } from "../types";

// ═══════════════════════════════════════════════════
//  CONSTANTS
// ═══════════════════════════════════════════════════

/** Target words per phrase group */
const PHRASE_TARGET = 5;
/** Max words in a single phrase group */
const PHRASE_MAX = 7;
/** Min words — avoid breaking a group too small */
const PHRASE_MIN = 2;

/** Words never given automatic emphasis */
const STOP_WORDS = new Set([
  // articles / determiners
  "a", "an", "the", "this", "that", "these", "those",
  // be / have / do
  "is", "am", "are", "was", "were", "be", "been", "being",
  "have", "has", "had", "do", "does", "did",
  // modals
  "will", "would", "shall", "should", "may", "might", "must", "can", "could",
  // prepositions
  "of", "in", "to", "for", "with", "on", "at", "from", "by", "up",
  "about", "into", "through", "during", "before", "after", "above",
  "below", "between", "out", "off", "over", "under",
  // conjunctions
  "and", "but", "or", "if", "so", "than", "because", "as", "until", "while",
  // pronouns
  "i", "me", "my", "he", "him", "his", "she", "her", "it", "its",
  "we", "us", "our", "they", "them", "their", "you", "your",
  // adverbs / misc
  "again", "further", "then", "once", "here", "there", "when",
  "where", "why", "how", "all", "both", "each", "few", "more", "most",
  "other", "some", "such", "no", "nor", "not", "only", "own", "same",
  "too", "very", "just", "also", "now", "still", "even",
  // contractions
  "don't", "doesn't", "didn't", "won't", "wouldn't", "can't",
  "couldn't", "shouldn't", "isn't", "aren't", "wasn't", "weren't",
  "i'm", "he's", "she's", "it's", "we're", "they're", "i've",
  "you've", "we've", "they've", "i'll", "you'll", "he'll", "she'll",
  // fillers
  "ok", "okay", "oh", "um", "uh", "well", "like", "right", "yeah",
  // other low-value
  "what", "which", "who", "that", "going", "gets", "goes", "says",
  "just", "really", "thing", "things",
]);

// ═══════════════════════════════════════════════════
//  SMART PHRASE GROUPING
// ═══════════════════════════════════════════════════

interface PhraseGroup {
  words: WordTiming[];
  startTime: number;
  endTime: number;
  layoutSeed: number;
  animStyle: number;
}

/**
 * Group words into phrases respecting punctuation & clause breaks.
 * Sentence-ending punctuation (. ! ? ; —) forces a phrase break.
 * Commas and colons force a break only if the current group >= 3.
 */
function buildPhraseGroups(wordTimings: WordTiming[]): PhraseGroup[] {
  const groups: PhraseGroup[] = [];
  let current: WordTiming[] = [];

  for (let i = 0; i < wordTimings.length; i++) {
    current.push(wordTimings[i]);
    const w = wordTimings[i].word;
    const endsWithHardBreak = /[.!?;\u2014]$/.test(w);
    const endsWithSoftBreak = /[,:]$/.test(w);
    const atMax = current.length >= PHRASE_MAX;
    const atTarget = current.length >= PHRASE_TARGET;
    const isLast = i === wordTimings.length - 1;

    const shouldBreak =
      atMax ||
      isLast ||
      endsWithHardBreak ||
      (endsWithSoftBreak && current.length >= 3) ||
      (atTarget && i + 1 < wordTimings.length);

    if (shouldBreak && current.length >= PHRASE_MIN) {
      const groupIndex = groups.length;
      groups.push({
        words: [...current],
        startTime: current[0].start,
        endTime: current[current.length - 1].end,
        layoutSeed: groupIndex * 17 + current.length * 7,
        animStyle: groupIndex % ENTRY_STYLES.length,
      });
      current = [];
    }
  }

  // Flush leftover (< PHRASE_MIN words)
  if (current.length > 0) {
    if (groups.length > 0) {
      // Merge with last group
      const last = groups[groups.length - 1];
      last.words.push(...current);
      last.endTime = current[current.length - 1].end;
    } else {
      groups.push({
        words: current,
        startTime: current[0].start,
        endTime: current[current.length - 1].end,
        layoutSeed: 0,
        animStyle: 0,
      });
    }
  }

  return groups;
}

/**
 * When word_timings are empty, estimate them from text with
 * slight variation based on word length (longer words take longer).
 */
function estimateWordTimings(text: string, duration: number): WordTiming[] {
  const words = text.split(/\s+/).filter(Boolean);
  if (words.length === 0) return [];

  // Weight by character count for more natural pacing
  const totalChars = words.reduce((s, w) => s + w.length, 0);
  const GAP = 0.04;
  const usableDur = duration - GAP * words.length - 0.15;

  let t = 0.1;
  return words.map((w) => {
    const fraction = w.length / totalChars;
    const wordDur = Math.max(0.12, usableDur * fraction);
    const wt: WordTiming = { word: w, start: t, end: t + wordDur };
    t = wt.end + GAP;
    return wt;
  });
}

// ═══════════════════════════════════════════════════
//  EMPHASIS DETECTION
// ═══════════════════════════════════════════════════

function isEmphasisCandidate(word: string, emphasisSet: Set<string>): "forced" | "auto" | false {
  const clean = word.replace(/[^a-zA-Z'\u2019]/g, "").toLowerCase();
  if (emphasisSet.has(clean)) return "forced";
  if (STOP_WORDS.has(clean)) return false;
  if (clean.length <= 3) return false;
  if (clean.length === 4) return false;
  return clean.length >= 5 ? "auto" : false;
}

/**
 * Cap emphasis so max 1-2 per phrase group.
 * Returns indices of words that should be emphasised.
 */
function getEmphasisIndices(
  words: WordTiming[],
  emphasisSet: Set<string>,
): Set<number> {
  const forced: number[] = [];
  const auto: number[] = [];

  for (let i = 0; i < words.length; i++) {
    const result = isEmphasisCandidate(words[i].word, emphasisSet);
    if (result === "forced") forced.push(i);
    else if (result === "auto") auto.push(i);
  }

  const result = new Set<number>(forced);
  // Add at most 1 auto-detected emphasis if no forced ones exist
  const maxAuto = Math.max(0, 2 - forced.length);
  for (let c = 0; c < Math.min(maxAuto, auto.length); c++) {
    result.add(auto[c]);
  }
  return result;
}

// ═══════════════════════════════════════════════════
//  ENTRY ANIMATION STYLES (regular words)
// ═══════════════════════════════════════════════════

type EntryAnimFn = (
  p: number,
  wordIndex: number,
  fps: number,
) => React.CSSProperties;

const ENTRY_STYLES: EntryAnimFn[] = [
  // 0: Pop up from below with overshoot
  (p, wi) => ({
    opacity: interpolate(p, [0, 0.4], [0, 1], { extrapolateRight: "clamp" }),
    transform: `translateY(${interpolate(p, [0, 1], [70, 0])}px) scale(${interpolate(p, [0, 0.65, 1], [0.3, 1.12, 1])}) rotate(${(wi % 2 === 0 ? 1 : -1) * interpolate(p, [0, 1], [3, 0])}deg)`,
  }),
  // 1: Scale bounce from center
  (p, wi) => ({
    opacity: interpolate(p, [0, 0.3], [0, 1], { extrapolateRight: "clamp" }),
    transform: `scale(${interpolate(p, [0, 0.55, 0.8, 1], [0, 1.3, 0.92, 1])}) rotate(${(wi % 3 - 1) * interpolate(p, [0, 1], [2, 0])}deg)`,
  }),
  // 2: Slide in from left with deceleration
  (p, wi) => ({
    opacity: interpolate(p, [0, 0.35], [0, 1], { extrapolateRight: "clamp" }),
    transform: `translateX(${interpolate(p, [0, 1], [-150 - wi * 20, 0])}px) rotate(${interpolate(p, [0, 1], [-4, 0])}deg)`,
  }),
  // 3: Drop from above with bounce
  (p, wi) => ({
    opacity: interpolate(p, [0, 0.3], [0, 1], { extrapolateRight: "clamp" }),
    transform: `translateY(${interpolate(p, [0, 0.6, 0.8, 1], [-90, 8, -3, 0])}px) rotate(${(wi % 2 === 0 ? -1 : 1) * interpolate(p, [0, 1], [6, 0])}deg)`,
  }),
  // 4: 3D flip from bottom
  (p) => ({
    opacity: interpolate(p, [0, 0.25], [0, 1], { extrapolateRight: "clamp" }),
    transform: `perspective(600px) rotateX(${interpolate(p, [0, 1], [90, 0])}deg) translateY(${interpolate(p, [0, 1], [20, 0])}px)`,
    transformOrigin: "bottom center",
  }),
  // 5: Slide in from right
  (p, wi) => ({
    opacity: interpolate(p, [0, 0.35], [0, 1], { extrapolateRight: "clamp" }),
    transform: `translateX(${interpolate(p, [0, 1], [140 + wi * 15, 0])}px) rotate(${interpolate(p, [0, 1], [3, 0])}deg)`,
  }),
  // 6: Pop up with skew
  (p, wi) => ({
    opacity: interpolate(p, [0, 0.3], [0, 1], { extrapolateRight: "clamp" }),
    transform: `translateY(${interpolate(p, [0, 1], [55, 0])}px) skewX(${interpolate(p, [0, 1], [(wi % 2 === 0 ? -12 : 12), 0])}deg) scale(${interpolate(p, [0, 0.6, 1], [0.5, 1.08, 1])})`,
  }),
  // 7: Typewriter slam (drops from slight offset, no rotation)
  (p) => ({
    opacity: interpolate(p, [0, 0.15], [0, 1], { extrapolateRight: "clamp" }),
    transform: `translateY(${interpolate(p, [0, 0.4, 1], [-30, 2, 0])}px) scale(${interpolate(p, [0, 0.3, 1], [1.4, 1.02, 1])})`,
  }),
];

// ═══════════════════════════════════════════════════
//  EMPHASIS ENTRY ANIMATIONS (impact words)
// ═══════════════════════════════════════════════════

const EMPHASIS_STYLES: EntryAnimFn[] = [
  // 0: SLAM from above at 2x size
  (p) => ({
    opacity: interpolate(p, [0, 0.2], [0, 1], { extrapolateRight: "clamp" }),
    transform: `translateY(${interpolate(p, [0, 0.5, 0.75, 1], [-120, 5, -2, 0])}px) scale(${interpolate(p, [0, 0.4, 0.7, 1], [2.0, 1.1, 0.95, 1])})`,
  }),
  // 1: Elastic grow with brightness punch
  (p) => ({
    opacity: interpolate(p, [0, 0.15], [0, 1], { extrapolateRight: "clamp" }),
    transform: `scale(${interpolate(p, [0, 0.35, 0.6, 0.8, 1], [0, 1.6, 0.85, 1.08, 1])})`,
    filter: `brightness(${interpolate(p, [0, 0.2, 0.5, 1], [2.5, 1.8, 1.1, 1])})`,
  }),
  // 2: Rotate slam with scale
  (p) => ({
    opacity: interpolate(p, [0, 0.2], [0, 1], { extrapolateRight: "clamp" }),
    transform: `rotate(${interpolate(p, [0, 0.45, 0.7, 1], [-25, 6, -2, 0])}deg) scale(${interpolate(p, [0, 0.4, 0.7, 1], [0.2, 1.35, 0.93, 1])})`,
  }),
  // 3: 3D flip slam
  (p) => ({
    opacity: interpolate(p, [0, 0.2], [0, 1], { extrapolateRight: "clamp" }),
    transform: `perspective(500px) rotateY(${interpolate(p, [0, 1], [-90, 0])}deg) scale(${interpolate(p, [0, 0.5, 1], [0.6, 1.15, 1])})`,
  }),
  // 4: Pop up mega-scale with shadow burst
  (p) => ({
    opacity: interpolate(p, [0, 0.15], [0, 1], { extrapolateRight: "clamp" }),
    transform: `translateY(${interpolate(p, [0, 1], [50, 0])}px) scale(${interpolate(p, [0, 0.3, 0.6, 1], [0, 1.8, 0.9, 1])})`,
  }),
];

// ═══════════════════════════════════════════════════
//  ROW LAYOUT PRESETS
// ═══════════════════════════════════════════════════

interface RowPreset {
  rowSplit: (count: number) => number[];
  alignments: Array<"flex-start" | "center" | "flex-end">;
}

const ROW_PRESETS: RowPreset[] = [
  // 0: Left -> Center -> Right
  {
    rowSplit: (n) => n <= 2 ? [n] : n <= 4 ? [2, n - 2] : [2, 1, n - 3],
    alignments: ["flex-start", "center", "flex-end"],
  },
  // 1: Center -> Left -> Center
  {
    rowSplit: (n) => n <= 2 ? [n] : n <= 4 ? [2, n - 2] : [2, 2, n - 4],
    alignments: ["center", "flex-start", "center"],
  },
  // 2: Right -> Center -> Left
  {
    rowSplit: (n) => n <= 2 ? [n] : n <= 3 ? [1, n - 1] : [1, 2, n - 3],
    alignments: ["flex-end", "center", "flex-start"],
  },
  // 3: Left -> Right -> Center
  {
    rowSplit: (n) => n <= 2 ? [n] : n <= 4 ? [2, n - 2] : [2, 1, n - 3],
    alignments: ["flex-start", "flex-end", "center"],
  },
  // 4: Center -> Right -> Left
  {
    rowSplit: (n) => n <= 2 ? [n] : n <= 3 ? [2, n - 2] : [1, 2, n - 3],
    alignments: ["center", "flex-end", "flex-start"],
  },
  // 5: Left -> Left -> Right (staircase)
  {
    rowSplit: (n) => n <= 2 ? [n] : n <= 4 ? [1, n - 1] : [1, 2, n - 3],
    alignments: ["flex-start", "flex-start", "flex-end"],
  },
  // 6: Right -> Right -> Left (reverse staircase)
  {
    rowSplit: (n) => n <= 2 ? [n] : n <= 4 ? [1, n - 1] : [2, 1, n - 3],
    alignments: ["flex-end", "flex-end", "flex-start"],
  },
  // 7: Center -> Center -> Center (balanced)
  {
    rowSplit: (n) => n <= 2 ? [n] : n <= 4 ? [2, n - 2] : [2, 1, n - 3],
    alignments: ["center", "center", "center"],
  },
];

// ═══════════════════════════════════════════════════
//  EXIT ANIMATIONS
// ═══════════════════════════════════════════════════

type ExitAnimFn = (progress: number) => React.CSSProperties;

const EXIT_STYLES: ExitAnimFn[] = [
  // 0: Fade + shrink
  (p) => ({
    opacity: 1 - p,
    transform: `scale(${interpolate(p, [0, 1], [1, 0.7])})`,
    filter: `blur(${interpolate(p, [0, 1], [0, 6])}px)`,
  }),
  // 1: Fly up + fade
  (p) => ({
    opacity: 1 - p,
    transform: `translateY(${interpolate(p, [0, 1], [0, -60])}px)`,
  }),
  // 2: Fly down + fade
  (p) => ({
    opacity: 1 - p,
    transform: `translateY(${interpolate(p, [0, 1], [0, 50])}px) scale(${interpolate(p, [0, 1], [1, 0.85])})`,
  }),
  // 3: Scatter (scale + rotate out)
  (p) => ({
    opacity: 1 - p,
    transform: `scale(${interpolate(p, [0, 1], [1, 1.3])}) rotate(${interpolate(p, [0, 1], [0, 8])}deg)`,
    filter: `blur(${interpolate(p, [0, 1], [0, 8])}px)`,
  }),
];

// ═══════════════════════════════════════════════════
//  IMPACT PULSE (screen shake on emphasis)
// ═══════════════════════════════════════════════════

function getImpactShake(frame: number, fps: number, impactFrame: number): React.CSSProperties {
  const elapsed = frame - impactFrame;
  if (elapsed < 0 || elapsed > 12) return {};

  const decay = interpolate(elapsed, [0, 12], [1, 0], { extrapolateRight: "clamp" });
  const shakeX = Math.sin(elapsed * 2.8) * 4 * decay;
  const shakeY = Math.cos(elapsed * 3.2) * 3 * decay;
  const scalePulse = 1 + 0.015 * decay;

  return {
    transform: `translate(${shakeX}px, ${shakeY}px) scale(${scalePulse})`,
  };
}

// ═══════════════════════════════════════════════════
//  SINGLE KINETIC WORD
// ═══════════════════════════════════════════════════

interface KineticWordProps {
  word: string;
  wordTiming: WordTiming;
  isEmphasis: boolean;
  wordIndexInGroup: number;
  entryAnimFn: EntryAnimFn;
  emphasisAnimFn: EntryAnimFn;
  accentColor: string;
  baseColor: string;
  baseFontSize: number;
  groupExiting: boolean;
  exitProgress: number;
  exitAnimFn: ExitAnimFn;
  microRotation: number;
}

const KineticWord: React.FC<KineticWordProps> = ({
  word,
  wordTiming,
  isEmphasis,
  wordIndexInGroup,
  entryAnimFn,
  emphasisAnimFn,
  accentColor,
  baseColor,
  baseFontSize,
  groupExiting,
  exitProgress,
  exitAnimFn,
  microRotation,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentTime = frame / fps;

  // Word hasn't appeared yet — invisible placeholder preserving layout space
  if (currentTime < wordTiming.start - 0.03) {
    return (
      <span
        style={{
          display: "inline-block",
          opacity: 0,
          fontSize: baseFontSize,
          margin: "3px 5px",
        }}
      >
        {word}
      </span>
    );
  }

  // Spring entry starting at word's start time
  const wordStartFrame = Math.round(wordTiming.start * fps);
  const localEntryFrame = Math.max(0, frame - wordStartFrame);

  const entrySpring = spring({
    frame: localEntryFrame,
    fps,
    config: isEmphasis
      ? { damping: 9, mass: 0.7, stiffness: 220 }
      : { damping: 13, mass: 0.4, stiffness: 190 },
    durationInFrames: isEmphasis ? 18 : 12,
  });

  // Choose animation
  const animFn = isEmphasis ? emphasisAnimFn : entryAnimFn;
  const entryStyle = animFn(entrySpring, wordIndexInGroup, fps);

  // Exit
  const exitStyle = groupExiting ? exitAnimFn(exitProgress) : {};

  // Sizing
  const emphasisSize = baseFontSize * 1.45;
  const fontSize = isEmphasis ? emphasisSize : baseFontSize;
  const fontWeight: number = isEmphasis ? 900 : 700;
  const color = isEmphasis ? accentColor : baseColor;

  // Micro-rotation for hand-placed feel (applied after entry completes)
  const settled = entrySpring >= 0.95;
  const settledRotation = settled && !groupExiting ? microRotation : 0;

  // Subtle breathing for emphasis words after entry
  let breatheScale = 1;
  if (isEmphasis && settled && !groupExiting) {
    breatheScale = 1 + Math.sin(currentTime * 3) * 0.018;
  }

  // Text stroke: multi-directional offset shadows for bulletproof readability
  const S = isEmphasis ? 3 : 2;
  const strokeShadow = [
    `${S}px ${S}px 0 rgba(0,0,0,0.9)`,
    `${-S}px ${S}px 0 rgba(0,0,0,0.9)`,
    `${S}px ${-S}px 0 rgba(0,0,0,0.9)`,
    `${-S}px ${-S}px 0 rgba(0,0,0,0.9)`,
    `0 ${S}px 0 rgba(0,0,0,0.9)`,
    `0 ${-S}px 0 rgba(0,0,0,0.9)`,
    `${S}px 0 0 rgba(0,0,0,0.9)`,
    `${-S}px 0 0 rgba(0,0,0,0.9)`,
    // Outer soft glow
    `0 0 12px rgba(0,0,0,0.5)`,
    `0 4px 16px rgba(0,0,0,0.4)`,
  ].join(", ");

  // Extra colour glow for emphasis words
  const emphasisGlow = isEmphasis
    ? `, 0 0 30px ${accentColor}55, 0 0 60px ${accentColor}22`
    : "";

  // Compose final transform
  const buildTransform = (): string => {
    if (groupExiting && exitStyle.transform) {
      return exitStyle.transform as string;
    }
    const parts: string[] = [];
    if (entryStyle.transform) parts.push(entryStyle.transform as string);
    if (settledRotation !== 0) parts.push(`rotate(${settledRotation}deg)`);
    if (breatheScale !== 1) parts.push(`scale(${breatheScale})`);
    return parts.join(" ") || "none";
  };

  return (
    <span
      style={{
        display: "inline-block",
        fontFamily: "'Inter', 'SF Pro Display', system-ui, sans-serif",
        fontSize,
        fontWeight,
        color,
        lineHeight: 1.2,
        textTransform: isEmphasis ? "uppercase" : "none",
        textShadow: strokeShadow + emphasisGlow,
        letterSpacing: isEmphasis ? 1 : 0,
        margin: "3px 5px",
        whiteSpace: "nowrap",
        willChange: "transform, opacity",
        opacity: groupExiting
          ? (exitStyle.opacity as number) ?? 1
          : (entryStyle.opacity as number) ?? 1,
        transform: buildTransform(),
        filter: (groupExiting ? exitStyle.filter : entryStyle.filter) as string | undefined,
        transformOrigin: (entryStyle.transformOrigin as string) || "center center",
      }}
    >
      {word}
    </span>
  );
};

// ═══════════════════════════════════════════════════
//  RESPONSIVE FONT SIZE
// ═══════════════════════════════════════════════════

function getBaseFontSize(avgCharsPerPhrase: number): number {
  if (avgCharsPerPhrase <= 15) return 80;
  if (avgCharsPerPhrase <= 25) return 72;
  if (avgCharsPerPhrase <= 40) return 64;
  if (avgCharsPerPhrase <= 60) return 56;
  return 50;
}

// ═══════════════════════════════════════════════════
//  MAIN KINETIC TEXT BLOCK
// ═══════════════════════════════════════════════════

interface KineticTextBlockProps {
  screen: ScreenData;
  effects: SceneEffectsPlan;
  style: VisualStyle;
  sceneStartFrame: number;
  sceneDurationFrames: number;
  layoutMode?: "classic" | "fullbleed";
}

export const KineticTextBlock: React.FC<KineticTextBlockProps> = ({
  screen,
  effects,
  style: vs,
  sceneStartFrame,
  sceneDurationFrames,
  layoutMode = "fullbleed",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentTime = frame / fps;

  // Word timings (real or estimated)
  const wordTimings = useMemo(() => {
    if (screen.word_timings && screen.word_timings.length > 0) {
      return screen.word_timings;
    }
    return estimateWordTimings(screen.text, screen.duration);
  }, [screen.word_timings, screen.text, screen.duration]);

  // Phrase groups
  const phraseGroups = useMemo(
    () => buildPhraseGroups(wordTimings),
    [wordTimings],
  );

  // Emphasis set from explicit props
  const emphasisSet = useMemo(() => {
    const set = new Set<string>();
    for (const ew of screen.emphasis_words || []) {
      set.add(ew.text.toLowerCase());
    }
    return set;
  }, [screen.emphasis_words]);

  // FORCE high-contrast colors for video text
  const accentColor = rgbToCSS(vs.highlight_color ?? vs.accent);
  const baseColor = "#FFFFFF";

  // Responsive font size
  const avgChars = useMemo(() => {
    if (phraseGroups.length === 0) return 30;
    const totalChars = phraseGroups.reduce(
      (s, g) => s + g.words.reduce((ss, w) => ss + w.word.length, 0),
      0,
    );
    return totalChars / phraseGroups.length;
  }, [phraseGroups]);
  const baseFontSize = getBaseFontSize(avgChars);

  // Active phrase group
  const activeGroupIndex = (() => {
    for (let i = phraseGroups.length - 1; i >= 0; i--) {
      if (currentTime >= phraseGroups[i].startTime - 0.08) return i;
    }
    return 0;
  })();

  // Track emphasis impact frames for screen shake
  const impactFrame = useMemo(() => {
    const group = phraseGroups[activeGroupIndex];
    if (!group) return -1;
    const emphasisIdxs = getEmphasisIndices(group.words, emphasisSet);
    for (const idx of emphasisIdxs) {
      const wt = group.words[idx];
      const wFrame = Math.round(wt.start * fps);
      if (frame >= wFrame && frame <= wFrame + 14) return wFrame;
    }
    return -1;
  }, [phraseGroups, activeGroupIndex, emphasisSet, frame, fps]);

  const impactShake = impactFrame >= 0 ? getImpactShake(frame, fps, impactFrame) : {};

  const EXIT_DURATION = 0.22;

  return (
    <div
      style={{
        position: "absolute",
        // SAFE ZONE: centered vertically, away from platform icons
        top: "18%",
        bottom: "22%",
        left: 36,
        right: 36,
        zIndex: 25,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "stretch",
        pointerEvents: "none",
        ...impactShake,
      }}
    >
      {phraseGroups.map((group, groupIdx) => {
        const isActive = groupIdx === activeGroupIndex;
        const isPrev = groupIdx === activeGroupIndex - 1;
        if (!isActive && !isPrev) return null;

        // Exit animation
        const nextStart = groupIdx + 1 < phraseGroups.length
          ? phraseGroups[groupIdx + 1].startTime
          : Infinity;
        const exitStart = nextStart - EXIT_DURATION;
        const isExiting = currentTime >= exitStart && isPrev;
        const exitProgress = isExiting
          ? interpolate(currentTime, [exitStart, exitStart + EXIT_DURATION], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            })
          : 0;

        // Layout preset
        const preset = ROW_PRESETS[group.layoutSeed % ROW_PRESETS.length];
        const rowSplits = preset.rowSplit(group.words.length);

        // Exit animation style (varies per group)
        const exitAnimFn = EXIT_STYLES[groupIdx % EXIT_STYLES.length];

        // Entry animation style
        const entryAnimFn = ENTRY_STYLES[group.animStyle];
        const emphasisAnimFn = EMPHASIS_STYLES[group.layoutSeed % EMPHASIS_STYLES.length];

        // Per-group emphasis detection (capped)
        const emphasisIdxs = getEmphasisIndices(group.words, emphasisSet);

        // Distribute words into rows
        let wordOffset = 0;
        const rows: { wt: WordTiming; globalIdx: number }[][] = [];
        for (const count of rowSplits) {
          const row: { wt: WordTiming; globalIdx: number }[] = [];
          for (let j = 0; j < count && wordOffset < group.words.length; j++) {
            row.push({ wt: group.words[wordOffset], globalIdx: wordOffset });
            wordOffset++;
          }
          rows.push(row);
        }

        return (
          <div
            key={groupIdx}
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              gap: 14,
            }}
          >
            {rows.map((rowItems, rowIdx) => (
              <div
                key={rowIdx}
                style={{
                  display: "flex",
                  flexWrap: "nowrap",
                  justifyContent: preset.alignments[rowIdx] || "center",
                  alignItems: "baseline",
                  paddingLeft: 6,
                  paddingRight: 6,
                }}
              >
                {rowItems.map(({ wt, globalIdx }) => {
                  // Deterministic micro-rotation per word (-2 to +2 degrees)
                  const microRot = ((globalIdx * 37 + groupIdx * 13) % 5) - 2;

                  return (
                    <KineticWord
                      key={`${groupIdx}-${globalIdx}`}
                      word={wt.word}
                      wordTiming={wt}
                      isEmphasis={emphasisIdxs.has(globalIdx)}
                      wordIndexInGroup={globalIdx}
                      entryAnimFn={entryAnimFn}
                      emphasisAnimFn={emphasisAnimFn}
                      accentColor={accentColor}
                      baseColor={baseColor}
                      baseFontSize={baseFontSize}
                      groupExiting={isPrev && isExiting}
                      exitProgress={exitProgress}
                      exitAnimFn={exitAnimFn}
                      microRotation={microRot}
                    />
                  );
                })}
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
};

export default KineticTextBlock;
