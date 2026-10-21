# Reference editorial preset

The new `reference_editorial` output preset is available in the existing **News** content mode through CLI, Flask and Gradio. It renders a separate version 2 Remotion composition. Existing News v1, article, story, stock and AI pipelines remain unchanged when the preset is not selected. News accepts the existing URL, text, topic and supplied-story inputs; other content modes do not silently switch into News. This preset currently requires vertical 1080 × 1920 / 30 fps and Remotion. Unsupported combinations return an error before generation.

## Delivered media and evidence

- [Complete baseline-topic video](output/reference_editorial_demo/editorial.mp4), approximately 29.7 seconds. Uses the exact recovered script and existing Kokoro voice recording, with conservative edge trimming and a new master mix. No new facts were added or independently researched for this replay.
- [11.2-second first fixture](output/reference_editorial_fixture/editorial.mp4): progressive words, credited portrait cutouts, lower fades, shadows, comparison focus and persistent subject reframing.
- [Year counter](output/reference_editorial_primitives/year-counter/year-counter.mp4), [map separation](output/reference_editorial_primitives/map-separation/map-separation.mp4), [perspective object action](output/reference_editorial_primitives/object-action/object-action.mp4), [transfer and representation swap](output/reference_editorial_primitives/continuity/continuity.mp4). These are explicitly labeled silent motion studies, not additional historical/news claims.
- [Final contact sheet](output/reference_editorial_demo/review/contact.jpg), [baseline contact sheet](output/reference_editorial_review/baseline-contact.jpg), [reference contact sheet](output/reference_editorial_review/reference-contact.jpg).
- [Final scene-boundary frames](output/reference_editorial_demo/review/transition-10.56.jpg), [final location/reframe frames](output/reference_editorial_demo/review/transition-25.20.jpg), [reference focus frames](output/reference_editorial_review/reference-frames/transition-4.40.jpg), [reference lid-action frames](output/reference_editorial_review/reference-frames/transition-29.05.jpg). Each transition strip samples **every source frame at 30 fps**, not interpolated frames.
- [Timeline and asset manifest](output/reference_editorial_demo/editorial_manifest.json), [staged Remotion props](output/reference_editorial_demo/editorial_props.json), [SRT](output/reference_editorial_demo/subtitles.srt), [VTT](output/reference_editorial_demo/subtitles.vtt), [image credits](output/reference_editorial_demo/image_credits.txt).
- [Machine-readable delivery audit](output/reference_editorial_review/delivery-audit.json), [aligned waveform excerpts](output/reference_editorial_review/aligned-waveform.png), [reference ASR timings](output/reference_editorial_review/reference-transcription.json), [actual frame-seeking hashes](output/reference_editorial_demo/seek-check/determinism.json).

## Source-level diagnosis

The supplied baseline MP4 is byte-identical to `output/news_af1a95199a7245c687819d15b7c56e3a/news.mp4`. Its source account, script, cutouts, provider audio, v1 manifest and renderer props were recovered. A substitute topic fixture was unnecessary.

