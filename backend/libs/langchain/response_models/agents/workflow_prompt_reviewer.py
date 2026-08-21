from pydantic import BaseModel, Field


class NodePromptEnhancement(BaseModel):
    node_id: str = Field(description="Exact id of the node whose prompt should change.")
    improvements: list[str] = Field(default_factory=list, description="Independent, concrete prompt improvements grounded in this node's graph relationships.")


class WorkflowPromptReview(BaseModel):
    enhancements: list[NodePromptEnhancement] = Field(description="One entry for every execution node, including an empty improvements list when its prompt is already sufficient.")
    cross_node_issues: list[str] = Field(default_factory=list, description="Graph-level handoff, duplication, or contract problems found across prompts.")
