# Scale-to-zero deployment (portfolio studio + Autopilot)

Goal: keep the GitHub Pages "Generate" button and Buffer Autopilot working while
paying nothing when idle. Replaces the always-on 4 vCPU / 8 GiB instance
(~$223/month) that existed only because public renders ran inside the web instance.

## How it works

```
GitHub Pages ──POST /api/portfolio/jobs──► project-her (min 0, request-based CPU, 1 vCPU/2 GiB)
                                              reserve (quota, idempotency) → store private payload
                                              → RunJob(her-portfolio-worker, args=[job_id])   (synchronous)
                                                      ▼
                         her-portfolio-worker (Cloud Run Job, 4 vCPU/8 GiB, 0 retries, 3000 s)
                           claim (transaction) → heartbeat/watchdog → existing Runtime.execute
                           → private GCS media → Firestore status
GitHub Pages ──GET status / 55 s SSE / media tickets──► project-her (reads Firestore/GCS only)
```

Safety properties kept from the in-instance supervisor:

| Property | How |
|---|---|
| No paid replay | Client `retry=None`; ambiguous RunJob outcome is never re-dispatched; worker claim makes a duplicate execution a no-op |
| Definite dispatch failure | `PermissionDenied`/`NotFound`/… → job `failed`, slot released, "No model work was submitted" |
| Cold start | Queued+dispatched jobs get `HER_PORTFOLIO_START_GRACE` (900 s) before stale failure; running jobs keep the 120 s heartbeat rule |
| Cancellation | Cooperative via the durable flag; watchdog hard-stops descendants 20 s after an ignored cancel |
| Deadline | Watchdog marks `failed` and exits at the job deadline |
| Concurrency | Global slot held from dispatch through cold start; released on every terminal path |
| Input privacy | `payload:<id>` document has the job's TTL and is overwritten with `{consumed: true}` on claim |

`HER_PORTFOLIO_WORKER_JOB` unset ⇒ previous behaviour (thread/child process in the instance).

## Deploy

```sh
# 1. Billing: create a budget + alerts first, then reopen the billing account.
# 2. Review the plan (dry run), then apply.
python scripts/deploy_native_portfolio.py
python scripts/deploy_native_portfolio.py --approve-cloud-changes            # job executor (default)
#   options: --daily-limit 2 --visitor-limit 1 --service-memory 4Gi --worker-memory 8Gi
#   rollback: --executor instance  (always-on; billed 24/7)
```

The script deploys the service, then (still inside the drain guard, so admissions
stay paused) creates/updates `her-portfolio-worker` from the same image, copies
the service's env/secret bindings, and grants the service account
`roles/run.jobsExecutorWithOverrides` on that Job only.

## Autopilot (Buffer) scheduling

Keep `her-autopilot` at 4 vCPU / 8 GiB, but stop starting it every 10 minutes.
Each Job execution bills at least one minute plus a multi-GB image start.

| Time (IST) | Job | Action |
|---|---|---|
| 09:00 | `her-autopilot` (4/8) | generate + prepare (or `pipeline`, if it chains them) |
| 16:45 | `her-autopilot-light` (1 vCPU / 2 GiB) | schedule (Buffer posts at 18:30) |
| 17:30 | `her-autopilot-light` | retry |
| 21:00 | `her-autopilot-light` | verify |

Make the change in the Terraform scheduler variables so it doesn't drift.

## Validate

1. `curl -s -H 'Origin: https://klinteng.com' $SERVICE/api/portfolio/config` → `"enabled": true`. The first call after idle is a cold start.
2. One submission from the site → `gcloud run jobs executions list --job her-portfolio-worker --region us-central1` shows **exactly one** execution.
3. Progress advances on the site; video plays and downloads.
4. Cancel mid-render → execution ends within ~20 s; job `cancelled`.
5. After 48 h, the billing report has no always-allocated Cloud Run CPU SKU.

## Debugging

| Symptom | Check |
|---|---|
| Job `failed` immediately, "No model work was submitted" | Service account lacks `run.jobsExecutorWithOverrides` on the Job, or the Job name/region env is wrong (service logs: `Portfolio dispatch rejected`) |
| Stuck `queued`, then failed after ~15 min | Execution never started: check executions list, image pull, quota; service logs `dispatch outcome unknown` |
| Worker exits "already claimed" | Duplicate execution; harmless |
| Worker OOM | Keep 8 GiB (4 GiB OOM'd historically) |
| Web service OOM on start | Raise `--service-memory 4Gi`; still ~$0 idle |
