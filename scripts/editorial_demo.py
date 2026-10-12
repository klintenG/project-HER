"""Reproduce the supplied baseline with v2; no research, LLM or paid calls.

python scripts/editorial_demo.py --fixture   # first two real narration sections
python scripts/editorial_demo.py             # complete, preserved approved script
"""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent.news_models import Manifest
from agent.editorial.audio import prepare_existing,normalize,subtitles
from agent.editorial.assets import acquire
from agent.editorial.planner import build
from agent.editorial.render import render,stage

def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',default='output/news_af1a95199a7245c687819d15b7c56e3a/news_manifest.json');p.add_argument('--fixture',action='store_true');p.add_argument('--prepare-only',action='store_true');p.add_argument('--output');args=p.parse_args()
    old=Manifest.model_validate_json(Path(args.manifest).read_text());script=old.script
    if args.fixture:
        ss=script.sentences[:2];used={i for s in ss for i in s.entity_ids}
        script=script.model_copy(update={'sentences':ss,'narration':' '.join(s.text for s in ss),'entities':[e for e in script.entities if e.id in used]})
    out=Path(args.output or ('output/reference_editorial_fixture' if args.fixture else 'output/reference_editorial_demo'));out.mkdir(parents=True,exist_ok=True)
    raw,words,sections,diagnostics=prepare_existing(script,old.audio,out/'audio')
    mix=out/'master.wav';diagnostics['loudness']=normalize(raw,mix)
    entities,assets=acquire(script,out/'assets',existing=old.assets)
    m=build(script,words,sections,entities,assets,mix,out,out.name,diagnostics)
    subtitles(words,out/'subtitles')
    props=stage(m,out)
    print('Prepared',out,m.durationInFrames/30,'seconds',len(words),'aligned words',flush=True)
    if not args.prepare_only:
        video,stats=render(m,out/'editorial.mp4')
        m.diagnostics.update(finalAudio=stats,outputs={'video':str(video.resolve()),'srt':str((out/'subtitles.srt').resolve()),'vtt':str((out/'subtitles.vtt').resolve())})
        (out/'editorial_manifest.json').write_text(m.model_dump_json(indent=2))
        (out/'image_credits.txt').write_text('\n\n'.join(f'{a.subject}\n{a.attribution}\n{a.source}\n{a.fallback or ""}' for a in assets))
        print(video,stats['integratedLUFS'],stats['truePeakDBTP'])

if __name__=='__main__':main()
