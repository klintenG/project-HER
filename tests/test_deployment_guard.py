"""Deployments pause new admissions and drain rather than terminate active work."""
import copy
import unittest
from unittest.mock import MagicMock
import requests
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
    def test_force_maintenance_clear_overrides_stale_lock(self):
        self.policy['fields']['maintenance']={'booleanValue':True}
        self.states=['completed']
        with self.guard(force_maintenance_clear=True):
            self.assertTrue(self.policy['fields']['maintenance']['booleanValue'])
        self.assertFalse(self.policy['fields']['maintenance']['booleanValue'])
    def test_transition_from_old_backend_uses_emergency_pause_and_restores_it(self):
        self.states=['completed']
        with self.guard(legacy_pause=True):self.assertTrue(self.policy['fields']['disabled']['booleanValue'])
        self.assertFalse(self.policy['fields']['disabled']['booleanValue'])

    def test_transient_firestore_read_timeout_retries_without_repeating_write(self):
        original=self.session.request.side_effect;calls=[0]
        def flaky(method,url,**kwargs):
            if method=='GET' and calls[0]==0:
                calls[0]+=1;raise requests.ReadTimeout('temporary')
            return original(method,url,**kwargs)
        self.session.request.side_effect=flaky;self.states=['completed']
        with self.guard():pass
        self.assertEqual(calls[0],1)
        self.assertFalse(self.policy['fields']['maintenance']['booleanValue'])

    def test_cleanup_timeout_preserves_original_deploy_failure(self):
        self.states=['completed'];original=self.session.request.side_effect
        def cleanup_fails(method,url,**kwargs):
            if getattr(self,'fail_cleanup',False) and method=='GET' and url.endswith('/policy'):
                raise requests.ReadTimeout('temporary')
            return original(method,url,**kwargs)
        self.session.request.side_effect=cleanup_fails
        with self.assertRaisesRegex(RuntimeError,'build failed'):
            with self.guard():
                self.fail_cleanup=True
                raise RuntimeError('build failed')

    def test_cleanup_patch_timeout_rechecks_owner_then_retries(self):
        self.states=['completed'];original=self.session.request.side_effect;patches=[0]
        def flaky(method,url,**kwargs):
            if method=='PATCH' and url.endswith('/policy') and not kwargs['json']['fields']['maintenance']['booleanValue']:
                patches[0]+=1
                if patches[0]==1:raise requests.ReadTimeout('temporary')
            return original(method,url,**kwargs)
        self.session.request.side_effect=flaky
        with self.guard():pass
        self.assertEqual(patches[0],2)
        self.assertFalse(self.policy['fields']['maintenance']['booleanValue'])


if __name__=='__main__':unittest.main()
