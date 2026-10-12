"""Re-render saved real narration/assets through the atomic Visual Director.

No credentials, new facts, paid calls or timing estimates are introduced.
Use --fixture for a complete offline input-to-video pipeline with synthetic audio.
"""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent.editorial.models import Timeline
from agent.editorial.director import direct, VisualSettings, save_summary
from agent.editorial.planner import build
from agent.editorial.render import render
from agent.news_models import Script, Sentence, Entity


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',default='output/editorial_portuguese_recovery/editorial_manifest.json')
    parser.add_argument('--output',default='output/narration_visual_demo')
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--fixture',action='store_true')
    parser.add_argument('--live',action='store_true',help='Use configured LLM, speech and image providers for a short supplied fictional demonstration.')
    args=parser.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    if args.live:
        from agent.editorial.pipeline import run_editorial
        result=run_editorial('Fictional demonstration: A red ceramic cup stands beside a blue ceramic bowl. The cup stays in place while attention shifts to the bowl.',
            output_dir=out,source_policy='supplied',target_duration=12,music=False,asset_mode='auto')
        if not result.success:raise RuntimeError(result.errors)
        print(result.video_path);return
    if args.fixture:
        from tests.news_fixtures import FixtureLLM,FixtureTTS,SCRIPT,ACCOUNT,subject_image
        from agent.editorial.planner import semantic_plan
        from agent.news_pipeline import run_news
        class LLM(FixtureLLM):
            def __call__(self,instruction,data):
                if instruction.startswith('Propose'):
                    rows=semantic_plan(SCRIPT)
                    for row,s in zip(rows,SCRIPT.sentences):row['setupWords']=min(5,len(s.text.split())-1)
                    return {'beats':rows}
                return super().__call__(instruction,data)
        registry={}
        for entity in SCRIPT.entities:
            path=out/(entity.id+'.png');subject_image(entity.id).save(path)
            registry[entity.name]={'path':str(path.resolve()),'subject':entity.name,'source':'Synthetic offline illustration','license':'Project test artwork','attribution':'Project HER','role':'portrait' if entity.kind=='person' else 'object'}
        reg=out/'registry.json';reg.write_text(json.dumps(registry))
        result=run_news(ACCOUNT,output_dir=out,source_policy='supplied',visual_preset='reference_editorial',llm=LLM(),tts_provider='edge_tts',tts_engine=FixtureTTS(),asset_mode='local',local_assets=str(reg),music=False)
        if not result.success:raise RuntimeError(result.errors)
        print(result.video_path);return
    old=Timeline.model_validate_json(Path(args.manifest).read_text())
    sentences=[]
    for section in old.sections:
        linked=list(dict.fromkeys(l.entityId for l in old.layers if l.assetId and l.startFrame<round(section.end*30) and l.endFrame>round(section.start*30)))[:3]
        sentences.append(Sentence(id=section.id,text=section.text,claim_ids=section.sourceIds or ['preserved'],entity_ids=linked,phrase=section.text,role='development'))
    used={e for s in sentences for e in s.entity_ids};assets=[a for a in old.assets if a.entityId in used]
    entities=[e for e in old.entities if e.id in used]
    script=Script(summary='Preserved narration',narration=old.script,sentences=sentences,entities=[Entity(id=e.id,name=e.name,kind='person' if any(a.entityId==e.id and a.role=='portrait' for a in assets) else 'object',description=e.name,identity=e.identity) for e in entities])
    diagnostics={'verification':'Recorded narration and existing assets reused; no live provider calls.'}
    settings=VisualSettings();direction=direct(script,old.words,settings=settings,diagnostics=diagnostics)
    master=next(a for a in old.audio if a.kind=='master')
    timeline=build(script,old.words,old.sections,entities,assets,master.path,out,out.name,diagnostics,direction=direction,visual_settings=settings)
    save_summary(timeline,out)
    print('Prepared',len(timeline.beats),'atomic beats;',len(timeline.words),'recorded word timings',flush=True)
    if not args.prepare_only:
        video,stats=render(timeline,out/'editorial.mp4')
        timeline.diagnostics['finalAudio']=stats
        (out/'editorial_manifest.json').write_text(timeline.model_dump_json(indent=2))
        print(video,flush=True)

if __name__=='__main__':main()
