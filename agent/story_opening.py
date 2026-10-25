"""Shared two-second title/cutout lead-in for manual and autonomous exports.

Canonical story manifests retain narration-relative timing; opening.json records
its delivery offset. Captions and the exported MP4 include that offset.
"""
from __future__ import annotations
import functools
import hashlib
import json
import re
import os
import signal
import subprocess
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
import config

SECONDS=2.0


def run(args,cancel_event=None):
    process=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    deadline=time.monotonic()+900
    try:
        while True:
            if cancel_event and cancel_event.is_set():raise ValueError('Opening export cancelled')
            if time.monotonic()>deadline:raise TimeoutError('Opening export timed out')
            try:
                stdout,stderr=process.communicate(timeout=.5)
                if process.returncode:raise subprocess.CalledProcessError(process.returncode,args,stdout,stderr)
                return subprocess.CompletedProcess(args,process.returncode,stdout,stderr)
            except subprocess.TimeoutExpired:continue
    except BaseException:
        if process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.communicate(timeout=5)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.communicate()
        raise


def checksum(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):h.update(block)
    return h.hexdigest()


def short_title(title,hook=''):
    """Use approved story wording rather than manufacturing a clickbait claim."""
    title=re.sub(r'\s+',' ',title or '').strip()
    hook=re.sub(r'\s+',' ',hook or '').strip()
    source=hook if 1<=len(hook.split())<=8 and len(hook)<=70 else title or hook
    source=re.split(r'[.!;\n]',source)[0].strip()
    words=source.split()[:8]
    while words and (len(' '.join(words))>70 or words[-1].lower() in ('the','a','an','of','and','to','with','in','for','by')):words.pop()
    if not words:raise ValueError('Opening needs a meaningful story title')
    return ' '.join(words).rstrip(' ,:')


def assets_for(video):
    root=Path(video).parent
    original=root/'opening-assets.json'
    if original.exists():return json.loads(original.read_text())
    for name in ('editorial_props.json','remotion_props.json','news_manifest.json','manifest.json'):
        path=root/name
        if not path.exists():continue
        data=json.loads(path.read_text())
        rows=[{**a,'path':a.get('path') or a.get('local_path'),'subject':a.get('subject') or a.get('entity_id','')} for a in data.get('assets',[])]
        if rows:
            return rows
        rows=[{'path':p,'subject':s.get('character_name') or s.get('subject_text') or s.get('text',''),
               'role':'portrait'} for s in data.get('screens',[]) if not s.get('is_outro')
              for p in s.get('image_paths',[]) if p]
        if rows:return rows
    # MoviePy exports keep original source images beside the video.
    return [{'path':str(p.resolve()),'subject':p.stem,'role':'object'}
            for p in sorted(root.glob('*.png')) if not any(x in p.stem for x in ('thumbnail','opening','preview'))]


def choose_cutout(rows,title,output):
    words=set(re.findall(r'\w+',title.casefold()))-{'the','a','of','and','in','to','with'}
    ranked=sorted(enumerate(rows),key=lambda pair:(
        -len(words.intersection(re.findall(r'\w+',pair[1].get('subject','').casefold()))),
        pair[1].get('role') not in ('portrait','object'),pair[0]))
    for _,row in ranked:
        if row.get('role') in ('map','document','symbol'):continue
        raw=Path(row.get('path',''))
        path=raw if raw.is_absolute() else config.BASE_DIR/'remotion/public'/raw
        if not path.is_file():continue
        with Image.open(path) as source:
            image=source.convert('RGBA')
            alpha=image.getchannel('A')
            if alpha.getextrema()[0]==255:
                # Classic stock/AI output needs a real cutout, not a rectangular photo.
                from agent.cutout_processor import CutoutProcessor
                cut=Path(output)/'opening-cutout.png'
                from agent.news_models import NewsError
                try:CutoutProcessor().process(path,cut,allow_portrait_crop=True,allow_bottom_crop=True)
                except NewsError:continue
                image=Image.open(cut).convert('RGBA')
            bbox=image.getbbox()
            if not bbox:continue
            return image.crop(bbox),{'subject':row.get('subject',''),'path':str(path),'id':row.get('id')}
    raise ValueError('Opening needs one usable story image cutout; no unrelated image was substituted')


