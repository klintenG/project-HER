"""
Project HER v2.0 – Replicate TTS Engine (Kokoro-82m)
=====================================================
Ultra-cheap TTS via Replicate's hosted Kokoro-82m model.
Cost: ~$0.00022 per run → ~$0.003 per video (12 scenes).

Kokoro is a lightweight 82M param model (StyleTTS2-based) that produces
natural-sounding speech. It runs on T4 GPU with ~1s latency.

Word-level timing is estimated proportionally since Kokoro doesn't
return alignment data. This still works well for karaoke captions.

Usage:
    from agent.replicate_tts import ReplicateTTS
    tts = ReplicateTTS(mood="dramatic")
    clips = tts.generate_narration(key_points, output_dir)
"""

from __future__ import annotations

import base64
import io
import logging
import os
import struct
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import config

logger = logging.getLogger("replicate_tts")

# ── API Config ────────────────────────────────────

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", getattr(config, "REPLICATE_API_TOKEN", ""))

# Model identifiers on Replicate
KOKORO_MODEL = "jaaari/kokoro-82m"

# ── Voice Presets ─────────────────────────────────
# Kokoro uses voice codes: a=American, b=British, f=female, m=male
VOICE_PRESETS = {
    "storyteller":   "af_bella",      # Female, warm, A-quality
    "narrator":      "am_michael",    # Male, clear
    "warm":          "bf_emma",       # British female, warm
    "energetic":     "af_nova",       # Female, bright
    "deep":          "am_fenrir",     # Male, deep
    "professional":  "af_sarah",      # Female, professional
    "gentle":        "af_nicole",     # Female, gentle
    "dramatic":      "am_adam",       # Male, dramatic
    "british_male":  "bm_george",     # British male
    "british_fem":   "bf_isabella",   # British female
}

# Mood → voice preset mapping
MOOD_VOICE_MAP = {
    "neutral":      "narrator",
    "excitement":   "energetic",
    "dramatic":     "dramatic",
    "warm":         "storyteller",
    "suspense":     "deep",
    "inspirational":"storyteller",
    "thoughtful":   "professional",
    "calm":         "gentle",
    "playful":      "energetic",
    "serious":      "british_male",
    "melancholy":   "warm",
}


@dataclass
class WordTiming:
    """Word-level timing for karaoke captions."""
    word: str
    start: float
    end: float


@dataclass
class ReplicateClip:
    """Generated TTS clip with estimated word timings."""
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


