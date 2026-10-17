"""Isolated Remotion composition, immutable staged assets, explicit BT.709 export."""
from pathlib import Path
import json
import shutil
import subprocess
import signal
import os
import time
import logging
import math
import re
from agent.branding import branding_settings, output_frames
import config
from utils.render_resources import remotion_concurrency
from agent.news_models import NewsError
from .models import Timeline,digest
from .audio import measure,normalize

logger=logging.getLogger(__name__)


def delivery_issues(stats,*,allow_silence=False):
    loudness=stats['integratedLUFS'];peak=stats['truePeakDBTP']
    if loudness is None or peak is None:
        return [] if allow_silence and loudness is None and peak is None else ['missing audible narration or finite audio measurements']
    issues=[]
    if not math.isfinite(loudness) or abs(loudness+15)>1:issues.append(f'loudness {loudness} LUFS is outside -15 ±1 LUFS')
    if not math.isfinite(peak) or peak>-1:issues.append(f'true peak {peak} dBTP exceeds -1 dBTP')
    return issues


def finalize_audio(m,intermediate,output,cancel_event=None):
    """Measure actual AAC and repair codec overshoot without rerendering video.

    Each correction starts from the lossless master when it is the whole mix,
    never from the previous rejected AAC. Other timelines use the intermediate
    rendered mix so configured offsets/gains/music/effects remain intact.
    """
    output=Path(output);intermediate=Path(intermediate)
    audit_path=output.with_name(output.stem+'-metrics.json')
    attempts=[];source=None
    for repair in range(3):
        if cancel_event and cancel_event.is_set():raise NewsError('Editorial export cancelled','cancelled')
        stats=measure(output)
        meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(output)]))
        video=next(s for s in meta['streams'] if s['codec_type']=='video')
        issues=delivery_issues(stats,allow_silence=not m.words)
        attempts.append({'attempt':repair,'audio':stats,'issues':issues,'normalizationPeakDBTP':None if repair==0 else -1.5-.5*repair})
        # Save failures as well as successes: the previous gate discarded the
        # exact encoded measurements needed to diagnose a rejected export.
        audit={'audio':stats,'media':meta,'audioDelivery':{'targetLUFS':-15,'toleranceLU':1,'truePeakCeilingDBTP':-1,'passed':not issues,'attempts':attempts}}
        audit_path.write_text(json.dumps(audit,indent=2))
        if any(video.get(k)!='bt709' for k in ('color_space','color_transfer','color_primaries')) or video.get('pix_fmt')!='yuv420p':
            raise NewsError('Export color metadata failed validation; see '+str(audit_path))
        if not issues:
            if repair:
                stats['deliveryCorrection']={'repairs':repair,'normalizationPeakDBTP':-1.5-.5*repair,'measurements':str(audit_path.resolve())}
                m.warnings.append('AAC encoding required an automatic audio-only correction; final encoded loudness and true peak passed delivery checks.')
            return stats
        if repair==2 or stats['integratedLUFS'] is None:
            raise NewsError('Final AAC failed delivery targets after audio validation: '+'; '.join(issues)+'. Measurements: '+str(audit_path))
        logger.warning('Encoded editorial audio needs correction: %s; retrying audio only with more peak headroom.', '; '.join(issues))
        if source is None:
            master=m.audio[0] if len(m.audio)==1 else None
            if master and master.kind=='master' and master.gain==1 and master.offsetFrames==0:
                source=Path(master.path)
                if digest(source)!=master.sha256:raise NewsError('Stale editorial master checksum during audio correction.')
            else:
                source=output.with_name(output.stem+'-rendered-mix.wav')
                subprocess.run(['ffmpeg','-v','error','-y','-i',str(intermediate),'-map','0:a:0','-vn','-ar','48000','-ac','2','-c:a','pcm_s24le',str(source)],capture_output=True,check=True,timeout=180)
        corrected=output.with_name(output.stem+'-audio-delivery.wav')
        correction=normalize(source,corrected,true_peak=-2-.5*repair)
        attempts[-1]['correction']={'source':str(source.resolve()),'normalization':correction}
        if cancel_event and cancel_event.is_set():raise NewsError('Editorial export cancelled','cancelled')
        replacement=output.with_name(output.stem+'-audio-delivery.mp4')
        # apad/atrim preserve the composition and intentional closing hold;
        # -c:v copy keeps every already-rendered frame unchanged.
        subprocess.run(['ffmpeg','-v','error','-y','-i',str(output),'-i',str(corrected),'-map','0:v:0','-map','1:a:0',
            '-c:v','copy','-af',f'apad,atrim=duration={output_frames(m.durationInFrames,m.fps)/m.fps}',
            '-c:a','aac','-b:a','192k','-ar','48000','-ac','2','-movflags','+faststart',str(replacement)],capture_output=True,check=True,timeout=180)
        replacement.replace(output)


