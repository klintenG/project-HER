# Narrative visual audit implementation (16 October 2026)

## Pipeline and evidence

The `reference_editorial` path is `run_editorial` in `agent/editorial/pipeline.py`: input classification and research → approved script → visual subject planning → TTS and cutout acquisition → forced audio alignment → atomic visual direction → Remotion → BT.709 FFmpeg encode and audio delivery checks. The existing asset acquisition loop was sequential. TTS and cutouts already overlapped, but TTS began after optional visual planning. The default director keyed persistent layers by entity ID, so an unchanged portrait could satisfy a later action cue. The two supplied storyboards show exactly that for Fenrir's hand, binding, and bite moments; the reference storyboard changes focal subject with the narrated event.

The package contains storyboards, but the two inspected source MP4s and a Fenrir source job are absent from this checkout. No provider credentials or deployed telemetry were available in this environment. This limits final video and deployed performance claims.

## Measured latency

Thirteen distinct historical stage-time records in `output/**/editorial_manifest.json` have output durations of 45–90 seconds. Their recorded stage sums have median **403.08 s** and nearest-rank p95 **725.28 s**. Stage medians: input resolve 10.54 s, research 10.93 s, script 55.81 s, narration 166.27 s, cutouts 90.43 s, timeline 0.20 s, compose 62.76 s. These are saved local records from earlier pipeline versions, not a current production or website baseline; stage sums are not concurrency-aware critical paths. They support investigating TTS, provider waits and rendering, but do not establish a current root cause for the reported 10+ minutes.

A current 12.37-second source timeline was rendered as a 15.07-second branded export at 1080×1920, 30 fps, yuv420p BT.709. Wall time: Remotion **13.469 s**, FFmpeg encode **2.092 s**, audio delivery **0.617 s**, render and quality checks **16.413 s**. Duration and black-frame checks passed. Artifact: `output/action_audit_render_benchmark/editorial.mp4`. This is a short local render fixture and cannot quantify a full 60-second job speedup.

## Changes and flags

- `HER_NARRATIVE_VISUAL_PLANNER_V2=1` enables action coverage in the editorial visual planner. Set `0` for rollback. The planner classifies physical action by general language patterns, preserves an existing action variant when its description matches, or adds a separate interaction cutout request. It records action decisions and explicit degraded states in `visual_plan.json`. Script text and word timing are unchanged.
- Derived action assets use the established character cutout as a reference when available. The prompt asks for a single interaction cutout with contact and direction, and vision review rejects a portrait-only result or a character continuity failure. If bounded retries fail, the job records a degraded labelled visual instead of silently claiming the portrait depicts the action. The existing separate cutout layers, motion, captions, watermark and outro remain under the same renderer.
- In `local` asset mode, a distinct action asset can be supplied under the generated action entity ID in the registry. If it is absent, the output records a degraded action label; it does not reuse the canonical-name portrait for that action.
- `HER_PARALLEL_ASSET_PIPELINE_V2=1` starts TTS from the approved script while optional visual planning runs. TTS and asset acquisition then overlap as before. Set `0` to restore the previous scheduling. This moves work off the critical path when visual planning is slow, but no live provider comparison has been measured.
- Job diagnostics now include planning, alignment, layout, asset durations and bytes, cache hits, Remotion, FFmpeg and audio delivery timings. The existing content-addressed image and matte caches remain local; multi-instance durable storage is still needed before treating cloud cache hits as guaranteed.

## Regression coverage and limits

Automated fixtures cover Fenrir's distinct hand, binding and bite requests, Sisyphus's uphill and downhill states, portrait introduction, reuse of an already suitable action variant and reference-conditioned action generation. All 281 repository unit tests passed. The rendered fixture passed export checks.

The tests verify planning and generation routing, not that a live image provider produced a visually correct Fenrir or Sisyphus frame. Complete before/after Fenrir and Sisyphus MP4s, captions-off human review, ten comparable current runs, deployed p50/p95, provider cost, and klinteng.com submission/progress verification remain outstanding because the relevant source media, provider access and deployment access were unavailable. No 25–40% speed improvement or 90% visual action coverage is claimed from these local results.
