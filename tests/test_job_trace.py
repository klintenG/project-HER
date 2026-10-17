import json
import tempfile
import threading
import unittest
from pathlib import Path
from utils.job_trace import JobTrace


class TraceTests(unittest.TestCase):
    def test_failure_persists_only_error_type_and_no_private_payload(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'trace.json';trace=JobTrace(path,'job')
            with self.assertRaises(RuntimeError):
                with trace.span('image_provider_wait'):
                    raise RuntimeError('secret protected prompt')
            data=path.read_text();row=json.loads(data)['spans'][0]
            self.assertEqual(row['status'],'failed')
            self.assertEqual(row['error_type'],'RuntimeError')
            self.assertNotIn('secret',data)
            self.assertGreaterEqual(row['duration_seconds'],0)

    def test_concurrent_spans_are_atomic_and_wall_time_is_not_summed(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'trace.json';trace=JobTrace(path,'job');barrier=threading.Barrier(2)
            def worker():
                with trace.span('image_provider_wait'):barrier.wait(timeout=3)
            threads=[threading.Thread(target=worker) for _ in range(2)]
            for thread in threads:thread.start()
            for thread in threads:thread.join()
            data=json.loads(path.read_text());self.assertEqual(len(data['spans']),2)
            self.assertTrue(all(s['status']=='succeeded' for s in data['spans']))
            self.assertLessEqual(data['covered_wall_seconds'],sum(s['duration_seconds'] for s in data['spans'])+.00001)
