"""Real provider/renderer review, optionally preserving saved speech exactly."""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent.editorial import event_storyboard as events
from agent.editorial import sentence_storyboard as sentences
from agent.editorial.visuals import EditorialScript
from agent.editorial.models import Timeline
from agent.editorial.assets import acquire
from agent.editorial.planner import build
from agent.editorial.director import VisualSettings
from agent.editorial.render import render
from agent.news_script import NewsLLM


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--baseline',type=Path,required=True,help='Directory with news_preview.json and editorial_manifest.json')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--plan-only',action='store_true')
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    started=time.monotonic();diag={}
    source=json.loads((args.baseline/'news_preview.json').read_text())
    source_script=EditorialScript.model_validate(source['script'])
    old=Timeline.model_validate_json((args.baseline/'editorial_manifest.json').read_text())
    if source_script.narration!=old.script:raise ValueError('Baseline script/audio manifest mismatch')
    if args.resume and (out/'planned_script.json').exists():
        script=EditorialScript.model_validate_json((out/'planned_script.json').read_text())
    else:
        import config
        try:script,_=events.plan(source_script,None,NewsLLM(model=config.EDITORIAL_EVENT_MODEL),diag)
        finally:(out/'planning_diagnostics.json').write_text(json.dumps(diag,ensure_ascii=False,indent=2))
        (out/'planned_script.json').write_text(script.model_dump_json(indent=2))
        (out/'event_plan.json').write_text(json.dumps(script.event_plan,ensure_ascii=False,indent=2))
    print('Planned',len(script.sentences),'events',flush=True)
    words,sections=events.bind_audio(script,old.words)
    if args.plan_only:return
    if args.resume and (out/'acquired.json').exists():
        from agent.editorial.models import Entity,Asset
        saved=json.loads((out/'acquired.json').read_text())
        entities=[Entity.model_validate(e) for e in saved['entities']];assets=[Asset.model_validate(a) for a in saved['assets']]
        diag['assetAcquisition']=json.loads((out/'assets/asset_acquisition.json').read_text())
    else:
        entities,assets=acquire(script,out/'assets',asset_mode='ai',llm=NewsLLM(),diagnostics=diag)
        (out/'acquired.json').write_text(json.dumps({'entities':[e.model_dump() for e in entities],'assets':[a.model_dump() for a in assets]},indent=2))
    diag['sentenceQuality']=events.validate_assets(script,assets,diag['assetAcquisition'])
    events.save_report(script,assets,diag['assetAcquisition'],words,out)
    audio=next(a for a in old.audio if a.kind=='master')
    m=build(script,words,sections,entities,assets,audio.path,out,out.name,diag,direction=sentences.direction(script),visual_settings=VisualSettings.configured())
    qc=events.save_report(script,assets,diag['assetAcquisition'],words,out,m)
    m.diagnostics['eventQuality']=qc['metrics']
    (out/'sentence_storyboard.json').write_text(json.dumps(script.sentence_storyboard,indent=2))
    (out/'planned_script.json').write_text(script.model_dump_json(indent=2))
    video,stats=render(m,out/'editorial.mp4')
    m.diagnostics.update(finalAudio=stats,reviewWallSeconds=time.monotonic()-started)
    (out/'editorial_manifest.json').write_text(m.model_dump_json(indent=2))
    print(json.dumps({'video':str(video),**qc['metrics']},indent=2),flush=True)

if __name__=='__main__':main()
