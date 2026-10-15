# ProjectHER branding implementation

Implements `ProjectHER_Complete_Branding_Package/ProjectHER_Combined_Codex_Master_Prompt.md` in the existing render pipeline. Reference screenshots are not used as video overlays. Branding is native SVG/text with bundled Poppins Medium (500) and Bold (700), licensed under `assets/fonts/news/OFL.txt`.

## Behavior and scheduling

- One shared controller above all scenes displays `projectHER` from frame zero. At 1080 × 1920 its width is 220 px, top inset 105 px, and right inset 75 px. Dimensions scale with the shorter canvas edge. The tagline is suppressed on small canvases when unreadable.
- A single midpoint credit has 0.45-second entry/exit and a four-second fully visible hold. The center of its interval stays within 45–55% of story duration. Scene interiors are preferred over transition boundaries. Thin side rules expand/retract and the line moves 18 scaled pixels with smooth easing.
- Two diagonal overlays are the normal default from 30 seconds onward. Each has 0.5-second fades and a four-second hold, −32° rotation, seeded opacity in 8–12%, and 16 px drift. Fixed anchors alternate; there is no per-frame randomness. Text/document rectangles and approximate portrait-head regions are protected where structured scene geometry exists.
- The credit is reserved first. Overlay intervals must remain outside it and outside each other, with at least 1.75 seconds between complete fade intervals. Two seconds at the beginning/end of the story are reserved. Credit positioning checks protected text regions for a stable free row across its entire appearance.
- Clips below 15 seconds use only corner branding and the signature. At 15–30 seconds, one credit is preferred; an overlay can replace it if credit is disabled. At 30 seconds and above, default settings schedule the full set. Tight custom schedules omit events that cannot fit rather than shorten their holds or overlap them.
- The default closing adds 81 frames at 30 FPS (2.7 seconds). A single logo moves to center over 0.8 seconds, grows to 506 px at portrait baseline, and stays there. Story visuals blur/crossfade from 0.10–1.05 seconds; a gold rule reveals from 0.65–1.20 seconds. Navy is the default; ivory and soft-blur variants are configurable.
- Narration is stopped before the closing. Native captions clear; the frozen last visual is silent. No stinger is added. Native Editorial/News story manifests remain unchanged so their audio/hash validation contracts still hold. Total composition duration, Python result duration, and Editorial delivery checks include the added closing.
- Classic scene lengths now use the maximum of declared duration, narration duration, and last word end, rounded up per scene. Audio stays sequential; outgoing visuals alone extend into transitions. SRT offsets use the identical frame boundaries. Intro/outro scene narration is included in the global audio track.

The locally reviewed story has 2,005 story frames (66.833 seconds) plus 81 closing frames: 2,086 frames / 69.533 seconds. Its transient intervals are:

| Event | Start | End | Full hold |
|---|---:|---:|---:|
| Protective 1 | 13.100 s | 18.100 s | 4 s |
| Credit | 30.967 s | 35.900 s | 4 s |
| Protective 2 | 48.733 s | 53.733 s | 4 s |
| Signature | 66.833 s | 69.533 s | — |

Exact frame schedules and repeat-seek hashes are saved with the review assets.

## Configuration

All production bridges stage a `branding` object. Python generation reads optional `HER_BRANDING_JSON`; Remotion Studio/CLI accepts the same object in input props. No environment change is needed for the shipping defaults.

```json
{
  "branding": {
    "enabled": true,
    "theme": "projecther",
    "alwaysOnCornerLogo": true,
    "showTaglineWhenReadable": true,
    "creditEnabled": true,
    "creditHoldSeconds": 4,
    "creditWindowStrategy": "midTimeline",
    "protectiveOverlayEnabled": true,
    "protectiveOverlayOccurrences": 2,
    "protectiveOverlayHoldSeconds": 4,
    "protectiveOverlayOpacityRange": [0.08, 0.12],
    "deterministicSeed": "saved-render-id",
    "contrast": "dark",
    "creditBottomRatio": 0.09,
    "outro": {"enabled": true, "durationSeconds": 2.7, "theme": "midnightNavy"}
  }
}
```

For Python, `HER_BRANDING_JSON` contains the inner object, without the `branding` wrapper. Seeds come from generation IDs/titles unless explicitly overridden. Classic full-bleed/dark styles automatically select a light wordmark unless overridden. Use `contrast: "light"` for a dark baked MoviePy background. The schema enforces 3–5-second holds, 2–3-second closing duration, and an absolute 14% overlay-opacity ceiling. Setting `enabled: false` restores legacy branding and story-only duration.

## Integration and files

