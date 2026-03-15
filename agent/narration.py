"""
Project HER v2.0 – Narration Engine
Generates AI voice narration with WORD-LEVEL timestamps for animated captions.
Uses edge-tts WordBoundary events for precise subtitle synchronization.

v2.1 enhancements:
- Dual-voice support for Ghost Collaboration mode
- Speaker-aware narration generation
- Voice pair presets from config
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import edge_tts

import config
from agent.analyzer import KeyPoint
from utils.helpers import ensure_dir

logger = logging.getLogger(__name__)


@dataclass
class WordTiming:
    """Precise timing for a single word from TTS engine."""
    word: str
    start: float  # seconds
    end: float    # seconds


@dataclass
class NarrationClip:
    """A generated audio narration clip for a single scene."""
    key_point_index: int
    audio_path: Path
    duration: float = 0.0
    word_timings: list[WordTiming] = field(default_factory=list)
    subtitle_data: list[dict] = field(default_factory=list)  # grouped for display
    speaker: str = ""  # "narrator", "character", or "" for standard mode


class NarrationEngine:
    """
    Generates TTS narration with word-level timestamps.
    
    Key upgrade: Captures WordBoundary events from edge-tts to enable
    karaoke-style animated captions with precise per-word timing.
    """

    def __init__(
        self,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        volume: Optional[str] = None,
    ):
        self.voice = voice or config.DEFAULT_VOICE
        self.rate = rate or config.VOICE_SPEED or config.NARRATION_RATE
        self.volume = volume or config.NARRATION_VOLUME

    def generate_narration(
        self,
        key_points: list[KeyPoint],
        output_dir: Path,
    ) -> list[NarrationClip]:
        """Generate TTS audio with word-level timing for each key point."""
        audio_dir = ensure_dir(output_dir / "audio")
        clips = asyncio.run(self._generate_all(key_points, audio_dir))
        return clips

    async def _generate_all(
        self,
        key_points: list[KeyPoint],
        audio_dir: Path,
    ) -> list[NarrationClip]:
        """Generate all narration clips sequentially."""
        clips = []
        for kp in key_points:
            clip = await self._generate_single(kp, audio_dir)
            clips.append(clip)
        return clips

    async def _generate_single(
        self,
        key_point: KeyPoint,
        audio_dir: Path,
    ) -> NarrationClip:
        """Generate TTS audio for a single key point with word-level timestamps."""
        logger.info(
            "Generating narration for key point %d: '%s'",
            key_point.index,
            key_point.narration[:60],
        )

        audio_path = audio_dir / f"narration_{key_point.index}.mp3"

        communicate = edge_tts.Communicate(
            text=key_point.narration,
            voice=self.voice,
            rate=self.rate,
            volume=self.volume,
            boundary="WordBoundary",
        )

        # Stream: collect audio bytes AND per-word boundary timestamps
        # edge-tts v7.x supports boundary='WordBoundary' for precise per-word timing.
        audio_chunks = []
        word_boundaries = []

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                offset = chunk.get("offset", 0)
                duration = chunk.get("duration", 0)
                text = chunk.get("text", "")
                # Convert from 100-nanosecond units to seconds
                start_sec = offset / 10_000_000
                dur_sec = duration / 10_000_000
                if text.strip():
                    word_boundaries.append(WordTiming(
                        word=text.strip(),
                        start=round(start_sec, 3),
                        end=round(start_sec + dur_sec, 3),
                    ))

        # Write audio file
        audio_path.write_bytes(b"".join(audio_chunks))

        # Use precise word-level timing from edge-tts
        word_timings = word_boundaries

        # Get actual audio duration
        duration = self._get_audio_duration(audio_path)

        # Build grouped subtitle data from word timings
        subtitle_data = self._build_grouped_subtitles(word_timings, duration)

        logger.info(
            "Narration %d generated: %.1fs, %d words timed, saved to %s",
            key_point.index,
            duration,
            len(word_timings),
            audio_path.name,
        )

        return NarrationClip(
            key_point_index=key_point.index,
            audio_path=audio_path,
            duration=duration,
            word_timings=word_timings,
            subtitle_data=subtitle_data,
        )

    @staticmethod
    def _estimate_word_timings(
        sentence_boundaries: list[dict],
    ) -> list[WordTiming]:
        """
        Estimate per-word timing from sentence-level boundaries.
        
        edge-tts v7.x only provides SentenceBoundary events, so we split
        each sentence's time span across its words proportionally based on
        character length (longer words take more time to speak).
        """
        word_timings: list[WordTiming] = []
        for sent in sentence_boundaries:
            words = sent["text"].split()
            if not words:
                continue

            sent_start = sent["start"]
            sent_dur = sent["duration"]

            # Weight by character count (add 1 to avoid zero-length)
            char_counts = [len(w) + 1 for w in words]
            total_chars = sum(char_counts)

            cursor = sent_start
            for word, chars in zip(words, char_counts):
                word_dur = sent_dur * (chars / total_chars)
                word_timings.append(WordTiming(
                    word=word,
                    start=round(cursor, 3),
                    end=round(cursor + word_dur, 3),
                ))
                cursor += word_dur

        return word_timings

    def _build_grouped_subtitles(
        self,
        word_timings: list[WordTiming],
        duration: float,
        words_per_group: int = 4,
    ) -> list[dict]:
        """
        Group word timings into subtitle display chunks.
        Each group contains individual word timings for karaoke-style highlighting.
        """
        if not word_timings:
            return []

        groups = []
        for i in range(0, len(word_timings), words_per_group):
            group_words = word_timings[i:i + words_per_group]
            if not group_words:
                continue

            group_start = group_words[0].start
            group_end = group_words[-1].end

            # Extend group end to next group start (or duration) for no gaps
            next_start = duration
            if i + words_per_group < len(word_timings):
                next_start = word_timings[i + words_per_group].start
            group_end = max(group_end, min(next_start, group_end + 0.1))

            groups.append({
                "start": round(group_start, 3),
                "end": round(min(group_end, duration), 3),
                "text": " ".join(w.word for w in group_words),
                "words": [
                    {
                        "word": w.word,
                        "start": w.start,
                        "end": w.end,
                    }
                    for w in group_words
                ],
            })

        return groups

    @staticmethod
    def _get_audio_duration(audio_path: Path) -> float:
        """Get the duration of an audio file with multiple fallback methods."""
        # Method 1: moviepy
        try:
            from moviepy import AudioFileClip
            clip = AudioFileClip(str(audio_path))
            dur = clip.duration
            clip.close()
            return dur
        except Exception:
            pass

        # Method 2: mutagen (lightweight, handles mp3/ogg/wav)
        try:
            from mutagen import File as MutagenFile
            audio = MutagenFile(str(audio_path))
            if audio and audio.info and audio.info.length:
                return audio.info.length
        except Exception:
            pass

        # Method 3: pydub
        try:
            from pydub import AudioSegment
            seg = AudioSegment.from_file(str(audio_path))
            return len(seg) / 1000.0
        except Exception:
            pass

        # Method 4: file-size estimation (very rough — assumes 16kHz 16-bit mono for edge-tts mp3)
        try:
            size = audio_path.stat().st_size
            # Typical edge-tts mp3 bitrate ~48kbps → 6000 bytes/sec
            estimated = size / 6000.0
            logger.warning("Audio duration estimated from file size: %.1fs — timing may be approximate", estimated)
            return max(1.0, estimated)
        except Exception:
            pass

        logger.error("Could not determine audio duration for %s — using 3.0s fallback", audio_path)
        return 3.0

    # ── Dual-Voice (Ghost Collaboration) ──────────────

    def generate_dialogue_narration(
        self,
        screens: list,
        output_dir: Path,
        voice_pair_name: str = "default",
    ) -> list[NarrationClip]:
        """
        Generate TTS narration for Ghost Collaboration dialogue mode.
        
        Each screen has a `speaker` field ("narrator" or "character").
        Uses different voices for each speaker from GHOST_COLLAB_VOICES config.
        
        Args:
            screens: List of ScreenSegment objects with speaker fields.
            output_dir: Directory for audio output.
            voice_pair_name: Key into config.GHOST_COLLAB_VOICES.
            
        Returns:
            List of NarrationClip objects with speaker metadata.
        """
        audio_dir = ensure_dir(output_dir / "audio")
        
        # Get voice pair
        voice_pair = config.GHOST_COLLAB_VOICES.get(
            voice_pair_name, config.GHOST_COLLAB_VOICES["default"]
        )
        narrator_voice = voice_pair["narrator"]
        character_voice = voice_pair["character"]
        
        logger.info(
            "Generating dialogue narration: narrator=%s, character=%s",
            narrator_voice, character_voice,
        )
        
        clips = asyncio.run(
            self._generate_dialogue_all(
                screens, audio_dir, narrator_voice, character_voice
            )
        )
        return clips

    async def _generate_dialogue_all(
        self,
        screens: list,
        audio_dir: Path,
        narrator_voice: str,
        character_voice: str,
    ) -> list[NarrationClip]:
        """Generate all dialogue narration clips sequentially."""
        clips = []
        for screen in screens:
            # Skip intro/outro screens
            if getattr(screen, "is_intro", False) or getattr(screen, "is_outro", False):
                continue
            
            speaker = getattr(screen, "speaker", "narrator") or "narrator"
            voice = character_voice if speaker == "character" else narrator_voice
            
            clip = await self._generate_dialogue_single(
                screen, audio_dir, voice, speaker
            )
            clips.append(clip)
        return clips

    async def _generate_dialogue_single(
        self,
        screen,
        audio_dir: Path,
        voice: str,
        speaker: str,
    ) -> NarrationClip:
        """Generate TTS for a single dialogue screen with the appropriate voice."""
        logger.info(
            "Generating dialogue narration [%s] screen %d: '%s'",
            speaker, screen.index, screen.text[:60],
        )

        audio_path = audio_dir / f"narration_{screen.index}.mp3"

        communicate = edge_tts.Communicate(
            text=screen.text,
            voice=voice,
            rate=self.rate,
            volume=self.volume,
            boundary="WordBoundary",
        )

        audio_chunks = []
        word_boundaries = []

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                offset = chunk.get("offset", 0)
                duration = chunk.get("duration", 0)
                text = chunk.get("text", "")
                start_sec = offset / 10_000_000
                dur_sec = duration / 10_000_000
                if text.strip():
                    word_boundaries.append(WordTiming(
                        word=text.strip(),
                        start=round(start_sec, 3),
                        end=round(start_sec + dur_sec, 3),
                    ))

        audio_path.write_bytes(b"".join(audio_chunks))
        word_timings = word_boundaries
        duration = self._get_audio_duration(audio_path)
        subtitle_data = self._build_grouped_subtitles(word_timings, duration)

        logger.info(
            "Dialogue narration [%s] %d: %.1fs, %d words, %s",
            speaker, screen.index, duration, len(word_timings), audio_path.name,
        )

        return NarrationClip(
            key_point_index=screen.index,
            audio_path=audio_path,
            duration=duration,
            word_timings=word_timings,
            subtitle_data=subtitle_data,
            speaker=speaker,
        )

    @staticmethod
    def list_available_voices() -> list[dict]:
        """List all available edge-tts voices."""
        voices = asyncio.run(edge_tts.list_voices())
        english_voices = [
            {
                "name": v["ShortName"],
                "gender": v["Gender"],
                "locale": v["Locale"],
            }
            for v in voices
            if v["Locale"].startswith("en")
        ]
        return english_voices
