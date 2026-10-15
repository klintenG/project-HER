# ProjectHER — Unified Master Prompt for Watermark System + Signature Closing

## PURPOSE
This document is the **single source of truth** for implementing **both** of the following inside the **existing ProjectHER video-generation repository**:
1. the full in-video watermark / motion-branding system, and
2. the closing signature / branded outro sequence.

This prompt **supersedes the earlier split documents**:
- `ProjectHER_Codex_Watermark_Master_Prompt.md`
- `ProjectHER_Codex_Outro_Addendum.md`

Do not omit any behavior from either document. Implement the combined system so all approved branding behaviors coexist without conflicts.

---

## ROLE FOR CODEX
Act as a **senior Remotion motion designer, React/TypeScript engineer, and video rendering systems engineer** working **inside my current ProjectHER application codebase**.

Your job is to:
- inspect the existing repository structure,
- integrate the full branding behavior into the actual shared render pipeline,
- preserve all existing working video-generation flows,
- deliver production-ready code,
- avoid speculative redesigns,
- and validate the result in preview and exported MP4 output.

Do **not** create a separate prototype app, separate renderer, or parallel branding demo. Integrate directly into the existing ProjectHER implementation.

---

## BUSINESS GOAL
ProjectHER videos should feel:
- premium,
- elegant,
- editorial,
- authentic,
- consistent,
- and visibly branded without looking cheap or distracting.

The branding system must deter casual reposting/cropping while preserving content readability.
The ending should provide a refined sense of closure after narration ends.

---

## MASTER REFERENCES INCLUDED WITH THIS PACKAGE
Use the following reference images as **visual targets**. These are **reference mockups only**. Do **not** paste the PNG screenshots directly over videos. Recreate the design natively using Remotion + vector/text components.

### A. Watermark reference images (`references/watermark/`)
1. `00_option_5_original_reference.png`
   - Source of truth for the approved watermark direction.
   - Shows the combined appearance of:
     - top-right `projectHER` branding,
     - bottom `Made with projectHER` line,
     - faint diagonal protective overlay.
   - Important: this image shows all elements together for visual communication only. **Actual timing behavior must follow this prompt**.

2. `01_corner_brand_always_on.png`
   - Original ProjectHER frame with only the permanent corner logo visible.

3. `02_midpoint_made_with_credit.png`
   - Original ProjectHER frame showing the lower `Made with projectHER` credit treatment.

4. `03_intermit_protective_overlay.png`
   - Original ProjectHER frame showing the faint diagonal protective overlay.

5. `04_return_to_corner_only.png`
   - Original ProjectHER frame representing the normal in-between state where only the top-right logo remains.

6. `05_four_state_storyboard.png`
   - Summary of the intended state flow during the main video.

7. `06_example_timing.png`
   - Example timing diagram for a ~66.8 second portrait video.
   - This is illustrative, not a hard-coded schedule.

### B. Closing / outro reference images (`references/closing/`)
1. `01_last_story_frame_corner_logo.png`
   - Last story frame with the top-right brand still present.

2. `02_logo_moving_scene_fades.png`
   - Corner logo begins moving inward while story visuals begin transitioning.

3. `03_centered_brand_reveal.png`
   - Brand grows into the center and the branded closing look starts becoming dominant.

4. `04_final_navy_signature_RECOMMENDED.png`
   - Final recommended closing frame and the main visual target.

5. `05_final_ivory_editorial.png`
   - Acceptable alternate closing theme if configurable.

6. `06_final_soft_blur_variant.png`
   - Alternate retaining some blurred memory of the story frame.

7. `ProjectHER_Closing_Motion_Storyboard.png`
   - Storyboard for the full closing motion.

8. `ProjectHER_Final_Card_Options.png`
   - Comparison sheet of final card options.

### C. Supporting source screenshots (`references/source_frames/`)
Use these to understand the original ProjectHER video composition and content layout:
- `project_her_frame_18.jpg`
- `project_her_frame_33.jpg`
- `project_her_frame_63.jpg`
- `projecther_last_original_frame.png`
- `project_her_contact_sheet.jpg`
- `watermark_options_for_projecther.png`
- `projecther_watermark_style_comparison.png`

