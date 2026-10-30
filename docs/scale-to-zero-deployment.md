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

## Free-tier budget: ~31 heavy minutes a day

Cloud Run's monthly free tier for Jobs is 240,000 vCPU-seconds and 450,000 GiB-seconds per
billing account. On the 4 vCPU / 8 GiB render job memory runs out first:
450,000 / 8 = 56,250 s = 937 minutes a month = **about 31 minutes a day**. A 1 vCPU / 2 GiB job
counts a quarter as much per minute. Every start bills at least one minute.

### What changed to fit
| Change | Why |
|---|---|
| `autopilot_schedules` variable, lean defaults (see below) | The original schedule started the 4 vCPU job 68 times a day |
| `prepare` runs on `her-autopilot-light` | It only re-uploads an already validated MP4 (recovery step); it never renders |
| `render_timeout_seconds` = 3000 (was 7200) | A hung 2-hour render would burn about four days of free minutes |
| Shared compute meter (`utils/compute_meter.py`) | Every Job execution adds its billed, weighted seconds to `compute:<YYYY-MM>` in Firestore |
| Visitor admission uses the meter | A visitor render is admitted only if the pool still covers Autopilot's expected need for the rest of the month plus the render |
| `scripts/compute_budget_report.py` | Reads real executions from Cloud Run and compares them with the free tier |

Default schedule (IST, set `autopilot_schedules` in tfvars to change):

| Step | Cron | Starts/day | Job |
|---|---|---|---|
| generate | `0 9,13 * * *` | 2 | `her-autopilot` (4 vCPU / 8 GiB). Renders one story per run; exits cheaply with `queue_full` when stocked |
| prepare | `10 10,14 * * *` | 2 | `her-autopilot-light` |
| schedule | `0 16,17,18 * * *` | 3 | `her-autopilot-light` |
| retry | `5,20,35,50 18 * * *` | 4 | `her-autopilot-light` (dense inside the 18:00-19:00 window; needs >= 5 min lead) |
| verify | `10 19,21 * * *` | 2 | `her-autopilot-light` (`retry` already verifies first) |

That is 13 starts/day (was 68). Start overhead is about 4 heavy-minutes/day, so the daily budget is
roughly `render time + 4 minutes` against 31.

### What fits (estimates; measure with the report script)
| Median render | Autopilot per day | Left for visitors per month | Visitor videos per month (25 min each, conservative) |
|---|---|---|---|
| 10 min | ~14 min | ~520 min | ~20 |
| 15 min | ~19 min | ~370 min | ~14 |
| 20 min | ~24 min | ~220 min | ~8 |
| 25 min | ~29 min | ~65 min | ~2 |
| 27+ min | at or over budget | none | none: reduce render time or accept a small overage |

The only measured render in the repo (docs/generation-performance-review.md) took 21 minutes on 2 CPU / 4 GiB.
The 4 vCPU / 8 GiB time is **not measured yet**. Treat the table as a model until `compute_budget_report.py` shows real numbers.

### Keep the ready queue small
Steady state renders one video a day whatever the queue target is, but a target of 3 means three renders
while the queue first fills. Set the Autopilot ready queue target to **2** (dashboard setting or
`AUTOPILOT_READY_QUEUE_TARGET`): one day of cushion if a render fails, one extra render once.

### Visitor admission (HER_COMPUTE_BUDGET=1)
```
headroom = pool(56,250) - used_this_month - days_left_in_month x 1,500   # Autopilot reserve
admit a visitor render only if headroom >= 1,500 (assumed visitor render, in heavy-seconds)
```
Tunable: `HER_COMPUTE_POOL_SECONDS`, `HER_COMPUTE_AUTOPILOT_DAILY_SECONDS`, `HER_COMPUTE_VISITOR_JOB_SECONDS`
(set it to the measured median render). When closed, `/api/portfolio/config` returns `enabled: false` and
`compute_budget_open: false`, and new submissions get HTTP 429. Existing jobs and resubmissions are untouched.
The month is the UTC calendar month; Google's billing month follows Pacific time, so expect a few hours of skew.
Operator override: set `compute_budget_disabled: true` on the Firestore `her_portfolio/policy` document
(you accept paid minutes, about $0.16 per render), or redeploy with `HER_COMPUTE_BUDGET=0`.

### Check reality
```sh
python scripts/compute_budget_report.py --days 30     # read-only; needs gcloud access
```
It prints per-day pool usage, the median render duration (use it for `HER_COMPUTE_VISITOR_JOB_SECONDS`) and
a verdict. The Cloud Billing report remains the source of truth.

### Limits of this design
* The meter is for admission control, not billing. It estimates startup time and cannot see other workloads in the same billing account.
* If Firestore is unreachable, metering is skipped (jobs never fail because of it), so usage is under-counted.
* Failed renders still cost minutes. Provider outages on bad days can double the day's render time (generate runs twice).
* Request-based web service CPU has its own free tier (180,000 vCPU-s, 2 million requests); the web tier is far below it.

## Local rehearsal (no Google Cloud)

`HER_PORTFOLIO_LOCAL_WORKER=1` makes the local server dispatch each job to the real
`agent.portfolio_worker` as a separate process, sharing the SQLite store. It exercises
dispatch, the transactional claim, heartbeats and slot release. Providers are real,
so a generation spends provider credits; Google Cloud is not used.

```sh
export HER_PORTFOLIO_ENABLED=1 HER_PORTFOLIO_LOCAL_WORKER=1 PORT=8765
export HER_PORTFOLIO_SIGNING_KEY=$(python3 -c "import secrets;print(secrets.token_urlsafe(48))")
export HER_PORTFOLIO_LOCAL_DIR=$PWD/temp/rehearsal HER_PORTFOLIO_DAILY_LIMIT=5 HER_PORTFOLIO_VISITOR_LIMIT=5
python web_ui.py
# in another shell; Origin must be an allowed local origin (http://localhost:8766):
curl -s -X POST localhost:8765/api/portfolio/jobs -H 'Origin: http://localhost:8766' \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: local-rehearsal-key-0001' \
  -d '{"text":"A fictional red cup stands on a table."}'
```

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
