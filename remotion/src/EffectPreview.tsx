/**
 * Project HER v2.0 – Effect Preview Composition
 * ===============================================
 * Renders a short (3-second) preview of a single Remotion effect.
 * Used by the Remotion Studio tab for on-demand effect previews.
 *
 * Input props:
 *   effectCategory: "text_entry" | "text_exit" | "text_continuous" |
 *                   "image_entry" | "image_treatment" | "image_exit" |
 *                   "transition" | "overlay" | "background"
 *   effectName: string (e.g. "scale_bounce", "ken_burns", "crossfade")
 */

import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  Img,
  staticFile,
} from "remotion";
import { z } from "zod";

import { textEntry, textExit, textContinuous } from "./effects/textAnimations";
import { imageEntry, imageTreatment, imageExit } from "./effects/imageAnimations";
import { transitions } from "./transitions/sceneTransitions";
import { getOverlayComponent } from "./effects/overlays";
import { getBackgroundComponent } from "./effects/backgrounds";

// ── Props schema ──
export const EffectPreviewSchema = z.object({
  effectCategory: z.string(),
  effectName: z.string(),
});
export type EffectPreviewProps = z.infer<typeof EffectPreviewSchema>;

// ── Shared styles ──
const FILL: React.CSSProperties = {
  position: "absolute",
  top: 0,
  left: 0,
  width: "100%",
  height: "100%",
};

const GRADIENT_BG: React.CSSProperties = {
  ...FILL,
  background: "linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)",
};

const SAMPLE_TEXT_STYLE: React.CSSProperties = {
  color: "#fff",
  fontSize: 64,
  fontWeight: 800,
  textAlign: "center" as const,
  fontFamily: "'Inter', 'Segoe UI', system-ui, sans-serif",
  lineHeight: 1.2,
  textShadow: "0 4px 20px rgba(0,0,0,0.5)",
};

const LABEL_STYLE: React.CSSProperties = {
  position: "absolute",
  bottom: 40,
  left: 0,
  right: 0,
  textAlign: "center" as const,
  color: "rgba(255,255,255,0.6)",
  fontSize: 28,
  fontFamily: "'Inter', 'Segoe UI', system-ui, sans-serif",
  letterSpacing: 2,
  textTransform: "uppercase" as const,
};

// ── Sample image (gradient placeholder) ──
const SampleImage: React.FC<{ style?: React.CSSProperties }> = ({ style }) => (
  <div
    style={{
      width: "70%",
      height: "50%",
      borderRadius: 24,
      background:
        "linear-gradient(135deg, #ff6b6b 0%, #ffa502 25%, #7bed9f 50%, #70a1ff 75%, #a55eea 100%)",
      boxShadow: "0 20px 60px rgba(0,0,0,0.4)",
      ...style,
    }}
  />
);

