"""Durability, retention, privacy and operator access for generation diagnostics."""
import base64
import json
import logging
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from flask import Flask
from agent.portfolio_api import Runtime,CreateJob,install
from agent.portfolio_store import SQLiteStore,LocalMedia
from agent.run_diagnostics import ProviderEvents,failure_details,MAX_EVENTS


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name)
        self.rt=Runtime(SQLiteStore(root/'jobs.db'),LocalMedia(root/'media'),'s'*48,executor=lambda *a:None)
        self.job,_=self.rt.reserve(CreateJob(text='Private story must never appear in diagnostic logs'),'local','diagnostic-fixture-key')
        self.jid=self.job['job_id']
        self.app=Flask(__name__);install(self.app);self.app.extensions['her_portfolio']=self.rt
        self.client=self.app.test_client();self.url='/api/portfolio/operator/jobs/'+self.jid+'/diagnostics'
        self.env=patch.dict(os.environ,{'HER_OPERATOR_KEY':'test-operator-password','HER_PORTFOLIO_LOCK_LEGACY':'0'})
        self.env.start();self.addCleanup(self.env.stop)
        self.auth={'Authorization':'Basic '+base64.b64encode(b'operator:test-operator-password').decode()}
    def stage(self,name,status,seconds=0):
        self.rt.update(self.jid,stage={'name':name,'label':name,'status':status,'elapsed':seconds})
    def test_operator_only_even_without_legacy_lock(self):
        for headers in ({},{'Authorization':'Bearer '+self.rt.capability(self.jid)},{'Authorization':'Basic '+base64.b64encode(b'operator:wrong').decode()}):
            self.assertEqual(self.client.get(self.url,headers=headers).status_code,401)
        response=self.client.get(self.url,headers=self.auth)
        self.assertEqual(response.status_code,200);self.assertEqual(response.headers['Cache-Control'],'no-store')
        self.assertIn('attachment',response.headers['Content-Disposition'])
    def test_success_survives_job_expiry_and_downloads_jsonl(self):
        self.rt.update(self.jid,status='running');self.stage('narrate','running');self.stage('narrate','completed',18)
        self.stage('compose','running');self.stage('compose','completed',42)
        self.rt.update(self.jid,status='completed',stage=None,result={'duration':60,'title':'Private title'},performance={'uniqueAssets':9,'assetWorkers':2,'assets':[{'seconds':4,'entityId':'Private subject'}]})
        job=self.rt.store.get('job:'+self.jid);job['expires_at']=time.time()-1;self.rt.store.set('job:'+self.jid,job)
        response=self.client.get(self.url,headers=self.auth);data=response.json
        self.assertEqual(data['slowest_completed_stage'],'compose');self.assertEqual(data['stage_seconds']['narrate'],18)
        self.assertEqual(data['unique_assets'],9);self.assertNotIn('Private',response.text)
        rows=[json.loads(line) for line in self.client.get(self.url+'?format=jsonl',headers=self.auth).text.splitlines()]
        self.assertEqual(rows[0]['kind'],'summary');self.assertEqual(rows[-1]['status'],'completed')
        original=data
        self.rt.update(self.jid,status='failed',error='late worker')
        self.assertEqual(self.client.get(self.url,headers=self.auth).json,original)
    def test_failure_and_killed_worker_keep_last_stage(self):
        self.stage('cutouts','running')
        try:raise ValueError('token=private-secret https://private.test/story')
        except ValueError as exc:details=failure_details(exc)
        self.rt.update(self.jid,status='failed',stage=None,failure=details)
        data=self.client.get(self.url,headers=self.auth).json
        self.assertEqual(data['interrupted_stage'],'cutouts');self.assertEqual(data['failure']['type'],'ValueError')
        self.assertNotIn('private-secret',json.dumps(data));self.assertNotIn('https://',json.dumps(data))
        self.assertTrue(data['failure']['frames'])
    def test_stale_worker_failure_is_recorded(self):
        self.stage('compose','running')
        job=self.rt.store.get('job:'+self.jid);job['heartbeat_at']=time.time()-200;self.rt.store.set('job:'+self.jid,job)
        self.assertEqual(self.rt.get_job(self.jid)['status'],'failed')
        self.assertEqual(self.client.get(self.url,headers=self.auth).json['interrupted_stage'],'compose')
    def test_retention_is_enforced_before_ttl_deletion(self):
        record=self.rt.store.get('diagnostic:'+self.jid);record['expires_at']=time.time()-1;self.rt.store.set('diagnostic:'+self.jid,record)
        self.assertEqual(self.client.get(self.url,headers=self.auth).status_code,410)
    def test_provider_logs_are_normalized_and_bounded(self):
        handler=ProviderEvents()
        for _ in range(MAX_EVENTS+10):
            record=logging.LogRecord('utils.llm_client',logging.WARNING,'/private/file',1,'HTTP 503 retry token=SECRET prompt=private story https://signed.url',(),None)
            handler.handle(record)
        events=handler.drain();self.assertEqual(len(events),MAX_EVENTS);self.assertEqual(handler.drain(),[])
        self.assertEqual(events[0]['http_status'],503);self.assertTrue(events[0]['retry'])
        self.rt.diagnostic_events(self.jid,events)
        text=self.client.get(self.url,headers=self.auth).text
        for private in ('SECRET','signed.url','private story','/private/file'):self.assertNotIn(private,text)
    def test_progress_updates_do_not_create_unbounded_event_history(self):
        self.stage('compose','running')
        for seconds in range(30):self.stage('compose','running',seconds)
        data=self.client.get(self.url,headers=self.auth).json
        self.assertEqual(len(data['events']),1)
        self.assertNotIn('events',self.rt.present(self.rt.get_job(self.jid)))
