"""Reviewable production rollout; dry-run by default. Never prints secret values.

Creates durable services/secrets and changes the existing public Cloud Run
service only with --approve-cloud-changes. Portfolio publishing is separate.
"""
import argparse
import json
import os
import secrets
import subprocess
import tempfile
from pathlib import Path
from dotenv import dotenv_values

PROJECT='project-her-510715';REGION='us-central1';SERVICE='project-her'
BUCKET=PROJECT+'-portfolio-output'
WORKER_JOB='her-portfolio-worker'
# Cloud Run sets these itself; they must not be copied onto the worker Job.
# The render worker never publishes or administers: keep those credentials out of it.
WORKER_EXCLUDED_ENV={'BUFFER_API_KEY','AUTOPILOT_ADMIN_TOKEN','HER_OPERATOR_KEY'}
RESERVED_ENV={'PORT','K_SERVICE','K_REVISION','K_CONFIGURATION','HER_PORTFOLIO_WORKER_JOB','HER_PORTFOLIO_WORKER_REGION'}


def run(args,*,data=None,allow_failure=False):
    print('Cloud step: '+' '.join(args[:3]),flush=True)
    result=subprocess.run(['gcloud',*args,'--project='+PROJECT,'--quiet'],input=data,capture_output=True,text=True)
    if result.returncode and not allow_failure:
        # gcloud output may contain env values; don't echo a deployment export.
        raise RuntimeError('gcloud command failed: '+' '.join(args[:4])+' (exit '+str(result.returncode)+'). Review the command locally; secret values are not printed.')
    return result


def ensure_replicate_secret(account,source):
    name='her-provider-replicate-token'
    current=run(['secrets','describe',name,'--format=value(name)'],allow_failure=True)
    if current.returncode:
        value=os.getenv('REPLICATE_API_TOKEN') or dotenv_values(Path(source)/'.env').get('REPLICATE_API_TOKEN','')
        if not value:raise RuntimeError('Configure REPLICATE_API_TOKEN locally or provision her-provider-replicate-token before enabling public generation. No credential value was printed.')
        run(['secrets','create',name,'--replication-policy=automatic','--data-file=-'],data=value)
    run(['secrets','add-iam-policy-binding',name,'--member=serviceAccount:'+account,'--role=roles/secretmanager.secretAccessor'])
    return 'REPLICATE_API_TOKEN='+name+':latest'


