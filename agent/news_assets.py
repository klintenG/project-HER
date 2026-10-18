"""Separate editorial subjects through the application's configured image providers."""
from __future__ import annotations
import asyncio
import base64
import hashlib
import io
import json
import logging
import re
import shutil
import time
import uuid
from pathlib import Path
from urllib.parse import quote
import httpx
from PIL import Image
from agent.ai_visuals import AIImageGenerator
from agent.cutout_processor import CutoutProcessor
from agent.news_models import Asset, NewsError
import config

logger = logging.getLogger(__name__)


def subject_prompt(entity, attempt=0):
    """Describe a cutout, overriding any scene language in the script's description."""
    prompt=('Recognizable '+entity.name+'. ' if entity.identity in ('real','fictional') else 'One isolated ')+entity.description+'. '
    if entity.kind=='person':
        prompt+='Fully colored editorial illustration, natural skin tones, visible faces and recognizable anatomy, no black silhouettes. '
    if entity.kind=='animal':
        prompt+='One representative animal of the described species, natural colors, realistic recognizable anatomy, full head/neck/body/legs/feet visible. Use a single animal even when the species name is plural; no flock, no silhouette icon or abstract shape. '
    if entity.is_group and entity.identity!='real':
        prompt+='One compact group of three representative people, shoulders together, same scale and baseline, all heads and feet visible. '
    if entity.identity=='real' and entity.kind=='person':
        prompt+='Preserve the specific identity, recognizable facial features, age, proportions, and distinctive appearance. Do not replace with an anonymous lookalike or invent an event or action. '
    if 'football' in (entity.name+' '+entity.description).lower():
        prompt+='Association football (soccer): ordinary soccer shirts and shorts, no helmets, no shoulder pads, no American football uniforms. '
    prompt+=config.NEWS_STYLE_SUFFIX
    prompt+=' Background instruction takes precedence over setting references: show only the subject against one solid neutral color, no field, grass, pitch, floor, ground plane or cast shadows. No invented badges, logos or lettering. '
    if attempt==1:
        prompt+='Regenerate with a solid mid-gray studio backdrop. Use a simpler composition, clear silhouette edges and wide empty margins. '
    elif attempt>=2:
        prompt+='Regenerate as a simplified natural-color editorial drawing on a solid contrasting background. No photographic scene details. '
    return prompt


def verified_assets():
    if not config.NEWS_VERIFIED_ASSETS_JSON: return {}
    registry=json.loads(Path(config.NEWS_VERIFIED_ASSETS_JSON).read_text())
    if not isinstance(registry,dict): raise NewsError('News verified asset registry must be an object.')
    for key,row in registry.items():
        if not all(row.get(field) for field in ('path','source_url','license','name')):
            raise NewsError('Verified assets require path, source_url, license and name.')
        path=(config.BASE_DIR/row['path']).resolve()
        try: path.relative_to(config.ASSETS_DIR.resolve())
        except ValueError: raise NewsError('Verified News assets must be inside assets/.')
        if path.suffix.lower()!='.png' or not path.is_file(): raise NewsError('Verified News assets must be local RGBA PNGs.')
        row['path']=str(path)
    return registry


