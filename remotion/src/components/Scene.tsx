/**
 * Project HER v2.0 – Scene Component
 * ====================================
 * Main scene renderer. Composes background, image(s), text,
 * overlays, and optional 3D elements into a single screen.
 */

import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  AbsoluteFill,
  Audio,
  Sequence,
  interpolate,
  spring,
  staticFile,
} from "remotion";
import { ScreenData, SceneEffectsPlan, VisualStyle, rgbToCSS } from "../types";
import { TextBlock } from "./TextBlock";
import { ImageBlock, MultiImageBlock } from "./ImageBlock";
import { getOverlayComponent } from "../effects/overlays";
import { getBackgroundComponent } from "../effects/backgrounds";
import { BrandBar } from "./BrandBar";

// ═══════════════════════════════════════════════════
//  DEFAULT EFFECTS (if none provided)
// ═══════════════════════════════════════════════════

const DEFAULT_EFFECTS: SceneEffectsPlan = {
  screen_index: 0,
  text_entry: "fade_in",
  text_entry_params: {},
  text_exit: "fade_out",
  text_exit_params: {},
  text_continuous: "none",
  text_continuous_params: {},
  image_entry: "img_fade_in",
  image_entry_params: {},
  image_treatment: "ken_burns",
  image_treatment_params: {},
  image_exit: "img_fade_out",
  image_exit_params: {},
  scene_transition: "crossfade",
  scene_transition_params: {},
  overlay_effect: "overlay_none",
  overlay_params: {},
  background_effect: "bg_none",
  background_params: {},
  emphasis_style: "scale_bounce",
  emphasis_params: {},
  reasoning: "",
};

// ═══════════════════════════════════════════════════
//  CLAYMORPHISM BACKGROUND
// ═══════════════════════════════════════════════════

interface ClayBgProps {
  style: VisualStyle;
  effects: SceneEffectsPlan;
}

