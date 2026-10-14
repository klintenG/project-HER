# Native Project HER rollout — implementation and real test evidence

The native portfolio studio is published at **https://klinteng.com/projects/project-her/#studio**. Backend repairs are deployed on **project-her-00017-8mn**; a fresh controlled production test on that revision passed. The additional user-approved controlled job completed successfully. The actual published portfolio restored it, played its private MP4 and downloaded identical bytes without leaving klinteng.com or submitting another job. Public creation is enabled with enforced quotas.

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

## Reliability review — 14 October 2026

Job `1b681c18ed9f472ebb7057d215c39420` began at 18:04:27 IST on revision 15 while the revision-16 image was building. Its last heartbeat was 18:06:17; Cloud Run sent TERM to revision 15 at 18:06:28 as the new revision took traffic. The job was detected as interrupted at 18:08:18, well before its 45-minute deadline. The earlier preflight checked too early and allowed a new submission during the image build. This rollout interruption was caused by our deployment, not an input problem or a newly observed memory overrun.

`utils/deployment_guard.py` now atomically pauses admissions through an operator-owned maintenance policy immediately before deployment, drains nonterminal jobs, and aborts rather than killing work if draining exceeds its bound. It preserves the independent emergency pause and daily-limit override, and clears only its own maintenance flag on normal completion/failure. The checked-in full-source deploy script uses this guard. The first transition uses the old backend's emergency pause as a compatibility bridge; future revisions understand maintenance directly. Existing scoped status/events/media remain accessible during maintenance. A process forcibly killed outside Python can leave maintenance set; an operator must inspect deployment status before clearing that policy.

Additional recent records showed a Replicate speech connection failure (`a14ab5f2ac9643eabf717358b124240a`) and zero-duration forced-alignment word (`04f1d82171f44d8ba33bc15b818781f0`). Accepted speech prediction GETs now recover bounded connection/temporary 5xx failures without recreating the prediction. Only a connection timeout before a POST reaches the provider can retry creation; ambiguous POST read/connection errors remain honest failures to prevent duplicate paid calls. Existing 429 pacing/wait budgets and Replicate-only configuration remain unchanged.

Zero-duration alignment now recomputes measured Whisper cross-attention/DTW at filter widths 7, 3 and 11, reusing the encoder output; it retains exact script tokens and never invents evenly spaced word timing. If no measured alignment succeeds, the job still fails honestly. Previous provider readiness, inference-cache release/one-worker rendering, strict cutout framing/cache retries and private durable delivery remain in place.

Full Python suite: **248 passed**, including deployment drain/timeout/failure ownership, maintenance admission with existing-job access, same-prediction safe network recovery, ambiguous-POST no-duplicate protection, and bounded measured-alignment recovery. No new paid generation has yet been submitted for this reliability revision. This fixes identified causes and improves recovery; it cannot guarantee no provider outage, host restart, unacceptable image or missing speech in every future input.

Reliability deployment: build `d1bb7748-01f0-432d-a11d-dd37463b5507`, ready revision `project-her-00017-8mn`. The guard paused admission, found zero unfinished jobs immediately before the revision switch, and cleared maintenance while preserving daily limits disabled. CPU/RAM/instance settings and provider secrets are unchanged.


## Fresh approved production verification — revision 17

The user explicitly approved exactly one additional generation to verify the reliability repairs. Job **`d221a507b3884e86967c01a7a36e9b51`** was created through the actual published klinteng.com Generate button, using the short supplied fictional red-cup/blue-bowl description and a 15-second target. No additional generation was created during monitoring or browser recovery.

The real job **completed in 592.3 seconds**. Observed snapshots included input resolution, source extraction, script approval, narration/word alignment, visual asset preparation, rendering/mix checks and completed. No backend revision was changed while this job ran. No worker-stop, narration, zero-duration-alignment or cutout-quality failure terminated this run. This one short input does not establish reliability for every topic, portrait, article, provider load or host restart, and does not prove each recovery branch was exercised; dedicated regression tests cover those branches.

