"""Deterministic semantic templates, measured text and audio-anchored storyboard."""
from __future__ import annotations
import math
import re
from pathlib import Path
from PIL import ImageFont
from agent.news_models import Rect, Text, Layer, Beat, Event, NewsError
import config


def font_path(weight=600):
    return config.FONTS_DIR/'news'/('Poppins-Bold.ttf' if weight==700 else 'Poppins-SemiBold.ttf')


def validate_glyphs(text,weight=600):
    # Avoid silently drawing tofu/system-font substitutions for unsupported scripts.
    from fontTools.ttLib import TTFont
    font=TTFont(str(font_path(weight)))
    cmap=font.getBestCmap(); font.close()
    missing=[c for c in text if not c.isspace() and ord(c) not in cmap]
    if missing:
        raise NewsError("News font lacks glyphs for this language. Install a licensed matching font pair in assets/fonts/news; missing characters: "+''.join(dict.fromkeys(missing))[:20])


def measure_text(text,rect,width,height,start_size=76,weight=600,min_size=34):
    validate_glyphs(text,weight)
    # Width-normalized type, capped on wide formats to keep a deliberate landscape hierarchy.
    scale=min(width/1080,height/1080)
    for size in range(start_size,min_size-1,-2):
        px=max(1,round(size*scale))
        font=ImageFont.truetype(str(font_path(700)),px)
        lines=[]; line=''
        for word in text.split():
            candidate=(line+' '+word).strip()
            if font.getlength(candidate)>rect.w*width and line:
                lines.append(line); line=word
            else:
                line=candidate
        if line: lines.append(line)
        if lines and max(font.getlength(l) for l in lines)<=rect.w*width and (len(lines)*1.12+.2)*px<=rect.h*height:
            # Store size in 1080 width units; renderers use width/1080.
            return lines,px*1080/width
    raise NewsError("Display phrase does not fit legibly; shorten/reflow the phrase or split the beat.")


def template_for(entities):
    if not entities: return "text_bridge"
    if len(entities)==1: return "single_subject"
    if len(entities)==3: return "person_two_objects"
    if any(e.exact_asset for e in entities): return "subject_context"
    if any(e.kind in ('building','place') for e in entities): return "place_object_stack"
    return "two_subjects"


def geometry(template,count,wide=False):
    # Boxes include generous motion/shadow room and have no accidental overlap.
    head=Rect(x=.11,y=.22,w=.78,h=.12)
    if template=='text_bridge':
        return Rect(x=.13,y=.38,w=.74,h=.25),[],[]
    if template=='single_subject':
        boxes=[(.20,.38,.60,.35)]
    elif template=='two_subjects':
        boxes=[(.11,.39,.36,.34),(.53,.39,.36,.34)]
    elif template=='person_two_objects':
        boxes=[(.35,.35,.30,.185),(.13,.63,.32,.125),(.55,.63,.32,.125)]
    elif template=='place_object_stack':
        boxes=[(.22,.36,.56,.18),(.33,.64,.34,.12)]
    elif template=='subject_context':
        boxes=[(.34,.38,.32,.35),(.20,.41,.60,.28)]
    else:
        raise NewsError("Unknown News layout template")
    labels=[]
    for x,y,w,h in boxes:
        labels.append(Rect(x=x,y=y+h+.012,w=w,h=.065))
    return head,[Rect(x=x,y=y,w=w,h=h) for x,y,w,h in boxes[:count]],labels[:count]


def word_frame(audio,sentence_id,anchor,default,fps):
    anchor_words=re.findall(r'\w+',anchor.casefold())
    words=[w for w in audio.words if w.sentence_id==sentence_id]
    normalized=[re.sub(r'\W+','',w.text.casefold()) for w in words]
    for i in range(len(words)):
        if anchor_words and normalized[i:i+len(anchor_words)]==anchor_words:
            return round(words[i].start*fps)
    return default


def storyboard(script,audio,assets,width,height,fps,plan=None):
    from agent.news_storyboard import plan_storyboard
    import hashlib
    plan=plan or plan_storyboard(script,width,height)
    if plan.script_hash != hashlib.sha256(script.model_dump_json().encode()).hexdigest() or (plan.width,plan.height)!=(width,height):
        raise NewsError("Stale semantic storyboard plan")
    entity={e.id:e for e in script.entities}
    asset={a.entity_id:a for a in assets}
    beats=[]; events=[]
    duration=math.ceil(audio.duration*fps)
    for i,s in enumerate(script.sentences):
        phrase=next(p for p in audio.phrases if p.sentence_id==s.id)
        start=0 if i==0 else round(phrase.start*fps)
        end=round(audio.phrases[i+1].start*fps) if i+1<len(audio.phrases) else duration
        planned=plan.beats[i]
        entities=[entity[layer.entity_id] for layer in planned.subjects]
        template=planned.template
        headline=planned.text.rect
        lines,size=planned.text.lines,planned.text.size
        # Native word anchors where available; otherwise the entire phrase reveals at its real audio clip start.
        native=[w for w in audio.words if w.sentence_id==s.id]
        phrase_words=[re.sub(r'\W+','',w.casefold()) for w in s.phrase.split()]
        spoken_words=[re.sub(r'\W+','',w.text.casefold()) for w in native]
        match=next((j for j in range(len(spoken_words)) if spoken_words[j:j+len(phrase_words)]==phrase_words),None)
        anchors=[min(end-1,max(start,round(native[match+j].start*fps))) for j in range(len(phrase_words))] if match is not None else [start]*len(phrase_words)
        texts=[Text(id=f'text-{s.id}',text=s.phrase,lines=lines,rect=headline,size=size,weight=600,reveal_frames=anchors,emphasis=s.emphasis)]
        layers=[]
        for j,(e,subject_plan) in enumerate(zip(entities,planned.subjects)):
            box=subject_plan.rect
            if e.id not in asset: raise NewsError(f"Essential subject cutout missing: {e.name}")
            reveal=min(end-1,max(start,word_frame(audio,s.id,e.name,start,fps)))
            persist=subject_plan.persist
            layers.append(Layer(id=f'entity-{e.id}',asset_id=asset[e.id].id,entity_id=e.id,rect=box,z=subject_plan.layer_order,reveal=reveal,exit=end,persist=persist,portrait_fade=subject_plan.portrait_fade,overlap=subject_plan.overlap,opacity=subject_plan.opacity))
            # Labels are real compositor text, never baked into an AI asset.
            if subject_plan.label is None:
                events.append(Event(kind='persist' if persist else 'reveal',frame=reveal,target=f'entity-{e.id}'))
                continue
            label_lines,label_size=subject_plan.label.lines,subject_plan.label.size
            label=subject_plan.label.rect
            texts.append(Text(id=f'label-{s.id}-{e.id}',text=e.name,lines=label_lines,rect=label,size=label_size,weight=600,reveal_frames=[reveal]*len(e.name.split())))
            events.append(Event(kind='persist' if persist else 'reveal',frame=reveal,target=f'entity-{e.id}'))
            events.append(Event(kind='emphasize',frame=min(end-1,reveal+10),target=f'entity-{e.id}'))
        beats.append(Beat(id=f'beat-{i}',start=start,end=end,sentence_ids=[s.id],template=template,texts=texts,layers=layers))
    return beats,events
