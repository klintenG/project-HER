# Editorial failures: diagnosis and recovery

## Egypt visual rejection

The local failure is recorded under `output/editorial_981e0265498e40628b9b55205b6b4d30/assets/asset_acquisition.json`. The script requested Egypt as an ancient desert landscape. The previous generic cutout prompt prohibited landscapes and all scenery, producing contradictory instructions. Two candidates failed mask quality checks; the third was rejected as a fortress with domes from the wrong architectural context.

Place entities now use a compact contextual vignette. Terrain, sky, water and landmarks may appear inside the vignette; the outer background must remain solid and removable. The prompt explicitly names the place and requires the narrated period and regional architecture. This does not permit maps, invented exact-location claims, unrelated buildings or arbitrary fallback icons. Generated place assets have the context role and remain labelled illustrations. The existing bounded generation/segmentation/review loop is retained.

## Autonomous script rejection

The production worker reported `Editorial validation failed within revision budget`. Previously the draft/review sequence was discarded, so the exact historical rejection cannot be recovered from that error alone.

The writer/reviewer prompts now distinguish original fiction from sourced traditional narratives. Fiction is checked against its selected fictional arc; traditional narratives must follow the retrieved source variant. Compression and paraphrasing are allowed, while missing essential events, unsupported events and incomplete endings still fail. Schema failures report relevant fields without echoing the entire generated narration. Cost/provider ceilings propagate rather than being treated as a bad draft.

Every revision persists its draft, review booleans, specific feedback and LLM usage in `editorial_attempts`. Rejected scripts receive the failed checks and feedback for the next bounded revision. Final errors contain the latest reason. The dashboard includes this history in the story diagnostics. No retry budgets or paid-call limits were increased.

## Operating after the patch

Restart the local Flask process to load Python changes. Start a new generation; failed jobs are not automatically replayed. If a story is rejected again, inspect its error and `editorial_attempts` before deciding whether the selected story or its sources need editorial correction. The patch does not guarantee acceptance of every generated script/image, and does not bypass validation or automatically publish a test video.

## Handoff to the deployment session

The user requested that the other active session own deployment. This session did not deploy a Cloud Run revision or change the worker image. Deploy the current shared workspace through the normal guarded rollout, including both web and worker; do not use the temporary patch-build snapshots, which predate concurrent hook/prompt and Autopilot configuration changes.

The implementation changes from this session are in `agent/editorial/assets.py`, `automation/autonomous_story_director.py`, and `templates/autopilot.html`. Concurrent changes to hook length, Autopilot call/revision budgets, `.env.example`, and the deployment script were preserved. Their increased limits are separate from the prompt/diagnostic fixes above.

Validation of the merged workspace: 341 tests passed, including contextual-place prompts, continued wrong-region rejection, bounded editorial repair, retained review history, specific schema errors and propagation of budget limits. Dashboard JavaScript syntax and whitespace checks passed. No paid generation or social publication was started. The provider URL in the reported log is informational; the local failure arose later in visual validation.

Both temporary Cloud Build jobs finished successfully before cancellation could take effect; neither image was deployed. There are no remaining builds from this session in progress. Use the shared workspace rather than those snapshots for the coordinated release.
