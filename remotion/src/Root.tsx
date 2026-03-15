/**
 * Project HER v2.0 – Root Composition
 * =====================================
 * Registers the Remotion composition and reads input props.
 */

import React from "react";
import { Composition } from "remotion";
import { Video } from "./Video";
import { VideoPropsSchema, VideoProps } from "./types";
import { EffectPreview, EffectPreviewSchema } from "./EffectPreview";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="ProjectHER"
        component={Video}
        durationInFrames={300} // overridden by calculateMetadata
        fps={30}
        width={1080}
        height={1920}
        schema={VideoPropsSchema}
        defaultProps={{
          title: "Project HER Demo",
          hook: "AI-powered article to video",
          brand_text: "HER",
          watermark: "",
          mood: "neutral",
          content_mode: "article",
          screens: [
            {
              index: 0,
              text: "Welcome to Project HER",
              duration: 4,
              visual_type: "text_only",
              scene_type: "A",
              emotion: "neutral",
              is_intro: true,
              is_outro: false,
              setup_text: "",
              subject_text: "",
              caption_text: "",
              speaker: "",
              character_name: "",
              narration_position: "top",
              emphasis_words: [],
              image_paths: [],
              audio_path: "",
              audio_duration: 0,
              word_timings: [],
            },
          ],
          visual_style: {
            name: "claymorphism",
            bg_center_color: [240, 235, 225],
            bg_edge_color: [215, 206, 194],
            text_dark: [45, 35, 30],
            text_light: [255, 255, 255],
            primary: [255, 136, 0],
            secondary: [75, 140, 200],
            accent: [255, 87, 51],
            card_bg: [255, 255, 255, 200],
            card_radius: 24,
            image_corner_radius: 20,
            highlight_color: [255, 136, 0],
            highlight_text: [255, 255, 255],
          },
          fps: 30,
          width: 1080,
          height: 1920,
          cta: "Thanks for watching!",
          visual_theme: "dynamic",
          layout_mode: "classic",
          transition_frames: 15,
          scene_silence_ms: 0,
        }}
        calculateMetadata={async ({ props }) => {
          // Calculate total duration from all screens
          const totalSeconds = props.screens.reduce(
            (sum: number, s: { duration: number }) => sum + s.duration,
            0,
          );
          const fps = props.fps || 30;
          return {
            durationInFrames: Math.ceil(totalSeconds * fps),
            fps,
            width: props.width || 1080,
            height: props.height || 1920,
          };
        }}
      />

      {/* Effect Preview – short clips for Remotion Studio */}
      <Composition
        id="EffectPreview"
        component={EffectPreview}
        durationInFrames={90}
        fps={30}
        width={540}
        height={960}
        schema={EffectPreviewSchema}
        defaultProps={{
          effectCategory: "text_entry",
          effectName: "scale_bounce",
        }}
      />
    </>
  );
};
