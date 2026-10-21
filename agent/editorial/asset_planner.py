"""Finalize unique paid assets over the existing semantic storyboard before acquisition.

No sentence rewriting, guessed action substitutions, or paid calls happen here.
"""
import json
import os
from pathlib import Path
from .image_policy import ImagePolicy, enabled
from agent.news_models import NewsError

PHYSICAL_ROLES={'action_tableau','interaction','aftermath'}


def finalize(script, output=None, enforce=True):
    p=ImagePolicy.load()
    registry={e.id:e for e in getattr(script,'identity_registry',[]) or script.entities}
    entities={e.id:e for e in script.entities}
    events={b['visual_section_id']:b for b in (getattr(script,'event_plan',None) or {}).get('beats',[])}
    assets={}; beats=[]
    required_masters=set()
    total_words=max(1,len(script.narration.split())); cursor=0
    from .image_policy import number
    words_per_second=number('PLANNER_WORDS_PER_MINUTE',150)/60
    if not words_per_second:raise ValueError('PLANNER_WORDS_PER_MINUTE must be positive')
    for row in getattr(script,'sentence_storyboard',[]):
        event=events.get(row['sentence_id'],{})
        refs=list(dict.fromkeys(row.get('continuity_references',[])))
        role=event.get('role',row.get('shot_role',''))
        # Semantic event roles are authoritative. Unknown legacy character poses
        # stay on the action tier instead of risking an inaccurate cheap image.
        physical=event.get('physical_action') is True or row.get('beat_type') in ('ACTION','EVENT') or role in PHYSICAL_ROLES or (not role and bool(refs)) or event.get('criticality')=='P0'
        typography=row.get('media_source')=='typography'
        if typography and (physical or not enabled('ENABLE_TEXT_ONLY_SCENES')):
            raise NewsError('Typography cannot replace essential action: '+row['sentence_id'])
        source=row.get('media_source','generated_scene')
        key=row['primary_entity_id']
        entity=entities[key]
        if physical:refs=list(dict.fromkeys(refs+event.get('actor_ids',[])))
        character_ids=[r for r in refs if r in registry and registry[r].kind in ('person','animal')]
        if character_ids and not enabled('ENABLE_CHARACTER_CONSISTENCY'):
            raise NewsError('Character consistency cannot be disabled for planned recurring character scenes')
        required_masters.update(character_ids)
        if physical:row['continuity_references']=character_ids
        mode='typography' if typography else 'verified_reference' if source=='verified_reference' else 'seedream' if physical else 'schnell'
        reuse=character_ids[0] if role=='character_intro' and len(character_ids)==1 and enabled('ENABLE_ASSET_REUSE') else None
        if source=='reuse_cutouts' and not enabled('ENABLE_ASSET_REUSE'):
            raise NewsError('Asset reuse is disabled but the semantic plan requires a reusable composition')
        if source=='reuse_cutouts':
            if event.get('criticality')=='P0' or not character_ids:
                raise NewsError('Unsafe or empty canonical composition: '+row['sentence_id'])
            reuse=character_ids[0]
            for rid in character_ids[1:]:
                if rid not in row['secondary_entity_ids']:row['secondary_entity_ids'].append(rid)
                sentence=next(s for s in script.sentences if s.id==row['sentence_id'])
                if rid not in sentence.entity_ids:sentence.entity_ids.append(rid)
                if rid not in entities:
                    script.entities.append(registry[rid]);entities[rid]=registry[rid]
        if reuse: mode='reuse'
        model=p.action if mode=='seedream' else p.character if entity.kind=='person' else p.background if entity.kind=='place' else p.object if entity.kind not in ('person','animal') else p.simple
        spec={'id':key,'mode':mode,'model':model if mode in ('schnell','seedream') else None,'reference_ids':character_ids if mode=='seedream' else [],'reuse_id':reuse,'estimated_cost_usd':p.price(model) if mode in ('schnell','seedream') else 0}
        previous=assets.get(key)
        if previous and previous!=spec:raise NewsError('Conflicting reuse requirements for asset '+key)
        assets[key]=spec
        n=len(row.get('narration_text','').split())
        beats.append({'section_id':row['sentence_id'],'asset_id':key,'mode':mode,'timing':{'estimated_start_sec':cursor/words_per_second,'estimated_end_sec':(cursor+n)/words_per_second,'start_fraction':cursor/total_words,'end_fraction':(cursor+n)/total_words,'provenance':'planning_word_fraction; bind to measured audio before render'}})
        cursor+=n
    for mid in sorted(required_masters):
        master=registry[mid]
        assets.setdefault(mid,{'id':mid,'mode':'schnell','model':p.character if master.kind=='person' else p.simple,'reference_ids':[],'reuse_id':None,'estimated_cost_usd':p.schnell_price})
    # Include secondary and legacy-mode assets, never silently omit their cost.
    for eid,e in entities.items():
        assets.setdefault(eid,{'id':eid,'mode':'schnell','model':p.character if e.kind=='person' else p.background if e.kind=='place' else p.object,'reference_ids':[],'reuse_id':None,'estimated_cost_usd':p.schnell_price})
    paid=[a for a in assets.values() if a['mode'] in ('schnell','seedream')]
    actions=sum(a['mode']=='seedream' for a in paid)
    cost=sum(a['estimated_cost_usd'] for a in paid)
    from .visual_pacing import pacing_issues

    # Cross-check action scene importances when action count or budget exceeds targets
    if actions > p.max_actions or len(paid) > p.max_images or cost > p.image_budget:
        action_candidates = []
        for idx, b in enumerate(beats):
            if b['mode'] == 'seedream':
                event = events.get(b['section_id'], {})
                crit = event.get('criticality', 'P1')
                spec = assets.get(b['asset_id'], {})
                ref_count = len(spec.get('reference_ids', []))
                role = event.get('role', '')
                score = (0 if crit == 'P2' else 1 if crit == 'P1' else 2) * 10 + ref_count
                action_candidates.append((score, idx, b, event, spec, role))

        action_candidates.sort(key=lambda x: (x[0], x[1]))

        # Pass 1: Check if lower-priority non-P0 beats can suffice with typography
        if enabled('ENABLE_TEXT_ONLY_SCENES'):
            for score, idx, b, event, spec, role in action_candidates:
                if actions <= p.max_actions and len(paid) <= p.max_images and cost <= p.image_budget:
                    break
                crit = event.get('criticality', 'P1')
                if crit == 'P0' or event.get('physical_action') is True:
                    continue
                test_modes = [('typography' if i == idx else x['mode']) for i, x in enumerate(beats)]
                if not pacing_issues(test_modes):
                    b['mode'] = 'typography'
                    spec['mode'] = 'typography'
                    spec['estimated_cost_usd'] = 0
                    for row in getattr(script, 'sentence_storyboard', []):
                        if row.get('sentence_id') == b['section_id']:
                            row['media_source'] = 'typography'
                    paid = [a for a in assets.values() if a['mode'] in ('schnell', 'seedream')]
                    actions = sum(a['mode'] == 'seedream' for a in paid)
                    cost = sum(a['estimated_cost_usd'] for a in paid)

        # Pass 2: For single-character non-P0 actions, optimize to schnell
        for score, idx, b, event, spec, role in action_candidates:
            if actions <= p.max_actions and cost <= p.image_budget:
                break
            if b['mode'] == 'seedream':
                crit = event.get('criticality', 'P1')
                refs = spec.get('reference_ids', [])
                if crit != 'P0' and len(refs) <= 1:
                    b['mode'] = 'schnell'
                    spec['mode'] = 'schnell'
                    spec['model'] = p.character if refs else p.simple
                    spec['estimated_cost_usd'] = p.schnell_price
                    paid = [a for a in assets.values() if a['mode'] in ('schnell', 'seedream')]
                    actions = sum(a['mode'] == 'seedream' for a in paid)
                    cost = sum(a['estimated_cost_usd'] for a in paid)

    pacing_errors=pacing_issues([b['mode'] for b in beats])
    conflicts=list(pacing_errors)
    allow_overrun = not enforce or os.getenv('PROJECTHER_ALLOW_ASSET_OVERRUN', '').lower() in ('true', '1', 'yes')
    try:
        p.check(0,cost)
    except NewsError as exc:
        if allow_overrun:
            pass
        else:
            conflicts.append(str(exc))
    if len(paid)>p.max_images:
        if not allow_overrun:
            conflicts.append(f'{len(paid)} images exceed configured maximum {p.max_images}; review required')
    if actions>p.max_actions:
        if not allow_overrun:
            conflicts.append(f'{actions} essential actions exceed configured maximum {p.max_actions}; review required')
    ratio=(len(paid)-actions)/len(paid) if paid else 1
    from .image_policy import number
    soft_target=number('GENERATED_IMAGE_SOFT_TARGET',8,True)
    warnings = []
    if len(paid)>soft_target:
        warnings.append('Image count above soft target; essential visuals retained')
    if ratio<p.ratio:
        warnings.append('Schnell ratio below target; preserve essential actions instead of padding asset count')
    if actions>p.max_actions:
        warnings.append(f'Essential actions ({actions}) retained above target {p.max_actions}; narrative actions preserved')
    if len(paid)>p.max_images:
        warnings.append(f'Paid images ({len(paid)}) retained above average threshold {p.max_images}; essential visuals preserved')
    if cost>p.image_budget:
        warnings.append(f'Estimated image cost ${cost:.3f} above budget ${p.image_budget:.2f}; essential visuals preserved')
    result={'typography_pacing':{'positions':[i+1 for i,b in enumerate(beats) if b['mode']=='typography'],'passed':not pacing_errors,'issues':pacing_errors},'version':1,'assets':list(assets.values()),'beats':beats,'estimated_image_cost_usd':round(cost,6),
        'other_services_reserved_usd':p.other_reserved,'estimated_total_reserved_usd':round(cost+p.other_reserved,6),
        'schnell_count':len(paid)-actions,'seedream_count':actions,'schnell_ratio':ratio,
        'soft_image_target':soft_target,'warnings':warnings,
        'limits':{'max_images':p.max_images,'max_action_images':p.max_actions,'image_budget_usd':p.image_budget,'video_budget_usd':p.total_budget},
        'conflicts':conflicts,'status':'needs_review' if conflicts else 'ready'}
    if output:
        Path(output).mkdir(parents=True,exist_ok=True)
        Path(output,'asset_generation_plan.json').write_text(json.dumps(result,indent=2))
    if conflicts and enforce:raise NewsError('Asset plan needs review: '+'; '.join(conflicts))
    return result


