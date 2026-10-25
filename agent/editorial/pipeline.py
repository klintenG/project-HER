"""Reference editorial preset through the existing News script/TTS routes."""
from __future__ import annotations
from agent.branding import output_frames
import json
import time
import uuid
from pathlib import Path
import config
from agent.news_models import NewsError
from utils.progress import ProgressTracker
from .audio import prepare_existing,normalize,subtitles,run
from .assets import acquire
from .planner import build,semantic_plan
from .render import render

STAGES=[('resolve','Resolving input'),('research','Extracting source evidence'),('script','Approving script'),('narrate','Narration and word alignment'),('cutouts','Preparing entity assets'),('timeline','Planning editorial beats'),('compose','Rendering and measuring mix')]

def check_configuration(renderer,video_format,subtitle_mode,asset_mode):
    if renderer!='remotion':raise NewsError('reference_editorial requires Remotion; MoviePy cannot render its persistent layers and events.')
    if video_format!='vertical':raise NewsError('reference_editorial currently supports 1080 × 1920 vertical only. Choose another preset for square or horizontal.')
    if subtitle_mode not in ('editorial','complete'):raise NewsError('Editorial text mode must be editorial or complete.')
    if asset_mode not in ('auto','stock','ai','local'):raise NewsError('Editorial assets must be auto, stock, ai, or local.')