These are supporting references only, not overlay assets.

---

## NON-NEGOTIABLE BRAND DIRECTION

### Official brand name
- Product name: **ProjectHER**
- Wordmark styling: **`projectHER`**
  - `project` = lowercase
  - `HER` = uppercase
- Do **not** rename it to HER., HER Studio, K10 Motion, K10 Originals, etc.

### Palette
Use restrained premium colors:
- Deep navy: `#111B2B`
- Muted champagne gold: `#CBA96E`
- Warm ivory / light editorial surface: `#F7F5F0`
- Support neutrals may be derived near slate/navy families, but keep the system restrained.

### Typography
Preferred direction:
- Inter or a visually close existing bundled font,
- `project` in medium weight,
- `HER` in bold,
- clean kerning,
- precise alignment,
- no decorative script,
- no generic futuristic AI styling.

### Logo line
Optional / recommended subline under the wordmark:
- `STORIES IN MOTION`
- Small uppercase with generous tracking
- Keep where legible; may be hidden only when export size makes it unreadable.

### Style rules
Avoid:
- neon looks,
- glowing logo treatments,
- loud drop shadows,
- boxed/pill-shaped logo backgrounds,
- busy repeated pattern watermarks,
- generic AI sparkles,
- flashy 3D spin animations,
- YouTube-style subscription end cards,
- visual clutter.

The overall feel must remain premium editorial motion branding.

---

## SYSTEM OVERVIEW
The final ProjectHER branding system has **four coordinated layers/behaviors**:

### Layer 1 — Permanent top-right ProjectHER identity
- Always visible during the story/video content.
- Starts from frame 0.
- Remains visible throughout the video.
- During the final closing sequence, this **same visible logo** transitions into the centered closing brand signature.

### Layer 2 — Mid-video kinetic `Made with projectHER` credit
- Appears once during the main video timeline.
- Appears near the bottom of the frame.
- Animates in, stays visible for 3–5 seconds, animates out.
- Time placement is around the **middle of the video** (temporal midpoint), not vertical center.

### Layer 3 — Intermittent diagonal protective overlay
- A faint, low-opacity diagonal `projectHER` watermark.
- Appears at some point(s) during the video.
- Each appearance stays visible for 3–5 seconds.
- Should feel subtle, not distracting.

### Layer 4 — Branded ending / signature closing
- Starts only **after narration and final subtitle are complete**.
- Uses the same top-right ProjectHER brand, animating it smoothly to center.
- Ends on a premium brand closing frame.

---

## IMPORTANT DECISION: SHOULD LAYER 2 AND LAYER 3 APPEAR AT THE SAME TIME?
**Default answer: NO.**

### Reasoning
If the bottom `Made with projectHER` credit and the diagonal protective overlay appear at the same time, the screen will feel too busy because:
- the top-right logo is already always present,
- the content itself may have captions, narration-led story beats, and illustrations,
- ProjectHER's chosen aesthetic is clean editorial minimalism.

### Final rule
- Layer 1 (top-right logo) = always visible during main content.
- Layer 2 (`Made with projectHER`) = one mid-video occurrence.
- Layer 3 (diagonal protective overlay) = separate occurrence(s), not overlapping Layer 2 by default.
- Layer 4 (closing sequence) = after main content ends; transient overlays must be absent.

### Separation rule
Maintain at least **1.5 to 2.0 seconds gap** between transient branding events, measured from the end of one fade-out to the start of the next fade-in where possible.

---

## DETAILED IMPLEMENTATION SPECIFICATION

# 1. Layer 1 — Permanent top-right `projectHER`

## Behavior
- Present from video frame 0 until the end of the main video content.
- Then it smoothly transitions into the closing animation.
- It must not randomly disappear at scene changes.
- It must exist in exported output, not only in the preview UI.

## Appearance
- Display the `projectHER` wordmark.
- Show `STORIES IN MOTION` below it where legible.
- Transparent background.
- Crisp vector/SVG rendering.

