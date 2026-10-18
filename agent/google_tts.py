"""
Project HER v2.0 – Google AI Studio TTS Engine
================================================
Free high-quality TTS via Google's Gemini API (AI Studio).
Uses the gemini-2.5-flash-preview-tts model for speech generation.

Cost: FREE (within AI Studio rate limits)
Quality: Near-premium, multiple distinctive voices
Latency: ~2-4s per screen
Rate limit: Free tier = 10 RPM → built-in throttle + retry with backoff

Available voices:
  - Zephyr  — Bright, upbeat, expressive
  - Puck    — Playful, versatile narrator
  - Charon  — Deep, authoritative
  - Kore    — Clear, professional female
  - Fenrir  — Bold, dramatic male
  - Leda    — Warm, nurturing
  - Orus    — Confident, informative
  - Aoede   — Musical, poetic

Word-level timing is estimated proportionally (same approach as
Replicate/Kokoro) since Gemini TTS doesn't return alignment data.
The proportional estimator accounts for punctuation pauses and
character-weighted word lengths — works well for karaoke captions.

Usage:
    from agent.google_tts import GoogleTTS
    tts = GoogleTTS(mood="dramatic")
    clips = tts.generate_narration(key_points, output_dir)
"""

from __future__ import annotations

import base64
import io
import logging
import os
import re
import struct
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests

import config

logger = logging.getLogger("google_tts")


# ── Google AI Studio Configuration ─────────────────

GOOGLE_TTS_API_KEY = (
    os.getenv("GOOGLE_TTS_API_KEY")
    or os.getenv("GEMINI_API_KEY")
    or os.getenv("GOOGLE_API_KEY")
    or getattr(config, "GOOGLE_TTS_API_KEY", "")
    or getattr(config, "GEMINI_API_KEY", "")
)

GEMINI_TTS_MODEL = os.getenv("GEMINI_TTS_MODEL", getattr(config, "GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts"))
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"

# ── Rate Limiting ──────────────────────────────────
# Free tier: 10 RPM (but in practice bursts of >3 hit quota)
# We throttle to ~3 RPM with retry + backoff
MIN_REQUEST_INTERVAL = 7.0    # seconds between requests (safe for 10 RPM)
MAX_RETRIES = 2               # retry on 429 rate limit errors (fail fast)
RETRY_BASE_WAIT = 10.0        # base wait for exponential backoff

# ── Voice Presets ─────────────────────────────────
# Available Gemini TTS voices and their characteristics
VOICE_PRESETS = {
    "bright":       "Zephyr",    # Bright, upbeat
    "playful":      "Puck",      # Playful, versatile
    "authoritative": "Charon",   # Deep, authoritative
    "professional": "Kore",      # Clear, professional
    "dramatic":     "Fenrir",    # Bold, dramatic
    "warm":         "Leda",      # Warm, nurturing
    "informative":  "Orus",      # Confident, informative
    "poetic":       "Aoede",     # Musical, poetic
}

# Map content mood → best voice
MOOD_VOICE_MAP = {
    "neutral":      "informative",
    "excitement":   "bright",
    "dramatic":     "dramatic",
    "suspense":     "authoritative",
    "thoughtful":   "professional",
    "informative":  "informative",
    "calm":         "warm",
    "urgent":       "bright",
    "sadness":      "warm",
    "anger":        "dramatic",
    "awe":          "poetic",
    "mystery":      "authoritative",
    "joy":          "playful",
    "tension":      "dramatic",
    "nostalgia":    "warm",
    "triumph":      "bright",
    "horror":       "authoritative",
    "wonder":       "poetic",
    "inspirational": "bright",
    "playful":      "playful",
    "serious":      "authoritative",
    "melancholy":   "warm",
}


@dataclass
class WordTiming:
    """Word-level timing for karaoke captions."""
    word: str
    start: float
    end: float


