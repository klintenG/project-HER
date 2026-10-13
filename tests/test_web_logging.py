"""Server logs must retain the failures delivered to the browser."""
import json
import subprocess
import tempfile
import time
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import config
import web_ui
from agent.news_models import NewsError
from agent.orchestrator import PipelineResult
from utils.progress import StageInfo


class WebLoggingTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for mapping in (web_ui._active_jobs, web_ui._progress_queues, web_ui._job_results):
            self.stack.enter_context(patch.dict(mapping, clear=True))
        self.stack.enter_context(patch("web_ui._check_and_reserve_quota", return_value=None))
        self.stack.enter_context(patch("web_ui.get_provider_info", return_value={"ready": True}))
        self.stack.enter_context(patch("agent.news_script.NewsLLM"))
        for name in ("FPS", "VIDEO_BITRATE", "RENDER_THREADS"):
            self.stack.enter_context(patch.object(config, name, getattr(config, name)))
        thread = self.stack.enter_context(patch("web_ui.threading.Thread"))
        thread.return_value.start.side_effect = lambda: thread.call_args.kwargs["target"]()
        self.client = web_ui.app.test_client()

    def test_old_live_job_remains_pollable_and_keeps_failure_stage(self):
        job_id='long-running-render'
        web_ui._active_jobs[job_id]={'started':time.time()-1200,'thread':SimpleNamespace(is_alive=lambda:True),'stage':'compose'}
        response=self.client.get('/api/result/'+job_id)
        self.assertEqual(response.status_code,202)
        self.assertEqual(response.json,{'status':'running'})
        self.assertIn(job_id,web_ui._active_jobs)
        with self.assertLogs('web_ui',level='ERROR') as logs:
            web_ui._log_job_failure(job_id,'news','Export fixture failure')
        self.assertIn('stage=compose',logs.output[0])
        web_ui._job_results[job_id]={'error':'Export fixture failure'}
        response=self.client.get('/api/result/'+job_id)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['error'],'Export fixture failure')

    def test_cleanup_removes_dead_workers_and_abandoned_reservations(self):
        now=time.time();live=SimpleNamespace(is_alive=lambda:True);dead=SimpleNamespace(is_alive=lambda:False)
        web_ui._active_jobs.update({
            'live':{'started':now-1200,'thread':live},
            'dead':{'started':now-1,'thread':dead},
            'new-reservation':{'started':now-30,'thread':None},
            'abandoned':{'started':now-601,'thread':None},
            'completed':{'started':now-30,'thread':live},
        })
        web_ui._job_results['completed']={'success':True}
        web_ui._prune_active_jobs()
        self.assertEqual(set(web_ui._active_jobs),{'live','new-reservation'})

    def test_browser_keeps_polling_confirmed_running_job_until_result(self):
        # Run the actual browser function with a delayed result, starting at the
        # former timeout boundary. No network, browser or provider is required.
        code=r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(process.argv[1],'utf8');
const start=html.indexOf('function pollResult(');
let end=html.indexOf('{',start),depth=0;
do {if(html[end]==='{')depth++;if(html[end]==='}')depth--;end++;} while(depth);
const replies=[{status:'running'},{status:'running'},{video_url:'/output/finished.mp4'}];
const timers=[],displayed=[];let stopped=0,polls=0;
const sandbox={fetch:async()=>{polls++;return {ok:true,json:async()=>replies.shift()};},
 setTimeout:fn=>timers.push(fn),document:{getElementById:()=>({textContent:''})},
 stopTimer:()=>stopped++,showToast:()=>assert.fail('Live job timed out'),
 resetToStudio:()=>assert.fail('Live job reset'),displayResult:value=>displayed.push(value)};
vm.runInNewContext(html.slice(start,end)+";pollResult('long-job',120);",sandbox);
(async()=>{for(let i=0;i<3;i++){await new Promise(setImmediate);if(timers.length)timers.shift()();}
 await new Promise(setImmediate);assert.equal(polls,3);assert.equal(stopped,1);
 assert.equal(displayed[0].video_url,'/output/finished.mp4');})().catch(error=>{console.error(error);process.exitCode=1;});