## Baseline portrait layout (1080 × 1920)
- Approx. top inset: 90–125 px
- Approx. right inset: 65–85 px
- Approx. wordmark width: 190–240 px
- Scale proportionally for other resolutions/aspect ratios.

## Constraints
- Avoid overlap with headlines, captions, platform UI safe zones, and important scene labels.
- Choose a dark/light version if required for contrast.
- No visible boxed backing shape unless absolutely required.
- Position should remain stable across scene cuts.

## Architectural rule
This should be mounted once at a top-level shared composition layer where possible, not redundantly redefined inside every scene.

---

# 2. Layer 2 — Kinetic `Made with projectHER` credit

## Content
Center-aligned inline text:
- `Made with projectHER`

Style:
- `Made with` in muted navy/slate
- `projectHER` in official ProjectHER styling
- thin short horizontal rules on left and right
- no opaque banner background

## Vertical position
- Bottom region of the frame, similar to approved reference option 5.
- Must rise slightly if subtitles/platform controls require space.
- The user phrase “comes in the middle of the video” means **middle in time**, not middle of the screen.

## Time position
- Occurs once in normal short-form outputs.
- Target around 45%–55% of total main-content duration.
- Choose a calm portion of the scene.
- Avoid:
  - opening hook,
  - major reveal,
  - dense caption moment,
  - strong transition,
  - final story beat,
  - closing outro.

## Motion
### Entry (0.35–0.50s)
- Fade from 0 → 1
- Move upward by ~12–24px
- Use clean ease-out
- Thin side rules reveal via width expansion or subtle wipe
- Optional tiny scale settle (0.5–1.5%) allowed
- No elastic bounce

### Hold
- Fully visible hold = **3–5 seconds**
- Default hold = **4 seconds**
- Hold time excludes entry and exit durations

### Exit (0.35–0.50s)
- Fade out
- Reverse move slightly
- Retract side rules
- No soundtrack interruption

---

# 3. Layer 3 — Protective diagonal overlay

## Content
- Large diagonal `projectHER` wordmark only
- Do not include `STORIES IN MOTION` inside the giant overlay

## Visual angle
- Approx. diagonal orientation between `-25°` and `-38°`
  (visual rise bottom-left toward top-right)

## Positioning behavior
- Overlay should partially cross meaningful illustration/image regions sometimes.
- It should not fully sit only on blank margins.
- It must avoid meaningfully blocking faces, text, evidence, subtitles, or key scene focal points.
- Use defined diagonal anchor presets, not frame-by-frame jitter.

## Timing
For a typical 45–90 second video:
- Start with **2 occurrences** by default.
- Each occurrence:
  - fade in: ~0.4–0.6s
  - fully visible hold: **3–5 seconds**, default 4s
  - fade out: ~0.4–0.6s
- Optional micro drift during hold: 8–25px
- No spinning, sweeping, or aggressive motion.

## Opacity
- Base opacity target: **8–12%**
- Never exceed ~14% without explicit review
- Adapt to background legibility
- Goal = visible-but-subtle deterrent, not obvious ad overlay

## Determinism
- Schedule appearances deterministically.
- Seed with a stable render identifier or saved seed.
- Do not use unconstrained `Math.random()` per frame.
- Preview and final export must match.

---

# 4. Layer 4 — Signature closing / outro

## Key intent
After narration and final subtitle end, provide a premium ProjectHER closing with a sense of closure.

## Core idea
Instead of introducing a separate new end-card logo abruptly, use the **same top-right ProjectHER logo** that has been visible all along.
That logo should:
1. begin from its existing top-right position,
2. animate toward the center,
3. scale up gracefully,
4. while the story frame transitions into a refined brand background,
5. then hold as a finished ProjectHER brand signature.

## Non-negotiable closing behavior
- Start only after narration ends and final subtitle clears.
- Do not cut narration, last word, last subtitle, or last scene content.
- Temporary watermark layers (`Made with projectHER` and protective overlay) must be absent during the outro.
- Do not duplicate the logo visibly. Use one continuous moving brand element or a visually seamless handoff.