def stage(timeline,output):
    m=Timeline.model_validate(timeline.model_dump());props=m.model_dump();props['branding']=branding_settings(m.generationId)
    if digest(m.fonts.semibold)+digest(m.fonts.bold)!=m.fonts.version:raise NewsError('Editorial font changed; rebuild measured phrase geometry before rendering.')
    stage=config.BASE_DIR/'remotion/public/editorial'/m.generationId;stage.mkdir(parents=True,exist_ok=True)
    def copy(source,name,sha=None):
        path=Path(source)
        if not path.is_file():raise NewsError('Missing editorial render asset: '+str(path))
        if sha and digest(path)!=sha:raise NewsError('Stale editorial asset/audio checksum: '+str(path))
        destination=stage/name
        if path.resolve()!=destination.resolve():shutil.copyfile(path,destination)
        return f'editorial/{m.generationId}/{name}'
    for i,a in enumerate(m.assets):props['assets'][i]['path']=copy(a.path,f'asset-{i}{Path(a.path).suffix}',a.sha256)
    for i,a in enumerate(m.audio):props['audio'][i]['path']=copy(a.path,f'audio-{i}.wav',a.sha256)
    props['fonts']['semibold']=copy(m.fonts.semibold,'Poppins-SemiBold.ttf')
    props['fonts']['bold']=copy(m.fonts.bold,'Poppins-Bold.ttf')
    path=Path(output)/'editorial_props.json';path.write_text(json.dumps(props,ensure_ascii=False,indent=2))
    return path.resolve()


