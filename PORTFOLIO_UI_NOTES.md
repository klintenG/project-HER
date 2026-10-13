# Creator UX update — 13 October 2026

The portfolio now has an owner-approved local HER output with original-input provenance, transcript and captions. The fixed portfolio/case-study link and no-cost sample link in the creator complete the navigation journey. Publish the portfolio changes before releasing the sample link.

`templates/index.html` keeps the existing News/reference-editorial default. Unmodified inputs still submit `ui_profile: editorial_studio` with the exact server defaults. Basic/advanced settings use the existing API fields; customized requests submit `ui_profile: creator`, which passes through the existing backend contract without changing generation code. Reference editorial checks Remotion/vertical compatibility before submission. All legacy controls remain in `/classic`.

New UI behavior: keyboard-accessible example buttons and Advanced disclosure, visible labels/help/limits, safe fixed return link, accurate renderer label, persistent failure/quota/cancelled states, no invented polling stages, no autoplay, and output/download gated on a safe same-origin URL plus playable metadata. Captured idle/completion states in browser tests use explicitly intercepted fixtures, not real generated jobs.

Only `web_ui.py`'s page context gains the configured visitor/day caps for display. Default profiles, pipeline, provider calls, SSE/polling routes, cancellation backend, deployment settings and secrets are unchanged. No paid APIs or render jobs were executed for the UX update.

Offline regression commands:

```sh
PYTHONPYCACHEPREFIX=/private/tmp/her-portfolio-pycache .venv/bin/python -m unittest discover -s tests
remotion/node_modules/.bin/tsc --noEmit -p remotion/tsconfig.json
# Start the local Flask app at 127.0.0.1:7861; browser API requests are intercepted.
PUPPETEER_MODULE=/absolute/path/to/puppeteer-core.js \
HER_SAMPLE_PATH=/absolute/path/to/approved/editorial-remotion.mp4 \
HER_SITE_URL=http://127.0.0.1:7861 node tests/browser-creator.mjs
```

The browser suite covers 320, 375, 430, 768, 1024 and 1440px; default/custom request fields; incompatible-format validation; SSE stages; real fixture MP4 metadata; invalid-artifact rejection; quota and cancellation; keyboard/focus and reduced motion. It prevents all real API requests. The sample fixture is the approved MP4 supplied by the owner.

Outstanding backend work: durable jobs/results/shared quotas, trusted client-IP handling, input/spend budgets and preview cost controls. Existing in-memory protections reset on restart and are not distributed enforcement. Do not claim live generation or cloud-resource validation from local tests. Use the existing Docker/Cloud Run deployment procedure, preserving current resource configuration; no deployment was performed here.
Final verification: 208 offline Python tests passed; Remotion TypeScript check passed; browser fixture suite passed at 320/375/430/768/1024/1440px with 30 intercepted submissions and no real jobs; JavaScript syntax and git diff whitespace checks passed. Screenshots are /private/tmp/her-creator-qa/creator-idle-375.png and creator-idle-1440.png. Portfolio playback, captions, seeking, byte-identical sample copy and deferred loading passed. No deployment occurred.
