from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel


class RunWorkflowRequest(BaseModel):
    input: str


class NodeRunResponse(BaseModel):
    id: str
    node_id: str
    node_name: str
    status: str
    input: Optional[str] = None
    output: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class WorkflowRunResponse(BaseModel):
    id: str
    workflow_id: str
    status: str
    input: str
    final_output: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    finished_at: Optional[datetime] = None
    nodes: List[NodeRunResponse] = []
