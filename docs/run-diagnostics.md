# Deployed run diagnostics

Every newly admitted native portfolio generation gets a private diagnostic record in Firestore (`her_portfolio/diagnostic:<job_id>`). It survives worker cleanup and video expiry. The default retention is **14 days**, configurable with `HER_DIAGNOSTICS_DAYS` (1–90). The existing collection TTL on `delete_after` applies; the API enforces expiry even before Firestore deletes a record.

## Download from the deployed URL

Open this URL, replacing `JOB_ID` with the generation's job ID:

```
https://project-her-svnnlerw4q-uc.a.run.app/api/portfolio/operator/jobs/JOB_ID/diagnostics
```

The browser asks for username **operator** and the existing **HER_OPERATOR_KEY** password. This is the operator credential, not a visitor access token or a provider API key. It downloads `her-JOB_ID-diagnostics.json`. Add `?format=jsonl` to download a summary followed by one JSON event per line.

Alternatively, let curl prompt for the password so it stays out of shell history:

```sh
curl --fail --user operator \
  'https://project-her-svnnlerw4q-uc.a.run.app/api/portfolio/operator/jobs/JOB_ID/diagnostics' \
  --output run-diagnostics.json
```

This endpoint is always operator-protected, even if the optional legacy API lock is off. Existing visitor job tokens cannot access diagnostics. Responses use `Cache-Control: no-store`. No my-website changes are required; use the job ID returned by its generation request.

## What the report includes

- Job ID, Cloud Run revision, start/finish timestamps, status and total elapsed time.
- Stage start/completion/failure events and measured completed-stage durations.
- The slowest completed stage and last reported stage.
- Interrupted-stage marker for a worker stopped during a running stage. This does **not** invent the missing final duration.
- Known terminal failure category; handled exception type and safe file/function/line locations, when available. The pipeline can wrap an underlying error, so these locations may identify the wrapper rather than the provider's original exception.
- Provider warning metadata: component, severity, HTTP status where present, retry/fallback indicator and aggregate warning counts. A retry warning is not proof that another provider request succeeded.
- Final unique-image count, per-image elapsed seconds and worker settings when returned by the editorial pipeline.

All timestamps are Unix epoch seconds (UTC); durations are seconds. `observed_elapsed_seconds` updates when downloading an active run. `stage_seconds` measures stage wall time, not billed provider compute. Some stages include multiple operations: for example composition includes rendering/export validation. This is not yet a separate span for every internal function or provider request.

The report intentionally excludes submitted stories, image prompts, titles, raw provider responses/log messages, credentials, signed URLs, absolute paths and traceback locals. Provider warning buffers flush at stage callbacks and normal worker exit. A hard kill may lose warnings buffered since the last flush, but previously persisted stage events survive. Job transitions, including supervisor timeout/stopped-worker failures, are saved transactionally with job state. Event history is capped at 200; `dropped_events` identifies persisted history truncation. Provider warning buffers are also capped at 200.

For a run whose worker has just died, the existing supervisor/status check records terminal failure. A diagnostics download alone is read-only and does not declare an apparently stalled run dead. Old runs do not acquire missing historical stage timings retroactively.

## Deployment

Deploy the application code through the existing Cloud Run drain guard. No resource upgrade or paid test generation is needed to enable diagnostics. CPU/RAM settings and provider credentials should be preserved. The existing Firestore service-account permissions and collection TTL suffice; no public storage bucket or separate log-file server is needed.

Offline coverage includes successful runs, supervisor/stale-worker failures, expiry, authenticated JSON/JSONL downloads, visitor-token rejection, terminal-state protection, bounded events and sensitive-data exclusion. Production endpoint verification does not create a video.
