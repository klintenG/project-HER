#!/usr/bin/env python3
"""Apply the free-tier Autopilot layout to an EXISTING deployment using gcloud only.

Use this when the Cloud Run jobs and Cloud Scheduler jobs already exist but there is no
Terraform state for deploy/autopilot (running `terraform apply` blind would try to create
resources that exist). It mirrors deploy/autopilot/main.tf:

  * her-autopilot        4 vCPU / 8 GiB  render job: timeout 3000 s, HER_COMPUTE_BUDGET=1, HER_COMPUTE_WEIGHT=1
  * her-autopilot-light  1 vCPU / 2 GiB  clone of the render job for prepare/schedule/verify/retry
  * the five Cloud Scheduler jobs get the lean cron schedule; only `generate` targets the big job
  * the light job receives the same run.jobsExecutorWithOverrides members as the render job

Default is a DRY RUN: read-only gcloud calls run, every change is printed instead.
  python scripts/apply_lean_autopilot.py                 # show the plan
  python scripts/apply_lean_autopilot.py --apply         # make the changes (schedulers stay paused)
  python scripts/apply_lean_autopilot.py --resume        # resume the schedulers (separate, explicit step)

The job's current environment is copied to the light job through a private temporary file
that is deleted afterwards. Secret values are never printed.
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import tempfile

PROJECT='project-her-510715'
HEAVY='her-autopilot'
LIGHT='her-autopilot-light'
STEPS=('generate','prepare','schedule','verify','retry')
# Keep identical to the defaults of `autopilot_schedules` in deploy/autopilot/main.tf (a test enforces this).
SCHEDULES={'generate':'0 9,13 * * *','prepare':'10 10,14 * * *','schedule':'0 16,17,18 * * *',
           'verify':'10 19,21 * * *','retry':'5,20,35,50 18 * * *'}
TIME_ZONE='Asia/Kolkata'
RENDER_TIMEOUT=3000
LIGHT_TIMEOUT=900
EXECUTOR_ROLE='roles/run.jobsExecutorWithOverrides'


class Gcloud:
    def __init__(self,project,region,apply=False,runner=None,out=print):
        self.project=project;self.region=region;self.apply=apply;self.out=out
        self.runner=runner or self._run

    @staticmethod
    def _run(args):
        done=subprocess.run(['gcloud']+args,capture_output=True,text=True)
        return done.returncode,done.stdout,done.stderr

    def read(self,args,*,allow_failure=False):
        code,stdout,stderr=self.runner(args+['--project='+self.project])
        if code and not allow_failure:raise SystemExit(f'gcloud {" ".join(args[:4])} failed: {stderr.strip()[-400:]}')
        return None if code else stdout

    def change(self,args,note):
        self.out(('APPLY  ' if self.apply else 'WOULD  ')+note)
        if not self.apply:return
        code,_,stderr=self.runner(args+['--project='+self.project])
        if code:raise SystemExit(f'FAILED: {note}\n{stderr.strip()[-600:]}')


def heavy_spec(g):
    raw=g.read(['run','jobs','describe',HEAVY,'--region='+g.region,'--format=json'])
    task=json.loads(raw)['spec']['template']['spec']['template']['spec']
    container=task['containers'][0]
    env={};secrets={}
    for item in container.get('env',[]):
        ref=(item.get('valueFrom') or {}).get('secretKeyRef')
        if ref:secrets[item['name']]=f"{ref['name']}:{ref.get('key','latest')}"
        else:env[item['name']]=str(item.get('value',''))
    return {'image':container['image'],'service_account':task['serviceAccountName'],'env':env,'secrets':secrets,
            'command':container.get('command',['python']),'args':container.get('args',[])}


def light_job(g,spec):
    env=dict(spec['env'],HER_COMPUTE_BUDGET='1',HER_COMPUTE_WEIGHT='0.25')
    secret_flag=','.join(f'{name}={ref}' for name,ref in sorted(spec['secrets'].items()))
    fd,path=tempfile.mkstemp(prefix='her-light-env-',suffix='.json');os.close(fd);os.chmod(path,0o600)
    try:
        with open(path,'w') as handle:json.dump(env,handle)
        args=['run','jobs','deploy',LIGHT,'--region='+g.region,'--image='+spec['image'],
              '--service-account='+spec['service_account'],'--cpu=1','--memory=2Gi','--max-retries=0',
              f'--task-timeout={LIGHT_TIMEOUT}s','--tasks=1','--parallelism=1','--command='+','.join(spec['command']),
              '--args='+','.join(spec['args']),'--env-vars-file='+path]
        if secret_flag:args.append('--set-secrets='+secret_flag)
        g.change(args,f'create/update {LIGHT} (1 vCPU / 2 GiB, {LIGHT_TIMEOUT}s) from {HEAVY} image, env and secrets')
    finally:
        os.unlink(path)


def heavy_job(g):
    g.change(['run','jobs','update',HEAVY,'--region='+g.region,f'--task-timeout={RENDER_TIMEOUT}s',
              '--update-env-vars=HER_COMPUTE_BUDGET=1,HER_COMPUTE_WEIGHT=1'],
             f'update {HEAVY}: timeout {RENDER_TIMEOUT}s, HER_COMPUTE_BUDGET=1, HER_COMPUTE_WEIGHT=1')


def copy_executors(g):
    raw=g.read(['run','jobs','get-iam-policy',HEAVY,'--region='+g.region,'--format=json'])
    members=[m for b in json.loads(raw).get('bindings',[]) if b.get('role')==EXECUTOR_ROLE for m in b.get('members',[])]
    if not members:print(f'NOTE   {HEAVY} has no {EXECUTOR_ROLE} members; the scheduler may lack permission',file=sys.stderr)
    for member in members:
        g.change(['run','jobs','add-iam-policy-binding',LIGHT,'--region='+g.region,'--member='+member,'--role='+EXECUTOR_ROLE],
                 f'allow {member} to run {LIGHT}')


def schedulers(g):
    for step in STEPS:
        job=HEAVY if step=='generate' else LIGHT
        uri=f'https://run.googleapis.com/v2/projects/{g.project}/locations/{g.region}/jobs/{job}:run'
        body=json.dumps({'overrides':{'containerOverrides':[{'args':['-m','automation.autopilot_worker',step]}]}},separators=(',',':'))
        g.change(['scheduler','jobs','update','http',f'her-autopilot-{step}','--location='+g.region,'--schedule='+SCHEDULES[step],
                  '--time-zone='+TIME_ZONE,'--uri='+uri,'--http-method=POST','--update-headers=Content-Type=application/json',
                  '--message-body='+body],f'scheduler her-autopilot-{step}: "{SCHEDULES[step]}" ({TIME_ZONE}) -> {job}')


def resume(g):
    for step in STEPS:
        g.change(['scheduler','jobs','resume',f'her-autopilot-{step}','--location='+g.region],f'resume scheduler her-autopilot-{step}')


def main(argv=None,runner=None):
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--project',default=PROJECT);parser.add_argument('--region',default='us-central1')
    parser.add_argument('--apply',action='store_true',help='make the changes (default: dry run)')
    parser.add_argument('--resume',action='store_true',help='only resume the five schedulers')
    args=parser.parse_args(argv)
    g=Gcloud(args.project,args.region,apply=args.apply or args.resume,runner=runner)
    if not g.apply:print('DRY RUN - nothing will be changed. Add --apply to execute.')
    if args.resume:resume(g);return 0
    spec=heavy_spec(g)
    light_job(g,spec);heavy_job(g);copy_executors(g);schedulers(g)
    print('\nDone. Schedulers keep their current paused/enabled state. Verify, then run with --resume.' if g.apply else '\nDry run complete.')
    return 0


if __name__=='__main__':sys.exit(main())
