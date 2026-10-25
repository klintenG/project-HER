"""Deterministic media quality gates and a cover captured from the final MP4."""
from __future__ import annotations
import hashlib
import json
import re
import subprocess
from pathlib import Path
from PIL import Image, ImageStat, ImageDraw, ImageFont, ImageOps
import config


def command(args, timeout=180):
    return subprocess.run(args,check=True,capture_output=True,text=True,timeout=timeout)


def file_hash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


class ThumbnailComposer:
    # Fully entered at .45s, exit starts at 2.3s in the common Remotion overlay.
    offset_ms=1500
    def compose(self,video,story):
        target=Path(video).with_name('thumbnail.png')
        command(['ffmpeg','-v','error','-y','-ss',str(self.offset_ms/1000),'-i',str(video),'-frames:v','1',str(target)])
        props_path=Path(video).parent/'editorial_props.json'
        selected=[]
        if props_path.exists():
            props=json.loads(props_path.read_text())
            candidates=[a for a in props['assets'] if a.get('alpha') and a.get('role') in ('portrait','object')]
            names=[n.casefold() for n in story.get('primary_characters',[])]
            candidates.sort(key=lambda a: (not any(n in a['subject'].casefold() for n in names),a.get('role')!='portrait'))
            if candidates:
                asset=candidates[0];source=config.BASE_DIR/'remotion/public'/asset['path']
                with Image.open(source) as original:
                    cutout=original.convert('RGBA')
                    bbox=cutout.getbbox()
                    if not bbox:raise ValueError('Selected cover cutout is empty')
                    cutout=ImageOps.contain(cutout.crop(bbox),(900,1060),Image.Resampling.LANCZOS)
                cover=Image.new('RGBA',(1080,1920),'#dedde1')
                cover.alpha_composite(cutout,((1080-cutout.width)//2,740+(1060-cutout.height)//2))
                draw=ImageDraw.Draw(cover)
                bold=str(config.BASE_DIR/'remotion/public/branding/Poppins-Bold.ttf')
                medium=str(config.BASE_DIR/'remotion/public/branding/Poppins-Medium.ttf')
                title=story['script']['hook_text']
                for size in range(82,35,-2):
                    font=ImageFont.truetype(bold,size);lines=[];line=''
                    for word in title.split():
                        proposed=(line+' '+word).strip()
                        if draw.textlength(proposed,font=font)>820 and line:lines.append(line);line=word
                        else:line=proposed
                    lines.append(line)
                    if len(lines)<=3 and all(draw.textlength(l,font=font)<=820 for l in lines):break
                draw.rounded_rectangle((86,346,994,700),radius=20,fill='#111b2b')
                draw.rectangle((86,365,94,680),fill='#cba96e')
                for i,line in enumerate(lines):draw.text((540,375+i*(size+12)),line,font=font,fill='#f7f5f0',anchor='mt')
                draw.text((540,180),'projectHER',font=ImageFont.truetype(bold,48),fill='#111b2b',anchor='mt')
                draw.text((540,1830),'STORIES IN MOTION',font=ImageFont.truetype(medium,24),fill='#111b2b',anchor='mt')
                cover.convert('RGB').save(target)
                selected=[{'id':asset['id'],'subject':asset['subject'],'path':asset['path']}]
                # Buffer selects an exported frame rather than accepting a cover upload.
                # Replace a brief opening interval without shifting audio or caption times.
                embedded=Path(video).with_name('cover-embedded.mp4')
                try:
                    command(['ffmpeg','-v','error','-y','-i',str(video),'-i',str(target),
                        '-filter_complex',"[0:v][1:v]overlay=0:0:enable='between(t,1.1,1.9)'[v]",
                        '-map','[v]','-map','0:a','-c:v','libx264','-preset','fast','-crf','18',
                        '-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart',str(embedded)],timeout=900)
                    embedded.replace(video)
                finally:embedded.unlink(missing_ok=True)
        with Image.open(target) as image:
            gray=image.convert('L')
            if image.size!=(1080,1920) or ImageStat.Stat(gray).stddev[0]<8 or ImageStat.Stat(gray).mean[0]<5:
                raise ValueError('Cover is incomplete, black, or incorrectly sized')
            panel=gray.crop((86,346,994,538))
            dark=sum(panel.histogram()[:90])/max(1,panel.width*panel.height)
            text=gray.crop((130,370,950,442))
            light=sum(text.histogram()[210:])/max(1,text.width*text.height)
            if dark<.4 or light<.01:
                raise ValueError('Cover hook panel is obscured or its text is not readable')
        metadata={'path':str(target),'offset_ms':self.offset_ms,'hook_text':story['script']['hook_text'],
            'visual_assets':selected,'additional_image_generations':0,
            'composition':'Single story cutout with editorial palette, typography and concise title' if selected else 'Opening frame fallback','size':[1080,1920]}
        target.with_suffix('.json').write_text(json.dumps(metadata,indent=2))
        return metadata


class VideoQualityValidator:
    def validate(self,video,settings,story,cover):
        video=Path(video);checks=[]
        def check(name,passed,detail=''):
            checks.append({'name':name,'result':'PASS' if passed else 'FAIL','detail':detail})
        check('file',video.is_file() and video.stat().st_size>1000)
        if not checks[-1]['result']=='PASS':return {'passed':False,'checks':checks}
        probe=json.loads(command(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(video)]).stdout)
        streams=probe['streams'];v=next((s for s in streams if s['codec_type']=='video'),{})
        a=next((s for s in streams if s['codec_type']=='audio'),{})
        duration=float(probe['format'].get('duration',0))
        check('container','mp4' in probe['format'].get('format_name',''))
        check('codecs',v.get('codec_name')=='h264' and a.get('codec_name')=='aac')
        check('portrait',(v.get('width'),v.get('height'))==(1080,1920))
        check('duration',settings.min_video_seconds<=duration<=settings.max_video_seconds,str(duration))
        check('cover_timestamp',0<cover['offset_ms']<duration*1000 and Path(cover['path']).is_file())
        editorial_path=video.parent/'editorial_props.json'
        if editorial_path.exists():
            from agent.editorial.models import Timeline
            props=json.loads(editorial_path.read_text())
            branding=props.pop('branding',{})
            try:
                timeline=Timeline.model_validate(props)
                check('timeline_contract',True)
            except ValueError:
                timeline=None
                check('timeline_contract',False)
            check('embedded_hook',props.get('diagnostics',{}).get('autopilotHook')==story['script']['hook_text'])
            check('story_assignment',props.get('diagnostics',{}).get('autopilotStoryId')==story['story_id'])
            check('floating_watermark',branding.get('enabled',True) and branding.get('protectiveOverlayEnabled',True)
                  and branding.get('protectiveOverlayOccurrences',2)>0 and branding.get('watermarkText')=='@project.HER')
            if timeline is not None:
                assets=[*timeline.assets,*timeline.audio]
                check('source_assets',bool(assets) and all((config.BASE_DIR/'remotion/public'/a.path).is_file()
                    and file_hash(config.BASE_DIR/'remotion/public'/a.path)==a.sha256 for a in assets))
                check('narration_and_captions',bool(timeline.words) and bool(timeline.audio))
                check('caption_timing',bool(timeline.words)) # Full alignment is validated by Timeline.
                check('ending_not_truncated',duration>=timeline.durationInFrames/timeline.fps-.1)
                last_frame=timeline.words[-1].start*timeline.fps if timeline.words else 0
                ending=[l for l in timeline.layers if l.assetId and l.startFrame<=last_frame<l.endFrame]
                check('ending_has_visual',bool(ending))
                check('story_scene_review',all(story.get('scene_review',{}).get(k) for k in ('passed','complete_arc','visual_ending')))
        else:
            props_path=video.parent/'remotion_props.json'
            props=json.loads(props_path.read_text()) if props_path.exists() else {}
            check('embedded_hook',props.get('autopilot_hook')==story['script']['hook_text'])
            branding=props.get('branding',{})
            check('floating_watermark',branding.get('enabled',True) and branding.get('protectiveOverlayEnabled',True)
                  and branding.get('protectiveOverlayOccurrences',2)>0 and branding.get('watermarkText')=='@project.HER')
            screens=props.get('screens',[])
            check('scene_images',bool(screens) and all(s.get('image_paths') and all(s['image_paths']) for s in screens if not s.get('is_outro')))
            check('source_assets',bool(props.get('autopilot_asset_audit',{}).get('passed')))
            narration=[s for s in screens if s.get('audio_duration',0)>0]
            check('narration_and_captions',bool(narration) and all(s.get('audio_path') and s.get('word_timings') for s in narration))
            timing_ok=True
            for screen in narration:
                last=0
                for word in screen['word_timings']:
                    start,end=word.get('start',-1),word.get('end',-1)
                    if not 0<=start<=end<=max(screen['duration'],screen['audio_duration'])+.15 or start<last-.05:timing_ok=False
                    last=end
            check('caption_timing',timing_ok)
            planned=sum(max(s.get('duration',0),s.get('audio_duration',0),max([w['end'] for w in s.get('word_timings',[])]+[0])) for s in screens)
            check('ending_not_truncated',duration>=planned-.1)
            check('ending_has_visual',bool(narration) and bool(narration[-1].get('image_paths')))
        # Decode the entire file and inspect signal rather than trusting metadata.
        scan=command(['ffmpeg','-hide_banner','-nostats','-i',str(video),'-af','volumedetect,silencedetect=noise=-40dB:d=2',
            '-vf','blackdetect=d=0.4:pix_th=0.02','-f','null','-']).stderr
        volume=re.search(r'mean_volume:\s*(-?[\d.]+) dB',scan)
        check('audible_audio',bool(volume) and float(volume[1])>-38)
        from agent.branding import outro_frames
        intentional_outro=outro_frames(30,branding)/30
        silences=[max(0,float(length)-(intentional_outro if float(end)>=duration-.15 else 0))
                  for end,length in re.findall(r'silence_end:\s*([\d.]+)\s*\|\s*silence_duration:\s*([\d.]+)',scan)]
        check('no_long_silence',all(x<=2 for x in silences) and sum(silences)<=duration*.12)
        check('no_black_intervals','black_start:' not in scan)
        report={'passed':all(c['result']=='PASS' for c in checks),'checks':checks,'duration':duration,
                'story_id':story['story_id'],'sha256':file_hash(video)}
        video.with_name('quality-report.json').write_text(json.dumps(report,indent=2))
        return report
