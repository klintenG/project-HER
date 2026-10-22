# Narration-driven image movement revision

The follow-up restores the movement requested in the working Branch 1/2 examples: introduce an image centrally, move that same layer aside for complementary text, focus the currently narrated subject within a group, and promote a surviving layer into the next composition.

Latest integrated review: `output/three_branch_narration_motion_final/osiris-review.mp4`.
Original Branch 1 story rerendered through the same updated compiler: `output/branch1_persistent_motion_review/osiris-review.mp4`.
No narration, images, provider settings or generation budgets were changed. These are cached-media renders with zero image/TTS generation calls.

## Cross-check and cause

Read `working-branch-1` and `working-branch-2` versions of `editorial/director.py` and `reference.py`, and inspected actual supplied-video frames at 24.8, 25.4, 26.7, 27.3 and 31.5 seconds. The original frame sequence shows the narrated subject growing/receding while established actors stay on stage. The corresponding cached reference timelines contain 22/23 reframe events; the initial integrated curated timeline had only three. Default sentence-level event layouts had overridden the more varied reference staging.

The revision reuses the inherited keyed layer lifetimes, absolute word clock, cubic easing and `reframe` primitive. It does not animate replacement portraits in place of the selected action illustrations.

## Behavior

- A single image begins centrally, then travels to the left while the next spoken phrase occupies the right. Contrast clauses such as “Instead” establish the mirrored image-right/text-left composition.
- Spoken names resolve to existing visible layers using the stable identity registry and composite membership. This uses aligned word onsets, not guessed sentence durations.
- Within two- and three-image groups, the narrated layer expands and returns to full emphasis; supporting layers shrink and recede. A new typed `spotlight` event controls image opacity independently of entrance/exit fades, so repeated focus restores full opacity instead of accumulating dimming.
- Retained layers keep their IDs, asset IDs and intervals. Group-to-single transitions interpolate from their established positions into the large hero composition. The Branch 1 rerender demonstrates retained-layer promotions around 56.77 s and 68.37 s. A compiler regression explicitly covers three-to-one promotion.
- Typography reserves the complementary zone. Group shots retain the top text zone while focus changes below it. The final payoff, watermark, captions and separate branding package remain intact.
- Composite images move as one layer; no duplicate character portraits are added to simulate internal movement.

`agent/editorial/staging.py` owns focus selection and geometry; `reference.py` compiles phrase/stage transitions. The obsolete fixed-layout helper was removed. No second production renderer was added. The existing contextual-motion switch controls transition duration and the existing action-motion path.

## Render evidence and checks

The integrated revision has 15 reframe events and 19 spotlight changes, versus three reframes before this follow-up. The cached Branch 1 story has 31 reframes and 20 spotlight changes with the new compiler. Counts describe the manifests; sampled encoded frames provide the visible evidence.

The 52-second integrated review retains the complete approved narration and selected artwork. The Branch 1 comparison is about 77.67 s with the current final hold/outro. Both preliminary full exports passed encoded duration/black-frame checks. Final export measurements are saved next to the latest MP4.

Evidence: `motion-staging-review.jpg` and `visual_evidence/` inside the integrated review directories. Frames at 8.6/10.0/10.7 s show the centered chest composition moving left and the narration text moving right. Frames around 32.2/35.4 s show Horus receding as Seth becomes the narrated focus. The closing underworld contrast uses the mirrored treatment.

Validation:
- Full discovery: 335 tests, with the same two failures and two errors previously reproduced on untouched Branch 3; all other 331 passed.
- After adding the mirrored-treatment regression, all 11 targeted staging/reference tests passed.
- Actual JS frame evaluator checks passed for supporting opacity, focus restoration, independent exit fade, movement midpoint and deterministic seeking.
- TypeScript, branding and News contract checks passed.
- Real Chromium repeated-frame seeking was pixel-identical after visiting the closing slate; complete-caption mode rendered.

The existing image-quality limitations recorded in VISUAL_QA_REPORT.md are outside this movement-only revision. No new image or narration generation was used to correct motion.

## Reproduction

```sh
.venv/bin/python scripts/render_three_branch_review.py --cached output/three_branch_osiris_curated --output output/three_branch_narration_motion_final
.venv/bin/python scripts/render_three_branch_review.py --cached output/editorial_adecc6652b554af6b4ddb5317a9fcf85 --output output/branch1_persistent_motion_review
.venv/bin/python -m unittest tests.test_editorial_staging tests.test_reference_parity
node remotion/check-editorial-staging.cjs
```