class NewsImageGenerator(AIImageGenerator):
    def __init__(self):
        super().__init__(portrait_mode=False)
        self.visual_style='news_editorial_cutout'
        self.style_suffix=config.NEWS_STYLE_SUFFIX
        self.width=self.height=1024

    async def real_subject(self,prompt,path,reference=None):
        """One bounded premium prediction; never silently fall back to a generic model."""
        if not self.replicate_token:
            raise NewsError('Real-subject AI images need REPLICATE_API_TOKEN; no generic substitute was used.')
        model=config.NEWS_REFERENCE_IMAGE_MODEL if reference else config.NEWS_REAL_IMAGE_MODEL
        if model not in {'black-forest-labs/flux-1.1-pro','black-forest-labs/flux-dev','black-forest-labs/flux-kontext-pro'}:
            raise NewsError('Select flux-1.1-pro or flux-dev for NEWS_REAL_IMAGE_MODEL; expensive models are not enabled automatically.')
        inputs={'prompt':prompt,'aspect_ratio':'1:1','output_format':'png'}
        if reference:
            with Image.open(reference.path) as image:
                image.thumbnail((1024,1024)); buffer=io.BytesIO(); image.convert('RGB').save(buffer,format='JPEG',quality=90)
            inputs['input_image']='data:image/jpeg;base64,'+base64.b64encode(buffer.getvalue()).decode()
            inputs['prompt_upsampling']=False
        elif model.endswith('/flux-dev'):
            inputs.update(num_outputs=1,num_inference_steps=28,megapixels='1')
        else:
            inputs['prompt_upsampling']=False
        headers={'Authorization':'Bearer '+self.replicate_token}
        prediction=None;finished=False
        async with httpx.AsyncClient(timeout=25,follow_redirects=False) as client:
            try:
                response=await client.post(f'https://api.replicate.com/v1/models/{model}/predictions',headers=headers,json={'input':inputs})
                if response.status_code not in (200,201):
                    raise NewsError(f'Replicate real-subject request failed (HTTP {response.status_code}); check model access/credits.')
                row=response.json(); prediction=row.get('id')
                if not isinstance(prediction,str) or not re.fullmatch('[a-zA-Z0-9_-]+',prediction):
                    prediction=None
                    raise NewsError('Replicate returned an invalid prediction ID.')
                for _ in range(60):
                    if row.get('status')=='succeeded':
                        finished=True
                        outputs=row.get('output'); url=outputs[0] if isinstance(outputs,list) and outputs else outputs
                        # Download through the same public-DNS-pinned bounded fetcher as references.
                        from agent.news_research import fetch
                        data,_=await asyncio.get_running_loop().run_in_executor(None,lambda:fetch(url,types=('image/png','image/jpeg','image/webp'),limit=15_000_000))
                        path.write_bytes(data)
                        return 'replicate:'+model
                    if row.get('status') in ('failed','canceled'):
                        finished=True
                        raise NewsError('Replicate real-subject prediction failed or was cancelled; no generic substitute was used.')
                    await asyncio.sleep(1.5)
                    response=await client.get(f'https://api.replicate.com/v1/predictions/{prediction}',headers=headers)
                    if response.status_code!=200:
                        raise NewsError(f'Replicate prediction status failed (HTTP {response.status_code}).')
                    row=response.json()
                raise NewsError('Replicate real-subject prediction exceeded its polling limit.')
            except (httpx.HTTPError,ValueError,TypeError,KeyError):
                raise NewsError('Replicate real-subject request was unavailable or invalid; check model access/credits.') from None
            finally:
                if prediction and not finished:
                    try: await client.post(f'https://api.replicate.com/v1/predictions/{prediction}/cancel',headers=headers)
                    except httpx.HTTPError: pass

    async def subject(self,prompt,path):
        async with httpx.AsyncClient(timeout=self.timeout,follow_redirects=False) as client:
            for provider in self._build_fallback_chain():
                if provider=='replicate' and not self.replicate_token: continue
                if provider=='huggingface' and not self.hf_token: continue
                if provider=='pollinations' and not config.POLLINATIONS_API_KEY: continue
                try:
                    if provider=='replicate':
                        data=await self._call_replicate(client,prompt)
                    elif provider=='huggingface':
                        from huggingface_hub import InferenceClient
                        def generate():
                            inference=InferenceClient(provider=config.NEWS_HF_PROVIDER,api_key=self.hf_token,timeout=60)
                            image=inference.text_to_image(prompt,model=self.hf_model,width=1024,height=1024)
                            out=io.BytesIO(); image.save(out,format='PNG'); return out.getvalue()
                        data=await asyncio.get_running_loop().run_in_executor(None,generate)
                    else:
                        response=await client.get('https://gen.pollinations.ai/image/'+quote(prompt,safe=''),
                            params={'model':config.NEWS_POLLINATIONS_MODEL,'width':1024,'height':1024,'seed':int(hashlib.sha256(prompt.encode()).hexdigest()[:8],16)%100000},
                            headers={'Authorization':'Bearer '+config.POLLINATIONS_API_KEY},timeout=90)
                        data=response.content if response.status_code==200 and response.headers.get('content-type','').startswith('image/') else None
                    if data and 1000<len(data)<30_000_000:
                        path.write_bytes(data); return provider
                except Exception:
                    # Do not leak credential-bearing provider responses into progress/logs.
                    continue
        raise NewsError('News image generation failed. Configure a working REPLICATE_API_TOKEN, HF_API_TOKEN/provider/model, or POLLINATIONS_API_KEY. No rectangular fallback was used.')


