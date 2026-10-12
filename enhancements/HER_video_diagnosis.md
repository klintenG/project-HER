# Project HER: reference versus generated video diagnosis

## Verdict

The generated video has adopted the reference's broad ingredients—portrait format, pale background, dark text and isolated objects—but not its editorial system. The reference continuously develops an idea through separately timed words, assets, emphasis and visual relationships. The generated video largely presents six complete headlines above a few slowly scaling assets. Changing the theme or adding more generic effects will not close this gap. The application needs a narration-aligned, layered editorial timeline.

The largest priorities are: progressive text, meaningful visual events within scenes, accurate assets, continuity across scenes, shorter gaps between narration segments, and a substantially louder final mix.

## Evidence and limits

Reviewed inputs: `reference-ai-video(1).mp4` and `generated-video.mp4`. Also read the supplied `PROJECT_DOCUMENTATION.md` to map recommendations to HER's documented architecture. That documentation describes features; it is not proof that those features were enabled or correctly connected in this particular run. The local repository and generation manifest were not provided, so source-level causes below are hypotheses to investigate.

Both videos were decoded through their entire duration. Visual inspection used samples every 0.2 seconds, covering every second of both timelines, followed by finer inspection of selected transitions using source frames. All 1,744 reference frames and 1,033 generated frames were also decoded for frame-change measurements. The tables describe visible activity within each one-second interval; approximate event boundaries have about 0.1–0.2 second sampling uncertainty unless explicitly measured from source frames.

**Audio limitation:** direct audio listening and speech transcription are unavailable in this session. Loudness, peaks and near-silence were measured from the actual stereo tracks. Voice accent, delivery, music identity, audible sound effects, and exact spoken-word-to-caption alignment are therefore unverified. The visible text sequence is not presented as an independently verified transcript. The implementation prompt requires the coding agent to verify these aspects locally.

The subjects differ: the reference is a historical diamond explainer; the generated video discusses Musk, Starlink and India. Compare their production grammar, not the factual accuracy or completeness of two unrelated stories. Historical and news statements displayed in these files have not been fact-checked here.

## File-level comparison

| Property | Reference | Generated | Meaning |
|---|---|---|---|
| Container duration | 58.211 s | 34.496 s | Different scripts; do not pad the second simply to match duration. |
| Video duration | 58.133 s | 34.433 s | Both have a small audio/container tail. |
| Dimensions | 720 × 1280 | 1080 × 1920 | Resolution is already sufficient in the generated file. |
| Frame rate | 30 fps | 30 fps | Frame rate is not the main gap. |
| Video codec | H.264 High | H.264 High | Both use a suitable delivery codec. |
| Video bitrate | About 407 kb/s | About 771 kb/s | Higher bitrate does not produce better editorial design. |
| Color metadata | BT.709, limited range | BT.470bg matrix, full range; transfer/primaries unspecified | Standardize export color handling; this does not alone explain the visible design difference. |
| Audio | HE-AAC, 44.1 kHz stereo | AAC-LC, 48 kHz stereo | Codec/sample rate are not the primary audio problem. |
| Integrated stereo loudness | **−14.21 LUFS** | **−25.21 LUFS** | Generated mix is about **11 LU quieter**. |
| True peak | −0.87 dBTP | −8.99 dBTP | Generated output leaves substantial peak headroom. |
| Loudness range | 2.5 LU | 3.6 LU | Reference mix has somewhat tighter measured dynamics. |
| Renderer metadata | Not identified | Remotion 4.0.242 | Build on the existing Remotion pipeline. |

## Detailed production comparison

