# Editorial generation latency

The native News/Editorial path previously did three long media phases in sequence: Replicate speech, image sourcing/cutouts, then word alignment. Saved local manifests show examples of 60-second stories taking 706–725 seconds end to end. In those examples narration took 188–245 seconds, cutouts 236–331 seconds, and composition about 64–70 seconds. These are observed historical jobs, not a guarantee for every provider or story.

After script and visual approval, cutout sourcing now runs alongside speech generation. Both results must finish before the same Whisper word alignment, image manifest validation, and Remotion rendering begin. Whisper is deliberately kept after cutouts to avoid loading both inference models at once on the 4 GiB Cloud Run worker. The workspace displays one truthful “Generating narration and cutouts” stage while this happens. `editorial_manifest.json` records `diagnostics.mediaTimings` (`speechSeconds`, `cutoutsSeconds`, `overlapSeconds`, `wallSeconds`) and `diagnostics.stageTimings` for comparison with earlier jobs.

Replicate speech for scripts with at least four distinct uncached sentences uses at most two HTTP workers. The global 12-second prediction admission pacing, provider retries, exact model/voice/speed inputs, cache key, per-sentence audio conversion, sentence order, and subsequent word alignment are unchanged. Identical sentences in a job share one prediction. `NEWS_REPLICATE_TTS_WORKERS=1` disables this speech overlap if provider throttling warrants it; the default is 2 and the maximum is 2. The image selection, likeness review, retries, alpha cutouts, render resolution/CRF, and final audio/video quality gates are unchanged.

The expected saving is primarily the portion of speech generation that overlaps cutout sourcing, plus any remote speech latency hidden by the second paced worker. Provider throttling, an image retry, cold starts, and unusually long scripts can still exceed ten minutes. A production timing claim requires a newly generated job after manual deployment. Do not use a previous job's cached result to measure cold-generation speed.

Validation without paid provider calls:

```sh
cd /Users/klinten/Desktop/My-projects/project-HER
.venv/bin/python -m unittest tests.test_editorial tests.test_news_tts tests.test_news tests.test_portfolio_api tests.test_editorial_visuals tests.test_visual_director -q
```

Manual backend rollout, after review:

```sh
.venv/bin/python scripts/deploy_native_portfolio.py
.venv/bin/python scripts/deploy_native_portfolio.py --approve-cloud-changes
```

The static klinteng.com studio consumes stage labels from the API, so this backend optimization does not require a website publication.
