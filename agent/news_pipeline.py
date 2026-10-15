"""Integrated additive News orchestration; no daily publication or global mutation."""
from __future__ import annotations
from agent.branding import output_frames
import math
import logging
import time
import uuid
from pathlib import Path
from PIL import Image
import config
from utils.progress import ProgressTracker
from agent.news_models import Manifest,Theme,NewsError
from agent.news_script import NewsLLM,write_script
from agent.news_research import analyze_input,research
from agent.news_assets import generate_cutouts
from agent.news_audio import synthesize,write_srt
from agent.news_layout import storyboard,font_path,validate_glyphs

logger = logging.getLogger(__name__)

NEWS_STAGES=[('resolve','Resolving input'),('research','Researching / extracting'),('script','Validating script'),('subjects','Planning subjects'),('cutouts','Generating cutouts'),('cutout_qa','Validating cutouts'),('narrate','Narrating / alignment'),('timeline','Finalizing layout / timeline'),('compose','Rendering News')]


def preview_news(text,source_policy='auto',tone='informative',language='english',target_duration=0,llm=None):
    llm=llm or NewsLLM()
    inp=analyze_input(text,source_policy,llm)
    evidence,warnings=research(inp,llm)
    script=write_script(inp,evidence,llm,tone,language,target_duration or config.NEWS_DEFAULT_DURATION)
    return {'status':'ready','content_mode':'news','input':inp.model_dump(),'evidence':evidence.model_dump(),'script':script.model_dump(),'warnings':warnings}


