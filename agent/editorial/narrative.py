"""Versioned semantic intent, independent of asset identity and audio timing."""
from __future__ import annotations
import hashlib
import re
from typing import Literal, Optional
from pydantic import Field, model_validator
from agent.news_models import Model


class SemanticEvent(Model):
    kind: Literal['physical_action','context'] = 'physical_action'
    start_word: int = Field(ge=0)
    end_word: int = Field(gt=0)
    verb: str = Field(min_length=1,max_length=100)
    actor_ids: list[str] = Field(min_length=1,max_length=3)
    target_ids: list[str] = Field(default_factory=list,max_length=3)
    visual_goal: str = Field(min_length=1,max_length=1000)
    result_state: str = Field(default='',max_length=1000)
    priority: float = Field(default=.9,ge=0,le=1)
    motion_intent: Literal['none','uphill','downhill','reach','tighten','impact'] = 'none'
    contact_required: Optional[bool] = None
    anchor: Optional[str] = None


class NarrativeBeat(Model):
    id: str
    section_id: str
    text: str
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    start_word: int = Field(ge=0)
    end_word: int = Field(gt=0)
    kind: Literal['physical_action', 'context']
    verb: str = ''
    actor_ids: list[str] = Field(default_factory=list)
    target_ids: list[str] = Field(default_factory=list)
    identity_reference_ids: list[str] = Field(default_factory=list)
    visual_goal: str
    result_state: str = ''
    state_before: str = ''
    priority: float = Field(default=.5, ge=0, le=1)
    required_action_visible: bool = False
    motion_intent: Literal['none','uphill','downhill','reach','tighten','impact'] = 'none'
    contact_required: bool = True
    asset_ids: list[str] = Field(default_factory=list)
    decision: Literal['reuse_identity', 'reuse_action_variant', 'generate_interaction_cutout', 'degraded_no_identity', 'degraded_asset_budget']
    start_ms: Optional[float] = None
    end_ms: Optional[float] = None
    alignment_confidence: Optional[float] = None
    timing_provenance: Optional[str] = None
    degraded_reason: Optional[str] = None

    @model_validator(mode='after')
    def spans(self):
        if self.end_char <= self.start_char or self.end_word <= self.start_word:
            raise ValueError('Narrative spans must be nonempty')
        if self.kind == 'physical_action' and not self.required_action_visible:
            raise ValueError('Physical actions require visible action')
        return self


class IdentityPack(Model):
    entity_id: str
    name: str
    description: str
    kind: str
    identity: str


