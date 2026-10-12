"""Audio-first News timing; estimated provider word durations are never exported."""
from __future__ import annotations
import hashlib
import logging
import re
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace
from agent.news_models import Audio, Boundary, NewsError
import config

logger=logging.getLogger(__name__)


def _make_engine(provider,voice,speed,language,cancel_event):
    if provider=='google_tts':
        from agent.google_tts import GoogleTTS, VOICE_PRESETS
        return GoogleTTS(voice_name=voice if voice in VOICE_PRESETS.values() else None,mood='informative')
    if provider=='elevenlabs':
        from agent.elevenlabs_tts import ElevenLabsTTS, VOICE_PRESETS
        return ElevenLabsTTS(voice_id=voice if voice in VOICE_PRESETS.values() else None,mood='informative')
    if provider in ('replicate','chatterbox_turbo'):
        from agent.news_tts import NewsReplicateTTS,CHATTERBOX
        return NewsReplicateTTS(voice,speed,language,cancel_event,model=CHATTERBOX if provider=='chatterbox_turbo' else None)
    from agent.narration import NarrationEngine
    from agent.news_tts import LANGUAGES
    code=LANGUAGES.get(language.lower(),language.lower())
    if code not in config.LANGUAGE_VOICES:
        raise NewsError('Unknown News narration language; choose a configured language code.')
    selected=config.AVAILABLE_VOICES.get(voice,voice) if voice else None
    # Google/Kokoro voice IDs cannot be sent to Edge, nor English voices to Hindi speech.
    if not selected or not selected.lower().startswith(code.split('-')[0]+'-') or not selected.endswith('Neural'):
        selected=config.LANGUAGE_VOICES[code]['voice']
    return NarrationEngine(voice=selected,rate=speed)


def _failure_reason(exc):
    # Provider exceptions can contain authorization headers or signed delivery URLs.
    if isinstance(exc,NewsError) or str(exc).startswith('Google TTS failed'):
        return str(exc)[:400]
    return f'{type(exc).__name__}: speech generation or audio validation failed'


def probe_duration(path):
    result=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(path)],capture_output=True,text=True,check=True,timeout=20)
    duration=float(result.stdout.strip())
    if not 0<duration<1200: raise NewsError('Narration duration is invalid.')
    return duration


def valid_words(words,text,duration):
    normalize=lambda s:re.sub(r'\W+','',s.casefold())
    if not words or normalize(''.join(w.word for w in words)) != normalize(text): return False
    previous=0
    for w in words:
        if w.start<previous-.01 or w.end<=w.start or w.end>duration+.05: return False
        previous=w.end
    return True


def synthesize(script,output,provider,voice=None,speed='+0%',engine=None,pause=.16,language='en',cancel_event=None,diagnostic_sink=None):
    """Retry a complete narration with bounded providers, including partial/invalid audio failures."""
    from agent.news_tts import cancelled
    if provider not in ('google_tts','elevenlabs','replicate','chatterbox_turbo','edge_tts'):
        raise NewsError('Unknown News speech provider.')
    providers=[provider]
    if provider in ('google_tts','elevenlabs'): providers.append('replicate')
    if provider!='edge_tts': providers.append('edge_tts')
    failures=[]; root=Path(output); root.mkdir(parents=True,exist_ok=True)
    # Unique attempt folders prevent an earlier job's files from masking a provider failure.
    attempt_root=root/'narration_attempts'/uuid.uuid4().hex
    for candidate in providers:
        cancelled(cancel_event)
        attempt=attempt_root/candidate; attempt.mkdir(parents=True,exist_ok=True)
        current=None
        try:
            current=engine if candidate==provider and engine is not None else _make_engine(candidate,voice,speed,language,cancel_event)
            logger.info('News narration | provider=%s | model=%s | sentences=%d',candidate,getattr(current,'model','default'),len(script.sentences))
            audio=_synthesize_once(script,attempt,candidate,current,pause,cancel_event)
            cancelled(cancel_event)
            final=root/'news_narration.wav'; Path(audio.path).replace(final)
            result=audio.model_copy(update={'path':str(final.resolve()),'provider':candidate,
                'model':getattr(current,'model',None),'fallbacks':failures[:]})
            if diagnostic_sink is not None:
                diagnostic_sink.update(requestedProvider=provider,resolvedProvider=candidate,requestedVoice=voice,
                    resolvedVoice=getattr(current,'voice_name',getattr(current,'voice_id',getattr(current,'voice',None))),
                    requestedSpeed=speed,resolvedSpeed=getattr(current,'rate',getattr(current,'speed',None)))
            logger.info('News narration complete | provider=%s | duration=%.2fs | alignment=%s | fallbacks=%d',candidate,result.duration,result.method,len(failures))
            return result
        except Exception as exc:
            cancelled(cancel_event)
            if isinstance(exc,NewsError) and exc.status=='cancelled': raise
            reason=_failure_reason(exc); failures.append(f'{candidate}: {reason}')
            next_provider=providers[providers.index(candidate)+1:][:1]
            logger.warning('News narration | provider=%s | failed=%s | next=%s',candidate,reason,next_provider[0] if next_provider else 'none')
        finally:
            session=getattr(current,'_session',None)
            if session is not None: session.close()
    raise NewsError('All News narration providers failed. '+'; '.join(failures))


