"""Reference editorial preset through the existing News script/TTS routes."""
from __future__ import annotations
from agent.branding import output_frames
import json
import time
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import config
from agent.news_models import NewsError
from utils.progress import ProgressTracker
from utils.job_trace import JobTrace
from .audio import prepare_existing,normalize,subtitles,run
from .assets import acquire
from .planner import build,semantic_plan
from .render import render

STAGES=[('resolve','Resolving input'),('research','Extracting source evidence'),('script','Approving script'),('media','Generating narration and cutouts'),('timeline','Planning editorial beats'),('compose','Rendering and measuring mix')]


def prepare_parallel_media(speech,visuals,cancel_event=None,on_speech_ready=None,diagnostics=None):
    """Overlap remote media work; return only after all cutout processing ends."""
    abandon_assets=threading.Event()
    class AssetCancellation:
        def is_set(self):return abandon_assets.is_set() or (cancel_event is not None and cancel_event.is_set())
    marks={};started=time.monotonic()
    def timed_visuals():
        marks['visualStart']=time.monotonic()
        try:return visuals(AssetCancellation())
        finally:marks['visualEnd']=time.monotonic()
    with ThreadPoolExecutor(max_workers=1) as asset_pool:
        asset_future=asset_pool.submit(timed_visuals)
        try:
            marks['speechStart']=time.monotonic()
            audio=speech()
            marks['speechEnd']=time.monotonic()
            if on_speech_ready:on_speech_ready()
            assets=asset_future.result()
            if diagnostics is not None:
                diagnostics.update(wallSeconds=round(time.monotonic()-started,3),
                    speechSeconds=round(marks['speechEnd']-marks['speechStart'],3),
                    cutoutsSeconds=round(marks['visualEnd']-marks['visualStart'],3),
                    overlapSeconds=round(max(0,min(marks['speechEnd'],marks['visualEnd'])-max(marks['speechStart'],marks['visualStart'])),3))
            return audio,assets
        except Exception:
            abandon_assets.set()
            raise

def check_configuration(renderer,video_format,subtitle_mode,asset_mode):
    if renderer!='remotion':raise NewsError('reference_editorial requires Remotion; MoviePy cannot render its persistent layers and events.')
    if video_format!='vertical':raise NewsError('reference_editorial currently supports 1080 × 1920 vertical only. Choose another preset for square or horizontal.')
    if subtitle_mode not in ('editorial','complete'):raise NewsError('Editorial text mode must be editorial or complete.')
    if asset_mode not in ('auto','stock','ai','local'):raise NewsError('Editorial assets must be auto, stock, ai, or local.')


