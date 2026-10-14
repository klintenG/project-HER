# Native Project HER rollout — implementation and real test evidence

The native portfolio studio is published at **https://klinteng.com/projects/project-her/#studio**. Backend repairs are deployed on **project-her-00014-ddb**. The additional user-approved controlled job completed successfully. The actual published portfolio restored it, played its private MP4 and downloaded identical bytes without leaving klinteng.com or submitting another job. Public creation is enabled with enforced quotas.

## Changes and routes

Portfolio commit `36065b7` is on remote `main`; GitHub Pages deployment succeeded and normal visitor URLs serve the new native HTML/client/controller. The existing homepage/card remains familiar, with internal Try Project HER navigation. The existing `/projects/project-her/` route contains the studio, genuine previous example, pipeline and engineering disclosures. Playground links internally to that one studio. There is no iframe, external creation redirect or duplicate generator.

The static portfolio uses its existing HTML/CSS/JavaScript framework, with a JSDoc-typed adapter rather than introducing React/build infrastructure. Modified/new files are `index.html`, `projects/index.html`, `playground/index.html`, `projects/project-her/index.html`, `js/config.js`, `js/main.js`, `js/project-her-client.js`, `js/project-her-studio.js`, `css/project-her-studio.css`, browser tests and native API/schema/handoff docs. The approved previous sample is unchanged and clearly separate from current-session output. The final portfolio follow-up sets `nativeIntegrationVerified` true based on the real production proof below; its publication status is recorded separately.

HER implementation adds `agent/portfolio_api.py`, `agent/portfolio_store.py`, storage dependencies, deployment/explicit smoke tools and scoped API tests. `web_ui.py` installs native CORS/authentication and fixes legacy output traversal/basename fallback. Docker prepares exact alignment/browser dependencies; source upload excludes duplicated local caches. Renderer packages are consistently pinned to 4.0.535, with compatible transitive fixes; npm audit reported zero vulnerabilities.

Follow-up repairs: mandatory Replicate credential readiness/provisioning; safe GET-only monitoring retries and token-on-stdin resume that never submits a job; native model-cache release before composition; `utils/render_resources.py` applies one-worker native concurrency across Editorial, News and Classic Remotion bridges. Standalone defaults remain unchanged. Prior user changes in `de26b43` are preserved.

## Confirmed API contract

Base: `https://project-her-svnnlerw4q-uc.a.run.app/api/portfolio`.

| Method/path | Contract |
|---|---|
| GET `/config` | Actual options/defaults/limits and enabled status; fail closed without secure storage, exact alignment, legacy lock or default Replicate credentials. |
| POST `/jobs` | Allowed Origin, strict JSON and random `Idempotency-Key`; 202 `{job_id,access_token,expires_at,status,cancel_supported}`. Same key/input recovers the same admission. |
| GET `/submission` | Recover an ambiguous acknowledgement using that same unguessable key. |
| GET `/jobs/<id>` | Scoped Bearer access; real durable status/stage/result. Wrong/missing access is 404; expired access 410. |
| GET `/jobs/<id>/events` | Authenticated streaming fetch; real progress/done, finite streams and polling fallback. |
| POST `/jobs/<id>/cancel` | Scoped access and allowed Origin; News only, final cancellation confirmed separately. Classic unsupported. |
| GET/HEAD `/jobs/<id>/media/<kind>` | Thirty-minute media-scoped ticket; byte ranges/attachment and renewal through authorized job status. |

Statuses are queued/running/completed/failed/cancelled. Stages expose actual name/label/status/elapsed, without fake percentages or provider logs. Completed title/duration/resolution/language/media appear only after private upload succeeds.

Default request: News, informative/storytelling, vertical, auto duration 0, Remotion/reference editorial, progressive editorial phrases, automatic assets/sources, configured Replicate/Kokoro and no music. Claymorphism is the general Classic style; News has its own reference art direction. Inputs max 6000 characters/16000 request bytes; URL max 2048; target 0 or 15–90 seconds. News speech max 220 words before provider work; delivered video max 180 seconds. Classic uses its configured server narration and does not support News-only voice/music controls. The portfolio schema documents every option and compatibility rule.

## Production deployment

Project `project-her-510715`, region `us-central1`, existing service `project-her`:

