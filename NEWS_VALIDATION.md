# News implementation validation — 2026-10-11

The integrated News pipeline and both render backends were exercised in this workspace. This is implementation validation, not a claim of production readiness or universal image/provider quality. Existing daily-publishing files were not changed. `PROJECT_DOCUMENTATION.md` was read as a project map and left intact.

## Automated checks actually run

- `python -m unittest discover -s tests -v`: **100 passed**, with deterministic evidence, LLM, image and audio fixtures; no paid services required. Covers URL body/metadata and verbatim claims, dated topic retrieval, ambiguity choices, supplied fiction without invented aftermath, missing research, independent script review with bounded repair, malicious instructions as data, DNS pinning/redirect validation/internal address rejection, bounded failed candidates, alpha/margin/component QA, preservation of white clothing and full-body feet, segmentation failures, cache reuse, sentence-only/native timing and pauses, shared contract failures, six templates, persistent subjects, square/landscape adaptation, long names, Devanagari glyphs, pre-clip safe-zone pixels, every-frame geometry, optional music, isolated concurrent News jobs, cancellation, Flask/Gradio/CLI routing and existing mode/default routing. Added Serper coverage verifies authenticated POST format/result normalization, missing-key failures, quota/malformed responses without credential leakage, and rejection of authenticated API redirects. The 23 News speech tests cover quota/partial/corrupt audio recovery, consistent complete narration, missing credentials, all-provider failure, session cleanup, language routing, bounded models/input size, validated cache reuse, cancellation, throttled-request reset handling and remote prediction timeout cancellation.
- `remotion/node_modules/.bin/tsc --noEmit -p remotion`: passed.
- `node remotion/check-news-contract.cjs`: Python fixture accepted; five malformed manifest variants rejected by Zod/hash validation.
- Python compile checks for the changed application/modules/scripts/tests: passed.
- `git diff --check`: passed.
- Gradio 4 imported and its News function dispatched with mocked orchestration; compatible HF SDK pin verified locally. This does not substitute for an interactive browser session.

Local warnings: Apple's Python 3.9 SSL build reports urllib3's LibreSSL warning; Gradio/FastAPI report upstream deprecations. These did not prevent the checks or live HTTPS retrieval. Docker build, Cloud Run deployment and full legacy paid-provider generation were not run.

## News speech fallback validation

Verified the current input schemas through Replicate's authenticated read-only model API and pinned Kokoro and Chatterbox Turbo versions. Live 83-character Argentina World Cup speech samples succeeded:

- `output/news_tts_validation/google_tts/news_narration.wav`: **7.150 seconds**, live Kokoro after an explicitly simulated Google quota exception. The manifest records `replicate`, the Kokoro model, one fallback reason and sentence-only timing.
- `output/news_tts_validation/chatterbox_turbo/news_narration.wav`: **5.200 seconds**, live Chatterbox Turbo, sentence-only timing. An initial connection interruption created no prediction (confirmed by read-only prediction history); a subsequent explicit validation request succeeded.
- `output/news_tts_validation/recovered_video/news.mp4`: **1080×1920, 14.600 seconds, H.264/AAC**. Reuses the previously reviewed Trump/Odysseus script and existing live images. Google failure was simulated; Replicate actually returned HTTP 429 after one cached sentence, and the complete narration recovered through live Edge TTS. All three final sentence clips use Edge, with 28 validated native word boundaries. This demonstrates the full fallback chain and rendering without extra image generation. The new bounded 429 reset wait was added after this run and tested with mocked HTTP responses; no claim of a live throttle-reset recovery.

`ffprobe` verified audio/video durations and the recovered manifest passed the shared Zod/hash checks. No numerical listening-quality ranking was measured. Both models are exposed in the News selector, while Kokoro remains the low-cost default fallback. Published Replicate prices checked on 2026-10-11: Kokoro approximately $0.00031/prediction (variable runtime/input), Chatterbox Turbo $0.025/1,000 input characters. Actual invoice totals were not retrieved. Cached WAVs, complete per-provider attempt folders and fallback metadata are retained for review.

## Offline render fixtures

`python scripts/render_news_fixture.py --renderer both` produced actual H.264/AAC MP4s at **1080×1920, 30 FPS**:

| Output | Video duration | Audio/container notes |
| --- | --- | --- |
| `output/news_validation/fixture_moviepy.mp4` | 13.100 s | Audio 13.080 s; container 13.100 s |
| `output/news_validation/fixture_remotion.mp4` | 13.100 s | AAC duration 13.163 s/container; packet padding extends slightly beyond final video frame |

These use explicitly fictional supplied evidence, deterministic LLM responses, drawn RGBA scientist/diamond/microscope subjects, and synthetic word pulses with known boundaries. **There is no spoken TTS or live image generation in these fixtures.** They exercise two → three → one → text beats, progressive grey text, persistent identity and rebalancing, transitions, true transparent silhouettes, shadows and the portrait lower fade. Full details are in `output/news_validation/news_manifest.json` and `subtitles.srt`.