| Element | What the reference does | What the generated video does | Required change |
|---|---|---|---|
| Story delivery | Opens a curiosity loop, answers it, explains the journey, ends at a current location. | Displays a sequence of news summaries. | Plan a hook, explanation and honest takeaway; preserve attribution and uncertainty. |
| Text timing | Words and phrases accumulate; important names and conclusions arrive later. | Entire scene headline appears together, then stays. | Render words/phrases on an aligned timeline. |
| Text hierarchy | Mixes small connecting language, larger names, large years and location headings. | Most headlines have similar weight and scale. | Add semantic text roles and deliberate emphasis. |
| Caption position | Text sits above, below or beside the relevant visual; text-only beats also occur. | Usually fixed headline above objects, with small names below. | Use layout-aware phrase blocks and anchored labels. |
| Subtitles | No separate conventional bottom subtitle strip is visible. Text itself serves the storytelling function. | Headlines are summaries, not visibly progressive captions. | Make editorial text the default display; offer complete subtitles separately. |
| Background | Cool light gray, brighter middle, noticeably darker outer/top/bottom regions. | Warm off-white, much lighter with shallow tonal variation. | Match the cool gray vignette and maintain it through transitions. |
| Object scale | Changes dramatically when an object becomes the focus. | Mild scaling/zoom within largely unchanged compositions. | Add semantic focus, compare and transfer events. |
| Layering | Portraits, maps, jewels, words and shadows operate independently. | Few assets occupy fixed slots. | Preserve separate renderable layers and per-layer timing. |
| People | Isolated figures with soft lower-edge fades integrate into the scene. | Portrait cutouts often terminate at a hard rectangular lower edge. | Prepare proper alpha masks and optional bottom fades. |
| Depth | Long directional cast-shadow shapes and soft contact shadows create a shared space. | Weak or little visible shared shadow treatment. | Use consistent directional shadows, tuned per asset type. |
| Asset fidelity | Distinct portraits, jewels, maps, a mine photo, landmarks and a heraldic emblem. | A globe is repeatedly labeled Starlink; a generic building is labeled Ministry of Communications. | Select assets for their actual identity or clearly use a symbolic representation. |
| Asset reuse | Reuses an object to explain its movement or changed ownership/location. | Repeats the globe through several different statements without a new visual relationship. | Reuse entity identity, but change its narrative role and composition. |
| Scene variety | Comparison, question, map+object, portrait, document/photo, years, locations, text-only, box action. | Six main headline cards; final three revolve around the same globe. | Implement a small, reliable semantic template library. |
| Transitions | Fast scale settlements, lateral movement, opacity overlap, object replacement and perspective action. | Primarily fades and slight image scaling; some transitions wash almost to the background. | Choose transitions for story continuity and avoid background-only gaps. |
| Internal animation | One jewel enlarges while the other shrinks; map pieces separate; years count; a box closes. | No comparable explanatory actions visible. | Add explicit event primitives, not just entry/exit effects. |
| Timing | New words or visual relationships appear during a scene. | Large intervals pass with the same headline and arrangement. | Schedule microbeats inside each narration section. |
| Audio continuity | No near-silent interval ≥150 ms was detected at −40 dBFS. | Five inter-section gaps are about 1.15–1.24 seconds. | Inspect padding and trims; target short natural boundaries. |
| Ending | Finishes with bank/location identity and concluding text. | Repeated globe plus “Launch timeline remains unclear.” | Make the concluding visual express the actual takeaway or uncertainty. |

### What already works

The generated file is readable, has a restrained palette, uses 9:16 correctly, exports at 1080p/30 fps, and already combines cutouts with labels. The portrait identities are more relevant than generic stock footage would be. Retain that foundation. The gap is the absence of coordinated editorial development inside the composition.

### Background, color and image treatment

The reference is not a pure white slide. Its cool gray gradient/vignette creates a brighter stage in the central area. Photographic colors—gold jewelry, red clothing and colored emblems—provide the accents; text stays mainly dark gray. There is no evidence for a default neon keyword palette, colored karaoke boxes, particles, auroras or heavy film effects.

The reference also uses different asset treatments deliberately. Some figures are cutouts with a lower fade; the mine remains a rectangular photo; an archival portrait remains a rectangle; maps act as silhouettes. Do not remove every background indiscriminately or turn every image into the same rounded card.

The reference's assets are more visibly differentiated, but their authentic identities are not established by the MP4 alone. Its labeled bank facade, historical portraits and maps also require source validation before reuse in factual content.

Repeated directional shadow shapes reinforce the scene's depth. Approximate them as a silhouette projected toward the lower-left, with low opacity and modest blur; add a softer local contact shadow where useful. These are practical approximations of the raster appearance, not a recovered lighting rig.

### Typography and subtitles

The reference font appears to be a rounded/geometric sans serif. The precise font family cannot be identified reliably from this compressed raster. Start with an appropriate installed, licensed family such as Poppins and compare letter shapes visually. Do not claim an exact font match until checked.

For a 1080 × 1920 implementation, useful initial values are roughly 52–68 px for ordinary narration text, 78–110 px for emphasis, 120–180 px for a dominant year/location, and 32–44 px for entity labels. These are proposed tuning values, not measured font specifications from the source project. Use consistent line height, deliberate line breaks and screen-space collision checks.

