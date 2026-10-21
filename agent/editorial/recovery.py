"""Saved-media recovery; image, voice and vision providers are never invoked."""
import json
from pathlib import Path


def recover(job, render_video=True):
    from agent.editorial.visuals import EditorialScript
    from agent.editorial import assets as sourcing, sentence_storyboard as sb, event_storyboard as ev
    from agent.editorial import quality_artifacts as qa
    from agent.editorial import audio as sound
    from agent.editorial.planner import build, semantic_plan
    from agent.editorial.director import VisualSettings
    from agent.editorial.typography import integrate
    from agent.editorial.render import render
    from agent.news_models import Script, NewsError
    import config
    root=Path(job).resolve()
    data=json.loads((root/'visual_plan.json').read_text());script=EditorialScript.model_validate(data['script'])
    original=json.loads((root/'news_preview.json').read_text())
    approved=sb.segment(Script.model_validate(original['script']))
    ledger=json.loads((root/'assets/image_prediction_ledger.json').read_text())
    before=len(ledger)
    class NoGeneration:
        async def subject(self,*args,**kwargs):raise NewsError('Recovery requires saved images; paid generation is disabled.')
        scene_subject=subject;event_scene_subject=subject;identity_subject=subject;action_subject=subject;real_subject=subject
    def no_review(*args,**kwargs):raise NewsError('Remote review disabled during local recovery')
    diagnostics={}
    if config.IMAGE_FAILURE_POLICY!='deliver_with_warnings':
        raise NewsError('Local delivery recovery requires IMAGE_FAILURE_POLICY=deliver_with_warnings')
    entities,assets=sourcing.acquire(script,root/'assets',asset_mode='ai',image_generator=NoGeneration(),visual_review=no_review,diagnostics=diagnostics)
    ev.validate_assets(script,assets,diagnostics['assetAcquisition'])
    # Speech chunks are authoritative: never regenerate narration or guess its split.
    groups=list((root/'narration_attempts').glob('*/**/audio/narration_0.wav'))
    clips=None
    for first in sorted(groups,key=lambda p:p.stat().st_mtime,reverse=True):
        candidate=[first.parent/f'narration_{i}.wav' for i in range(len(approved.sentences))]
        if all(p.is_file() for p in candidate):clips=candidate;break
    if clips is None:raise NewsError('Complete saved speech chunks unavailable; no paid narration requested')
    raw,words,sections,audio_diag=sound.assemble(approved,clips,root/'audio',gap=0)
    words,sections=ev.bind_audio(script,words)
    diagnostics.update(audio_diag,recovery={'paid_requests':0,'saved_predictions':before,'source':'saved images and per-sentence narration only'})
    master=root/'recovered-master.wav';sound.normalize(raw,master)
    settings=VisualSettings.configured();direction=sb.direction(script)
    plan=semantic_plan(script,None,diagnostics)
    manifest=build(script,words,sections,entities,assets,master,root,root.name,diagnostics,plan,'editorial',visual_cues=data['sections'],direction=direction,visual_settings=settings)
    manifest=integrate(manifest,script)
    manifest.warnings.append('Recovered from paid saved media. Some scenes did not pass semantic/cutout review; inspect quality_report.json. No new generation calls.')
    edl=ev.save_report(script,assets,diagnostics['assetAcquisition'],words,root,manifest)
    qa.write(root,script,assets,diagnostics['assetAcquisition'],edl,status='renderable_with_warnings')
    path=root/'recovered_manifest.json';path.write_text(manifest.model_dump_json(indent=2))
    sound.subtitles(words,root/'recovered-subtitles')
    if render_video:
        video,stats=render(manifest,root/'recovered.mp4')
        qa.contact_sheet(video,root)
        qa.write(root,script,assets,diagnostics['assetAcquisition'],edl,status='delivered_with_warnings')
        (root/'recovery_result.json').write_text(json.dumps({'success':True,'video':str(video),'paid_requests':0,'quality':'needs_review','audio':stats},indent=2))
    assert len(json.loads((root/'assets/image_prediction_ledger.json').read_text()))==before
    return path

