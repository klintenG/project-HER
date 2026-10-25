"""Authenticated Autopilot administration. Dispatch durable work outside HTTP."""
from __future__ import annotations
import hmac
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from flask import Blueprint, jsonify, render_template, request
from pydantic import ValidationError
import config
from .autopilot import Autopilot, current_settings
from .autopilot_config import Settings, next_scheduled_slot, publication_time


def dispatch(action,command_id):
    args=[action,'--command-id',command_id]
    if action in ('generate','schedule','dry-run','pipeline'):args+=['--force']
    if os.getenv('K_SERVICE'):
        import google.auth
        from google.auth.transport.requests import AuthorizedSession
        project=os.getenv('GOOGLE_CLOUD_PROJECT') or os.getenv('GCLOUD_PROJECT')
        region=os.getenv('AUTOPILOT_JOB_REGION','us-central1')
        job=os.getenv('AUTOPILOT_JOB_NAME','')
        if not project or not job:raise ValueError('Configure the Autopilot Cloud Run Job before dispatching work')
        credentials,_=google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
        response=AuthorizedSession(credentials).post(
            f'https://run.googleapis.com/v2/projects/{project}/locations/{region}/jobs/{job}:run',
            json={'overrides':{'containerOverrides':[{'args':['-m','automation.autopilot_worker',*args]}]}},timeout=30)
        response.raise_for_status()
        return {'operation':response.json().get('name')}
    log_dir=config.BASE_DIR/'data'/'autopilot'/'logs';log_dir.mkdir(parents=True,exist_ok=True)
    with (log_dir/(command_id+'.log')).open('ab') as log:
        process=subprocess.Popen([sys.executable,'-m','automation.autopilot_worker',*args],cwd=config.BASE_DIR,
            stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    return {'worker_pid':process.pid}


def install(app,service_factory=Autopilot,dispatcher=dispatch):
    bp=Blueprint('autopilot',__name__)
    @bp.before_request
    def authorize():
        if request.path in ('/autopilot','/dashboard'):return None
        secret=os.getenv('AUTOPILOT_ADMIN_TOKEN','')
        supplied=request.headers.get('Authorization','')
        if len(secret)<32:return jsonify(error='Autopilot administration is not configured'),503
        if not hmac.compare_digest(supplied,'Bearer '+secret):return jsonify(error='Administrator authorization required'),401
        if request.content_length and request.content_length>16000:return jsonify(error='Request too large'),413
    @bp.after_request
    def headers(response):
        response.headers['Cache-Control']='no-store'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['X-Frame-Options']='DENY'
        return response
    @bp.errorhandler(Exception)
    def error(exc):
        from agent.portfolio_api import safe_message
        return jsonify(error=safe_message(exc)),400 if isinstance(exc,(ValueError,ValidationError)) else 503
    @bp.route('/autopilot')
    @bp.route('/dashboard')
    def page():return render_template('autopilot.html')
    @bp.route('/api/autopilot')
    def overview():
        service=service_factory();registry=service.registry;cfg=service.settings
        stories=registry.stories();posts=registry.publications()
        now=datetime.now(timezone.utc)
        due=publication_time(cfg,now)
        next_slot=next_scheduled_slot(cfg,now)
        day=now.astimezone(ZoneInfo(cfg.timezone)).date().isoformat()
        cost_today=registry.store.get('cost:'+day) or {'reserved_usd':0,'entries':[]}
        commands=registry.store.get('autopilot-commands') or {'ids':[]}
        autopilot_stories=[s for s in stories if s.get('creation_mode')=='AUTOPILOT']
        counts={
            'total_stories':len(stories),
            'autopilot_generated':len(autopilot_stories),
            'ready_unused':sum(s.get('generation_status')=='READY' and s.get('publication_status')=='UNUSED' for s in stories),
            'generating':sum(s.get('generation_status') in ('RESERVED','GENERATING','PREPARED') for s in stories),
            'scheduled':sum(s.get('publication_status') in ('ASSIGNED','SCHEDULED') for s in stories),
            'published':sum(s.get('publication_status') in ('PUBLISHED','PARTIAL') for s in stories),
            'failed':sum(s.get('generation_status')=='FAILED' for s in stories),
            'skipped':sum(s.get('generation_status')=='SKIPPED' for s in stories),
            'legacy_archived':sum(s.get('creation_mode')=='LEGACY' for s in stories),
        }
        return jsonify(settings=cfg.model_dump(),next_publication=due.isoformat() if due else None,
            next_scheduled_slot=next_slot.isoformat(),
            live_publishing_validated=os.getenv('AUTOPILOT_LIVE_VALIDATED','').lower()=='true',
            cost_today=cost_today,
            counts=counts,
            ready_count=counts['ready_unused'],
            stories=stories[-100:][::-1],publications=posts[-100:][::-1],alerts=registry.snapshot()['alerts'][::-1],
            commands=[registry.store.get('command:'+i) for i in commands['ids'][-20:]][::-1])
    @bp.route('/api/autopilot/channels')
    def channels():return jsonify(channels=service_factory().buffer.discover())
    @bp.route('/api/autopilot/settings',methods=['POST'])
    def settings():
        service=service_factory();updates=request.get_json()
        allowed={'enabled','publish_time','category_weights','ready_queue_target'}
        if not isinstance(updates,dict) or set(updates)-allowed:raise ValueError('Only non-secret editorial and schedule settings can be changed here')
        cfg=Settings.model_validate({**service.settings.model_dump(),**updates})
        service.registry.store.set('autopilot-settings',{k:getattr(cfg,k) for k in allowed})
        return jsonify(settings=cfg.model_dump())
    @bp.route('/api/autopilot/actions',methods=['POST'])
    def action():
        service=service_factory();data=request.get_json() or {};action=data.get('action')
        if action=='publish-now':
            sid=data.get('story_id','')
            story=service.registry.store.get('story:'+sid)
            if not story:raise ValueError('Unknown story')
        if action=='skip':
            sid=data.get('story_id','')
            def skip(tx):
                story=tx.get('story:'+sid)
                if not story or story['publication_status']!='UNUSED':raise ValueError('Only unused queued stories can be skipped')
                story.update(generation_status='SKIPPED',updated_at=time.time())
                tx.set('story:'+sid,story)
                return story
            return jsonify(service.registry.store.atomic(skip))
        if action not in ('generate','schedule','verify','dry-run','retry','prepare','pipeline','publish-now'):raise ValueError('Unsupported action')
        cid=uuid.uuid4().hex
        def enqueue(tx):
            index=tx.get('autopilot-commands') or {'ids':[]}
            # Bound expensive admin jobs and suppress double clicks.
            rows=[tx.get('command:'+i) for i in index['ids'][-20:]]
            if any(r and r['action']==action and r['status'] in ('queued','running') and r['created_at']>time.time()-7200 for r in rows):
                raise ValueError('An operation of this type is already queued or running')
            index['ids']=(index['ids']+[cid])[-100:]
            tx.set('command:'+cid,{'command_id':cid,'action':action,'status':'queued','created_at':time.time(),'story_id':data.get('story_id','')})
            tx.set('autopilot-commands',index)
        service.registry.store.atomic(enqueue)
        try:
            result=dispatcher(action,cid)
            service.registry.update('command:'+cid,dispatch=result)
        except Exception:
            # A lost dispatch response may still start a worker: command claim is idempotent.
            service.registry.update('command:'+cid,dispatch_status='unknown')
            raise
        return jsonify(command_id=cid,status='queued'),202
    app.register_blueprint(bp)
