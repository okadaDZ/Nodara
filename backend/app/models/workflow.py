from typing import List, Optional
from pydantic import BaseModel, Field
import uuid


class Position(BaseModel):
    x: float = 0.0
    y: float = 0.0


class WorkflowNode(BaseModel):
    id: str = Field(default_factory=lambda: f"node_{uuid.uuid4().hex[:8]}")
    type: str = "agent"  # agent, input, output (extensible)
    name: str
    description: str = ""
    instructions: str = ""
    position: Optional[Position] = None


class WorkflowEdge(BaseModel):
    id: str = Field(default_factory=lambda: f"edge_{uuid.uuid4().hex[:8]}")
    source: str
    target: str


class Workflow(BaseModel):
    id: str = Field(default_factory=lambda: f"wf_{uuid.uuid4().hex[:8]}")
    name: str
    description: str = ""
    enabled: bool = True
    nodes: List[WorkflowNode] = Field(default_factory=list)
    edges: List[WorkflowEdge] = Field(default_factory=list)
