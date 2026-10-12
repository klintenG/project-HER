"""Validated semantic plan built before any paid image or speech requests."""
from __future__ import annotations
import hashlib
import re
from typing import Optional
from agent.news_models import Model,Rect,Template

class TextPlan(Model):
    text: str
    lines: list[str]
    size: float
    rect: Rect
    narration_anchor: str

class SubjectPlan(Model):
    entity_id: str
    asset_id: str
    description: str
    visual_role: str
    rect: Rect
    label: Optional[TextPlan]
    layer_order: int
    reveal_anchor: str
    exit_anchor: str
    persist: bool
    overlap: str
    opacity: float
    portrait_fade: bool

class BeatPlan(Model):
    id: str
    sentence_ids: list[str]
    action_description: str
    template: Template
    text: TextPlan
    subjects: list[SubjectPlan]

class StoryboardPlan(Model):
    schema_version: str = '1.0'
    script_hash: str
    width: int
    height: int
    beats: list[BeatPlan]


def plan_storyboard(script,width,height):
    from agent.news_layout import template_for,geometry,measure_text
    entities={e.id:e for e in script.entities}
    beats=[]
    for i,s in enumerate(script.sentences):
        subjects=[entities[e] for e in s.entity_ids]
        if len(subjects)==3: subjects.sort(key=lambda e:e.kind!='person')
        template=template_for(subjects)
        if template=='subject_context': subjects.sort(key=lambda e:bool(e.exact_asset))
        headline,boxes,labels=geometry(template,len(subjects),width>height)
        lines,size=measure_text(s.phrase,headline,width,height)
        layers=[]
        for j,(e,box,label_box) in enumerate(zip(subjects,boxes,labels)):
            context=bool(template=='subject_context' and e.exact_asset)
            label=None
            if not context:
                label_lines,label_size=measure_text(e.name,label_box,width,height,40,min_size=28)
                label=TextPlan(text=e.name,lines=label_lines,size=label_size,rect=label_box,narration_anchor=e.name)
            portrait=e.is_portrait
            layers.append(SubjectPlan(entity_id=e.id,asset_id=f'asset-{e.id}',description=e.description,visual_role=e.kind,rect=box,label=label,layer_order=0 if context else j+1,reveal_anchor=e.name,exit_anchor=s.id+':end',persist=bool(i and e.id in script.sentences[i-1].entity_ids),overlap='context' if context else 'none',opacity=.18 if context else 1,portrait_fade=portrait))
        # All non-context boxes, including labels, are checked before asset generation.
        rectangles=[headline]+[layer.rect for layer in layers if layer.overlap=='none']+[layer.label.rect for layer in layers if layer.label]
        for j,a in enumerate(rectangles):
            for b in rectangles[j+1:]:
                if min(a.x+a.w,b.x+b.w)-max(a.x,b.x)>.001 and min(a.y+a.h,b.y+b.h)-max(a.y,b.y)>.001:
                    raise ValueError('Semantic storyboard contains a foreground collision')
        beats.append(BeatPlan(id=f'beat-{i}',sentence_ids=[s.id],action_description=s.text,template=template,text=TextPlan(text=s.phrase,lines=lines,size=size,rect=headline,narration_anchor=s.phrase),subjects=layers))
    return StoryboardPlan(script_hash=hashlib.sha256(script.model_dump_json().encode()).hexdigest(),width=width,height=height,beats=beats)
