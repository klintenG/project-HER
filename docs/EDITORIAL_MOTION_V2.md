# ProjectHER editorial cutout motion, Phase 2

This extends the existing event planner and Remotion renderer. It keeps the clean
neutral canvas, Poppins typography, isolated subjects, sparse compositions,
word-aligned copy, projected shadows, and ProjectHER watermark/closing controller
seen in `old-generated-video.mp4`. It adds action-aware shot direction; the
rectangular Thor review is a content source and negative layout reference.

## Architecture and contracts

Existing path: input → approved script (`news_script`) → narration synthesis and
alignment (`editorial/audio`) → immutable event spans (`event_storyboard`) →
beat-aware prompts and continuity references (`scene_plan`, `images`, `assets`) →
alpha preparation (`cutout_processor`, `assets.prepare`) → entity lifetimes
(`director`) → phrase choreography (`reference`) → **shot direction
(`shot_direction`)** → staged assets/schema → Remotion → existing FFmpeg/audio
and branding delivery checks.

The existing nine beat types, visual modes, five asset categories, six Phase 1
layout templates, costume/prop state, `must_show`, and narration word IDs remain
the semantic source. Phase 2 never swaps an action image for an introduction
portrait. An explicit action also overrides an erroneous CHARACTER_INTRO hint;
action-based closing images preserve the action instead of requesting a neutral
hero pose. The text planner defaults to `GEMINI_MODEL`; its image model remains
independently configurable using `HER_EDITORIAL_EVENT_IMAGE_MODEL`.

`shotDirection` diagnostics and `shot_plan.json` version `editorial-motion-v2.1`
contain each phrase's original beat/section IDs, absolute half-open frame interval,
verbatim narration, semantic type and visual intent; object tracks retain asset
IDs, original depicted action and subjects, alpha/role, bounds and typed
`LayerMotion`; text tracks retain aligned word IDs, bounds and animation ID.
Frame rounding uses the original 30 fps export clock. Subtitles retain their
existing separate setting. This does not introduce a parallel timeline schema.

Composition families: hero introduction, typography-led hook, dual-subject
tension, action focus, multi-layer event, object/evidence focus, reaction punch,
conflict/chase, reveal/twist, and closing resolve. Selection is deterministic,
uses semantic type and neighboring sections, and limits identical family streaks.
One combined transparent action tableau is valid: it preserves anatomical
contact. Truly disconnected pieces can enter with bounded stagger/parallax.

The director reserves normalized brand/UI-safe areas and separates primary
subject boxes from editorial text. Short, measured narration chunks retain exact
word reveals; their motion uses group slide or line reveal rather than moving
every word independently. Entrances, directional drift, restrained focus pushes,
scale and exits use typed bounded frame values. Existing transform events are
removed only when this pass owns the corresponding scene layer, avoiding doubled
entrances/fades/scales. Action silhouettes are visible immediately at their
semantic onset; entrances settle rather than fading the action away.

Generated rectangular story assets raise an actionable error rather than silently
becoming scene cards. Verified photos/maps/documents may retain their frame;
provenance and factual status remain attached. Photography receives no fake
cutout floor shadow. Alpha preparation and dimensions happen before rendering.
Element sidecars bind source and part checksums: corrupt/missing/stale parts fall
back to the original combined action PNG, with a log warning. Python and browser
contracts validate element asset references, fitted-image geometry and focus
intervals. No bitmap segmentation occurs per frame.

## Configuration

Only the reference-v2 route with Phase 1 `scene_plan` metadata uses this pass.
Existing legacy and alternate News paths retain their routing. Phase 1 image
providers, models, credentials, retries and budgets remain separately configurable.
Motion adds **no provider calls**.

All keys below have prefix `HER_EDITORIAL_MOTION_V2_`:

| Suffix | Default | Allowed values / effect |
|---|---|---|
| ENABLED | true | false retains the previous Phase 1/reference render route |
| INTENSITY | standard | restrained, standard, energetic |
| LAYOUT_VARIETY | true | semantic family alternatives and offset staging |
| LAYERED_PARALLAX | true | separately animate valid extracted alpha elements |
| KINETIC_TEXT | true | group/line motion; false retains existing word slide |
| ALLOW_DOCUMENTARY_FRAMES | true | permits factual/context photographs and explicit photo/map/document roles |
| MAX_IDENTICAL_LAYOUT_STREAK | 2 | 1–5 sections; alternative must preserve meaning |
| LONG_HOLD_WARNING_MS | 4500 | 1000–30000; diagnostic, never alters narration |
| ENTRY_MS | 280 | 100–450; shortened to fit short asset lifetimes |
| EXIT_MS | 160 | 0–300; shortened to fit short asset lifetimes |
| STAGGER_MS | 130 | 0–250; bounded by available layer lifetime |

