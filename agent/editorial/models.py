"""The v2 contract. JSON Schema exported from these models also validates in Remotion.

All frame intervals are absolute and half-open [startFrame, endFrame).
Seconds are converted once from the master audio clock, never accumulated as frames.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Interval(Model):
    startFrame: int = Field(ge=0)
    endFrame: int = Field(gt=0)


class Word(Model):
    id: str
    sectionId: str
    text: str
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    provenance: Literal['provider', 'whisper_forced', 'whisper_transcribed', 'estimated_phrase']
    confidence: float = Field(ge=0, le=1)


class Section(Model):
    id: str
    text: str
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    wordIds: list[str]
    sourceIds: list[str] = Field(default_factory=list)


class Audio(Model):
    path: str
    offsetFrames: int = Field(default=0, ge=0)
    duration: float = Field(gt=0)
    kind: Literal['master', 'music', 'effect'] = 'master'
    gain: float = Field(default=1, ge=0, le=1)
    sha256: str


class Asset(Model):
    id: str
    entityId: str
    path: str
    originalPath: str
    role: Literal['portrait', 'object', 'context', 'photo', 'document', 'map', 'symbol']
    subject: str
    source: str
    license: str
    attribution: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    alpha: bool
    factual: bool
    confidence: float = Field(ge=0, le=1)
    preparation: Literal['trimmed_alpha', 'rectangle', 'vetted_geometry', 'symbolic']
    focalPoint: list[float] = Field(default_factory=lambda: [.5, .5], min_length=2, max_length=2)
    fallback: Optional[str] = None
    sha256: str


class Entity(Model):
    id: str
    name: str
    identity: Literal['real', 'generic', 'fictional']
    assetIds: list[str]
    source: str


class Bounds(Model):
    x: float = Field(ge=0, le=1080)
    y: float = Field(ge=0, le=1920)
    w: float = Field(gt=0, le=1080)
    h: float = Field(gt=0, le=1920)


class Phrase(Model):
    wordIds: list[str]
    lines: list[list[str]]
    emphasis: list[str] = Field(default_factory=list)
    mode: Literal['word_accumulate', 'phrase_reveal', 'emphasis_reveal', 'connector', 'entity_label']
    size: float = Field(ge=32, le=180)
    weight: Literal[600, 700] = 600
    align: Literal['left', 'center', 'right'] = 'center'
    # Static labels are distinguished from spoken words and subtitles.
    label: Optional[str] = None
    anticipationFrames: int = Field(default=0, ge=0, le=3)
    animation: Literal['word_slide', 'group_slide', 'line_reveal'] = 'word_slide'


class MotionElement(Model):
    """One separately animated piece of a layer's cutout (positions are fractions of the fitted image)."""
    assetId: str
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)
    depth: float = Field(default=.5, ge=0, le=1)
    delayFrames: int = Field(default=0, ge=0, le=60)


class LayerMotion(Model):
    """Bounded, deterministic editorial motion for one story cutout; no arbitrary CSS."""
    entrance: Literal['rise', 'slide_left', 'slide_right', 'pop', 'punch', 'slam', 'fade'] = 'rise'
    exit: Literal['fade', 'shrink', 'none'] = 'fade'
    entranceFrames: int = Field(default=14, ge=1, le=40)
    driftX: float = Field(default=0, ge=-160, le=160)
    driftY: float = Field(default=0, ge=-160, le=160)
    scaleTo: float = Field(default=1, ge=.85, le=1.25)
    tilt: float = Field(default=0, ge=-12, le=12)
    parallaxDepth: float = Field(default=.5, ge=0, le=1)
    initialOpacity: float = Field(default=0, ge=0, le=1)
    exitFrames: int = Field(default=6, ge=0, le=30)
    focusFrame: Optional[int] = Field(default=None, ge=0)
    focusScale: float = Field(default=1, ge=1, le=1.08)
    entranceTravel: float = Field(default=240, ge=0, le=240)
    elements: list[MotionElement] = Field(default_factory=list, max_length=4)


