"""Durable Autopilot workflow; only worker processes perform expensive work."""
from __future__ import annotations
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
import requests
import config
from agent.portfolio_store import SQLiteStore, FirestoreStore, GCSMedia
from .autopilot_config import Settings, next_scheduled_slot, publication_time
from .autopilot_store import Registry
from .autonomous_story_director import AutonomousStoryDirector
from .buffer_client import BufferClient, BufferRejected, build_post
from .social_metadata import SocialMetadataGenerator
from .video_quality import ThumbnailComposer, VideoQualityValidator, file_hash


def configured_registry():
    cloud=bool(os.getenv('K_SERVICE') or os.getenv('CLOUD_RUN_JOB'))
    project=os.getenv('GOOGLE_CLOUD_PROJECT') or os.getenv('GCLOUD_PROJECT')
    if cloud:
        if not project:raise ValueError('Cloud Autopilot requires GOOGLE_CLOUD_PROJECT')
        return Registry(FirestoreStore(project,'her_autopilot'))
    root=Path(os.getenv('AUTOPILOT_LOCAL_DIR',str(config.BASE_DIR/'data'/'autopilot')))
    return Registry(SQLiteStore(root/'autopilot.sqlite3'))


def current_settings(registry):
    persisted=registry.store.get('autopilot-settings') or {}
    return Settings.model_validate({**Settings.environment().model_dump(),**persisted})


class PublicMedia:
    """Dedicated publishable bucket. Never expose the private portfolio bucket."""
    def __init__(self):
        self.bucket=os.getenv('AUTOPILOT_PUBLIC_BUCKET','')
        if not self.bucket or self.bucket==os.getenv('HER_PORTFOLIO_BUCKET'):
            raise ValueError('Configure a separate AUTOPILOT_PUBLIC_BUCKET')
        self.media=GCSMedia(self.bucket,os.getenv('GOOGLE_CLOUD_PROJECT') or os.getenv('GCLOUD_PROJECT'))
    def upload(self,path,sid,kind='video'):
        key='autopilot/'+sid+('/video.mp4' if kind=='video' else '/thumbnail.png')
        content_type='video/mp4' if kind=='video' else 'image/png'
        blob=self.media.bucket.blob(key)
        if blob.exists(timeout=15):
            blob.reload(timeout=15)
            if blob.metadata is None or blob.metadata.get('sha256')!=file_hash(path):raise ValueError('Existing public asset hash mismatch')
        else:
            blob.metadata={'sha256':file_hash(path)}
            blob.upload_from_filename(str(path),content_type=content_type,if_generation_match=0,timeout=180)
        url='https://storage.googleapis.com/'+self.bucket+'/'+quote(key,safe='/')
        self.verify(url,content_type)
        return url
    @staticmethod
    def verify(url,content_type='video/mp4'):
        # Only URLs constructed from our configured GCS bucket are accepted.
        bucket=os.getenv('AUTOPILOT_PUBLIC_BUCKET','')
        prefix='https://storage.googleapis.com/'+bucket+'/autopilot/'
        if not bucket or not url.startswith(prefix):raise ValueError('Untrusted public-media URL')
        with requests.get(url,headers={'Range':'bytes=0-1023'},stream=True,allow_redirects=False,timeout=(10,30)) as response:
            if response.status_code not in (200,206):raise ValueError('Media is not publicly reachable')
            if response.headers.get('Content-Type','').split(';')[0]!=content_type:raise ValueError('Incorrect media Content-Type')
            if not next(response.iter_content(1024),b''):raise ValueError('Public media is empty')


