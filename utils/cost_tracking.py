"""Per-video estimates for the supported Schnell/Seedream image combination."""
from __future__ import annotations
import config


def summarize_model_usage_and_costs(prediction_records=None, asset_records=None):
    pricing=config.REPLICATE_MODEL_ESTIMATED_COSTS
    schnell=config.SIMPLE_IMAGE_MODEL
    seedream=config.ACTION_IMAGE_MODEL
    counts={schnell:0,seedream:0};costs={schnell:0.0,seedream:0.0}
    roles={key:0.0 for key in ('initial_character','scene_editing','supporting_objects','retries')}
    rejected_count=0;rejected_cost=0.0;total=0.0;unpriced=0;attempts=[]
    for rec in prediction_records or []:
        if not rec.get('prediction_id'):continue
        model=rec.get('model_name') or 'unknown'
        supplied=rec.get('estimated_cost')
        unit=float(supplied) if isinstance(supplied,(int,float)) else pricing.get(model)
        if unit is None:
            unpriced+=1;unit=0.0
        counts[model]=counts.get(model,0)+1;costs[model]=costs.get(model,0.0)+unit;total+=unit
        rejected=rec.get('outcome')=='rejected' or rec.get('status') in ('failed','canceled')
        if rejected:rejected_count+=1;rejected_cost+=unit
        tier=rec.get('tier')
        role='supporting_objects' if tier=='support' else 'initial_character' if tier=='person' else 'scene_editing'
        roles[role]+=unit
        if rec.get('retry_number',1)>1:roles['retries']+=unit
        attempts.append({key:rec.get(key) for key in ('sentence_id','character_or_object','model_name','reference_count','prediction_id','retry_number','rejection_reason')})
        attempts[-1].update(generation_duration=rec.get('total_provider_wait_seconds'),
            outcome=rec.get('outcome') or ('accepted' if rec.get('status')=='succeeded' else 'unverified'),
            estimated_cost=unit,final_asset_path=rec.get('final_asset_path') or rec.get('target_path'))
    report=(f"MODEL USAGE\nFLUX Schnell: {counts[schnell]} images — ${costs[schnell]:.3f}\n"
            f"Seedream 4: {counts[seedream]} images — ${costs[seedream]:.3f}\n"
            f"Rejected Attempts: {rejected_count}\nCost of Rejected Images: ${rejected_cost:.3f}\n"
            f"Retry cost: ${roles['retries']:.3f}\nTotal Estimated Replicate Cost: ${total:.3f}\n"
            f"Unpriced Predictions: {unpriced}\nActual Billed Cost: N/A (configured estimates only)")
    return {'model_counts':counts,'model_costs':{k:round(v,6) for k,v in costs.items()},
        'flux_schnell':{'count':counts[schnell],'cost':round(costs[schnell],6)},
        'seedream_4':{'count':counts[seedream],'cost':round(costs[seedream],6)},
        'rejected_attempts':rejected_count,'cost_of_rejected_images':round(rejected_cost,6),
        'total_estimated_replicate_cost':round(total,6),'actual_billed_cost':None,
        'unpriced_prediction_count':unpriced,'role_breakdown':{k:round(v,6) for k,v in roles.items()},
        'attempts':attempts,'formatted_text':report}
