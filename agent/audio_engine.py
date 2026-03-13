"""
Project HER v2.0 – Audio Engine
Generates procedural background music and sound effects.
No external music files needed — creates ambient audio programmatically.
"""

from __future__ import annotations

import logging
import struct
import math
import random
from pathlib import Path
from typing import Optional

import numpy as np

import config
from utils.helpers import ensure_dir

logger = logging.getLogger(__name__)


class AudioEngine:
    """
    Generates procedural background music and sound effects.
    
    Creates ambient music tracks programmatically using sine wave synthesis,
    eliminating the need for royalty-free music files.
    """

    SAMPLE_RATE = 44100

    # Musical scales for different moods (frequencies in Hz)
    MOOD_SCALES = {
        "calm": {
            "notes": [261.63, 293.66, 329.63, 392.00, 440.00, 523.25],  # C major pentatonic
            "tempo": 0.8,
            "reverb": 0.4,
            "pad_volume": 0.6,
        },
        "upbeat": {
            "notes": [329.63, 369.99, 415.30, 493.88, 554.37, 659.25],  # E major
            "tempo": 1.2,
            "reverb": 0.2,
            "pad_volume": 0.4,
        },
        "dramatic": {
            "notes": [220.00, 261.63, 293.66, 329.63, 415.30, 440.00],  # A minor
            "tempo": 0.6,
            "reverb": 0.5,
            "pad_volume": 0.7,
        },
        "suspenseful": {
            "notes": [220.00, 233.08, 277.18, 329.63, 369.99, 440.00],  # A phrygian
            "tempo": 0.5,
            "reverb": 0.6,
            "pad_volume": 0.8,
        },
        "playful": {
            "notes": [523.25, 587.33, 659.25, 783.99, 880.00, 1046.50],  # C major high
            "tempo": 1.4,
            "reverb": 0.15,
            "pad_volume": 0.35,
        },
        "inspirational": {
            "notes": [293.66, 349.23, 392.00, 440.00, 523.25, 587.33],  # D major
            "tempo": 0.9,
            "reverb": 0.35,
            "pad_volume": 0.55,
        },
        "neutral": {
            "notes": [261.63, 329.63, 392.00, 440.00, 523.25],  # C major triad+
            "tempo": 0.7,
            "reverb": 0.3,
            "pad_volume": 0.3,
        },
    }

    def generate_background_music(
        self,
        duration: float,
        mood: str = "neutral",
        output_dir: Optional[Path] = None,
    ) -> Path:
        """
        Generate procedural ambient background music.

        Args:
            duration: Duration in seconds.
            mood: Music mood from MUSIC_MOODS.
            output_dir: Directory to save the audio file.

        Returns:
            Path to the generated WAV file.
        """
        output_dir = output_dir or config.TEMP_DIR
        ensure_dir(output_dir)
        output_path = output_dir / "bgm.wav"

        scale_config = self.MOOD_SCALES.get(mood, self.MOOD_SCALES["neutral"])
        notes = scale_config["notes"]
        tempo = scale_config["tempo"]
        pad_volume = scale_config["pad_volume"]

        num_samples = int(duration * self.SAMPLE_RATE)
        audio = np.zeros(num_samples, dtype=np.float64)

        # Layer 1: Ambient pad (sustained chord tones)
        pad = self._generate_pad(notes[:3], duration, pad_volume)
        audio += pad[:num_samples]

        # Layer 2: Slow melodic arpeggios
        arp = self._generate_arpeggio(notes, duration, tempo, volume=0.25)
        audio += arp[:num_samples]

        # Layer 3: Sub-bass warmth
        sub = self._generate_sub_bass(notes[0] / 2, duration, volume=0.15)
        audio += sub[:num_samples]

        # Layer 4: Subtle shimmer/texture
        shimmer = self._generate_shimmer(notes[-2:], duration, volume=0.08)
        audio += shimmer[:num_samples]

        # Apply fade in/out
        fade_samples = int(config.BGM_FADE_DURATION * self.SAMPLE_RATE)
        if fade_samples > 0 and fade_samples < num_samples // 2:
            # Fade in
            fade_in = np.linspace(0, 1, fade_samples)
            audio[:fade_samples] *= fade_in
            # Fade out
            fade_out = np.linspace(1, 0, fade_samples)
            audio[-fade_samples:] *= fade_out

        # Normalize to prevent clipping
        peak = np.max(np.abs(audio))
        if peak > 0:
            audio = audio / peak * 0.85

        # Apply final volume
        audio *= config.BGM_VOLUME

        # Write WAV file
        self._write_wav(output_path, audio)
        logger.info("Background music generated: %.1fs, mood=%s", duration, mood)
        return output_path

    def generate_transition_sfx(
        self,
        sfx_type: str = "whoosh",
        output_dir: Optional[Path] = None,
    ) -> Path:
        """Generate a transition sound effect."""
        output_dir = output_dir or config.TEMP_DIR
        ensure_dir(output_dir)
        output_path = output_dir / f"sfx_{sfx_type}.wav"

        if sfx_type == "whoosh":
            audio = self._generate_whoosh(duration=0.4)
        elif sfx_type == "pop":
            audio = self._generate_pop(duration=0.15)
        elif sfx_type == "rise":
            audio = self._generate_rise(duration=0.6)
        else:
            audio = self._generate_whoosh(duration=0.4)

        audio *= config.SFX_VOLUME

        self._write_wav(output_path, audio)
        logger.info("SFX generated: %s", sfx_type)
        return output_path

    # ── Synthesis Primitives ──────────────────────────────

    def _generate_pad(
        self, notes: list[float], duration: float, volume: float
    ) -> np.ndarray:
        """Generate a sustained ambient pad from chord tones."""
        num_samples = int(duration * self.SAMPLE_RATE)
        pad = np.zeros(num_samples, dtype=np.float64)
        t = np.linspace(0, duration, num_samples, endpoint=False)

        for freq in notes:
            # Detuned pair for richness
            wave1 = np.sin(2 * np.pi * freq * t)
            wave2 = np.sin(2 * np.pi * (freq * 1.003) * t)  # Slight detune
            # Slow amplitude modulation for movement
            lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.15 * t + random.uniform(0, 2 * math.pi))
            pad += (wave1 + wave2) * lfo * volume / len(notes)

        return pad

    def _generate_arpeggio(
        self, notes: list[float], duration: float, tempo: float, volume: float
    ) -> np.ndarray:
        """Generate a gentle arpeggio pattern."""
        num_samples = int(duration * self.SAMPLE_RATE)
        arp = np.zeros(num_samples, dtype=np.float64)

        note_duration = 1.5 / tempo  # Duration of each note
        note_samples = int(note_duration * self.SAMPLE_RATE)

        current_sample = 0
        note_idx = 0

        while current_sample < num_samples:
            freq = notes[note_idx % len(notes)]
            end_sample = min(current_sample + note_samples, num_samples)
            length = end_sample - current_sample

            t = np.linspace(0, length / self.SAMPLE_RATE, length, endpoint=False)
            # Sine with gentle envelope
            envelope = np.exp(-t * 1.5)  # Decay envelope
            wave = np.sin(2 * np.pi * freq * t) * envelope * volume
            arp[current_sample:end_sample] += wave

            current_sample = end_sample
            note_idx += 1

        return arp

    def _generate_sub_bass(
        self, freq: float, duration: float, volume: float
    ) -> np.ndarray:
        """Generate a deep sub-bass tone."""
        num_samples = int(duration * self.SAMPLE_RATE)
        t = np.linspace(0, duration, num_samples, endpoint=False)
        # Low sine wave with slow LFO
        lfo = 0.8 + 0.2 * np.sin(2 * np.pi * 0.08 * t)
        wave = np.sin(2 * np.pi * freq * t) * lfo * volume
        return wave

    def _generate_shimmer(
        self, notes: list[float], duration: float, volume: float
    ) -> np.ndarray:
        """Generate high-frequency shimmer texture."""
        num_samples = int(duration * self.SAMPLE_RATE)
        shimmer = np.zeros(num_samples, dtype=np.float64)
        t = np.linspace(0, duration, num_samples, endpoint=False)

        for freq in notes:
            high_freq = freq * 2  # Octave up
            # Intermittent shimmer with random phase
            phase = random.uniform(0, 2 * math.pi)
            lfo_rate = random.uniform(0.1, 0.3)
            lfo = np.maximum(0, np.sin(2 * np.pi * lfo_rate * t + phase))
            wave = np.sin(2 * np.pi * high_freq * t) * lfo * volume / len(notes)
            shimmer += wave

        return shimmer

    def _generate_whoosh(self, duration: float = 0.4) -> np.ndarray:
        """Generate a whoosh transition sound."""
        num_samples = int(duration * self.SAMPLE_RATE)
        t = np.linspace(0, duration, num_samples, endpoint=False)

        # Filtered noise sweep
        noise = np.random.uniform(-1, 1, num_samples)
        # Frequency sweep envelope
        sweep = np.sin(np.pi * t / duration) ** 2
        # Bandpass-like effect using modulated sine
        carrier = np.sin(2 * np.pi * np.linspace(200, 2000, num_samples) * t)
        whoosh = noise * sweep * 0.3 + carrier * sweep * 0.2

        # Smooth envelope
        env = np.sin(np.pi * t / duration)
        return whoosh * env

    def _generate_pop(self, duration: float = 0.15) -> np.ndarray:
        """Generate a quick pop/click sound."""
        num_samples = int(duration * self.SAMPLE_RATE)
        t = np.linspace(0, duration, num_samples, endpoint=False)

        # Sharp attack, fast decay
        env = np.exp(-t * 30)
        freq_sweep = 800 - 600 * t / duration
        wave = np.sin(2 * np.pi * freq_sweep * t) * env
        return wave

    def _generate_rise(self, duration: float = 0.6) -> np.ndarray:
        """Generate a rising tone effect."""
        num_samples = int(duration * self.SAMPLE_RATE)
        t = np.linspace(0, duration, num_samples, endpoint=False)

        # Rising frequency
        freq = np.linspace(200, 800, num_samples)
        wave = np.sin(2 * np.pi * freq * t / self.SAMPLE_RATE * num_samples)
        env = np.linspace(0, 1, num_samples) * np.exp(-t * 0.5)
        return wave * env * 0.4

    def _write_wav(self, path: Path, audio: np.ndarray) -> None:
        """Write a mono WAV file from numpy array."""
        # Convert to 16-bit PCM
        audio = np.clip(audio, -1.0, 1.0)
        pcm = (audio * 32767).astype(np.int16)

        num_samples = len(pcm)
        data_size = num_samples * 2  # 16-bit = 2 bytes per sample

        with open(path, "wb") as f:
            # RIFF header
            f.write(b"RIFF")
            f.write(struct.pack("<I", 36 + data_size))
            f.write(b"WAVE")
            # fmt chunk
            f.write(b"fmt ")
            f.write(struct.pack("<I", 16))       # chunk size
            f.write(struct.pack("<H", 1))        # PCM format
            f.write(struct.pack("<H", 1))        # mono
            f.write(struct.pack("<I", self.SAMPLE_RATE))
            f.write(struct.pack("<I", self.SAMPLE_RATE * 2))  # byte rate
            f.write(struct.pack("<H", 2))        # block align
            f.write(struct.pack("<H", 16))       # bits per sample
            # data chunk
            f.write(b"data")
            f.write(struct.pack("<I", data_size))
            f.write(pcm.tobytes())


def select_mood_for_tone(tone: str) -> str:
    """Auto-select a background music mood based on the content tone."""
    tone_to_mood = {
        "informative": "neutral",
        "storytelling": "inspirational",
        "social": "upbeat",
        "dramatic": "dramatic",
        "educational": "calm",
        "motivational": "inspirational",
    }
    return tone_to_mood.get(tone, "neutral")
