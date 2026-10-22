"""Reference-v2 phrase/event choreography on the existing absolute audio clock.

No generated facts, substitute assets, estimated timestamps, or render-time
randomness. The original director owns identity and subject lifetimes. This
compiler owns readable phrases, semantic layouts, and their visual handoffs.
"""
import re
from .models import Beat, Bounds, Event, Layer, Phrase, frames


def chunks(words, names):
    """Pause/clause boundaries with atomic proper names and readable holds."""
    from .planner import emphasis_key
    keys=[emphasis_key(w.text) for w in words]
    protected=set()
    for name in names:
        wanted=[emphasis_key(t) for t in name.split()]
        for i in range(len(keys)-len(wanted)+1):
            if keys[i:i+len(wanted)]==wanted:
                protected.update(range(i+1,i+len(wanted)))
    spans=[];begin=0
    for i,w in enumerate(words):
        boundary=i+1
        pause=boundary<len(words) and words[boundary].start-w.end>.18
        clause=bool(re.search(r'[,;:!?…]$',w.text))
        next_turn=boundary<len(words) and keys[boundary] in ('but','while','yet','then','because')
        if boundary not in protected and (boundary-begin>=5 or (boundary-begin>=2 and (pause or clause or next_turn))):
            spans.append(words[begin:boundary]);begin=boundary
    if begin<len(words):spans.append(words[begin:])
    # A short trailing connector belongs to the preceding idea. Never speed up
    # the voice or invent onsets to meet the preferred reading duration.
    out=[]
    for span in spans:
        if out and (len(span)<2 or span[-1].end-span[0].start<.65) and len(out[-1])+len(span)<=10:
            out[-1]+=span
        else:out.append(span)
    return out


def grammar(text, role, visuals, assets, first=False, last=False):
    t=text.casefold()
    if last or role=='close':return 'final-reveal'
    if re.search(r'\b\d{3,4}\b',t):return 'timeline-date'
    if first:return 'hero-object'
    if re.search(r'\b(but|yet|while|instead|rivalries|split|apart|unlike)\b',t):return 'split-outcome'
    if re.search(r'\b(pardon|scroll|document|treaty|letter|loan|seal)\b',t):return 'document-evidence'
    if re.search(r'\b(sent|fought|invaded|defeating|pressure|weaken|stop|crush|control)\w*\b',t):return 'cause-effect'
    if any(assets[v.assetId].role=='map' for v in visuals):
        return 'location-change' if re.search(r'\b(to|from|moved|reached)\b',t) else 'map-event'
    if len(visuals)>1:return 'comparison'
    if any(assets[v.assetId].role=='portrait' for v in visuals):return 'portrait-event'
    if re.search(r'\b(retire|walked|away|kept|took|passed)\w*\b',t):return 'asset-handoff'
    if not visuals:return 'typographic-breath'
    return 'incremental-claim'


def narrative_layout(beat):
    """Select geometry from the planned event, without another model request."""
    if not beat:
        return None
    text=' '.join(str(beat.get(k,'')) for k in ('main_action','state_before','state_after','visual_focus','location')).casefold()
    if re.search(r'\b(reflect|mirror|reveal(?:s|ed)? her image|reveal(?:s|ed)? his image)\b',text):
        return 'object-closeup'
    if re.search(r'\b(emerg|return(?:s|ed)? (?:of )?(?:the )?(?:sun|light)|sunlight|daylight|illuminat|relight|radiant)\w*\b',text):
        return 'dramatic-reveal'
    if re.search(r'\b(dark(?:ness|en)?|destruct|destroy|collaps|burn|flood|storm|transform)\w*\b',text):
        return 'environment-change'
    if re.search(r'\b(danc|laugh|plead|confront|pull|drag|fight|embrac|react|peek|listen|hear)\w*\b',text):
        return 'character-interaction'
    if beat.get('important_object') and not beat.get('identity_reference_ids'):
        return 'object-closeup'
    return 'event-hero'


