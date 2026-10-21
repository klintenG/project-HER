"""Sisyphus acceptance fixture. Offline only: NO image, voice or vision API calls.

The rendered shapes exercise pipeline contracts, not visual storytelling quality.
Live evaluation: submit the emitted narration through the existing app/API.
"""
import argparse
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

EVENTS=[
 ('Sisyphus was a clever Greek king who angered Zeus.',['sisyphus','zeus'],'confront','interaction',['Sisyphus faces an angry Zeus']),
 ('Zeus commanded Thanatos to capture the king.',['zeus','thanatos'],'command','interaction',['Zeus points toward the king while Thanatos listens']),
 ('But Sisyphus wrapped chains around Thanatos and trapped Death.',['sisyphus','thanatos'],'chain','action_tableau',['Sisyphus physically fastens chains around Thanatos wrists and torso']),
 ('With Death bound, mortals could no longer die.',['thanatos'],'bound','aftermath',['Thanatos visibly restrained and unable to act; surviving mortals nearby']),
 ('Ares shattered the chains and freed Thanatos.',['ares','thanatos'],'free','action_tableau',['Ares breaks chains off Thanatos; broken links separate from wrists']),
 ('Then Ares seized Sisyphus and dragged him into the underworld.',['ares','sisyphus'],'drag','action_tableau',['Ares grips Sisyphus arm and pulls him toward an underworld gate']),
 ('Sisyphus pleaded with Hades and Persephone for permission to return.',['sisyphus','hades','persephone'],'plead','interaction',['Sisyphus gestures pleadingly toward Hades and Persephone seated on thrones']),
 ('Back on Earth, Sisyphus lounged and refused to return.',['sisyphus'],'lounge','aftermath',['Sisyphus reclines comfortably on a couch; relaxed posture; no held prop']),
 ('Zeus condemned the captured king to an eternal punishment.',['zeus','sisyphus'],'sentence','interaction',['Zeus pronounces sentence over captive Sisyphus']),
 ('Sisyphus pressed both palms against an enormous boulder and pushed it uphill.',['sisyphus'],'push_uphill','action_tableau',['Both palms contact huge irregular stone, torso leans forward, feet brace on incline rising right; boulder 2 to 3 times torso height']),
 ('Near the summit, the boulder slipped free and rolled back downhill.',['sisyphus'],'roll_downhill','aftermath',['Huge boulder rolls down toward lower left; exhausted Sisyphus above it loses contact; slope visible']),
 ('Sisyphus began again, pushing the enormous boulder forever.',['sisyphus'],'repeat_push','action_tableau',['Sisyphus physically pushes the huge boulder uphill again; eternal cycle visible']),
]


def sample():
    from agent.news_models import Entity,Script,Sentence
    from agent.editorial import event_storyboard as ev
    descriptions={'sisyphus':'Athletic ancient Greek man with curly dark hair and beard, ivory tunic; empty hands, no accessory',
        'zeus':'Elderly muscular Greek god, white beard, white and gold robe',
        'thanatos':'Solemn black-winged personification of Death in dark ancient robe',
        'ares':'Ancient Greek warrior with bronze helmet and red cloak',
        'hades':'Ancient underworld king in dark royal robes and crown',
        'persephone':'Ancient underworld queen in burgundy robes with dark braided hair'}
    people=[Entity(id=k,name=k.title(),kind='person',identity='fictional',description=v) for k,v in descriptions.items()]
    sentences=[];beats=[]
    for i,(text,actors,verb,role,required) in enumerate(EVENTS):
        sid=f's{i}';sentences.append(Sentence(id=sid,text=text,claim_ids=['fixture'],entity_ids=actors,phrase=' '.join(text.split()[:6]),role='development'))
        objects=['boulder','mountain_slope'] if i>=9 else ['chain'] if i in (2,3,4) else []
        forbidden=['standing portrait only','extra limbs','duplicate protagonists','embedded captions','modern clothing']
        if i>=9:forbidden+=['wheel','shield','small disc','missing boulder']
        beats.append(dict(beat_id=f'{sid}_1',section_id=sid,narration_excerpt=text,event_type='action',actor_ids=actors,verb=verb,object_ids=[],setting='ancient Greek mythology',visual_intent=required[0],must_show=required,must_not_show=forbidden,role=role,criticality='P0',confidence=.95,physical_action=True,concept=dict(subject=' and '.join(actors),action=required[0],important_objects=objects,setting='ancient Greek mythology',emotion='strained' if i>=9 else 'dramatic',state_change=required[0],state_before=f'Before event {i}',state_after=required[0],visual_focus=required[0],description='Editorial action cutout: '+required[0],identity_ids=actors,relevance=.99,narrative_importance=1,novelty=.95,readability=.95)))
    source=Script(summary='Sisyphus: death, defiance and the eternal boulder',narration=' '.join(s.text for s in sentences),sentences=sentences,entities=people)
    reply={'continuity_bible':[dict(entity_id=p.id,description=p.description,wardrobe_states={'base':p.description},prop_designs=[]) for p in people],'beats':beats}
    planned,cues=ev.plan(source,None,lambda instruction,*_: {'accepted':True} if instruction.startswith('Audit event') else reply,{})
    return source,planned,cues,reply


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='output/sisyphus_acceptance');parser.add_argument('--render-offline',action='store_true');args=parser.parse_args()
    root=Path(args.output).resolve();root.mkdir(parents=True,exist_ok=True)
    # Explicit fixture profile: no essential beat demotion for quotas/budget.
    profile={'GENERATED_IMAGE_MAX':'24','MAX_SEEDREAM_ACTION_IMAGES':'16','MAX_IMAGE_BUDGET_USD':'.60',
        'IMAGE_ESTIMATED_BUDGET_USD':'.60','MAX_TOTAL_VIDEO_BUDGET_USD':'.80','TYPOGRAPHY_BEAT_TARGET':'0',
        'PROJECTHER_ALLOW_ASSET_OVERRUN':'false','PROJECTHER_ALLOW_CRITICAL_EVENT_FALLBACK':'false'}
    with patch.dict(os.environ,profile):
        source,planned,cues,reply=sample()
        from agent.editorial.asset_planner import finalize
        from agent.editorial.quality_artifacts import write
        plan=finalize(planned,root)
        write(root,planned)
        (root/'narration.txt').write_text(source.narration)
        (root/'example_prompts.json').write_text(json.dumps([{'scene_id':b['sentence_id'],'prompt':b['event_generation_prompt']} for b in planned.sentence_storyboard],indent=2))
        if args.render_offline:
            import config
            import scripts.validate_smart_images as runner
            with patch.object(runner,'sample',sample),patch.object(config,'PROJECTHER_IMAGE_BUDGET_USD',.60),patch.object(config,'RENDER_BLOCK_ON_CRITICAL_VISUAL_FAILURE',True),patch.object(sys,'argv',['validate_smart_images','--output',str(root)]):
                runner.main()
            quality=json.loads((root/'quality_report.json').read_text())
            quality.update(status='offline_fixture_only',scope='Synthetic shapes/audio and mocked semantic judgments. Does not establish any real scene visibly depicts the narrated action.')
            (root/'quality_report.json').write_text(json.dumps(quality,indent=2))
        print(json.dumps({'story_beats':len(EVENTS),'action_images':plan['seedream_count'],'estimated_image_usd':plan['estimated_image_cost_usd'],'output':str(root),'live_quality_verified':False},indent=2))

if __name__=='__main__':main()
