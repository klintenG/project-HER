# Project HER — agent guide (read this first)

Owner: Karthik (GitHub `klintenG`). Personal side project: narrated video generator.
Two parts: (1) public portfolio on GitHub Pages with a **Generate** button that calls this backend;
(2) **Autopilot**: generates one story video a day and posts it to Instagram/YouTube through Buffer.
Goal: run on Google Cloud at near-zero cost (stay inside Cloud Run's monthly free tier).

## Cloud facts (verified Oct 30–31, 2026)
- Project `project-her-510715`, region `us-central1`, billing account `0174E3-3D8051-717898` (was closed Oct 27, reopened).
- Web service `project-her`: 1 vCPU / 2 GiB, min instances 0, request-based CPU. Dispatches each visitor render to Cloud Run Job `her-portfolio-worker` (4 vCPU / 8 GiB).
- Jobs: `her-autopilot` (4 vCPU / 8 GiB, 3000 s, runs `generate` only), `her-autopilot-light` (1 vCPU / 2 GiB, 900 s, runs prepare/schedule/verify/retry), `her-portfolio-worker`.
- Cloud Scheduler: five jobs `her-autopilot-{generate,prepare,schedule,verify,retry}`, lean cron (13 starts/day, times in `scripts/apply_lean_autopilot.py`). **Currently PAUSED.** Resume with `python scripts/apply_lean_autopilot.py --resume` only when the owner says so.
- Free-tier model: 450,000 GiB-s/month on the 4 vCPU/8 GiB job = ~937 min/month = ~31 min/day. A 1 vCPU/2 GiB job counts a quarter. Every start bills >= 1 minute. `utils/compute_meter.py` meters usage in Firestore doc `her_portfolio/compute:YYYY-MM`; visitor renders are refused (HTTP 429, `/config` `enabled:false`) when Autopilot's daily video would no longer fit. Check real usage: `python scripts/compute_budget_report.py --days 7` (it undercounts short failed runs; do not trust it as exact yet).
- **No Terraform state exists** and Terraform is not installed. Resources were created outside Terraform. `deploy/autopilot/main.tf` is documentation only: **do not run `terraform apply`** (it would try to re-create existing resources). Use `scripts/apply_lean_autopilot.py` (dry run by default) and `scripts/deploy_native_portfolio.py` (`--approve-cloud-changes` makes real changes; without it only prints a plan).
- Live publishing flags on the jobs must stay `AUTOPILOT_ENABLED=true`, `BUFFER_DRY_RUN=false`, `AUTOPILOT_LIVE_VALIDATED=true`. The deploy script copies `.env` values into Cloud Run, so check `.env` before every deploy (`grep -E '^(AUTOPILOT_ENABLED|BUFFER_DRY_RUN|AUTOPILOT_LIVE_VALIDATED)=' .env`).
- Public config currently reports `daily_limits_disabled: true` (per-day cap on visitor renders is off). Ask the owner whether that is intended.

## Hard rules
1. **Never spend money without the owner's explicit OK**: no `gcloud run jobs execute`, no real generation, no resuming schedulers, no deploys with `--approve-cloud-changes`. Replicate calls cost credits.
2. Never print, log or commit secrets (`.env`, API keys, tokens). Do not paste env dumps. Redact before showing output.
3. No automatic paid replay: ambiguous job dispatch is never re-dispatched; Cloud Run job retries stay 0.
4. The worker jobs must not hold `BUFFER_API_KEY`, `AUTOPILOT_ADMIN_TOKEN` or `HER_OPERATOR_KEY` (the render worker only).
5. Keep the public API contract and the `her-autopilot` job/scheduler names unchanged.
6. Prefer the smallest change; keep tests green (`python -m pytest tests -q`). Known pre-existing failures when gradio/rembg are missing: test_editorial (2), test_news gradio dispatch, test_generation_performance rembg.

## Architecture in brief
- `agent/portfolio_api.py` — Flask API for the Generate button, quotas, dispatch to the worker job; `agent/portfolio_worker.py` — one render per job execution; `agent/portfolio_store.py` — Firestore (cloud) / SQLite (local).
- `automation/autopilot*.py`, `automation/autopilot_worker.py` — Autopilot actions (generate/prepare/schedule/verify/retry/dry-run/publish-now/pipeline). Publish window 18:00–19:00 IST.
- `utils/llm_client.py` — shared LLM factory; providers `gemini`, `groq`, `replicate` (new). `utils/replicate_llm.py` — Replicate adapter.
- Local rehearsal without Google Cloud: `HER_PORTFOLIO_LOCAL_WORKER=1` (see `docs/scale-to-zero-deployment.md`).

## State of the work
Done and deployed: scale-to-zero web service, per-render worker job, lean schedule, compute meter and visitor admission, light job, `scripts/apply_lean_autopilot.py`.

In progress — **replace Gemini with Replicate LLMs** (owner's request; Gemini returned `402 Payment Required`, so the first real `generate` run failed at the first LLM call):
- Patch `replicate-llm-provider.patch` adds `LLM_PROVIDER=replicate` (settings `REPLICATE_LLM_MODEL`, `REPLICATE_LLM_MAX_OUTPUT_TOKENS`, `REPLICATE_LLM_INPUT/OUTPUT_USD_PER_M`). Apply with `git am`. Tests: `tests/test_replicate_llm.py`.
- Default model is `meta/meta-llama-3-70b-instruct` (already used by Autopilot's story step, repo-configured price $0.65 in / $2.75 out per million tokens — verify at replicate.com/pricing). **Open questions to settle by measuring, not guessing:** its context window is small (~8k): `agent/news_script.py` asks for up to 6500 output tokens, which is capped to 4096 by default, so check scripts are not truncated; try cheaper/larger-context Replicate models via `REPLICATE_LLM_MODEL` (the adapter assumes the Llama-style input `prompt/system_prompt/max_tokens/temperature`; other models may need field changes); JSON-only steps rely on a prompt hint, `response_format` is not enforced by Replicate.
- **Gap:** `agent/editorial/vision.py` hard-codes `get_llm_client('gemini', ...)` for image review. It is text+image and the Replicate adapter is text-only. Decide with the owner: keep Gemini just for vision (needs a Gemini key with billing), skip vision review, or add a Replicate vision model.
- To activate on Cloud Run after the patch is deployed: set `LLM_PROVIDER=replicate` (and optionally `REPLICATE_LLM_MODEL`) on `her-autopilot`, `her-autopilot-light` and the service. `REPLICATE_API_TOKEN` is already bound from Secret Manager.

## Next steps, in order
1. Apply the Replicate patch, run tests, review the diff; look for any other hard-coded `'gemini'` use (`grep -rn "gemini" --include=*.py agent automation utils`).
2. Owner rotates the exposed Google/Pexels keys (they appeared in a pasted job dump) and updates `.env`; consider moving them to Secret Manager.
3. With owner approval: `python scripts/deploy_native_portfolio.py` (preview) then `--approve-cloud-changes`; set `LLM_PROVIDER=replicate` on the jobs.
4. With owner approval, run ONE manual `generate`: `gcloud run jobs execute her-autopilot --project project-her-510715 --region us-central1 --args="-m,automation.autopilot_worker,generate"`; read logs (filter FutureWarning noise) and measure wall time on 4 vCPU. Oct 25–26 logs showed Autopilot failing on its own before the outage: "Story model input ceiling reached", "Model did not return a complete schema-valid JSON document", "No strong unique story within candidate budget", "Editorial validation failed within revision budget", "Video quality gate failed: duration". Fix those with the owner.
5. Only after a successful video: resume schedulers, set the Autopilot ready-queue target to 2, run `compute_budget_report.py`, set `HER_COMPUTE_VISITOR_JOB_SECONDS` to the measured median render time.
6. Cleanup/tech debt: keys into Secret Manager; decide whether to import resources into Terraform with remote state; fix `compute_budget_report.py` undercounting failed runs; revisit `daily_limits_disabled`.

## How to work with the owner
Karthik wants progress, not command-by-command walkthroughs: make the change, run the tests, and give him the one command he must run (with what to paste back). Explain reasoning briefly. Ask only when a decision is genuinely his (money, publishing, deleting).
