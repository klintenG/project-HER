/**
 * Project HER v2.0 – Main Video Composition
 * ==========================================
 * Sequences all scenes with transitions into a complete video.
 * Receives VideoProps as input props from the Python bridge.
 */

import React, { useMemo } from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  AbsoluteFill,
  Sequence,
  interpolate,
} from "remotion";
import { VideoProps, ScreenData, VisualStyle, SceneEffectsPlan } from "./types";
import { Scene, IntroScene, OutroScene } from "./components/Scene";
import { getTransition, TransitionTiming } from "./transitions/sceneTransitions";

// ═══════════════════════════════════════════════════
//  TRANSITION WRAPPER
// ═══════════════════════════════════════════════════

interface TransitionLayerProps {
  children: React.ReactNode;
  transition: TransitionTiming;
  transitionFrame: number; // frame within the transition zone
  isEntering: boolean;
}

const TransitionLayer: React.FC<TransitionLayerProps> = ({
  children,
  transition,
  transitionFrame,
  isEntering,
}) => {
  const progress = interpolate(transitionFrame, [0, transition.durationInFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const style = isEntering
    ? transition.enterStyle(progress)
    : transition.exitStyle(progress);

  return (
    <AbsoluteFill style={style}>
      {children}
    </AbsoluteFill>
  );
};

// ═══════════════════════════════════════════════════
//  VIDEO COMPOSITION
// ═══════════════════════════════════════════════════

export const Video: React.FC<VideoProps> = (props) => {
  const { fps, width, height } = useVideoConfig();
  const frame = useCurrentFrame();

  const {
    title,
    hook,
    brand_text: brandText,
    watermark,
    screens,
    visual_style: visualStyle,
    cta,
    layout_mode: layoutMode,
    transition_frames: transitionFramesProp,
  } = props;

  // Build timeline: compute start frame and duration for each scene
  const timeline = useMemo(() => {
    const DEFAULT_TRANSITION_FRAMES = transitionFramesProp || 15;
    let currentFrame = 0;
    const entries: Array<{
      screen: ScreenData;
      startFrame: number;
      durationFrames: number;
      transitionIn?: TransitionTiming;
      transitionOut?: TransitionTiming;
    }> = [];

    screens.forEach((screen, i) => {
      const durationFrames = Math.round(screen.duration * fps);
      const effects = screen.effects;

      // Variable transition duration based on emotion (enhanced pipeline)
      let tFrames = DEFAULT_TRANSITION_FRAMES;
      if (layoutMode === "fullbleed" && effects) {
        const emotion = screen.emotion || "neutral";
        // Fast cuts for action/urgent, slow for calm/sad
        const emotionTransFrames: Record<string, number> = {
          excitement: 8, urgent: 6, anger: 8, tension: 10,
          joy: 10, triumph: 10, dramatic: 12,
          calm: 24, sadness: 24, nostalgia: 22, thoughtful: 20,
          mystery: 18, awe: 20, wonder: 20, horror: 14,
          neutral: 15, informative: 15,
        };
        tFrames = emotionTransFrames[emotion] || DEFAULT_TRANSITION_FRAMES;
      }

      // Transition INTO this scene (from previous)
      const transitionIn = i > 0
        ? getTransition(effects?.scene_transition || "crossfade", tFrames)
        : undefined;

      // For the first scene, no overlap
      const overlap = transitionIn ? transitionIn.durationInFrames : 0;
      const startFrame = i === 0 ? 0 : currentFrame - overlap;

      entries.push({
        screen,
        startFrame,
        durationFrames,
        transitionIn,
      });

      currentFrame = startFrame + durationFrames;
    });

    // Link transition out to next scene's transition in
    for (let i = 0; i < entries.length - 1; i++) {
      entries[i].transitionOut = entries[i + 1].transitionIn;
    }

    return { entries, totalFrames: currentFrame };
  }, [screens, fps]);

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {timeline.entries.map((entry, i) => {
        const { screen, startFrame, durationFrames, transitionIn, transitionOut } = entry;

        // Compute local frame from the global frame (for transition detection only).
        // Inside <Sequence>, children get the local frame automatically via useCurrentFrame().
        const localFrame = frame - startFrame;

        // Skip scenes that aren't currently visible
        if (localFrame < 0 || localFrame >= durationFrames) return null;

        // Determine if we're in a transition zone
        const inTransitionIn = transitionIn && localFrame < transitionIn.durationInFrames;
        const inTransitionOut = transitionOut && localFrame >= durationFrames - transitionOut.durationInFrames;

        // Build the scene content — do NOT pass sceneStartFrame for frame math
        // since Sequence already offsets useCurrentFrame() for children.
        const sceneContent = screen.is_intro ? (
          <IntroScene
            title={title}
            hook={hook}
            visualStyle={visualStyle}
            brandText={brandText}
          />
        ) : screen.is_outro ? (
          <OutroScene
            cta={cta}
            brandText={brandText}
            visualStyle={visualStyle}
          />
        ) : (
          <Scene
            screen={screen}
            visualStyle={visualStyle}
            brandText={brandText}
            watermark={watermark}
            sceneStartFrame={startFrame}
            layoutMode={layoutMode || "classic"}
          />
        );

        // Wrap in transition if needed
        let rendered = sceneContent;

        if (inTransitionIn && transitionIn) {
          rendered = (
            <TransitionLayer
              transition={transitionIn}
              transitionFrame={localFrame}
              isEntering={true}
            >
              {rendered}
            </TransitionLayer>
          );
        } else if (inTransitionOut && transitionOut) {
          rendered = (
            <TransitionLayer
              transition={transitionOut}
              transitionFrame={localFrame - (durationFrames - transitionOut.durationInFrames)}
              isEntering={false}
            >
              {rendered}
            </TransitionLayer>
          );
        }

        return (
          <Sequence
            key={i}
            from={startFrame}
            durationInFrames={durationFrames}
            name={`Scene-${i}-${screen.scene_type}`}
          >
            {rendered}
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

export default Video;
