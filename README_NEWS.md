# News mode

News accepts a URL (with optional notes), a dated public event query, or a supplied local account. Choose **News** in Flask/Gradio, or pass `--content-mode news`. Existing modes and the daily publishing automation retain their routes and defaults. News does not publish anything.

The fixed `news_editorial_cutout` style uses separate RGBA subjects on off-white paper, local Poppins SemiBold/Bold, grey phrases, small fades and restrained movement. Both renderers consume the same versioned evidence, script, assets, layout and audio timeline. Foreground stays inside x=8–92%, y=20–85%, including labels, shadows and motion. There are six layouts: single subject, two subjects, three subjects, subject with audited context, place/object stack and text bridge. Repeated subjects reuse their cutout and remain through context changes. The old karaoke overlay and effects agent are bypassed for News.

## Setup

Use Python 3.9–3.12 for the pinned News CPU segmentation stack, FFmpeg/ffprobe, and Node 18+ for Remotion. The implementation was exercised on Python 3.9.6, Node 22 and Remotion 4.0.242; the application runtime was not upgraded.

```bash
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-news.txt
cd remotion && npm ci && cd ..
```

Keep your existing `.env`; copy the additional settings from `.env.example`. Configure the existing LLM and TTS provider and at least one working image provider. News needs no Pexels credential. `huggingface_hub>=0.31,<1` supports Inference Providers while retaining `HfFolder` needed by this project's Gradio 4 installation.

News search uses Serper's authenticated `POST https://google.serper.dev/search`, with `SERPER_API_KEY` sent only in the `X-API-KEY` header. Organic result links are normalized and passed through the existing secure article retrieval/evidence pipeline; snippets alone are not treated as article evidence. Search requests retain the same limits and timeouts, perform no automatic retries, and reject API redirects. Restart the app after changing `.env`; hosted deployments need `SERPER_API_KEY` in their environment/secrets.

| Setting | Purpose/default |
| --- | --- |
| `SERPER_API_KEY` | Serper Google Search for public topic queries and related article research |
| `NEWS_MAX_PAGES` | At most 3 retained sources; clamped to 1–3 |
| `NEWS_HTTP_TIMEOUT` | Per-connect/read timeout, default 12 seconds, capped at 20 |
| `NEWS_DEFAULT_DURATION` | Adaptive script target, default 55 seconds; source completeness takes priority |
| `NEWS_CUTOUT_BACKEND` | `rembg`; another implementation can be injected through `CutoutProcessor.segmenter` |
| `NEWS_CUTOUT_MODELS` | Explicit `isnet-general-use`; at most two comma-separated compatible rembg model names |
| `NEWS_CUTOUT_CACHE` | Processed RGBA cache, default `temp/news_cutouts` |
| `NEWS_REAL_IMAGE_MODEL` | Named real-subject fallback: `black-forest-labs/flux-1.1-pro`; `black-forest-labs/flux-dev` is also allowed |
| `NEWS_MAX_REAL_IMAGE_CALLS` | Premium predictions per video, default 8, clamped 0–12; 0 permits references/cached results only |
| `U2NET_HOME` | Persistent downloaded model directory; set to `temp/news-models` or an absolute writable volume |
| `NUMBA_CACHE_DIR` | Writable Numba cache, e.g. `temp/numba` |
| `NEWS_HF_PROVIDER` | Hugging Face Inference Providers selection, default `auto`; uses existing `HF_API_TOKEN` and image model |
| `POLLINATIONS_API_KEY` | Authenticated News Pollinations fallback credential |
| `NEWS_POLLINATIONS_MODEL` | `black-forest-labs/flux.1-schnell` at the current authenticated endpoint |
| `NEWS_MUSIC` | Optional quiet, ducked procedural music, default off |
| `NEWS_VERIFIED_ASSETS_JSON` | Optional audited maps/flags/logos registry |

Generic and fictional subjects reuse the existing configured image chain (normally Replicate FLUX Schnell → Hugging Face → Pollinations), with at most three generation attempts and distinct retry prompts. News uses the existing working Replicate implementation, the official HF Inference Providers SDK and authenticated `gen.pollinations.ai`. Provider access, supported models, credits and availability depend on the configured account. Each attempt retains its raw image and logs failures. An essential failed subject stops the job rather than becoming a rectangular slide.

