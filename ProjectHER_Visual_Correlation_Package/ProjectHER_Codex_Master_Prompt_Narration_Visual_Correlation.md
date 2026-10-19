# PROJECTHER — CODEX MASTER IMPLEMENTATION PROMPT
## Critical fix: narration-to-image correlation, scene-specific action depiction, and visual timeline alignment

**Role:** Act as a senior AI-video systems architect, multimodal prompt engineer, editorial motion designer, and production-grade full-stack engineer. **Audit the existing ProjectHER repository and implement the solution; do not merely propose it.** Operate conservatively: preserve existing working behavior and aesthetics, make focused changes, and verify end-to-end rendered outputs.

**Input evidence:** Two newly rendered videos, `editorial-3.mp4` (~61.1 s) and `editorial-4.mp4` (~63.1 s), and the desired editorial reference, `reference-ai-video.mp4` (the uploaded local copy may be named `reference-ai-video(9).mp4`, ~58.2 s). If they are not accessible in your workspace, request their paths or use the enclosed audit and contact sheets; **do not pretend to have seen files you cannot open**. See `ProjectHER_Visual_Correlation_Audit.md` for an independent visual comparison and timing observations.

---

## 0. THE PRIMARY GOAL — THIS IS THE NON-NEGOTIABLE REQUIREMENT

ProjectHER's purpose is not to place attractive character portraits next to narration. It is to **tell the narrated story visually, exactly when relevant events are being spoken**.

- When the narration introduces a person, a good portrait is appropriate.
- When narration describes a person **doing** something, the video must **depict the action**, relationship, object and setting — through a scene-specific image, composite or meaningful documentary illustration.
- When a location, object, year, document, institution or change of ownership matters, show that precise type of visual rather than defaulting to the same person's face.
- When narration reaches an emotional or comic reveal, the visual itself must communicate it. Text, camera zooms, shuffled portraits or changing subtitles **cannot substitute for the missing event**.
- Timing must follow the **actual spoken narration**, not a preselected image carousel or rough time buckets.

**Working mental model:** `A story → a series of semantic events → an illustrated storyboard → temporally matched visual beats → a rendered video`. **Not** `A story → entity list → 5–6 cutout portraits reused until the end`.

Cost is no longer the primary blocker for this request. Favor the right visuals over overly restrictive portrait-count caps. Do not generate an arbitrary number just to satisfy a quantity; use as many distinct *semantically necessary* assets as the story needs, with sensible cost controls and informed reuse.

---

## 1. WHAT THE CURRENT VIDEOS PROVE AND WHAT THEY DO NOT

The existing editorial typography, clean background, ProjectHER branding, cutout illustration quality and overall vertical format are usable. **Retain them.** The failure is visual storytelling.

Approximate Thor story scenes from the two supplied outputs:

| Approx. interval | Narrated event | Current visual failure | Mandatory target |
|---|---|---|---|
| 0–8 s | Thor's hammer missing/stolen | Static Thor/Thrym cutouts; one version also emphasizes an unclear large artifact | Hammer theft or discovery of empty hammer spot; recognizably distressed Thor |
| 9–17 s | Thrym demands Freyja, she refuses | Thrym and Freyja standing next to each other | Giant's demand; Freyja rejecting him with a readable gesture/expression |
| 18–23 s | Loki's plan | Character portraits alone; Loki in `editorial-4` wears a modern black business suit | Loki proposing bridal veil/disguise to furious Thor, in a coherent Norse design |
| 24–29 s | Thor becomes disguised bride | Mostly unchanged warrior portrait with a veil | Actual bridal disguise being assembled/used, not a token veil pasted onto a warrior portrait |
| 30–40 s | Thor eats huge feast; giant grows suspicious; Loki explains | Standing Thor/Loki/Thrym, no food or dinner scene | Wedding banquet, ox/salmon/mead props, visible eating, astonished giant, Loki's intervention |
| 40–50 s | Hammer is brought for blessing; Thor grabs it and reveals himself | Free-standing hammer/portraits, no interaction | Hammer delivered/placed → Thor grabs it → disguise comes off |
| 51–60 s | Showdown and punchline | Nearly unchanged portraits until end | Distinct confrontation/aftermath and comic ending image |

