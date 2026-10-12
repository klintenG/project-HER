"""Rebuild layout from accepted visual cues/assets; no provider calls."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent.editorial.models import Timeline
from agent.editorial.visuals import EditorialScript
from agent.editorial.planner import build
from agent.editorial.render import render

out=Path(sys.argv[1]);old=Timeline.model_validate_json((out/'editorial_manifest.json').read_text())
visual=json.loads((out/'visual_plan.json').read_text());script=EditorialScript.model_validate(visual['script'])
plan=[]
for section in old.sections:
    beat=next(b for b in old.beats if section.id in b.sectionIds)
    phrase=next(l for l in old.layers if l.id in beat.layerIds and l.phrase and l.phrase.mode=='word_accumulate')
    plan.append({'sectionId':section.id,'template':beat.template,'purpose':beat.purpose,'setupWords':len(phrase.phrase.wordIds) if len(phrase.phrase.wordIds)<len(section.wordIds) else None,'emphasisWords':[]})
m=build(script,old.words,old.sections,old.entities,old.assets,old.audio[0].path,out,old.generationId,old.diagnostics,plan,old.subtitleMode,visual_cues=visual['sections'])
video,stats=render(m,out/'editorial.mp4');m.diagnostics.update(finalAudio=stats,outputs={'video':str(video.resolve()),'srt':str((out/'subtitles.srt').resolve()),'vtt':str((out/'subtitles.vtt').resolve())})
(out/'editorial_manifest.json').write_text(m.model_dump_json(indent=2))
print('Reframed and rendered',video,'assets',len(m.assets),'LUFS',stats['integratedLUFS'],'peak',stats['truePeakDBTP'],flush=True)
