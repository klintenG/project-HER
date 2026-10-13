# Reference editorial implementation and review

The existing `reference_editorial` path now defaults to `reference-v2`. Classic News, article/topic/story routing, existing image providers, saved outputs, and ordinary slideshow modes retain their routes. This is an improvement in editorial mechanics, not a claim of full reference parity.

## Evidence and architecture diagnosis

Reviewed the supplied master prompt, evidence inventory, reference/current comparison sheet and generated comparison windows. The exact 58.211-second reference is also present at `enhancements/reference-ai-video.mp4`. The saved Zheng Yi Sao baseline is `output/editorial_fcb1866532dd45e8b16a77974c76f820/`; its raw Remotion output has the audited 56.128-second container duration. The comparison uses its finished `editorial.mp4`, preserving that entire folder.

Confirmed causes:

- `director.compile_direction` limited primary text to dates and occasional exact-span headlines. `EditorialVideo` forced a bottom transcript whenever `narrationDriven` was enabled, even with editorial text selected.
- Both director and legacy planner appended synthetic/stock descriptors beneath subjects.
- Director geometry generally used a 440px single subject and repeated horizontal image rows. Assets changed only at entity cues; semantic action and phrase changes often left the composition unchanged.
- The script writer's duration budget and craft instructions favored long, stiff narration. Its shared behavior needed an editorial-specific refinement rather than a change to every input mode.

Assumptions disproved: the project already has a versioned validated timeline, persistent subjects, meaningful entity cues, exact provider/Whisper word timing, deterministic frame animation, local staging/checksums, optional music ducking, and encoded audio normalization. These were extended rather than replaced. Audio gaps are not evidence of a broken gain stage: music is disabled by default and the preserved sample contains speech pauses.

## Files and decisions

| File | Change |
|---|---|
| `agent/editorial/reference.py` | Compiles exact aligned words into pause/clause phrases, protects multiword entity names, selects semantic grammar, reserves text/image regions, reframes persistent assets, and writes an inspectable storyboard with timing provenance. |
| `agent/editorial/director.py` | Version selection and v2 compiler integration; canonical name-only labels. Existing user edits to headline planning remain intact. |
| `agent/editorial/models.py` | Explicit `editorialStyleVersion`, plus reference grammar names in the validated beat contract. Legacy remains the default when loading older manifests. |
| `agent/editorial/planner.py` | Removes renderer-added provenance labels from its separate fallback path. |
| `agent/editorial/pipeline.py` | Enables editorial-specific narration instructions through the current writer. |
| `agent/news_script.py` | Editorial-only duration budget, spoken-language/hook/payoff rules, evidence and attribution priority, historical art-direction constraints. Existing user edits remain intact. |
| `config.py` | New-render default `HER_EDITORIAL_STYLE_VERSION=reference-v2`; existing visual-settings JSON can override it. |
| `remotion/src/editorial/EditorialVideo.tsx` | Independent caption track, larger integrated word reveals, stable word spacing, restrained neutral canvas, duplicate-name avoidance, and speech-timed abstract pressure/fracture diagrams. No geographic geometry or authenticated documents are invented. |
| `remotion/src/editorial/schema.json`, `types.ts` | Regenerated from Pydantic with the existing exporter. |
| `agent/editorial/qa.py`, `render.py` | Encoded frame-activity and quarter-second audio-floor diagnostics; long low-activity spans are warnings, not an optimization target. Existing loudness, peak, black-frame and duration gates remain. |
| `scripts/reference_parity_review.py` | Reproducible offline before/after render, four comparison sheets, original reference measurements, playable HTML, credits and reconstruction metadata. |
| `tests/test_reference_parity.py`, `tests/test_editorial.py` | Verifies phrase coverage, original claims, canonical labels, proper names, sync error, text-only stories, legacy fallback, bounds and timeline integrity; changes the obsolete stock-label expectation. |

No new dependencies, provider substitutions, paid calls, source claims or media downloads were needed. The benchmark reuses the original speech, alignments and assets, including imperfect artwork. Future live generation uses the existing paid/free providers and their existing billing. Disclosure and source/rights metadata remain in manifests, credits and the review JSON, outside the image labels.

`VisualSettings()` explicitly constructed without overrides retains legacy behavior for older integrations. `VisualSettings.configured()` selects v2 for new application runs. Set `HER_EDITORIAL_STYLE_VERSION=legacy` to roll back the compositor. Old manifests remain loadable and old videos are not overwritten. Set `HER_NARRATION_VISUAL_SETTINGS='{"allowPhraseTimingFallback":false}'` for strict alignment; estimated fallback timings otherwise remain explicitly flagged as unverified. V2 does not fabricate word timing.

## Run and reproduce

From `/Users/klinten/Desktop/My-projects/project-HER`:

```sh
.venv/bin/python web_ui.py
# Open http://localhost:7860; select Reference editorial and progressive editorial phrases.

.venv/bin/python scripts/reference_parity_review.py
# Reuses the saved Zheng Yi Sao audio and assets; no API calls.

.venv/bin/python scripts/reference_parity_review.py --prepare-only
.venv/bin/python scripts/reference_parity_review.py --report-only
.venv/bin/python -m unittest discover -s tests
remotion/node_modules/.bin/tsc --noEmit -p remotion/tsconfig.json
node remotion/check-editorial-render.cjs output/reference_parity_v2/editorial_props.json output/reference_parity_v2/seek-checks
open output/reference_parity_v2/review.html
```

