"""Run the existing editorial pipeline against the sourced Osiris fixture.

Uses configured providers and existing bounded retries. No model overrides.
The resulting script is finalized by the standard evidence-based writer; the
fixture is source input, not fabricated speech/alignment or render evidence.
"""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent.editorial.pipeline import run_editorial


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,default=Path('output/three_branch_osiris_live'))
    p.add_argument('--cached',type=Path,help='Rerender an existing real aligned job; retains its script, including known narrative gaps.')
    p.add_argument('--resume-plan',type=Path,help='Replay a saved real script and bounded planner response; all media still use the standard pipeline.')
    p.add_argument('--asset-overrides',type=Path,help='Curated cached asset provenance map for a render-only review; no generation.')
    args=p.parse_args()
    if args.cached:
        return cached_review(args.cached,args.output,args.asset_overrides)
    fixture=json.loads(Path('tests/fixtures/narrative/osiris.json').read_text())
    text=' '.join(fixture['sentences'])
    def progress(*args,**kwargs):
        print(str(args)[:400],str(kwargs)[:200],flush=True)
    llm=None
    if args.resume_plan:
        from agent.news_script import NewsLLM
        live=NewsLLM()
        previous=json.loads((args.resume_plan/'news_preview.json').read_text())
        replies=sorted(args.resume_plan.glob('planner_reply_*.json'))
        if not replies:raise ValueError('No recorded real planner response to resume.')
        reply=json.loads(replies[-1].read_text())
        def llm(instruction,data):
            if instruction.startswith('Extract central event claims'):
                return {k:previous['evidence'][k] for k in ('claims','conflicts','unresolved')}
            if instruction.startswith('Write a captivating'):return previous['script']
            if instruction.startswith('Plan one genuinely'):return reply
            return live(instruction,data)
    result=run_editorial(text,output_dir=args.output,source_policy='supplied',
        language='english',target_duration=0,progress_callback=progress,llm=llm)
    report={'success':result.success,'video':str(result.video_path) if result.video_path else None,
        'errors':result.errors,'details':result.news_details}
    (args.output/'review_result.json').write_text(json.dumps(report,indent=2,default=str))
    print(json.dumps({'success':report['success'],'video':report['video'],'errors':report['errors']},indent=2),flush=True)
    if not result.success:raise SystemExit(1)


def cached_review(baseline,out,overrides_path=None):
    import hashlib
    from agent.editorial.models import Timeline
    from agent.editorial.visuals import EditorialScript
    from agent.editorial.narrative import storyboard_narrative
    from agent.editorial.director import VisualSettings
    from agent.editorial.planner import build
    from agent.editorial.render import render
    from agent.editorial.sentence_storyboard import direction,embedded_members
    from agent.editorial.canonical import lock_script
    from agent.editorial.quality import audit_timeline
    old=Timeline.model_validate_json((baseline/'editorial_manifest.json').read_text())
    overrides=json.loads(overrides_path.read_text()) if overrides_path else {}
    for target,source in overrides.items():
        provenance=Timeline.model_validate_json(Path(source['manifest']).read_text())
        selected=next(a for a in provenance.assets if a.id==source['assetId'])
        index=next(i for i,a in enumerate(old.assets) if a.id==target)
        replacement=old.assets[index]
        old.assets[index]=selected.model_copy(update={'id':replacement.id,'entityId':replacement.entityId,
            'fallback':(selected.fallback or '')+' Curated cached event illustration; cross-run identity continuity needs review.'})
    script=EditorialScript.model_validate(json.loads((baseline/'visual_plan.json').read_text())['script'])
    script.sentence_storyboard=json.loads((baseline/'sentence_storyboard.json').read_text())
    registry={e.id:e for e in script.identity_registry}
    for row in script.sentence_storyboard:
        depicted=embedded_members(row['visual_description'],registry.values(),row.get('identity_reference_ids',[]))
        row['depicted_entity_ids']=depicted
        row['secondary_entity_ids']=[eid for eid in row['secondary_entity_ids'] if eid not in depicted]
    script.narrative_plan=storyboard_narrative(script).bind_audio(old.words)
    out.mkdir(parents=True,exist_ok=True)
    canonical=lock_script(script)
    (out/'canonical_script.json').write_text(json.dumps(canonical,indent=2))
    m=build(script,old.words,old.sections,old.entities,old.assets,Path(old.audio[0].path),out,
        'recompose_'+hashlib.sha256(str(out.resolve()).encode()).hexdigest()[:16],{},direction=direction(script),visual_settings=VisualSettings.configured())
    m.diagnostics['integrationQuality']=audit_timeline(script,m,canonical)
    m.warnings.append('Cached-asset recompose retains the original narration and artwork; physical-action visual acceptance still requires review.')
    (out/'narrative_beat_plan.json').write_text(script.narrative_plan.model_dump_json(indent=2))
    (out/'sentence_storyboard.json').write_text(json.dumps(script.sentence_storyboard,indent=2))
    (out/'visual_plan.json').write_text(json.dumps({'script':script.model_dump()},indent=2))
    (out/'curated_asset_provenance.json').write_text(json.dumps(overrides,indent=2))
    (out/'editorial_manifest.json').write_text(m.model_dump_json(indent=2))
    video,stats=render(m,out/'osiris-review.mp4')
    (out/'review_result.json').write_text(json.dumps({'video':str(video),'audio':stats,
        'quality':m.diagnostics['integrationQuality'],'acceptancePassed':False,'warnings':m.warnings},indent=2))

if __name__=='__main__':main()