1. **Whole headline cards:** `agent/news_layout.py::storyboard` searches for an exact contiguous match between the short display headline and spoken words. Its fallback assigns every word the beat's starting frame. The baseline used Kokoro through `agent/news_tts.py`, with `audio.method="sentence_clips"` and an empty `words` array. Even native timings would not match rewritten headlines such as “Musk accuses…” against “Elon Musk has accused…”. `NewsVideo.tsx::NewsText` therefore reveals the whole headline together. The new preset uses exact approved spoken word IDs, rather than assigning summary text the timing of different speech.
2. **Static/generic visual structure:** the v1 planner chooses geometry chiefly from entity count/kind. Its event list is recorded but `NewsVideo.tsx` does not execute that list. The image component has only a small entry-scale curve and a persistence reframe. Three later sections retain essentially the same network diagram. The new renderer evaluates explicit independently timed actions; the full demonstration has comparison, response, process and conclusion layouts, with separate setup/payoff beats inside each section.
3. **Misidentified asset role:** the “globe” is actually a Commons Starlink constellation diagram. Wikidata identity linking did not establish that it matched the requested *terminal photograph*. The ministry building was an unverified Flux illustration. The new demo uses a labeled network symbol and institution symbol. Musk and Ambani reuse the existing credited Commons photographs; no synthetic real-person portraits were made. Originals and prepared alpha crops remain separate.
4. **Washouts and detached labels:** v1 replaces its active beat wholesale and applies outgoing/incoming opacity ramps at its boundary. Labels are screen-space text independent of cutout motion. The new composition owns the stage continuously, keys persistent entities once, gives text its own exit timing, and attaches labels/shadows to their parent transform. Iteration caught and corrected a late-section entity-ID reuse error, label proximity, and overlapping text at boundaries.
5. **Audio pauses:** `agent/news_audio.py::_synthesize_once` retained whole provider clips, including leading/trailing padding, and inserted another 160 ms. The six Kokoro clips contain roughly 0.32–0.37 s of removable leading padding and 0.49–0.55 s of trailing padding. The new assembler retains waveform/alignment handles, preserves internal pauses, joins at sample offsets and inserts 120 ms deliberately. Actual measured boundary gaps include retained handles and are about 0.27 s; they are not claimed to be exactly 120 ms.
6. **Quiet mix:** the baseline News path had no final integrated-loudness normalization. Its audio is passed into Remotion at unity; repeated attenuation was not found in this path. The new path normalizes the assembled stereo mix with measured two-pass `loudnorm`, then measures the actual encoded AAC. Music is off in the demonstration, so it is not masking gaps. The configured optional bed uses the existing ducked music route before final normalization.
7. **Color and renderer configuration:** the installed Remotion is 4.0.242. Its intermediate output is full-range BT.470bg `yuvj420p`. The new bridge explicitly converts to limited-range BT.709 and sets H.264 VUI color primaries/transfer/matrix, then asserts actual metadata. Adding container options alone initially left primaries/transfer unspecified; inspection caught this. Catalog effects, particles, automatic whooshes and branding are not enabled in the new preset.

## Measured results

FFmpeg measurements use the original/final stereo tracks. Silence detection is a **separate** pass at −40 dBFS, minimum 150 ms; it is not run downstream of normalization.

| Measurement | Reference | Supplied baseline | New full video |
|---|---:|---:|---:|
| Integrated loudness | −14.21 LUFS | −25.21 LUFS | about −14.93 LUFS |
| True peak | −0.87 dBTP | −8.99 dBTP | about −1.46 dBTP |
| Container duration | 58.211 s | 34.496 s | about 29.717 s |
| Five section-boundary near-silent gaps | No detected gaps ≥150 ms | 1.236 / 1.214 / 1.150 / 1.148 / 1.174 s | about 0.275 / 0.278 / 0.269 / 0.272 / 0.274 s |

The current exact figures, stream metadata and hashes are in `delivery-audit.json`. The new composition is 890 frames (29⅔ seconds), covering the actual master plus an 18-frame closing hold. AAC/container padding is reported separately. The roughly 0.7-second ending silence includes that intentional readable hold. Natural internal pauses of roughly 0.33–0.41 seconds remain intact.

Reference speech timing comes from **local Whisper small transcription with word timestamps**, separate from the visually observed transition ledger. For example, the model places “Kohinoor” at 0.16–0.58 s, “Queen Victoria” at 2.56–3.12 s, and “Bangladesh” at 8.34–8.70 s. It mistranscribes some proper names (including Daria-i-Noor), so this is an uncorrected ASR artifact, not an approved transcript.

The demonstration uses **known-script forced alignment**, not inferred text from ASR and not equal word durations. CTranslate2 aligns supplied Whisper tokens against each actual recording. Silent edge refinement, trims and offsets are explicit in `audio/alignment.json`. Original punctuation, contractions and names remain in display words. Token probabilities are a confidence signal, not a calibrated timing error. Low-confidence words remain tagged. Render onsets and the three-frame opacity ramp can be checked against those anchors; independent ≤100 ms *phonetic* accuracy is not claimed for every word.

## Implementation and compatibility

