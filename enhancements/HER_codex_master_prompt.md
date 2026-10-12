# Codex master prompt: build the reference editorial video system in Project HER

Copy the prompt below into your coding agent. Give it the local application repository, both videos, and `HER_video_diagnosis.md`. Set the two video paths to their locations on your computer; the reference upload may be named `reference-ai-video(1).mp4`.

---

## Your task

You are the senior engineer and motion designer implementing this change in my existing Project HER video-generation application. Work in the actual repository. Diagnose the current output, implement the changes, render representative videos, inspect the results, and iterate until the new preset reproduces the reference's editorial style closely.

Inputs:

- `REFERENCE_VIDEO_PATH`: /Users/klinten/Desktop/My-projects/project-HER/enhancements/reference-ai-video.mp4
- `BASELINE_VIDEO_PATH`: /Users/klinten/Desktop/My-projects/project-HER/enhancements/generated-video.mp4
- `HER_video_diagnosis.md`: /Users/klinten/Desktop/My-projects/project-HER/enhancements/HER_video_diagnosis.md


The reference is a minimalist, layered, kinetic editorial explainer. Its appearance comes from timed words, isolated assets, shadows, semantic visual actions and continuity. My current output mostly holds a full headline above fixed assets. Fix that production model. Merely changing a theme, turning on random effects, adding a zoom, or making the video longer is insufficient.

Deliver working code and demonstrated output. Do not stop after proposing an architecture, creating disconnected components, or declaring visual parity without reviewing a render.

## 1. Inspect and establish the baseline

Read applicable repository instructions and inspect the current renderer, installed versions and pipeline. Locate the actual equivalents of these documented files:

- `agent/orchestrator.py`, `agent/analyzer.py`, `agent/story_splitter.py`.
- `agent/visuals.py`, `agent/ai_visuals.py`.
- `agent/narration.py`, `agent/google_tts.py`, `agent/elevenlabs_tts.py`, other TTS adapters.
- `agent/effects_agent.py`, `agent/audio_engine.py`, `agent/audio_utils.py`.
- `agent/remotion_renderer.py`.
- `remotion/src/Root.tsx`, `Video.tsx`, `types.ts`, scene/text/image components.
- Flask/Gradio/CLI configuration and preset controls.

Inspect both MP4s locally with audio playback. Extract a visual contact sheet at least once per second, then inspect short transitions at source frame rate. Listen to narration, music and effects. Determine the reference's spoken-word timing with an available transcription/alignment route. Keep visually observed timing distinct from measured speech timing.

Trace one real generation run from input to final Remotion props and assembled audio. Check whether word timestamps exist, whether they reach the renderer, whether text code actually uses them, and whether settings are silently replaced by defaults. Inspect any baseline manifest or generation inputs available. If the baseline's exact input is unavailable, state that and create a comparable controlled fixture.

Record source-level causes for the static headline cards, repeated generic assets, transition washouts, long inter-section pauses and low loudness. Do not assume every documented feature is enabled merely because it exists in a catalog.

## 2. Scope and compatibility

Add a visual/output preset named `reference_editorial` or a clear equivalent within the existing architecture. Keep content mode and visual preset separate.

If a News mode already exists, expose this preset there and connect it to the existing News pipeline. If it does not exist, add the visual preset to the generator without inventing a separate news research system as part of this task. Support the existing URL/text/story inputs through their current routes.

Preserve existing article, topic, story, voice, stock-image, AI-image and other mode behavior when the new preset is not selected. Do not globally replace the renderer or default effect behavior for unrelated presets. Preserve old manifests using versioned schemas or explicit adapters. Keep user data and cached assets usable.

Use Remotion for this preset, building on the installed project's APIs and patterns. If the MoviePy backend cannot faithfully support the required layered events, clearly state that in the UI/configuration and require Remotion for this preset. Never silently substitute the old card compositor while claiming the reference style was produced.

Do not add new paid services unless necessary and configured. Reuse existing TTS and asset providers. Keep the change within video generation; unrelated publication, deployment and automation changes are outside this task.

## 3. Define the visual contract

