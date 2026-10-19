# ProjectHER — Narration-to-Visual Correlation Audit

**Inputs reviewed:** `editorial-3.mp4` (61.08 s, 1080×1920, 30 fps), `editorial-4.mp4` (63.08 s, 1080×1920, 30 fps), `reference-ai-video(9).mp4` (58.21 s, 720×1280, 30 fps). All three contain audio streams.

**Audit method:** Reviewed time-sampled frames across the entirety of each clip, with closer inspection of representative full-resolution frames. Story-to-visual comparisons are based on visible captions and scenes, and the supplied Thor-story context; no separate word-accurate transcription or source-code audit was possible here. The times below are approximate visual positions, not forced-aligned speech times. The reference video covers a **different story** (diamond ownership/provenance), so the comparison is of **storytelling behaviors**, not matching content shot for shot.

## Executive finding

The generated clips' individual illustrations look usable, but their editorial renderer appears to associate narration with **named entities and reusable portraits**, not with **specific plot events**. As a result the story's narrative verbs — steal, demand, refuse, disguise, eat, react, reveal, seize, confront — are usually never portrayed. Words change while the corresponding underlying visual stays nearly the same. The reference uses varied content-specific visuals including jewels, monarchs, maps, mine imagery, archival records, a date, and a bank to signify the precise subject of each clause. The fix is an **event-first shot and asset plan with audio-linked time spans** and visual semantic QA, rather than merely buying/generating more pictures.

## Comparison by interval — both generated clips

| Approx. position | Story content visible in captions | `editorial-3` observation | `editorial-4` observation | Required visual behavior |
|---|---|---|---|---|
| 0–8 s | Thor's crisis; Mjölnir stolen | Repeated central large dark artifact/shape, small character cutouts, opening text | Repeated standing Thor with Thrym/Thor miniatures; no theft shown | Establish Thor/hammer; visualize an empty hammer place, hammer being stolen, or Thrym hiding it |
| 9–17 s | Thrym demands Freyja; she refuses | Big standing Thrym + small standing Freyja, repeated | Similar portraits/standing pair, repeated | Show demand, reaction, Freyja actively refusing or turning away; stakes clear |
| 18–23 s | Loki devises disguise plan | Large Loki portrait and small Thor | Modern black-suit Loki portrait beside Thor (anachronistic style mismatch for mythological setting) | Loki proposing disguise to Thor; costume/veil props, facial expressions, visual plan |
| 24–29 s | Thor puts on bridal disguise | Thor's mostly unchanged costume with veil on portrait | Similar veil on otherwise normal Thor costume | Clearly legible actual bridal disguise, preparations, joke; preferably scene with Loki helping; intentional costume continuity |
| 30–40 s | Wedding feast, excessive eating, suspicions/explanation | Thor, Thrym or Loki portrait cutouts; no banquet, food, or eating | Standing Thor portrait with narration text such as 'consumed an entire ox'; still no food/feast | Wedding table, ox/salmon/mead, Thor eating in disguise, Thrym reacting, Loki improvising excuse |
| 40–50 s | Hammer used for wedding blessing, Thor grabs it, reveals himself | Standing portraits and an isolated hammer prop, with no grab or reveal action | Standing Thor and Thrym, no actual sequence of hand taking hammer or reveal | Hammer placed on bride's lap → Thor's hand grips handle → torn veil / furious reveal |
| 51–60 s | Thrym's fate and punchline | Static Thrym / Thor pairs while voice reaches action-ending | Static Thrym / Thor pairs while punchline plays | Show actual confrontation/aftermath, then a deliberately timed closing visual punchline, not just another standing portrait |

**Additional issues:**
- Both renders use a very narrow group of illustrated subjects repeated in different arrangements; zoom, position, and caption updates do not make a portrait a scene depicting an action.
- `editorial-4` renders Loki in a contemporary black business suit, which clashes with the Norse-era visual storytelling elsewhere. A global 'style' label without character/costume controls is insufficient.
- `editorial-3` and `editorial-4` render different identities/styles for the same recurring named characters across independent generations. Within-video consistency seems better, but cross-shot identity and scene-specific wardrobe must be explicit.
- Assets sometimes appear based on presence of a named character rather than relevance of the current narrated **verb**, environment, and object.
- Visuals at the climax remain similar to those used earlier, reducing payoff precisely when scene specificity matters most.
- The existing white/gray editorial canvas, typography, logo and general cleanliness can be retained. Their removal is **not** required and would be a regression.

## What the reference does differently

