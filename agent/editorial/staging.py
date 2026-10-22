"""Narration-led editorial staging on persistent, independently keyed layers.

Uses the branch-1 reframe grammar: reveal, make room for type, promote a
spoken subject from the group, and carry surviving images into the next shot.
"""
import re
from .models import Bounds, frames


def focus_cues(m,script):
    registry={e.id:e for e in [*getattr(script,'identity_registry',[]),*script.entities]}
    members={row['primary_entity_id']:set(row.get('depicted_entity_ids',row.get('identity_reference_ids',[])))
        for row in getattr(script,'sentence_storyboard',[])}
    visuals=[l for l in m['layers'] if l.assetId]
    norm=lambda text:re.sub(r'[^\w]','',text.casefold())
    cues=[]
    for section in m['sections']:
        words=[w for w in m['words'] if w.sectionId==section.id]
        keys=[norm(w.text) for w in words]
        for i,word in enumerate(words):
            at=frames(word.start)
            live=[l for l in visuals if l.startFrame<=at<l.endFrame]
            matches=[]
            for eid,entity in registry.items():
                # Composite catalog names are not spoken identity names.
                if eid.startswith(('scene-','action-')):continue
                name=[norm(t) for t in entity.name.split()]
                if name and keys[i:i+len(name)]==name:
                    candidates=[l for l in live if l.entityId==eid or eid in members.get(l.entityId,set())]
                    if candidates:matches.append((len(name),candidates[0],eid))
            if matches:
                _,layer,eid=max(matches,key=lambda row:row[0])
                cues.append({'frame':at,'layerId':layer.id,'entityId':eid,'wordId':word.id})
    return sorted(cues,key=lambda row:row['frame'])


def focus_at(live,at,cues,atomic):
    ids={l.id for l in live}
    spoken=next((c for c in reversed(cues) if c['frame']<=at and c['layerId'] in ids),None)
    # A new primary scene supersedes an old supporting subject until another
    # subject is actually named. Don't let yesterday's cue own today's shot.
    latest=next((b for b in reversed(atomic) if b['startFrame']<=at<b['endFrame']),None)
    if latest and (spoken is None or spoken['frame']<latest['startFrame']):
        primary=next((l for l in live if l.entityId==latest['primaryEntityId']),None)
        if primary:return primary.id
    return spoken['layerId'] if spoken else (live[0].id if live else None)


def stage(live,focus,reveal=False,side='left',final=False):
    top=Bounds(x=90,y=300,w=900,h=310)
    if not live:return Bounds(x=90,y=620,w=900,h=580),{}
    hero=next((l for l in live if l.id==focus),live[0])
    support=[l for l in live if l.id!=hero.id]
    if not support:
        if final:return Bounds(x=90,y=1360,w=900,h=250),{hero.id:Bounds(x=190,y=570,w=700,h=680)}
        if reveal:return top,{hero.id:Bounds(x=190,y=650,w=700,h=700)}
        if side=='left':
            return Bounds(x=640,y=640,w=350,h=550),{hero.id:Bounds(x=70,y=660,w=500,h=680)}
        return Bounds(x=90,y=640,w=350,h=550),{hero.id:Bounds(x=510,y=660,w=500,h=680)}
    if len(support)==1:
        # Stable screen slots; the narrated image expands while its counterpart
        # recedes, instead of swapping every image arbitrarily across the stage.
        left=live.index(hero)==0
        targets={hero.id:Bounds(x=75 if left else 505,y=620,w=500,h=700),
            support[0].id:Bounds(x=700 if left else 80,y=850,w=300,h=430)}
    else:
        targets={hero.id:Bounds(x=325,y=610,w=430,h=700),
            support[0].id:Bounds(x=55,y=870,w=240,h=390),
            support[1].id:Bounds(x=785,y=870,w=240,h=390)}
    return top,targets