Invalid settings raise Pydantic errors naming the field. For comparison, set
`HER_EDITORIAL_MOTION_V2_ENABLED=false`; do not disable the action/event planner.
The unchanged earlier `HER_EDITORIAL_STYLE_VERSION=legacy` is a broader rollback.
Existing serialized plans without the additive motion fields retain renderer
fallback defaults. No export aspect ratio, narration rate, audio mix, music,
subtitle preference, font files, or branding-controller timing was changed.

## Evidence and reproduction

Review artifacts: [Sisyphus video](../output/editorial_motion_review/sisyphus-proof/editorial.mp4),
[Thor video](../output/editorial_motion_review/thor/editorial.mp4),
[documentary video](../output/editorial_motion_review/history/editorial.mp4).
Each output has `editorial_manifest.json`, `shot_plan.json`, `metrics.json`,
encoded visual-quality/activity diagnostics, and `review/index.html` with
start/middle/end screenshots, source asset IDs, exact intervals and text tracks.
The root review directory preserves reference contact sheets and 5 Hz motion
strips; these are comparative evidence, not a claim of pixel-exact parity.

Sisyphus uses five selected intervals of existing measured narration and four
new transparent built-in imagegen illustrations, plus the original intro cutout.
`narration-provenance.json` records source sample ranges and retained word IDs;
all word timings shift by their exact waveform splice offset, never estimated.
The prompt set and generated source assets are stored in `validation-assets`.
Thor retains the earlier authored event plan and recorded narration, and uses
background removal and alpha trimming on its prior event artwork. A few group
masks required manually reviewed segmenter candidates after conservative
connected-component QA rejected them. These are explicitly named `candidate`
assets; this review does not relax production mask thresholds. The history
sample retains the prior NASA-source imagery, narration, attribution and factual
flags. These are renderer/semantic validation runs, not fresh factual research.

```sh
.venv/bin/python -m unittest tests.test_shot_direction tests.test_scene_plan \
  tests.test_event_storyboard tests.test_editorial tests.test_reference_parity \
  tests.test_sentence_storyboard
remotion/node_modules/.bin/tsc --noEmit -p remotion/tsconfig.json
node remotion/check-cutout-motion.cjs
.venv/bin/python scripts/build_sisyphus_motion_review.py \
  --assets output/editorial_motion_review/validation-assets
.venv/bin/python scripts/rebuild_editorial_motion_review.py \
  --source output/visual_correlation/thor_curated \
  --output output/editorial_motion_review/thor \
  --alpha-dir output/editorial_motion_review/thor/assets
.venv/bin/python scripts/rebuild_editorial_motion_review.py \
  --source output/visual_correlation/history \
  --output output/editorial_motion_review/history
```

A full live-provider attempt hit Edge TTS handshake errors and Replicate rate
limits; it was stopped after these bounded failures. The proof videos use real
recorded speech and actual rendering, not mocked video or tone pulses. The fresh
Sisyphus artwork used four built-in imagegen calls. Existing paid-provider attempts
may incur their normal charges; exact billing was not available. This pass adds
no runtime provider dependency or mandatory additional motion-generation spend.

## Reference audit and editorial review

| Reference interval | Observed behavior | Preserved / upgraded behavior |
|---|---|---|
| Old, 3.8–5.0 s | Sisyphus enters offset right, name phrase left, words reveal on narration | hero introduction layout, same typeface, measured word timing |
| Old, about 9–20 s | Zeus/Thanatos and multiple foreground identities share a neutral canvas | event tableaus and independently valid supporting elements |
| Old, about 26–50 s | Plain Sisyphus is reused over escape/punishment/boulder narration | distinct return, divine judgment, and pushing-boulder images |
| Benchmark, 1.0–2.2 s | Diamond changes to jewel object, copy above/below, projected shadow | object/evidence family; linked image and phrase changes |
| Benchmark, about 28–40 s | Cutouts and an occasional documentary photo/date alternate | factual frame exception; no generated scene-card fallback |

| Narrated moment | Visual in proof | Composition |
|---|---|---|
| Sisyphus introduction | original Sisyphus cutout | hero introduction |
| Traps Death in chains | Sisyphus actively binds winged Thanatos | action focus |
| Return to living world | running Sisyphus and threshold | action focus |
| Gods impose punishment | Zeus judges kneeling Sisyphus | multi-layer event |
| Roll boulder uphill | hands and body visibly push the rock uphill | action focus |
| Thor's hammer missing | distressed Thor and empty rack | hero / premise staging |
| Thrym possesses hammer | giant grips Mjölnir | action/event staging |
| Freyja refuses | refusal gesture toward Thrym | conflict/reaction staging |
| Bridal plan and disguise | Loki, gown, then veiled Thor | event/action staging |
| Wedding feast | veiled Thor eating at a table with ox/barrels | event staging |
| Blessing / hammer retrieval | handoff, then veiled Thor gripping hammer | event then action focus |
| Reveal / fight | veil torn away, then combat with giants | reveal then conflict composition |