def _synthesize_once(script,output,provider,engine,pause,cancel_event):
    from agent.news_tts import cancelled
    points=[SimpleNamespace(index=i,narration=s.text,text=s.text,headline=s.phrase,emotion='neutral',speaker='',character_name='') for i,s in enumerate(script.sentences)]
    clips=engine.generate_narration(points,Path(output))
    cancelled(cancel_event)
    clips_by_id={getattr(c,'key_point_index',getattr(c,'index',-1)):c for c in clips}
    if len(clips_by_id)!=len(clips) or set(clips_by_id)!=set(range(len(points))):
        raise NewsError('Speech provider did not return exactly one clip per News sentence.')
    from moviepy import AudioFileClip, AudioClip, concatenate_audioclips
    import numpy as np
    opened=[]; combined=None; boundaries=[]; words=[]; cursor=0; methods=[]
    audio_path=Path(output)/'news_narration.wav'
    try:
        for i,s in enumerate(script.sentences):
            cancelled(cancel_event)
            c=clips_by_id.get(i)
            if c is None or not Path(c.audio_path).is_file(): raise NewsError(f'Missing narration clip for {s.id}')
            duration=probe_duration(c.audio_path)
            clip=AudioFileClip(str(c.audio_path)); clip.duration=duration; clip.end=duration; opened.append(clip)
            boundaries.append(Boundary(sentence_id=s.id,text=s.text,start=cursor,end=cursor+duration))
            reliable=provider in ('edge_tts','elevenlabs') and valid_words(getattr(c,'word_timings',[]),s.text,duration)
            methods.append('native_words' if reliable else 'sentence_clips')
            if reliable:
                words.extend(Boundary(sentence_id=s.id,text=w.word,start=cursor+w.start,end=cursor+w.end) for w in c.word_timings)
            cursor+=duration
            if i+1<len(script.sentences) and pause:
                silence=AudioClip(lambda t:np.zeros((len(t),2)) if isinstance(t,np.ndarray) else np.zeros(2),duration=pause,fps=44100)
                opened.append(silence); cursor+=pause
        combined=concatenate_audioclips(opened)
        combined.write_audiofile(str(audio_path),fps=44100,codec='pcm_s16le',logger=None)
    finally:
        if combined: combined.close()
        for clip in opened:
            proc=getattr(getattr(clip,'reader',None),'proc',None)
            clip.close()
            if proc:
                for stream in (proc.stdout,proc.stderr):
                    if stream and not stream.closed: stream.close()
    duration=probe_duration(audio_path)
    method=methods[0] if len(set(methods))==1 else 'mixed'
    return Audio(path=str(audio_path.resolve()),duration=duration,method=method,
        quality='Native validated word boundaries' if method=='native_words' else 'Actual per-sentence synthesized audio clips; phrase reveals only where native words are unavailable. No estimated word alignment.',
        script_hash=hashlib.sha256(script.narration.encode()).hexdigest(),phrases=boundaries,words=words)


def write_srt(audio,path):
    def stamp(t):
        ms=round(t*1000); h,ms=divmod(ms,3600000); m,ms=divmod(ms,60000); s,ms=divmod(ms,1000)
        return f'{h:02}:{m:02}:{s:02},{ms:03}'
    Path(path).write_text('\n\n'.join(f'{i+1}\n{stamp(p.start)} --> {stamp(p.end)}\n{p.text}' for i,p in enumerate(audio.phrases)),encoding='utf-8')


def mix_music(audio,output,music_path=None):
    """Reuse the procedural music engine, then duck it under the unchanged narration."""
    if music_path is None:
        from agent.audio_engine import AudioEngine
        music_path=AudioEngine().generate_background_music(audio.duration,mood='calm',output_dir=Path(output)/'music')
    if not Path(music_path).is_file(): raise NewsError('Selected News music file is missing.')
    mixed=Path(output)/'news_mix.wav'
    fade_start=max(0,audio.duration-.7)
    graph=f'[1:a]volume=0.4,afade=t=in:d=0.5,afade=t=out:st={fade_start}:d=0.7[m];[m][0:a]sidechaincompress=threshold=0.02:ratio=6:attack=10:release=250[d];[0:a][d]amix=inputs=2:normalize=0[out]'
    subprocess.run(['ffmpeg','-v','error','-y','-i',audio.path,'-stream_loop','-1','-i',str(music_path),'-filter_complex',graph,'-map','[out]','-t',str(audio.duration),'-ar','44100','-ac','2','-c:a','pcm_s16le',str(mixed)],capture_output=True,check=True,timeout=90)
    if abs(probe_duration(mixed)-audio.duration)>.02: raise NewsError('Music mix changed narration duration.')
    return audio.model_copy(update={'path':str(mixed.resolve())})