def run_editorial(text,*,output_dir=None,source_policy='auto',tone='informative',language='english',target_duration=0,video_format='vertical',renderer='remotion',voice=None,tts_provider=None,speed='+0%',quality='high',brand_text='',progress_callback=None,cancel_event=None,music=None,music_path=None,llm=None,image_generator=None,processor=None,tts_engine=None,subtitle_mode='editorial',asset_mode='auto',local_assets=None):
    from agent.orchestrator import PipelineResult
    from agent.news_script import NewsLLM,write_script
    from agent.news_research import analyze_input,research
    from agent.news_audio import synthesize,mix_music
    from agent.news_tts import LANGUAGES,cancelled
    started=time.monotonic();generation='editorial_'+uuid.uuid4().hex
    out=Path(output_dir) if output_dir else config.OUTPUT_DIR/generation;out.mkdir(parents=True,exist_ok=True)
    trace=JobTrace(out/'job_trace.json',out.name if out.name.startswith('portfolio_') else generation)
    total_span=trace.span('end_to_end');total_span.__enter__()
    tracker=ProgressTracker(progress_callback,stages=STAGES);stage='resolve';timings={};phase=time.monotonic()
    def begin(name,message=''):
        nonlocal stage,phase
        cancelled(cancel_event);tracker.complete_stage(stage);timings[stage]=round(time.monotonic()-phase,3)
        stage=name;phase=time.monotonic();tracker.start_stage(stage,message)
    try:
        tracker.start_stage(stage);check_configuration(renderer,video_format,subtitle_mode,asset_mode)
        llm=llm or NewsLLM();inp=trace.call('input_fetch_and_extract',analyze_input,text,source_policy,llm,diagnostics_path=out/'input_classification.json')
        begin('research');evidence,warnings=trace.call('research',research,inp,llm)
        begin('script');script=trace.call('research_or_script_generation',write_script,inp,evidence,llm,tone,language,target_duration or config.NEWS_DEFAULT_DURATION,editorial=True)
        from agent.news_layout import validate_glyphs
        for sentence in script.sentences:validate_glyphs(sentence.text)
        for entity in script.entities:validate_glyphs(entity.name)
        (out/'news_preview.json').write_text(json.dumps({'input':inp.model_dump(),'evidence':evidence.model_dump(),'script':script.model_dump(),'warnings':warnings},ensure_ascii=False,indent=2))
        from .visuals import plan_visuals
        from . import sentence_storyboard as storyboard
        strict=config.SENTENCE_PRIMARY_VISUALS
        if strict:script=trace.call('narration_segmentation',storyboard.segment,script)
        narration_settings={};asset_diagnostics={};media_timings={}
        approved_script=script
        begin('media','Planning narrative visuals and generating narration')
        def speech():
            speech_started=time.monotonic()
            try:return trace.call('TTS_generation',synthesize,approved_script,out,tts_provider or config.TTS_PROVIDER,voice,speed,tts_engine,pause=0,language=language,cancel_event=cancel_event,diagnostic_sink=narration_settings)
            finally:media_timings['actualSpeechSeconds']=round(time.monotonic()-speech_started,3)
        # The approved narration is immutable under visual planning. Start TTS
        # while the optional visual LLM decides which cutouts are needed.
        speech_pool=ThreadPoolExecutor(max_workers=1) if config.PARALLEL_ASSET_PIPELINE_V2 else None
        speech_future=speech_pool.submit(speech) if speech_pool else None
        visual_diagnostics={}
        # Local registries intentionally specify every supplied subject; they
        # retain the script plan instead of adding unregistered illustrations.
        visual_started=time.monotonic()
        script,cues=trace.call('semantic_beat_planning',storyboard.plan if strict else plan_visuals,script,evidence,llm if strict or asset_mode!='local' else None,visual_diagnostics)
        timings['semantic_beat_planning']=round(time.monotonic()-visual_started,3)
        if strict:(out/'sentence_storyboard.json').write_text(json.dumps(script.sentence_storyboard,ensure_ascii=False,indent=2))
        (out/'visual_plan.json').write_text(json.dumps({'script':script.model_dump(),'sections':cues,'diagnostics':visual_diagnostics},ensure_ascii=False,indent=2))
        tracker.update_stage('media',detail='Generating narration and sourcing cutouts together')
        # Remote speech and cutout sourcing are independent after the approved
        # visual script. Finish cutouts before loading Whisper for alignment so
        # the 4 GiB production worker never holds both inference models.
        visuals=lambda visual_cancel:acquire(script,out/'assets',local_registry=local_assets,asset_mode=asset_mode,llm=llm,
            cancel_event=visual_cancel,image_generator=image_generator,processor=processor,evidence=evidence,diagnostics=asset_diagnostics,trace=trace)
        audio,(entities,assets)=prepare_parallel_media((lambda:speech_future.result()) if speech_future else speech,visuals,cancel_event,
            lambda:tracker.update_stage('media',progress=.5,detail='Speech ready; completing visual cutouts'),media_timings)
        if speech_pool:speech_pool.shutdown(wait=True);speech_pool=None
        cancelled(cancel_event)
        if strict:
            from .vision import VisualReview
            visual_diagnostics['sentenceQuality']=trace.call('sentence_asset_validation',storyboard.validate_assets,script,assets,asset_diagnostics.get('assetAcquisition',{}),VisualReview())
        tracker.update_stage('media',progress=.75,detail='Aligning approved narration to audio')
        code=LANGUAGES.get(language.lower(),language.lower()).split('-')[0]
        align_started=time.monotonic()
        raw,words,sections,diagnostics=trace.call('word_forced_alignment',prepare_existing,script,audio,out/'audio',code)
        timings['word_forced_alignment']=round(time.monotonic()-align_started,3)
        if getattr(script,'narrative_plan',None):
            script.narrative_plan.bind_audio(words).validate_script(script)
            visual_diagnostics['narrativeQuality']=script.narrative_plan.assess_assets(assets,asset_diagnostics.get('assetAcquisition',{}))
            (out/'narrative_beat_plan.json').write_text(script.narrative_plan.model_dump_json(indent=2))
        diagnostics.update(asset_diagnostics,mediaTimings=media_timings)
        if getattr(script,'narrative_plan',None):diagnostics['narrativeBeatPlan']=script.narrative_plan.model_dump()
        diagnostics.update(visual_diagnostics)
        from .director import VisualSettings,direct,save_summary
        visual_settings=VisualSettings.configured()
        direction_started=time.monotonic()
        direction=storyboard.direction(script) if strict else direct(script,words,cues,None if asset_mode=='local' else llm,visual_settings,diagnostics) if visual_settings.narrationDrivenVisualsEnabled else None
        timings['scene_planning_and_layout']=round(time.monotonic()-direction_started,3)
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
        mix=out/'master.wav';diagnostics['loudness']=trace.call('audio_normalization',normalize,mix_source,mix)
        begin('timeline','Aligning semantic beats to the final master track')
        # The atomic director already owns layout intent. Keep the legacy plan
        # for inspection without a redundant LLM layout request in this mode.
        plan=trace.call('timeline_planning',semantic_plan,script,None if direction is not None else llm,diagnostics=diagnostics);(out/'semantic_plan.json').write_text(json.dumps(plan,indent=2))
        m=build(script,words,sections,entities,assets,mix,out,generation,diagnostics,plan,subtitle_mode,visual_cues=cues,direction=direction,visual_settings=visual_settings)
        if strict:
            diagnostics['sentenceQuality'].update(trace.call('sentence_render_validation',storyboard.validate_render,script,m))
            (out/'sentence_storyboard.json').write_text(json.dumps(script.sentence_storyboard,ensure_ascii=False,indent=2))
        m.warnings.extend(diagnostics.get('visualDirector',{}).get('warnings',[]))
        m.warnings.extend(warnings+diagnostics.get('alignmentWarnings',[])+diagnostics.get('semanticPlan',{}).get('warnings',[])+diagnostics.get('visualPlan',{}).get('warnings',[]))
        if diagnostics.get('narrativeQuality',{}).get('degradedBeats'):
            m.warnings.append('Some required action visuals are degraded; review narrative_beat_plan.json before publishing.')
        if diagnostics.get('sentenceQuality',{}).get('degraded_sentences') or (diagnostics.get('sentenceQuality') and not diagnostics['sentenceQuality'].get('fullyCompliant',True)):
            m.warnings.append('Some sentence visuals used graceful fallback; video completed with degraded visual flags.')
        if target_duration and abs(m.durationInFrames/30-target_duration)>max(5,target_duration*.2):m.warnings.append('Actual speech duration differs from target; no padding added.')
        if brand_text:m.warnings.append('Brand text is omitted by this minimalist preset.')
        m.warnings=list(dict.fromkeys(m.warnings))
        if visual_settings.diagnosticMode:save_summary(m,out)
        subtitles(words,out/'subtitles');begin('compose')
        render_started=time.monotonic()
        video,stats=trace.call('render_and_delivery',render,m,out/'editorial.mp4',cancel_event,trace=trace)
        timings['Remotion_and_FFmpeg']=round(time.monotonic()-render_started,3)
        thumb=out/'thumbnail.jpg';run(['ffmpeg','-v','error','-y','-ss','1','-i',str(video),'-frames:v','1',str(thumb)])
        tracker.complete_stage(stage);timings[stage]=round(time.monotonic()-phase,3)
        timings['end_to_end']=round(time.monotonic()-started,3)
        m.diagnostics.update(stageTimings=timings,criticalPathSeconds=timings['end_to_end'],finalAudio=stats,outputs={'video':str(video.resolve()),'srt':str((out/'subtitles.srt').resolve()),'vtt':str((out/'subtitles.vtt').resolve())})
        manifest=out/'editorial_manifest.json';manifest.write_text(m.model_dump_json(indent=2))
        (out/'image_credits.txt').write_text('\n\n'.join(f'{a.subject}\n{a.attribution}\n{a.source}\n{a.fallback or ""}' for a in assets))
        total_span.__exit__(None,None,None)
        if getattr(config,'PERF_DIAGNOSTICS',True):
            try:
                from utils.generation_diagnostics import export_reports
                export_reports(out,trace.job_id,'succeeded')
            except Exception:pass
        return PipelineResult(success=True,video_path=video,srt_path=out/'subtitles.srt',thumbnail_path=thumb,duration=output_frames(m.durationInFrames,30)/30,resolution='1080x1920',video_format='vertical',title=script.summary,key_point_count=len(m.beats),processing_time=time.monotonic()-started,content_type='news',theme='reference_editorial',caption_style=subtitle_mode,hook=script.sentences[0].text,
            news_details={'status':'ready','preset':'reference_editorial','output_dir':str(out.resolve()),'manifest':str(manifest.resolve()),'sources':[{'id':s.id,'title':s.title,'url':s.url} for s in evidence.sources],
                'images':[{'name':a.subject,'origin':'generated' if a.source.startswith('replicate:') else a.preparation,'identity_verified':a.factual,'attribution':a.attribution,'source_url':a.source,
                    'likeness_reviewed':any(r.get('assetId')==a.id and bool(r.get('generation',{}).get('visualReview')) for r in diagnostics['assetAcquisition']['assets'])} for a in assets],
                'narration':{'provider':audio.provider,'model':audio.model,'fallbacks':audio.fallbacks},'warnings':m.warnings,'audio':stats,
                'narrative_quality':diagnostics.get('narrativeQuality'),'sentence_quality':diagnostics.get('sentenceQuality')})
    except Exception as exc:
        if 'speech_pool' in locals() and speech_pool:speech_pool.shutdown(wait=True,cancel_futures=True)
        tracker.fail_stage(stage,str(exc));details=exc.response() if isinstance(exc,NewsError) else {'status':'error','error':str(exc)}
        details['output_dir']=str(out.resolve())
        (out/'editorial_failure.json').write_text(json.dumps({'stage':stage,**details},indent=2))
        total_span.__exit__(type(exc),exc,exc.__traceback__)
        if getattr(config,'PERF_DIAGNOSTICS',True):
            try:
                from utils.generation_diagnostics import export_reports
                export_reports(out,trace.job_id,'failed')
            except Exception:pass
        return PipelineResult(errors=[str(exc)],content_type='news',processing_time=time.monotonic()-started,news_details=details)
