"""Private, bounded run diagnostics. Never persist prompts or raw log messages."""
from __future__ import annotations
import logging
import math
import os
import re
import time
import traceback
from pathlib import Path

logger=logging.getLogger(__name__)
MAX_EVENTS=200


def retention_seconds():
    return max(1,min(90,int(os.getenv('HER_DIAGNOSTICS_DAYS','14'))))*86400


def number(value):
    return round(float(value),3) if isinstance(value,(int,float)) and math.isfinite(value) else None


def identifier(value):
    return re.sub(r'[^a-zA-Z0-9_.-]','_',str(value))[:100]


def new_record(job):
    return {'schema_version':1,'record_type':'run_diagnostics','job_id':job['job_id'],
            'created_at':job['created_at'],'expires_at':job['created_at']+retention_seconds(),
            'status':'queued','events':[],'dropped_events':0,'stage_seconds':{},
            'revision':identifier(os.getenv('K_REVISION','local')),
            'configuration':{key:os.getenv(key,default) for key,default in (
                ('HER_REMOTION_CONCURRENCY','1' if (os.getenv('K_SERVICE') or os.getenv('CLOUD_RUN_JOB')) else '2'),
                ('EDITORIAL_ASSET_WORKERS','2'),('HER_INFERENCE_THREADS','2'),
                ('HER_ALIGNMENT_MODEL','small'))}}


def append(record,event):
    if event['kind']=='provider_warning':
        record['provider_warning_count']=record.get('provider_warning_count',0)+1
        record['retry_warning_count']=record.get('retry_warning_count',0)+int(event.get('retry',False))
    record['events'].append(event)
    if len(record['events'])>MAX_EVENTS:
        record['events'].pop(0);record['dropped_events']+=1
    record['updated_at']=event['at']
    return record


def transition(record,job,fields,previous_stage):
    now=job['updated_at'];event={'at':now,'kind':'job','status':job['status']}
    stage=fields.get('stage')
    if stage:
        stage={key:identifier(stage[key]) for key in ('name','status')}
        stage['seconds']=number(fields['stage'].get('elapsed'))
        event.update(kind='stage',stage=stage)
        record['last_stage']=stage
        if stage['status'] in ('completed','failed'):record['stage_seconds'][stage['name']]=stage['seconds']
    if fields.get('failure'):
        record['failure']=fields['failure']
    if job['status'] in ('completed','failed','cancelled'):
        if job['status']!='completed':
            error=job.get('error') or ''
            record['failure_reason']=('cancelled' if job['status']=='cancelled' else 'deadline_exceeded' if 'deadline' in error else 'worker_stopped' if 'worker stopped' in error else 'worker_start_failed' if 'could not start' in error else 'generation_failed')
        record['finished_at']=now
        record['elapsed_seconds']=number(now-job['created_at'])
        if previous_stage and previous_stage.get('status')=='running':
            # A killed worker cannot report a final duration. Mark it incomplete.
            record['interrupted_stage']=identifier(previous_stage['name'])
        result=job.get('result') or {}
        record['output_seconds']=number(result.get('duration'))
        perf=job.get('performance') or {}
        record['unique_assets']=number(perf.get('uniqueAssets'))
        record['asset_workers']=number(perf.get('assetWorkers'))
        record['asset_seconds']=[number(a.get('seconds')) for a in perf.get('assets',[])[:24]]
    record['status']=job['status']
    append(record,event)
    return event


def failure_details(exc):
    # No exception message, source-code lines, absolute paths, locals or provider bodies.
    return {'type':identifier(type(exc).__name__),'frames':[
        {'file':Path(f.filename).name,'function':identifier(f.name),'line':f.lineno}
        for f in traceback.extract_tb(exc.__traceback__)[-12:]]}


class ProviderEvents(logging.Handler):
    """Collect only normalized warning/error metadata for this worker thread group.

    Raw provider logs may contain credentials or narration. They are never stored.
    The bounded buffer is flushed by the normal progress callback, avoiding a
    Firestore write for every provider log and preserving the video on log failure.
    """
    def __init__(self):
        super().__init__(logging.WARNING)
        import threading
        self.owner=threading.get_ident();self.events=[]

    def emit(self,record):
        import threading
        if record.thread!=self.owner and not ((os.getenv('K_SERVICE') or os.getenv('CLOUD_RUN_JOB')) and threading.current_thread().name.startswith('editorial-assets')):return
        if not record.name.startswith(('agent.','utils.llm_client')) or record.name==__name__:return
        try:
            message=record.getMessage()
            status=re.search(r'\bHTTP\s+(\d{3})\b',message)
            event={'at':record.created,'kind':'provider_warning','component':identifier(record.name),
                   'level':record.levelname,'retry':bool(re.search(r'retry|retrying|throttl|fallback|falling back',message,re.I))}
            if status:event['http_status']=int(status.group(1))
            self.events.append(event)
            if len(self.events)>MAX_EVENTS:self.events.pop(0)
        except Exception:pass

    def drain(self):
        self.acquire()
        try:
            events=self.events;self.events=[];return events
        finally:self.release()