Representative actual decoded Remotion frames, including first/last frames and transition boundaries, are in `output/news_validation/actual-remotion-*.png`; `remotion-contact.png` is a review sheet. MoviePy frames from the same manifest are `frame-*.png`. Review corrected unstable progressive phrase matching and the Pillow lowercase baseline before the final render. Geometry and pixel checks inspect foreground before the final safe mask, so clipping does not hide failed layout checks.

All decoded frames were also compared with their blank first frame in the reserved top/bottom zones at 270×480 review resolution: 393 frames per fixture, 307 live frames, no pixels with a color difference above 20/255. Maximum differences were 0–3/255 from H.264 compression. Results are saved in `decoded_safe_zone_checks.json`.

`output/news_validation/hindi-remotion.png` is an actual Remotion frame with shaped Devanagari text from the bundled Poppins font. Its props use silent Studio fixture audio; this is a typography check, not a live Hindi speech run. MoviePy Hindi explicitly fails on this machine's Pillow build without libraqm rather than drawing broken text.

Legacy controls were also rendered: `output/news_validation/legacy/legacy_moviepy.mp4` (ordinary article compositor with fixture media, 270×480/15 FPS, about 8.49 s) and `legacy_remotion.mp4` (existing ProjectHER default Article composition, 30 frames at quarter scale). Existing article/deep-dive/thought-experiment/ghost-collab/kids-story routing and omitted-mode defaults pass automated checks; these renders do not verify every older mode against every external provider.

## Successful live-provider sample

`output/news_live_validation/news.mp4` is an actual **1080×1920, 30 FPS, H.264/AAC** MoviePy result: video/container **10.233 s**, narration **10.210 s**.

Input was explicitly fictional: a tiger approached a boy near a village; the boy stood still, the tiger left, nobody was injured, and the date was unspecified. It deliberately tested a usable supplied account without invented hospital/rescue scenes or a false claim of independent news verification. The final narration identifies the fictional basis and remains 24 words rather than filling 55 seconds.

Stages exercised with real services/resources:

- Configured Gemini classification/evidence/script and evidence review.
- Configured Replicate image generation for separate tiger, generic boy and village subjects.
- Real CPU rembg/ISNet segmentation of opaque provider output into RGBA PNGs, followed by mask QA.
- Real Google TTS sentence clips, FFprobe duration measurement, concatenated WAV and SRT.
- Shared semantic layout/timeline and actual MoviePy H.264/AAC composition.

Manual review found an initial boy silhouette with unwanted edging and a seated tiger that did not express the narrated approach. Those assets were regenerated with more precise appearance/action prompts; final assets and fallback reasons are recorded in `news_manifest.json`. The detached-component gate was tightened after review. Provider output still varies and may retain thin generated edge artifacts; numerical mask QA cannot prove an exact identity, anatomy or perfect fur/glass edges. This sample involved manual quality corrections, not a claim that every generated asset passes unattended.

Google TTS does not supply native word timestamps here. The manifest correctly reports **`sentence_clips`** and uses real phrase boundaries; its word list is empty. Live word-level speech alignment was not verified. The final sample's `thumbnail.jpg`, `news_preview.json`, `news_evidence.json` and `news_storyboard_plan.json` reflect the reviewed assets/script; an earlier failed attempt is retained separately as `news_prior_attempt_failure.json`.

A separate opaque white-coat segmentation check is saved at `output/news_segmentation_validation/opaque_source.png` and `real_segmented.png`. Real ISNet produced useful transparency (coverage about 0.552, transparent margin about 0.041) while preserving white clothing. The diamond fixture proves transparent-object compositing and QA structure; a live reflective diamond segmentation run was not performed.

## Successful live URL preview and unverified integrations