@dataclass
class GoogleTTSClip:
    """Generated TTS clip with word timings."""
    index: int
    audio_path: Path
    duration: float = 0.0
    word_timings: list[WordTiming] = field(default_factory=list)
    subtitle_data: list[dict] = field(default_factory=list)
    speaker: str = ""

    @property
    def key_point_index(self) -> int:
        """Alias for compatibility with NarrationClip interface."""
        return self.index


class GoogleTTS:
    """
    Free TTS via Google AI Studio's Gemini API.

    Uses the gemini-2.5-flash-preview-tts model's speech generation
    endpoint. Audio is returned as WAV and converted to MP3 for
    pipeline compatibility.
    """

    def __init__(
        self,
        voice_name: Optional[str] = None,
        mood: str = "neutral",
        api_key: Optional[str] = None,
    ):
        self.api_key = api_key or GOOGLE_TTS_API_KEY
        self.mood = mood

        # Select voice based on mood if no explicit voice
        if voice_name:
            self.voice_name = voice_name
        else:
            preset_key = MOOD_VOICE_MAP.get(mood, "informative")
            self.voice_name = VOICE_PRESETS.get(preset_key, "Orus")

        self._session = requests.Session()
        self._last_request_time = 0.0  # for rate limiting

        if not self.api_key:
            logger.warning(
                "No GOOGLE_TTS_API_KEY found. Set it in .env or config. "
                "Get a free key at https://aistudio.google.com/apikey"
            )

        logger.info(
            "Google TTS initialized: voice=%s, mood=%s",
            self.voice_name, mood,
        )

    def generate_narration(
        self,
        key_points: list,
        output_dir: Path,
    ) -> list[GoogleTTSClip]:
        """
        Generate TTS for each key point using Gemini TTS.

        Args:
            key_points: List of KeyPoint objects (index, narration, emotion, etc.)
            output_dir: Directory for audio files

        Returns:
            List of GoogleTTSClip with paths and estimated word timings
        """
        audio_dir = output_dir / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        clips = []
        consecutive_failures = 0
        for kp in key_points:
            clip = self._generate_single(kp, audio_dir)
            clips.append(clip)

            # Fail-fast: if daily quota is exhausted or first 2 screens both fail,
            # the API is exhausted or down — bail immediately to trigger fallback.
            if clip.duration > 0 and Path(clip.audio_path).exists():
                consecutive_failures = 0  # reset on success
            else:
                consecutive_failures += 1
                if getattr(self, "_daily_quota_exhausted", False) or consecutive_failures >= 2:
                    logger.warning(
                        "Google TTS: %d consecutive failures — "
                        "API likely exhausted. Aborting early for fallback.",
                        consecutive_failures,
                    )
                    raise RuntimeError(
                        f"Google TTS failed {consecutive_failures} consecutive "
                        f"screens (likely rate-limited). Triggering fallback."
                    )

        # ── Validate: count how many clips actually have audio ──
        valid = [c for c in clips if c.duration > 0 and Path(c.audio_path).exists()]
        total_dur = sum(c.duration for c in valid)
        logger.info(
            "Google TTS narration: %d/%d clips succeeded, %.1fs total",
            len(valid), len(clips), total_dur,
        )

        if not valid:
            raise RuntimeError(
                f"Google TTS failed for ALL {len(clips)} screens "
                f"(API key may be rate-limited or invalid). "
                f"Triggering edge-tts fallback."
            )

        # If some (but not all) failed, log a warning but continue
        if len(valid) < len(clips):
            failed = len(clips) - len(valid)
            logger.warning(
                "Google TTS: %d/%d screens had no audio — "
                "those screens will be silent.",
                failed, len(clips),
            )

        return clips

    def _throttle(self) -> None:
        """Rate-limit requests to stay within Gemini free-tier quota."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            wait = MIN_REQUEST_INTERVAL - elapsed
            logger.debug("Rate limiting: waiting %.1fs before next request", wait)
            time.sleep(wait)
        self._last_request_time = time.time()

    def _call_gemini_tts(self, text: str, voice: str, idx: int) -> dict | None:
        """
        Call Gemini TTS API with rate limiting and retry on 429.
        Returns the parsed JSON response, or None on failure.
        """
        url = f"{GEMINI_API_BASE}/models/{GEMINI_TTS_MODEL}:generateContent"
        params = {"key": self.api_key}

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": text}
                    ]
                }
            ],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": voice
                        }
                    }
                }
            }
        }

        for attempt in range(MAX_RETRIES + 1):
            self._throttle()
            try:
                resp = self._session.post(
                    url, params=params, json=payload, timeout=60,
                )
                resp.raise_for_status()
                return resp.json()

            except requests.exceptions.HTTPError as e:
                # NOTE: requests.Response.__bool__() returns self.ok,
                # so a 429 response is falsy. Use `is not None` instead.
                status = e.response.status_code if e.response is not None else 0
                body = ""
                retry_after = None
                try:
                    err_data = e.response.json()
                    body = err_data.get("error", {}).get("message", "")
                    # Parse "Please retry in 33.9s" from the error message
                    m = re.search(r"retry in ([\d.]+)s", body)
                    if m:
                        retry_after = float(m.group(1))
                except Exception:
                    pass

                body_lower = body.lower()
                is_quota_exhausted = (
                    "per_day" in body_lower
                    or "perday" in body_lower
                    or "limit: 10" in body_lower
                    or bool(re.search(r"retry in [\d.]+[hd]", body_lower))
                )
                if status == 429 and is_quota_exhausted:
                    self._daily_quota_exhausted = True
                    logger.warning(
                        "Google TTS daily quota exhausted for screen %d (%s). Fast-falling back to edge-tts.",
                        idx, body[:120],
                    )
                    return None

                if status == 429 and attempt < MAX_RETRIES:
                    wait = retry_after or (RETRY_BASE_WAIT * (2 ** attempt))
                    # Cap maximum wait at 45s (fail fast → fallback to edge-tts)
                    wait = min(wait, 45.0)
                    logger.warning(
                        "Google TTS rate limited for screen %d (attempt %d/%d). "
                        "Waiting %.0fs before retry…",
                        idx, attempt + 1, MAX_RETRIES, wait,
                    )
                    time.sleep(wait)
                    continue

                logger.error(
                    "Google TTS API error for screen %d (HTTP %s): %s",
                    idx, status, body or e,
                )
                return None

            except requests.exceptions.RequestException as e:
                logger.error("Google TTS connection error for screen %d: %s", idx, e)
                return None

        logger.error("Google TTS exhausted all retries for screen %d", idx)
        return None

    def _generate_single(self, key_point, audio_dir: Path) -> GoogleTTSClip:
        """Generate TTS for a single key point via Gemini API."""
        text = key_point.narration
        idx = key_point.index
        emotion = getattr(key_point, "emotion", self.mood)

        # Use the SAME narrator voice for all screens in the video.
        # Voice is picked once at __init__ time based on overall mood.
        voice = self.voice_name

        logger.info(
            "Google TTS generating [%d]: '%s' (voice=%s, emotion=%s)",
            idx, text[:60], voice, emotion,
        )

        audio_path = audio_dir / f"narration_{idx}.mp3"

        # ── Call API with retry ──
        data = self._call_gemini_tts(text, voice, idx)
        if data is None:
            return GoogleTTSClip(index=idx, audio_path=audio_path)

        # ── Extract audio from response ──
        try:
            candidates = data.get("candidates", [])
            if not candidates:
                logger.error("No candidates in Google TTS response for screen %d", idx)
                return GoogleTTSClip(index=idx, audio_path=audio_path)

            parts = candidates[0].get("content", {}).get("parts", [])
            inline_data = None
            for part in parts:
                if "inlineData" in part:
                    inline_data = part["inlineData"]
                    break

            if not inline_data or not inline_data.get("data"):
                logger.error("No audio data in Google TTS response for screen %d", idx)
                return GoogleTTSClip(index=idx, audio_path=audio_path)

            audio_b64 = inline_data["data"]
            mime_type = inline_data.get("mimeType", "")
            audio_bytes = base64.b64decode(audio_b64)
            logger.debug("Screen %d: mime=%s, %d bytes", idx, mime_type, len(audio_bytes))

        except (KeyError, IndexError) as e:
            logger.error("Failed to parse Google TTS response for screen %d: %s", idx, e)
            return GoogleTTSClip(index=idx, audio_path=audio_path)

        # ── Convert to MP3 ──
        try:
            if "mp3" in mime_type or "mpeg" in mime_type:
                # Already MP3 — save directly
                audio_path.write_bytes(audio_bytes)
            elif self._has_wav_header(audio_bytes):
                # Proper WAV file with RIFF header
                tmp = audio_dir / f"narration_{idx}_tmp.wav"
                tmp.write_bytes(audio_bytes)
                self._wav_to_mp3(tmp, audio_path)
                tmp.unlink(missing_ok=True)
            else:
                # Raw PCM (Linear16) — most common from Gemini TTS
                sample_rate = self._parse_sample_rate(mime_type)
                self._pcm_to_mp3(audio_bytes, audio_path, sample_rate=sample_rate)
        except Exception as conv_err:
            logger.error(
                "Audio conversion failed for screen %d: %s",
                idx, conv_err,
            )
            return GoogleTTSClip(index=idx, audio_path=audio_path)

        # ── Duration + word timings ──
        duration = self._get_audio_duration(audio_path)
        word_timings = self._estimate_word_timings(text, duration)
        subtitle_data = self._build_grouped_subtitles(word_timings, duration)

        logger.info(
            "Google TTS [%d]: %.1fs, %d words, voice=%s, saved to %s",
            idx, duration, len(word_timings), voice, audio_path.name,
        )

        return GoogleTTSClip(
            index=idx,
            audio_path=audio_path,
            duration=duration,
            word_timings=word_timings,
            subtitle_data=subtitle_data,
        )

    # ── Audio Conversion ──────────────────────────────

    @staticmethod
    def _has_wav_header(data: bytes) -> bool:
        """Check if bytes start with a RIFF/WAV header."""
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE"

    @staticmethod
    def _parse_sample_rate(mime_type: str) -> int:
        """
        Extract sample rate from mime type like 'audio/L16;rate=24000'.
        Falls back to 24000 (Gemini TTS default).
        """
        m = re.search(r"rate=(\d+)", mime_type)
        return int(m.group(1)) if m else 24000

    @staticmethod
    def _pcm_to_mp3(
        pcm_bytes: bytes,
        mp3_path: Path,
        sample_rate: int = 24000,
        channels: int = 1,
    ) -> None:
        """
        Convert raw Linear16 PCM bytes to MP3 via ffmpeg.

        Gemini TTS returns raw signed-16-bit little-endian PCM (no WAV header).
        We tell ffmpeg the exact input format so it decodes correctly.
        """
        cmd = [
            "ffmpeg", "-y",
            # Input format: raw signed 16-bit LE PCM
            "-f", "s16le",
            "-ar", str(sample_rate),
            "-ac", str(channels),
            "-i", "pipe:0",
            # Output: MP3 at 128kbps, 44.1kHz
            "-codec:a", "libmp3lame",
            "-b:a", "128k",
            "-ar", "44100",
            str(mp3_path),
        ]
        result = subprocess.run(
            cmd,
            input=pcm_bytes,
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace")[-500:]
            raise RuntimeError(
                f"PCM→MP3 ffmpeg failed (exit {result.returncode}): {stderr}"
            )

    @staticmethod
    def _wav_to_mp3(wav_path: Path, mp3_path: Path) -> None:
        """Convert a proper WAV file to MP3."""
        # Try pydub first
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_wav(str(wav_path))
            audio.export(str(mp3_path), format="mp3", bitrate="128k")
            return
        except Exception:
            pass

        # Fallback: direct ffmpeg
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(wav_path),
                "-codec:a", "libmp3lame", "-b:a", "128k",
                "-ar", "44100", str(mp3_path),
            ],
            capture_output=True, timeout=15,
        )
        if result.returncode != 0:
            raise RuntimeError(f"WAV→MP3 conversion failed (exit {result.returncode})")

    # ── Word Timing Estimation ────────────────────────

    @staticmethod
    def _estimate_word_timings(text: str, duration: float) -> list[WordTiming]:
        """
        Estimate word-level timings proportionally from audio duration.

        Uses character-weighted distribution with punctuation pause weights.
        Same proven approach as Replicate TTS — works well for karaoke captions.
        """
        words = text.split()
        if not words or duration <= 0:
            return []

        # Character-length weights with punctuation pause adjustments
        weights = []
        for w in words:
            base = len(w)
            if w.endswith((".", "!", "?", "...")):
                base += 3  # sentence-end pause
            elif w.endswith((",", ";", ":")):
                base += 1.5  # clause-break pause
            elif w.endswith(("—", "–")):
                base += 2  # dash pause
            weights.append(base)

        total_weight = sum(weights)
        if total_weight == 0:
            total_weight = len(words)
            weights = [1.0] * len(words)

        # Small margins at start/end for natural pacing
        start_margin = 0.05
        end_margin = 0.1
        usable = duration - start_margin - end_margin
        if usable <= 0:
            usable = duration

        timings = []
        cursor = start_margin
        for i, w in enumerate(words):
            word_dur = usable * (weights[i] / total_weight)
            timings.append(WordTiming(
                word=w,
                start=round(cursor, 3),
                end=round(cursor + word_dur, 3),
            ))
            cursor += word_dur

        return timings

    # ── Subtitle Grouping ─────────────────────────────

    @staticmethod
    def _build_grouped_subtitles(
        word_timings: list[WordTiming],
        duration: float,
        words_per_group: int = 4,
    ) -> list[dict]:
        """Group word timings into subtitle chunks for display."""
        groups = []
        for i in range(0, len(word_timings), words_per_group):
            chunk = word_timings[i:i + words_per_group]
            if not chunk:
                continue
            groups.append({
                "text": " ".join(w.word for w in chunk),
                "start": chunk[0].start,
                "end": chunk[-1].end,
                "words": [
                    {"word": w.word, "start": w.start, "end": w.end}
                    for w in chunk
                ],
            })
        return groups

    # ── Duration Detection ────────────────────────────

    @staticmethod
    def _get_audio_duration(audio_path: Path) -> float:
        """Get audio duration from file."""
        # Try moviepy (already in project)
        try:
            from moviepy import AudioFileClip
            clip = AudioFileClip(str(audio_path))
            dur = clip.duration
            clip.close()
            return dur
        except Exception:
            pass

        # Try pydub
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(str(audio_path))
            return len(audio) / 1000.0
        except Exception:
            pass

        # Rough estimate from file size (128kbps MP3)
        try:
            size = audio_path.stat().st_size
            return size / (128 * 1024 / 8)
        except Exception:
            return 3.0

    # ── Utility ───────────────────────────────────────

    def check_quota(self) -> dict:
        """
        Check API key validity. Gemini TTS is free within rate limits:
        - 10 RPM, 2000 RPD for free-tier keys
        """
        try:
            url = f"{GEMINI_API_BASE}/models/{GEMINI_TTS_MODEL}"
            resp = self._session.get(url, params={"key": self.api_key}, timeout=10)
            if resp.status_code == 200:
                return {"status": "active", "model": GEMINI_TTS_MODEL, "tier": "free"}
            else:
                return {"status": "error", "code": resp.status_code}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    def list_voices() -> list[dict]:
        """List all available Gemini TTS voices."""
        return [
            {"name": "Zephyr",  "style": "Bright, upbeat, expressive"},
            {"name": "Puck",    "style": "Playful, versatile narrator"},
            {"name": "Charon",  "style": "Deep, authoritative"},
            {"name": "Kore",    "style": "Clear, professional female"},
            {"name": "Fenrir",  "style": "Bold, dramatic male"},
            {"name": "Leda",    "style": "Warm, nurturing"},
            {"name": "Orus",    "style": "Confident, informative"},
            {"name": "Aoede",   "style": "Musical, poetic"},
        ]