def run_news(text,*,output_dir=None,source_policy='auto',tone='informative',language='english',target_duration=0,video_format='vertical',renderer='remotion',voice=None,tts_provider=None,speed='+0%',quality='high',brand_text='',progress_callback=None,cancel_event=None,music=None,music_path=None,llm=None,image_generator=None,processor=None,tts_engine=None,visual_preset="news_editorial_cutout",subtitle_mode="editorial",asset_mode="auto",local_assets=None):
    from agent.orchestrator import PipelineResult
    if visual_preset == "reference_editorial":
        from agent.editorial.pipeline import run_editorial
        return run_editorial(text,output_dir=output_dir,source_policy=source_policy,tone=tone,language=language,target_duration=target_duration,
            video_format=video_format,renderer=renderer,voice=voice,tts_provider=tts_provider,speed=speed,quality=quality,brand_text=brand_text,
            progress_callback=progress_callback,cancel_event=cancel_event,music=music,music_path=music_path,llm=llm,
            image_generator=image_generator,processor=processor,tts_engine=tts_engine,subtitle_mode=subtitle_mode,asset_mode=asset_mode,local_assets=local_assets)
    if visual_preset not in ("news_editorial_cutout", "default", ""):
        return PipelineResult(errors=["Unknown visual preset: "+visual_preset],content_type="news")
    start=time.monotonic(); generation=uuid.uuid4().hex
    effective_tts=tts_provider or config.TTS_PROVIDER
    use_music=config.NEWS_MUSIC if music is None else music
    output=Path(output_dir) if output_dir else config.OUTPUT_DIR/f'news_{generation}'
    output.mkdir(parents=True,exist_ok=True)
    tracker=ProgressTracker(progress_callback,stages=NEWS_STAGES)
    stage='resolve'; timings={}; phase=time.monotonic()
    def begin(name,message=''):
        nonlocal stage,phase
        if cancel_event is not None and cancel_event.is_set(): raise NewsError('News generation cancelled.','cancelled')
        tracker.complete_stage(stage)
        timings[stage]=round(time.monotonic()-phase,3)
        stage=name; phase=time.monotonic(); tracker.start_stage(name,message)
    try:
        tracker.start_stage(stage)
        if cancel_event is not None and cancel_event.is_set(): raise NewsError('News generation cancelled.','cancelled')
        if renderer not in ('remotion','moviepy'): raise NewsError('Renderer must be remotion or moviepy.')
        llm=llm or NewsLLM()
        inp=analyze_input(text,source_policy,llm,diagnostics_path=output/'input_classification.json')
        begin('research')
        evidence,warnings=research(inp,llm)
        (output/'news_evidence.json').write_text(__import__('json').dumps({'input':inp.model_dump(),'evidence':evidence.model_dump(),'warnings':warnings},ensure_ascii=False,indent=2))
        begin('script')
        script=write_script(inp,evidence,llm,tone,language,target_duration or config.NEWS_DEFAULT_DURATION)
        (output/'news_preview.json').write_text(__import__('json').dumps({'input':inp.model_dump(),'evidence':evidence.model_dump(),'script':script.model_dump(),'warnings':warnings},ensure_ascii=False,indent=2))
        begin('subjects')
        from agent.news_storyboard import plan_storyboard
        fmt=dict(config.VIDEO_FORMATS[video_format]); qp=dict(config.QUALITY_PRESETS.get(quality,config.QUALITY_PRESETS['high']))
        width,height=fmt['width'],fmt['height']; fps=qp['fps']
        plan=plan_storyboard(script,width,height)
        (output/'news_storyboard_plan.json').write_text(plan.model_dump_json(indent=2))
        for sentence in script.sentences: validate_glyphs(sentence.phrase)
        for entity in script.entities: validate_glyphs(entity.name)
        if renderer == 'moviepy' and any('\u0900' <= c <= '\u097f' for c in script.narration):
            from PIL import features
            if not features.check_feature('raqm'):
                raise NewsError('MoviePy Hindi/Devanagari text needs Pillow with libraqm shaping. Install a RAQM-enabled Pillow build or select Remotion; News will not render broken glyphs.')
        begin('cutouts')
        assets=generate_cutouts(script,output,inp.basis,image_generator,processor,cancel_event,llm=llm)
        for asset in assets:
            if asset.image_model:
                name=next(e.name for e in script.entities if e.id==asset.entity_id)
                warnings.append(f'{name}: AI illustration via {asset.image_model}; likeness has not been measured or independently verified.')
        begin('cutout_qa')
        from agent.cutout_processor import mask_statistics
        entities={e.id:e for e in script.entities}
        for asset in assets: mask_statistics(Image.open(asset.path).convert('RGBA'),allow_geometry=asset.provider=='verified_local',allow_group=entities[asset.entity_id].is_group)
        begin('narrate')
        if effective_tts=='edge_tts' and language in config.LANGUAGE_VOICES:
            voice=config.LANGUAGE_VOICES[language]['voice']
        audio=synthesize(script,output,effective_tts,voice,speed,tts_engine,language=language,cancel_event=cancel_event)
        if audio.fallbacks: warnings.append('Narration used '+audio.provider+' after '+ '; '.join(audio.fallbacks))
        if use_music:
            from agent.news_audio import mix_music
            audio=mix_music(audio,output,music_path)
        if audio.method!='native_words': warnings.append(audio.quality)
        if target_duration and abs(audio.duration-target_duration)>max(10,target_duration*.2): warnings.append(f'Actual narration {audio.duration:.1f}s differs from target {target_duration}s; source completeness and natural speech preserved.')
        begin('timeline')
        beats,events=storyboard(script,audio,assets,width,height,fps,plan)
        validate_glyphs(brand_text)
        if len(brand_text)>36: raise NewsError('News branding must be 36 characters or shorter.')
        manifest=Manifest(generation_id=generation,width=width,height=height,fps=fps,duration_frames=math.ceil(audio.duration*fps),
            theme=Theme(font_semibold=str(font_path().resolve()),font_bold=str(font_path(700).resolve()),branding=brand_text),input=inp,evidence=evidence,script=script,audio=audio,assets=assets,beats=beats,events=events,warnings=warnings,stage_timings=timings)
        manifest_path=output/'news_manifest.json'; manifest_path.write_text(manifest.model_dump_json(indent=2))
        srt=output/'subtitles.srt'; write_srt(audio,srt)
        begin('compose')
        video=output/'news.mp4'
        if renderer=='remotion':
            from agent.news_renderer import render_remotion
            render_remotion(manifest,video,cancel_event)
        else:
            from agent.news_compositor import render_moviepy
            render_moviepy(manifest,video,qp['bitrate'],cancel_event)
        from agent.news_compositor import NewsFrames
        thumb=output/'thumbnail.jpg'; Image.fromarray(NewsFrames(manifest).frame(min(manifest.duration_frames-1,round(fps*1.5)))).save(thumb)
        tracker.complete_stage(stage)
        timings[stage]=round(time.monotonic()-phase,3)
        manifest.stage_timings=timings
        images=[{'name':entities[a.entity_id].name,'origin':a.origin,'model':a.image_model,'source_url':a.source_url,'attribution':a.attribution,'identity_verified':a.identity_verified} for a in assets]
        credits=output/'image_credits.txt'
        credits.write_text('\n\n'.join(f"{row['name']} ({row['origin']})\n"+(row['attribution'] or 'AI-generated editorial illustration')+(f"\nModel: {row['model']}" if row['model'] else '') for row in images))
        manifest.outputs={'video':str(video.resolve()),'srt':str(srt.resolve()),'thumbnail':str(thumb.resolve()),'image_credits':str(credits.resolve()),'description':'Identity reference photos and/or AI editorial illustrations; not claimed to depict the narrated event. Image credits: '+str(credits.resolve())+'. Sources: '+'; '.join(s.url or s.title for s in evidence.sources)}
        manifest_path.write_text(manifest.model_dump_json(indent=2))
        (output/'news_failure.json').unlink(missing_ok=True)
        return PipelineResult(success=True,video_path=video,srt_path=srt,thumbnail_path=thumb,duration=output_frames(manifest.duration_frames,fps)/fps,resolution=f'{width}x{height}',video_format=video_format,title=script.summary,key_point_count=len(beats),processing_time=time.monotonic()-start,content_type='news',theme='news_editorial_cutout',caption_style='news_phrases',hook=script.sentences[0].text,news_details={'status':'ready','input':inp.model_dump(),'sources':[{'id':s.id,'title':s.title,'url':s.url} for s in evidence.sources],'images':images,'narration':{'provider':audio.provider,'model':audio.model,'fallbacks':audio.fallbacks},'warnings':warnings,'manifest':str(manifest_path.resolve())})
    except Exception as exc:
        if not isinstance(exc,NewsError):
            logger.exception('News generation %s failed at stage=%s: %s (output: %s)',generation,stage,exc,output)
        tracker.fail_stage(stage,str(exc))
        details=exc.response() if isinstance(exc,NewsError) else {'status':'error','error':str(exc)}
        (output/'news_failure.json').write_text(__import__('json').dumps(details,indent=2))
        return PipelineResult(errors=[str(exc)],content_type='news',processing_time=time.monotonic()-start,news_details=details)
