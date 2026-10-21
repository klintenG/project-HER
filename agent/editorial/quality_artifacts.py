"""Reviewable event contracts and job artifacts; metadata is never visual proof."""
from pathlib import Path
from typing import Literal
import json
import math
import subprocess
from pydantic import Field, model_validator
from agent.news_models import Model, NewsError


class VisualScenePlan(Model):
    scene_id: str
    beat_type: Literal['INTRO','CONTEXT','INTERACTION','PHYSICAL_ACTION','CONSEQUENCE','EMOTIONAL','TRANSITION','OUTRO']
    actor_ids: list[str] = Field(default_factory=list)
    verb: str
    object_ids: list[str] = Field(default_factory=list)
    required_visible_relationships: list[str]
    forbidden: list[str] = Field(default_factory=list)
    asset_role: Literal['ACTOR_ONLY','EVENT_ACTION','EVENT_OUTCOME','CONTEXT','OUTRO']
    generation_attempt_limit: Literal[1] = 1
    scene_asset_id: str

    @model_validator(mode='after')
    def compatible(self):
        if self.beat_type in ('INTERACTION','PHYSICAL_ACTION','CONSEQUENCE') and self.asset_role not in ('EVENT_ACTION','EVENT_OUTCOME'):
            raise ValueError('An event cannot be fulfilled by an actor-only visual')
        return self


def visual_contract(beat):
    role=beat['role']
    kind=('PHYSICAL_ACTION' if role=='action_tableau' else 'INTERACTION' if role=='interaction' else
          'CONSEQUENCE' if role in ('aftermath','reveal') else 'INTRO' if role=='character_intro' else 'CONTEXT')
    return VisualScenePlan(scene_id=beat['beat_id'],beat_type=kind,actor_ids=beat['actor_ids'],verb=beat['verb'],
        object_ids=beat['object_ids'],required_visible_relationships=beat['must_show'],forbidden=beat['must_not_show'],
        asset_role='EVENT_OUTCOME' if kind=='CONSEQUENCE' else 'EVENT_ACTION' if kind in ('PHYSICAL_ACTION','INTERACTION') else 'ACTOR_ONLY' if kind=='INTRO' else 'CONTEXT',
        scene_asset_id=beat['asset_entity_id'])


def write(output, script=None, assets=(), acquisition=None, edl=None, status=None):
    root=Path(output);root.mkdir(parents=True,exist_ok=True)
    def save(name,value):
        target=root/name;temporary=target.with_suffix('.tmp')
        temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str));temporary.replace(target)
    plan=getattr(script,'event_plan',None) or {}
    if plan:
        save('storyboard.json',{'script_sha256':plan['script_sha256'],'beats':plan['beats'],
            'visual_scene_plans':[visual_contract(b).model_dump() for b in plan['beats']]})
        save('character_bible.json',plan['continuity_bible'])
    acquisition=acquisition or {}
    if not acquisition and (root/'assets/asset_acquisition.json').exists():
        acquisition=json.loads((root/'assets/asset_acquisition.json').read_text())
    ledger=root/'assets/image_prediction_ledger.json'
    predictions=json.loads(ledger.read_text()) if ledger.exists() else []
    estimated=sum(float(p.get('estimated_cost') or 0) for p in predictions)
    save('generation_cost_report.json',{'model_request_count':len(predictions),'accepted_prediction_count':sum(bool(p.get('prediction_id')) for p in predictions),
        'reserved_image_cost_usd':round(estimated,6),'actual_billed_usd':None,'scope':'Conservative reservations, including unknown outcomes. Vision/TTS/render costs excluded.',
        'items':predictions})
    save('asset_manifest.json',{'assets':[a.model_dump() for a in assets],'acquisition':acquisition})
    if edl is None and (root/'event_edl.json').exists():edl=json.loads((root/'event_edl.json').read_text())
    rows=(edl or {}).get('beats',[]);critical=[r for r in rows if r['criticality']=='P0']
    failures=[r['beat_id'] for r in rows if r['validation_status']!='passed']
    # A timeline gap is distinct from a semantic failure. Count uncovered action
    # intervals conservatively; report unknown when no bound EDL is available.
    action_seconds=sum(max(0,(r.get('audio_end_ms') or 0)-(r.get('visual_onset_ms') or r.get('audio_start_ms') or 0))/1000
        for r in critical if not r.get('render_coverage')) if rows else None
    report={'status':status or ('passed' if rows and not failures else 'needs_review'),
        'visual_coverage_percent':100*sum(r['validation_status']=='passed' for r in rows)/len(rows) if rows else None,
        'critical_event_coverage':sum(r['validation_status']=='passed' and r.get('render_coverage',False) for r in critical)/len(critical) if critical else None,
        'portrait_misuse_count':sum(r.get('semantic_review',{}).get('portraitSubstitution') is True for r in rows),
        'text_only_action_seconds':action_seconds,'text_only_measurement':'Conservative uncovered critical timeline duration, not pixel classification',
        'scene_repetition_violations':[r['beat_id'] for r in rows if any('identical image' in x for x in r.get('reasons',[]))],
        'missing_objects':[{'beat_id':r['beat_id'],'expected':r.get('object_ids',[]),'status':'unverified'} for r in rows if r.get('semantic_review',{}).get('objectsCorrect') is not True],
        'failed_validation':failures,'model_request_count':len(predictions),'image_cost_usd':round(estimated,6),
        'human_review_links':[r['rendered_frame'] for r in rows if r.get('rendered_frame')],
        'scope':'Probabilistic semantic review and timeline checks; no claim of anatomical certainty or verified billing.'}
    save('quality_report.json',report)
    return report


def enforce(edl):
    import config
    if (config.IMAGE_FAILURE_POLICY=='strict' or config.RENDER_BLOCK_ON_CRITICAL_VISUAL_FAILURE) and not edl['metrics']['p0_acceptance_passed']:
        raise NewsError('Critical visual QA failed; inspect quality_report.json and event_edl.json. Output is diagnostic, not complete.','needs_review')


def contact_sheet(video, output):
    """Persist every 1-fps sample plus a compact labeled sheet for human review."""
    import config
    from PIL import Image, ImageOps, ImageDraw
    root=Path(output);frames=root/'render_qa_frames';frames.mkdir(exist_ok=True)
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(video),'-vf',f'fps={config.VISUAL_QA_CONTACT_SHEET_FPS},scale=216:-1',str(frames/'%05d.jpg')],check=True,capture_output=True,timeout=180)
    paths=sorted(frames.glob('*.jpg'))
    if not paths:raise NewsError('Encoded video produced no QA samples')
    cols=8;w=216;h=408
    sheet=Image.new('RGB',(cols*w,math.ceil(len(paths)/cols)*h),'#eeeeee');draw=ImageDraw.Draw(sheet)
    for i,path in enumerate(paths):
        with Image.open(path) as im:sheet.paste(ImageOps.contain(im,(w,h-24)),((i%cols)*w,(i//cols)*h+24))
        draw.text(((i%cols)*w+6,(i//cols)*h+4),f'{i/config.VISUAL_QA_CONTACT_SHEET_FPS:.1f}s',fill='black')
    sheet.save(root/'render_contact_sheet.jpg',quality=88)
