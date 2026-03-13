"""
Project HER v2.0 – Pipeline Progress Tracking
Provides a callback-based system for pipeline stage progress reporting.
Used by CLI (Rich progress bars) and Web UI (SSE real-time updates).
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable

logger = logging.getLogger(__name__)


@dataclass
class StageInfo:
    """Info about a single pipeline stage."""
    name: str
    label: str
    index: int        # 1-based stage number
    total: int        # total number of stages
    status: str = "pending"   # pending | running | completed | failed
    message: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0
    elapsed: float = 0.0
    progress_pct: float = 0.0  # 0.0 – 1.0 within this stage
    detail: str = ""           # sub-step detail text


# Callback type: (stage_info) -> None
ProgressCallback = Callable[[StageInfo], None]

# Pipeline stages definition
PIPELINE_STAGES = [
    ("scrape",   "Scraping article"),
    ("analyze",  "Analyzing with AI"),
    ("visuals",  "Finding visuals"),
    ("narrate",  "Generating narration"),
    ("compose",  "Composing video"),
]


class ProgressTracker:
    """
    Tracks pipeline progress and emits callbacks.
    
    Usage:
        tracker = ProgressTracker(callback=my_handler)
        tracker.start_stage("scrape")
        tracker.update_stage("scrape", progress=0.5, detail="Downloading HTML...")
        tracker.complete_stage("scrape", "Article scraped: 500 words")
    """

    def __init__(self, callback: Optional[ProgressCallback] = None):
        self.callback = callback
        self.stages: dict[str, StageInfo] = {}
        self.total_stages = len(PIPELINE_STAGES)
        self._pipeline_start = time.time()

        for idx, (name, label) in enumerate(PIPELINE_STAGES, 1):
            self.stages[name] = StageInfo(
                name=name,
                label=label,
                index=idx,
                total=self.total_stages,
            )

    def start_stage(self, name: str, message: str = ""):
        """Mark a stage as running."""
        stage = self.stages.get(name)
        if not stage:
            return
        stage.status = "running"
        stage.started_at = time.time()
        stage.message = message or f"Starting {stage.label}..."
        stage.progress_pct = 0.0
        self._emit(stage)

    def update_stage(
        self,
        name: str,
        progress: float = 0.0,
        detail: str = "",
        message: str = "",
    ):
        """Update progress within a stage (0.0 to 1.0)."""
        stage = self.stages.get(name)
        if not stage:
            return
        stage.progress_pct = max(0.0, min(1.0, progress))
        if detail:
            stage.detail = detail
        if message:
            stage.message = message
        stage.elapsed = time.time() - stage.started_at
        self._emit(stage)

    def complete_stage(self, name: str, message: str = ""):
        """Mark a stage as completed."""
        stage = self.stages.get(name)
        if not stage:
            return
        stage.status = "completed"
        stage.completed_at = time.time()
        stage.elapsed = stage.completed_at - stage.started_at
        stage.progress_pct = 1.0
        stage.message = message or f"{stage.label} complete"
        self._emit(stage)

    def fail_stage(self, name: str, error: str = ""):
        """Mark a stage as failed."""
        stage = self.stages.get(name)
        if not stage:
            return
        stage.status = "failed"
        stage.completed_at = time.time()
        stage.elapsed = stage.completed_at - stage.started_at
        stage.message = error or f"{stage.label} failed"
        self._emit(stage)

    def get_overall_progress(self) -> float:
        """Get overall pipeline progress (0.0 to 1.0)."""
        completed = sum(1 for s in self.stages.values() if s.status == "completed")
        running = [s for s in self.stages.values() if s.status == "running"]
        partial = running[0].progress_pct if running else 0.0
        return (completed + partial) / self.total_stages

    def get_elapsed(self) -> float:
        """Total elapsed time since pipeline start."""
        return time.time() - self._pipeline_start

    def to_dict(self) -> dict:
        """Serialize full progress state for SSE/JSON."""
        return {
            "overall_progress": round(self.get_overall_progress(), 3),
            "elapsed": round(self.get_elapsed(), 1),
            "stages": [
                {
                    "name": s.name,
                    "label": s.label,
                    "index": s.index,
                    "total": s.total,
                    "status": s.status,
                    "message": s.message,
                    "elapsed": round(s.elapsed, 1),
                    "progress_pct": round(s.progress_pct, 3),
                    "detail": s.detail,
                }
                for s in self.stages.values()
            ],
        }

    def _emit(self, stage: StageInfo):
        """Emit progress callback."""
        if self.callback:
            try:
                self.callback(stage)
            except Exception as e:
                logger.debug("Progress callback error: %s", e)
