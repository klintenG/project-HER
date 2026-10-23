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
