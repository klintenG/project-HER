"""Offline contracts: concurrency, restart, manual isolation and ambiguous writes."""
import copy
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch,Mock
from flask import Flask
from agent.portfolio_store import SQLiteStore
from automation.autopilot_store import Registry,duplicate
from automation.autopilot_config import Settings,publication_time
from automation.autonomous_story_director import Candidate,Script,ReplicateJSON
from automation.autopilot import Autopilot
from automation.autopilot_api import install
from automation.buffer_client import build_post,BufferClient,BufferRejected
from automation.engine_budget import EngineBudget,active_budget,charge_image
from automation.social_metadata import SocialMetadataGenerator


def candidate():
    return dict(title='Medusa and the curse',canonical_story_id='ovid-medusa-transformation',
        canonical_aliases=['Medousa cursed'],story_origin='MYTHOLOGY',category='MYTHOLOGY',mythology_tradition='Ovid',
        primary_characters=['Medusa'],character_aliases=['Medousa'],story_summary='Medusa is transformed after the desecration of a temple.',
        central_conflict='A punishment transforms Medusa',major_plot_events=['temple desecration','Athena curses Medusa','hair becomes serpents'],
        ending='Medusa becomes a feared gorgon',supporting_references=['Ovid, Metamorphoses 4'])


def ready(registry):
    row=registry.reserve(candidate())
    script={'hook_text':'The curse that changed everything','narration':'Narration'}
    row.update(script=script)
    return registry.update('story:'+row['story_id'],generation_status='READY',quality={'passed':True},
        media_url='https://storage.googleapis.com/test/autopilot/vid/video.mp4',cover={'offset_ms':1500},
        script=script,social_metadata=SocialMetadataGenerator().generate(row))


class FixedClock(datetime):
    @classmethod
    def now(cls,tz=None):return datetime(2026,10,25,10,0,tzinfo=timezone.utc).astimezone(tz)


class FakeBuffer:
    def __init__(self):self.remote=[];self.calls=[];self.error=None;self.organization='org'
    def discover(self):return {p:{'id':p,'displayName':p} for p in ('instagram','youtube')}
    def posts(self,channel):return [p for p in self.remote if p['channelId']==channel]
    def create(self,payload):
        self.calls.append(payload)
        post=dict(id=str(len(self.calls)),channelId=payload['channelId'],text=payload['text'],dueAt=payload.get('dueAt'),status='sending' if payload.get('mode')=='shareNow' else 'scheduled',schedulingType='automatic',externalLink=None)
        self.remote.append(post)
        if self.error==payload['channelId']:raise TimeoutError('Response lost after commit')
        return post
    def get(self,pid):return next(p for p in self.remote if p['id']==pid)


