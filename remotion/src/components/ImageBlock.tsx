/**
 * Project HER v2.0 – ImageBlock Component
 * =========================================
 * Renders AI-generated images with animated entry/treatment/exit
 * effects including Ken Burns, zoom pulse, parallax, etc.
 */

import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  Img,
  interpolate,
  staticFile,
} from "remotion";
import { getImageEntryStyle, getImageTreatmentStyle, getImageExitStyle } from "../effects/imageAnimations";
import { SceneEffectsPlan, VisualStyle } from "../types";

// ═══════════════════════════════════════════════════
//  SINGLE IMAGE BLOCK
// ═══════════════════════════════════════════════════

interface ImageBlockProps {
  imagePath: string;
  effects: SceneEffectsPlan;
  style: VisualStyle;
  sceneStartFrame: number;
  sceneDurationFrames: number;
  layout?: "full" | "top" | "bottom" | "left" | "right" | "center";
  index?: number; // for multi-image
}

export const ImageBlock: React.FC<ImageBlockProps> = ({
  imagePath,
  effects,
  style: vs,
  sceneStartFrame,
  sceneDurationFrames,
  layout = "center",
  index = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  // useCurrentFrame() inside <Sequence> already returns the local frame
  const localFrame = frame;
  const progress = localFrame / sceneDurationFrames;

  // Entry: first 10%, Treatment: 10%-90%, Exit: last 10%
  const entryEnd = 0.1;
  const exitStart = 0.9;

  const entryProgress = interpolate(progress, [0, entryEnd], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const treatmentProgress = interpolate(progress, [entryEnd, exitStart], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const exitProgress = interpolate(progress, [exitStart, 1], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Frame-based calculations
  const entryFrames = Math.round(sceneDurationFrames * entryEnd);
  const entryFrame = Math.min(localFrame, entryFrames);
  const treatmentFrames = Math.round(sceneDurationFrames * (exitStart - entryEnd));
  const treatmentFrame = Math.max(0, localFrame - entryFrames);
  const exitFrames = Math.round(sceneDurationFrames * (1 - exitStart));
  const exitFrame = progress > exitStart ? localFrame - Math.round(sceneDurationFrames * exitStart) : 0;

  // Effect styles
  const entryStyle = getImageEntryStyle(effects.image_entry, entryFrame, fps);
  const treatmentStyle = getImageTreatmentStyle(effects.image_treatment, treatmentFrame, fps, treatmentFrames);
  const exitStyle = progress > exitStart
    ? getImageExitStyle(effects.image_exit, exitFrame, fps)
    : {};

  // Merge
  const imageEffectStyle: React.CSSProperties = {
    ...treatmentStyle,
    ...entryStyle,
    ...(progress > exitStart ? exitStyle : {}),
  };

  // In fullbleed ("full") mode, strip CSS filter properties from treatments
  // to prevent brightness/saturation/hue changes that wash out images.
  // Transform-based effects (ken_burns, zoom_pulse, parallax) still apply.
  if (layout === "full") {
    delete imageEffectStyle.filter;
    delete (imageEffectStyle as any).WebkitFilter;
  }

  // Layout positioning
  const containerStyle: React.CSSProperties = (() => {
    const base: React.CSSProperties = {
      position: "absolute",
      overflow: "hidden",
      borderRadius: vs.image_corner_radius,
      boxShadow: "0 12px 40px rgba(0,0,0,0.2), 0 4px 12px rgba(0,0,0,0.1)",
    };

    switch (layout) {
      case "full":
        return { ...base, top: 0, left: 0, width: "100%", height: "100%", borderRadius: 0 };
      case "center":
      default:
        // Fixed center-ish position (slightly below middle)
        // Leaves ~28% top and ~30% bottom clear for text + branding
        return {
          ...base,
          top: "28%",
          left: 40,
          right: 40,
          width: "auto",
          height: "42%",
        };
    }
  })();

  return (
    <div style={containerStyle}>
      <Img
        src={imagePath.startsWith("http") ? imagePath : staticFile(imagePath)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          ...imageEffectStyle,
        }}
      />
    </div>
  );
};

// ═══════════════════════════════════════════════════
//  MULTI-IMAGE LAYOUT
// ═══════════════════════════════════════════════════

interface MultiImageBlockProps {
  imagePaths: string[];
  effects: SceneEffectsPlan;
  style: VisualStyle;
  sceneStartFrame: number;
  sceneDurationFrames: number;
}

export const MultiImageBlock: React.FC<MultiImageBlockProps> = ({
  imagePaths,
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
  const count = imagePaths.length;

  if (count === 0) return null;

  // For multi-image: stagger entry, show all in a grid or slideshow
  if (count <= 2) {
    // Side by side vertical — fixed center position
    return (
      <div
        style={{
          position: "absolute",
          top: "28%",
          left: 30,
          right: 30,
          height: "42%",
          display: "flex",
          gap: 16,
        }}
      >
        {imagePaths.map((path, i) => {
          const stagger = i * 0.1;
          const imgProgress = interpolate(progress, [stagger, stagger + 0.15], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          const treatProgress = interpolate(progress, [0.15, 0.85], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });

          const entryLocalFrame = Math.round(imgProgress * 15); // ~15 frames for entry
          const treatLocalFrame = Math.max(0, Math.round(treatProgress * sceneDurationFrames));

          const entryStyle = getImageEntryStyle(effects.image_entry, entryLocalFrame, fps);
          const treatStyle = getImageTreatmentStyle(effects.image_treatment, treatLocalFrame, fps, sceneDurationFrames);

          return (
            <div
              key={i}
              style={{
                flex: 1,
                borderRadius: vs.image_corner_radius,
                overflow: "hidden",
                boxShadow: "0 8px 32px rgba(0,0,0,0.15)",
                ...entryStyle,
              }}
            >
              <Img
                src={path}
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                  ...treatStyle,
                }}
              />
            </div>
          );
        })}
      </div>
    );
  }

  // 3+ images: grid layout
  return (
    <div
      style={{
        position: "absolute",
        top: "28%",
        left: 30,
        right: 30,
        height: "42%",
        display: "grid",
        gridTemplateColumns: count <= 4 ? "1fr 1fr" : "1fr 1fr 1fr",
        gap: 12,
      }}
    >
      {imagePaths.slice(0, 6).map((path, i) => {
        const stagger = i * 0.08;
        const imgProgress = interpolate(progress, [stagger, stagger + 0.15], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });

        return (
          <div
            key={i}
            style={{
              borderRadius: vs.image_corner_radius * 0.6,
              overflow: "hidden",
              boxShadow: "0 4px 16px rgba(0,0,0,0.1)",
              opacity: imgProgress,
              transform: `scale(${interpolate(imgProgress, [0, 1], [0.8, 1])})`,
            }}
          >
            <Img
              src={path}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
              }}
            />
          </div>
        );
      })}
    </div>
  );
};

export default ImageBlock;
