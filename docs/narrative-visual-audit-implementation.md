# ProjectHER narrative visual audit — implementation and evidence

Status: integrated locally; visual acceptance and deployment gates remain open. Earlier candidate reports showing 100% coverage were contradicted by frame inspection (ribbon replaced by straps, incorrect biting contact). They are not acceptance evidence.

## Discovery and architecture

Reviewed both audit storyboards, the original Fenrir recording, the reference video, and the saved Sisyphus job. `agent/editorial/pipeline.py` routes input/research/script through visual planning, narration, assets, alignment, direction, timeline, Remotion and FFmpeg delivery. Portfolio orchestration persists the job and uploads the result. Existing article, topic, news, voice and output paths remain integrated.

The visual failure comes from conflating a recurring entity with its current action/state. Reusing a wolf and a standing person cannot show hand contact, tightening restraints or a bite. Existing deterministic action support also missed multiple events in a sentence and could select a different character as the actor. Whole-sentence image/review context leaked a later bite into an earlier binding event. Tight reference crops caused clipped feet; mixed prop references encouraged biting ribbon instead of the hand.

## Integrated changes

- `agent/editorial/narrative.py`: versioned `narrative-v2` identity packs and beats; exact script SHA, character/word spans, actor/target/reference IDs, goal, result and preceding state, priority, motion, decision and degradation. Actual aligned words bind timestamps/confidence/provenance. Asset review coverage is explicitly separate from final-video acceptance.
- `visuals.py` and `action_beats.py`: structured semantic extraction in the existing planning call, grounded anchors, conservative general action guards and bounded fallback. Distinct events cannot be swallowed by a broad semantic span. Mental/context verbs do not automatically request physical gestures. Narration remains unchanged. Story names occur in fixtures, not runtime special cases.
- `assets.py`: canonical identity masters precede dependent action assets; independent context acquisition overlaps ready actions. Bounded workers, padded references, multi-character conditioning, current-event-only generation/review, persistent restraint state, strict action/contact/continuity gates. Failed action assets are reported as degraded; portraits do not count as successful action coverage. Existing multi-cutout layouts remain.
- `images.py`: explicit image tiers, bounded budgets/deadlines, account admission metrics, retry rejected creates only; poll the accepted ID after transient polling errors. Ambiguous outcomes do not trigger another paid prediction. Cancellation attempts cancel the accepted prediction. HTTP 401/402/403 closes further creates for the job; a create-side server error has an ambiguous outcome and is never automatically resubmitted.
- The action adapter uses Seedream 4 with separate original master references, 2K output, `max_images=1` and `sequential_image_generation=disabled`; no automatic image regeneration or model switching.
- `utils/provider_admission.py`: credential-hashed, file-locked account pacing across processes on one host, shared by narration and editorial images. Epoch timestamps coordinate processes (this Mac’s Python 3.9 monotonic origin is process-local; two independent interpreters measured 0.0069s and 0.0046s). Waiters commit no future reservations, so cancellation cannot leave a phantom queue. This does not coordinate separate Cloud Run instances.
- `utils/job_trace.py`: success/failure spans, monotonic elapsed and UTC, parent IDs, runtime CPU/memory, durable structured logs; queue, provider admission, generation, matte, review, render and upload are distinguishable. Overlapping durations are never summed as job time. Logs omit narration, credentials and image payloads.
- Narration starts alongside semantic planning under the parallel flag. The existing renderer retains audio/output QA and branding. An opt-in direct BT.709 path removes a second encode only when metadata qualifies; it remains off pending color review.
- Matte repair remains off. Production does not fill holes or relax clipping/alpha gates to force acceptance. The recorded Fenrir fixture has a separately audited opaque-ribbon recovery; that operation is not a generic production repair.

## Flags, caches and compatibility