def deploy_worker_job(account,workdir,args):
    """Create/update the per-render Job from the service's freshly deployed image.

    Env and secret bindings are copied from the service so providers behave
    identically. Plain values go through a private temp file, never argv.
    """
    service=json.loads(run(['run','services','describe',SERVICE,'--region='+REGION,'--format=json']).stdout)
    container=service['spec']['template']['spec']['containers'][0]
    plain={};secret_refs=[]
    for item in container.get('env',[]):
        if item['name'] in RESERVED_ENV or item['name'] in WORKER_EXCLUDED_ENV:continue
        ref=(item.get('valueFrom') or {}).get('secretKeyRef')
        if ref:secret_refs.append(item['name']+'='+ref['name']+':'+ref.get('key','latest'))
        else:plain[item['name']]=item.get('value','')
    env_file=workdir/'worker-env.yaml'
    env_file.write_text(''.join(k+': '+json.dumps(v)+'\n' for k,v in plain.items()))
    command=['run','jobs','deploy',WORKER_JOB,'--image='+container['image'],'--region='+REGION,
        '--service-account='+account,'--command=python','--args=-m,agent.portfolio_worker',
        '--tasks=1','--max-retries=0','--task-timeout=3000s','--cpu='+args.worker_cpu,'--memory='+args.worker_memory,
        '--env-vars-file='+str(env_file)]
    if secret_refs:command.append('--set-secrets='+','.join(secret_refs))
    try:run(command)
    finally:env_file.unlink(missing_ok=True)
    # Narrowest role that can start this one Job with per-execution args.
    run(['run','jobs','add-iam-policy-binding',WORKER_JOB,'--region='+REGION,'--member=serviceAccount:'+account,'--role=roles/run.jobsExecutorWithOverrides'])


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--approve-cloud-changes',action='store_true')
    parser.add_argument('--clear-maintenance',action='store_true',help='Clear stale maintenance lock if previous deployment was interrupted')
    parser.add_argument('--performance-profile',action='store_true',help='Use 4 CPU/8Gi, two render tabs and three asset workers; increases Cloud Run billing')
    parser.add_argument('--image',help='Deploy an existing container image directly without rebuilding from source')
    parser.add_argument('--executor',choices=('job','instance'),default='job',
        help='job (default): web scales to zero, each render runs in Cloud Run Job '+WORKER_JOB+'. instance: legacy always-on render inside the web instance.')
    parser.add_argument('--daily-limit',default='2');parser.add_argument('--visitor-limit',default='1')
    parser.add_argument('--service-cpu',default='1');parser.add_argument('--service-memory',default='2Gi')
    parser.add_argument('--worker-cpu',default='4');parser.add_argument('--worker-memory',default='8Gi')
    args=parser.parse_args()
    if args.executor=='job':
        print(f'Plan: Firestore (default) in us-central1; private bucket {BUCKET}; signing/operator secrets; scoped IAM; deploy {SERVICE} with native API + legacy lock, min instances 0, request-based CPU, {args.service_cpu} CPU/{args.service_memory}; '
              f'Cloud Run Job {WORKER_JOB} at {args.worker_cpu} CPU/{args.worker_memory}, 0 retries, one execution per admitted render; daily quota {args.daily_limit} / network identity {args.visitor_limit}.')
        print('Idle cost is ~0: no instance runs between requests. Each render bills Job time plus provider (Replicate) usage. This does not publish the portfolio or submit a paid generation.')
    else:
        print(f'Plan (legacy instance executor): deploy {SERVICE} with min/max instances 1, always-allocated CPU, preserve existing CPU/RAM; daily quota {args.daily_limit} / network identity {args.visitor_limit}.')
        print('WARNING: one always-on instance is billed 24/7 even with no visitors.')
    if args.performance_profile:print('Performance override: render tabs, image workers and inference threads are raised for the renderer ('+('worker Job' if args.executor=='job' else 'web instance, 4 CPU / 8Gi')+'). Higher active billing; end-to-end latency must be measured.')
    if not args.approve_cloud_changes:return
    os.umask(0o077)
    source=Path(__file__).resolve().parents[1];os.chdir(source)
    snapshot=run(['run','services','describe',SERVICE,'--region='+REGION,'--format=json'])
    service=json.loads(snapshot.stdout);account=service['spec']['template']['spec']['serviceAccountName']
    backup=Path(tempfile.mkdtemp(prefix='her-native-rollout-'))/'previous-service.json';backup.write_text(snapshot.stdout)
    print('Private rollback snapshot saved to '+str(backup))
    run(['services','enable','firestore.googleapis.com','storage.googleapis.com','secretmanager.googleapis.com'])
    databases=run(['firestore','databases','list','--format=json'])
    if not any(row.get('name','').endswith('/(default)') for row in json.loads(databases.stdout)):
        run(['firestore','databases','create','--database=(default)','--location='+REGION,'--type=firestore-native'])
    # The friendly gcloud representation omits projectNumber; verify ownership
    # using the raw Storage API metadata before changing an existing bucket.
    existing=run(['storage','buckets','describe','gs://'+BUCKET,'--raw','--format=json'],allow_failure=True)
    if existing.returncode:
        run(['storage','buckets','create','gs://'+BUCKET,'--location='+REGION,'--uniform-bucket-level-access','--public-access-prevention'])
    else:
        info=json.loads(existing.stdout)
        project_number=json.loads(run(['projects','describe',PROJECT,'--format=json(projectNumber)']).stdout)['projectNumber']
        if str(info.get('project_number',info.get('projectNumber','')))!=str(project_number):
            raise RuntimeError('The named bucket could not be verified as belonging to this project; no policy changes were made to it.')
        run(['storage','buckets','update','gs://'+BUCKET,'--uniform-bucket-level-access','--public-access-prevention'])
    lifecycle=backup.with_name('output-lifecycle.json')
    lifecycle.write_text(json.dumps({'rule':[{'action':{'type':'Delete'},'condition':{'age':2,'matchesPrefix':['portfolio/']}}]}))
    run(['storage','buckets','update','gs://'+BUCKET,'--lifecycle-file='+str(lifecycle),'--clear-soft-delete'])
    run(['storage','buckets','add-iam-policy-binding','gs://'+BUCKET,'--member=serviceAccount:'+account,'--role=roles/storage.objectUser'])
    run(['projects','add-iam-policy-binding',PROJECT,'--member=serviceAccount:'+account,'--role=roles/datastore.user','--condition=None'])
    for name in ('her-portfolio-signing-key','her-portfolio-operator-key'):
        current=run(['secrets','describe',name,'--format=value(name)'],allow_failure=True)
        if current.returncode:
            run(['secrets','create',name,'--replication-policy=automatic','--data-file=-'],data=secrets.token_urlsafe(48))
        run(['secrets','add-iam-policy-binding',name,'--member=serviceAccount:'+account,'--role=roles/secretmanager.secretAccessor'])
    provider_binding=ensure_replicate_secret(account,source)
    secret_bindings=['HER_PORTFOLIO_SIGNING_KEY=her-portfolio-signing-key:latest','HER_OPERATOR_KEY=her-portfolio-operator-key:latest',provider_binding]
    for env_key,secret_name in (('AUTOPILOT_ADMIN_TOKEN','her-autopilot-admin-token'),('BUFFER_API_KEY','her-provider-buffer-key')):
        if not run(['secrets','describe',secret_name,'--format=value(name)'],allow_failure=True).returncode:
            run(['secrets','add-iam-policy-binding',secret_name,'--member=serviceAccount:'+account,'--role=roles/secretmanager.secretAccessor'])
            secret_bindings.append(env_key+'='+secret_name+':latest')
    run(['firestore','fields','ttls','update','delete_after','--collection-group=her_portfolio','--database=(default)','--enable-ttl','--async'])
    values={'HER_PORTFOLIO_ENABLED':'1','HER_PORTFOLIO_LOCK_LEGACY':'1','HER_PORTFOLIO_BUCKET':BUCKET,
        'GOOGLE_CLOUD_PROJECT':PROJECT,'HER_PORTFOLIO_ORIGINS':'https://klinteng.com,https://www.klinteng.com',
        'HER_PORTFOLIO_DAILY_LIMIT':args.daily_limit,'HER_PORTFOLIO_VISITOR_LIMIT':args.visitor_limit,'HER_PORTFOLIO_CONCURRENCY':'1',
        'HER_TRUSTED_PROXY_HOPS':'0','HER_ALIGNMENT_MODEL':'small','HER_ALIGNMENT_DOWNLOAD':'0',
        'AUTOPILOT_PUBLIC_BUCKET':PROJECT+'-autopilot-media','AUTOPILOT_JOB_NAME':'her-autopilot','AUTOPILOT_JOB_REGION':REGION,
        # Preserve operational publishing state; deployment is not live validation.
        'AUTOPILOT_DAILY_COST_LIMIT_USD':'6','AUTOPILOT_MAX_INPUT_CHARS':'48000'}
    if args.performance_profile:values.update(HER_REMOTION_CONCURRENCY='3',EDITORIAL_ASSET_WORKERS='3',OMP_NUM_THREADS='2',HER_CUTOUT_THREADS='2',HER_INFERENCE_THREADS='4',MODEL_CHECKSUM_DISABLED='1')
    local_env=dotenv_values(Path(source)/'.env')
    for key in ('GEMINI_API_KEY','GOOGLE_TTS_API_KEY','PEXELS_API_KEY','GROQ_API_KEY','AUTOPILOT_LLM_MODEL','BUFFER_ORGANIZATION_ID','BUFFER_INSTAGRAM_CHANNEL_ID','BUFFER_YOUTUBE_CHANNEL_ID','AUTOPILOT_ENABLED','BUFFER_DRY_RUN','AUTOPILOT_LIVE_VALIDATED','BUFFER_YOUTUBE_CATEGORY_ID','BUFFER_YOUTUBE_PRIVACY','VIDEO_WATERMARK_TEXT','AUTOPILOT_MAX_LLM_CALLS','AUTOPILOT_MAX_SCRIPT_REVISIONS'):
        val=os.getenv(key) or local_env.get(key)
        if val: values[key]=str(val)
    if args.executor=='job':
        values.update({'HER_PORTFOLIO_WORKER_JOB':WORKER_JOB,'HER_PORTFOLIO_WORKER_REGION':REGION,'HER_PORTFOLIO_START_GRACE':'900'})
        # Web tier only validates, enqueues and serves status/media: small, request-billed, scale to zero.
        scaling=['--cpu-throttling','--min-instances=0','--max-instances=1','--concurrency=20','--cpu='+args.service_cpu,'--memory='+args.service_memory,'--timeout=300']
    else:
        scaling=['--no-cpu-throttling','--min-instances=1','--max-instances=1','--concurrency=20',*(['--cpu=4','--memory=8Gi'] if args.performance_profile else []),'--timeout=3600']
    env='^~^'+'~'.join(k+'='+v for k,v in values.items())
    import sys
    sys.path.insert(0,str(source))
    from utils.deployment_guard import DeploymentGuard
    target_deploy = ['--image='+args.image] if args.image else ['--source='+str(source)]
    with DeploymentGuard(PROJECT, force_maintenance_clear=args.clear_maintenance):
        deploy=run(['run','deploy',SERVICE,*target_deploy,'--region='+REGION,*scaling,
            '--update-env-vars='+env,'--update-secrets='+','.join(secret_bindings)])
        if args.executor=='job':
            # Inside the guard: admissions stay paused until the worker exists.
            deploy_worker_job(account,backup.parent,args)
        else:
            run(['run','services','update',SERVICE,'--region='+REGION,'--remove-env-vars=HER_PORTFOLIO_WORKER_JOB,HER_PORTFOLIO_WORKER_REGION'],allow_failure=True)
    if not run(['run','jobs','describe','her-autopilot','--region='+REGION],allow_failure=True).returncode:
        updated=json.loads(run(['run','services','describe',SERVICE,'--region='+REGION,'--format=json']).stdout)
        deployed_image=updated['spec']['template']['spec']['containers'][0]['image']
        run(['run','jobs','update','her-autopilot','--region='+REGION,'--image='+deployed_image,'--update-env-vars='+env])
    print('Cloud Run deployment completed. Next: check /api/portfolio/config, run one explicitly allowed smoke generation, then publish the reviewed portfolio changes.')

if __name__=='__main__':main()