def generation_report(records, policy):
    counters={}; reserved=0; actual=0; actual_known=True; retries=0
    for r in records:
        model=r['model_name'];cost=float(r.get('estimated_cost') or 0);reserved+=cost
        counter=counters.setdefault(model,{'requests':0,'estimated_usd':0,'retry_usd':0})
        counter['requests']+=1;counter['estimated_usd']+=cost
        if r.get('retry_number',1)>1:counter['retry_usd']+=cost;retries+=cost
        charge=r.get('actual_charged_cost_usd')
        if charge is None:actual_known=False
        else:actual+=float(charge)
    for counter in counters.values():
        for key in ('estimated_usd','retry_usd'):counter[key]=round(counter[key],6)
    return {'models':counters,'reserved_image_usd':round(reserved,6),'retry_usd':round(retries,6),
        'actual_charged_image_usd':round(actual,6) if actual_known else None,
        'remaining_image_usd':round(policy.image_budget-reserved,6),
        'other_services_reserved_usd':policy.other_reserved,
        'remaining_total_reserved_usd':round(policy.total_budget-policy.other_reserved-reserved,6),
        'billing_status':'provider charges unavailable' if not actual_known else 'provider reported',
        'total_cost_status':'other services reserved estimate; final total charge not verified'}


def bind_timing(plan, words, output):
    for beat in plan['beats']:
        selected=[w for w in words if w.sectionId==beat['section_id']]
        if selected:
            beat['timing']={'start_sec':selected[0].start,'end_sec':selected[-1].end,
                'provenance':sorted({w.provenance for w in selected})}
    Path(output,'asset_generation_plan.json').write_text(json.dumps(plan,indent=2))