class ReplicateTTS:
    """
    Ultra-cheap TTS via Replicate's Kokoro-82m model.
    
    Cost: ~$0.00022 per run (~4,545 runs per $1).
    A 12-scene video costs ~$0.003 total.
    """

    def __init__(
        self,
        voice: Optional[str] = None,
        mood: str = "neutral",
    ):
        self.mood = mood

        # Select voice based on mood if no explicit voice
        if voice:
            self.voice = voice
        else:
            preset_name = MOOD_VOICE_MAP.get(mood, "storyteller")
            self.voice = VOICE_PRESETS.get(preset_name, "af_bella")

        logger.info(
            "Replicate TTS (Kokoro) initialized: voice=%s, mood=%s",
            self.voice, mood,
        )

    def generate_narration(
        self,
        key_points: list,
        output_dir: Path,
    ) -> list[ReplicateClip]:
        """
        Generate TTS for each key point using Kokoro via Replicate.
        
        Args:
            key_points: List of KeyPoint objects (index, narration, emotion)
            output_dir: Directory for audio files
            
        Returns:
            List of ReplicateClip with paths and estimated word timings
        """
        import replicate

        audio_dir = output_dir / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        clips = []
        for kp in key_points:
            clip = self._generate_single(kp, audio_dir)
            clips.append(clip)

        total_dur = sum(c.duration for c in clips)
        logger.info(
            "Replicate narration complete: %d clips, %.1fs total",
            len(clips), total_dur,
        )
        return clips

    def _generate_single(self, key_point, audio_dir: Path) -> ReplicateClip:
        """Generate TTS for a single key point."""
        import replicate

        text = key_point.narration
        idx = key_point.index
        emotion = getattr(key_point, "emotion", self.mood)

        # Choose voice per-emotion for variety
        emotion_voice = MOOD_VOICE_MAP.get(emotion)
        voice = VOICE_PRESETS.get(emotion_voice, self.voice) if emotion_voice else self.voice

        logger.info(
            "Replicate generating [%d]: '%s' (voice=%s)",
            idx, text[:60], voice,
        )

        audio_path = audio_dir / f"narration_{idx}.mp3"

        try:
            # Call Kokoro via Replicate
            output = replicate.run(
                KOKORO_MODEL,
                input={
                    "text": text,
                    "voice": voice,
                    "speed": 1.0,
                },
            )

            # Output is a URL to the generated audio file
            if hasattr(output, "read"):
                # FileOutput object — read directly
                audio_bytes = output.read()
            elif isinstance(output, str) and output.startswith("http"):
                # URL string — download
                audio_bytes = urllib.request.urlopen(output).read()
            else:
                # Might be an iterator or other format
                audio_bytes = b""
                for chunk in output:
                    if isinstance(chunk, bytes):
                        audio_bytes += chunk
                    elif isinstance(chunk, str) and chunk.startswith("http"):
                        audio_bytes = urllib.request.urlopen(chunk).read()
                        break

            if not audio_bytes:
                logger.error("No audio data returned for screen %d", idx)
                return ReplicateClip(index=idx, audio_path=audio_path)

            # Save audio
            audio_path.write_bytes(audio_bytes)

            # Get duration
            duration = self._get_audio_duration(audio_path, audio_bytes)

            # Estimate word-level timings proportionally
            word_timings = self._estimate_word_timings(text, duration)

            # Build grouped subtitles
            subtitle_data = self._build_grouped_subtitles(word_timings, duration)

            logger.info(
                "Replicate [%d]: %.1fs, %d words, saved to %s",
                idx, duration, len(word_timings), audio_path.name,
            )

            return ReplicateClip(
                index=idx,
                audio_path=audio_path,
                duration=duration,
                word_timings=word_timings,
                subtitle_data=subtitle_data,
            )

        except Exception as e:
            logger.error("Replicate TTS error for screen %d: %s", idx, e)
            return ReplicateClip(index=idx, audio_path=audio_path)

    @staticmethod
    def _estimate_word_timings(text: str, duration: float) -> list[WordTiming]:
        """
        Estimate word-level timings proportionally from audio duration.
        
        Uses character-weighted distribution: longer words get more time.
        Adds small padding for natural pauses at punctuation.
        """
        words = text.split()
        if not words or duration <= 0:
            return []

        # Weight each word by character length
        weights = []
        for w in words:
            base = len(w)
            # Add pause weight for punctuation
            if w.endswith((".", "!", "?", "...")):
                base += 3  # longer pause at sentence end
            elif w.endswith((",", ";", ":")):
                base += 1.5  # shorter pause at clause break
            elif w.endswith(("—", "–")):
                base += 2  # dash pause
            weights.append(base)

        total_weight = sum(weights)
        if total_weight == 0:
            total_weight = len(words)
            weights = [1.0] * len(words)

        # Small margin at start and end
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

    @staticmethod
    def _build_grouped_subtitles(
        word_timings: list[WordTiming],
        duration: float,
        words_per_group: int = 5,
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

    @staticmethod
    def _get_audio_duration(audio_path: Path, audio_bytes: bytes) -> float:
        """Get audio duration from the file."""
        # Try pydub first
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(str(audio_path))
            return len(audio) / 1000.0
        except Exception:
            pass

        # Try mutagen
        try:
            from mutagen.mp3 import MP3
            info = MP3(str(audio_path))
            return info.info.length
        except Exception:
            pass

        # Rough estimate from file size (128kbps MP3)
        return len(audio_bytes) / (128 * 1024 / 8)


# ── Cost estimator ────────────────────────────────

def estimate_replicate_cost(num_scenes: int = 12) -> float:
    """Estimate Replicate Kokoro cost for a video."""
    cost_per_run = 0.00022
    return num_scenes * cost_per_run
