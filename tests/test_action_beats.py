"""Narrative regression cases; names are fixture data, not planner branches."""
import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from agent.news_models import Entity, Sentence, Script
from agent.editorial.visuals import plan_visuals
from agent.editorial.assets import acquire
from agent.cutout_processor import CutoutProcessor
from tests.news_fixtures import subject_image
import config
import threading


def fixture(lines, people):
    entities=[Entity(id=name.lower(),name=name,kind=kind,identity='fictional',description=description)
              for name,kind,description in people]
    sentences=[Sentence(id=f's{i}',text=line,phrase=line,claim_ids=['fixture'],role='hook' if i==0 else 'development',
                        entity_ids=[e.id for e in entities if e.name.casefold() in line.casefold()])
               for i,line in enumerate(lines)]
    return Script(summary='Action fixture',narration=' '.join(lines),entities=entities,sentences=sentences)


class ActionBeatTests(unittest.TestCase):
    def test_restraint_state_persists_through_exposition_until_release(self):
        script=fixture(['Mira was a guard.', 'Mira was bound in a white ribbon.',
                        'Mira remained in the hall.', 'Mira broke free from the ribbon.', 'Mira stood outside.'],
                       [('Mira','person','Blue tunic, brown hair, standing')])
        planned,_=plan_visuals(script)
        self.assertEqual(planned.sentences[1].entity_ids[0],planned.sentences[2].entity_ids[0])
        self.assertNotEqual(planned.sentences[2].entity_ids[0],planned.sentences[3].entity_ids[0])
        self.assertEqual(planned.sentences[4].entity_ids,['mira'])

    def test_semantic_word_index_errors_do_not_duplicate_guard_actions(self):
        script=fixture(['Mira was a worker.', 'Mira rolled a boulder uphill, only for it to tumble back down.'],
                       [('Mira','person','Blue tunic, brown hair, standing')])
        response={'subjects':[],'sections':[{'sectionId':'s0','cues':[{'entityId':'mira','anchor':'Mira'}]},
            {'sectionId':'s1','cues':[{'entityId':'mira','anchor':'Mira'}],'events':[
                {'start_word':3,'end_word':7,'verb':'roll','actor_ids':['mira'],'visual_goal':'Roll the boulder uphill'},
                {'start_word':8,'end_word':12,'verb':'tumble','actor_ids':['mira'],'visual_goal':'Boulder rolling back down','motion_intent':'downhill'}]}]}
        planned,_=plan_visuals(script,llm=MagicMock(side_effect=[response,{'supported':True,'problems':[]}]))
        actions=[b for b in planned.narrative_plan.beats if b.required_action_visible]
        self.assertEqual(len(actions),2)
        self.assertEqual([b.start_word for b in actions],[1,9])
        self.assertFalse(actions[1].contact_required)
    def test_one_sentence_preserves_two_causal_states_and_exact_spans(self):
        script=fixture(['Mira was a queen.', 'She pushed a boulder uphill, only for it to tumble back down the hill.'],
                       [('Mira','person','Purple tunic and dark braid, standing')])
        planned,rows=plan_visuals(script)
        actions=[b for b in planned.narrative_plan.beats if b.required_action_visible]
        self.assertEqual([b.verb for b in actions],['uphill_push','downhill_return'])
        self.assertNotEqual(actions[0].asset_ids,actions[1].asset_ids)
        self.assertTrue(all(b.identity_reference_ids==['mira'] for b in actions))
        for beat in actions:
            self.assertEqual(script.narration[beat.start_char:beat.end_char],beat.text)
        planned.narrative_plan.validate_script(planned)
        self.assertEqual(len(rows[1]['cues']),2)

    def test_action_outside_myth_examples_and_generic_identity(self):
        script=fixture(['A worker stood beside a door.', 'The worker pulled the door open.'],
                       [('worker','person','Anonymous worker with blue jacket, standing')])
        script.entities[0].identity='generic'
        planned,_=plan_visuals(script)
        self.assertTrue(planned.sentences[1].entity_ids[0].startswith('action-'))

    def test_negation_and_same_event_do_not_create_duplicate_images(self):
        script=fixture(['Mira stood beside a ribbon.', 'The ribbon was impossible to break.', 'The ribbon was tied and tightened around Mira.'],
                       [('Mira','person','Purple tunic, standing')])
        planned,_=plan_visuals(script)
        actions=[b for b in planned.narrative_plan.beats if b.required_action_visible]
        self.assertEqual([b.verb for b in actions],['binding'])

    def test_late_director_cannot_replace_or_move_action(self):
        from agent.editorial.director import baseline,validate_direction,VisualSettings
        script=fixture(['Mira stood still.', 'Mira pushed a boulder uphill.'],
                       [('Mira','person','Purple tunic, standing')])
        planned,rows=plan_visuals(script)
        direction=baseline(planned,rows,VisualSettings())
        validate_direction(direction,planned,VisualSettings())
        direction.cues[-1].startWord=0;direction.cues[-1].endWord=1;direction.cues[-1].phrase='Mira'
        with self.assertRaisesRegex(ValueError,'Required action'):
            validate_direction(direction,planned,VisualSettings())

    def test_structured_semantics_cover_verbs_outside_offline_vocabulary(self):
        script=fixture(['Mira stood on the pier.', 'Mira boarded the vessel.'],
                       [('Mira','person','Purple tunic, dark braid, standing')])
        response={'subjects':[],'sections':[
            {'sectionId':'s0','cues':[{'entityId':'mira','anchor':'Mira'}]},
            {'sectionId':'s1','cues':[{'entityId':'mira','anchor':'Mira'}],'events':[
                {'start_word':1,'end_word':4,'verb':'board_vessel','actor_ids':['mira'],'target_ids':[],
                 'visual_goal':'Mira stepping aboard the narrated vessel','result_state':'aboard the vessel','priority':.9}]}]}
        llm=MagicMock(side_effect=[response,{'supported':True,'problems':[]}])
        planned,_=plan_visuals(script,llm=llm)
        self.assertEqual(planned.narrative_plan.extraction,'semantic_with_deterministic_guard')
        action=planned.narrative_plan.beats[-1]
        self.assertEqual(action.verb,'board_vessel')
        self.assertEqual(action.actor_ids,['mira'])
        self.assertTrue(action.asset_ids[0].startswith('action-'))
        self.assertIn('semantic_events_to_verify',llm.call_args.args[1])

    def test_interaction_states_replace_portrait_without_rewriting_words(self):
        lines=['Fenrir was a fearsome wolf.', 'Tyr placed his hand inside Fenrir’s jaws.',
               'The ribbon tightened around Fenrir.', 'Fenrir bit Tyr’s hand.']
        script=fixture(lines,[('Fenrir','animal','Large charcoal wolf, silver muzzle, red eyes, standing'),
                              ('Tyr','person','Norse god with brown armor and braided hair, standing'),
                              ('ribbon','object','White magical ribbon')])
        audit={};planned,rows=plan_visuals(script,diagnostics=audit)
        self.assertEqual(planned.narration,script.narration)
        self.assertEqual([x['kind'] for x in audit['visualPlan']['actionBeats']],['hand_contact','binding','bite'])
        for sentence,row in zip(planned.sentences[1:],rows[1:]):
            self.assertTrue(sentence.entity_ids[0].startswith('action-'))
            self.assertEqual(row['cues'][0]['entityId'],sentence.entity_ids[0])
            self.assertNotIn('fenrir',sentence.entity_ids)
        self.assertEqual(planned.sentences[0].entity_ids,['fenrir'])

    def test_uphill_and_return_are_distinct_visual_states(self):
        lines=['Sisyphus was a king.', 'Sisyphus pushed a boulder uphill.',
               'The boulder rolled back down the hill as Sisyphus watched.']
        script=fixture(lines,[('Sisyphus','person','Ancient king in a purple tunic and gold cloak')])
        planned,_=plan_visuals(script)
        self.assertEqual(planned.sentences[0].entity_ids,['sisyphus'])
        self.assertNotEqual(planned.sentences[1].entity_ids[0],planned.sentences[2].entity_ids[0])
        self.assertTrue(all(s.entity_ids[0].startswith('action-') for s in planned.sentences[1:]))

    def test_broad_semantic_span_cannot_swallow_a_different_guarded_event(self):
        from agent.editorial.action_beats import ensure_action_coverage
        script=fixture(['Mira pushed a boulder uphill, only for it to tumble back down.'],
                       [('Mira','person','Purple tunic, standing')])
        audit={'semanticEvents':{'s0':[{'start_word':1,'end_word':13,'verb':'uphill_push',
            'actor_ids':['mira'],'visual_goal':'Mira pushing the boulder uphill'}]}}
        planned,_=ensure_action_coverage(script,[{'cues':[{'entityId':'mira','anchor':'Mira','startWord':0}]}],audit)
        actions=[b for b in planned.narrative_plan.beats if b.required_action_visible]
        self.assertEqual([b.verb for b in actions],['uphill_push','downhill_return'])
        self.assertLessEqual(actions[0].end_word,actions[1].start_word)
        self.assertNotEqual(actions[0].asset_ids,actions[1].asset_ids)

    def test_existing_suitable_variant_is_reused(self):
        script=fixture(['Mira stood still.', 'Mira pushed a boulder uphill.'],
                       [('Mira','person','Purple tunic, standing')])
        action=Entity(id='mira-action',name='Mira',kind='person',identity='fictional',
                      description='Mira visibly pushing a boulder uphill in her purple tunic')
        script.entities.append(action)
        script.sentences[1].entity_ids=['mira-action']
        audit={};planned,_=plan_visuals(script,diagnostics=audit)
        self.assertEqual(planned.sentences[1].entity_ids,['mira-action'])
        self.assertEqual(audit['visualPlan']['actionBeats'][0]['decision'],'reuse_action_variant')

    def test_action_generation_uses_established_cutout_as_reference(self):
        script=fixture(['Mira stood still.', 'Mira pushed a boulder uphill.'],
                       [('Mira','person','Purple tunic, dark hair, standing')])
        planned,_=plan_visuals(script)
        generator=MagicMock()
        async def create(prompt,path,reference=None):
            subject_image('mira').save(path)
            return 'fixture'
        generator.subject=AsyncMock(side_effect=create)
        generator.real_subject=AsyncMock(side_effect=create)
        review=MagicMock(return_value={'subjectMatch':True,'usable':True,'geometricPlaceholder':False,
            'contextAppropriate':True,'subjectConfidence':.9,'actionVisible':True,
            'contactVisible':True,'portraitOnly':False,'recognizable':True,'sameClothingOrFur':True})
        with tempfile.TemporaryDirectory() as root,patch('agent.editorial.vision.VisualReview',return_value=review),\
             patch.object(config,'NEWS_IDENTITY_IMAGE_CACHE',Path(root)/'image-cache'),\
             patch.object(config,'NEWS_CUTOUT_CACHE',Path(root)/'cutout-cache'):
            _,assets=acquire(planned,Path(root),processor=CutoutProcessor(segmenter=lambda image,model:image),
                             image_generator=generator,visual_review=review)
            self.assertEqual(len(assets),2)
            self.assertEqual(generator.real_subject.call_count,1)
            self.assertTrue(Path(generator.real_subject.call_args.args[2].path).is_file())
            self.assertIn('identity-board',Path(generator.real_subject.call_args.args[2].path).name)

    def test_two_interactions_overlap_after_both_masters_are_ready(self):
        script=fixture(['Mira and Ivo were workers.', 'Mira pulled Ivo out of the doorway.', 'Ivo lifted Mira onto the platform.'],
                       [('Mira','person','Blue jacket, dark braid, standing'),('Ivo','person','Red jacket, gray hair, standing')])
        planned,_=plan_visuals(script)
        generator=MagicMock();masters=[];boards=[];barrier=threading.Barrier(2)
        async def portrait(prompt,path):
            subject_image('mira').save(path);masters.append(path);return 'fixture'
        async def action(prompt,path,reference):
            from PIL import Image
            self.assertEqual(len(masters),2)
            with Image.open(reference.path) as board:boards.append(board.size)
            barrier.wait(timeout=3)
            subject_image('mira').save(path);return 'fixture'
        generator.subject=AsyncMock(side_effect=portrait);generator.real_subject=AsyncMock(side_effect=action)
        review=MagicMock(return_value={'subjectMatch':True,'usable':True,'geometricPlaceholder':False,
            'contextAppropriate':True,'subjectConfidence':.9,'actionVisible':True,'contactVisible':True,
            'portraitOnly':False,'recognizable':True,'sameClothingOrFur':True})
        with tempfile.TemporaryDirectory() as root,patch.object(config,'EDITORIAL_ACTION_WORKERS',2),\
             patch.object(config,'NEWS_IDENTITY_IMAGE_CACHE',Path(root)/'images'),\
             patch.object(config,'NEWS_CUTOUT_CACHE',Path(root)/'mattes'):
            _,assets=acquire(planned,Path(root),processor=CutoutProcessor(segmenter=lambda image,model:image),
                             image_generator=generator,visual_review=review)
            self.assertEqual(len(assets),4)
            self.assertEqual(boards,[(1024,1024),(1024,1024)])

    def test_degraded_label_never_counts_as_action_coverage(self):
        script=fixture(['Mira stood still.', 'Mira pushed a boulder uphill.'],
                       [('Mira','person','Purple tunic, standing')])
        planned,_=plan_visuals(script)
        report=planned.narrative_plan.assess_assets([],{'assets':[]})
        self.assertEqual(report['reviewedActionCoverage'],0)
        self.assertFalse(report['acceptancePassed'])

    def test_independent_context_wait_does_not_block_a_ready_action(self):
        script=fixture(['Mira stood still.', 'Clouds gathered overhead.', 'Mira lifted a box.'],
                       [('Mira','person','Blue jacket, standing'),('Clouds','object','Isolated white clouds')])
        planned,_=plan_visuals(script);started=threading.Event();generator=MagicMock()
        async def subject(prompt,path):
            if 'clouds' in prompt.split('Story context,')[0].lower():
                self.assertTrue(started.wait(3),'Context generation blocked the ready action')
            subject_image('mira').save(path);return 'fixture'
        async def action(prompt,path,reference):
            started.set();subject_image('mira').save(path);return 'fixture'
        generator.subject=AsyncMock(side_effect=subject);generator.real_subject=AsyncMock(side_effect=action)
        review=MagicMock(return_value={'subjectMatch':True,'usable':True,'geometricPlaceholder':False,
            'contextAppropriate':True,'subjectConfidence':.9,'actionVisible':True,'contactVisible':True,
            'portraitOnly':False,'recognizable':True,'sameClothingOrFur':True})
        with tempfile.TemporaryDirectory() as root,patch.object(config,'EDITORIAL_ACTION_WORKERS',2),\
             patch.object(config,'NEWS_IDENTITY_IMAGE_CACHE',Path(root)/'images'),\
             patch.object(config,'NEWS_CUTOUT_CACHE',Path(root)/'mattes'):
            acquire(planned,Path(root),processor=CutoutProcessor(segmenter=lambda image,model:image),image_generator=generator,visual_review=review)
        self.assertTrue(started.is_set())

    def test_high_priority_action_beats_compile_without_conflicting_scale_transitions(self):
        from agent.editorial.planner import build
        from agent.editorial.director import direct, VisualSettings
        from agent.editorial.models import Asset, Entity as EditorialEntity, Word, Section
        script=fixture([
            'Mira and Ivo stood on the platform.',
            'When the cord was tightened around struggling Mira, she bit Ivo on the hand.',
        ],[('Mira','person','Blue jacket, dark braid, standing'),('Ivo','person','Red jacket, gray hair, standing')])
        planned,cues=plan_visuals(script)
        words=[]; sections=[]; t=0.0
        for s in planned.sentences:
            s_start=t; wids=[]
            for idx, tok in enumerate(s.text.split()):
                wid=f'{s.id}-w{idx}'; wids.append(wid)
                words.append(Word(id=wid,sectionId=s.id,text=tok,start=round(t,2),end=round(t+0.32,2),provenance='provider',confidence=0.99))
                t+=0.34
            sections.append(Section(id=s.id,text=s.text,start=round(s_start,2),end=round(t,2),wordIds=wids))
        assets=[Asset(id=f'asset-{e.id}',entityId=e.id,role='portrait' if e.kind=='person' else 'object',path=f'/tmp/{e.id}.png',originalPath=f'/tmp/{e.id}.png',width=512,height=512,alpha=True,source='test',license='test',attribution='test',subject=e.name,factual=False,fallback='test',confidence=0.9,preparation='trimmed_alpha',sha256='0'*64) for e in planned.entities]
        entities=[EditorialEntity(id=e.id,name=e.name,identity=e.identity,source='test',assetIds=[f'asset-{e.id}']) for e in planned.entities]
        direction=direct(planned,words,cues,settings=VisualSettings())
        with tempfile.TemporaryDirectory() as root, patch('agent.news_audio.probe_duration', return_value=round(t+0.5,2)):
            audio=Path(root)/'audio.wav'; audio.write_bytes(b'RIFF')
            timeline=build(planned,words,sections,entities,assets,audio,Path(root),'test-job',{},visual_cues=cues,direction=direction,visual_settings=VisualSettings())
            self.assertTrue(len(timeline.beats)>=2)


if __name__=='__main__':unittest.main()
