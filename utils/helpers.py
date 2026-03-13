"""
Project HER – Utility helpers
Common helper functions used across modules.
"""

from __future__ import annotations

import re
import hashlib
import unicodedata
from pathlib import Path
from typing import Optional


def slugify(text: str, max_length: int = 50) -> str:
    """Convert text to a URL/filename-safe slug."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text[:max_length]


def hash_text(text: str) -> str:
    """Return a short MD5 hash of text (for caching / unique IDs)."""
    return hashlib.md5(text.encode()).hexdigest()[:10]


def clamp(value: float, lo: float, hi: float) -> float:
    """Clamp a value between lo and hi."""
    return max(lo, min(hi, value))


def ensure_dir(path: Path) -> Path:
    """Create directory if it doesn't exist and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def seconds_to_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timestamp format HH:MM:SS,mmm."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_srt(subtitles: list[dict], output_path: Path) -> Path:
    """
    Generate an SRT subtitle file.

    Each subtitle dict: {"start": float, "end": float, "text": str}
    """
    lines = []
    for i, sub in enumerate(subtitles, 1):
        start = seconds_to_timestamp(sub["start"])
        end = seconds_to_timestamp(sub["end"])
        lines.append(f"{i}")
        lines.append(f"{start} --> {end}")
        lines.append(sub["text"])
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def wrap_text(text: str, max_chars: int = 35) -> str:
    """Wrap text to fit within max_chars per line."""
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        if len(current_line) + len(word) + 1 <= max_chars:
            current_line = f"{current_line} {word}".strip()
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return "\n".join(lines)


def truncate_text(text: str, max_length: int = 200) -> str:
    """Truncate text to max_length, ending at a word boundary."""
    if len(text) <= max_length:
        return text
    truncated = text[:max_length].rsplit(" ", 1)[0]
    return truncated.rstrip(".,;:!?") + "..."