The reference video (a different story about famous diamonds) picks different visuals for each idea: **crown → Victoria → specific diamond → bank/vault → Kollur mine → historical rulers → map → East India Company → archival jewelry → year → Partition/Dhaka → bank building.** It also reuses important items intentionally. Copy this *semantic matching behavior* and concise typography, **not its subject matter and not all shots literally**.

**Do not assume the root cause from this report.** Identify whether character-centric extraction, prompt templates, asset caps, hash keys, reuse policies, scheduler, scene schema, compositor limits or missing QA causes it in the real code. Document findings with file/function names and evidence.

---

## 2. MANDATORY REPOSITORY AUDIT BEFORE EDITING

Inspect the actual active end-to-end pipeline and trace one generated video through:

1. User input handling: topic, raw story, pasted article, URL, input mode, editorial/news/story modes.
2. Research/script drafting versus user-provided verbatim story handling.
3. Speech creation, resulting final narration script, durations, audio timestamps and subtitles.
4. Text-to-scene segmentation: how scenes are counted, their content and IDs.
5. Entity extraction, image-generation provider calls, image prompts, references and asset storage.
6. Deduplication, cache keys, cost/scene/image-count limits, fallback selection and default portraits.
7. Layout templates, Remotion/image compositor, existing animation hooks and transitions.
8. Timeline assembly and sync among audio, subtitles, visuals, metadata and final outro.
9. Quality gates, retries, metrics, persisted manifests and debug reports.

Deliver a short **root-cause ledger** with `observed bug | actual module/function | why it occurs | fix | regression risk`. Inspect the input/output JSON or intermediate render artifacts if available. Do not rewrite the app or rename modules without evidence.

**Compatibility guardrails:** Preserve ProjectHER naming, its typography, visual identity, on-screen word emphasis, watermark, ending/closing package, TTS voices, audio levels, modes, input methods, live app behavior, render contracts, failure/retry semantics and deployed environment. Do not add intrusive labels such as **"AI-generated illustration"** below every image; any provenance requirements belong in metadata or context-appropriate disclosure, not redundant decorative captions. Use a feature flag or backward-compatible schema version if changing shared pipeline contracts. Avoid making the News mode or other flows regress. Keep all current image providers working.

---

## 3. BUILD AN EVENT-FIRST STORYBOARD PLANNER (CORE CHANGE)

Create a first-class **visual beat / semantic event** layer, independent of character/entity extraction.

**Order of operations:**

`normalized input → final narration script → semantic event graph + entity/continuity bible → beat-level visual plan → generated/retrieved media → semantic media verification → speech word/phrase alignment → timed EDL → editorial composition/render → automated QC`.

Planning can overlap speech generation for latency; however, the **final timing must use the final audio and final script**, not estimates. If scripts are revised downstream, recompute beat boundaries and invalidate stale linked assets when the semantics change.

### 3A. Extract visual beats from the script

For every clause or tightly related cluster, extract:

- Exact spoken source span: `narration_excerpt`, stable `script_character_start/end`, speaker/segment and beat ID.
- `event_type`: introduce, action, reaction, exchange, journey, discovery, document, location, object-detail, timeline, comparison, reveal, aftermath, outro, etc.
- `agent/actor`, `verb/action`, `patient/object`, other participants, setting/time period, causal relationship and emotional stakes.
- `visual_intent`: **What must the viewer be able to see to understand this sentence with sound muted?**
- `must_show`: concrete visual requirements (e.g. `hammer in giant's possession`, `Thor eating at table`, `Freyja refusing`).
- `must_not_show`: forbidden misunderstandings/anachronisms (e.g. modern business suit on Norse Loki, empty banquet, Thor holding the hammer before its reveal).
- `shot_role`: character intro, contextual object, documentary artifact, environmental establishing shot, two-character interaction, action tableau, reaction shot, map, date card, animated diagram, final reveal.
- `priority`: P0 for essential plot verbs/climax, P1 for essential context, P2 for decorative connective material.
- Confidence, visual assets needed and fallback strategy.

