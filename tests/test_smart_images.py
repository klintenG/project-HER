"""Offline policy contracts: no live models, tokens or billable validation."""
import asyncio
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from PIL import Image
from agent.editorial.asset_planner import finalize, generation_report
from agent.editorial.image_policy import ImagePolicy, negative_constraints, scene_prompt
from agent.editorial.images import EditorialImages
from agent.editorial import event_storyboard as ev
from agent.news_models import Entity, Script, Sentence, NewsError
from utils.image_models import build_input
import config

LINES=[
 'Sisyphus was a mortal king, remembered for his cleverness and pride.',
 'Zeus ruled above him, watching the affairs of gods and mortals.',
 'A massive boulder would become the instrument of the king’s punishment.',
 'A steep mountain rose above the dark and silent underworld.',
 'His royal crown recalled the authority he had once enjoyed.',
 'His empty throne stood as a reminder of his vanished power.',
 'Far away, the city he had ruled continued without him.',
 'Zeus seized Sisyphus by the wrist and confronted the defiant king.',
 'Sisyphus pressed both hands against the boulder and pushed it uphill.',
 'At the summit, the boulder slipped away and rolled back down.',
 'Every time, the promise of an ending dissolved into another beginning.',
 'The punishment was measured in repetition, rather than passing years.',
 'Hope and exhaustion became the two sides of the same struggle.',
 'And still, he faced the thought of doing it all again.']


def sample():
    masters=[Entity(id='sisyphus',name='Sisyphus',kind='person',identity='fictional',description='A muscular middle-aged Greek king, curly brown hair, short beard, ochre tunic and leather sandals'),Entity(id='zeus',name='Zeus',kind='person',identity='fictional',description='A tall elderly Greek god, long white hair and beard, white robe with gold trim')]
    ss=[Sentence(id=f's{i}',text=t,claim_ids=['fiction'],entity_ids=[m.id for m in masters],phrase=' '.join(t.split()[:4]),role='development') for i,t in enumerate(LINES)]
    source=Script(summary='Sisyphus: a myth of repetition and a punishment imposed by Zeus',narration=' '.join(LINES),sentences=ss,entities=masters)
    beats=[]
    subjects=['Sisyphus','Zeus','boulder','mountain','crown','throne','city']
    for i,s in enumerate(ss):
        refs=['sisyphus'] if i in (0,8,9) else ['zeus'] if i==1 else ['sisyphus','zeus'] if i==7 else []
        role='character_intro' if i<2 else 'object_detail' if i in (2,4,5) else 'location' if i in (3,6) else 'interaction' if i==7 else 'action_tableau' if i in (8,9) else 'timeline'
        beats.append(dict(beat_id=f'b{i}',section_id=s.id,narration_excerpt=s.text,event_type='action' if 7<=i<=9 else 'context',actor_ids=refs,verb=['seize','push','roll'][i-7] if 7<=i<=9 else 'reflect',object_ids=[],setting='ancient Greek myth',visual_intent=s.text,must_show=[s.text],must_not_show=['extra people'],role=role,criticality='P0' if 7<=i<=9 else 'P2',confidence=.95,media_source='typography' if i>=10 else 'generated_scene',concept=dict(subject=subjects[i] if i<7 else 'Sisyphus and Zeus' if i==7 else 'Sisyphus pushing boulder' if i==8 else 'Boulder rolling away' if i==9 else 'Repetition',action=s.text,important_objects=['boulder'] if i in (8,9) else [],setting='ancient Greek myth',emotion='determined',state_change=s.text,state_before='before '+str(i),state_after='after '+str(i),visual_focus=s.text,description='Isolated editorial composition: '+s.text,identity_ids=refs,relevance=.95,narrative_importance=.25 if i>=10 else .95,novelty=.9,readability=.95)))
    for i,b in enumerate(beats):
        if i in (4,6,10,12):
            b.update(media_source='typography',role='comparison' if i in (4,6) else 'timeline')
            b['concept']['narrative_importance']=.25
        elif i in (11,13):
            b.update(media_source='reuse_cutouts',role='comparison' if i==11 else 'reaction',physical_action=False,actor_ids=['sisyphus'])
            b['concept'].update(identity_ids=['sisyphus'],narrative_importance=.25)
    reply={'continuity_bible':[dict(entity_id=m.id,description=m.description,wardrobe_states={'base':m.description},prop_designs=[]) for m in masters],'beats':beats}
    script,cues=ev.plan(source,None,lambda instruction,*_: {'accepted':True} if instruction.startswith('Audit event') else reply,{})
    return source,script,cues,reply


