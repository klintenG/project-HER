"""Native API contracts/security with local durable stores; no paid provider calls."""
import base64
import json
import concurrent.futures
import tempfile
import time
import threading
import unittest
import config
from pathlib import Path
from unittest.mock import patch,MagicMock
from flask import Flask
from agent.portfolio_api import install,Runtime,CreateJob,APIError,terminate_worker,cleanup_cloud_job
from agent.portfolio_store import SQLiteStore,LocalMedia

ORIGIN='https://klinteng.com'
RealThread=threading.Thread

class PortfolioAPITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.rt=Runtime(SQLiteStore(self.root/'state.db'),LocalMedia(self.root/'media'),'s'*48,daily=10,visitor=2,concurrent=1,executor=lambda *args:None)
        self.app=Flask(__name__);install(self.app);self.app.extensions['her_portfolio']=self.rt;self.client=self.app.test_client()
        self.thread=patch('agent.portfolio_api.threading.Thread');self.thread.start();self.addCleanup(self.thread.stop)
    def create(self,key='unique-request-key-0001',data=None,**kwargs):
        return self.client.post('/api/portfolio/jobs',json=data or {'text':'A fictional red cup stands on a table.'},headers={'Origin':ORIGIN,'Idempotency-Key':key},**kwargs)
    def headers(self,job):return {'Authorization':'Bearer '+job['access_token'],'Origin':ORIGIN}
    def test_capabilities_and_origin_allowlist(self):
        response=self.client.get('/api/portfolio/config',headers={'Origin':ORIGIN})
        self.assertEqual(response.status_code,200);self.assertTrue(response.json['enabled'])
        self.assertEqual(response.headers['Access-Control-Allow-Origin'],ORIGIN)
        self.assertEqual(response.json['defaults']['tts_provider'],'replicate')
        self.assertEqual(response.json['limits']['input_characters'],6000)
        response=self.client.get('/api/portfolio/config',headers={'Origin':'https://attacker.invalid'})
        self.assertEqual(response.status_code,403);self.assertNotIn('Access-Control-Allow-Origin',response.headers)
    def test_create_requires_origin_and_validated_options(self):
        self.assertEqual(self.client.post('/api/portfolio/jobs',json={'text':'x'},headers={'Idempotency-Key':'a'*32}).status_code,403)
        for data in [{'text':'x'*6001},{'text':'x','format':'square'},{'text':'x','target_duration':91},{'text':'x','local_assets':'/etc/passwd'},{'text':'x','tts_provider':'unknown'},{'url':'file:///etc/passwd'}]:
            with self.subTest(data=list(data)):self.assertEqual(self.create(data=data).status_code,422)
        self.assertIsNone(self.rt.store.get('active'))
    def test_private_urls_are_rejected_before_quota_or_worker(self):
        for url in ['http://127.0.0.1/','http://169.254.169.254/latest/meta-data','http://localhost/']:
            with self.subTest(url=url):self.assertEqual(self.create(data={'url':url}).status_code,422)
        self.assertIsNone(self.rt.store.get('active'))
    def test_oversized_json_is_rejected(self):
        response=self.client.post('/api/portfolio/jobs',data='x'*16001,content_type='application/json',headers={'Origin':ORIGIN,'Idempotency-Key':'a'*32})
        self.assertEqual(response.status_code,413)
    def test_idempotency_recovers_same_job_without_another_paid_slot(self):
        first=self.create();second=self.create()
        self.assertEqual(first.status_code,202);self.assertEqual(first.json['job_id'],second.json['job_id'])
        self.assertEqual(first.json['access_token'],second.json['access_token'])
        self.assertEqual(self.create(data={'text':'A different story.'}).status_code,409)
        response=self.client.get('/api/portfolio/submission',headers={'Origin':ORIGIN,'Idempotency-Key':'unique-request-key-0001'})
        self.assertEqual(response.json['job_id'],first.json['job_id'])
    def test_same_submission_stays_idempotent_when_network_identity_changes(self):
        first=self.create(environ_overrides={'REMOTE_ADDR':'203.0.113.10'})
        second=self.create(environ_overrides={'REMOTE_ADDR':'203.0.113.20'})
        self.assertEqual(second.json['job_id'],first.json['job_id'])
        recovered=self.client.get('/api/portfolio/submission',headers={'Origin':ORIGIN,'Idempotency-Key':'unique-request-key-0001'},environ_overrides={'REMOTE_ADDR':'203.0.113.30'})
        self.assertEqual(recovered.json['job_id'],first.json['job_id'])
    def test_job_capability_is_scoped_and_state_survives_new_runtime(self):
        job=self.create().json;jid=job['job_id']
        self.assertEqual(self.client.get('/api/portfolio/jobs/'+jid).status_code,404)
        self.assertEqual(self.client.get('/api/portfolio/jobs/'+jid,headers={'Authorization':'Bearer '+'a'*64}).status_code,404)
        self.app.extensions['her_portfolio']=Runtime(SQLiteStore(self.root/'state.db'),self.rt.media,'s'*48,executor=lambda *args:None)
        response=self.client.get('/api/portfolio/jobs/'+jid,headers=self.headers(job))
        self.assertEqual(response.json['status'],'queued');self.assertNotIn('text',response.json)
        self.assertNotIn('access_token',response.json)
    def test_progress_stream_reports_real_stored_stage_and_completion(self):
        job=self.create().json;jid=job['job_id']
        self.rt.update(jid,status='failed',stage={'name':'narrate','label':'Narration','status':'failed','elapsed':3.1},error='Speech provider unavailable.')
        response=self.client.get('/api/portfolio/jobs/'+jid+'/events',headers=self.headers(job))
        self.assertIn(b'event: done',response.data);self.assertIn(b'Speech provider unavailable',response.data)
        self.assertNotIn(b'progress_pct',response.data)
    def test_news_cancellation_is_requested_not_fabricated_as_completed(self):
        job=self.create().json
        response=self.client.post('/api/portfolio/jobs/'+job['job_id']+'/cancel',headers=self.headers(job))
        self.assertEqual(response.status_code,202);self.assertEqual(response.json['status'],'cancelling')
        state=self.client.get('/api/portfolio/jobs/'+job['job_id'],headers=self.headers(job)).json
        self.assertEqual(state['status'],'queued');self.assertTrue(state['cancel_requested'])
    def test_classic_cancellation_is_not_offered(self):
        job=self.create(data={'text':'A story about a cup.','content_mode':'article','visual_preset':'default','tts_provider':config.TTS_PROVIDER}).json
        self.assertFalse(job['cancel_supported'])
        self.assertEqual(self.client.post('/api/portfolio/jobs/'+job['job_id']+'/cancel',headers=self.headers(job)).status_code,409)
    def test_global_quota_and_concurrency_are_transactional(self):
        model=CreateJob(text='Fictional cup story.')
        def reserve(index):
            try:self.rt.reserve(model,str(index),'key-'+str(index)*20);return 202
            except APIError as exc:return exc.status
        with patch('agent.portfolio_api.threading.Thread',RealThread),concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(reserve,range(6)))
        self.assertEqual(results.count(202),1);self.assertEqual(results.count(429),5)
    def test_daily_visitor_budget_persists_and_forwarded_spoofing_does_not_reset_it(self):
        self.rt.visitor=1
        first=self.create().json;self.rt.update(first['job_id'],status='failed');self.rt.release(first['job_id'])
        response=self.client.post('/api/portfolio/jobs',json={'text':'A story'},headers={'Origin':ORIGIN,'Idempotency-Key':'different-request-key-02','X-Forwarded-For':'198.51.100.222'})
        self.assertEqual(response.status_code,429)
    def test_expired_worker_is_failed_without_replaying_and_frees_slot(self):
        job=self.create().json
        data=self.rt.store.get('job:'+job['job_id']);data['deadline']=time.time()-1;self.rt.store.set('job:'+job['job_id'],data)
        state=self.client.get('/api/portfolio/jobs/'+job['job_id'],headers=self.headers(job)).json
        self.assertEqual(state['status'],'failed');self.assertIn('No automatic paid retry',state['error'])
        self.assertEqual(self.rt.store.get('active')['jobs'],{})
    def test_private_media_range_download_tickets_and_expiration(self):
        job=self.create().json;jid=job['job_id'];source=self.root/'fixture.mp4';source.write_bytes(bytes(range(100)))
        asset=self.rt.media.upload(source,jid+'/video.mp4','video/mp4')
        self.rt.update(jid,status='completed',result={'title':'Fixture only','duration':1,'resolution':'1080x1920','assets':{'video':asset}})
        result=self.client.get('/api/portfolio/jobs/'+jid,headers=self.headers(job)).json['result']
        response=self.client.get(result['video_url'],headers={'Origin':ORIGIN,'Range':'bytes=10-19'})
        self.assertEqual(response.status_code,206);self.assertEqual(response.data,bytes(range(10,20)));self.assertEqual(response.headers['Content-Range'],'bytes 10-19/100')
        self.assertEqual(self.client.get(result['video_url'],headers={'Range':'bytes=200-300'}).status_code,416)
        response=self.client.get(result['download_url']);self.assertEqual(response.data,bytes(range(100)));self.assertIn('attachment',response.headers['Content-Disposition'])
        self.assertEqual(self.client.get('/api/portfolio/jobs/'+jid+'/media/video?ticket=invalid').status_code,410)
        other=result['video_url'].replace(jid,'a'*32);self.assertEqual(self.client.get(other).status_code,404)
        source.unlink();(self.rt.media.root/asset['key']).unlink()
        self.assertEqual(self.client.get(result['video_url']).status_code,410)
    def test_kill_switch_does_not_hide_existing_jobs(self):
        job=self.create().json;self.rt.store.set('policy',{'disabled':True})
        self.assertEqual(self.create(key='a-new-request-key-002').status_code,503)
        self.assertEqual(self.client.get('/api/portfolio/jobs/'+job['job_id'],headers=self.headers(job)).status_code,200)
    def test_legacy_paid_and_private_routes_cannot_bypass_native_controls(self):
        with patch.dict('os.environ',{'HER_PORTFOLIO_LOCK_LEGACY':'1','HER_OPERATOR_KEY':'operator-key'}):
            self.app.add_url_rule('/api/generate','legacy',lambda:{'ok':True},methods=['POST'])
            self.assertEqual(self.client.post('/api/generate').status_code,401)
            basic=base64.b64encode(b'operator:operator-key').decode()
            self.assertEqual(self.client.post('/api/generate',headers={'Authorization':'Basic '+basic}).status_code,200)

    def test_legacy_output_cannot_escape_output_root_or_find_another_job(self):
        import web_ui
        outside=self.root/'private.txt';outside.write_text('private contents')
        output=self.root/'output';output.mkdir();(output/'other-job').mkdir();(output/'other-job'/'video.mp4').write_bytes(b'other job')
        with patch.object(config,'OUTPUT_DIR',output):
            client=web_ui.app.test_client()
            for path in ['/output/../private.txt','/output/%2e%2e/private.txt','/output/video.mp4']:
                self.assertEqual(client.get(path).status_code,404)
    def test_native_deadline_stops_detached_media_descendants(self):
        process=MagicMock(pid=123);process.is_alive.side_effect=[True,False]
        child=MagicMock();module=MagicMock();module.Process.return_value.children.return_value=[child]
        module.NoSuchProcess=ProcessLookupError;module.wait_procs.return_value=([child],[])
        with patch.dict('sys.modules',{'psutil':module}):terminate_worker(process)
        child.terminate.assert_called_once();process.terminate.assert_called_once()
        module.Process.return_value.children.assert_called_once_with(recursive=True)

    def test_cloud_cleanup_removes_only_owned_job_workspaces(self):
        jid='a'*32;generation='editorial_'+'b'*32
        output=self.root/'output';scratch=self.root/'temp';base=self.root/'base'
        owned=output/('portfolio_'+jid);owned.mkdir(parents=True)
        (owned/'editorial_props.json').write_text(json.dumps({'generationId':generation}))
        stage=base/'remotion/public/editorial'/generation;stage.mkdir(parents=True);(stage/'audio.wav').write_bytes(b'private')
        neighbour=stage.with_name('editorial_'+'c'*32);neighbour.mkdir()
        workspace=scratch/'portfolio-work'/jid;workspace.mkdir(parents=True);(workspace/'speech.mp3').write_bytes(b'private')
        other=workspace.with_name('d'*32);other.mkdir()
        with patch.object(config,'OUTPUT_DIR',output),patch.object(config,'TEMP_DIR',scratch),patch.object(config,'BASE_DIR',base):
            cleanup_cloud_job(jid)
            self.assertFalse(owned.exists());self.assertFalse(stage.exists());self.assertFalse(workspace.exists())
            self.assertTrue(neighbour.exists());self.assertTrue(other.exists())
            owned.mkdir();(owned/'editorial_props.json').write_text(json.dumps({'generationId':'../'+neighbour.name}))
            cleanup_cloud_job(jid);self.assertTrue(neighbour.exists())
            with self.assertRaises(ValueError):cleanup_cloud_job('../other')

if __name__=='__main__':unittest.main()
