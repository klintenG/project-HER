"""Scoped native portfolio API over the existing HER rendering pipelines.

Anonymous creation is bounded by transactional shared budgets. Job capabilities
never authorize another job. Public output uses expiring media tickets and a
private durable store; no provider credentials or local filesystem paths cross
this boundary. Cloud Run is fail-closed without explicit durable configuration.
"""
from __future__ import annotations
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import re
import secrets
import threading
import time
import uuid
from datetime import datetime,timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from flask import Blueprint,Response,jsonify,request,stream_with_context
from itsdangerous import URLSafeTimedSerializer,BadSignature,SignatureExpired
from pydantic import BaseModel,ConfigDict,Field,ValidationError,model_validator
import config
from .news_models import NewsError
from .portfolio_store import SQLiteStore,FirestoreStore,LocalMedia,GCSMedia

logger=logging.getLogger(__name__)
PREFIX='/api/portfolio'
TERMINAL={'completed','failed','cancelled'}


class APIError(Exception):
    def __init__(self,message,status=400):self.message=message;self.status=status


class CreateJob(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    text:str=Field(default='',max_length=6000)
    url:str=Field(default='',max_length=2048)
    content_mode:Literal['news','article']='news'
    tone:str='informative'
    format:Literal['vertical','horizontal','square']='vertical'
    target_duration:int=Field(default=0,ge=0,le=90)
    visual_style:str='claymorphism'
    renderer:Literal['remotion','moviepy']='remotion'
    visual_preset:Literal['reference_editorial','default']='reference_editorial'
    editorial_text:Literal['editorial','complete']='editorial'
    editorial_assets:Literal['auto','stock','ai']='auto'
    news_source_policy:Literal['auto','online','supplied']='auto'
    tts_provider:Literal['replicate','edge_tts','google_tts','elevenlabs','chatterbox_turbo']='replicate'
    news_music:bool=False
    language:Literal['english','hindi','french']='english'
    speed:Literal['-20%','-10%','+0%','+10%','+20%']='+0%'
    @model_validator(mode='after')
    def valid(self):
        self.text=self.text.strip();self.url=self.url.strip()
        if not self.text and not self.url:raise ValueError('Enter a topic, story or public article URL.')
        if len(self.text)+len(self.url)>6000:raise ValueError('Input must be at most 6000 characters.')
        if self.tone not in config.TONE_PRESETS:raise ValueError('Unsupported narration tone.')
        if self.visual_style not in config.VISUAL_STYLES:raise ValueError('Unsupported visual style.')
        if self.target_duration and self.target_duration<15:raise ValueError('Choose automatic duration or 15–90 seconds.')
        if self.content_mode=='news' and self.visual_preset=='reference_editorial' and (self.renderer!='remotion' or self.format!='vertical'):
            raise ValueError('Reference editorial requires Remotion and vertical 9:16 output.')
        if self.url and (urlsplit(self.url).scheme not in ('http','https') or len(self.url.split())!=1):raise ValueError('Enter one public HTTP(S) article URL.')
        if self.content_mode=='article' and self.visual_preset!='default':raise ValueError('Classic mode uses its standard visual preset.')
        if self.content_mode=='article' and (self.tts_provider!=config.TTS_PROVIDER or self.language!='english' or self.speed!='+0%' or self.news_music):
            raise ValueError('Classic uses the backend-configured narration provider; language, speed and optional music controls are News-only.')
        return self


def safe_message(text):
    text=str(text)
    text=re.sub(r'https?://\S+','[source]',text)
    text=re.sub(r'/(?:Users|app|private|tmp)/\S+','[internal path]',text)
    text=re.sub(r'(?i)(bearer\s+|(?:api[_-]?key|authorization|token|secret)\s*[=:]\s*)\S+',r'\1[redacted]',text)
    text=re.sub(r'\b(?:sk-|r8_)[A-Za-z0-9_-]{12,}','[redacted]',text)
    return text[:500]


def terminate_worker(process):
    """Stop detached Remotion/Chromium/FFmpeg descendants as well as Python."""
    import psutil
    try:children=psutil.Process(process.pid).children(recursive=True)
    except psutil.NoSuchProcess:children=[]
    for child in reversed(children):
        try:child.terminate()
        except psutil.NoSuchProcess:pass
    if process.is_alive():process.terminate()
    process.join(10)
    _,remaining=psutil.wait_procs(children,timeout=5)
    for child in remaining:
        try:child.kill()
        except psutil.NoSuchProcess:pass
    if process.is_alive():process.kill();process.join(5)


class DurableCancel(threading.Event):
    def __init__(self,runtime,job_id,deadline):
        super().__init__();self.runtime=runtime;self.job_id=job_id;self.deadline=deadline;self.checked=0
    def is_set(self):
        if time.time()>self.deadline:super().set()
        if time.monotonic()-self.checked>2:
            self.checked=time.monotonic()
            job=self.runtime.store.get('job:'+self.job_id)
            if not job or job.get('cancel_requested') or job['status'] in TERMINAL:super().set()
        return super().is_set()
    def wait(self,timeout=None):
        end=time.monotonic()+(timeout if timeout is not None else 2700)
        while not self.is_set() and time.monotonic()<end:super().wait(min(.25,max(0,end-time.monotonic())))
        return self.is_set()


class Runtime:
    def __init__(self,store,media,secret,*,enabled=True,daily=10,visitor=2,concurrent=1,timeout=2700,executor=None):
        if len(secret)<32:raise ValueError('Portfolio signing key must contain at least 32 characters.')
        self.store=store;self.media=media;self.secret=secret;self.enabled=enabled
        self.daily=daily;self.visitor=visitor;self.concurrent=concurrent;self.timeout=timeout
        self.tickets=URLSafeTimedSerializer(secret,salt='her-media-v1')
        self.executor=executor or (self.execute_cloud if os.getenv('K_SERVICE') else self.execute_local)
    def digest(self,value):return hmac.new(self.secret.encode(),value.encode(),hashlib.sha256).hexdigest()
    def capability(self,jid):return self.digest('job-access:'+jid)
    def update(self,jid,**fields):
        def change(tx):
            job=tx.get('job:'+jid)
            if not job:return None
            # A late worker cannot overwrite a recorded timeout or cancellation.
            if job['status'] in TERMINAL:return job
            if fields.get('status') in TERMINAL:
                history=job.get('stages') or []
                if history and history[-1]['status']=='running':
                    history[-1]={**history[-1],'status':'completed' if fields['status']=='completed' else 'failed'}
                    job['stages']=history
            job.update(fields,updated_at=time.time());tx.set('job:'+jid,job);return job
        return self.store.atomic(change)
    def update_stage(self,jid,stage):
        def change(tx):
            job=tx.get('job:'+jid)
            if not job or job['status'] in TERMINAL:return job
            current={'name':stage.name,'label':stage.label,'status':stage.status,'elapsed':round(stage.elapsed,1)}
            history=job.get('stages') or []
            history=[item for item in history if item['name']!=stage.name]+[current]
            job.update(stage=current,stages=history,updated_at=time.time())
            tx.set('job:'+jid,job)
            return job
        return self.store.atomic(change)
    def reserve(self,data,identity,key):
        if not self.enabled or min(self.daily,self.visitor,self.concurrent)<=0:raise APIError('Public generation is temporarily unavailable. Previously generated examples remain available.',503)
        now=time.time();day=datetime.now(timezone.utc).date().isoformat()
        owner=self.digest('visitor:'+identity);request_key=self.digest('request:'+key)
        payload_hash=hashlib.sha256(json.dumps(data.model_dump(),sort_keys=True).encode()).hexdigest()
        jid=uuid.uuid4().hex
        def reserve(tx):
            previous=tx.get('request:'+request_key)
            old=tx.get('job:'+previous['job_id']) if previous else None
            quota=tx.get('quota:'+day) or {'total':0,'visitors':{},'active':{},'expires_at':now+7*86400}
            # Global active slots must also survive UTC day rollover.
            slots=tx.get('active') or {'jobs':{}}
            policy=tx.get('policy') or {}
            if policy.get('maintenance'):raise APIError('The video studio is being updated. Existing jobs continue; please try again after the update finishes.',503)
            if policy.get('disabled'):raise APIError('Public generation is temporarily paused. Previously generated examples remain available.',503)
            if previous:
                if previous['payload_hash']!=payload_hash:raise APIError('Submission key already belongs to different input. Start a new submission.',409)
                if old and old['expires_at']>now:return old,False
                raise APIError('This submission expired. Start a new submission.',410)
            slots['jobs']={j:d for j,d in slots['jobs'].items() if d>now}
            if len(slots['jobs'])>=self.concurrent:raise APIError('A video is already rendering. Please try again after it finishes.',429)
            if not policy.get('daily_limits_disabled') and quota['total']>=self.daily:raise APIError('The public daily generation budget has been reached. Please return tomorrow.',429)
            if not policy.get('daily_limits_disabled') and quota['visitors'].get(owner,0)>=self.visitor:raise APIError('Your daily generation limit has been reached. Please return tomorrow.',429)
            deadline=now+self.timeout
            job={'job_id':jid,'status':'queued','created_at':now,'updated_at':now,'heartbeat_at':now,'deadline':deadline,'expires_at':now+48*3600,
                 'cancel_supported':data.content_mode=='news','cancel_requested':False,'stage':None,'stages':[],'result':None,'error':None}
            quota['total']+=1;quota['visitors'][owner]=quota['visitors'].get(owner,0)+1
            slots['jobs'][jid]=min(deadline,now+120);slots['expires_at']=now+7*86400
            tx.set('quota:'+day,quota);tx.set('active',slots);tx.set('job:'+jid,job)
            tx.set('request:'+request_key,{'job_id':jid,'payload_hash':payload_hash,'expires_at':job['expires_at']})
            return job,True
        return self.store.atomic(reserve)
    def heartbeat(self,jid):
        def beat(tx):
            job=tx.get('job:'+jid);slots=tx.get('active') or {'jobs':{}}
            if not job or job['status'] in TERMINAL:return
            now=time.time();job['heartbeat_at']=now;slots['jobs'][jid]=min(job['deadline'],now+120)
            tx.set('job:'+jid,job);tx.set('active',slots)
        self.store.atomic(beat)
    def execute_local(self,jid,data):
        stopped=threading.Event()
        def keepalive():
            while not stopped.wait(15):self.heartbeat(jid)
        thread=threading.Thread(target=keepalive,daemon=True);thread.start()
        try:self.execute(jid,data)
        finally:stopped.set();thread.join(2)
    def execute_cloud(self,jid,data):
        # Keep expensive Python/media work in a killable child, not the request
        # thread. A deployment/instance restart is reported as an interrupted
        # job; accepted paid work is never replayed automatically.
        import multiprocessing
        process=multiprocessing.get_context('spawn').Process(target=cloud_worker,args=(jid,data.model_dump()),daemon=True)
        try:
            process.start();job=self.get_job(jid);cancel_at=None;heartbeat=0
            while process.is_alive():
                if time.monotonic()-heartbeat>15:self.heartbeat(jid);heartbeat=time.monotonic()
                current=self.get_job(jid)
                if current['status'] in TERMINAL:
                    process.join(1)
                    if process.is_alive():terminate_worker(process)
                    break
                if current.get('cancel_requested') and cancel_at is None:cancel_at=time.monotonic()
                if time.time()>job['deadline'] or (cancel_at is not None and time.monotonic()-cancel_at>20):
                    terminate_worker(process)
                    self.update(jid,status='cancelled' if cancel_at is not None else 'failed',error='Generation cancelled.' if cancel_at is not None else 'Generation exceeded its deadline. No automatic paid retry was made.')
                    break
                process.join(1)
            current=self.get_job(jid)
            if current['status'] not in TERMINAL:self.update(jid,status='failed',error='The rendering worker stopped. No automatic paid retry was made.')
        except Exception as exc:
            logger.error('Portfolio worker %s failed | type=%s',jid,type(exc).__name__)
            self.update(jid,status='failed',error='The rendering worker could not start. No automatic paid retry was made.')
        finally:
            if process.is_alive():terminate_worker(process)
            try:cleanup_cloud_job(jid)
            finally:self.release(jid)
    def release(self,jid):
        def release(tx):
            active=tx.get('active') or {'jobs':{}}
            active['jobs'].pop(jid,None);active['expires_at']=time.time()+7*86400
            tx.set('active',active)
        self.store.atomic(release)
    def get_job(self,jid):
        job=self.store.get('job:'+jid)
        if not job or job['expires_at']<time.time():raise APIError('This job or its output has expired. Create another video.',410)
        if job['status'] not in TERMINAL and (job['deadline']<time.time() or job.get('heartbeat_at',job['created_at'])<time.time()-120):
            job=self.update(jid,status='failed',error='The worker stopped or the generation deadline expired. No automatic paid retry was made.')
            self.release(jid)
        return job
    def authorized(self,jid):
        if not re.fullmatch(r'[0-9a-f]{32}',jid):raise APIError('Job not found.',404)
        token=request.headers.get('Authorization','').removeprefix('Bearer ')
        if not hmac.compare_digest(token,self.capability(jid)):raise APIError('Job not found or access token missing.',404)
        return self.get_job(jid)
    def present(self,job):
        result=job.get('result')
        if result:
            result={k:v for k,v in result.items() if k!='assets'}
            for kind in job['result']['assets']:
                ticket=self.tickets.dumps({'job':job['job_id'],'kind':kind})
                path=f'{PREFIX}/jobs/{job["job_id"]}/media/{kind}?ticket={ticket}'
                result[kind+'_url']=path
                if kind=='video':result['download_url']=path+'&download=1'
        return {k:(job.get(k,[]) if k=='stages' else job[k]) for k in ('job_id','status','created_at','updated_at','expires_at','cancel_supported','cancel_requested','stage','stages','error')}|{'result':result}
    def execute(self,jid,data):
        job=self.get_job(jid);cancel=DurableCancel(self,jid,job['deadline'])
        out=config.OUTPUT_DIR/('portfolio_'+jid);out.mkdir(parents=True,exist_ok=True)
        from utils.job_trace import JobTrace
        trace=JobTrace(out/'portfolio_trace.json',jid);trace.queue_wait(job['created_at'])
        execution=trace.span('worker_end_to_end');execution.__enter__();trace_error=None
        self.update(jid,status='running')
        models_released=False
        def progress(stage):
            nonlocal models_released
            if os.getenv('K_SERVICE') and stage.name=='compose' and stage.status=='running' and not models_released:
                release_cloud_models();models_released=True
            # Stage status comes from the real pipeline. No synthesized percent
            # or prompts, provider logs, private paths or transcript are exposed.
            self.update_stage(jid,stage)
        try:
            if cancel.is_set():raise NewsError('Generation cancelled.','cancelled')
            source='\n'.join(s for s in (data.url,data.text) if s)
            if data.content_mode=='news':
                from .news_pipeline import run_news
                from .news_script import NewsLLM
                class PublicLLM(NewsLLM):
                    def __call__(self,instruction,payload):
                        if instruction.startswith('Write a captivating'):
                            instruction+=' Public demo limit: keep the narration at or below 220 words; never truncate or invent facts to meet the limit.'
                        value=super().__call__(instruction,payload)
                        if isinstance(value,dict) and isinstance(value.get('narration'),str) and len(value['narration'].split())>220:
                            raise NewsError('The script exceeds the public demo speech budget. Shorten the supplied story and retry. No speech or images were generated.')
                        return value
                result=run_news(source,output_dir=out,source_policy=data.news_source_policy,tone=data.tone,language=data.language,
                    target_duration=data.target_duration,video_format=data.format,renderer=data.renderer,tts_provider=data.tts_provider,
                    speed=data.speed,music=data.news_music,visual_preset=data.visual_preset,subtitle_mode=data.editorial_text,
                    asset_mode=data.editorial_assets,progress_callback=progress,cancel_event=cancel,llm=PublicLLM())
            else:
                from .orchestrator import AgentOrchestrator
                # Classic scraping is performed through the same pinned-address
                # retrieval as News; never pass an unvalidated URL to requests.
                if data.url or re.match(r'^https?://',data.text):
                    from .news_research import fetch,extract
                    raw,final=fetch(data.url or data.text)
                    article=extract(raw,final,'article')
                    source=article.title+'\n'+article.text[:14000]+('\n'+data.text if data.url else '')
                result=AgentOrchestrator().run(input_source=source,content_mode='article',output_dir=out,
                    tone=data.tone,video_format=data.format,visual_style=data.visual_style,renderer=data.renderer,
                    target_duration=data.target_duration,tts_provider=data.tts_provider,ai_images=True,progress_callback=progress)
            if cancel.is_set():raise NewsError('Generation cancelled.','cancelled')
            if not result.success:
                raise NewsError('; '.join(result.errors) or 'Generation failed.',result.news_details.get('status','error') if result.news_details else 'error')
            if not 0<result.duration<=180:raise NewsError('The output exceeded the public demo duration limit. Shorten the input and create another video.')
            assets={}
            assets['video']=trace.call('result_upload',self.media.upload,result.video_path,f'portfolio/{jid}/video.mp4','video/mp4')
            if result.thumbnail_path and Path(result.thumbnail_path).is_file():
                assets['poster']=trace.call('result_upload',self.media.upload,result.thumbnail_path,f'portfolio/{jid}/poster.jpg','image/jpeg')
            if result.srt_path and Path(result.srt_path).is_file():
                vtt=out/'captions.vtt'
                captions=re.sub(r'(\d{2}:\d{2}:\d{2}),(\d{3})',r'\1.\2',Path(result.srt_path).read_text())
                vtt.write_text('WEBVTT\n\n'+captions)
                assets['captions']=trace.call('result_upload',self.media.upload,vtt,f'portfolio/{jid}/captions.vtt','text/vtt')
            if cancel.is_set():raise NewsError('Generation cancelled.','cancelled')
            quality=(result.news_details or {}).get('narrative_quality')
            self.update(jid,status='completed',result={'title':result.title,'duration':result.duration,'resolution':result.resolution,'language':data.language,'assets':assets,
                'visual_review_required':bool(quality and not quality.get('acceptancePassed'))},stage=None)
            logger.info('Portfolio job %s completed; duration=%.2f',jid,result.duration)
        except Exception as exc:
            trace_error=exc
            current=self.store.get('job:'+jid) or {}
            is_cancelled=current.get('cancel_requested') and data.content_mode=='news'
            message='Generation cancelled.' if is_cancelled else safe_message(exc) if isinstance(exc,NewsError) else 'Generation failed. Please adjust the input and retry. No automatic paid retry was made.'
            if time.time()>job['deadline']:message='Generation exceeded its deadline. No automatic paid retry was made.'
            self.update(jid,status='cancelled' if is_cancelled else 'failed',error=message,stage=None)
            logger.warning('Portfolio job %s ended | type=%s | cancelled=%s',jid,type(exc).__name__,is_cancelled)
        finally:
            execution.__exit__(type(trace_error) if trace_error else None,trace_error,trace_error.__traceback__ if trace_error else None)
            self.release(jid)


def env_enabled(name):return os.getenv(name,'0').lower() in ('1','true','yes')


def release_cloud_models():
    """Cutouts/alignment are finished; release their native memory before Chrome."""
    import gc
    import sys
    import ctypes
    module=sys.modules.get('agent.cutout_processor')
    if module is not None:getattr(module,'_SESSIONS',{}).clear()
    gc.collect()
    try:
        trim=ctypes.CDLL(None).malloc_trim
        trim.argtypes=[ctypes.c_size_t];trim.restype=ctypes.c_int;trim(0)
    except (AttributeError,OSError):pass
    logger.info('Portfolio inference caches released before composition.')


def cleanup_cloud_job(jid):
    """Remove only this native job's private scratch files after its worker stops."""
    import shutil
    if not re.fullmatch(r'[0-9a-f]{32}',jid):raise ValueError('Invalid native job identifier')
    out=config.OUTPUT_DIR/('portfolio_'+jid)
    for filename,field,folder,prefix in (
        ('editorial_props.json','generationId','editorial','editorial_'),
        ('news_remotion_props.json','generation_id','news',''),
    ):
        try:generation=json.loads((out/filename).read_text()).get(field,'')
        except (OSError,ValueError):continue
        if isinstance(generation,str) and re.fullmatch(re.escape(prefix)+r'[0-9a-f]{32}',generation):
            shutil.rmtree(config.BASE_DIR/'remotion'/'public'/folder/generation,ignore_errors=True)
    shutil.rmtree(out,ignore_errors=True)
    shutil.rmtree(config.TEMP_DIR/'portfolio-work'/jid,ignore_errors=True)


def cloud_worker(jid,data):
    # Keep prompt/media caches private to the child. The supervising process
    # removes this workspace even after a hard timeout or cancellation.
    config.TEMP_DIR=config.TEMP_DIR/'portfolio-work'/jid
    os.environ['HER_REMOTION_CONCURRENCY']='1'
    config.TEMP_DIR.mkdir(parents=True,exist_ok=True)
    for name,folder in (('CACHE_DIR','cache'),('NEWS_TTS_CACHE','speech'),
                        ('NEWS_REFERENCE_CACHE','references'),('NEWS_IDENTITY_IMAGE_CACHE','images'),
                        ('NEWS_CUTOUT_CACHE','cutouts')):
        setattr(config,name,config.TEMP_DIR/folder)
        getattr(config,name).mkdir(parents=True,exist_ok=True)
    config.NARRATION_VISUAL_SETTINGS={**config.NARRATION_VISUAL_SETTINGS,'allowPhraseTimingFallback':False}
    config.NEWS_MAX_REAL_IMAGE_CALLS=min(config.NEWS_MAX_REAL_IMAGE_CALLS,4)
    config.EDITORIAL_MAX_SUPPORT_CALLS=min(config.EDITORIAL_MAX_SUPPORT_CALLS,24)
    configured_runtime().execute(jid,CreateJob.model_validate(data))


def configured_runtime():
    cloud=bool(os.getenv('K_SERVICE'))
    secret=os.getenv('HER_PORTFOLIO_SIGNING_KEY','')
    if len(secret)<32:raise APIError('Native generation is unavailable until secure job access is configured.',503)
    if cloud:
        bucket=os.getenv('HER_PORTFOLIO_BUCKET');project=os.getenv('GOOGLE_CLOUD_PROJECT') or os.getenv('GCLOUD_PROJECT')
        if not bucket or not project:raise APIError('Native generation is unavailable until durable job and output storage is configured.',503)
        if not env_enabled('HER_PORTFOLIO_LOCK_LEGACY'):raise APIError('Public generation is unavailable until legacy endpoints are protected.',503)
        if not config.REPLICATE_API_TOKEN:
            raise APIError('Public generation is unavailable until Replicate narration is configured on the backend.',503)
        import importlib.util
        model=os.getenv('HER_ALIGNMENT_MODEL','small')
        cache=config.ASSETS_DIR/'alignment'/('models--Systran--faster-whisper-'+model)
        if importlib.util.find_spec('faster_whisper') is None or not any(cache.glob('snapshots/*/model.bin')):
            raise APIError('Public generation is unavailable until the exact speech-alignment model is installed in the backend image.',503)
        store=FirestoreStore(project);media=GCSMedia(bucket,project)
    else:
        root=Path(os.getenv('HER_PORTFOLIO_LOCAL_DIR',str(config.TEMP_DIR/'portfolio')))
        store=SQLiteStore(root/'jobs.sqlite3');media=LocalMedia(root/'media')
    return Runtime(store,media,secret,enabled=env_enabled('HER_PORTFOLIO_ENABLED'),daily=int(os.getenv('HER_PORTFOLIO_DAILY_LIMIT','10')),
        visitor=int(os.getenv('HER_PORTFOLIO_VISITOR_LIMIT','2')),concurrent=int(os.getenv('HER_PORTFOLIO_CONCURRENCY','1')))


def install(app):
    bp=Blueprint('her_portfolio',__name__,url_prefix=PREFIX)
    lock=threading.Lock()
    def runtime():
        with lock:
            if 'her_portfolio' not in app.extensions:app.extensions['her_portfolio']=configured_runtime()
            return app.extensions['her_portfolio']
    def allowed_origins():
        origins=set(os.getenv('HER_PORTFOLIO_ORIGINS','https://klinteng.com,https://www.klinteng.com').split(','))
        if not os.getenv('K_SERVICE'):origins.update(('http://127.0.0.1:8766','http://localhost:8766','http://127.0.0.1:8767'))
        return origins
    @bp.before_request
    def guard():
        origin=request.headers.get('Origin')
        if origin and origin not in allowed_origins():raise APIError('This website is not allowed to use the video API.',403)
        if request.method=='POST' and origin not in allowed_origins():raise APIError('Submit generation requests from the portfolio studio.',403)
        if request.content_length and request.content_length>16000:raise APIError('Request is too large.',413)
    @bp.after_request
    def headers(response):
        response.headers['Cache-Control']='no-store';response.headers['Referrer-Policy']='no-referrer'
        return response
    @bp.errorhandler(APIError)
    def expected(exc):return jsonify({'error':exc.message}),exc.status
    @bp.errorhandler(Exception)
    def unexpected(exc):
        logger.error('Portfolio API %s unavailable | type=%s',request.path,type(exc).__name__)
        return jsonify({'error':'The video backend is temporarily unavailable. Try again later; previously generated examples remain available.'}),503
    @bp.route('/config')
    def capabilities():
        rt=runtime()
        # Check actual durable-store access before enabling the Generate action.
        rt.store.get('health')
        rt.media.exists({'key':'health-check','size':0,'content_type':'application/octet-stream'})
        policy=rt.store.get('policy') or {}
        enabled=rt.enabled and min(rt.daily,rt.visitor,rt.concurrent)>0 and not policy.get('disabled') and not policy.get('maintenance')
        return jsonify({'version':1,'enabled':enabled,'limits':{'input_characters':6000,'duration_seconds':90,'output_seconds':180,'daily_jobs':rt.daily,'visitor_daily_jobs':rt.visitor,'daily_limits_disabled':bool(policy.get('daily_limits_disabled')), 'concurrent_jobs':rt.concurrent,'output_hours':48},
            'options':{'tone':list(config.TONE_PRESETS),'visual_style':list(config.VISUAL_STYLES),
                       'format':['vertical','horizontal','square'],'renderer':['remotion','moviepy'],
                       'tts_provider':['replicate','edge_tts','google_tts','elevenlabs','chatterbox_turbo']},
            'defaults':{k:v.default for k,v in CreateJob.model_fields.items()},
            'classic_defaults':{'tts_provider':config.TTS_PROVIDER,'language':'english','speed':'+0%'},
            'cancellation':{'news':True,'article':False}})
    def identity():
        # Never trust the leftmost client-supplied forwarding address. Default
        # to the socket peer; operators may explicitly configure trusted hops.
        hops=int(os.getenv('HER_TRUSTED_PROXY_HOPS','0'))
        addresses=[p.strip() for p in request.headers.get('X-Forwarded-For','').split(',') if p.strip()]
        ip=addresses[-hops] if hops>0 and len(addresses)>=hops else request.remote_addr or 'unknown'
        try:
            parsed=ipaddress.ip_address(ip)
            return str(ipaddress.ip_network(str(parsed)+'/64',strict=False)) if parsed.version==6 else str(parsed)
        except ValueError:return 'unknown'
    @bp.route('/jobs',methods=['POST'])
    def create():
        if not request.is_json:raise APIError('Send a JSON request.',415)
        raw=request.stream.read(16001)
        if len(raw)>16000:raise APIError('Request is too large.',413)
        try:body=json.loads(raw)
        except (ValueError,UnicodeDecodeError):raise APIError('Send a valid JSON request.',400)
        try:data=CreateJob.model_validate(body)
        except ValidationError as exc:
            first=exc.errors()[0];raise APIError(str(first['msg']).removeprefix('Value error, '),422)
        key=request.headers.get('Idempotency-Key','')
        if not re.fullmatch(r'[a-zA-Z0-9_-]{16,80}',key):raise APIError('A valid submission key is required.',400)
        # DNS and redirects are revalidated again by the actual fetcher. The
        # validation at this boundary also rejects literal metadata/private URLs.
        from .news_research import public_url
        for url in [data.url,*re.findall(r'https?://[^\s<>]+',data.text)]:
            if url:
                try:public_url(url.rstrip('.,)'))
                except NewsError:raise APIError('Article links must resolve only to public HTTP(S) addresses on standard ports.',422)
        rt=runtime();job,fresh=rt.reserve(data,identity(),key)
        if fresh:
            try:threading.Thread(target=rt.executor,args=(job['job_id'],data),daemon=True).start()
            except Exception:
                rt.update(job['job_id'],status='failed',error='The worker could not start. No model work was submitted.');rt.release(job['job_id']);raise
        return jsonify({'job_id':job['job_id'],'access_token':rt.capability(job['job_id']),'expires_at':job['expires_at'],'status':job['status'],'cancel_supported':job['cancel_supported']}),202
    @bp.route('/submission')
    def recover():
        key=request.headers.get('Idempotency-Key','')
        if not re.fullmatch(r'[a-zA-Z0-9_-]{16,80}',key):raise APIError('Submission not found.',404)
        rt=runtime()
        record=rt.store.get('request:'+rt.digest('request:'+key))
        if not record:raise APIError('The previous submission could not be located. Its acknowledgement may still be pending; do not submit with a new key immediately.',404)
        job=rt.get_job(record['job_id'])
        return jsonify({'job_id':job['job_id'],'access_token':rt.capability(job['job_id']),'expires_at':job['expires_at'],'status':job['status'],'cancel_supported':job['cancel_supported']})
    @bp.route('/jobs/<jid>')
    def status(jid):
        rt=runtime();return jsonify(rt.present(rt.authorized(jid)))
    @bp.route('/jobs/<jid>/events')
    def events(jid):
        rt=runtime();rt.authorized(jid)
        @stream_with_context
        def stream():
            last=None;started=time.monotonic()
            # Finite streams let a client reconnect without tying up a worker
            # indefinitely. Polling uses the same durable record.
            while time.monotonic()-started<55:
                job=rt.get_job(jid);value=rt.present(job);encoded=json.dumps(value)
                if encoded!=last:
                    kind='done' if job['status'] in TERMINAL else 'progress'
                    yield 'event: '+kind+'\ndata: '+encoded+'\n\n';last=encoded
                else:yield ': keepalive\n\n'
                if job['status'] in TERMINAL:return
                time.sleep(2)
        return Response(stream(),mimetype='text/event-stream',headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})
    @bp.route('/jobs/<jid>/cancel',methods=['POST'])
    def cancel(jid):
        rt=runtime();job=rt.authorized(jid)
        if not job['cancel_supported']:raise APIError('This rendering mode does not support cancellation.',409)
        if job['status'] in TERMINAL:return jsonify(rt.present(job))
        job=rt.update(jid,cancel_requested=True)
        return jsonify({'status':'cancelling','job_id':jid}),202
    @bp.route('/jobs/<jid>/media/<kind>',methods=['GET','HEAD'])
    def media(jid,kind):
        rt=runtime()
        try:ticket=rt.tickets.loads(request.args.get('ticket',''),max_age=1800)
        except (BadSignature,SignatureExpired):raise APIError('This media link expired. Refresh the job to renew it.',410)
        if ticket!={'job':jid,'kind':kind}:raise APIError('Media not found.',404)
        job=rt.get_job(jid);asset=(job.get('result') or {}).get('assets',{}).get(kind)
        if not asset or job['status']!='completed':raise APIError('Media is unavailable.',404)
        if not rt.media.exists(asset):raise APIError('This output expired. Create another video.',410)
        size=asset['size'];start=0;end=size-1;status_code=200
        header=request.headers.get('Range')
        if header:
            match=re.fullmatch(r'bytes=(\d*)-(\d*)',header)
            if not match or not any(match.groups()):return Response(status=416,headers={'Content-Range':f'bytes */{size}'})
            a,b=match.groups()
            if not a:start=max(0,size-int(b))
            else:start=int(a);end=min(int(b),size-1) if b else size-1
            if start>end or start>=size:return Response(status=416,headers={'Content-Range':f'bytes */{size}'})
            status_code=206
        headers={'Accept-Ranges':'bytes','Content-Length':str(end-start+1),'Content-Type':asset['content_type'],'X-Content-Type-Options':'nosniff'}
        if status_code==206:headers['Content-Range']=f'bytes {start}-{end}/{size}'
        if request.args.get('download')=='1':headers['Content-Disposition']=f'attachment; filename="project-her-{jid[:8]}.mp4"'
        return Response(b'' if request.method=='HEAD' else rt.media.chunks(asset,start,end),status=status_code,headers=headers)
    app.register_blueprint(bp)
    @app.before_request
    def protect_legacy():
        if not env_enabled('HER_PORTFOLIO_LOCK_LEGACY'):return
        protected=request.path.startswith(('/api/','/output/','/daily-output/','/effect-previews/')) and not request.path.startswith(PREFIX+'/')
        if not protected:return
        operator=os.getenv('HER_OPERATOR_KEY','')
        auth=request.authorization
        if operator and auth and auth.type=='basic' and auth.username=='operator' and hmac.compare_digest(auth.password or '',operator):return
        return jsonify({'error':'Public generation and job access use the native portfolio studio. Operator authentication is required for this endpoint.'}),401,{'WWW-Authenticate':'Basic realm="Project HER operator", charset="UTF-8"'}
    @app.after_request
    def portfolio_cors(response):
        # Registered after the legacy wildcard CORS hook: Flask executes after
        # hooks in reverse registration order, so web_ui also delegates here.
        if request.path.startswith(PREFIX+'/') or env_enabled('HER_PORTFOLIO_LOCK_LEGACY'):
            response.headers.pop('Access-Control-Allow-Origin',None)
            origin=request.headers.get('Origin')
            if origin in allowed_origins():response.headers['Access-Control-Allow-Origin']=origin
            response.headers['Vary']='Origin'
            response.headers['Access-Control-Allow-Headers']='Content-Type, Authorization, Idempotency-Key, Range'
            response.headers['Access-Control-Allow-Methods']='GET, HEAD, POST, OPTIONS'
            response.headers['Access-Control-Expose-Headers']='Content-Length,Content-Range,Content-Disposition,Retry-After'
        return response
    app.extensions['her_portfolio_cors']=portfolio_cors
