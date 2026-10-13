# Reference-Style Editorial Video: Forensic Comparison and Codex Master Implementation Prompt

**Input videos**
- Reference: `reference-ai-video(5).mp4` (user's reference, originally named `reference-ai-video.mp4`)
- Current output: `editorial-remotion.mp4`

**Objective:** Change the **existing** AI video generator so that its selected editorial/news visual mode generates the **same kind of kinetic-typography, narration-driven, high-density editorial motion storytelling** shown by the reference—not just the same gray background and historical cutout illustrations. Preserve other functioning input modes and generation flows.

> **Important comparison limitation:** The source stories are different. The reference tells a story about the Kohinoor and Daria-i-Noor diamonds; the generated video is about Zheng Yi Sao. Absolute timecode correspondence cannot be interpreted as the same event. Compare visual grammar, pace, motion technique, text timing, composition, sound, and storytelling function. Also, video frame/audio analysis does not reveal the original editing project or exact code. Suggested implementation parameters below are **starting targets**, not measured original source settings.

---

# PART A — OBSERVED FORENSIC FINDINGS

## A1. Verified media facts

| Metric | Reference | Current output | Interpretation |
|---|---:|---:|---|
| Duration | 58.211 s | 56.128 s | Both fit a roughly one-minute short; duration alone is not the problem. |
| Dimensions | 720×1280 | 1080×1920 | Both 9:16. The generated file's higher pixel count does **not** indicate better editorial quality. |
| Frame rate | 30 fps | 30 fps | Same temporal delivery resolution. |
| Video codec | H.264 | H.264 | Neither is a limiting factor. |
| Audio codec | AAC | AAC | Neither is a limiting factor. |
| Integrated audio loudness (EBU R128) | approx. −14.1 LUFS | approx. −15.0 LUFS | Similar overall loudness; do not try to solve storytelling via a simple gain increase. |
| 0.2-s frame comparison: average changed pixels (grayscale delta >8/255) | approx. **5.76%** | approx. **0.92%** | Reference has about **6.2×** the frame-to-frame changed-pixel proportion **for these two videos**. A rough motion/activity proxy, **not** an animation or quality score. |
| 0.2-s frame comparison: intervals with very low absolute pixel difference (mean <0.9/255) | approx. **46%** | approx. **81%** | Current output spends a substantially higher proportion of sampled intervals virtually unchanged. |
| 0.25-s audio windows under −35 dBFS RMS | 1/233 | 25/225 | Reference maintains a much more continuous audio floor; current mix contains noticeable measurable low-level gaps. |

**Method:** FFprobe stream metadata; actual video stills at one-second intervals and focused half-second intervals; small, common-size grayscale frame differences sampled approximately every 0.2 seconds; audio RMS windows and EBU loudness analysis. Pixel-difference figures are susceptible to motion blur, text changes, source contrast, compression and content differences. Treat as evidence of an activity gap, not a hard artistic target to game.

## A2. Overall verdict

**Already reasonably close:** vertical framing, light neutral background, dark bold sans-serif type, isolated subjects with ample negative space, basic staged insertion/removal, approximately one-minute runtime.

**Still materially different:** scene-specific art direction, motion density, voice-to-type choreography, dynamic text placement, image scale, spatial depth and compositing, asset relevance/credibility, non-repetitive scene grammar, narrative tension, sound-bed continuity, strong opening, memorable closing.

**Root cause hypothesis to verify in code:** The renderer seems driven by repeated fixed-layout content cards (top headline + small center illustration + image label + bottom sentence), instead of a **semantic beat timeline** in which narration, keywords, assets and movements are programmed together. Do **not** assume this code architecture until repository inspection confirms it.

## A3. Reference visual language — specifically observed

1. **Visual thought, not caption card:** From 0–2 s the crown/diamond and sentence fragments are co-composed; by 3–5 s Queen Victoria, two comparative jewels and their names share one illustrative explanation. Words become part of the visual explanation rather than a persistent subtitle row.
2. **Partial-sentence reveals:** At ~18–21 s, “the Persian ruler” gains the heavier “Nadir Shah,” then the map and “invaded India” appear, then “took both diamonds.” Text arrives as meaningful chunks in the order of narrated information.
3. **Real changes within one scene:** At ~31–35 s the historical gem comparison gives way to Queen Victoria, a crown, and an emphasized “the Kohinoor,” followed by a contrast heading for Daria-i-Noor. It is not merely the same illustration sliding in and being held.
4. **Variable visual emphasis:** Keywords and names such as Nadir Shah, Ranjit Singh, India, Kolkata, 1907, 1947, and Sonali Bank take noticeably different sizes and placements; small bridging words are lighter or smaller.
5. **Different image functions:** Historical portrait cutouts, jewels, India maps, mine photograph, archival/pictorial evidence, company crest, city landmark, year card, and architectural image. Assets are selected according to the **meaning of the phrase**. Some images have soft lower feathering/fade; some have strong floor shadows; some archival photos are shown as simple rectangles.
6. **Editorial layout families:** comparative pair; big object with floating text; central portrait + statement; map silhouette + label; full-width image/document evidence; big-year pivot; typographic bridge; location switch; concluding place/object reveal. These alternate with purposeful repetition.
7. **Neutral, restrained grade:** mainly off-white/light-gray background, charcoal or gray copy, desaturated pictorial assets, modest shadow, rare natural asset colors. Motion and information hierarchy carry the excitement, not bright transitions.
8. **Reference has flaws too:** Certain claims/images may require sourcing or fact checks. Recreate its **presentation grammar**, not unverified history, accidentally misleading imagery, or inaccessible microtext.

## A4. Current generated video — specifically observed

1. **Weak launch:** ~0–1.2 s has an empty-looking upper frame while the first long bottom sentence starts. The first strong title/subject pairing only appears around ~1.5 s. This wastes the crucial first second.
2. **Unbalanced repeated template:** frequent illustration around central upper half, heavy heading at the top, tiny subject name/`Illustration` directly beneath, and a short narration caption far below. This produces disjointed reading zones and large stretches of unused space.
3. **Very small, repeated imagery:** Zheng Yi Sao character is held around ~1.5–11 s and returns again ~37–43 and ~50–56 s. The warship and emperor pairing persists ~14–21 s, including near-identical subsecond frames. A modern-looking “Government Official” graphic lasts ~31–36 s. Such recurrence is visibly more static than the reference.
4. **Metadata contamination:** literal labels including `Illustration` appear under `Zheng Yi Sao`, `Pirate Fleet`, `Imperial Warship`, `Chinese Emperor`, `Merchant Vessel`, `Government Official`, `Pardon Scroll`, `Wealth`, `Blackbeard`. The label is redundant, distracting, and especially harmful at very small font sizes.
5. **Narration and screen copy are partitioned incorrectly:** persistent bottom sentence fragments (e.g. “Yet, her forces proved resilient, successfully…”) carry the spoken information separately from static top headings (“most powerful pirates,” “1807,” “Chinese emperor,” “terrorized merchant vessels,” “1810,” “1844”). The reference instead turns the narration's own key words into evolving main motion graphics.
6. **Heading repetition instead of narrative transformation:** 1807 holds across ~7–12 s; “Chinese emperor”/same object combination ~13–21; “1810” ~37–43; “1844” ~51–56. Big year cards can be effective, but not if the remainder of each scene is nearly still.
7. **Visual credibility inconsistency:** a cartoonish modern-official-style image for a Qing-government context and inconsistent historical figure/ship art styles undercut trust. The comparison reference uses mixed but more information-specific archival/historical assets. Do not portray unverified illustrative portraits as authenticated photographs.
8. **Weak ending:** final frames repeatedly hold “1844” + small figure + routine explanatory line. No composed visual payoff. Reference also ends simply, but with a final physical/location reveal tied to the story.
9. **Motion is far less continuous:** verified quantitatively in A1 and visibly in focused half-second strips. There are some entrances/fades in the generated video; it is **not** accurate to claim there are none. Rather, too much runtime is spent in nearly identical states after an entrance.
10. **Audio-bed difference:** while the reference remains above the −35 dBFS quarter-second threshold for virtually the whole video, the current output has many intervals below it. This supports a request to inspect narration pauses, music/ambience coverage, crossfades and normalization. **The audio measurements alone do not prove what instruments or sound effects are present.**
11. **Script language is serviceable but stiff:** phrases visible in the generated copy include “achieved the extraordinary,” “her forces proved resilient, successfully,” “government pressure intensified while internal rivalries…,” and “defying the typical end for such a notorious figure.” This reads like condensed encyclopedia prose instead of a gripping 55-second spoken narrative.

## A5. Essential corrections requested by the video owner

**Correction 1 — remove AI/illustration labels:** Under an image, show **only** a useful real-world name (e.g., `Zheng Yi Sao`, `Imperial Warship`, `Blackbeard`), and only when a name truly aids recognition. Do **not** display `Illustration`, `AI Illustration`, `AI Generated`, `Generated Image`, `Stock Image`, `Visual`, `Concept Art`, or similar image-source descriptors in the video. Do not blindly remove “illustration” if it appears as part of a legitimate historical quote; target renderer-added provenance labels. If synthetic/reconstructed imagery requires disclosure, put it in the **video description/metadata or a dedicated disclosures workflow**, not repetitive labels underneath every asset. Never falsely present AI visuals as authentic archival evidence.

**Correction 2 — rewrite for spoken narration:** Strong first 1–2 s, tension and contrast, one coherent arc, short sentences, nouns/verbs instead of stacked bureaucratic phrases, precise facts, a payoff, and an explicitly synchronized scene plan. Preserve source details supplied by the user; don't silently invent extra events.

**Correction 3 — style parity:** Prioritize the reference's visual storytelling system. Cosmetic change alone is inadequate. Do not aim for a misleading perfect-pixel copy from unrelated content/assets; aim for equivalent **rules, cadence, motion design, visual density, and professional polish**.

**Correction 4 — texts and motion:** Upgrade from static top heading + bottom subtitles to phrase-synchronized, spatially integrated kinetic typography. Build multiple real art-directed motion patterns and transitions; use them based on story semantics rather than random presets.

---

# PART B — SECOND-BY-SECOND OBSERVATION LOG

The following is a **one-second keyframe audit**, supplemented by half-second inspections at 0–5, 18–22, 31–35, and 45–49 seconds. A 1 Hz audit is not a claim that every individual source frame has been manually enumerated; quantitative frame comparisons sample approximately 5 Hz. The observations below refer to what is visible **at or near** the given timestamp and are not word-level audio transcriptions.

## B1. Reference video — 0 through 58 seconds

| Time | Frame observation / active idea |
|---|---|
| 00s | Large isolated royal crown; immediate physical object opens the story. |
| 01s | “The Kohinoor wouldn’t be the world’s…” builds above a large gemstone. |
| 02s | Phrase extends to “world’s most”; jewelry/bracelet visual replaces the first gemstone, with “famous” below. |
| 03s | Queen Victoria arrives; two rings/jewels presented as a comparison with names. |
| 04s | Phrase expands to “if Queen Victoria had chosen”; queen and side-by-side jewels remain composed. |
| 05s | Daria-i-Noor grows in prominence; Queen Victoria remains for context. |
| 06s | Large diamond and rhetorical question about the Daria-i-Noor; single focal object. |
| 07s | A bank vault appears with a geography silhouette and initial “It’s”; abrupt semantic pivot. |
| 08s | “It’s locked inside a bank vault” resolves over the vault. |
| 09s | “in Bangladesh” is revealed beneath; place context added after the vault idea. |
| 10s | Named Daria-i-Noor gem in an isolated product-like composition. |
| 11s | Mine photograph with beginning text “in the…”; switch from illustration to evidence/location. |
| 12s | Kollur mine in India completed; geographic source established. |
| 13s | Black-and-white historical mounted party appears with “For a long time.” |
| 14s | Ownership sentence gradually builds above the historical party; bottom bridge begins. |
| 15s | “the Maratha rulers” emphasized beneath riders; prior sentence resolves. |
| 16s | Typographic bridge “before passing to the…” with no dominant object. |
| 17s | “Mughal emperors” completes; pure-type shot highlights new ownership. |
| 18s | Nadir Shah begins as new historical character below “the Persian ruler.” |
| 19s | Proper name “Nadir Shah” gains large emphasis above the portrait. |
| 20s | Map of India appears behind portrait and “invaded India” replaces name as headline. |
| 21s | “took both diamonds” enters lower portion while invasion/map/portrait context persists. |
| 22s | Typographic bridge “both gems” with a clean reset. |
| 23s | Ranjit Singh portrait enters; “both gems eventually reached” grows above. |
| 24s | “Ranjit Singh” appears prominently under portrait. |
| 25s | “the ruler of Punjab” changes the top wording while historical portrait remains. |
| 26s | East India Company crest replaces portrait; corporate takeover story begins. |
| 27s | “when the East India Company annexed…” builds around the crest. |
| 28s | Display-case/jewelry inset starts; material transition to what happened to the gems. |
| 29s | Display case held as a short setup rather than a permanent template. |
| 30s | East India Company heraldry shown in boxed framing. |
| 31s | Side-by-side gem document/photo with “They were later presented.” |
| 32s | “to Queen Victoria” added to the lower part of the photo comparison. |
| 33s | Queen Victoria, crown, and “She kept…” stage the split in outcomes. |
| 34s | “the Kohinoor” becomes large; next contrast “While…” appears. |
| 35s | Frame clears to “While the Daria-i-Noor” for the counterpoint. |
| 36s | Gem over India Gate illustration; “India” large behind/above. |
| 37s | Gem over Kolkata bridge; location transforms from India to Kolkata. |
| 38s | Archival portrait panel emerges with name beginning. |
| 39s | Portrait plus identifying “Khwaja Alimullah”; new human/historical focal point. |
| 40s | “the Nawab of Dhaka” appears beneath portrait. |
| 41s | “purchased it” completes beneath portrait; story progresses using paired text. |
| 42s | Very large “1907” title card; rhythmic date beat. |
| 43s | New historical portrait of Nawab Salimullah overlays the date. |
| 44s | Diamond with “mortgaged the diamond” above it. |
| 45s | “to the…” builds beneath the phrase as the gem stays visible. |
| 46s | “to the government / for a loan” completes, with “for a loan” very large. |
| 47s | Indian-subcontinent geographic silhouette; “After the partition” appears. |
| 48s | “of India” and “in” expand the partition explanation. |
| 49s | Large “1947” below map; date reveal. |
| 50s | Kolkata city landmark + gem; location transition. |
| 51s | Kolkata composition persists briefly with subtle changes. |
| 52s | Dhaka landmark replaces Kolkata; the same gem anchors the geographic relocation. |
| 53s | Typography-only statement “Today it remains preserved”; a clean breath/pivot. |
| 54s | Same concluding statement held for comprehension. |
| 55s | Sonali Bank architecture begins to enter, title growing behind/above. |
| 56s | “Sonali Bank” becomes a large heading over architecture. |
| 57s | “a state-owned bank” completes at bottom. |
| 58s | “in Bangladesh” completes the final location reveal. |

**Reference animation notes:** Within the 0–5 s half-second strip, an opening crown is replaced by a gemstone and then jewelry while words appear in segments; around 2.5 s an overlapping faded handoff leads into the queen comparison. At 18–22 s, name, map, action and outcome are introduced in waves. At 31–35 s, the gem image gives way to Queen Victoria and changing contrasting statements. These changes happen **inside** scenes, not only at cuts.

## B2. Generated video — 0 through 56 seconds

| Time | Frame observation / active idea |
|---|---|
| 00s | Mostly bare upper canvas, a small line of narration text near the lower part. |
| 01s | Opening narration remains in small bottom type; no strong visual focal event yet. |
| 02s | Zheng Yi Sao small portrait + `Zheng Yi Sao / Illustration`; title “most powerful pirates” appears. |
| 03s | Essentially same portrait + headline + label, with another bottom narration fragment. |
| 04s | Heading goes away but portrait and `Illustration` label persist; bottom caption changes. |
| 05s | Same portrait; narration line about commanding hundreds of ships. |
| 06s | Same small portrait; little active story visual beyond narration. |
| 07s | Large static “1807” is introduced above the same portrait. |
| 08s | Date/portrait held with “In 1807…” sentence below. |
| 09s | Same date/portrait; bottom text advances to fleet control. |
| 10s | A small pirate fleet ship added beside the repeated portrait; dual `Illustration` labels. |
| 11s | 1807 + two objects persist; bottom line mentions the South China Sea. |
| 12s | Same composition continues, almost no intervening motion. |
| 13s | Generic “Chinese emperor” character replaces woman; subject label includes `Illustration`. |
| 14s | Imperial warship added to emperor; heading and two labels visible. |
| 15s | Same emperor/warship pairing; narration says he dispatched warships. |
| 16s | Unchanged pairing; explanatory subtitle “dismantle her growing maritime power.” |
| 17s | Same pairing still held. |
| 18s | Same pairing; bottom line changes to forces proving resilient. |
| 19s | Nearly identical emperor/warship/labels, no battle transformation. |
| 20s | Same illustration pair remains. |
| 21s | Text advances to defeating imperial fleets; emperor/ship pair persists. |
| 22s | Emperor disappears, one imperial warship remains centered small. |
| 23s | Single warship still held with bottom combat statement. |
| 24s | Single warship still held, bottom line reduced to “combat.” |
| 25s | Same ship, new bottom line about alliance terrorizing commerce. |
| 26s | Headline “terrorized merchant vessels” appears above same small warship. |
| 27s | Merchant-vessel image replaces imperial warship. |
| 28s | Merchant ship and headline persist; bottom line describes vessels/coastal towns. |
| 29s | Same merchant vessel and label; bottom word “region.” |
| 30s | Ship remains, bottom setup about growing government pressure. |
| 31s | Modern-looking “Government Official” character appears, labeled `Illustration`. |
| 32s | Official and same narration line continue. |
| 33s | Official held, same lower line; little visual evolution. |
| 34s | Official still held; new lower line about internal rivalries. |
| 35s | Same official; same rivalries sentence fragment. |
| 36s | Official stays as lower line resolves “coalition.” |
| 37s | Large “1810” with same official; claim begins about a negotiated outcome. |
| 38s | Official fades out, leaving prominent 1810 and faint remainder. |
| 39s | Zheng Yi Sao returns below 1810; new fragment about formal negotiations. |
| 40s | Same woman and 1810; bottom text advances. |
| 41s | Pardon scroll appears alongside woman; both names plus `Illustration` labels. |
| 42s | The 1810/pardon-scroll composition held. |
| 43s | Prior elements fade; bottom line says she retired with wealth intact. |
| 44s | Treasure chest shown + `Wealth / Illustration`; bottom line held. |
| 45s | Same treasure chest; subtitle about escaping violent fate. |
| 46s | Same treasure chest; similar lower line held. |
| 47s | Same treasure chest; bottom line references Blackbeard. |
| 48s | Portrait of Blackbeard added alongside treasure chest; headline “pirates like Blackbeard.” |
| 49s | Same Blackbeard/treasure arrangement; bottom line “She remained free…” |
| 50s | Zheng Yi Sao returns again; small bottom statement. |
| 51s | Large “1844” arrives above repeat portrait. |
| 52s | 1844/portrait held; bottom line discusses “typical end.” |
| 53s | 1844/portrait held. |
| 54s | New bottom fragment “such a notorious figure.” |
| 55s | Same 1844/portrait/closing fragment. |
| 56s | Closing static combination remains right up to video end. |

**Generated animation notes:** At 0–5 s, top title appears around 1.5 s but the image/bottom captions remain close to fixed positions. At 18–22 s, the emperor and ship are nearly unchanged across multiple consecutive half-second samples despite a major “defeating fleets” narration beat. At 31–35 s, the modern-looking official remains in place through a changing multi-second subtitle. This is the clearest, reproducible defect to correct.

## B3. Functional contrast, not wrong same-second matching

| Editorial function | Reference example | Generated analogue / issue | Required action |
|---|---|---|---|
| Immediate hook | 0–2 s crown → gem → unfinished “wouldn't be…” claim | 0–2 s empty opening → bottom sentence → tiny portrait | Open with **large semantically relevant asset** and/or readable kinetic statement in first 0.3–0.7 s. |
| Comparison / conflict | 3–5 s queen + two named diamonds in one frame | 13–21 s generic emperor + generic warship unchanged | Build actual conflict via opposing fleets, opposing directions, animated map / loss/win transformation. |
| Cause-and-effect | 18–21 s ruler → named ruler → map → invasion → stolen gems | 30–36 s one official still image while pressure/rivalries are merely narrated | Express pressure with fleet encirclement; express rivals with a split alliance diagram. |
| Revealed date | 42–43 s large 1907 → new portrait | 37–43 s 1810 held over same portrait/scroll | Use date as a 0.6–1.3 s rhythmic pivot, not a six-second immobile header. |
| Payoff | 55–58 s name/location/architecture resolves | 51–56 s same 1844/woman/title | Deliver visual contrast, reveal or takeaway and strong finish. |

---

# PART C — CODEX CODING AGENT MASTER PROMPT (COPY FROM HERE)

## ROLE AND OBJECTIVE

You are the **principal Remotion motion designer, video-rendering engineer, narrative editor, media pipeline architect, and regression-test owner** for my **existing local AI video generator**.

**Task:** Implement a high-fidelity editorial storytelling video system, using my provided reference video as the benchmark, while preserving all currently working flows. The reference video is `reference-ai-video.mp4` / possibly uploaded as `reference-ai-video(5).mp4`; the currently deficient output is `editorial-remotion.mp4`. **Study those videos if local to the repository.** If the files aren't there, use the timestamped forensic findings above as requirements; do not pretend you inspected absent files.

My generated video currently uses similar gray background and bold typography but remains too static, template-like and caption-dependent. **The new output must follow the reference's coordinated kinetic typography, asset placement, semantic movement, evidence/location scenes, rapid story progression, and precise narrator/visual synchronization.** This is a real engineering implementation request, **not** a request to produce advice, mockups or a generic list of animation ideas.

### Non-negotiable operating principles

1. **Audit actual code before changing it.** Identify entry points, modes, input routes (URL/article/topic/user-authored story), story processor, research/fact-check layer, prompt templates, TTS provider, word timing/alignment, asset generation/retrieval, scene planning, Remotion compositions, audio mixing, FFmpeg processing, APIs, data contract, queues, caching and UI controls. Find where the current repeated card layout and `Illustration` labels originate.
2. **Scope changes to the intended Editorial / News mode**, determined by inspecting the application's real modes. If Editorial is an option inside News, modify that path; if the mode naming differs, adapt without inventing new conflicting UI paths. Preserve existing working modes, image alternatives, article input, direct-topic input, and user-supplied offline story input. Preserve existing output behavior for non-targeted modes. Use a versioned opt-in renderer flag (e.g. `editorialStyleVersion: 'reference-v2'`) with safe fallback as appropriate.
3. **Implementation over superficial preset changes.** Reuse current libraries and services if technically adequate. Add capabilities where necessary and refactor only with a tested migration route. Don't replace user settings or paid providers without permission.
4. **No fake functionality:** If narration word timestamps are unavailable, obtain credible alignment from speech/audio or TTS marks; do not fabricate sync or mark placeholders as production complete. If source media/license verification is absent, state the blocker and use honest fallback assets.
5. **Use Remotion frame-based deterministic motion.** No randomness in the render loop; seeded reproducibility. Animations driven from timeline frame state, not `setTimeout`, uncontrolled CSS animation clocks or mount timing. Maintain stable results across preview, local render and cloud render.
6. **Reference parity is the main product goal**: high-information, deceptively simple, animation-rich minimalist historical/news short video. Do not turn this into flashy neon Reels, gaming typography, generic explainer slideshow, meme captions, or constant whip pans.

## 1. PRIORITY ORDER — DO THIS IN ORDER

**P0 (blocking):** reproducible current baseline, protect other modes, remove display of redundant `Illustration`/`AI Generated` metadata, fix timeline-to-speech alignment, first-second dead composition, overly repetitive static layouts and tiny illustrations.

**P1 (core style parity):** narrative beat segmentation; new structured script+beat schema; reference-inspired scene grammar; inline kinetic text; context-sized assets; semantic map/timeline/comparison/evidence visualizations; coordinated group choreography and transitions; consistent image masking/shadow/feather; strong beginning and resolution.

**P2 (polish):** natural spoken script; voice prosody and pauses; consistent music bed/ambience and deliberate sound accents; asset quality/relevance and fact sourcing; platform-safe typography; mobile legibility; nuanced easing and motion blur where useful.

**P3 (production):** robust validation, preview/debug overlays, screenshot/audio regression tests, benchmark sample outputs, performance/caching, model retry/fallback behaviors and documentation.

Do not claim success merely because the video renders without exception.

## 2. EDITORIAL STORYTELLING PIPELINE — REPLACE THE CARD MENTAL MODEL

**New conceptual pipeline:**

`User input (URL/topic/story) → gather or respect input facts → constrained verified fact pack → hook and narrated script → semantic beat segmentation → illustration/asset plan → TTS performance → word/phrase timing alignment → storyboard/timeline → deterministic Remotion composition → mix audio → render → QA`.

**The key rule:** The output of the LLM is **not** a list of slides with title/image/description. It is a **time-ordered plan of narrative beats**, each with a subject, spoken words, screen keywords, precise timing and a concrete **visual event**. Each meaningful clause should cause something visible: text introduction, asset arrival, comparison, relocation, replacement, zoom to evidence, movement through a map, transition to a date, handoff of ownership, etc.

### Input handling invariants

- **URL/article:** extract the underlying story and source claims, normalize dates/places/entities and maintain provenance. Research when available; mark uncertainties.
- **Short topic:** research before writing claims when online research exists; if no reliable material, ask for details or clearly state uncertainty—not hallucinate a detailed history.
- **Detailed or local user-supplied story:** honor supplied specifics as the primary intended input; do not quietly replace them with a different online narrative. Flag possible factual inconsistency for review rather than destroying the user story.
- **Non-News/other modes:** untouched except shared bug fixes verified by regressions.
- **Journalistic/editorial honesty:** synthetic images must not be misrepresented as archival photographs or first-hand evidence. Keep required synthetic-media disclosure in metadata/description or appropriate product UI, separate from captions, and use citations in supporting metadata where feasible.

### Narration editor rules

- 50–60 s sample target, **duration measured from generated voice performance**, not guessed from word count; support other requested durations.
- Make the first spoken sentence an intriguing, verifiable tension/contrast with a visual hook in the first second. Avoid “Today we will talk about…” and encyclopedia introductions.
- Aim for ~105–135 words for a ~55–60 s short **as a baseline only**; adjust to actual speaking rate, punctuation, pauses, language and content complexity. Overly rushed speech is a failure.
- Use roughly this arc: **hook → subject/setting → escalation → reversal → payoff → final resonant detail**. Vary arc as appropriate; factual accuracy outranks a made-up twist.
- Build natural short spoken sentences; favor active verbs; eliminate stiffness like “achieved the extraordinary,” “proved resilient, successfully…” or “typical end for such a notorious figure.”
- Human-readable punctuation, predictable pronunciation of foreign names, intentional breaths/pauses. Avoid sudden volume spikes and robotic monotonous cadence. Test output voice on actual playback; don't infer voice quality from amplitude metrics alone.
- Reference-style videos seldom require every narrated word on screen. Extract short important **keywords/phrases** and reveal them during the corresponding spoken moment.
- Preserve optional **true accessibility subtitles** as a separate toggle; don't conflate those with narrative kinetic text or duplicate all narration at the bottom.

## 3. STRUCTURED SCENE CONTRACT

Implement or adapt a validated, typed scene plan. Example schema (illustrative, adapt to codebase):

```ts
type VideoMode = 'editorial-news' | string;
type TextRole = 'bridge' | 'claim' | 'entity' | 'date' | 'location' | 'emphasis' | 'annotation';
type SceneGrammar =
  | 'hero-object' | 'kinetic-type' | 'portrait-event'
  | 'comparison' | 'map-event' | 'timeline-date'
  | 'document-evidence' | 'asset-handoff' | 'location-change'
  | 'cause-effect' | 'split-outcome' | 'final-reveal';

type TimedText = {
  id: string; text: string; role: TextRole;
  spokenWordIds: string[];
  startMs: number; endMs: number;
  emphasis?: 'regular' | 'medium' | 'hero';
  animation?: 'rise-reveal' | 'blur-resolve' | 'scale-settle' |
              'mask-wipe' | 'replace' | 'counter' | 'none';
  layoutAnchor?: string;
};

type Asset = {
  id: string; entityId?: string;
  kind: 'portrait' | 'object' | 'photo' | 'document' |
        'map' | 'diagram' | 'architecture';
  url: string;
  visibleName?: string; // optional useful name ONLY
  sourceType?: 'historic-photo' | 'licensed-photo' | 'illustrated' | 'generated';
  sourceCitation?: string; rightsInfo?: string;
  isHistoricalReconstruction?: boolean;
  mask?: 'transparent' | 'feather-bottom' | 'rectangle' | 'custom';
  focalPoint?: {x: number; y: number};
  motionIntent?: 'enter' | 'hand-off' | 'compare' | 'travel' |
                'focus' | 'exit' | 'hold';
};

type NarrationWord = {
  id: string; text: string;
  startMs: number; endMs: number;
  confidence?: number;
};

type EditorialBeat = {
  id: string; narrativePurpose: string;
  grammar: SceneGrammar;
  startMs: number; endMs: number;
  narration: string;
  words: NarrationWord[];
  texts: TimedText[];
  assets: Asset[];
  composition: {
    focalAssetId?: string;
    relationships?: Array<{subject: string; action: string; object: string}>;
    layoutVariant: string;
    subjectRegion?: {x: number; y: number; w: number; h: number};
  };
  transitions?: {in?: string; out?: string; overlapMs?: number};
  soundCues?: Array<{atMs: number; kind: string; gainDb?: number}>;
};

type EditorialRenderPlan = {
  version: 2;
  mode: VideoMode;
  fps: number;
  width: number; height: number;
  narrationAudioUrl: string;
  musicUrl?: string;
  beats: EditorialBeat[];
  sourceFacts?: Array<{claim: string; source?: string; verified?: boolean}>;
  warnings?: string[];
};
```

Use a strict schema validator (existing project standard; e.g. Zod if already present), repair/retry invalid LLM plan outputs and provide deterministic fallback behaviors. Keep word timecodes in **absolute audio milliseconds**, convert to Remotion frames in one clear utility. Store normalization and timebase conversion in one place. Test no negative durations, overlap bugs, out-of-range frames, missing mandatory assets, or missing timing.

**Critical:** `sourceType`, `rightsInfo`, `isHistoricalReconstruction` and citations remain in internal metadata. They **MUST NOT** be concatenated to the visible image label. If a relevant visible name exists, display only `visibleName` (e.g. `Zheng Yi Sao`). Hide a generic label if it adds no information. An audit of renderer components should enforce this across every asset category.

## 4. REFERENCE-INSPIRED GRAPHIC DESIGN SYSTEM

Develop reusable, data-driven design tokens with proportional layout logic—not one fixed top/middle/bottom card.

**Canvas:** 9:16 vertical; final export ideally 1080×1920/30 fps (preserve configurable targets). Neutral off-white/light gray background, very subtle depth/gradient. No heavy patterned wallpaper, vignette or purple/blue AI-template glows.

**Typography:** one cohesive modern grotesk/sans-serif family using properly licensed bundled fonts; use weight hierarchy (e.g. 400/500/600/700, perhaps 800 sparingly), mostly charcoal (`#303035` as a **starting** approximation, tune against captures), some medium gray (`#6A6A70`), rare accent from a relevant object. Maintain readable punctuation/hyphens/diacritics and correctly shaped international names. Never bake caption text into pictures when it should be animated separately.

**Visual scale and positioning:** Reference assets are frequently much larger than current output and text is compositionally close to its subject. Build responsive asset bounding boxes, focus-aware scaling and cropping. Suggested **starting** ranges, NOT measured original settings: hero noun 80–150 px at 1080 width, major title 60–100 px, supporting text 34–54 px, optional object ID 24–36 px (respect readability and safe areas). Use per-scene fit-to-content measurement; avoid crowding. Do not enforce one font size everywhere.

**Spatial layout:** meaningful compositions within title-safe regions, but allow controlled visual movement across the center, upper, and lower zones. Typical safe perimeter ~6–9% horizontal and platform-aware top/bottom (allow extra lower UI-safe region for Reels/Shorts). Use layout presets with semantic anchors and collision checks; text must not obscure faces/important details or overlap other text unexpectedly.

**Subject treatments:** transparent silhouette cutouts for historical figures/objects, soft bottom feather for selected portrait illustrations, restrained natural shadows, archival/document rectangles when appropriate, muted location silhouettes and architectural overlays. All asset treatments should feel from the same editorial family. If real cutout transparency is unavailable, do not reveal ugly opaque bounding boxes or fake a clean cutout without inspection.

**Naming labels:** short names can be placed at object level; omit generic `Illustration`, `AI-generated`, `Image`, `Photo` or provider descriptors. Examples: allowed `Zheng Yi Sao`, `Qing warships`, `South China Sea`, `1810`, `Blackbeard`; disallowed `Zheng Yi Sao Illustration`, `Warship AI Generated Illustration`, `Photo`, `Asset 4`. Only show factual proper names that match the image. Use separate internal provenance fields and disclosure handling.

## 5. REQUIRED SCENE-GRAMMAR LIBRARY (NOT RANDOM EFFECTS)

Implement at least these composition primitives as reusable Remotion components/layout families, with entrance/hold/exit phases and story-semantic transitions:

1. `HeroObjectReveal`: large subject first, sentence builds around it. **Opening reference 0–2 s.**
2. `IncrementalClaim`: 2–4 phrase chunks arrive tied to audio; current words rise/resolve while old words retain logical place or subtly shift. **Reference 0–2, 18–21, 44–46.**
3. `TwoAssetComparison`: two relevant objects aligned with meaningful differences, labels only when useful; one can scale/emphasize when mentioned. **Reference 3–5.**
4. `PortraitToEvent`: portrait arrives; named entity expands; map/action is then revealed behind or beside person; action caption emerges. **Reference 18–21.**
5. `MapTravelOrChange`: map silhouette with point/path/location title, changes of location; do not imply inaccurate geography. **Reference 7–9, 47–49, 50–52.**
6. `EvidenceReveal`: archival image/document/photo appears, text builds next to or above rather than leaving tiny default labels; use appropriate source disclosure outside frames. **Reference 11–12, 31–32, 38–41.**
7. `DatePunch`: date takes focus quickly and hands off to its consequence. **Reference 42–43 and 48–49.**
8. `AssetHandoff`: graphic A moves/fades to B or changes scale while text explains succession. **Reference 35–37 and 50–52.**
9. `CauseEffectDiagram`: cause and effect are visually represented (e.g. opposing fleets move, alliances split), not just described underneath an immobile asset.
10. `ContrastAndPayoff`: “while/but/however” language triggers an actual spatial and visual contrast—good for reversals and endings.
11. `TypographicBreath`: quick, legible words on a nearly empty background for emphasis, usually **under** the duration of a major visual scene. **Reference 16–17, 22, 35, 53–54.**
12. `FinalLocationOrMeaningReveal`: readable final statement, decisive image/location/value, last half-second for comprehension rather than a frozen six-second card. **Reference 55–58.**

Provide compositional diversity with constrained selection: avoid using exactly the same scene grammar for more than two consecutive beats unless a valid editorial reason exists. Use explanatory labels when useful, not on all objects. Do not introduce extra images simply to raise motion statistics. Each visual must advance meaning.

## 6. MOTION DESIGN — PRACTICAL IMPLEMENTATION TARGETS

The reference is marked by **controlled, frequent micro-events**: phrase reveal; image entering; old image scale/opacity handoff; key word enlargement; map silhouette arriving; change in spatial relationship; restrained shadow; short deliberate holds. Reproduce the logic, not an obnoxious preset.

**Initial tunable durations, not claims about source internals:**

- Micro text entrance: typically 6–14 frames (0.2–0.47 s at 30 fps).
- Larger object entrance: typically 10–24 frames (~0.33–0.8 s), sometimes masked by an overlap/fade.
- Phrase handoff: often 8–18 frames (~0.27–0.6 s).
- Strong date/name settle: ~10–20 frames, then meaningful change follows.
- More important than exact duration: schedule the entrance to land **on the word/phrase it explains**, and avoid static holds that extend well past their speech beat.
- Compose with `spring`, `interpolate`, `Easing`, masked reveals, transforms and opacity as appropriate; clamp outputs; support perceptual easing. Subtle parallax, small translate/scale and image shadow can add life, but never constant floating/fidgeting.
- Transitions should be motivated: map → place; person → action; conflict → consequence; object A → object B; year → new period. Prefer seamless image/text handoffs, wipes/fades and composition replacements over random full-screen transitions.
- Use overlap/cross-dissolve **when narratively meaningful**; do not have everything vanish before every next scene. Reference frequently retains context briefly as the next element arrives.
- Avoid rapid flickering, offscreen fly-ins, giant bounce, chaotic camera motion, glitch or strobe effects. Honor reduced-motion preview where supported.
- Use performance-friendly transform/opacity changes; keep all visual state a pure function of frame time and stable plan data.

**Timing invariant:** For every spoken entity, named date, emphasized noun or action shown on screen, the associated text/asset should appear approximately when the word is heard (default target ±150–250 ms depending on planned anticipation/hold), not seconds before/after; validate with actual aligned word timestamps. Narration can anticipate visuals as a deliberate exception if explicitly encoded in the plan.

**Motion-density health check:** The two supplied videos showed mean >8/255 grayscale changed-pixel fractions of ~5.76% vs ~0.92% at 0.2-s intervals. Use this as **diagnostic evidence** that the current output is too static, not as a mandatory optimizer objective. Review repeated near-duplicate holds, e.g., ~18–21 and ~31–35 s in the current clip. Do not game the score with random background noise or unnecessary shimmer.

## 7. THE TYPOGRAPHY FIX — MOST IMPORTANT VISUAL CHANGE

**Remove the mandatory “headline at top + image in middle + full sentence subtitle at bottom” template for this mode.** Replace with on-screen animated **narrative phrases** as the primary typography:

- Display one meaningful short phrase at a time with active/inactive contrast: e.g., `The Qing government` → `sent warships` → `to stop her`, while the image shows the actual transformation.
- Promote proper nouns/dates only when script calls for them; use small connective words, larger important words, measured line breaks.
- Text movement should relate to objects: “invaded India” appears above a map, “1810” in a date-punch frame, “PARDON” reveals as a scroll arrives. Not every phrase should appear in the same row.
- Use the actual TTS word timing for `TimedText` schedules, not character-count-based estimates. For phrase splitting, use semantic boundaries/pauses and fitting rules; avoid cutting mid-name or highlighting the wrong word.
- Keep transcript/subtitle accessibility as an **optional independent track**, with platform safe area and high contrast. When optional subtitles are enabled, ensure they don't duplicate huge primary animated words unnecessarily or collide with labels.
- Implement text-fit/layout tests for 4:5, 9:16 previews and long names, and export 9:16 final without clipping. Avoid tiny text visible only on a desktop monitor.

## 8. ASSET SELECTION AND IMAGE QUALITY

- Prefer specific visual evidence/relevant symbols: ships, sea maps, a fleet comparison, historical documents, Qing official portrait where justified, negotiation/seal/scroll, treasure/wealth, opposing historical outcome.
- For historical people, do not claim an invented modern or generic image is an authentic portrait. Use consistent historically inspired illustration and disclose it outside the frames as appropriate.
- Set an art-direction style guide: coherent illustration rendering (era, shadows, perspective, color saturation, detail level, transparent edges). Avoid a random blend of cartoon pirate, modern civic official and unrelated stock icon unless intended.
- If image providers support separate “photo/research” and “AI illustration” modes, **keep both existing modes functional**. The editorial scene planner chooses among permitted provider types; output labels must remain clean in either case.
- Build image-selection validation for topical relevance, identity/entity accuracy, proper aspect ratio, unusable watermarks/logos, bad cutouts, transparent-edge halos and visual continuity. If model-assisted image quality checks aren't available, log and provide QA thumbnails.
- Cache sanitized, normalized, correct-resolution sources before Remotion rendering. Ensure no video-frame-by-frame remote fetches.
- Don't infer that a person really looked a certain way from a generative image; no fake documentary claims.

## 9. AUDIO ENGINE, VOICE, MUSIC AND SYNC

**Observed:** output and reference integrated loudness are similar (~−15 vs −14.1 LUFS), yet generated audio has much more near-silence (25/225 vs reference 1/233 quarter-second windows below −35 dBFS). Review the actual mix pipeline.

- Preserve or improve TTS timbre by testing listening quality, pronunciations, rhythm, sentence stress and dramatic but natural pacing. Do not invent quality claims without auditions.
- Prefer TTS that exposes word marks; otherwise align generated waveform to exact transcript with a robust aligner. Store alignment confidence and degrade gracefully if low-confidence.
- Keep intentional pauses short and purposeful; don't leave visual/audio dead space between every clip. Visual elements can bridge a pause when there's reason.
- Provide a subtle, properly licensed bed/ambience where editorially appropriate, including across speech pauses, with envelope/ducking beneath narration. Actual target levels must be set by listening and platform standards; avoid music obscuring consonants.
- Use subtle sound cues only for high-value reveals/transitions (e.g. date, map move, turning point), never for every text word. Correct clipping and crossfade discontinuities.
- Loudness-normalize with a specified target based on distribution platform; test true peaks and background-vs-voice balance; don't simply add gain to compensate for a boring script.
- Ensure final audio/video durations match within the chosen ending-tail policy; no abrupt truncation of last line, unintended leading delay, double narration, drifting slides or desynced subtitles.

## 10. ZHENG YI SAO — EDITORIAL TEST STORY AND DEMONSTRATION

Use the **same test topic as my generated clip** to make an apples-to-apples before/after comparison. This is an illustrative script to refine after fact check and voice-duration measurement—not a license to rewrite other users' stories or invent historical facts.

### Proposed improved narration, ~110 words

> One of history’s most powerful pirates did something almost unheard of. She retired.
>
> Her name was Zheng Yi Sao.
>
> In 1807, she took control of a vast pirate fleet in the South China Sea.
>
> The Qing government sent warships to stop her. Her crews fought back—and the empire struggled to crush them.
>
> For years, merchants feared the pirate alliance.
>
> But government pressure grew, and rivalries threatened to tear it apart.
>
> Then, in 1810, Zheng Yi Sao made an extraordinary move. She negotiated a pardon.
>
> She walked away from piracy with much of her fortune, escaping the fate of pirates like Blackbeard.
>
> And she lived until 1844.

**Verify the claims and any numeric fleet size before publication**, including government terminology and the distinction between individual battles, fleets, negotiated terms, wealth retained and death year. Better to omit an unverified number than make up dramatic “hundreds of ships” imagery as a precise fact. The final wording/timing must flow naturally, allow sentence stress, and not become more complex than the video can visually explain.

### New reference-style storyboard (illustrative timing to adjust to actual aligned TTS)

| Approx. time | Spoken/story function | Motion composition to build | Visual motion/typography |
|---|---|---|---|
| 00–03s | Unexpected hook: the pirate who retired | `HeroObjectReveal` into `IncrementalClaim` | Ship silhouette/fleet enters immediately; “ONE OF HISTORY'S MOST POWERFUL PIRATES” breaks into smaller phrases; “SHE RETIRED” becomes surprising emphasized resolution. No blank canvas. |
| 03–06s | Identify person | `PortraitEvent` | Portrait grows much larger than current output; `Zheng Yi Sao` appears on cue; clean *name only* label. |
| 06–10s | Year and command | `DatePunch` → `CauseEffectDiagram` | “1807” quick large date; portrait/map/fleet appear in staged sequence; fleet group or map conveys scope without fake ship counts. |
| 10–14s | Geographic setting | `MapTravelOrChange` | South China Sea map silhouette and prominent place label; ship route traces gradually; avoid inaccurate coastlines. |
| 14–19s | Government attacks | `TwoAssetComparison` → `CauseEffectDiagram` | Qing warships enter from one side, pirate fleet from other; “sent warships” grows with incoming opposing ships. |
| 19–24s | Conflict and resistance | `ContrastAndPayoff` | Fleet positioning changes to show resistance; “FOUGHT BACK”/“COULDN'T CRUSH THEM” appears with audio; avoid fake precise battle footage. |
| 24–28s | Merchants in fear | `AssetHandoff` | Warships hand off to merchant shipping lane; ships on map or larger merchant vessel replace them; no multi-second unmoving tiny boat. |
| 28–33s | Pressure and fractures | `CauseEffectDiagram` | Pressure squeezes route/area; the pirate alliance visually splits into groups; “RIVALRIES” appears on the moment of rupture. No modern government-official cartoon. |
| 33–38s | Year 1810 and shocking decision | `DatePunch` + `TypographicBreath` | “1810” lands, then question/reversal: instead of battle, a negotiation/scroll frame. |
| 38–44s | Negotiated pardon | `DocumentEvidence` + `IncrementalClaim` | Pardon scroll/seal appears and becomes the focus; animated words “NEGOTIATED A PARDON”; clean provenance outside image captions. |
| 44–50s | Wealth and comparison | `TwoAssetComparison` | Zheng Yi Sao and Blackbeard briefly positioned in visual contrast, or wealth vs naval battle; “survived / died fighting” only if facts support exact language. |
| 50–56s | Long survival/payoff | `FinalLocationOrMeaningReveal` | “WALKED AWAY” or “SHE SURVIVED” resolves with portrait / faded map; “1844” enters later as compact final fact, not a six-second frozen title. |
| 56–60s, if voice needs it | End hold/tail | `FinalLocationOrMeaningReveal` | Resolve last thought, 0.3–0.7 s readable outro/tail, no unexplained emptiness. |

**Do not hardcode this timeline as the only video**. Build general semantic grammar and use this as a benchmark fixture. The reference's actual visual style matters more than copying these sample captions verbatim. Adjust time ranges to audio—not audio to an arbitrary prebuilt slide schedule.

## 11. EDITORIAL ANIMATION TECHNICAL PATTERNS

Provide reusable Remotion interfaces/hooks for local timeline and phrase cues, e.g.:

```ts
const msToFrame = (ms: number, fps: number) => Math.round(ms * fps / 1000);
const clamp01 = (n: number) => Math.max(0, Math.min(1, n));
// Example only; integrate using the project's current conventions.
function localProgress(frame: number, start: number, duration: number) {
  return clamp01((frame - start) / Math.max(1, duration));
}
```

Components to implement/modify might include `EditorialCanvas`, `PhraseSequence`, `KineticText`, `HeroAsset`, `HistoricalPortrait`, `MapSilhouette`, `EvidenceCard`, `NameLabel`, `SceneComposer`, `EditorialTransition`, `NarrationTrack`, `MusicBed`, and `SceneDebugOverlay`. The component names are suggestions, **not** a requirement to create duplicate architecture if equivalent code exists.

Set transition logic based on the beat plan. Split elements into independent timed layers (`Sequence`, `AbsoluteFill` or local timeline management per existing style) so words and assets need not all enter simultaneously. Design smooth overlap between outgoing and incoming subjects; ensure visibility spans and easing are exact, deterministically reproducible and measurable.

**Avoid:** repeatedly mapping one sentence into `topTitle`, `centerImage`, `bottomCaption` and calling it editorial; putting the literal asset type in `NameLabel`; randomizing animations; re-rendering identical graphics for 4–7 seconds while only bottom text changes; cropping faces out of frame; excessive microscopic labels; unsupported statements like “100% match” absent a direct output comparison.

## 12. VALIDATION, TESTS AND DONE CRITERIA

**Automated tests to build:**

- Schema parsing/normalization (valid beats, ordered bounded times, stable IDs, no missing voice alignment, valid URLs/assets, known layout names).
- Scene changes synchronized to narrated phrase/word timecodes; add tolerance tests for spoken entity/action/key-phrase reveal within ~250 ms, with explicit authored exceptions.
- No screen-visible provenance suffix from renderer-added fields: search text tree/caption track against `/(^|\s)(AI[- ]?generated|AI illustration|illustration|stock image|generated image)(\s|$)/i` **for label contexts only**, not historical transcript quotations. Tests should use separate display-label fields rather than blindly censor user scripts.
- No top-caption/bottom-caption required pair in every scene; variation in grammar and layout.
- Asset-size/collision/safe-area checks on 1080×1920, preview aspect variants and long proper nouns.
- Story-specific no-hallucination tests: sourced facts/uncertainties carried through planning; no fabricated exact fleets/years/quotes added in embellishment stage.
- Regression tests for article URL, short topic, detailed user story, AI-image toggle if supported, other existing video modes, save/export/download, local/cloud render.
- FFprobe/FFmpeg smoke tests for ~30 fps, configured vertical export, audio stream, duration and non-clipped finish.
- Voice/audio QA: objective scan for unexpected near-silence, peak overs, blank first second and abrupt last word; thresholds should be tuned with actual renders and intentional pauses excluded.
- Frame screenshot/unit tests: render fixtures at representative frame indices and compare using visual diffs; don't apply fragile pixel-perfect thresholds across platform font rasterization without tolerances.
- Frame-activity report: plot 0.2-s frame-difference summaries (same rescaling/method as baseline), report major long-static stretches as warnings, and manually review meaningful activity rather than chasing a percentage.

**Manual acceptance checklist:**

- First 0.5–1 s communicates a visible story premise; no empty introduction.
- 0–5 s sequence has several meaningful reveals, not just one subtitle change.
- Named places/people/date/objects arrive close to narration, with correct emphasis.
- At least 8 meaningfully distinct scene layouts/grammar uses in a normal ~55-s test output, subject to story needs; not eight arbitrary transitions.
- No generic `Illustration`, `AI-generated` or provider/source prefixes/suffixes below any displayed image; useful factual names only.
- No routine multi-second frozen character while unrelated narrative details are spoken (unless deliberate breathing/suspense shot with explicit rationale).
- Every important beat is expressed in visuals as well as voice: invasion, resistance, pressure, fractured alliance, pardon, survival (for test fixture).
- Subject cutouts are clean; era, style and asset relevance are consistent; no obviously anachronistic generic official for an early-1800s China scene.
- Kinetic text is large and readable on an actual phone, not only in a large web player.
- Narration sounds natural; words are not chopped/clipped; music/ambience feels continuous if chosen; no disruptive silence unless intentionally authored.
- Last 3 s deliver an actual story payoff and readable close rather than a held character + year caption.
- Other modes and existing sources/input flows continue working.

**Reference-based acceptance:** Re-render **the same Zheng Yi Sao sample** through old and new editorial modes, keep both files, and prepare a *human-reviewable* side-by-side storyboard and playback. Show exact results for 0–5, 13–21, 30–39 and last 7 seconds. The new output should look markedly closer to the reference's animation density, dynamic typography, transitions and narrative progression. **Do not claim an exact replica of another creator's proprietary assets, timing, voice, or composition.** Build original art direction that matches the mechanics and perceived production quality.

## 13. ENGINEERING WORKFLOW AND REQUIRED DELIVERABLES

Perform the work in these gates, in order:

### Gate 1 — Baseline and architecture diagnosis

- Locate the actual mode and pipeline; identify root causes of card template, provenance suffix, timing drift/static holds, weak story output and gaps in audio.
- Record existing test command(s), render command(s), baseline output and test input. Map files/components to affected responsibilities. Summarize the plan for code changes before destructive refactoring.

### Gate 2 — Visual data contract and story quality

- Implement versioned beat plan, validation, better narration prompt/script editor, cue extraction, timed semantic asset plan. Keep user-provided factual story intact and separate marketing/visual emphasis from factual claims.

### Gate 3 — Scene grammar + motion renderer

- Deliver reference-inspired scene library and replace repetitive layout in **target** mode. Integrate synchronized text reveals, map/portrait/evidence transitions, scale/feather/shadow systems, legibility/safe area and clean image name renderer.

### Gate 4 — Narration/audio synchronization and finishing

- Integrate actual word timing, conditional captions, appropriate bed/music and voice QA. Detect silent starts, frozen spans, final-line truncation and unintended overlap.

### Gate 5 — Visual verification and regression

- Re-render Zheng Yi Sao sample, create playable before/after and objective stats, and execute other-mode regression. Fix failures before marking complete.

**Final response from the coding agent MUST include:**

1. Root causes actually identified in code and which assumptions proved wrong.
2. File-by-file implementation summary and key decisions.
3. Setup/config changes, dependencies, paid API implications and migration/default behavior.
4. Exact commands for running app, rendering one sample, running tests and opening a local preview.
5. New sample video output location (only if actually produced); evidence from 0–5, 13–21, 30–39, final sequence.
6. Table of acceptance criteria with **Pass / Fail / Not tested**, and evidence. No unjustified blanket “done.”
7. Clear list of remaining gaps compared with reference and next concrete fixes.

**Definition of done:** The generated product is no longer a sequence of stationary, captioned illustrations. It behaves like a compact editorial motion piece in which **the words, people, objects, places, documents and transitions all participate in telling the story at the same time the narrator tells it**, while the old workflows remain reliable.

---

# PART D — REVIEWER NOTES / RISKS

1. **Different subject matter:** An objective comparison should also use a newly rendered diamond story and/or a locally available licensed matched-asset topic if legally available, as a secondary benchmark. Zheng Yi Sao old-vs-new is the main implementation regression fixture because it isolates improvement on identical topic.
2. **Voice/narration assessment boundary:** This analysis verified audio timing/loudness and visible on-screen script/copy; it did **not** produce a reliable ASR transcript or a human listening assessment of vocal tone/timbre/acting. The coding agent must audition actual audio and inspect TTS/ASR timing before claiming the voice quality was fixed.
3. **Visual coverage boundary:** Still frames were inspected every whole second with half-second strips for high-value periods, plus automated frame differences sampled at about 5 Hz. This supports a detailed timecode audit, **not** a claim of expert manual inspection of every one of the ~1,700 frames in each video.
4. **Historical caution:** Reference-style effects may incorporate historical portraits, maps, photographs or archive-looking artifacts; avoid representing synthetic reconstructions as authentic documents. Fact-check substantive news/historical claims and ensure licensing of third-party images/music/fonts.
5. **Engineering uncertainty:** Without the local repository, root-cause file paths and exact current prompt/code structures cannot be confirmed. Therefore this master prompt explicitly directs Codex to inspect and adapt rather than replace working systems blindly.

**The one change that matters most:** make video planning **phrase/event/asset-driven**, with audio-aligned kinetic typography and semantic image transformations. Merely removing `Illustration` tags, altering font weight, and adding generic transitions will never reproduce the reference style.