class Layer(Interval):
    id: str
    role: Literal['subject', 'object', 'map', 'photo', 'heading', 'phrase', 'label', 'shadow', 'document', 'year', 'box']
    entityId: Optional[str] = None
    assetId: Optional[str] = None
    parentId: Optional[str] = None
    bounds: Bounds
    anchor: Literal['screen', 'entity'] = 'screen'
    origin: str = Field(default='50% 70%', pattern=r'^\d+% \d+%$')
    z: int = Field(default=10, ge=0, le=50)
    opacity: float = Field(default=1, ge=0, le=1)
    mask: Literal['none', 'lower_fade'] = 'none'
    shadow: bool = False
    motion: Optional[LayerMotion] = None
    phrase: Optional[Phrase] = None
    value: Optional[int] = None


class Event(Interval):
    id: str
    type: Literal['focus_shift', 'settle', 'context_change', 'transfer', 'map_separate', 'year_counter', 'object_action', 'representation_swap', 'emphasis', 'fade', 'reframe']
    targetIds: list[str] = Field(min_length=1)
    easing: Literal['linear', 'easeOutCubic'] = 'easeOutCubic'
    # Explicit bounded parameters; no arbitrary CSS, JavaScript or catalog names.
    dx: float = Field(default=0, ge=-1080, le=1080)
    dy: float = Field(default=0, ge=-1920, le=1920)
    scaleFrom: float = Field(default=1, ge=.2, le=2)
    scaleTo: float = Field(default=1, ge=.2, le=2)
    secondaryScale: float = Field(default=.78, ge=.3, le=1)
    opacityFrom: float = Field(default=1, ge=0, le=1)
    opacityTo: float = Field(default=1, ge=0, le=1)
    fromValue: int = 0
    toValue: int = 0
    assetId: Optional[str] = None
    angleFrom: float = Field(default=-105, ge=-150, le=0)
    angleTo: float = Field(default=0, ge=-150, le=0)
    boundsFrom: Optional[Bounds] = None
    boundsTo: Optional[Bounds] = None


Template = Literal['single_subject', 'comparison', 'person_context', 'object_location', 'document_photo', 'date_year', 'location_transfer', 'process', 'connector', 'conclusion', 'hero-object', 'incremental-claim', 'portrait-event', 'map-event', 'timeline-date', 'document-evidence', 'asset-handoff', 'location-change', 'cause-effect', 'split-outcome', 'typographic-breath', 'final-reveal', 'event-hero', 'environment-change', 'character-interaction', 'object-closeup', 'dramatic-reveal', 'hero-intro', 'dual-tension', 'action-focus', 'event-montage', 'twist-composition', 'reaction-beat']


class Transition(Interval):
    kind: Literal['overlap', 'reframe', 'settle', 'swap', 'object']
    persist: list[str] = Field(default_factory=list)
    enter: list[str] = Field(default_factory=list)
    leave: list[str] = Field(default_factory=list)


class Beat(Interval):
    id: str
    template: Template
    sectionIds: list[str]
    layerIds: list[str]
    purpose: str


class Fonts(Model):
    semibold: str
    bold: str
    version: str


