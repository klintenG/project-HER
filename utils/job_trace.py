"""Content-free wall-clock spans persisted on success, failure and cancellation."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import logging
import os
import threading
import time
import uuid
from contextvars import ContextVar
logger=logging.getLogger(__name__)


class JobTrace:
    def __init__(self, path, job_id):
        self.path=Path(path);self.job_id=job_id
        self.origin=time.monotonic();self.lock=threading.RLock();self.spans=[]
        self.current=ContextVar('her_job_span_'+job_id,default=None);self.root_id=None
        self.runtime={key:os.environ[key] for key in ('K_SERVICE','K_REVISION','HER_EDITORIAL_ACTION_WORKERS','HER_REMOTION_CONCURRENCY') if key in os.environ}
        self.runtime['host_cpu_count']=os.cpu_count()
        for key,path in [('cpu_quota','/sys/fs/cgroup/cpu.max'),('memory_limit_bytes','/sys/fs/cgroup/memory.max')]:
            try:self.runtime[key]=Path(path).read_text().strip()
            except OSError:pass
        self.persist()

    def persist(self):
        with self.lock:
            active=sorted((s['start_offset_seconds'],s.get('end_offset_seconds',time.monotonic()-self.origin)) for s in self.spans if s['name']!='end_to_end')
            # The union of measured intervals accounts for overlap; never sum
            # parallel spans and call that total job latency.
            covered=0.;end=0.
            for start,stop in active:
                covered+=max(0,stop-max(start,end));end=max(end,stop)
            row={'schema_version':'job-trace-v1','job_id':self.job_id,'runtime':self.runtime,
                 'elapsed_seconds':round(time.monotonic()-self.origin,6),'covered_wall_seconds':round(covered,6),'spans':self.spans}
            temporary=self.path.with_name(self.path.name+'.'+uuid.uuid4().hex+'.tmp')
            self.path.parent.mkdir(parents=True,exist_ok=True)
            temporary.write_text(json.dumps(row,indent=2));temporary.replace(self.path)

    @contextmanager
    def span(self,name,**metadata):
        row={'id':uuid.uuid4().hex,'name':name,'start_utc':datetime.now(timezone.utc).isoformat(),
             'start_offset_seconds':time.monotonic()-self.origin,'status':'running','metadata':metadata}
        row['parent_span_id']=self.current.get() or self.root_id
        if self.root_id is None:self.root_id=row['id']
        token=self.current.set(row['id'])
        with self.lock:self.spans.append(row);self.persist()
        try:
            yield row['metadata']
        except BaseException as exc:
            row['status']='failed';row['error_type']=type(exc).__name__
            raise
        else:row['status']='succeeded'
        finally:
            with self.lock:
                row['end_utc']=datetime.now(timezone.utc).isoformat()
                row['end_offset_seconds']=time.monotonic()-self.origin
                row['duration_seconds']=row['end_offset_seconds']-row['start_offset_seconds']
                self.persist()
                # Cloud scratch is ephemeral. Persist content-free events in
                # the host's structured log stream as well as the local file.
                logger.info('HER_JOB_SPAN %s',json.dumps({'schema_version':'job-trace-v1','job_id':self.job_id,'runtime':self.runtime,**row},separators=(',',':')))
            self.current.reset(token)

    def call(self,name,fn,*args,**kwargs):
        with self.span(name):return fn(*args,**kwargs)

    def queue_wait(self, created_at):
        now=time.time();duration=max(0,now-created_at)
        with self.lock:
            self.spans.append({'id':uuid.uuid4().hex,'name':'queue_wait','status':'succeeded',
                'start_utc':datetime.fromtimestamp(created_at,timezone.utc).isoformat(),
                'end_utc':datetime.fromtimestamp(now,timezone.utc).isoformat(),
                'start_offset_seconds':-duration,'end_offset_seconds':0,
                'duration_seconds':duration,'metadata':{'clock':'durable_job_wall_clock'}})
            self.persist()
            logger.info('HER_JOB_SPAN %s',json.dumps({'schema_version':'job-trace-v1','job_id':self.job_id,**self.spans[-1]},separators=(',',':')))
