from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class RunWorkflowRequest(BaseModel):
    input: str


class NodeRunResponse(BaseModel):
    id: str
    node_id: str
    node_name: str
    status: str
    input: str | None = None
    output: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class WorkflowRunResponse(BaseModel):
    id: str
    workflow_id: str
    status: str
    input: str
    final_output: str | None = None
    error: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
    nodes: list[NodeRunResponse] = []


class WorkflowRunListResponse(BaseModel):
    runs: list[WorkflowRunResponse]
