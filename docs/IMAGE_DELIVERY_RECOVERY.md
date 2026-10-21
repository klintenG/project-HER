# Saved-image delivery and recovery

The current policy follows the user's updated preference: complete the video using
already-paid images, and report quality concerns separately. The previous audit's
strict rejection behavior remains available explicitly.

## Default behavior

`IMAGE_FAILURE_POLICY=deliver_with_warnings` and
`RENDER_BLOCK_ON_CRITICAL_VISUAL_FAILURE=false`:

- A raw image is cached before background removal, styling or semantic review.
- If cutout processing fails, the original image is retained as a framed scene.
- If semantic review fails, that scene's own image remains usable for delivery;
  its failed review is not changed to a passing review.
- If a request returns no readable image, the scene is marked "Visual unavailable"
  rather than substituting an unrelated character portrait or regenerating.
- Seedream is never regenerated to satisfy the reviewer.
- Existing per-job assets and the original prediction ledger are reused on resume.
- The exact same request in the normal app flow reuses a saved result or resumes
  saved media from a previous failed job, within `IMAGE_SAVED_JOB_REUSE_SECONDS`
  (default 24 hours). Changing script inputs/settings changes the request key.
- Narration metadata is checkpointed as soon as speech generation succeeds.
- The final video can be delivered with `visual_quality=needs_review`; this is
  successful export with unresolved quality warnings, not verified visual approval.

Set `IMAGE_FAILURE_POLICY=strict` to explicitly block export on failed semantic
review. `RENDER_BLOCK_ON_CRITICAL_VISUAL_FAILURE=true` independently opts into
critical QA blocking. Budgets and cancellation remain enforced in either mode.
Restart the app after changing `.env` to reload these settings.

## Recover an existing failed job without generating again

```sh
venv/bin/python scripts/recover_editorial_job.py \
  --job output/editorial_14795da96d5f4c3590780ad60a528524
```

Recovery uses saved speech chunks and the existing asset registry/ledger. It has
no image, voice, or vision generation provider enabled. Local alignment, Remotion
and FFmpeg perform the remaining work. The output is `recovered.mp4`, alongside
`recovered_manifest.json`, `recovered-subtitles.srt`, `recovery_result.json`,
`quality_report.json`, and a one-second contact sheet. A missing/corrupt saved file
cannot be recovered through a hidden paid call. Failures in export can be retried
from `recovered_manifest.json` with no image generation.

The job above was recovered to a 62.144-second 1080×1920 H.264/AAC MP4 from its
existing media. Its saved ledger still contains the same 14 predictions. No new
image/voice/vision generation requests were made for recovery. Several semantic
warnings remain (for example, a pleading figure does not establish that rulers
are visibly present); they remain recorded rather than being relabeled as passes.

This prevents the observed quality-gate/cutout failures from discarding paid
work. External provider outages, missing files, insufficient credits, storage
errors or renderer failures cannot be guaranteed never to occur. Saved media and
local recovery isolate those failures from new image spending.

## Validation

The full test suite completed with 419 passing tests in `venv`. Two UI import tests
require Gradio, present in `.venv` rather than `venv`; they are checked separately.
New tests exercise cutout failure without regeneration, cached-asset resume, saved
video reuse without research/image providers, readable-file validation, and strict
opt-in behavior. Existing strict tests explicitly select that mode. The recovered
video's contact sheet was inspected and its 1080×1920 H.264/AAC streams verified.

## Cutout-only delivery update

The subsequent user request removes the scene-panel fallback described above.
All raster assets now receive a foreground-mask check before composition, and
render staging repeats the check so old cached opaque images cannot bypass it.
RGBA mode, transparent padding, or rounded panel corners alone do not count as a
cutout. Opaque or nearly rectangular masks are rejected as scene panels.

Editorial image requests always include the shared isolation rules at provider
submission, even if contextual prompt formatting is disabled. They request full
subjects, essential props, generous uniform matte margins, and no frame, scenery
panel or painted checkerboard. The adapters do not assume a native transparent
output parameter. Background removal is still required to produce real alpha.

Local recovery can accept an existing irregular mask despite source-edge clipping,
then trim dust and add compositing margins; it cannot reconstruct clipped limbs.
It can run the configured local segmenter and, for an appropriate uniform neutral
matte, remove border-connected background. Recovery masks are cached by source
checksum. None of these paths submits another image-generation request. If no
usable foreground mask can be recovered, the original remains on disk and the
scene is explicitly unavailable, never pasted as a rectangular image.

`output/editorial_14795da96d5f4c3590780ad60a528524/recovered-cutout.mp4` is the
updated 62.144-second export. All 10 scene assets have true nonrectangular alpha
masks. The 14 saved predictions are unchanged. Semantic and anatomy warnings
remain separate from these structural alpha checks.