The crucial distinction is **progressive reveal**, not necessarily karaoke highlighting. In the reference, text grows from short language into a complete phrase, and important words change size or position. A full headline colored one word at a time would still differ. Reserve final phrase geometry before revealing words so the existing text does not jump sideways whenever a word is added.

If editorial text omits spoken filler, export a complete aligned SRT/VTT separately. If optional complete burned-in subtitles are enabled, avoid duplicating the same words in both the editorial text and a subtitle bar.

### Motion, continuity and transitions

Many reference shots have calm holds. The reference is not constantly moving every element. It uses short meaningful changes followed by enough time to read them. The generated file also has minor image movement; calling it completely static would be inaccurate. Its problem is that the movement rarely explains anything.

At about 2.4 s, the queen/comparison composition enters large and settles down while outgoing content fades. At about 4.4–5.1 s, the Daria-i-Noor side becomes dominant and the other jewel recedes. At about 25.43–25.70 s, the emblem starts oversized and rapidly settles. These are different editorial moves, not one universal transition.

At about 29.07–29.40 s, the jewel box changes perspective and becomes a closed emblem-bearing box. This is a **story object action**, not a decorative cube transition between two unrelated slides.

At about 41.2–42.1 s, year digits change rapidly and settle at 1908. At about 47.3–47.8 s, a map breaks into spatially separated pieces. At about 36.3–36.6 s and 51.0–51.3 s, location compositions move laterally. Repeating the jewel preserves visual identity even when the surrounding location changes.

## Reference: second-by-second visual ledger

Each row covers `[second, next second)`, except the final row. Words below describe text visible in that interval; they are not an audio transcript.

