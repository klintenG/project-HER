"""Render an eight-beat visual review against the supplied Japanese narration.

This is a frame-review fixture. The baseline audio is reused, while the word
times below are approximate and must not be treated as forced alignment.
"""
from __future__ import annotations
import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from agent.editorial.director import VisualSettings
from agent.editorial.models import Asset, Audio, Entity as RenderEntity, Fonts, Section, Word, digest
from agent.editorial.planner import build
from agent.editorial.render import render
from agent.editorial.sentence_storyboard import direction
from agent.editorial.visuals import EditorialScript
from agent.news_models import Entity, Sentence
from agent.news_layout import font_path


SCENES = [
    ('confront', 'Amaterasu confronted her brother Susanoo.', 'confronting Susanoo', 'heavenly court', 'tension', 'character-interaction'),
    ('darkness', 'Amaterasu entered the cave, and darkness spread across the world.', 'hiding inside the cave', 'cave and darkening world', 'sunlight to darkness', 'environment-change'),
    ('pleading', 'The gods pleaded outside the sealed cave.', 'pleading toward the closed cave', 'cave entrance', 'fear and concern', 'character-interaction'),
    ('dance', 'Ame-no-Uzume danced as the gathered gods laughed.', 'dancing before laughing gods', 'cave courtyard', 'laughter and curiosity', 'character-interaction'),
    ('peeking', 'Hearing the celebration, Amaterasu peeked outside.', 'reacting and peeking from the cave', 'cave opening', 'curiosity', 'character-interaction'),
    ('mirror', 'Amaterasu saw her own reflection in the sacred mirror.', 'seeing her face inside the mirror', 'cave entrance', 'wonder', 'object-closeup'),
    ('pulling', 'A god pulled Amaterasu out of the cave.', 'pulling Amaterasu across the threshold', 'cave threshold', 'rescue', 'character-interaction'),
    ('sunlight', 'Sunlight returned as Amaterasu emerged.', 'emerging while the world relights', 'brightening landscape', 'darkness to sunlight', 'dramatic-reveal'),
]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path('output/japanese_narrative_review_20261018'))
    args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    audio=out/'baseline_narration.wav'
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(args.baseline),'-vn','-ar','48000','-ac','2','-c:a','pcm_s24le',str(audio)],check=True)
    duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(audio)]))
    boundaries=[0,8,15,23,37,49,62,69,duration]
    sentence_rows=[];entities=[];assets=[];words=[];sections=[];storyboard=[]
    for i,(name,text,action,setting,change,composition) in enumerate(SCENES):
        image=out/'assets'/f'{i+1:02d}_{name}.png'
        if not image.is_file():raise FileNotFoundError(image)
        eid=f'scene-{i+1}';aid=f'asset-{eid}';sid=f'sentence-{i+1}'
        entity=Entity(id=eid,name=name.title(),kind='object',identity='generic',description=action)
        entities.append(entity)
        sentence_rows.append(Sentence(id=sid,text=text,claim_ids=['review'],entity_ids=[eid],phrase=action,role='development'))
        from PIL import Image
        with Image.open(image) as im:width,height=im.size
        assets.append(Asset(id=aid,entityId=eid,path=str(image),originalPath=str(image),role='object',subject=name,source='local image generation review',license='project review',attribution='ProjectHER review artwork',width=width,height=height,alpha=False,factual=False,confidence=.8,preparation='rectangle',fallback='Illustrative mythology reconstruction for visual review',sha256=digest(image)))
        start,end=boundaries[i:i+2];tokens=text.split();ids=[]
        for j,token in enumerate(tokens):
            wid=f'w-{i}-{j}';ids.append(wid)
            word_start=start+(end-start)*j/len(tokens)
            word_end=start+(end-start)*(j+1)/len(tokens)
            words.append(Word(id=wid,sectionId=sid,text=token,start=word_start,end=word_end,provenance='estimated_phrase',confidence=.3))
        sections.append(Section(id=sid,text=text,start=start,end=end,wordIds=ids))
        storyboard.append({'sentence_id':sid,'primary_entity_id':eid,'secondary_entity_ids':[],
            'main_action':action,'state_before':'before '+change,'state_after':change,
            'visual_focus':action,'location':setting,'composition_type':composition})
    narration=' '.join(row.text for row in sentence_rows)
    script=EditorialScript(narration=narration,summary='Amaterasu and the cave',sentences=[row.model_dump() for row in sentence_rows],entities=entities,sentence_storyboard=storyboard)
    render_entities=[RenderEntity(id=e.id,name=e.name,identity='generic',assetIds=[assets[i].id],source='review') for i,e in enumerate(entities)]
    from agent.editorial.audio import normalize
    master=out/'master.wav';normalize(audio,master)
    settings=VisualSettings.configured().model_copy(update={'editorialStyleVersion':'reference-v2'})
    m=build(script,words,sections,render_entities,assets,master,out,'japanese_narrative_review_20261018',{},direction=direction(script),visual_settings=settings)
    (out/'sentence_report.json').write_text(json.dumps([{
        'sentence':text,'primary_visual':f'assets/{i+1:02d}_{name}.png','visual_action':action,
        'continuity_references':['Amaterasu design from first scene'] if name in ('darkness','peeking','mirror','pulling','sunlight') else [],
        'composition':composition,'relevance':'pending rendered-frame review',
        'timing':'approximate review timing; baseline audio reused'
    } for i,(name,text,action,setting,change,composition) in enumerate(SCENES)],indent=2))
    video,stats=render(m,out/'japanese-narrative-review.mp4')
    print(json.dumps({'video':str(video),'frames':m.durationInFrames,'audio':stats},indent=2))


if __name__=='__main__':main()
