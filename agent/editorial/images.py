"""Explicit per-job Replicate tiers and bounded calls, without global mutation."""
import config
from utils.image_models import adapter_for, build_input, ImageModelConfigError
import logging
import threading
from agent.news_assets import NewsImageGenerator
from agent.news_models import NewsError
logger=logging.getLogger(__name__)


class EditorialImages(NewsImageGenerator):
    def __init__(self,trace=None,primary_count=0):
        super().__init__()
        self.replicate_model=config.EDITORIAL_SUPPORT_IMAGE_MODEL
        self.primary_limit=primary_count*(2+config.NEWS_ASSET_RETRIES)+4 if primary_count else 0
        self.primary_calls=0
        self.support_calls=0
        self.real_calls=0
        self._budget_lock=threading.Lock()
        self._provider_blocked_status=None
        from utils.provider_admission import ProviderAdmission
        self.admission=ProviderAdmission(self.replicate_token,config.EDITORIAL_IMAGE_MIN_INTERVAL,scope='image')
        self.trace=trace
        self._active_http=0
        self._peak_http=0
        self._active_predictions=0
        self._peak_predictions=0
        self.prediction_records=[]
        self.metrics={
            'createRequests':0,
            'acceptedPredictions':0,
            'rateLimitResponses':0,
            'backoffSeconds':0,
            'pollRetries':0,
            'admissionWaitSeconds':0.0,
            'apiDurationSeconds':0.0,
            'downloadDurationSeconds':0.0,
            'peakHttpConcurrency':0,
            'peakProviderConcurrency':0,
            'predictionRecords':self.prediction_records,
        }

    def metric(self,name,value=1):
        with self._budget_lock:self.metrics[name]+=value

    def _enter_http(self):
        with self._budget_lock:
            self._active_http+=1
            if self._active_http>self._peak_http:
                self._peak_http=self._active_http
                self.metrics['peakHttpConcurrency']=self._peak_http

    def _exit_http(self):
        with self._budget_lock:
            self._active_http=max(0,self._active_http-1)

    def _enter_prediction(self):
        with self._budget_lock:
            self._active_predictions+=1
            if self._active_predictions>self._peak_predictions:
                self._peak_predictions=self._active_predictions
                self.metrics['peakProviderConcurrency']=self._peak_predictions

    def _exit_prediction(self):
        with self._budget_lock:
            self._active_predictions=max(0,self._active_predictions-1)

    async def subject(self,prompt,path):
        with self._budget_lock:
            if self.support_calls>=config.EDITORIAL_MAX_SUPPORT_CALLS:
                raise NewsError('Supporting-image call limit reached; reuse cached assets or increase EDITORIAL_MAX_SUPPORT_CALLS.')
            self.support_calls+=1
        if not self.replicate_token:raise NewsError('Editorial illustrations require REPLICATE_API_TOKEN.')
        # Explicit low-cost model; no hidden upgrade through global preferences.
        return await self.real_subject(prompt,path,tier='support')

    async def identity_subject(self,prompt,path):
        return await self.real_subject(prompt,path,tier='person')

    def _invoke_prediction(self,prompt,path,reference,tier,turbo=None,seed=None,aspect_ratio='1:1'):
        import inspect
        kwargs={'turbo':turbo,'seed':seed,'aspect_ratio':aspect_ratio}
        target=getattr(self._prediction,'side_effect',self._prediction) or self._prediction
        try:
            sig=inspect.signature(target)
            if not any(p.kind==inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                kwargs={k:v for k,v in kwargs.items() if k in sig.parameters}
        except Exception:
            pass
        return self._prediction(prompt,path,reference,tier,**kwargs)

    async def scene_subject(self,prompt,path,reference=None,turbo=None,seed=None,aspect_ratio='1:1'):
        with self._budget_lock:
            if self.primary_calls>=self.primary_limit:raise NewsError('Sentence primary capacity exhausted after bounded repairs.')
            self.primary_calls+=1
        return await self._invoke_prediction(prompt,path,reference,'action' if reference is not None else 'support',turbo=turbo,seed=seed,aspect_ratio=aspect_ratio)

    async def event_scene_subject(self,prompt,path,reference=None,turbo=None,seed=None,aspect_ratio='1:1'):
        """Event scenes use the explicit multi-reference quality tier."""
        with self._budget_lock:
            if self.primary_calls>=self.primary_limit:raise NewsError('Event scene capacity exhausted after bounded repairs.')
            self.primary_calls+=1
        return await self._invoke_prediction(prompt,path,reference,'event',turbo=turbo,seed=seed,aspect_ratio=aspect_ratio)

    async def alternate_scene_subject(self,prompt,path,turbo=None,seed=None,aspect_ratio='1:1'):
        """One bounded second-model attempt after scene-specific repairs fail."""
        with self._budget_lock:
            if self.primary_calls>=self.primary_limit:raise NewsError('Sentence primary capacity exhausted after bounded repairs.')
            self.primary_calls+=1
        return await self._invoke_prediction(prompt,path,None,'support_alternate',turbo=turbo,seed=seed,aspect_ratio=aspect_ratio)

    async def fallback_scene_subject(self,prompt,path,reference,kind='premium',aspect_ratio='1:1'):
        if kind == 'premium' and not config.PROJECTHER_PREMIUM_FALLBACK_ENABLED:
            raise NewsError('Premium image fallback is disabled.')
        if kind == 'alternate_edit' and not config.PROJECTHER_ALTERNATE_EDIT_FALLBACK_ENABLED:
            raise NewsError('Alternate image editing fallback is disabled.')
        return await self._invoke_prediction(prompt,path,reference,kind,aspect_ratio=aspect_ratio)

    async def action_subject(self,prompt,path,reference=None,turbo=None,seed=None,aspect_ratio='1:1'):
        return await self.real_subject(prompt,path,reference,tier='action',turbo=turbo,seed=seed,aspect_ratio=aspect_ratio)

    async def real_subject(self,prompt,path,reference=None,tier='person',turbo=None,seed=None,aspect_ratio='1:1'):
        if tier in ('person','action'):
            with self._budget_lock:
                limit=config.NEWS_MAX_REAL_IMAGE_CALLS+self.primary_limit if self.primary_limit else config.NEWS_MAX_REAL_IMAGE_CALLS
                if self.real_calls>=limit:raise NewsError('Real-person image call limit reached.')
                self.real_calls+=1
        return await self._invoke_prediction(prompt,path,reference,tier,turbo=turbo,seed=seed,aspect_ratio=aspect_ratio)

    async def _prediction(self,prompt,path,reference,tier,turbo=None,seed=None,aspect_ratio='1:1'):
        import asyncio
        # The provider deadline starts at first admission; time spent queued
        # behind the shared account rate limit is not provider latency.
        admitted=asyncio.Event()
        task=asyncio.ensure_future(self._prediction_request(prompt,path,reference,tier,admitted,turbo=turbo,seed=seed,aspect_ratio=aspect_ratio))
        waiter=asyncio.ensure_future(admitted.wait())
        try:
            await asyncio.wait({task,waiter},return_when=asyncio.FIRST_COMPLETED)
            waiter.cancel()
            return await asyncio.wait_for(task,timeout=max(config.EDITORIAL_IMAGE_TIMEOUT,300) if tier=='event' else config.EDITORIAL_IMAGE_TIMEOUT)
        except asyncio.TimeoutError:
            raise NewsError('Image prediction outcome unavailable after its deadline; no automatic new prediction will be submitted.') from None
        except asyncio.CancelledError:
            task.cancel();waiter.cancel();raise

    async def _prediction_request(self,prompt,path,reference,tier,admitted=None,turbo=None,seed=None,aspect_ratio='1:1'):
        import asyncio
        import base64
        from datetime import datetime,timezone
        import io
        import re
        import time
        import httpx
        from PIL import Image
        from agent.news_research import fetch
        if not self.replicate_token:raise NewsError('Editorial images require REPLICATE_API_TOKEN.')
        role=tier if tier in ('premium','alternate_edit','event') else 'support_fallback' if tier=='support_alternate' else 'continuity' if reference else 'support' if tier in ('support','action') else 'identity'
        model=getattr(config,f'PROJECTHER_IMAGE_{role.upper()}_MODEL') if role in ('premium','alternate_edit','identity') else config.EDITORIAL_ACTION_IMAGE_MODEL if role=='continuity' else config.EDITORIAL_FALLBACK_IMAGE_MODEL if role=='support_fallback' else config.EDITORIAL_SUPPORT_IMAGE_MODEL
        adapter_name=config.PROJECTHER_IMAGE_ADAPTERS.get(role)
        if tier=='event':
            model=config.EDITORIAL_EVENT_IMAGE_MODEL
            adapter_name=None  # Capability is selected from the event model, not the legacy tier.
        adapter=adapter_for(model,adapter_name)
        is_pruna=adapter.name=='pruna_edit'
        is_nano=adapter.name=='nano_banana'
        reference_count=0
        if reference and adapter.references != 0:
            if adapter.references == 1:
                source_paths = [reference.path]
            else:
                paths = getattr(reference, 'paths', None)
                source_paths = paths or [reference.path]
            reference_count = len(source_paths)
            encoded = []
            for source_path in source_paths:
                with Image.open(source_path) as image:
                    if 'A' in image.getbands():
                        rgba = image.convert('RGBA')
                        rgba.thumbnail((640, 640))
                        canvas = Image.new('RGBA', (1024, 1024), (216, 216, 216, 255))
                        canvas.alpha_composite(rgba, ((1024 - rgba.width) // 2, (1024 - rgba.height) // 2))
                        image = canvas.convert('RGB')
                    else:
                        image = image.convert('RGB')
                        image.thumbnail((1024, 1024))
                    buffer = io.BytesIO()
                    fmt = 'PNG' if (is_nano or is_pruna) else 'JPEG'
                    image.save(buffer, format=fmt, quality=90)
                mime = 'image/png' if fmt == 'PNG' else 'image/jpeg'
                encoded.append(f'data:{mime};base64,' + base64.b64encode(buffer.getvalue()).decode())
        else:
            encoded = []
        try:
            inputs=build_input(model,prompt,encoded,config.PROJECTHER_IMAGE_ASPECT_RATIO if aspect_ratio=='1:1' else aspect_ratio,
                config.PROJECTHER_PRUNA_TURBO if turbo is None else turbo,
                config.PROJECTHER_PRUNA_SEED if seed is None else seed,adapter_name)
        except ImageModelConfigError as exc:
            raise NewsError(f'Image model capability error before request: {exc}') from exc
        headers={'Authorization':'Bearer '+self.replicate_token,'Prefer':'wait=10'};prediction=None;finished=False
        iso_now=lambda:datetime.now(timezone.utc).isoformat()
        estimated_cost=getattr(config,'REPLICATE_MODEL_ESTIMATED_COSTS',{}).get(model,0.010)
        if role in ('premium','alternate_edit','support_fallback') and config.PROJECTHER_IMAGE_BUDGET_USD > 0:
            with self._budget_lock:
                spent=sum(float(r.get('estimated_cost') or 0) for r in self.prediction_records if r.get('prediction_id'))
            if spent+estimated_cost>config.PROJECTHER_IMAGE_BUDGET_USD:
                raise NewsError(f'Image planning budget would be exceeded by {role} fallback; no prediction submitted.')
        telemetry={
            'provider':'replicate',
            'image_role':role,
            'configured_model':model,
            'actual_model':model,
            'fallback_reason':'quality_retry' if role in ('premium','alternate_edit','support_fallback') else None,
            'model_name':model,
            'model_version':None,
            'tier':tier,
            'target_path':str(path),
            'reference_count':reference_count,
            'turbo':inputs.get('turbo') if is_pruna else None,
            'seed':inputs.get('seed') if is_pruna else None,
            'estimated_cost':estimated_cost,
            'request_admission_timestamp':iso_now(),
            'admission_wait_seconds':0.0,
            'http_request_start_timestamp':None,
            'http_response_timestamp':None,
            'http_status_code':None,
            'prediction_id':None,
            'prediction_creation_latency_seconds':0.0,
            'prediction_state_transitions':[],
            'prediction_completion_timestamp':None,
            'total_provider_wait_seconds':0.0,
            'provider_reported_predict_time_seconds':None,
            'poll_attempts':0,
            'poll_interval_delays':[],
            'http_429_count':0,
            'retry_delay_seconds':0.0,
            'output_download_duration_seconds':0.0,
            'status':'started',
        }
        with self._budget_lock:
            self.prediction_records.append(telemetry)
        async with httpx.AsyncClient(timeout=25,follow_redirects=False) as client:
            prediction_entered=False
            try:
                for create_attempt in range(config.PROJECTHER_IMAGE_RETRIES+1):
                    with self._budget_lock:blocked=self._provider_blocked_status
                    if blocked:raise NewsError('Replicate image request failed (HTTP '+str(blocked)+'); no further predictions submitted for this job.')
                    from contextlib import nullcontext
                    admission_started=time.monotonic()
                    try:
                        with self.trace.span('image_provider_admission') if self.trace else nullcontext():
                            await self.admission.wait()
                    finally:
                        adm_dur=time.monotonic()-admission_started
                        telemetry['admission_wait_seconds']=round(telemetry['admission_wait_seconds']+adm_dur,6)
                        self.metric('admissionWaitSeconds',adm_dur)
                    self.metric('createRequests')
                    if admitted is not None:admitted.set()
                    if not prediction_entered:
                        self._enter_prediction()
                        prediction_entered=True
                    http_start=time.monotonic()
                    telemetry['http_request_start_timestamp']=iso_now()
                    self._enter_http()
                    try:
                        response=await client.post('https://api.replicate.com/v1/models/'+model+'/predictions',headers=headers,json={'input':inputs})
                    finally:
                        self._exit_http()
                    create_lat=time.monotonic()-http_start
                    telemetry['http_response_timestamp']=iso_now()
                    telemetry['http_status_code']=response.status_code
                    telemetry['prediction_creation_latency_seconds']=round(create_lat,6)
                    if response.status_code in (401,402,403):
                        with self._budget_lock:self._provider_blocked_status=response.status_code
                    if response.status_code!=429 or create_attempt==config.PROJECTHER_IMAGE_RETRIES:break
                    # Retry only a rejected request; an accepted prediction is
                    # polled by ID, never recreated after a polling failure.
                    delay=15
                    try:
                        supplied=response.headers.get('retry-after') or response.json().get('retry_after')
                        if isinstance(supplied,(str,int,float)):
                            parsed=float(supplied)
                            delay=int(parsed) if parsed.is_integer() else max(1,min(60,parsed))
                            delay=max(1,min(60,delay))
                        else:
                            detail=str(response.json().get('detail',''))
                            m=re.search(r'(?:~|in\s+)(\d+(?:\.\d+)?)\s*(?:s|seconds)',detail)
                            if m:delay=max(1,min(60,int(float(m.group(1)))+1))
                    except (ValueError,TypeError,AttributeError):pass
                    self.admission.throttled(delay)
                    telemetry['http_429_count']+=1
                    telemetry['retry_delay_seconds']+=float(delay)
                    self.metric('rateLimitResponses');self.metric('backoffSeconds',delay)
                    logger.warning('Replicate image request throttled (HTTP 429); waiting %.1fs before retrying the rejected request (%s/%s).',delay,create_attempt+1,config.PROJECTHER_IMAGE_RETRIES)
                    await asyncio.sleep(delay)
                if response.status_code>=500:
                    telemetry['status']='http_5xx'
                    raise NewsError('Image prediction outcome unavailable (HTTP '+str(response.status_code)+'); no automatic new prediction will be submitted.')
                if response.status_code not in (200,201,202):
                    telemetry['status']=f'http_{response.status_code}'
                    raise NewsError('Replicate image request failed (HTTP '+str(response.status_code)+'); check model access and credits.')
                row=response.json();prediction=row.get('id')
                if not isinstance(prediction,str) or not re.fullmatch('[a-zA-Z0-9_-]+',prediction):prediction=None;raise NewsError('Invalid image prediction ID.')
                telemetry['prediction_id']=prediction
                telemetry['model_version']=row.get('version')
                initial_status=row.get('status') or 'starting'
                telemetry['prediction_state_transitions'].append({'status':initial_status,'at':iso_now(),'offset_seconds':0.0})
                self.metric('acceptedPredictions')
                provider_wait_start=http_start
                poll_failures=0
                last_status=initial_status
                for poll_idx in range(100):
                    cur_status=row.get('status')
                    if cur_status and cur_status!=last_status:
                        telemetry['prediction_state_transitions'].append({'status':cur_status,'at':iso_now(),'offset_seconds':round(time.monotonic()-provider_wait_start,4)})
                        last_status=cur_status
                    if cur_status=='succeeded':
                        finished=True
                        provider_wait=time.monotonic()-provider_wait_start
                        telemetry['prediction_completion_timestamp']=iso_now()
                        telemetry['total_provider_wait_seconds']=round(provider_wait,6)
                        metrics_obj=row.get('metrics') if isinstance(row.get('metrics'),dict) else {}
                        if isinstance(metrics_obj.get('predict_time'),(int,float)):
                            telemetry['provider_reported_predict_time_seconds']=round(float(metrics_obj['predict_time']),6)
                        self.metric('apiDurationSeconds',provider_wait)
                        result=row.get('output');url=result[0] if isinstance(result,list) and result else result
                        dl_start=time.monotonic()
                        data,_=await asyncio.get_running_loop().run_in_executor(None,lambda:fetch(url,types=('image/png','image/jpeg','image/webp'),limit=15_000_000))
                        dl_dur=time.monotonic()-dl_start
                        telemetry['output_download_duration_seconds']=round(dl_dur,6)
                        telemetry['status']='succeeded'
                        self.metric('downloadDurationSeconds',dl_dur)
                        path.write_bytes(data)
                        with Image.open(path) as generated_image:
                            generated_image.verify()
                        return 'replicate:'+model
                    if cur_status in ('failed','canceled'):
                        finished=True
                        telemetry['status']=cur_status
                        telemetry['total_provider_wait_seconds']=round(time.monotonic()-provider_wait_start,6)
                        raise NewsError('Replicate image prediction failed or was cancelled.')
                    poll_delay=0.6 if poll_idx<2 else 0.9 if poll_idx<5 else 1.2
                    telemetry['poll_attempts']+=1
                    telemetry['poll_interval_delays'].append(poll_delay)
                    await asyncio.sleep(poll_delay)
                    try:
                        self._enter_http()
                        try:
                            response=await client.get('https://api.replicate.com/v1/predictions/'+prediction,headers={'Authorization':'Bearer '+self.replicate_token})
                        finally:
                            self._exit_http()
                        if response.status_code!=200:
                            if response.status_code==429 or response.status_code>=500:raise httpx.TransportError('Transient polling response')
                            raise NewsError('Image prediction outcome unavailable; no automatic new prediction will be submitted.')
                    except httpx.HTTPError:
                        poll_failures+=1;self.metric('pollRetries')
                        if poll_failures>3:raise NewsError('Image prediction outcome unavailable; no automatic new prediction will be submitted.') from None
                        await asyncio.sleep(min(10,2**poll_failures));continue
                    poll_failures=0
                    row=response.json()
                telemetry['status']='poll_timeout'
                raise NewsError('Image prediction outcome unavailable after polling limit; no automatic new prediction will be submitted.')
            except NewsError:raise
            except (httpx.HTTPError,ValueError,TypeError,KeyError) as exc:
                telemetry['status']='transport_error'
                raise NewsError('Replicate image request unavailable ('+type(exc).__name__+'); check credentials, model access and credits.') from None
            finally:
                if prediction_entered:
                    self._exit_prediction()
                if prediction and not finished:
                    try:await client.post('https://api.replicate.com/v1/predictions/'+prediction+'/cancel',headers={'Authorization':'Bearer '+self.replicate_token})
                    except httpx.HTTPError:pass