**Avoid over-segmenting at every comma.** Group clauses that share one coherent illustration; split whenever a **meaningful action, location, object, character relationship or temporal state changes**. Do not plan using only keyword-to-character matches. A story that mentions Thor ten times does not justify showing the same Thor portrait ten times.

### 3B. Sample typed intermediate representation (adapt to actual codebase)

```json
{
  "beat_id": "thor-feast-01",
  "narration_excerpt": "Thor consumed an entire ox, eight salmon",
  "script_span": { "start": 0, "end": 0 },
  "event": {
    "actor_ids": ["thor"],
    "verb": "devours",
    "object_ids": ["roasted_ox", "salmon"],
    "setting_id": "giant_wedding_hall",
    "state": "thor_disguised_as_bride",
    "reaction_actor_ids": ["thrym"],
    "emotion": "absurd_comedy"
  },
  "visual": {
    "role": "action_tableau",
    "must_show": ["Thor disguised as bride", "wedding banquet table", "clearly visible large meal", "Thor actively eating"],
    "must_not_show": ["solo standing portrait", "modern clothing", "empty background with only title text"],
    "composition": "medium-wide three-quarter angle, food foreground, giant reacts behind",
    "style_profile": "projecther-editorial-mythology"
  },
  "audio_alignment": { "start_sec": null, "end_sec": null, "confidence": null },
  "asset": { "type": "scene_image", "id": null, "status": "unresolved" },
  "criticality": "P0"
}
```

The example's `script_span` contains **placeholder offsets**; actual values must be generated from the final script. Do not hardcode sample times/offsets. Create typed schema, versioned manifest, validators and backwards-compatible loaders in the repo's native language.

### 3C. Story-specific versus reusable data

Maintain two separate registries:

1. **Continuity bible** for stable subject identity: Thor's hair/beard/face, Mjölnir's design, Thrym's proportions, Freyja's look, Loki's look, a shared mythological art direction; deliberate wardrobe states for pre-disguise → bridal disguise → reveal.
2. **Event asset registry** for new scenes: `Thor discovers hammer missing`, `Loki shows wedding veil`, `Thor devours feast`, `Thrym reacts`, `hammer handoff`, etc.

An entity image may be reused to anchor a composition, but the scene must still acquire visually explicit event context. Caching must not collapse all action prompts featuring Thor into one portrait. Audit keys and make them include story, beat/action semantics, visual role, continuity revision, model/provider/style and scene prompt version where needed. Permit deduping only for semantically interchangeable images or intentional recurring artifacts.

---

## 4. PRODUCE SCENE-SPECIFIC IMAGES, NOT MORE GENERIC PORTRAITS

### 4A. Write prompts for *visible actions*

Replace portrait-first prompting with scene-first prompting for action beats. Each prompt should include:

`visible action + actor(s) + object being acted on + environment + costume/state + physical interaction + dramatic reaction + camera composition + historical/mythological era + light/color/style + negative constraints`.

**Bad:** `Thor, Norse god, strong man, white background, professional illustration`.

**Good:** `At a giants' wedding banquet in Norse mythology, a massive red-bearded Thor, unmistakably wearing a bridal veil and ornate dress, is seated at a long banquet table and comically devouring an enormous meal. Roasted ox and salmon are visible in foreground; Thrym leans back in astonishment; Loki, acting as attendant, anxiously intervenes. One frozen peak-action storytelling moment, coherent character identities, mythic attire, clean premium editorial-illustration style, readable at phone size, no modern suit, no floating disconnected cutouts, no lettering in the image.`

Another example:

**Bad:** `Mjölnir, Thor, giant, epic scene`.

**Good:** `At the wedding ceremony inside a giant's hall, a giant attendant lays the engraved hammer Mjölnir into the lap of Thor disguised as a veiled bride; Thor's hand has just closed tightly around its handle, eyes intense, Thrym delighted and unaware. Show physical contact, the hammer, bridal costume and nearby giant unmistakably; camera tight medium shot, clear focal point, no later aftermath shown yet.`