Both semantic relevance and motion must pass; a moving wrong portrait or static
rectangular generated scene fails. The review tools expose evidence and do not
automatically certify artistry, anatomy or historical truth. In particular:

- 2.5D transforms move a coherent illustration; they do not articulate limbs.
- The compact Sisyphus proof covers five required action/event cases; it does not
  include a separate downhill-boulder shot or a whole newly narrated story.
- Thor artwork retains some small floor/doorway accents from the prior art and
  a few imperfect edges; no room-sized rectangular generated backdrops remain.
- Source cue anchors are preserved: action/reveal art can enter at its spoken
  action word rather than at an introductory timing phrase. Review exact word
  frames, not just section midpoint screenshots.
- Documentary asset correctness follows the saved source review; this motion
  test does not reauthenticate each archive record.

## Files changed in this upgrade

| File/component | Purpose |
|---|---|
| `agent/editorial/shot_direction.py` | New deterministic semantic staging pass, validated environment settings and inspectable tracks |
| `agent/editorial/reference.py`, `director.py` | Invoke the pass after existing choreography and export the shot plan |
| `agent/editorial/scene_plan.py` | Guard explicit actions against intro misclassification; preserve actions in closing prompts |
| `agent/editorial/models.py`, Remotion `schema.json` / `types.ts` | Add backward-compatible typed phrase/motion fields; validate alpha-element and focus references |
| `agent/editorial/cutout_style.py` | Check source/part hashes before reusing extracted pieces; preserve combined art on stale masks |
| Remotion `cutoutMotion.ts`, `EditorialVideo.tsx`, `contract.ts` | Reusable frame-pure motion, grouped text motion, legacy numeric defaults and browser validation |
| `config.py`, `.env.example` | Correct text-planner default and document motion controls without altering image-provider overrides |
| `scripts/build_sisyphus_motion_review.py`, `rebuild_editorial_motion_review.py`, `review_editorial_motion.py` | Reproducible real renders, waveform/asset provenance and frame evidence |
| `tests/test_shot_direction.py`, `remotion/check-cutout-motion.cjs` | Semantic, timing, layout, alpha-cache, rollback, determinism and renderer checks |
| `tests/test_event_storyboard.py` | Give its orchestration fixture a real transparent foreground so it satisfies the new scene-card rejection gate |
| `scripts/scene_plan_demo.py` | Make its existing narration-provider choice selectable for validation retries |

Existing in-progress Phase 1 files were retained and extended. Their approved
narration, continuity planning, event-generation prompts, acquisition policies,
and provider interfaces were not replaced by a separate video app.

Validation: **68 Python tests passed**, TypeScript type checking passed, and
`node remotion/check-cutout-motion.cjs` passed legacy-default, visibility, stagger,
finite-transform, directional-motion and deterministic-seek checks. Encoded
output checks and per-video audio/activity measurements are saved beside the
videos. The review report distinguishes those measurements from human inspection
of the actual depicted actions.

Additive renderer fields (old manifests receive defaults):

| Contract | Fields |
|---|---|
| `Phrase` | `animation`: `word_slide` (default), `group_slide`, `line_reveal` |
| `LayerMotion` | `initialOpacity` 0–1 (default 0), `exitFrames` 0–30 (default 6), absolute `focusFrame` (default null), `focusScale` 1–1.08 (default 1), `entranceTravel` 0–240 canvas pixels (default 240) |
| Existing motion interval | `entranceFrames` now permits 1–40 frames to settle within very short spoken beats |

Final encoded QA:

| Proof | Duration | Loudness / true peak | Alpha assets | Semantic cue checks |
|---|---:|---|---:|---|
| Sisyphus | 23.7 s | −15.06 LUFS / −3.01 dBTP | 5 / 5 | all matched |
| Thor | 63.07 s | −15.04 LUFS / −1.80 dBTP | 16 / 16 | all matched |
| Apollo 11 | 28.47 s | −15.05 LUFS / −1.81 dBTP | 0 / 5, factual frames retained | all matched |

All three have no detected black interval, no estimated word timings, and no
long low-activity span in the existing encoded-media diagnostic. Motion scores
are not a substitute for review of silhouettes, text readability and action
meaning. [Combined review](../output/editorial_motion_review/index.html) includes
frame galleries, per-shot manifests and a synchronized Thor before/after video
(original scene-card version on the left, upgraded cutout presentation on the
right). The [machine QA report](../output/editorial_motion_review/acceptance-report.json)
retains every checked word/asset onset.
