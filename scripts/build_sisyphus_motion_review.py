"""Real rendered cutout sample with measured narration; no speech API required.

Selects five complete narrated moments from the existing Sisyphus recording.
All retained words preserve their measured source offsets. Fresh action images
must be supplied in --assets; neither fake timestamps nor tone-pulse speech.
"""
import argparse
import json
import math
import shutil
import sys
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent.editorial.audio import samples,write_wave,normalize
from agent.editorial.models import Asset,Entity,Word,Section,digest
from agent.editorial.visuals import EditorialScript
from agent.news_models import Sentence,Entity as ScriptEntity
from agent.editorial.scene_plan import BeatInput,plan_story
from agent.editorial.sentence_storyboard import direction
from agent.editorial.planner import build
from agent.editorial.director import VisualSettings,save_summary
from agent.editorial.render import render
from review_editorial_motion import export


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--baseline',type=Path,default=Path('output/narrative_audit/before_sisyphus/editorial_manifest.json'));ap.add_argument('--assets',type=Path,required=True);ap.add_argument('--output',type=Path,default=Path('output/editorial_motion_review/sisyphus-proof'));args=ap.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);assetdir=out/'assets';assetdir.mkdir(exist_ok=True)
    old=json.loads(args.baseline.read_text());data=samples(old['audio'][0]['path']);rate=48000
    # source section, first word index, end-exclusive index, cutout, semantic type
    specs=[('s2',0,None,'intro','CHARACTER_INTRO'),('s4',9,None,'binding','ACTION'),('s6',4,None,'escape','ACTION'),('s8',0,None,'judgment','EVENT'),('s9',0,11,'boulder','ACTION')]
    words=[];sections=[];parts=[];assets=[];entities=[];sentences=[];storyboard=[];offset=0;inputs=[];details=[]
    for i,(source,first,last,name,kind) in enumerate(specs):
        sw=[w for w in old['words'] if w['sectionId']==source][first:last]
        # Keep the full final word and a short natural pause. The old waveform
        # is spliced at exact sample boundaries; timestamps shift by that offset.
        begin=max(0,round((sw[0]['start']-.025)*rate));finish=min(len(data),round((sw[-1]['end']+.08)*rate))
        sid=f's{i}';eid=f'scene-{name}';aid=f'asset-{name}';ids=[]
        for j,w in enumerate(sw):
            wid=f'{sid}-w{j}';ids.append(wid);words.append(Word(**{**w,'id':wid,'sectionId':sid,'start':w['start']-begin/rate+offset/rate,'end':w['end']-begin/rate+offset/rate}))
        parts.append(data[begin:finish]);text=' '.join(w['text'] for w in sw)
        sections.append(Section(id=sid,text=text,start=words[-len(sw)].start,end=words[-1].end,wordIds=ids))
        image=assetdir/f'{name}.png'
        original=Path(next(a['path'] for a in old['assets'] if a['entityId']=='sisyphus')) if name=='intro' else args.assets/f'{name}.png'
        shutil.copyfile(original,image)
        with Image.open(image) as im:w,h=im.size;alpha=im.mode=='RGBA' and im.getchannel('A').getextrema()[0]<255
        if not alpha:raise ValueError('Review sample requires a transparent cutout: '+str(image))
        action={'intro':'Sisyphus introduction','binding':'Sisyphus binding Thanatos in chains','escape':'Sisyphus returning through the underworld threshold','judgment':'Zeus judging kneeling Sisyphus','boulder':'Sisyphus pushing a huge boulder uphill'}[name]
        assets.append(Asset(id=aid,entityId=eid,path=str(image),originalPath=str(original.resolve()),role='object',subject=action,source='ProjectHER recorded baseline' if name=='intro' else 'Built-in imagegen; authored validation asset',license='Generated illustration',attribution='ProjectHER validation illustration',width=w,height=h,alpha=True,factual=False,confidence=.9,preparation='trimmed_alpha',fallback='Illustrative mythology cutout; human reviewed, not documentary evidence',sha256=digest(image)))
        entities.append(Entity(id=eid,name=name,identity='fictional',assetIds=[aid],source='Illustration'))
        sentences.append(Sentence(id=sid,text=text,entity_ids=[eid],claim_ids=['myth'],phrase=' '.join(text.split()[:4]),role='development'))
        inputs.append(BeatInput(text=text,index=i,total=len(specs),actors=['Sisyphus'],hint=kind))
        storyboard.append(dict(sentence_id=sid,primary_entity_id=eid,secondary_entity_ids=[],main_action=action,visual_focus=action,identity_reference_ids=['Sisyphus'],onset_anchor=sw[0]['text']))
        details.append(dict(sourceSection=source,sourceWordIds=[w['id'] for w in sw],sourceSampleStart=begin,sourceSampleEnd=finish,outputSampleStart=offset,action=action))
        offset+=finish-begin
    for row,plan in zip(storyboard,plan_story(inputs)):row['scene_plan']=plan.as_dict()
    script=EditorialScript(narration=' '.join(s.text for s in sentences),summary='Sisyphus: actions in editorial cutouts',sentences=[s.model_dump() for s in sentences],entities=[ScriptEntity(id=e.id,name=e.name,identity='fictional',kind='object',description=assets[i].subject) for i,e in enumerate(entities)],sentence_storyboard=storyboard)
    write_wave(out/'narration-source.wav',np.concatenate(parts));normalize(out/'narration-source.wav',out/'master.wav')
    settings=VisualSettings(editorialStyleVersion='reference-v2')
    m=build(script,words,sections,entities,assets,out/'master.wav',out,out.name,{'sampleProvenance':details},direction=direction(script),visual_settings=settings)
    save_summary(m,out);(out/'planned_script.json').write_text(script.model_dump_json(indent=2));(out/'narration-provenance.json').write_text(json.dumps(details,indent=2))
    video,stats=render(m,out/'editorial.mp4');(out/'metrics.json').write_text(json.dumps(stats,indent=2));(out/'editorial_manifest.json').write_text(m.model_dump_json(indent=2))
    print(export(out/'editorial_manifest.json',video,out/'review'))

if __name__=='__main__':main()
