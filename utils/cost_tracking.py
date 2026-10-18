"""Accurate per-video image cost tracking for ProjectHER.

Tracks FLUX Schnell, Pruna P-Image-Edit, FLUX Kontext Pro, retries, and role breakdowns.
"""
from __future__ import annotations
import config


def summarize_model_usage_and_costs(prediction_records: list[dict] | None = None, asset_records: list[dict] | None = None) -> dict:
    pricing = getattr(config, 'REPLICATE_MODEL_ESTIMATED_COSTS', {
        'black-forest-labs/flux-schnell': 0.003,
        'prunaai/p-image-edit': 0.010,
        'black-forest-labs/flux-kontext-pro': 0.040,
        'black-forest-labs/flux-1.1-pro': 0.040,
        'black-forest-labs/flux-dev': 0.040,
        'google/nano-banana-pro': 0.040,
    })

    model_counts: dict[str, int] = {
        'black-forest-labs/flux-schnell': 0,
        'prunaai/p-image-edit': 0,
        'black-forest-labs/flux-kontext-pro': 0,
    }
    model_costs: dict[str, float] = {
        'black-forest-labs/flux-schnell': 0.0,
        'prunaai/p-image-edit': 0.0,
        'black-forest-labs/flux-kontext-pro': 0.0,
    }

    rejected_count = 0
    rejected_cost = 0.0
    total_cost = 0.0
    attempts_list = []

    roles = {
        'initial_character': 0.0,
        'scene_editing': 0.0,
        'supporting_objects': 0.0,
        'retries': 0.0,
        'premium_fallback': 0.0,
    }

    # A rejected HTTP request or local validation failure has no Replicate
    # prediction and must not be reported as a billed output image.
    records = [r for r in (prediction_records or []) if r.get('prediction_id')]
    for rec in records:
        model = rec.get('model_name') or 'unknown'
        if isinstance(rec.get('estimated_cost'),(int,float)):
            unit_cost = float(rec['estimated_cost'])
        elif model in pricing:
            unit_cost = pricing[model]
        elif 'schnell' in model.lower():
            unit_cost = 0.003
        elif 'pruna' in model.lower() or 'p-image-edit' in model.lower():
            unit_cost = 0.010
        elif 'kontext' in model.lower() or 'pro' in model.lower():
            unit_cost = 0.040
        else:
            unit_cost = pricing.get(model, 0.010)
        status = rec.get('status')
        outcome = rec.get('outcome')
        is_rejected = (outcome == 'rejected' or status in ('failed', 'canceled'))

        model_counts[model] = model_counts.get(model, 0) + 1
        model_costs[model] = model_costs.get(model, 0.0) + unit_cost
        total_cost += unit_cost

        if is_rejected:
            rejected_count += 1
            rejected_cost += unit_cost
            roles['retries'] += unit_cost
        else:
            tier = rec.get('tier')
            if tier == 'support':
                roles['supporting_objects'] += unit_cost
            elif tier == 'action':
                roles['scene_editing'] += unit_cost
            elif tier == 'person':
                roles['initial_character'] += unit_cost
            elif tier == 'support_alternate':
                roles['premium_fallback'] += unit_cost
            else:
                roles['scene_editing'] += unit_cost

        attempts_list.append({
            'sentence_id': rec.get('sentence_id'),
            'character_or_object': rec.get('character_or_object'),
            'model_name': model,
            'reference_count': rec.get('reference_count', 0),
            'turbo': rec.get('turbo'),
            'prediction_id': rec.get('prediction_id'),
            'generation_duration': rec.get('total_provider_wait_seconds'),
            'retry_number': rec.get('retry_number', 1),
            'outcome': outcome or ('accepted' if status == 'succeeded' else 'rejected'),
            'rejection_reason': rec.get('rejection_reason'),
            'estimated_cost': unit_cost,
            'final_asset_path': rec.get('final_asset_path') or rec.get('target_path'),
        })

    schnell_count = model_counts.get('black-forest-labs/flux-schnell', 0)
    schnell_cost = model_costs.get('black-forest-labs/flux-schnell', 0.0)
    pruna_count = model_counts.get('prunaai/p-image-edit', 0)
    pruna_cost = model_costs.get('prunaai/p-image-edit', 0.0)
    kontext_count = model_counts.get('black-forest-labs/flux-kontext-pro', 0)
    kontext_cost = model_costs.get('black-forest-labs/flux-kontext-pro', 0.0)

    extra_model_lines = []
    standard_models = {'black-forest-labs/flux-schnell', 'prunaai/p-image-edit', 'black-forest-labs/flux-kontext-pro'}
    for m, c in model_counts.items():
        if m not in standard_models and c > 0:
            extra_model_lines.append(f"{m}: {c} images — ${model_costs.get(m, 0.0):.3f}")
    extra_text = ("\n" + "\n".join(extra_model_lines)) if extra_model_lines else ""

    text_report = (
        "MODEL USAGE\n"
        f"FLUX Schnell: {schnell_count} images — ${schnell_cost:.3f}\n"
        f"Pruna P-Image-Edit: {pruna_count} images — ${pruna_cost:.3f}\n"
        f"Kontext Pro: {kontext_count} images — ${kontext_cost:.3f}"
        f"{extra_text}\n"
        f"Rejected Attempts: {rejected_count}\n"
        f"Cost of Rejected Images: ${rejected_cost:.3f}\n"
        f"Total Estimated Replicate Cost: ${total_cost:.3f}\n"
        "Actual Billed Cost: N/A (estimated based on published Replicate pricing)\n\n"
        "Cost Breakdown by Category:\n"
        f"- Initial character generation: ${roles['initial_character']:.3f}\n"
        f"- Scene-specific editing: ${roles['scene_editing']:.3f}\n"
        f"- Supporting objects: ${roles['supporting_objects']:.3f}\n"
        f"- Retry cost: ${roles['retries']:.3f}\n"
        f"- Premium fallback cost: ${roles['premium_fallback']:.3f}"
    )

    return {
        'model_counts': model_counts,
        'model_costs': {k: round(v, 4) for k, v in model_costs.items()},
        'flux_schnell': {'count': schnell_count, 'cost': round(schnell_cost, 4)},
        'pruna_p_image_edit': {'count': pruna_count, 'cost': round(pruna_cost, 4)},
        'flux_kontext_pro': {'count': kontext_count, 'cost': round(kontext_cost, 4)},
        'rejected_attempts': rejected_count,
        'cost_of_rejected_images': round(rejected_cost, 4),
        'total_estimated_replicate_cost': round(total_cost, 4),
        'actual_billed_cost': None,
        'role_breakdown': {k: round(v, 4) for k, v in roles.items()},
        'attempts': attempts_list,
        'formatted_text': text_report,
    }
