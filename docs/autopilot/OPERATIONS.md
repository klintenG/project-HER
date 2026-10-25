# ProjectHER Autopilot operations

## State of delivery

Autopilot is implemented inside the existing Flask application and remains **disabled**, with Buffer in **dry-run** by default. Live Buffer publication and cloud deployment have not been verified in this checkout: Buffer credentials, dedicated publishable media hosting and an Autopilot admin token are absent. The existing Cloud Run project and private storage were verified read-only. Do not interpret offline tests, a rendered MP4, or a scheduled post as proof of publication.

The default engine is the studio's current `AgentOrchestrator.run(content_mode='story', visual_preset='reference_editorial')` supplied-story route. It retains existing entity acquisition, cutouts, exact speech alignment, persistent layers, narration-driven focus, transitions, AAC loudness correction and Remotion export. It does not turn fiction into online news research. Manual routes do not instantiate the story director or run Autopilot deduplication.

The protective floating watermark now defaults to `@project.HER`. Its original mask, angle, scale, opacity, timing and drift are retained. Corner branding, credits and closing animation retain the original ProjectHER SVG. The optional opening hook is shared by the reference-editorial and classic compositions and disappears after 2.8 seconds. The thumbnail is the actual frame at 1,500 ms, after its entrance and before exit, with no extra image generation.

## Configuration and Buffer setup

1. Read `.env.example` and set the Autopilot additions in your existing backend environment. Do not put credentials in HTML, frontend build variables or checked-in tfvars.
2. In Buffer's [API dashboard/documentation](https://developers.buffer.com/), create a developer API key with access to the organization containing the already connected Instagram and YouTube accounts. Store it as `BUFFER_API_KEY` in Secret Manager. Keep `AUTOPILOT_ENABLED=false`, `BUFFER_DRY_RUN=true`, and `AUTOPILOT_LIVE_VALIDATED=false`.
3. Generate a random administrator token of at least 32 characters. Store it as `AUTOPILOT_ADMIN_TOKEN` on the Flask service. This token protects every `/api/autopilot` route; it is separate from anonymous portfolio capabilities. Use HTTPS for remote administration.
4. Open `/autopilot` from the studio navigation. Enter the admin token and use **Check Buffer connections**. Account discovery selects an organization only when exactly one is accessible. Otherwise configure `BUFFER_ORGANIZATION_ID`. Channel discovery requires exactly one matching service or explicit `BUFFER_INSTAGRAM_CHANNEL_ID` and `BUFFER_YOUTUBE_CHANNEL_ID`.
5. Both channels must be connected, unlocked, have scheduling permission and not default to reminders. Configure a professional Instagram account with automatic Reels support in Buffer. Unsupported account/features or a returned `notification` scheduling type block the platform; there is no reminder fallback.
6. Set `AUTOPILOT_LLM_MODEL` to an accessible Replicate text model accepting `prompt`, `system_prompt`, `max_tokens` and `temperature`. No model identifier is embedded in the director. The example chooses `meta/meta-llama-3-70b-instruct`, whose authenticated model endpoint and input schema were verified live. Existing image-model configuration is unchanged.
7. Configure `AUTOPILOT_PUBLIC_BUCKET` as a **separate** GCS bucket with anonymous object-read access. Never make `HER_PORTFOLIO_BUCKET` public. Private validated originals go to `HER_PORTFOLIO_BUCKET/autopilot-archive/`; only finished MP4/cover files go to the dedicated public bucket. An organization policy forbidding public access requires a separately approved public media host adapter; expiring portfolio tickets are not substituted.
8. Set `GOOGLE_CLOUD_PROJECT` (or the existing `GCLOUD_PROJECT`), `HER_PORTFOLIO_BUCKET`, `AUTOPILOT_JOB_NAME` and `AUTOPILOT_JOB_REGION` on the Flask service and job where applicable. Include the existing creative-engine secrets/settings in the job environment.