Require **entity reference/character bible conditioning** wherever provider supports it (reference-image, seed, image-to-image, character sheet or equivalent). If unsupported, prefer deliberate scene-to-scene character descriptions and continuity checks. Do not fabricate a provider capability.

### 4B. Variety is meaningful, not random

Support visual roles: scene tableau; 2-character confrontation; object-in-hand close-up; action-before/after; reaction; wider setting; map/location; timeline/date; historically relevant document; product/jewel/prop; character intro; emotionally timed reveal. Pick the role based on the current script event.

- Character first introduced → portrait or character + setting.
- Action → action tableau or layered interaction, **not a portrait**.
- Historical claim/News → source-appropriate photograph, map, archive artifact, verified document where available; do not silently misrepresent fictional AI art as a real documentary photograph.
- Mythology → coherent original illustrations; allow surreal mythological content without making the costumes contemporary by accident.
- Abstract concepts → genuinely meaningful iconography/diagram, not random decorative photos.
- Recurrent character/object → may reuse image only if the same scene/action is still being described, or reuse a consistent character *within a new scene*.

### 4C. Preserve ProjectHER editorial look

The target is **not** to plaster 60 seconds of random full-screen movie paintings over the existing UI. Preserve:

- Spacious premium neutral background, clean typography and highlighted word styling.
- ProjectHER top branding/watermark and signature end card.
- A rich mix of cutout foreground, unobtrusive supporting contextual photography, multi-layer illustrations, maps/records, full-scene panels when genuinely needed, subtle depth and editorial negative space.
- Phone-scale legibility, safe margins, consistent shadow/masking/colors/scale, correct text hierarchy.

Add new compositing/layout primitives if required: staging characters **interacting** on one plane, supporting ground/table/environment masks, depth ordering, semantic focus, environment vignette/panel, and movement that emphasizes actions. Images need not be literally animated to depict motion; a *frozen peak-action pose* with correct relationship is better than animated standing portraits. If parallax/keyframes are added, do not imply an action that the image does not depict.

### 4D. Content correctness and identity consistency

Enforce: same Thor/Thrym/Loki across shots, correct accessory and prop custody, correct attire for time/state, logically ordered events, no early reveal/spoiler, no duplicated extra faces/hands, no impossible object contact, no random character imports, no modern business outfit in a Norse scene unless explicitly requested. For real history/news, provenance and fact-checking are necessary for important locations and documents, with uncertainty handled appropriately.

---

## 5. A REAL ASSET SELECTION AND VERIFICATION STAGE

The image-generation call being successful only proves a file exists. It does **not** prove the file shows the story.

Add a media resolver per beat:

1. Draft best-fit scene generation/retrieval prompt.
2. Choose appropriate source: AI image generation for mythic/dramatized action; contextual photos/archives/maps for verified news/history; composite when useful.
3. Generate/retrieve candidates, retaining prompt/seed/provider/model/cost/asset ID.
4. Check media technical integrity: dimensions, corruption, transparency/background, crop-safe critical region.
5. Run **semantic verification** of image vs `must_show` / `must_not_show` and actor/prop continuity. Use a real visual-capable model if one is integrated; otherwise provide a transparent manual review/metadata fallback and record validation limitations. **Never call a text-only keyword match visual verification.**
6. Score content match as more important than pure aesthetic polish; select best verified candidate. Retry/re-prompt targeted missing action or object when feasible.
7. If no candidate illustrates a P0 action: switch to meaningful multi-layer action composition, or mark beat `needs_review`. Do **not** silently substitute an unrelated standing character and declare success.

Possible score components (weights configurable): `event_action_match`, `required_object_visibility`, `actor_identity`, `setting_accuracy`, `visual_readability`, `style_consistency`, `asset_uniqueness`, `historical_sensitivity`.

