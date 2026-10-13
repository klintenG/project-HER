"""One real, explicitly opted-in native API job; never used by CI.

Prints sanitized stage/status evidence. Scoped access and media tickets stay in
memory; the report contains no tokens, prompts from strangers, or signed URLs.
"""
import argparse
import hashlib
import json
import subprocess
import time
import uuid
from pathlib import Path
from urllib.parse import urljoin,urlsplit
import requests


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',default='https://project-her-svnnlerw4q-uc.a.run.app/api/portfolio')
    p.add_argument('--allow-paid-generation',action='store_true');p.add_argument('--browser-check');p.add_argument('--browser-submit',action='store_true');p.add_argument('--output',default='output/native-portfolio-smoke')
    args=p.parse_args();base=args.base.rstrip('/');origin='https://klinteng.com'
    session=requests.Session();session.headers.update({'Origin':origin})
    response=session.get(base+'/config',timeout=90);response.raise_for_status();caps=response.json()
    if not caps.get('enabled'):raise RuntimeError('Native API reports generation disabled; no paid work submitted.')
    print('Native API ready; options/limits fetched from deployment.')
    if not args.allow_paid_generation:
        print('No job submitted. Add --allow-paid-generation for exactly one controlled provider-backed generation.');return
    text='Fictional demonstration: A red ceramic cup stands beside a blue ceramic bowl. The cup stays in place while attention shifts to the bowl.'
    payload={'text':text,'news_source_policy':'supplied','target_duration':15}
    if args.browser_submit:
        if base!='https://project-her-svnnlerw4q-uc.a.run.app/api/portfolio':raise RuntimeError('Live browser submission requires the production API.')
        submitted=subprocess.run(['node',str(Path(__file__).with_name('submit_native_portfolio.mjs'))],input=json.dumps({'site':origin,**payload}),text=True,capture_output=True,timeout=300)
        if submitted.returncode:raise RuntimeError('Live studio submission was not confirmed. Do not resubmit automatically; inspect the original job before retrying.')
        accepted=json.loads(submitted.stdout)
    else:
        key=uuid.uuid4().hex
        response=session.post(base+'/jobs',json=payload,headers={'Idempotency-Key':key},timeout=90);response.raise_for_status()
        accepted=response.json()
    jid=accepted['job_id'];session.headers['Authorization']='Bearer '+accepted['access_token']
    print('Created real job '+jid);events=[];last=None;deadline=time.monotonic()+3000
    while time.monotonic()<deadline:
        response=session.get(base+'/jobs/'+jid,timeout=45);response.raise_for_status();job=response.json()
        marker=(job['status'],json.dumps(job.get('stage'),sort_keys=True))
        if marker!=last:
            events.append({'status':job['status'],'stage':job.get('stage')});last=marker
            print(job['status'],(job.get('stage') or {}).get('label',''),flush=True)
        if job['status'] in ('completed','failed','cancelled'):break
        time.sleep(6)
    else:raise RuntimeError('Smoke monitoring deadline reached. Do not resubmit automatically; query the original job.')
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    streamed=session.get(base+'/jobs/'+jid+'/events',stream=True,timeout=30)
    streamed.raise_for_status();sse_checked=streamed.headers.get('Content-Type','').startswith('text/event-stream')
    first=next(streamed.iter_lines(chunk_size=1),b'');streamed.close()
    if not sse_checked or not first.startswith(b'event:'):raise RuntimeError('Actual SSE endpoint check failed')
    report={'sse_checked':sse_checked,'job_id':jid,'input':text,'submitted_through_production_ui':args.browser_submit,'events':events,'status':job['status'],'error':job.get('error'),'deployment_base':base}
    if job['status']!='completed':
        (out/'smoke.json').write_text(json.dumps(report,indent=2));raise RuntimeError('Real job did not complete: '+str(job.get('error')))
    result=job['result'];host=urlsplit(base).netloc
    def media(value):
        url=urljoin(base,value)
        if urlsplit(url).netloc!=host or not urlsplit(url).path.startswith('/api/portfolio/jobs/'+jid+'/media/'):raise RuntimeError('Unexpected media URL')
        return url
    ranged=session.get(media(result['video_url']),headers={'Range':'bytes=0-4095'},timeout=60)
    if ranged.status_code!=206 or len(ranged.content)!=4096:raise RuntimeError('Playback byte-range smoke failed')
    response=session.get(media(result['download_url']),stream=True,timeout=120);response.raise_for_status()
    if 'attachment' not in response.headers.get('Content-Disposition',''):raise RuntimeError('Download headers failed')
    video=out/'generated.mp4';size=0;digest=hashlib.sha256()
    with video.open('wb') as stream:
        for chunk in response.iter_content(65536):
            size+=len(chunk)
            if size>150_000_000:raise RuntimeError('Unexpectedly large smoke output')
            stream.write(chunk);digest.update(chunk)
    metadata=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(video)]))
    stream=next(s for s in metadata['streams'] if s['codec_type']=='video')
    if (stream['width'],stream['height'])!=(1080,1920) or not any(s['codec_type']=='audio' for s in metadata['streams']):raise RuntimeError('Unexpected video format')
    report.update(output=str(video.resolve()),bytes=size,sha256=digest.hexdigest(),media=metadata,range_status=ranged.status_code,download_attachment=True)
    (out/'smoke.json').write_text(json.dumps(report,indent=2))
    if args.browser_check:
        proof=subprocess.run(['node',args.browser_check],input=json.dumps({'job_id':jid,'token':accepted['access_token'],'expires_at':accepted['expires_at'],'sha256':digest.hexdigest(),'site':'https://klinteng.com'}),text=True,capture_output=True,timeout=300)
        report['production_browser_passed']=proof.returncode==0
        (out/'smoke.json').write_text(json.dumps(report,indent=2))
        if proof.returncode:raise RuntimeError('Production browser verification failed; no additional job was submitted. Review the deployed portfolio revision.')
        print(proof.stdout.strip())
    (out/'smoke.json').write_text(json.dumps(report,indent=2));print('Actual generated MP4 downloaded and probed: '+str(video.resolve()))

if __name__=='__main__':main()
