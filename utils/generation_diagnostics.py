"""Sanitized, overlap-aware handoff reports; private artifact publication is separate."""
from datetime import datetime
import json
import os
import resource
import shutil
import sys
import tempfile
from pathlib import Path


def _read(path, default):
    try:return json.loads(path.read_text())
    except (OSError, ValueError):return default


def _epoch(value):
    return datetime.fromisoformat(value).timestamp()


def _sanitize_text(text, max_len=140):
    if not isinstance(text, str):return ''
    import re
    cleaned=re.sub(r'https?://\S+','[url]',text)
    cleaned=re.sub(r'(?:Bearer\s+|r8_|sk-|AIza)[A-Za-z0-9_\-.]+','[redacted]',cleaned)
    cleaned=re.sub(r'/[A-Za-z0-9_.\-/]+','[path]',cleaned)
    cleaned=' '.join(cleaned.split())
    return cleaned[:max_len]


def _sanitize_obj(value):
    if isinstance(value, str):
        return _sanitize_text(value, 240)
    if isinstance(value, list):
        return [_sanitize_obj(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _sanitize_obj(v) for k, v in value.items() if k not in ('outputPath', 'path', 'originalPath')}
    return value


def export_reports(directory, job_id, outcome=None):
    import config
    directory=Path(directory);spans=[];traces=[]
    for name in ('job_trace.json','portfolio_trace.json'):
        trace=_read(directory/name,{})
        if trace:
            traces.append(trace)
            for span in trace.get('spans',[]):spans.append({**span,'trace_file':name})
    finished=[s for s in spans if 'end_utc' in s]
    start=min((_epoch(s['start_utc']) for s in spans),default=0)
    end=max((_epoch(s['end_utc']) for s in finished),default=start)
    e2e_spans=[s for s in finished if s['name'] in ('end_to_end','worker_end_to_end') and s.get('duration_seconds')]
    offset_spans=[s for s in finished if s.get('start_offset_seconds') is not None and s.get('end_offset_seconds') is not None]
    if e2e_spans:
        total_wall=max(float(s['duration_seconds']) for s in e2e_spans)
    elif offset_spans and len(traces)==1:
        total_wall=max(0.,max(float(s['end_offset_seconds']) for s in offset_spans)-min(float(s['start_offset_seconds']) for s in offset_spans))
    else:
        total_wall=max(0.,end-start)

    manifest=_read(directory/'editorial_manifest.json',{})
    acquisition=_read(directory/'assets'/'asset_acquisition.json',{})
    storyboard=_read(directory/'sentence_storyboard.json',[])
    visual_plan=_read(directory/'visual_plan.json',{})
    failure=_read(directory/'editorial_failure.json',{})
    diag=manifest.get('diagnostics',{}) if isinstance(manifest,dict) else {}
    if not storyboard and isinstance(visual_plan,dict):
        storyboard=(visual_plan.get('script') or {}).get('sentence_storyboard') or []
    sentence_quality=diag.get('sentenceQuality',{}) or (visual_plan.get('diagnostics') or {}).get('sentenceQuality',{})
    stage_timings=diag.get('stageTimings',{})
    media_timings=diag.get('mediaTimings',{})
    render_timings=(diag.get('finalAudio') or {}).get('stageTimings',{})
    provider_metrics=acquisition.get('providerMetrics',{})
    prediction_records=_sanitize_obj(acquisition.get('predictionRecords',[]))
    from utils.cost_tracking import summarize_model_usage_and_costs
    cost_report=acquisition.get('costReport') or diag.get('costReport') or summarize_model_usage_and_costs(acquisition.get('predictionRecords',[]),acquisition.get('assets',[]))
    narration_settings=diag.get('narrationSettings',{})
    tts_telemetry=_sanitize_obj(narration_settings.get('sentenceTelemetry',[]))

    trace_provenance='genuine_live_trace' if spans else ('reconstructed_from_saved_manifest_and_audit' if (manifest or acquisition) else 'empty')
    if total_wall<=0 and stage_timings.get('end_to_end'):
        total_wall=float(stage_timings['end_to_end'])

    # Concurrency analysis over image_provider_wait and image_task spans
    wait_spans=[s for s in finished if s['name']=='image_provider_wait']
    task_spans=[s for s in finished if s['name'] in ('image_task','new_action_asset_generation','entity_identity_asset_generation')]
    use_offsets=bool(offset_spans and len(traces)==1)
    def _span_bounds(s):
        if use_offsets and s.get('start_offset_seconds') is not None and s.get('end_offset_seconds') is not None:
            return float(s['start_offset_seconds']),float(s['end_offset_seconds'])
        return _epoch(s['start_utc']),_epoch(s['end_utc'])
    events=sorted([(b[0],1) for s in wait_spans for b in (_span_bounds(s),)]+[(b[1],-1) for s in wait_spans for b in (_span_bounds(s),)])
    concurrent=peak=0;weighted_concurrency=0.;prev_t=events[0][0] if events else 0.
    active_window=0.
    for t,delta in events:
        if concurrent>0 and t>prev_t:
            dt=t-prev_t
            weighted_concurrency+=concurrent*dt
            active_window+=dt
        concurrent+=delta
        peak=max(peak,concurrent)
        prev_t=t
    if peak==0 and provider_metrics.get('peakProviderConcurrency'):
        peak=int(provider_metrics['peakProviderConcurrency'])
    avg_concurrency=round(weighted_concurrency/active_window,3) if active_window>0 else (1.0 if peak==1 else 0.0)

    intervals=sorted(_span_bounds(s) for s in finished if s['name'] not in ('end_to_end','worker_end_to_end'))
    base_start=min((a for a,_ in intervals),default=0.) if use_offsets else start
    covered=0.;last=base_start;serial_gaps=0.
    for a,b in intervals:
        if a>last and last>base_start:serial_gaps+=a-last
        covered+=max(0.,b-max(a,last))
        last=max(last,b)
    if covered<=0 and total_wall>0 and not spans:
        covered=total_wall

    # Per-entity span lookup for image-level timings
    wait_by_entity={}
    for s in wait_spans:
        eid=(s.get('metadata') or {}).get('entity_id')
        if eid:wait_by_entity.setdefault(eid,[]).append(s)
    queue_by_entity={}
    for s in finished:
        if s['name']=='image_task':
            eid=(s.get('metadata') or {}).get('entity_id')
            if eid:queue_by_entity[eid]=(s.get('metadata') or {}).get('queue_wait_seconds',0.)
    bg_spans=[s for s in finished if s['name']=='background_removal_and_alpha']
    total_bg_seconds=round(sum(s.get('duration_seconds',0.) for s in bg_spans),4)
    if total_bg_seconds<=0:
        total_bg_seconds=round(sum(float(r.get('cutoutProcessingSeconds',0) or 0) for r in acquisition.get('assets',[])),4)
    admission_spans=[s for s in finished if s['name']=='image_provider_admission']
    total_admission_seconds=round(sum(s.get('duration_seconds',0.) for s in admission_spans),4)

    beat_by_entity={b.get('primary_entity_id'):b for b in storyboard if isinstance(b,dict)}
    rendered_asset_ids={l.get('assetId') for l in manifest.get('layers',[]) if isinstance(l,dict) and l.get('assetId')}

    images=[]
    for idx,row in enumerate(acquisition.get('assets',[])):
        eid=row.get('entityId','')
        beat=beat_by_entity.get(eid,{})
        waits=wait_by_entity.get(eid,[])
        row_preds=row.get('predictionRecords',[]) or []
        api_sec=round(sum(w.get('duration_seconds',0.) for w in waits),4) or round(float(row.get('apiWaitSeconds',0.) or 0.),4)
        total_sec=round(float(row.get('durationSeconds',api_sec or 0.)),4)
        q_wait=round(float(queue_by_entity.get(eid,0.)),4)
        cut_sec=round(float(row.get('cutoutProcessingSeconds',0.) or 0.),4)
        rev_sec=round(float(row.get('visualReviewSeconds',0.) or 0.),4)
        adm_sec=round(float(row.get('admissionWaitSeconds',0.) or 0.),4)
        proc_sec=round(max(0.,total_sec-api_sec),4)
        asset_id=row.get('assetId')
        displayed=bool(asset_id and asset_id in rendered_asset_ids) if rendered_asset_ids else (beat.get('render_visibility')=='passed')
        attempts=max(int(row.get('attemptCount',0) or 0),len(waits),len(row_preds),1+len(row.get('rejectedAttempts',[])),1)
        images.append({
            'task_index':idx+1,
            'entityId':eid,
            'assetId':asset_id,
            'sentence_id':row.get('sentenceId') or beat.get('sentence_id','shared_identity'),
            'role':row.get('role','primary' if eid.startswith('scene-') else 'identity_or_secondary'),
            'primary_subject_type':row.get('primarySubjectType') or beat.get('primary_subject_type'),
            'visual_concept':_sanitize_text(beat.get('visual_focus') or row.get('name',''),80),
            'provider':row.get('provider') or (waits[-1].get('metadata',{}).get('model') if waits else 'local_or_cache'),
            'request_start_utc':waits[0]['start_utc'] if waits else (row_preds[0].get('http_request_start_timestamp') or row_preds[0].get('requestStartUtc') if row_preds else None),
            'request_end_utc':waits[-1]['end_utc'] if waits else (row_preds[-1].get('prediction_completion_timestamp') or row_preds[-1].get('requestEndUtc') if row_preds else None),
            'queue_wait_seconds':q_wait,
            'admission_wait_seconds':adm_sec,
            'api_duration_seconds':api_sec,
            'cutout_processing_seconds':cut_sec,
            'visual_review_seconds':rev_sec,
            'processing_and_review_seconds':proc_sec,
            'durationSeconds':total_sec,
            'attempts':attempts,
            'rejected_attempts':len(row.get('rejectedAttempts',[])),
            'recorded_errors':len(row.get('errors',[])),
            'cacheHit':bool(row.get('cacheHit',False)),
            'route':row.get('route','ready'),
            'identityReferences':row.get('identityReferences',[]),
            'dimensions':[row.get('width'),row.get('height')],
            'bytes':row.get('bytes'),
            'sha256':row.get('sha256') or (row.get('generation') or {}).get('sha256'),
            'displayed_in_render':displayed,
            'origin':'reused_or_cached' if row.get('cacheHit') else 'generated',
            'prediction_records':_sanitize_obj(row_preds),
        })

    fps=manifest.get('fps',30) if manifest else 30
    # Scene-level visual storyboard report (Part 10)
    scene_report=[]
    for idx,beat in enumerate(storyboard):
        if not isinstance(beat,dict):continue
        st=beat.get('start_time');et=beat.get('end_time')
        mid_t=round((float(st)+float(et))/2.0,3) if isinstance(st,(int,float)) and isinstance(et,(int,float)) else None
        mid_frame=round(mid_t*fps) if mid_t is not None else None
        scene_report.append({
            'sentence_number':idx+1,
            'sentence_id':beat.get('sentence_id'),
            'narration_text':_sanitize_text(beat.get('narration_text',''),180),
            'visual_focus':_sanitize_text(beat.get('visual_focus',''),100),
            'main_action':_sanitize_text(beat.get('main_action') or beat.get('action',''),80),
            'important_object':_sanitize_text(beat.get('important_object',''),80),
            'primary_subject_type':beat.get('primary_subject_type','event'),
            'primary_entity_id':beat.get('primary_entity_id'),
            'primary_asset_id':beat.get('primary_asset_id'),
            'primary_asset_sha256':beat.get('primary_asset_sha256'),
            'primary_asset_origin':beat.get('primary_asset_origin'),
            'primary_asset_is_distinct':bool(beat.get('primary_asset_is_distinct')),
            'perceptual_dhash':beat.get('perceptual_dhash'),
            'reused_character_ids':beat.get('continuity_references',[]),
            'secondary_entity_ids':beat.get('secondary_entity_ids',[]),
            'composition_type':beat.get('composition_type','layered_cutout'),
            'start_time':st,
            'end_time':et,
            'start_frame':beat.get('start_frame'),
            'end_frame':beat.get('end_frame'),
            'representative_midpoint_seconds':mid_t,
            'representative_midpoint_frame':mid_frame,
            'rendered_layer_id':beat.get('rendered_layer_id'),
            'rendered_bounds':beat.get('rendered_bounds'),
            'asset_generation_status':beat.get('asset_generation_status'),
            'asset_relevance_status':beat.get('asset_relevance_status'),
            'asset_status':beat.get('asset_status'),
            'render_visibility':beat.get('render_visibility','pending'),
        })

    sentences_count=sentence_quality.get('narrationSentences') or len(storyboard) or len(manifest.get('sections',[]))
    distinct_primaries=sentence_quality.get('distinctPrimaryVisuals') or sum(b.get('primary_asset_is_distinct') is True for b in storyboard)
    if not storyboard and images:
        distinct_primaries=len({i.get('sha256') or i.get('assetId') for i in images if i.get('assetId')})
    rendered_primaries=sentence_quality.get('primaryAssetsInRender') or sum(b.get('render_visibility')=='passed' for b in storyboard)
    if not storyboard and images:
        rendered_primaries=sum(1 for i in images if i.get('displayed_in_render'))
    reused_secondary=sentence_quality.get('reusedSecondaryAssets') or len({eid for b in storyboard for eid in b.get('secondary_entity_ids',[])})
    visual_metrics={
        'sentences':sentences_count,
        'storyboard_visual_beats':len(storyboard),
        'planned_primaries':sentence_quality.get('plannedPrimaryVisuals') or len(storyboard),
        'generated_assets':len(images),
        'distinct_primaries':distinct_primaries,
        'reused_secondary_assets':reused_secondary,
        'rendered_primaries':rendered_primaries,
        'sentences_without_distinct_primary':max(0,sentences_count-distinct_primaries),
        'images_rejected_for_duplication':sentence_quality.get('imagesRejectedForDuplication',0),
        'image_generation_failures':sentence_quality.get('imageGenerationFailures',sum(i['recorded_errors'] for i in images)),
        'fallback_attempts':sentence_quality.get('fallbackAttempts',0),
        'scene_relevance_failures':sentence_quality.get('sceneRelevanceFailures',0),
        'invariant_planned_ge_sentences':bool(sentences_count>0 and len(storyboard)>=sentences_count),
        'invariant_distinct_ge_sentences':bool(sentences_count>0 and distinct_primaries>=sentences_count),
        'invariant_rendered_eq_sentences':bool(sentences_count>0 and rendered_primaries>=sentences_count),
        'acceptance_passed':bool(sentence_quality.get('acceptancePassed',False)),
    }

    # Critical path & bottleneck ranking
    top_spans=[s for s in finished if s['name'] not in ('end_to_end','worker_end_to_end','image_task','image_provider_wait','image_provider_admission','background_removal_and_alpha')]
    top_spans.sort(key=lambda s:_epoch(s['start_utc']))
    critical_chain=[]
    cursor=start
    for s in top_spans:
        s_start=_epoch(s['start_utc']);s_end=_epoch(s['end_utc'])
        if s_end>cursor+0.001:
            critical_chain.append({'stage':s['name'],'duration_seconds':round(s['duration_seconds'],4),'effective_advance_seconds':round(s_end-max(cursor,s_start),4),'status':s['status']})
            cursor=max(cursor,s_end)
    if not critical_chain and finished:
        for s in sorted(finished,key=lambda s:_epoch(s['start_utc'])):
            if s['name'] not in ('end_to_end','worker_end_to_end'):
                critical_chain.append({'stage':s['name'],'duration_seconds':round(s['duration_seconds'],4),'effective_advance_seconds':round(s['duration_seconds'],4),'status':s['status']})
    if len(critical_chain)<=1 and stage_timings:
        critical_chain=[]
        for stage_key,label in [
            ('resolve','input_fetch_and_extract'),
            ('research','research'),
            ('script','research_or_script_generation'),
            ('semantic_beat_planning','semantic_beat_planning'),
            ('media','parallel_media_tts_and_cutouts'),
            ('timeline','timeline_planning'),
            ('compose','render_and_delivery'),
        ]:
            val=stage_timings.get(stage_key)
            if isinstance(val,(int,float)) and val>0:
                critical_chain.append({'stage':label,'duration_seconds':round(float(val),4),'effective_advance_seconds':round(float(val),4),'status':'succeeded'})

    # Bottleneck contributors
    candidates=[]
    def _add_candidate(name,dur,cause,evidence_str,opportunity):
        if dur and dur>0:
            candidates.append({
                'operation':name,
                'duration_seconds':round(float(dur),4),
                'percent_of_wall_time':round(min(100.,100.*float(dur)/total_wall),1) if total_wall>0 else 0.,
                'cause_category':cause,
                'evidence':evidence_str,
                'optimization_opportunity':opportunity,
                'confidence':'high',
            })
    span_by_name={}
    for s in finished:span_by_name.setdefault(s['name'],[]).append(s)
    for sname,cause,opp in [
        ('queue_wait','queue','Reduce queue contention or scale worker concurrency if queue wait dominates'),
        ('input_fetch_and_extract','network','Cache fetched source text or streamline input classification'),
        ('research','network','Bound web search pages and HTTP timeouts'),
        ('research_or_script_generation','provider','Reduce LLM repair iterations and token output size'),
        ('TTS_generation','provider','Overlap TTS with visual planning/sourcing and use dedicated TTS admission scope'),
        ('semantic_beat_planning','provider','Single-pass structured storyboard generation with strict schema validation'),
        ('entity_identity_asset_generation','provider','Acquire identity references in parallel or reuse supporting cutouts'),
        ('new_action_asset_generation','provider','Bounded parallel scene generation with adaptive Replicate admission pacing'),
        ('background_removal_and_alpha','compute','Reuse warm ONNX rembg session and run cutout trimming as each image completes'),
        ('sentence_asset_validation','provider','Batch ordered primary cutouts into a single multimodal diversity check'),
        ('word_forced_alignment','compute','Persist forced-alignment cache across runs and downsample in-memory'),
        ('render_and_delivery','compute','Use hardware-tuned Remotion concurrency and single-pass audio measurement'),
        ('result_upload','network','Stream upload directly with bounded chunk size'),
    ]:
        items=span_by_name.get(sname,[])
        if items:
            dur=sum(x.get('duration_seconds',0.) for x in items) if sname not in ('new_action_asset_generation','entity_identity_asset_generation','image_provider_wait') else max(x.get('duration_seconds',0.) for x in items)
            total_acc=sum(x.get('duration_seconds',0.) for x in items)
            _add_candidate(sname,dur,cause,f'{len(items)} span(s), max={max(x.get("duration_seconds",0.) for x in items):.3f}s, accumulated={total_acc:.3f}s',opp)
    if not candidates and stage_timings:
        if media_timings.get('cutoutsSeconds'):
            _add_candidate('cutout_acquisition_and_matting',media_timings['cutoutsSeconds'],'provider','Recorded in manifest mediaTimings','Parallelize scene primary generation and decouple admission pacing')
        if media_timings.get('speechSeconds'):
            _add_candidate('TTS_generation',media_timings['speechSeconds'],'provider','Recorded in manifest mediaTimings','Decouple TTS admission scope from image generation')
        if stage_timings.get('compose'):
            _add_candidate('render_and_delivery',stage_timings['compose'],'compute','Recorded in manifest stageTimings','Single-pass audio loudness measurement and pre-headroom normalization')
    if wait_spans:
        _add_candidate('image_provider_wait (accumulated)',sum(x.get('duration_seconds',0.) for x in wait_spans),'provider',
            f'{len(wait_spans)} provider call(s), peak_concurrency={peak}, admission_wait={total_admission_seconds:.2f}s',
            'Overlap independent scene-primary predictions across worker threads while respecting rate limits')
    candidates.sort(key=lambda c:c['duration_seconds'],reverse=True)

    # Sanitized errors & retries
    error_records=[]
    for s in spans:
        if s.get('status')=='failed' or s.get('error_type'):
            error_records.append({'source':'span','name':s['name'],'error_type':s.get('error_type','Error'),'attempt':(s.get('metadata') or {}).get('attempt',1)})
    for img in images:
        if img['rejected_attempts'] or img['recorded_errors']:
            error_records.append({'source':'image_asset','entity_id':img['entityId'],'sentence_id':img['sentence_id'],
                'rejected_attempts':img['rejected_attempts'],'recorded_errors':img['recorded_errors'],'route':img['route']})
    if failure:
        error_records.append({'source':'pipeline_failure','stage':failure.get('stage'),'status':failure.get('status')})

    root=next((s for s in reversed(spans) if s['name'] in ('worker_end_to_end','end_to_end')), {})
    resolved_outcome=outcome or root.get('status') or ('failed' if failure else 'succeeded' if manifest else 'unknown')
    video_frames=manifest.get('durationInFrames',0) if manifest else 0
    video_path=directory/'editorial.mp4'
    output_bytes=video_path.stat().st_size if video_path.is_file() else None

    runtime_info={
        'environment':'cloud_run' if os.getenv('K_SERVICE') else 'local',
        'python_version':sys.version.split()[0],
        'service':os.getenv('K_SERVICE','local_process'),
        'revision':os.getenv('K_REVISION','local'),
        'commit':os.getenv('HER_BUILD_COMMIT','working_tree'),
        'region':os.getenv('GOOGLE_CLOUD_REGION') or os.getenv('CLOUD_RUN_REGION') or 'unspecified',
        'configured_action_workers':getattr(config,'EDITORIAL_ACTION_WORKERS',1),
        'configured_remotion_concurrency':render_timings.get('remotionConcurrency') or os.getenv('HER_REMOTION_CONCURRENCY','default'),
        'process_peak_rss_native_units':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'trace_runtimes':[t.get('runtime',{}) for t in traces],
    }
    remotion_sec=render_timings.get('remotionRenderSeconds') or render_timings.get('remotionSeconds')
    rendering_info={
        'renderer':'remotion',
        'frames':video_frames,
        'fps':fps,
        'resolution':[manifest.get('width',1080),manifest.get('height',1920)] if manifest else [1080,1920],
        'asset_staging_seconds':render_timings.get('assetStagingSeconds'),
        'remotion_render_seconds':remotion_sec,
        'remotion_concurrency':render_timings.get('remotionConcurrency'),
        'ffmpeg_encode_seconds':render_timings.get('ffmpegEncodeSeconds'),
        'audio_delivery_seconds':render_timings.get('audioDeliverySeconds'),
        'visual_quality_scan_seconds':render_timings.get('visualQualityScanSeconds'),
        'total_render_and_qa_seconds':render_timings.get('renderAndQualitySeconds') or stage_timings.get('Remotion_and_FFmpeg') or stage_timings.get('compose'),
        'video_encode_passes':render_timings.get('videoEncodePasses'),
        'average_fps_throughput':round(video_frames/remotion_sec,2) if remotion_sec else None,
        'output_size_bytes':output_bytes,
    }
    tts_spans=[s for s in finished if s['name'] in ('TTS_generation','tts_generation_and_alignment')]
    vis_spans=[s for s in finished if s['name'] in ('semantic_beat_planning','cutout_acquisition_and_matting','entity_identity_asset_generation','new_action_asset_generation','image_task')]
    span_speech_sec=round(sum(s.get('duration_seconds',0.) for s in tts_spans),3) if tts_spans else None
    span_cutouts_sec=round(max(_epoch(s['end_utc']) for s in vis_spans)-min(_epoch(s['start_utc']) for s in vis_spans),3) if vis_spans else None
    span_overlap_sec=0.
    if tts_spans and vis_spans:
        t0=min(_epoch(s['start_utc']) for s in tts_spans);t1=max(_epoch(s['end_utc']) for s in tts_spans)
        v0=min(_epoch(s['start_utc']) for s in vis_spans);v1=max(_epoch(s['end_utc']) for s in vis_spans)
        span_overlap_sec=round(max(0.,min(t1,v1)-max(t0,v0)),3)
    speech_wall=media_timings.get('actualSpeechSeconds') or media_timings.get('speechSeconds') or span_speech_sec
    cutouts_wall=media_timings.get('cutoutsSeconds') or span_cutouts_sec
    overlap_wall=media_timings.get('overlapSeconds',span_overlap_sec)
    if isinstance(media_timings.get('actualSpeechSeconds'),(int,float)) and isinstance(cutouts_wall,(int,float)):
        overlap_wall=round(max(float(overlap_wall or 0.),min(float(media_timings['actualSpeechSeconds']),float(cutouts_wall))),3)
    concurrency_info={
        'total_image_tasks':len(images),
        'total_provider_wait_spans':len(wait_spans),
        'peak_image_provider_concurrency':peak,
        'average_active_image_concurrency':avg_concurrency,
        'configured_action_workers':acquisition.get('actionWorkers',getattr(config,'EDITORIAL_ACTION_WORKERS',1)),
        'tts_visual_overlap_seconds':overlap_wall,
        'speech_wall_seconds':speech_wall,
        'cutouts_wall_seconds':cutouts_wall,
        'alignment_seconds':stage_timings.get('word_forced_alignment'),
        'serial_gap_seconds':round(serial_gaps,4),
        'admission_wait_seconds':round(float(provider_metrics.get('admissionWaitSeconds',total_admission_seconds)),4),
        'rate_limit_responses':provider_metrics.get('rateLimitResponses',0),
        'rate_limit_backoff_seconds':provider_metrics.get('backoffSeconds',0),
        'background_removal_total_seconds':total_bg_seconds,
    }

    recommendations=[]
    if provider_metrics.get('rateLimitResponses',0)>0:
        recommendations.append('Replicate returned HTTP 429 rate-limit responses; increase account credit tier or adjust HER_EDITORIAL_IMAGE_MIN_INTERVAL / NEWS_REPLICATE_MIN_INTERVAL.')
    if (render_timings.get('videoEncodePasses') or 2)>1:
        recommendations.append('Remotion output is re-encoded by FFmpeg for BT.601->BT.709 color conversion (2 encode passes). Validate HER_EDITORIAL_DIRECT_BT709=1 on target runtime to use -c:v copy.')
    if any(i['rejected_attempts']>0 for i in images):
        recommendations.append('Multimodal visual review rejected one or more initial image candidates, triggering regeneration retries. Inspect scene_report and image rejected_attempts.')
    if not recommendations:
        recommendations.append('Pipeline completed without rate-limit backoffs or rejected image retries; primary wall time is governed by external model inference and Remotion frame rendering.')

    sanitized_spans=_sanitize_obj(spans)
    report={
        'schema_version':'generation-diagnostics-v3',
        'trace_provenance':trace_provenance,
        'job_id':job_id,
        'outcome':resolved_outcome,
        'start_utc':min((s['start_utc'] for s in spans),default=None),
        'finish_utc':max((s['end_utc'] for s in finished),default=None),
        'total_elapsed_seconds':round(total_wall,6),
        'measured_wall_seconds':round(covered,6),
        'unattributed_wall_seconds':round(max(0.,total_wall-covered),6),
        'peak_image_provider_concurrency':peak,
        'runtime':runtime_info['trace_runtimes'],
        'infrastructure':runtime_info,
        'process_peak_rss_native_units':runtime_info['process_peak_rss_native_units'],
        'revision':os.getenv('K_REVISION'),
        'commit':os.getenv('HER_BUILD_COMMIT'),
        'video_mode':manifest.get('preset','reference_editorial'),
        'actual_video_seconds':round(video_frames/fps,3) if video_frames and fps else None,
        'resolution':[manifest.get('width'),manifest.get('height')],
        'fps':manifest.get('fps'),
        'output_size_bytes':output_bytes,
        'visual_metrics':visual_metrics,
        'scene_report':scene_report,
        'stage_timings':stage_timings,
        'concurrency_analysis':concurrency_info,
        'tts_telemetry':tts_telemetry,
        'prediction_records':prediction_records,
        'critical_path':critical_chain,
        'bottleneck_ranking':candidates,
        'rendering':rendering_info,
        'images':images,
        'cost_report':cost_report,
        'model_usage':cost_report,
        'provider_metrics':provider_metrics,
        'errors_and_retries':error_records,
        'recommended_next_investigation':recommendations,
        'spans':sanitized_spans,
        'limitations':[
            'Browser timings unavailable unless submitted by the client.',
            'Cold-start/cache comparison requires separate controlled runs; process peak RSS includes earlier jobs.',
            'Overlapping durations must not be summed. Span nesting expresses dependencies, not a proven critical-path DAG.',
            'Report serialization and report upload occur after the measured worker interval.',
        ],
    }

    coverage_payload={
        'schema_version':'sentence-visual-coverage-v1',
        'job_id':job_id,
        'outcome':resolved_outcome,
        'trace_provenance':trace_provenance,
        'invariants':{
            'planned_primary_image_tasks_ge_sentences':visual_metrics['invariant_planned_ge_sentences'],
            'distinct_valid_primary_images_ge_sentences':visual_metrics['invariant_distinct_ge_sentences'],
            'sentences_with_rendered_distinct_primary_images_eq_sentences':visual_metrics['invariant_rendered_eq_sentences'],
            'all_passed':visual_metrics['acceptance_passed'],
        },
        'summary':visual_metrics,
        'sentences':scene_report,
        'supporting_and_identity_assets':[i for i in images if i.get('role')!='primary'],
    }

    timeline_payload={
        'schema_version':'pipeline-timeline-v1',
        'job_id':job_id,
        'outcome':resolved_outcome,
        'trace_provenance':trace_provenance,
        'start_utc':report['start_utc'],
        'finish_utc':report['finish_utc'],
        'total_elapsed_seconds':report['total_elapsed_seconds'],
        'measured_wall_seconds':report['measured_wall_seconds'],
        'stage_timings':stage_timings,
        'concurrency_analysis':concurrency_info,
        'critical_path':critical_chain,
        'tts_sentence_timeline':tts_telemetry,
        'image_prediction_timeline':prediction_records,
        'image_task_timeline':images,
        'rendering_breakdown':rendering_info,
        'spans':sanitized_spans,
    }

    paths=[
        directory/'generation_diagnostics.json',
        directory/'generation_diagnostics_report.txt',
        directory/'sentence_visual_coverage.json',
        directory/'pipeline_timeline.json',
    ]
    paths[0].write_text(json.dumps(report,indent=2))
    paths[2].write_text(json.dumps(coverage_payload,indent=2))
    paths[3].write_text(json.dumps(timeline_payload,indent=2))

    # Build human-readable report (Sections A–K)
    lines=[
        '========================================================================',
        'PROJECTHER GENERATION DIAGNOSTIC REPORT',
        '========================================================================',
        '',
        '## A. Generation Summary',
        f'Job ID: {job_id}',
        f'Trace Provenance: {trace_provenance}',
        f'Environment: {runtime_info["environment"]} (service={runtime_info["service"]}, revision={runtime_info["revision"]})',
        f'Video Mode: {report["video_mode"]}',
        f'Total Generation Time: {report["total_elapsed_seconds"]:.3f} s (measured covered wall: {report["measured_wall_seconds"]:.3f} s, unattributed: {report["unattributed_wall_seconds"]:.3f} s)',
        f'Final Video Duration: {report["actual_video_seconds"] if report["actual_video_seconds"] is not None else "N/A"} s',
        f'Resolution / FPS: {rendering_info["resolution"][0]}x{rendering_info["resolution"][1]} @ {rendering_info["fps"]} fps',
        f'Narration Sentences: {visual_metrics["sentences"]}',
        f'Unique Primary Images: {visual_metrics["distinct_primaries"]} (Rendered in video: {visual_metrics["rendered_primaries"]})',
        f'Generated / Acquired Images: {visual_metrics["generated_assets"]}',
        f'Reused Secondary Images: {visual_metrics["reused_secondary_assets"]}',
        f'Sentence-Primary Invariant (distinct >= sentences): {visual_metrics["invariant_distinct_ge_sentences"]}',
        f'Output Size: {output_bytes if output_bytes is not None else "N/A"} bytes',
        f'Result: {report["outcome"]}',
        '',
        '## MODEL USAGE',
        f'FLUX Schnell: {cost_report["flux_schnell"]["count"]} images — ${cost_report["flux_schnell"]["cost"]:.3f}',
        f'Seedream 4: {cost_report["seedream_4"]["count"]} images — ${cost_report["seedream_4"]["cost"]:.3f}',
        f'Rejected Attempts: {cost_report["rejected_attempts"]}',
        f'Cost of Rejected Images: ${cost_report["cost_of_rejected_images"]:.3f}',
        f'Total Estimated Replicate Cost: ${cost_report["total_estimated_replicate_cost"]:.3f}',
        'Actual Billed Cost: N/A (configured model estimates only)',
        '',
        'Cost Breakdown by Category:',
        f"- Initial character generation: ${cost_report['role_breakdown']['initial_character']:.3f}",
        f"- Scene-specific editing: ${cost_report['role_breakdown']['scene_editing']:.3f}",
        f"- Supporting objects: ${cost_report['role_breakdown']['supporting_objects']:.3f}",
        f"- Retry cost: ${cost_report['role_breakdown']['retries']:.3f}",
        '',
        '## B. Stage Duration Breakdown (Inclusive Spans; Parallel Stages Overlap)',
        f'{"Stage":<36} | {"Duration (s)":>12} | {"% Wall":>7} | {"Status":<10} | Metadata',
        '-'*96,
    ]
    if finished:
        for s in sorted(finished,key=lambda s:_epoch(s['start_utc'])):
            pct=(100.*s['duration_seconds']/total_wall) if total_wall>0 else 0.
            lines.append(f'{s["name"]:<36} | {s["duration_seconds"]:>12.3f} | {pct:>6.1f}% | {s["status"]:<10} | {json.dumps(_sanitize_obj(s.get("metadata",{})))}')
    else:
        for k,v in stage_timings.items():
            if isinstance(v,(int,float)):
                pct=(100.*float(v)/total_wall) if total_wall>0 else 0.
                lines.append(f'{k:<36} | {float(v):>12.3f} | {pct:>6.1f}% | {"recorded":<10} | {{"source":"stageTimings"}}')

    lines+=[
        '',
        '## C. Individual Image-Generation Times',
        f'{"#":>2} | {"Sentence":<14} | {"Entity ID":<24} | {"Role":<10} | {"Queue(s)":>8} | {"API(s)":>8} | {"Cut(s)":>7} | {"Rev(s)":>7} | {"Total(s)":>8} | {"Tries":>5} | {"Cache":<5} | {"Route"}',
        '-'*138,
    ]
    for img in images:
        lines.append(f'{img["task_index"]:>2} | {str(img["sentence_id"]):<14} | {str(img["entityId"])[:24]:<24} | {str(img["role"])[:10]:<10} | {img["queue_wait_seconds"]:>8.3f} | {img["api_duration_seconds"]:>8.3f} | {img["cutout_processing_seconds"]:>7.3f} | {img["visual_review_seconds"]:>7.3f} | {img["durationSeconds"]:>8.3f} | {img["attempts"]:>5} | {str(img["cacheHit"]):<5} | {img["route"]}')
    slowest=sorted(images,key=lambda x:x['durationSeconds'],reverse=True)[:3]
    if slowest:
        lines.append('Slowest image tasks: '+', '.join(f'{x["entityId"]} ({x["durationSeconds"]:.3f}s, tries={x["attempts"]})' for x in slowest))

    lines+=[
        '',
        '## D. Concurrency Analysis',
        f'Total image tasks: {concurrency_info["total_image_tasks"]}',
        f'Peak concurrent image provider requests: {concurrency_info["peak_image_provider_concurrency"]}',
        f'Average active image provider concurrency: {concurrency_info["average_active_image_concurrency"]}',
        f'Configured action workers: {concurrency_info["configured_action_workers"]}',
        f'TTS and visual sourcing overlap: {concurrency_info["tts_visual_overlap_seconds"]:.3f} s (speech={concurrency_info["speech_wall_seconds"]} s, cutouts={concurrency_info["cutouts_wall_seconds"]} s, alignment={concurrency_info["alignment_seconds"]} s)',
        f'Sequential unattributed gap time: {concurrency_info["serial_gap_seconds"]:.3f} s',
        f'Admission pacing wait (accumulated): {concurrency_info["admission_wait_seconds"]:.3f} s',
        f'Rate-limited responses (HTTP 429): {concurrency_info["rate_limit_responses"]} (backoff={concurrency_info["rate_limit_backoff_seconds"]} s)',
        f'Background removal total CPU work: {concurrency_info["background_removal_total_seconds"]:.3f} s across {len(bg_spans) or len(images)} cutout(s)',
        f'Rendering breakdown: staging={rendering_info["asset_staging_seconds"]}s, remotion={rendering_info["remotion_render_seconds"]}s (concurrency={rendering_info["remotion_concurrency"]}), ffmpeg={rendering_info["ffmpeg_encode_seconds"]}s, audio_delivery={rendering_info["audio_delivery_seconds"]}s, qa={rendering_info["visual_quality_scan_seconds"]}s',
        '',
        '## E. Critical Path',
    ]
    if critical_chain:
        lines.append(' -> '.join(f'{c["stage"]} ({c["duration_seconds"]:.2f}s)' for c in critical_chain))
    else:
        lines.append('No completed stage chain recorded.')

    lines+=[
        '',
        '## F. Bottleneck Ranking',
        f'{"Rank":>4} | {"Operation / Stage":<34} | {"Duration(s)":>11} | {"% Wall":>7} | {"Category":<10} | Evidence & Optimization Opportunity',
        '-'*120,
    ]
    for idx,cand in enumerate(candidates[:8]):
        lines.append(f'{idx+1:>4} | {cand["operation"]:<34} | {cand["duration_seconds"]:>11.3f} | {cand["percent_of_wall_time"]:>6.1f}% | {cand["cause_category"]:<10} | {cand["evidence"]} -> {cand["optimization_opportunity"]}')

    lines+=[
        '',
        '## G. Errors and Retries (Sanitized)',
        json.dumps(error_records,indent=2) if error_records else 'None recorded.',
        'Provider counters: '+json.dumps(provider_metrics),
        '',
        '## H. Scene-Level Visual Quality Report',
        f'{"#":>2} | {"Sentence ID":<14} | {"Subject Type":<12} | {"Primary Asset ID":<28} | {"Distinct":<8} | {"Rendered":<8} | {"Window (s)":<15} | {"Secondary IDs"}',
        '-'*120,
    ]
    for sc in scene_report:
        win=f'{sc["start_time"]:.2f}-{sc["end_time"]:.2f}' if isinstance(sc.get('start_time'),(int,float)) and isinstance(sc.get('end_time'),(int,float)) else 'N/A'
        lines.append(f'{sc["sentence_number"]:>2} | {str(sc["sentence_id"]):<14} | {str(sc.get("primary_subject_type",""))[:12]:<12} | {str(sc["primary_asset_id"])[:28]:<28} | {str(sc["primary_asset_is_distinct"]):<8} | {str(sc["render_visibility"]):<8} | {win:<15} | {",".join(sc.get("secondary_entity_ids",[]))}')

    lines+=[
        '',
        '## I. Recommended Next Investigation',
        *[f'- {rec}' for rec in recommendations],
        '',
        '## J. Optimization Comparison & Telemetry Notes',
        f'- TTS sentence telemetry records: {len(tts_telemetry)}',
        f'- Image prediction telemetry records: {len(prediction_records)}',
        f'- Trace provenance: {trace_provenance}',
        '',
        '## K. Unresolved External Constraints & Measurement Limitations',
        *[f'- {lim}' for lim in report['limitations']],
    ]
    paths[1].write_text('\n'.join(lines)+'\n')

    # Mirror into diagnostics/runs/<job_id>/ when enabled and writable
    if getattr(config,'PERF_DIAGNOSTICS',True):
        try:
            configured_runs=Path(getattr(config,'DIAGNOSTICS_RUNS_DIR',config.BASE_DIR/'diagnostics'/'runs'))
            default_runs=(config.BASE_DIR/'diagnostics'/'runs').resolve()
            in_temp=str(directory.resolve()).startswith(str(Path(tempfile.gettempdir()).resolve()))
            if not (in_temp and configured_runs.resolve()==default_runs):
                runs_dir=configured_runs/str(job_id)
                if runs_dir.resolve()!=directory.resolve():
                    runs_dir.mkdir(parents=True,exist_ok=True)
                    for p in paths:shutil.copyfile(p,runs_dir/p.name)
        except OSError:
            pass
    return paths