"""
        template=Path(__file__).resolve().parents[1]/'templates/index.html'
        result=subprocess.run(['node','-e',code,str(template)],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def generate_failure(self, mode, *, raises=False):
        error = "Cutout provider failed: fixture service unavailable"

        def fail(*args, **kwargs):
            kwargs["progress_callback"](StageInfo(
                name="cutouts", label="Generating cutouts", index=5, total=9,
                status="failed", message=error))
            if raises:
                raise RuntimeError(error)
            return PipelineResult(errors=[error], news_details={"status": "error", "error": error})

        target = "agent.news_pipeline.run_news" if mode == "news" else "agent.orchestrator.AgentOrchestrator"
        with patch(target) as pipeline, self.assertLogs("web_ui", level="ERROR") as logs:
            if mode == "news":
                pipeline.side_effect = fail
            else:
                pipeline.return_value.run.side_effect = fail
            response = self.client.post("/api/generate", json={
                "content_mode": mode, "text": "A supplied event account", "ai_images": True})
        self.assertEqual(response.status_code, 200)
        job_id = response.json["job_id"]
        result = self.client.get("/api/result/" + job_id).json
        self.assertEqual(result["error"], error)
        message = "\n".join(logs.output)
        for detail in (error, job_id, "mode=" + mode, "stage=cutouts", "status=error"):
            self.assertIn(detail, message)
        events = self.client.get("/api/progress/" + job_id).get_data(as_text=True)
        self.assertIn("event: progress", events)
        self.assertIn("event: done", events)
        self.assertIn(json.dumps(error), events)
        self.assertNotIn(job_id, web_ui._active_jobs)
        return logs

    def test_news_returned_failure_logs_ui_error_and_job_stage(self):
        self.generate_failure("news")

    def test_legacy_returned_failure_logs_ui_error_and_job_stage(self):
        self.generate_failure("article")

    def test_worker_exceptions_log_traceback_and_preserve_ui_delivery(self):
        for mode in ("news", "article"):
            with self.subTest(mode=mode):
                logs = self.generate_failure(mode, raises=True)
                self.assertTrue(logs.records[0].exc_info)
                self.assertIn("Traceback (most recent call last)", logs.output[0])
                self.assertIn("RuntimeError:", logs.output[0])

    def test_news_pipeline_retains_traceback_when_returning_failure(self):
        from agent.news_pipeline import run_news
        with tempfile.TemporaryDirectory() as directory:
            with patch("agent.news_pipeline.analyze_input", side_effect=RuntimeError("fixture resolver crash")), \
                    self.assertLogs("agent.news_pipeline", level="ERROR") as logs:
                result = run_news("An event", llm=object(), output_dir=directory)
            self.assertFalse(result.success)
            self.assertEqual(result.errors, ["fixture resolver crash"])
            self.assertEqual(json.loads((Path(directory) / "news_failure.json").read_text())["error"], result.errors[0])
        self.assertTrue(logs.records[0].exc_info)
        self.assertIn("stage=resolve", logs.output[0])
        self.assertIn("RuntimeError: fixture resolver crash", logs.output[0])

    def test_generation_validation_errors_log_same_response_details(self):
        for mode in ("news", "article"):
            with self.subTest(mode=mode), self.assertLogs("web_ui", level="ERROR") as logs:
                response = self.client.post("/api/generate", json={"content_mode": mode})
            self.assertEqual(response.status_code, 400)
            self.assertIn(response.json["error"], logs.output[0])
            self.assertIn("/api/generate", logs.output[0])
            self.assertIn("HTTP 400", logs.output[0])

    def test_expected_preview_error_is_logged_without_traceback(self):
        with patch("agent.news_pipeline.preview_news", side_effect=NewsError("No readable event sources")), \
                self.assertLogs("web_ui", level="ERROR") as logs:
            response = self.client.post("/api/preview", json={"content_mode": "news", "text": "An event"})
        self.assertEqual(response.status_code, 422)
        self.assertIn(response.json["error"], logs.output[0])
        self.assertIn("/api/preview", logs.output[0])
        self.assertIsNone(logs.records[0].exc_info)

    def test_studio_generation_enforces_fixed_defaults_on_server(self):
        with patch('web_ui._start_news_job',return_value=({'job_id':'fixed-studio'},200)) as start:
            response=self.client.post('/api/generate',json={
                'ui_profile':'editorial_studio','text':'A supplied story',
                'content_mode':'article','tone':'dramatic','format':'square',
                'renderer':'moviepy','visual_preset':'default','tts_provider':'edge_tts',
                'news_music':True,'platform':'youtube','local_assets':'other.json'})
        self.assertEqual(response.status_code,200)
        data,source=start.call_args.args
        self.assertEqual(source,'A supplied story')
        self.assertEqual({key:data[key] for key in web_ui.STUDIO_GENERATION_DEFAULTS},{
            'tone':'informative','format':'vertical','visual_style':'claymorphism',
            'target_duration':0,'content_mode':'news','renderer':'remotion',
            'visual_preset':'reference_editorial','editorial_text':'editorial',
            'editorial_assets':'auto','news_source_policy':'auto','tts_provider':'replicate','news_music':False})
        self.assertEqual(data['platform'],'');self.assertIsNone(data['local_assets'])

    def test_studio_preview_uses_same_news_defaults(self):
        with patch('agent.news_pipeline.preview_news',return_value={}) as preview:
            response=self.client.post('/api/preview',json={
                'ui_profile':'editorial_studio','text':'A supplied story',
                'content_mode':'article','tone':'dramatic','target_duration':120,'news_source_policy':'online'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(preview.call_args.args[0],'A supplied story')
        self.assertEqual(preview.call_args.kwargs['tone'],'informative')
        self.assertEqual(preview.call_args.kwargs['target_duration'],0)
        self.assertEqual(preview.call_args.kwargs['source_policy'],'auto')

    def test_studio_browser_submits_defaults_without_removed_controls(self):
        html=self.client.get('/').get_data(as_text=True)
        removed=['selTone','selFormat','selVisualStyle','selDuration','selContentMode','selRenderer',
                 'newsVisualPreset','editorialText','editorialAssets','newsSourcePolicy','newsTtsProvider','newsMusic']
        for control in removed:self.assertNotIn('id="'+control+'"',html)
        code=r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(0,'utf8');
const defaults=html.match(/const STUDIO_DEFAULTS = Object.freeze\(([^;]+)\);/)[1];
const start=html.indexOf('async function handleGenerate(');let end=html.indexOf('{',start),depth=0;
do {if(html[end]==='{')depth++;if(html[end]==='}')depth--;end++;}while(depth);
const removed=new Set(['selTone','selFormat','selVisualStyle','selDuration','selContentMode','selRenderer','newsVisualPreset','editorialText','editorialAssets','newsSourcePolicy','newsTtsProvider','newsMusic']);
const node=()=>({style:{},append(){},replaceChildren(){},querySelector:()=>({})});
let submitted,job;
const sandbox={promptInput:{value:'A supplied story',focus(){}},document:{
 getElementById:id=>{assert(!removed.has(id),'Read removed control '+id);return node();},createElement:node},
 fetch:async(url,options)=>{assert.equal(url,'/api/generate');submitted=JSON.parse(options.body);return {json:async()=>({job_id:'studio-job'})};},
 setUIState(){},startTimer(){},stopTimer(){},showToast:message=>assert.fail(message),resetToStudio(){},connectSSE:id=>job=id};
(async()=>{await vm.runInNewContext('const STUDIO_DEFAULTS=Object.freeze('+defaults+');'+html.slice(start,end)+';handleGenerate();',sandbox);
 assert.equal(job,'studio-job');assert.equal(submitted.text,'A supplied story');assert.equal(submitted.ui_profile,'editorial_studio');
 for(const [key,value] of Object.entries({tone:'informative',format:'vertical',visual_style:'claymorphism',target_duration:0,content_mode:'news',renderer:'remotion',visual_preset:'reference_editorial',editorial_text:'editorial',editorial_assets:'auto',news_source_policy:'auto',tts_provider:'replicate',news_music:false}))assert.deepEqual(submitted[key],value,key);
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
        result=subprocess.run(['node','-e',code],input=html,capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_unexpected_preview_errors_log_tracebacks(self):
        for mode in ("news", "article"):
            target = "agent.news_pipeline.preview_news" if mode == "news" else "agent.orchestrator.AgentOrchestrator"
            with self.subTest(mode=mode), patch(target, side_effect=RuntimeError("fixture preview crash")), \
                    self.assertLogs("web_ui", level="ERROR") as logs:
                response = self.client.post("/api/preview", json={"content_mode": mode, "text": "An event"})
            self.assertIn(response.status_code, (422, 500))
            self.assertTrue(any(record.exc_info for record in logs.records))
            self.assertIn("RuntimeError: fixture preview crash", "\n".join(logs.output))
            self.assertIn(response.json["error"], "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
