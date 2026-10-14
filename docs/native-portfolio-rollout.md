# Native Project HER rollout — implementation and real test evidence

The native portfolio studio is published at **https://klinteng.com/projects/project-her/#studio**. Backend repairs are deployed on **project-her-00014-ddb**. Public creation is temporarily paused while approval is pending for one final controlled output test. Successful hosted MP4 playback/download has **not** been verified; no completed result or interactive-success claim is fabricated.

## Changes and routes

Portfolio commit `36065b7` is on remote `main`; GitHub Pages deployment succeeded and normal visitor URLs serve the new native HTML/client/controller. The existing homepage/card remains familiar, with internal Try Project HER navigation. The existing `/projects/project-her/` route contains the studio, genuine previous example, pipeline and engineering disclosures. Playground links internally to that one studio. There is no iframe, external creation redirect or duplicate generator.

The static portfolio uses its existing HTML/CSS/JavaScript framework, with a JSDoc-typed adapter rather than introducing React/build infrastructure. Modified/new files are `index.html`, `projects/index.html`, `playground/index.html`, `projects/project-her/index.html`, `js/config.js`, `js/main.js`, `js/project-her-client.js`, `js/project-her-studio.js`, `css/project-her-studio.css`, browser tests and native API/schema/handoff docs. The approved previous sample is unchanged and clearly separate from current-session output. `nativeIntegrationVerified` remains false.

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

Both tests were created by the **actual published studio Generate button**, using the supplied fictional red-cup/blue-bowl account, supplied-source policy and 15-second target. No additional job was submitted during read-only recovery.

1. `9105035229db4bc58b228da01a306079`: real queued/running/input/research/script progression and SSE checked. Failed before speech because Cloud Run lacked `REPLICATE_API_TOKEN`. Production browser restored this failure after refresh, showed the real error and adjustment action, hid completed player/download, and created zero new jobs. Gemini had temporary 503/high-demand fallback. Evidence: `output/native-portfolio-smoke/smoke.json`.
2. `3744786da9ef44ada8a00e8e4be154d2`: real UI admission reached composition. A local monitor connection reset was recovered against the **same job**. Cloud Run reported **4,176 MiB used against a 4,096 MiB limit** at `2026-10-14T05:55:40.736171Z` (11:25:40 IST). The persisted job correctly became failed after the worker interruption; there is no completed MP4. Evidence: `output/native-portfolio-smoke-retest/smoke.json`.

Repair 1 securely deployed the existing local credential, verified free Replicate account authentication/model metadata access, and made missing default-provider configuration fail readiness before quota/provider work. Repair 2 releases completed ONNX segmentation sessions/native allocator memory before composition and reduces native Remotion concurrency without increasing billing capacity. Both are deployed. Successful real output verification remains pending, and admissions remain paused to prevent more failed paid work.

## Verification passed / not run

- **232 Python tests passed**, including API security/state, provider readiness, cache release/concurrency, and recovery tests proving resume never POSTs a job even with creation flags.
- **66 portfolio route/width checks** and **13 intercepted studio scenarios**, 320–1440px, keyboard/focus/overflow, refresh, error/quota/unavailable and SSE fallback: passed. These are fixtures, not hosted success.
- Typed adapter, Remotion TypeScript, JS syntax/diff checks and a five-frame editorial render from existing assets: passed. No paid provider was called for that frame check; color format remains compatible with the compositor.
- Final deployed prerequisite readiness, storage access, allowed-origin CORS, empty-input rejection (422), missing capability (404), foreign origin (403) and legacy lock (401): passed. TTL/bucket/capacity verified.
- Actual UI submission, durable failed-job state, real status/SSE and first production failure/refresh UI: passed.
- Successful hosted MP4, live playback/range/download/hash match and completed-job browser recovery: **not yet passed**. No complete-generation badge/claim is enabled.
- No portfolio production build exists: GitHub Pages serves static files. Production ingress trust is intentionally conservative rather than guessed.

## Exact remaining and future steps

An additional controlled generation requires approval because both prior authorizations were used and another run incurs new provider work. After approval, enable admissions using the durable policy switch, submit exactly one further UI smoke job and verify that same job:

```sh
PUPPETEER_MODULE=/Users/klinten/Desktop/My-projects/project-HER/temp/native-browser/node_modules/puppeteer-core/lib/esm/puppeteer/puppeteer-core.js \
  .venv/bin/python scripts/smoke_native_portfolio.py --allow-paid-generation --browser-submit \
  --browser-check ../my-website/tests/project-her-live.mjs --output output/native-portfolio-smoke-final
```

For a monitoring disconnect, **never rerun creation**. `--resume-ui-job <existing-id>` reads only that job's scoped token from stdin and performs status/SSE/media/browser checks, with GET-only retries. No access tokens are persisted in reports or printed.

After real success, record actual file/FFprobe/hash/range/player/download evidence and update status/docs. GitHub CLI publication still has no credentials in this execution session, so the final reviewable portfolio follow-up must be pushed from the user's authenticated terminal/VS Code if that remains unchanged. Initial commit `36065b7` is already published; this authentication limit does not negate its deployment.

Future full-source backend deployment:

```sh
.venv/bin/python scripts/deploy_native_portfolio.py --approve-cloud-changes
```

The script now provisions/binds mandatory Replicate credentials securely from the existing secret or local configured value. It preserves service settings/providers, prepares model dependencies, enables the legacy lock/private storage and applies the approved warm instance. No secret, private snapshot, scoped ticket or generated visitor artifact should be published in git.