Use duplicate detection for output QA (perceptual image similarity plus asset reuse IDs), but do **not** treat repeated shot of a recurring jewel or protagonist as automatically wrong. Trigger a warning when **different P0 actions** share the **same generic portrait-only image**.

Image budget must be **beat-sensitive**: estimate needed unique action/context assets after planning. For ~60-second narrative videos, one useful starting expectation is often **10–18 substantively different visual beats** (flexible, not a hard number), mixed with purposeful object/entity reuse. Support more/fewer when the story demands it. Preserve provider quotas, batching, caching and retries, but do not allow the price optimizer to eliminate the very scenes that tell the story. Report planned vs attempted vs accepted images and any downgraded beats.

---

## 6. NARRATION-TO-VISUAL TIMING: AN EVENT-ALIGNED EDL

The renderer must use an **edit decision list (EDL)** matching each selected visual to the exact spoken beat.

### 6A. Source of truth for time

- Freeze the final narration text before voice generation and beat binding, or update linked plans if rewriting is unavoidable.
- Prefer word-level timestamps returned by the TTS provider; if unavailable, perform real forced alignment against **the actual produced audio**.
- If precise alignment is genuinely unavailable, use phrase-level estimates with explicit low confidence, visualize it in QC, and avoid claiming exact alignment.
- Map each beat's `script_span` to beginning/end audio timestamps. Handle pauses, breaths, pronunciation, repeated words, punctuation, SSML/TTS script normalization, and narration time stretching gracefully.
- Time primary scene visual around the onset of the event verb/object; do not show aftermath before the narrative reveals it.

### 6B. Timing rules

- The picture relevant to a clause must become visible at its spoken onset (within a configurable small offset, e.g. ±0.3–0.5 s for P0 events when alignment confidence permits).
- Maintain coverage until the event is finished; do not cut to the next scene on a fixed three-second clock while the existing event is still being narrated.
- On a long multi-step sentence, split: wedding feast → giant's surprise → Loki's excuse; do not hold a one-image portrait over all three actions.
- Avoid abrupt flashing: typical beat lengths around 2–5 s are reasonable, but **semantic content and the actual speech take priority**. Longer holds for deliberate tension/context and shorter sub-beats for climax are acceptable.
- Leave relevant safe area for subtitles/headline; subtitles and word emphasis must remain synchronized independently of image transitions.
- Existing ProjectHER 2–3 s signature outro should start **after story narration and any intentional closing pause**, and not steal visual coverage from the last story line.

### 6C. Persist EDL and render diagnostics

For each beat store:

```json
{
  "beat_id": "thor-reveal-01",
  "audio_start_ms": 0,
  "audio_end_ms": 0,
  "image_asset_id": "asset_tbd",
  "entry_transition": "editorial_cut_or_reveal",
  "visual_required_action": "thor_grabs_hammer_and_reveals_identity",
  "validation_status": "pending",
  "alignment_confidence": null
}
```

**Times are placeholders** in this schema example. Record actual audio-derived times at runtime. A scene preview should display exact spoken phrase, beat start/end, rendered frame/thumbnail, prompt, asset and validation status. Build visibility into how beats map onto audio and output video; it should be possible to catch a mismatch *before* rendering the entire final video.

---

## 7. THE THOR STORY IS THE REQUIRED GOLDEN TEST

Use the exact supplied narration and assets if available. The following **ordered expected visuals** are a **semantic storyboard**; timings must come from actual narration and not this example:

