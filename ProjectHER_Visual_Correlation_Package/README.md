# ProjectHER Narration-to-Visual Correlation Fix Package

## Files

- `ProjectHER_Visual_Correlation_Audit.md` — frame-based audit of editorial-3, editorial-4 and reference video, with scene-level observations and root-cause hypotheses.
- `ProjectHER_Codex_Master_Prompt_Narration_Visual_Correlation.md` — ready-to-use coding-agent implementation brief with architecture, acceptance tests, QA, and expected outputs.
- `reference_frames/editorial-3_3s_montage.jpg` — sampled visual timeline, 0–60 s.
- `reference_frames/editorial-4_3s_montage.jpg` — sampled visual timeline, 0–60 s.
- `reference_frames/reference_3s_montage.jpg` — sampled visual timeline, 0–57 s.

## Instructions

1. Make this folder available to your coding agent in the actual ProjectHER code workspace.
2. Attach or provide paths to the three source MP4s so the agent can inspect source videos; the videos themselves are **not** included in this ZIP.
3. Give the coding agent the **Codex Master Prompt** as its main instruction; the **Audit** and montages are supplementary evidence.
4. Ask for a newly rendered Thor video and the exact narration→scene→asset alignment report before considering the task done.

**Limit of audit:** Video frames were visually sampled. The captions and visible scene narrative support the identified failure; word-level audio transcription, exact visual onset deltas and code-level root causes have not been independently verified in this package.
