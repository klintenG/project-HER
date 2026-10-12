"""Isolated, durable Remotion asset bridge. Never uses the legacy slideshow fallback."""
from __future__ import annotations
import json
import shutil
import subprocess
import os
import signal
import time
from pathlib import Path
from agent.news_models import Manifest, NewsError
import config


def stage_remotion(manifest,output):
    manifest=Manifest.model_validate(manifest.model_dump())
    root=config.BASE_DIR/'remotion'
    stage=root/'public'/'news'/manifest.generation_id
    stage.mkdir(parents=True,exist_ok=True)
    props=manifest.model_dump()
    def copy(path,name):
        source=Path(path)
        if not source.is_file(): raise NewsError('Missing News render asset: '+name)
        shutil.copy2(source,stage/name)
        return f'news/{manifest.generation_id}/{name}'
    props['audio']['path']=copy(manifest.audio.path,'narration.wav')
    props['theme']['font_semibold']=copy(manifest.theme.font_semibold,'Poppins-SemiBold.ttf')
    props['theme']['font_bold']=copy(manifest.theme.font_bold,'Poppins-Bold.ttf')
    for i,a in enumerate(manifest.assets):
        props['assets'][i]['path']=copy(a.path,f'cutout-{i}.png')
    path=Path(output)/'news_remotion_props.json'
    path.write_text(json.dumps(props,ensure_ascii=False,indent=2))
    return path.resolve()


def render_remotion(manifest,path,cancel_event=None):
    props=stage_remotion(manifest,Path(path).parent)
    root=config.BASE_DIR/'remotion'
    cli=root/'node_modules'/'.bin'/'remotion'
    if not cli.is_file(): raise NewsError('Run npm ci in remotion/ before selecting Remotion.')
    process=subprocess.Popen([str(cli),'render','src/index.ts','ProjectHERNews',str(Path(path).resolve()),'--props',str(props),'--concurrency','2','--overwrite'],cwd=str(root),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=os.name=='posix')
    started=time.monotonic()
    try:
        while True:
            if cancel_event is not None and cancel_event.is_set(): raise NewsError('News generation cancelled.','cancelled')
            if time.monotonic()-started>900: raise NewsError('News Remotion render exceeded the 15-minute limit.')
            try:
                stdout,stderr=process.communicate(timeout=.25)
                break
            except subprocess.TimeoutExpired:
                continue
        if process.returncode: raise NewsError('News Remotion render failed: '+(stderr or stdout)[-1800:])
    except BaseException:
        if process.poll() is None:
            if os.name=='posix': os.killpg(process.pid,signal.SIGTERM)
            else: process.terminate()
            try: process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                if os.name=='posix': os.killpg(process.pid,signal.SIGKILL)
                else: process.kill()
                process.communicate()
        shutil.rmtree(root/'public'/'news'/manifest.generation_id,ignore_errors=True)
        raise
    if not Path(path).is_file(): raise NewsError('News renderer produced no video.')
    return Path(path)
