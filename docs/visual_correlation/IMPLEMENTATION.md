# Event storyboard implementation

`agent/editorial/event_storyboard.py` owns the additive `event-storyboard-v1` plan, continuity bible, exact excerpt/character/word validation, bounded semantic planning and repair, explicit intentional reuse, scene prompts, audio rebinding, media and encoded-frame QC, and event EDL. Exported native Pydantic schemas and the planning prompt sit beside this document. The semantic text completeness audit is explicitly distinct from visual verification.

`sentence_storyboard.plan` accepts validated event concepts while its legacy behavior remains available. The event path retains all interacting character references and permits meaningful scene panels. `assets.acquire` uses event requirements with a real visual model, compares identity references, preserves necessary environment fragments, retrieves verified documentary references when requested, and prevents critical portrait/label substitution. Successful file generation alone never establishes semantic acceptance.

`EditorialImages.event_scene_subject` uses the existing adapter/capability system and a separately configurable quality model. The initial Pruna candidates inspected in this task often preserved a standing pose, lost props, substituted a separate bride, or kept base clothes. Those candidates were rejected. The supported `google/nano-banana-pro` multi-reference model is therefore the event tier default; existing identity/support/legacy tiers retain their configured models. Set `HER_EDITORIAL_EVENT_IMAGE_MODEL` to another supported model to change that tier. Provider admission, cancellation, retry limits and telemetry remain shared. The event deadline allows 300 seconds after admission; ambiguous timed-out accepted predictions are not automatically resubmitted.

`pipeline.run_editorial` preserves original approved TTS groups and actual audio. Only visual section IDs are reassigned after word alignment. Optional exact `onset_anchor` phrases bind image entrances to decisive spoken verbs/objects rather than introductory setup phrases; full narration spans remain separately persisted. The binder requires identical word IDs, order and timestamps, including repeated words. Estimates remain labelled and cannot satisfy the P0 synchronization gate. EDL deltas measure render entry relative to supplied measured word boundaries, not independently observed acoustic onset. Assets and encoded frames have separate review evidence. The final frame review occurs after actual rendering; unavailable visual review produces `needs_review`.

No Remotion timeline schema migration was needed. Existing scene/image layers already support full image panels; these occupy the same safe editorial geometry and coexist with portraits, photos, captions, word emphasis and branding. The same renderer, audio normalization and 2.7-second signature package are retained.

## Review and reproduction

- `scripts/visual_correlation_review.py` runs live planning/acquisition over a preserved narration manifest. It saves raw planning diagnostics and supports resume.
- `scripts/visual_correlation_candidates.py` is an explicitly curated acceptance-fixture fallback. It creates real provider candidates or retrieves source-linked photos, retains rejected candidates and accepts manual reviews only with matching image checksum and observations. It cannot certify the unavailable live planner. It renders through the real editorial compiler and Remotion, with existing speech/alignment providers.
- `scripts/visual_correlation_contact_sheet.py` extracts encoded frames every two seconds plus event midpoints, annotates aligned narration, and creates an HTML review page with per-event playback, prompts, requirements and review status.
- Curated Thor, NASA history and original comedy fixtures live in `tests/fixtures/visual_correlation/`. Story names appear only in fixtures/review data, never common planning logic.

Use the existing virtualenv with `PYTHONPYCACHEPREFIX=/tmp/her-pycache` under the local workspace sandbox. Run the full suite with `.venv/bin/python -m unittest discover -s tests -q`, and the shared renderer contract check with `remotion/node_modules/.bin/tsc --noEmit -p remotion/tsconfig.json`.

## Readiness and limitations

The existing Gemini credential began returning HTTP 401 during this work. Pro-model access also returned zero-quota responses earlier. The user selected manual review and documentation of the provider blocker. No credential was printed or changed. Curated samples provide asset, audio and renderer evidence; they do not establish autonomous live-planner acceptance. Restore model authentication and run the live planner on all three narratives before production acceptance.

The native image adapter supports real multi-image conditioning for Pruna and Nano Banana, and a single reference for Flux Kontext. Unsupported capabilities fail before submission. Illustrations retain reconstruction/provenance metadata; archival NASA assets retain source links and credits. No per-image decorative provenance captions were introduced.

No deployment was performed. Cloud Run retains the existing container, fonts, FFmpeg, Chromium, speech and optional local alignment dependencies. The event path adds no package dependency or port. Review longer image generation deadlines against the deployment's existing request/job timeout and memory limits. Set `HER_EVENT_STORYBOARD_ENABLED=0` for the prior sentence-only path; `HER_SENTENCE_PRIMARY_VISUALS=0` retains the older editorial route. Other presets and specialized modes retain their current routing.