- Current ready revision `project-her-00014-ddb`; capacity remains **2 CPU / 4Gi**, min/max instances 1, always-allocated CPU, HTTP concurrency 20. Native admission concurrency 1; native Remotion concurrency now 1.
- Firestore regional `(default)` database; `her_portfolio.delete_after` TTL ACTIVE.
- Private `project-her-510715-portfolio-output`, uniform access/public-access prevention; two-day lifecycle only on `portfolio/`, extra soft-delete retention disabled. App access expires at 48 hours; physical deletion is asynchronous.
- Signing/operator secrets plus `her-provider-replicate-token` in Secret Manager; runtime access scoped to those secrets. Existing Gemini/provider settings preserved. Provider values never enter browser/source/log output.
- Daily global budget 10 admissions; network identity 2/day; failed jobs count. Trusted proxy hops remain conservatively 0, so shared proxies can share a quota. Admissions are not an exact currency budget.
- Native workers have heartbeat/lease, hard deadline, cancellation and owned scratch/staging cleanup. Interrupted paid work is failed rather than silently replayed.

Builds: base `785aef3c-1618-4086-bdfb-e2dbdb00614e`; renderer/cleanup `9720650c-5a5e-4c8d-8a86-427a05f4585d`; credential readiness `c503e205-93a6-469e-a9b1-38bfbbc5b9e5`; memory repair `78957d83-72f0-42cd-9477-f69373e8f261`. Follow-up images pin the immutable preceding image and reviewed changed files. Future full-source deployments use the checked-in Dockerfile, sources and lockfile.

## Real end-to-end evidence and failures

All three tests were created by the **actual published studio Generate button**, using the supplied fictional red-cup/blue-bowl account, supplied-source policy and 15-second target. No additional job was submitted during read-only recovery.

1. `9105035229db4bc58b228da01a306079`: real queued/running/input/research/script progression and SSE checked. Failed before speech because Cloud Run lacked `REPLICATE_API_TOKEN`. Production browser restored this failure after refresh, showed the real error and adjustment action, hid completed player/download, and created zero new jobs. Gemini had temporary 503/high-demand fallback. Evidence: `output/native-portfolio-smoke/smoke.json`.
2. `3744786da9ef44ada8a00e8e4be154d2`: real UI admission reached composition. A local monitor connection reset was recovered against the **same job**. Cloud Run reported **4,176 MiB used against a 4,096 MiB limit** at `2026-10-14T05:55:40.736171Z` (11:25:40 IST). The persisted job correctly became failed after the worker interruption; there is no completed MP4. Evidence: `output/native-portfolio-smoke-retest/smoke.json`.

Repair 1 securely deployed the existing local credential, verified free Replicate account authentication/model metadata access, and made missing default-provider configuration fail readiness before quota/provider work. Repair 2 releases completed ONNX segmentation sessions/native allocator memory before composition and reduces native Remotion concurrency without increasing billing capacity. Both are deployed. The additional explicitly approved test below verified successful output; admissions are now enabled under the existing limits.

3. `2529226b31c14ef48e2c8a3aae184a6e`: additional explicitly approved job created through the published studio on revision `project-her-00014-ddb`; completed in approximately 516 seconds. Observed durable snapshots: queued → running → script → narration/alignment → completed. Intermediate visual/render stages were not captured by this polling report and no progress is fabricated. The 15-second target produced an actual **25.749-second** H.264/AAC MP4, **1080×1920**, **2,727,367 bytes**. Actual byte-range HTTP 206 and attachment delivery passed. SHA-256: `899b3b0d2ec569340e6fbbc34168232bb6b0891c5e3c2942ced87c5c07b8580d`.

The first completed-job browser check failed transiently; a read-only repeat against that **same job** passed. Production Chromium restored the real job from scoped tab storage, played the private MP4, downloaded a matching SHA-256 file, remained on klinteng.com and made **zero new job submissions**. Evidence: `output/native-portfolio-smoke-final/smoke.json`, `generated.mp4`, `temp/native-browser-final-proof.log`, `temp/native-live/production.png`. These private test assets are ignored in git; no credential or signed media link is included in this report.

## Verification passed / not run

