"""Event semantics, exact source spans, measured timing and fail-closed QC."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
from agent.editorial import event_storyboard as ev
from agent.editorial.models import Word
from agent.news_models import NewsError
from tests.test_sentence_storyboard import script_for


def response(script, chunks=None):
    beats=[]
    for s in script.sentences:
        for text in (chunks or {}).get(s.id,[s.text]):
            i=len(beats)
            beats.append(dict(beat_id=f'b{i}',section_id=s.id,narration_excerpt=text,event_type='action',
                actor_ids=['identity'],verb=f'action-{i}',object_ids=[],setting='mythic hall',causal_link='',
                visual_intent=text,must_show=[text],must_not_show=['solo standing portrait'],role='action_tableau',
                criticality='P0',confidence=.9,concept=dict(subject='Character',action=text,important_objects=[],
                setting='mythic hall',emotion='surprise',state_change=text,state_before='before',state_after=text,
                visual_focus=text,description='The character actively performs this event: '+text,identity_ids=['identity'],
                relevance=.95,narrative_importance=.9,novelty=.9,readability=.9)))
    return dict(continuity_bible=[dict(entity_id=e.id,description=e.description,wardrobe_states={'base':'blue robe'},prop_designs=[]) for e in script.entities],beats=beats)


def planned(lines,chunks=None):
    script=script_for(lines);reply=response(script,chunks)
    result,_=ev.plan(script,None,lambda instruction,*_: {'accepted':True} if instruction.startswith('Audit event') else reply,{})
    return script,result,reply


class EventStoryboardTests(unittest.TestCase):
    def test_sequential_actions_split_without_rewriting_audio(self):
        source,script,_=planned(['She took the key, opened the door, and escaped.'],
            {'s0':['She took the key,','opened the door,','and escaped.']})
        self.assertEqual(script.narration,source.narration)
        self.assertEqual(len(script.sentences),3)
        plan=ev.EventPlan.model_validate(script.event_plan).validate_script(source)
        self.assertEqual([source.narration[b.script_character_start:b.script_character_end] for b in plan.beats],
            [s.text for s in script.sentences])
        self.assertEqual(len({b.asset_entity_id for b in plan.beats}),3)
        words=[Word(id=f'w{i}',sectionId='s0',text=t,start=i*.4+.1,end=i*.4+.35,provenance='provider',confidence=.98) for i,t in enumerate(source.narration.split())]
        bound,sections=ev.bind_audio(script,words)
        self.assertEqual([(w.id,w.text,w.start,w.end) for w in bound],[(w.id,w.text,w.start,w.end) for w in words])
        self.assertEqual(sections[1].start,words[4].start)
        words[0].text='Changed'
        with self.assertRaises(NewsError):ev.bind_audio(script,words)

    def test_repeated_phrase_is_bound_by_position_not_first_occurrence(self):
        source,script,_=planned(['She knocked. She knocked.'],{'s0':['She knocked.','She knocked.']})
        beats=script.event_plan['beats']
        self.assertEqual(beats[1]['script_character_start'],13)
        self.assertNotEqual(beats[0]['asset_entity_id'],beats[1]['asset_entity_id'])

    def test_stale_missing_overlapping_and_unknown_spans_rejected(self):
        source=script_for(['She lifted it and dropped it.']);base=response(source)
        for change in ('missing','unknown','duplicate'):
            r=copy.deepcopy(base)
            if change=='missing':r['beats'][0]['narration_excerpt']='lifted it'
            if change=='unknown':r['beats'][0]['actor_ids']=['stranger']
            if change=='duplicate':r['beats']*=2
            if change!='unknown':
                # Recoverable planner slips are repaired onto the exact frozen words.
                result,_=ev.plan(source,None,lambda instruction,*_: {'accepted':True} if instruction.startswith('Audit event') else r,{})
                self.assertEqual(' '.join(x['narration_excerpt'] for x in result.event_plan['beats']).split(),source.narration.split())
                continue
            with self.assertRaises(NewsError):ev.plan(source,None,lambda instruction,*_: {'accepted':True} if instruction.startswith('Audit event') else r,{})
        _,script,_=planned(['She lifted it.'])
        with self.assertRaises(ValueError):ev.EventPlan.model_validate(script.event_plan).validate_script(source)

    def test_object_in_hand_preserves_character_conditioning(self):
        source=script_for(['She grabbed the hammer.']);r=response(source)
        c=r['beats'][0]['concept'];c.update(visual_focus='Close-up of hammer in hand',important_objects=['hammer'])
        result,_=ev.plan(source,None,lambda instruction,*_: {'accepted':True} if instruction.startswith('Audit event') else r,{})
        self.assertEqual(result.sentence_storyboard[0]['continuity_references'],['identity'])

    def test_intentional_reuse_requires_identical_action_and_state(self):
        source=script_for(['The jewel sparkled. The jewel sparkled.'])
        r=response(source,{'s0':['The jewel sparkled.','The jewel sparkled.']})
        r['beats'][1].update(verb=r['beats'][0]['verb'],reuse_of='b0')
        result,_=ev.plan(source,None,lambda instruction,*_: {'accepted':True} if instruction.startswith('Audit event') else r,{})
        self.assertEqual(result.sentences[0].entity_ids,result.sentences[1].entity_ids)
        r['beats'][1]['concept']['state_after']='broken jewel'
        with self.assertRaises(NewsError):ev.plan(source,None,lambda instruction,*_: {'accepted':True} if instruction.startswith('Audit event') else r,{})

    def test_visual_judge_required_not_text_metadata_or_relevance_alone(self):
        self.assertFalse(ev.review_passes({'relevant':True},None))
        proof={k:True for k in ('relevant','actionCorrect','objectsCorrect','continuityCorrect','requirementsVisible','forbiddenAbsent')}
        proof.update(portraitSubstitution=False,problems=[])
        self.assertTrue(ev.review_passes(proof,None))
        proof['portraitSubstitution']=True
        self.assertFalse(ev.review_passes(proof,None))

    def test_duplicate_portrait_for_different_actions_fails_coverage(self):
        _,script,_=planned(['She ate the feast.','She grabbed the hammer.'])
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'portrait.png';Image.new('RGB',(100,100),'red').save(path)
            assets=[];records=[];words=[]
            proof={k:True for k in ('relevant','actionCorrect','objectsCorrect','continuityCorrect','requirementsVisible','forbiddenAbsent')}
            proof.update(portraitSubstitution=False,problems=[])
            for i,b in enumerate(script.event_plan['beats']):
                assets.append(SimpleNamespace(entityId=b['asset_entity_id'],id=f'a{i}',path=str(path)))
                records.append(dict(entityId=b['asset_entity_id'],generation={'sentenceReview':proof}))
                for j,t in enumerate(b['narration_excerpt'].split()):
                    words.append(Word(id=f'w{i}-{j}',sectionId=b['visual_section_id'],text=t,start=i*5+j*.3,end=i*5+j*.3+.2,provenance='estimated_phrase',confidence=0))
            report=ev.report(script,assets,{'assets':records},words)
            self.assertEqual(report['beats'][1]['validation_status'],'needs_review')
            self.assertFalse(report['metrics']['p0_acceptance_passed'])
            self.assertIsNone(report['beats'][0]['render_onset_delta_ms'])

    def test_history_and_comedy_generalize_without_story_names(self):
        for lines in (["In 1969, Apollo 11 launched from Florida.","Armstrong stepped onto the Moon.","The capsule returned to Earth."],
                      ['The baker slipped on flour, caught the cake, and landed in a chair.']):
            _,s,_=planned(lines)
            self.assertEqual(s.narration,' '.join(lines))
            self.assertTrue(all(b['must_show'] for b in s.event_plan['beats']))

    def test_curated_golden_storyboards_cover_exact_spans(self):
        root=Path(__file__).parent/'fixtures/visual_correlation'
        for filename,count in [('thor.json',14),('history.json',5),('comedy.json',5)]:
            fixture=json.loads((root/filename).read_text())
            from agent.editorial.visuals import EditorialScript
            source=EditorialScript.model_validate(fixture['source_script'])
            def curated(instruction,data):
                if instruction.startswith('Audit event'):return {'accepted':True}
                ids={section['id'] for section in data['target_sections']}
                return {'continuity_bible':fixture['response']['continuity_bible'],
                    'beats':[b for b in fixture['response']['beats'] if b['section_id'] in ids]}
            script,_=ev.plan(source,None,curated,{})
            self.assertEqual(len(script.event_plan['beats']),count)
            self.assertEqual(script.narration,source.narration)
            if filename=='thor.json':
                self.assertEqual([b['verb'] for b in script.event_plan['beats']][-4:],
                    ['grab','reveal','confrontation','comic_aftermath'])
                self.assertTrue(all(b['must_show'] for b in script.event_plan['beats']))

    def test_critical_portrait_and_provider_failure_never_become_accepted(self):
        from agent.editorial.assets import acquire
        import config
        import shutil
        class Processor:
            version='unit-test'
            def process(self,source,dest,**kwargs):
                shutil.copyfile(source,dest)
                return {'foreground':.5},'unit-test'
        class Generator:
            async def subject(self,prompt,path):
                Image.new('RGB',(320,320),'#bbbbbb').save(path)
                return 'replicate:unit-test'
            async def scene_subject(self,prompt,path,reference=None):return await self.subject(prompt,path)
        def judge(instruction,data,paths):
            if instruction.startswith('Validate this'):
                return dict(relevant=False,actionCorrect=False,objectsCorrect=False,
                    portraitSubstitution=True,problems=['Standing portrait does not depict action'])
            return dict(subjectMatch=True,usable=True,geometricPlaceholder=False,contextAppropriate=True,subjectConfidence=.99)
        for failure in ('portrait','rate_limit','missing_judge'):
            _,script,_=planned(['She ate a feast.'])
            generator=Generator()
            if failure=='rate_limit':
                async def blocked(*args,**kwargs):raise NewsError('HTTP 429 provider unavailable')
                generator.scene_subject=blocked
            elif failure=='missing_judge':
                def unavailable(*args,**kwargs):raise RuntimeError('visual judge unavailable')
                chosen_judge=unavailable
            with tempfile.TemporaryDirectory() as root,patch.object(config,'NEWS_IDENTITY_IMAGE_CACHE',Path(root)/'cache'):
                try:
                    _,assets=acquire(script,Path(root)/'assets',asset_mode='ai',image_generator=generator,
                        processor=Processor(),visual_review=chosen_judge if failure=='missing_judge' else judge,diagnostics={})
                except NewsError:
                    continue  # Actionable failure is correct when no usable event survives.
                acquisition=json.loads((Path(root)/'assets/asset_acquisition.json').read_text())
                summary=ev.validate_assets(script,assets,acquisition)
                self.assertFalse(summary['acceptancePassed'])
                self.assertTrue(summary['degradedSentences'])

    def test_event_pipeline_keeps_original_speech_groups_and_compiles_edl(self):
        from tests.news_fixtures import FixtureLLM,FixtureTTS,ACCOUNT
        from agent.editorial.pipeline import run_editorial
        from agent.editorial.assets import prepare
        from agent.editorial.models import Entity as RenderEntity
        import config
        class LLM(FixtureLLM):
            def __call__(self,instruction,data):
                if instruction.startswith('Audit event'):return {'accepted':True}
                if instruction.startswith('Plan the semantic events'):
                    entities=data['entities'];beats=[]
                    for section in data['target_sections']:
                        refs=section['entity_ids'][:1]
                        text=section['text']
                        beats.append(dict(beat_id=section['id'],section_id=section['id'],narration_excerpt=text,
                            event_type='context',actor_ids=refs,verb='illustrate',object_ids=[],setting='laboratory',
                            visual_intent=text,must_show=[text],must_not_show=[],role='object_detail',criticality='P1',confidence=1,
                            concept=dict(subject='Demonstration',action=text,important_objects=[],setting='laboratory',emotion='neutral',
                                state_change=text,visual_focus=text,description='Synthetic orchestration test illustration for '+text,
                                identity_ids=refs,relevance=1,narrative_importance=1,novelty=1,readability=1)))
                    return {'continuity_bible':[dict(entity_id=e['id'],description=e['description']) for e in entities],'beats':beats}
                return super().__call__(instruction,data)
        def acquisition(script,output,**kwargs):
            output=Path(output);output.mkdir(parents=True,exist_ok=True);assets=[];entities=[];records=[]
            for i,e in enumerate(script.entities):
                image=output/(e.id+'.png')
                from PIL import ImageDraw
                cutout=Image.new('RGBA',(320,320),(0,0,0,0))
                ImageDraw.Draw(cutout).ellipse((40,20,280,300),fill=(20+i*40,80,120,255))
                cutout.save(image)
                a=prepare(e,image,output,source='Synthetic unit fixture',license='test',attribution='test',role='context',factual=False)
                assets.append(a);entities.append(RenderEntity(id=e.id,name=e.name,identity=e.identity,assetIds=[a.id],source=a.source))
                check=dict(relevant=True,actionCorrect=True,objectsCorrect=True,continuityCorrect=True,requirementsVisible=True,
                    forbiddenAbsent=True,portraitSubstitution=False,problems=[])
                records.append(dict(entityId=e.id,generation={'sentenceReview':check}))
            kwargs['diagnostics']['assetAcquisition']={'assets':records}
            return entities,assets
        with tempfile.TemporaryDirectory() as tmp,patch.object(config,'EVENT_STORYBOARD_ENABLED',True),patch.object(config,'SENTENCE_PRIMARY_VISUALS',True):
            root=Path(tmp)
            def rendered(script,m,video,out):return json.loads((Path(out)/'event_edl.json').read_text())
            with patch('agent.editorial.pipeline.acquire',side_effect=acquisition),patch('agent.editorial.pipeline.render',side_effect=lambda m,p,*a,**k:(p,{})),patch('agent.editorial.pipeline.run'),patch('agent.editorial.vision.VisualReview'),patch.object(ev,'verify_rendered',side_effect=rendered),patch('agent.editorial.quality_artifacts.contact_sheet'):
                result=run_editorial(ACCOUNT,output_dir=root,source_policy='supplied',llm=LLM(),tts_provider='edge_tts',tts_engine=FixtureTTS(),music=False)
            self.assertTrue(result.success,result.errors)
            edl=json.loads((root/'event_edl.json').read_text())
            manifest=json.loads((root/'editorial_manifest.json').read_text())
            self.assertEqual(len(edl['beats']),4)
            self.assertTrue(all(w['provenance']=='provider' for w in manifest['words']))
            self.assertTrue(all(w['sectionId'].startswith('event-') for w in manifest['words']))
            self.assertTrue(all(b['audio_start_ms'] is not None for b in edl['beats']))

    def test_visual_entry_uses_spoken_action_anchor_not_setup_phrase(self):
        from agent.editorial.sentence_storyboard import direction
        source=script_for(['During the ceremony, she grabbed the hammer.'])
        r=response(source);r['beats'][0]['onset_anchor']='grabbed'
        script,_=ev.plan(source,None,lambda instruction,*_: {'accepted':True} if instruction.startswith('Audit event') else r,{})
        cue=direction(script).cues[0]
        self.assertEqual(cue.startWord,4)
        self.assertEqual(cue.phrase,'grabbed the hammer.')
        r['beats'][0]['onset_anchor']='unspoken action'
        with self.assertRaises(NewsError):ev.plan(source,None,lambda instruction,*_: {'accepted':True} if instruction.startswith('Audit event') else r,{})

    def test_multibatch_beat_id_collisions_are_disambiguated(self):
        lines = [
            'Line one happens here.',
            'Line two happens here.',
            'Line three happens here.',
            'Line four happens here.',
            'Line five happens here.',
            'Line six happens here.'
        ]
        source = script_for(lines)
        def colliding_batches(instruction, data):
            if instruction.startswith('Audit event'):
                return {'accepted': True}
            beats = []
            for s in data['target_sections']:
                idx = len(beats) + 1
                beats.append(dict(beat_id=f'b{idx}', section_id=s['id'], narration_excerpt=s['text'],
                    event_type='action', actor_ids=['identity'], verb=f'action-{idx}', object_ids=[],
                    setting='hall', visual_intent=s['text'], must_show=[s['text']], must_not_show=[],
                    role='action_tableau', criticality='P0', confidence=.9,
                    concept=dict(subject='Character', action=s['text'], important_objects=[], setting='hall',
                        emotion='neutral', state_change=s['text'], visual_focus=s['text'],
                        description='Description for ' + s['text'], identity_ids=['identity'],
                        relevance=.95, narrative_importance=.9, novelty=.9, readability=.9)))
            return dict(continuity_bible=[dict(entity_id=e.id, description=e.description, wardrobe_states={}, prop_designs=[]) for e in source.entities], beats=beats)

        diag = {}
        script, _ = ev.plan(source, None, colliding_batches, diag)
        plan_beats = script.event_plan['beats']
        self.assertEqual(len(plan_beats), 6)
        beat_ids = [b['beat_id'] for b in plan_beats]
        self.assertEqual(len(beat_ids), len(set(beat_ids)))
        self.assertEqual(beat_ids[:3], ['b1', 'b2', 'b3'])
        self.assertEqual(beat_ids[3:], ['s3_b1', 's4_b2', 's5_b3'])

    def test_p0_character_intro_normalized(self):
        source = script_for(['Sisyphus was a cunning king who tricked Death.'])
        r = response(source)
        r['beats'][0]['criticality'] = 'P0'
        r['beats'][0]['role'] = 'character_intro'
        r['beats'][0]['concept']['action'] = 'Sisyphus preparing a cunning trick'
        script, _ = ev.plan(source, None, lambda instruction, *_: {'accepted': True} if instruction.startswith('Audit event') else r, {})
        plan_beats = script.event_plan['beats']
        self.assertEqual(plan_beats[0]['role'], 'action_tableau')

    def test_batch_extraneous_beats_filtered_and_multisection_covered(self):
        lines = [f'Sentence {i} happens here.' for i in range(1, 11)]
        source = script_for(lines)
        def noisy_batches(instruction, data):
            if instruction.startswith('Audit event'):
                return {'accepted': True}
            target_ids = {s['id'] for s in data['target_sections']}
            # Return beats for targets, but also extraneous beats from all sections (simulating LLM hallucinating full script)
            beats = []
            for s in source.sentences:
                beats.append(dict(beat_id=f'{s.id}_b1', section_id=s.id, narration_excerpt=s.text,
                    event_type='action', actor_ids=['identity'], verb='action', object_ids=[],
                    setting='hall', visual_intent=s.text, must_show=[s.text], must_not_show=[],
                    role='action_tableau', criticality='P0', confidence=.9,
                    concept=dict(subject='Character', action=s.text, important_objects=[], setting='hall',
                        emotion='neutral', state_change=s.text, visual_focus=s.text,
                        description='Description for ' + s.text, identity_ids=['identity'],
                        relevance=.95, narrative_importance=.9, novelty=.9, readability=.9)))
            return dict(continuity_bible=[dict(entity_id=e.id, description=e.description, wardrobe_states={}, prop_designs=[]) for e in source.entities], beats=beats)

        diag = {}
        script, _ = ev.plan(source, None, noisy_batches, diag)
        plan_beats = script.event_plan['beats']
        self.assertEqual(len(plan_beats), 10)
        self.assertEqual([b['section_id'] for b in plan_beats], [s.id for s in source.sentences])

if __name__=='__main__':unittest.main()
