from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from libs.models.workflow import Workflow, WorkflowNode, WorkflowEdge
from libs.langchain.chains.main_chain import CreatorAnalysis


class CreateWorkflowFromTextRequest(BaseModel):
    text: str


class AIEditWorkflowRequest(BaseModel):
    instruction: str


class GenerateAgentInstructionsRequest(BaseModel):
    user_hint: str = ""


class ImproveAgentInstructionsRequest(BaseModel):
    current_instructions: str
    user_feedback: str = ""


class SetWorkflowEnabledRequest(BaseModel):
    enabled: bool


class RenameWorkflowRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Workflow name cannot be blank.")
        return cleaned


class WorkflowSummary(BaseModel):
    id: str
    name: str
    description: str = ""
    node_count: int = 0
    run_count: int = 0
    last_run_at: datetime | None = None
    enabled: bool = True
    schedule_enabled: bool = False
    schedule_mode: str | None = None
    next_run_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WorkflowListResponse(BaseModel):
    workflows: list[WorkflowSummary]


class WorkflowDetailResponse(BaseModel):
    workflow: Workflow


class ImageWorkflowResponse(BaseModel):
    workflow: Workflow
    analysis: CreatorAnalysis


class ImageWorkflowJobCreated(BaseModel):
    job_id: str


class ImageWorkflowJobStatus(BaseModel):
    job_id: str
    status: str
    stage: str
    result: ImageWorkflowResponse | None = None
    error: str | None = None


class GeneratedInstructionResponse(BaseModel):
    instructions: str


class AudioWorkflowResponse(BaseModel):
    transcription: str
    workflow: Workflow