| Time | Visible composition and changes | Production lesson |
|---|---|---|
| 00–01 | Crown on gray stage; “The Kohinoor” develops; crown is replaced by a gemstone; next phrase begins. | Start immediately; time text and object replacement separately. |
| 01–02 | Gemstone holds, phrase builds, then bracelet/jewel assembly replaces it around 1.7 s. | Multiple visual beats can share one sentence. |
| 02–03 | “Famous diamond” completes; around 2.4 s, queen and two labeled jewels enter large and settle. | Overlap outgoing/incoming layers with scale settlement. |
| 03–04 | Queen remains above two jewels; “if Queen Victoria had chosen” accumulates. | Phrase reveal within a stable composition. |
| 04–05 | Daria-i-Noor grows; Kohinoor shrinks; emphasis shifts toward the chosen object. | Comparative scale expresses importance. |
| 05–06 | Comparison exits; question text starts; jewelry becomes a loose diamond representation. | Change representation when asking a new question. |
| 06–07 | Gold jewel setting returns; “end up?” completes; vault and map enter around 6.7 s. | Pay off the question with a new visual idea. |
| 07–08 | Map behind a vault; “It's locked inside a bank vault” builds. | Location and object are separate layers. |
| 08–09 | Vault holds; “in Bangladesh” appears underneath. | Reveal the location after the setup. |
| 09–10 | Vault/map give way to the gold jewel; “The Daria-i-Noor” begins. | Reuse the story's central object. |
| 10–11 | Origin phrase adds “was discovered”; mine photo slides in around 10.8 s. | Object-to-location change follows the narrative. |
| 11–12 | Rectangular mine photo; “in the Kollur mine” develops; lower location phrase begins. | Preserve appropriate photographic framing. |
| 12–13 | “In India” completes; horsemen enter around 12.4 s; “For a long time” begins. | Transition to the historical period. |
| 13–14 | Horsemen hold; “it was owned by” grows above; lower identity text starts. | Distribute a sentence across two text zones. |
| 14–15 | “The Maratha rulers” completes below; quiet hold. | A readable hold is useful after a reveal. |
| 15–16 | Horsemen fade; text-only “before passing to…” takes over. | Text-only connectors can be intentional scenes. |
| 16–17 | “Mughal emperors” appears with stronger hierarchy. | Emphasize the meaningful entity, not every word. |
| 17–18 | Text moves away; isolated ruler enters; “the Persian ruler” develops. | Lateral continuity introduces a new person. |
| 18–19 | Name builds into “Nadir Shah” in larger type. | Name reveal changes the visual hierarchy. |
| 19–20 | Ruler persists; India silhouette enters behind; “invaded India” takes over. | Keep the actor and change the context. |
| 20–21 | Map/ruler composition; “took both diamonds” builds beneath. | Add an action/consequence microbeat. |
| 21–22 | Prior layout exits; “both gems” becomes the new text-led setup. | Transition on the semantic boundary. |
| 22–23 | “Eventually reached” accumulates; next ruler starts appearing near 23 s. | Anticipation precedes the entity reveal. |
| 23–24 | Ranjit Singh cutout; name arrives below; cast shadow remains consistent. | Anchor labels to their subject. |
| 24–25 | Composition shifts; Punjab silhouette appears behind; “the ruler of Punjab” replaces the prior phrase. | Recontextualize a persistent person. |
| 25–26 | Around 25.43 s an oversized emblem appears and settles; faint map behind; new phrase starts below. | Short dramatic scale change, then readability. |
| 26–27 | East India Company phrase progressively reveals. | Text progression supplies activity without camera noise. |
| 27–28 | “Annexed Punjab” completes; box with two jewels replaces the emblem around 27.6 s. | Translate a narrative consequence into an object scene. |
| 28–29 | Open jewel box holds with subtle staging. | Quiet anticipation before the action. |
| 29–30 | Box rotates/changes perspective and closes with an emblem on its surface. | Animate the story object itself. |
| 30–31 | Box moves out; archival jewel illustration slides in; “They were later presented” reveals. | Movement continues the ownership journey. |
| 31–32 | Illustration holds; “to Queen Victoria” develops below. | Two caption regions complete one proposition. |
| 32–33 | Queen and crown return; “She kept” begins. | Bring back established entities rather than new substitutes. |
| 33–34 | “The Kohinoor” grows in emphasis; queen/crown begin fading near 34 s. | A choice receives stronger typography. |
| 34–35 | Text-only “While the Daria-i-Noor” bridges the contrast. | Use a brief connector rather than another full card. |
| 35–36 | India heading, landmark and jewel enter; composition settles. | Combine location heading with persistent object. |
| 36–37 | India composition slides into Kolkata with bridge imagery; jewel identity stays consistent. | Visualize movement between places. |
| 37–38 | Kolkata holds; archival portrait arrives near 37.8 s. | Alternate geographic and human scenes. |
| 38–39 | “Khwaja Alimullah” develops over the rectangular portrait. | Not every historical image needs cutout treatment. |
| 39–40 | Lower text accumulates into “the Nawab of Dhaka.” | Progressive descriptive text. |
| 40–41 | Lower phrase adds “purchased it”; portrait remains. | An otherwise quiet shot still develops semantically. |
| 41–42 | Portrait fades; year digits rapidly count forward through the 1900s. | A year can be an animated narrative element. |
| 42–43 | Counter settles at 1908; standing Nawab cutout enters in front; name reveals above. | Layer a person with a temporal context. |
| 43–44 | Nawab scene slides away; jewel enters; “mortgaged the diamond” builds. | Change focus from person to action object. |
| 44–45 | Jewel holds while the phrase expands. | Word timing prevents an early full-text dump. |
| 45–46 | “To the government” completes above; “for a loan” arrives larger below. | Emphasize the consequence with scale and placement. |
| 46–47 | Jewel fades; map appears; “After the partition…” begins. | Introduce the next historical/geographic event. |
| 47–48 | Map divides into separated pieces; “of India” completes. | Use factual map geometry and an explanatory animation. |
| 48–49 | “In 1947” appears beneath the separated map. | Attach the date to the action just shown. |
| 49–50 | Map transitions into Kolkata bridge + jewel composition. | Resume object/location continuity. |
| 50–51 | Kolkata holds; lateral location transfer begins near the end of the interval. | Allow a readable origin before the transfer. |
| 51–52 | Dhaka landmark/heading replaces Kolkata; jewel remains the same object. | Preserve entity identity through a location change. |
| 52–53 | Dhaka fades; text-only “Today it remains preserved” begins. | Build the closing proposition. |
| 53–54 | Closing phrase holds on the shared gray stage. | Text-only holds can reinforce a conclusion. |
| 54–55 | “In the vault of” gains emphasis; bank composition enters laterally near 54.8 s. | Delay the final identity until the reveal. |
| 55–56 | Bank facade settles; “Sonali Bank” completes above. | End on a concrete named visual anchor. |
| 56–57 | “A state-owned bank” reveals below. | Complete the final explanation progressively. |
| 57–58 | “In Bangladesh” appears with stronger emphasis. | Finish with the geographic answer. |
| 58–58.211 | Final bank/name/location layout holds until the video ends at 58.133 s; brief audio/container tail. | Preserve the final readable frame. |

