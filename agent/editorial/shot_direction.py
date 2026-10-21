"""Offline Phase 2 director. Phase 1 owns depiction; this pass only stages it.

Uses existing layers/events and absolute 30fps audio clock. The inspectable v1
shot plan retains exact word, asset and action references; no provider calls.
"""
from __future__ import annotations
import os
from typing import Literal
from pydantic import Field
from .models import Model, Bounds, Event, LayerMotion, frames
from . import scene_plan


class MotionSettings(Model):
    enabled: bool = True
    intensity: Literal['restrained', 'standard', 'energetic'] = 'standard'
    layoutVariety: bool = True
    layeredParallax: bool = True
    kineticText: bool = True
    allowDocumentaryFrames: bool = True
    maxIdenticalLayoutStreak: int = Field(default=2, ge=1, le=5)
    longHoldWarningMs: int = Field(default=4500, ge=1000, le=30000)
    entryMs: int = Field(default=280, ge=100, le=450)
    exitMs: int = Field(default=160, ge=0, le=300)
    staggerMs: int = Field(default=130, ge=0, le=250)

    @classmethod
    def configured(cls):
        # Pydantic parses booleans and rejects misspellings rather than silently
        # treating invalid environment settings as false.
        keys = {'enabled':'ENABLED', 'intensity':'INTENSITY', 'layoutVariety':'LAYOUT_VARIETY',
                'layeredParallax':'LAYERED_PARALLAX', 'kineticText':'KINETIC_TEXT',
                'allowDocumentaryFrames':'ALLOW_DOCUMENTARY_FRAMES',
                'maxIdenticalLayoutStreak':'MAX_IDENTICAL_LAYOUT_STREAK',
                'longHoldWarningMs':'LONG_HOLD_WARNING_MS', 'entryMs':'ENTRY_MS',
                'exitMs':'EXIT_MS', 'staggerMs':'STAGGER_MS'}
        return cls.model_validate({k:os.environ['HER_EDITORIAL_MOTION_V2_'+v] for k,v in keys.items()
                                   if 'HER_EDITORIAL_MOTION_V2_'+v in os.environ})


FAMILIES = {
    'HOOK': ('typography_led_hook', 'object_or_evidence_focus'),
    'CHARACTER_INTRO': ('hero_introduction', 'object_or_evidence_focus'),
    'CONTEXT': ('object_or_evidence_focus', 'multi_layer_event'),
    'ACTION': ('action_focus', 'multi_layer_event'),
    'EVENT': ('multi_layer_event', 'action_focus'),
    'REACTION': ('reaction_punch', 'dual_subject_tension'),
    'CONFLICT': ('conflict_or_chase', 'dual_subject_tension'),
    'TWIST': ('reveal_or_twist', 'action_focus'),
    'OUTRO': ('closing_resolve', 'hero_introduction'),
}


def composition(family, count, mirror=False, variant=0):
    """Normalized safe canvas: brand above .13, UI below .84. No subject flips."""
    def b(x,y,w,h):
        if mirror:x=1-x-w
        return Bounds(x=round(x*1080),y=round(y*1920),w=round(w*1080),h=round(h*1920))
    top=b(.09,.155,.82,.14)
    bottom=b(.09,.70,.82,.13)
    if family in ('hero_introduction','reaction_punch'):
        caption=b(.085,.31,.34,.25)
        primary=b(.47,.25,.44,.43)
        supports=[b(.08,.60,.28,.18),b(.68,.65,.23,.15)]
    elif family=='typography_led_hook':
        caption=b(.09,.24,.82,.21)
        primary=b(.23,.47,.58,.28)
        supports=[b(.08,.55,.24,.20),b(.70,.53,.23,.20)]
    elif family in ('dual_subject_tension','conflict_or_chase'):
        caption=top
        primary=b(.06,.34,.43,.36) if count>1 else b(.08,.34,.84,.40)
        supports=[b(.51,.38,.43,.35),b(.38,.65,.24,.14)]
    elif family=='object_or_evidence_focus':
        caption=bottom
        primary=b(.15,.29,.70,.37)
        supports=[b(.04,.45,.24,.22),b(.75,.43,.20,.23)]
    elif family=='reveal_or_twist':
        caption=bottom
        primary=b(.08,.22,.84,.44)
        supports=[b(.70,.46,.23,.22),b(.04,.49,.23,.20)]
    elif family=='closing_resolve':
        caption=bottom
        primary=b(.18,.29,.64,.35)
        supports=[b(.06,.49,.25,.19),b(.72,.48,.23,.20)]
    else:
        # Wide combined action tableaux keep anatomical contact intact. Offset
        # the group without reflecting pixels or breaking a held prop away.
        caption=bottom if variant%2 else top
        primary=b(.06 if variant%2 else .12,.25 if variant%2 else .34,.80,.40)
        supports=[b(.70,.46 if variant%2 else .52,.24,.20),b(.04,.49 if variant%2 else .57,.22,.17)]
    return caption,[primary,*supports][:count]