Target output: vertical 1080 × 1920, 30 fps, H.264 video with AAC audio. Preserve quality rather than reproducing the reference's low bitrate. Export consistent BT.709 color handling and a compatible pixel format; inspect actual resulting metadata and image appearance.

The visual contract:

1. One continuous cool, light-gray stage with a brighter middle and gentle darker outer/top/bottom regions.
2. Mostly dark-gray typography. Photographic colors and occasional document/emblem colors supply accents.
3. A rounded/geometric sans serif. Inspect available fonts; choose a close licensed family, compare letterforms to the reference, and bundle/load it deterministically. Do not claim the font family has been recovered from the MP4.
4. Separate people, objects, location silhouettes, text blocks, labels and shadows.
5. Soft lower fades for suitable cutout portraits; retain rectangles for documentary photos where appropriate.
6. Low-opacity directional cast shadows and restrained contact shadows, with consistent direction across the production.
7. Timed word/phrase reveals and deliberate size/weight hierarchy.
8. Varied semantic compositions and meaningful object actions inside scenes.
9. Short, coordinated transitions that maintain the background and narrative continuity.
10. Quiet holds after meaningful reveals; movement should explain the story.

Do not enable generic particles, auroras, glitter, animated brand bars, neon karaoke boxes, loud badges, decorative spinning cubes or unrelated catalog effects by default in this preset. The perspective jewel-box action in the reference is a story-object action; support analogous object actions when relevant.

Initial 1080p tuning ranges, to verify visually:

- Ordinary narration phrases: roughly 52–68 px.
- Emphasis/names: roughly 78–110 px.
- Dominant years/locations: roughly 120–180 px.
- Entity labels: roughly 32–44 px; never shrink them into illegibility to fit.
- Side safe margins: initially about 8% of width; verify for the target platform.
- Most meaningful compositions occupy the central/upper-middle region, with generous intentional negative space.

These values are starting points. Measure the reference's proportions at a common canvas size and refine them. Do not use one fixed headline rectangle and one fixed image rectangle for every shot.

## 4. Separate narrative sections from visual beats

Stop treating one narration paragraph as one indivisible card.

Maintain two related structures:

- **Narrative sections:** coherent phrases/sentences with recorded voice timing.
- **Visual beats:** separately timed changes in text, assets, layout, emphasis, movement or state within and across those sections.

A sentence may introduce a person, show a second entity, reveal a claim, emphasize its subject, and move to an explanatory object without needing five separate TTS clips. Likewise, one established object can persist across two sections.

Plan the script for a compact hook, context, meaningful development and an honest takeaway. For news, preserve claims as claims and label attribution appropriately. Do not turn an accusation into a verified fact or invent a launch date to manufacture a conclusion.

For the baseline topic, prefer explanatory visual concepts such as a person/company introduction, attributed claim, response, requirements, license-versus-readiness distinction and uncertainty about a timeline. Use only details supported by the actual input/source records. This is a storyboard example, not permission to fabricate news.

Allow configurable duration; around 45–60 seconds can be a useful default for an explainer, but a concise 34-second story can still have the same production quality. Do not pad to 58 seconds. Resolve duration through script length and actual speech rate before freezing the final frame timeline.

## 5. Add a validated editorial timeline

Extend or adapt the existing schema so the renderer receives a complete, explicit, deterministic plan. Do not generate executable TSX/CSS from the LLM.

Required concepts:

- `schemaVersion`, `preset`, `width`, `height`, `fps`, `durationInFrames`.
- Global narration asset(s), music/effects assets when configured, and actual audio offsets.
- Aligned words with stable IDs, original text, start/end seconds or frames and alignment provenance/confidence.
- Persistent entities with stable IDs, canonical names, asset references and identity/source metadata.
- Scene/layout templates, absolute timeline starts/ends, and logical narration references.
- Independently timed layers: subject, object, map, photo, heading, narration phrase, entity label, shadow.
- Layer anchors, bounds, z-order, transform origin, masks and allowed treatments.
- Phrase blocks with exact word IDs, emphasis spans, reveal mode and layout anchor.
- Events with absolute frame ranges, target layer IDs, allowlisted action types and validated parameters.
- Transition metadata, including which layers persist, leave or enter.
- Optional complete subtitle track distinct from editorial text.