## Generated: second-by-second visual ledger

| Time | Visible composition and changes | Gap relative to reference |
|---|---|---|
| 00–01 | Whole “Musk accuses oligarchs of blocking” headline fades in; Musk and globe appear together; small labels. | No progressive hook; displayed phrase does not say what is being blocked. |
| 01–02 | Same headline, portrait and globe; slight image scaling. | No new text or explanation. |
| 02–03 | Same composition. | No internal editorial beat. |
| 03–04 | Same composition with mild asset movement. | Movement does not express a relationship. |
| 04–05 | Same composition. | Long hold on an already complete headline. |
| 05–06 | Same scene starts fading toward its end. | Near-silent interval begins around 5.35 s. |
| 06–07 | Headline and right asset change via fades; Musk persists; Ambani enters; next full headline appears. | Limited continuity is present, but not used to explain the claim. |
| 07–08 | “Musk questions Mukesh Ambani” above two portraits. | Full headline remains static. |
| 08–09 | Two-portrait composition holds. | No attribution, quote or action reveal on screen. |
| 09–10 | Same composition. | Another short measured audio pause occurs; visual does not develop. |
| 10–11 | Same composition. | No meaningful change. |
| 11–12 | Same composition. | A long inter-section near-silent gap begins around 11.84 s. |
| 12–13 | Portraits fade; nearly background-only midpoint around 12.60 s; generic building enters with new full headline. | Transition loses visual continuity and becomes washed out. |
| 13–14 | “India rejects blocking claims”; building labeled “Ministry of Communications.” | Label asserts a specific identity the visible asset does not establish. |
| 14–15 | Same building/headline. | No policy/claim comparison. |
| 15–16 | Same composition. | No progressive details. |
| 16–17 | Same composition. | Long generic hold. |
| 17–18 | Building/headline fade out. | Long near-silent gap begins around 17.36 s. |
| 18–19 | Almost background-only midpoint around 18.07 s; globe fades in beneath security-assessment headline. | New topic is represented by an unchanged symbolic globe. |
| 19–20 | Globe + “Operators must complete security assessments.” | No security-process visual. |
| 20–21 | Same composition. | No requirement checklist or staged explanation. |
| 21–22 | Same composition. | Mild image movement supplies little meaning. |
| 22–23 | Same composition. | Static full headline. |
| 23–24 | Same composition. | Prolonged repetition. |
| 24–25 | Headline fades into “Starlink holds license but stalls”; globe stays. | Long pause around 24.00–25.15 s; no license-versus-readiness comparison. |
| 25–26 | New headline above same globe. | The visual does not distinguish licensing from launch. |
| 26–27 | Same composition. | No explanatory event. |
| 27–28 | Same composition. | Repetition without a new visual role. |
| 28–29 | Same composition. | Another long hold. |
| 29–30 | Old headline fades toward “Launch timeline remains unclear”; globe stays. | Near-silent gap around 29.17–30.35 s; minimal transition. |
| 30–31 | Ending headline fades fully in above globe. | No uncertainty/timeline visual. |
| 31–32 | Same composition. | No closing emphasis. |
| 32–33 | Same composition. | Ending holds without new information. |
| 33–34 | Same layout; near-silent tail begins around 33.83 s. | No distinct closing visual. |
| 34–34.496 | Globe fades toward background while headline is retained in sampled closing frames; video ends at 34.433 s. | End-frame/audio-tail behavior should be checked deliberately. |

## Audio diagnosis supported by measurements

Measurements used the original stereo files, not the mono analysis copies. Integrated loudness was measured with FFmpeg's loudness analysis; near-silence used a −40 dBFS threshold and a 150 ms minimum duration. This measures the **combined mix**, not isolated speech or music.

| Generated near-silent interval | Duration | Visible context |
|---|---:|---|
| 0.000–0.478 s | 0.478 s | Opening fade precedes audio activity. |
| 5.350–6.585 s | 1.236 s | First/second section boundary. |
| 11.840–13.054 s | 1.214 s | Portraits to ministry/building section. |
| 17.364–18.514 s | 1.150 s | Ministry/building to assessment section. |
| 24.004–25.152 s | 1.148 s | Assessment to licensing section. |
| 29.172–30.346 s | 1.174 s | Licensing to closing section. |
| 33.831–34.496 s | 0.665 s | Closing tail. |