class StoreFixture(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'state.sqlite3'
        self.registry=Registry(SQLiteStore(self.path))
    def tearDown(self):self.tmp.cleanup()


class StoreTests(StoreFixture):
    def test_exact_and_alternate_title_rejected_across_restart(self):
        self.registry.reserve(candidate());other=Registry(SQLiteStore(self.path))
        with self.assertRaises(ValueError):other.reserve(candidate())
        alternate=candidate();alternate['title']='Woman turned into a monster'
        with self.assertRaises(ValueError):other.reserve(alternate)
    def test_distinct_character_arc_allowed(self):
        self.registry.reserve(candidate());other=candidate()
        other.update(title='Perseus and the gorgon',canonical_story_id='perseus-medusa-beheading',canonical_aliases=[],
            major_plot_events=['Perseus receives a shield','Perseus approaches sleeping gorgon','Perseus cuts off her head'],ending='Pegasus emerges and Perseus escapes')
        self.registry.reserve(other)
        self.assertEqual(len(self.registry.stories()),2)
    def test_manual_never_blocks_or_calls_registry(self):
        self.registry.reserve(candidate())
        with patch.object(self.registry.store,'atomic',side_effect=AssertionError('Manual must bypass all checks')):
            self.assertIsNone(self.registry.reserve(candidate(),generation_mode='MANUAL'))
    def test_event_comparison_not_character_overlap(self):
        a=candidate();b=candidate();b.update(title='Renamed',canonical_story_id='different-name',canonical_aliases=[])
        self.assertEqual(duplicate(a,b),'narrative_events')
        b.update(major_plot_events=['new voyage','new obstacle','new revelation'],ending='A different ending')
        self.assertIsNone(duplicate(a,b))
    def test_concurrent_reservations(self):
        def reserve(_):
            try:return self.registry.reserve(candidate())
            except ValueError:return None
        with ThreadPoolExecutor(max_workers=4) as executor:results=list(executor.map(reserve,range(4)))
        self.assertEqual(sum(r is not None for r in results),1)
    def test_budget_is_atomic(self):
        def spend(_):
            try:self.registry.spend(.5,1,'test');return True
            except ValueError:return False
        with ThreadPoolExecutor(max_workers=4) as executor:results=list(executor.map(spend,range(4)))
        self.assertEqual(sum(results),2)
    def test_lease_fencing(self):
        token=self.registry.claim('job',60);self.assertTrue(token)
        self.assertIsNone(self.registry.claim('job',60))
        self.registry.release('job','wrong-token');self.assertIsNone(self.registry.claim('job',60))
        self.registry.release('job',token);self.assertTrue(self.registry.claim('job',60))
    def test_legacy_import_persistent_and_idempotent(self):
        path=Path(self.tmp.name)/'history.json';path.write_text(json.dumps({'stories':[{'id':'old','title':'Old tale','status':'published','synopsis':'A complete old story'}]}))
        self.registry.import_legacy(path);self.registry.import_legacy(path)
        self.assertEqual(len(self.registry.stories()),1)
        self.assertEqual(self.registry.stories()[0]['creation_mode'],'LEGACY')
    def test_corrupt_legacy_history_not_silently_reset(self):
        path=Path(self.tmp.name)/'history.json';path.write_text('{')
        with self.assertRaises(json.JSONDecodeError):self.registry.import_legacy(path)
    def test_engine_ceiling_leaves_manual_unchanged(self):
        charge_image('replicate')
        budget=EngineBudget(.1,.05,2,self.registry,'sid');token=active_budget.set(budget)
        try:
            charge_image('replicate');charge_image('huggingface')
            with self.assertRaises(ValueError):charge_image('replicate')
        finally:active_budget.reset(token)
        self.assertEqual(budget.count,2)


class ScheduleTests(unittest.TestCase):
    def test_ist_conversion(self):
        due=publication_time(Settings(),datetime(2026,10,25,6,tzinfo=timezone.utc))
        self.assertEqual(due.isoformat(),'2026-10-25T13:00:00+00:00')
    def test_late_inside_and_outside_window(self):
        from automation.autopilot_config import next_scheduled_slot
        cfg=Settings()
        self.assertEqual(publication_time(cfg,datetime(2026,10,25,13,5,tzinfo=timezone.utc)).hour,13)
        self.assertIsNone(publication_time(cfg,datetime(2026,10,25,13,28,tzinfo=timezone.utc)))
        self.assertEqual(next_scheduled_slot(cfg,datetime(2026,10,25,14,15,tzinfo=timezone.utc)).isoformat(),'2026-10-26T13:00:00+00:00')
        with self.assertRaises(ValueError):publication_time(cfg,datetime(2026,10,25))
    def test_config_fail_closed(self):
        for kwargs in ({'publish_time':'20:00'},{'timezone':'UTC'},{'category_weights':{'MYTHOLOGY':-1}},{'min_video_seconds':90,'max_video_seconds':45},{'daily_cost_limit_usd':float('nan')}):
            with self.assertRaises(ValueError):Settings(**kwargs)
    def test_model_config_swappable(self):
        with patch.dict(os.environ,{'AUTOPILOT_LLM_MODEL':'owner/replacement'}):
            self.assertEqual(Settings.environment().llm_model,'owner/replacement')
    def test_platform_payload_contract(self):
        story=candidate();story['script']={'hook_text':'A curse changes everything'}
        metadata=SocialMetadataGenerator().generate(story)
        ig=build_post('instagram','ig','https://media/video.mp4','2026-10-25T13:00:00Z',metadata,1500)
        yt=build_post('youtube','yt','https://media/video.mp4',ig['dueAt'],metadata,1500)
        self.assertEqual(ig['assets'][0]['video']['metadata'],{'thumbnailOffset':1500})
        self.assertNotIn('metadata',yt['assets'][0]['video'])
        self.assertNotIn('thumbnailUrl',json.dumps([ig,yt]))
        self.assertNotEqual(ig['text'],yt['text'])
        self.assertEqual(ig['schedulingType'],'automatic');self.assertEqual(yt['mode'],'customScheduled')
        self.assertTrue(ig['metadata']['instagram']['shouldShareToFeed'])


class PublishingTests(StoreFixture):
    def setUp(self):
        super().setUp();self.buffer=FakeBuffer()
        self.legacy=patch.object(Registry,'import_legacy');self.legacy.start()
        self.service=Autopilot(self.registry,self.buffer)
        self.registry.store.set('autopilot-settings',{'enabled':True,'dry_run':False})
        self.env=patch.dict(os.environ,{'AUTOPILOT_LIVE_VALIDATED':'true'});self.env.start()
        self.clock=patch('automation.autopilot.datetime',FixedClock);self.clock.start()
        self.media=patch('automation.autopilot.PublicMedia.verify');self.media.start()
    def tearDown(self):
        self.media.stop();self.clock.stop();self.env.stop();self.legacy.stop();super().tearDown()
    def test_single_video_two_platforms_no_duplicate_retries(self):
        story=ready(self.registry)
        self.service.schedule();self.service.schedule()
        self.assertEqual(len(self.buffer.calls),2)
        self.assertEqual(self.buffer.calls[0]['assets'][0]['video']['url'],self.buffer.calls[1]['assets'][0]['video']['url'])
        self.assertEqual(self.registry.store.get('story:'+story['story_id'])['publication_status'],'SCHEDULED')
    def test_lost_response_reconciles_only_missing_platform(self):
        ready(self.registry);self.buffer.error='instagram'
        self.service.schedule();self.assertEqual(len(self.buffer.calls),2)
        self.service.schedule();self.assertEqual(len(self.buffer.calls),2)
        self.assertEqual({r['status'] for r in self.registry.publications()},{'SCHEDULED'})
    def test_ambiguous_without_remote_result_never_reposts(self):
        ready(self.registry);self.buffer.error='instagram';self.service.schedule()
        self.buffer.remote=[p for p in self.buffer.remote if p['channelId']!='instagram']
        self.service.schedule();self.assertEqual(len(self.buffer.calls),2)
        self.assertEqual(self.registry.store.get('publication:2026-10-25:instagram')['status'],'UNKNOWN')
    def test_remote_confirmation_required(self):
        story=ready(self.registry);self.service.schedule()
        self.assertNotEqual(self.registry.store.get('story:'+story['story_id'])['publication_status'],'PUBLISHED')
        self.buffer.remote[0].update(status='sent',externalLink='https://instagram.com/post')
        self.buffer.remote[1].update(status='error',error={'message':'Failed'})
        self.service.verify()
        saved=self.registry.store.get('story:'+story['story_id'])
        self.assertEqual(saved['publication_status'],'PARTIAL');self.assertEqual(saved['published_platforms'],['instagram'])
    def test_no_video_never_posts(self):
        with self.assertRaises(ValueError):self.service.schedule()
        self.assertFalse(self.buffer.calls)
    def test_dry_run_does_not_consume_inventory_or_daily_slot(self):
        story=ready(self.registry);self.service.schedule(force_dry_run=True)
        self.assertFalse(self.buffer.calls);self.assertFalse(self.registry.store.get('daily:2026-10-25'))
        self.assertEqual(self.registry.store.get('story:'+story['story_id'])['publication_status'],'UNUSED')
    def test_notification_is_blocked(self):
        story=ready(self.registry);self.service.schedule()
        self.buffer.remote[0]['schedulingType']='notification';self.service.verify()
        self.assertEqual(self.registry.store.get('publication:2026-10-25:instagram')['status'],'BLOCKED')
    def test_channel_queue_limit(self):
        ready(self.registry)
        for i in range(10):self.buffer.remote.append(dict(id='old'+str(i),channelId='instagram',text='old',dueAt='2026-10-24T13:00:00Z',status='scheduled'))
        self.service.schedule();self.assertEqual(len(self.buffer.calls),1)
        self.assertEqual(self.buffer.calls[0]['channelId'],'youtube')
    def test_pausing_does_not_render(self):
        self.registry.store.set('autopilot-settings',{'enabled':False})
        self.assertEqual(self.service.generate()['status'],'paused')
        self.assertEqual(self.service.schedule()['status'],'paused')
    def test_concurrent_daily_assignment(self):
        ready(self.registry)
        def assign(_):return self.service._daily('2026-10-25','2026-10-25T13:00:00+00:00')[0]['story_id']
        with ThreadPoolExecutor(max_workers=4) as executor:ids=list(executor.map(assign,range(4)))
        self.assertEqual(len(set(ids)),1);self.assertEqual(len(self.registry.publications()),2)


class ApiTests(StoreFixture):
    def setUp(self):
        super().setUp();self.legacy=patch.object(Registry,'import_legacy');self.legacy.start()
        self.service=Autopilot(self.registry,FakeBuffer());self.dispatch=Mock(return_value={'pid':1})
        app=Flask(__name__);install(app,lambda:self.service,self.dispatch);self.client=app.test_client()
        self.env=patch.dict(os.environ,{'AUTOPILOT_ADMIN_TOKEN':'a'*32});self.env.start()
        self.headers={'Authorization':'Bearer '+'a'*32}
    def tearDown(self):self.env.stop();self.legacy.stop();super().tearDown()
    def test_auth_required(self):
        self.assertEqual(self.client.get('/api/autopilot').status_code,401)
        self.assertEqual(self.client.post('/api/autopilot/actions',json={'action':'generate'}).status_code,401)
        self.dispatch.assert_not_called()
    def test_settings_no_secret_access(self):
        response=self.client.post('/api/autopilot/settings',json={'BUFFER_API_KEY':'bad'},headers=self.headers)
        self.assertEqual(response.status_code,400)
    def test_real_controls_enqueue_once(self):
        response=self.client.post('/api/autopilot/actions',json={'action':'generate'},headers=self.headers)
        self.assertEqual(response.status_code,202);self.dispatch.assert_called_once()
        response=self.client.post('/api/autopilot/actions',json={'action':'generate'},headers=self.headers)
        self.assertEqual(response.status_code,400)
    def test_no_auth_when_token_unconfigured(self):
        with patch.dict(os.environ,{'AUTOPILOT_ADMIN_TOKEN':''}):
            self.assertEqual(self.client.get('/api/autopilot',headers=self.headers).status_code,503)
    def test_works_under_portfolio_legacy_lock(self):
        from agent.portfolio_api import install as install_portfolio
        app=Flask(__name__,template_folder=str(Path(__file__).resolve().parents[1]/'templates'))
        install_portfolio(app);install(app,lambda:self.service,self.dispatch)
        client=app.test_client()
        with patch.dict(os.environ,{'HER_PORTFOLIO_LOCK_LEGACY':'1'}):
            self.assertEqual(client.get('/autopilot').status_code,200)
            self.assertEqual(client.get('/dashboard').status_code,200)
            self.assertEqual(client.get('/api/autopilot').status_code,401)
            resp=client.get('/api/autopilot',headers=self.headers)
            self.assertEqual(resp.status_code,200)
            body=resp.get_json()
            self.assertIn('counts',body)
            self.assertIn('next_scheduled_slot',body)
            self.assertEqual(client.get('/api/autopilot/channels',headers=self.headers).status_code,200)
            self.assertEqual(client.post('/api/autopilot/actions',json={'action':'pipeline'},headers=self.headers).status_code,202)



class ModelContractTests(unittest.TestCase):
    def test_wrapped_json_is_validated(self):
        from pydantic import BaseModel
        from automation.autonomous_story_director import Batch,parse_structured
        class Example(BaseModel):
            title:str
        result=parse_structured('Here is the result:\n```json\n{"title":"A complete tale"}\n```',Example)
        self.assertEqual(result.title,'A complete tale')
        with self.assertRaises(ValueError):parse_structured('{"title":',Example)
        items=[candidate()|{'title':f'Story {i}','canonical_story_id':f'myth:{i}','source_urls':['https://example.org/text']} for i in range(5)]
        batch=parse_structured(json.dumps(items),Batch)
        self.assertEqual(len(batch.candidates),5)
    def test_traditional_story_requires_references_and_urls(self):
        row=candidate()
        with self.assertRaises(ValueError):Candidate.model_validate(row)
        row['source_urls']=['https://example.org/primary-text']
        self.assertEqual(Candidate.model_validate(row).story_origin,'MYTHOLOGY')
    def test_script_hook_length_is_checked(self):
        from automation.autonomous_story_director import parse_structured
        row={'narration':' '.join(['A story develops through a meaningful conflict and resolution.']*13),
            'hook_text':'A hook with far too many unnecessary and unrelated words to fit',
            'setup':'Setup','conflict':'Conflict','escalation':'Escalation','climax':'Climax','resolution':'Resolution'}
        with self.assertRaises(ValueError):parse_structured(json.dumps(row),Script)
    def test_semantic_duplicates_and_uncertainty_are_rejected(self):
        from automation.autonomous_story_director import AutonomousStoryDirector,OriginalityReview
        prior=candidate();prior['story_id']='previous'
        llm=Mock()
        director=AutonomousStoryDirector(Settings(),Mock(),llm)
        for duplicate_result,confidence in ((True,.95),(False,.5)):
            llm.ask.return_value=OriginalityReview(is_duplicate=duplicate_result,confidence=confidence,reason='Arc comparison')
            with self.assertRaises(ValueError):director.semantic_originality(candidate(),[prior])
        llm.ask.return_value=OriginalityReview(is_duplicate=False,confidence=.95,reason='Distinct events involving the same character')
        self.assertFalse(director.semantic_originality(candidate(),[prior])['is_duplicate'])

    def test_source_retrieval_failure_is_closed(self):
        from automation.autonomous_story_director import AutonomousStoryDirector
        with patch('agent.news_research.fetch',side_effect=ValueError('unreachable')):
            with self.assertRaises(ValueError):AutonomousStoryDirector.source_evidence(['https://example.org/missing'])
    def test_llm_ceiling_blocks_network_call(self):
        registry=Mock();settings=Settings(llm_model='owner/model',max_llm_calls=4)
        llm=ReplicateJSON(settings,registry);llm.calls=4
        with patch('config.REPLICATE_API_TOKEN','token'),patch('requests.post') as post:
            with self.assertRaises(ValueError):llm.ask('ideation','prompt',Candidate)
            post.assert_not_called()


class MediaGateTests(unittest.TestCase):
    def test_untrusted_media_url_never_fetched(self):
        from automation.autopilot import PublicMedia
        with patch.dict(os.environ,{'AUTOPILOT_PUBLIC_BUCKET':'publishable'}),patch('requests.get') as get:
            with self.assertRaises(ValueError):PublicMedia.verify('http://127.0.0.1/admin')
            get.assert_not_called()
    def test_wrong_content_type_rejected(self):
        from automation.autopilot import PublicMedia
        response=Mock(status_code=200,headers={'Content-Type':'text/html'})
        response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        with patch.dict(os.environ,{'AUTOPILOT_PUBLIC_BUCKET':'publishable'}),patch('requests.get',return_value=response):
            with self.assertRaises(ValueError):PublicMedia.verify('https://storage.googleapis.com/publishable/autopilot/video.mp4')
    def test_missing_video_fails_without_ffprobe(self):
        from automation.video_quality import VideoQualityValidator
        with patch('automation.video_quality.command') as command:
            report=VideoQualityValidator().validate('/nonexistent/video.mp4',Settings(),{}, {})
            self.assertFalse(report['passed']);command.assert_not_called()
    def test_actual_ffmpeg_rejects_black_silent_wrong_format_video(self):
        import shutil,subprocess
        from automation.video_quality import VideoQualityValidator
        if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):self.skipTest('ffmpeg/ffprobe unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bad.mp4'
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=black:s=160x284:r=15:d=2',
                '-f','lavfi','-i','anullsrc=r=44100:cl=mono','-t','2','-c:v','libx264','-preset','ultrafast','-c:a','aac',str(path)],check=True)
            cover=Path(tmp)/'thumbnail.png';cover.write_bytes(b'fixture')
            story={'story_id':'test','script':{'hook_text':'A valid hook'}}
            report=VideoQualityValidator().validate(path,Settings(),story,{'offset_ms':1500,'path':str(cover)})
            self.assertFalse(report['passed'])
            failed={c['name'] for c in report['checks'] if c['result']=='FAIL'}
            self.assertTrue({'portrait','duration','audible_audio','no_black_intervals'}.issubset(failed))

