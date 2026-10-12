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
import uuid
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
        self._session = requests.Session()
        self._session.headers.update({'Authorization':'Bearer '+token})

    def _request(self, method, url, **kwargs):
        for attempt in range(3):
            cancelled(self.cancel_event)
            try:
                response = self._session.request(method, url, timeout=(10,25), **kwargs)
            except requests.RequestException:
                raise NewsError('Replicate speech connection failed; no automatic paid retry.') from None
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
            except (ValueError,TypeError,OverflowError): wait = 15
            response.close()
            if attempt==2 or wait>45 or self._throttle_wait+wait>90:
                raise NewsError('Replicate speech is rate-limited (HTTP 429); bounded wait exhausted, switching provider.')
            self._throttle_wait += wait
            logger.warning('Replicate speech throttled (HTTP 429); waiting %ds before resubmitting the rejected request (%d/2).',wait,attempt+1)
            if self.cancel_event is not None:
                self.cancel_event.wait(wait)
            else:
                time.sleep(wait)
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
                headers={'Cancel-After':'2m', 'Prefer':'wait=5'})
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
                    raise NewsError(f'Replicate speech prediction {status}; using the next configured provider.')
                if time.monotonic() >= deadline:
                    raise NewsError('Replicate speech timed out; prediction cancellation requested.')
                if self.cancel_event is not None:
                    self.cancel_event.wait(1)
                else:
                    time.sleep(1)
                row = self._request('GET',f'https://api.replicate.com/v1/predictions/{prediction}')
        finally:
            if prediction and not finished:
                try:
                    self._session.post(f'https://api.replicate.com/v1/predictions/{prediction}/cancel',timeout=(5,10))
                except requests.RequestException:
                    logger.warning('Could not confirm remote speech cancellation; Cancel-After remains in effect.')

    def generate_narration(self, points, output_dir):
        from agent.news_audio import probe_duration
        cancelled(self.cancel_event)
        # Validate every input before the first paid call. News sentences are short; never truncate them.
        if not points or len(points)>80 or sum(len(p.narration) for p in points)>12000:
            raise NewsError('Replicate News speech exceeds the bounded narration budget.')
        if self.model == CHATTERBOX and any(len(p.narration)>500 for p in points):
            raise NewsError('Chatterbox Turbo allows at most 500 characters per News sentence; use Kokoro or Edge.')
        output_dir = Path(output_dir)/'audio'; output_dir.mkdir(parents=True,exist_ok=True)
        cache = Path(config.NEWS_TTS_CACHE); cache.mkdir(parents=True,exist_ok=True)
        clips = []
        for point in points:
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
            clips.append(SimpleNamespace(index=point.index,audio_path=path,duration=duration,word_timings=[]))
        return clips