- `agent/editorial/models.py` is the Pydantic v2 contract. `scripts/export_editorial_schema.py` generates the browser JSON Schema and TypeScript types. Ajv validates that exact schema in Remotion; relational checks are covered by shared accepted/rejected conformance cases. Intervals are absolute `[startFrame, endFrame)`.
- `agent/editorial/audio.py` handles actual provider timestamps or local forced alignment, waveform edge refinement, sample offsets, two-pass stereo normalization, measurements and SRT/VTT. Google adapter estimates are not accepted as native word timing.
- `agent/editorial/assets.py` maintains source provenance, alpha preparation, checksums and likeness-review records. Automatic mode retrieves licensed real portraits first, then uses reference-guided premium illustrations with multimodal likeness checks. Historical reconstructions and supporting imagery use an explicit lower-cost model. Local registries take precedence. Exact geometry and real-person identity are never established by AI generation alone.
- `agent/editorial/templates.py` contains portrait profiles for the ten semantic template names. `planner.py` maps approved words and entities into those bounds. Bounded LLM suggestions choose semantic templates/phrase splits/emphasis; no generated CSS/TSX executes. Specialized event studies use explicit factual/illustrative plans rather than forcing those actions into unrelated news.
- Emphasis suggestions resolve case, surrounding punctuation and contiguous phrases back to original spoken tokens. Rewritten headline words absent from narration never receive fabricated timestamps. If optional semantic suggestions remain invalid after two attempts, the same deterministic editorial planner completes generation and records the rejected suggestions and fallback warning under `diagnostics.semanticPlan` and in the UI result.
- `remotion/src/editorial/EditorialVideo.tsx` and `motion.ts` render persistent layers, reserved text geometry, parented labels, lower masks, consistent shadows, focus/settlement/reframe/transfer/map separation/year/lid/swap/emphasis/fade actions. There is no wall-clock animation or uncontrolled randomness.
- `agent/editorial/render.py` validates assets/fonts/checksums, stages the composition, renders, converts color, measures AAC and validates delivery targets. If encoded AAC misses the target, it makes at most two audio-only corrections with additional peak headroom and remeasures each result. Video packets are copied unchanged; all attempts and rejected measurements are retained in the delivery audit. It never uses MoviePy as a fallback.
- `agent/editorial/pipeline.py` reuses the existing News evidence/script and TTS adapters. Progress covers source/script, narration/alignment, assets, planning and rendering. `news_pipeline.py` dispatches only when selected; orchestrator, CLI, Flask worker and Gradio forward the resolved preset and text/asset choices. The ordinary UI exposes the preset, duration, voice/provider, asset route, text profile and music.
- V1 manifests still validate/render with `ProjectHERNews`. `scripts/editorial_demo.py` explicitly adapts a v1 script/audio/assets into v2 by re-aligning its actual audio. It never fabricates timings to satisfy v2. Old files and caches are not rewritten.
- Font geometry uses the bundled licensed Poppins SemiBold/Bold files (OFL in `assets/fonts/news`). These are a visually suitable alternative, not an identified/recovered reference font. Font hashes, script/audio hashes and preparation identity prevent stale reuse.

## Run and preview

From this repository root:

```sh
# One-time optional local alignment setup; no paid speech/alignment service.
.venv/bin/python -m pip install -r requirements-editorial.txt
.venv/bin/python scripts/setup_editorial.py

# Reproduce this repository's recovered baseline without an LLM or paid API.
.venv/bin/python scripts/editorial_demo.py --fixture
.venv/bin/python scripts/editorial_demo.py
.venv/bin/python scripts/editorial_primitives.py

# The actual generator route: URL, --text or --file; uses configured providers.
.venv/bin/python main.py generate --content-mode news \
  --visual-preset reference_editorial --renderer remotion --format vertical \
  --news-source-policy supplied --file /path/to/source-account.txt \
  --target-duration 50 --editorial-text editorial --editorial-assets auto

# Flask, or the existing Gradio entry point:
.venv/bin/python web_ui.py
.venv/bin/python app.py

# Inspect the full timeline in Remotion Studio:
cd remotion
npx remotion studio src/index.ts --props ../output/reference_editorial_demo/editorial_props.json
# Select ProjectHEREditorial. The built-in default is a self-contained year study.
```

