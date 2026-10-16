"""Action coverage for the approved script, before any paid image requests.

The rules detect physical relationships, not story names. A generated interaction
is one cutout, so contact and occlusion survive the existing layer compositor.
"""
import hashlib
import re
from .visuals import EditorialScript
from agent.news_models import Entity

ACTION_PATTERNS = (
    ('bite', r'\b(?:bite|bit|bitten|biting|bites)\b'),
    ('hand_contact', r'\bhand\b.{0,65}\b(?:jaws?|mouth)\b|\b(?:jaws?|mouth)\b.{0,65}\bhand\b'),
    ('binding', r'\b(?:bind|bound|binding|tied|tie|tighten|tightened|tightening|chain|chained)\b'),
    ('uphill_push', r'\b(?:push|pushed|pushing|roll|rolled|rolling)\b.{0,70}\b(?:boulder|rock|stone)\b.{0,45}\b(?:uphill|up the hill|up a hill|up the slope)\b'),
    ('downhill_return', r'\b(?:boulder|rock|stone|it)\b.{0,65}\b(?:roll|rolled|rolling|fall|fell|falling)\b.{0,35}\b(?:back|downhill|down the hill|down the slope)\b'),
)


def action_kind(text):
    for kind, pattern in ACTION_PATTERNS:
        if re.search(pattern, text, re.I):
            return kind
    return None


def _action_visible(entity, kind):
    description=entity.description.casefold()
    required={
        'hand_contact': ('hand', 'jaw'), 'bite': ('bit', 'bite', 'biting', 'jaws'),
        'binding': ('bound', 'bind', 'tied', 'tighten', 'chain'),
        'uphill_push': ('boulder', 'uphill', 'push'),
        'downhill_return': ('boulder', 'downhill', 'back down', 'rolling down'),
    }[kind]
    return sum(token in description for token in required)>=2


def ensure_action_coverage(script, rows, audit):
    """Repair portrait-only plans with a story-specific action cutout.

    Called after optional LLM planning and on deterministic fallback. Existing
    variants that already describe the action are retained. The approved text
    and its timestamps are never changed.
    """
    entities={e.id:e for e in script.entities}
    additions=[];sentences=[];decisions=[];prior_text=''
    for sentence,row in zip(script.sentences,rows):
        kind=action_kind(sentence.text)
        if not kind:
            sentences.append(sentence);prior_text+=' '+sentence.text;continue
        selected=[entities[eid] for eid in sentence.entity_ids if eid in entities]
        if any(_action_visible(e,kind) for e in selected):
            decisions.append({'sectionId':sentence.id,'kind':kind,'decision':'reuse_action_variant'})
            sentences.append(sentence);prior_text+=' '+sentence.text;continue
        # An established character supplies visual identity; a pronoun may
        # refer to the last named protagonist. Keep the action itself primary.
        actor=next((e for e in selected if e.kind in ('person','animal') and e.identity!='generic' and e.name.casefold() in sentence.text.casefold()),None)
        if actor is None:
            actor=next((e for e in reversed(list(entities.values())) if e.kind in ('person','animal') and e.identity!='generic' and e.name.casefold() in prior_text.casefold()),None)
        if actor is None:
            decisions.append({'sectionId':sentence.id,'kind':kind,'decision':'degraded_no_identity'})
            sentences.append(sentence);prior_text+=' '+sentence.text;continue
        if len(entities)>=24:
            decisions.append({'sectionId':sentence.id,'kind':kind,'decision':'degraded_asset_budget'})
            sentences.append(sentence);prior_text+=' '+sentence.text;continue
        key='action-'+hashlib.sha256((actor.id+'|'+kind+'|'+sentence.text).encode()).hexdigest()[:12]
        context=', '.join(e.name for e in selected if e.id!=actor.id)
        description=(f'Action-specific editorial interaction cutout. The same recognizable {actor.name}: '
            f'{actor.description}. Clearly show this exact narrated physical event: {sentence.text} '
            f'Preserve character appearance and show visible contact, body pose, and object direction. '
            f'Include the interacting subject or prop ({context}) within this one cutout when needed. '
            'Non-gory, isolated on a plain contrasting background; no captions or scenery.')
        variant=Entity(id=key,name=actor.name,kind=actor.kind,identity=actor.identity,description=description)
        entities[key]=variant;additions.append(variant)
        # The interaction replaces the portrait, while distinct props and
        # supporting actors can remain as independently animated layers.
        retained=[eid for eid in sentence.entity_ids if eid!=actor.id and entities[eid].name.casefold()!=actor.name.casefold()]
        ids=[key,*retained][:12]
        anchor=next((word for word in sentence.text.split() if re.search(r'\b(?:hand|jaws?|bite|bit|bound|tied|tighten|chain|push|roll|fell|fall)\w*\b',word,re.I)),sentence.text.split()[0])
        row['cues']=[{'entityId':key,'anchor':anchor},*[cue for cue in row['cues'] if cue['entityId'] in retained]]
        sentences.append(sentence.model_copy(update={'entity_ids':ids}))
        decisions.append({'sectionId':sentence.id,'kind':kind,'decision':'generate_interaction_cutout','assetId':key,'anchor':anchor})
        prior_text+=' '+sentence.text
    audit['actionBeats']=decisions
    if not additions:return script,rows
    return EditorialScript.model_validate({**script.model_dump(),'entities':[e.model_dump() for e in entities.values()],
        'sentences':[s.model_dump() for s in sentences]}),rows