| Approx. time | On-screen subject | Why it is stronger as visual storytelling |
|---|---|---|
| 0–9 s | Crown, Queen Victoria, named diamonds | Introduces exact physical subjects and the historical figure rather than one recycled character portrait |
| 9–13 s | Diamond ring/jewel and Kollur mine image | Visual type switches from artifact to its geographic source as the narration switches topic |
| 15–24 s | Maratha riders, Persian ruler, India map, Ranjit Singh | People **plus** location/ownership changes; illustrative supporting geography adds context |
| 27–35 s | East India Company emblem, old jeweled ring records, Queen Victoria | Event/ownership transitions portrayed by institution, documents and ruler |
| 36–48 s | India context, Khwaja Alimullah, '1908', ring and administrative context | Changes visual category to a portrait, date card and historical prop when needed |
| 48–58 s | Partition map, Dhaka, bank building | Location, geopolitical change, and present-day custody given directly relevant visuals |

The reference also reuses certain key jewels and portraits intentionally. That is fine. **Reuse is useful when an artifact recurs in the story; it is harmful when reused in place of a required event visual.** The reference has a predominantly editorial/infographic style, not fully acted cinematic footage. The desired solution is a hybrid visual vocabulary: **dynamic documentary assets + action-bearing illustration/composites, presented within the same premium editorial aesthetic**.

## Root cause hypotheses — verify against code, do not assume

1. Character extraction is driving scene asset selection, rather than predicate/event extraction.
2. Image generation happens once per entity, with reuse until video end; dynamic scene requests never exist or are discarded.
3. Generic image template such as 'character portrait of X' is reused for scene narration even when verbs and locations change.
4. Asset caps, caching keys, or deduping are organized by character rather than `(story, action beat, prompt identity, visual role)`.
5. Scene schemas contain `character`/`asset_id` but omit `visible_action`, `props`, `setting`, and `must_show`.
6. Remotion compositor supports only free-floating cutouts, not staged interactions and action-based compositions.
7. No post-generation semantic image QA verifies the requested action really appears in the candidate image.
8. Subtitle/scene timelines may be keyed to approximate chunks rather than the actual spoken phrase timestamps.

## Severity and correction priority

**P0 — must fix:** event-first scene planning; scene-specific action depiction; proper narration/asset alignment; reject portrait-only visuals for high-action beats; avoid wrong/missing props.

**P1 — high value:** stable character/style references; meaningful geographical/temporal props; better variety of visual types; scene-specific compositions; QA coverage report.

**P2 — polish:** motion choreography, detailed camera/easing changes, sophisticated 2.5D/parallax and supplementary effects. Motion must not be used as a substitute for illustrating the right event.

## Preferred expected output for the Thor story (conceptual)

1. Thor discovers his hammer missing; conspicuously empty place/hand and alarmed reaction.
2. Thrym hides or displays the stolen hammer in a giant's hall.
3. Thrym demands Freyja; Freyja visibly rejects the proposal.
4. Loki presents a veil/dress and persuades an angry Thor.
5. Thor genuinely disguised as a bride arrives at a wedding hall, escorted by Loki.
6. Thor devours food at the feast; ox/salmon/mead visible.
7. Thrym is visibly astonished; Loki explains while Thor stays in disguise.
8. Wedding ceremony; giant places Mjölnir within reach of the disguised Thor.
9. Close-up of Thor's hand gripping Mjölnir; veil pulled away.
10. Thor's reveal, confrontation, impact and short comic final payoff.

A single still can illustrate a clear action moment if it contains interacting characters and explicit props. Full animation or expensive video generation is **not** required.

## Confirmation criteria

- Every meaningful spoken event has a corresponding planned visual with a `must_show` subject/verb/object specification.
- A portrait alone cannot pass QA for scenes requiring eating, disguising, stealing, seizing or confrontation.
- The requested visual is visible during its spoken clause, not merely somewhere in the video.
- Key props (Mjölnir, bridal attire, banquet) and setting (giants' wedding hall) are legible at mobile resolution.
- Character identity and wardrobe changes are intentional, not random.
- The implementation does not break other ProjectHER modes, input types, narration, logo, watermark, signature outro or the reference-inspired editorial typography and composition.
- The pipeline emits a human-reviewable scene plan and visual coverage/audit report; no silent fallback to a generic character cutout for high-value beats.

## Visual contact sheets

Generated from the uploaded videos at three-second intervals; included separately in `reference_frames/`:

- `editorial-3_3s_montage.jpg`
- `editorial-4_3s_montage.jpg`
- `reference_3s_montage.jpg`

These are time-sampled visual observations, not proof of word-level audio alignment or evidence that a particular internal code module is at fault.
