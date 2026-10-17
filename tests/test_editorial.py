"""Boundary, compatibility and integration tests; no provider/LLM calls."""
import copy
import hashlib
import json
import math
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,MagicMock
import numpy as np
from agent.editorial.models import Timeline,Layer,Event,Bounds,frames,digest
from agent.editorial.audio import remap_words,refine_silence_edges,write_wave
from agent.editorial.pipeline import check_configuration
from agent.news_models import NewsError,Manifest

ROOT=Path(__file__).resolve().parents[1]

def semantic_script():
    """Production failure shape: headline emphasis differs from spoken tokens."""
    from agent.news_models import Script,Sentence
    rows=[
        Sentence(id='s1',text='In software engineering, these agents now assist with requirements, code generation, and testing.',claim_ids=['c1'],phrase='Software engineering agents assisting',role='hook',emphasis=['software','engineering']),
        Sentence(id='s2',text='These systems connect human researchers with code, physics, and databases to accelerate innovation.',claim_ids=['c2'],phrase='Connecting researchers with tools',role='close',emphasis=['researchers','tools']),
    ]
    return Script(summary='AI agents',narration=' '.join(s.text for s in rows),sentences=rows)


class EditorialTests(unittest.TestCase):
    def test_remote_speech_and_visual_sourcing_overlap_without_changing_results(self):
        from agent.editorial.pipeline import prepare_parallel_media
        visual_started=threading.Event();speech_started=threading.Event()
        def visuals(cancel):
            visual_started.set()
            self.assertTrue(speech_started.wait(2))
            self.assertFalse(cancel.is_set())
            return ('verified-cutout',)
        def speech():
            speech_started.set()
            self.assertTrue(visual_started.wait(2))
            return 'approved-audio'
        timings={}
        self.assertEqual(prepare_parallel_media(speech,visuals,diagnostics=timings),('approved-audio',('verified-cutout',)))
        self.assertGreaterEqual(timings['overlapSeconds'],0)
        self.assertIn('cutoutsSeconds',timings)

    def test_speech_failure_cancels_unfinished_visual_work(self):
        from agent.editorial.pipeline import prepare_parallel_media
        started=threading.Event();stopped=threading.Event()
        def visuals(cancel):
            started.set()
            while not cancel.is_set():time.sleep(.01)
            stopped.set()
        def speech():
            self.assertTrue(started.wait(2))
            raise NewsError('Speech unavailable')
        with self.assertRaisesRegex(NewsError,'Speech unavailable'):
            prepare_parallel_media(speech,visuals)
        self.assertTrue(stopped.is_set())

    def test_semantic_emphasis_resolves_original_tokens_and_phrases(self):
        from agent.editorial.planner import semantic_plan,spoken_emphasis
        script=semantic_script();diagnostics={}
        rows=semantic_plan(script)
        for row in rows:row['setupWords']=5
        rows[0]['emphasisWords']=['SOFTWARE ENGINEERING','requirements']
        rows[1]['emphasisWords']=['innovation']
        llm=MagicMock(return_value={'beats':rows})
        plan=semantic_plan(script,llm,diagnostics)
        self.assertEqual(plan[0]['emphasisWords'],['software','engineering,','requirements,'])
        self.assertEqual(plan[1]['emphasisWords'],['innovation.'])
        self.assertEqual(diagnostics['semanticPlan']['mode'],'llm');llm.assert_called_once()
        self.assertEqual(llm.call_args.args[1]['spokenWords']['s1'],script.sentences[0].text.split())
        original='“Rao’s” AI-powered lab can’t report -5 or C++ results.'
        matched,missing=spoken_emphasis(original,["rao's","AI-powered LAB","can't",'-5','C++','cant','5','AI powered'])
        self.assertEqual(matched,['“Rao’s”','AI-powered','lab','can’t','-5','C++'])
        self.assertEqual(missing,['cant','5','AI powered'])

    def test_semantic_plan_retries_invented_emphasis_with_actionable_error(self):
        from agent.editorial.planner import semantic_plan
        script=semantic_script();diagnostics={};valid=semantic_plan(script)
        for row in valid:row['setupWords']=5
        invalid=copy.deepcopy(valid);invalid[1]['emphasisWords']=['tools']
        llm=MagicMock(side_effect=[{'beats':invalid},{'beats':valid}])
        plan=semantic_plan(script,llm,diagnostics)
        self.assertEqual(llm.call_count,2)
        self.assertIn('s2',llm.call_args.args[1]['previousErrors'][0])
        self.assertIn('tools',llm.call_args.args[1]['previousErrors'][0])
        self.assertEqual(diagnostics['semanticPlan']['mode'],'llm')
        self.assertEqual(plan[1]['emphasisWords'],['researchers'])

    def test_invalid_optional_semantic_plans_use_safe_editorial_layouts(self):
        from agent.editorial.planner import semantic_plan
        script=semantic_script();original=script.model_dump();valid=semantic_plan(script)
        for row in valid:row['setupWords']=5
        changes={
            'invented emphasis':lambda rows:rows[1].update(emphasisWords=['tools']),
            'noncontiguous phrase':lambda rows:rows[0].update(emphasisWords=['software testing']),
            'nonstring emphasis':lambda rows:rows[0].update(emphasisWords=[{'word':'software'}]),
            'unknown template':lambda rows:rows[0].update(template='glitter'),
            'unresolved section':lambda rows:rows[0].update(sectionId='missing'),
            'boolean split':lambda rows:rows[0].update(setupWords=True),
        }
        for name,change in changes.items():
            with self.subTest(name=name):
                rows=copy.deepcopy(valid);change(rows);diagnostics={}
                llm=MagicMock(side_effect=lambda *args:{'beats':copy.deepcopy(rows)})
                plan=semantic_plan(script,llm,diagnostics)
                self.assertEqual(llm.call_count,2)
                self.assertEqual(diagnostics['semanticPlan']['mode'],'deterministic_fallback')
                self.assertEqual(len(diagnostics['semanticPlan']['errors']),2)
                self.assertTrue(diagnostics['semanticPlan']['warnings'])
                self.assertEqual([r['template'] for r in plan],['process','conclusion'])
                self.assertEqual(plan[0]['emphasisWords'],['software','engineering,'])
                self.assertEqual(plan[1]['emphasisWords'],['researchers'])
                self.assertEqual(script.model_dump(),original)

    def test_offline_semantic_plan_omits_only_unspoken_headline_emphasis(self):
        from agent.editorial.planner import semantic_plan
        diagnostics={};plan=semantic_plan(semantic_script(),diagnostics=diagnostics)
        self.assertEqual(plan[1]['emphasisWords'],['researchers'])
        self.assertEqual(diagnostics['semanticPlan']['baselineRepairs'],[{'sectionId':'s2','omittedEmphasis':['tools']}])
        self.assertEqual(diagnostics['semanticPlan']['attempts'],0)

    def test_subject_first_named_late_in_conclusion_has_no_early_transfer(self):
        from agent.news_models import Script,Sentence,Entity as ScriptEntity
        from agent.editorial.models import Word,Section,Entity
        from agent.editorial.assets import prepare
        from agent.editorial.planner import build
        from PIL import Image
        sentences=[
            Sentence(id='s1',text='Opening reports describe the process.',claim_ids=['c1'],phrase='The process',role='hook'),
            Sentence(id='s2',text='The final illustration shows a Researcher.',claim_ids=['c2'],entity_ids=['researcher'],phrase='A researcher',role='close'),
        ]
        researcher=ScriptEntity(id='researcher',name='Researcher',kind='person',description='A generic illustrated researcher')
        script=Script(summary='Illustrative process',narration=' '.join(s.text for s in sentences),sentences=sentences,entities=[researcher])
        cursor=0;words=[];sections=[]
        # Explicit unit-test timing isolates a subject introduced late, rather
        # than testing a live speech provider or approximating production timing.
        for sentence in sentences:
            start=cursor;ids=[]
            for i,text in enumerate(sentence.text.split()):
                wid=sentence.id+'-w'+str(i);ids.append(wid)
                words.append(Word(id=wid,sectionId=sentence.id,text=text,start=cursor+.1,end=cursor+.3,confidence=1,provenance='provider'))
                cursor+=.4
            sections.append(Section(id=sentence.id,text=sentence.text,start=start,end=cursor,wordIds=ids,sourceIds=sentence.claim_ids));cursor+=.12
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);audio=root/'master.wav';write_wave(audio,np.full(math.ceil(cursor)*48000,.01))
            photo=root/'fixture-photo.png';Image.new('RGB',(240,360),'#aaccee').save(photo)
            asset=prepare(researcher,photo,root,source='Unit-test image',license='Test fixture',attribution='Test fixture',role='photo',factual=False)
            asset=asset.model_copy(update={'subject':'A deliberately long stock alt description of a researcher standing in a laboratory observing a digital interface'})
            entity=Entity(id=researcher.id,name=researcher.name,identity='generic',assetIds=[asset.id],source=asset.source)
            m=build(script,words,sections,[entity],[asset],audio,root,'late-conclusion-test')
            subject=next(layer for layer in m.layers if layer.id=='entity-researcher')
            self.assertEqual(subject.startFrame,frames(words[-1].start))
            self.assertFalse(any(event.type=='transfer' and subject.id in event.targetIds for event in m.events))
            self.assertTrue(any(event.type=='settle' and subject.id in event.targetIds for event in m.events))
            label=next(layer for layer in m.layers if layer.id==subject.id+'-label')
            self.assertEqual(label.phrase.label,'Researcher')
            Timeline.model_validate(m.model_dump())

    def test_sample_offsets_do_not_accumulate_frame_rounding(self):
        rows=[dict(text='word',start=.4,end=.8,confidence=.9,provenance='provider')]
        cursor=0
        for i in range(73):
            offset=cursor/48000
            w=remap_words(rows,.25,offset,'s'+str(i))[0]
            self.assertAlmostEqual(w.start,offset+.15)
            self.assertLessEqual(abs(frames(w.start)/30-w.start),1/60)
            cursor+=42113+5760
        self.assertNotEqual(frames(cursor/48000),73*frames((42113+5760)/48000))

    def test_silence_refinement_keeps_word_and_consonant_handle(self):
        data=np.zeros(48000);data[24000:36000]=.08
        rows=refine_silence_edges([dict(text='test',start=0,end=1)],data)
        self.assertAlmostEqual(rows[0]['start'],.49)
        self.assertAlmostEqual(rows[0]['end'],.77)

    def test_unsupported_backend_fails_before_providers(self):
        with self.assertRaisesRegex(NewsError,'requires Remotion'):check_configuration('moviepy','vertical','editorial','stock')
        with self.assertRaisesRegex(NewsError,'vertical only'):check_configuration('remotion','square','editorial','stock')
        from agent.news_pipeline import run_news
        with tempfile.TemporaryDirectory() as tmp,patch('agent.news_script.NewsLLM') as llm:
            result=run_news('A supplied account',visual_preset='reference_editorial',renderer='moviepy',output_dir=Path(tmp))
        self.assertFalse(result.success);llm.assert_not_called()

    def test_news_dispatch_is_opt_in_and_preserves_settings(self):
        from agent.news_pipeline import run_news
        with patch('agent.editorial.pipeline.run_editorial',return_value='editorial') as run:
            value=run_news('story',visual_preset='reference_editorial',tts_provider='edge_tts',music=False,subtitle_mode='complete',asset_mode='local',local_assets='registry.json')
        self.assertEqual(value,'editorial');self.assertEqual(run.call_args.kwargs['subtitle_mode'],'complete')
        self.assertEqual(run.call_args.kwargs['tts_provider'],'edge_tts');self.assertEqual(run.call_args.kwargs['local_assets'],'registry.json')

    def test_shared_contract_and_semantic_failures(self):
        from scripts.editorial_primitives import year
        year(True)
        path=ROOT/'output/reference_editorial_primitives/year-counter/editorial_manifest.json'
        source=json.loads(path.read_text());Timeline.model_validate(source)
        cases=[{'name':'valid year study','accept':True,'value':source}]
        changes={
          'unsupported action':lambda m:m['events'][0].update(type='glitter'),
          'unresolved target':lambda m:m['events'][0].update(targetIds=['absent']),
          'negative dimensions':lambda m:m['layers'][0]['bounds'].update(w=-10),
          'empty interval':lambda m:m['events'][0].update(endFrame=24),
          'exceeds composition':lambda m:m['events'][0].update(endFrame=150),
          'truncated master':lambda m:m['audio'][0].update(duration=12),
          'stale script':lambda m:m.update(scriptHash='0'*64),
          'unknown template':lambda m:m['beats'][0].update(template='random_card'),
          'unresolved word':lambda m:m['layers'][0]['phrase'].update(emphasis=['missing']),
          'wrong action target':lambda m:m['events'][0].update(type='object_action'),
          'unknown field':lambda m:m.update(arbitrary_css='display:none'),
          'invalid parent':lambda m:m['layers'][0].update(parentId='heading',anchor='entity'),
        }
        for name,change in changes.items():
            m=copy.deepcopy(source);change(m)
            with self.subTest(name=name),self.assertRaises(ValueError):Timeline.model_validate(m)
            cases.append({'name':name,'accept':False,'value':m})
        layer=Layer(id='l',role='object',startFrame=0,endFrame=120,bounds=Bounds(x=200,y=600,w=200,h=300)).model_dump()
        motion=[]
        def sample(kind,params,expected):
            event=Event(id='e',type=kind,startFrame=10,endFrame=30,targetIds=['l'],easing='linear',**params).model_dump()
            motion.append({'layer':layer,'event':event,'frame':20,'expected':expected})
        sample('focus_shift',{'scaleTo':1.28},{'scale':1.14})
        sample('transfer',{'dx':400,'dy':-60},{'x':200,'y':-30})
        sample('year_counter',{'fromValue':2000,'toValue':2026},{'value':2013})
        sample('object_action',{'angleFrom':-100,'angleTo':0},{'angle':-50})
        sample('map_separate',{'dx':80,'dy':40},{'x':-40,'y':-20})
        sample('representation_swap',{'assetId':'view-b'},{'swap':.5})
        sample('settle',{'scaleFrom':1.6,'scaleTo':1,'opacityFrom':0},{'scale':1.3,'opacity':.5})
        out=ROOT/'output/editorial_conformance.json';out.write_text(json.dumps({'cases':cases,'motion':motion}))
        result=subprocess.run(['node','remotion/check-editorial-contract.cjs',str(out)],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_cli_and_gradio_forward_new_preset(self):
        from click.testing import CliRunner
        import main
        from agent.orchestrator import PipelineResult
        result=PipelineResult(success=True)
        with patch('agent.orchestrator.AgentOrchestrator') as factory:
            factory.return_value.run.return_value=result
            out=CliRunner().invoke(main.cli,['generate','--content-mode','news','--text','Supplied story','--visual-preset','reference_editorial','--editorial-text','complete'])
        self.assertEqual(out.exit_code,0,out.output)
        self.assertEqual(factory.return_value.run.call_args.kwargs['visual_preset'],'reference_editorial')
        self.assertEqual(factory.return_value.run.call_args.kwargs['editorial_text'],'complete')
        self.assertEqual(factory.return_value.run.call_args.kwargs['editorial_assets'],'auto')
        import os
        with patch.dict(os.environ,{'GRADIO_ANALYTICS_ENABLED':'False'}):import app
        with patch('agent.orchestrator.AgentOrchestrator') as factory:
            factory.return_value.run.return_value=result
            app.generate_video('Supplied story','','informative','cinematic','vertical','karaoke','aria','fade',False,content_mode='news',renderer='remotion',visual_preset='reference_editorial',editorial_text='complete',progress=MagicMock())
        self.assertEqual(factory.return_value.run.call_args.kwargs['visual_preset'],'reference_editorial')
        self.assertEqual(factory.return_value.run.call_args.kwargs['editorial_text'],'complete')
        self.assertEqual(factory.return_value.run.call_args.kwargs['editorial_assets'],'auto')

    def test_flask_worker_forwards_actual_preset(self):
        import web_ui
        from agent.orchestrator import PipelineResult
        with web_ui.app.test_request_context('/'),patch('agent.news_script.NewsLLM'),patch('agent.news_pipeline.run_news',return_value=PipelineResult(errors=['fixture completion'])) as run:
            with patch('web_ui.threading.Thread') as thread:
                thread.side_effect=lambda target,**kwargs:SimpleNamespace(start=target)
                response=web_ui._start_news_job({'visual_preset':'reference_editorial','editorial_text':'complete','editorial_assets':'local','local_assets':'fixture.json'},'A supplied story')
        self.assertEqual(run.call_args.kwargs['visual_preset'],'reference_editorial')
        self.assertEqual(run.call_args.kwargs['subtitle_mode'],'complete')
        self.assertEqual(run.call_args.kwargs['local_assets'],'fixture.json')

    def test_full_pipeline_with_native_timestamp_provider_fixture(self):
        from tests.news_fixtures import FixtureLLM,FixtureTTS,SCRIPT,ACCOUNT,subject_image
        from agent.editorial.planner import semantic_plan
        from agent.news_pipeline import run_news
        from agent.editorial.render import stage
        class LLM(FixtureLLM):
            def __init__(self):
                super().__init__();self.classification_calls=0
            def __call__(self,instruction,data):
                if instruction.startswith('Classify'):
                    self.classification_calls+=1
                    result=super().__call__(instruction,data)
                    if self.classification_calls==1:result['kind']='reported'
                    return result
                if instruction.startswith('Propose'):
                    rows=semantic_plan(SCRIPT)
                    for row,s in zip(rows,SCRIPT.sentences):
                        row['setupWords']=min(5,len(s.text.split())-1);row['emphasisWords']=[]
                    # Invalid optional styling must not discard completed speech
                    # and assets or prevent the normal pipeline from rendering.
                    rows[0]['emphasisWords']=['unspoken invented emphasis']
                    return {'beats':rows}
                return super().__call__(instruction,data)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);registry={}
            for e in SCRIPT.entities:
                p=root/(e.id+'.png');subject_image(e.id).save(p)
                registry[e.name]={'path':str(p),'subject':e.name,'source':'offline fixture artwork','license':'test artwork','attribution':'test fixture','role':'portrait' if e.kind=='person' else 'object'}
            reg=root/'registry.json';reg.write_text(json.dumps(registry))
            def renderer(m,path,event=None,trace=None):
                Timeline.model_validate(m.model_dump());stage(m,root)
                return path,{'integratedLUFS':-15,'truePeakDBTP':-1.5}
            with patch('agent.editorial.pipeline.render',side_effect=renderer),patch('agent.editorial.pipeline.run'):
                result=run_news(ACCOUNT,output_dir=root,source_policy='supplied',visual_preset='reference_editorial',tts_provider='edge_tts',tts_engine=FixtureTTS(),llm=LLM(),asset_mode='local',local_assets=str(reg),music=False)
            self.assertTrue(result.success,result.errors)
            m=Timeline.model_validate_json((root/'editorial_manifest.json').read_text())
            self.assertTrue(all(w.provenance=='provider' for w in m.words))
            self.assertEqual(len(m.sections),4);self.assertGreater(len(m.beats),4)
            self.assertEqual(m.diagnostics['semanticPlan']['mode'],'deterministic')
            self.assertTrue(m.narrationDriven)
            self.assertIn('atomicStoryboard',m.diagnostics)
            classification=json.loads((root/'input_classification.json').read_text())
            self.assertEqual(classification['status'],'ready')
            self.assertEqual(len(classification['attempts']),2)
            self.assertEqual(classification['attempts'][0]['kind'],'reported')
            self.assertEqual(classification['attempts'][1]['resolvedKind'],'supplied_account')
            self.assertEqual(m.diagnostics['input']['basis'],'fictional')

if __name__=='__main__':unittest.main()
