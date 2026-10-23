# Generation review — 23 October 2026

## Measured production evidence

Read Cloud Run logs and service configuration and the durable Firestore job record. Inspected the portfolio client at `../my-website/js/project-her-{client,studio}.js`. No production configuration, deployment, job submission or existing output was changed.

| Item | Observed |
|---|---|
| Job | `6e7526929bdd4974a99b12dc23de0a63` |
| Story | King Erysichthon cuts down Demeter's sacred oak and receives endless hunger |
| Created | 23 October 2026, 22:30:58.541 IST |
| Completed | 23 October 2026, 22:51:56.497 IST |
| Elapsed | **1,257.956 seconds / 20 minutes 58 seconds** |
| Output | 68.2 seconds, 1080 × 1920 |
| Ready revision inspected | `project-her-00039-8xq` |
| Capacity | 2 CPU, 4 GiB, minimum/maximum instances 1, CPU throttling disabled |

The portfolio uses SSE and fallback polling, normally every three seconds. The backend record itself takes 21 minutes; browser progress polling does not explain that delay. Increasing HTTP concurrency (currently 20) does not make one rendering job parallel: application admission permits one job, and the cloud worker forces one render tab.

Observed during this run: Gemini HTTP 503 high-demand retries at 22:38:35, 22:39:06 and 22:41:53 IST. Background-removal model download started at 22:41:08 and finished at 22:41:15 (about seven seconds). Downloading the model is avoidable but cannot explain 21 minutes. Roughly 610 seconds had already elapsed by the first logged model download; this is a timeline marker, **not a measured stage boundary**.

The previous worker did not retain stage history in Firestore. Its detailed local manifests and render logs are deleted by job cleanup, and its spawned process did not initialize INFO-level logging. Therefore exact script / speech / alignment / images / rendering totals for this old job cannot honestly be reconstructed. The five-image count comes from the user's review; the retained job record does not store the asset manifest. The deployed service snapshot is current configuration, not proof of every historical setting.

A read-only request using the local Replicate credential returned HTTP 403. Automatic approval review rejected accessing the production credential for further timing inspection; no production secret was retrieved. Provider prediction-level breakdown remains unavailable.

## Implemented fixes

- **Image throughput:** two concurrent asset workers overlap remote generation, retrieval and review. Segmentation remains serialized to bound memory. Shared image-call budgets are locked; results preserve narration order. First failure stops queued work and signals in-flight generation cancellation. No quality checks, call ceilings or identity requirements are removed. Per-asset elapsed times are recorded.
- **Inference:** cloud defaults cap OpenMP to two threads and use two configurable Whisper CPU threads, matching the existing CPU allocation. The image build preloads configured segmentation models rather than downloading them on the first request after a new revision.
- **Provider overload:** News/editorial LLM requests use a 45-second request timeout and a shared 90-second retry budget across model fallbacks, instead of repeatedly granting each fallback 90 seconds. This bounds retries; it cannot eliminate provider outages or guarantee successful responses within the target.
- **Observability:** completed stage durations are retained in Firestore and emitted to Cloud Logging. The completed job retains stage timings, unique-asset count, asset worker count and per-asset elapsed times separately from public response data. INFO logging is enabled in the spawned cloud worker. No prompt, token or private media URL is added to timing logs.
- **Image diversity:** contextual planning targets one distinct subject per approximately 15 narration words, capped at 12. For 120–180 words this means approximately 8–12 story-relevant subjects, where supported. A sparse supported plan gets a repair pass to include omitted objects, settings and important actions. A supported plan is retained if expansion fails; no filler quota, invented events, duplicate poses or geometry placeholders are introduced. Existing named characters may reuse their images. Existing movement, size, effects, transitions and rendering choreography are unchanged.
- **Labels:** removed the renderer condition that hid an attached label while the same name appeared in editorial text. This condition made labels appear late despite correct timeline timestamps. Labels now remain visible with their parent and inherit its existing transforms and opacity.

## Deployment and the 2–3 minute target

The changes are local and tested, **not deployed**. No new paid video was generated. No 2–3 minute completion claim is established.

An explicit `--performance-profile` is prepared in `scripts/deploy_native_portfolio.py`. It uses 4 CPU / 8 GiB, two render tabs, three asset workers and four inference threads. The default rollout preserves existing CPU/RAM; the cloud worker now respects an explicitly configured render-tab limit. One admitted video job remains the limit. HTTP concurrency and the warm-instance settings remain unchanged. The performance profile increases both idle and active cloud cost.

Review the plan without changing cloud resources:

```sh
.venv/bin/python scripts/deploy_native_portfolio.py --performance-profile
```

After deployment/cost approval:

```sh
.venv/bin/python scripts/deploy_native_portfolio.py --performance-profile --approve-cloud-changes
```

The existing deployment guard drains unfinished jobs before changing revisions. Then, with approval for one paid test, generate the same 60–70-second narration once and inspect retained stage timings, output, all label entrances and story-specific image coverage. A 180-second total is the acceptance target, not a timeout that should discard longer legitimate jobs. If rendering still dominates, benchmark additional render capacity; if provider waits dominate, additional CPU will not fix them. Do not scale infrastructure blindly or claim speed from mocked tests.

Cloud Run request concurrency and Remotion rendering concurrency are separate controls: [Google Cloud concurrency documentation](https://docs.cloud.google.com/run/docs/about-concurrency), [Remotion render CLI](https://www.remotion.dev/docs/cli/render). No my-website change is required for these backend fixes. Existing MP4s retain their old labels/images; only newly generated outputs use the fixes.

## Verification

- Full offline Python suite: **270 tests passed**, including new concurrency/order, first-failure cancellation, atomic image budget, diversity repair retention, and shared retry-budget regressions.
- Remotion TypeScript check passed.
- Actual local Remotion frame rendered from existing reference-v2 assets at frame 70: the attached “Lord Shiva” label is visible while the main editorial phrase also says “Lord Shiva”. No provider request was made. Preview: `/tmp/her-label-fixed.png`.
- Deployment performance-profile dry-run and `git diff --check` passed.
- Local Remotion reports an existing Zod version warning; the frame render and TypeScript check still succeed. No dependency migration was included.
- Production end-to-end latency, increased-capacity memory behavior and story-specific image diversity remain to be measured after deployment.
