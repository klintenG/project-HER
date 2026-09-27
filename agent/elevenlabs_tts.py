"""
Project HER v2.0 – ElevenLabs TTS Engine
==========================================
High-quality narration via ElevenLabs with character-level timestamps
reconstructed into word-level timings for karaoke captions.

Used for the Generate tab pipeline (non-kids_story content modes).
Kids Story tab continues to use edge-tts for cost efficiency.

Voice selection:
  - George  (JBFqnCBsd6RMkjVDRZzb) — Warm, Captivating Storyteller  (default)
  - Liam    (TX3LPaxmHKxFdv7VOQHJ) — Energetic, Social Media Creator
  - Brian   (nPczCjzI2devNBz1zQrb) — Deep, Resonant and Comforting
  - Sarah   (EXAVITQu4vr4xnSDxMaL) — Mature, Reassuring, Confident
  - Alice   (Xb7hH8MSUJpSbSDYk0k2) — Clear, Engaging Educator
  - Matilda (XrExE9yKIg1WjnnlVkGX) — Knowledgeable, Professional

Supports:
  - Emotion-aware voice selection (mood → best voice)
  - Character-to-word timestamp reconstruction
  - MP3 output at 44.1 kHz / 128 kbps
  - Silence gap insertion between scenes
"""

from __future__ import annotations

import base64
import logging
import re
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests

import config

logger = logging.getLogger("elevenlabs_tts")


# ── ElevenLabs Configuration ─────────────────────────

ELEVENLABS_API_KEY = config.os.getenv(
    "ELEVENLABS_API_KEY",
    "",
)
ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1"
ELEVENLABS_MODEL = "eleven_multilingual_v2"

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_WAIT = 5.0  # seconds

# Voice presets — best free voices for different moods
VOICE_PRESETS = {
    "storyteller":  "JBFqnCBsd6RMkjVDRZzb",  # George — warm storyteller
    "energetic":    "TX3LPaxmHKxFdv7VOQHJ",  # Liam — social media energy
    "deep":         "nPczCjzI2devNBz1zQrb",  # Brian — deep, resonant
    "professional": "EXAVITQu4vr4xnSDxMaL",  # Sarah — mature, confident
    "educator":     "Xb7hH8MSUJpSbSDYk0k2",  # Alice — clear educator
    "warm":         "XrExE9yKIg1WjnnlVkGX",  # Matilda — knowledgeable
    "casual":       "iP95p4xoKVk53GoZ742B",  # Chris — charming, down-to-earth
    "dramatic":     "pNInz6obpgDQGcFmaJgB",  # Adam — dominant, firm
}

DEFAULT_VOICE_ID = "2KkUKn1TzEOhhKPCZGrT"

# Map content mood → best voice
MOOD_VOICE_MAP = {
    "excitement":   "energetic",
    "dramatic":     "dramatic",
    "suspense":     "deep",
    "thoughtful":   "professional",
    "informative":  "educator",
    "calm":         "warm",
    "urgent":       "energetic",
    "sadness":      "deep",
    "anger":        "dramatic",
    "awe":          "storyteller",
    "mystery":      "deep",
    "joy":          "energetic",
    "tension":      "dramatic",
    "nostalgia":    "warm",
    "triumph":      "storyteller",
    "horror":       "deep",
    "wonder":       "storyteller",
    "neutral":      "storyteller",
}


@dataclass
class WordTiming:
    """Word-level timing for karaoke."""
    word: str
    start: float
    end: float


@dataclass
class ElevenLabsClip:
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