class NarrativeBeatPlan(Model):
    plan_version: Literal['narrative-v2'] = 'narrative-v2'
    script_sha256: str
    entities: list[IdentityPack]
    beats: list[NarrativeBeat]
    extraction: str = 'deterministic'

    def validate_script(self, script):
        if self.script_sha256 != hashlib.sha256(script.narration.encode()).hexdigest():
            raise ValueError('Narrative plan belongs to a different script')
        sections = {s.id: s for s in script.sentences}
        offsets = {}; cursor = 0
        for sentence in script.sentences:
            offsets[sentence.id] = cursor; cursor += len(sentence.text) + 1
        known = {e.entity_id for e in self.entities}
        seen = set()
        for beat in self.beats:
            if beat.id in seen or beat.section_id not in sections:
                raise ValueError('Duplicate beat or unknown section')
            seen.add(beat.id)
            sentence = sections[beat.section_id]
            tokens = list(re.finditer(r'\S+', sentence.text))
            if beat.end_word > len(tokens):
                raise ValueError('Narrative word span out of bounds')
            start = offsets[sentence.id] + tokens[beat.start_word].start()
            end = offsets[sentence.id] + tokens[beat.end_word-1].end()
            if (start, end) != (beat.start_char, beat.end_char) or script.narration[start:end] != beat.text:
                raise ValueError('Narrative span must match exact approved text')
            if not set(beat.identity_reference_ids + beat.actor_ids + beat.target_ids) <= known:
                raise ValueError('Unknown narrative identity')
        return self

    def bind_audio(self, words):
        """Use the same validated final word boundaries as captions and layers."""
        by_section = {}
        for word in words: by_section.setdefault(word.sectionId, []).append(word)
        for beat in self.beats:
            selected = by_section[beat.section_id][beat.start_word:beat.end_word]
            if len(selected) != beat.end_word-beat.start_word:
                raise ValueError('Missing aligned narrative words')
            beat.start_ms = selected[0].start * 1000
            beat.end_ms = selected[-1].end * 1000
            beat.alignment_confidence = min(w.confidence for w in selected)
            beat.timing_provenance = selected[0].provenance
        return self


    def validate_coverage(self, script):
        self.validate_script(script)
        for sentence in script.sentences:
            spans=sorted((b.start_word,b.end_word) for b in self.beats if b.section_id==sentence.id)
            cursor=0
            for start,end in spans:
                if start != cursor:
                    raise ValueError('Missing or duplicated narrative words: '+sentence.id)
                cursor=end
            if cursor != len(sentence.text.split()):
                raise ValueError('Incomplete narrative sentence: '+sentence.id)
        return self

    def assess_assets(self, assets, acquisition):
        """Coverage means a reviewed action, never merely a new filename."""
        records={r.get('entityId'):r for r in acquisition.get('assets',[])}
        available={a.entityId:a for a in assets}
        required=[b for b in self.beats if b.required_action_visible]
        passed=[];degraded=[];manual=[]
        for beat in required:
            candidates=[available[eid] for eid in beat.asset_ids if eid in available]
            if not candidates or any(a.source=='Project HER subject label' for a in candidates):
                beat.degraded_reason='Required action asset unavailable; see acquisition diagnostics'
                degraded.append(beat.id)
            elif all(self._review_passes(records.get(a.entityId,{}).get('generation',{}),beat) for a in candidates):
                passed.append(beat.id)
            else:
                manual.append(beat.id)
        return {'requiredActionBeats':len(required),'reviewedActionBeats':len(passed),
            'reviewedActionCoverage':len(passed)/len(required) if required else None,
            'degradedBeats':degraded,'manualReviewBeats':manual,
            'acceptancePassed':not degraded and not manual,
            'scope':'Asset review only; captions-off final video review still required'}

    @staticmethod
    def _review_passes(proof,beat):
        action=proof.get('actionReview',{})
        continuity=proof.get('continuityReview',{})
        return (action.get('actionVisible') is True and action.get('portraitOnly') is False
            and not action.get('problems',[]) and (not beat.contact_required or action.get('contactVisible') is True)
            and continuity.get('recognizable') is True and continuity.get('sameClothingOrFur') is True and not continuity.get('problems',[]))


def storyboard_narrative(script):
    """Bridge the default sentence planner to the shared exact-word contract.

    No generation requests. Multiple verbs remain separate traceable beats even
    when artwork is a single composite; that limitation is explicit downstream.
    """
    from .action_beats import action_events
    registry={e.id:e for e in [*script.identity_registry,*script.entities]}
    rows={b['sentence_id']:b for b in script.sentence_storyboard}
    beats=[];offset=0
    for sentence in script.sentences:
        tokens=list(re.finditer(r'\S+',sentence.text));row=rows[sentence.id]
        events=action_events(sentence.text)
        boundaries=sorted({0,len(tokens),*[e['start_word'] for e in events]})
        by_start={e['start_word']:e for e in events}
        for index,(start,end) in enumerate(zip(boundaries,boundaries[1:])):
            event=by_start.get(start);physical=event is not None
            refs=row.get('depicted_entity_ids',row.get('identity_reference_ids',[]))
            beats.append(NarrativeBeat(id=f'beat-{sentence.id}-{index}',section_id=sentence.id,
                text=sentence.text[tokens[start].start():tokens[end-1].end()],
                start_char=offset+tokens[start].start(),end_char=offset+tokens[end-1].end(),
                start_word=start,end_word=end,kind='physical_action' if physical else 'context',
                verb=event['verb'] if physical else '',
                actor_ids=[eid for eid in refs if registry[eid].kind in ('person','animal')],
                target_ids=[eid for eid in refs if registry[eid].kind not in ('person','animal')],identity_reference_ids=refs,
                visual_goal=row.get('visual_focus') or sentence.text,
                result_state=row.get('state_after',''),state_before=row.get('state_before',''),
                priority=.9 if physical else .5,required_action_visible=physical,
                contact_required=physical and event['verb'] in ('opening','entering','sealing','recovery','gathering','restoration'),
                asset_ids=[row['primary_entity_id']],decision='reuse_action_variant'))
        offset+=len(sentence.text)+1
    plan=NarrativeBeatPlan(script_sha256=hashlib.sha256(script.narration.encode()).hexdigest(),
        entities=[IdentityPack(entity_id=e.id,name=e.name,description=e.description,kind=e.kind,identity=e.identity) for e in registry.values()],
        beats=beats,extraction='sentence_storyboard_with_action_guard')
    return plan.validate_coverage(script)