class Timeline(Model):
    schemaVersion: Literal['2.0'] = '2.0'
    preset: Literal['reference_editorial'] = 'reference_editorial'
    contentMode: str = 'news'
    width: Literal[1080] = 1080
    height: Literal[1920] = 1920
    fps: Literal[30] = 30
    durationInFrames: int = Field(gt=0)
    generationId: str = Field(pattern=r'^[A-Za-z0-9_-]+$')
    script: str
    scriptHash: str
    fonts: Fonts
    audio: list[Audio]
    words: list[Word]
    sections: list[Section]
    entities: list[Entity]
    assets: list[Asset]
    layers: list[Layer]
    beats: list[Beat]
    events: list[Event]
    transitions: list[Transition]
    subtitleMode: Literal['editorial', 'complete'] = 'editorial'
    narrationDriven: bool = False
    editorialStyleVersion: Literal['legacy', 'reference-v2'] = 'legacy'
    warnings: list[str] = Field(default_factory=list)
    diagnostics: dict = Field(default_factory=dict)

    @model_validator(mode='after')
    def coherent(self):
        def fail(message): raise ValueError(message)
        registries = {}
        for key in ('words', 'sections', 'entities', 'assets', 'layers', 'beats', 'events'):
            rows=getattr(self,key); registry={r.id:r for r in rows}
            if len(rows)!=len(registry): fail('Duplicate '+key+' IDs')
            registries[key]=registry
        w,s,e,a,l=(registries[k] for k in ('words','sections','entities','assets','layers'))
        if self.scriptHash != hashlib.sha256(self.script.encode()).hexdigest(): fail('Stale script hash')
        if self.script != ' '.join(sec.text for sec in self.sections): fail('Script/sections mismatch')
        if len([x for x in self.audio if x.kind=='master'])!=1: fail('Exactly one master audio required')
        master=next(x for x in self.audio if x.kind=='master')
        if master.offsetFrames!=0: fail('Master audio must start at frame zero')
        for track in self.audio:
            if track.duration*30+track.offsetFrames>self.durationInFrames+.01: fail('Audio truncated')
        previous=0
        for word in self.words:
            if word.sectionId not in s or word.start<previous-.001 or word.end<=word.start or word.end>master.duration+.01: fail('Invalid word alignment')
            previous=word.end
        for sec in self.sections:
            if sec.end<=sec.start or sec.end>master.duration+.01 or not sec.wordIds: fail('Invalid section interval')
            if any(i not in w or w[i].sectionId!=sec.id for i in sec.wordIds): fail('Unresolved section word')
            if ''.join(w[i].text for i in sec.wordIds).replace(' ','')!=sec.text.replace(' ',''): fail('Display words must preserve script')
            if any(w[i].start<sec.start-.001 or w[i].end>sec.end+.001 for i in sec.wordIds): fail('Words outside section')
        if [i for sec in self.sections for i in sec.wordIds] != [word.id for word in self.words]:fail('Incomplete or reordered word coverage')
        for entity in self.entities:
            if any(i not in a or a[i].entityId!=entity.id for i in entity.assetIds): fail('Unresolved entity asset')
        for asset in self.assets:
            if asset.entityId not in e: fail('Unresolved asset entity')
            if not asset.factual and not asset.fallback: fail('Symbolic assets must disclose fallback')
        for row in [*self.layers,*self.events,*self.beats,*self.transitions]:
            if not 0<=row.startFrame<row.endFrame<=self.durationInFrames: fail('Invalid frame interval')
        for layer in self.layers:
            if layer.entityId and layer.entityId not in e: fail('Unresolved layer entity')
            if layer.assetId and (layer.assetId not in a or a[layer.assetId].entityId!=layer.entityId): fail('Unresolved layer asset')
            if layer.motion:
                if layer.motion.focusFrame is not None and not layer.startFrame<=layer.motion.focusFrame<layer.endFrame:
                    fail('Motion focus outside layer interval')
                for element in layer.motion.elements:
                    if element.assetId not in a or a[element.assetId].entityId!=layer.entityId or not a[element.assetId].alpha:
                        fail('Unresolved alpha motion element')
                    if element.x+element.w>1.000001 or element.y+element.h>1.000001:
                        fail('Motion element outside fitted image')
            if layer.role in ('subject','object','map','photo','document','shadow') and not layer.assetId:fail('Visual layer requires an asset')
            if layer.role in ('heading','phrase','label') and not layer.phrase:fail('Text layer requires a phrase')
            if layer.role=='year' and layer.value is None:fail('Year layer requires a value')
            if layer.parentId and (layer.parentId not in l or l[layer.parentId].parentId or layer.parentId==layer.id): fail('Invalid parent')
            if (layer.anchor=='entity') != bool(layer.parentId): fail('Entity anchors need a parent')
            if layer.parentId and not (l[layer.parentId].startFrame<=layer.startFrame<layer.endFrame<=l[layer.parentId].endFrame): fail('Detached label interval')
            b=layer.bounds
            if b.x+b.w>1080 or b.y+b.h>1920: fail('Layer out of bounds')
            if layer.phrase:
                p=layer.phrase
                if any(i not in w for i in p.wordIds) or not set(p.emphasis)<=set(p.wordIds): fail('Unresolved phrase word/emphasis')
                if [i for line in p.lines for i in line]!=p.wordIds: fail('Phrase line breaks do not match words')
                if not p.wordIds and not p.label: fail('Empty phrase')
                if p.wordIds and p.label: fail('Labels and aligned phrases are distinct')
                if any(w[i].start*30>=layer.endFrame for i in p.wordIds): fail('Text exits before reveal')
        for beat in self.beats:
            if not set(beat.sectionIds)<=s.keys() or not set(beat.layerIds)<=l.keys(): fail('Unresolved beat reference')
        for event in self.events:
            if not set(event.targetIds)<=l.keys(): fail('Unresolved event target')
            if any(not(l[i].startFrame<=event.startFrame<event.endFrame<=l[i].endFrame) for i in event.targetIds): fail('Event outside target interval')
            if event.type in ('focus_shift','map_separate') and len(event.targetIds)<2: fail('Action requires two targets')
            if event.type=='year_counter' and any(l[i].role!='year' for i in event.targetIds): fail('Counter needs year layer')
            if event.type=='object_action' and any(l[i].role!='box' for i in event.targetIds): fail('Lid action needs box layer')
            if event.type=='map_separate' and any(not l[i].assetId or a[l[i].assetId].preparation!='vetted_geometry' for i in event.targetIds): fail('Map action requires vetted geometry')
            if event.type=='representation_swap' and (event.assetId not in a or any(a[event.assetId].entityId!=l[i].entityId for i in event.targetIds)): fail('Swap must preserve identity')
            if event.type=='reframe':
                if len(event.targetIds)!=1 or not event.boundsFrom or not event.boundsTo:fail('Reframe requires one target and explicit bounds')
                for bounds in (event.boundsFrom,event.boundsTo):
                    if bounds.x+bounds.w>1080 or bounds.y+bounds.h>1920:fail('Reframe outside canvas')
        for t in self.transitions:
            if not set(t.persist+t.enter+t.leave)<=l.keys(): fail('Unresolved transition layer')
        if not self.beats or self.beats[0].startFrame!=0 or max(b.endFrame for b in self.beats)!=self.durationInFrames: fail('Incomplete visual coverage')
        for b,c in zip(self.beats,self.beats[1:]):
            if c.startFrame>b.endFrame: fail('Background-only beat gap')
        if self.narrationDriven:
            for b,c in zip(self.beats,self.beats[1:]):
                if b.endFrame!=c.startFrame:fail('Atomic beats must partition the timeline')
            visuals=[layer for layer in self.layers if layer.assetId]
            for frame in sorted({v.startFrame for v in visuals}):
                active=[v for v in visuals if v.startFrame<=frame<v.endFrame]
                if len(active)>3 or len({v.entityId for v in active})!=len(active):fail('Conflicting atomic entity layers')
            for layer in visuals:
                transforms=sorted([event for event in self.events if layer.id in event.targetIds and event.type in ('settle','emphasis','focus_shift')],key=lambda event:event.startFrame)
                if any(a.endFrame>b.startFrame for a,b in zip(transforms,transforms[1:])):fail('Conflicting atomic scale transitions')
            ordered=sorted(self.transitions,key=lambda transition:transition.startFrame)
            if any(a.endFrame>b.startFrame for a,b in zip(ordered,ordered[1:])):fail('Overlapping atomic composition transitions')
        return self


def frames(seconds):
    return math.floor(seconds*30+.5)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def export_schema(path):
    Path(path).write_text(json.dumps(Timeline.model_json_schema(),indent=2)+'\n')
