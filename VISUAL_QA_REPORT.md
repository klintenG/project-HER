# Visual and audio QA — Osiris integration

Primary review: [osiris-review.mp4](output/three_branch_osiris_curated/osiris-review.mp4). Status: **reviewable render; full production visual acceptance not passed**.

## What was actually exercised

The live run used configured LLM/image/TTS adapters, real new action illustrations, cutout processing, local Whisper alignment, the existing typed timeline, Remotion Chromium and encoded delivery QA. The final curated recomposition reuses those exact audio samples/timings, removes planned embedded prop duplicates, and selects the stronger existing Branch 3 resurrection artwork. It makes no extra image/TTS calls.

|Measurement|Final curated result|
|---|---|
|Encoded video|1080×1920, 30 fps, H.264, yuv420p, BT.709|
|Runtime|52.000 s including 2.700 s configured branded slate|
|Canonical script|139 words, 13 sentences; SHA256 `57cbea8ad6d279b2b4600a9f171bf645456c41b010f1146b4e744bf89ea572b8`|
|Speech timing|139 words with actual `whisper_forced` alignment; no estimated timings|
|Last aligned word|“heir.” ends at 48.280 s|
|Final story composition|Ends at 49.300 s; 1.020 s after last word|
|Narration master|48.340 s; no overlap with principal brand-slate reveal|
|Encoded loudness|−15.07 LUFS|
|Encoded true peak|−1.78 dBTP|
|Black-frame/duration gate|Passed; no black intervals; actual duration matches expected|
|Music|Disabled by existing configuration; outro is intentionally silent|
|Composite action fallbacks|11 recorded; articulated-action acceptance remains false|

Numbers come from `osiris-review-metrics.json`, `osiris-review-visual-quality.json`, `review_result.json` and the manifest. “Measured alignment” establishes provenance, not perceptual synchronization certainty: the lowest word probability is about 0.0008 and alignment warnings need listening review.

## Evidence and semantic comparisons

`output/three_branch_osiris_curated/visual_evidence/` contains genuine encoded frames alongside the three supplied MP4s. `sample_audit.json` records event-specific timestamps. Different source timestamps are selected for the same narrated event; no equal-time merge or generated stand-in evidence was used.

Comparison sheets cover opening, setup, chest, trap/river, search, scattering, revival, underworld, Horus, resolution and outro. Source Branch 3 has no comparable rhetorical opening or resolved Horus aftermath; those cells are explicitly absent. Branch 1 has no equivalent branded final slate. Source timestamps are approximate event samples from the supplied audit and should not be treated as word alignments.

For each detected physical action, motion strips sample −0.25, 0, +0.25 and +0.50 s relative to its actual aligned onset. Stage-only pixel differences exclude the headline zone. The existing encoded 5 Hz activity scan covers the video, but pixel change can come from camera/whole-cutout motion and does not prove a lid closing or a hand making contact. No full human-speed playback/listening pass is claimed.

A separate real Chromium seek review on the controlled cached comparison rendered opening, full slate and complete-caption mode. The repeated frame was pixel-identical after seeking out of order. TypeScript/branding/News contract checks passed. These checks are not substitutes for the visual defects below.

## Findings

|Event|Observed result / remaining issue|
|---|---|
|Opening|The new murder illustration failed existing bounded relevance checks; a standing Seth fallback was used. The script hook is source-supported, but its action portrayal remains degraded.|
|Royal couple|A contextual couple image replaces portrait-only staging. Planned membership prevents adding another Isis; actual anatomy/appearance still require review.|
|Chest setup|New artwork contains Seth and an open chest. The final recomposition removes the separate duplicate chest from its support layers. The lid is illustrated open rather than physically articulated.|
|Entering / trap|New artwork depicts Osiris within the chest, an improvement over a portrait beside it. Entry, lid closure and sealing still lack separately animated body/lid occlusion; whole-image motion is explicitly a fallback.|
|River disposal|New illustration depicts a thrown chest and compact water context. Directional movement follows the verb, but matte defects on Seth and a flattened event need review.|
|Search / recovery|Kneeling Isis and a chest/recovery context are clearer than standing portraits. Searching and recovering share a composite rather than a fully staged discovery action.|
|Scattering|A non-graphic fragments/map-like tableau conveys scattering. It is illustrative, not vetted geography. Do not treat its outline or fragment locations as historical evidence.|
|Restoration|The new accepted image appears to show an incorrect second figure. The primary curated review replaces it with the stronger cached Branch 3 Isis/Osiris magic illustration. This fixes event clarity while introducing a visible cross-run appearance/style change. Provenance is retained; identity continuity is not declared passed.|
|Underworld|A seated Osiris communicates his new role. Motion remains deliberately restrained; throne/body matte edges need inspection.|
|Horus challenge and outcome|The new script explicitly says Horus defeated Seth and claimed Egypt's throne. New confrontation/victory artwork is present. The defeated figure's identity/anatomy remains subject to manual review.|
|Payoff / branding|The living/dead roles resolve the story. Final phrase holds before a separate navy/gold ProjectHER slate, with no speech cut-off or duplicate branding system.|
|Typography|Words use a full-contrast mask reveal rather than passing through pale gray opacity. Bundled-font geometry and measured onsets remain fixed. Early reveal frames intentionally show partial glyphs; mobile/full-speed review is still necessary.|

## Acceptance disposition

Passed structurally: one production renderer, locked canonical script, exact word coverage, measured timing provenance, semantic beat traceability, planned duplicate-membership checks, complete Horus outcome, readable final hold, configured watermark/outro, encoded video/audio checks, preserved provider settings and unchanged unrelated mode implementations.

Not passed or not independently verified: separately articulated critical actions, all character/prop anatomy and matte edges, cross-run character identity continuity, perfect word-emphasis perception, lower-cost primary reuse for exposition, full playback/listening and all production story/visual acceptance criteria. The generated-source run also reports one degraded sentence (`s1`). Frame activity or a successful render must not turn those into passing visual claims.

The selected review is a concrete improvement and a usable comparison artifact. It is not a basis for saying the entire master-prompt definition of done has been achieved.
