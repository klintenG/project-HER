"""Proof run for beat-aware cutout scenes: Thor and Sisyphus through the real editorial pipeline.

    .venv/bin/python scripts/scene_plan_demo.py thor
    .venv/bin/python scripts/scene_plan_demo.py sisyphus [--fixture-speech]

What is real: narration (edge-tts, word timings), image generation (Replicate, the project's configured event
model), background removal (rembg), cutout styling/element extraction, scene classification, layout, motion,
Remotion render and ffmpeg encode.
What is authored: the semantic event plan below stands in for the planner LLM (the Gemini key in .env currently
returns 401), and vision review is stubbed to "accept". Beat types are intentionally NOT hinted, so
scene_plan.classify_beat decides them. Output: output/scene_plan_<story>/ (editorial.mp4, scene_plan.json,
scene_plan_sheet.jpg).
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
from agent.news_models import Entity, Script, Sentence
from agent.editorial.pipeline import run_editorial
from tests.news_fixtures import FixtureLLM, FixtureTTS
from tests.test_sentence_storyboard import review


def person(id_, name, description):
    return Entity(id=id_, name=name, kind='person', identity='fictional', description=description)


THOR_CAST = [
    person('thor', 'Thor', 'Muscular Norse god of thunder, long braided red-blond hair and beard, blue tunic, fur-trimmed cloak, leather bracers'),
    person('thrym', 'Thrym', 'Huge brown-bearded frost giant with a horned iron crown and heavy fur robes'),
    person('freyja', 'Freyja', 'Elegant Norse goddess, long golden hair, blue gown with a gold amber necklace'),
    person('loki', 'Loki', 'Lean sly trickster god, black slicked hair, green cloak with a golden clasp'),
]
SISYPHUS_CAST = [
    person('sisyphus', 'Sisyphus', 'Cunning ancient Greek king, dark beard, tan linen chiton, strong build'),
    person('thanatos', 'Thanatos', 'Winged god of death in a flowing black hooded robe with dark feathered wings'),
    person('zeus', 'Zeus', 'Majestic white-bearded king of the Greek gods in a white toga holding a lightning bolt'),
]

# line, entity ids, role, criticality, actors, verb, objects, action, subject, emotion, must_show, state_after
THOR = [
    ('Thor, the mighty God of Thunder, ruled the skies with his magical hammer, Mjölnir.', ['thor'], 'character_intro', 'P1', ['thor'], 'stand', ['Mjölnir hammer'], 'standing proudly holding Mjölnir', 'Thor', 'pride', ['Thor holding his hammer Mjölnir'], 'Thor in his normal blue tunic and cloak with Mjölnir'),
    ('One morning, Thor woke up to find his hammer missing.', ['thor'], 'action_tableau', 'P0', ['thor'], 'search', ['empty hammer rack'], 'searching frantically, looking at his empty hand and the empty place where Mjölnir should be', 'Thor', 'alarm', ['Thor looking at an empty hand where the hammer should be'], 'Thor without the hammer'),
    ('A giant named Thrym had stolen it, and he buried it deep underground.', ['thrym'], 'action_tableau', 'P0', ['thrym'], 'bury', ['Mjölnir hammer', 'dirt mound'], 'crouching over a hole, burying Mjölnir in the ground with a smug grin', 'Thrym', 'smug', ['Thrym burying the hammer Mjölnir in a mound of earth'], 'Hammer buried'),
    ('Thrym demanded the goddess Freyja as his bride in return.', ['thrym', 'freyja'], 'interaction', 'P0', ['thrym', 'freyja'], 'demand', [], 'pointing a demanding finger at Freyja while she stands back', 'Thrym and Freyja', 'greed', ['Thrym pointing at Freyja while she recoils'], 'Demand made'),
    ('But Freyja refused.', ['freyja', 'thrym'], 'interaction', 'P0', ['freyja'], 'refuse', [], 'Freyja turning her back and holding up a hand in refusal', 'Freyja', 'defiance', ['Freyja holding up a hand, face turned away in refusal'], 'Refusal'),
    ('So Loki dressed Thor in a bridal gown and veil.', ['loki', 'thor'], 'action_tableau', 'P0', ['loki', 'thor'], 'dress', ['bridal gown', 'veil'], 'draping a white bridal gown and veil over a grumpy Thor while Loki smirks', 'Thor in bridal disguise with Loki', 'grumpy', ['Thor wearing a white bridal gown and veil, Loki adjusting the veil'], 'Thor wears the bridal gown and veil, still bearded'),
    ('At the wedding feast, Thor ate an entire ox and drank three barrels of mead.', ['thor', 'thrym'], 'action_tableau', 'P0', ['thor'], 'devour', ['roast ox', 'mead barrels', 'feast table'], 'tearing into a whole roasted ox at a feast table with mead barrels beside him, still in bridal veil', 'Thor at the feast', 'gluttony', ['Thor in bridal veil eating a whole roasted ox beside three mead barrels'], 'Thor in veil at the feast'),
    ('The giants stared in shock.', ['thrym'], 'reaction', 'P1', ['thrym'], 'stare', [], 'wide-eyed giants staring in shock with open mouths', 'Shocked giants', 'shock', ['Giants with wide eyes and open mouths in shock'], 'Giants stunned'),
    ('Thrym ordered the hammer placed in the bride\'s lap to bless the marriage.', ['thrym', 'thor'], 'interaction', 'P0', ['thrym', 'thor'], 'bless', ['Mjölnir hammer'], 'a giant lowering Mjölnir into the lap of the veiled bride (Thor) in a blessing', 'Hammer blessing', 'ceremony', ['Mjölnir resting in the lap of the veiled bride while Thrym places it'], 'Hammer in the bride\'s lap'),
    ('Then Thor ripped off his veil and revealed himself.', ['thor'], 'reveal', 'P0', ['thor'], 'reveal', ['torn veil'], 'tearing off the bridal veil in a dramatic reveal, fierce expression, Mjölnir in hand', 'Thor revealed', 'fury', ['Thor tearing off the veil with Mjölnir in his fist'], 'Veil torn off, Thor revealed'),
    ('He grabbed Mjölnir and smashed the giants in a furious battle.', ['thor', 'thrym'], 'action_tableau', 'P0', ['thor', 'thrym'], 'smash', ['Mjölnir hammer'], 'swinging Mjölnir with lightning, smashing the giants, giants flying backwards', 'Thor in battle', 'fury', ['Thor swinging Mjölnir at giants who fly backwards'], 'Giants defeated'),
    ('And so the God of Thunder won back his hammer, and his pride.', ['thor'], 'aftermath', 'P1', ['thor'], 'triumph', ['Mjölnir hammer'], 'standing victorious holding Mjölnir overhead with lightning behind him', 'Thor victorious', 'triumph', ['Thor triumphant with Mjölnir raised'], 'Victorious'),
]
SISYPHUS = [
    ('Sisyphus was a cunning king of ancient Greece.', ['sisyphus'], 'character_intro', 'P1', ['sisyphus'], 'stand', [], 'standing with a clever knowing smirk', 'Sisyphus', 'cunning', ['Sisyphus with a clever smirk'], 'Sisyphus intro'),
    ('He tricked Death itself, locking Thanatos in his own chains.', ['sisyphus', 'thanatos'], 'action_tableau', 'P0', ['sisyphus', 'thanatos'], 'chain', ['iron chains'], 'wrapping heavy iron chains around the winged Thanatos while Sisyphus smirks', 'Sisyphus chaining Thanatos', 'cunning', ['Thanatos wrapped in iron chains, Sisyphus pulling the chain tight'], 'Thanatos chained'),
    ('But he escaped the underworld, and refused to return.', ['sisyphus'], 'action_tableau', 'P0', ['sisyphus'], 'escape', ['underworld gate'], 'sprinting away from a dark underworld gate, looking back with a grin', 'Sisyphus escaping', 'triumph', ['Sisyphus running away from the underworld gate looking back'], 'Escaped'),
    ('The gods condemned him in a terrible divine judgment.', ['zeus', 'sisyphus'], 'interaction', 'P0', ['zeus', 'sisyphus'], 'condemn', ['lightning bolt'], 'Zeus pointing a lightning bolt in divine judgment at the kneeling Sisyphus', 'Divine judgment', 'dread', ['Zeus pointing a lightning bolt down at kneeling Sisyphus'], 'Judged'),
    ('He was cursed to push a huge boulder up a hill.', ['sisyphus'], 'action_tableau', 'P0', ['sisyphus'], 'push', ['huge boulder'], 'straining with both hands against a huge boulder pushing it UP a steep hill', 'Sisyphus pushing', 'strain', ['Sisyphus leaning hard against a huge boulder pushing uphill'], 'Pushing uphill'),
    ('Every time he reached the top, the boulder rolled back down.', ['sisyphus'], 'action_tableau', 'P0', ['sisyphus'], 'roll', ['huge boulder'], 'the huge boulder tumbling and rolling downhill away from Sisyphus who throws up his arms in despair', 'Boulder rolling down', 'despair', ['A huge boulder rolling downhill away from Sisyphus with his arms thrown up'], 'Boulder rolling downhill'),
    ('And so he pushes it forever.', ['sisyphus'], 'aftermath', 'P1', ['sisyphus'], 'push', ['huge boulder'], 'a small tired figure pushing the huge boulder, endless', 'Sisyphus eternal', 'weary', ['Sisyphus wearily pushing the boulder'], 'Eternal task'),
]
STORIES = {'thor': (THOR_CAST, THOR), 'sisyphus': (SISYPHUS_CAST, SISYPHUS)}


def build(story):
    cast, rows = STORIES[story]
    sentences = [Sentence(id=f's{i}', text=r[0], claim_ids=[f'c{i + 1}'], entity_ids=r[1][:3], phrase=' '.join(r[0].split()[:4]),
                          role='hook' if i == 0 else 'close' if i == len(rows) - 1 else 'development') for i, r in enumerate(rows)]
    script = Script(summary=story.title() + ' myth', narration=' '.join(r[0] for r in rows), sentences=sentences, entities=cast)
    return script, rows


def planner(script, rows):
    by_text = {r[0]: r for r in rows}

    def beats_for(section):
        text, ids, role, crit, actors, verb, objects, action, subject, emotion, show, after = by_text[section['text']]
        return dict(beat_id='b-' + section['id'], section_id=section['id'], narration_excerpt=text, event_type=verb, actor_ids=actors, verb=verb,
                    object_ids=[], setting='story moment', causal_link='', visual_intent=action, must_show=show, must_not_show=['text', 'standing portrait pose' if role != 'character_intro' else 'extra people'],
                    role=role, criticality=crit, confidence=.9,
                    concept=dict(subject=subject, action=action, important_objects=objects, setting='story moment', emotion=emotion, state_change=after, state_before='before', state_after=after,
                                 visual_focus=action, description='Isolated cutout composition: ' + action, identity_ids=ids[:2] if role != 'character_intro' else ids[:1], secondary_ids=[],
                                 relevance=.95, narrative_importance=.9, novelty=.9, readability=.9))

    class LLM(FixtureLLM):
        def __call__(self, instruction, data):
            if instruction.startswith('Plan the semantic events'):
                return dict(continuity_bible=[dict(entity_id=e.id, description=e.description, wardrobe_states={'base': 'base costume'}, prop_designs=['Mjölnir: short-handled stone war hammer with a leather grip'] if e.id == 'thor' else []) for e in script.entities],
                            beats=[beats_for(s) for s in data['target_sections']])
            if instruction.startswith('Audit event'):
                return {'accepted': True, 'problems': []}
            return super().__call__(instruction, data)
    return LLM('Fictional account: ' + script.narration, script)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('story', choices=sorted(STORIES), nargs='?', default='thor')
    parser.add_argument('--fixture-speech', action='store_true', help='tone pulses instead of live edge-tts')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    script, rows = build(args.story)
    out = args.output or config.OUTPUT_DIR / f'scene_plan_{args.story}'
    with patch('agent.editorial.vision.VisualReview', return_value=review):
        result = run_editorial('Fictional account: ' + script.narration, output_dir=out, source_policy='supplied', llm=planner(script, rows),
                               tts_provider='edge_tts', tts_engine=FixtureTTS() if args.fixture_speech else None, music=False)
    print('success', result.success, result.errors, flush=True)
    if not result.success:
        return 1
    manifest = json.loads((out / 'editorial_manifest.json').read_text())
    plan = manifest['diagnostics'].get('scenePlan', [])
    (out / 'scene_plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2))
    for row in plan:
        print(f"{row['beat_type']:<16}{row['template']:<18}{row['visual_mode']:<28}{row['text'][:60]}")
    video = out / 'editorial.mp4'
    duration = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(video)]))
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(video), '-vf', f'fps=18/{duration},scale=270:-1,tile=6x3', '-frames:v', '1', str(out / 'scene_plan_sheet.jpg')], check=True)
    print(video, round(duration, 1), 'seconds')
    return 0


if __name__ == '__main__':
    sys.exit(main())
