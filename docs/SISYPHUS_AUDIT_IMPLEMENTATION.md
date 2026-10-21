# Sisyphus event-quality upgrade

**Updated delivery preference:** see [IMAGE_DELIVERY_RECOVERY.md](IMAGE_DELIVERY_RECOVERY.md). The user subsequently requested preserving paid images and delivering videos with warnings. Strict critical blocking described below is now opt-in; local `.env` uses `IMAGE_FAILURE_POLICY=deliver_with_warnings`.

The master audit was read from `ProjectHER_Sisyphus_Analysis_Package/ProjectHER_Sisyphus_Full_Audit_and_Codex_Master_Prompt.md` before the session interruption. The package disappeared from the workspace during the interruption. Neither source MP4 was available in that package when first inspected. The written audit defines the visual intent; this implementation does not claim a forensic mapping from the supplied MP4 pixels to a historical generation ID.

## Verified code paths and changes

- Input/research/script remain in `agent/editorial/pipeline.py`, `agent/news_research.py`, and the existing script writer. Approved narration stays frozen; TTS starts independently and `event_storyboard.bind_audio` binds visual sections to measured word IDs/times.
- `agent/editorial/event_storyboard.py` already extracts actors, verbs, objects, before/after state, exact narration spans and separate action keyframes. It already checks repeated images and includes multimodal event review. The existing smart-image planner reserves unique assets before requests. These were extended rather than replaced.
- `agent/editorial/assets.py` had a candidate/character/typography fallback hierarchy controlled by `PROJECTHER_ALLOW_CRITICAL_EVENT_FALLBACK`. A failed P0 image could enter that hierarchy, including an unverified candidate. P0 rejection now blocks regardless of that legacy flag. Failed art is retained for review and never accepted as a completed critical scene. Asset-overrun defaults now require explicit configuration.
- `agent/editorial/images.py` uses the existing persisted job ledger, atomic budget reservations and no Seedream create-request retries. Requests now include prompt and input checksum provenance; Seedream size and prompt enhancement are configurable. The adapter validates the 10-reference maximum and emits a single output, without a separate `negative_prompt` field.
- `agent/editorial/pipeline.py` previously warned about failed event QA and could still return success. It now emits diagnostic reports and stops on failed critical preflight or encoded-frame checks when `RENDER_BLOCK_ON_CRITICAL_VISUAL_FAILURE=true` (default).
- `agent/editorial/quality_artifacts.py` adds typed `VisualScenePlan` contracts. Action/interaction/consequence plans cannot select `ACTOR_ONLY`. Generated assets carry an independent `assetRole`; explicit actor-only assets fail event QA even if text-based review metadata claims success. Legacy untagged assets retain backward compatibility and still require existing visual review.
- `agent/editorial/scene_plan.py` previously required all props to touch and prohibited floor planes. This contradicted rollback separation and readable inclines. Prompts now allow separated released props, enormous essential objects and compact supporting terrain; no requirement to preserve an unrequested carried accessory.
- Generated Remotion schema/types include the new asset-role metadata. Existing 1080×1920 rendering, layout grammar, watermark and signature closing remain intact.

The historical wheel portrait cannot be conclusively attributed to one old request without its matching generation log and original MP4. The verified fallback and completion paths explain how misleading output *could* survive; that is distinct from proving which request produced the audited wheel.

## Configuration and compatibility

Existing `CHARACTER_IMAGE_MODEL`, `OBJECT_IMAGE_MODEL`, `ACTION_IMAGE_MODEL` settings remain valid. New `IMAGE_CHARACTER_MODEL`, `IMAGE_PROP_MODEL`, `IMAGE_ACTION_MODEL` take precedence. Existing model allowlist remains FLUX Schnell plus Seedream 4; there is no automatic premium selection. `ENABLE_EXPENSIVE_IMAGE_MODELS=false` documents the baseline, but enabling it does not expand that allowlist.

`IMAGE_ACTION_SIZE=2K`, `IMAGE_ENHANCE_PROMPT=true`, `IMAGE_ACTION_MAX_ATTEMPTS=1`, `IMAGE_VISION_QA_MODEL`, `IMAGE_ESTIMATED_BUDGET_USD`, `RENDER_BLOCK_ON_CRITICAL_VISUAL_FAILURE=true`, and `VISUAL_QA_CONTACT_SHEET_FPS=1` are supported. An attempt count other than one is rejected. The optional vision override uses the existing Gemini-compatible reviewer; without an override the existing configured reviewer remains active. Semantic uncertainty is not converted into a passing result.

Image-budget aliases do not override the separate total-video budget, maximum scene count or service reservation. Defaults now allow 24 generated images, 16 Seedream actions, $0.60 in images and $0.80 including the configured non-image reservation. Explicit lower environment limits remain authoritative; a budget conflict stops before calls rather than demoting essential actions. Existing low-cost modes can explicitly configure smaller budgets.

