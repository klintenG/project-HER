"""Speech failures must recover without stale files, paid loops, or invented timing."""
import io
import subprocess
import tempfile
import threading
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import config
from agent.news_audio import synthesize, _make_engine, probe_duration
from agent.news_models import NewsError
from agent.news_tts import NewsReplicateTTS, KOKORO, CHATTERBOX, VERSIONS
from tests.news_fixtures import SCRIPT, FixtureTTS


def wav_bytes():
    buffer=io.BytesIO()
    with wave.open(buffer,'wb') as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(24000)
        audio.writeframes(b'\0\0'*12000)
    return buffer.getvalue()


class FailingTTS:
    def generate_narration(self,*args):
        raise RuntimeError('Google TTS failed 2 consecutive screens (likely rate-limited). Triggering fallback.')


class NewsSpeechTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        sentences=SCRIPT.sentences[:2]
        self.script=SCRIPT.model_copy(update={'sentences':sentences,'narration':' '.join(s.text for s in sentences)})

    def test_google_quota_recovers_with_complete_replicate_audio(self):
        with patch('agent.news_audio._make_engine',return_value=FixtureTTS()) as factory, self.assertLogs('agent.news_audio',level='INFO') as logs:
            audio=synthesize(self.script,self.root,'google_tts',engine=FailingTTS())
        self.assertEqual(factory.call_args.args[0],'replicate')
        self.assertEqual(audio.provider,'replicate'); self.assertEqual(len(audio.fallbacks),1)
        self.assertEqual(len(audio.phrases),2); self.assertEqual(audio.words,[])
        self.assertAlmostEqual(audio.duration,probe_duration(audio.path),places=3)
        self.assertIn('next=replicate',' '.join(logs.output))

    def test_partial_google_clips_are_replaced_in_full(self):
        partial=MagicMock()
        partial.generate_narration.side_effect=lambda points,path:FixtureTTS().generate_narration(points,path)[:1]
        with patch('agent.news_audio._make_engine',return_value=FixtureTTS()):
            audio=synthesize(self.script,self.root,'google_tts',engine=partial)
        self.assertEqual(audio.provider,'replicate'); self.assertEqual(len(audio.phrases),2)
        self.assertIn('exactly one clip',audio.fallbacks[0])

    def test_corrupt_audio_triggers_fallback_even_if_file_exists(self):
        def generate(points,path):
            corrupt=path/'bad.wav';corrupt.write_bytes(b'not audio')
            return [SimpleNamespace(index=i,audio_path=corrupt,word_timings=[]) for i in range(len(points))]
        broken=MagicMock(); broken.generate_narration.side_effect=generate
        with patch('agent.news_audio._make_engine',return_value=FixtureTTS()):
            audio=synthesize(self.script,self.root,'google_tts',engine=broken)
        self.assertEqual(audio.provider,'replicate')

    def test_failed_replicate_moves_to_edge_and_keeps_native_timing(self):
        def factory(provider,*args):
            return FailingTTS() if provider=='replicate' else FixtureTTS()
        with patch('agent.news_audio._make_engine',side_effect=factory):
            audio=synthesize(self.script,self.root,'google_tts',engine=FailingTTS())
        self.assertEqual(audio.provider,'edge_tts'); self.assertEqual(len(audio.fallbacks),2)
        self.assertEqual(audio.method,'native_words'); self.assertTrue(audio.words)

    def test_missing_replicate_key_falls_through_to_edge(self):
        original=_make_engine
        def factory(provider,*args):
            return FixtureTTS() if provider=='edge_tts' else original(provider,*args)
        with patch.object(config,'REPLICATE_API_TOKEN',''),patch('agent.news_audio._make_engine',side_effect=factory):
            audio=synthesize(self.script,self.root,'google_tts',engine=FailingTTS())
        self.assertEqual(audio.provider,'edge_tts');self.assertIn('TOKEN is missing',audio.fallbacks[1])

    def test_explicit_edge_never_calls_a_paid_fallback(self):
        with patch('agent.news_audio._make_engine') as factory:
            audio=synthesize(self.script,self.root,'edge_tts',engine=FixtureTTS())
        factory.assert_not_called(); self.assertEqual(audio.fallbacks,[])

    def test_all_providers_fail_once_with_actionable_final_error(self):
        with patch('agent.news_audio._make_engine',return_value=FailingTTS()) as factory:
            with self.assertRaisesRegex(NewsError,'All News narration providers failed.*edge_tts'):
                synthesize(self.script,self.root,'google_tts',engine=FailingTTS())
        self.assertEqual(factory.call_count,2)

    def test_attempts_use_distinct_directories_and_close_sessions(self):
        failed=FailingTTS(); failed._session=MagicMock()
        good=FixtureTTS();good._session=MagicMock()
        with patch('agent.news_audio._make_engine',return_value=good):
            synthesize(self.script,self.root,'google_tts',engine=failed)
            synthesize(self.script,self.root,'google_tts',engine=failed)
        self.assertEqual(len(list((self.root/'narration_attempts').iterdir())),2)
        self.assertEqual(failed._session.close.call_count,2);self.assertEqual(good._session.close.call_count,2)

    def test_cancelled_generation_does_not_trigger_paid_fallback(self):
        event=threading.Event()
        cancelled=MagicMock()
        def fail(*args):
            event.set();raise RuntimeError('cancelled during speech')
        cancelled.generate_narration.side_effect=fail
        with patch('agent.news_audio._make_engine') as factory:
            with self.assertRaises(NewsError) as error:
                synthesize(self.script,self.root,'google_tts',engine=cancelled,cancel_event=event)
        self.assertEqual(error.exception.status,'cancelled');factory.assert_not_called()

    def test_foreign_edge_fallback_uses_matching_language_voice(self):
        with patch('agent.narration.NarrationEngine') as edge:
            _make_engine('edge_tts','aria','+0%','hindi',None)
        self.assertEqual(edge.call_args.kwargs['voice'],config.LANGUAGE_VOICES['hi']['voice'])

    def test_unknown_provider_does_not_spend_money(self):
        with patch('agent.news_audio._make_engine') as factory:
            with self.assertRaisesRegex(NewsError,'Unknown News speech'):
                synthesize(self.script,self.root,'typo')
        factory.assert_not_called()

    def test_explicit_replicate_keeps_provider_when_retries_are_exhausted(self):
        with patch.object(config,'NEWS_REPLICATE_ONLY',True),patch('agent.news_audio._make_engine') as factory:
            with self.assertRaisesRegex(NewsError,'All News narration providers failed.*replicate'):
                synthesize(self.script,self.root,'replicate',engine=FailingTTS())
        factory.assert_not_called()

    def test_replicate_fallback_can_be_enabled_explicitly(self):
        with patch.object(config,'NEWS_REPLICATE_ONLY',False),patch('agent.news_audio._make_engine',return_value=FixtureTTS()) as factory:
            audio=synthesize(self.script,self.root,'replicate',engine=FailingTTS())
        self.assertEqual(audio.provider,'edge_tts');self.assertEqual(factory.call_args.args[0],'edge_tts')

    def test_mp3_padding_uses_decoded_samples_for_long_narration(self):
        # MP3 duration includes frame/encoder padding. The old MoviePy path
        # overwrote its reader duration with this value and read past EOF.
        source=self.root/'padded.mp3'
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',
            'sine=frequency=440:sample_rate=24000:duration=0.234',
            '-c:a','libmp3lame',str(source)],check=True,capture_output=True)
        raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(source),
            '-ac','2','-ar','44100','-f','s16le','-'])
        samples=len(raw)//4;decoded_duration=samples/44100
        sentences=[self.script.sentences[0].model_copy(update={'id':f's{i}'}) for i in range(12)]
        script=self.script.model_copy(update={'sentences':sentences,'narration':' '.join(s.text for s in sentences)})
        engine=MagicMock()
        engine.generate_narration.side_effect=lambda points,out:[SimpleNamespace(index=p.index,audio_path=source,duration=999,word_timings=[]) for p in points]
        pause=.01371;pause_samples=round(pause*44100)
        # Inject an overreported input duration to exercise the EOF regression
        # regardless of this FFmpeg build's gapless-MP3 metadata behavior.
        def metadata_duration(path):
            return decoded_duration+.05 if Path(path)==source else probe_duration(path)
        with patch('agent.news_audio.probe_duration',side_effect=metadata_duration),patch('agent.news_audio._make_engine') as fallback:
            audio=synthesize(script,self.root/'assembled','edge_tts',engine=engine,pause=pause)
        fallback.assert_not_called()
        with wave.open(audio.path,'rb') as result:
            self.assertEqual(result.getnframes(),12*samples+11*pause_samples)
        self.assertAlmostEqual(audio.duration,(12*samples+11*pause_samples)/44100,places=5)
        for i,boundary in enumerate(audio.phrases):
            self.assertAlmostEqual(boundary.start,i*(samples+pause_samples)/44100,places=8)
            self.assertAlmostEqual(boundary.end-boundary.start,decoded_duration,places=8)
        self.assertFalse(list((self.root/'assembled').rglob('decoded-*')))


class ReplicateSpeechTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        for name,value in [('REPLICATE_API_TOKEN','fixture-token'),('NEWS_TTS_CACHE',self.root/'cache'),
                           ('NEWS_REPLICATE_MIN_INTERVAL',0),('NEWS_REPLICATE_RATE_LIMIT_RETRIES',2),('NEWS_REPLICATE_RATE_LIMIT_WAIT',90)]:
            p=patch.object(config,name,value);p.start();self.addCleanup(p.stop)
        self.points=[SimpleNamespace(index=0,narration='Argentina won the World Cup.')]

    def engine(self,**kwargs):
        engine=NewsReplicateTTS(**kwargs);self.addCleanup(engine._session.close);return engine

    def test_model_and_language_are_bounded_before_network(self):
        with self.assertRaisesRegex(NewsError,'must be'):
            self.engine(model='expensive/unknown')
        for model,language in [(KOKORO,'de'),(CHATTERBOX,'hi')]:
            with self.assertRaisesRegex(NewsError,'does not support'):
                self.engine(model=model,language=language)
        self.assertEqual(self.engine(model=KOKORO,language='hindi').voice,'hf_alpha')

    def test_cache_reuses_exact_valid_audio_and_changes_for_speed(self):
        engine=self.engine(model=KOKORO)
        with patch.object(engine,'_predict',return_value=wav_bytes()) as predict:
            first=engine.generate_narration(self.points,self.root/'one')
            second=engine.generate_narration(self.points,self.root/'two')
        predict.assert_called_once();self.assertEqual(first[0].duration,.5)
        self.assertEqual(second[0].word_timings,[])
        self.assertEqual(Path(first[0].audio_path).read_bytes(),Path(second[0].audio_path).read_bytes())
        faster=self.engine(model=KOKORO,speed='+20%')
        with patch.object(faster,'_predict',return_value=wav_bytes()) as predict:
            faster.generate_narration(self.points,self.root/'faster')
        self.assertEqual(predict.call_args.args[0]['speed'],1.2)

    def test_corrupted_cache_is_regenerated(self):
        engine=self.engine(model=KOKORO)
        with patch.object(engine,'_predict',return_value=wav_bytes()) as predict:
            engine.generate_narration(self.points,self.root/'one')
            next((self.root/'cache').glob('*.wav')).write_bytes(b'broken')
            engine.generate_narration(self.points,self.root/'two')
        self.assertEqual(predict.call_count,2)

    def test_turbo_character_limit_preflights_entire_script(self):
        engine=self.engine(model=CHATTERBOX)
        points=self.points+[SimpleNamespace(index=1,narration='x'*501)]
        with patch.object(engine,'_predict') as predict:
            with self.assertRaisesRegex(NewsError,'500 characters'):
                engine.generate_narration(points,self.root)
        predict.assert_not_called()

    def test_prediction_uses_pinned_schema_and_bounded_download(self):
        engine=self.engine(model=KOKORO)
        response=MagicMock(status_code=201)
        response.json.return_value={'id':'p123','status':'succeeded','output':'https://replicate.delivery/audio.wav'}
        with patch.object(engine._session,'request',return_value=response) as request,patch('agent.news_research.fetch',return_value=(wav_bytes(),'https://replicate.delivery/audio.wav')) as fetch:
            engine.generate_narration(self.points,self.root)
        self.assertEqual(request.call_args.kwargs['json']['version'],VERSIONS[KOKORO])
        self.assertEqual(request.call_args.kwargs['headers']['Cancel-After'],'2m')
        self.assertEqual(fetch.call_args.kwargs['limit'],20_000_000)

    def test_pending_prediction_is_cancelled_on_job_cancellation(self):
        event=threading.Event();engine=self.engine(model=KOKORO,cancel_event=event)
        def response(*args,**kwargs):
            event.set();return {'id':'p123','status':'processing'}
        with patch.object(engine,'_request',side_effect=response),patch.object(engine._session,'post') as cancel:
            with self.assertRaises(NewsError) as error:
                engine.generate_narration(self.points,self.root)
        self.assertEqual(error.exception.status,'cancelled');self.assertTrue(cancel.call_args.args[0].endswith('/p123/cancel'))

    def test_failed_paid_prediction_is_not_retried_or_cached(self):
        engine=self.engine(model=KOKORO)
        with patch.object(engine,'_request',return_value={'id':'p123','status':'failed'}) as request:
            with self.assertRaisesRegex(NewsError,'prediction failed'):
                engine.generate_narration(self.points,self.root)
        request.assert_called_once();self.assertEqual(list((self.root/'cache').glob('*.wav')),[])

    def test_provider_error_does_not_expose_response_credentials(self):
        engine=self.engine(model=KOKORO)
        response=MagicMock(status_code=401,text='fixture-token secret response')
        with patch.object(engine._session,'request',return_value=response):
            with self.assertRaises(NewsError) as error:
                engine.generate_narration(self.points,self.root)
        self.assertIn('401',str(error.exception));self.assertNotIn('fixture-token',str(error.exception))

    def test_rejected_429_honors_reset_then_creates_only_one_prediction(self):
        engine=self.engine(model=KOKORO)
        rejected=MagicMock(status_code=429,headers={'Retry-After':'2'})
        accepted=MagicMock(status_code=201)
        accepted.json.return_value={'id':'p123','status':'succeeded','output':'https://replicate.delivery/audio.wav'}
        with patch.object(engine._session,'request',side_effect=[rejected,accepted]) as request,patch('agent.news_tts.time.sleep') as sleep,patch('agent.news_research.fetch',return_value=(wav_bytes(),'https://replicate.delivery/audio.wav')):
            engine.generate_narration(self.points,self.root)
        sleep.assert_called_once_with(3);self.assertEqual(request.call_count,2)

    def test_persistent_429_is_bounded_and_has_no_cached_audio(self):
        engine=self.engine(model=KOKORO)
        rejected=MagicMock(status_code=429,headers={})
        rejected.json.return_value={'detail':'Request was throttled. Your rate limit resets in ~30s.'}
        with patch.object(engine._session,'request',return_value=rejected) as request,patch('agent.news_tts.time.sleep') as sleep:
            with self.assertRaisesRegex(NewsError,'rate-limited'):
                engine.generate_narration(self.points,self.root)
        self.assertEqual(request.call_count,3);self.assertEqual(sleep.call_count,2)
        self.assertEqual(sleep.call_args.args[0],31)
        self.assertEqual(list((self.root/'cache').glob('*.wav')),[])

    def test_cancel_during_throttle_never_submits_again(self):
        event=threading.Event();engine=self.engine(model=KOKORO,cancel_event=event)
        rejected=MagicMock(status_code=429,headers={'Retry-After':'2'})
        def wait(seconds): event.set()
        with patch.object(engine._session,'request',return_value=rejected) as request,patch.object(event,'wait',side_effect=wait):
            with self.assertRaises(NewsError) as error:
                engine.generate_narration(self.points,self.root)
        self.assertEqual(error.exception.status,'cancelled');request.assert_called_once()

    def test_remote_timeout_cancels_prediction_without_new_paid_call(self):
        engine=self.engine(model=KOKORO)
        with patch.object(engine,'_request',return_value={'id':'p123','status':'processing'}) as request,patch('agent.news_tts.time.monotonic',side_effect=[0,121]),patch.object(engine._session,'post') as cancel:
            with self.assertRaisesRegex(NewsError,'timed out'):
                engine.generate_narration(self.points,self.root)
        request.assert_called_once();cancel.assert_called_once()

    def test_prediction_pacing_is_shared_across_engine_instances(self):
        first=self.engine();second=self.engine();now=[100.0]
        def advance(seconds):now[0]+=seconds
        with patch.object(config,'NEWS_REPLICATE_MIN_INTERVAL',12),patch.object(NewsReplicateTTS,'_next_prediction_at',0),patch('agent.news_tts.time.monotonic',side_effect=lambda:now[0]),patch('agent.news_tts.time.sleep',side_effect=advance) as sleep:
            first._pace_prediction();second._pace_prediction();first._pace_prediction()
        self.assertEqual([c.args[0] for c in sleep.call_args_list],[12,12])

    def test_extended_cooldown_honors_server_reset_without_changing_provider(self):
        engine=self.engine()
        rejected=MagicMock(status_code=429,headers={'Retry-After':'120'})
        accepted=MagicMock(status_code=201)
        accepted.json.return_value={'id':'p123'}
        with patch.object(config,'NEWS_REPLICATE_RATE_LIMIT_WAIT',600),patch.object(engine._session,'request',side_effect=[rejected,accepted]) as request,patch('agent.news_tts.time.sleep') as sleep:
            self.assertEqual(engine._request('POST','https://api.replicate.com/v1/predictions')['id'],'p123')
        sleep.assert_called_once_with(121);self.assertEqual(request.call_count,2)

    def test_total_cooldown_budget_is_not_reset_between_sentences(self):
        engine=self.engine()
        engine._throttle_wait=89
        rejected=MagicMock(status_code=429,headers={'Retry-After':'2'})
        with patch.object(engine._session,'request',return_value=rejected) as request,patch('agent.news_tts.time.sleep') as sleep:
            with self.assertRaisesRegex(NewsError,'budget exhausted'):
                engine._request('POST','https://api.replicate.com/v1/predictions')
        sleep.assert_not_called();request.assert_called_once()


if __name__=='__main__': unittest.main()
