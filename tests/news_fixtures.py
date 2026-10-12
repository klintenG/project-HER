"""Offline semantic fixtures: illustrated scientist, diamond, microscope, synthetic audio pulses."""
from __future__ import annotations
import copy
import json
import math
import wave
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from PIL import Image, ImageDraw
from agent.news_models import Input,Source,Claim,Evidence,Script,Sentence,Entity,Manifest,Theme
from agent.news_audio import synthesize
from agent.news_layout import storyboard,font_path
from agent.cutout_processor import CutoutProcessor
from agent.news_assets import generate_cutouts

ACCOUNT='Fictional account: Mira brought a diamond to a lab. Mira examined the diamond beside a microscope. The microscope stayed on the bench as the demonstration continued. The account gives no measurement or test result.'
SCRIPT=Script(summary='An illustrative laboratory demonstration',narration='According to this fictional account, Mira brought a diamond to the lab. Mira examined the diamond beside a microscope. The microscope stayed as the demonstration continued. The account gives no measurement or test result.',sentences=[
    Sentence(id='s1',text='According to this fictional account, Mira brought a diamond to the lab.',claim_ids=['c1'],entity_ids=['mira','diamond'],phrase='Mira brought a diamond',role='hook',emphasis=['Mira']),
    Sentence(id='s2',text='Mira examined the diamond beside a microscope.',claim_ids=['c2'],entity_ids=['mira','diamond','microscope'],phrase='Mira examined the diamond',role='development'),
    Sentence(id='s3',text='The microscope stayed as the demonstration continued.',claim_ids=['c3'],entity_ids=['microscope'],phrase='The demonstration continues',role='development'),
    Sentence(id='s4',text='The account gives no measurement or test result.',claim_ids=['c4'],entity_ids=[],phrase='No test result supplied',role='close')],entities=[
        Entity(id='mira',name='Mira',kind='person',description='A generic illustrated scientist with dark hair and a white laboratory coat, front view, upper body'),
        Entity(id='diamond',name='Diamond',kind='object',description='One faceted diamond, three-quarter view'),
        Entity(id='microscope',name='Microscope',kind='object',description='One laboratory microscope, side view')])

class FixtureLLM:
    def __init__(self,account=ACCOUNT,script=SCRIPT): self.account=account; self.script=script
    def __call__(self,instruction,data):
        if instruction.startswith('Classify'):
            text=data['text']; kind='supplied_account' if data['source_policy']=='supplied' or 'Fictional account' in text or 'attacked a local boy' in text else 'topic_query'
            return dict(subject='Laboratory demonstration' if kind=='supplied_account' else text,event_date='2022' if '2022' in text else None,entities=['Mira','diamond','microscope'],places=[],kind=kind,basis='fictional' if 'Fictional' in text else ('user_supplied' if kind=='supplied_account' else 'reported'),assumptions=[],clarification=None,choices=[])
        if instruction.startswith('Extract'):
            sources=data['sources']; src=sources[0]
            return dict(claims=[dict(id=f'c{i+1}',source_ids=[src['id']],text=s.text,excerpts={src['id']:src['text']}) for i,s in enumerate(self.script.sentences)],conflicts=[],unresolved=['No measurement or result provided'])
        if instruction.startswith('Write'): return self.script.model_dump()
        if instruction.startswith('Check'): return dict(supported=True,problems=[])
        raise AssertionError(instruction)


