"""Pillow/MoviePy News adapter consuming the same manifest as Remotion."""
from __future__ import annotations
import math
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from agent.cutout_processor import portrait_fade, mask_statistics
from agent.news_models import Manifest, NewsError


def motion(manifest,beat,layer,frame,previous=None,next_beat=None):
    n=manifest.theme.transition_frames
    entering=1 if layer.persist else min(1,max(0,(frame-layer.reveal)/n))
    keeping=bool(next_beat and any(l.id==layer.id for l in next_beat.layers))
    leaving=1 if keeping else min(1,max(0,(beat.end-frame)/n))
    opacity=entering*leaving*layer.opacity
    settle=1-(1-entering)**3
    rect=layer.rect.model_dump()
    if layer.persist and previous:
        old=next((l for l in previous.layers if l.id==layer.id),None)
        if old:
            t=min(1,max(0,(frame-beat.start)/n)); t=1-(1-t)**3
            rect={k:getattr(old.rect,k)+(v-getattr(old.rect,k))*t for k,v in rect.items()}
    scale=1+.025*math.sin(min(1,max(0,(frame-layer.reveal)/18))*math.pi)
    return rect,opacity,(1-settle)*.008,scale


class NewsFrames:
    def __init__(self,manifest):
        self.m=Manifest.model_validate(manifest.model_dump() if isinstance(manifest,Manifest) else manifest)
        self.width,self.height=self.m.width,self.m.height
        self.assets={a.id:a for a in self.m.assets}
        entities={e.id:e for e in self.m.script.entities}
        self.images={}
        for a in self.m.assets:
            if not Path(a.path).is_file(): raise NewsError('Missing News cutout: '+a.id)
            im=Image.open(a.path).convert('RGBA'); mask_statistics(im,allow_geometry=a.provider=='verified_local',allow_group=entities[a.entity_id].is_group); self.images[a.id]=im
        self.fonts={}
        for weight,path in ((600,self.m.theme.font_semibold),(700,self.m.theme.font_bold)):
            if not Path(path).is_file(): raise NewsError('Missing bundled News font')
            self.fonts[weight]=path
        # Static deterministic paper: no moving grain, saturated gradient or full-canvas zoom.
        yy,xx=np.mgrid[0:self.height,0:self.width]
        radius=np.clip(((xx/self.width-.5)**2+(yy/self.height-.48)**2)/.5,0,1)
        center=np.array([250,249,246]); edge=np.array([221,218,212])
        bg=center[None,None,:]*(1-radius[:,:,None]*.45)+edge[None,None,:]*radius[:,:,None]*.45
        noise=np.random.default_rng(self.m.seed).normal(0,.3,(self.height,self.width,1))
        self.background=Image.fromarray(np.uint8(np.clip(bg+noise,0,255))).convert('RGBA')
        self.prepared={}

    def frame(self,frame,clip_foreground=True):
        m=self.m; frame=min(m.duration_frames-1,max(0,frame))
        i=next(i for i,b in enumerate(m.beats) if b.start<=frame<b.end)
        beat=m.beats[i]; previous=m.beats[i-1] if i else None; following=m.beats[i+1] if i+1<len(m.beats) else None
        fg=Image.new('RGBA',(self.width,self.height))
        for layer in sorted(beat.layers,key=lambda l:l.z):
            rect,alpha,dy,scale=motion(m,beat,layer,frame,previous,following)
            if alpha<=0: continue
            base=self.images[layer.asset_id]
            if layer.portrait_fade: base=portrait_fade(base)
            w,h=rect['w']*self.width,rect['h']*self.height
            ratio=min(w/base.width,h/base.height)*.92*scale
            size=(max(1,round(base.width*ratio)),max(1,round(base.height*ratio)))
            image=base.resize(size,Image.Resampling.LANCZOS)
            x=round((rect['x']+rect['w']/2)*self.width-size[0]/2)
            y=round((rect['y']+rect['h']/2+dy)*self.height-size[1]/2)
            shadow=Image.new('RGBA',fg.size)
            sh=Image.new('RGBA',size,(35,35,35,0)); sh.putalpha(image.getchannel('A').point(lambda a:round(a*.14*alpha)))
            shadow.alpha_composite(sh,(x+round(self.width*.004),y+round(self.width*.005)))
            shadow=shadow.filter(ImageFilter.GaussianBlur(self.width*.007))
            fg=Image.alpha_composite(fg,shadow)
            image.putalpha(image.getchannel('A').point(lambda a:round(a*alpha)))
            fg.alpha_composite(image,(x,y))
        draw=ImageDraw.Draw(fg)
        for text in beat.texts:
            size=max(1,round(text.size*self.width/1080))
            fonts={w:ImageFont.truetype(path,size) for w,path in self.fonts.items()}
            y=text.rect.y*self.height
            index=0
            emphasis={word.strip('.,:!?') for phrase in text.emphasis for word in phrase.split()}
            fade=min(1,max(0,(beat.end-frame)/m.theme.transition_frames))
            for line in text.lines:
                words=line.split()
                lengths=[fonts[700 if word.strip('.,:!?') in emphasis else text.weight].getlength(word+(' ' if j+1<len(words) else '')) for j,word in enumerate(words)]
                x=(text.rect.x+text.rect.w/2)*self.width-sum(lengths)/2
                for word,length in zip(words,lengths):
                    reveal=text.reveal_frames[index]
                    opacity=min(1,max(0,(frame-reveal)/m.theme.transition_frames))*fade
                    weight=700 if word.strip('.,:!?') in emphasis else text.weight
                    draw.text((x,y),word,font=fonts[weight],fill=(80,80,80,round(255*opacity)),anchor='la',stroke_width=0)
                    x+=length; index+=1
                y+=size*1.12
        if m.theme.branding:
            font=ImageFont.truetype(self.fonts[600],max(10,round(min(self.width,self.height)*.014)))
            draw.text((self.width*.5,self.height*.203),m.theme.branding,font=font,fill=(104,104,104,180),anchor='mt')
        # Final exact 20%/15% mask; templates keep visual content away from this boundary.
        mask=Image.new('L',fg.size,0)
        ImageDraw.Draw(mask).rectangle((round(self.width*.08),math.ceil(self.height*.2),math.floor(self.width*.92)-1,math.floor(self.height*.85)-1),fill=255)
        alpha=np.asarray(fg.getchannel('A'),dtype=np.uint16)*np.asarray(mask,dtype=np.uint16)//255
        if clip_foreground: fg.putalpha(Image.fromarray(alpha.astype('uint8')))
        return np.asarray(Image.alpha_composite(self.background,fg).convert('RGB'))


def render_moviepy(manifest,path,bitrate='5000k',cancel_event=None):
    from moviepy import VideoClip,AudioFileClip
    frames=NewsFrames(manifest)
    audio=AudioFileClip(manifest.audio.path)
    def make_frame(t):
        if cancel_event is not None and cancel_event.is_set(): raise NewsError('News generation cancelled.','cancelled')
        return frames.frame(int(t*manifest.fps))
    clip=VideoClip(make_frame,duration=manifest.duration_frames/manifest.fps).with_audio(audio)
    try:
        clip.write_videofile(str(path),fps=manifest.fps,codec='libx264',audio_codec='aac',bitrate=bitrate,threads=2,logger=None)
    finally:
        clip.close(); audio.close()
    return Path(path)
