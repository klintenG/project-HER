"""Pause admissions and drain existing native jobs before replacing Cloud Run.

Uses the operator's gcloud identity; preserves emergency pause and daily-limit
settings. It never starts/replays provider work or marks a live job completed.
"""
import subprocess
import time
import uuid
import requests


class DeploymentGuard:
    def __init__(self,project,*,session=None,token_provider=None,clock=time.monotonic,sleep=time.sleep,timeout=3000,legacy_pause=False,force_maintenance_clear=False):
        self.session=session or requests.Session()
        self.token_provider=token_provider or (lambda:subprocess.check_output(['gcloud','auth','print-access-token'],text=True).strip())
        self.root=f'https://firestore.googleapis.com/v1/projects/{project}/databases/(default)/documents/her_portfolio/'
        self.clock=clock;self.sleep=sleep;self.timeout=timeout;self.owner=uuid.uuid4().hex
        self.token=None;self.token_time=0;self.legacy_pause=legacy_pause;self.prior_disabled=False
        self.force_maintenance_clear=force_maintenance_clear

    def request(self,method,key,**kwargs):
        # GETs are safe to repeat. A timed-out PATCH may already have applied,
        # so leave writes to the caller's owner/updateTime checks.
        attempts=3 if method=='GET' else 1
        for attempt in range(attempts):
            if not self.token or self.clock()-self.token_time>1800:
                self.token=self.token_provider();self.token_time=self.clock()
            try:
                response=self.session.request(method,self.root+key,headers={'Authorization':'Bearer '+self.token},timeout=(10,30),**kwargs)
                if method=='GET' and response.status_code==404:return None
                response.raise_for_status();return response.json()
            except (requests.Timeout,requests.ConnectionError):
                if attempt+1==attempts:raise
                self.sleep(attempt+1)

    def set_maintenance(self,enabled,current):
        params=[('updateMask.fieldPaths','maintenance'),('updateMask.fieldPaths','maintenance_owner')]
        if current:params.append(('currentDocument.updateTime',current['updateTime']))
        else:params.append(('currentDocument.exists','false'))
        fields={'maintenance':{'booleanValue':enabled},'maintenance_owner':{'stringValue':self.owner if enabled else ''}}
        if self.legacy_pause:
            params.append(('updateMask.fieldPaths','disabled'))
            fields['disabled']={'booleanValue':True if enabled else self.prior_disabled}
        return self.request('PATCH','policy',params=params,json={'fields':fields})

    def reopen(self):
        for attempt in range(3):
            current=self.request('GET','policy')
            if not current or current['fields'].get('maintenance_owner',{}).get('stringValue')!=self.owner:
                return
            try:
                self.set_maintenance(False,current)
                print('Deployment maintenance cleared; prior daily/emergency settings preserved.',flush=True)
                return
            except (requests.Timeout,requests.ConnectionError):
                # A timed-out conditional PATCH may have succeeded. Re-read
                # owner/updateTime before another attempt; never replay blind.
                if attempt==2:raise
                self.sleep(attempt+1)

    def __enter__(self):
        current=self.request('GET','policy')
        if current and current.get('fields',{}).get('maintenance',{}).get('booleanValue'):
            if not self.force_maintenance_clear:
                raise RuntimeError('Another deployment is already maintaining the studio; no deployment started. Use --clear-maintenance if a previous deployment was aborted.')
            print('Overriding stale maintenance lock (--clear-maintenance specified).',flush=True)
        self.prior_disabled=bool(current and current.get('fields',{}).get('disabled',{}).get('booleanValue'))
        self.set_maintenance(True,current)
        print('New admissions paused for deployment; waiting for existing jobs.',flush=True)
        end=self.clock()+self.timeout;last=None
        try:
            while True:
                active=self.request('GET','active') or {}
                ids=active.get('fields',{}).get('jobs',{}).get('mapValue',{}).get('fields',{})
                running=0
                for jid in ids:
                    job=self.request('GET','job:'+jid)
                    if job and job.get('fields',{}).get('status',{}).get('stringValue') not in ('completed','failed','cancelled'):
                        running+=1
                if running!=last:print(f'Deployment drain: {running} unfinished jobs.',flush=True);last=running
                if not running:return self
                if self.clock()>=end:raise RuntimeError('Existing jobs have not finished; deployment aborted without stopping them.')
                self.sleep(5)
        except BaseException:
            try:self.reopen()
            except Exception as cleanup_error:
                print('WARNING: Could not verify that deployment maintenance was cleared ('+type(cleanup_error).__name__+'). Check the Firestore policy before accepting new jobs.',flush=True)
            raise

    def __exit__(self,exc_type,exc_value,traceback):
        try:self.reopen()
        except Exception as cleanup_error:
            if exc_type is None:raise
            print('WARNING: Deployment failed and maintenance cleanup could not be verified ('+type(cleanup_error).__name__+'). Check the Firestore policy before accepting new jobs.',flush=True)
        return False
