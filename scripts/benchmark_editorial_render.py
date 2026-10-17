"""Paired real render benchmark, explicitly excluding remote generation latency."""
import argparse
import json
import math
import statistics
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import config
from agent.editorial.models import Timeline
from agent.editorial.render import render
from utils.job_trace import JobTrace


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--repeat',type=int,default=1)
    parser.add_argument('--mode',choices=['legacy','direct','both'],default='both');args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True);rows=[]
    for i in range(args.repeat):
        for mode in (['legacy','direct'] if args.mode=='both' else [args.mode]):
            config.EDITORIAL_DIRECT_BT709=mode=='direct'
            out=args.output/f'{i:02d}-{mode}';out.mkdir(exist_ok=True)
            m=Timeline.model_validate_json(args.manifest.read_text())
            trace=JobTrace(out/'job_trace.json',out.name)
            with trace.span('end_to_end',scope='render_only'):
                video,stats=render(m,out/'editorial.mp4',trace=trace)
            row={'iteration':i,'mode':mode,'scope':'render_only','video':str(video.resolve()),**stats['stageTimings']}
            rows.append(row);(args.output/'runs.json').write_text(json.dumps(rows,indent=2));print(row,flush=True)
    summaries={}
    for mode in sorted({r['mode'] for r in rows}):
        durations=sorted(r['renderAndQualitySeconds'] for r in rows if r['mode']==mode)
        summaries[mode]={'count':len(durations),'p50Seconds':statistics.median(durations),'p95Seconds':durations[math.ceil(.95*len(durations))-1]}
    (args.output/'summary.json').write_text(json.dumps({'scope':'local render only; not full generation or cloud latency','groups':summaries},indent=2))

if __name__=='__main__':main()