Local Remotion Studio preview:

```sh
cd remotion
./node_modules/.bin/remotion studio src/index.ts --props=../output/reference_parity_v2/editorial_props.json
```

The Mac sandbox prevents Chromium's Mach-port bootstrap; rendering/frame checks were run with reviewed local execution outside that sandbox. One approval-review timeout was retried successfully. No account credentials or remote publishing were involved.

## Outputs and acceptance

- New video: `output/reference_parity_v2/editorial.mp4`.
- Before/after playback: `output/reference_parity_v2/review.html`.
- Requested windows: `opening.jpg` (0–5s), `conflict.jpg` (13–21s), `turn.jpg` (30–39s), `ending.jpg` (last seven seconds), in that folder. Each sheet places before above after.
- Full metrics: `comparison.json`, `editorial-metrics.json`, `editorial-visual-quality.json`, `editorial-activity.json`.
- Timing/layer audit: `editorial_manifest.json`, `storyboard_summary.json` and `diagnostics.referenceStoryboard`.

| Criterion | Result | Evidence / limit |
|---|---|---|
| Existing routes and mode regression | Pass | Full Python suite; classic News/slideshow code unchanged. Live third-party services not exercised. |
| Clean visible image names | Pass | Both planner paths use canonical names; tests and rendered sheets. Source metadata retained. |
| Narration-synchronized primary text | Pass | 31 phrases over nine grammar families; exact recorded Whisper marks, frame quantization within one frame; low-confidence marks retained as warnings. |
| Optional independent captions | Pass | Explicit complete-caption profile renders; v2 editorial mode omits forced bottom transcript. |
| Larger subjects and varied composition | Pass | Opening/conflict/turn/ending sheets; portrait, date, comparison, evidence, action, contrast and conclusion families. |
| Nonblank opening | Pass | Rendered frame zero contains an anticipatory first word within the allowed 100ms opening window. |
| Strong story premise in first second | Fail | The preserved generic hook delays the actual premise. New production prompt requests an immediate supported contrast; a fresh narration must demonstrate it. |
| Meaningful pressure / fracture graphics | Pass | Original script words trigger abstract relation diagrams; not documentary evidence. |
| Deterministic frame seeking | Pass | `seek-checks/determinism.json`; repeated frame 100 after seeking to closing frame has identical hash. |
| Vertical media and non-clipped finish | Pass | 1080×1920, 30fps, AAC/H.264; encoded visual-quality and loudness/true-peak gates. |
| Typography and label bounds | Pass | Contract/font-fit checks, named-entity tests, selected full-resolution frames. Exhaustive mobile-device/collision testing is not claimed. |
| 4:5 preview and cloud render | Not tested | Existing editorial path is vertical-only; cloud execution was not available in this review. |
| Refined narration performance | Not tested | Production prompt updated; comparison intentionally retains the old recorded narration. No new voice audition. |
| Historically credible artwork throughout sample | Fail | Reused modern-looking official and inconsistent historic reconstructions remain. Need era-correct replacement assets with source/identity review. |
| Continuous audio bed in sample | Fail | No bed added to preserved speech. Existing optional music/ducking remains available; no new listening assessment. |
| Full reference style parity | Fail | Activity improves substantially but static holds, asset diversity, maps/evidence transformations, authored pacing and a stronger final payoff remain below the reference. |

Measurements in `comparison.json` use the same 90×160 grayscale, 5Hz process across all three videos. They may differ from the supplied forensic numbers because of rescaling, resampling and the finished baseline versus raw Remotion file. Changed-pixel fractions are diagnostic evidence, never a quality score. Audio-floor figures alone say nothing about timbre or acting.

## Concrete remaining work

1. Generate and audition a fresh, evidence-reviewed Zheng Yi Sao narration with the updated editorial prompt; the controlled comparison deliberately cannot demonstrate changed voice performance or rewritten prose.
2. Replace the modern official with a sourced or clearly disclosed Qing-era reconstruction; normalize portrait/ship styles and inspect masks/feathering. Reusing the originals isolates compositor changes but leaves their historical weaknesses visible.
3. Author richer movement, ownership and alliance scenes from vetted assets. The current compiler provides semantic composition, reframe, comparison and relation graphics; it does not fabricate accurate coastlines, travel routes or archival evidence when those assets are absent.
4. Enable and audition an appropriate existing music bed if desired; measure/licence a chosen track and check narration consonants, pauses and the final word. The sample preserves original speech and its silence profile.
5. Review on a phone, author exceptions for deliberate static holds, and validate actual cloud output and any future alternate-aspect preview before claiming production parity.

## Final measured results

199 Python tests passed; TypeScript compiled without errors; final Chromium seek/caption checks passed.

| Diagnostic | Before | After | Reference |
|---|---:|---:|---:|
| Changed pixels (%) | 1.05 | 2.69 | 6.82 |
| Low-activity intervals (%) | 84.95 | 67.03 | 50.69 |
| Quiet quarter-second windows | 17.00 | 17.00 | 0.00 |

Final AAC: -15.08 LUFS, -1.48 dBTP. These measurements are from the actual final export.
