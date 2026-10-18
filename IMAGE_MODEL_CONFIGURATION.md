# ProjectHER image model configuration

Image routing is loaded by `config.py` at process startup. A running video job keeps that imported configuration; restart the application after editing `.env`. Process and Cloud Run environment variables take precedence over the local `.env` file. Never put API tokens in the frontend or a checked-in file.

## Roles

| Variable | Default | Adapter | Reference images | Cost effect |
| --- | --- | --- | --- | --- |
| `PROJECTHER_IMAGE_PROVIDER` | `replicate` | Replicate | Depends on model | Yes; currently only Replicate is supported |
| `PROJECTHER_IMAGE_IDENTITY_MODEL` | `black-forest-labs/flux-schnell` | `flux_schnell` | No | Yes |
| `PROJECTHER_IMAGE_SUPPORT_MODEL` | `black-forest-labs/flux-schnell` | `flux_schnell` | No | Yes |
| `PROJECTHER_IMAGE_CONTINUITY_MODEL` | `prunaai/p-image-edit` | `pruna_edit` | Multiple | Yes |
| `PROJECTHER_IMAGE_PREMIUM_MODEL` | `black-forest-labs/flux-kontext-pro` | `flux_kontext` | One | Yes, only when enabled |
| `PROJECTHER_IMAGE_ALTERNATE_EDIT_MODEL` | `black-forest-labs/flux-kontext-dev` | `flux_kontext` | One | Yes, only when enabled |
| `PROJECTHER_IMAGE_SUPPORT_FALLBACK_MODEL` | `black-forest-labs/flux-1.1-pro` | `flux_pro` | No | Yes, only when enabled |

All roles are validated during startup, including disabled fallback roles. To switch continuity models, change only `PROJECTHER_IMAGE_CONTINUITY_MODEL` and restart. Supported values include `prunaai/p-image-edit`, `black-forest-labs/flux-kontext-pro`, and `black-forest-labs/flux-kontext-dev`. A custom model needs a verified compatible `PROJECTHER_IMAGE_<ROLE>_ADAPTER`; otherwise startup fails before any paid request. Existing adapters are `flux_schnell`, `flux_pro`, `flux_dev`, `pruna_edit`, `flux_kontext`, and `nano_banana`. Schema compatibility is the operator's responsibility for custom IDs.

The `PROJECTHER_PREMIUM_FALLBACK_ENABLED`, `PROJECTHER_ALTERNATE_EDIT_FALLBACK_ENABLED`, and `PROJECTHER_SUPPORT_FALLBACK_ENABLED` switches default to `false`. An enabled edit fallback must support the same number of references as the scene. A one-reference Kontext fallback will fail clearly for a two-character Pruna scene. `PROJECTHER_IMAGE_BUDGET_USD` is a planning cap for fallback attempts, not a billing guarantee.

`PROJECTHER_PRUNA_TURBO`, `PROJECTHER_PRUNA_COMPLEX_SCENE_TURBO`, `PROJECTHER_PRUNA_RETRY_TURBO`, `PROJECTHER_PRUNA_MAX_ATTEMPTS`, and optional `PROJECTHER_PRUNA_SEED` control Pruna execution. `PROJECTHER_IMAGE_MAX_CONCURRENCY`, `PROJECTHER_IMAGE_RETRIES`, and `PROJECTHER_IMAGE_TIMEOUT_SECONDS` control image execution. Set `PROJECTHER_IMAGE_<ROLE>_ESTIMATED_COST_USD` to revise planning rates as prices change. The cost report describes estimated image charges, not the Replicate invoice.

The older `PROJECTHER_CHARACTER_EDIT_MODEL`, `EDITORIAL_ACTION_IMAGE_MODEL`, `EDITORIAL_SUPPORT_IMAGE_MODEL`, `EDITORIAL_FALLBACK_IMAGE_MODEL`, `NEWS_REAL_IMAGE_MODEL`, and `NEWS_REFERENCE_IMAGE_MODEL` values remain accepted for older deployments when the new role variable is absent. Set only the new role variables for new deployments. Explicit new role values take precedence over these older values. The News and Reference Editorial paths resolve through the same continuity role when it is set. Other existing AI model settings (`GEMINI_MODEL`, `GROQ_MODEL`, `EDITORIAL_VISION_MODEL`, `GEMINI_TTS_MODEL`, `NEWS_REPLICATE_TTS_MODEL`, `ELEVENLABS_MODEL`, `HER_ALIGNMENT_MODEL`, and `NEWS_CUTOUT_MODELS`) remain environment configurable.

## Examples

```dotenv
# Low cost
PROJECTHER_IMAGE_IDENTITY_MODEL=black-forest-labs/flux-schnell
PROJECTHER_IMAGE_SUPPORT_MODEL=black-forest-labs/flux-schnell
PROJECTHER_IMAGE_CONTINUITY_MODEL=prunaai/p-image-edit
PROJECTHER_PREMIUM_FALLBACK_ENABLED=false

# Premium continuity: replace only the continuity value above
# PROJECTHER_IMAGE_CONTINUITY_MODEL=black-forest-labs/flux-kontext-pro

# Alternative editor: replace only the continuity value above
# PROJECTHER_IMAGE_CONTINUITY_MODEL=black-forest-labs/flux-kontext-dev
```

For Cloud Run, supply the same variable names as service environment variables and deploy a new revision. Keep `REPLICATE_API_TOKEN`, Gemini, and speech credentials in Secret Manager or the deployment's existing secret mechanism. The portfolio at klinteng.com continues to call the configured ProjectHER backend; it does not need image model variables.

The [Replicate Pruna schema](https://replicate.com/prunaai/p-image-edit/api/schema) uses an `images` array, `prompt`, `aspect_ratio`, optional `turbo`, and optional `seed`. Pricing displayed by Replicate was $0.01 per output image when checked on 18 October 2026. The [Kontext Pro schema](https://replicate.com/black-forest-labs/flux-kontext-pro/api/schema) uses `input_image` and displayed $0.04 per output image. Verify prices before changing estimates.
