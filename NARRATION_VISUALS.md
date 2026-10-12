# Narration-driven visual storytelling

The `reference_editorial` preset now uses a Visual Director between final audio
alignment and asset acquisition. Other presets retain their original behavior.
It supports the existing topic/URL/supplied-account News input resolver and the
orchestrator's article, topic and story routes. Specialized character/series
modes retain their existing pipelines. The editorial renderer remains vertical
1080×1920, 30 fps; horizontal and square use the existing presets.

## Pipeline and contract

1. Existing input research and script validation approve the narration.
2. Contextual visual extraction reuses canonical entities and identifies exact
   spoken anchors. Up to 12 subjects can be mentioned in a sentence; at most
   three are visible together. New named subjects must occur in the script and
   pass the existing evidence review.
3. Existing TTS generates narration. Native provider boundaries are checked for
   text, monotonicity and audio bounds. Otherwise the existing known-script
   Whisper alignment runs. Invalid cached boundaries are discarded.
4. The Visual Director returns Pydantic-validated word spans, primary/secondary
   subjects, relationships, intent and confidence. It can introduce, continue,
   emphasize or replace subjects within one sentence. Invalid results get one
   repair attempt, then an explicitly diagnosed deterministic fallback.
5. Existing image preparation, caches and providers are reused. Named objects
   and places additionally use identity-linked Wikidata/Commons candidates,
   multimodal relevance/identity/watermark review, duplicate checks and
   resolution ranking. Sources, licensing and review decisions are saved.
6. The compiler converts word onsets into absolute frames once. It maintains
   entity lifetimes, focus, semantic layouts, entrance/exit animations and
   geometry transitions. Stable entity/asset references survive reframing.
   It does not ask an LLM to generate rendering code or timestamps.
7. Python and Remotion validate references, duration coverage, simultaneous
   layers, reframe bounds and conflicting transitions. The existing renderer
   executes the saved timeline deterministically.
8. The encoded output is checked for duration, sustained black frames, loudness,
   peak level and color metadata.

Composition variants cover single subjects, person with object, object/portrait
comparisons, three subjects, place with foreground object, event context,
chronology, ownership and location changes. Related entities persist through
these changes. Native or forced audio alignment remains authoritative.

Captions are a separate bottom track in the new mode. Names attach to their
images; spoken year/numeric markers can appear above them. Complete-caption
mode suppresses the extra date text. Nonfactual assets retain an Illustration
label. A missing verified identity is never replaced with another named person
or object: named-object lookup failure uses a disclosed symbol; existing strict
real-person lookup failures still stop with an actionable error.

## Run

Use the existing **News → Reference editorial → Remotion → Vertical** controls,
or the CLI:

```sh
.venv/bin/python main.py generate --text 'Your topic or supplied account' \
  --content-mode news --visual-preset reference_editorial --renderer remotion
```

For supplied content add `--news-source-policy supplied`. URLs use `--url`.
Live runs need the existing configured LLM, TTS and image providers. No new paid
provider or Python/Node dependency was added.

Configuration follows `config.py`, with optional validated JSON overrides:

```sh
export HER_NARRATION_VISUAL_SETTINGS='{"maxSimultaneousSubjects":3,"enableSubjectPersistence":true,"enableContextualTransitions":true,"enableEditorialText":true,"allowPhraseTimingFallback":false}'
```

Defaults enable the feature only within this preset. Set
`narrationDrivenVisualsEnabled` to false to use the prior editorial planner.
Other options: `syncToleranceMs` (200), `minReadableBeatDurationMs` (700),
`entryDurationMs` (250), and `diagnosticMode` (true).

When forced alignment is unavailable and `allowPhraseTimingFallback` is true
(the default), timestamps are explicitly marked `estimated_phrase`, confidence
zero, and accompanied by warnings. They are distributed within measured audio
clip durations and **do not meet the word-level synchronization guarantee**.
Set the option false for strict measured-timing-only output. Rapid real spoken
cues stay at their original onsets and produce readability diagnostics instead
of silently delaying a subject to satisfy a minimum duration.

## Tests and samples

```sh
.venv/bin/python -m unittest discover -s tests -q
(cd remotion && ./node_modules/.bin/tsc --noEmit)

# Complete input → script → audio → assets → director → actual Remotion video.
# Provider fixtures use synthetic word pulses and original test illustrations.
.venv/bin/python scripts/narration_visual_demo.py --fixture \
  --output output/narration_visual_fixture

# Reuse a saved real narration and its assets, without external provider calls.
.venv/bin/python scripts/narration_visual_demo.py \
  --manifest output/editorial_portuguese_recovery/editorial_manifest.json \
  --output output/narration_visual_demo
```

The saved-narration demonstration needs that pre-existing local manifest and
its referenced files. The complete synthetic fixture is self-contained after
installing the project's existing dependencies/fonts. Both render through
Chromium, which must be permitted to launch by the host environment.

Artifacts beside each video:

- `visual_plan.json`: extracted subjects and exact narration anchors.
- `visual_direction.json`: validated semantic cue instructions.
- `storyboard_summary.json`: script, words, entities, assets, exact character
  spans, cue timestamps, active layers, target positions, focus and warnings.
- `editorial_manifest.json`: complete reusable storyboard including word
  timing provenance, asset hashes, layers, events and diagnostics.
- `assets/asset_acquisition.json`: retrieval routes, candidate reviews,
  relevance scores and provenance.
- `editorial-visual-quality.json` and `editorial-metrics.json`: encoded output
  checks. Black-frame detection does not certify semantic image correctness or
  detect every white/background-only frame.

Re-render a saved manifest with `Timeline.model_validate_json(...)` and
`agent.editorial.render.render(timeline, output_path)`; no LLM or TTS call is
needed. The renderer verifies local asset, audio and font checksums.

## Changes made for this implementation

- `agent/editorial/director.py` — settings, structured intent, validation,
  fallback, semantic layouts, deterministic layer compiler, diagnostics.
- `agent/editorial/visuals.py` — separate total mentioned-subject capacity from
  screen capacity; supported named subject extraction.
- `agent/editorial/audio.py` — timing input validation and explicit fallback.
- `agent/editorial/assets.py` — named artifact/place retrieval, ranking and
  disclosed optional supporting-asset failure.
- `agent/editorial/planner.py`, `pipeline.py` — director integration.
- `agent/editorial/models.py` — estimated timing provenance, atomic invariants,
  geometry transitions and additive narration-driven flag.
- `agent/editorial/render.py` — encoded visual output checks.
- `agent/orchestrator.py`, `main.py` — explicit preset routing for ordinary
  input modes and preservation of CLI speech settings.
- `config.py` — reusable validated settings source.
- `remotion/src/editorial/{EditorialVideo.tsx,motion.ts,contract.ts}` — separate
  captions, continuous geometry evaluation, browser contract checks.
- `remotion/src/editorial/{schema.json,types.ts}` — regenerated shared contract.
- `tests/test_visual_director.py` — timing, persistence, geometry, failure and
  asset-selection regression coverage.
- `scripts/narration_visual_demo.py` — reproducible real renderer demonstrations.

Live semantic planning and live candidate identity checks are not certified by
an offline fixture. Temporal alignment confidence also cannot prove a provider
placed every word within 150–250 ms of the acoustic onset. These are explicit
limits; inspect the saved diagnostics and real speech when evaluating a topic.
