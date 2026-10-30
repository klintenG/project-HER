"""Free-tier compute budget: meter, admission control, worker metering, schedules. Offline."""
import importlib.util
import re
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch,MagicMock
from flask import Flask
from agent.portfolio_api import install,Runtime,configured_runtime
from agent.portfolio_store import SQLiteStore,LocalMedia
from agent import portfolio_worker
from utils import compute_meter
from utils.compute_meter import ComputeBudget,billed_seconds,month_key,record,record_best_effort

ORIGIN='https://klinteng.com'
ROOT=Path(__file__).resolve().parents[1]


def ts(year,month,day,hour=12):
    return datetime(year,month,day,hour,tzinfo=timezone.utc).timestamp()


class MeterMathTests(unittest.TestCase):
    def test_billing_matches_cloud_run_minimum_and_startup(self):
        self.assertEqual(billed_seconds(1),60);self.assertEqual(billed_seconds(49),60)
        self.assertEqual(billed_seconds(600),610)

    def test_month_key_is_utc_calendar_month(self):
        self.assertEqual(month_key(ts(2026,10,31,23)),'compute:2026-10');self.assertEqual(month_key(ts(2026,11,1,0)),'compute:2026-11')

    def test_pool_is_memory_bound_for_the_render_job(self):
        # 450,000 GiB-s / 8 GiB = 56,250 s = 937.5 min = ~31 min/day: the figure the plan relies on.
        self.assertEqual(compute_meter.POOL_SECONDS,450000/8);self.assertAlmostEqual(compute_meter.POOL_SECONDS/60/30,31.25)

    def test_record_accumulates_by_source_with_weight(self):
        with tempfile.TemporaryDirectory() as d:
            store=SQLiteStore(Path(d)/'s.db');now=ts(2026,10,5)
            heavy=record(store,'portfolio',600,1.0,now=now);light=record(store,'autopilot',10,0.25,now=now)
            self.assertEqual(heavy,610);self.assertEqual(light,60*0.25)
            doc=store.get(month_key(now))
            self.assertEqual((doc['runs'],doc['total'],doc['portfolio'],doc['autopilot']),(2,heavy+light,heavy,light))
            self.assertGreater(doc['expires_at'],now+60*86400)   # TTL so old months expire

    def test_headroom_reserves_autopilot_for_every_remaining_day(self):
        budget=ComputeBudget(pool=56250,autopilot_daily=1500,visitor_job=1500)
        self.assertEqual(budget.days_left(ts(2026,10,29)),3)           # 29,30,31
        self.assertEqual(budget.headroom(None,ts(2026,10,1)),56250-31*1500)
        self.assertTrue(budget.admits_visitor({'total':0},ts(2026,10,1))[0])
        # Late in the month with Autopilot behind its reserve, visitors are refused until the pool recovers.
        self.assertFalse(budget.admits_visitor({'total':56250-3*1500-1499},ts(2026,10,29))[0])
        self.assertTrue(budget.admits_visitor({'total':56250-3*1500-1500},ts(2026,10,29))[0])

    def test_record_best_effort_is_off_by_default_and_never_raises(self):
        broken=MagicMock();broken.atomic.side_effect=RuntimeError('firestore down')
        with patch.dict('os.environ',{},clear=True):
            self.assertIsNone(record_best_effort('autopilot',time.monotonic(),store=broken));broken.atomic.assert_not_called()
        with patch.dict('os.environ',{'HER_COMPUTE_BUDGET':'1'},clear=True):
            self.assertIsNone(record_best_effort('autopilot',time.monotonic(),store=broken))   # swallowed

    def test_weight_comes_from_the_job_environment(self):
        with tempfile.TemporaryDirectory() as d:
            store=SQLiteStore(Path(d)/'s.db')
            with patch.dict('os.environ',{'HER_COMPUTE_BUDGET':'1','HER_COMPUTE_WEIGHT':'0.25'},clear=True):
                self.assertEqual(record_best_effort('autopilot',time.monotonic(),store=store),15.0)


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.store=SQLiteStore(self.root/'state.db')
        self.budget=ComputeBudget(pool=56250,autopilot_daily=1500,visitor_job=1500)
        self.rt=Runtime(self.store,LocalMedia(self.root/'media'),'s'*48,daily=10,visitor=5,concurrent=1,executor=lambda *a:None,budget=self.budget)
        self.app=Flask(__name__);install(self.app);self.app.extensions['her_portfolio']=self.rt;self.client=self.app.test_client()
        patcher=patch('agent.portfolio_api.threading.Thread');patcher.start();self.addCleanup(patcher.stop)
    def exhaust(self):
        self.store.set(month_key(time.time()),{'total':56250.0,'autopilot':0.0,'portfolio':0.0,'runs':1,'expires_at':time.time()+86400})
    def create(self,key='unique-request-key-0001'):
        return self.client.post('/api/portfolio/jobs',json={'text':'A fictional red cup stands on a table.'},headers={'Origin':ORIGIN,'Idempotency-Key':key})

    def test_open_budget_admits_and_config_reports_open(self):
        self.assertEqual(self.create().status_code,202)
        config=self.client.get('/api/portfolio/config',headers={'Origin':ORIGIN}).json
        self.assertTrue(config['enabled']);self.assertTrue(config['compute_budget_open'])

    def test_exhausted_budget_refuses_new_visitors_and_closes_the_button(self):
        self.exhaust()
        refused=self.create();self.assertEqual(refused.status_code,429);self.assertIn('free rendering time',refused.json['error'])
        config=self.client.get('/api/portfolio/config',headers={'Origin':ORIGIN}).json
        self.assertFalse(config['enabled']);self.assertFalse(config['compute_budget_open'])

    def test_existing_submission_is_still_recoverable_when_budget_closes(self):
        first=self.create();self.exhaust()
        again=self.create();self.assertEqual(again.status_code,202);self.assertEqual(again.json['job_id'],first.json['job_id'])

    def test_operator_override_and_no_budget_behave_as_before(self):
        self.exhaust();self.store.set('policy',{'compute_budget_disabled':True})
        self.assertEqual(self.create().status_code,202)
        self.rt.budget=None;self.store.set('policy',{});self.assertEqual(self.create(key='unique-request-key-0002').status_code,429)  # concurrency slot, not budget
    def test_configured_runtime_enables_budget_only_when_switched_on(self):
        env={'HER_PORTFOLIO_SIGNING_KEY':'s'*48,'HER_PORTFOLIO_LOCAL_DIR':str(self.root/'local')}
        with patch.dict('os.environ',env,clear=True):self.assertIsNone(configured_runtime().budget)
        with patch.dict('os.environ',{**env,'HER_COMPUTE_BUDGET':'1','HER_COMPUTE_POOL_SECONDS':'1000'},clear=True):
            self.assertEqual(configured_runtime().budget.pool,1000)


class WorkerMeteringTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.rt=Runtime(SQLiteStore(self.root/'state.db'),LocalMedia(self.root/'media'),'s'*48,daily=10,visitor=5,concurrent=1,executor=lambda *a:None,
                        dispatcher=lambda jid:'exec-1',start_grace=600)
        self.app=Flask(__name__);install(self.app);self.app.extensions['her_portfolio']=self.rt;self.client=self.app.test_client()
        patcher=patch('agent.portfolio_api.threading.Thread');patcher.start();self.addCleanup(patcher.stop)

    def test_portfolio_worker_meters_every_execution_including_duplicates(self):
        jid=self.client.post('/api/portfolio/jobs',json={'text':'A fictional red cup stands on a table.'},headers={'Origin':ORIGIN,'Idempotency-Key':'unique-request-key-0001'}).json['job_id']
        self.rt.execute=MagicMock()
        with patch.dict('os.environ',{'HER_COMPUTE_BUDGET':'1'}),patch('agent.portfolio_api.configured_runtime',return_value=self.rt),\
             patch('agent.portfolio_api.prepare_worker_environment'),patch('agent.portfolio_api.cleanup_cloud_job'):
            portfolio_worker.main([jid]);portfolio_worker.main([jid])      # second is a duplicate claim: no work, still billed
        doc=self.rt.store.get(month_key(time.time()))
        self.assertEqual(doc['runs'],2);self.assertGreaterEqual(doc['portfolio'],120)   # two >= 1-minute starts

    def test_hard_stop_path_meters_before_exiting(self):
        self.rt.store.set('job:'+'a'*32,{'status':'running','cancel_requested':True,'deadline':time.time()+999,'expires_at':time.time()+999,'created_at':time.time(),'job_id':'a'*32})
        order=[];stop=threading.Event();now=[time.time()]
        def clock():
            now[0]+=15;return now[0]
        with patch.object(portfolio_worker,'stop_descendants'):
            portfolio_worker.watchdog(self.rt,'a'*32,time.time()+2700,stop,exit_process=lambda code:order.append('exit'),clock=clock,interval=0.01,on_exit=lambda:order.append('meter'))
        self.assertEqual(order,['meter','exit'])

    def test_autopilot_worker_meters_each_run(self):
        from automation import autopilot_worker
        service=MagicMock();service.registry=MagicMock()
        with patch.object(autopilot_worker,'Autopilot',return_value=service),patch.object(sys,'argv',['autopilot_worker','verify']),\
             patch('utils.compute_meter.record_best_effort') as meter:
            autopilot_worker.main()
        service.verify.assert_called_once();self.assertEqual(meter.call_args.args[0],'autopilot')


class ReportScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('compute_budget_report',ROOT/'scripts'/'compute_budget_report.py')
        cls.report=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.report)
    def execution(self,start,end,cpu='4',memory='8Gi'):
        return {'status':{'startTime':start,'completionTime':end},'spec':{'template':{'spec':{'containers':[{'resources':{'limits':{'cpu':cpu,'memory':memory}}}]}}}}
    def test_quantities(self):
        q=self.report.quantity
        self.assertEqual((q('8Gi',0),q('2',0),q('1000m',0),q('512Mi',0),q(None,7),q('weird',7)),(8.0,2.0,1.0,0.5,7,7))
    def test_heavy_render_is_ten_pool_minutes_and_light_start_is_a_quarter_minute(self):
        out=self.report.summarize([('her-autopilot',self.execution('2026-10-05T03:30:00Z','2026-10-05T03:40:00Z')),
                                   ('her-autopilot-light',self.execution('2026-10-05T12:00:00Z','2026-10-05T12:00:05Z',cpu='1',memory='2Gi'))])
        self.assertEqual(out['days'][0]['runs'],2);self.assertAlmostEqual(out['days'][0]['heavy_minutes'],10.25,delta=0.06)   # 10 min + one 60 s light start at quarter weight
        self.assertEqual(out['median_render_seconds'],600)
    def test_unusable_executions_are_ignored(self):
        self.assertIsNone(self.report.execution_usage({'status':{}},'her-autopilot'))


class ScheduleBudgetGuard(unittest.TestCase):
    """Fails if the expensive 68-starts-a-day schedule or a 2-hour render cap comes back."""
    @staticmethod
    def starts(cron):
        minute,hour,*_=cron.split()
        if '*/' in minute or '*/' in hour or '-' in minute or '-' in hour or hour=='*' or minute=='*':raise AssertionError('use explicit lists: '+cron)
        return len(minute.split(','))*len(hour.split(','))
    def setUp(self):
        self.tf=(ROOT/'deploy'/'autopilot'/'main.tf').read_text()
        block=self.tf[self.tf.index('variable "autopilot_schedules"'):self.tf.index('validation')]
        self.schedules=dict(re.findall(r'^\s+(generate|prepare|schedule|verify|retry) = "([^"]+)"',block,re.M))
    def test_daily_starts_and_pool_cost_are_small(self):
        self.assertEqual(set(self.schedules),{'generate','prepare','schedule','verify','retry'})
        counts={k:self.starts(v) for k,v in self.schedules.items()}
        heavy=counts['generate'];light=sum(v for k,v in counts.items() if k!='generate')
        self.assertLessEqual(heavy+light,16)                       # originally 68
        self.assertLessEqual(heavy*1.0+light*0.25,6.0)             # start overhead in heavy-minutes/day, excluding the render itself
    def test_only_generate_uses_the_render_job_and_timeout_is_capped(self):
        step=self.tf[self.tf.index('step_job = {'):]
        step=step[:step.index('}')]
        self.assertIn('generate = google_cloud_run_v2_job.autopilot.id',step)
        for name in ('prepare','schedule','verify','retry'):self.assertIn(f'{name} = google_cloud_run_v2_job.autopilot_light.id',step)
        self.assertIn('variable "render_timeout_seconds"',self.tf);self.assertRegex(self.tf,r'render_timeout_seconds" \{ type = number\s+default = 3000')
        self.assertIn('resource "google_cloud_run_v2_job" "autopilot" {',self.tf)   # address unchanged (deletion_protection)
    def test_jobs_declare_metering_weights(self):
        self.assertIn('HER_COMPUTE_BUDGET = "1"',self.tf);self.assertIn('HER_COMPUTE_WEIGHT = "1"',self.tf);self.assertIn('HER_COMPUTE_WEIGHT = "0.25"',self.tf)


if __name__=='__main__':unittest.main()