def _generate(awaitable,cancel_event):
    async def bounded():
        task=asyncio.create_task(awaitable)
        try:
            while not task.done():
                await asyncio.wait({task},timeout=.2)
                if cancel_event is not None and cancel_event.is_set(): raise NewsError('News generation cancelled.','cancelled')
            return await task
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task,return_exceptions=True)
    return asyncio.run(bounded())


def _real_cutout(entity,output,processor,generator,source_basis,reference_provider,llm,cancel_event,budget):
    file_id=hashlib.sha256(entity.id.encode()).hexdigest()[:16]
    def check_cancel():
        if cancel_event is not None and cancel_event.is_set(): raise NewsError('News generation cancelled.','cancelled')
    references=[]
    try: references=reference_provider.find(entity,llm)
    except Exception as exc:
        logger.warning('Reference lookup unavailable for %s: %s',entity.name,type(exc).__name__)
    check_cancel()
    for i,reference in enumerate(references[:2]):
        raw=output/f'{file_id}-reference-{i+1}.image';cutout=output/f'{file_id}-reference-{i+1}.png'
        shutil.copy2(reference.path,raw)
        try:
            stats,method=processor.process(raw,cutout,allow_group=entity.is_group,allow_portrait_crop=entity.is_portrait,allow_bottom_crop=True)
            logger.info('News subject %s: actual reference photo (%s)',entity.name,reference.entity_url)
            return Asset(id='asset-'+entity.id,entity_id=entity.id,path=str(cutout.resolve()),raw_path=str(raw.resolve()),
                prompt='Actual identity-linked reference photograph; background removed, no AI redraw.',provider='wikimedia_commons',
                source_url=reference.source_url,reference_url=reference.source_url,reference_entity=reference.entity_url,
                license=reference.license,attribution=reference.attribution+'; background removed for video',origin='photo',illustrative=False,identity_verified=True,
                source_basis='Identity reference photo; not claimed to depict the narrated event.',segmentation=method,mask=stats)
        except NewsError as exc:
            logger.warning('News reference cutout %s failed QA: %s',entity.name,exc)
    reference=references[0] if references else None
    model=config.NEWS_REFERENCE_IMAGE_MODEL if reference else config.NEWS_REAL_IMAGE_MODEL
    for attempt in range(config.NEWS_REAL_IMAGE_ATTEMPTS):
        check_cancel()
        prompt=subject_prompt(entity,attempt)
        if reference:
            prompt='Edit the supplied reference only: preserve the same identity, face, hairstyle, clothing, colors, pose, and recognizable object geometry. Remove surrounding scenery and place the existing subject on a contrasting flat neutral background with clear margins. Do not invent missing details, add people or change facial identity. '+prompt
        key=hashlib.sha256(('identity-v1|'+entity.name+'|'+prompt+'|'+model+'|'+processor.version+'|'+(hashlib.sha256(Path(reference.path).read_bytes()).hexdigest() if reference else 'no-reference')).encode()).hexdigest()
        cache=Path(config.NEWS_IDENTITY_IMAGE_CACHE)/key
        raw=output/f'{file_id}-ai-{attempt+1}-raw.png';cutout=output/f'{file_id}-ai-{attempt+1}.png'
        cached=(cache/'raw.image').is_file()
        if not cached:
            if budget[0]>=config.NEWS_MAX_REAL_IMAGE_CALLS:
                raise NewsError('Real-subject image call limit reached. Reuse cached images or increase NEWS_MAX_REAL_IMAGE_CALLS explicitly.')
            generator=generator or NewsImageGenerator()
            if not hasattr(generator,'real_subject'):
                raise NewsError('This image adapter does not support identity-aware real subjects.')
            budget[0]+=1
        try:
            if cached:
                shutil.copy2(cache/'raw.image',raw)
                provider='replicate:'+model
            else:
                logger.info('News subject %s: %s | paid call %s/%s',entity.name,model,budget[0],config.NEWS_MAX_REAL_IMAGE_CALLS)
                provider=_generate(generator.real_subject(prompt,raw,reference),cancel_event)
            stats,method=processor.process(raw,cutout,allow_group=entity.is_group,allow_portrait_crop=entity.is_portrait,allow_bottom_crop=True)
            cache.mkdir(parents=True,exist_ok=True)
            temporary=cache/(uuid.uuid4().hex+'.tmp');shutil.copy2(raw,temporary);temporary.replace(cache/'raw.image')
            return Asset(id='asset-'+entity.id,entity_id=entity.id,path=str(cutout.resolve()),raw_path=str(raw.resolve()),prompt=prompt,
                provider=provider,image_model=model,origin='reference_edit' if reference else 'generated',identity_verified=False,
                source_url=reference.source_url if reference else None,reference_url=reference.source_url if reference else None,
                reference_entity=reference.entity_url if reference else None,license=reference.license if reference else None,
                attribution=reference.attribution+'; AI adaptation for video' if reference else None,source_basis=source_basis+'; AI likeness, not a photograph or verified identity match',
                segmentation=method,mask=stats,fallback='Reference photo needed a cutout edit' if reference else 'No suitable Commons reference; named-subject AI illustration')
        except NewsError as exc:
            if exc.status=='cancelled': raise
            logger.warning('News real subject %s attempt %s/%s failed: %s',entity.name,attempt+1,config.NEWS_REAL_IMAGE_ATTEMPTS,exc)
    raise NewsError('Could not create a usable identity-aware image for '+entity.name+'. Supply an audited reference asset or retry; no anonymous substitute was used.')


