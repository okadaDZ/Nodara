from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from app.models.workflow import Workflow, WorkflowNode, WorkflowEdge


class CreateWorkflowFromTextRequest(BaseModel):
    text: str


class AIEditWorkflowRequest(BaseModel):
    instruction: str


class GenerateAgentInstructionsRequest(BaseModel):
    current_instructions: Optional[str] = ""
    user_hint: Optional[str] = ""


class WorkflowSummary(BaseModel):
    id: str
    name: str
    description: str = ""
    node_count: int = 0
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class WorkflowListResponse(BaseModel):
    workflows: List[WorkflowSummary]


class WorkflowDetailResponse(BaseModel):
    workflow: Workflow


class AudioWorkflowResponse(BaseModel):
    transcription: str
    workflow: Workflow
