"""scripts/apply_lean_autopilot.py: lean layout via gcloud, with a fake gcloud (no cloud access)."""
import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('apply_lean_autopilot',ROOT/'scripts'/'apply_lean_autopilot.py')
lean=importlib.util.module_from_spec(spec);sys.modules['apply_lean_autopilot']=lean;spec.loader.exec_module(lean)

JOB={'spec':{'template':{'spec':{'template':{'spec':{'serviceAccountName':'w@p.iam.gserviceaccount.com','containers':[{
    'image':'img@sha256:abc','command':['python'],'args':['-m','automation.autopilot_worker','verify'],
    'env':[{'name':'A','value':'1'},{'name':'KEY','value':'literal-secret-value'},
           {'name':'BUFFER_API_KEY','valueFrom':{'secretKeyRef':{'name':'her-provider-buffer-key','key':'latest'}}}]}]}}}}}}
POLICY={'bindings':[{'role':lean.EXECUTOR_ROLE,'members':['serviceAccount:s@p.iam.gserviceaccount.com','serviceAccount:web@p.iam.gserviceaccount.com']},
                    {'role':'roles/other','members':['user:x@y.z']}]}


class Fake:
    def __init__(self):self.calls=[];self.env_file=None
    def __call__(self,args):
        self.calls.append(args)
        if args[:3]==['run','jobs','describe']:return 0,json.dumps(JOB),''
        if args[:3]==['run','jobs','get-iam-policy']:return 0,json.dumps(POLICY),''
        for a in args:
            if a.startswith('--env-vars-file='):self.env_file=json.loads(Path(a.split('=',1)[1]).read_text())
        return 0,'',''
    def mutations(self):return [c for c in self.calls if c[:3]!=['run','jobs','describe'] and c[:3]!=['run','jobs','get-iam-policy']]


class LeanTests(unittest.TestCase):
    def run_main(self,*argv):
        fake=Fake()
        import io,contextlib
        buf=io.StringIO()
        with contextlib.redirect_stdout(buf):code=lean.main(list(argv),runner=fake)
        return fake,buf.getvalue(),code

    def test_dry_run_only_reads(self):
        fake,out,code=self.run_main()
        self.assertEqual(code,0);self.assertEqual(fake.mutations(),[]);self.assertIn('DRY RUN',out);self.assertIn('WOULD',out)
        self.assertNotIn('literal-secret-value',out)

    def test_apply_builds_light_job_copy_with_secrets_and_weight(self):
        fake,out,_=self.run_main('--apply')
        deploy=[c for c in fake.calls if c[:3]==['run','jobs','deploy']][0]
        self.assertIn('--cpu=1',deploy);self.assertIn('--memory=2Gi',deploy);self.assertIn('--image=img@sha256:abc',deploy)
        self.assertIn('--set-secrets=BUFFER_API_KEY=her-provider-buffer-key:latest',deploy)
        self.assertEqual(fake.env_file['HER_COMPUTE_WEIGHT'],'0.25');self.assertEqual(fake.env_file['HER_COMPUTE_BUDGET'],'1')
        self.assertEqual(fake.env_file['KEY'],'literal-secret-value');self.assertNotIn('BUFFER_API_KEY',fake.env_file)
        self.assertNotIn('literal-secret-value',out+json.dumps(deploy))  # never printed or put on the command line

    def test_heavy_job_capped_and_metered(self):
        fake,_,_=self.run_main('--apply')
        update=[c for c in fake.calls if c[:3]==['run','jobs','update']][0]
        self.assertIn('--task-timeout=3000s',update);self.assertIn('--update-env-vars=HER_COMPUTE_BUDGET=1,HER_COMPUTE_WEIGHT=1',update)

    def test_scheduler_targets_and_paused_state_untouched(self):
        fake,_,_=self.run_main('--apply')
        sched={c[4].split('-')[-1]:c for c in fake.calls if c[:4]==['scheduler','jobs','update','http']}
        self.assertEqual(set(sched),set(lean.STEPS))
        for step,call in sched.items():
            uri=[a for a in call if a.startswith('--uri=')][0]
            self.assertTrue(uri.endswith('/jobs/her-autopilot:run' if step=='generate' else '/jobs/her-autopilot-light:run'),uri)
            self.assertIn('--schedule='+lean.SCHEDULES[step],call)
            self.assertIn(step,json.loads([a for a in call if a.startswith('--message-body=')][0].split('=',1)[1])['overrides']['containerOverrides'][0]['args'])
        self.assertFalse([c for c in fake.calls if c[:3]==['scheduler','jobs','resume']])

    def test_executors_are_copied_to_light_job(self):
        fake,_,_=self.run_main('--apply')
        members=[a.split('=',1)[1] for c in fake.calls if c[:3]==['run','jobs','add-iam-policy-binding'] for a in c if a.startswith('--member=')]
        self.assertEqual(members,POLICY['bindings'][0]['members'])

    def test_resume_only_resumes(self):
        fake,_,_=self.run_main('--resume')
        self.assertEqual([c[3] for c in fake.mutations()],[f'her-autopilot-{s}' for s in lean.STEPS])
        self.assertTrue(all(c[:3]==['scheduler','jobs','resume'] for c in fake.mutations()))

    def test_failure_stops_with_message(self):
        def failing(args):
            return (1,'','PERMISSION_DENIED') if args[:3]==['run','jobs','deploy'] else Fake()(args)
        with self.assertRaises(SystemExit) as caught:lean.main(['--apply'],runner=failing)
        self.assertIn('PERMISSION_DENIED',str(caught.exception))

    def test_schedules_match_terraform_defaults(self):
        text=(ROOT/'deploy'/'autopilot'/'main.tf').read_text()
        block=text[text.index('variable "autopilot_schedules"'):]
        block=block[:block.index('validation')]
        terraform=dict(re.findall(r'(\w+)\s*=\s*"([^"]+)"',block.split('default = {',1)[1]))
        self.assertEqual(terraform,lean.SCHEDULES)


if __name__=='__main__':unittest.main()
