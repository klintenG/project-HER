"""
Project HER – Story History Store
Persistent storage for all generated/published stories.
Used by the Validator Agent to prevent duplicates and track performance.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict

import config

logger = logging.getLogger(__name__)

HISTORY_FILE = config.BASE_DIR / "data" / "story_history.json"


@dataclass
class StoryRecord:
    """A single story entry in the history."""
    id: str                          # unique id: YYYYMMDD_NNN
    title: str
    hook: str
    synopsis: str                    # 2-3 sentence summary
    moral: str
    genre: str                       # e.g. "drama", "sci-fi", "historical", "fable"
    tags: list[str] = field(default_factory=list)
    full_story: str = ""
    status: str = "approved"         # "approved" | "published" | "rejected"
    created_at: str = ""
    published_at: str = ""
    video_path: str = ""
    platforms_published: list[str] = field(default_factory=list)
    platform_metadata: dict = field(default_factory=dict)  # per-platform titles/descriptions
    rejection_reason: str = ""
    score: float = 0.0               # validator score 0-10

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


class StoryHistory:
    """Read/write access to the story history JSON file."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or HISTORY_FILE
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                with open(self.path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                logger.warning("Corrupt history file, starting fresh")
        return {"stories": [], "metadata": {"created": datetime.now().isoformat(),
                                            "total_generated": 0, "total_published": 0}}

    def _save(self):
        with open(self.path, "w") as f:
            json.dump(self._data, f, indent=2, default=str)

    # ── Queries ────────────────────────────────────────

    @property
    def all_stories(self) -> list[dict]:
        return self._data.get("stories", [])

    @property
    def published_stories(self) -> list[dict]:
        return [s for s in self.all_stories if s.get("status") == "published"]

    @property
    def approved_stories(self) -> list[dict]:
        return [s for s in self.all_stories if s.get("status") in ("approved", "published")]

    def get_recent_titles(self, days: int = 30) -> list[str]:
        """Get titles of stories from the last N days."""
        cutoff = datetime.now().timestamp() - (days * 86400)
        titles = []
        for s in self.all_stories:
            try:
                created = datetime.fromisoformat(s["created_at"]).timestamp()
                if created >= cutoff:
                    titles.append(s["title"])
            except (KeyError, ValueError):
                continue
        return titles

    def get_recent_synopses(self, days: int = 30) -> list[str]:
        """Get synopses of stories from the last N days for duplicate detection."""
        cutoff = datetime.now().timestamp() - (days * 86400)
        synopses = []
        for s in self.all_stories:
            try:
                created = datetime.fromisoformat(s["created_at"]).timestamp()
                if created >= cutoff:
                    synopses.append(s.get("synopsis", s.get("title", "")))
            except (KeyError, ValueError):
                continue
        return synopses

    def get_stories_for_date(self, date_str: str) -> list[dict]:
        """Get all stories for a specific date (YYYY-MM-DD)."""
        return [s for s in self.all_stories if s.get("created_at", "").startswith(date_str)]

    def get_today_count(self) -> int:
        today = datetime.now().strftime("%Y-%m-%d")
        return len(self.get_stories_for_date(today))

    # ── Mutations ──────────────────────────────────────

    def _next_id(self) -> str:
        today = datetime.now().strftime("%Y%m%d")
        today_count = sum(1 for s in self.all_stories if s.get("id", "").startswith(today))
        return f"{today}_{today_count + 1:03d}"

    def add_story(self, record: StoryRecord) -> str:
        """Add a new story to history. Returns the assigned ID."""
        if not record.id:
            record.id = self._next_id()
        self._data["stories"].append(asdict(record))
        self._data["metadata"]["total_generated"] = self._data["metadata"].get("total_generated", 0) + 1
        self._save()
        logger.info("Added story '%s' (id=%s) to history", record.title, record.id)
        return record.id

    def update_story(self, story_id: str, **updates):
        """Update fields on an existing story."""
        for s in self._data["stories"]:
            if s.get("id") == story_id:
                s.update(updates)
                if updates.get("status") == "published":
                    self._data["metadata"]["total_published"] = \
                        self._data["metadata"].get("total_published", 0) + 1
                self._save()
                logger.info("Updated story %s: %s", story_id, list(updates.keys()))
                return True
        logger.warning("Story %s not found for update", story_id)
        return False

    def mark_published(self, story_id: str, platform: str, video_path: str = ""):
        """Mark a story as published on a specific platform."""
        for s in self._data["stories"]:
            if s.get("id") == story_id:
                s["status"] = "published"
                s["published_at"] = datetime.now().isoformat()
                if video_path:
                    s["video_path"] = video_path
                platforms = s.get("platforms_published", [])
                if platform not in platforms:
                    platforms.append(platform)
                s["platforms_published"] = platforms
                self._save()
                return True
        return False

    def summary_for_validator(self, days: int = 30) -> str:
        """
        Build a compact text summary of recent stories for the validator agent.
        This is injected into the LLM prompt so the validator can detect duplicates.
        """
        recent = []
        cutoff = datetime.now().timestamp() - (days * 86400)
        for s in self.all_stories:
            try:
                created = datetime.fromisoformat(s["created_at"]).timestamp()
                if created >= cutoff:
                    recent.append(s)
            except (KeyError, ValueError):
                continue

        if not recent:
            return "No stories published in the last 30 days."

        lines = [f"=== {len(recent)} stories from the last {days} days ==="]
        for s in recent[-50:]:  # cap at last 50 to fit context windows
            lines.append(
                f"- [{s.get('genre', '?')}] \"{s.get('title', 'untitled')}\" — "
                f"{s.get('synopsis', '')[:100]}"
            )
        return "\n".join(lines)