const ClayBackground: React.FC<ClayBgProps> = ({ style: vs, effects }) => {
  const centerColor = rgbToCSS(vs.bg_center_color);
  const edgeColor = rgbToCSS(vs.bg_edge_color);

  return (
    <AbsoluteFill>
      {/* Base gradient */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(ellipse at 50% 40%, ${centerColor} 0%, ${edgeColor} 100%)`,
        }}
      />
      {/* Animated background effect layer */}
      {effects.background_effect && effects.background_effect !== "bg_none" && (() => {
        const BgComponent = getBackgroundComponent(effects.background_effect);
        // Provide safe defaults for background components
        const defaultBgProps = {
          baseColor: vs.bg_center_color as [number, number, number],
          color1: vs.bg_center_color as [number, number, number],
          color2: vs.bg_edge_color as [number, number, number],
        };
        return <BgComponent {...defaultBgProps} {...(effects.background_params || {})} />;
      })()}
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════
//  MAIN SCENE
// ═══════════════════════════════════════════════════

interface SceneProps {
  screen: ScreenData;
  visualStyle: VisualStyle;
  brandText?: string;
  watermark?: string;
  sceneStartFrame: number;
}

export const Scene: React.FC<SceneProps> = ({
  screen,
  visualStyle,
  brandText = "",
  watermark = "",
  sceneStartFrame,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const effects = screen.effects || DEFAULT_EFFECTS;
  const sceneDurationFrames = Math.round(screen.duration * fps);

  // Image always in a fixed center position — text is the dynamic element
  const imageLayout = (): "full" | "center" => {
    if (screen.visual_type === "image" && screen.image_paths.length > 0) {
      return "center";
    }
    return "center";
  };

  return (
    <AbsoluteFill>
      {/* Layer 0: Background */}
      <ClayBackground style={visualStyle} effects={effects} />

      {/* Layer 1: Images */}
      {screen.visual_type === "image" && screen.image_paths.length > 0 && (
        <ImageBlock
          imagePath={screen.image_paths[0]}
          effects={effects}
          style={visualStyle}
          sceneStartFrame={sceneStartFrame}
          sceneDurationFrames={sceneDurationFrames}
          layout={imageLayout()}
        />
      )}

      {screen.visual_type === "multi_image" && screen.image_paths.length > 0 && (
        <MultiImageBlock
          imagePaths={screen.image_paths}
          effects={effects}
          style={visualStyle}
          sceneStartFrame={sceneStartFrame}
          sceneDurationFrames={sceneDurationFrames}
        />
      )}

      {/* Layer 2: Text */}
      <TextBlock
        screen={screen}
        effects={effects}
        style={visualStyle}
        sceneStartFrame={sceneStartFrame}
        sceneDurationFrames={sceneDurationFrames}
      />

      {/* Layer 3: Overlay effects */}
      {effects.overlay_effect && effects.overlay_effect !== "overlay_none" && (() => {
        const OvComponent = getOverlayComponent(effects.overlay_effect);
        return <OvComponent {...(effects.overlay_params || {})} />;
      })()}

      {/* Layer 4: Brand bar */}
      {brandText && (
        <BrandBar
          text={brandText}
          color={rgbToCSS(visualStyle.primary)}
          textColor={rgbToCSS(visualStyle.text_light)}
        />
      )}

      {/* Layer 5: Audio */}
      {screen.audio_path && (
        <Audio src={staticFile(screen.audio_path)} />
      )}
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════
//  INTRO SCENE
// ═══════════════════════════════════════════════════

interface IntroSceneProps {
  title: string;
  hook: string;
  visualStyle: VisualStyle;
  brandText: string;
}

export const IntroScene: React.FC<IntroSceneProps> = ({
  title,
  hook,
  visualStyle,
  brandText,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleSpring = spring({ frame, fps, config: { damping: 14, mass: 0.8 } });
  const hookSpring = spring({ frame: Math.max(0, frame - 12), fps, config: { damping: 12 } });

  return (
    <AbsoluteFill>
      {/* Background */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `linear-gradient(135deg, 
            ${rgbToCSS(visualStyle.primary, 0.9)} 0%, 
            ${rgbToCSS(visualStyle.secondary, 0.9)} 50%,
            ${rgbToCSS(visualStyle.accent, 0.9)} 100%)`,
        }}
      />

      {/* Title */}
      <div
        style={{
          position: "absolute",
          top: "30%",
          left: 60,
          right: 60,
          textAlign: "center",
          opacity: titleSpring,
          transform: `translateY(${(1 - titleSpring) * 40}px) scale(${0.9 + titleSpring * 0.1})`,
        }}
      >
        <h1
          style={{
            fontFamily: "'Inter', 'SF Pro Display', sans-serif",
            fontSize: 52,
            fontWeight: 900,
            color: rgbToCSS(visualStyle.text_light),
            lineHeight: 1.2,
            textShadow: "0 4px 20px rgba(0,0,0,0.3)",
            margin: 0,
          }}
        >
          {title}
        </h1>
      </div>

      {/* Hook */}
      {hook && (
        <div
          style={{
            position: "absolute",
            top: "55%",
            left: 80,
            right: 80,
            textAlign: "center",
            opacity: hookSpring,
            transform: `translateY(${(1 - hookSpring) * 30}px)`,
          }}
        >
          <p
            style={{
              fontFamily: "'Inter', sans-serif",
              fontSize: 28,
              fontWeight: 500,
              color: rgbToCSS(visualStyle.text_light, 0.9),
              lineHeight: 1.5,
              margin: 0,
            }}
          >
            {hook}
          </p>
        </div>
      )}

      {/* Brand */}
      {brandText && (
        <BrandBar
          text={brandText}
          color={rgbToCSS(visualStyle.text_light, 0.2)}
          textColor={rgbToCSS(visualStyle.text_light)}
        />
      )}
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════
//  OUTRO SCENE
// ═══════════════════════════════════════════════════

interface OutroSceneProps {
  cta: string;
  brandText: string;
  visualStyle: VisualStyle;
}

export const OutroScene: React.FC<OutroSceneProps> = ({
  cta,
  brandText,
  visualStyle,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const enterSpring = spring({ frame, fps, config: { damping: 15 } });

  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(circle at 50% 50%, 
            ${rgbToCSS(visualStyle.bg_center_color)} 0%, 
            ${rgbToCSS(visualStyle.bg_edge_color)} 100%)`,
        }}
      />

      <div
        style={{
          position: "absolute",
          top: "40%",
          left: 60,
          right: 60,
          textAlign: "center",
          opacity: enterSpring,
          transform: `scale(${0.8 + enterSpring * 0.2})`,
        }}
      >
        <p
          style={{
            fontFamily: "'Inter', 'SF Pro Display', sans-serif",
            fontSize: 44,
            fontWeight: 800,
            color: rgbToCSS(visualStyle.text_dark),
            lineHeight: 1.3,
            margin: 0,
          }}
        >
          {cta}
        </p>
      </div>

      {brandText && (
        <BrandBar
          text={brandText}
          color={rgbToCSS(visualStyle.primary, 0.15)}
          textColor={rgbToCSS(visualStyle.primary)}
        />
      )}
    </AbsoluteFill>
  );
};

export default Scene;
