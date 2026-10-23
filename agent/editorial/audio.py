"""Known-script forced alignment, conservative edge trims, sample-accurate assembly.

Whisper's cross-attention DTW aligns supplied tokens; it never distributes time by
word/character length. Low probabilities are retained as warnings, not hidden.
"""
from __future__ import annotations
import hashlib
import json
import math
import os
import re
import subprocess
import wave
from pathlib import Path
import numpy as np
from agent.news_models import NewsError
from .models import Word, Section, Audio, digest


def run(args):
    return subprocess.run(args,capture_output=True,text=True,check=True,timeout=180)


def samples(path, rate=48000):
    p=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-f','f32le','-ac','1','-ar',str(rate),'-'],capture_output=True,check=True,timeout=60)
    return np.frombuffer(p.stdout,dtype='<f4').copy()


def write_wave(path, data, rate=48000):
    with wave.open(str(path),'wb') as f:
        f.setnchannels(2); f.setsampwidth(2); f.setframerate(rate)
        stereo=np.repeat(np.clip(data,-1,1)[:,None],2,axis=1)
        f.writeframes((stereo*32767).astype('<i2').tobytes())


def measure(path,*,true_peak=-1.5):
    result=run(['ffmpeg','-hide_banner','-i',str(path),'-af',f'loudnorm=I=-15:TP={true_peak}:LRA=7:print_format=json','-f','null','-'])
    stats=json.loads(re.findall(r'\{[^{}]+\}',result.stderr)[-1])
    silence=run(['ffmpeg','-hide_banner','-i',str(path),'-af','silencedetect=noise=-40dB:d=0.15','-f','null','-']).stderr
    starts=[float(x) for x in re.findall(r'silence_start: ([\d.]+)',silence)]
    ends=[float(x) for x in re.findall(r'silence_end: ([\d.]+)',silence)]
    finite=lambda value:float(value) if math.isfinite(float(value)) else None
    return {'integratedLUFS':finite(stats['input_i']),'truePeakDBTP':finite(stats['input_tp']),
        'loudnessRangeLU':float(stats['input_lra']), 'silences':[{'start':s,'end':e,'duration':e-s} for s,e in zip(starts,ends)],'loudnorm':stats}


def normalize(source,target,*,true_peak=-1.5):
    before=measure(source,true_peak=true_peak); s=before['loudnorm']
    if before['integratedLUFS'] is None: raise NewsError('Silent narration cannot be normalized.')
    filt=f"loudnorm=I=-15:TP={true_peak}:LRA=7:measured_I={s['input_i']}:measured_TP={s['input_tp']}:measured_LRA={s['input_lra']}:measured_thresh={s['input_thresh']}:offset={s['target_offset']}:linear=true:print_format=json"
    run(['ffmpeg','-v','error','-y','-i',str(source),'-af',filt,'-ar','48000','-ac','2','-c:a','pcm_s24le',str(target)])
    return {'before':before,'after':measure(target)}


