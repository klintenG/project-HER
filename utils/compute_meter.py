"""Free-tier compute accounting for the Cloud Run Jobs that render and publish.

Cloud Run's monthly free tier for Jobs/instance-billed CPU is 240,000 vCPU-seconds
and 450,000 GiB-seconds per *billing account*. On the 4 vCPU / 8 GiB render job memory
runs out first, so one month holds 450,000 / 8 = 56,250 render-seconds (~937 minutes,
~31 minutes a day). Everything is measured in these "heavy-equivalent" seconds: a
1 vCPU / 2 GiB job is a quarter of a render-second per second.

Autopilot's daily video has priority. Visitor renders are admitted only if the pool
still covers Autopilot's expected need for the rest of the month plus this render.
All figures are estimates for admission control, not invoices: confirm real billing
with scripts/compute_budget_report.py and the Cloud Billing report.

Enabled by HER_COMPUTE_BUDGET=1 (the deploy script and Terraform set it). Disabled
everywhere else, so local development and tests are unaffected. Never raises into a
job: metering failures are logged and ignored.
"""
from __future__ import annotations
import calendar
import logging
import os
import time
from datetime import datetime, timezone

logger=logging.getLogger(__name__)

POOL_SECONDS=56250.0          # heavy-equivalent seconds in the monthly free tier
AUTOPILOT_DAILY_SECONDS=1500.0  # reserved per remaining day (25 min: one render + overhead)
VISITOR_JOB_SECONDS=1500.0      # assumed cost of one visitor render until measured
MIN_BILLED_SECONDS=60.0         # Cloud Run Jobs bill at least one minute per start
STARTUP_SECONDS=10.0            # container start before our code runs (estimate)
RETENTION_DAYS=75


def enabled():
    return os.getenv('HER_COMPUTE_BUDGET','0').lower() in ('1','true','yes')


def env_float(name,default):
    try:value=float(os.getenv(name,''))
    except ValueError:return default
    return value if value>=0 else default


def month_key(now=None):
    moment=datetime.fromtimestamp(time.time() if now is None else now,timezone.utc)
    return f'compute:{moment.year:04d}-{moment.month:02d}'


def billed_seconds(elapsed):
    """Wall time Cloud Run would bill for one execution (one-minute minimum)."""
    return max(MIN_BILLED_SECONDS,float(elapsed)+STARTUP_SECONDS)


class ComputeBudget:
    def __init__(self,*,pool=POOL_SECONDS,autopilot_daily=AUTOPILOT_DAILY_SECONDS,visitor_job=VISITOR_JOB_SECONDS):
        self.pool=pool;self.autopilot_daily=autopilot_daily;self.visitor_job=visitor_job

    @classmethod
    def from_env(cls):
        return cls(pool=env_float('HER_COMPUTE_POOL_SECONDS',POOL_SECONDS),
                   autopilot_daily=env_float('HER_COMPUTE_AUTOPILOT_DAILY_SECONDS',AUTOPILOT_DAILY_SECONDS),
                   visitor_job=env_float('HER_COMPUTE_VISITOR_JOB_SECONDS',VISITOR_JOB_SECONDS))

    @staticmethod
    def days_left(now):
        """Calendar days left in the UTC month, counting today (conservative)."""
        moment=datetime.fromtimestamp(now,timezone.utc)
        return calendar.monthrange(moment.year,moment.month)[1]-moment.day+1

    def headroom(self,doc,now):
        """Heavy-seconds visitors may still use without endangering Autopilot's daily video."""
        used=float((doc or {}).get('total',0))
        return self.pool-used-self.days_left(now)*self.autopilot_daily

    def admits_visitor(self,doc,now):
        room=self.headroom(doc,now)
        return room>=self.visitor_job,room

    def summary(self,doc,now):
        doc=doc or {}
        return {'pool_minutes':round(self.pool/60,1),'used_minutes':round(float(doc.get('total',0))/60,1),
                'autopilot_minutes':round(float(doc.get('autopilot',0))/60,1),'portfolio_minutes':round(float(doc.get('portfolio',0))/60,1),
                'runs':int(doc.get('runs',0)),'visitor_headroom_minutes':round(self.headroom(doc,now)/60,1)}


def record(store,source,elapsed,weight=1.0,now=None):
    """Add one execution's heavy-equivalent seconds to this month's shared meter."""
    now=time.time() if now is None else now
    seconds=billed_seconds(elapsed)*weight
    key=month_key(now)
    def add(tx):
        doc=tx.get(key) or {'total':0.0,'autopilot':0.0,'portfolio':0.0,'runs':0}
        doc['total']=float(doc.get('total',0))+seconds
        doc[source]=float(doc.get(source,0))+seconds
        doc['runs']=int(doc.get('runs',0))+1
        doc['updated_at']=now
        doc['expires_at']=now+RETENTION_DAYS*86400
        tx.set(key,doc)
    store.atomic(add)
    return seconds


def open_store():
    """The same durable store the portfolio API uses (Firestore in the cloud, SQLite locally)."""
    from pathlib import Path
    import config
    if os.getenv('K_SERVICE') or os.getenv('CLOUD_RUN_JOB'):
        project=os.getenv('GOOGLE_CLOUD_PROJECT') or os.getenv('GCLOUD_PROJECT')
        if not project:raise RuntimeError('GOOGLE_CLOUD_PROJECT is required to meter cloud compute')
        from agent.portfolio_store import FirestoreStore
        return FirestoreStore(project)
    from agent.portfolio_store import SQLiteStore
    root=Path(os.getenv('HER_PORTFOLIO_LOCAL_DIR',str(config.TEMP_DIR/'portfolio')))
    return SQLiteStore(root/'jobs.sqlite3')


def record_best_effort(source,started,store=None,weight=None):
    """Meter one finished execution. `started` is a time.monotonic() value. Never raises."""
    if not enabled():return None
    try:
        weight=env_float('HER_COMPUTE_WEIGHT',1.0) if weight is None else weight
        return record(store or open_store(),source,time.monotonic()-started,weight)
    except Exception as exc:
        logger.warning('Compute metering skipped | type=%s',type(exc).__name__)
        return None