| Beat | Semantic action | Acceptable scene-specific visual | Examples of invalid fallbacks |
|---|---|---|---|
| 1 | Thor discovers hammer gone | Thor searching/empty spot, visibly missing Mjölnir | Hero portrait with text 'stolen' |
| 2 | Thrym has stolen hammer | Giant hiding/holding Mjölnir in giant hall | Random large giant and small Thor |
| 3 | Thrym demands Freyja | Giant gesturing/demanding bride, Freyja in context | Portrait pair separated in empty space |
| 4 | Freyja refuses | Freyja visibly angry/rejecting him | Neutral smiling Freyja portrait |
| 5 | Loki suggests bridal trick | Loki holding/showing veil/gown to skeptical Thor | Loki solo in modern business suit |
| 6 | Thor disguises himself | Thor fitting dress/veil, full comic bridal disguise | Original Thor hero costume plus minor veil only |
| 7 | Arrives at giant wedding | Disguised Thor and Loki in actual wedding hall, Thrym approaches | Cutout Thor on empty background |
| 8 | Thor devours feast | Food-filled banquet, Thor eating, recognizably disguised | Standing Thor with 'ox, salmon' text and no food |
| 9 | Thrym is suspicious | Shocked Thrym at table, physical reaction to feast | Neutral giant standing |
| 10 | Loki explains | Loki improvises explanation to Thrym, both in situ | Solo Loki portrait |
| 11 | Hammer presented for blessing | Giant/attendant brings Mjölnir toward veiled bride | Floating hammer unrelated to bride |
| 12 | Thor grips hammer | Close-up of his hand physically seizing hammer, dramatic focus | Hammer graphic shown beside Thor |
| 13 | Thor reveals himself | Thor tearing veil/disguise and rising with hammer | Unchanged portrait |
| 14 | Giants defeated / comic ending | Distinct confrontation/aftermath and humorous final beat | Repeat Thrym/Thor portrait while punchline plays |

A single strong scene may cover more than one adjacent beat if both requirements are legible and temporally plausible; do not enforce 14 paid images mechanically. Conversely, a dense action beat may need more than one visual. **The metric is visual event coverage, not image count**.

**Independent non-Thor tests:** Add at least (a) a true historical/news narrative featuring persons, places, dates, maps/artifacts and (b) a simple comedy/myth story with several sequential physical actions. The improvement must generalize; do not hardcode "Thor", "Freyja" or "Mjölnir" into common components.

---

## 8. TESTS AND MEASURABLE ACCEPTANCE CRITERIA

### P0 acceptance gates (required)

1. For all **critical action beats** in the golden test, each rendered frame/scene **visibly** illustrates the intended action or a coherent immediate visual counterpart (at minimum, a credible visual representation with actors + specific prop + setting). No solo portrait passes for an eating/grabbing/dressing/confronting beat.
2. The video shows an actual **banquet**, an obvious **disguise**, a genuine **hammer handoff/grab**, and the **reveal** — all while the relevant narration occurs.
3. Each P0 beat's chosen asset either passes visual semantic validation or is explicitly flagged for review; the pipeline cannot silently downgrade critical content to a generic portrait.
4. The `event_type/action` of the selected asset must match the planned beat; avoid repeating one image across different named actions.
5. Visual transitions align to real spoken timing when word/phrase time data is available, with a target onset delta **≤0.5 s for P0 beats** (log actual measured deviations, exceptions and confidence rather than gaming the number).
6. Scene/character continuity passes human-visible comparison, including costumes and hammer custody. Do not use anachronistic suits unintentionally.
7. Story conclusion remains visible until it is narrated; outro begins only after completion.
8. Existing input flows/modes/logo/subtitles/audio/export are verified functional and unchanged except for intended improvements.

### Further quality targets (configurable; report misses honestly)

- Target **≥90% meaningful beat visual coverage** across multiple test stories; **100% P0 beat coverage** in the Thor golden case or explicitly reported hard failure for manual review. Define coverage as human-/vision-verified `must_show`, not a count of generated file IDs.
- For P0 action beats, **zero** substitutions of a generic static portrait without the described action.
- A reasonable variety of role types (objects, characters, interactions, settings, timelines, maps as applicable). No mandatory quota when content does not support them.
- No unapproved repeated full-frame image covering **multiple unrelated actions**; purposeful reuse of characters/objects is acceptable.
- Mobile-scale legibility: faces, action props, visual relationships, subtitle-safe area and brand-safe area all visible in target 9:16 preview.
- Track additional image generation cost and render latency; do not sacrifice event semantics for marginal savings.

### Minimum regression/testing work

