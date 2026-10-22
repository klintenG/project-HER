# Three-branch integration report

22 October 2026. Branch: `integration/three-branch-editorial`, based on `working-branch-3` f858ab3. This is a real rendered review build, **not a claim that every production acceptance criterion passes**. Physical articulation, several image defects and full listening/playback review remain open.

## Result and provenance

Primary review: `output/three_branch_osiris_curated/osiris-review.mp4`. It uses the new complete 139-word narration, new action artwork, and the stronger cached Branch 3 resurrection illustration. All footage is rendered by the existing ProjectHEREditorial Remotion composition. The replacement illustration and its source manifest/asset ID are recorded in `curated_asset_provenance.json`; cross-run character appearance needs review.

Other evidence:
- `output/three_branch_osiris_final/editorial.mp4`: actual provider-backed pipeline output, including its known image fallbacks.
- `output/three_branch_osiris_review/osiris-cached-comparison.mp4`: recomposition of that new run with embedded prop duplicates removed.
- `output/three_branch_cached_comparison/osiris-cached-comparison.mp4`: original Branch 3 cached narration/artwork, rerendered for a controlled motion comparison. Its original story is unresolved and is not the final regression.
- `THREE_BRANCH_BASELINE.md`: branch/code matrix, base selection, preserved configuration and audit evidence.
- `VISUAL_QA_REPORT.md`: observed defects, semantic comparisons and acceptance limits.

No source branch was modified, merged wholesale, deleted or force-pushed. Initial working tree was clean. Existing stash remains untouched. No deployment or remote push occurred.

## Source mapping

Branch 1's existing `editorial/director.py`, `editorial/reference.py` and `remotion/src/editorial/motion.ts` provide continuous layer lifetimes, settle/focus/transfer/fade/reframe behavior and absolute audio-clock choreography. `motion.ts` is identical in branches 1 and 3. Branch 2 adds the native branding controller and narration-safe closing package; it does not introduce a separate editorial kinetic renderer. Its phrase typography is inherited and retained. Branch 3 extends contextual scene planning, identity references, action images, alpha preparation and event composition. The integration extends those shared implementations rather than adding another production renderer.

## Changes

|Files|Result|
|---|---|
|`agent/editorial/canonical.py`, `pipeline.py`|Persist versioned canonical narration/hash before media, reject downstream text mutation, validate scene planning before paid speech/images start. Speech and image sourcing still overlap after planning. This deliberately trades some latency for avoiding narration charges when semantic planning fails.|
|`agent/news_script.py`|Editorial-only source-supported opening/closure instructions and completeness checks inside the existing bounded evidence review. Conservative English fragment/unresolved-fictional-confrontation guard. News writing receives no new editorial constraints.|
|`action_beats.py`, `narrative.py`|Recognize opening, entering, sealing, disposal, search/recovery, scattering, gathering, restoration and confrontation. Default sentence planner now produces the typed exact-character/word beat plan, including context before verbs and complete word coverage. Clouds gathering do not create a character action.|
|`sentence_storyboard.py`|Track depicted identities/props separately from reference-conditioning IDs; remove supporting copies of subjects already embedded in a primary. Normalize rejected collages into independently staged actors.|
|`reference.py`, `choreography.py`|Bound event images and disjoint supporting stages; reserve a final payoff composition. Add word-triggered directional motion/recovery using inherited transfer events. Explicitly report whole-composite motion as a fallback, not articulated action proof. Respect the existing contextual-motion switch.|
|`planner.py`|Keep at least one second after the final aligned word, then the existing separately configured outro. No narration truncation.|
|`quality.py`, `pipeline.py`|Require locked script/word coverage, measured alignment, duplicate-membership checks and a final story hold. Surface composite-action/manual-review status in diagnostics/results rather than calling it fully compliant.|
|`EditorialVideo.tsx`|Reveal words with a mask at full text color instead of fading through nearly invisible text. Keep inherited geometry, bundled fonts and caption separation.|
|Review scripts and fixtures/tests|Fixed sourced Osiris input; real provider run, saved-plan recovery, cached asset recomposition and semantic frame comparisons. No invented narration timestamps or synthetic render evidence.|

The earlier test expecting a separate relic beside a cutout already lifting that relic was updated to the intentionally corrected duplicate-prop behavior. A separate regression verifies that a prop not depicted inside the primary remains available as an independent layer.

## Narration and providers

