# Validation record — 2026-10-25

## Completed

- Full repository Python suite: **328 tests passed** in 16.645 seconds. Command: `PYTHONPYCACHEPREFIX=/tmp/her-pycache .venv/bin/python -m unittest discover -s tests -q`.
- Final focused suite after the semantic-originality addition: see `tests/test_autopilot.py` and `tests/test_branding.py`. It covers persistent duplicate rejection, renamed canonical arcs, separate arcs sharing characters, manual route bypass, semantic duplicate/uncertain decisions, concurrent reservations and daily assignments, budget ceilings, stale leases, lost Buffer responses, partial platform success, notification blocking, queue limits, remote confirmation, API authorization, media URL validation and actual FFmpeg rejection of a black/silent/wrong-size file.
- Remotion TypeScript check passed: `./remotion/node_modules/.bin/tsc --noEmit -p remotion/tsconfig.json`.
- Dashboard JavaScript syntax check passed with `node --check` on its extracted script.
- Authenticated Replicate model/schema lookup succeeded. A live five-candidate science-fiction cycle selected “The Aurora Initiative”; the final 151-word script passed editorial validation. Prediction metrics and failed schema attempts were retained. See `MODEL_EVALUATION.md`.
- The actual reference-editorial renderer exported a **57.706-second 1080 × 1920 H.264/AAC MP4** from a schema-compatible cached timeline. No new story/image/speech calls were made for the render regression. Encoded loudness was approximately **−15.06 LUFS**, true peak **−1.46 dBTP**; original export, visual-activity and black-frame checks passed.
- Portrait frames verified `@project.HER` in the existing protective overlay, unchanged corner branding, and a readable cover. Visual inspection caught and fixed a real stacking-order bug: the hook now renders above subject images. The cover composer also rejects an obscured hook panel. The silence gate excludes the intentional closing-brand duration while rejecting long unintended gaps.
- Cached rendering artifacts are under `output/autopilot-validation/editorial/`, including `editorial.mp4`, `thumbnail.png`, media metrics and the render validation report. Earlier classic-frame checks are under `output/autopilot-validation/`.
- Read-only cloud inspection confirmed ProjectHER's existing service/project, native Firestore database, private portfolio bucket and service account in `us-central1`. No cloud deployment, IAM/bucket creation, secret creation or social publication was performed.

## Deliberately not claimed

The cached render fixture is **not READY for publication**: it lacks an Autopilot-selected/approved story assignment and scene review. Its technically valid MP4 cannot bypass those workflow gates. It is not the video for the live science-fiction script.

Actual new-story generation through narration/assets/rendering/public storage as one cloud job remains unverified. Live story diversity across all configured genres, historical-source retrieval on representative traditions, and editorial quality across multiple complete productions still need phased validation.

Buffer authentication/discovery, live GraphQL mutation acceptance, real Instagram/YouTube publication, selected Instagram cover behavior, API timeout reconciliation against Buffer itself, and Cloud Run/Scheduler execution remain unverified because no Buffer API credential, dedicated public-media bucket or Autopilot admin secret is configured. Offline transport fixtures test the implemented safety contracts; they do not establish provider publication success.

Terraform is not installed locally; its template still needs `terraform fmt`, `validate`, a reviewed plan and application against the existing project. Its schedules default to paused and live publishing defaults to disabled/dry-run.

The existing Remotion installation reports a Zod-version warning during rendering. TypeScript checks and the full cached render pass with the repository's current dependency set; this change does not upgrade the existing schema dependency as part of the integration.

Provider-reported billed dollars were unavailable. Token-derived estimates and conservative reservations are distinct from actual invoices. Embeddings are optional and not implemented; deterministic checks plus a bounded semantic review of relevant prior arcs reduce duplicate risk without claiming perfect semantic detection.

Follow `OPERATIONS.md` for controlled tests, credential setup, activation, monitoring, retention and rollback. Daily publishing must remain disabled/dry-run until both platform test publications have been remotely confirmed.