- **232 Python tests passed**, including API security/state, provider readiness, cache release/concurrency, and recovery tests proving resume never POSTs a job even with creation flags.
- **66 portfolio route/width checks** and **13 intercepted studio scenarios**, 320–1440px, keyboard/focus/overflow, refresh, error/quota/unavailable and SSE fallback: passed. These are fixtures, not hosted success.
- Typed adapter, Remotion TypeScript, JS syntax/diff checks and a five-frame editorial render from existing assets: passed. No paid provider was called for that frame check; color format remains compatible with the compositor.
- Final deployed prerequisite readiness, storage access, allowed-origin CORS, empty-input rejection (422), missing capability (404), foreign origin (403) and legacy lock (401): passed. TTL/bucket/capacity verified.
- Actual UI submission, durable failed-job state, real status/SSE and first production failure/refresh UI: passed.
- Successful hosted MP4, live playback/range/download/hash match and completed-job browser recovery: **passed against the actual published site and same real job**, not fixtures.
- No portfolio production build exists: GitHub Pages serves static files. Production ingress trust is intentionally conservative rather than guessed.

## Exact remaining and future steps

The approved rollout and the additional controlled output test are complete. Do not run another paid generation merely to verify documentation or publishing. For future monitoring, `--resume-ui-job <existing-id>` reads that job's scoped token from stdin and never creates another job. The scoped output expires 48 hours after admission; the genuine local evidence remains available.

The published initial portfolio commit is `36065b7`. Final proof/docs/status are prepared as a separate follow-up. Publish that follow-up through the existing `main` GitHub Pages flow after reviewing its diff; no backend redeployment is needed. GitHub authentication is not available to this execution session, so publication may require the user's authenticated terminal/VS Code. This affects the final documentation/status flag only: actual native generation/playback/download was already verified on the published initial studio.

Future full-source backend deployment:

```sh
.venv/bin/python scripts/deploy_native_portfolio.py --approve-cloud-changes
```

The script now provisions/binds mandatory Replicate credentials securely from the existing secret or local configured value. It preserves service settings/providers, prepares model dependencies, enables the legacy lock/private storage and applies the approved warm instance. No secret, private snapshot, scoped ticket or generated visitor artifact should be published in git.

## Operator testing override — 14 October 2026

At the user's explicit request, daily per-network and global generation limits are temporarily disabled via `her_portfolio/policy.daily_limits_disabled=true`. Admissions still record counters. One concurrent render, input/duration validation, scoped authorization and the independent emergency pause remain enforced. This override requires no frontend publication to unblock generation. The frontend follow-up reports testing mode accurately when published.

Re-enable manually (no redeployment required):

```sh
cd /Users/klinten/Desktop/My-projects/project-HER
.venv/bin/python scripts/set_native_daily_limits.py --enable
```

To disable again, use `--disable`. The command uses the operator's authenticated gcloud account, modifies only this policy field and does not create jobs or clear existing counts. Re-enabling immediately enforces the original 2/network/day and 10/global/day against retained current-day counts. Targeted API suite: 23 passed, including disable/re-enable, unchanged concurrency and independent emergency pause.

Live override deployment: build `b023c43c-e3d7-42e6-b275-2faf958e29b7`, ready revision `project-her-00015-ldq`. Actual GET config confirmed `enabled=true`, `daily_limits_disabled=true`, concurrency 1. Full Python suite: **233 passed**. No additional paid generation was submitted for this change.

## Cutout framing recovery — 14 October 2026

The reported cutout failure rejected an opaque provider image and an edge-touching segmented subject. Quality thresholds remain unchanged. Editorial generation now requests a centered subject occupying at most 60% of canvas width/height, with 20% empty margins, a contrasting flat backdrop and a fresh smaller composition on retries. Retry prompts use the attempt-specific subject instructions. Rejected illustration cache entries are bypassed on the next attempt; accepted cache entries still require checksums and mask QA. Each raw attempt is retained separately in job scratch for diagnosis.

`CutoutQualityError` distinguishes unusable segmentation from provider/identity errors. One additional attempt beyond the configured count is allowed only after mask QA failure; existing per-job image-call budgets remain enforced. Provider/authentication and likeness failures do not gain extra retries. Existing disclosed contextual-symbol fallback remains unchanged; essential real people/groups still require usable assets and fail honestly if all attempts fail. Nothing accepts opaque or clipped images simply to complete a render.

Full Python suite: **236 passed**. New regressions reproduce edge clipping twice before a successful third attempt, a rejected cached image followed by fresh generation, and exhausted generic versus essential named-person behavior. Existing group/identity/security tests pass. No additional paid generation was submitted; the visitor can retry their failed input after deployment and refresh.

Cutout repair deployed: build `ca68d618-59d4-439d-b0ad-c9ebbde09bff`, revision `project-her-00016-cbd`; private storage/provider secrets/capacity are preserved. No portfolio publish is required for this backend-only repair.