class Aligner:
    def __init__(self,language='en'):
        try:
            from faster_whisper import WhisperModel
            from faster_whisper.tokenizer import Tokenizer
        except ImportError:
            raise NewsError('reference_editorial needs true word timing. Install requirements-editorial.txt for local forced alignment or use validated Edge/ElevenLabs timestamps.') from None
        import config
        model=os.getenv('HER_ALIGNMENT_MODEL','small')
        try:
            self.model=WhisperModel(model,device='cpu',compute_type='int8',cpu_threads=max(1,min(8,int(os.getenv("HER_INFERENCE_THREADS","2")))),
                download_root=str(config.ASSETS_DIR/'alignment'),local_files_only=os.getenv('HER_ALIGNMENT_DOWNLOAD','0')!='1')
        except Exception as exc:
            raise NewsError('Local alignment model is unavailable. Install requirements-editorial.txt and download the model with scripts/setup_editorial.py, or use validated Edge/ElevenLabs timestamps. '+type(exc).__name__) from None
        self.tokenizer=Tokenizer(self.model.hf_tokenizer,self.model.model.is_multilingual,task='transcribe',language=language)

    def align(self,data,text):
        # data is a mono 16 kHz sentence/group. Provider clips longer than 29s
        # require sentence splitting upstream, never truncation here.
        from faster_whisper.audio import pad_or_trim
        if len(data)>29*16000: raise NewsError('Alignment group exceeds 29s; split the script sentence before synthesizing.')
        features=self.model.feature_extractor(data)
        encoded=self.model.encode(pad_or_trim(features))
        # Whisper's speech text tokens conventionally begin with a space. Keep
        # that tokenizer context, while retaining original display spelling.
        for width in (7,3,11):
            rows=self.model.find_alignment(self.tokenizer,[self.tokenizer.encode(' '+text.lstrip())],encoded,len(data)//160,median_filter_width=width)[0]
            try:return alignment_words(rows,text)
            except NewsError as exc:
                if not str(exc).startswith('Zero-duration aligned word:'):raise
                if width==11:return self.transcribed_alignment(data,text)
                # Recompute measured cross-attention/DTW with a different
                # smoothing width. Never spread time evenly or invent onsets.
                continue


    def transcribed_alignment(self,data,text):
        # Spoken punctuation need not match the script's punctuation. Require
        # every recognized lexical word in order, then restore display spelling.
        segments,_=self.model.transcribe(data,language=self.tokenizer.language_code,beam_size=5,word_timestamps=True,vad_filter=False)
        measured=[word for segment in segments for word in (segment.words or [])]
        original=text.split()
        canonical=lambda token:token.strip().casefold().replace('’',"'").strip('.,:;!?…“”"()')
        if len(measured)!=len(original) or any(not canonical(token) or canonical(word.word)!=canonical(token) for word,token in zip(measured,original)):
            raise NewsError('Zero-duration alignment could not be recovered: recognized speech does not exactly match the script.')
        result=[];previous=0;duration=len(data)/16000
        for word,token in zip(measured,original):
            start=float(word.start);end=float(word.end);probability=float(word.probability)
            if not (math.isfinite(start) and math.isfinite(end) and previous-.001<=start<end<=duration+.001 and .35<=probability<=1):
                raise NewsError('Zero-duration alignment could not be recovered with reliable measured word timing.')
            signal=data[max(0,int(start*16000)):min(len(data),math.ceil(end*16000))]
            if not len(signal) or float(np.sqrt(np.mean(signal**2)))<1e-5:
                raise NewsError('Zero-duration alignment recovery found a word without audible speech.')
            result.append(dict(text=token,start=start,end=end,confidence=probability,provenance='whisper_transcribed'))
            previous=end
        return result


def alignment_words(rows,text):
    # Merge subword punctuation/contractions by exact original whitespace tokens.
    # No normalized display text is substituted into the plan.
    compact=lambda v: re.sub(r'\s+','',v)
    expected=text.split(); result=[]; index=0
    for original in expected:
        parts=[]; joined=''
        while index<len(rows) and len(compact(joined))<len(compact(original)):
            part=rows[index];parts.append(part);joined+=part['word'];index+=1
        if compact(joined)!=compact(original) or not parts:
            raise NewsError('Forced alignment token mismatch; revise the script or use native provider timing.')
        voiced=[p for p in parts if p['end']>p['start']]
        if not voiced: raise NewsError('Zero-duration aligned word: '+original)
        result.append(dict(text=original,start=float(voiced[0]['start']),end=float(voiced[-1]['end']),
            confidence=float(min(p['probability'] for p in voiced)),provenance='whisper_forced'))
    if index!=len(rows): raise NewsError('Unconsumed alignment tokens')
    return result


def remap_words(rows,trim_start,offset,section_id):
    return [Word(id=f'{section_id}-w{i}',sectionId=section_id,text=w['text'],
        start=w['start']-trim_start+offset,end=w['end']-trim_start+offset,
        confidence=w['confidence'],provenance=w['provenance']) for i,w in enumerate(rows)]


def refine_silence_edges(rows,data,rate=48000):
    """DTW sometimes gives first words the leading silence. Snap only silent
    parts of a word to observed signal, with 10ms handles. Internal speech and
    breathing are retained; this isn't an equal-word timing approximation.
    """
    rows=[dict(r) for r in rows];bin_size=round(rate*.005)
    n=len(data)//bin_size
    rms=np.sqrt(np.mean(data[:n*bin_size].reshape(-1,bin_size)**2,axis=1))
    threshold=min(10**(-50/20),float(rms.max())*.008)
    for row in rows:
        a=max(0,int(row['start']/.005));b=min(n,math.ceil(row['end']/.005))
        active=np.flatnonzero(rms[a:b]>threshold)
        if len(active):
            first=(a+active[0])*.005;last=(a+active[-1]+1)*.005
            if first-row['start']>.04:row['start']=max(row['start'],first-.01)
            if row['end']-last>.06:row['end']=min(row['end'],last+.02)
    return rows


def assemble(script,clips,output,language='en',native=None,gap=.12):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    aligner=None; words=[]; sections=[]; buffers=[]; offsets=[]; warnings=[]; cursor=0; rate=48000
    for i,(section,clip) in enumerate(zip(script.sentences,clips)):
        data=samples(clip)
        key=hashlib.sha256((digest(clip)+section.text+'alignment-v5-'+os.getenv('HER_ALIGNMENT_MODEL','small')+'-faster-whisper-1.2.1-'+language).encode()).hexdigest()
        cache=output/(key+'.alignment.json')
        rows=native.get(section.id) if native else None
        if rows is None and cache.is_file():
            try:rows=json.loads(cache.read_text())
            except (ValueError,OSError):rows=None
        if rows is not None:
            try:
                previous=0
                if len(rows)!=len(section.text.split()):raise ValueError('word count')
                for row,token in zip(rows,section.text.split()):
                    start=float(row['start']);end=float(row['end'])
                    if row['text']!=token or not (math.isfinite(start) and math.isfinite(end) and previous-.001<=start<end<=len(data)/rate+.001):raise ValueError('word bounds')
                    previous=end
            except (ValueError,TypeError,KeyError):
                rows=None;warnings.append(section.id+': rejected invalid provider/cache word timing; requested fresh forced alignment.')
        if rows is None:
            try:
                aligner=aligner or Aligner(language)
                rows=aligner.align(samples(clip,16000),section.text)
                cache.write_text(json.dumps(rows,indent=2))
            except NewsError as exc:
                from .director import VisualSettings
                if not VisualSettings.configured().allowPhraseTimingFallback:raise
                tokens=section.text.split();duration=len(data)/rate
                rows=[dict(text=t,start=j*duration/len(tokens),end=(j+1)*duration/len(tokens),confidence=0,provenance='estimated_phrase') for j,t in enumerate(tokens)]
                warnings.append(section.id+': ESTIMATED phrase timing; word onsets are not measured and synchronization tolerance is not guaranteed. '+str(exc))
        if rows and rows[0]['provenance'] in ('whisper_forced','whisper_transcribed'):rows=refine_silence_edges(rows,data)
        if not rows: raise NewsError('Missing aligned words')
        # Inspect 10ms RMS bins only at the two clip edges. Preserve all internal
        # pauses. Keep 60ms handles around either signal OR alignment, whichever
        # is wider; no fixed-duration cutting into provider output.
        bins=len(data)//480
        rms=np.sqrt(np.mean(data[:bins*480].reshape(-1,480)**2,axis=1))
        active=np.flatnonzero(rms>10**(-45/20))
        if not len(active): raise NewsError('Narration clip has no audible signal')
        first=min(active[0]*.01,rows[0]['start'])
        last=max((active[-1]+1)*.01,rows[-1]['end'])
        left=max(0,int((first-.06)*rate));right=min(len(data),math.ceil((last+.06)*rate))
        trimmed=data[left:right]; offset=cursor/rate
        mapped=remap_words(rows,left/rate,offset,section.id)
        words.extend(mapped)
        sections.append(Section(id=section.id,text=section.text,start=offset,end=offset+len(trimmed)/rate,
            wordIds=[w.id for w in mapped],sourceIds=section.claim_ids))
        offsets.append({'sectionId':section.id,'source':str(clip),'sourceDuration':len(data)/rate,'trimStart':left/rate,
            'trimEnd':(len(data)-right)/rate,'offset':offset,'sampleOffset':cursor,'retainedDuration':len(trimmed)/rate})
        if any(w.confidence<.5 for w in mapped): warnings.append(section.id+': low-confidence words retained; inspect alignment.json')
        buffers.append(trimmed);cursor+=len(trimmed)
        if i+1<len(clips):
            silence=np.zeros(round(gap*rate),dtype=np.float32);buffers.append(silence);cursor+=len(silence)
    if len(sections)!=len(script.sentences): raise NewsError('Missing narration clips')
    raw=output/'assembled.wav';write_wave(raw,np.concatenate(buffers))
    aligned=output/'alignment.json'; aligned.write_text(json.dumps({'words':[w.model_dump() for w in words],'offsets':offsets,'warnings':warnings},indent=2))
    return raw,words,sections,{'offsets':offsets,'alignmentWarnings':warnings,'sampleRate':rate,
        'confidenceMeaning':'Provider words: provider validated against script; forced/transcribed words: Whisper token probability, not calibrated temporal accuracy; transcription recovery requires an exact lexical script match and audible word intervals. Edge refinements use the waveform.',
        'alignmentVersion':'known-script-dtw-v5-exact-transcript-recovery'}


def prepare_existing(script,audio,output,language='en'):
    """Explicit v1 adapter: use its actual sentence boundaries, re-align audio.

    Never converts missing v1 word timings into fictional timestamps.
    """
    root=Path(output);root.mkdir(parents=True,exist_ok=True);clips=[];native={}
    for i,section in enumerate(script.sentences):
        phrase=next(p for p in audio.phrases if p.sentence_id==section.id)
        path=root/f'section-{i}.wav'
        run(['ffmpeg','-v','error','-y','-i',audio.path,'-ss',str(phrase.start),'-t',str(phrase.end-phrase.start),'-ac','1','-ar','48000',str(path)])
        clips.append(path)
        boundaries=[w for w in audio.words if w.sentence_id==section.id]
        if boundaries and audio.method=='native_words':
            # Native token spelling must preserve the approved display script.
            original=section.text.split()
            norm=lambda x:re.sub(r'\W+','',x.casefold())
            if len(boundaries)==len(original) and all(norm(b.text)==norm(t) for b,t in zip(boundaries,original)):
                native[section.id]=[dict(text=t,start=b.start-phrase.start,end=b.end-phrase.start,confidence=1,provenance='provider') for b,t in zip(boundaries,original)]
    return assemble(script,clips,root,language,native)


def subtitles(words,path):
    def stamp(t,sep):
        ms=round(t*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000)
        return f'{h:02}:{m:02}:{s:02}{sep}{ms:03}'
    groups=[]
    for word in words:
        if not groups or groups[-1][-1].sectionId!=word.sectionId or len(groups[-1])>=6: groups.append([])
        groups[-1].append(word)
    for suffix,sep in [('srt',','),('vtt','.')]:
        body='\n\n'.join(f'{i+1}\n{stamp(g[0].start,sep)} --> {stamp(g[-1].end,sep)}\n'+ ' '.join(w.text for w in g) for i,g in enumerate(groups))
        Path(path).with_suffix('.'+suffix).write_text(('WEBVTT\n\n' if suffix=='vtt' else '')+body+'\n')
