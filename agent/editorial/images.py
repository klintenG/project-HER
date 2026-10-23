"""Explicit per-job Replicate tiers and bounded calls, without global mutation."""
import config
import logging
import threading
from agent.news_assets import NewsImageGenerator
from agent.news_models import NewsError
logger=logging.getLogger(__name__)


class EditorialImages(NewsImageGenerator):
    def __init__(self):
        super().__init__()
        self.replicate_model=config.EDITORIAL_SUPPORT_IMAGE_MODEL
        self._budget_lock=threading.Lock()
        self.support_calls=0
        self.real_calls=0

    async def subject(self,prompt,path):
        with self._budget_lock:
            if self.support_calls>=config.EDITORIAL_MAX_SUPPORT_CALLS:
                raise NewsError('Supporting-image call limit reached; reuse cached assets or increase EDITORIAL_MAX_SUPPORT_CALLS.')
            self.support_calls+=1
        if not self.replicate_token:raise NewsError('Editorial illustrations require REPLICATE_API_TOKEN.')
        # Explicit low-cost model; no hidden upgrade through global preferences.
        return await self.real_subject(prompt,path,tier='support')

    async def real_subject(self,prompt,path,reference=None,tier='person'):
        if tier=='person':
            with self._budget_lock:
                if self.real_calls>=config.NEWS_MAX_REAL_IMAGE_CALLS:raise NewsError('Real-person image call limit reached.')
                self.real_calls+=1
        return await self._prediction(prompt,path,reference,tier)

    async def _prediction(self,prompt,path,reference,tier):
        import asyncio
        import base64
        import io
        import re
        import httpx
        from PIL import Image
        from agent.news_research import fetch
        if not self.replicate_token:raise NewsError('Editorial images require REPLICATE_API_TOKEN.')
        model=config.EDITORIAL_SUPPORT_IMAGE_MODEL if tier=='support' else config.NEWS_REFERENCE_IMAGE_MODEL if reference else config.NEWS_REAL_IMAGE_MODEL
        allowed={'black-forest-labs/flux-schnell'} if tier=='support' else {'black-forest-labs/flux-kontext-pro','black-forest-labs/flux-1.1-pro','black-forest-labs/flux-dev'}
        if model not in allowed:raise NewsError('Unsupported editorial image model: '+model)
        inputs={'prompt':prompt,'aspect_ratio':'1:1','output_format':'png'}
        if tier=='support':inputs.update(num_outputs=1,num_inference_steps=4)
        if reference:
            with Image.open(reference.path) as image:
                image=image.convert('RGB');image.thumbnail((1024,1024));buffer=io.BytesIO();image.save(buffer,format='JPEG',quality=90)
            inputs['input_image']='data:image/jpeg;base64,'+base64.b64encode(buffer.getvalue()).decode()
        headers={'Authorization':'Bearer '+self.replicate_token};prediction=None;finished=False
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0,connect=15.0),follow_redirects=False) as client:
            try:
                for create_attempt in range(3):
                    try:
                        response=await client.post('https://api.replicate.com/v1/models/'+model+'/predictions',headers=headers,json={'input':inputs})
                        if response.status_code!=429 or create_attempt==2:break
                        delay=30
                        try:
                            supplied=response.headers.get('retry-after') or response.json().get('retry_after')
                            if isinstance(supplied,(str,int,float)):delay=max(1,min(60,float(supplied)))
                        except (ValueError,TypeError,AttributeError):pass
                        logger.warning('Replicate image request throttled (HTTP 429); waiting %.1fs before retrying the rejected request (%s/2).',delay,create_attempt+1)
                        await asyncio.sleep(delay)
                    except httpx.TimeoutException:
                        if create_attempt==2:raise
                        logger.warning('Replicate create prediction timed out; retrying creation attempt (%s/2).',create_attempt+1)
                        await asyncio.sleep(2)
                if response.status_code not in (200,201):raise NewsError('Replicate image request failed (HTTP '+str(response.status_code)+'); check model access and credits.')
                row=response.json();prediction=row.get('id')
                if not isinstance(prediction,str) or not re.fullmatch('[a-zA-Z0-9_-]+',prediction):prediction=None;raise NewsError('Invalid image prediction ID.')
                for _ in range(120):
                    if row.get('status')=='succeeded':
                        finished=True;result=row.get('output');url=result[0] if isinstance(result,list) and result else result
                        data,_=await asyncio.get_running_loop().run_in_executor(None,lambda:fetch(url,types=('image/png','image/jpeg','image/webp'),limit=15_000_000))
                        path.write_bytes(data);return 'replicate:'+model
                    if row.get('status') in ('failed','canceled'):finished=True;raise NewsError('Replicate image prediction failed or was cancelled.')
                    await asyncio.sleep(2.0)
                    try:
                        poll_resp=await client.get('https://api.replicate.com/v1/predictions/'+prediction,headers=headers)
                        if poll_resp.status_code==200:
                            row=poll_resp.json()
                        elif poll_resp.status_code in (429,502,503,504):
                            logger.warning('Replicate image poll transient status HTTP %d; continuing poll.',poll_resp.status_code)
                            continue
                        else:
                            raise NewsError('Replicate image polling failed (HTTP '+str(poll_resp.status_code)+').')
                    except httpx.TimeoutException:
                        logger.warning('Replicate image poll read timed out; continuing poll.')
                        continue
                raise NewsError('Replicate image polling limit reached.')
            except NewsError:raise
            except (httpx.HTTPError,ValueError,TypeError,KeyError) as exc:raise NewsError('Replicate image request unavailable ('+type(exc).__name__+'); check credentials, model access and credits.') from None
            finally:
                if prediction and not finished:
                    try:await client.post('https://api.replicate.com/v1/predictions/'+prediction+'/cancel',headers=headers)
                    except httpx.HTTPError:pass