## Duration
- Default outro duration: **2.7 seconds**
- Configurable range: 2.0–3.0 seconds
- For the 30 FPS reference this equals **81 frames**
- Append it after the story content instead of overlapping the final spoken sentence.

## Recommended storyboard timing for 2.7s outro
### 0.00s
- Last story frame visible
- Top-right `projectHER` logo still in its normal position
- Narration already completed

### 0.00–0.80s
- The single logo translates from top-right to center
- Scale up by approx. 2.0–2.6x
- Use restrained ease-in-out
- No teleporting, no second logo

### 0.10–1.05s
- Story frame gently blurs/dims and crossfades into branded background
- Preferred default: midnight navy background with very subtle gradient/radial depth

### 0.65–1.20s
- `STORIES IN MOTION` tagline becomes readable beneath the logo
- Thin gold accent line reveals softly
- No excessive sparkle/particle noise

### 1.20–2.70s
- Hold centered logo and tagline clearly and stably
- End cleanly on the finished brand signature
- Optional fade to final black/end only if already part of product behavior

## Recommended closing theme
Default = **Midnight Navy**
- Background: navy
- `project` in light/off-white
- `HER` in gold
- Tagline in light text

Allowed alternates if configurable:
- ivory editorial theme
- soft-blur memory of story frame

But the primary shipping default should be the recommended navy signature.

## Size target for portrait closing state
For 1080 × 1920 final centered signature:
- logo width target: approx. 420–540 px
- centered within safe area
- tagline clearly legible beneath

## Audio rule
- Narration ends before outro begins
- Existing background music may decay naturally with subtle tail (0.2–0.4s if needed)
- Do not add loud logo stingers or cheesy sound effects automatically

---

## DURATION & SCHEDULING STRATEGY

### Example for ~66.8 second story video at 30 FPS
This is an example schedule only:
- Top-right logo: entire story duration
- Protective overlay #1: ~14–19 sec
- `Made with projectHER`: ~30.5–35.5 sec
- Protective overlay #2: ~46–51 sec
- Closing outro: starts only after story/narration/subtitles complete (~66.8 sec main content), then adds 2.7 sec

Resulting total output duration becomes approximately:
- main content: 66.8 sec
- outro: +2.7 sec
- total: ~69.5 sec

### Scheduling rules
1. Reserve the credit interval first (around middle of story timeline).
2. Place overlay occurrences outside that interval.
3. Maintain at least 1.5–2.0 sec gap between transient branding events.
4. Do not schedule transient overlays in the final outro.
5. If the video is short, adapt intelligently rather than forcing every event.

### Short video fallback suggestions
- Very short clip (<15s): keep permanent top-right logo + optionally one transient element only if it does not disturb pacing; outro may use shortened mode if explicitly supported.
- 15–30s: top-right + one credit or one overlay + optional shorter outro.
- 30–90s: full behavior set by default.

Use engineering judgment while preserving the approved aesthetic.

---

## IMPLEMENTATION APPROACH
Adapt to the actual repository, but the architecture should follow these principles:

1. Inspect:
   - Remotion compositions
   - scene sequencing
   - subtitle timing / alignment data
   - narration duration metadata
   - shared branding components
   - export/render pipeline
   - cloud render path if present

2. Create or refactor reusable components such as:
   - `ProjectHERBrandMark`
   - `ProjectHERCornerBrand`
   - `ProjectHERMadeWithCredit`
   - `ProjectHERProtectiveOverlay`
   - `ProjectHEROutro` / `ProjectHERBrandSignature`
   - `ProjectHERBrandingController` (or similar)

3. Mount the permanent logo in a shared top-level layer.

4. Drive all animation with deterministic Remotion logic using:
   - `useCurrentFrame`
   - `useVideoConfig`
   - `interpolate`
   - `Easing`
   - and only carefully bounded spring behavior if required

5. Compute transient schedule from stable timing metadata.

6. Compute `outroStartFrame` from actual end of story/narration/subtitles.

