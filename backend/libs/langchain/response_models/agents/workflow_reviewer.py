from __future__ import annotations

from pydantic import BaseModel, Field

from .workflow_architect import WorkflowDraft


class WorkflowReview(BaseModel):
    workflow: WorkflowDraft = Field(description="Complete corrected workflow. Return the draft unchanged when no correction is needed.")
    corrections: list[str] = Field(default_factory=list, description="Short audit trail of concrete corrections applied.")
    requires_user_review: bool = Field(description="True when unreadable evidence or unresolved direction could materially change execution.")
    confidence: float = Field(ge=0, le=1, description="Confidence that the corrected graph matches the observed image.")
