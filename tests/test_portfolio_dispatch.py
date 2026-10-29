"""Scale-to-zero execution: web dispatches to a Cloud Run Job; no paid provider calls."""
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
from flask import Flask
import config
from agent.portfolio_api import install,Runtime,configured_runtime
from agent.portfolio_store import SQLiteStore,LocalMedia
from agent import portfolio_worker

ORIGIN='https://klinteng.com'


class PermissionDenied(Exception):"""Same class name as google.api_core.exceptions.PermissionDenied."""


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.calls=[];self.outcome=lambda jid:'projects/p/locations/r/jobs/w/executions/w-abc'
        def dispatcher(jid):
            self.calls.append(jid);return self.outcome(jid)
        self.rt=Runtime(SQLiteStore(self.root/'state.db'),LocalMedia(self.root/'media'),'s'*48,daily=10,visitor=5,concurrent=1,
                        executor=MagicMock(side_effect=AssertionError('in-instance executor must not run')),dispatcher=dispatcher,start_grace=600)
        self.app=Flask(__name__);install(self.app);self.app.extensions['her_portfolio']=self.rt;self.client=self.app.test_client()
        self.thread=patch('agent.portfolio_api.threading.Thread');self.started=self.thread.start();self.addCleanup(self.thread.stop)
    def create(self,key='unique-request-key-0001',text='A fictional red cup stands on a table.'):
        return self.client.post('/api/portfolio/jobs',json={'text':text},headers={'Origin':ORIGIN,'Idempotency-Key':key})

    def test_admitted_job_is_dispatched_once_without_in_instance_render(self):
        response=self.create();self.assertEqual(response.status_code,202);jid=response.json['job_id']
        self.assertEqual(self.calls,[jid]);self.started.assert_not_called()
        job=self.rt.store.get('job:'+jid)
        self.assertEqual((job['status'],job['dispatch']),('queued','dispatched'))
        self.assertTrue(job['execution'].endswith('w-abc'))
        self.assertEqual(self.rt.store.get('payload:'+jid)['request']['text'],'A fictional red cup stands on a table.')
        # The same submission key never dispatches again.
        self.assertEqual(self.create().json['job_id'],jid);self.assertEqual(len(self.calls),1)
        # The concurrency slot is held through the worker's cold start.
        self.assertEqual(self.create(key='unique-request-key-0002').status_code,429)

    def test_definite_rejection_fails_job_and_frees_slot(self):
        def reject(jid):raise PermissionDenied('missing run.jobs.runWithOverrides')
        self.outcome=reject
        response=self.create();jid=response.json['job_id']
        self.assertEqual(response.json['status'],'failed')
        self.assertIn('No model work was submitted',self.rt.store.get('job:'+jid)['error'])
        self.outcome=lambda jid:'exec-2'
        self.assertEqual(self.create(key='unique-request-key-0002').status_code,202)

    def test_ambiguous_dispatch_is_not_replayed_and_fails_only_after_start_grace(self):
        def timeout(jid):raise TimeoutError('deadline exceeded')
        self.outcome=timeout
        jid=self.create().json['job_id']
        self.assertEqual(self.rt.get_job(jid)['status'],'queued')
        self.assertEqual(self.rt.store.get('job:'+jid)['dispatch'],'unknown')
        later=time.time()+300
        with patch('agent.portfolio_api.time.time',return_value=later):self.assertEqual(self.rt.get_job(jid)['status'],'queued')
        later=time.time()+700
        with patch('agent.portfolio_api.time.time',return_value=later):
            job=self.rt.get_job(jid)
        self.assertEqual(job['status'],'failed');self.assertIn('No automatic paid retry',job['error'])
        self.assertEqual(len(self.calls),1)

    def test_claim_is_exclusive_and_consumes_private_payload(self):
        jid=self.create().json['job_id']
        state,request=self.rt.claim(jid,'exec-1')
        self.assertEqual(state,'claimed');self.assertEqual(request['text'],'A fictional red cup stands on a table.')
        self.assertEqual(self.rt.store.get('payload:'+jid),{'consumed':True,'expires_at':self.rt.store.get('job:'+jid)['expires_at']})
        self.assertEqual(self.rt.claim(jid,'exec-2'),('skip',None))
        self.assertEqual(self.rt.store.get('job:'+jid)['worker'],'exec-1')

    def test_cancel_before_worker_start_does_no_work(self):
        response=self.create();jid=response.json['job_id']
        cancel=self.client.post(f'/api/portfolio/jobs/{jid}/cancel',headers={'Origin':ORIGIN,'Authorization':'Bearer '+response.json['access_token']})
        self.assertEqual(cancel.status_code,202)
        self.assertEqual(self.rt.claim(jid,'exec-1'),('cancelled',None))
        self.assertEqual(self.rt.store.get('job:'+jid)['status'],'cancelled')

    def test_worker_main_runs_claimed_job_once(self):
        jid=self.create().json['job_id'];self.rt.execute=MagicMock()
        with patch('agent.portfolio_api.configured_runtime',return_value=self.rt),\
             patch('agent.portfolio_api.prepare_worker_environment'),patch('agent.portfolio_api.cleanup_cloud_job'):
            self.assertEqual(portfolio_worker.main([jid]),0)
            self.assertEqual(portfolio_worker.main([jid]),0)
        self.rt.execute.assert_called_once()
        self.assertEqual(self.rt.execute.call_args.args[1].text,'A fictional red cup stands on a table.')
        self.assertEqual(portfolio_worker.main(['../bad']),2)

    def test_watchdog_hard_stops_ignored_cancellation(self):
        jid=self.create().json['job_id'];self.rt.claim(jid,'exec-1');self.rt.update(jid,status='running')
        self.rt.update(jid,cancel_requested=True)
        now=[time.time()];exits=[]
        def clock():
            now[0]+=15;return now[0]
        stop=threading.Event()
        with patch.object(portfolio_worker,'stop_descendants') as kill:
            portfolio_worker.watchdog(self.rt,jid,time.time()+2700,stop,exit_process=exits.append,clock=clock,interval=0.01)
        self.assertEqual(exits,[0]);kill.assert_called_once()
        self.assertEqual(self.rt.store.get('job:'+jid)['status'],'cancelled')
        self.assertEqual(self.rt.store.get('active')['jobs'],{})

    def test_only_web_service_with_worker_job_dispatches(self):
        base={'HER_PORTFOLIO_SIGNING_KEY':'s'*48,'HER_PORTFOLIO_BUCKET':'b','GOOGLE_CLOUD_PROJECT':'proj','HER_PORTFOLIO_LOCK_LEGACY':'1'}
        model=self.root/'assets'/'alignment'/'models--Systran--faster-whisper-small'/'snapshots'/'x';model.mkdir(parents=True);(model/'model.bin').write_bytes(b'')
        stores=dict(FirestoreStore=MagicMock(),GCSMedia=MagicMock())
        with patch.object(config,'REPLICATE_API_TOKEN','r8_fixture'),patch.object(config,'ASSETS_DIR',self.root/'assets'),\
             patch('importlib.util.find_spec',return_value=object()),patch.multiple('agent.portfolio_api',**stores):
            with patch.dict('os.environ',{**base,'K_SERVICE':'project-her','HER_PORTFOLIO_WORKER_JOB':'her-portfolio-worker'},clear=True):
                self.assertIsNotNone(configured_runtime().dispatcher)
            with patch.dict('os.environ',{**base,'K_SERVICE':'project-her'},clear=True):
                self.assertIsNone(configured_runtime().dispatcher)
            with patch.dict('os.environ',{**base,'CLOUD_RUN_JOB':'her-portfolio-worker','HER_PORTFOLIO_WORKER_JOB':'her-portfolio-worker'},clear=True):
                rt=configured_runtime();self.assertIsNone(rt.dispatcher)
                stores['FirestoreStore'].assert_called_with('proj')  # Job uses durable stores, not SQLite


if __name__=='__main__':unittest.main()
