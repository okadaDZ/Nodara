from __future__ import annotations

import uuid
from typing import Literal
from pydantic import BaseModel, Field, model_validator
from core.settings import settings

SUPPORT_TYPES = {"tool", "memory", "parser"}


class Position(BaseModel):
    x: float = 0.0
    y: float = 0.0


class WorkflowNode(BaseModel):
    id: str = Field(default_factory=lambda: f"node_{uuid.uuid4().hex[:8]}")
    type: str = "agent"  # agent, input, output
    name: str
    description: str = ""
    instructions: str = ""
    model: str = Field(default_factory=lambda: settings.llm_model)
    model_override: bool = False
    position: Position | None = None


class WorkflowEdge(BaseModel):
    id: str = Field(default_factory=lambda: f"edge_{uuid.uuid4().hex[:8]}")
    source: str
    target: str
    kind: Literal["flow", "conditional", "tool", "memory", "parser"] = "flow"
    label: str = ""


class Workflow(BaseModel):
    id: str = Field(default_factory=lambda: f"wf_{uuid.uuid4().hex[:8]}")
    name: str
    description: str = ""
    enabled: bool = True
    nodes: list[WorkflowNode] = Field(default_factory=list)
    edges: list[WorkflowEdge] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_graph(self) -> "Workflow":
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("Workflow node IDs must be unique")

        known = set(node_ids)
        node_types = {node.id: node.type for node in self.nodes}
        if not any(node_type not in SUPPORT_TYPES for node_type in node_types.values()):
            raise ValueError("Workflow must contain at least one execution node")
        signatures: set[tuple[str, str, str, str]] = set()
        outgoing: dict[str, list[str]] = {node_id: [] for node_id in known}
        indegree = {node_id: 0 for node_id in known if node_types[node_id] not in SUPPORT_TYPES}

        for edge in self.edges:
            if edge.source not in known or edge.target not in known:
                raise ValueError(f"Edge {edge.id} references a missing node")
            if edge.source == edge.target:
                raise ValueError(f"Edge {edge.id} cannot connect a node to itself")
            signature = (edge.source, edge.target, edge.kind, edge.label)
            if signature in signatures:
                raise ValueError(f"Duplicate edge from {edge.source} to {edge.target}")
            signatures.add(signature)

            if edge.kind in SUPPORT_TYPES:
                support_endpoints = [endpoint for endpoint in (edge.source, edge.target) if node_types[endpoint] in SUPPORT_TYPES]
                if len(support_endpoints) != 1 or node_types[support_endpoints[0]] != edge.kind:
                    raise ValueError(f"{edge.kind} edge must connect one matching support node")
            elif node_types[edge.source] in SUPPORT_TYPES or node_types[edge.target] in SUPPORT_TYPES:
                raise ValueError("Support nodes must use tool, memory, or parser edges")
            else:
                outgoing[edge.source].append(edge.target)
                indegree[edge.target] += 1

        queue = [node_id for node_id, degree in indegree.items() if degree == 0]
        visited = 0
        while queue:
            current = queue.pop()
            visited += 1
            for target in outgoing[current]:
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue.append(target)
        if visited != len(indegree):
            raise ValueError("Workflow execution graph must not contain cycles")
        return self