- `remotion/src/branding/timing.ts`: validated configuration, deterministic schedule, story/outro frame helpers.
- `remotion/src/branding/Branding.tsx`: SVG brand mark, kinetic credit, protective overlay, shared story/signature controller.
- `remotion/src/Root.tsx`, `Video.tsx`, `NewsVideo.tsx`, `editorial/EditorialVideo.tsx`: existing compositions, metadata, safe scene regions, audio/caption handling.
- `remotion/src/types.ts`, `news-types.ts`: branding and encoded-source props.
- `remotion/src/components/Scene.tsx`, `TextBlock.tsx`: global narration ownership and top-caption clearance.
- `agent/branding.py`: Python duration/config helpers and MoviePy finishing through the existing `ProjectHER` composition.
- `agent/remotion_renderer.py`, `news_renderer.py`, `news_pipeline.py`, `editorial/render.py`, `editorial/pipeline.py`: staged configuration, synchronized SRT and delivered durations.
- `agent/compositor.py`, `clay_compositor.py`, `news_compositor.py`: MoviePy finish, legacy-watermark suppression.
- `assets/fonts/news/Poppins-Medium.ttf`, `remotion/public/branding/`: deterministic font assets/license. `Dockerfile` copies source fonts even when cloud-upload rules exclude staged public assets.
- `tests/test_branding.py`, `remotion/check-branding.cjs`: timing/configuration regression checks.
- `remotion/render-branding-review.cjs`, `scripts/branding_evidence.py`: reproducible production-composition exports, repeat-seek checks, MP4 screenshots, and excerpt reel.
- `.gitignore`: excludes temporary MoviePy staging.

## Verification and evidence

Local checks passed:

- TypeScript typecheck and scheduling assertions at 24, 25, 30, and 60 FPS, including short clips, non-overlap, hold length, configuration bounds, and narration-safe lengths.
- 69 Python tests covering branding, existing Editorial/News contracts, and audio delivery.
- A full 1080 × 1920 real-story MP4 with 2,086 encoded frames and the appended closing; repeat seeking produces identical PNG hashes.
- Source-to-encoded narration correlation is 0.9999865; closing audio peak is zero after its first 100 ms. Full-size and 360-pixel-wide decoded frames were visually reviewed.
- Classic 16:9 and square exports and a News portrait export, rendered at half scale for smoke review.
- MoviePy's encoded-source finish: 90 original frames become 171 frames at 30 FPS; source audio is retained.

Review assets are local, under `output/branding-review/`:

- `branded-story.mp4`: full story with branding.
- `branding-preview.mp4`: short reel with corner-only, protective, credit, and signature excerpts at their original animation speed.
- `01-corner.png` through `06-signature.png`: screenshots decoded from the MP4.
- Corresponding `*-mobile.png`: 360-pixel-wide review images.
- `studio-*.png`: direct composition frames used for deterministic seeking checks.
- `schedule.json`, `validation.json`, `encoded-metadata.json`, `audio-verification.json`, `python-tests.log`: recorded evidence.

Reproduce checks locally:

```bash
cd /Users/klinten/Desktop/My-projects/project-HER
.venv/bin/python -m unittest tests.test_branding tests.test_editorial tests.test_news tests.test_editorial_audio_delivery -q
cd remotion
npx tsc --noEmit
node check-branding.cjs
node render-branding-review.cjs ../output/editorial_1959bbeb40fe4f5e82aede73150538c1/editorial_props.json ../output/branding-review
cd ..
.venv/bin/python scripts/branding_evidence.py output/branding-review
```

The review command uses an existing staged local story. For another machine, first generate/stage a story and substitute its `editorial_props.json` path.

## Trade-offs and validation limits

MoviePy retains its existing story generation and uses the shared Remotion composition for the branding finish. This adds a second encoding pass and requires the repository's Node/Chromium dependencies even when the story renderer is MoviePy. A failed finish preserves the original file and raises an explicit error; it does not silently deliver an unbranded replacement. Baked captions/faces in an encoded source have no semantic geometry, so native mask/clearance behavior is available most precisely in the structured Remotion pipelines. Existing baked captions can remain in the last-frame memory until it crossfades away. For visually dense custom footage, review and set contrast/credit placement explicitly.

Structured face protection uses portrait bounds, not face detection. Arbitrary footage still needs visual review. News/Editorial scene contracts are unchanged; the Editorial preset continues to support its existing portrait format only. Branding itself supports portrait, landscape, and square.

No live cloud render or deployment was performed. Local and cloud use the same composition entry point and packaged fonts, but the deployed environment has not been exercised. The installed Remotion CLI emits a pre-existing Zod-version advisory; the current typechecks, compositions, and encoded exports pass without changing the repository's schema dependency.

## Manual deployment — not executed

Use the repository's existing guarded rollout script. The first command is dry-run only. The second performs the deployment when **you** choose to run it; it uses the existing Cloud Run project/service, waits for active work, and preserves provider settings.

```bash
cd /Users/klinten/Desktop/My-projects/project-HER
.venv/bin/python scripts/deploy_native_portfolio.py
.venv/bin/python scripts/deploy_native_portfolio.py --approve-cloud-changes
```

This existing script can also provision its configured Firestore/storage/secret/IAM dependencies and sets minimum instances to one. It does not publish the portfolio frontend. Review its dry-run output before invoking the second command. After rollout, use the existing application to generate a short video and verify its added closing and reported duration.