def compose_card(title,cutout,target,size):
    width,height=size
    canvas=Image.new('RGBA',(1080,1920),'#dedde1')
    # Editorial paper palette, quiet halo and a single large subject.
    halo=Image.new('RGBA',canvas.size);draw=ImageDraw.Draw(halo)
    draw.ellipse((50,630,1030,1770),fill='#f1f0f2');halo=halo.filter(ImageFilter.GaussianBlur(90));canvas.alpha_composite(halo)
    draw=ImageDraw.Draw(canvas)
    fontroot=config.BASE_DIR/'assets/fonts/news'
    bold=str(fontroot/'Poppins-Bold.ttf');medium=str(fontroot/'Poppins-Medium.ttf')
    draw.text((90,125),'projectHER',font=ImageFont.truetype(bold,38),fill='#111b2b')
    draw.line((90,215,250,215),fill='#b58a48',width=6)
    for size_px in range(92,39,-2):
        font=ImageFont.truetype(bold,size_px);lines=[];line=''
        for word in title.split():
            candidate=(line+' '+word).strip()
            if draw.textlength(candidate,font=font)>900 and line:lines.append(line);line=word
            else:line=candidate
        lines.append(line)
        if len(lines)<=3 and all(draw.textlength(line,font=font)<=900 for line in lines):break
    if len(lines)>3 or any(draw.textlength(line,font=font)>900 for line in lines):raise ValueError('Opening title is too long to display legibly')
    draw.rounded_rectangle((70,300,1010,690),radius=24,fill='#111b2b')
    y=325+(330-len(lines)*(size_px+12))/2
    for i,line in enumerate(lines):draw.text((540,y+i*(size_px+12)),line,font=font,fill='#f7f5f0',anchor='mt')
    cutout=ImageOps.contain(cutout,(920,1030),Image.Resampling.LANCZOS)
    x=(1080-cutout.width)//2;y=755+(1030-cutout.height)//2
    shadow=Image.new('RGBA',canvas.size);shadow.paste('#111b2b',(x+12,y+20,x+12+cutout.width,y+20+cutout.height),cutout.getchannel('A'))
    shadow.putalpha(shadow.getchannel('A').point(lambda a:int(a*.16)));canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)))
    canvas.alpha_composite(cutout,(x,y))
    draw=ImageDraw.Draw(canvas);draw.text((540,1830),'STORIES IN MOTION',font=ImageFont.truetype(medium,23),fill='#44424c',anchor='mt')
    if width>=height:
        # Preserve portrait design proportions on landscape/square exports.
        fitted=ImageOps.contain(canvas,(width,height),Image.Resampling.LANCZOS)
        result=Image.new('RGBA',(width,height),'#dedde1');result.alpha_composite(fitted,((width-fitted.width)//2,(height-fitted.height)//2));canvas=result
    else:canvas=canvas.resize((width,height),Image.Resampling.LANCZOS)
    canvas.convert('RGB').save(target)


def shift_captions(path,seconds):
    path=Path(path)
    if not path.is_file():return
    def shift(match):
        h,m,s,separator,ms=match.groups();total=round((int(h)*3600+int(m)*60+int(s)+int(ms)/1000+seconds)*1000)
        return f'{total//3600000:02d}:{total//60000%60:02d}:{total//1000%60:02d}{separator}{total%1000:03d}'
    timestamp=r'(\d{2}):(\d{2}):(\d{2})([,.])(\d{3})'
    path.write_text(re.sub(r'(?m)^\d{2}:\d{2}:\d{2}[,.]\d{3} --> .*$',
        lambda cue:re.sub(timestamp,shift,cue.group(0)),path.read_text()))


def add_opening(result,hook='',cancel_event=None):
    if not result.success or not result.video_path or not Path(result.video_path).is_file():return result
    video=Path(result.video_path);metadata=video.with_name('opening.json')
    if metadata.exists():
        previous=json.loads(metadata.read_text())
        if previous.get('video_sha256')==checksum(video):return result
        raise ValueError('Opening metadata does not match this export; regenerate rather than prepend twice')
    title=short_title(result.title or result.hook,hook)
    cutout,asset=choose_cutout(assets_for(video),title,video.parent)
    probe=json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(video)]).stdout)
    stream=next(s for s in probe['streams'] if s['codec_type']=='video')
    if not any(s['codec_type']=='audio' for s in probe['streams']):raise ValueError('Story opening requires the narrated audio stream')
    fps=stream.get('r_frame_rate','30/1');duration=float(probe['format']['duration']);poster=video.with_name('opening.png')
    compose_card(title,cutout,poster,(stream['width'],stream['height']))
    if cancel_event and cancel_event.is_set():raise ValueError('Opening export cancelled')
    replacement=video.with_name(video.stem+'-with-opening.mp4')
    try:
        run(['ffmpeg','-v','error','-y','-loop','1','-framerate',fps,'-t',str(SECONDS),'-i',str(poster),'-i',str(video),
            '-filter_complex_threads','1','-filter_complex',
            '[0:v]setsar=1,format=yuv420p,fade=t=in:st=0:d=0.12:color=0xdedde1,fade=t=out:st=1.88:d=0.12:color=0xdedde1,setpts=PTS-STARTPTS[intro];[1:v]setsar=1,format=yuv420p,setpts=PTS-STARTPTS[story];'
            '[intro][story]concat=n=2:v=1:a=0[v];[1:a]adelay=2000:all=1,alimiter=limit=0.8414:level=false:latency=true,apad[a]',
            '-map','[v]','-map','[a]','-t',str(duration+SECONDS),'-r',fps,'-c:v','libx264','-preset','fast','-crf','17',
            '-color_range','tv','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709',
            '-c:a','aac','-b:a','192k','-ar','48000','-ac','2','-movflags','+faststart',str(replacement)],cancel_event)
        if cancel_event and cancel_event.is_set():raise ValueError('Opening export cancelled')
        replacement.replace(video)
    finally:replacement.unlink(missing_ok=True)
    paths={Path(result.srt_path)} if result.srt_path else set()
    paths.update(video.parent.glob('subtitles.vtt'))
    for path in paths:shift_captions(path,SECONDS)
    info={'version':1,'duration_seconds':SECONDS,'narration_offset_seconds':SECONDS,'title':title,
        'asset':asset,'poster_path':str(poster),'video_sha256':checksum(video),'additional_image_generations':0}
    metadata.write_text(json.dumps(info,indent=2))
    with Image.open(poster) as image:image.convert('RGB').save(video.with_name('thumbnail.jpg'),quality=95)
    result.duration=duration+SECONDS;result.thumbnail_path=poster
    result.news_details={**result.news_details,'opening':info}
    manifest=video.parent/'manifest.json'
    if manifest.exists():
        data=json.loads(manifest.read_text())
        if 'duration' in data and 'screens' not in data:
            data.update(duration=result.duration,opening=info,thumbnail_file=poster.name);manifest.write_text(json.dumps(data,indent=2))
    return result


def with_story_opening(function):
    @functools.wraps(function)
    def wrapped(*args,**kwargs):
        started=time.monotonic()
        result=function(*args,**kwargs)
        if not getattr(result,'success',False):return result
        try:
            callback=kwargs.get('progress_callback')
            existing=Path(result.video_path).with_name('opening.json') if result.video_path else None
            needs_opening=result.video_path and Path(result.video_path).is_file() and not (existing and existing.exists())
            if callback and needs_opening:
                from utils.progress import StageInfo
                callback(StageInfo(name='compose',label='Creating story opening',index=1,total=1,status='running',progress_pct=.99,detail='Adding the two-second title and story cutout; aligning subtitles'))
            updated=add_opening(result,kwargs.get('autopilot_hook',''),kwargs.get('cancel_event'))
            updated.processing_time=max(updated.processing_time,time.monotonic()-started)
            if callback and needs_opening:
                callback(StageInfo(name='compose',label='Story opening ready',index=1,total=1,status='completed',progress_pct=1))
            return updated
        except Exception as exc:
            result.success=False;result.errors.append('Story opening failed: '+str(exc))
            return result
    return wrapped