Named real subjects follow a separate route. The script explicitly classifies every entity as `real`, `fictional`, or `generic`, with an independent review before images. Donald Trump, a specific landmark or a recognizable product uses real references; Odysseus uses fictional AI imagery; an anonymous scientist or ordinary diamond uses generic imagery. Wikidata search resolves the identity, including same-name ambiguity, and its P18 image links lead to Commons files. Up to five identity candidates and two files are considered. Commons metadata must provide author/credit and a supported reusable license. Bounded downloads allow JPEG/PNG/WebP images up to 15 MB/25 MP; public DNS is pinned and redirects revalidated. Source identity, license, attribution and transformations are retained. This initial source adapter covers Wikidata/Commons, not arbitrary copyrighted search thumbnails or every real subject.

An original reference image that passes segmentation is used without an image-generation call. Cropped head-and-shoulders portraits may retain intentional lower-torso cropping, but clipped heads and upper side edges still fail; final assets have transparent padding. Portraits with damaged semitransparent clothing fail QA and use a cleaner reference or a reference-guided edit. If the reference needs adaptation, News uses [FLUX Kontext Pro](https://replicate.com/black-forest-labs/flux-kontext-pro) with the actual reference image and instructions to preserve identity. If no suitable reference is found, a named illustration uses [FLUX1.1 Pro](https://replicate.com/blog/flux-1-1-pro-is-here/). Both default models were listed at $0.04 per output when checked on 2026-10-11, rather than token pricing. There are at most two premium attempts per real entity and eight premium predictions per job by default: approximately $0.32 of premium image outputs at those listed rates, excluding other services and subject to pricing changes. Failed requests count against the app's call cap. Successful premium images are cached across jobs using identity, prompt, model, reference bytes and processing version. The app requests one output at 1:1, disables prompt upsampling, cancels unfinished predictions on cancellation, and never automatically escalates to Max/Ultra or substitutes a generic cheap-model face for a real subject.

Original reference images have `origin: photo`, `illustrative: false`, source attribution, and `identity_verified: true` meaning the source record was matched to the entity. This flag is not biometric verification or proof that the image depicts the narrated event. AI adaptations have `origin: reference_edit`; reference-free AI has `origin: generated`. Both remain illustrative and unverified as a facial match. No numeric resemblance score, including “90%,” is invented. Sources/credits are visible in News result details, the manifest and `image_credits.txt`. Fictional/generic subjects never trigger reference retrieval or premium generation.

The first opaque asset downloads approximately 179 MB of ISNet weights. Sessions are initialized once per worker/model and inference is serialized safely; processed assets are cached using source bytes, backend/model/version and geometry policy. Allow memory for ONNX inference plus video rendering; there is no GPU requirement. Durable Remotion preview copies use a per-generation folder rather than expiring provider URLs. Remove old output/staged folders according to your retention policy, excluding active jobs.

Docker installs `requirements-news.txt` by default (`--build-arg INSTALL_NEWS_CUTOUTS=0` omits it) and places model/Numba caches under `/app/temp`. Mount or prepopulate the model cache for deployments without runtime download access. Docker image build and Cloud Run resource sizing have not been validated in this change.

## Inputs, preview and sources

The main Flask creation studio now submits a fixed configuration without editable settings: informative storytelling, vertical, Claymorphism request style, automatic duration (`0`), News, Remotion, Reference editorial, progressive phrases, automatic portraits/AI cutouts, automatic sources, Replicate's configured speech model, and no background music. Preview and generation share these defaults, and the server enforces them for the studio profile. Reference editorial continues to own its rendering/asset art direction; the general Claymorphism style field is not an override of that preset. Classic UI and direct API mode selections retain their existing behavior.

- **Auto** researches public queries, headlines and URLs before asking about ambiguous identities, titles or events. A concrete local account can be used directly, including a short factual sentence. Classification uses semantic analysis, not just length.
- **Online research** performs one focused Serper query and fetches selected pages. It retains up to three sources and attempts at most six search candidates plus supplied URLs. Near-duplicate syndications are not independent accounts. A single source remains explicitly `single_source`.
- **Use my account** only uses supplied facts. A URL without details or a vague topic is insufficient under this policy. Unknown dates, identities, causes and outcomes remain unknown. Fictional/hypothetical input is identified in the narration and evidence.

For the **Reference editorial** preset, choose **Assets → Automatic · portraits + AI cutouts**. It retrieves real portraits, uses reference-guided premium AI with likeness review when a portrait cannot be prepared, and creates lower-cost contextual/historical/fictional illustrations as needed. Real-person identity requires online evidence or an audited reference; a generated face alone cannot establish it. Bodies and clothing are retained, backgrounds are removed, and contextual images enter on aligned spoken phrases. See [reference editorial imagery](REFERENCE_EDITORIAL.md#contextual-imagery-and-person-cutouts) for configuration and diagnostics.

For Auto/Online topics, classifier uncertainty is passed to evidence extraction rather than stopping before search. Short headlines are searched as entered, without adding model-inferred names or dates. Undated headlines are not assigned today's date. If retrieved sources still describe materially different events or years, the app asks you to choose; unavailable sources produce an actionable research error rather than an invented story.

Without Serper credentials, readable URLs and supplied accounts remain usable with a reduced-verification warning. A vague topic fails with instructions to configure search or supply a source/details. Ambiguous elections, inaugurations and tournaments return `needs_clarification` with event/year choices; Flask lets you append a choice, and the CLI reports the same structured response with a failing exit status.

Preview is optional and incurs LLM/research calls, but no image/TTS calls. It shows detected event/date/basis, full narration, sources, assumptions and warnings. Generation independently resolves and validates the input again; preview is not an approval step or a persistent script editor.

```bash
python main.py preview --content-mode news \
  --url "https://www.nobelprize.org/prizes/physics/2024/press-release/"

python main.py generate --content-mode news --renderer remotion \
  --text "Argentina winning the 2022 FIFA World Cup" --target-duration 55

python main.py generate --content-mode news --news-source-policy supplied \
  --renderer moviepy \
  --text "Fictional account: A tiger approached a boy near a village. The boy stood still and the tiger left. No one was injured. The date is unspecified."

python main.py generate --content-mode news --url "https://example.com/article" \
  --text "Focus on the confirmed result." --renderer remotion --quality high
```

Generate also supports `--file`, `--format`, `--language`, `--voice`, `--tone`, `--speed`, `--brand`, `--news-music` and a local `--bgm` file. Platform selection supplies format. News uses quality-controlled FPS, default high/30 FPS, and the explicit duration target/default rather than legacy cinematic effects or intro/outro cards. Theme/caption/color-grade/custom-font/intro/outro controls do not change the fixed News composition. News always retains full SRT subtitles as an output artifact.

Speech is synthesized per sentence before absolute timing is assigned. Valid Edge/ElevenLabs native word timestamps drive word builds and entity mentions. Google/Kokoro estimated timestamps are discarded: actual clip boundaries drive phrase reveals and the manifest reports `sentence_clips` or `mixed`. No proportional word timing is presented as forced alignment. Inter-sentence pauses are included in the concatenated audio/timeline. Short source material is allowed to produce a shorter video. Music is optional and FFmpeg ducks it under speech without changing timing.

News narration automatically falls back from Google (or ElevenLabs) to Replicate, then free Edge TTS. Exceptions, missing sentence clips, and invalid audio trigger a complete replacement narration with one provider. Selecting Edge directly makes no paid speech requests. Selecting Replicate or Chatterbox Turbo keeps that provider exclusively by default (`NEWS_REPLICATE_ONLY=1`), preserving the voice even during throttling; set `NEWS_REPLICATE_ONLY=0` to restore the Edge fallback for those selections. The web News narration selector also offers Chatterbox Turbo directly. Every switch and final provider appears in terminal logs; manifest audio fields `provider`, `model`, and `fallbacks` retain the result. Failed attempts remain in isolated `narration_attempts/` directories for diagnosis.

`NEWS_REPLICATE_TTS_MODEL=jaaari/kokoro-82m` is the default budget fallback. Replicate currently estimates [Kokoro](https://replicate.com/jaaari/kokoro-82m) at about **$0.00031 per prediction**, variable with input/runtime: twelve uncached sentences are roughly $0.0037, not a guaranteed video price. Optional `NEWS_REPLICATE_TTS_MODEL=resemble-ai/chatterbox-turbo` uses [Chatterbox Turbo](https://replicate.com/resemble-ai/chatterbox-turbo) at **$0.025 per 1,000 input characters**; 1,500 characters cost about $0.0375. Speech is priced by characters/runtime, not LLM tokens. These are the only enabled Replicate speech models; failed paid predictions are not automatically retried or upgraded to a more expensive model.

Validated WAV clips are cached in `temp/news_speech` by pinned model version, exact text, voice and model inputs. Repeated matching clips avoid new predictions. Requests use a remote two-minute cancellation deadline, bounded polling/downloads, and local cancellation. Uncached speech predictions have a shared minimum 12-second start interval across jobs in the current application process (`NEWS_REPLICATE_MIN_INTERVAL=12`); cache hits and polling do not consume these prediction slots. A rejected HTTP 429 request can be resubmitted up to seven times (`NEWS_REPLICATE_RATE_LIMIT_RETRIES=7`), honoring its Retry-After header or reset hint with a small buffer. Total throttle cooldown is bounded to 600 seconds per narration (`NEWS_REPLICATE_RATE_LIMIT_WAIT=600`), in addition to ordinary pacing. Waits are cancellable. Accepted or ambiguously timed-out paid prediction requests are never resubmitted. With an explicit Replicate selection, persistent throttling stops with an actionable error rather than changing provider; the Google/ElevenLabs fallback chains retain their previous provider behavior. Pacing is process-local and cannot coordinate other processes, external tools or image requests using the same account. [Replicate applies tighter limits to some low-credit accounts](https://replicate.com/docs/topics/predictions/rate-limits/).

Kokoro accepts English, Hindi and French in News; English UK uses a British voice, while English India currently uses the US voice. Unsupported languages produce an actionable error in Replicate-only mode; automatic fallback remains available when explicitly enabled. Turbo is English-only, limits each sentence to 500 characters and uses its natural speaking rate. Replicate output supplies sentence boundaries only; word timestamps are never invented. Google quota exhaustion still needs a quota reset or account change, but no longer stops a News video when a fallback is available.

Bundled Poppins covers Latin and Devanagari. Unsupported glyphs fail with an actionable font message before image generation; News does not silently substitute system fonts. Hindi in MoviePy needs a Pillow build with libraqm. The current macOS Python build lacks it, so use Remotion there. Other legacy language choices remain available to older modes; their scripts are not automatically supported by the News font pair.

## Artifacts, API and contracts

Each `output/news_<generation>/` includes `news_evidence.json`, `news_preview.json`, `news_storyboard_plan.json`, raw and processed cutouts, sentence audio, `news_narration.wav`, `news_manifest.json`, `subtitles.srt`, `news.mp4`, and `thumbnail.jpg`. Failed jobs record `news_failure.json` and keep diagnostics. Successful Remotion runs also have `news_remotion_props.json` and durable media in `remotion/public/news/<generation>/`. Load those props into **ProjectHERNews** in Remotion Studio for the same preview/export composition. Cancellation terminates the render process group and removes only that job's staged render media; retained outputs/caches support diagnosis and reuse.

`POST /api/generate` keeps existing request fields and adds `content_mode: "news"`, `news_source_policy: "auto" | "online" | "supplied"`, and optional `news_music`. It returns the normal job ID; existing SSE/status/download routes carry progress and result metadata. `POST /api/preview` returns structured News data, HTTP 409 for ambiguity or 422 for an evidence failure. `POST /api/news/cancel/<job_id>` cancels a News job. Result metadata includes source links, warnings and a manifest URL. Settings are passed per job; News avoids the legacy global-config mutations and stock-image constructor requirement.

When running `python web_ui.py`, generation failures in every mode are logged in the terminal with the same error sent to the UI, the job ID, mode, and last reported stage. Preview and request validation failures include the endpoint and HTTP status. Unexpected exceptions include tracebacks; ambiguity prompts use warning-level logs and cancellation uses info-level logs.

`agent/news_models.py` is authoritative. Run `python scripts/export_news_contract.py` after modifying it; this generates `agent/news/manifest.schema.json` and `remotion/src/news-contract.ts`. TypeScript builds a strict Zod schema from that same JSON Schema, then applies matching reference/timing/layout checks and a SHA-256 narration/alignment check. Unknown fields, stale alignment, missing essential subjects, bad claim links, unsafe coordinates and collisions fail before render.

Retrieval validates public HTTP(S) DNS results, pins the selected IP while preserving TLS hostname verification, revalidates redirects, disallows internal/mixed/reserved addresses and nonstandard ports, caps response bytes/time and checks content type. It does not use environment proxies or bypass paywalls/access controls. Retrieved instructions remain untrusted data. Evidence retains metadata, verbatim claim excerpts, conflicts and unresolved details; writing gets up to three bounded evidence-review/repair attempts before expensive assets.

Claim extraction selects numbered passages from the retrieved article body. The backend copies the original text into evidence excerpts, preserving exact whitespace and punctuation instead of asking the model to reproduce quotations. Invalid references, paraphrased legacy excerpts and malformed evidence get up to three extraction/repair attempts, then fail with an actionable message. The manifest's verbatim-excerpt invariant and independent script evidence review remain strict.

For exact geography/branding, provide operator-audited RGBA PNGs inside `assets/` and reference their registry keys. Generated silhouettes never stand in for exact national outlines, flags or logos. Registry example (replace with an actual licensed, reviewed asset):

```json
{
  "audited-region": {
    "path": "assets/verified/region.png",
    "name": "Accurate region outline",
    "source_url": "https://authoritative.example/geometry",
    "license": "Record the asset's actual license here"
  }
}
```

All generated assets are marked illustrative; prompts/providers, raw/cutout paths, segmentation method, mask statistics and fallback reasons are recorded. The description explicitly distinguishes illustrations/reference images from documentary event footage. Mask QA rejects opaque/empty rectangles, missing margin, implausible coverage, major detached components and excessive semitransparent fringes. Explicit human groups may contain several substantial, vertically aligned silhouettes; single subjects retain the strict detached-component gate. Group handling remains subject to opacity, margin, coverage, rectangular-mask and fringe checks, and rejects detached ground strips and small stray blobs. Generic/fictional team prompts use compact representative groups; real teams preserve their reference lineup. Football prompts specify association football and override scene language such as fields or grass. It never removes every white pixel. These checks cannot prove anatomical integrity, facial resemblance or perfect reflective-object edges; manually review publication candidates.

## Dependencies, models and licenses

The selected [rembg 2.0.57 release](https://pypi.org/project/rembg/2.0.57/) supports the existing Python 3.9 runtime. News pins compatible ONNX Runtime, NumPy and OpenCV bounds separately instead of installing current upstream rembg blindly. rembg's library license is MIT. The explicit model is **ISNet general-use**, not a changing library default. Its [pinned adapter](https://github.com/danielgatis/rembg/blob/v2.0.57/rembg/sessions/dis_general_use.py) downloads the ONNX release with MD5 `fc16ebd8b0c10d971d3513d564d01e29`; keep checksum verification enabled.

Model provenance is the [official DIS/IS-Net repository](https://github.com/xuebinqin/DIS), which links the general-use weights and [Apache 2.0 project license](https://github.com/xuebinqin/DIS/blob/main/LICENSE.md). Its terms explicitly name code/evaluation metrics and separate dataset terms; the rembg ONNX release provides no distinct weight-license statement. Consequently, library MIT/project Apache 2.0 should not be represented as an independently confirmed license grant for redistributed ONNX weights. Weights are downloaded at runtime and are not bundled in this repository. Confirm weight redistribution/commercial deployment terms with the model owner for your deployment, or inject a separately licensed segmentation backend. This license ambiguity remains documented rather than assumed away.

Poppins files and their SIL Open Font License are bundled under `assets/fonts/news/`; identical files are staged for Remotion. [Google Fonts Poppins](https://github.com/google/fonts/tree/main/ofl/poppins) documents the source/license. Current API references used for News: [Serper search/playground](https://serper.dev/playground), [Replicate FLUX](https://replicate.com/black-forest-labs/flux-1.1-pro/api), [HF text-to-image](https://huggingface.co/docs/inference-providers/tasks/text-to-image), [Pollinations API](https://github.com/pollinations/pollinations/blob/main/APIDOCS.md).

## Validation and sample outputs

```bash
python -m unittest discover -s tests -v
python scripts/render_news_fixture.py --renderer both
remotion/node_modules/.bin/tsc --noEmit -p remotion
node remotion/check-news-contract.cjs
```

See [NEWS_VALIDATION.md](NEWS_VALIDATION.md) for the checks actually run, real sample paths, fixture provenance and remaining limits. No supplied reference screenshots were attached to this request; the implemented visual language follows the written description, and an exact visual/font match is not claimed.
