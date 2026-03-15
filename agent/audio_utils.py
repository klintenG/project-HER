"""
Project HER v2.0 – Audio Utilities
====================================
Audio post-processing utilities for enhanced pipeline:
- Silence gap insertion between narration clips
- Transition SFX generation and staging
"""

from __future__ import annotations

import logging
import struct
import wave
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger("audio_utils")


def append_silence_to_audio(
    audio_path,
    silence_ms: int = 300,
    output_path=None,
) -> Optional[float]:
    """
    Append silence to the end of an audio file (MP3 or WAV).
    Overwrites the source file (or writes to output_path).
    
    Args:
        audio_path: Path (str or Path) to the source audio file
        silence_ms: Duration of silence in milliseconds
        output_path: Optional output path (defaults to overwriting source)
        
    Returns:
        New duration in seconds, or None on failure
    """
    audio_path = Path(audio_path)
    if silence_ms <= 0:
        return None
    
    out = Path(output_path) if output_path else audio_path
    
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(str(audio_path))
        silence = AudioSegment.silent(duration=silence_ms)
        combined = audio + silence
        fmt = out.suffix.lstrip(".") or "mp3"
        combined.export(str(out), format=fmt)
        new_duration = len(combined) / 1000.0
        logger.debug("Appended %dms silence to %s (%.1fs)", silence_ms, audio_path.name, new_duration)
        return new_duration
    except ImportError:
        pass
    
    # Fallback: use moviepy for MP3 files
    try:
        from moviepy import AudioFileClip, concatenate_audioclips
        clip = AudioFileClip(str(audio_path))
        
        sr = clip.fps or 44100
        
        from moviepy import AudioClip
        silence_clip = AudioClip(
            lambda t: np.zeros((1, clip.nchannels)),
            duration=silence_ms / 1000,
            fps=sr,
        )
        
        combined = concatenate_audioclips([clip, silence_clip])
        combined.write_audiofile(str(out), logger=None)
        new_duration = combined.duration
        clip.close()
        combined.close()
        logger.debug("Appended %dms silence to %s (moviepy, %.1fs)", silence_ms, audio_path.name, new_duration)
        return new_duration
    except Exception as e:
        logger.warning("Could not append silence to %s: %s", audio_path.name, e)
        return None


def generate_whoosh_sfx(output_dir: Path) -> Path:
    """
    Generate a clean whoosh/swoosh transition sound effect.
    Returns path to the WAV file.
    """
    output_path = output_dir / "sfx_whoosh.wav"
    if output_path.exists() and output_path.stat().st_size > 1000:
        return output_path
    
    sample_rate = 44100
    duration = 0.35
    num_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, num_samples)
    
    # Frequency sweep (low to high to low)
    freq = 200 + 1800 * np.sin(np.pi * t / duration)
    phase = 2 * np.pi * np.cumsum(freq) / sample_rate
    
    # White noise filtered with envelope
    noise = np.random.randn(num_samples) * 0.3
    
    # Combine sweep + noise
    signal = np.sin(phase) * 0.4 + noise
    
    # Amplitude envelope (quick attack, sustain, decay)
    envelope = np.exp(-3 * ((t - duration/2) / (duration/3)) ** 2)
    signal *= envelope * 0.6
    
    # Normalize
    peak = np.max(np.abs(signal))
    if peak > 0:
        signal = signal / peak * 0.7
    
    # Write WAV
    _write_wav_mono(output_path, signal, sample_rate)
    logger.info("Generated whoosh SFX: %s", output_path.name)
    return output_path


def _write_wav_mono(path: Path, audio: np.ndarray, sample_rate: int = 44100):
    """Write a mono numpy array as a 16-bit WAV file."""
    audio_int = np.clip(audio * 32767, -32768, 32767).astype(np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_int.tobytes())
