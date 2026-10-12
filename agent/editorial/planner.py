"""Small semantic library; geometry and every onset are deterministic.

LLM suggestions may select templates, never geometry, code or arbitrary effects.
The same planner runs offline with no LLM using sentence roles/entity types.
"""
from __future__ import annotations
import hashlib
import logging
import math
import re
import unicodedata
from pathlib import Path
from PIL import ImageFont
from agent.news_layout import font_path,validate_glyphs
from agent.news_models import NewsError
from .models import *
from .templates import profile

TEMPLATES=('single_subject','comparison','person_context','object_location','document_photo','date_year','location_transfer','process','connector','conclusion')
logger=logging.getLogger(__name__)


def emphasis_key(word):
    """Match display punctuation/case without rewriting the spoken token.

    Internal apostrophes, hyphens, signs and suffixes remain significant, so
    matching cannot turn "can't" into "cant" or "-5" into "5".
    """
    return unicodedata.normalize('NFKC',word).translate(str.maketrans({'’':"'",'‘':"'",'“':'"','”':'"'})).casefold().strip('.,:;!?…\"\'()[]{}')


def spoken_emphasis(text,values):
    """Resolve individual words or contiguous phrases to original tokens.

    Return unresolved suggestions separately: script emphasis describes a
    rewritten headline in v1 and is not authoritative for spoken text.
    """
    tokens=text.split();keys=[emphasis_key(word) for word in tokens]
    selected=set();missing=[]
    for value in values:
        wanted=[emphasis_key(word) for word in value.split()] if isinstance(value,str) else []
        if not wanted or not all(wanted):missing.append(value);continue
        spans=[i for i in range(len(keys)-len(wanted)+1) if keys[i:i+len(wanted)]==wanted]
        if not spans:missing.append(value);continue
        for i in spans:selected.update(range(i,i+len(wanted)))
    return list(dict.fromkeys(tokens[i] for i in sorted(selected))),missing


def template_for(sentence,entities):
    text=sentence.text.lower()
    if sentence.role=='close':return 'conclusion'
    if re.search(r'\b(must|requirements?|assessments?|steps?)\b',text):return 'process'
    if re.search(r'\b(license|licensed)\b',text) and re.search(r'\b(but|yet)\b',text):return 'process'
    if any(e.kind=='building' for e in entities):return 'document_photo'
    if not entities:return 'connector'
    if len(entities)>=2:
        if any(e.kind=='place' for e in entities):return 'object_location'
        return 'comparison'
    if any(e.kind=='person' for e in entities):return 'person_context'
    return 'single_subject'


