import {ProjectHERBrandingController,useBrandClosing} from './branding/Branding';
import {classicFrames,screenFrames,config} from './branding/timing';
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
  OffthreadVideo,
  Audio,
  Freeze,
  staticFile,
  Sequence,
  interpolate,
} from "remotion";
import { VideoProps, ScreenData, VisualStyle, SceneEffectsPlan } from "./types";
import { Scene, IntroScene, OutroScene } from "./components/Scene";
import { Watermark } from "./components/Watermark";
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

const StoryVideo: React.FC<VideoProps> = (props) => {
  const { fps, width, height } = useVideoConfig();
  const frame = useCurrentFrame();
  const closing=useBrandClosing();

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
      const durationFrames = screenFrames(screen, fps);
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

      // Never overlap spoken audio. Extend only the outgoing visual hold.
      const startFrame = i === 0 ? 0 : currentFrame;

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
  }, [screens, fps, layoutMode, transitionFramesProp]);

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {timeline.entries.map((entry, i) => {
        const { screen, startFrame, durationFrames, transitionIn, transitionOut } = entry;

        // Compute local frame from the global frame (for transition detection only).
        // Inside <Sequence>, children get the local frame automatically via useCurrentFrame().
        const localFrame = frame - startFrame;

        // Skip scenes that aren't currently visible
        if (localFrame < 0 || localFrame >= durationFrames+(transitionOut?.durationInFrames??0)) return null;

        // Determine if we're in a transition zone
        const inTransitionIn = transitionIn && localFrame < transitionIn.durationInFrames;
        const inTransitionOut = transitionOut && localFrame >= durationFrames;

        // Build the scene content — do NOT pass sceneStartFrame for frame math
        // since Sequence already offsets useCurrentFrame() for children.
        const sceneContent = screen.is_intro ? (
          <IntroScene
            title={title}
            hook={hook}
            visualStyle={visualStyle}
            brandText={config(props.branding).enabled ? "" : brandText}
          />
        ) : screen.is_outro ? (
          <OutroScene
            cta={cta}
            brandText={config(props.branding).enabled ? "" : brandText}
            visualStyle={visualStyle}
          />
        ) : (
          <Scene
            screen={{...screen,duration:durationFrames/fps}}
            visualStyle={visualStyle}
            brandText={config(props.branding).enabled ? "" : brandText}
            watermark={watermark}
            sceneStartFrame={startFrame}
            layoutMode={layoutMode || "classic"}
          />
        );

        // Wrap in transition if needed
        let rendered = <Freeze frame={durationFrames-1} active={localFrame>=durationFrames}>{sceneContent}</Freeze>;

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
              transitionFrame={localFrame - durationFrames}
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
            durationInFrames={durationFrames+(transitionOut?.durationInFrames??0)}
            name={`Scene-${i}-${screen.scene_type}`}
          >
            {rendered}
          </Sequence>
        );
      })}

      {!closing && timeline.entries.map(({screen,startFrame,durationFrames},i)=>screen.audio_path ? <Sequence key={`audio-${i}`} from={startFrame} durationInFrames={durationFrames}><Audio src={staticFile(screen.audio_path)}/></Sequence> : null)}

      {/* Global anti-crop watermark — renders above all scenes/transitions */}
      {!config(props.branding).enabled && watermark && (
        <Watermark text={watermark} />
      )}
    </AbsoluteFill>
  );
};

export const Video: React.FC<VideoProps> = (props) => {
 const branding=useMemo(()=>({deterministicSeed:props.title,contrast:(props.layout_mode==='fullbleed'||props.visual_style.bg_center_color.reduce((a,b)=>a+b,0)<384?'light':'dark') as 'light'|'dark',...props.branding}),[props.branding,props.title,props.layout_mode,props.visual_style]);
 let cursor=0;
 const windows=props.screens.map(s=>{const start=cursor;cursor+=screenFrames(s,props.fps);return {start:start+Math.round(props.fps*.6),end:cursor-Math.round(props.fps*.6)};});
 const regions=props.layout_mode==='fullbleed'?[]:props.screens.map((s,i)=>({start:windows[i].start,end:windows[i].end,x:.05,y:s.narration_position==='top'?.11:.72,w:.9,h:.18}));
 return <ProjectHERBrandingController storyFrames={classicFrames(props)} branding={branding} windows={windows} regions={regions}>{props.source_video?<EncodedStory src={props.source_video}/>:<StoryVideo {...props}/>}</ProjectHERBrandingController>;
};
export default Video;

const EncodedStory:React.FC<{src:string}>=({src})=><OffthreadVideo src={staticFile(src)} muted={useBrandClosing()} style={{width:"100%",height:"100%",objectFit:"contain"}}/>;
