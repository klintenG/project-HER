# Narration-aware image generation

The existing `reference_editorial` pipeline now finalizes a unique-asset plan after
semantic event planning and before requesting narration or images. URL, topic,
article and supplied-account inputs retain their existing research/script flow.
Other presets retain their rendering contracts; all image-generation paths now
use the same two-model allowlist without provider/model-switching fallbacks. Local-asset mode remains offline.

## Integration

- `agent/editorial/asset_planner.py`: deduplicated assets, canonical master dependencies,
  explicit typography and reused-cutout compositions, estimated timing, budget
  conflicts and model counts. Timings are rebound to final measured word boundaries.
- `agent/editorial/image_policy.py`: validated environment settings, model roles,
  configurable prices and image/video budget reservations, contextual A–H prompts
  and subject-specific constraints. No unsupported `negative_prompt` field.
- `utils/image_models.py`: Seedream adapter uses `image_input`, `size=2K`,
  `max_images=1`, and `sequential_image_generation=disabled`, following the
  [Replicate input schema](https://replicate.com/bytedance/seedream-4/api/schema).
- `agent/editorial/images.py`: immutable per-job model routing, atomic request-cost
  reservations and a durable prediction ledger. Seedream never retries POST,
  including rate limits. Accepted predictions retain the existing GET polling path.
- `agent/editorial/assets.py`: keeps the existing extraction, review and caching
  pipeline; original canonical master images, cutouts and action links persist in
  the job's application-managed assets folder. Smart generation disables legacy
  alternate-model repairs. Unusable action images stop with a review requirement.
- `agent/editorial/event_storyboard.py`: conceptual typography and nonphysical
  dialogue reuse are explicit semantic choices. Essential physical events stay on
  the action tier. Dialogue must explicitly declare `physical_action=false`.
- `agent/editorial/typography.py`, `director.py`, and
  `remotion/src/editorial/EditorialVideo.tsx`: retain measured phrase reveals,
  typography-safe placement, restrained perspective/depth entry, existing backgrounds,
  transitions and branding. Transparent composition carriers satisfy the existing
  entity contract and are omitted from drawing; they are never generated images.
- `agent/editorial/pipeline.py` / `visuals.py`: connect the plan to acquisition and
  final audio timing without rewriting narration or replacing the renderer.
- `.env.example`: all requested settings plus `OTHER_SERVICES_RESERVED_USD` and
  preliminary `PLANNER_WORDS_PER_MINUTE`. The five canonical model roles are the only model selectors. Existing component
  names are read-only aliases; retired model environment keys cannot select models.

## Reports and recovery

Each job writes `asset_generation_plan.json`, then measured beat timings. Its
`assets/` folder contains `character_reference_registry.json`, original masters in
`canonical_references/`, `image_prediction_ledger.json`, acquisition diagnostics,
and `generation_cost_report.json`. Existing event EDL and render diagnostics remain.

A request is reserved before its HTTP POST. Unknown outcomes retain their cost
reservation. A restarted Seedream asset fails closed if already reserved: inspect
its stored prediction ID and recover that prediction rather than resubmitting.
Automated cross-process prediction recovery is not implemented. Do not delete the
ledger to bypass a failed/unknown action. Normal in-process polling downloads the
same prediction without another paid job.

Prices are configurable estimates. Actual charged cost is `null` unless available;
provider execution time is not presented as billing. The configured non-image
service allowance is reserved against the overall video budget. It must be sized
for the selected narration, LLM and existing review providers. It is not an
itemized actual-cost meter for those services and cannot guarantee the final bill.

Schnell retries reserve additional cost before submission and use the existing
review feedback to correct prompts. Seedream quality failures record review status
and stop; no automatic quality reruns or unrelated portrait substitutions occur.
This implementation conservatively stops rather than inventing a zero-cost physical
interaction when no verified composition is available.

## Reproducible validation

```sh
PYTHONPYCACHEPREFIX=/private/tmp/projecther-pycache .venv/bin/python -m unittest discover -s tests -q
cd remotion && npx tsc --noEmit
# From repository root, choose a NEW output folder:
PYTHONPYCACHEPREFIX=/private/tmp/projecther-pycache venv/bin/python scripts/validate_smart_images.py --output output/smart_images_review
```

The render command uses synthetic artwork/audio, mocked provider HTTP responses and
mocked visual judgments, then exercises the actual input, script, planning,
acquisition, alignment, typography, subtitle, branding, Remotion and FFmpeg paths.
It never calls live generation services. Chromium must be able to launch locally.
This validates orchestration and export, not live anatomical accuracy, canonical
likeness, natural speech timing or provider billing. Inspect a live story before
claiming production visual acceptance. The fixture report is not independent visual
proof even when its mocked judgments pass.

## Sample fourteen-beat plan

The machine-readable fixture is `tests/fixtures/smart_images/sisyphus_14_beat_plan.json`.
The sample uses the two original canonical masters in the interaction.

| Beat | Visual | New generation |
| --- | --- | --- |
| 1 | Sisyphus introduction | Schnell master, reused as cutout |
| 2 | Zeus introduction | Schnell master, reused as cutout |
| 3 | Boulder | Schnell |
| 4 | Mountain | Schnell |
| 5 | Crown as a metaphor for lost authority | Remotion typography |
| 6 | Empty throne | Schnell |
| 7 | Life in the city continues without its king | Remotion typography |
| 8 | Zeus seizes Sisyphus's wrist | Seedream, both original masters |
| 9 | Sisyphus physically pushes the boulder uphill | Seedream, original Sisyphus master |
| 10 | Boulder slips away and rolls downhill | Seedream, original Sisyphus master |
| 11 | Another beginning | Remotion typography |
| 12 | Repetition rather than passing years | Reused Sisyphus cutout and animated text |
| 13 | Hope and exhaustion | Remotion typography |
| 14 | Doing it all again | Reused Sisyphus cutout and animated text |

Five Schnell images cost an estimated $0.015; three Seedream images cost $0.090.
Total estimated image spend is **$0.105**, or **$0.185** with the default $0.08
non-image reservation. Two Schnell retries would bring those to $0.111 / $0.191.
The 62.5% Schnell share is below the 70% target and is explicitly reported as a
warning; unnecessary images are not generated solely to pad this ratio.
Shorter stories produce fewer images; low Schnell ratios produce a warning rather
than unnecessary padding. Essential actions exceeding configured caps produce a
reviewable conflict instead of a false low-cost substitution.

Final local validation: **404 Python tests passed**, TypeScript `--noEmit` passed,
and the full offline-provider workflow exported a **54.25-second, 1080×1920
H.264/AAC BT.709** video. Encoded loudness was **−15.01 LUFS**, true peak
**−12.21 dBTP**, with no detected black intervals. Fourteen beats used five
Schnell mock predictions, three Seedream mock predictions, four typography
compositions and two additional reused-character compositions. No paid requests were made. See `docs/SMART_IMAGE_VALIDATION.json`
for scope and limitations, and `output/smart_images_original_story_pacing/editorial.mp4`
for the synthetic integration video. Existing uncommitted work was preserved.

## Typography pacing

The semantic planner analyzes the complete narration before selecting lower-priority
conceptual commentary for text. Essential actions, introductions and important reveals
retain images. Story-seeded suggested positions add variety only as advisory tie-breakers;
they never override semantic suitability. `TYPOGRAPHY_BEAT_TARGET=4` is a maximum/target,
not a quota. Use fewer when four suitable, separated text beats are unavailable.

`TYPOGRAPHY_MIN_IMAGE_BEATS_BETWEEN=1` prohibits consecutive typography scenes. Plans
with three or more typography beats must distribute them across the story rather than
cluster them in one half or ending block. The semantic planner repairs violations within
its existing bounded planning attempts. Asset preflight independently enforces the same
rules before paid requests and records typography positions and pacing conflicts.
Narration order is never shuffled to meet these constraints. The original sample narration
is preserved exactly. Four conceptual beats at **5, 7, 11 and 13** use typography;
two closing commentary beats reuse character imagery, reducing new generation
from ten to eight images without weakening the three essential action scenes.

## Two-model enforcement

The allowlist contains only FLUX Schnell and Seedream 4. It applies to the general
styled-image, News and editorial paths. Custom adapter names cannot authorize an
unknown model. Alternative provider paths, extra image-model adapters, obsolete
model benchmark scripts and their pricing entries have been removed. Existing
text planning, speech, visual review and segmentation models are unaffected.
Use `IMAGE_MODEL_CONFIGURATION.md` and `.env.example` for current settings.

## Default capacity

The default event profile permits 24 generated images, 16 Seedream action images,
$0.60 in image reservations, and $0.80 including a $0.08 non-image service
reservation. Defaults match `.env.example` and the provider adapter. Existing
explicit lower environment caps remain enforced. `IMAGE_ESTIMATED_BUDGET_USD`
overrides `MAX_IMAGE_BUDGET_USD` when set. Restart the app after changing `.env`.
Plans persist effective `limits`; budget errors show planned and allowed amounts.
