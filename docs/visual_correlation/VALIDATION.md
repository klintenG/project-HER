# Validation and rollout evidence

Artifacts: [before/after storyboard](../../output/visual_correlation/BEFORE_AFTER.md), [metrics](../../output/visual_correlation/quality_metrics.json), and the real [Thor](../../output/visual_correlation/thor_curated/editorial.mp4), [history](../../output/visual_correlation/history/editorial.mp4), and [comedy](../../output/visual_correlation/comedy/editorial.mp4) videos. Each run includes `event_plan.json`, `event_edl.json`, acquired assets, prompts/provider records, source and encoded-frame manual review observations bound to image checksums, full Remotion manifest, synchronized SRT/VTT, contact sheet and an HTML event review page.

The supplied generated clips and reference were inspected through their complete contact sheets, with source durations measured by ffprobe. The reference is a different diamond story. The new Thor sample uses the saved exact narration and actual `whisper_forced` word boundaries, keeping the original audio and 63.082-second output duration. The two independent samples use real Replicate speech and actual local forced alignment; they are not silent/synthetic fixtures.

## Commands

```sh
PYTHONPYCACHEPREFIX=/tmp/her-pycache .venv/bin/python -m unittest discover -s tests -q
remotion/node_modules/.bin/tsc --noEmit -p remotion/tsconfig.json
git diff --check
```

Final result: **347 tests passed** (29.021 seconds), TypeScript contract check passed, and `git diff --check` passed. A concurrent PNG preparation race exposed by the full suite was fixed with atomic content-addressed file replacement; the full suite then passed.

The complete suite covers News input classification and topic/URL/supplied-text resolution, API routing, audio/TTS providers, semantic extraction, exact and repeated-word spans, immutable speech groups, action-specific cache identity, render contracts, branding/outro, provider admission/cancellation/recovery, forbidden critical fallback, duplicate portraits across different actions, unavailable visual judge and rate-limit failure, explicit reuse/state compatibility, and the event pipeline's EDL compilation. Unit tests with synthetic illustrations/pulses explicitly test orchestration, not real image semantics or live speech quality. The rendered samples provide the separate real-media evidence.

## Acceptance matrix

| Requirement | Evidence / status |
|---|---|
| Thor hammer missing, theft, demand, refusal, disguise proposal, actual disguise, wedding arrival, banquet, suspicion/explanation, handoff, grip, reveal, confrontation and aftermath | Fourteen manually inspected original scene assets and fourteen encoded frames; per-beat requirements in Thor EDL. The suspicious giant and Loki explanation share one simultaneous tableau because the supplied narration does not separately narrate a suspicion beat. |
| Zero generic portrait substitution for P0 actions | New event resolver forbids portrait/label replacement when no critical scene survives. Initial wrong candidates are retained and described in `rejected_candidates.json`; all final P0 assets depict the actual action. |
| Event timing follows actual audio | Original/provider or forced word times retained. Exact `onset_anchor` phrases trigger scene entrances at decisive spoken verbs/objects, skipping introductory setup phrases. Full narration span and visual onset remain separate EDL fields. Compiled frame deltas are logged; they are not independent acoustic measurements. |
| Final story line remains visible, then signature outro | Last visual layer covers narration end; existing story duration includes the closing hold; 2.7-second branding package is appended afterwards. |
| Identity / costume / custody | Image references and continuity bible; manual scene comparison. Thor changes from blue Norse tunic to full ivory bridal gown, then torn gown and removed veil; Loki remains in green Norse clothing. The hammer is absent, held by giant, handed over, then held by Thor in source order. |
| Factual history / source provenance | Mission-specific NASA crew, launch, ladder descent, sampling and recovery photos. The weak distant launch image was replaced after encoded-frame review. Credits and source URLs retained. No generated photo presented as archive evidence. |
| Independent physical comedy | Five distinct carrying/slipping/catching/landing/biting scenes, consistent baker and cake story; actual speech and final video. Minor layer compression of the cake is documented in manual review. |
| Existing mode/input contracts | Full regression suite, native Remotion type contract and actual existing editorial renderer. Other presets and specialized modes are not rerouted. No live deployed-app or Cloud Run smoke test was run. |
| Live autonomous semantic planner | **Not certified.** Initial lightweight model produced incomplete/schema-invalid plans; Pro access had zero quota; then configured Gemini returned HTTP 401. User selected manual review. Curated typed acceptance fixtures are clearly labelled and must not be represented as live planner success. |
| Deployment | No deployment or remote setting changed. Restore LLM/vision authentication and run the live review command for all three scripts before production acceptance. Feature flags provide rollback. |

Image provider rate limiting was handled by its existing bounded retry/admission logic; final telemetry retains actual accepted predictions and HTTP 429 counts. Costs are not claimed as actual billed dollars because a billing receipt is unavailable. The metrics distinguish image counts, source retrieval, retries, manual coverage and timing. Actual render latency, encoded loudness/peak, duration and black-frame checks are saved in each manifest and quality report.