Several shorter pauses also occur inside sections. The five longer inter-section gaps sum to about **5.92 seconds**, approximately **17% of the entire generated clip**. That is a material pacing cost. A −40 dBFS detector is not a speech recognizer, so do not trim every detected pause automatically.

The absence of detected near-silence in the reference indicates a continuous audio floor. A background music/ambience bed is one possible explanation, but the measurement alone does not identify its source. Do not claim that a specific reference soundtrack or whoosh has been heard or matched.

For the new preset, start around −15 LUFS integrated, with a true-peak ceiling of −1 dBTP. Tune against the reference and check on a phone. Use short, intentional narration boundaries; avoid an unconditional extra second between generated TTS clips. If adding a music bed, keep it below intelligible speech and duck it during narration. Peak normalization alone will not correct the current integrated-loudness gap.

## Likely implementation causes to investigate

These are hypotheses, not findings from the source code:

1. **One card per narration segment.** The scene model may contain only a headline and one/two assets. That cannot express the reference's within-sentence changes.
2. **Timing information lost or unused.** Documentation claims word timestamps, but the output shows complete headlines. Timestamps might not reach the Remotion props, or this preset may bypass them.
3. **Independent effect selection without a shared plan.** Catalog effects cannot decide which object should remain visible, which word introduces it, or how ownership/location changes are shown.
4. **Generic entity-to-image fallback.** The globe and generic building suggest semantically broad substitutions without a strong identity check.
5. **Per-segment silence/padding.** Repeated 1.2-second gaps suggest a consistent boundary policy or stacked tail/start padding; inspect actual audio assembly before deciding.
6. **Low final mix gain or inconsistent normalization.** Determine whether voice/music are attenuated more than once or whether the final mix bypasses loudness normalization.
7. **Preset/configuration bridge mismatch.** The documented features may exist but be ignored, overwritten by defaults, or flattened during Python-to-Remotion serialization.

Documented places to inspect: `agent/orchestrator.py`, `agent/analyzer.py`, `agent/story_splitter.py`, `agent/narration.py`, TTS provider modules, `agent/visuals.py`, `agent/ai_visuals.py`, `agent/effects_agent.py`, `agent/audio_engine.py`, `agent/audio_utils.py`, `agent/remotion_renderer.py`, and `remotion/src/{types.ts,Video.tsx,components}`. Resolve their current equivalents in the actual checkout first.

## Implementation priorities

| Priority | Deliverable | Reason |
|---|---|---|
| P0 | A deterministic editorial timeline and renderer fixture | Establish the visual grammar before relying on LLM choices. |
| P0 | Aligned progressive text with semantic emphasis | Largest visible difference across almost every second. |
| P0 | Correct entity assets and explicit symbolic fallbacks | Improve credibility immediately. |
| P0 | Remove unintended long audio padding; normalize final mix | Correct the measured pacing and loudness defects. |
| P1 | Semantic templates, separate layers and persistent entity IDs | Enable varied scenes and object continuity. |
| P1 | Compare/focus, location transfer, map split, year counter and object-action events | Reproduce the reference's explanatory animation capabilities. |
| P1 | Cool-gray stage, figure masks and directional shadows | Match the visual finish. |
| P1 | Frame-based overlap transitions and caption collision checks | Avoid fade-to-background gaps and layout instability. |
| P2 | UI preset, preview controls, caching, quality diagnostics and documentation | Make the new behavior reliable and usable. |

## What “exactly like the reference” should mean

For new subjects, reproduce the **layout grammar, hierarchy, event timing, continuity, asset treatment, pacing and audio envelope**. Do not force every story into the reference's historical objects or its exact 58-second duration.

A pixel-identical reconstruction of the same reference would additionally need its source assets, font, masks, animation curves, narration and soundtrack. Those are not recoverable with certainty from the compressed MP4 alone. A close visual reconstruction is practical with careful comparison; pixel identity should not be promised from a generic prompt.

Use the accompanying `HER_codex_master_prompt.md` with both MP4s and the actual local repository. Its acceptance criteria require implementation, rendered evidence and comparison, while preserving existing application flows.