def layout(kind, visuals, assets):
    """Each family reserves disjoint text, asset and optional name regions."""
    top=Bounds(x=90,y=300,w=900,h=310)
    lower=Bounds(x=90,y=1360,w=900,h=250)
    if not visuals:return Bounds(x=90,y=620,w=900,h=580),{}
    if kind in ('event-hero','environment-change','character-interaction','object-closeup','dramatic-reveal'):
        if kind=='dramatic-reveal':
            caption=Bounds(x=95,y=1390,w=890,h=220)
            primary=Bounds(x=150,y=480,w=780,h=820)
        elif kind=='object-closeup':
            caption=Bounds(x=95,y=1390,w=890,h=220)
            primary=Bounds(x=160,y=530,w=760,h=760)
        elif kind=='environment-change':
            caption=Bounds(x=95,y=270,w=890,h=230)
            primary=Bounds(x=150,y=570,w=780,h=760)
        elif kind=='character-interaction':
            caption=Bounds(x=95,y=300,w=890,h=220)
            primary=Bounds(x=95 if len(visuals)>1 else 150,y=590,w=560 if len(visuals)>1 else 780,h=740)
        else:
            caption=Bounds(x=95,y=280,w=890,h=230)
            primary=Bounds(x=150,y=570,w=780,h=760)
        if len(visuals)==2:
            primary=Bounds(x=95,y=590,w=560,h=680)
        elif len(visuals)==3:
            primary=Bounds(x=340,y=590,w=400,h=600)
        targets={visuals[0].id:primary}
        if len(visuals)>1:
            targets[visuals[1].id]=Bounds(x=710,y=790,w=275,h=400)
        if len(visuals)>2:
            targets[visuals[1].id]=Bounds(x=65,y=790,w=250,h=360)
            targets[visuals[2].id]=Bounds(x=765,y=790,w=250,h=360)
        return caption,targets
    if kind=='portrait-event' and len(visuals)==1:
        return Bounds(x=85,y=660,w=405,h=500),{visuals[0].id:Bounds(x=520,y=600,w=470,h=600)}
    if kind=='timeline-date' and len(visuals)<=2:
        return top,{v.id:Bounds(x=120+i*460 if len(visuals)>1 else 180,y=720,w=420 if len(visuals)>1 else 720,h=520 if len(visuals)>1 else 660) for i,v in enumerate(visuals)}
    if len(visuals)==1:
        v=visuals[0]
        if kind=='document-evidence':return top,{v.id:Bounds(x=140,y=660,w=800,h=640)}
        if kind=='final-reveal':return lower,{v.id:Bounds(x=160,y=520,w=760,h=760)}
        if kind=='asset-handoff':return lower,{v.id:Bounds(x=160,y=540,w=760,h=740)}
        if kind in ('map-event','location-change'):return top,{v.id:Bounds(x=110,y=640,w=860,h=660)}
        return top,{v.id:Bounds(x=160,y=600,w=760,h=720)}
    if len(visuals)==3:
        # Hierarchical composition: prominent hero cutout, two smaller flanked cutouts
        return top,{
            visuals[0].id: Bounds(x=340, y=600, w=400, h=520),
            visuals[1].id: Bounds(x=70,  y=720, w=300, h=420),
            visuals[2].id: Bounds(x=710, y=720, w=300, h=420),
        }
    if kind in ('map-event','location-change'):
        return top,{visuals[0].id:Bounds(x=100,y=720,w=400,h=480),visuals[1].id:Bounds(x=540,y=620,w=460,h=580)}
    return lower if kind=='split-outcome' else top,{visuals[0].id:Bounds(x=80,y=600 if kind=='split-outcome' else 640,w=460,h=580),visuals[1].id:Bounds(x=540,y=640 if kind=='split-outcome' else 700,w=460,h=540)}


