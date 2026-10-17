"""Reproduce a saved-narration visual regression with actual provider assets.

This deliberately reports a visual-pipeline run, never a full generation speedup.
Use --prepare-only to inspect exact action requests before any provider transfer.
"""
import argparse
import json
import sys
import signal
import threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent.editorial.models import Timeline, Word, Section
from agent.editorial.visuals import plan_visuals, EditorialScript
from agent.editorial.assets import acquire
from agent.editorial.planner import build
from agent.editorial.director import direct, VisualSettings, save_summary
from agent.editorial.render import render
from agent.news_models import Script
from utils.job_trace import JobTrace


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',type=Path,help='Existing editorial manifest with news_preview.json beside it')
    parser.add_argument('--inputs',type=Path,help='JSON containing script, words, sections, master and registry for recorded source media')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--visual-plan',type=Path,help='Reuse an inspected visual_plan.json for exactly this narration')
    parser.add_argument('--semantic',action='store_true',help='Use the configured live semantic planner')
    parser.add_argument('--prepare-only',action='store_true',help='Save requests without image calls or render; --semantic still calls the configured LLM')
    args=parser.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
    if args.inputs:
        data=json.loads(args.inputs.read_text());script=Script.model_validate(data['script'])
        if data.get('preparation_status')=='pending' and not args.prepare_only:
            parser.error('Source matte extraction is pending; repair identities before live generation')
        words=[Word.model_validate(w) for w in data['words']];sections=[Section.model_validate(s) for s in data['sections']]
        master=data['master'];registry=data['registry']
    elif args.manifest:
        old=Timeline.model_validate_json(args.manifest.read_text())
        source=json.loads((args.manifest.parent/'news_preview.json').read_text())['script']
        script=Script.model_validate(source);words=old.words;sections=old.sections
        master=next(a.path for a in old.audio if a.kind=='master')
        registry={a.subject:{'path':a.originalPath if Path(a.originalPath).is_file() else a.path,'subject':a.subject,'source':a.source,'license':a.license,'attribution':a.attribution,'role':a.role,'factual':a.factual} for a in old.assets}
    else:parser.error('Pass --manifest or --inputs')
    cancel=threading.Event()
    signal.signal(signal.SIGTERM,lambda *_:cancel.set())
    signal.signal(signal.SIGINT,lambda *_:cancel.set())
    trace=JobTrace(out/'job_trace.json',out.name)
    with trace.span('end_to_end',scope='saved_narration_visual_regression'):
        llm=None
        if args.semantic:
            from agent.news_script import NewsLLM
            llm=NewsLLM()
        diagnostics={'verification':'Recorded audio reused; this is not a full input-to-video latency benchmark.'}
        if args.visual_plan:
            saved=json.loads(args.visual_plan.read_text());planned=EditorialScript.model_validate(saved['script']);cues=saved['sections']
            if planned.narration!=script.narration:parser.error('Saved visual plan narration differs from recorded source')
            planned.narrative_plan.validate_script(planned)
            diagnostics.update(saved.get('diagnostics',{}))
        else:
            planned,cues=trace.call('semantic_beat_planning',plan_visuals,script,llm=llm,diagnostics=diagnostics)
        planned.narrative_plan.bind_audio(words).validate_script(planned)
        (out/'narrative_beat_plan.json').write_text(planned.narrative_plan.model_dump_json(indent=2))
        (out/'visual_plan.json').write_text(json.dumps({'script':planned.model_dump(),'sections':cues,'diagnostics':diagnostics},indent=2))
        if args.prepare_only:return
        reg=out/'registry.json';reg.write_text(json.dumps(registry))
        entities,assets=acquire(planned,out/'assets',local_registry=reg,asset_mode='auto',diagnostics=diagnostics,trace=trace,cancel_event=cancel)
        diagnostics['narrativeQuality']=planned.narrative_plan.assess_assets(assets,diagnostics['assetAcquisition'])
        direction=direct(planned,words,cues,settings=VisualSettings())
        diagnostics['narrativeBeatPlan']=planned.narrative_plan.model_dump()
        m=build(planned,words,sections,entities,assets,master,out,out.name,diagnostics,visual_cues=cues,direction=direction,visual_settings=VisualSettings())
        save_summary(m,out)
        video,stats=render(m,out/'editorial.mp4',trace=trace,cancel_event=cancel);m.diagnostics['finalAudio']=stats
        (out/'editorial_manifest.json').write_text(m.model_dump_json(indent=2))
        (out/'narrative_beat_plan.json').write_text(planned.narrative_plan.model_dump_json(indent=2))
        print(video,flush=True)
        if not diagnostics['narrativeQuality']['acceptancePassed']:
            raise RuntimeError('Export exists but required action visual acceptance is pending or degraded; inspect narrativeQuality')

if __name__=='__main__':main()