Use the project's existing validation tools; if it already uses Zod/Pydantic, integrate with them rather than introducing a second contradictory contract. Validate at the Python→JSON boundary and again before rendering. Share one schema or add explicit conformance fixtures so both sides agree.

Example event semantics, adapted to actual project types:

```json
{
  "type": "compare_focus",
  "startFrame": 90,
  "endFrame": 102,
  "primaryLayerId": "entity-b-visual",
  "secondaryLayerId": "entity-a-visual",
  "primaryScale": [1.0, 1.28],
  "secondaryScale": [1.0, 0.78],
  "easing": "easeOutCubic"
}
```

This illustrates the contract, not a claim about an existing Remotion API. Implement appropriate components/helpers using the installed project version.

Validate that entity/word/layer references resolve; frame ranges are finite and within the composition; visible layers do not have negative dimensions; alignment is monotonic; emphasis spans correspond to actual words; and unsupported action/template names cannot silently fall back to a generic card.

Use one explicit frame interval convention, preferably `[startFrame, endFrame)`. Derive seconds→frames consistently. Calculate total composition length from the actual master timeline, including any deliberate closing hold. Do not subtract visual overlaps from narrated audio duration or accumulate rounding error across sections.

## 6. Make narration timing authoritative

Write the approved script first. Generate narration and obtain true word timing before final visual scheduling.

Use reliable provider timestamps when available. Otherwise use forced alignment of the known script against the generated audio with an available local/configured tool. Do not simulate alignment by assigning equal time per word or dividing by character count.

Prefer continuous narration or sentence groups when the provider supports it. If using separate clips, detect redundant start/end padding, preserve consonant onsets and breathing, assemble the master track, and remap every word timestamp to its true global offset. Inspect the waveform and listen before deciding how much to trim. Avoid truncating legitimate pauses.

Preserve punctuation, contractions, hyphenated names and multilingual text. Normalize for matching without losing the original display text. Tag missing/low-confidence alignment instead of quietly claiming accuracy.

Once final audio is assembled, schedule text reveal and semantic events on it:

- Introduce a name/object as the relevant phrase is spoken.
- Reveal the important word at its actual time; a small purposeful anticipation may be configured, not invented accidentally.
- Keep complete phrase text long enough to read before it exits.
- Allocate brief pauses for genuine emphasis.
- Avoid automatic 1+ second pauses at every scene boundary.

For the default flowing explainer, start with approximately 80–250 ms intentional sentence/section gaps where suitable and a short closing hold. These are adjustable targets, not mandatory trims of all silence.

## 7. Implement progressive editorial typography

Provide a dedicated component for timed phrase blocks with separate modes:

- `word_accumulate`: words appear in sequence and previously revealed words remain.
- `phrase_reveal`: a short phrase appears as a unit when appropriate.
- `emphasis_reveal`: selected names, dates or conclusions arrive with stronger size/weight.
- `connector`: brief low-density text between visual ideas.
- `entity_label`: anchored to an object/person and readable independently.

The target is not a static full headline with a moving colored highlight. Keep the default reference-like text dark gray, with hierarchy rather than a neon karaoke palette.

Reserve the final phrase's measured layout before reveal, retaining invisible words in geometry or an equivalent approach. This prevents line wrapping and centering from shifting every time a word appears. Load fonts before measurement/render. Make deliberate line breaks part of the validated plan, with renderer correction if they exceed bounds.

A single sentence may occupy a top block and then a lower emphasis block. Choose position based on visual bounds; do not cover faces or squeeze a caption into a map/portrait. Keep labels attached to their moving entity. Reposition headings when subjects move, rather than leaving them behind in empty space.

For complete subtitles, provide an aligned SRT/VTT export. If a full subtitle overlay is enabled, use an explicit layout profile that prevents duplicated simultaneous text and collisions with editorial blocks. Distinguish full spoken captions from editorial summaries in data and UI.

## 8. Build a compact semantic template library

Implement reusable templates that consume explicit layers and events, not hardcoded topic-specific videos:

1. **Single subject/object:** focal asset, timed top phrase, optional lower emphasis.
2. **Two-entity comparison:** independently sized assets, anchored labels, focus shift to one entity.
3. **Person + context:** foreground figure and a low-opacity location/organization/context layer behind.
4. **Object + location:** map/landmark behind a persistent foreground object.
5. **Document/photo:** properly framed archival/photo/source visual with progressive explanatory text.
6. **Date/year:** dominant digits, optional counting transition, then person/event reveal.
7. **Location transfer:** origin→destination movement while the core object remains identifiable.
8. **Process/requirements:** staged reveal of a small number of relevant requirements or states.
9. **Text connector:** deliberately brief text-only transition.
10. **Conclusion:** concrete named anchor or truthful uncertainty/takeaway with a readable final hold.

Use suitable templates for the story, not all of them in every render. Avoid choosing the same template for three consecutive narrative developments unless continuity requires it and the internal state meaningfully changes.

Keep a clean default 9:16 layout. If horizontal/square variants are supported, use actual layout profiles; do not stretch portrait geometry and claim parity.

## 9. Implement the missing explanatory event primitives

At minimum, support these actions with explicit timing and testable intermediate states:

- **Focus shift:** primary object grows while secondary object reduces/recedes; labels remain attached.
- **Oversized entrance and settlement:** an incoming object briefly starts larger and settles rapidly with fade/position coordination.
- **Persistent context change:** person remains while map/context and narration block change.
- **Location transfer:** move a stable object/entity between place compositions.
- **Map separation:** divide verified map geometry into independently moving regions. Prefer vetted SVG/masks; do not invent boundaries with an image model.
- **Year counter:** change digits through a range and settle on the correct final year. The settled value is factual; intermediate values are clearly transitional, not presented as additional events.
- **Object action:** a relevant object opens, closes, flips, or changes state; support a perspective box/lid action or equivalent demonstrable capability.
- **Representation swap:** exchange an object's photographic view and contextual representation while preserving its entity identity.
- **Emphasis conclusion:** meaningful words arrive in a larger block following a setup phrase.

Every action must work as a reusable primitive. Do not hardcode Queen Victoria, a diamond or a specific news story into the renderer. Do not add arbitrary motion when the input has no semantic reason for that action.

## 10. Preserve layer continuity through transitions

Use short transitions selected by meaning:

- Lateral slide/reframe for a location change or next related idea.
- Scale/opacity settlement for a focal entity introduction.
- Quick representation swap for a new view of the same object.
- Modest overlap fade for an idea boundary with no spatial relationship.
- Object-specific action for an actual opening/closing/transfer event.

Start with roughly 6–12 frames for many transitions, then tune against the reference. Some reference transitions settle over slightly longer periods; do not force every event to the same duration.

Keep the gray stage visible and consistent. Avoid fading the entire composition to near-white between sentences. Outgoing and incoming subject/text layers should overlap deliberately. If an entity persists, do not destroy/recreate it unnecessarily; preserve asset identity and animate its new anchor.

Use absolute frame timing and clamp progress values. Avoid double-transforming assets through both a parent transition and child zoom. Ensure transition overlap does not shift or truncate the narration track. Labels and shadows must follow the same coordinate transform as their subject, while planned text blocks may stay in screen space.

All animations must be deterministic under frame seeking and parallel rendering. Use seeded randomness only when needed. Do not rely on wall-clock time, uncontrolled CSS animations or asynchronous state changes to determine a frame.

## 11. Correct the asset pipeline

Create an entity registry before asset acquisition. Reuse one consistent approved asset per entity unless a view change is intentional.

For each asset retain: entity ID, requested role, actual subject, local path, source/provenance, dimensions, crop/focal point, alpha availability, preparation status, confidence, and whether it is factual or symbolic.

Correct the visible baseline failures:

- Do not label a generic globe “Starlink” as if it establishes the actual brand/product. Use a correct supplied/sourced representation where possible. Otherwise use an explicit satellite/network symbol and label its role honestly.
- Do not label an arbitrary classical building “Ministry of Communications” as though it were a verified photograph. Use a verified relevant source visual, properly identified official text/document, or a neutral institutional symbol.
- Do not use fabricated photorealistic portraits for named real people.
- Do not make up logos, maps, dates or document screenshots with AI imagery.

