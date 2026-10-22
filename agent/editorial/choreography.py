"""Word-triggered movement using the inherited cutout transfer primitive.

Flattened interactions stay intact. These motions support a depicted event,
and are explicitly not proof of articulated limb or prop motion.
"""
from .models import Event, frames


MOVEMENT = {
    'opening': (0,-16), 'entering': (20,16), 'sealing': (0,12),
    'disposal': (38,28), 'search': (30,0), 'recovery': (0,-24),
    'scattering': (26,8), 'gathering': (-26,-8), 'restoration': (0,-32),
    'confrontation': (24,0), 'uphill_push': (32,-24),
    'downhill_return': (-32,24), 'physical_interaction': (12,0),
}


def choreograph_actions(m,script,settings):
    plan=getattr(script,'narrative_plan',None)
    if plan is None:return
    words={s.id:[w for w in m['words'] if w.sectionId==s.id] for s in m['sections']}
    records=[]
    for beat in plan.beats:
        if not beat.required_action_visible:continue
        sw=words[beat.section_id]
        start=frames(sw[beat.start_word].start)
        end=max(start+1,frames(sw[beat.end_word-1].end))
        candidates=[l for l in m['layers'] if l.assetId and l.entityId in beat.asset_ids and l.startFrame<=start<l.endFrame]
        for layer in candidates:
            stop=min(end,layer.endFrame)
            dx,dy=MOVEMENT.get(beat.verb,(0,-12))
            # Reserve a short recovery to the original stage position. This
            # avoids accumulating offsets when a composite spans many verbs.
            middle=start+max(1,(stop-start)*2//3)
            ids=[]
            if settings.enableContextualTransitions and stop-start>=3:
                for suffix,a,b,x,y in [('act',start,middle,dx,dy),('settle',middle,stop,-dx,-dy)]:
                    eid=f'action-{beat.id}-{layer.id}-{suffix}'
                    m['events'].append(Event(id=eid,type='transfer',targetIds=[layer.id],startFrame=a,endFrame=b,dx=x,dy=y))
                    ids.append(eid)
            records.append({'beatId':beat.id,'verb':beat.verb,'layerId':layer.id,'assetId':layer.assetId,
                'startFrame':start,'endFrame':stop,'eventIds':ids,
                'portrayal':'composite_motion_fallback',
                'requiresVisualReview':True,
                'limitation':'Whole-cutout movement; contact, occlusion and separate body/prop articulation are not verified.'})
    m['diagnostics']['actionChoreography']={'actions':records,
        'articulatedActionAcceptance':False if records else None,
        'motionEnabled':settings.enableContextualTransitions}