class Autopilot:
    def __init__(self,registry=None,buffer=None):
        self.registry=registry or configured_registry()
        self.buffer=buffer or BufferClient()
        self.registry.import_legacy(config.BASE_DIR/"data"/"story_history.json")
    @property
    def settings(self):return current_settings(self.registry)
    def generate(self,force=False,progress=None):
        report=progress or (lambda **fields: None)
        cfg=self.settings
        if not cfg.enabled and not force:return {'status':'paused'}
        lock='lock:generation';token=self.registry.claim(lock,10800)
        if not token:return {'status':'busy'}
        story=None
        try:
            ready=[s for s in self.registry.stories() if s['generation_status']=='READY' and s['publication_status']=='UNUSED']
            if len(ready)>=cfg.ready_queue_target and not force:return {'status':'queue_full'}
            # A stale generation is quarantined, not blindly re-rendered after restart.
            for s in self.registry.stories():
                if s['generation_status'] in ('RESERVED','GENERATING') and s.get('reservation_expires_at',0)<time.time():
                    self.registry.update('story:'+s['story_id'],generation_status='FAILED',error='Worker reservation expired; assets retained for diagnosis')
            from zoneinfo import ZoneInfo
            day=datetime.now(ZoneInfo(cfg.timezone)).date().isoformat()
            spent=(self.registry.store.get('cost:'+day) or {}).get('reserved_usd',0)
            if spent+cfg.engine_reserve_usd+6*cfg.llm_call_reserve_usd>cfg.daily_cost_limit_usd:
                raise ValueError('Insufficient daily budget for a complete story and render; no provider request made')
            report(stage='story',label='Selecting and writing story',percent=3)
            director=AutonomousStoryDirector(cfg,self.registry)
            story=director.select();report(stage='script',label='Writing and reviewing script',percent=8,story_id=story['story_id']);story=director.write(story)
            sid=story['story_id'];key='story:'+sid
            self.registry.spend(cfg.engine_reserve_usd,cfg.daily_cost_limit_usd,'video-engine',sid)
            self.registry.update(key,generation_status='GENERATING',costs={'story_llm_reserved_usd':sum(u['reserved_usd'] for u in director.llm.usage),
                'video_engine_reserved_usd':cfg.engine_reserve_usd,'actual_usd':None})
            out=config.OUTPUT_DIR/('autopilot_'+sid);out.mkdir(parents=True,exist_ok=True)
            from agent.orchestrator import AgentOrchestrator
            from .engine_budget import EngineBudget, active_budget
            budget=EngineBudget(cfg.engine_reserve_usd,cfg.image_request_reserve_usd,cfg.max_image_calls,self.registry,sid)
            from agent.editorial.images import EditorialImages
            image_generator=EditorialImages(autopilot_budget=budget)
            budget_token=active_budget.set(budget)
            try:
                def render_progress(stage):
                    fraction=1 if stage.status=='completed' else stage.progress_pct
                    report(stage=stage.name,label=stage.label,detail=stage.detail or stage.message,
                        percent=round(15+65*(stage.index-1+fraction)/stage.total))
                result=AgentOrchestrator().run(progress_callback=render_progress,input_source=story['script']['narration'],tone='storytelling',
                    video_format='vertical',output_dir=out,ai_images=True,renderer='remotion',
                    content_mode='story',visual_preset='reference_editorial',editorial_assets='auto',
                    tts_provider=config.TTS_PROVIDER,autopilot_image_generator=image_generator,
                target_duration=(cfg.min_video_seconds+cfg.max_video_seconds)//2,
                autopilot_hook=story['script']['hook_text'],autopilot_story_id=sid,
                autopilot_scene_validator=lambda plan:director.validate_plan(story,plan))
            finally:
                active_budget.reset(budget_token)
            if not result.success or not result.video_path:raise ValueError('ProjectHER generation failed: '+'; '.join(result.errors))
            story=self.registry.store.get(key)
            self.registry.update(key,costs={
                'story_llm_reserved_usd':sum(u['reserved_usd'] for u in director.llm.usage if u['task'] in ('ideation','scriptwriter')),
                'validation_llm_reserved_usd':sum(u['reserved_usd'] for u in director.llm.usage if u['task'] not in ('ideation','scriptwriter')),
                'image_estimated_usd':budget.spent,'image_requests':budget.count,
                'engine_reserved_usd':cfg.engine_reserve_usd,'voice_actual_usd':None,'render_actual_usd':None,
                'storage_actual_usd':None,'character_consistency_extra_usd':0,'actual_usd':None})
            video=Path(result.video_path)
            report(stage='quality',label='Creating cover and validating video',percent=83)
            cover=ThumbnailComposer().compose(video,story)
            quality=VideoQualityValidator().validate(video,cfg,story,cover)
            self.registry.update(key,video_path=str(video),cover=cover,quality=quality,
                social_metadata=SocialMetadataGenerator().generate(story))
            if not quality['passed']:raise ValueError('Video quality gate failed: '+', '.join(c['name'] for c in quality['checks'] if c['result']=='FAIL'))
            self.registry.update(key,generation_status='PREPARED')
            if os.getenv('CLOUD_RUN_JOB') or os.getenv('K_SERVICE'):
                private_bucket=os.getenv('HER_PORTFOLIO_BUCKET','')
                if not private_bucket:raise ValueError('Cloud video recovery requires HER_PORTFOLIO_BUCKET')
                private=GCSMedia(private_bucket,os.getenv('GOOGLE_CLOUD_PROJECT') or os.getenv('GCLOUD_PROJECT'))
                vkey='autopilot-archive/'+sid+'/video.mp4';ckey='autopilot-archive/'+sid+'/thumbnail.png'
                private.upload(video,vkey,'video/mp4');private.upload(cover['path'],ckey,'image/png')
                self.registry.update(key,private_archive={'bucket':private_bucket,'video':vkey,'cover':ckey})
            report(stage='upload',label='Uploading validated video and cover',percent=95)
            public=PublicMedia();media_url=public.upload(video,sid);cover_url=public.upload(cover['path'],sid,'cover')
            return self.registry.update(key,generation_status='READY',media_url=media_url,cover_url=cover_url,
                video_sha256=quality['sha256'],ready_at=time.time())
        except Exception as exc:
            if story:
                saved=self.registry.store.get('story:'+story['story_id']) or {}
                self.registry.update('story:'+story['story_id'],generation_status='PREPARED' if saved.get('quality',{}).get('passed') else 'FAILED',error=str(exc))
            self.registry.alert('Generation failed: '+str(exc));raise
        finally:self.registry.release(lock,token)
    def _daily(self,day,due):
        """One video per IST day, independent platform records and queue inventory."""
        def assign(tx):
            index=tx.get('autopilot-index') or {'stories':[], 'publications':[], 'alerts':[]}
            daily=tx.get('daily:'+day)
            existing_story=tx.get('story:'+daily['story_id']) if daily else None
            stories=[tx.get(k) for k in index['stories']] if not daily else []
            if daily:return daily,existing_story
            ready=[s for s in stories if s and s['generation_status']=='READY' and s['publication_status']=='UNUSED' and s.get('quality',{}).get('passed')]
            if not ready:raise ValueError('No validated unused video; skip publication')
            story=min(ready,key=lambda s:s['created_at']);sid=story['story_id']
            daily={'story_id':sid,'publication_date':day,'due_at':due,'platforms':['instagram','youtube']}
            posts=[]
            for platform in daily['platforms']:
                key='publication:'+day+':'+platform
                row={'key':key,'video_id':sid,'publication_date':day,'platform':platform,'due_at':due,'status':'PENDING','attempts':0}
                posts.append((key,row))
                index['publications'].append(key)
            story['publication_status']='ASSIGNED';story['scheduled_date']=day
            tx.set('story:'+sid,story);tx.set('daily:'+day,daily)
            for key,row in posts:tx.set(key,row)
            tx.set('autopilot-index',index)
            return daily,story
        return self.registry.store.atomic(assign)
    def _remote(self,record,post):
        if post.get('schedulingType')!='automatic':
            status='BLOCKED';error='Buffer returned notification publishing; automatic publication required'
        else:
            status={'sent':'SENT','error':'REMOTE_ERROR','scheduled':'SCHEDULED','buffer':'SCHEDULED','sending':'SENDING'}.get(post['status'],'BLOCKED')
            error=(post.get('error') or {}).get('message','')
        result=self.registry.update(record['key'],status=status,buffer_post_id=post['id'],
            external_url=post.get('externalLink'),remote_error=error,verified_at=time.time())
        if status in ('BLOCKED','REMOTE_ERROR'):self.registry.alert(record['platform']+': '+(error or 'Unexpected remote state'))
        return result
    def _begin_submission(self,record,payload,token,**fields):
        def begin(tx):
            lease=tx.get('lock:publishing')
            row=tx.get(record['key'])
            if not lease or lease['token']!=token or lease['expires_at']<=time.time():return False
            if not row or row['status'] not in ('PENDING','RETRY') or row.get('buffer_post_id'):return False
            row.update(fields,status='SUBMITTING',attempts=row['attempts']+1,payload=payload)
            tx.set(record['key'],row)
            return True
        return self.registry.store.atomic(begin)
    def schedule(self,force_dry_run=False,force=False):
        cfg=self.settings
        if not cfg.enabled and not force_dry_run and not force:return {'status':'paused'}
        dry_run=cfg.dry_run or force_dry_run
        now=datetime.now(timezone.utc)
        due=next_scheduled_slot(cfg,now) if force else publication_time(cfg,now)
        if due is None:
            self.registry.alert('Publishing window missed; defer inventory, no catch-up posts')
            return {'status':'window_missed'}
        from zoneinfo import ZoneInfo
        day=due.astimezone(ZoneInfo(cfg.timezone)).date().isoformat()
        lock='lock:publishing';token=self.registry.claim(lock,600)
        if not token:return {'status':'busy'}
        try:
            channels=self.buffer.discover()
            if dry_run:
                ready=[s for s in self.registry.stories() if s['generation_status']=='READY' and s['publication_status']=='UNUSED']
                if not ready:raise ValueError('No ready video for dry-run')
                story=ready[0];PublicMedia.verify(story['media_url'])
                payloads={p:build_post(p,c['id'],story['media_url'],due.isoformat(),story['social_metadata'],story['cover']['offset_ms']) for p,c in channels.items()}
                return {'status':'dry_run','payloads':payloads,'remote_mutations':0}
            if not os.getenv('AUTOPILOT_LIVE_VALIDATED','').lower()=='true':
                raise ValueError('Live publishing requires AUTOPILOT_LIVE_VALIDATED=true after controlled platform tests')
            daily,story=self._daily(day,due.isoformat())
            PublicMedia.verify(story['media_url'])
            results=[]
            for platform,channel in channels.items():
                record=self.registry.store.get('publication:'+day+':'+platform)
                if record['status']=='SENT':results.append(record);continue
                if record.get('buffer_post_id'):
                    results.append(self._remote(record,self.buffer.get(record['buffer_post_id'])));continue
                remote=self.buffer.posts(channel['id'])
                matches=[p for p in remote if p.get('text')==story['social_metadata']['instagram_caption' if platform=='instagram' else 'youtube_description']
                    and p.get('dueAt') and datetime.fromisoformat(p['dueAt'].replace('Z','+00:00'))==datetime.fromisoformat(record['due_at'])]
                if len(matches)==1:
                    results.append(self._remote(record,matches[0]));continue
                if len(matches)>1:
                    self.registry.update(record['key'],status='BLOCKED',error='Multiple matching remote posts');continue
                if record['status'] in ('SUBMITTING','UNKNOWN'):
                    # Empty reads do not prove a lost mutation never committed.
                    self.registry.alert(platform+': ambiguous scheduling attempt; reconciliation found no definitive result')
                    continue
                if record['status']=='BLOCKED' or record.get('retry_at',0)>time.time():continue
                if record['attempts']>=cfg.max_publication_attempts:
                    self.registry.update(record['key'],status='BLOCKED',error='Retry circuit open');continue
                if sum(p['status'] in ('scheduled','buffer','sending') for p in remote)>=cfg.channel_queue_limit:
                    self.registry.update(record['key'],status='RETRY',error='Channel scheduled-post limit reached',retry_at=time.time()+900);continue
                # An old daily assignment must never be sent late under today's slot.
                if datetime.fromisoformat(record['due_at'])<=datetime.now(timezone.utc):
                    self.registry.update(record['key'],status='BLOCKED',error='Assigned publication time missed');continue
                payload=build_post(platform,channel['id'],story['media_url'],record['due_at'],story['social_metadata'],story['cover']['offset_ms'])
                if not self._begin_submission(record,payload,token,channel_id=channel['id'],media_url=story['media_url'],
                        thumbnail_offset=story['cover']['offset_ms'] if platform=='instagram' else None):continue
                try:
                    post=self.buffer.create(payload)
                    results.append(self._remote(record,post))
                except BufferRejected as exc:
                    self.registry.update(record['key'],status='RETRY',error=str(exc),retry_at=time.time()+min(3600,60*2**record['attempts']))
                    self.registry.alert(platform+': '+str(exc))
                except Exception as exc:
                    self.registry.update(record['key'],status='UNKNOWN',error=type(exc).__name__+'; reconcile before any retry')
                    self.registry.alert(platform+': scheduling result unknown')
            self.refresh_story(story['story_id'])
            return {'status':'processed','platforms':results,'story_id':story['story_id']}
        finally:self.registry.release(lock,token)
    def publish_now(self,sid):
        """Explicit operator action, serialized with scheduled publishing."""
        cfg=self.settings
        if cfg.dry_run or os.getenv('AUTOPILOT_LIVE_VALIDATED','').lower()!='true':
            raise ValueError('Immediate publication requires validated live publishing and dry-run disabled')
        lock='lock:publishing';token=self.registry.claim(lock,600)
        if not token:return {'status':'busy'}
        try:
            story=self.registry.store.get('story:'+sid)
            if not story or story.get('generation_status')!='READY' or not story.get('quality',{}).get('passed'):
                raise ValueError('Select a validated READY video')
            if story.get('publication_status') not in ('UNUSED','ASSIGNED','SCHEDULED','PARTIAL'):
                raise ValueError('This video cannot be published again')
            PublicMedia.verify(story['media_url'])
            channels=self.buffer.discover();results=[]
            for platform,channel in channels.items():
                records=[r for r in self.registry.publications() if r['video_id']==sid and r['platform']==platform]
                if len(records)>1:raise ValueError('Multiple publication records require reconciliation')
                if records:
                    record=records[0]
                else:
                    key='publication:manual:'+sid+':'+platform
                    def reserve(tx):
                        index=tx.get('autopilot-index')
                        row={'key':key,'video_id':sid,'publication_date':datetime.now(timezone.utc).date().isoformat(),
                            'platform':platform,'status':'PENDING','attempts':0,'due_at':datetime.now(timezone.utc).isoformat()}
                        current=tx.get(key)
                        if current:return current
                        st=tx.get('story:'+sid)
                        index['publications'].append(key)
                        tx.set(key,row);tx.set('autopilot-index',index)
                        st['publication_status']='ASSIGNED';tx.set('story:'+sid,st)
                        return row
                    record=self.registry.store.atomic(reserve)
                if record['status'] in ('SENT','SENDING'):continue
                if record['status'] in ('UNKNOWN','SUBMITTING','IMMEDIATE_UNKNOWN','IMMEDIATE_SUBMITTING'):
                    raise ValueError('Publication outcome is uncertain; verify before retrying')
                if record.get('buffer_post_id'):
                    remote=self.buffer.get(record['buffer_post_id'])
                    self._remote(record,remote)
                    if remote['status'] in ('sent','sending'):continue
                    if remote['status'] not in ('scheduled','buffer'):raise ValueError('Remote post is not scheduled')
                    payload={'id':record['buffer_post_id'],'mode':'shareNow'}
                else:
                    if record['attempts']>=cfg.max_publication_attempts:raise ValueError('Publication attempt limit reached')
                    payload=build_post(platform,channel['id'],story['media_url'],record['due_at'],story['social_metadata'],story['cover']['offset_ms'])
                    payload.pop('dueAt');payload['mode']='shareNow'
                self.registry.update(record['key'],status='IMMEDIATE_SUBMITTING',attempts=record['attempts']+1,
                    payload=payload,channel_id=channel['id'])
                try:
                    post=self.buffer.edit(payload) if record.get('buffer_post_id') else self.buffer.create(payload)
                    results.append(self._remote(record,post))
                except BufferRejected as exc:
                    self.registry.update(record['key'],status='BLOCKED',error=str(exc))
                    raise
                except Exception:
                    self.registry.update(record['key'],status='IMMEDIATE_UNKNOWN',error='Verify remote outcome before retrying')
                    raise
            self.refresh_story(sid)
            return {'story_id':sid,'platforms':results,'status':'processed'}
        finally:self.registry.release(lock,token)

    def refresh_story(self,sid):
        records=[r for r in self.registry.publications() if r['video_id']==sid]
        sent=[r['platform'] for r in records if r['status']=='SENT']
        state='PUBLISHED' if len(sent)==2 else ('PARTIAL' if sent else ('SCHEDULED' if any(r['status'] in ('SCHEDULED','SENDING') for r in records) else 'ASSIGNED'))
        self.registry.update('story:'+sid,publication_status=state,published_platforms=sent)
    def verify(self):
        results=[]
        for record in self.registry.publications():
            if record['status']=='SENT':continue
            try:
                if record.get('buffer_post_id'):
                    results.append(self._remote(record,self.buffer.get(record['buffer_post_id'])))
                    self.refresh_story(record['video_id'])
                elif record['status'] in ('UNKNOWN','SUBMITTING'):
                    channels=self.buffer.discover();channel=channels[record['platform']]
                    remote=self.buffer.posts(channel['id']);payload=record.get('payload',{})
                    matches=[p for p in remote if p['text']==payload.get('text') and p.get('dueAt') and
                        datetime.fromisoformat(p['dueAt'].replace('Z','+00:00'))==datetime.fromisoformat(record['due_at'])]
                    if len(matches)==1:
                        results.append(self._remote(record,matches[0]));self.refresh_story(record['video_id'])
            except Exception as exc:self.registry.alert('Verification failed: '+type(exc).__name__)
        return {'results':results}

    def prepare_existing(self):
        """Retry only media delivery after a successful render; never spend on images again."""
        results=[]
        for story in self.registry.stories():
            if story['generation_status']!='PREPARED' or not story.get('quality',{}).get('passed'):continue
            lock='lock:prepare:'+story['story_id'];token=self.registry.claim(lock,600)
            if not token:continue
            try:
                video=Path(story['video_path']);cover_path=Path(story['cover']['path'])
                if not video.is_file() or not cover_path.is_file():
                    archive=story.get('private_archive')
                    if not archive:raise ValueError('Validated source is missing and no durable archive is available')
                    from google.cloud import storage
                    bucket=storage.Client().bucket(archive['bucket'])
                    video.parent.mkdir(parents=True,exist_ok=True)
                    bucket.blob(archive['video']).download_to_filename(str(video),timeout=180)
                    bucket.blob(archive['cover']).download_to_filename(str(cover_path),timeout=60)
                if file_hash(video)!=story['quality']['sha256']:raise ValueError('Validated video hash mismatch')
                public=PublicMedia()
                url=public.upload(video,story['story_id']);cover_url=public.upload(cover_path,story['story_id'],'cover')
                results.append(self.registry.update('story:'+story['story_id'],generation_status='READY',media_url=url,cover_url=cover_url,error='',ready_at=time.time()))
            except Exception as exc:self.registry.alert('Media preparation failed: '+str(exc))
            finally:self.registry.release(lock,token)
        return {'prepared':len(results)}

    def retry_failed(self):
        """Reconcile first; retries reuse remote IDs, completed MP4s and daily assignment."""
        self.verify()
        # Pending pre-creation failures use the regular scheduling path. Known remote
        # failures are re-scheduled by editing the same post, never by creating one.
        cfg=self.settings
        if not cfg.enabled or cfg.dry_run:return {'status':'paused_or_dry_run'}
        now=datetime.now(timezone.utc);due=publication_time(cfg,now)
        if due is None:return {'status':'window_missed'}
        from zoneinfo import ZoneInfo
        day=due.astimezone(ZoneInfo(cfg.timezone)).date().isoformat()
        lock='lock:publishing';token=self.registry.claim(lock,600)
        if not token:return {'status':'busy'}
        try:
            for record in self.registry.publications():
                if record['status']!='REMOTE_ERROR' or record['publication_date']!=day:continue
                if record['attempts']>=cfg.max_publication_attempts:
                    self.registry.update(record['key'],status='BLOCKED',error='Retry circuit open')
                    self.registry.alert(record['platform']+': retry circuit open')
                    continue
                if record.get('retry_at',0)>time.time():continue
                post=self.buffer.get(record['buffer_post_id'])
                if post['status']!='error':self._remote(record,post);continue
                self.registry.update(record['key'],status='SUBMITTING',attempts=record['attempts']+1,due_at=due.isoformat())
                try:
                    post=self.buffer.edit({'id':record['buffer_post_id'],'mode':'customScheduled',
                        'schedulingType':'automatic','dueAt':due.isoformat(),'saveToDraft':False})
                    self._remote(record,post)
                except Exception as exc:
                    self.registry.update(record['key'],status='UNKNOWN',error='Retry result unknown: '+type(exc).__name__)
        finally:self.registry.release(lock,token)
        return self.schedule()
