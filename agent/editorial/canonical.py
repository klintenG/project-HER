"""Editorial script lock and conservative closure checks, before paid media work."""
import hashlib
import re
from agent.news_models import NewsError


def script_hash(script):
    return hashlib.sha256(script.narration.encode()).hexdigest()


def lock_script(script):
    if script.narration != ' '.join(s.text for s in script.sentences):
        raise NewsError('Canonical narration differs from sentence text.')
    if len({s.id for s in script.sentences}) != len(script.sentences):
        raise NewsError('Duplicate canonical sentence IDs.')
    return {'version': 1, 'sha256': script_hash(script), 'narration': script.narration,
            'sentences': [{'id': s.id, 'text': s.text} for s in script.sentences]}


def assert_locked(script, locked):
    if lock_script(script) != locked:
        raise NewsError('Approved narration changed after the canonical script was locked.')


def validate_closure(script, language='english'):
    """Only obvious English incomplete endings; semantic review handles other cases.

    This does not invent a resolution or force one on an ongoing factual story.
    """
    if language.lower() not in ('english', 'en', 'en-us', 'en-gb'):
        return
    final = script.sentences[-1].text.strip()
    if re.search(r'\b(?:and|but|because|until|while|to|the|a|an)[.!?…]*$', final, re.I):
        raise ValueError('Editorial ending is a grammatical fragment; complete it from evidence.')
    fictional = any(e.identity == 'fictional' for e in script.entities)
    if fictional and re.search(r'\b(?:challeng\w*|confront\w*|would (?:fight|battle)|prepared to)\b', final, re.I) and not re.search(
        r'\b(?:won|lost|defeated|victory|victorious|settled|resolved|became|crowned|claimed|inherited)\b', final, re.I
    ):
        raise ValueError('Fictional story ends on an unresolved confrontation; include its supported outcome.')
