from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


NodeType = Literal["trigger", "query_builder", "agent", "condition", "action", "output", "tool", "memory", "parser"]
EdgeKind = Literal["flow", "conditional", "tool", "memory", "parser"]


class WorkflowDraftNode(BaseModel):
    id: str = Field(description="Stable lowercase snake_case identifier. It must be unique and must not contain spaces.")
    type: NodeType = Field(description="Executable or support-node type derived from visual evidence.")
    name: str = Field(description="Short human-readable title, preferably preserving the visible label.")
    description: str = Field(default="", description="One sentence describing this node's responsibility without inventing external capabilities.")
    instructions: str = Field(default="", description="Leave empty during architecture extraction; the dedicated prompt-engineering stage fills this later.")
    source_ref: str = Field(default="", description="Diagram observation reference that produced this node.")


class WorkflowDraftEdge(BaseModel):
    source: str = Field(description="Existing source node id.")
    target: str = Field(description="Existing target node id.")
    kind: EdgeKind = Field(default="flow", description="Execution or support connection kind.")
    label: str = Field(default="", description="Preserved branch label; required for conditional outcomes when visible.")


class WorkflowDraft(BaseModel):
    name: str = Field(description="Short workflow name based on the visible title or dominant purpose.")
    description: str = Field(default="", description="One factual sentence describing the extracted workflow.")
    nodes: list[WorkflowDraftNode] = Field(description="Normalized nodes; one per observed node unless duplicates are visibly the same box.")
    edges: list[WorkflowDraftEdge] = Field(description="Directed graph connections preserving fan-out, fan-in, and support attachments.")
    assumptions: list[str] = Field(default_factory=list, description="Minimal explicit assumptions made only where the image was ambiguous.")