Use `--editorial-text complete` for full spoken captions in a dedicated top region; this suppresses simultaneous editorial spoken blocks and retains attached entity labels. Both profiles export the complete aligned SRT/VTT. Use `--news-music` or the existing `--bgm` option for a quiet ducked bed. The demo intentionally has no music/effects. Voice/provider remains controlled by existing UI/configuration (`TTS_PROVIDER` in CLI environments). Some existing Google/ElevenLabs adapters do not support the generic speed control; their actual output duration is authoritative, never stretched to a requested duration.

For local assets, use `--editorial-assets local --local-assets assets/editorial/registry.json`. Registry entries use the exact approved entity name:

```json
{
  "Canonical entity name": {
    "path": "/absolute/path/to/approved.png",
    "subject": "Canonical entity name",
    "role": "portrait",
    "source": "source URL or supplied asset record",
    "license": "actual license",
    "attribution": "actual credit"
  }
}
```

If a correct identity/role asset cannot be obtained, the output uses a labeled symbolic fallback and records it. Missing render paths, changed assets, stale fonts, unsupported glyphs and illegibly long labels produce useful errors. Local geometry is not invented. The map study uses [Natural Earth public-domain data](https://www.naturalearthdata.com/about/terms-of-use/) and preserves the original coordinate relationship before schematic separation.

## Verification and remaining limits

```sh
PYTHONPYCACHEPREFIX=/tmp/her-pycache .venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/export_editorial_schema.py
cd remotion
npx tsc --noEmit
node check-news-contract.cjs ../output/news_validation/news_manifest.json
node check-editorial-contract.cjs ../output/editorial_conformance.json
cd ..
node remotion/check-editorial-render.cjs output/reference_editorial_demo/editorial_props.json output/reference_editorial_demo/seek-check
.venv/bin/python scripts/editorial_report.py
```

127 tests passed, including 100 existing regressions. New checks exercise accumulated sample offsets, actual native-timestamp assembly through the integrated pipeline, unsupported renderer rejection before provider calls, CLI/Flask/Gradio propagation, Python/JS agreement on malformed references/intervals/geometry/actions, punctuation/phrase emphasis resolution, invalid optional-plan recovery, and a subject first named late in the conclusion. Actual FFmpeg/AAC tests verify audio correction preserves compressed video packets and the master checksum, compliant exports are not reencoded, and persistent failures stop after two corrections while retaining measurements. Job tests retain live workers past ten minutes and execute the browser polling function through delayed running/result responses. Input classification checks repair malformed enums/fields, preserve URL/account/fiction/clarification routing, and stop before research/TTS/assets if three attempts remain invalid; the integrated editorial test also starts with `kind=reported`, then repairs and completes. Thirteen conformance cases and seven intermediate action states pass. Actual Chromium frame 100 is pixel-identical when rendered, followed by the closing frame, then sought back and rendered again. The complete-caption layout, opening/closing frames, contact sheets and 30 fps transition strips were rendered and reviewed. TypeScript passes.

The fixture provider in the **integration unit test** emits labeled synthetic pulses to test offsets; the **delivered full video** uses the actual recovered Kokoro narration. No new paid-provider run is claimed. The source story remains the archived baseline account, not newly fact-checked news.

**Remaining acceptance limits:** acoustic listening, ordinary-speaker/headphone/phone audition, voice expressiveness and exact music parity cannot be verified through this session. The reference assets/voice/font project files were unavailable. The network and institution assets are intentionally disclosed symbols; they are less photographic than the reference. The full demo has fewer object actions because those actions would not be supported by this source; the separate studies demonstrate them. The preset is vertical and News-only today, and unsupported scripts/glyphs fail explicitly. Low-confidence forced-alignment words require listening review before claiming universal 100 ms sync. This is demonstrated structural/style progress with measured delivery audio, not pixel parity or a claim that every acceptance criterion has been independently verified.

## Web UI emphasis-planning fix

The first live AI-agents story stopped after narration/assets at the timeline stage. Semantic validation compared suggestions against whitespace tokens literally, rejecting punctuation differences such as `engineering` versus `engineering,`. In addition, v1 script emphasis refers to rewritten headline text: this job's final headline included `tools`, which is absent from the spoken sentence. The exact rejected LLM replies were not saved, so the individual offending response cannot be identified retrospectively.

The planner now matches case, boundary punctuation and contiguous phrases back to original spoken tokens. It rejects invented words, gives section-specific repair errors, and after two invalid optional plans completes the same editorial composition using deterministic layouts. Diagnostics and UI warnings disclose the fallback. A second replay-discovered issue is also fixed: conclusion reframing applies only to established subjects; a newly named subject uses its own timed entrance. Stock photo labels now state their illustrative role rather than repeating entity names or displaying lengthy alt text.

The [recovered live story](output/editorial_0c7380d555af4255a526b794112820b4/editorial.mp4) uses its saved 55 aligned words, unchanged master WAV and cached photo, with no new provider calls. Its [manifest](output/editorial_0c7380d555af4255a526b794112820b4/editorial_manifest.json) records the recovery and [contact sheet](output/editorial_0c7380d555af4255a526b794112820b4/review/contact.jpg) shows the result. The photo's original source URL and photographer were not persisted before the failed timeline stage; that gap is explicitly disclosed in the recovered credits. Restart `python web_ui.py` to load these Python changes; Flask runs with automatic reload disabled.

## Encoded-audio and long-job recovery

Web job `4ef40f16ee0b` completed its visual render but failed the final audio gate. Its master measured −15.00 LUFS / −1.49 dBTP; the intermediate measured −14.90 LUFS / −1.49 dBTP; final AAC encoding raised the peak to −0.97 dBTP, 0.03 dB above the −1 dBTP delivery ceiling. The previous gate rejected the entire job and wrote no encoded measurements. The updated exporter retains those measurements, normalizes the existing mix with additional peak headroom, copies the video stream, and checks actual AAC again. The ceiling remains enforced. Each correction starts from the saved lossless master for a single unity-gain master track; timelines with additional audio tracks/gains use their complete rendered mix.

The [recovered video](output/editorial_188a9918e42641e49d10e56ed9bf36b1/editorial.mp4) measures **−14.94 LUFS / −1.98 dBTP** after one correction. Compressed video packet hashes match the rejected file exactly, and the original master checksum is unchanged. No new TTS, research, image or Chromium render calls were needed. Its [delivery audit](output/editorial_188a9918e42641e49d10e56ed9bf36b1/editorial-metrics.json), [manifest](output/editorial_188a9918e42641e49d10e56ed9bf36b1/editorial_manifest.json) and [contact sheet](output/editorial_188a9918e42641e49d10e56ed9bf36b1/review/contact.jpg) are available.

The polling 404s and `stage=initializing` log had a separate cause: cleanup removed live worker metadata once a job exceeded ten minutes. Cleanup now retains live workers, removes finished workers/abandoned reservations, and returns HTTP 202 while a tracked job runs. Browser polling resets its connection retry budget whenever the server confirms `status=running`; the six-minute budget applies to unconfirmed/failed polls. Restart the Python server and refresh the browser to load both fixes.

## Input-classifier validation repair

Web job `a8b80a89548c` failed at `resolve` because the model returned `kind="reported"`. `kind` describes input form (`source_url`, `topic_query`, `supplied_account`, `mixed`); `reported` belongs to the independent `basis` field. The old resolver trusted a single model reply before constructing `Input`, exposing a raw Pydantic error.

`agent/news_research.py::analyze_input` now supplies a classifier schema derived from the existing Input model, distinguishes the two enums in its prompt, validates the response, and requests up to three repairs with field-specific feedback and the unchanged input. It preserves validated URL-only/mixed routing, account attribution, fiction and genuine clarification requests. It never guesses that `reported` means a research topic or converts all malformed inputs into supplied facts. Persistent malformed responses produce an actionable error before research, narration or image calls. Preview, classic News and reference editorial share this resolver; old Input/manifest schemas are unchanged.

Both generation pipelines save `input_classification.json` with attempt counts, routing values and errors. The [offline regression replay](output/news_input_validation/input_classification.json) demonstrates the exact invalid enum repaired on the second attempt with no provider calls. The reported live attempts stopped before speech/assets, so they have no completed video to recover. Restart `python web_ui.py` and retry the same input to use the corrected resolver.

## Research before topic clarification

Job `af0e63a8749e` stopped at `resolve`: the classifier returned `kind=topic_query`, `basis=user_supplied` and a question about Vijay's identity and whether the meeting was factual. Its clarification was raised before Serper or article retrieval ran. Auto/Online public topics and URLs now defer those questions to evidence extraction. The classifier prompt treats public headlines as research requests, and non-fictional topic queries retain reported attribution rather than becoming supplied evidence. Deferred questions and source policy are recorded in `input_classification.json`.

Short topic queries use the original normalized headline for search, preventing inferred identities, titles or dates from redirecting research. Undated research inputs discard classifier-invented event dates; date constraints actually present in the input are preserved. The hardcoded Trump/Argentina questions were removed: historical ambiguity is now evaluated after retrieval, with explicit instructions against silently selecting the newest event or merging different years. Supplied-account questions and structured evidence-stage clarification responses remain supported. No-evidence failures still stop before narration or image generation.

The live [research/script preview](output/news_research_first_validation/news_preview.json) exercises the exact Rahul Gandhi/Vijay headline through the configured providers without generating audio, images or video. One rerun exposed an extracted claim expanding “Saturday” into a full date absent from its quoted passages; extraction now rejects unsupported claim years and repairs them within its existing three-attempt bound before script writing. The extractor is also instructed to preserve relative-date wording rather than deriving unsupported dates from publication metadata.

All **136 tests pass**. Regression checks cover research ordering, original-headline search, attribution, date constraints, article URL routing, unavailable evidence, bounded validation/date repair and historical choices after retrieval. Restart `python web_ui.py` and use Auto or Online research to load the change.

## Contextual imagery and person cutouts

The October review of `/Users/klinten/Downloads/reference-ai-video.mp4` used its full 58.21-second duration and a two-second [contact sheet](output/editorial_review_reference/reference-contact.jpg). Its visual vocabulary changes with the story: gems, a queen and comparison pair, a vault/map, mine, mounted rulers, Nadir Shah, Punjab ruler, company emblem, archival portraits, jewellery, city/location and a bank. Most compositions hold for roughly two to four seconds; related subjects persist across adjacent phrases, with two or three images together where narration connects them. The previous generated story's recurring two or three portraits did not supply that context.

`agent/editorial/visuals.py` now plans sentence-specific subjects and exact spoken anchors without rewriting the approved narration. A separate editorial script supports up to 24 subjects, while each composition retains at most three. Generic contextual people, objects and buildings must illustrate explicitly mentioned context and pass an independent evidence review. New named identities, maps, logos and exact artifacts cannot be invented by this step. Invalid optional plans receive two repairs, then disclose their fallback. Cue onsets use actual aligned words, with at most two frames of anticipation. A late subject's focus animation is omitted when it cannot fit; its entrance is never pulled earlier to make room. Adjacent relevant subjects reuse their layers; irrelevant subjects leave. Full-body/torso cutouts no longer receive an automatic lower-body fade.

Choose **News → Reference editorial → Assets: Automatic · portraits + AI cutouts** (the new default). Flask, Gradio, orchestrator and CLI carry the same `auto` option; older explicit stock/AI/local selections remain accepted. Refresh the browser after restarting `python web_ui.py`.

For actual people, lookup first resolves role/name aliases through Wikidata/Commons and retrieved source bodies. User assertions or search snippets alone cannot establish an actual identity. A linked, non-deprecated Wikidata death date or an explicitly cited source death passage permits historical reconstruction. Licensed photographs undergo background removal and mask QA; opaque-photo fallback was removed from the ordinary person route. If a usable photo cannot be prepared, the tool may use a clear source-associated reference with **Seedream 4**, then compare the generated cutout against that reference using the configured multimodal Gemini model. Wrong/uncertain likeness, extra people, lost torso/clothing and segmentation failures reject the image; Seedream uses one output with no regeneration retries; other paid calls are bounded. Source-associated web images with unknown reuse rights are used only as reference inputs, never inserted as documentary photos. Successful generated images remain labeled **AI illustration**, `identity_verified=false`; visual agreement does not prove identity. No usable reference for a contemporary real person produces an actionable error rather than an anonymous profile symbol or a claimed verified face.

Historical, fictional and generic supporting illustrations use **FLUX Schnell** by default. Raw images and accepted review records are cached by prompt, model and reference checksum, and only accepted results enter the cache. Configurations are per-job instances; no global image preference is mutated. Both routes preserve available clothing/body, request generous margins, remove backgrounds using the existing CPU segmentation models and validate transparency, coverage, edges and detached components. Local explicitly chosen symbolic assets and unverified exact geometry retain disclosed fallback behavior.

In **Automatic** and **AI** modes, human collectives such as Portuguese forces, troops, armies and teams use representative AI group cutouts even when the collective itself is real. These bypass individual portrait lookup and likeness checks, retain the collective's name, use narration context for period/clothing, and are labeled AI illustrations rather than actual members or an exact lineup. Local registry assets take precedence. The acquisition audit records `representative_group_illustration`; named individual people still use the portrait/reference route. Unnamed roles are generic subjects, not named identities.

Job `a3e03d5bb403` had classified “Portuguese forces” as a real person and searched for a modern military institution's portrait. The [recovered video](output/editorial_portuguese_recovery/editorial.mp4) reuses the failed job's unchanged approved narration, word alignment, master audio and cached historical illustration; only the missing group cutout was generated through the supporting-image tier. Both assets have validated transparency and illustration labels. Final AAC measured **−15.06 LUFS / −1.49 dBTP** and passed delivery checks. This recovery repairs visual acquisition; it does not independently revise the saved historical narrative or validate the historical portrait's likeness.

Configuration: `REPLICATE_API_TOKEN`, `GEMINI_API_KEY` for existing multimodal review, `CHARACTER_IMAGE_MODEL=black-forest-labs/flux-schnell`, `ACTION_IMAGE_MODEL=bytedance/seedream-4`, and optional `EDITORIAL_VISION_MODEL`. Image generation supports only those two models. See [image configuration](IMAGE_MODEL_CONFIGURATION.md) for budgets, retry policy and request schemas.

Each run writes `visual_plan.json` (subjects, exact cues, review/fallback diagnostics) and `assets/asset_acquisition.json` (identity sources, route, mask QA, model, rejected attempts and accepted likeness review). The final manifest retains both diagnostics and asset checksums. `scripts/editorial_visual_review.py PREVIOUS --output OUTPUT` reuses a saved narration for live visual validation; `scripts/editorial_person_review.py PREVIOUS ENTITY_ID OUTPUT` exercises one actual-person route.

Live verification produced this [27.2-second updated video](output/editorial_visual_review/editorial.mp4) and [contact sheet](output/editorial_visual_review/contact.jpg), reusing the previous Bhagat Singh narration. The plan has **seven subjects instead of three**: Bhagat Singh, Durga Devi Vohra, Rajguru, representative police, a railway station, child and train. All seven are transparent cutouts; the historical figures are explicitly labeled illustrative reconstructions, not validated portraits. A separate [Rahul Gandhi photo check](output/editorial_person_review/person_review.json) retrieved a usable actual portrait. The [premium route exercise](output/editorial_premium_review/person_review.json) deliberately forced a reference edit for QA and passed actual image comparison plus mask checks; the artifact records `forcedReferenceEditForQA=true`, and does not imply that AI is preferred over available photographs.

The live run exposed HTTP 429 throttling, a reference prompt that could override the source's clothing, and multi-image text overlap in the process/document profiles. The adapter now honors bounded retry delays for rejected create requests without duplicating accepted predictions; reference edits preserve the photograph rather than applying a conflicting textual portrait description. Multi-subject profiles keep text beneath images/labels, and incompatible box sizes crossfade rather than retaining oversized portraits. Explicitly spoken named people are restored to their beat's cues. The final export measures **−15.20 LUFS / −1.47 dBTP**. All **159 Python tests**, TypeScript and the existing 13 Python/Remotion contract cases plus seven motion states pass. This validates the exercised routes; likeness-review confidence is model output, not a calibrated identity guarantee or assurance that every future person has a usable reference.
