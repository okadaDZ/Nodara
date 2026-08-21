from pydantic import BaseModel, Field


class NodePromptDraft(BaseModel):
    node_id: str = Field(description="Exact node id supplied in the input.")
    instructions: str = Field(description="Production-ready agent system prompt with INPUT, TASK, RULES, and OUTPUT sections.")