class ElevenLabsTTS:
    """
    High-quality TTS via ElevenLabs with word-level timestamps.
    
    Uses the /with-timestamps endpoint to get character-level timing,
    then reconstructs word boundaries for karaoke captions.
    """

    def __init__(
        self,
        voice_id: Optional[str] = None,
        mood: str = "neutral",
        api_key: Optional[str] = None,
    ):
        self.api_key = api_key or ELEVENLABS_API_KEY
        self.mood = mood
        
        # Select voice based on mood if no explicit voice
        if voice_id:
            self.voice_id = voice_id
        else:
            preset_name = MOOD_VOICE_MAP.get(mood, "storyteller")
            self.voice_id = VOICE_PRESETS.get(preset_name, DEFAULT_VOICE_ID)
        
        self._session = requests.Session()
        self._session.headers.update({
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        })
        
        logger.info(
            "ElevenLabs TTS initialized: voice=%s, mood=%s",
            self.voice_id, mood,
        )

    def generate_narration(
        self,
        key_points: list,
        output_dir: Path,
    ) -> list[ElevenLabsClip]:
        """
        Generate high-quality TTS for each key point with word timings.
        
        Args:
            key_points: List of KeyPoint objects (index, narration, emotion, etc.)
            output_dir: Directory for audio files
            
        Returns:
            List of ElevenLabsClip with paths and word timings
            
        Raises:
            RuntimeError: If no clips could be generated (triggers edge-tts fallback)
        """
        audio_dir = output_dir / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        
        clips = []
        consecutive_failures = 0
        for kp in key_points:
            clip = self._generate_single(kp, audio_dir)
            clips.append(clip)
            
            if clip.duration > 0 and clip.audio_path.exists():
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                logger.warning(
                    "ElevenLabs: screen %d failed (%d consecutive failures)",
                    kp.index, consecutive_failures,
                )
                if consecutive_failures >= 2:
                    raise RuntimeError(
                        f"ElevenLabs TTS: {consecutive_failures} consecutive failures — "
                        "likely quota exhausted or API issue"
                    )
        
        valid_clips = [c for c in clips if c.duration > 0 and c.audio_path.exists()]
        if not valid_clips:
            raise RuntimeError("ElevenLabs TTS: all clips failed — no audio generated")
        
        total_dur = sum(c.duration for c in clips)
        logger.info(
            "ElevenLabs narration complete: %d/%d clips valid, %.1fs total",
            len(valid_clips), len(clips), total_dur,
        )
        return clips

    def _generate_single(self, key_point, audio_dir: Path) -> ElevenLabsClip:
        """Generate TTS for a single key point with word-level timestamps and retry."""
        text = key_point.narration
        idx = key_point.index
        emotion = getattr(key_point, "emotion", self.mood)
        
        logger.info(
            "ElevenLabs generating [%d]: '%s' (emotion=%s)",
            idx, text[:60], emotion,
        )
        
        audio_path = audio_dir / f"narration_{idx}.mp3"
        
        # Use the with-timestamps endpoint for character-level timing
        url = f"{ELEVENLABS_BASE_URL}/text-to-speech/{self.voice_id}/with-timestamps"
        
        payload = {
            "text": text,
            "model_id": ELEVENLABS_MODEL,
            "output_format": "mp3_44100_128",
            "voice_settings": self._voice_settings_for_emotion(emotion),
        }
        
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = self._session.post(url, json=payload, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                break  # success
            except requests.exceptions.RequestException as e:
                last_error = e
                status = 0
                if e.response is not None:
                    status = e.response.status_code
                
                logger.warning(
                    "ElevenLabs API error for screen %d (attempt %d/%d, status=%d): %s",
                    idx, attempt + 1, MAX_RETRIES, status, e,
                )
                
                # Don't retry on auth errors or bad requests
                if status in (401, 403, 400):
                    break
                
                # Rate limit or server error — wait and retry
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_BASE_WAIT * (2 ** attempt)
                    logger.info("Waiting %.0fs before retry...", wait)
                    time.sleep(wait)
        else:
            # All retries exhausted
            logger.error("ElevenLabs: all %d retries failed for screen %d: %s", MAX_RETRIES, idx, last_error)
            return ElevenLabsClip(index=idx, audio_path=audio_path, duration=0.0)
        
        # Extract audio
        audio_b64 = data.get("audio_base64", "")
        if not audio_b64:
            logger.error("No audio data in ElevenLabs response for screen %d", idx)
            return ElevenLabsClip(index=idx, audio_path=audio_path)
        
        audio_bytes = base64.b64decode(audio_b64)
        audio_path.write_bytes(audio_bytes)
        
        # Extract character-level alignment
        alignment = data.get("alignment", {})
        characters = alignment.get("characters", [])
        char_starts = alignment.get("character_start_times_seconds", [])
        char_ends = alignment.get("character_end_times_seconds", [])
        
        # Reconstruct word-level timings from character timings
        word_timings = self._chars_to_words(characters, char_starts, char_ends)
        
        # Get audio duration
        duration = self._get_mp3_duration(audio_path, audio_bytes)
        
        # Build grouped subtitles
        subtitle_data = self._build_grouped_subtitles(word_timings, duration)
        
        logger.info(
            "ElevenLabs [%d]: %.1fs, %d words timed, saved to %s",
            idx, duration, len(word_timings), audio_path.name,
        )
        
        return ElevenLabsClip(
            index=idx,
            audio_path=audio_path,
            duration=duration,
            word_timings=word_timings,
            subtitle_data=subtitle_data,
        )

    @staticmethod
    def _voice_settings_for_emotion(emotion: str) -> dict:
        """
        Adjust voice settings based on scene emotion.
        ElevenLabs supports stability, similarity_boost, style, and use_speaker_boost.
        """
        # Defaults — balanced storytelling
        settings = {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.4,
            "use_speaker_boost": True,
        }
        
        emotion_overrides = {
            "excitement":  {"stability": 0.3, "style": 0.7},
            "dramatic":    {"stability": 0.4, "style": 0.8},
            "suspense":    {"stability": 0.6, "style": 0.5},
            "calm":        {"stability": 0.7, "style": 0.2},
            "sadness":     {"stability": 0.6, "style": 0.5},
            "anger":       {"stability": 0.3, "style": 0.9},
            "joy":         {"stability": 0.3, "style": 0.7},
            "tension":     {"stability": 0.4, "style": 0.6},
            "horror":      {"stability": 0.5, "style": 0.6},
            "urgent":      {"stability": 0.3, "style": 0.8},
            "awe":         {"stability": 0.5, "style": 0.6},
            "mystery":     {"stability": 0.6, "style": 0.4},
            "wonder":      {"stability": 0.4, "style": 0.6},
            "triumph":     {"stability": 0.35, "style": 0.8},
            "nostalgia":   {"stability": 0.6, "style": 0.3},
        }
        
        overrides = emotion_overrides.get(emotion, {})
        settings.update(overrides)
        return settings

    @staticmethod
    def _chars_to_words(
        characters: list[str],
        starts: list[float],
        ends: list[float],
    ) -> list[WordTiming]:
        """
        Reconstruct word-level timings from character-level alignment.
        Groups characters into words by whitespace/punctuation boundaries.
        """
        if not characters or len(characters) != len(starts):
            return []
        
        words = []
        current_word = ""
        word_start = 0.0
        word_end = 0.0
        
        for i, char in enumerate(characters):
            if char == " " or char == "\n":
                # End current word
                if current_word.strip():
                    words.append(WordTiming(
                        word=current_word.strip(),
                        start=round(word_start, 3),
                        end=round(word_end, 3),
                    ))
                current_word = ""
                word_start = 0.0
            else:
                if not current_word:
                    word_start = starts[i]
                current_word += char
                word_end = ends[i]
        
        # Final word
        if current_word.strip():
            words.append(WordTiming(
                word=current_word.strip(),
                start=round(word_start, 3),
                end=round(word_end, 3),
            ))
        
        return words

    @staticmethod
    def _build_grouped_subtitles(
        word_timings: list[WordTiming],
        duration: float,
        words_per_group: int = 4,
    ) -> list[dict]:
        """Group word timings into subtitle chunks for display."""
        if not word_timings:
            return []
        
        groups = []
        for i in range(0, len(word_timings), words_per_group):
            group_words = word_timings[i:i + words_per_group]
            if not group_words:
                continue
            
            group_start = group_words[0].start
            group_end = group_words[-1].end
            
            next_start = duration
            if i + words_per_group < len(word_timings):
                next_start = word_timings[i + words_per_group].start
            group_end = max(group_end, min(next_start, group_end + 0.1))
            
            groups.append({
                "start": round(group_start, 3),
                "end": round(min(group_end, duration), 3),
                "text": " ".join(w.word for w in group_words),
                "words": [
                    {"word": w.word, "start": w.start, "end": w.end}
                    for w in group_words
                ],
            })
        
        return groups

    @staticmethod
    def _get_mp3_duration(path: Path, audio_bytes: bytes = b"") -> float:
        """Estimate MP3 duration from file size and bitrate."""
        try:
            from moviepy import AudioFileClip
            clip = AudioFileClip(str(path))
            dur = clip.duration
            clip.close()
            return dur
        except Exception:
            pass
        
        # Fallback: estimate from file size (128 kbps)
        size = len(audio_bytes) if audio_bytes else path.stat().st_size
        bitrate = 128_000 / 8  # bytes per second
        return size / bitrate if bitrate > 0 else 3.0

    def check_quota(self) -> dict:
        """Check remaining character quota."""
        try:
            resp = self._session.get(
                f"{ELEVENLABS_BASE_URL}/../v1/user/subscription",
                timeout=10,
            )
            data = resp.json()
            return {
                "tier": data.get("tier", "unknown"),
                "limit": data.get("character_limit", 0),
                "used": data.get("character_count", 0),
                "remaining": data.get("character_limit", 0) - data.get("character_count", 0),
            }
        except Exception as e:
            logger.warning("Could not check ElevenLabs quota: %s", e)
            return {"tier": "unknown", "remaining": -1}