Actual output: **22.848 seconds**, H.264/AAC, **1080×1920**, **2,321,732 bytes**. Range playback returned HTTP 206; attachment delivery and actual SSE endpoint checks passed. SHA-256: `3826ad1a0f5384c529461baebd78040c7e91bc65c7225d26535cc9d4e4823593`. Chromium restored the completed job on the actual production portfolio, played the private MP4 and downloaded identical bytes while remaining on klinteng.com and issuing **zero new POST /jobs requests**. Browser proof passed on its first attempt.

Private ignored evidence: `output/native-reliability-smoke/smoke.json`, `output/native-reliability-smoke/generated.mp4`, `temp/native-reliability-smoke.log`, `temp/native-reliability-live/production.png`, and extracted frame `frame-8s.jpg`. The frame confirms a visible isolated asset; it is not a full semantic/visual synchronization audit. No scoped access token, signed media URL or generated visitor file is committed.

All identified backend repairs remain deployed; daily limits remain disabled at the user's request, with one concurrent render enforced. No additional portfolio deployment is required for these backend repairs.

## Emu War missing imagery audit — 14 October 2026

The user supplied `/Users/klinten/Downloads/project-her-ea056437.mp4` (66.773 seconds, 1080×1920, audio) and the story used to generate it. Extracted video frames confirm generic cube assets labelled “Emus” and “Defeat medal”, alongside actual illustrations of birds, soldiers, a gun and a truck. Evidence is privately retained in `temp/emu-visual-audit/contact-sheet.jpg`; the original download is unchanged.

The resolver previously used deterministic cube/profile/building symbols when identity-linked photo lookup, generated-image QA or supporting-call budgets failed. The native worker also clamped supporting image calls to eight despite a longer visual plan. These automatic symbolic fallback routes are removed. Missing non-person references now produce explicitly labelled contextual AI illustrations; stock misses also use generated imagery. Missing required exact/local assets and exhausted acquisition attempts fail honestly instead of rendering placeholder geometry. A final acquisition guard rejects symbolic-preparation assets.

Every new non-reference generated illustration receives visual relevance QA: requested subject, usable depiction, story-era appropriateness and absence of an unrelated geometric substitute. Rejected images regenerate within bounded attempts; transient review failures recheck the same picture. Cached accepted images require matching checksums and accepted review metadata; illustration cache version is bumped. Existing identity/reference checks remain strict. Animal prompts require a recognizable natural-color complete representative animal rather than a silhouette icon or flock that cannot pass cutout QA. Prompts include narration context for historical clothing/equipment without introducing extra scene characters.

The visual planner is instructed to reuse recurring subjects rather than duplicate “Emus”/“Emu silhouette” entities, and to avoid unmentioned medals/trophies for defeat/success. Native supporting-image calls now have a **24-call ceiling**, respecting any smaller operator setting; named-person image calls remain capped at four. These additional supporting calls can increase model usage per longer job; CPU, memory and render concurrency are unchanged. Daily limits remain disabled as requested.

**254 Python tests passed.** Regressions cover missing real emu photos → reviewed AI image, rejected generated cubes → regeneration, acquisition of ten images under the bounded budget, exhausted cutouts with no symbols, missing exact/local maps with no invented geometry, and transient review recovery without another image prediction. No real new story generation has been submitted yet; mocked review acceptance is not a production visual-quality proof. The smoke tool now accepts an approved story file/target duration for a future single controlled test without resubmission after monitoring loss.

Relevant-image deployment: build `2c203d35-2adf-401c-97f5-9706eabbe8fd`, ready revision **`project-her-00018-2vp`**. The guard paused new admission immediately before deployment, found zero unfinished jobs, and reopened the studio. No portfolio publish is needed. The old downloaded Emu War MP4 is not modified by a backend deployment; a new generation is required to evaluate the replacements on that story.

