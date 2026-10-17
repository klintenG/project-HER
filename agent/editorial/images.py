"""Explicit per-job Replicate tiers and bounded calls, without global mutation."""
import config
import logging
import threading
from agent.news_assets import NewsImageGenerator
from agent.news_models import NewsError
logger=logging.getLogger(__name__)


class EditorialImages(NewsImageGenerator):
    def __init__(self,trace=None):
        super().__init__()
        self.replicate_model=config.EDITORIAL_SUPPORT_IMAGE_MODEL
        self.support_calls=0
        self.real_calls=0
        self._budget_lock=threading.Lock()
        self._provider_blocked_status=None
        from utils.provider_admission import ProviderAdmission
        self.admission=ProviderAdmission(self.replicate_token,max(config.EDITORIAL_IMAGE_MIN_INTERVAL,config.NEWS_REPLICATE_MIN_INTERVAL))
        self.trace=trace
        self.metrics={'createRequests':0,'acceptedPredictions':0,'rateLimitResponses':0,'backoffSeconds':0,'pollRetries':0,'admissionWaitSeconds':0}

    def metric(self,name,value=1):
        with self._budget_lock:self.metrics[name]+=value

    async def subject(self,prompt,path):
        with self._budget_lock:
            if self.support_calls>=config.EDITORIAL_MAX_SUPPORT_CALLS:
                raise NewsError('Supporting-image call limit reached; reuse cached assets or increase EDITORIAL_MAX_SUPPORT_CALLS.')
            self.support_calls+=1
        if not self.replicate_token:raise NewsError('Editorial illustrations require REPLICATE_API_TOKEN.')
        # Explicit low-cost model; no hidden upgrade through global preferences.
        return await self.real_subject(prompt,path,tier='support')

    async def action_subject(self,prompt,path,reference=None):
        return await self.real_subject(prompt,path,reference,tier='action')

    async def real_subject(self,prompt,path,reference=None,tier='person'):
        if tier in ('person','action'):
            with self._budget_lock:
                if self.real_calls>=config.NEWS_MAX_REAL_IMAGE_CALLS:raise NewsError('Real-person image call limit reached.')
                self.real_calls+=1
        return await self._prediction(prompt,path,reference,tier)

    async def _prediction(self,prompt,path,reference,tier):
        import asyncio
        try:
            return await asyncio.wait_for(self._prediction_request(prompt,path,reference,tier),timeout=config.EDITORIAL_IMAGE_TIMEOUT)
        except asyncio.TimeoutError:
            raise NewsError('Image prediction outcome unavailable after its deadline; no automatic new prediction will be submitted.') from None

    async def _prediction_request(self,prompt,path,reference,tier):
        import asyncio
        import base64
        import io
        import re
        import httpx
        from PIL import Image
        from agent.news_research import fetch
        if not self.replicate_token:raise NewsError('Editorial images require REPLICATE_API_TOKEN.')
        model=config.EDITORIAL_ACTION_IMAGE_MODEL if tier=='action' else config.EDITORIAL_SUPPORT_IMAGE_MODEL if tier=='support' else config.NEWS_REFERENCE_IMAGE_MODEL if reference else config.NEWS_REAL_IMAGE_MODEL
        allowed={'black-forest-labs/flux-schnell','black-forest-labs/flux-1.1-pro','black-forest-labs/flux-dev'} if tier=='support' else {'black-forest-labs/flux-kontext-pro','black-forest-labs/flux-1.1-pro','black-forest-labs/flux-dev'}
        if tier=='action':allowed=allowed|{'google/nano-banana-pro'}
        if model not in allowed:raise NewsError('Unsupported editorial image model: '+model)
        inputs={'prompt':prompt,'aspect_ratio':'1:1','output_format':'png'}
        if model=='black-forest-labs/flux-schnell':inputs.update(num_outputs=1,num_inference_steps=4)
        if model=='google/nano-banana-pro':
            inputs.update(resolution='2K',allow_fallback_model=False)
        if reference:
            paths=getattr(reference,'paths',None) if model=='google/nano-banana-pro' else None
            encoded=[]
            for source_path in paths or [reference.path]:
                with Image.open(source_path) as image:
                    image=image.convert('RGB');image.thumbnail((1024,1024));buffer=io.BytesIO();image.save(buffer,format='PNG' if model=='google/nano-banana-pro' else 'JPEG',quality=90)
                encoded.append(('data:image/png;base64,' if model=='google/nano-banana-pro' else 'data:image/jpeg;base64,')+base64.b64encode(buffer.getvalue()).decode())
            inputs['image_input' if model=='google/nano-banana-pro' else 'input_image']=encoded if model=='google/nano-banana-pro' else encoded[0]
        headers={'Authorization':'Bearer '+self.replicate_token};prediction=None;finished=False
        async with httpx.AsyncClient(timeout=25,follow_redirects=False) as client:
            try:
                for create_attempt in range(3):
                    with self._budget_lock:blocked=self._provider_blocked_status
                    if blocked:raise NewsError('Replicate image request failed (HTTP '+str(blocked)+'); no further predictions submitted for this job.')
                    from contextlib import nullcontext
                    import time
                    admission_started=time.monotonic()
                    try:
                        with self.trace.span('image_provider_admission') if self.trace else nullcontext():
                            await self.admission.wait()
                    finally:self.metric('admissionWaitSeconds',time.monotonic()-admission_started)
                    self.metric('createRequests')
                    response=await client.post('https://api.replicate.com/v1/models/'+model+'/predictions',headers=headers,json={'input':inputs})
                    if response.status_code in (401,402,403):
                        with self._budget_lock:self._provider_blocked_status=response.status_code
                    if response.status_code!=429 or create_attempt==2:break
                    # Retry only a rejected request; an accepted prediction is
                    # polled by ID, never recreated after a polling failure.
                    delay=30
                    try:
                        supplied=response.headers.get('retry-after') or response.json().get('retry_after')
                        if isinstance(supplied,(str,int,float)):delay=max(1,min(60,float(supplied)))
                    except (ValueError,TypeError,AttributeError):pass
                    self.admission.throttled(delay)
                    self.metric('rateLimitResponses');self.metric('backoffSeconds',delay)
                    logger.warning('Replicate image request throttled (HTTP 429); waiting %.1fs before retrying the rejected request (%s/2).',delay,create_attempt+1)
                    await asyncio.sleep(delay)
                if response.status_code>=500:raise NewsError('Image prediction outcome unavailable (HTTP '+str(response.status_code)+'); no automatic new prediction will be submitted.')
                if response.status_code not in (200,201):raise NewsError('Replicate image request failed (HTTP '+str(response.status_code)+'); check model access and credits.')
                row=response.json();prediction=row.get('id')
                if not isinstance(prediction,str) or not re.fullmatch('[a-zA-Z0-9_-]+',prediction):prediction=None;raise NewsError('Invalid image prediction ID.')
                self.metric('acceptedPredictions')
                poll_failures=0
                for _ in range(80):
                    if row.get('status')=='succeeded':
                        finished=True;result=row.get('output');url=result[0] if isinstance(result,list) and result else result
                        data,_=await asyncio.get_running_loop().run_in_executor(None,lambda:fetch(url,types=('image/png','image/jpeg','image/webp'),limit=15_000_000))
                        path.write_bytes(data);return 'replicate:'+model
                    if row.get('status') in ('failed','canceled'):finished=True;raise NewsError('Replicate image prediction failed or was cancelled.')
                    await asyncio.sleep(1.5)
                    try:
                        response=await client.get('https://api.replicate.com/v1/predictions/'+prediction,headers=headers)
                        if response.status_code!=200:
                            if response.status_code==429 or response.status_code>=500:raise httpx.TransportError('Transient polling response')
                            raise NewsError('Image prediction outcome unavailable; no automatic new prediction will be submitted.')
                    except httpx.HTTPError:
                        poll_failures+=1;self.metric('pollRetries')
                        if poll_failures>3:raise NewsError('Image prediction outcome unavailable; no automatic new prediction will be submitted.') from None
                        await asyncio.sleep(min(10,2**poll_failures));continue
                    poll_failures=0
                    row=response.json()
                raise NewsError('Image prediction outcome unavailable after polling limit; no automatic new prediction will be submitted.')
            except NewsError:raise
            except (httpx.HTTPError,ValueError,TypeError,KeyError) as exc:raise NewsError('Replicate image request unavailable ('+type(exc).__name__+'); check credentials, model access and credits.') from None
            finally:
                if prediction and not finished:
                    try:await client.post('https://api.replicate.com/v1/predictions/'+prediction+'/cancel',headers=headers)
                    except httpx.HTTPError:pass