// ── Main preview component ──
export const EffectPreview: React.FC<EffectPreviewProps> = ({
  effectCategory,
  effectName,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const label = `${effectCategory.replace(/_/g, " ")} › ${effectName.replace(/_/g, " ")}`;

  // ─── TEXT ENTRY ───
  if (effectCategory === "text_entry") {
    const fn = (textEntry as any)[effectName];
    const style = fn ? fn(frame, fps) : { opacity: 1 };
    // Special handling for typewriter
    if (effectName === "typewriter" && fn) {
      const result = fn(frame, fps, "Hello World");
      const text = "Hello World".slice(0, result.visibleChars ?? 11);
      return (
        <AbsoluteFill style={GRADIENT_BG}>
          <div style={{ ...FILL, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <div style={{ ...SAMPLE_TEXT_STYLE, minWidth: "8ch" }}>{text}<span style={{ opacity: frame % 20 < 10 ? 1 : 0 }}>|</span></div>
          </div>
          <div style={LABEL_STYLE}>{label}</div>
        </AbsoluteFill>
      );
    }
    return (
      <AbsoluteFill style={GRADIENT_BG}>
        <div style={{ ...FILL, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div style={{ ...SAMPLE_TEXT_STYLE, ...style }}>Hello World</div>
        </div>
        <div style={LABEL_STYLE}>{label}</div>
      </AbsoluteFill>
    );
  }

  // ─── TEXT EXIT ───
  if (effectCategory === "text_exit") {
    const fn = (textExit as any)[effectName];
    // Show text fully visible for first 30 frames, then animate exit
    const exitFrame = Math.max(0, frame - 30);
    const style = exitFrame > 0 && fn ? fn(exitFrame, fps) : {};
    return (
      <AbsoluteFill style={GRADIENT_BG}>
        <div style={{ ...FILL, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div style={{ ...SAMPLE_TEXT_STYLE, ...style }}>Goodbye</div>
        </div>
        <div style={LABEL_STYLE}>{label}</div>
      </AbsoluteFill>
    );
  }

  // ─── TEXT CONTINUOUS ───
  if (effectCategory === "text_continuous") {
    const fn = (textContinuous as any)[effectName];
    const style = fn ? fn(frame, fps) : {};
    return (
      <AbsoluteFill style={GRADIENT_BG}>
        <div style={{ ...FILL, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div style={{ ...SAMPLE_TEXT_STYLE, ...style }}>Looping Effect</div>
        </div>
        <div style={LABEL_STYLE}>{label}</div>
      </AbsoluteFill>
    );
  }

  // ─── IMAGE ENTRY ───
  if (effectCategory === "image_entry") {
    const fn = (imageEntry as any)[effectName];
    const style = fn ? fn(frame, fps) : {};
    return (
      <AbsoluteFill style={GRADIENT_BG}>
        <div style={{ ...FILL, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <SampleImage style={style} />
        </div>
        <div style={LABEL_STYLE}>{label}</div>
      </AbsoluteFill>
    );
  }

  // ─── IMAGE TREATMENT ───
  if (effectCategory === "image_treatment") {
    const fn = (imageTreatment as any)[effectName];
    const style = fn ? fn(frame, fps, durationInFrames) : {};
    return (
      <AbsoluteFill style={GRADIENT_BG}>
        <div style={{ ...FILL, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <SampleImage style={style} />
        </div>
        <div style={LABEL_STYLE}>{label}</div>
      </AbsoluteFill>
    );
  }

  // ─── IMAGE EXIT ───
  if (effectCategory === "image_exit") {
    const fn = (imageExit as any)[effectName];
    const exitFrame = Math.max(0, frame - 30);
    const style = exitFrame > 0 && fn ? fn(exitFrame, fps) : {};
    return (
      <AbsoluteFill style={GRADIENT_BG}>
        <div style={{ ...FILL, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <SampleImage style={style} />
        </div>
        <div style={LABEL_STYLE}>{label}</div>
      </AbsoluteFill>
    );
  }

  // ─── SCENE TRANSITIONS ───
  if (effectCategory === "transition") {
    const tfn = (transitions as any)[effectName];
    const timing = tfn ? tfn() : null;
    if (timing) {
      const { durationInFrames: transFrames } = timing;
      // Show Scene A, then transition zone, then Scene B
      const holdA = 20;
      const transStart = holdA;
      const transEnd = transStart + transFrames;

      let sceneAStyle: React.CSSProperties = {};
      let sceneBStyle: React.CSSProperties = { opacity: 0 };

      if (frame >= transStart && frame < transEnd) {
        const p = (frame - transStart) / transFrames;
        sceneAStyle = timing.exitStyle(p);
        sceneBStyle = timing.enterStyle(p);
      } else if (frame >= transEnd) {
        sceneAStyle = { opacity: 0 };
        sceneBStyle = { opacity: 1 };
      }

      return (
        <AbsoluteFill>
          {/* Scene A */}
          <AbsoluteFill
            style={{
              background: "linear-gradient(135deg, #e74c3c 0%, #c0392b 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              ...sceneAStyle,
            }}
          >
            <div style={{ ...SAMPLE_TEXT_STYLE, fontSize: 56 }}>Scene A</div>
          </AbsoluteFill>
          {/* Scene B */}
          <AbsoluteFill
            style={{
              background: "linear-gradient(135deg, #2ecc71 0%, #27ae60 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              ...sceneBStyle,
            }}
          >
            <div style={{ ...SAMPLE_TEXT_STYLE, fontSize: 56 }}>Scene B</div>
          </AbsoluteFill>
          <div style={LABEL_STYLE}>{label}</div>
        </AbsoluteFill>
      );
    }
  }

  // ─── OVERLAYS ───
  if (effectCategory === "overlay") {
    const OverlayComp = getOverlayComponent(effectName);
    return (
      <AbsoluteFill style={GRADIENT_BG}>
        <div
          style={{
            ...FILL,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <SampleImage />
        </div>
        <OverlayComp />
        <div style={LABEL_STYLE}>{label}</div>
      </AbsoluteFill>
    );
  }

  // ─── BACKGROUNDS ───
  if (effectCategory === "background") {
    const BgComp = getBackgroundComponent(effectName);
    return (
      <AbsoluteFill>
        <BgComp baseColor={[30, 40, 80]} secondaryColor={[255, 136, 0]} />
        <div style={{ ...FILL, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div style={{ ...SAMPLE_TEXT_STYLE, fontSize: 48 }}>Background</div>
        </div>
        <div style={LABEL_STYLE}>{label}</div>
      </AbsoluteFill>
    );
  }

  // ─── FALLBACK ───
  return (
    <AbsoluteFill style={GRADIENT_BG}>
      <div style={{ ...FILL, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ ...SAMPLE_TEXT_STYLE, fontSize: 36 }}>
          Unknown: {effectCategory} / {effectName}
        </div>
      </div>
    </AbsoluteFill>
  );
};
