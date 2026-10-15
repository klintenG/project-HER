"""Shared render settings; story manifests retain their original audio contract."""
import json
import math
import os


def branding_settings(seed='projecther'):
    settings=json.loads(os.environ.get('HER_BRANDING_JSON','{}'))
    if not isinstance(settings,dict):
        raise ValueError('HER_BRANDING_JSON must be an object')
    settings.setdefault('deterministicSeed',str(seed))
    return settings


def outro_frames(fps, settings=None):
    c=branding_settings() if settings is None else settings
    outro=c.get('outro',{})
    if not c.get('enabled',True) or not outro.get('enabled',True):return 0
    seconds=outro.get('durationSeconds',2.7)
    if not isinstance(seconds,(int,float)) or not math.isfinite(seconds) or not 2<=seconds<=3:
        raise ValueError('Brand outro duration must be 2–3 seconds')
    return math.floor(seconds*fps+.5)


def output_frames(story_frames,fps,settings=None):
    return story_frames+outro_frames(fps,settings)


def screen_frames(screen,fps):
    seconds=max(screen.get("duration",0),screen.get("audio_duration",0),*(w["end"] for w in screen.get("word_timings",[])),0)
    return max(1,math.ceil(seconds*fps))


def brand_encoded_video(path, *, seed='projecther', cancel_event=None):
    """Finish MoviePy output through the same ProjectHER composition and controller.

    Replace only after a successful render. The original survives failure/cancel.
    """
    import shutil
    import subprocess
    import uuid
    import signal
    import time
    from pathlib import Path
    import config
    from utils.render_resources import remotion_concurrency
    settings=branding_settings(seed)
    path=Path(path).resolve()
    metadata=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(path)]))
    video=next(s for s in metadata['streams'] if s['codec_type']=='video')
    num,den=map(int,video['r_frame_rate'].split('/'));fps=num/den
    frames=int(video.get('nb_frames') or math.ceil(float(video['duration'])*fps))
    if not settings.get('enabled',True):return frames/fps
    root=config.BASE_DIR/'remotion';cli=root/'node_modules/.bin/remotion'
    stage=root/'public'/'branding-renders'/uuid.uuid4().hex
    stage.mkdir(parents=True)
    result=path.with_name(path.stem+'-branded.mp4')
    try:
        shutil.copyfile(path,stage/'story.mp4')
        props={'title':'ProjectHER','screens':[],'fps':fps,'width':video['width'],'height':video['height'],
               'source_video':f'branding-renders/{stage.name}/story.mp4','source_duration_frames':frames,'branding':settings}
        propfile=stage/'props.json';propfile.write_text(json.dumps(props))
        log=path.with_suffix('.branding.log')
        with log.open('w') as handle:
            process=subprocess.Popen([str(cli),'render','src/index.ts','ProjectHER',str(result),'--props',str(propfile),
                '--concurrency',str(remotion_concurrency()),'--codec','h264','--crf','16','--overwrite'],cwd=root,stdout=handle,stderr=subprocess.STDOUT,start_new_session=True)
            started=time.monotonic()
            while process.poll() is None:
                if (cancel_event and cancel_event.is_set()) or time.monotonic()-started>1200:
                    os.killpg(process.pid,signal.SIGTERM);process.wait(timeout=10)
                    raise RuntimeError('Branding render cancelled or timed out; original video preserved')
                time.sleep(.2)
        if process.returncode:raise RuntimeError('Branding render failed; original preserved. See '+str(log))
        result.replace(path)
        return output_frames(frames,fps,settings)/fps
    finally:
        shutil.rmtree(stage,ignore_errors=True)
        result.unlink(missing_ok=True)
