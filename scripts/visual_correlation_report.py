"""Summarize actual persisted event, provider, render and review evidence."""
import argparse
import json
import subprocess
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('output/visual_correlation'));args=p.parse_args()
    root=args.root.resolve();summaries=[];tables=[]
    for name in ['thor_curated','history','comedy']:
        folder=root/name
        if not (folder/'event_edl.json').exists():continue
        edl=json.loads((folder/'event_edl.json').read_text());acq=json.loads((folder/'assets/asset_acquisition.json').read_text())
        runs=[*acq.get('previousRuns',[]),acq]
        predictions=[r for run in runs for r in run.get('providerMetrics',{}).get('predictionRecords',[])]
        unique={r.get('prediction_id'):r for r in predictions if r.get('prediction_id')}
        manifest=json.loads((folder/'editorial_manifest.json').read_text()) if (folder/'editorial_manifest.json').exists() else {}
        delivery=manifest.get('diagnostics',{}).get('finalAudio',{})
        metrics={**edl['metrics'],'provider_predictions':len(unique),'scene_generation_predictions':sum('-candidate' in str(r.get('target_path','')) for r in unique.values()),'identity_generation_predictions':sum('-identity' in str(r.get('target_path','')) for r in unique.values()),'sum_provider_task_wait_seconds':round(sum(float(r.get('total_provider_wait_seconds') or 0) for r in unique.values()),3),'rate_limit_responses':sum(run.get('providerMetrics',{}).get('rateLimitResponses',0) for run in runs),
            'reported_billed_cost_usd':None,'cost_note':'Provider billing receipt unavailable; configured adapter estimates are not actual billed costs.',
            'render_and_quality_seconds':delivery.get('stageTimings',{}).get('renderAndQualitySeconds'),'encoded_lufs':delivery.get('integratedLUFS'),'encoded_true_peak_dbtp':delivery.get('truePeakDBTP'),'black_frame_check':delivery.get('visualQuality',{}).get('passed'),'story_last_word_sec':manifest.get('words',[{}])[-1].get('end'),'outro_starts_sec':manifest.get('durationInFrames',0)/manifest.get('fps',30),'video':str(folder/'editorial.mp4'),'edl':str(folder/'event_edl.json'),'contact_sheet':str(folder/'contact_sheet.jpg'),'review_page':str(folder/'review.html')}
        if (folder/'editorial.mp4').exists():
            media=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type,width,height,r_frame_rate','-of','json',str(folder/'editorial.mp4')]))
            metrics['media']=media
        deltas=[abs(b['render_onset_delta_ms']) for b in edl['beats'] if b['render_onset_delta_ms'] is not None]
        metrics['max_compiled_onset_delta_ms']=max(deltas) if deltas else None
        summaries.append({'story':name,**metrics})
        lines=[f'## {name}', '', '| Spoken event | Audio interval | Before | Chosen scene | Review |', '|---|---|---|---|---|']
        for b in edl['beats']:
            clean=lambda s:str(s).replace('|','/').replace('\n',' ')
            before='Generic/reused character fallback in supplied Thor baseline' if name=='thor_curated' else 'Independent regression narrative'
            lines.append(f'| {clean(b["narration_excerpt"])} | {b["audio_start_ms"]/1000:.3f}–{b["audio_end_ms"]/1000:.3f}s; visual @{b.get("visual_onset_ms",b["audio_start_ms"])/1000:.3f}s | {before} | {clean(b["visual_intent"])} (`{b["asset_id"]}`) | {clean(b["validation_status"])} |')
        tables.append('\n'.join(lines))
    (root/'quality_metrics.json').write_text(json.dumps(summaries,indent=2))
    text='# ProjectHER visual correlation evidence\n\nCurated acceptance plans, real generated/retrieved images, actual speech and Remotion outputs. Gemini authentication returned HTTP 401; the user explicitly chose manual review. These renders do not certify the blocked autonomous live planner. Manual observations are stored with image checksums; encoded-frame review is recorded separately.\n\n'
    text+='| Story | Beats | Accepted | Meaningful coverage | Max compiled onset delta | P0 gate |\n|---|---:|---:|---:|---:|---|\n'
    for s in summaries:text+=f'| {s["story"]} | {s["beats"]} | {s["accepted_beats"]} | {s["meaningful_coverage"]:.0%} | {s["max_compiled_onset_delta_ms"]} ms | {s["p0_acceptance_passed"]} |\n'
    text+='\n[Thor video](thor_curated/editorial.mp4) · [before/after contact sheet](thor_curated/before_after_contact_sheet.jpg) · [Thor review page](thor_curated/review.html) · [history video](history/editorial.mp4) · [comedy video](comedy/editorial.mp4)\n\nCompiled onset deltas measure frame entry against the exact selected action/prop anchors in the audio-derived word timestamps. The opening image has a deliberate 60 ms pre-roll. They do not independently measure acoustic onset error. Full-image/phone-scale manual review, source provenance, story coverage and final narration/outro coverage remain separate evidence.\n\n'+'\n\n'.join(tables)
    (root/'BEFORE_AFTER.md').write_text(text)
    print(root/'BEFORE_AFTER.md');print(root/'quality_metrics.json')

if __name__=='__main__':main()
