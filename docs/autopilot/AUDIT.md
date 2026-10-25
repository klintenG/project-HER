# ProjectHER Autopilot technical audit

Inspected 2026-10-25 before implementation. Working tree was clean.

- Flask `web_ui.py` is the Cloud Run entry point (`project-her-510715`, service `project-her`, region `us-central1`); Gradio `app.py` and Click `main.py` are additional interfaces. Preserve all three and their manual modes.
- `AgentOrchestrator.run` dispatches the working AI image/story splitter/narration/effects/Remotion pipeline; News/reference editorial has its own existing dispatch. Use its supplied-story `reference_editorial` route for Autopilot to retain the current studio quality rather than presenting fiction as researched news.
- `agent/ai_visuals.py` uses the configured Replicate REST client conventions, bearer token and prediction polling, with existing provider fallbacks. Do not alter active image models. General analysis currently uses Gemini/Groq via `utils/llm_client.py`.
- `automation/daily_pipeline.py` already curates stories and calls the actual orchestrator. Its JSON history, randomized server-local scheduling and manual/browser publishing do not provide cloud-safe idempotency or Buffer publishing.
- `agent/portfolio_store.py` supplies transactional SQLite (local) and Firestore (cloud), plus private GCS media. Reuse its record stores with a separate namespace. Private portfolio media tickets are unsuitable for Buffer; use a separate publishable bucket.
- `agent/portfolio_api.py` demonstrates detached Cloud Run Job execution and scoped authorization. New Autopilot admin routes require their own backend bearer secret and do not inherit anonymous generation access.
- Remotion writes `remotion_props.json`, stages generated assets, renders H.264 and exports captions. Its protective floating overlay uses `ProjectHERBrandMark`, also used by the corner logo, credit and outro. Change only the protective overlay text; preserve timing, mask, opacity, geometry and closing SVG.
- Docker already installs ffmpeg, Chromium, Node, Firestore/GCS dependencies and Remotion. Cloud Scheduler must execute recoverable jobs, not start long rendering inside HTTP requests.

Implementation sequence: durable config/registry and budgeted story director; optional hook in the existing renderer plus shared floating watermark; deterministic media gates and frame export; current Buffer GraphQL adapter and per-platform durable attempts; worker entry point and authenticated administration; focused regression/resilience tests and operational documentation. Keep Autopilot disabled and Buffer dry-run enabled until real platform publications have been verified. Live provider verification is distinct from offline tests.