The authenticated GraphQL adapter uses `https://api.buffer.com`, `createPost`, `automatic`, `customScheduled`, a UTC `dueAt`, one shared MP4 URL, Instagram Reel/feed/AI metadata and YouTube title/category/audience/AI/privacy metadata. Default YouTube category is Entertainment (`24`), audience is not made for kids and privacy is public. Change the category/privacy environment settings deliberately for the content being published.

Instagram uses `assets[].video.metadata.thumbnailOffset=1500`. No `thumbnailUrl` is sent. Buffer cannot select a YouTube Shorts thumbnail; YouTube chooses the displayed frame. See [Buffer's video example](https://developers.buffer.com/examples/create-video-post.html) and [current metadata reference](https://developers.buffer.com/reference).

## Storage and migration

Local development uses `data/autopilot/autopilot.sqlite3`; mount persistent local storage if using it beyond development. Cloud Run services **and Jobs** require Firestore and use the `her_autopilot` collection in the existing project. They never silently fall back to SQLite. No relational migration or composite Firestore index is required: records are accessed by key through the existing `SQLiteStore` / `FirestoreStore` interfaces.

On first initialization, the existing `data/story_history.json` is imported once without changing the source file. Import preserves legacy titles, summaries, script hashes and publication state. Legacy entries without canonical identities cannot acquire those identities without editorial review; context and narrative-event comparisons supplement their exact checks. Corrupt source history fails visibly instead of starting over.

Canonical arc IDs and aliases, normalized titles, script hashes, narrative fingerprints and event comparisons apply only to Autopilot. Shared characters alone do not cause rejection. Semantic embeddings are not enabled; the configurable similarity threshold controls token-set narrative-event overlap. A separate bounded semantic editorial review compares each otherwise eligible candidate with the twelve most relevant prior arcs, ranked across all stored history using events and character aliases. Duplicate decisions or low-confidence novelty are rejected. This is conservative layered deduplication, not a mathematical guarantee of semantic novelty. Curated canonical aliases and diverse historical examples remain useful validation before activation.

Registry writes, cost reservations, daily assignments and publication-attempt claims use transactions. SQLite uses `BEGIN IMMEDIATE`; Firestore reads precede writes. A day reserves exactly one unused video and creates independent `video_id + IST publication_date + platform` records. Generation leases quarantine abandoned work rather than automatically repeating paid rendering. Duplicate scheduler invocations do not consume another video.

## Validation before activation

Run the offline regression suite from the repository root:

```sh
PYTHONPYCACHEPREFIX=/tmp/her-pycache .venv/bin/python -m unittest discover -s tests -q
./remotion/node_modules/.bin/tsc --noEmit -p remotion/tsconfig.json
```

An explicitly invoked, bounded **paid text-only** check is available:

```sh
.venv/bin/python -m scripts.validate_autopilot_story \
  --model meta/meta-llama-3-70b-instruct --category SCIFI \
  --output output/autopilot-validation/story-scifi
```

`--resume` reuses the last reserved concept after a script failure. Other supported test categories are `MYTHOLOGY`, `FANTASY`, `FOLKLORE`, and `OTHER`. Traditional stories require retrievable source URLs as well as named traditions and references. Retrieval reuses the existing bounded, IP-pinned public-source fetcher; the editorial review checks the retrieved text. Unavailable or unsupported traditions fail closed within the candidate budget.

To validate branding and covers without additional story/image/speech costs, use a **schema-compatible cached timeline with its staged assets still present**:

```sh
.venv/bin/python -m scripts.validate_autopilot_render \
  --props output/storytelling_zheng/editorial_props.json \
  --output output/autopilot-validation/editorial
```

This invokes the real production editorial renderer, including export and audio gates. It is explicitly a cached fixture regression, not approval of a newly generated story. Old cached manifests may require regeneration through the current pipeline if their schema predates the present engine.

From the dashboard, **Generate one video** deliberately runs a paid generation even while normal Autopilot is paused. It validates the planned story/visuals before narration and asset generation, then validates the final export. Required gates include hash-checked staged assets, the timeline's exact script/word contract, final-event visuals, dimensions/codecs/duration, audio signal, unintended silence excluding the existing outro, black intervals, watermark, hook and cover readability. The standalone cover checks the visible panel and light text so an asset obscuring the hook cannot pass unnoticed. Gates inspect the existing render plan and media signals; they do not perform expensive frame-by-frame semantic recognition.

Publishing retries never render again. A delivery failure leaves a validated video `PREPARED`; **Retry media delivery** recovers from the private archive, checks its hash and uploads again. If a worker dies before a durable archive upload completes, scratch assets may require operator recovery; it will not silently purchase a second render.

Use **Dry-run publishing test** to authenticate, resolve channels, verify a public video and inspect actual provider payloads without creating posts or consuming the daily assignment.

For initial **controlled live** tests, use an existing READY video separately from the production daily scheduler:

```sh
.venv/bin/python -m scripts.validate_buffer_publication \
  --story-id READY_STORY_ID --due-at '2026-10-26T18:30:00+05:30'
```

The command above only previews payloads. Choose an appropriate future date/time inside your configured window, inspect the result, then repeat with `--confirm-live-test` to explicitly schedule real test posts. This one test command bypasses normal dry-run/paused state; the daily workflow remains disabled. It reserves the test video, records attempts durably and reconciles repeated invocations. It does not generate another video. Run `python -m automation.autopilot_worker verify` after the scheduled time and inspect both external URLs. Confirm the Instagram cover in Buffer/the published Reel. Do not enable production until both records are remotely confirmed `SENT` with the expected video and automatic publishing.

## Cloud deployment

Read-only inspection confirmed the existing `project-her-510715` project, `project-her` Cloud Run service and native Firestore database in `us-central1`, plus `project-her-510715-portfolio-output` private storage. No Buffer secret exists in that project.

`deploy/autopilot/main.tf` is an infrastructure template for the **existing ProjectHER image/project**, not a second application. Copy `example.tfvars` to a private tfvars file and supply real resource identifiers and existing Secret Manager IDs. Enable the Run, Scheduler, Firestore, Storage, Secret Manager, Logging and Monitoring APIs in the project. Firestore must already have a native database. Review a Terraform plan before applying. Terraform is not installed in this checkout, so provider validation/application remains outstanding.

The template provisions one Cloud Run Job using the current Docker image, worker/scheduler service accounts, a dedicated public bucket, scoped secret access, authenticated Scheduler invocations and a failure metric/alert. The worker accesses the existing private bucket and Firestore. Grant the existing Flask service account Firestore access to `her_autopilot` and job execution with overrides; it dispatches the same worker via the Run API. Mount the admin token and set the job/project/region variables on that existing service. The HTTP action returns after dispatch and does not render inside the request.

Default schedules, all explicitly `Asia/Kolkata`:

| Step | Invocation | Behavior |
|---|---|---|
| Generate | 09:00, 11:00, 13:00, 15:00 | Fill unused validated inventory up to target three; daily budget still applies |
| Prepare | 10:10, 12:10, 14:10, 16:10 | Recover validated uploads; never render again |
| Schedule | Every 10 minutes, 16:00–18:50 | Assign one video/day; default publish 18:30 |
| Verify | Every 10 minutes, 18:00–23:50 | Query Buffer; record sent/error and external URLs |
| Retry | 18:05, :15, :25, :35, :45, :55 | Reconcile first; retry only eligible failed platform |

The job has no automatic Cloud Run paid-work retries and a two-hour task deadline. Scheduler may repeat an invocation safely. Generation and publication use independent durable locks and per-record claims. The default $2 reservation limit may require several days to build the reserve of three; increase it deliberately for initial inventory if appropriate.

After controlled publications pass, set `live_publishing_validated=true`, `buffer_dry_run=false`, `autopilot_enabled=true`, and unpause the schedulers in your reviewed deployment configuration. A persisted dashboard pause/enabled setting overrides the environment's enabled default, so inspect the dashboard state as well. Keep both web and job environments consistent. Configure at least one real Cloud Monitoring notification channel; an empty notification-channel list stores/logs alerts but does not deliver them to an administrator.

## Timing and failure recovery

`publication_time` uses an aware clock and the IANA zone; default 18:30 IST becomes 13:00 UTC. If the preferred time is missed, at least five minutes of lead time must remain inside the configured window. Otherwise inventory is deferred and the day is skipped. Existing assignments are not silently moved to another day or replaced by another video. No catch-up post is created tomorrow.

A remotely accepted post is only `SCHEDULED`. `PUBLISHED` requires both independent platform records to reach remote `sent`. Partial success remains `PARTIAL`; retrying YouTube cannot create another Instagram post. A known failed Buffer post is edited using its existing ID and a future in-window time, never recreated. Authentication/validation/rate-limit rejections have bounded backoff; repeated attempts open a circuit. Unknown HTTP/GraphQL outcomes remain `UNKNOWN` and reconcile by channel, caption and scheduled time before further action. If no definitive result is found, the workflow alerts and stops instead of guessing that the original mutation failed.

For a stuck `UNKNOWN` record, inspect Buffer for the exact channel, caption, due time and video. Preserve the record. Adopt the existing remote post ID only after verifying identity; never clear the record and trigger a fresh create just to remove an error. This deliberate fail-closed case may require operator intervention when a provider cannot establish whether it committed a mutation.

Pause Autopilot from the dashboard to stop new background generation/scheduling. Verification remains available. Posts already scheduled in Buffer retain their scheduled time; remove/pause those in Buffer if stopping their publication is intended. Manual ProjectHER generation stays available.

Use the dashboard's operation records, quality reports, per-platform errors and recent alerts. Worker failures also emit `AUTOPILOT_ALERT` to Cloud Logging. Inspect `command:<id>`, `story:<id>`, `publication:<date>:<platform>`, `daily:<date>`, `cost:<IST date>`, `llm-usage:<prediction>` and `engine-usage:<story>` in the durable store as needed. Keep diagnostic assets private.

## Cost and retention boundaries

Call counts, output token limits, input size, timeouts, candidate batches, script revisions, image requests, per-engine reservations and daily reservations are bounded. Every image creation attempt, including timeout retries in the current editorial engine, consumes a request reservation before the network call. Per-video logs distinguish story/validation LLM reservations, estimated images and unknown narration/render/storage bills. Replicate token metrics and prediction IDs are retained; configured token rates produce usage estimates. `actual_usd=null` means the provider did not supply a billed amount.

The example text rates ($0.65/million input tokens, $2.75/million output tokens) belong to the example Llama model and must be updated when selecting another model. Reservations are not bank-level spending guarantees across arbitrary provider pricing, existing Gemini analysis, narration, render compute or storage. Set conservative rates/reserves for the active engines and use provider/cloud billing budgets as the independent bill-level control. Do not infer an actual invoice from a reservation.

Do not attach a blanket age-based lifecycle rule to the publishable bucket: it could expire a queued or ambiguous post. `python -m scripts.cleanup_autopilot_media` lists public assets eligible after **both** platforms have confirmed SENT and the default seven-day retry/retention window has passed. `--execute` deletes only those videos/covers with generation preconditions and a verified video hash. Give a separate operator/janitor identity delete permission on the dedicated publishable bucket; the default generation worker has no delete permission. Private originals remain archived for diagnosis and follow the existing private-storage retention policy.

For rollback, pause schedulers, pause Autopilot and restore Buffer dry-run first. Reconcile already scheduled posts in Buffer. Deploy the previous ProjectHER image if needed, but retain the `her_autopilot` collection/public objects/archives and do not reset daily or publication records. Preserve historical keys across redeployments to keep duplicate protection intact.
