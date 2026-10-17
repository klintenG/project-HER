"""Separate reusable identities from event poses; never rewrite approved speech."""
import hashlib
import re
from .visuals import EditorialScript
from .narrative import NarrativeBeat, NarrativeBeatPlan, IdentityPack
from agent.news_models import Entity

# Conservative offline coverage. The live visual planner also supplies semantic
# events, including actions outside this vocabulary. No story names occur here.
ACTION_PATTERNS = (
    ('bite', r'\b(?:bite|bit|bitten|biting|bites)\b'),
    ('hand_contact', r'\b(?:his|her|their)\s+hand\b(?=.{0,65}\b(?:jaws?|mouth)\b)'),
    ('breaking', r'\b(?:break|broke|breaks|breaking|shatter|shattered|shattering)\b'),
    ('binding', r'\b(?:bind|bound|binding|tied|tie|tighten|tightened|tightening|chained)\b'),
    ('uphill_push', r'\b(?:push|pushed|pushes|pushing|roll|rolled|rolling)\b(?=.{0,100}\b(?:uphill|up (?:the|a) (?:hill|slope))\b)'),
    ('downhill_return', r'\b(?:roll|rolled|rolling|fall|fell|falling|tumble|tumbled|tumbling)\b(?=.{0,45}\b(?:back|downhill|down (?:the|a) (?:hill|slope))\b)'),
    ('physical_interaction', r'\b(?:lifted|lifting|carried|carrying|struck|striking|grabbed|grabbing|pulled|pulling|rescued|rescuing|embraced|embracing|opened|opening|destroyed|destroying|escaped|escaping)\b'),
)


def action_kind(text):
    events = action_events(text)
    return events[0]['verb'] if events else None


def action_events(text):
    tokens = list(re.finditer(r'\S+', text)); found = []
    for kind, pattern in ACTION_PATTERNS:
        for match in re.finditer(pattern, text, re.I):
            if re.search(r'(?:impossible to|cannot|could not|did not|never|not to|demanded that .{1,25}|asked that .{1,25})\s*$',text[max(0,match.start()-40):match.start()],re.I):continue
            index = next(i for i, token in enumerate(tokens) if token.end() > match.start())
            if any(e['start_word'] == index for e in found): continue
            found.append(dict(start_word=index, end_word=len(tokens), verb=kind))
    found.sort(key=lambda e: e['start_word'])
    found=[event for i,event in enumerate(found) if i==0 or event['verb']!=found[i-1]['verb']]
    # Distinct causal states in one sentence must survive as separate cues.
    for event, following in zip(found, found[1:]): event['end_word'] = following['start_word']
    return found


def _action_visible(entity, kind):
    if entity.kind not in ('person', 'animal'): return False
    description = entity.description.casefold()
    # A noun list or 'standing with a chain' cannot satisfy an action.
    if re.search(r'\bstanding\b|\bportrait\b', description): return False
    patterns = dict(ACTION_PATTERNS)
    return bool(re.search(patterns.get(kind, r'(?!)'), description, re.I))


def _event_clause_instruction(kind, text, actor, references, entities):
    names = [entities[eid].name for eid in references if eid in entities]
    actor_name = actor.name if actor else "the subject"
    other_names = ", ".join(n for n in names if not actor or n != actor.name) or "the other character"
    if kind == 'hand_contact':
        return f'Show {other_names if actor and actor.kind == "animal" else actor_name} placing an extended hand directly inside the open jaws/mouth of {actor_name if actor and actor.kind == "animal" else other_names} in one connected interaction cutout.'
    if kind == 'binding':
        return f'Show {actor_name} visibly restrained by the exact binding prop narrated in the context. Preserve its material and color from its reference; do not substitute chains, leather straps or a different restraint. Make the wrapping and physical attachment readable.'
    if kind == 'bite':
        return f'Show {actor_name} actively biting the exact narrated target: {text}. Show closed jaws/teeth making the narrated contact, visibly different from resting or approaching. Non-gory: conceal injury, with no blood or exposed severed anatomy.'
    if kind == 'breaking':
        return f'Show {actor_name} breaking the explicitly narrated object or restraint. Preserve the object material and color; do not invent chains when the narration refers to another restraint. Show the actual point of breakage and an active pose.'
    if kind == 'uphill_push':
        return f'Repose {actor_name} leaning forward at a steep angle with both hands pressed firmly against a massive heavy stone boulder, straining to push/roll the boulder UP.'
    if kind == 'downhill_return':
        return f'Show the boulder visibly rolling back downhill away from {actor_name}, who has released it. This must differ from the uphill pushing state: hands are no longer pushing, the boulder is below the figure with clear downhill direction.'
    return f'Show {actor_name} performing the physical action ({text}) with clear contact and body pose.'