- Unit tests: segmentation, action extraction schema validation, script-span mapping, asset cache key uniqueness, forbidden fallback behavior, intentional reuse, state transitions, EDL mapping.
- Integration test: script → audio → visual plan → real image candidates → scene validation → Remotion render → preview/QC manifest.
- Golden-story snapshot/storyboard test for Thor plus non-Thor stories.
- Visual review montage: representative image every 1–3 s **with the aligned narrated text**; compare changed implementation to both supplied generated videos and editorial reference.
- Validate both editorial layout and at least one existing other mode/input path against regression.
- Failure test: image provider returns same standing Thor portrait for `eating` and `grabbing` — system must flag/retry, not accept as a successful action render.
- Failure test: provider exceeds rate limit/missing visual judge — system logs degraded verification honestly and protects important scenes.

---

## 9. IMPLEMENTATION ORDER — KEEP CHANGES CONTROLLED

**Phase A — Diagnosis and visibility**

- Locate real functions/inputs for scene segmentation, entity image generation, caching, time mapping and renderer. Trace a single render.
- Add logs/manifest for `narration excerpt → beat → visual intent → prompt → candidate → chosen asset → exact timing → rendered frame`.
- Establish golden test inputs, original snapshot/report and root-cause ledger.

**Phase B — Semantic beat planner**

- Define structured versioned schema, extractor prompts, output validation and retry policy.
- Add event/action-centered plan and continuity bible.
- Retain backward compatibility while routing new editorial render path to beat planner.

**Phase C — Action-specific assets**

- Build contextual generation prompts and diverse asset strategies.
- Fix cache/dedupe and selection rules for scene-level media.
- Add semantic image QA/retry/fallback, with strong handling for P0 beats.
- Add composition/layout support for multi-subject action tableaux and contextual props.

**Phase D — Temporal binding**

- Resolve beat start/end from final narration/audio, build EDL, integrate renderer and maintain captions/outro.
- Add preview/manifest + alignment/coverage instrumentation.

**Phase E — Verification and rollout**

- Render new Thor sample, a history/news sample and a second action story.
- Make before/after thumbnail/contact sheets, actual video outputs and evidence-based audit notes.
- Fix any remaining mis-mapped or inaccurate events before declaring work complete.
- Keep feature flags/rollback or safe migration path as appropriate; preserve existing stable behavior.

---

## 10. REQUIRED OUTPUTS FROM YOU, THE CODING AGENT

At the end, provide:

1. **Root cause report** naming the actual modules/logic that caused portrait-only reuse.
2. **Code changes** made, with affected files and brief architectural reasoning; no fake changes or simulated implementation.
3. **Schemas and prompts** for event-first beat planning, action visual generation and media verification.
4. **Before/after storyboard/coverage table**, showing every important spoken event and corresponding chosen new scene.
5. **Actual rendered videos and contact-sheet previews**, not just prompt output.
6. **Quality metrics**: beats, unique contextual/action assets, intentional reuse, unresolved scenes, failures/retries, per-beat semantic coverage, alignment deltas, time/cost when measurable.
7. **Test commands/results** and a regression checklist for editor/news/story modes and article/URL/text inputs where supported.
8. **Known limitations** including any lack of word-level alignment, unavailable image-reference conditioning or absent visual-semantic judge, and safe fallback behavior.
9. **Deployment/readiness notes** for the existing Cloud Run or equivalent deployment pipeline if affected.

**Definition of done:** Watch the resulting Thor video with the sound off: can a person infer that the hammer is stolen, Freyja rejects a demand, Loki creates a bridal disguise, Thor eats at a wedding banquet, Thrym is shocked, the hammer returns for the ceremony, Thor grabs it and reveals himself, and the story ends with the intended punchline? If **not**, the fix is not complete, even if the generated illustrations are individually beautiful.

**Important final instruction:** Do not solve this as a superficial increase of image count, a slideshow shuffle, a background animation, or a global scene-duration tweak. **Fix the semantics of story-to-scene planning, scene-specific image generation, verification, and spoken-event alignment end to end.**
