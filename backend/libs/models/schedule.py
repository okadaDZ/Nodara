from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class WorkflowSchedule(BaseModel):
    id: str = Field(default_factory=lambda: f"schedule_{uuid.uuid4().hex[:8]}")
    workflow_id: str
    mode: Literal["once", "window"]
    enabled: bool = True
    input_text: str
    timezone: str = "UTC"
    run_at: datetime | None = None
    window_start: str | None = None
    window_end: str | None = None
    interval_minutes: int | None = None
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @model_validator(mode="after")
    def validate_mode_fields(self) -> "WorkflowSchedule":
        if not self.input_text.strip():
            raise ValueError("Schedule input cannot be empty.")
        if self.mode == "once" and self.run_at is None:
            raise ValueError("A one-time schedule requires run_at.")
        if self.mode == "window":
            if not self.window_start or not self.window_end:
                raise ValueError("A repeating window requires start and end times.")
            if not self.interval_minutes or self.interval_minutes < 5 or self.interval_minutes > 1440:
                raise ValueError("Window interval must be between 5 and 1440 minutes.")
        return self


class ScheduleUpsert(BaseModel):
    mode: Literal["once", "window"]
    enabled: bool = True
    input_text: str
    timezone: str = "UTC"
    run_at: datetime | None = None
    window_start: str | None = None
    window_end: str | None = None
    interval_minutes: int | None = None

    @model_validator(mode="after")
    def validate_mode_fields(self) -> "ScheduleUpsert":
        if not self.input_text.strip():
            raise ValueError("Schedule input cannot be empty.")
        if self.mode == "once" and self.run_at is None:
            raise ValueError("A one-time schedule requires run_at.")
        if self.mode == "window":
            if not self.window_start or not self.window_end:
                raise ValueError("A repeating window requires start and end times.")
            if not self.interval_minutes or self.interval_minutes < 5 or self.interval_minutes > 1440:
                raise ValueError("Window interval must be between 5 and 1440 minutes.")
        return self