7. Extend `durationInFrames` to include outro duration.

8. Ensure preview and exported MP4 match visually.

9. Use vector/native text, not screenshot overlays.

10. Preserve all existing video-generation modes and output aspect ratios.

---

## CONFIGURATION EXPECTATIONS
Add configuration support where practical, adapting to the repo’s naming style.
Recommended config surface:

```ts
branding: {
  enabled: true,
  theme: 'projecther',
  alwaysOnCornerLogo: true,
  showTaglineWhenReadable: true,
  creditEnabled: true,
  creditHoldSeconds: 4,
  creditWindowStrategy: 'midTimeline',
  protectiveOverlayEnabled: true,
  protectiveOverlayOccurrences: 2,
  protectiveOverlayHoldSeconds: 4,
  protectiveOverlayOpacityRange: [0.08, 0.12],
  deterministicSeed: 'stable-per-render',
  outro: {
    enabled: true,
    durationSeconds: 2.7,
    theme: 'midnightNavy',
  }
}
```

This is an example only; fit it into the app’s actual config model.

---

## DO NOT BREAK / DO NOT CHANGE
- Do not break existing generation flows.
- Do not redesign the app into a different product.
- Do not rename ProjectHER.
- Do not remove the approved premium editorial style.
- Do not hardcode branding in a way that only works for one specific demo video.
- Do not add distracting motion or flashy VFX.
- Do not hide the permanent top-right identity during the story.
- Do not allow transient overlays to clutter the closing outro.
- Do not rely on preview-only CSS that vanishes in final encoded video.

---

## TESTING / ACCEPTANCE CHECKLIST
Implementation is complete only if all conditions below are satisfied.

### Core branding
- [ ] `projectHER` top-right brand appears from frame 0.
- [ ] It remains present throughout the story across scene cuts.
- [ ] It is visible in exported MP4, not just the UI preview.

### Mid-video credit
- [ ] `Made with projectHER` appears once during the main story timeline.
- [ ] It appears near the bottom of the frame.
- [ ] It uses kinetic motion in → hold → out.
- [ ] Fully visible hold lasts 3–5 seconds.
- [ ] It does not disrupt captions, hook, or key reveal.

### Protective overlay
- [ ] Faint diagonal `projectHER` overlay appears intermittently.
- [ ] Each occurrence holds 3–5 seconds.
- [ ] Opacity remains subtle (roughly 8–12%).
- [ ] It avoids meaningfully blocking key content.
- [ ] It is deterministic between preview and render.

### Simultaneity / scheduling
- [ ] `Made with projectHER` and protective overlay do not overlap by default.
- [ ] Transient events maintain sensible spacing.

### Outro
- [ ] Outro begins only after narration and final subtitle are complete.
- [ ] The same corner logo transitions smoothly to the center.
- [ ] No visible double-logo issue occurs.
- [ ] Centered signature grows to an elegant readable size.
- [ ] Recommended navy closing card is the default.
- [ ] Outro holds for proper closure and ends cleanly.
- [ ] Total output duration includes the appended outro.

### End-to-end system integrity
- [ ] Audio remains synchronized.
- [ ] Existing modes/exports still work.
- [ ] Portrait and supported non-portrait formats behave correctly.
- [ ] Full-size and mobile-sized review both look good.
- [ ] Preview and cloud/exported outputs are visually consistent.

### Evidence required from Codex
Codex should provide:
- changed file list / implementation summary,
- explanation of how schedule is computed,
- screenshots from rendered MP4 at key moments,
- a short exported preview showing:
  - normal corner logo,
  - protective overlay,
  - `Made with projectHER`,
  - closing motion.

---

## FINAL INSTRUCTION TO CODEX
Implement this branding system as a **single integrated ProjectHER branding feature set** inside the current repository.
Use the included references faithfully, but translate them into robust, reusable, resolution-independent motion components.

If a scene-specific conflict arises, protect story readability first while preserving the approved branding system.
Report any trade-offs transparently.

This document is the consolidated source of truth for the ProjectHER watermark system **and** the ProjectHER signature closing sequence.
