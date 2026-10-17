"""Import measured transcription and actual frame identities for local regression.

Fixture-specific names, crops and spelling corrections are data, never planner
branches. No speech generation, image generation or external transfer occurs.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
from agent.news_models import Script, Sentence, Entity
from agent.editorial.models import Word, Section
from agent.editorial.audio import normalize
from agent.cutout_processor import CutoutProcessor


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--media',type=Path,required=True)
    parser.add_argument('--transcription',type=Path,required=True);parser.add_argument('--fixture',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
    fixture=json.loads(args.fixture.read_text());rows=json.loads(args.transcription.read_text())
    entities=[Entity.model_validate({k:v for k,v in row.items() if k not in ('aliases','frame_time','crop','opaque_matte_recovery')}) for row in fixture['entities']]
    all_words=[w for row in rows for w in row['words']];words=[];sections=[];sentences=[];pending=[]
    corrections=fixture.get('transcription_corrections',{})
    for i,w in enumerate(all_words):
        token=corrections.get(w['text'],w['text']);pending.append((w,token))
        if not re.search(r'[.!?]$',token) and i<len(all_words)-1:continue
        sid=f's{len(sentences)+1}';line=' '.join(token for _,token in pending)
        ids=[e.id for e,row in zip(entities,fixture['entities']) if any(re.search(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',line,re.I) for alias in [e.name,*row.get('aliases',[])])]
        if not ids and sentences:ids=sentences[-1].entity_ids[:1]
        sentences.append(Sentence(id=sid,text=line,phrase=line,claim_ids=['recorded-audio'],entity_ids=ids[:3],role='hook' if not sentences else 'development'))
        sw=[]
        for j,(value,text) in enumerate(pending):
            if value['end']<=value['start']:raise ValueError('Zero-duration transcription token; realignment required')
            word=Word(id=f'{sid}-w{j}',sectionId=sid,text=text,start=value['start'],end=value['end'],confidence=value['probability'],provenance='whisper_transcribed')
            words.append(word);sw.append(word.id)
        sections.append(Section(id=sid,text=line,start=pending[0][0]['start'],end=pending[-1][0]['end'],wordIds=sw,sourceIds=['recorded-audio']))
        pending=[]
    script=Script(summary=fixture['summary'],narration=' '.join(s.text for s in sentences),sentences=sentences,entities=entities)
    source=out/'recorded-audio.wav';master=out/'master.wav'
    duration=words[-1].end+.25
    if fixture.get('preserve_branded_duration'):
        from agent.branding import outro_frames
        media_duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(args.media)]))
        duration=max(duration,media_duration-outro_frames(30)/30)
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(args.media),'-t',str(duration),'-vn','-ar','48000','-ac','2',str(source)],check=True)
    normalize(source,master);registry={}
    data={'script':script.model_dump(),'words':[w.model_dump() for w in words],'sections':[s.model_dump() for s in sections],
          'master':str(master.resolve()),'registry':{},'preparation_status':'pending',
          'timing_note':'Measured Whisper transcription, manually corrected proper-name spellings; acoustic onset review pending.'}
    # Keep script/timing evidence even when a low-contrast source crop fails
    # the normal matte gate. Do not substitute a degraded opaque rectangle.
    (out/'transcript_inputs.json').write_text(json.dumps(data,indent=2))
    for entity,row in zip(entities,fixture['entities']):
        frame=out/(entity.id+'-frame.png');cut=out/(entity.id+'-master.png')
        subprocess.run(['ffmpeg','-v','error','-y','-ss',str(row['frame_time']),'-i',str(args.media),'-frames:v','1',str(frame)],check=True)
        with Image.open(frame) as image:image.crop(tuple(row['crop'])).save(frame)
        processor=CutoutProcessor()
        if row.get('opaque_matte_recovery'):
            # Explicitly audited fixture material only: this opaque ribbon has
            # no enclosed transparent holes. Keep source RGB, not premultiplied
            # black pixels from the failed model mask. Production stays strict.
            import numpy as np
            from scipy.ndimage import binary_fill_holes,label
            original_processor=processor
            def segment(source,model):
                result=original_processor.segment(source,model)
                mask=binary_fill_holes(np.asarray(result.getchannel('A'))>12)
                components,_=label(mask);counts=np.bincount(components.ravel());counts[0]=0
                mask=components==int(counts.argmax())
                recovered=source.convert('RGBA').copy()
                recovered.putalpha(Image.fromarray((mask*255).astype('uint8')))
                return recovered
            processor=CutoutProcessor(segmenter=segment)
        processor.process(frame,cut,allow_portrait_crop=entity.is_portrait,allow_bottom_crop=True)
        registry[entity.name]={'path':str(cut.resolve()),'subject':entity.name,'source':'User supplied ProjectHER regression frame '+str(row['frame_time']),
            'license':'User supplied regression media','attribution':'ProjectHER source render','factual':False,'role':'portrait' if entity.kind=='person' else 'object'}
    data.update(registry=registry,preparation_status='ready')
    (out/'inputs.json').write_text(json.dumps(data,indent=2));print(out/'inputs.json',flush=True)

if __name__=='__main__':main()
