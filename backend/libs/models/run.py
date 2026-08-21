from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class NodeRun(BaseModel):
    id: str = Field(default_factory=lambda: f"noderun_{uuid.uuid4().hex[:8]}")
    workflow_run_id: str
    node_id: str
    node_name: str = ""
    status: str = "waiting"  # waiting, running, completed, failed, skipped
    input: str | None = None
    output: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class WorkflowRun(BaseModel):
    id: str = Field(default_factory=lambda: f"run_{uuid.uuid4().hex[:8]}")
    workflow_id: str
    status: str = "running"  # running, completed, failed
    input: str
    final_output: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    nodes: list[NodeRun] = Field(default_factory=list)