def subject_image(subject):
    # Clean antialiased transparent silhouette assets, not rectangular photo stand-ins.
    im=Image.new('RGBA',(512,640)); d=ImageDraw.Draw(im)
    if subject=='mira':
        d.ellipse((168,70,346,286),fill='#343033')
        d.ellipse((188,105,326,275),fill='#BA8E70')
        d.polygon([(170,276),(220,250),(290,250),(350,276),(400,560),(112,560)],fill='#DEE1DF')
        d.polygon([(220,259),(256,337),(291,259),(315,530),(200,530)],fill='#6C8288')
        d.polygon([(171,278),(221,259),(246,347),(220,450)],fill='#FCFBF6')
        d.polygon([(292,260),(347,282),(295,450),(269,345)],fill='#FCFBF6')
        d.ellipse((215,174,226,184),fill='#393335'); d.ellipse((284,174,295,184),fill='#393335')
        d.arc((235,206,280,230),0,160,fill='#755548',width=4)
        d.polygon([(165,280),(125,310),(89,480),(128,505),(202,348)],fill='#EAEBE8')
        d.polygon([(346,280),(382,313),(420,479),(384,505),(309,350)],fill='#EAEBE8')
        d.rounded_rectangle((293,376,331,415),radius=4,fill='#CFD6D2')
    elif subject=='diamond':
        d.polygon([(105,270),(170,185),(340,185),(405,270),(256,455)],fill='#ABB9C0')
        d.polygon([(105,270),(256,455),(191,272)],fill='#DEE5E5')
        d.polygon([(191,272),(256,455),(319,272)],fill='#FAFBF8')
        d.polygon([(319,272),(256,455),(405,270)],fill='#8B9DA8')
        d.polygon([(170,185),(191,272),(319,272),(340,185)],fill='#D6E2E7')
        d.line([(105,270),(405,270)],fill='#F9FCFB',width=5)
    else:
        d.line((280,237,326,278),fill='#8B969A',width=42)
        d.line((230,270,277,238),fill='#9DA9AC',width=24)
        d.rounded_rectangle((100,500,402,545),radius=16,fill='#686E72')
        d.polygon([(300,490),(348,490),(348,270),(304,270)],fill='#9EA8AA')
        d.arc((201,200,401,502),-85,90,fill='#737E82',width=42)
        d.polygon([(221,180),(254,161),(298,237),(263,260)],fill='#56656C')
        d.polygon([(204,151),(251,127),(276,164),(228,190)],fill='#41494F')
        d.rounded_rectangle((151,337,311,360),radius=6,fill='#4D5D64')
        d.line((230,260,196,315),fill='#9DA9AC',width=20)
        d.ellipse((297,330,345,378),fill='#C8CCCA')
        d.ellipse((312,344,331,363),fill='#6C777C')
        d.polygon([(199,510),(227,417),(250,427),(241,510)],fill='#B6BFBD')
    return im

class FixtureImages:
    provider='fixture-editorial-illustration'
    async def subject(self,prompt,path):
        subject='mira' if 'scientist' in prompt else ('microscope' if 'microscope' in prompt else 'diamond')
        subject_image(subject).save(path)
        return self.provider

class FixtureTTS:
    """Known word-boundary pulses; deliberately NOT a live TTS/speech verification."""
    def generate_narration(self,points,output):
        from agent.narration import WordTiming,NarrationClip
        path=Path(output)/'audio'; path.mkdir(parents=True,exist_ok=True)
        clips=[]
        for point in points:
            words=point.narration.split(); timings=[]; pieces=[]; cursor=0; sr=22050
            for i,word in enumerate(words):
                dur=.20+min(.15,len(word)*.012)
                t=np.arange(round(dur*sr))/sr
                env=np.minimum(1,t/.02)*np.minimum(1,(dur-t)/.03)
                tone=np.sin(2*np.pi*(220+30*(i%5))*t)*.10*env
                pieces.extend([tone,np.zeros(round(.07*sr))])
                timings.append(WordTiming(word=word,start=cursor,end=cursor+len(tone)/sr))
                cursor+=(len(tone)+round(.07*sr))/sr
            samples=np.concatenate(pieces)
            audio=path/f'{point.index}.wav'
            with wave.open(str(audio),'wb') as f:
                f.setnchannels(1);f.setsampwidth(2);f.setframerate(sr);f.writeframes((samples*32767).astype('<i2').tobytes())
            clips.append(NarrationClip(key_point_index=point.index,audio_path=audio,duration=len(samples)/sr,word_timings=timings))
        return clips


def fixture_manifest(output,width=1080,height=1920):
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    script=SCRIPT.model_copy(deep=True)
    inp=Input(original=ACCOUNT,normalized=ACCOUNT,kind='supplied_account',source_policy='supplied',subject=script.summary,basis='fictional')
    src=Source(id='input',title='Fictional supplied fixture',text=ACCOUNT,retrieved_at='2026-10-11T00:00:00Z')
    evidence=Evidence(sources=[src],claims=[Claim(id=f'c{i+1}',source_ids=['input'],text=s.text,excerpts={'input':ACCOUNT}) for i,s in enumerate(script.sentences)],verification='fictional')
    assets=generate_cutouts(script,output,'fictional',FixtureImages(),CutoutProcessor(backend='none'))
    audio=synthesize(script,output,'edge_tts',engine=FixtureTTS(),pause=.55)
    audio.quality='Deterministic synthetic word pulses with known fixture boundaries; not spoken narration or live TTS.'
    beats,events=storyboard(script,audio,assets,width,height,30)
    return Manifest(generation_id='fixture-news-'+str(width),width=width,height=height,fps=30,duration_frames=math.ceil(audio.duration*30),theme=Theme(font_semibold=str(font_path().resolve()),font_bold=str(font_path(700).resolve())),input=inp,evidence=evidence,script=script,audio=audio,assets=assets,beats=beats,events=events,warnings=['OFFLINE FIXTURE: supplied evidence, LLM, generated subjects and speech provider replaced. Audio is synthetic word pulses. No live provider success claimed.'])
