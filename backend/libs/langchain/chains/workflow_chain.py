from __future__ import annotations

import uuid
from pydantic import BaseModel, Field
from libs.langchain.prompts.templates import WORKFLOW_GENERATOR_PROMPT, WORKFLOW_AI_EDIT_PROMPT
from libs.langchain.provider import BaseAIProvider, get_ai_provider
from libs.langchain.langfuse_client import trace_scope
from libs.models.workflow import Workflow, WorkflowNode, WorkflowEdge, Position


class GeneratedNode(BaseModel):
    id: str = Field(description="Unique node id, e.g. agent_1")
    name: str = Field(description="Agent title, e.g. Researcher, Summarizer, Writer")
    description: str = Field(default="", description="Short role explanation")
    instructions: str = Field(default="", description="Actionable execution instructions")
    type: str = Field(default="agent", description="Node type: trigger, query_builder, agent, condition, action, output, tool, memory, or parser")


class GeneratedEdge(BaseModel):
    source: str = Field(description="Source agent id")
    target: str = Field(description="Target agent id")
    kind: str = Field(default="flow", description="Edge kind: flow, conditional, tool, memory, or parser")
    label: str = Field(default="", description="Short branch or connection label")


class GeneratedWorkflow(BaseModel):
    name: str = Field(description="Workflow title")
    description: str = Field(default="", description="Workflow summary")
    nodes: list[GeneratedNode] = Field(description="List of agent nodes")
    edges: list[GeneratedEdge] = Field(description="Directed edges")


class WorkflowChain:
    def __init__(self, provider: BaseAIProvider | None = None):
        self.provider = provider or get_ai_provider()

    async def generate_from_text(self, text: str) -> Workflow:
        with trace_scope(
            "workflow.create-from-text",
            input={"request": text.strip()},
            tags=["workflow-creation", "text"],
            metadata={"source": "text"},
            as_type="agent",
        ) as trace:
            prompt = f"User Request:\n{text.strip()}\n\nGenerate the complete agent workflow graph."
            generated = await self.provider.generate_structured(
                prompt=prompt,
                schema=GeneratedWorkflow,
                system_prompt=WORKFLOW_GENERATOR_PROMPT,
            )
            trace.update(output={
                "workflow_name": generated.name,
                "node_count": len(generated.nodes),
                "edge_count": len(generated.edges),
            })

        nodes: list[WorkflowNode] = []
        node_id_map: dict[str, str] = {}

        for i, gn in enumerate(generated.nodes):
            real_id = gn.id or f"agent_{i+1}"
            node_id_map[gn.id] = real_id
            nodes.append(
                WorkflowNode(
                    id=real_id,
                    type=gn.type,
                    name=gn.name,
                    description=gn.description,
                    instructions=gn.instructions,
                    position=Position(x=0.0, y=float(i * 130)),
                )
            )

        edges: list[WorkflowEdge] = []
        if generated.edges:
            for ge in generated.edges:
                src = node_id_map.get(ge.source, ge.source)
                tgt = node_id_map.get(ge.target, ge.target)
                kind = ge.kind if ge.kind in {"flow", "conditional", "tool", "memory", "parser"} else "flow"
                edges.append(WorkflowEdge(source=src, target=tgt, kind=kind, label=ge.label))
        else:
            for i in range(len(nodes) - 1):
                edges.append(WorkflowEdge(source=nodes[i].id, target=nodes[i + 1].id))

        workflow = Workflow(
            id=f"wf_{uuid.uuid4().hex[:8]}",
            name=generated.name or "New Workflow",
            description=generated.description,
            nodes=nodes,
            edges=edges,
        )
        return workflow

    async def edit_workflow(self, current_workflow: Workflow, instruction: str) -> Workflow:
        prompt = f"""
Existing Workflow:
{current_workflow.model_dump_json(indent=2)}

User Instruction:
{instruction.strip()}

Modify the workflow graph according to the user request.
"""
        updated = await self.provider.generate_structured(
            prompt=prompt,
            schema=GeneratedWorkflow,
            system_prompt=WORKFLOW_AI_EDIT_PROMPT,
        )

        nodes: list[WorkflowNode] = []
        node_id_map: dict[str, str] = {}
        for i, gn in enumerate(updated.nodes):
            real_id = gn.id or f"agent_{i+1}"
            node_id_map[gn.id] = real_id
            nodes.append(
                WorkflowNode(
                    id=real_id,
                    type=gn.type,
                    name=gn.name,
                    description=gn.description,
                    instructions=gn.instructions,
                    position=Position(x=0.0, y=float(i * 130)),
                )
            )

        edges: list[WorkflowEdge] = []
        for ge in updated.edges:
            src = node_id_map.get(ge.source, ge.source)
            tgt = node_id_map.get(ge.target, ge.target)
            kind = ge.kind if ge.kind in {"flow", "conditional", "tool", "memory", "parser"} else "flow"
            edges.append(WorkflowEdge(source=src, target=tgt, kind=kind, label=ge.label))

        return Workflow(
            id=current_workflow.id,
            name=updated.name or current_workflow.name,
            description=updated.description or current_workflow.description,
            enabled=current_workflow.enabled,
            nodes=nodes,
            edges=edges,
        )