The completed story includes chest setup, entrapment/disposal, Isis's search, scattering/restoration, Horus's challenge and victory, and the living/dead kingdoms payoff. The fixture identifies a Plutarch-derived chest tradition and acknowledges variant tellings. Supporting references: [Fitzwilliam Museum, Osiris](https://fitzmuseum.cam.ac.uk/explore-our-collection/highlights/context/stories-and-histories/osiris) and [British Museum, Egyptian deities](https://www.britishmuseum.org/learn/schools/ages-7-11/ancient-egypt/ancient-egyptian-gods-and-goddesses). Search excerpts supported the selected outcome; direct page fetches returned 502/403 in this session. Source data and approved output are retained in the run artifacts.

No .env, image/TTS model default, adapter, retry limit, provider fallback or global visual style was changed. Google TTS exhausted its daily quota; the configured fallback produced all 13 sentences with Replicate `jaaari/kokoro-82m` (`af_bella`). Actual audio was aligned with local Whisper; every delivered word has `whisper_forced` provenance. Some alignment probabilities are very low; measured alignment is not a guarantee of perceptually perfect emphasis. Review `alignmentWarnings` and listen to names/rapid words. Music was disabled by the existing configuration; no new score or artificial music tail was added.

## Generation count and cost

The successful provider-backed run recorded **25 accepted image predictions**: configured support/action tiers and existing bounded repair/fallback behavior, not additional motion-driven generation. There were 13 successful Replicate narration clips. Exact model/status counts are available in `generation_counts.json` and the run's acquisition telemetry. Provider billing amounts are not reported by these adapters, so no dollar amount is claimed.

An earlier attempt generated four Google speech clips before its visual plan failed; it was stopped during rate-limit handling. No images were generated by that failed attempt. Planning now precedes paid media to prevent that failure pattern. The recovered script/evidence/planner response were real provider outputs replayed through the same validators; the source evidence IDs had to be retained together. All cached comparisons, duplicate fixes, resurrection selection and final recompositions made **zero additional generation calls**.

The first normal sandbox run could not reach the LLM. Network-enabled execution worked. Local Chromium required execution outside the restricted sandbox. A separate seek test downloaded the Remotion-matching headless browser; no package/dependency version was changed.

## Validation

- Full Python discovery: **329 tests run; 325 passed, 2 failures and 2 errors**. All four remaining cases reproduce on untouched f858ab3 in an isolated `/private/tmp/her_branch3_baseline` snapshot using the same environment. They concern existing News image-budget fixture handling and reference-model expectations (flux-schnell versus configured flux-kontext-pro). No unrelated News fixes were folded into this integration.
- Focused editorial/action/storyboard/branding/input suite passed before the final prop-specific extension; final full discovery includes that extension with no new failures.
- After adding explicit final-hold/alignment rejection and action-onset bounds checks, all 9 integration-quality tests passed.
- `tsc --noEmit` passed. Branding schedule checks and News Zod checks passed.
- Actual cached render passed Python/Remotion timeline conformance. Chromium repeated-frame seeking was pixel-identical after visiting the closing frame; complete-caption mode and brand slate rendered.
- Real provider-backed and recomposed exports passed 1080×1920/30 fps, encoded duration/black-frame checks and encoded AAC delivery checks. See QA report for primary artifact measurements.
- Semantic comparisons use different source timestamps for the same event. Quarter-second action strips and a 5 Hz encoded activity scan inspect real frames; neither proves correct anatomy or articulated action.

Test transcripts copied to `output/three_branch_evidence/`. Do not interpret these results as a fully green repository test suite.

## Reproduction

Run from the repository root with existing dependencies, credentials and local alignment model installed:

```sh
.venv/bin/python scripts/render_three_branch_review.py --output output/osiris_fresh
```

This invokes existing configured providers and can incur their normal generation costs. To render the retained completed job without provider calls:

```sh
.venv/bin/python scripts/render_three_branch_review.py --cached output/three_branch_osiris_final --asset-overrides output/three_branch_osiris_final/curated_overrides.json --output output/osiris_reproduced
.venv/bin/python scripts/compare_three_branch_review.py --job output/osiris_reproduced --video output/osiris_reproduced/osiris-review.mp4
.venv/bin/python -m unittest discover -s tests
cd remotion
./node_modules/.bin/tsc --noEmit
node check-branding.cjs
node check-news-contract.cjs
```

`--references` on the comparison script overrides the local source MP4 folder. Provider randomness is not presented as deterministic; script hashes, actual word timings, asset checksums and render events are retained for deterministic cached rendering.

## Remaining acceptance work

The renderer supports separately controlled subjects; the newly generated interactions themselves are mostly flattened composites. Moving those images cannot visibly articulate a lid, hand or body part. Opening/entering/sealing imagery improved but separately animated lid/occlusion remains incomplete. Opening imagery degraded to a reused character. Some cutouts have matte/anatomy defects. The selected older resurrection image improves event clarity but differs from new character artwork. Default sentence-primary planning still requests a distinct primary per sentence; this integration does not solve the broader generation-cost/reuse policy. A full human start-to-end preview and audio listening pass has not been performed by this agent. These are explicit open items, not checked-off production acceptance.