def ensure_action_coverage(script, rows, audit, identities=None):
    entities = {e.id: e for e in script.entities}
    masters = list({e.id:e for e in [*(identities or []),*script.entities]}.values())
    entities={**{e.id:e for e in masters},**entities}
    sentences = []; decisions = []; beats = []; seen_action_variants = {}
    prior_actor = None; offset = 0
    persistent_states={}
    semantic = audit.pop('semanticEvents', {})
    for sentence, row in zip(script.sentences, rows):
        tokens = list(re.finditer(r'\S+', sentence.text))
        selected = [entities[eid] for eid in sentence.entity_ids]
        named = [e for e in masters if not e.id.startswith('action-') and re.search(r'(?<!\w)'+re.escape(e.name)+r'(?!\w)', sentence.text, re.I)]
        characters = [e for e in named if e.kind in ('person', 'animal')]
        # Also include section characters (e.g. via aliases like 'wolf' -> Fenrir)
        section_characters = list({e.id: e for e in [*characters, *(e for e in selected if not e.id.startswith('action-') and e.kind in ('person', 'animal'))]}.values())
        events = semantic.get(sentence.id) or action_events(sentence.text)
        guard_kinds={event['start_word']:event['verb'] for event in action_events(sentence.text)}
        grounded=[]
        for event in events:
            within=[kind for start,kind in guard_kinds.items() if event['start_word']<=start<event['end_word']]
            kind=guard_kinds.get(event['start_word'],within[0] if len(within)==1 else event['verb'])
            grounded.append({**event,'verb':kind})
        events=grounded
        # Validated semantic events can add verbs but cannot erase a known event.
        missing=[guard for guard in action_events(sentence.text) if not any(
            event['verb']==guard['verb'] and event['start_word']<=guard['start_word']<event['end_word']
            for event in events)]
        events = sorted([*events,*missing], key=lambda e:e['start_word'])
        new_ids = list(sentence.entity_ids); new_cues = list(row['cues'])
        if not events:
            # A restraint does not disappear merely because the next line is
            # exposition. Reuse its state asset until a release/break event.
            replacements={eid:persistent_states[eid]['asset_id'] for eid in new_ids if eid in persistent_states}
            new_ids=[replacements.get(eid,eid) for eid in new_ids]
            new_cues=[{**cue,'entityId':replacements.get(cue['entityId'],cue['entityId'])} for cue in new_cues]
            beats.append(NarrativeBeat(id='beat-'+sentence.id,section_id=sentence.id,text=sentence.text,
                start_char=offset,end_char=offset+len(sentence.text),start_word=0,end_word=len(tokens),
                kind='context',visual_goal=sentence.text,asset_ids=new_ids,decision='reuse_identity'))
        for index, event in enumerate(events):
            start = event['start_word']; end = min(event['end_word'], events[index+1]['start_word'] if index+1<len(events) else len(tokens))
            if not 0 <= start < end <= len(tokens): raise ValueError('Invalid action word span')
            text = sentence.text[tokens[start].start():tokens[end-1].end()]
            kind = event['verb']
            actor_ids = event.get('actor_ids') or []
            actor = next((entities[eid] for eid in actor_ids if eid in entities),None)
            # Pronoun subject before a newly named target refers to the prior
            # protagonist, rather than turning that target into the actor.
            if actor is None and re.match(r'^(?:he|she|it|they)\b',sentence.text,re.I): actor=prior_actor
            actor = actor or next(iter(characters), None) or prior_actor or next((e for e in selected if e.kind in ('person','animal')),None)
            prefix_text = sentence.text[:tokens[start].end()]
            prefix_chars = [e for e in section_characters if re.search(r'(?<!\w)'+re.escape(e.name)+r'(?!\w)', prefix_text, re.I)]
            clause_chars = [e for e in section_characters if re.search(r'(?<!\w)'+re.escape(e.name)+r'(?!\w)', text, re.I)]
            if kind == 'binding' and (prefix_chars or clause_chars):
                bound_subject = prefix_chars[-1] if prefix_chars else clause_chars[0]
                actor = bound_subject
                references = list(dict.fromkeys([*(event.get('actor_ids') or [bound_subject.id]), *event.get('target_ids',[])]))
            else:
                references = list(dict.fromkeys([*(event.get('actor_ids') or ([actor.id] if actor else [])),
                    *event.get('target_ids',[]), *(e.id for e in section_characters if not event.get('actor_ids'))]))
            props=[e.id for e in selected if e.kind=='object' and any(re.search(r'(?<!\w)'+re.escape(part)+r'(?!\w)',sentence.text,re.I) for part in e.name.split() if len(part)>3)]
            references=list(dict.fromkeys([*references,*props]))
            state_context='; '.join(persistent_states[eid]['description'] for eid in references if eid in persistent_states)
            decision='generate_interaction_cutout'; asset_id=None
            action_sig = ('|'.join(references), kind, event.get('result_state') or text)
            suitable=next((e for e in selected if _action_visible(e,kind)),None) or (seen_action_variants.get(action_sig) if kind != 'physical_interaction' else None)
            if suitable:
                decision='reuse_action_variant'; asset_id=suitable.id
            elif actor is None:
                decision='degraded_no_identity'
            elif len(entities)>=24:
                decision='degraded_asset_budget'
            else:
                key='action-'+hashlib.sha256(('|'.join(references)+'|'+kind+'|'+text).encode()).hexdigest()[:12]
                identities_str='; '.join(f'{entities[eid].name}: '+re.sub(r'\b(?:standing|portrait|neutral pose|front view)\b','',entities[eid].description,flags=re.I) for eid in references)
                visual_goal = event.get('visual_goal') or _event_clause_instruction(kind, text, actor, references, entities)
                result_state = event.get('result_state') or text
                # Local context is included for pronouns; the exact event is
                # singled out so a later climax does not leak into this pose.
                description=(f'Edit the reference character(s) to depict this exact physical action: {visual_goal} '
                    f'Action-specific editorial interaction cutout. Event state: {text}. Result state: {result_state}. '
                    f'Established physical state before this event: {state_context or "no additional state constraint"}. Preserve that state unless this event explicitly changes it. '
                    f'Identity references: {identities_str}. '
                    'Show physically legible contact, body pose and object direction. Preserve every referenced character, clothing and fur. '
                    'Include only the narrated interacting subjects and props in one connected cutout on a flat contrasting mid-gray background with generous empty margins around the entire figure; no captions or scenery.')
                entities[key]=Entity(id=key,name=actor.name,kind=actor.kind,identity=actor.identity,description=description)
                if kind != 'physical_interaction':
                    seen_action_variants[action_sig]=entities[key]
                asset_id=key
            if asset_id and kind=='binding' and actor:
                persistent_states[actor.id]={'asset_id':asset_id,'description':actor.name+' remains restrained. '+text+' Props: '+'; '.join(entities[eid].description for eid in props)}
            if kind=='breaking':
                for eid in references:persistent_states.pop(eid,None)
            if asset_id:
                # Remove duplicate standing participants, while keeping props
                # and contextual assets under their existing independent motion.
                covered=set(references)
                new_ids=[eid for eid in new_ids if eid not in covered]
                new_cues=[cue for cue in new_cues if cue['entityId'] not in covered and cue['entityId']!=asset_id]
                if asset_id not in new_ids: new_ids.insert(0,asset_id)
                new_cues.append({'entityId':asset_id,'anchor':tokens[start].group(),'startWord':start})
            visual_goal = event.get('visual_goal') or _event_clause_instruction(kind, text, actor, references, entities)
            beat=NarrativeBeat(id=f'beat-{sentence.id}-{index}',section_id=sentence.id,text=text,
                start_char=offset+tokens[start].start(),end_char=offset+tokens[end-1].end(),start_word=start,end_word=end,
                kind='physical_action',verb=kind,actor_ids=event.get('actor_ids') or ([actor.id] if actor else []),
                target_ids=event.get('target_ids') or [eid for eid in references if not actor or eid!=actor.id],
                identity_reference_ids=references,visual_goal=visual_goal,result_state=event.get('result_state',text),
                priority=event.get('priority',.95 if kind=='bite' else .9),required_action_visible=True,state_before=state_context,
                motion_intent=(event.get('motion_intent') if event.get('motion_intent') not in (None,'none') else {'uphill_push':'uphill','downhill_return':'downhill','hand_contact':'reach','binding':'tighten','bite':'impact'}.get(kind,'none')),
                contact_required=event['contact_required'] if event.get('contact_required') is not None else kind!='downhill_return' and event.get('motion_intent')!='downhill',
                asset_ids=[asset_id] if asset_id else [],decision=decision)
            beats.append(beat)
            decisions.append({'sectionId':sentence.id,'kind':kind,'decision':decision,'assetId':asset_id,'anchor':tokens[start].group()})
        row['cues']=sorted(new_cues,key=lambda cue:not cue['entityId'].startswith('action-'))
        sentences.append(sentence.model_copy(update={'entity_ids':new_ids[:12]}))
        if characters: prior_actor=characters[0]
        offset+=len(sentence.text)+1
    audit['actionBeats']=decisions
    plan=NarrativeBeatPlan(script_sha256=hashlib.sha256(script.narration.encode()).hexdigest(),
        entities=[IdentityPack(entity_id=e.id,name=e.name,description=e.description,kind=e.kind,identity=e.identity) for e in masters],beats=beats,
        extraction='semantic_with_deterministic_guard' if semantic else 'deterministic')
    used={eid for sentence in sentences for eid in sentence.entity_ids}
    planned=EditorialScript.model_validate({**script.model_dump(),'entities':[e.model_dump() for e in entities.values() if e.id in used],
        'sentences':[s.model_dump() for s in sentences],'narrative_plan':plan.model_dump()})
    plan.validate_script(planned)
    return planned,rows