def run_editorial(text,*,output_dir=None,source_policy='auto',tone='informative',language='english',target_duration=0,video_format='vertical',renderer='remotion',voice=None,tts_provider=None,speed='+0%',quality='high',brand_text='',progress_callback=None,cancel_event=None,music=None,music_path=None,llm=None,image_generator=None,processor=None,tts_engine=None,subtitle_mode='editorial',asset_mode='auto',local_assets=None,autopilot_hook='',autopilot_scene_validator=None,autopilot_story_id=''):
    from agent.orchestrator import PipelineResult
    from agent.news_script import NewsLLM,write_script
    from agent.news_research import analyze_input,research
    from agent.news_audio import synthesize,mix_music
    from agent.news_tts import LANGUAGES,cancelled
    started=time.monotonic();generation='editorial_'+uuid.uuid4().hex
    out=Path(output_dir) if output_dir else config.OUTPUT_DIR/generation;out.mkdir(parents=True,exist_ok=True)
    tracker=ProgressTracker(progress_callback,stages=STAGES);stage='resolve';timings={};phase=time.monotonic()
    def begin(name,message=''):
        nonlocal stage,phase
        cancelled(cancel_event);tracker.complete_stage(stage);timings[stage]=round(time.monotonic()-phase,3)
        stage=name;phase=time.monotonic();tracker.start_stage(stage,message)
    try:
        tracker.start_stage(stage);check_configuration(renderer,video_format,subtitle_mode,asset_mode)
        llm=llm or NewsLLM();inp=analyze_input(text,source_policy,llm,diagnostics_path=out/'input_classification.json')
        begin('research');evidence,warnings=research(inp,llm)
        begin('script');script=write_script(inp,evidence,llm,tone,language,target_duration or config.NEWS_DEFAULT_DURATION,editorial=True)
        from agent.news_layout import validate_glyphs
        for sentence in script.sentences:validate_glyphs(sentence.text)
        for entity in script.entities:validate_glyphs(entity.name)
        (out/'news_preview.json').write_text(json.dumps({'input':inp.model_dump(),'evidence':evidence.model_dump(),'script':script.model_dump(),'warnings':warnings},ensure_ascii=False,indent=2))
        from .visuals import plan_visuals
        visual_diagnostics={}
        # Local registries intentionally specify every supplied subject; they
        # retain the script plan instead of adding unregistered illustrations.
        script,cues=plan_visuals(script,evidence,None if asset_mode=='local' else llm,visual_diagnostics)
        (out/'visual_plan.json').write_text(json.dumps({'script':script.model_dump(),'sections':cues,'diagnostics':visual_diagnostics},ensure_ascii=False,indent=2))
        if autopilot_scene_validator:
            autopilot_scene_validator({'script':script.model_dump(),'visual_cues':cues})
        begin('narrate','Generating speech, aligning exact script and removing redundant clip padding')
        narration_settings={}
        audio=synthesize(script,out,tts_provider or config.TTS_PROVIDER,voice,speed,tts_engine,pause=0,language=language,cancel_event=cancel_event,diagnostic_sink=narration_settings)
        from concurrent.futures import ThreadPoolExecutor
        import threading
        prefetch_stop=threading.Event()
        cpu_lock=threading.Lock()
        class _PrefetchCancel:
            def is_set(self):return prefetch_stop.is_set() or (cancel_event is not None and cancel_event.is_set())
        acquisition_diagnostics={}
        cutout_pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='editorial-assets-coord')
        # Acquire cpu_lock before submitting acquire() so network image generation
        # overlaps with Whisper alignment while CPU-heavy rembg waits until Whisper finishes.
        cpu_lock.acquire()
        cutout_future=cutout_pool.submit(acquire,script,out/'assets',local_registry=local_assets,asset_mode=asset_mode,llm=llm,cancel_event=_PrefetchCancel(),image_generator=image_generator,processor=processor,evidence=evidence,diagnostics=acquisition_diagnostics,process_lock=cpu_lock)
        try:
            try:
                code=LANGUAGES.get(language.lower(),language.lower()).split('-')[0]
                raw,words,sections,diagnostics=prepare_existing(script,audio,out/'audio',code)
            finally:
                cpu_lock.release()
            diagnostics.update(visual_diagnostics)
            from .director import VisualSettings,direct,save_summary
            visual_settings=VisualSettings.configured()
            direction=direct(script,words,cues,None if asset_mode=='local' else llm,visual_settings,diagnostics) if visual_settings.narrationDrivenVisualsEnabled else None
            if direction is not None:
                (out/'visual_direction.json').write_text(direction.model_dump_json(indent=2))
            cancelled(cancel_event)
            from agent.news_audio import probe_duration
            diagnostics.update(provider=audio.provider,providerModel=audio.model,providerFallbacks=audio.fallbacks,narrationSettings=narration_settings,input=inp.model_dump(),evidence=evidence.model_dump())
            if voice and narration_settings.get('resolvedVoice') not in (None,voice):warnings.append('Requested voice '+voice+' resolved to '+str(narration_settings['resolvedVoice'])+' for '+audio.provider+'.')
            if speed not in ('+0%','0%',0,None) and narration_settings.get('resolvedSpeed') is None:warnings.append(audio.provider+' does not expose this speed control; its natural recorded timing is used.')
            mix_source=raw
            if (config.NEWS_MUSIC if music is None else music):
                mixed=mix_music(audio.model_copy(update={'path':str(raw.resolve()),'duration':probe_duration(raw)}),out,music_path)
                mix_source=Path(mixed.path);diagnostics['music']={'enabled':True,'source':str(music_path or 'existing procedural music engine'),'ducking':True}
            else:diagnostics['music']={'enabled':False}
            mix=out/'master.wav';diagnostics['loudness']=normalize(mix_source,mix)
            begin('cutouts','Finding portraits, checking generated likenesses and preparing contextual cutouts')
            diagnostics.update(acquisition_diagnostics)
            entities,assets=cutout_future.result()
            diagnostics.update(acquisition_diagnostics)
        finally:
            prefetch_stop.set()
            cutout_pool.shutdown(wait=True)
        begin('timeline','Aligning semantic beats to the final master track')
        # The atomic director already owns layout intent. Keep the legacy plan
        # for inspection without a redundant LLM layout request in this mode.
        plan=semantic_plan(script,None if direction is not None else llm,diagnostics=diagnostics);(out/'semantic_plan.json').write_text(json.dumps(plan,indent=2))
        m=build(script,words,sections,entities,assets,mix,out,generation,diagnostics,plan,subtitle_mode,visual_cues=cues,direction=direction,visual_settings=visual_settings)
        if autopilot_hook:
            m.diagnostics['autopilotHook']=autopilot_hook
            m.diagnostics['autopilotStoryId']=autopilot_story_id
        m.warnings.extend(diagnostics.get('visualDirector',{}).get('warnings',[]))
        m.warnings.extend(warnings+diagnostics.get('alignmentWarnings',[])+diagnostics['semanticPlan']['warnings']+diagnostics['visualPlan']['warnings'])
        if target_duration and abs(m.durationInFrames/30-target_duration)>max(5,target_duration*.2):m.warnings.append('Actual speech duration differs from target; no padding added.')
        if brand_text:m.warnings.append('Brand text is omitted by this minimalist preset.')
        m.warnings=list(dict.fromkeys(m.warnings))
        if visual_settings.diagnosticMode:save_summary(m,out)
        subtitles(words,out/'subtitles');begin('compose')
        video,stats=render(m,out/'editorial.mp4',cancel_event)
        thumb=out/'thumbnail.jpg';run(['ffmpeg','-v','error','-y','-ss','1','-i',str(video),'-frames:v','1',str(thumb)])
        tracker.complete_stage(stage);timings[stage]=round(time.monotonic()-phase,3)
        m.diagnostics.update(stageTimings=timings,finalAudio=stats,outputs={'video':str(video.resolve()),'srt':str((out/'subtitles.srt').resolve()),'vtt':str((out/'subtitles.vtt').resolve())})
        manifest=out/'editorial_manifest.json';manifest.write_text(m.model_dump_json(indent=2))
        (out/'image_credits.txt').write_text('\n\n'.join(f'{a.subject}\n{a.attribution}\n{a.source}\n{a.fallback or ""}' for a in assets))
        return PipelineResult(success=True,video_path=video,srt_path=out/'subtitles.srt',thumbnail_path=thumb,duration=output_frames(m.durationInFrames,30)/30,resolution='1080x1920',video_format='vertical',title=script.summary,key_point_count=len(m.beats),processing_time=time.monotonic()-started,content_type='news',theme='reference_editorial',caption_style=subtitle_mode,hook=script.sentences[0].text,
            news_details={'performance':{'stageSeconds':timings,'assetWorkers':diagnostics['assetAcquisition'].get('workers',1),'uniqueAssets':len(assets),'assets':[{'entityId':r['entityId'],'seconds':r.get('elapsedSeconds')} for r in diagnostics['assetAcquisition']['assets']]},'status':'ready','preset':'reference_editorial','manifest':str(manifest.resolve()),'sources':[{'id':s.id,'title':s.title,'url':s.url} for s in evidence.sources],
                'images':[{'name':a.subject,'origin':'generated' if a.source.startswith('replicate:') else a.preparation,'identity_verified':a.factual,'attribution':a.attribution,'source_url':a.source,
                    'likeness_reviewed':any(r.get('assetId')==a.id and bool(r.get('generation',{}).get('visualReview')) for r in diagnostics['assetAcquisition']['assets'])} for a in assets],
                'narration':{'provider':audio.provider,'model':audio.model,'fallbacks':audio.fallbacks},'warnings':m.warnings,'audio':stats})
    except Exception as exc:
        tracker.fail_stage(stage,str(exc));details=exc.response() if isinstance(exc,NewsError) else {'status':'error','error':str(exc)}
        (out/'editorial_failure.json').write_text(json.dumps({'stage':stage,**details},indent=2))
        return PipelineResult(errors=[str(exc)],content_type='news',processing_time=time.monotonic()-started,news_details=details)