| Environment variable | Default | Purpose |
| --- | --- | --- |
| `HER_NARRATIVE_VISUAL_PLANNER_V2` | `1` | Structured planning with conservative fallback |
| `HER_ACTION_ASSETS_V2` | `1` | Reference-conditioned event assets |
| `HER_PARALLEL_ASSET_PIPELINE_V2` | `1` | Narration/planning and bounded asset overlap |
| `HER_EDITORIAL_ACTION_WORKERS` | `2` | Action concurrency, capped at two |
| `HER_EDITORIAL_IMAGE_MIN_INTERVAL` | `1` | Effective pacing also respects narration account interval |
| `HER_EDITORIAL_IMAGE_TIMEOUT` | `180` | Prediction deadline in seconds |
| `ACTION_IMAGE_MODEL` | `bytedance/seedream-4` | Reference-guided action tier; no regeneration retries |
| `HER_EDITORIAL_DIRECT_BT709` | `0` | Experimental single video encode |
| `HER_CUTOUT_MATTE_REPAIR` | `0` | Optional matte consolidation |

Disable the three v2 flags for rollback. Public API additions are metadata; existing manifests without a narrative plan remain readable. Action identity/cache keys include prompt, model and reference digest; processing and review versions force revalidation, and raw checksums detect changes. Custom segmentation adapters do not share stale cached mattes. Caches are local disk, not a durable cross-instance service. No credentials enter cache keys in plaintext. Deployment/schema migration is not required for existing jobs.

## Measured performance

| Measurement | Result | Limits |
| --- | --- | --- |
| Six retained deployed jobs, 45–90s outputs | wall p50 **828.54s**, p95 **1107.52s** | Observational, configurations/cache states unknown |
| Paired local renderer experiment, two runs per mode | legacy p50 **59.0715s**, direct **52.6800s**; p95 **59.338s** vs **52.773s** | About **10.8% render-only** reduction, not full generation |
| Initial Sisyphus baseline renderer | Remotion **46.484s**, FFmpeg **6.724s**, audio QA **2.241s**, total **56.125s** | Local recorded-narration run |
| Initial direct experiment | FFmpeg **0.778s**; SSIM **0.995093** against baseline | Small color difference; direct mode remains off |
| Strict Fenrir candidate | **426.41s** saved-narration visual run | Failed visual gate; excludes research/script/TTS/upload |
| Strict Sisyphus candidate | **716.91s** saved-narration visual run | Failed visual gate; included over-extracted events corrected afterward |

Evidence: `output/narrative_audit/deployed_job_timings.json`, `render_benchmark/{runs,summary}.json`, and each candidate's `job_trace.json`. Current traces distinguish provider admission from actual request wait. CPU matte work is serialized where required by the underlying session. No claim of a 25–40% end-to-end improvement is supported. No ten-job controlled deployed comparison has been run. Per-call billing is not available; prediction/request/retry counts are recorded instead.

Cloud Run inspection found 2 CPU, 4Gi memory, container concurrency 20, timeout 3600s. That configuration can oversubscribe CPU-heavy render/matte jobs; changing it requires a measured deployment canary. Historical logs lacked the new stage spans, so retained wall timestamps alone cannot assign the production delay to a particular stage.

## Video evidence and remaining gates

Original Fenrir: `/Users/klinten/Downloads/project-her-f53324a2.mp4` (1080x1920, 30fps). Original Sisyphus and its manifest/audio/assets: `output/editorial_07200cfc88174aadb1080c31345a3b97/`. Baseline rerender: `output/narrative_audit/before_sisyphus/editorial.mp4`.

Strict complete candidates: `output/narrative_audit/fenrir_final/editorial.mp4` and `sisyphus_final/editorial.mp4`. Their CLI exits unsuccessfully when coverage fails, even though an inspectable video exists. Fenrir passed 1/5 reviewed action beats; Sisyphus passed 2/7 in that older, over-extracted plan. These are diagnostic failures, not release videos. Subsequent `*_action_editor` runs evaluate the explicit alternative image adapter and corrected prompts; inspect their manifests rather than assuming completion from directory names.