## Emu story test outcome and measured timing correction

Exactly one Emu War regeneration was explicitly approved and submitted through the live studio: job `ab171d59dbad4784b9742e615db9029d`. It failed during narration/word alignment with `Zero-duration aligned word: eliminate`, before visual acquisition. Thus no corrected full Emu video or production image-review success is claimed for that attempt. Evidence: `output/emu-relevant-visuals-smoke/smoke.json` and `temp/emu-visual-audit/live-story-test.log`.

The already-paid speech clip was recovered read-only before its provider output fields expired. Its actual text was “Their mission was simple: eliminate the emu population.” The colon consumed the following spoken word's interval in known-script DTW; changing filter widths/padding did not repair it. Local transcription correctly recognized all words and measured eliminate at **1.88–2.34 seconds**. A tested fallback now requires the complete recognized lexical token sequence to match the approved script (allowing capitalization/boundary-punctuation differences), reliable finite nonzero ordered intervals, and audible signal per word. It restores the exact original display tokens, including `simple:`. It does not distribute timestamps evenly, skip unspoken/missing words, fabricate silence timings or request new speech. Provenance is explicitly `whisper_transcribed`; generated Python/Remotion contracts are updated.

The exact failed audio passed the correction offline, with its original script tokens and measured timing preserved. Evidence: `temp/emu-visual-audit/recovered-real-alignment.json` and saved clip/text. Other provider input/output fields were no longer available for recovering all companion clips; no complete-story timing proof is claimed from that partial recovery. **259 Python tests and Remotion TypeScript passed**, including mismatch/zero/silence rejection. No further paid generation or prediction was submitted during this diagnosis.

Additional user changes appeared while work continued: commits `b8ad0c0` (operator maintenance controls) and `cbaa115` (cutout baseline/noise/fade handling). They are preserved. The timing patch's immutable image ancestry was verified against the then-ready `project-her-00022-qqg`, rather than deploying over it from an older base. A foreign maintenance lock from 22:45 IST (17:15 UTC) was verified stale: no active builds, no live render leases, unchanged ready revision and unchanged policy update/owner. It was conditionally taken over, drained and cleared without resetting daily/emergency policy.

Timing correction deployment: build `0a1230b5-25b8-49db-b8b4-43ad678a8c3b`, ready revision **`project-her-00023-l7s`**. No-placeholder imagery, subject/era review, 24 supporting-call ceiling and the newer cutout fixes remain in the image. Daily limits remain disabled. A new full Emu story generation needs a separate paid-test approval; the previous one was consumed by the failed attempt above.

Post-deployment readiness initially exposed a separate configuration loss on the newer Cloud Run service: all eleven native environment settings were absent, including bucket/project, enabled/legacy lock, origins, alignment settings and admission limits. Provider/signing/operator bindings and 2 CPU/4Gi warm-instance settings were still present. Those required non-secret native settings were restored using `--update-env-vars` under the drain guard, preserving provider values, daily-limit override and resources.

Final ready revision: **`project-her-00024-ncj`**, with the timing-patched image from revision 23 and the newer cutout code. Actual GET `/api/portfolio/config`: **HTTP 200, enabled=true, daily_limits_disabled=true, concurrency=1**. Unauthenticated legacy `/api/settings`: **HTTP 401**. No additional generation or prediction was created by these checks. Future deployments should use the checked-in `scripts/deploy_native_portfolio.py --approve-cloud-changes`, which applies required native settings with update semantics; replacing the service's environment with a partial `--set-env-vars` list can remove them again.

The user chose **“I’ll test it myself”** for the fresh Emu War generation after these corrections. No second controlled story job was submitted by this agent. Full corrected-story imagery/playback remains for that manual test; the earlier approved story test remains recorded as failed before images, and the repaired actual speech clip is verified offline. Do not claim a completed corrected Emu War MP4 until that manual test succeeds.