def direct(m, script, visual_settings, settings=None):
    cfg=settings or MotionSettings.configured()
    if not cfg.enabled:return
    rows={r['sentence_id']:r for r in getattr(script,'sentence_storyboard',[]) if r.get('scene_plan')}
    if not rows:return  # Legacy/local documentary routes remain unchanged.
    source_rows={r['primary_entity_id']:r for r in rows.values()}
    layers={l.id:l for l in m['layers']};assets={a.id:a for a in m['assets']}
    directed={l.id for l in m['layers'] if l.assetId and any(l.entityId==r['primary_entity_id'] or l.entityId in r.get('secondary_entity_ids',[]) for r in rows.values())}
    # One transform owner. Retain unrelated factual object events/provenance.
    m['events']=[e for e in m['events'] if not (set(e.targetIds)&directed and e.type in ('settle','fade','reframe','emphasis','focus_shift'))]
    plans=[];positions={};families=[];section_family={};warnings=[]
    for beat in m['beats']:
        sid=beat.sectionIds[0];row=rows.get(sid)
        if not row:continue
        scene=row['scene_plan'];kind=scene['beat_type']
        visible=[layers[lid] for lid in beat.layerIds if layers[lid].assetId and layers[lid].startFrame<beat.endFrame and layers[lid].endFrame>beat.startFrame]
        visible.sort(key=lambda l:l.entityId!=row['primary_entity_id'])
        if not visible:
            warnings.append(f'{beat.id}: no visual overlaps this spoken phrase');continue
        if sid not in section_family:
            candidates=FAMILIES[kind]
            family=candidates[0]
            if cfg.layoutVariety and len(families)>=cfg.maxIdenticalLayoutStreak and all(f==family for f in families[-cfg.maxIdenticalLayoutStreak:]):family=candidates[1]
            section_family[sid]=(family,len(families));families.append(family)
        family,index=section_family[sid]
        mirror=bool(index%2) if cfg.layoutVariety else False
        variant=index if cfg.layoutVariety else 0
        # Replacement assets may share a phrase interval without ever sharing
        # the screen. Size only simultaneous subjects, never future entrants.
        boundaries=sorted({beat.startFrame,*[v.startFrame for v in visible if beat.startFrame<v.startFrame<beat.endFrame],*[v.endFrame for v in visible if beat.startFrame<v.endFrame<beat.endFrame]})
        concurrent=max(sum(v.startFrame<=at<v.endFrame for v in visible) for at in boundaries)
        caption,_=composition(family,concurrent,mirror,variant)
        text=next((layers[lid] for lid in beat.layerIds if layers[lid].role=='phrase'),None)
        if text:
            from .planner import phrase_layout
            text.bounds=caption
            text.phrase.lines,text.phrase.size=phrase_layout(text.phrase.wordIds,m['words'],caption.w,100,caption.h)
            text.phrase.align='left' if family in ('hero_introduction','reaction_punch') else 'center'
            text.phrase.animation=('line_reveal' if family=='reveal_or_twist' else 'group_slide') if cfg.kineticText else 'word_slide'
        placements={v.id:[] for v in visible}
        for step,at in enumerate(boundaries):
            stop=boundaries[step+1] if step+1<len(boundaries) else beat.endFrame
            live=[v for v in visible if v.startFrame<=at<v.endFrame]
            _,boxes=composition(family,len(live),mirror,variant)
            for j,(layer,box) in enumerate(zip(live,boxes)):
                placements[layer.id].append({'frame':at,'bounds':box.model_dump()})
                if layer.id not in positions:layer.bounds=box
                elif positions[layer.id]!=box:
                    m['events'].append(Event(id=f'shot-reframe-{beat.id}-{step}-{j}',type='reframe',targetIds=[layer.id],startFrame=at,endFrame=min(stop,layer.endFrame,at+8),boundsFrom=positions[layer.id],boundsTo=box))
                positions[layer.id]=box
        tracks=[]
        for n,layer in enumerate(visible):
            box=Bounds(**placements[layer.id][0]['bounds'])
            asset=assets[layer.assetId]
            generated=not asset.factual and not asset.alpha and asset.preparation=='rectangle'
            if generated:raise ValueError(f'{sid}: generated story asset {asset.id} has no alpha; rectangular scene-card fallback is prohibited')
            documentary=asset.factual or asset.role in ('photo','map','document')
            if not cfg.allowDocumentaryFrames and documentary and not asset.alpha:
                raise ValueError(f'{sid}: documentary frames disabled; choose an alpha asset or enable documentary frames')
            if documentary and not asset.alpha:layer.shadow=False
            at=max(beat.startFrame,layer.startFrame);until=min(beat.endFrame,layer.endFrame)
            if layer.id in directed and not any(t['layerId']==layer.id for p in plans for t in p['objectTracks']):
                base=scene_plan.motion_spec(kind,bool(index%2))
                factor={'restrained':.45,'standard':.75,'energetic':1.0}[cfg.intensity]
                # Direction follows the story, rather than arbitrary alternate mirroring.
                action=' '.join(str(row.get(k,'')) for k in ('main_action','visual_focus')).lower()
                if 'uphill' in action or 'up a hill' in action:base.update(driftX=24,driftY=-24,tilt=0)
                if 'downhill' in action or 'back down' in action:base.update(driftX=-26,driftY=22,tilt=0)
                base.update(driftX=base['driftX']*factor,driftY=base['driftY']*factor,tilt=base['tilt']*factor,scaleTo=1+(base['scaleTo']-1)*factor)
                length=layer.endFrame-layer.startFrame
                base['entranceFrames']=max(1,min(round(cfg.entryMs*30/1000),max(1,length//3)))
                # Show recognizable silhouette immediately at an exact action onset;
                # settling continues afterwards without hiding the narrated action.
                base['initialOpacity']=1 if kind in ('ACTION','EVENT','CONFLICT','TWIST') else .25
                base['entranceTravel']=56*factor
                if kind in ('HOOK','TWIST'):base['entrance']='punch'
                base['exitFrames']=min(round(cfg.exitMs*30/1000),max(0,length//5))
                base['focusFrame']=max(layer.startFrame,min(until-1,frames(next((w.start for w in m['words'] if w.sectionId==sid and any(x in w.text.casefold() for x in ('grab','reveal','refus','push','trick'))),at/30))))
                base['focusScale']=1.025 if kind in ('REACTION','TWIST','ACTION') else 1
                elements=layer.motion.elements if layer.motion and cfg.layeredParallax else []
                for k,el in enumerate(elements):el.delayFrames=min(round(cfg.staggerMs*30/1000)*k,max(0,length//4))
                layer.motion=LayerMotion(**base,elements=elements)
            asset_row=source_rows.get(layer.entityId,row)
            tracks.append({'layerId':layer.id,'assetId':asset.id,'hasAlpha':asset.alpha,'assetRole':asset.role,
                           'depictedAction':asset_row.get('main_action',''),'subjectIds':asset_row.get('identity_reference_ids',[]),
                           'startFrame':at,'endFrame':until,'bounds':box.model_dump(),'keyframes':placements[layer.id],
                           'motion':layer.motion.model_dump() if layer.motion else None})
        plans.append({'beatId':beat.id,'sectionId':sid,'beatType':kind,'primaryVisualIntent':scene['visual_intent'],
                      'layoutId':family,'startFrame':beat.startFrame,'endFrame':beat.endFrame,'narrationText':beat.purpose,
                      'objectTracks':tracks,'textTracks':[{'layerId':text.id,'wordIds':text.phrase.wordIds,'animationId':text.phrase.animation,'bounds':caption.model_dump()}] if text else [],
                      'transition':'reveal_cut' if kind=='TWIST' else 'linked_exit_entry'})
    for p in plans:
        if (p['endFrame']-p['startFrame'])*1000/30>cfg.longHoldWarningMs:warnings.append(p['beatId']+': long visual hold; review narrative pacing')
    m['diagnostics']['shotDirection']={'version':'editorial-motion-v2.1','fps':30,'settings':cfg.model_dump(),'shots':plans,'warnings':warnings}
    m['warnings'].extend(warnings)