def semantic_plan(script,llm=None,diagnostics=None):
    entity={e.id:e for e in script.entities}
    baseline=[];repairs=[]
    for sentence in script.sentences:
        emphasis,missing=spoken_emphasis(sentence.text,sentence.emphasis)
        baseline.append({'sectionId':sentence.id,'template':template_for(sentence,[entity[i] for i in sentence.entity_ids]),'purpose':sentence.text,'setupWords':None,'emphasisWords':emphasis})
        if missing:repairs.append({'sectionId':sentence.id,'omittedEmphasis':missing})
    planning={'mode':'deterministic','attempts':0,'errors':[],'baselineRepairs':repairs,'warnings':[]}
    if diagnostics is not None:diagnostics['semanticPlan']=planning
    def deterministic(fallback=False):
        if fallback:
            planning['mode']='deterministic_fallback'
            planning['warnings'].append('Optional semantic layout suggestions failed validation twice; used deterministic reference_editorial layouts with the original aligned narration.')
        for repair in repairs:
            planning['warnings'].append(repair['sectionId']+': omitted headline emphasis absent from spoken narration: '+', '.join(repair['omittedEmphasis']))
        for warning in planning['warnings']:logger.warning(warning)
        return baseline
    if llm is None:return deterministic()
    errors=[]
    for attempt in range(2):
        planning['attempts']=attempt+1
        try:
            value=llm('Propose semantic layouts for this approved script, without changing facts. Return {beats:[{sectionId,template,purpose,setupWords,emphasisWords}]}, exactly one per sentence in order. setupWords is an integer number of initial spoken words to keep in the setup block (1 to 7, leaving at least one consequence word); use null for a one-word sentence. emphasisWords is a list of exact tokens from spokenWords, preserving punctuation. Select from each sentence text, never from its rewritten phrase or headline emphasis; use [] if no emphasis is needed. Templates: '+', '.join(TEMPLATES)+'. Geometry, words and timestamps are determined by code. Use comparisons for two actual entities, process for explicit requirements, document_photo for a source response, conclusion for uncertainty. Do not invent maps, dates, requirements or evidence. Avoid three identical successive layouts. Keep complete grammatical phrases; preserve attribution.',{'script':script.model_dump(),'spokenWords':{s.id:s.text.split() for s in script.sentences},'previousErrors':list(errors)})
            rows=value['beats']
            if not isinstance(rows,list) or len(rows)!=len(baseline) or any(not isinstance(r,dict) or set(r)!={'sectionId','template','purpose','setupWords','emphasisWords'} or r['sectionId']!=s.id or r['template'] not in TEMPLATES or not isinstance(r['purpose'],str) for r,s in zip(rows,script.sentences)):raise ValueError('Invalid semantic beat reference/template')
            for row,sentence in zip(rows,script.sentences):
                count=len(sentence.text.split())
                if not (count==1 and row['setupWords'] is None) and (type(row['setupWords']) is not int or not 1<=row['setupWords']<count or row['setupWords']>7):raise ValueError(sentence.id+': invalid spoken phrase split')
                if not isinstance(row['emphasisWords'],list):raise ValueError(sentence.id+': emphasisWords must be a list')
                emphasis,missing=spoken_emphasis(sentence.text,row['emphasisWords'])
                if missing:raise ValueError(sentence.id+': emphasis must refer to original spoken words; unresolved '+repr(missing))
                row['emphasisWords']=emphasis
            # Specialized templates need corresponding explicit facts/assets;
            # the default planner cannot infer a factual map or object action.
            for row,base in zip(rows,baseline):
                if row['template'] in ('date_year','location_transfer','object_location') and row['template']!=base['template']:row.update(base)
            planning['mode']='llm';planning['errors']=list(errors)
            return rows
        except (ValueError,KeyError,TypeError) as exc:
            errors.append(str(exc));planning['errors']=list(errors)
            logger.warning('Editorial semantic plan attempt %d rejected: %s',attempt+1,exc)
    return deterministic(fallback=True)


def phrase_layout(ids,words,width,size,height):
    """Measure full phrase once with bundled bold metrics, retaining line breaks."""
    lookup={w.id:w for w in words}
    for px in range(int(size),51,-2):
        font=ImageFont.truetype(str(font_path(700)),px)
        lines=[];current=[]
        for wid in ids:
            test=current+[wid];text=' '.join(lookup[i].text for i in test)
            if font.getlength(text)>width and current:lines.append(current);current=[wid]
            else:current=test
        if current:lines.append(current)
        if max(font.getlength(' '.join(lookup[i].text for i in line)) for line in lines)<=width and len(lines)*px*1.19<=height:
            return lines,px
    raise NewsError('Editorial phrase exceeds legible bounds; shorten sentence or split phrase: '+' '.join(lookup[i].text for i in ids))


def label_lines(text,width):
    font=ImageFont.truetype(str(font_path(600)),36);lines=[];line=''
    for word in text.split():
        test=(line+' '+word).strip()
        if font.getlength(test)>width and line:lines.append(line);line=word
        else:line=test
    if line:lines.append(line)
    if any(font.getlength(x)>width for x in lines) or len(lines)>3:raise NewsError('Entity label too long at 36px; supply a shorter canonical display name.')
    return '\n'.join(lines)


