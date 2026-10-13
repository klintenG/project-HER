"""Rebuild saved narration/assets without API calls; retain the original video.

python scripts/reference_parity_review.py --prepare-only
python scripts/reference_parity_review.py                 # render + evidence
"""
import argparse
import html
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent.editorial.models import Timeline
from agent.editorial.visuals import EditorialScript
from agent.editorial.director import Direction,VisualSettings,direct,save_summary
from agent.editorial.planner import build
from agent.editorial.render import render,stage
from agent.editorial.qa import activity




def evidence(before,after,out,duration):
    windows={'opening':[0,.5,1,2,3,4,5], 'conflict':[13,15,17,19,21], 'turn':[30,32,34,36,39],
             'ending':[max(0,duration-7+i) for i in range(7)]}
    for name,times in windows.items():
        sheet=Image.new('RGB',(180*len(times),700),'#fafafa');draw=ImageDraw.Draw(sheet)
        for row,path in enumerate([before,after]):
            for j,t in enumerate(times):
                raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(path),'-frames:v','1','-vf','scale=180:320','-f','image2pipe','-vcodec','png','-'])
                sheet.paste(Image.open(io.BytesIO(raw)),(180*j,350*row+25))
                draw.text((180*j+5,350*row+5),f'{"BEFORE" if row==0 else "AFTER"} {t:.1f}s',fill='#303035')
        sheet.save(out/(name+'.jpg'))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',default='output/editorial_fcb1866532dd45e8b16a77974c76f820/editorial_manifest.json')
    parser.add_argument('--output',default='output/reference_parity_v2')
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--report-only',action='store_true')
    args=parser.parse_args();source=Path(args.manifest);out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    old=Timeline.model_validate_json(source.read_text())
    visual=json.loads(source.with_name('visual_plan.json').read_text())
    script=EditorialScript.model_validate(visual['script'])
    settings=VisualSettings(editorialStyleVersion='reference-v2',allowPhraseTimingFallback=False)
    direction_path=source.with_name('visual_direction.json')
    direction=Direction.model_validate_json(direction_path.read_text()) if direction_path.exists() else direct(script,old.words,visual['sections'],settings=settings)
    master=next(a for a in old.audio if a.kind=='master')
    diagnostics={**old.diagnostics,'parityBaseline':str(source.resolve()),'verification':'Preserved exact recorded narration, word marks and asset hashes. No provider calls. Historical claims and illustrations have not been newly verified.'}
    m=build(script,old.words,old.sections,old.entities,old.assets,master.path,out,out.name,diagnostics,direction=direction,visual_settings=settings)
    save_summary(m,out);stage(m,out)
    print(f'Prepared {len(m.beats)} phrases, {m.diagnostics["referenceStoryboard"]["grammarCount"]} grammar families',flush=True)
    if args.prepare_only:return
    video=out/'editorial.mp4'
    if args.report_only:
        stats=json.loads((out/'editorial-metrics.json').read_text())['audio']
    else:video,stats=render(m,video)
    m.diagnostics['finalAudio']=stats
    (out/'editorial_manifest.json').write_text(m.model_dump_json(indent=2))
    before=source.with_name('editorial.mp4')
    evidence(before,video,out,m.durationInFrames/30)
    metrics={'before':activity(before),'after':activity(video),'encodedAudio':stats,'grammarCount':m.diagnostics['referenceStoryboard']['grammarCount'],
             'disclosures':[{'name':a.subject,'source':a.source,'license':a.license,'reconstruction':not a.factual,'notice':a.fallback} for a in m.assets]}
    reference=Path('enhancements/reference-ai-video.mp4')
    if reference.exists():metrics['reference']=activity(reference)
    (out/'comparison.json').write_text(json.dumps(metrics,indent=2))
    b=html.escape(os.path.relpath(before,out));a=html.escape(video.name)
    summary=json.dumps({k:{x:y for x,y in v.items() if x!='intervals'} for k,v in metrics.items() if k in ('before','after','reference')},indent=2)
    (out/'review.html').write_text(f'''<!doctype html><meta charset="utf-8"><title>Reference parity review</title>
<style>body{{font:16px system-ui;background:#eee;color:#303035;margin:32px}}.players{{display:flex;gap:24px}}video{{height:65vh;max-width:44vw}}img{{max-width:100%}}pre{{white-space:pre-wrap}}</style>
<h1>Zheng Yi Sao: preserved audio and assets, new choreography</h1>
<p>The baseline retains the original narration and artwork for a controlled comparison. Historical claims, modern-looking illustrations, and voice quality are not newly verified. Motion measurements are diagnostics, not artistic scores.</p>
<div class="players"><div><h2>Before</h2><video controls src="{b}"></video></div><div><h2>Reference v2</h2><video controls src="{a}"></video></div></div>
{''.join(f'<h2>{n}</h2><img src="{n}.jpg">' for n in ('opening','conflict','turn','ending'))}
<h2>Measurements</h2><pre>{html.escape(summary)}</pre><p>Asset sources, reconstruction disclosures and full measurements: <a href="comparison.json">comparison.json</a>.</p>''')
    print(video.resolve(),flush=True)

if __name__=='__main__':main()
