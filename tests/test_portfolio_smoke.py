"""Recovery checks must never create or repeat a billed generation."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
from scripts import smoke_native_portfolio as smoke

class SmokeRecoveryTests(unittest.TestCase):
    def test_resume_uses_existing_job_even_with_creation_flags(self):
        jid='a'*32;token='b'*64
        session=MagicMock();session.headers={}
        caps=MagicMock();caps.json.return_value={'enabled':False}
        status=MagicMock();status.json.return_value={'status':'failed','stage':None,'error':'fixture failure','created_at':100,'updated_at':200}
        events=MagicMock();events.headers={'Content-Type':'text/event-stream'};events.iter_lines.return_value=iter([b'event: done'])
        session.get.side_effect=[caps,status,events]
        with tempfile.TemporaryDirectory() as folder:
            args=['smoke','--resume-ui-job',jid,'--browser-submit','--allow-paid-generation','--output',folder]
            with patch('sys.argv',args),patch('sys.stdin',io.StringIO(token)),patch.object(smoke.requests,'Session',return_value=session),patch.object(smoke.subprocess,'run') as launch:
                with self.assertRaisesRegex(RuntimeError,'Real job did not complete'):smoke.main()
            session.post.assert_not_called();launch.assert_not_called()
            self.assertNotIn('POST',session.mount.call_args.args[1].max_retries.allowed_methods)
            raw=(Path(folder)/'smoke.json').read_text();self.assertNotIn(token,raw)
            self.assertTrue(json.loads(raw)['resumed_existing_job'])
    def test_resume_rejects_missing_scoped_access_without_submission(self):
        session=MagicMock();caps=MagicMock();caps.json.return_value={'enabled':True};session.get.return_value=caps
        with patch('sys.argv',['smoke','--resume-ui-job','a'*32]),patch('sys.stdin',io.StringIO('')),patch.object(smoke.requests,'Session',return_value=session):
            with self.assertRaisesRegex(RuntimeError,'scoped token on stdin'):smoke.main()
        session.post.assert_not_called();self.assertEqual(session.get.call_count,1)

if __name__=='__main__':unittest.main()
