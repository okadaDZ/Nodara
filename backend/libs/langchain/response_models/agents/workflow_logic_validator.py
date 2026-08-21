from pydantic import BaseModel, Field

from .workflow_architect import WorkflowDraft


class WorkflowRecommendation(BaseModel):
    title: str = Field(description="Short recommendation title shown to the user.")
    rationale: str = Field(description="Concrete logical gap or improvement supported by the workflow.")
    instruction: str = Field(description="Self-contained edit instruction that another agent can apply to the workflow.")


class WorkflowLogicReview(BaseModel):
    workflow: WorkflowDraft = Field(description="Complete structurally safe workflow; preserve the drawing unless a definite logical error requires a minimal repair.")
    is_logical: bool = Field(description="True when the workflow can execute coherently as drawn.")
    requires_redraw: bool = Field(description="True only when ambiguity or broken routing prevents a trustworthy workflow.")
    requires_user_decision: bool = Field(description="True when optional recommendations are available for the user to apply or skip.")
    summary: str = Field(description="Short plain-language assessment for the user.")
    recommendations: list[WorkflowRecommendation] = Field(default_factory=list, description="Optional improvements. Never silently apply these to the returned workflow.")
    confidence: float = Field(ge=0, le=1, description="Confidence in the logic assessment.")
