"""Rebuild a saved approved event plan using alpha cutouts or factual frames.

No new story facts, audio, word timings, image provider requests or identity
substitutions. The optional alpha directory contains prepared NN-cutout.png or
manually reviewed NN-candidate.png assets; originals remain untouched.
"""
import argparse
import json
import sys
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent.editorial.models import Timeline,digest
from agent.editorial.visuals import EditorialScript
from agent.editorial.scene_plan import BeatInput,plan_story
from agent.editorial.sentence_storyboard import direction
from agent.editorial.director import VisualSettings,save_summary
from agent.editorial.planner import build
from agent.editorial.render import render
from agent.editorial.cutout_style import extract_elements
from agent.editorial.assets import prepare
from review_editorial_motion import export


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--alpha-dir',type=Path);p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
    source=a.source.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    old=Timeline.model_validate_json((source/'editorial_manifest.json').read_text())
    script=EditorialScript.model_validate_json((source/'planned_script.json').read_text())
    beats=(script.event_plan or {}).get('beats',[]);by_section={b['visual_section_id']:b for b in beats}
    inputs=[]
    for i,s in enumerate(script.sentences):
        b=by_section.get(s.id,{})
        inputs.append(BeatInput(text=s.text,index=i,total=len(script.sentences),role=b.get('role'),verb=b.get('verb'),actors=b.get('actor_ids',[]),objects=b.get('object_ids',[]),hint=b.get('beat_type')))
    plans=plan_story(inputs)
    for row,plan in zip(script.sentence_storyboard,plans):row['scene_plan']=plan.as_dict()
    assets=[]
    for i,asset in enumerate(old.assets):
        if a.alpha_dir:
            path=a.alpha_dir/f'{i:02d}-cutout.png'
            if not path.is_file():path=a.alpha_dir/f'{i:02d}-candidate.png'
            if not path.is_file():raise FileNotFoundError(path)
            with Image.open(path) as im:w,h=im.size;alpha=im.mode=='RGBA' and im.getchannel('A').getextrema()[0]<255
            if not alpha:raise ValueError('Expected prepared alpha for '+str(path))
            entity=next(e for e in script.entities if e.id==asset.entityId)
            normalized=prepare(entity,path,out/'prepared-assets',source=asset.source,license=asset.license,attribution=asset.attribution,role=asset.role,factual=asset.factual)
            asset=asset.model_copy(update=dict(path=normalized.path,width=normalized.width,height=normalized.height,alpha=True,preparation='trimmed_alpha',sha256=normalized.sha256))
            extract_elements(asset.path)
        elif asset.factual and not asset.alpha:
            # A factual photo stays a factual photo; never fake a cutout or
            # use generated scene art as documentary evidence.
            asset=asset.model_copy(update={'role':'photo'})
        assets.append(asset)
    master=next(t for t in old.audio if t.kind=='master')
    m=build(script,old.words,old.sections,old.entities,assets,master.path,out,out.name,{'reviewSource':str(source),'reviewNote':'Existing measured narration and event imagery; new layout and alpha preprocessing only.'},direction=direction(script),visual_settings=VisualSettings(editorialStyleVersion='reference-v2'))
    save_summary(m,out);(out/'planned_script.json').write_text(script.model_dump_json(indent=2))
    if a.prepare_only:return
    video,stats=render(m,out/'editorial.mp4');(out/'metrics.json').write_text(json.dumps(stats,indent=2));(out/'editorial_manifest.json').write_text(m.model_dump_json(indent=2))
    print(export(out/'editorial_manifest.json',video,out/'review'))

if __name__=='__main__':main()