Successful unchanged assets reuse the existing checksum/model/prompt/reference-sensitive cache. Size and enhancement changes invalidate the cache. The persisted job ledger prevents another Seedream submission for the same asset on resume. To rerender cached assets, use the emitted `editorial_manifest.json` with `agent.editorial.render.render`; it makes no image calls. A changed creative brief is a separate job, not an implicit retry.

## Artifacts and interpretation

Jobs emit `storyboard.json`, `character_bible.json`, `asset_manifest.json`, `generation_cost_report.json`, `quality_report.json`, the detailed `event_edl.json`, and `render_contact_sheet.jpg` plus individual sampled JPEGs after export. Failure paths retain available diagnostic reports. A failed preflight intentionally has no MP4/contact sheet because rendering is blocked.

The cost report records conservative request reservations and distinguishes accepted prediction count; actual billed charges remain unknown. Vision, TTS, segmentation, render and storage costs are excluded. `text_only_action_seconds` conservatively reports uncovered critical timeline intervals, not a pixel-based semantic visibility measurement. Missing objects are marked unverified, not asserted absent from pixels. Anatomical defects and contact remain probabilistic vision judgments, with sample frames for human inspection. The contact sheet alone cannot establish full-frame, every-moment correctness.

## Reproduce

Create the complete example plan and prompts, with no remote calls:

```sh
venv/bin/python scripts/evaluate_sisyphus.py --output output/sisyphus_acceptance
```

Render the full offline integration fixture, with mocked images, voice and vision but real Remotion/FFmpeg:

```sh
venv/bin/python scripts/evaluate_sisyphus.py --output output/sisyphus_acceptance_render --render-offline
```

Use a fresh directory for this fixture. It plans 12 action images plus six canonical references, estimated at $0.378 at configured default prices. Synthetic shapes are deliberately NOT evidence that the nine required mythological actions look correct. Reports explicitly mark offline fixture scope. Chromium must be allowed to launch locally.

For live evaluation, paste emitted `narration.txt` into the existing editorial story-input flow, configure `GENERATED_IMAGE_MAX=24`, `MAX_SEEDREAM_ACTION_IMAGES=16`, `MAX_IMAGE_BUDGET_USD=0.60`, `MAX_TOTAL_VIDEO_BUDGET_USD=0.80`, `TYPOGRAPHY_BEAT_TARGET=0`, keep critical blocking on, and use configured provider credentials. Review the emitted storyboard before any generation. Inspect every chaining, freeing, dragging, pleading, lounging, sentencing, push, rollback and repetition frame. No live visual acceptance is claimed by the offline run.

## Remaining limits

No pre-authored physically correct deterministic multi-cutout fallback poses were supplied; failed critical actions block rather than synthesizing misleading geometry. Full live model QA, before/after source-video comparison, listening evaluation and independent boulder-layer motion remain unverified. Existing layer motion supports multi-object layouts, but splitting arbitrary generated scenes into physically independent moving limbs/rocks is not solved by this change. The planner's LLM completeness audit now rejects after bounded planning repairs instead of accepting a fatal omission as advisory. Other hard checks enforce structural spans, asset review, role compatibility, duplication and timeline coverage.

## Validation evidence (21 October 2026)

- Targeted image/event/input regression run: 96 tests passed; final focused run including fatal-completeness rejection: 59 passed.
- Full suite in `venv`: 408 passed and two UI imports failed because that environment lacks Gradio. Both failing tests passed separately under `.venv`, which contains Gradio. No dependency files were changed to hide the environment difference.
- `remotion/node_modules/.bin/tsc --noEmit`: passed.
- `git diff --check`: passed.
- `output/sisyphus_audit_offline_v2/editorial.mp4`: real H.264/AAC export, 1080×1920, 30 fps, 41.109 seconds. 41 one-second samples and a labeled contact sheet were produced. Mock visual checks and real timeline coverage reported 12/12 critical beats covered. This result applies only to the synthetic fixture; it is not live Sisyphus visual acceptance.
- Chromium initially could not launch inside the restricted sandbox. The same cached manifest rendered successfully with the approved local browser execution; no new image predictions were submitted. The initial attempt also exposed the browser schema needing regeneration for the new asset-role field, which was fixed.

## Budget-default correction

Job `f691275f9003` exposed stale fallback defaults in `ImagePolicy.load`: $0.12 image budget, $0.20 total reservation budget, 10 images and three actions. They conflicted with the complete event coverage required by this audit. Defaults, `.env.example`, local `.env`, and the provider-side default now agree on the event-capable profile above. Its archived plan has 10 action images and five anchors: $0.315 in images, $0.395 including the $0.08 non-image allowance. That exact plan passes the revised capacity/budget check without API calls. Explicit smaller caps still block. Restart the app to reload environment configuration before submitting a new job. This is an estimated reservation ceiling, not a verified total service bill.
