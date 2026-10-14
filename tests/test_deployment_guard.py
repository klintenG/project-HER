"""Deployments pause new admissions and drain rather than terminate active work."""
import copy
import unittest
from unittest.mock import MagicMock
from utils.deployment_guard import DeploymentGuard


class DeploymentGuardTests(unittest.TestCase):
    def setUp(self):
        self.time=0;self.calls=[]
        self.policy={'fields':{'disabled':{'booleanValue':False},'daily_limits_disabled':{'booleanValue':True}},'updateTime':'v1'}
        self.states=['running','completed']
        self.session=MagicMock();self.session.request.side_effect=self.request
    def request(self,method,url,**kwargs):
        key=url.rsplit('/',1)[-1];self.calls.append((method,key,kwargs))
        if key=='policy':
            if method=='PATCH':
                self.policy['fields'].update(copy.deepcopy(kwargs['json']['fields']));self.policy['updateTime']+='x'
            value=copy.deepcopy(self.policy)
        elif key=='active':value={'fields':{'jobs':{'mapValue':{'fields':{'a'*32:{'doubleValue':99999}}}}}}
        else:value={'fields':{'status':{'stringValue':self.states.pop(0) if len(self.states)>1 else self.states[0]}}}
        response=MagicMock(status_code=200);response.json.return_value=value;return response
    def sleep(self,seconds):self.time+=seconds
    def guard(self,**kwargs):
        return DeploymentGuard('fixture',session=self.session,token_provider=lambda:'operator-fixture',clock=lambda:self.time,sleep=self.sleep,timeout=10,**kwargs)
    def test_waits_for_live_job_and_preserves_other_policy_settings(self):
        with self.guard():
            self.assertTrue(self.policy['fields']['maintenance']['booleanValue']);self.assertEqual(self.time,5)
            self.assertEqual(self.states,['completed'])
        self.assertFalse(self.policy['fields']['maintenance']['booleanValue'])
        self.assertFalse(self.policy['fields']['disabled']['booleanValue'])
        self.assertTrue(self.policy['fields']['daily_limits_disabled']['booleanValue'])
        self.assertFalse(any(key.startswith('job:') and method!='GET' for method,key,_ in self.calls))
    def test_timeout_aborts_without_terminating_or_replaying_job(self):
        self.states=['running']
        with self.assertRaisesRegex(RuntimeError,'deployment aborted'):
            with self.guard():self.fail('Deployment must never proceed')
        self.assertFalse(self.policy['fields']['maintenance']['booleanValue'])
    def test_deployment_failure_clears_own_maintenance(self):
        self.states=['completed']
        with self.assertRaisesRegex(RuntimeError,'build failed'):
            with self.guard():raise RuntimeError('build failed')
        self.assertFalse(self.policy['fields']['maintenance']['booleanValue'])
    def test_foreign_maintenance_is_not_overwritten(self):
        self.policy['fields']['maintenance']={'booleanValue':True}
        with self.assertRaisesRegex(RuntimeError,'Another deployment'):
            with self.guard():pass
        self.assertFalse(any(method=='PATCH' for method,_,_ in self.calls))
    def test_transition_from_old_backend_uses_emergency_pause_and_restores_it(self):
        self.states=['completed']
        with self.guard(legacy_pause=True):self.assertTrue(self.policy['fields']['disabled']['booleanValue'])
        self.assertFalse(self.policy['fields']['disabled']['booleanValue'])


if __name__=='__main__':unittest.main()