| Scenario / event | Before | Required after behavior |
| --- | --- | --- |
| Fenrir: hand inside jaws | Standing cutouts apart | Connected interaction, established Tyr and wolf |
| Fenrir: ribbon tightens | Three floating portraits/prop | Same white silk visibly wraps and attaches to wolf |
| Fenrir: bite | Same standing figures | Closed-jaw contact with Tyr's hand, distinct pose, no gore |
| Sisyphus: uphill | Repeated king portrait | Same clothing/person strains against boulder, uphill motion |
| Sisyphus: downhill return | Repeated portrait | Separate released boulder, visible downhill direction |

Acceptance still requires captions-off final-video review of every climax, ≥90% manually verified action coverage, no continuity/material regressions, legible captions and multi-asset composition, and the existing watermark/outro. Automated asset review is necessary but insufficient.

Automated validation: **303 tests passed** (`python -m unittest discover -s tests`); TypeScript validation passed (`npx tsc --noEmit --project remotion/tsconfig.json`). Tests cover actors/targets, multiple events, unchanged narration, state continuity, generic new verbs, span grounding, deadline/retry/cancellation, no portrait-as-action success, reference conditioning, independent context concurrency, trace wall unions, and existing workflows. Beat-level decisions, reviews and stage measurements are exported in `output/narrative_audit/strict_candidate_report.json` by `scripts/report_narrative_regression.py`.

Rollout remains pending: no changed-code deployment, no fresh end-to-end hosted submission, no current backend klinteng.com embed test. Read-only deployed client review found submission guarding, retained idempotency keys and recovery; that is not a deployed regression test. Complete visual gates, then canary with matched inputs/provider settings and cold/warm cache labels, record stage and job p50/p95, and verify one submission/one durable job/eventually playable result before broader rollout.


## Latest controlled action-model candidate

`output/narrative_audit/fenrir_action_editor/editorial.mp4` completed at 1080x1920/30fps, 63.7667s, limited BT.709. Its recorded-narration visual run took **186.804s**, including **62.053s** render/audio QA (Remotion49.765s, FFmpeg8.839s, audio2.469s). Audio measured **−15.01 LUFS**, **−1.49 dBTP**; output-duration and black-frame checks passed. This is not a matched end-to-end speed comparison: it reuses narration and identities and changes the action model.

The latest Fenrir candidate passed **3/5 asset-reviewed action beats (60%)**, versus **1/5 (20%)** in the earlier strict Flux candidate. Manual inspection confirms readable hand-in-jaws contact and attached white ribbon, and the storyboard confirms watermark and branded ending. This is below the ≥90% target. The bite and release requests failed with Replicate **HTTP 402** (credits/model billing access), so those scenes contain explicitly degraded subject labels. They must not be released or counted as quality passes. No new predictions are justified until account credits/access are restored; do not automatically substitute an unreviewed model.

Comparison screenshot: `output/narrative_audit/fenrir_action_editor/before_after_storyboard.jpg`. Beat-by-beat reviews and provider metrics: `fenrir_action_editor/report.json`. Sisyphus action-model requests also received HTTP 402; its previous strict rendered comparisons remain available, but no successful new uphill/downhill comparison is established. The diagnostic export finished at 1080x1920/30fps, BT.709, 60.586s; all three new action requests were degraded by HTTP 402, so asset-reviewed action coverage is 0/3. This is not an acceptance video. Its before/after storyboard is beside the export. Combined results are in `output/narrative_audit/latest_candidate_report.json`.

The cross-process epoch-clock correction and billing circuit breaker were implemented after these comparison workers started. Do not describe their measured timings as the final-code performance. Final tests cover both fixes. The next funded run can reuse `--visual-plan .../visual_plan.json`, the source narration, and successfully cached action assets; no renewed payload approval is required for the already approved Replicate/Gemini transfers.
