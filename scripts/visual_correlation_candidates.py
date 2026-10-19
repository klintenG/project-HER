"""Curated golden storyboard -> real provider candidates -> explicit manual review.

This review fallback never claims live planner or automated vision acceptance.
The production pipeline continues to use its real multimodal judge. Use this
only with a curated fixture when that judge is unavailable; review.json must
contain actual visual observations, not inferred prompt compliance.
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent.editorial import event_storyboard as ev
from agent.editorial.visuals import EditorialScript
from agent.editorial.images import EditorialImages
from agent.editorial.assets import prepare
from agent.editorial.models import Timeline, Entity as RenderEntity
from agent.news_assets import _generate


def main():
    p=argparse.ArgumentParser();p.add_argument('--fixture',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--tts-provider',default='replicate',choices=['replicate','google_tts','elevenlabs','edge_tts']);p.add_argument('--baseline',type=Path);p.add_argument('--render',action='store_true');p.add_argument('--redo',default='')
    args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);folder=out/'assets';folder.mkdir(exist_ok=True)
    fixture=json.loads(args.fixture.read_text());source=EditorialScript.model_validate(fixture['source_script']);reply=fixture['response']
    def curated(instruction,data):
        if instruction.startswith('Audit event'):return {'accepted':True,'problems':[]}
        ids={s['id'] for s in data['target_sections']}
        return {'continuity_bible':reply['continuity_bible'],'beats':[b for b in reply['beats'] if b['section_id'] in ids]}
    diag={'planningProvenance':fixture['provenance'],'reviewMode':'manual_visual_review_required'}
    script,_=ev.plan(source,None,curated,diag)
    (out/'planned_script.json').write_text(script.model_dump_json(indent=2));(out/'event_plan.json').write_text(json.dumps(script.event_plan,indent=2))
    generator=EditorialImages(primary_count=len(script.sentences));masters={};audit={'mode':'curated_manual_review','assets':[]}
    acquisition_path=folder/'asset_acquisition.json'
    if acquisition_path.exists():audit=json.loads(acquisition_path.read_text())
    previous={r['entityId']:r for r in audit['assets']};records=[]
    def request(entity,path,reference=None,primary=False):
        started=time.monotonic();old=previous.get(entity.id,{})
        if path.exists() and args.redo!=entity.id and not (primary and args.redo=='all'):return old.get('provider','replicate:cached'),old.get('durationSeconds',0)
        if path.exists():
            import shutil
            rejected=folder/'rejected';rejected.mkdir(exist_ok=True)
            shutil.copyfile(path,rejected/(entity.id+'-'+str(int(time.time()))+'.png'))
        prompt=entity.description+' One coherent premium Norse editorial illustration.' if fixture.get('style')=='norse' else entity.description
        if primary:
            event=next(b for b in ev.EventPlan.model_validate(script.event_plan).beats if b.asset_entity_id==entity.id)
            prompt=ev.generation_prompt(event)
        method=generator.scene_subject if primary else generator.identity_subject if entity.kind=='person' else generator.subject
        call=method(prompt,path,reference) if primary else method(prompt,path)
        provider=_generate(call,None)
        return provider,round(time.monotonic()-started,3)
    required_refs={eid for b in script.sentence_storyboard for eid in b['continuity_references']}
    for entity in script.identity_registry:
        if entity.id not in required_refs:continue
        path=folder/(entity.id+'-identity.png')
        provider,seconds=request(entity,path)
        masters[entity.id]=path
        print('Identity ready:',entity.id,flush=True)
    def make(entity):
        beat=next(b for b in script.sentence_storyboard if b['primary_entity_id']==entity.id)
        refs=[str(masters[eid]) for eid in beat['continuity_references'] if eid in masters]
        reference=SimpleNamespace(path=refs[0],paths=refs,characters=beat['continuity_references']) if refs else None
        path=folder/(entity.id+'-candidate.png')
        planned_beat=next(b for b in script.event_plan['beats'] if b['asset_entity_id']==entity.id)
        supplied=fixture.get('supplied_assets',{}).get(planned_beat['beat_id'])
        if supplied:
            if not path.exists():
                from agent.news_research import fetch
                data,_=fetch(supplied['url'],types=('image/jpeg','image/png'),limit=15000000);path.write_bytes(data)
            provider=supplied['source'];seconds=0
        else:provider,seconds=request(entity,path,reference,True)
        asset=prepare(entity,path,folder,source=provider,license=supplied['license'] if supplied else 'Generated illustration',attribution=supplied['attribution'] if supplied else 'ProjectHER; '+provider,role='context',factual=bool(supplied))
        record=dict(entityId=entity.id,assetId=asset.id,path=asset.path,provider=provider,durationSeconds=seconds,
            requests=[{'prompt':ev.generation_prompt(ev.EventRecord.model_validate(planned_beat)),'identityReferences':refs}] if not supplied else [{'source':supplied['source'],'url':supplied['url']}],generation={},degraded=True,
            route='manual_review_pending',model=provider.removeprefix('replicate:'),sha256=asset.sha256)
        print('Candidate ready:',beat['sentence_id'],entity.id,flush=True)
        return asset,record
    primaries={b['primary_entity_id'] for b in script.sentence_storyboard}
    entities=[e for e in script.entities if e.id in primaries]
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(make,entities))
    assets=[pair[0] for pair in results];records=[pair[1] for pair in results]
    review_path=out/'review.json';reviews=json.loads(review_path.read_text()) if review_path.exists() else {}
    for record in records:
        review=reviews.get(record['entityId'])
        if review and review.get('sha256')==record['sha256'] and review.get('observations') and review.get('reviewer'):
            record['generation']['sentenceReview']=review['assessment']
            record['generation']['manualReviewEvidence']={k:review[k] for k in ('reviewer','observations','sha256')}
            record['degraded']=not ev.review_passes(review['assessment'],None)
            record['route']='manual_visual_review'
    history=audit.get('previousRuns',[])
    if audit.get('providerMetrics'):history.append({'assets':audit['assets'],'providerMetrics':audit['providerMetrics']})
    audit.update(assets=records,providerMetrics=generator.metrics,previousRuns=history)
    acquisition_path.write_text(json.dumps(audit,indent=2))
    render_entities=[RenderEntity(id=e.id,name=e.name,identity=e.identity,assetIds=['asset-'+e.id],source='Generated illustration') for e in entities]
    (out/'acquired.json').write_text(json.dumps({'entities':[e.model_dump() for e in render_entities],'assets':[a.model_dump() for a in assets]},indent=2))
    if not args.render:return
    if args.baseline:
        old=Timeline.model_validate_json((args.baseline/'editorial_manifest.json').read_text())
        if old.script!=source.narration:raise ValueError('Frozen source narration mismatch')
        words,sections=ev.bind_audio(script,old.words);audio=next(a for a in old.audio if a.kind=='master').path
    elif (out/'editorial_manifest.json').exists():
        old=Timeline.model_validate_json((out/'editorial_manifest.json').read_text())
        if old.script!=source.narration:raise ValueError('Cached narration no longer matches script')
        words,sections=old.words,old.sections
        audio=next(a for a in old.audio if a.kind=='master').path
    else:
        from agent.news_audio import synthesize
        from agent.editorial.audio import prepare_existing,normalize
        speech=synthesize(source,out,args.tts_provider,pause=0)
        raw,original,_,alignment=prepare_existing(source,speech,out/'audio','en')
        words,sections=ev.bind_audio(script,original);audio=out/'master.wav';normalize(raw,audio);diag.update(alignment)
    from agent.editorial.planner import build
    from agent.editorial.sentence_storyboard import direction
    from agent.editorial.director import VisualSettings
    from agent.editorial.render import render
    from agent.editorial.audio import subtitles
    diag['sentenceQuality']=ev.validate_assets(script,assets,audit)
    m=build(script,words,sections,render_entities,assets,audio,out,out.name,diag,direction=direction(script),visual_settings=VisualSettings.configured())
    qc=ev.save_report(script,assets,audit,words,out,m);m.diagnostics['eventQuality']=qc['metrics']
    m.warnings.append('Curated acceptance storyboard; live planner was not used. See manual visual review evidence.')
    subtitles(words,out/'subtitles')
    video,stats=render(m,out/'editorial.mp4');m.diagnostics['finalAudio']=stats
    (out/'editorial_manifest.json').write_text(m.model_dump_json(indent=2));(out/'planned_script.json').write_text(script.model_dump_json(indent=2))
    print(json.dumps({'video':str(video),'metrics':qc['metrics']},indent=2),flush=True)

if __name__=='__main__':main()
