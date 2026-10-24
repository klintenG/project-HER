"""Bounded, cached Replicate speech for News; no estimated word alignment."""
from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import shutil
import subprocess
import time
import threading
import uuid
from email.utils import parsedate_to_datetime
from pathlib import Path
from types import SimpleNamespace

import requests
import config
from agent.news_models import NewsError

logger = logging.getLogger(__name__)
KOKORO = 'jaaari/kokoro-82m'
CHATTERBOX = 'resemble-ai/chatterbox-turbo'
# Verified input schemas, pinned to avoid unexpected voice/schema changes.
VERSIONS = {
    KOKORO: 'f559560eb822dc509045f3921a1921234918b91739db4bf3daab2169b71c7a13',
    CHATTERBOX: '95c87b883ff3e842a1643044dff67f9d204f70a80228f24ff64bffe4a4b917d4',
}
LANGUAGES = {'english':'en', 'hindi':'hi', 'french':'fr'}
KOKORO_VOICES = {'en':'af_bella', 'en-gb':'bf_emma', 'en-in':'af_bella', 'hi':'hf_alpha', 'fr':'ff_siwis'}


def cancelled(event):
    if event is not None and event.is_set():
        raise NewsError('News generation cancelled.', 'cancelled')


class NewsReplicateTTS:
    # Shared by News/editorial jobs in this app process, including both models.
    _pacing_lock = threading.Lock()
    _next_prediction_at = 0.0

    def _wait(self, seconds):
        cancelled(self.cancel_event)
        if seconds>0:
            if self.cancel_event is not None:self.cancel_event.wait(seconds)
            else:time.sleep(seconds)
        cancelled(self.cancel_event)

    def _pace_prediction(self):
        interval=config.NEWS_REPLICATE_MIN_INTERVAL
        if interval<=0:return
        while not NewsReplicateTTS._pacing_lock.acquire(timeout=.2):cancelled(self.cancel_event)
        try:
            delay=max(0,NewsReplicateTTS._next_prediction_at-time.monotonic())
            if delay>0:logger.info('Replicate speech pacing; waiting %.1fs before the next prediction.',delay)
            self._wait(delay)
            NewsReplicateTTS._next_prediction_at=time.monotonic()+interval
        finally:NewsReplicateTTS._pacing_lock.release()

    def __init__(self, voice=None, speed='+0%', language='en', cancel_event=None, model=None):
        self.model = model or config.NEWS_REPLICATE_TTS_MODEL
        if self.model not in VERSIONS:
            raise NewsError('NEWS_REPLICATE_TTS_MODEL must be jaaari/kokoro-82m or resemble-ai/chatterbox-turbo.')
        self.language = LANGUAGES.get(language.lower(), language.lower())
        if self.language not in KOKORO_VOICES or (self.model == CHATTERBOX and not self.language.startswith('en')):
            raise NewsError('Selected Replicate speech model does not support this News language; use Edge TTS.')
        token = config.REPLICATE_API_TOKEN
        if not token:
            raise NewsError('Replicate speech unavailable: REPLICATE_API_TOKEN is missing.')
        self.voice = KOKORO_VOICES[self.language] if self.model == KOKORO else 'Andy'
        # Accept the existing Kokoro presets without accidentally treating a Google/Edge voice as one.
        if self.model == KOKORO:
            from agent.replicate_tts import VOICE_PRESETS
            allowed = set(VOICE_PRESETS.values()) | set(KOKORO_VOICES.values())
            if voice in allowed and voice[:1] == self.voice[:1]:
                self.voice = voice
        elif voice == 'Andy':
            self.voice = voice
        from agent.narration import NarrationEngine
        self.speed = max(.5, min(2., 1 + int(NarrationEngine._normalize_rate(speed).rstrip('%')) / 100))
        self.cancel_event = cancel_event
        self._throttle_wait = 0
        self._throttle_lock = threading.Lock()
        self._session = requests.Session()
        self._session.headers.update({'Authorization':'Bearer '+token})

    def _request(self, method, url, **kwargs):
        retries=config.NEWS_REPLICATE_RATE_LIMIT_RETRIES
        for attempt in range(retries+1):
            cancelled(self.cancel_event)
            if method=='POST' and url.endswith('/predictions'):self._pace_prediction()
            for network_attempt in range(3):
                try:
                    response = self._session.request(method, url, timeout=(10,25), **kwargs)
                except requests.RequestException as exc:
                    # GET only observes an accepted prediction. ConnectTimeout
                    # occurs before a POST reaches the provider; other POST
                    # failures are ambiguous and must never create duplicates.
                    safe_retry=method=='GET' or isinstance(exc,requests.ConnectTimeout)
                    if safe_retry and network_attempt<2:
                        self._wait(2**network_attempt);continue
                    raise NewsError('Replicate speech connection failed; no duplicate prediction was submitted.') from None
                if method=='GET' and response.status_code in (500,502,503,504) and network_attempt<2:
                    response.close();self._wait(2**network_attempt);continue
                break
            if response.status_code != 429: break
            # HTTP 429 means no prediction was accepted. Only this rejection is safe to resubmit.
            wait = response.headers.get('Retry-After')
            if not wait:
                try:
                    detail = response.json().get('detail','')
                    match = re.search(r'(?:~|in\s+)(\d+(?:\.\d+)?)\s*(?:s|seconds)',str(detail))
                    wait = match.group(1) if match else 15
                except (ValueError,AttributeError): wait = 15
            try: wait = max(1,math.ceil(float(wait)))+1
            except (ValueError,TypeError,OverflowError):
                try:wait=max(1,math.ceil(parsedate_to_datetime(str(wait)).timestamp()-time.time()))+1
                except (ValueError,TypeError,OverflowError,AttributeError):wait=15
            response.close()
            with self._throttle_lock:
                if attempt==retries or self._throttle_wait+wait>config.NEWS_REPLICATE_RATE_LIMIT_WAIT:
                    raise NewsError('Replicate speech is rate-limited (HTTP 429); retry/wait budget exhausted. Wait before retrying or increase NEWS_REPLICATE_RATE_LIMIT_WAIT.')
                self._throttle_wait += wait
            if config.NEWS_REPLICATE_MIN_INTERVAL>0:
                while not NewsReplicateTTS._pacing_lock.acquire(timeout=.2):cancelled(self.cancel_event)
                try:
                    NewsReplicateTTS._next_prediction_at=max(NewsReplicateTTS._next_prediction_at,time.monotonic()+wait)
                finally:NewsReplicateTTS._pacing_lock.release()
            logger.warning('Replicate speech throttled (HTTP 429); waiting %ds before resubmitting the rejected request (%d/%d).',wait,attempt+1,retries)
            self._wait(wait)
        if response.status_code not in (200,201,202):
            raise NewsError(f'Replicate speech request failed (HTTP {response.status_code}); check credits/model access.')
        try:
            row = response.json()
            if not isinstance(row, dict): raise ValueError()
            return row
        except ValueError:
            raise NewsError('Replicate speech returned invalid prediction data.') from None

    def _predict(self, inputs):
        prediction = None; finished = False
        try:
            row = self._request('POST','https://api.replicate.com/v1/predictions',
                json={'version':VERSIONS[self.model], 'input':inputs},
                headers={'Cancel-After':'2m', 'Prefer':'wait=20'})
            prediction = row.get('id')
            if not isinstance(prediction,str) or not re.fullmatch('[a-zA-Z0-9_-]+',prediction):
                prediction = None
                raise NewsError('Replicate speech returned an invalid prediction ID.')
            deadline = time.monotonic() + 120
            while True:
                cancelled(self.cancel_event)
                status = row.get('status')
                if status == 'succeeded':
                    finished = True
                    url = row.get('output')
                    if not isinstance(url,str) or not url.startswith('https://'):
                        raise NewsError('Replicate speech returned no audio URL.')
                    from agent.news_research import fetch
                    data,_ = fetch(url, types=('audio/wav','audio/x-wav','audio/wave','audio/mpeg','audio/flac','audio/ogg','application/octet-stream'),limit=20_000_000)
                    cancelled(self.cancel_event)
                    return data
                if status in ('failed','canceled'):
                    finished = True
                    raise NewsError(f'Replicate speech prediction {status}; no automatic paid retry.')
                if time.monotonic() >= deadline:
                    raise NewsError('Replicate speech timed out; prediction cancellation requested.')
                if self.cancel_event is not None:
                    self.cancel_event.wait(.5)
                else:
                    time.sleep(.5)
                row = self._request('GET',f'https://api.replicate.com/v1/predictions/{prediction}')
        finally:
            if prediction and not finished:
                try:
                    self._session.post(f'https://api.replicate.com/v1/predictions/{prediction}/cancel',timeout=(5,10))
                except requests.RequestException:
                    logger.warning('Could not confirm remote speech cancellation; Cancel-After remains in effect.')

    def generate_narration(self, points, output_dir):
        from concurrent.futures import ThreadPoolExecutor
        from agent.news_audio import probe_duration
        cancelled(self.cancel_event)
        # Validate every input before the first paid call. News sentences are short; never truncate them.
        if not points or len(points)>80 or sum(len(p.narration) for p in points)>12000:
            raise NewsError('Replicate News speech exceeds the bounded narration budget.')
        if self.model == CHATTERBOX and any(len(p.narration)>500 for p in points):
            raise NewsError('Chatterbox Turbo allows at most 500 characters per News sentence; use Kokoro or Edge.')
        output_dir = Path(output_dir)/'audio'; output_dir.mkdir(parents=True,exist_ok=True)
        cache = Path(config.NEWS_TTS_CACHE); cache.mkdir(parents=True,exist_ok=True)
        stop = threading.Event()
        def synthesize_point(point):
            if stop.is_set():
                cancelled(self.cancel_event)
                raise NewsError('Replicate speech aborted after earlier sentence failure.')
            cancelled(self.cancel_event)
            inputs = {'text':point.narration, 'voice':self.voice}
            if self.model == KOKORO: inputs['speed'] = self.speed
            # Turbo has no speed parameter. Its actual natural duration is used by the timeline.
            key = hashlib.sha256(json.dumps({'version':VERSIONS[self.model],'input':inputs,'adapter':1},sort_keys=True).encode()).hexdigest()
            cached = cache/(key+'.wav'); path = output_dir/f'narration_{point.index}.wav'
            duration = None
            if cached.is_file():
                try: duration = probe_duration(cached)
                except (OSError,ValueError,subprocess.SubprocessError): pass
            if duration is None:
                logger.info('Replicate speech | model=%s | sentence=%s | chars=%d | cache=miss',self.model,point.index,len(point.narration))
                raw = output_dir/f'{point.index}-{uuid.uuid4().hex}.raw'
                temporary = cache/f'{key}-{uuid.uuid4().hex}.wav'
                try:
                    raw.write_bytes(self._predict(inputs))
                    subprocess.run(['ffmpeg','-v','error','-y','-i',str(raw),'-vn','-ac','1','-ar','24000','-c:a','pcm_s16le',str(temporary)],capture_output=True,check=True,timeout=30)
                    duration = probe_duration(temporary)
                    cancelled(self.cancel_event)
                    temporary.replace(cached)
                finally:
                    raw.unlink(missing_ok=True); temporary.unlink(missing_ok=True)
            else:
                logger.info('Replicate speech | model=%s | sentence=%s | cache=hit',self.model,point.index)
            shutil.copyfile(cached,path)
            return SimpleNamespace(index=point.index,audio_path=path,duration=duration,word_timings=[])
        if len(points) <= 1 or config.NEWS_REPLICATE_MIN_INTERVAL >= 2:
            return [synthesize_point(point) for point in points]
        workers = min(3, len(points))
        failure = []
        def guarded(point):
            try:
                return synthesize_point(point)
            except Exception as exc:
                if not failure:
                    failure.append(exc)
                stop.set()
                raise
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix='news-tts') as pool:
            try:
                return list(pool.map(guarded, points))
            except Exception:
                stop.set()
                raise failure[0]