The pipeline securely fetched the actual [2024 Nobel Physics press release](https://www.nobelprize.org/prizes/physics/2024/press-release/) and produced a live evidence/script preview with **four linked claims** and resolved event date **2024-10-08**. Saved at `output/news_validation/live_url_preview.json`. This validates article-body retrieval plus the real LLM path, not search corroboration or a rendered Nobel video. Missing publication metadata was kept null.

The reported `Claim excerpt must occur verbatim in its source` error was reproduced structurally with a paraphrased quote. Extraction now selects indexed source passages and copies the original text in the backend, with bounded repair for invalid output. The user's exact query, **“Argentina winning the 2022 FIFA World Cup”**, passed a live Serper/LLM preview after the fix: two readable sources, two claims with exact source excerpts, resolved date **2022-12-18**, and three script sentences that passed independent evidence review. Saved at `output/news_validation/argentina_2022_preview.json`. No image generation or new video render was needed to validate this research-stage fix. Regression checks cover Unicode/whitespace preservation, quote repair, rejection of changed scores and invalid/nonconsecutive passage IDs, ambiguity preservation, and clean HTTP 422 errors after exhausted repairs.

- **Serper:** replaced the original search adapter and configuration at the user's request. A live authenticated search returned six normalized organic results for the 2024 Nobel Physics query, and the secure article retriever read 704 words from the primary press-release result. Saved without credentials at `output/news_validation/serper_live_check.json`. The original URL preview predates this migration and remains a `single_source` preview; the Serper check verifies search plus article retrieval, not a new multi-source script/video. The supplied key is stored only in the ignored local `.env` as `SERPER_API_KEY`, not in source/example files or browser code.
- **Hugging Face/Pollinations:** current official APIs checked; News adapters/configuration implemented. Replicate succeeded, so those fallback paths were not exercised live. Their account/model access remains to be verified with appropriate credentials/credits.
- **Edge/ElevenLabs/Kokoro:** existing adapters reused and actual-vs-estimated timing behavior audited. Native timing validation is fixture tested; the live sample used Google. Live native-word precision across speech providers was not measured.
- **Model license:** pinned release/runtime/download/checksum verified and real segmentation succeeded. Library and upstream project license scope is documented in [README_NEWS.md](README_NEWS.md); a separate license statement for the distributed ONNX weights was not found. Redistribution/commercial deployment terms remain to be confirmed rather than inferred from rembg's MIT license.
- **Visual reference:** the written paper/cutout/grey-type requirements were implemented and reviewed. No reference screenshots were attached in this workspace request, so an exact screenshot or font match is unverified.

Sample output/model caches are intentionally ignored by Git; the local paths above exist in this workspace. The fixture script and tests regenerate routine artifacts without paid APIs. Fonts, license, manifest schema/types and the self-contained Studio placeholder are source assets.

Terminal logging regression checks verify returned failures and unexpected exceptions in News and legacy workers, matching UI/polling/SSE error delivery, job/stage context, generation validation errors, preview errors, and preservation of tracebacks when News converts an unexpected exception into a failed result. All seven logging tests passed as part of the 76-test suite.

The reported France-team cutout failure was reproduced from the saved raw asset in `output/news_a2b85f6e34364b0bbc6396a2345d1303/`. ISNet removed the field, but a legitimate detached player triggered the single-subject component gate. The original segmented image now passes explicit-group QA while failing single-subject QA. Its original uniforms were visually unsuitable for association football; the revised prompt was separately checked with one live Replicate image and real ISNet segmentation. `output/news_cutout_debug/france_corrected_cutout.png` shows three generic players in plain dark soccer clothing, with coverage 0.481 and transparent margin 0.041. Prompt/provider/mask details are in `france_check.json`. Six new regressions cover explicit-group detection, retained background/clipping rejection, detached ground/debris rejection, cache isolation, distinct soccer retry prompts, preserved raw attempts, and group compositing. No full Argentina video was rendered for this fix.

Identity-aware image selection adds explicit real/fictional/generic classifications and independently reviews them before images. Live Gemini preview correctly classified Donald Trump as real and Odysseus as fictional (`output/news_identity_validation/identity_preview.json`). Wikidata disambiguation selected Q22686 rather than the same-name physician or other subjects, and Commons returned Daniel Torok's public-domain official 2025 portrait. The original image was retrieved without redraw (`trump_asset.json`, initial photo cutout under `trump-photo/cutouts/`), but visual review revealed ghosted suit pixels despite the initial geometric QA pass. The final portrait-quality gate rejects that segmentation and selects the reference-guided edit. Clean original reference images remain preferred; the free-photo route is covered by deterministic tests. Source-record identity matching is not biometric verification or proof of event footage.

Archived reference-edit validation used an image adapter that is no longer supported. Its saved media remains historical evidence only and does not validate the current two-model implementation. Current supported models and checks are documented in [image configuration](IMAGE_MODEL_CONFIGURATION.md) and [smart image validation](docs/SMART_IMAGE_VALIDATION.json). No archived live result is presented as a live Seedream 4 quality test.

The 22 additional identity tests cover free-photo preference without provider initialization, real-versus-fictional routing, source identity/metadata matching, ambiguous names, bounded/restricted image downloads, unsupported licenses, photo/edit provenance contracts, cropped portrait framing, preserved full-body/head clipping checks, paid cache reuse, per-video limits across entities, model allowlisting and provider cancellation. Python compile, shared JSON schema/Zod checks and TypeScript build passed.

A historical mixed-source News render remains under `output/news_identity_validation/`. It predates the current two-model image policy. Current end-to-end validation uses mocked image/speech providers with real Remotion/FFmpeg export; live likeness, anatomy and provider billing remain unverified. See `docs/SMART_IMAGE_VALIDATION.json` for the current evidence scope.