class ManualEngineIsolationTests(unittest.TestCase):
    def test_repeated_manual_input_bypasses_autopilot(self):
        from agent.orchestrator import AgentOrchestrator,PipelineResult
        orchestrator=object.__new__(AgentOrchestrator)
        orchestrator._run_ai_image_pipeline=Mock(return_value=PipelineResult(success=True))
        with tempfile.TemporaryDirectory() as tmp,patch.object(Registry,'reserve',side_effect=AssertionError('Manual deduplication is forbidden')):
            for _ in range(2):
                result=orchestrator.run('Medusa is cursed',ai_images=True,output_dir=Path(tmp))
                self.assertTrue(result.success)
        self.assertEqual(orchestrator._run_ai_image_pipeline.call_count,2)
        kwargs=orchestrator._run_ai_image_pipeline.call_args.kwargs
        self.assertEqual(kwargs['input_source'],'Medusa is cursed')
        self.assertIsNone(kwargs['autopilot_scene_validator'])
        self.assertEqual(kwargs['autopilot_hook'],'')
    def test_autopilot_reuses_current_editorial_supplied_story_route(self):
        from agent.orchestrator import AgentOrchestrator,PipelineResult
        orchestrator=object.__new__(AgentOrchestrator)
        orchestrator._llm_provider='gemini';orchestrator._llm_model=None
        validator=Mock();images=Mock()
        with patch('agent.editorial.pipeline.run_editorial',return_value=PipelineResult(success=True)) as engine:
            result=orchestrator.run('An original tale',content_mode='story',visual_preset='reference_editorial',
                autopilot_hook='A machine remembers tomorrow',autopilot_scene_validator=validator,
                autopilot_image_generator=images,autopilot_story_id='story-id')
        self.assertTrue(result.success)
        kwargs=engine.call_args.kwargs
        self.assertEqual(kwargs['source_policy'],'supplied')
        self.assertIs(kwargs['autopilot_scene_validator'],validator)
        self.assertIs(kwargs['image_generator'],images)
        self.assertEqual(kwargs['autopilot_story_id'],'story-id')


