from pydantic import BaseModel, Field


class EnhancedNodePrompt(BaseModel):
    node_id: str = Field(description="Exact node id supplied in the input.")
    instructions: str = Field(description="Final improved prompt. Preserve correct requirements and apply only supplied improvements.")
