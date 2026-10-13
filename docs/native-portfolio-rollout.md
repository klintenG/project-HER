# Native Project HER rollout — current evidence

Backend deployment is complete. Portfolio publication is blocked by missing GitHub credentials in this execution session. No paid smoke generation has been submitted. A reachable API/configuration is not claimed as proof of generation, playback or download.

## Implemented and committed

HER commit `458190b` on `new-enhancements`: scoped native Flask API, durable Firestore state/quotas, private Storage output, signed media delivery, exact alignment preparation, legacy operator authentication, SSRF/input limits, hard deadlines/cancellation, job-scoped scratch cleanup, deployment/smoke scripts, patched renderer dependencies and tests. Existing user changes in `de26b43` are preserved.

Portfolio commit `36065b7` on `main` in `/Users/klinten/Desktop/My-projects/my-website`: existing homepage/card preserved with internal Try Project HER CTA, one native studio on `/projects/project-her/#studio`, actual typed adapter/lifecycle, supported Simple/Advanced controls, sample/engineering sections, and redundant Playground form consolidation. No iframe or fake output. The existing approved sample remains unchanged. `nativeIntegrationVerified` is false until the controlled production test succeeds.

Changed backend files: `.env.example`, `.gcloudignore`, `Dockerfile`, `agent/portfolio_api.py`, `agent/portfolio_store.py`, `requirements-portfolio.txt`, `scripts/deploy_native_portfolio.py`, `scripts/smoke_native_portfolio.py`, `scripts/submit_native_portfolio.mjs`, `tests/test_portfolio_api.py`, `tests/test_editorial_visuals.py`, `web_ui.py`, `remotion/package.json`, `remotion/package-lock.json`.

Portfolio file/route details and complete request schema are in its `docs/project-her-native-handoff.md`, `docs/project-her-native-api.md` and `docs/project-her-request.schema.json`.

## Deployed infrastructure

Project `project-her-510715`, region `us-central1`, existing service `project-her`:

- Ready revision `project-her-00012-phb`, 100% traffic.
- 2 vCPU, 4Gi RAM, min/max instances 1, CPU throttling disabled, HTTP concurrency 20; native render admission concurrency 1.
- Native daily admission limit 10; server-derived network identity limit 2. Trusted proxy hops remain 0; shared proxies may share the conservative limit. Admissions are not an exact currency budget and failures count.
- Firestore `(default)` native regional database; `her_portfolio.delete_after` TTL is ACTIVE.
- Private `project-her-510715-portfolio-output` bucket, uniform access and public-access prevention. Delete lifecycle only on `portfolio/` after two days; extra soft-delete retention disabled. Application access expires at 48 hours; physical lifecycle/TTL deletion is asynchronous.
- Native signing/operator secrets in Secret Manager and scoped additional runtime IAM. Existing providers/settings preserved. Legacy generation/output requires operator Basic authentication.
- Base build `785aef3c-1618-4086-bdfb-e2dbdb00614e` succeeded. Final secured image build `9720650c-5a5e-4c8d-8a86-427a05f4585d` succeeded, pinned to the immutable base and updated with native cleanup plus patched renderer lockfile. Full future source builds include all current source changes.

Model/browser caches are excluded from source uploads; the Dockerfile downloads the exact alignment model during the build. Remotion packages are consistently pinned to 4.0.535, with compatible transitive fixes. npm audit reports zero vulnerabilities at verification time.

## API contract

Base `https://project-her-svnnlerw4q-uc.a.run.app/api/portfolio`:

| Method/path | Contract |
|---|---|
| GET `/config` | Actual defaults/options/limits and readiness. |
| POST `/jobs` | Allowed Origin, JSON and random `Idempotency-Key`; 202 job ID, scoped access token, expiry/status/cancel support. Same key/input recovers the same admission. |
| GET `/submission` | Recover acknowledgement with the same unguessable idempotency key. |
| GET `/jobs/<id>` | Scoped Bearer token; actual stored status/stage/result. |
| GET `/jobs/<id>/events` | Authenticated streamed fetch; actual progress/done, polling fallback. |
| POST `/jobs/<id>/cancel` | Authenticated News cancellation; Classic unsupported. |
| GET/HEAD `/jobs/<id>/media/<kind>` | 30-minute scoped ticket, range/attachment support, renewable through authorized status. |

Default request: News, informative, vertical, auto duration 0, claymorphism general style (Classic only), Remotion/reference editorial, editorial phrases, automatic assets/sources, configured Replicate and no music. Inputs max 6000 characters/16000 request bytes, URL max 2048, target 0 or 15–90 seconds. Public News narration max 220 words before speech/assets; completed video max 180 seconds. See the portfolio schema for all supported options and compatibility constraints.

## Verification

Passed locally: 227 Python tests including 19 native API/security/cleanup cases; 66 portfolio route/width checks; 13 intercepted studio scenarios at 320–1440px; typed client and Remotion TypeScript; JavaScript syntax; diff checks; five-frame 1080×1920 editorial render from existing assets without provider calls. Render color format remains compatible with the compositor. Fixtures do not prove hosted generation.

Passed against final deployment: enabled configuration and Firestore/Storage access; allowed-origin CORS/preflight (200); foreign origin rejected (403); empty input rejected without creating a job (422); missing job capability rejected (404); legacy operator lock (401). Bucket controls, TTL and revision traffic/capacity checked independently.

Not run: actual production UI job submission, completed hosted MP4, live job SSE, range/playback/download and public browser recovery. These require publication and the one controlled test. No new sample/result has been fabricated or published.

## Remaining steps

Publication attempt failed with `fatal: could not read Username for 'https://github.com': Device not configured`. GitHub CLI, an SSH identity and process GitHub tokens are not available. The cloud rollout approval remains valid; authentication is missing, not permission.

1. From an authenticated terminal or VS Code, publish the prepared commit:

   ```sh
   git -C /Users/klinten/Desktop/My-projects/my-website push origin main
   ```

2. Verify GitHub Pages serves the actual `#studio` page and native client assets at klinteng.com. Do not submit while the old page is still deployed.
3. From HER, run exactly one opted-in controlled generation through the published Generate button:

   ```sh
   .venv/bin/python scripts/smoke_native_portfolio.py --allow-paid-generation --browser-submit --browser-check ../my-website/tests/project-her-live.mjs
   ```

   The supplied fictional cup/bowl input targets 15 seconds. Credentials travel only through captured subprocess memory; status/report logs contain no tokens. Monitor the same job, check real SSE, byte ranges, attachment/FFprobe, then restore/play/download identical bytes in production Chromium. Do not automatically resubmit after an ambiguous or failed paid attempt.

4. Record actual evidence under `output/native-portfolio-smoke/`, update the portfolio handoff/status only after success, and publish the evidence/status follow-up. Do not publish scoped tokens, private output artifacts or rollback snapshots.

Future full backend rollout command, already approved for this implementation:

```sh
.venv/bin/python scripts/deploy_native_portfolio.py --approve-cloud-changes
```

It preserves provider settings and enables private storage/legacy lock with the approved warm instance. The portfolio is static GitHub Pages and has no production build command. No additional infrastructure changes are needed for the pending test.
