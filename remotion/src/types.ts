import {BrandingSchema} from './branding/timing';
/**
 * Project HER v2.0 – Remotion Video Schema & Types
 * =================================================
 * Complete type definitions for the video data passed from
 * the Python pipeline to the Remotion renderer.
 */

import { z } from "zod";

// ── Word Timing (from edge-tts WordBoundary) ──
export const WordTimingSchema = z.object({
  word: z.string(),
  start: z.number(), // seconds
  end: z.number(),   // seconds
});
export type WordTiming = z.infer<typeof WordTimingSchema>;

// ── Emphasis Word ──
export const EmphasisWordSchema = z.object({
  text: z.string(),
  style: z.enum(["bold", "color", "scale", "pulse"]).default("bold"),
});
export type EmphasisWord = z.infer<typeof EmphasisWordSchema>;

// ── Per-Scene Effects Plan ──
export const SceneEffectsPlanSchema = z.object({
  screen_index: z.number(),
  text_entry: z.string().default("fade_in"),
  text_entry_params: z.record(z.any()).default({}),
  text_exit: z.string().default("fade_out"),
  text_exit_params: z.record(z.any()).default({}),
  text_continuous: z.string().default("none"),
  text_continuous_params: z.record(z.any()).default({}),
  image_entry: z.string().default("img_fade_in"),
  image_entry_params: z.record(z.any()).default({}),
  image_treatment: z.string().default("ken_burns"),
  image_treatment_params: z.record(z.any()).default({}),
  image_exit: z.string().default("img_fade_out"),
  image_exit_params: z.record(z.any()).default({}),
  scene_transition: z.string().default("crossfade"),
  scene_transition_params: z.record(z.any()).default({}),
  overlay_effect: z.string().default("overlay_none"),
  overlay_params: z.record(z.any()).default({}),
  background_effect: z.string().default("bg_none"),
  background_params: z.record(z.any()).default({}),
  emphasis_style: z.string().default("scale_bounce"),
  emphasis_params: z.record(z.any()).default({}),
  reasoning: z.string().default(""),
});
export type SceneEffectsPlan = z.infer<typeof SceneEffectsPlanSchema>;

// ── Screen Segment (one scene in the video) ──
export const ScreenDataSchema = z.object({
  index: z.number(),
  text: z.string(),
  duration: z.number(),
  visual_type: z.enum(["image", "text_only", "multi_image"]).default("image"),
  scene_type: z.string().default("B"),
  emotion: z.string().default("neutral"),
  is_intro: z.boolean().default(false),
  is_outro: z.boolean().default(false),
  setup_text: z.string().default(""),
  subject_text: z.string().default(""),
  caption_text: z.string().default(""),
  speaker: z.string().default(""),
  character_name: z.string().default(""),
  narration_position: z.string().default("top"),
  emphasis_words: z.array(EmphasisWordSchema).default([]),
  // Image paths (resolved by Python)
  image_paths: z.array(z.string()).default([]),
  // Audio path
  audio_path: z.string().default(""),
  audio_duration: z.number().default(0),
  // Word timings for karaoke
  word_timings: z.array(WordTimingSchema).default([]),
  // Effects plan for this scene
  effects: SceneEffectsPlanSchema.optional(),
});
export type ScreenData = z.infer<typeof ScreenDataSchema>;

// ── Visual Style Tokens ──
export const VisualStyleSchema = z.object({
  name: z.string().default("claymorphism"),
  bg_center_color: z.tuple([z.number(), z.number(), z.number()]).default([240, 235, 225]),
  bg_edge_color: z.tuple([z.number(), z.number(), z.number()]).default([215, 206, 194]),
  text_dark: z.tuple([z.number(), z.number(), z.number()]).default([45, 35, 30]),
  text_light: z.tuple([z.number(), z.number(), z.number()]).default([255, 255, 255]),
  primary: z.tuple([z.number(), z.number(), z.number()]).default([255, 136, 0]),
  secondary: z.tuple([z.number(), z.number(), z.number()]).default([75, 140, 200]),
  accent: z.tuple([z.number(), z.number(), z.number()]).default([255, 87, 51]),
  card_bg: z.tuple([z.number(), z.number(), z.number(), z.number()]).default([255, 255, 255, 200]),
  card_radius: z.number().default(24),
  image_corner_radius: z.number().default(20),
  highlight_color: z.tuple([z.number(), z.number(), z.number()]).default([255, 136, 0]),
  highlight_text: z.tuple([z.number(), z.number(), z.number()]).default([255, 255, 255]),
});
export type VisualStyle = z.infer<typeof VisualStyleSchema>;

// ── Complete Video Input Props ──
export const VideoPropsSchema = z.object({
  branding: BrandingSchema.optional(),
  source_video:z.string().optional(),
  source_duration_frames:z.number().int().positive().optional(),
  title: z.string(),
  hook: z.string().default(""),
  autopilot_hook: z.string().max(90).optional(),
  brand_text: z.string().default(""),
  watermark: z.string().default(""),
  mood: z.string().default("neutral"),
  content_mode: z.string().default("article"),
  screens: z.array(ScreenDataSchema),
  visual_style: VisualStyleSchema.default({}),
  fps: z.number().default(30),
  width: z.number().default(1080),
  height: z.number().default(1920),
  cta: z.string().default("Thanks for watching!"),
  visual_theme: z.string().default("dynamic"),
  // Enhanced pipeline flags (Generate tab only)
  layout_mode: z.enum(["classic", "fullbleed"]).default("classic"),
  transition_frames: z.number().default(15),
  scene_silence_ms: z.number().default(0),
});
export type VideoProps = z.infer<typeof VideoPropsSchema>;

// ── Helpers ──
export function rgbToCSS(rgb: [number, number, number], alpha = 1): string {
  return `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${alpha})`;
}

export function rgbaToCSS(rgba: [number, number, number, number]): string {
  return `rgba(${rgba[0]}, ${rgba[1]}, ${rgba[2]}, ${rgba[3] / 255})`;
}
