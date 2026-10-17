import tempfile
import unittest
from unittest.mock import patch
from utils.provider_admission import ProviderAdmission


class AdmissionTests(unittest.TestCase):
    def test_independent_instances_share_pacing_without_plaintext_credential(self):
        with tempfile.TemporaryDirectory() as root,patch('utils.provider_admission.time.time',return_value=100):
            first=ProviderAdmission('private-token',interval=12,root=root)
            second=ProviderAdmission('private-token',interval=12,root=root)
            self.assertEqual(first._update(),0)
            self.assertEqual(second._update(),12)
            # A waiting/cancelled task must not book another future slot.
            self.assertEqual(second._update(),12)
            self.assertNotIn('private-token',str(first.path))
            self.assertNotIn('private-token',first.path.read_text())

    def test_throttling_delays_other_instances(self):
        with tempfile.TemporaryDirectory() as root,patch('utils.provider_admission.time.time',return_value=100):
            first=ProviderAdmission('token',interval=1,root=root)
            second=ProviderAdmission('token',interval=1,root=root)
            first.throttled(20)
            self.assertEqual(second._update(),20)

    def test_real_processes_share_admission_despite_different_monotonic_origins(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as root:
            first=ProviderAdmission('process-fixture',interval=2,root=root)
            self.assertEqual(first._update(),0)
            code="from utils.provider_admission import ProviderAdmission; import time,sys; time.monotonic=lambda:999999; print(ProviderAdmission('process-fixture',interval=2,root=sys.argv[1])._update())"
            result=subprocess.run([sys.executable,'-c',code,root],capture_output=True,text=True,check=True)
            delay=float(result.stdout)
            self.assertGreater(delay,0)
            self.assertLessEqual(delay,2)