class SmartImageTests(unittest.TestCase):
    def test_fourteen_beat_sample(self):
        source,script,_,_=sample();plan=finalize(script)
        self.assertEqual(script.narration,source.narration)
        self.assertEqual(len(plan['beats']),14)
        self.assertEqual((plan['schnell_count'],plan['seedream_count']),(5,3))
        self.assertEqual(sum(b['mode']=='typography' for b in plan['beats']),4)
        self.assertAlmostEqual(plan['estimated_image_cost_usd'],.105)
        self.assertEqual(plan['status'],'ready')
        self.assertEqual(plan['typography_pacing']['positions'],[5,7,11,13])
        self.assertTrue(plan['typography_pacing']['passed'])
        self.assertEqual([b['mode'] for b in plan['beats'][-4:]],['typography','reuse','typography','reuse'])
        actions=[a for a in plan['assets'] if a['mode']=='seedream']
        self.assertEqual(actions[0]['reference_ids'],['sisyphus','zeus'])
        self.assertEqual(actions[1]['reference_ids'],['sisyphus'])
        self.assertEqual({a['id'] for a in plan['assets'] if a['mode']=='schnell'} & {'sisyphus','zeus'},{'sisyphus','zeus'})

    def test_consecutive_and_end_loaded_typography_are_rejected(self):
        from agent.editorial.visual_pacing import pacing_issues
        self.assertTrue(pacing_issues(['image']*10+['typography']*4))
        self.assertTrue(pacing_issues(['image']*8+['typography','image','typography','image','typography','image']))
        self.assertFalse(pacing_issues(['image','typography','image','image','typography','image']))

    def test_typography_variety_is_repeatable_and_advisory(self):
        from agent.editorial.visual_pacing import planning_guidance
        source,_,_,_=sample()
        first=planning_guidance(source)
        self.assertEqual(first,planning_guidance(source))
        variants={tuple(planning_guidance(source.model_copy(update={'narration':source.narration+f' Context {i}.'}))['suggested_section_ids']) for i in range(8)}
        self.assertGreater(len(variants),1)
        self.assertIn('equally suitable',first['selection_rule'])

    def test_asset_preflight_blocks_unspaced_typography_before_acquisition(self):
        _,script,_,_=sample()
        rows=script.sentence_storyboard
        script.sentence_storyboard=[r for r in rows if r['media_source']!='typography']+[r for r in rows if r['media_source']=='typography']
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(NewsError,'consecutive text scenes'):finalize(script,tmp)
            report=json.loads(Path(tmp,'asset_generation_plan.json').read_text())
            self.assertFalse(report['typography_pacing']['passed'])

    def test_budget_conflict_saved_before_any_api_calls(self):
        _,script,_,_=sample()
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'MAX_IMAGE_BUDGET_USD':'.01'}):
            with self.assertRaisesRegex(NewsError,'needs review'):finalize(script,tmp)
            self.assertEqual(json.loads(Path(tmp,'asset_generation_plan.json').read_text())['status'],'needs_review')

    def test_scene_specific_constraints_and_supported_parameters(self):
        prompt=scene_prompt('Greek myth','Sisyphus and Zeus','Zeus seizes his wrist',['person','animal','object'],['Sisyphus','Zeus'])
        for term in ('A. Story','B. Subject','C. Requested','D. Physical','E. Visual','F. Preservation','G. Negative','H. Output','two arms','species anatomy','geometry','Exactly 2','swapped'):
            self.assertIn(term,prompt)
        for model in ('black-forest-labs/flux-schnell','bytedance/seedream-4'):
            inputs=build_input(model,prompt,['ref1','ref2'] if 'seedream' in model else [],'3:4')
            self.assertNotIn('negative_prompt',inputs)
            if 'seedream' in model:
                self.assertEqual(inputs['image_input'],['ref1','ref2'])
                self.assertEqual(inputs['max_images'],1)
                self.assertEqual(inputs['sequential_image_generation'],'disabled')

    def test_unsafe_seedream_settings_fail(self):
        for env in ({'SEEDREAM_MAX_RETRIES':'1'},{'SEEDREAM_MAX_IMAGES':'2'},{'ENABLE_PREMIUM_FALLBACK':'true'},{'ACTION_IMAGE_MODEL':'vendor/unsupported-image-model'},{'MAX_IMAGE_BUDGET_USD':'nan'}):
            with patch.dict(os.environ,env),self.assertRaises(ValueError):ImagePolicy.load()

    def test_retry_costs_and_unknown_billing(self):
        p=ImagePolicy.load()
        report=generation_report([{'model_name':p.simple,'estimated_cost':.003,'retry_number':1},{'model_name':p.simple,'estimated_cost':.003,'retry_number':2},{'model_name':p.action,'estimated_cost':.03}],p)
        self.assertAlmostEqual(report['retry_usd'],.003)
        self.assertAlmostEqual(report['reserved_image_usd'],.036)
        self.assertIsNone(report['actual_charged_image_usd'])
        with self.assertRaises(NewsError):p.check(p.image_budget-.001,.003)

    def test_physical_action_cannot_be_typography(self):
        _,_,_,reply=sample()
        bad=next(b for b in reply['beats'] if b['section_id']=='s8').copy();bad['media_source']='typography'
        with self.assertRaises(ValueError):ev.EventSpec.model_validate(bad)

    def test_single_character_plan_is_smaller_without_padding_ratio(self):
        source,_,_,reply=sample()
        source=source.model_copy(update={'sentences':[next(s for s in source.sentences if s.id==sid) for sid in ('s0','s8')],'entities':[source.entities[0]]})
        for sentence in source.sentences:sentence.entity_ids=['sisyphus']
        source.narration=' '.join(s.text for s in source.sentences)
        reply['beats']=[next(b for b in reply['beats'] if b['section_id']==sid) for sid in ('s0','s8')];reply['continuity_bible']=reply['continuity_bible'][:1]
        planned,_=ev.plan(source,None,lambda instruction,*_: {'accepted':True} if instruction.startswith('Audit event') else reply,{})
        plan=finalize(planned)
        self.assertEqual((plan['schnell_count'],plan['seedream_count']),(1,1))
        self.assertTrue(any('ratio' in w for w in plan['warnings']))

    def test_simple_two_character_dialogue_reuses_both_masters(self):
        source,_,_,reply=sample()
        source=source.model_copy(update={'sentences':[next(s for s in source.sentences if s.id=='s7')]})
        source.narration=source.sentences[0].text
        text='Sisyphus and Zeus spoke face to face about the punishment.'
        source.sentences[0].text=text;source.narration=text
        b=next(b for b in reply['beats'] if b['section_id']=='s7');b.update(media_source='reuse_cutouts',criticality='P2',physical_action=False,narration_excerpt=text,verb='speak',event_type='conversation',must_show=['Two canonical characters facing each other'])
        b['concept'].update(action=text,description=text,visual_focus=text,state_after='The conversation continues')
        reply['beats']=[b]
        planned,_=ev.plan(source,None,lambda instruction,*_: {'accepted':True} if instruction.startswith('Audit event') else reply,{})
        plan=finalize(planned)
        self.assertEqual((plan['schnell_count'],plan['seedream_count']),(2,0))
        self.assertEqual(plan['beats'][0]['mode'],'reuse')
        self.assertIn('zeus',planned.sentence_storyboard[0]['secondary_entity_ids'])

    def test_acquisition_seedream_failure_does_not_regenerate(self):
        import shutil
        from agent.editorial.assets import acquire
        source,_,_,reply=sample()
        source=source.model_copy(update={'sentences':[next(s for s in source.sentences if s.id=='s8')],'entities':[source.entities[0]]})
        source.sentences[0].entity_ids=['sisyphus'];source.narration=source.sentences[0].text
        reply['beats']=[next(b for b in reply['beats'] if b['section_id']=='s8')];reply['continuity_bible']=reply['continuity_bible'][:1]
        planned,_=ev.plan(source,None,lambda instruction,*_: {'accepted':True} if instruction.startswith('Audit event') else reply,{})
        planned.asset_generation_plan=finalize(planned)
        class Processor:
            version='smart-fixture'
            def process(self,raw,cut,**kwargs):
                shutil.copyfile(raw,cut);return {},'fixture'
        def review(instruction,*args):
            if instruction.startswith('Check that this generated'):
                return dict(subjectMatch=True,usable=True,geometricPlaceholder=False,contextAppropriate=True,subjectConfidence=.99,problems=[])
            return dict(relevant=False,actionCorrect=False,objectsCorrect=True,portraitSubstitution=True,problems=['wrong action'])
        with tempfile.TemporaryDirectory() as tmp,patch.object(config,'REPLICATE_API_TOKEN','offline'),patch.object(config,'PARALLEL_ASSET_PIPELINE_V2',False),patch.object(config,'PROJECTHER_ALLOW_CRITICAL_EVENT_FALLBACK',False),patch.object(config,'IMAGE_FAILURE_POLICY','strict'):
            root=Path(tmp);ref=root/'fixture.png'
            from PIL import ImageDraw
            image=Image.new('RGBA',(320,400));ImageDraw.Draw(image).ellipse((40,40,280,360),fill=(100,80,60,255));image.save(ref)
            response=MagicMock(status_code=201);response.json.return_value={'id':'offline','status':'succeeded','output':['https://example.org/image.png']}
            client=MagicMock();client.post=AsyncMock(return_value=response)
            context=MagicMock();context.__aenter__=AsyncMock(return_value=client);context.__aexit__=AsyncMock(return_value=False)
            with patch.object(config,'NEWS_IDENTITY_IMAGE_CACHE',root/'cache'),patch('httpx.AsyncClient',return_value=context),patch('agent.news_research.fetch',return_value=(ref.read_bytes(),'https://example.org/image.png')):
                gen=EditorialImages(primary_count=2)
                gen.admission.wait=AsyncMock()
                with self.assertRaisesRegex(NewsError,'regeneration prohibited'):
                    acquire(planned,root/'assets',asset_mode='ai',image_generator=gen,processor=Processor(),visual_review=review)
            self.assertEqual(client.post.await_count,2) # one master, exactly one action
            self.assertEqual(sum('seedream-4' in call.args[0] for call in client.post.call_args_list),1)
            self.assertTrue((root/'assets'/'generation_cost_report.json').exists())

    def test_schnell_retry_reserves_budget_before_second_paid_request(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(config,'REPLICATE_API_TOKEN','offline'),patch.dict(os.environ,{'MAX_IMAGE_BUDGET_USD':'.005'}):
            root=Path(tmp);image=root/'fixture.png';Image.new('RGB',(32,32),'red').save(image)
            key='portrait';prefix=hashlib.sha256(key.encode()).hexdigest()[:20]
            plan={'assets':[{'id':key,'mode':'schnell','model':'black-forest-labs/flux-schnell','reference_ids':[]}]}
            response=MagicMock(status_code=201);response.json.return_value={'id':'schnell1','status':'succeeded','output':['https://example.org/image.png']}
            client=MagicMock();client.post=AsyncMock(return_value=response)
            context=MagicMock();context.__aenter__=AsyncMock(return_value=client);context.__aexit__=AsyncMock(return_value=False)
            gen=EditorialImages();gen.configure_plan(plan,root);gen.admission.wait=AsyncMock()
            with patch('httpx.AsyncClient',return_value=context),patch('agent.news_research.fetch',return_value=(image.read_bytes(),'https://example.org/image.png')):
                asyncio.run(gen._prediction_request('Canonical portrait',root/(prefix+'-generated-1.png'),None,'person'))
                with self.assertRaisesRegex(NewsError,'budget'):
                    asyncio.run(gen._prediction_request('Corrected full-body portrait with visible feet',root/(prefix+'-generated-2.png'),None,'person'))
            self.assertEqual(client.post.await_count,1)

    def test_seedream_is_one_post_with_both_refs_and_durable_duplicate_guard(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(config,'REPLICATE_API_TOKEN','offline-token'):
            root=Path(tmp);ref=root/'reference.png';Image.new('RGB',(32,32),'red').save(ref)
            key='action';filename=hashlib.sha256(key.encode()).hexdigest()[:20]+'-generated-1.png'
            plan={'assets':[{'id':key,'mode':'seedream','model':'bytedance/seedream-4','reference_ids':['sisyphus','zeus']}]}
            response=MagicMock(status_code=201);response.json.return_value={'id':'test1','status':'processing'}
            client=MagicMock();client.post=AsyncMock(return_value=response)
            completed=MagicMock(status_code=200);completed.json.return_value={'id':'test1','status':'succeeded','output':['https://example.org/image.png']}
            client.get=AsyncMock(return_value=completed)
            context=MagicMock();context.__aenter__=AsyncMock(return_value=client);context.__aexit__=AsyncMock(return_value=False)
            gen=EditorialImages();gen.configure_plan(plan,root);gen.admission.wait=AsyncMock()
            reference=SimpleNamespace(path=str(ref),paths=[str(ref),str(ref)])
            with patch('httpx.AsyncClient',return_value=context),patch('agent.news_research.fetch',return_value=(ref.read_bytes(),'https://example.org/image.png')):
                asyncio.run(gen._prediction_request('Action',root/filename,reference,'event'))
                with self.assertRaisesRegex(NewsError,'already reserved'):asyncio.run(gen._prediction_request('Action',root/filename,reference,'event'))
                resumed=EditorialImages();resumed.configure_plan(plan,root)
                with self.assertRaisesRegex(NewsError,'already reserved'):asyncio.run(resumed._prediction_request('Action',root/filename,reference,'event'))
            self.assertEqual(client.post.await_count,1)
            request=client.post.call_args.kwargs['json']['input']
            self.assertEqual(len(request['image_input']),2)
            self.assertEqual(request['max_images'],1)
            self.assertEqual(client.get.await_count,1)
            self.assertIn('/predictions/test1',client.get.call_args.args[0])
            self.assertEqual(json.loads((root/'image_prediction_ledger.json').read_text())[0]['prediction_id'],'test1')

    def test_action_importance_cross_check_and_pipeline_overrun_tolerance(self):
        source,script,_,_=sample()
        # Create a script with 7 action beats like the user's Sisyphus story
        modified = script.model_copy(deep=True)
        # Set all beats to generated_scene action_tableau
        for idx, row in enumerate(modified.sentence_storyboard):
            if idx < 7:
                row['media_source'] = 'generated_scene'
                row['shot_role'] = 'action_tableau'
                row['continuity_references'] = ['sisyphus', 'zeus']
        with tempfile.TemporaryDirectory() as tmp:
            # Production pipeline calls finalize with enforce=False (not allow_overrun)
            plan = finalize(modified, tmp, enforce=False)
            self.assertEqual(plan['status'], 'ready')
            self.assertGreater(plan['seedream_count'], 0)
            self.assertTrue(any('actions' in w or 'retained' in w for w in plan['warnings']))


if __name__=='__main__':unittest.main()
