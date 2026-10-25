"""Offline concurrency, diversity and durable timing regressions."""
import asyncio
import threading
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,MagicMock
import config
from agent.editorial.assets import acquire
from agent.editorial.images import EditorialImages
from agent.editorial.visuals import plan_visuals
from agent.news_models import Entity,Script,Sentence,NewsError
from tests import test_editorial_visuals as fixtures
story=fixtures.story


class ParallelAssetTests(unittest.TestCase):
    setUp=fixtures.EditorialVisualTests.setUp
    tearDown=fixtures.EditorialVisualTests.tearDown
    def test_network_work_overlaps_but_output_order_is_stable(self):
        from tests.news_fixtures import subject_image
        barrier=threading.Barrier(2)
        async def generate(prompt,path):
            barrier.wait(timeout=3)
            subject_image('mira').save(path)
            return 'replicate:fixture'
        generator=SimpleNamespace(subject=generate)
        entities=[Entity(id=n,name=n,kind='object',identity='generic',description=n) for n in ('Cup','Bowl')]
        script=story().model_copy(update={'entities':entities})
        with patch.object(config,'EDITORIAL_ASSET_WORKERS',2):
            result,assets=acquire(script,self.root/'parallel',image_generator=generator,visual_review=self.review)
        self.assertEqual([e.id for e in result],['Cup','Bowl'])
        self.assertEqual([a.subject for a in assets],['Cup','Bowl'])

    def test_failure_stops_queued_generation(self):
        calls=[]
        async def generate(prompt,path):
            calls.append(path)
            raise NewsError('Provider unavailable')
        entities=[Entity(id=str(i),name='Cup '+str(i),kind='object',identity='generic',description='cup') for i in range(8)]
        with patch.object(config,'EDITORIAL_ASSET_WORKERS',1),patch.object(config,'NEWS_ASSET_RETRIES',0):
            with self.assertRaisesRegex(NewsError,'Provider unavailable'):
                acquire(story().model_copy(update={'entities':entities}),self.root/'failed',image_generator=SimpleNamespace(subject=generate),visual_review=self.review)
        self.assertEqual(len(calls),1)