Permit user-provided local assets and existing approved cache assets. Preserve both stock and AI-image workflows. AI imagery can supply appropriate generic illustrations, but does not verify an entity's identity.

Use relevant semantic queries and explicit asset-role validation instead of one broad keyword. Avoid fetching a new inconsistent portrait whenever the same name appears. Cache original and prepared forms separately, keyed by asset identity and preparation settings.

Prepare assets before rendering:

- Correct orientation/crop and keep enough resolution for planned enlargement.
- Remove backgrounds for suitable cutouts using available tools.
- Trim transparent padding so geometry reflects actual visible bounds.
- Add a feathered lower fade only where stylistically appropriate.
- Preserve rectangular documents/photos when that format carries meaning.
- Produce stable silhouettes for shadows where useful.
- Detect matte halos, clipped heads, distorted proportions and unintended white boxes.

If a correct asset is unavailable, use an explicit labeled symbolic fallback and report it in the run manifest. Do not silently claim asset accuracy. Never pass a missing image path to the final renderer and conceal the failure behind a blank scene.

## 12. Improve the audio assembly and final mix

The supplied baseline measures approximately −25.21 LUFS integrated, versus −14.21 LUFS for the reference. It has five near-silent inter-section gaps of approximately 1.15–1.24 seconds. Reproduce these measurements before changing code, then inspect their cause.

Check duplicate padding, per-scene voice tails, scene-transition silence, provider leading silence, renderer offsets and repeated volume attenuation. Fix the underlying assembly logic before adding music to hide the gaps.

Keep narration intelligible and at stable perceived volume. If a bed is configured, make it continuous, restrained and compatible with the story; duck it under speech. Add short effects only where they support an actual event. Do not automatically add a whoosh to every cut.

Normalize the final assembled stereo mix with proper loudness and true-peak analysis, using a two-pass workflow or equivalent when practical. Start around **−15 LUFS integrated, within about ±1 LU**, and **≤−1 dBTP true peak**. Tune to the reference and preserve clarity. Do not peak-normalize alone or boost until clipping occurs.

Check the result on ordinary speakers/headphones and a phone. Report actual before/after integrated loudness, true peak and boundary-gap measurements. Do not report voice expressiveness, exact music parity or word synchronization as verified without listening and alignment evidence.

## 13. Integrate planning without surrendering render control

Let the LLM propose semantic beats, entity roles, emphasis and suitable templates. Keep geometry constraints, frame math, asset validation, transition legality and final rendering deterministic in code.

Repair or reject plans that contain unresolved entities, invalid word references, unsupported events, excessive caption text, missing assets, repeated meaningless layouts, or impossible timing. Limit repair retries and surface a useful error rather than looping indefinitely.

Do not select arbitrary effects from the entire catalog for this preset. Use a narrow allowlist and a deliberate mapping from narrative purpose to action. The renderer must be able to produce a strong deterministic fixture without any LLM call.

Keep visual beats aligned to the final audio. If narration changes after a visual plan is drafted, recompute timing and revalidate the plan. Cache invalidation must include script, audio/alignment, preset/schema, asset preparations and font versions.

## 14. UI and run observability

Expose a simple visual preset selection, concise preview and a few meaningful choices:

- Output duration target.
- Voice/provider through existing controls.
- Assets through existing stock/AI/local routes.
- Editorial text versus optional complete subtitles.
- Music enabled/disabled where supported.

Keep advanced motion/layout controls out of the normal user flow. The default must produce a coherent result without asking the user to choose dozens of effects.

Show progress for script, narration/alignment, asset preparation, editorial planning and rendering through the existing progress mechanism. Make the preset effective in CLI, web UI and any supported application entry point; avoid a control that changes only frontend state.

Save a diagnostic manifest with the resolved preset/schema, script, entities, asset roles/fallbacks, actual word timing, frame plan, transition ranges, audio offsets, final duration and measured audio statistics. Provide a clear error for unsupported renderer/configuration combinations.

## 15. Implementation sequence

Proceed in this order, validating each milestone:

