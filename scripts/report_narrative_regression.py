"""Summarize recorded regressions without equating asset QA with video acceptance."""
import argparse
import json
from collections import defaultdict
from pathlib import Path


def report(directory):
    manifest=json.loads((directory/'editorial_manifest.json').read_text())
    diagnostics=manifest.get('diagnostics',{})
    plan=diagnostics.get('narrativeBeatPlan',{})
    assets={a['entityId']:a for a in manifest.get('assets',[])}
    acquisition=diagnostics.get('assetAcquisition',{})
    records={r['entityId']:r for r in acquisition.get('assets',[])}
    trace=json.loads((directory/'job_trace.json').read_text())
    stages=defaultdict(list)
    for span in trace.get('spans',[]):
        if 'duration_seconds' in span:stages[span['name']].append(span['duration_seconds'])
    return {'directory':str(directory),'scope':'Recorded-narration visual pipeline; excludes original input/research/script/TTS/upload',
        'wallSeconds':trace['elapsed_seconds'],'assetQuality':diagnostics.get('narrativeQuality'),
        'finalVideoManualAcceptance':'pending','providerMetrics':acquisition.get('providerMetrics'),
        'stageSpans':{name:{'count':len(values),'sumSeconds':sum(values),'maxSeconds':max(values)} for name,values in stages.items()},
        'stageWarning':'Nested and parallel span sums are not job wall time.',
        'beats':[{'id':b['id'],'text':b['text'],'startMs':b.get('start_ms'),'endMs':b.get('end_ms'),
            'verb':b['verb'],'decision':b['decision'],'assetIds':b['asset_ids'],
            'sources':[assets[eid]['source'] for eid in b['asset_ids'] if eid in assets],
            'reviews':[{key:records.get(eid,{}).get('generation',{}).get(key) for key in ('actionReview','continuityReview')} for eid in b['asset_ids']],
            'degradedReason':b.get('degraded_reason')} for b in plan.get('beats',[]) if b['required_action_visible']]}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('directories',type=Path,nargs='+');parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.write_text(json.dumps([report(d) for d in args.directories],indent=2))

if __name__=='__main__':main()