def render(m,output,cancel_event=None,trace=None):
    timings={};render_started=time.monotonic()
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    stage_started=time.monotonic()
    props=trace.call('asset_upload_or_download',stage,m,output.parent) if trace else stage(m,output.parent);root=config.BASE_DIR/'remotion';cli=root/'node_modules/.bin/remotion'
    timings['assetStagingSeconds']=round(time.monotonic()-stage_started,3)
    intermediate=output.with_name(output.stem+'-remotion.mp4')
    log=output.with_suffix('.render.log')
    color_options=['--color-space','bt709','--image-format','png'] if config.EDITORIAL_DIRECT_BT709 else []
    concurrency=remotion_concurrency()
    timings['remotionConcurrency']=concurrency
    remotion_started=time.monotonic()
    from contextlib import nullcontext
    with (trace.span('Remotion_or_other_render') if trace else nullcontext()), log.open('w') as handle:
        p=subprocess.Popen([str(cli),'render','src/index.ts','ProjectHEREditorial',str(intermediate.resolve()),'--props',str(props),
            '--concurrency',str(concurrency),
            '--codec','h264','--crf','16','--pixel-format','yuv420p','--overwrite',*color_options],cwd=root,stdout=handle,stderr=subprocess.STDOUT,start_new_session=True)
        deadline=time.monotonic()+1200
        while p.poll() is None:
            if (cancel_event and cancel_event.is_set()) or time.monotonic()>deadline:
                os.killpg(p.pid,signal.SIGTERM);p.wait(timeout=10);raise NewsError('Editorial render cancelled or timed out; see '+str(log))
            time.sleep(.2)
    if p.returncode:raise NewsError('Editorial Remotion failed: '+log.read_text()[-2500:])
    timings['remotionRenderSeconds']=round(time.monotonic()-remotion_started,3)
    timings['remotionSeconds']=round(time.monotonic()-render_started,3)
    # Remotion 4.0.242 emits full-range BT.470bg here. Explicit conversion, not
    # merely relabeling metadata, keeps the stage neutral and exports limited 709.
    encode_started=time.monotonic()
    encode_span=trace.span('FFmpeg_encode_and_mux') if trace else nullcontext()
    with encode_span:
        if config.EDITORIAL_DIRECT_BT709:
            # A metadata gate precedes stream copy. Never silently relabel a
            # 601 render as 709, nor drop an existing soundtrack/offset.
            metadata=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(intermediate)]))
            stream=next(s for s in metadata['streams'] if s['codec_type']=='video')
            if any(stream.get(k)!='bt709' for k in ('color_space','color_transfer','color_primaries')) or stream.get('pix_fmt')!='yuv420p':
                raise NewsError('Direct BT.709 render failed metadata validation; disable HER_EDITORIAL_DIRECT_BT709 for rollback.')
            subprocess.run(['ffmpeg','-v','error','-y','-i',str(intermediate),'-c:v','copy','-c:a','aac',
                '-b:a','192k','-ar','48000','-ac','2','-movflags','+faststart',str(output)],capture_output=True,check=True,timeout=240)
        else:
            subprocess.run(['ffmpeg','-v','error','-y','-i',str(intermediate),'-vf',
        'scale=in_range=pc:out_range=tv:in_color_matrix=bt601:out_color_matrix=bt709,format=yuv420p','-c:v','libx264','-crf','17','-preset','medium',
        '-x264-params','colorprim=bt709:transfer=bt709:colormatrix=bt709:range=tv',
        '-color_range','tv','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709',
        '-c:a','aac','-b:a','192k','-ar','48000','-ac','2','-movflags','+faststart',str(output)],capture_output=True,check=True,timeout=240)
    timings['ffmpegEncodeSeconds']=round(time.monotonic()-encode_started,3)
    timings['videoEncodePasses']=1 if config.EDITORIAL_DIRECT_BT709 else 2
    delivery_started=time.monotonic()
    stats=finalize_audio(m,intermediate,output,cancel_event)
    timings['audioDeliverySeconds']=round(time.monotonic()-delivery_started,3)
    qa_started=time.monotonic()
    # Inspect the encoded deliverable, not just the requested composition.
    metadata=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(output)]))
    video_stream=next(s for s in metadata['streams'] if s['codec_type']=='video')
    expected=output_frames(m.durationInFrames,m.fps)/m.fps
    duration=float(video_stream.get('duration',0))
    scan=subprocess.run(['ffmpeg','-hide_banner','-i',str(output),'-vf','blackdetect=d=0.25:pix_th=0.05:pic_th=0.98','-an','-f','null','-'],capture_output=True,text=True,check=True,timeout=180)
    black=[{'start':float(a),'end':float(b),'duration':float(c)} for a,b,c in re.findall(r'black_start:([\d.]+) black_end:([\d.]+) black_duration:([\d.]+)',scan.stderr)]
    quality={'expectedDuration':expected,'encodedDuration':duration,'blackIntervals':black,'passed':abs(duration-expected)<=2/m.fps and not black}
    output.with_name(output.stem+'-visual-quality.json').write_text(json.dumps(quality,indent=2))
    if not quality['passed']:raise NewsError('Encoded video failed duration/black-frame checks; see '+str(output.with_name(output.stem+'-visual-quality.json')))
    stats['visualQuality']=quality
    if m.editorialStyleVersion=='reference-v2':
        from .qa import activity
        report=activity(output)
        spans=[];start=None
        for interval in report['intervals']:
            if interval['meanDelta']<.9:
                if start is None:start=interval['at']-.2
            elif start is not None:
                if interval['at']-.2-start>=2.4:spans.append({'start':round(start,2),'end':round(interval['at']-.2,2)})
                start=None
        if start is not None and expected-start>=2.4:spans.append({'start':round(start,2),'end':expected})
        report['longLowActivitySpans']=spans
        output.with_name(output.stem+'-activity.json').write_text(json.dumps(report,indent=2))
        stats['activityReport']=str(output.with_name(output.stem+'-activity.json').resolve())
        if spans:m.warnings.append('Encoded video contains long low-activity spans; review editorial-activity.json for intentional holds versus static storytelling.')
    timings['visualQualityScanSeconds']=round(time.monotonic()-qa_started,3)
    timings['renderAndQualitySeconds']=round(time.monotonic()-render_started,3)
    stats['stageTimings']=timings
    return output,stats
