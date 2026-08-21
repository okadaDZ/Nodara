from pydantic import BaseModel, Field


class SchemeClassification(BaseModel):
    is_workflow_scheme: bool = Field(description="True only when the image contains nodes/steps and visible relationships that form a workflow or process scheme.")
    confidence: float = Field(ge=0, le=1, description="Confidence in the classification.")
    reason: str = Field(description="One short evidence-based reason for the decision.")
    user_message: str = Field(description="Direct message telling the user to continue or what kind of image to provide instead.")