class PerformanceTests(unittest.TestCase):
    def test_shared_image_budget_is_atomic(self):
        from concurrent.futures import ThreadPoolExecutor
        generator=EditorialImages();generator.replicate_token='fixture'
        generator._prediction=MagicMock(side_effect=lambda *a:async_result())
        async def call():
            try:await generator.subject('cup',Path('/unused'));return True
            except NewsError:return False
        with patch.object(config,'EDITORIAL_MAX_SUPPORT_CALLS',1),ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:asyncio.run(call()),range(8)))
        self.assertEqual(sum(results),1)
        self.assertEqual(generator.support_calls,1)
        self.assertEqual(generator._prediction.call_count,1)

    def test_sparse_supported_plan_is_retained_if_diversity_repair_fails(self):
        script=story()
        text='Example Person walked past the cafe carrying a cup and a book before sitting at the table for lunch with coffee and a bowl of soup.'
        script=script.model_copy(update={'narration':text,'sentences':[script.sentences[0].model_copy(update={'text':text})]})
        plan={'subjects':[],'sections':[{'sectionId':'s1','cues':[{'entityId':'person','anchor':'Example Person'}]}]}
        llm=MagicMock(side_effect=[plan,{'supported':True},{}]);diagnostics={}
        result,cues=plan_visuals(script,llm=llm,diagnostics=diagnostics)
        self.assertEqual(result.narration,text)
        self.assertEqual(diagnostics['visualPlan']['mode'],'llm')
        self.assertEqual(diagnostics['visualPlan']['attempts'],2)
        self.assertTrue(diagnostics['visualPlan']['warnings'])
        self.assertIn('diversity_guidance',llm.call_args_list[0].args[1])

    def test_short_visual_plan_gets_one_bounded_diversity_retry(self):
        script=story()
        text=' '.join(['Example Person examined the cup bowl plate book lamp and clock in the room.']*15)
        script=script.model_copy(update={'narration':text,'sentences':[script.sentences[0].model_copy(update={'text':text})]})
        subjects=[{'id':'obj-'+str(i),'name':n,'kind':'object','description':'One '+n,'identity':'generic','reference_query':None,'exact_asset':None}
                  for i,n in enumerate(('cup','bowl','plate','book','lamp','clock'))]
        cues=[{'entityId':'person','anchor':'Example Person'},*[{'entityId':s['id'],'anchor':s['name']} for s in subjects]]
        plan={'subjects':subjects,'sections':[{'sectionId':'s1','cues':cues}]}
        llm=MagicMock(side_effect=[plan,{'supported':True},plan,{'supported':True}]);diagnostics={}
        result,_=plan_visuals(script,llm=llm,diagnostics=diagnostics)
        self.assertEqual(len(result.entities),7)
        self.assertEqual(diagnostics['visualPlan']['attempts'],2)
        self.assertEqual(llm.call_count,4)

    def test_clean_cutout_skips_lazy_morphology_variants(self):
        from PIL import Image
        from agent.cutout_processor import CutoutProcessor
        from tests.news_fixtures import subject_image
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);src=root/'opaque.png';dest=root/'cut.png'
            Image.new('RGBA',(200,300),(120,120,120,255)).save(src)
            clean=subject_image('mira')
            processor=CutoutProcessor(segmenter=lambda img,model:clean)
            with patch.object(config,'NEWS_CUTOUT_CACHE',root/'cache'), \
                 patch('agent.cutout_processor.prune_detached_components') as prune, \
                 patch('agent.cutout_processor.soft_edge_fade') as fade:
                _,method=processor.process(src,dest)
            self.assertTrue(method.startswith('rembg:'))
            prune.assert_not_called()
            fade.assert_not_called()

    def test_replicate_tts_batches_multiple_sentences_in_order(self):
        from agent.news_tts import NewsReplicateTTS,KOKORO
        from tests.test_news_tts import wav_bytes
        barrier=threading.Barrier(2)
        def predict(inputs):
            barrier.wait(timeout=3)
            return wav_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            points=[SimpleNamespace(index=0,narration='First sentence.'),SimpleNamespace(index=1,narration='Second sentence.')]
            with patch.object(config,'REPLICATE_API_TOKEN','fixture-token'), \
                 patch.object(config,'NEWS_TTS_CACHE',root/'cache'), \
                 patch.object(config,'NEWS_REPLICATE_MIN_INTERVAL',0):
                engine=NewsReplicateTTS(model=KOKORO)
                try:
                    with patch.object(engine,'_predict',side_effect=predict):
                        clips=engine.generate_narration(points,root/'out')
                finally:
                    engine._session.close()
            self.assertEqual([c.index for c in clips],[0,1])

    def test_prepare_caps_alpha_cutout_dimensions_to_640(self):
        from PIL import Image, ImageDraw
        from agent.editorial.assets import prepare
        from agent.news_models import Entity
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);src=root/'large_alpha.png'
            im=Image.new('RGBA',(1024,1024),(0,0,0,0))
            draw=ImageDraw.Draw(im)
            draw.rectangle((60,40,960,980),fill=(200,120,80,255))
            im.save(src)
            entity=Entity(id='hero',name='Hero',kind='person',description='Hero portrait',identity='fictional')
            asset=prepare(entity,src,root/'out',source='test',license='test',attribution='test')
            self.assertLessEqual(max(asset.width,asset.height),640)
            self.assertTrue(asset.alpha)

    def test_editorial_images_accepts_http_202_when_prefer_wait_expires(self):
        import asyncio
        from agent.editorial.images import EditorialImages
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'out.png'
            post_resp=SimpleNamespace(status_code=202,json=lambda:{'id':'pred_202_ok','status':'starting'})
            poll_resp=SimpleNamespace(status_code=200,json=lambda:{'id':'pred_202_ok','status':'succeeded','output':['https://replicate.delivery/pbxt/test.png']})
            client=MagicMock()
            async def fake_post(*a,**k):return post_resp
            async def fake_get(*a,**k):return poll_resp
            client.post=fake_post;client.get=fake_get
            cm=MagicMock()
            async def aenter(*a):return client
            async def aexit(*a):return False
            cm.__aenter__=aenter;cm.__aexit__=aexit
            with patch.object(config,'REPLICATE_API_TOKEN','fixture-token'), \
                 patch('httpx.AsyncClient',return_value=cm), \
                 patch('agent.news_research.fetch',return_value=(b'\x89PNG\r\n\x1a\nfake', 'https://replicate.delivery/pbxt/test.png')), \
                 patch('asyncio.sleep',return_value=None):
                gen=EditorialImages()
                provider=asyncio.run(gen.subject('test prompt',dest))
            self.assertEqual(provider,'replicate:black-forest-labs/flux-schnell')
            self.assertTrue(dest.is_file())

    def test_cutout_processor_segment_default_rembg_path_runs_cleanly(self):
        from PIL import Image
        import agent.cutout_processor as cp
        img=Image.new('RGBA',(64,64),(255,255,255,255))
        fake_session=MagicMock()
        with patch.dict(cp._SESSIONS,{},clear=True), \
             patch('rembg.new_session',return_value=fake_session) as mock_ns, \
             patch('rembg.remove',return_value=img) as mock_rm:
            out=cp.CutoutProcessor().segment(img,'isnet-general-use')
        self.assertIs(out,img)
        mock_ns.assert_called_once()
        mock_rm.assert_called_once()

    def test_remotion_error_summary_strips_version_banner_and_preserves_failure_tail(self):
        from agent.editorial.render import _remotion_error_summary
        from agent.portfolio_api import safe_message
        with tempfile.TemporaryDirectory() as tmp:
            log=Path(tmp)/'editorial.render.log'
            log.write_text(
                '-------------\nVersion mismatch:\nExtra packages with wrong versions:\n  - zod: installed 3.25.76, required 4.5.4\n-------------\n\n'
                'Bundling 6%\nBundling 100%\nGetting composition\nError: Actual failure reason at the end of the log\n'
            )
            msg=safe_message('Editorial Remotion failed: '+_remotion_error_summary(log))
        self.assertNotIn('Version mismatch',msg)
        self.assertIn('Actual failure reason at the end of the log',msg)

async def async_result():return 'replicate:fixture'

class RetryBudgetTests(unittest.TestCase):
    def test_fallbacks_share_one_timeout_budget(self):
        import httpx
        from openai import APITimeoutError
        from utils.llm_client import _ResilientCompletions
        clock=[0.0];timeouts=[]
        primary=MagicMock()
        def fail(**kwargs):
            self.assertNotIn('retry_budget_seconds',kwargs)
            timeouts.append(kwargs['timeout']);clock[0]+=kwargs['timeout']
            raise APITimeoutError(request=httpx.Request('POST','https://example.test'))
        primary.chat.completions.create.side_effect=fail
        client=_ResilientCompletions(primary=primary,primary_model='primary',fallback_models=['second','third'])
        with patch('time.monotonic',side_effect=lambda:clock[0]),patch('time.sleep',side_effect=lambda n:clock.__setitem__(0,clock[0]+n)):
            with self.assertRaises(APITimeoutError):client.create(model='primary',timeout=45,retry_budget_seconds=90)
        self.assertEqual(len(timeouts),2)
        self.assertLess(timeouts[1],45)
        self.assertLessEqual(clock[0],90)
