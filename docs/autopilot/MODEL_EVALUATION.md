# Text model selection and observed validation

The model is configured only through `AUTOPILOT_LLM_MODEL`; image models are unchanged. Model comparisons below distinguish observations from expected tradeoffs. No comparative engagement or creative-writing benchmark was conducted.

| Candidate | Selection reasoning | Evidence in this implementation |
|---|---|---|
| Meta Llama 3 70B Instruct | Medium-cost general instruction model; chosen example default | Authenticated Replicate model lookup returned HTTP 200 and confirmed `max_tokens`. Live ideation, ranking, writing and editorial validation completed. |
| Meta Llama 3 8B Instruct | Smaller candidate for lower-cost experimentation | Listed in Meta's model family; no local creative-quality, latency or reliability evaluation was run. Do not assume equivalent editorial results. |
| DeepSeek R1 | Reasoning-oriented alternative | Replicate lists $3.75/million input and $10/million output tokens; the higher output price does not justify using it by default for short story copy without comparative evidence. Not live-tested here. |

Sources checked: [Replicate's Llama model](https://replicate.com/meta/meta-llama-3-70b-instruct) and [Replicate pricing](https://replicate.com/pricing). Recheck pricing/model access before activation. The example Llama rates are estimates, not provider invoice data; model changes require updating configured input/output rates and conservative reservations.

Observed Llama predictions in this session took approximately 26 seconds for a five-candidate batch, 5 seconds for ranking, 7–8 seconds for scriptwriting and 2 seconds for editorial validation. These are individual observations, not latency guarantees.

The first response wrapped schema-valid JSON in prose/Markdown. The parser now extracts a complete JSON document and still validates every field. An initial script's hook exceeded the requested word count; explicit 3–8-word instructions and bounded schema-failure revisions were added. The final science-fiction narrative, “The Aurora Initiative,” had 151 narration words and passed the editorial validator. Its 8.65 editorial score is a model judgment under configurable weights, not an objectively validated engagement predictor.

Six text predictions, including failed validation attempts, were created during that check. Their token counts imply approximately $0.014 at the example rates; actual billed cost was not returned. The durable conservative reservations totaled $0.60, below the $0.80 smoke-test ceiling. The full final script, prediction metrics and registry are local generated artifacts under `output/autopilot-validation/story-scifi/` and are not published.