1. Diagnose the existing path and capture a baseline render/manifest.
2. Define the validated timeline contract and compatibility adapter.
3. Build a deterministic 10–15 second fixture demonstrating progressive words, cutouts/shadows, two-entity focus shift and a context/location change.
4. Add separate short fixtures for year counter, map separation and perspective object action; they need not all appear in one news story.
5. Review rendered frames, typography, timing and transitions; refine them against reference excerpts.
6. Implement narration alignment/global offsets and correct audio gaps/mixing.
7. Integrate semantic planning and entity/asset acquisition.
8. Connect the preset to the actual UI/CLI paths.
9. Generate a complete representative video from the baseline topic or its supported input, then inspect and iterate.
10. Verify unrelated existing flows and finish documentation.

Do not implement all the components and postpone the first render until the end. Do not use reference-video playback, spliced reference footage, or reference frames as the complete scene background to fake a successful reconstruction. The output must be produced by the new layer/event renderer.

If original reference assets or font files are unavailable, use suitable supplied/local/approved alternatives, state the resulting limits, and still demonstrate the reusable production system. Pixel-identical reconstruction requires source assets and exact timing/voice/font information; do not promise it from an MP4 alone.

## 16. Verification and acceptance criteria

Use meaningful tests and render inspection appropriate to this change, not tests that simply mirror every implementation detail.

### Timing and rendering correctness

- Word alignment refers to the actual final narration and remains monotonic after clips are assembled.
- Text is visibly revealed across the sentence rather than displayed complete at scene start.
- Check representative spoken words and emphasis events against waveform/alignment and playback; target about 100 ms or better accuracy where alignment permits, and report exceptions.
- Phrase geometry does not jitter or rewrap on each word reveal.
- Global duration covers narration and deliberate ending holds; visual overlap cannot truncate speech.
- No unintended background-only transition gap, missing asset, caption collision, clipped face or detached label/shadow.
- Seeking and repeated rendering produce identical planned frames.
- Opening and closing frames are deliberate and readable.

### Style and editorial quality

- Cool gray stage, reference-like typography hierarchy, suitable masks and shadows are visible.
- The full demonstration uses at least three suitable semantic layouts and meaningful internal events, unless a documented shorter script reasonably needs fewer.
- The dominant visual changes when the dominant idea changes. Reuse of an entity has a purpose.
- Long complete-headline holds over an unchanged globe do not constitute the new preset.
- Each required primitive has a rendered demonstration, including focus shift, year count, map separation and an object action.
- New subjects follow the same visual grammar without hardcoded historical/newsy names in renderer logic.
- Asset labels are truthful about identity or symbolic role; factual maps/text are not fabricated.

### Audio

- Final integrated loudness is near the configured target; true peak respects the ceiling.
- Repeated accidental ~1.2-second inter-section pauses are eliminated or explicitly justified by editorial intent.
- Speech is intelligible, complete and not clipped at trims/transitions.
- Any music/effects remain below speech and are inspected by listening.

### Integration and regression

- Preset selection changes the actual generated timeline/render, not just UI text.
- Existing nonselected presets and old manifest inputs still work.
- Existing stock and AI-image paths remain available.
- Missing timestamps/assets, provider failures, long names and varying narration durations have defined outcomes.
- An unsupported fallback renderer never claims to have produced reference parity.
- Run the project's relevant existing checks; add targeted tests for global offset remapping, interval/transition math, schema references and compatibility where needed.

Compare **structure/style/timing** across different stories. Use pixel comparison only for a deterministic same-assets fixture; a visual similarity score between unrelated news and diamond scenes does not establish parity.

## 17. Required final deliverables

Return:

1. A concise diagnosis grounded in the source code, identifying what caused the visible/audio issues.
2. Implemented files and how the new preset is wired end to end.
3. Exact run/preview commands for the current project.
4. A complete demonstration MP4 and short primitive fixtures.
5. A timestamped contact sheet and before/after observations, including representative transition frames.
6. A manifest/timeline showing actual entity assets, text timing and events.
7. Actual before/after loudness, true peak, duration and boundary-gap measurements.
8. Checks/tests performed and any remaining concrete limits, including font/asset/voice differences.

Do not conclude with “implemented successfully” based only on compilation. Conclude after inspecting the rendered output, verifying audio timing/mix, and explaining the remaining differences from the reference.

Begin by inspecting the actual repository and the supplied videos, then implement the deterministic editorial fixture.

---
