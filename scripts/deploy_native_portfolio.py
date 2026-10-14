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


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--approve-cloud-changes',action='store_true');args=parser.parse_args()
    print('Plan: Firestore (default) in us-central1; private bucket '+BUCKET+'; signing/operator secrets; scoped IAM; deploy project-her with native API + legacy lock, min/max instances 1, existing 2 CPU/4Gi, private output lifecycle, daily quota 10 / network identity 2.')
    print('Existing provider secrets/settings are preserved. One minimum instance changes idle billing. This does not publish the portfolio or submit a paid generation.')
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
    run(['firestore','fields','ttls','update','delete_after','--collection-group=her_portfolio','--database=(default)','--enable-ttl','--async'])
    values={'HER_PORTFOLIO_ENABLED':'1','HER_PORTFOLIO_LOCK_LEGACY':'1','HER_PORTFOLIO_BUCKET':BUCKET,
        'GOOGLE_CLOUD_PROJECT':PROJECT,'HER_PORTFOLIO_ORIGINS':'https://klinteng.com,https://www.klinteng.com',
        'HER_PORTFOLIO_DAILY_LIMIT':'10','HER_PORTFOLIO_VISITOR_LIMIT':'2','HER_PORTFOLIO_CONCURRENCY':'1',
        'HER_TRUSTED_PROXY_HOPS':'0','HER_ALIGNMENT_MODEL':'small','HER_ALIGNMENT_DOWNLOAD':'0'}
    env='^~^'+'~'.join(k+'='+v for k,v in values.items())
    import sys
    sys.path.insert(0,str(source))
    from utils.deployment_guard import DeploymentGuard
    with DeploymentGuard(PROJECT):
        deploy=run(['run','deploy',SERVICE,'--source='+str(source),'--region='+REGION,
            '--no-cpu-throttling','--min-instances=1','--max-instances=1','--concurrency=20','--cpu=2','--memory=4Gi','--timeout=3600',
            '--update-env-vars='+env,'--update-secrets=HER_PORTFOLIO_SIGNING_KEY=her-portfolio-signing-key:latest,HER_OPERATOR_KEY=her-portfolio-operator-key:latest,'+provider_binding])
    print('Cloud Run deployment completed. Next: check /api/portfolio/config, run one explicitly allowed smoke generation, then publish the reviewed portfolio changes.')

if __name__=='__main__':main()