def choreograph(m,script,settings):
    from .planner import phrase_layout, label_lines, emphasis_key
    m['editorialStyleVersion']='reference-v2'
    m['layers']=[l for l in m['layers'] if l.entityId]
    # Rebuild geometric choreography, preserving the director's exact asset
    # entrances, emphasis, exits and provenance. No additional provider calls.
    m['events']=[e for e in m['events'] if e.type!='reframe']
    visuals=[l for l in m['layers'] if l.assetId]
    assets={a.id:a for a in m['assets']}
    names=[e.name for e in script.entities]
    storyboards={b['sentence_id']:b for b in getattr(script,'sentence_storyboard',[])}
    rows=[]
    for sentence in script.sentences:
        sw=[w for w in m['words'] if w.sectionId==sentence.id]
        for span in chunks(sw,names):rows.append((sentence,span))
    if not rows:raise ValueError('Reference-v2 requires aligned spoken phrases')
    m['beats']=[];audit=[];positions={}
    for i,(sentence,span) in enumerate(rows):
        start=0 if i==0 else frames(span[0].start)
        end=frames(rows[i+1][1][0].start) if i+1<len(rows) else m['durationInFrames']
        if end<=start:raise ValueError('Aligned phrases quantize to an empty interval')
        visible=[v for v in visuals if v.startFrame<end and v.endFrame>start]
        # A phrase may straddle an entity replacement. Use each actually active
        # composition independently; never put four future subjects on screen.
        active=[v for v in visible if v.startFrame<=start<v.endFrame]
        reserved=active or ([min(visible,key=lambda v:v.startFrame)] if visible else [])
        text=' '.join(w.text for w in span)
        kind='final-reveal' if i==len(rows)-1 else narrative_layout(storyboards.get(sentence.id)) or grammar(text,sentence.role,reserved,assets,first=i==0)
        if kind=='portrait-event' and len(visible)>1:kind='incremental-claim'
        box,_=layout(kind,reserved,assets)
        ids=[w.id for w in span]
        size=140 if kind=='timeline-date' and len(span)<=2 else 106
        lines,px=phrase_layout(ids,m['words'],box.w,size,box.h)
        emph={emphasis_key(t) for t in sentence.emphasis}
        emphasized=[w.id for w in span if emphasis_key(w.text) in emph or re.search(r'\d',w.text)]
        layer=Layer(id=f'reference-phrase-{i}',role='phrase',startFrame=start,endFrame=end,bounds=box,z=30,
            phrase=Phrase(wordIds=ids,lines=lines,mode='word_accumulate',size=px,weight=600,emphasis=emphasized,
                          anticipationFrames=min(3,frames(span[0].start)) if i==0 and span[0].start<=.1 else 0))
        m['layers'].append(layer)
        # Asset layout responds at phrase and identity boundaries. Positions are
        # absolute targets; seek order cannot accumulate offsets or drift.
        boundaries=sorted({start,*[v.startFrame for v in visible if start<v.startFrame<end],*[v.endFrame for v in visible if start<v.endFrame<end]})
        for j,at in enumerate(boundaries):
            until=boundaries[j+1] if j+1<len(boundaries) else end
            live=[v for v in visuals if v.startFrame<=at<v.endFrame]
            _,targets=layout(kind,live,assets)
            # Side-by-side pressure and resistance have a visible spatial
            # consequence; these are symbolic relations, not battle footage.
            for v in live:
                target=targets[v.id]
                if kind=='cause-effect' and len(live)==2:
                    target=target.model_copy(update={'x':target.x+(30 if live.index(v)==0 else -30)})
                if v.id not in positions:
                    v.bounds=target;positions[v.id]=target
                elif positions[v.id]!=target:
                    stop=min(until,v.endFrame,at+18)
                    if stop>at:
                        m['events'].append(Event(id=f'reference-reframe-{i}-{j}-{v.id}',type='reframe',targetIds=[v.id],startFrame=at,endFrame=stop,boundsFrom=positions[v.id],boundsTo=target))
                    positions[v.id]=target
        m['beats'].append(Beat(id=f'reference-beat-{i}',startFrame=start,endFrame=end,template=kind,sectionIds=[sentence.id],layerIds=[layer.id,*[v.id for v in visible]],purpose=text))
        audit.append({'id':f'reference-beat-{i}','grammar':kind,'phrase':text,'wordIds':ids,'startFrame':start,'endFrame':end,
                      'textBounds':box.model_dump(),'timingProvenance':sorted({w.provenance for w in span}),
                      'revealErrorMs':round(abs(frames(span[0].start)/30-span[0].start)*1000,3),
                      'readabilityWarning':(end-start)/30<.7})
    # Names remain optional identification. Source type, licenses, reconstruction
    # notices and all original asset fields remain in the manifest/credits.
    from .director import should_render_label
    for label in [l for l in m['layers'] if l.parentId]:
        parent=next((v for v in visuals if v.id==label.parentId),None)
        if not parent:continue
        entity=next((e for e in m['entities'] if e.id==label.entityId),None)
        if not should_render_label(entity):
            m['layers']=[l for l in m['layers'] if l.id!=label.id]
            for beat in m['beats']:beat.layerIds=[lid for lid in beat.layerIds if lid!=label.id]
            continue
        min_width=min([parent.bounds.w,*[e.boundsTo.w for e in m['events'] if e.type=='reframe' and parent.id in e.targetIds]])
        label.phrase.label=label_lines(entity.name,min_width)
        label.bounds=Bounds(x=0,y=0,w=min_width,h=150)
    if not settings.enableEditorialText:
        text_ids={l.id for l in m['layers'] if l.role=='phrase'}
        m['layers']=[l for l in m['layers'] if l.id not in text_ids]
        for beat in m['beats']:beat.layerIds=[lid for lid in beat.layerIds if lid not in text_ids]
    estimated=[w.id for w in m['words'] if w.provenance=='estimated_phrase']
    if estimated:m['warnings'].append('Reference-v2 contains estimated alignment: exact word synchronization is unverified; review alignment or enable strict alignment.')
    if m['words'][0].start>.25:m['warnings'].append('Narration has a leading delay over 250 ms; opening typography follows audio rather than fabricated word timing.')
    m['diagnostics']['referenceStoryboard']={'version':2,'timeUnit':'absolute frames','fps':30,'beats':audit,
        'estimatedWordIds':estimated,'grammarCount':len({r['grammar'] for r in audit}),
        'warnings':['Review supplied illustrations for historical accuracy; choreography does not authenticate assets.']}
    from .choreography import choreograph_actions
    choreograph_actions(m,script,settings)