def build(script,words,sections,entities,assets,audio_path,output,generation_id,diagnostics=None,plan=None,subtitle_mode='editorial',visual_cues=None,direction=None,visual_settings=None):
    from .audio import samples
    from agent.news_audio import probe_duration
    duration=probe_duration(audio_path);total=math.ceil(duration*30)+18
    m=dict(schemaVersion='2.0',preset='reference_editorial',contentMode='news',durationInFrames=total,generationId=generation_id,
        script=script.narration,scriptHash=hashlib.sha256(script.narration.encode()).hexdigest(),
        fonts=Fonts(semibold=str(font_path().resolve()),bold=str(font_path(700).resolve()),version=digest(font_path())+digest(font_path(700))),
        audio=[Audio(path=str(Path(audio_path).resolve()),duration=duration,sha256=digest(audio_path))],words=words,sections=sections,entities=entities,assets=assets,
        layers=[],beats=[],events=[],transitions=[],subtitleMode=subtitle_mode,warnings=[a.fallback for a in assets if a.fallback],diagnostics=diagnostics or {})
    if direction is not None:
        from .director import compile_direction, VisualSettings
        compile_direction(m,script,direction,visual_settings or VisualSettings.configured())
        m['warnings'].extend(m['diagnostics'].get('alignmentWarnings',[])+m['diagnostics'].get('visualDirector',{}).get('warnings',[]))
        m['warnings']=list(dict.fromkeys(m['warnings']))
        timeline=Timeline(**m)
        Path(output).mkdir(parents=True,exist_ok=True)
        (Path(output)/'editorial_manifest.json').write_text(timeline.model_dump_json(indent=2))
        return timeline
    layers=m['layers'];events=m['events'];by_entity={a.entityId:a for a in assets};layer_registry={};entity_lookup={e.id:e for e in entities}
    plan=plan or semantic_plan(script)
    cue_lookup={row['sectionId']:{cue['entityId']:cue['anchor'] for cue in row['cues']} for row in (visual_cues or [])}
    def event(kind,ids,start,end,**params):
        events.append(Event(id=f'event-{len(events)}',type=kind,targetIds=ids,startFrame=start,endFrame=end,**params))
    def phrase(ids,start,end,bounds,mode='word_accumulate',size=64):
        lines,px=phrase_layout(ids,words,bounds.w,size,bounds.h)
        layer=Layer(id=f'phrase-{len(layers)}',role='phrase',startFrame=start,endFrame=end,bounds=bounds,z=30,
            phrase=Phrase(wordIds=ids,lines=lines,mode=mode,size=px,weight=700 if mode=='emphasis_reveal' else 600,emphasis=ids if mode=='emphasis_reveal' else []))
        layers.append(layer);return layer.id
    previous_ids=[];entity_layers={}
    for i,(sentence,section,p) in enumerate(zip(script.sentences,sections,plan)):
        selected=[by_entity[e] for e in sentence.entity_ids];template=p['template']
        if visual_cues and selected and template=='connector':
            template=template_for(sentence,[e for e in script.entities if e.id in sentence.entity_ids])
        if template in ('person_context','object_location'):selected.sort(key=lambda a:a.role in ('context','map'))
        start=0 if i==0 else max(0,frames(section.start)-4)
        end=max(start+1,frames(sections[i+1].start)+6) if i+1<len(sections) else total
        end=min(total,end)
        text_end=min(end,frames(sections[i+1].start)+1) if i+1<len(sections) else end
        sw=[w for w in words if w.sectionId==section.id];ids=[w.id for w in sw];beat_ids=[]
        # Multiple visual beats inside a section: accumulate setup, then reveal
        # the exact spoken consequence below. Editorial text is never a summary
        # pretending to have the timing of different spoken words.
        count=len(ids);split=min(6,max(2,count//2))
        if count<=5:split=count
        if template=='conclusion':split=max(1,count-3)
        if template=='process':
            split=next((j for j,w in enumerate(sw) if j>0 and w.text.casefold() in ('must','but')),split)
        if p.get('setupWords') is not None:split=p['setupWords']
        for text in [sentence.text]+[entity_lookup[e].name for e in sentence.entity_ids]:validate_glyphs(text)
        top_box,bottom_box,asset_boxes=profile(template,len(selected))
        top=phrase(ids[:split],start,text_end,top_box,size=62)
        beat_ids.append(top)
        if ids[split:]:
            bottom=phrase(ids[split:],start,text_end,bottom_box,mode='emphasis_reveal',size=94 if template in ('conclusion','document_photo') else 70)
            beat_ids.append(bottom)
        if template=='connector' and not visual_cues:selected=[]
        count=len(selected)
        for j,a in enumerate(selected):
            eid=a.entityId;lid=entity_layers.get(eid,'entity-'+eid)
            b=asset_boxes[j]
            if count==2 and template=='comparison':
                # Reframe a subject/object pair when the story moves to a
                # person/person comparison; persistent entities are not rebuilt.
                if any(a.role=='symbol' for a in selected):b=Bounds(x=145+j*420,y=735,w=350,h=350)
            old=layer_registry.get(lid)
            # Reuse compatible bounds. A one-person composition moving into a
            # three-subject row needs a smaller box; crossfade that reframe
            # instead of leaving an oversized old portrait over its neighbors.
            persists=old is not None and lid in previous_ids and (old.bounds.w,old.bounds.h)==(b.w,b.h)
            if persists:
                # A single keyed layer spans sections; absolute events move it.
                old.endFrame=end
                label=layer_registry.get(lid+'-label')
                if label:label.endFrame=end
                if (old.bounds.x,old.bounds.y)!=(b.x,b.y):
                    prior_dx=sum(ev.dx for ev in events if ev.type in ('transfer','context_change') and lid in ev.targetIds)
                    prior_dy=sum(ev.dy for ev in events if ev.type in ('transfer','context_change') and lid in ev.targetIds)
                    event('context_change',[lid],start,min(end,start+10),dx=b.x-old.bounds.x-prior_dx,dy=b.y-old.bounds.y-prior_dy)
            else:
                if old:lid+=f'-{i}'
                first_name=entity_lookup[eid].name.casefold().split()[0]
                onset=next((frames(w.start) for w in sw if re.sub(r'[^\w]','',w.text.casefold()).startswith(first_name)),start)
                anchor=cue_lookup.get(sentence.id,{}).get(eid)
                if anchor:
                    from .visuals import anchor_index
                    index=anchor_index(sentence.text,anchor)
                    if index is None:raise NewsError('Visual cue is absent from aligned narration: '+anchor)
                    onset=max(start,frames(sw[index].start)-2)
                else:onset=0 if i==0 and j==0 else min(end-13,max(start,onset))
                layer=Layer(id=lid,role='subject' if a.role=='portrait' else 'object',entityId=eid,assetId=a.id,startFrame=onset,endFrame=end,bounds=b,
                    mask='none',shadow=True,
                    opacity=.18 if template in ('person_context','object_location') and j>0 else 1,z=1 if template in ('person_context','object_location') and j>0 else 10)
                layers.append(layer);layer_registry[lid]=layer
                # Intro is present at frame zero; subsequent introductions settle.
                event('settle',[lid],onset,min(end,onset+12),scaleFrom=1.16,scaleTo=1,opacityFrom=1 if onset<6 else 0,dy=20)
                short_symbol={'Satellite network symbol':'Network symbol','Institution symbol':'Institution symbol','Person symbol':'Person symbol','Object symbol':'Object symbol','Document symbol':'Document symbol'}.get(a.subject,a.subject)
                # Stock alt text is descriptive provenance, not a second entity
                # name. A concise role label avoids duplicate/oversized labels.
                role_label=short_symbol if a.role=='symbol' else 'Stock photo' if a.role=='photo' else 'AI illustration' if a.source.startswith('replicate:') else 'Illustration'
                label_text=entity_lookup[eid].name if a.factual else entity_lookup[eid].name+'\n'+role_label
                if template in ('process','document_photo') and not a.factual:label_text=role_label
                label_text='\n'.join(label_lines(line,b.w+40) for line in label_text.split('\n'))
                label=Layer(id=lid+'-label',role='label',entityId=eid,parentId=lid,anchor='entity',startFrame=onset,endFrame=end,
                    bounds=Bounds(x=0,y=b.h+18,w=b.w,h=150),z=20,phrase=Phrase(wordIds=[],lines=[],mode='entity_label',size=36,label=label_text))
                layers.append(label);layer_registry[label.id]=label
            entity_layers[eid]=lid
            beat_ids.extend([lid,lid+'-label'])
        visual_ids=[x for x in beat_ids if x.startswith('entity-') and not x.endswith('-label')]
        emphasis_tokens={emphasis_key(token) for value in p.get('emphasisWords',[]) for token in value.split()}
        for layer in layers:
            if layer.id in beat_ids and layer.phrase and layer.phrase.mode=='word_accumulate':
                layer.phrase.emphasis=[w.id for w in sw if w.id in layer.phrase.wordIds and emphasis_key(w.text) in emphasis_tokens]
        if len(visual_ids)==2:
            # Focus tracks the second entity's actual name if present.
            name=entity_lookup[selected[1].entityId].name.casefold().split()[0]
            anchor=next((frames(w.start) for w in sw if name in w.text.casefold()),frames(sw[max(1,len(sw)//2)].start))
            anchor=max(start+12,anchor,*(layer_registry[lid].startFrame+12 for lid in visual_ids))
            if anchor+12<=end:event('focus_shift',[visual_ids[1],visual_ids[0]],anchor,anchor+12,scaleTo=1.12,secondaryScale=.90)
        if visual_cues and len(visual_ids)==3:
            for lid in visual_ids[1:]:
                anchor=layer_registry[lid].startFrame+12
                active=[other for other in visual_ids if other!=lid and layer_registry[other].startFrame<=anchor]
                if active and anchor+10<end:event('focus_shift',[lid]+active,anchor,anchor+10,scaleTo=1.08,secondaryScale=.96)
        # Reframe established conclusion subjects. A new subject instead uses
        # its name-timed settlement; it cannot move before that layer exists.
        persistent_visual_ids=[lid for lid in visual_ids if lid in previous_ids]
        if template=='conclusion' and persistent_visual_ids:
            event('transfer',persistent_visual_ids,start,min(end,start+12),dy=-55)
        # Additional beat records track internal emphasis without extra TTS clips.
        division=min(end-1,max(start+1,frames(sw[split].start))) if split<len(sw) else end
        m['beats'].append(Beat(id=f'{section.id}-setup',startFrame=start,endFrame=division,sectionIds=[section.id],template=template,layerIds=beat_ids,purpose=p['purpose']))
        if division<end:m['beats'].append(Beat(id=f'{section.id}-payoff',startFrame=division,endFrame=end,sectionIds=[section.id],template=template,layerIds=beat_ids,purpose='Reveal the spoken consequence; hold for reading.'))
        if i:
            persist=list(set(previous_ids)&set(visual_ids));leave=[lid for lid in previous_ids if lid not in persist]
            m['transitions'].append(Transition(startFrame=start,endFrame=min(end,start+10),kind='overlap',persist=persist,enter=[x for x in visual_ids if x not in persist],leave=leave))
        previous_ids=visual_ids
    # Exit only at a layer's actual end, never at every narrative boundary.
    # Attached labels inherit the parent's opacity and transform exactly once.
    for layer in layers:
        if not layer.parentId and layer.endFrame<total:
            event('fade',[layer.id],max(layer.startFrame,layer.endFrame-10),layer.endFrame,opacityFrom=1,opacityTo=0)
    timeline=Timeline(**m)
    Path(output).mkdir(parents=True,exist_ok=True)
    (Path(output)/'editorial_manifest.json').write_text(timeline.model_dump_json(indent=2))
    return timeline