def generate_cutouts(script,output,source_basis,generator=None,processor=None,cancel_event=None,reference_provider=None,llm=None):
    processor=processor or CutoutProcessor()
    output=Path(output)/'cutouts'; output.mkdir(parents=True,exist_ok=True)
    assets=[];recovery=[]
    def degraded_label(entity,reason,requests,started):
        from PIL import Image, ImageDraw, ImageFont
        canvas=Image.new('RGBA',(800,800),(0,0,0,0));draw=ImageDraw.Draw(canvas)
        font=ImageFont.truetype(str(config.BASE_DIR/'assets/fonts/news/Poppins-Bold.ttf'),64)
        words=entity.name.split();lines=[];line=''
        for word in words:
            trial=(line+' '+word).strip()
            if line and draw.textlength(trial,font=font)>680:lines.append(line);line=word
            else:line=trial
        if line:lines.append(line)
        for index,text in enumerate(lines[:5]):
            draw.text(((800-draw.textlength(text,font=font))/2,310+index*78),text,font=font,fill='#202632')
        path=output/(hashlib.sha256(entity.id.encode()).hexdigest()[:20]+'-degraded-label.png');canvas.save(path)
        sentence_ids=[s.id for s in script.sentences if entity.id in s.entity_ids]
        recovery.append({'entityId':entity.id,'sentenceIds':sentence_ids,'originalRequest':requests[0] if requests else None,
            'requests':requests,'failure':reason,'retryCount':max(0,len(requests)-1),'fallbackMethod':'typography',
            'additionalDelaySeconds':round(time.monotonic()-started,3),'fullyCompliant':False})
        return Asset(id=f'asset-{entity.id}',entity_id=entity.id,path=str(path.resolve()),raw_path=str(path.resolve()),
            prompt=requests[0] if requests else entity.description,provider='projecther:typography',origin='generated',
            source_basis=source_basis,segmentation='typography',mask={},qa='degraded',
            fallback='Visual generation failed; contextual typography used. '+reason)
    registry=verified_assets()
    from agent.news_references import ReferencePhotos
    reference_provider=reference_provider or ReferencePhotos()
    budget=[0]
    for i,e in enumerate(script.entities):
        asset_started=time.monotonic()
        if cancel_event is not None and cancel_event.is_set(): raise NewsError("News generation cancelled.","cancelled")
        prompt=subject_prompt(e)
        key=hashlib.sha256(('news|'+e.id+'|'+prompt+'|'+getattr(generator,'provider',config.AI_IMAGE_PROVIDER)+'|'+processor.version).encode()).hexdigest()[:20]
        raw=output/f'{key}-raw.png'; cutout=output/f'{key}.png'
        error=None
        if e.exact_asset:
            row=registry.get(e.exact_asset)
            if not row: raise NewsError('Unknown verified geometry key; configure NEWS_VERIFIED_ASSETS_JSON or use accurate text.')
            shutil.copy2(row['path'],raw)
            stats,method=processor.process(raw,cutout,allow_geometry=True)
            assets.append(Asset(id=f'asset-{e.id}',entity_id=e.id,path=str(cutout.resolve()),raw_path=str(raw.resolve()),prompt='Audited local geometry: '+row['name'],provider='verified_local',origin='verified_local',source_url=row['source_url'],license=row['license'],source_basis='verified asset registry',segmentation=method,mask=stats))
            continue
        if e.identity=='real':
            try:assets.append(_real_cutout(e,output,processor,generator,source_basis,reference_provider,llm,cancel_event,budget))
            except NewsError as exc:
                if exc.status=='cancelled':raise
                assets.append(degraded_label(e,str(exc),[prompt],asset_started))
            continue
        generator=generator or NewsImageGenerator()
        requests=[]
        for attempt in range(config.NEWS_ASSET_RETRIES):
            if cancel_event is not None and cancel_event.is_set(): raise NewsError("News generation cancelled.","cancelled")
            try:
                revised=subject_prompt(e,attempt)
                requests.append(revised)
                raw=output/f'{key}-attempt-{attempt+1}-raw.png'
                provider=_generate(generator.subject(revised,raw),cancel_event)
                stats,method=processor.process(raw,cutout,allow_group=e.is_group,allow_portrait_crop=e.is_portrait,allow_bottom_crop=True)
                assets.append(Asset(id=f'asset-{e.id}',entity_id=e.id,path=str(cutout.resolve()),raw_path=str(raw.resolve()),prompt=revised,provider=provider,
                    source_basis=source_basis,segmentation=method,mask=stats,fallback='regenerated after mask QA failure' if attempt else None))
                error=None; break
            except Exception as exc:
                if isinstance(exc, NewsError) and exc.status == 'cancelled':
                    raise
                error=exc
                logger.warning('News cutout %s (%s), attempt %s/%s failed: %s',
                    e.id,e.name,attempt+1,config.NEWS_ASSET_RETRIES,exc)
        if error:assets.append(degraded_label(e,str(error),requests,asset_started))
    if recovery:(output.parent/'news_visual_recovery.json').write_text(__import__('json').dumps(recovery,indent=2))
    return assets
