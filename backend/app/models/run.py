from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class NodeRun(BaseModel):
    id: str = Field(default_factory=lambda: f"noderun_{uuid.uuid4().hex[:8]}")
    workflow_run_id: str
    node_id: str
    node_name: str = ""
    status: str = "waiting"  # waiting, running, completed, failed
    input: Optional[str] = None
    output: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class WorkflowRun(BaseModel):
    id: str = Field(default_factory=lambda: f"run_{uuid.uuid4().hex[:8]}")
    workflow_id: str
    status: str = "running"  # running, completed, failed
    input: str
    final_output: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    nodes: List[NodeRun] = Field(default_factory=list)