if __name__=='__main__':unittest.main()

class ImmediatePublishTests(StoreFixture):
    def test_ready_video_uses_share_now_and_repeat_does_not_duplicate(self):
        story=ready(self.registry);buffer=FakeBuffer()
        service=Autopilot(self.registry,buffer)
        with patch.dict(os.environ,{'BUFFER_DRY_RUN':'false','AUTOPILOT_LIVE_VALIDATED':'true'}),patch('automation.autopilot.PublicMedia.verify'):
            result=service.publish_now(story['story_id'])
            self.assertEqual(result['status'],'processed')
            self.assertEqual(len(buffer.calls),2)
            self.assertTrue(all(p['mode']=='shareNow' and 'dueAt' not in p for p in buffer.calls))
            service.publish_now(story['story_id'])
            self.assertEqual(len(buffer.calls),2)

    def test_dry_run_blocks_immediate_publication(self):
        story=ready(self.registry);buffer=FakeBuffer()
        with patch.dict(os.environ,{'BUFFER_DRY_RUN':'true'}):
            with self.assertRaises(ValueError):Autopilot(self.registry,buffer).publish_now(story['story_id'])
        self.assertEqual(buffer.calls,[])

    def test_ambiguous_create_cannot_be_repeated(self):
        story=ready(self.registry);buffer=FakeBuffer()
        buffer.error='instagram'
        # FakeBuffer requires dueAt; simulate the ambiguous network outcome directly.
        buffer.create=Mock(side_effect=TimeoutError('Response lost'))
        service=Autopilot(self.registry,buffer)
        with patch.dict(os.environ,{'BUFFER_DRY_RUN':'false','AUTOPILOT_LIVE_VALIDATED':'true'}),patch('automation.autopilot.PublicMedia.verify'):
            with self.assertRaises(TimeoutError):service.publish_now(story['story_id'])
            with self.assertRaises(ValueError):service.publish_now(story['story_id'])
            self.assertEqual(buffer.create.call_count,1)
