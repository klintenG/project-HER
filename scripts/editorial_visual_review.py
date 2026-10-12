"""Replay saved narration with live contextual imagery; no new speech calls."""
import argparse
import json
import logging
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent.news_models import Script,Evidence
from agent.news_script import NewsLLM
from agent.editorial.models import Timeline
from agent.editorial.visuals import plan_visuals,EditorialScript,restore_named_cues
from agent.editorial.assets import acquire
from agent.editorial.planner import build,semantic_plan
from agent.editorial.render import render,stage
from agent.editorial.audio import subtitles


def main():
    p=argparse.ArgumentParser();p.add_argument('previous');p.add_argument('--output',required=True);p.add_argument('--prepare-only',action='store_true');p.add_argument('--resume-plan',action='store_true');args=p.parse_args()
    logging.basicConfig(level=logging.WARNING)
    previous=Path(args.previous);out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    old=Timeline.model_validate_json((previous/'editorial_manifest.json').read_text())
    preview=json.loads((previous/'news_preview.json').read_text());script=Script.model_validate(preview['script']);evidence=Evidence.model_validate(preview['evidence'])
    diagnostics={'replaySource':str(previous.resolve()),'speechReused':True};llm=NewsLLM()
    print('Planning context visuals for saved narration...',flush=True)
    if args.resume_plan:
        saved=json.loads((out/'visual_plan.json').read_text());script=EditorialScript.model_validate(saved['script']);cues=saved['sections'];diagnostics.update(saved['diagnostics'])
        script,cues=restore_named_cues(script,cues)
    else:script,cues=plan_visuals(script,evidence,llm,diagnostics)
    (out/'visual_plan.json').write_text(json.dumps({'script':script.model_dump(),'sections':cues,'diagnostics':diagnostics},ensure_ascii=False,indent=2))
    print('Visual subjects: '+str(len(script.entities)),flush=True)
    entities,assets=acquire(script,out/'assets',asset_mode='auto',llm=llm,evidence=evidence,diagnostics=diagnostics)
    print('Prepared '+str(len(assets))+' assets; transparent='+str(sum(a.alpha for a in assets)),flush=True)
    plan=semantic_plan(script,llm,diagnostics)
    m=build(script,old.words,old.sections,entities,assets,old.audio[0].path,out,out.name,diagnostics,plan,old.subtitleMode,visual_cues=cues)
    m.warnings.extend(diagnostics['visualPlan']['warnings']+diagnostics['semanticPlan']['warnings'])
    subtitles(old.words,out/'subtitles');stage(m,out)
    if not args.prepare_only:
        video,stats=render(m,out/'editorial.mp4');m.diagnostics.update(finalAudio=stats)
        print('Rendered '+str(video),flush=True)
    (out/'editorial_manifest.json').write_text(m.model_dump_json(indent=2))
    (out/'image_credits.txt').write_text('\n\n'.join(a.subject+'\n'+a.attribution+'\n'+(a.fallback or '') for a in assets))


if __name__=='__main__':main()
