"""Validated, non-secret Autopilot settings. Manual generation never reads these."""
from __future__ import annotations
import json
import os
from datetime import datetime, timedelta, timezone, time
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Settings(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    enabled: bool = False
    dry_run: bool = True
    timezone: str = 'Asia/Kolkata'
    publish_start: str = '18:00'
    publish_end: str = '19:00'
    publish_time: str = '18:30'
    ready_queue_target: int = Field(default=3, ge=1, le=10)
    category_weights: dict[str, float] = Field(default_factory=lambda: dict(MYTHOLOGY=35,FANTASY=20,SCIFI=20,FOLKLORE=15,OTHER=10))
    score_weights: dict[str, float] = Field(default_factory=lambda: dict(hook=20,tension=20,visual=20,originality=15,emotion=10,clarity=10,ending=5))
    minimum_score: float = Field(default=7.5, ge=0, le=10)
    similarity_threshold: float = Field(default=.78, gt=0, le=1)
    min_video_seconds: int = Field(default=45, ge=15, le=180)
    max_video_seconds: int = Field(default=75, ge=15, le=180)
    llm_model: str = ''
    max_llm_calls: int = Field(default=12, ge=4, le=24)
    max_candidate_batches: int = Field(default=2, ge=1, le=3)
    max_script_revisions: int = Field(default=2, ge=0, le=4)
    max_output_tokens: int = Field(default=3000, ge=500, le=6000)
    model_timeout: int = Field(default=120, ge=15, le=300)
    max_input_chars: int = Field(default=48000, ge=2000, le=100000)
    llm_input_usd_per_million: float = Field(default=.65, ge=0, le=100)
    llm_output_usd_per_million: float = Field(default=2.75, ge=0, le=100)
    daily_cost_limit_usd: float = Field(default=6, gt=0, le=100)
    # Conservative reservation per request, not a claim about provider billing.
    llm_call_reserve_usd: float = Field(default=.10, gt=0, le=10)
    engine_reserve_usd: float = Field(default=1, gt=0, le=50)
    max_image_calls: int = Field(default=24, ge=1, le=64)
    image_request_reserve_usd: float = Field(default=.05, gt=0, le=5)
    channel_queue_limit: int = Field(default=10, ge=1, le=100)
    max_publication_attempts: int = Field(default=5, ge=1, le=10)

    @model_validator(mode='after')
    def valid(self):
        if self.timezone != 'Asia/Kolkata':
            raise ValueError('Autopilot timezone must be Asia/Kolkata')
        values = [time.fromisoformat(x) for x in (self.publish_start,self.publish_time,self.publish_end)]
        if not time(18) <= values[0] <= values[1] <= values[2] <= time(19):
            raise ValueError('Publication must fall within 18:00–19:00 IST')
        if any(v.second or v.microsecond or v.tzinfo for v in values):
            raise ValueError('Use local HH:MM publication times')
        if self.max_video_seconds < self.min_video_seconds:
            raise ValueError('Invalid duration bounds')
        for weights in (self.category_weights,self.score_weights):
            if not weights or any(v < 0 for v in weights.values()) or sum(weights.values()) <= 0:
                raise ValueError('Weights must be nonnegative with a positive total')
        if set(self.category_weights) - {'MYTHOLOGY','FANTASY','SCIFI','FOLKLORE','OTHER'}:
            raise ValueError('Unsupported story category')
        if set(self.score_weights) != {'hook','tension','visual','originality','emotion','clarity','ending'}:
            raise ValueError('All seven editorial score weights are required')
        return self

    @classmethod
    def environment(cls):
        values = {}
        for name in cls.model_fields:
            key = 'AUTOPILOT_' + name.upper()
            if name == 'dry_run': key = 'BUFFER_DRY_RUN'
            if key in os.environ:
                value = os.environ[key]
                values[name] = json.loads(value) if name.endswith('weights') else value
        return cls.model_validate(values)


def publication_time(settings: Settings, now: datetime, day=None):
    """Choose a future slot today, or explicitly return None after the window."""
    if now.tzinfo is None: raise ValueError('Timezone-aware clock required')
    local = now.astimezone(ZoneInfo(settings.timezone))
    day = day or local.date()
    zone = ZoneInfo(settings.timezone)
    preferred = datetime.combine(day,time.fromisoformat(settings.publish_time),zone)
    end = datetime.combine(day,time.fromisoformat(settings.publish_end),zone)
    due = max(preferred, local + timedelta(minutes=5))
    if due > end: return None
    return due.astimezone(timezone.utc)


def next_scheduled_slot(settings: Settings, now: datetime):
    """Return today's publication slot if still open, otherwise tomorrow's 18:30 IST slot."""
    if now.tzinfo is None: raise ValueError('Timezone-aware clock required')
    local = now.astimezone(ZoneInfo(settings.timezone))
    today = publication_time(settings, now, local.date())
    if today is not None: return today
    tomorrow = local.date() + timedelta(days=1)
    return datetime.combine(tomorrow, time.fromisoformat(settings.publish_time), ZoneInfo(settings.timezone)).astimezone(timezone.utc)
