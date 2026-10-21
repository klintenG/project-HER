# ProjectHER image model configuration

Image generation supports exactly two Replicate models:

| Role | Model | Configurable estimate |
| --- | --- | --- |
| Character masters, standalone objects, backgrounds and simple subjects | `black-forest-labs/flux-schnell` | $0.003/image |
| Significant actions, interactions and reference-guided edits | `bytedance/seedream-4` | $0.030/output |

```dotenv
REPLICATE_API_TOKEN=your_token
CHARACTER_IMAGE_MODEL=black-forest-labs/flux-schnell
OBJECT_IMAGE_MODEL=black-forest-labs/flux-schnell
BACKGROUND_IMAGE_MODEL=black-forest-labs/flux-schnell
SIMPLE_IMAGE_MODEL=black-forest-labs/flux-schnell
ACTION_IMAGE_MODEL=bytedance/seedream-4
SCHNELL_MAX_RETRIES=2
SEEDREAM_MAX_RETRIES=0
SEEDREAM_MAX_IMAGES=1
SEEDREAM_SEQUENTIAL_GENERATION=disabled
SCHNELL_ESTIMATED_COST_USD=0.003
SEEDREAM_ESTIMATED_COST_USD=0.030
MAX_IMAGE_BUDGET_USD=0.12
MAX_TOTAL_VIDEO_BUDGET_USD=0.20
OTHER_SERVICES_RESERVED_USD=0.08
```

`config.py` resolves all existing News, editorial and general-image compatibility
names from these roles. Those compatibility names cannot select other models.
Unsupported canonical model values fail at startup. A custom adapter name cannot
bypass the allowlist. There are no alternative image providers or model-switching
fallbacks. Text planning, narration, visual review and cutout segmentation retain
their own required models; these are not image-generation models.

The general styled-image path uses Schnell. News uses Schnell for new subjects
and Seedream for reference-guided edits; licensed original photographs remain
usable without a paid generation request. Editorial actions use Seedream and
original saved character masters, including both references for two-character
interactions. The smart narration planner continues selecting reusable assets
and separated typography scenes.

Seedream requests always specify one output and disabled sequential generation.
No quality or create-request retries occur, and no alternative model is submitted
when a Seedream asset fails. Accepted predictions are polled by their existing ID.
Schnell retries remain bounded and subject to the existing editorial budget check.

Cost reports contain Schnell and Seedream counts and configurable estimates,
with retry costs separated from rejected-image costs. Actual billing is unknown
unless explicitly reported. Unpriced archived records are disclosed rather than
assigned an invented price. Other-service costs remain a reserved estimate.

See [.env.example](.env.example) for the complete configuration and
[smart image generation](docs/SMART_IMAGE_GENERATION.md) for asset plans, timing,
reference storage, typography pacing and validation scope.
