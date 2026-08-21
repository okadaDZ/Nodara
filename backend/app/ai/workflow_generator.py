import uuid
from typing import List, Optional
from pydantic import BaseModel, Field
from app.ai.provider import BaseAIProvider, get_ai_provider
from app.models.workflow import Workflow, WorkflowNode, WorkflowEdge, Position


class GeneratedNode(BaseModel):
    id: str = Field(description="Unique node identifier, e.g. agent_1, agent_2")
    name: str = Field(description="Short human-friendly agent title, e.g. Researcher, Summarizer, Writer")
    description: str = Field(default="", description="1-sentence explanation of what this agent does")
    instructions: str = Field(default="", description="Detailed instructions for what the agent should execute")


class GeneratedEdge(BaseModel):
    source: str = Field(description="Node ID of source agent")
    target: str = Field(description="Node ID of target agent")


class GeneratedWorkflowSchema(BaseModel):
    name: str = Field(description="Concise workflow title")
    description: str = Field(default="", description="Summary of the overall workflow objective")
    nodes: List[GeneratedNode] = Field(description="List of agent nodes in execution order")
    edges: List[GeneratedEdge] = Field(description="List of directed connections from one agent to the next")


WORKFLOW_TEXT_SYSTEM_PROMPT = """
You are an expert AI workflow designer for a mobile application.
The user will provide an everyday natural language description of an objective they want AI agents to achieve.

Your job:
1. Convert their description into a clean, simple directed sequence of AI agents.
2. Create one agent for each distinct responsibility (e.g. Researcher, Synthesizer, Writer, Reviewer).
3. Use simple, human-readable names for agents (avoid technical jargon like "LLM Parser", "Embedding Engine", etc.).
4. Formulate clear initial instructions for each agent.
5. Define directed edges connecting the agents in sequential order (source agent -> target agent).

Return only valid structured data according to the schema.
"""


class WorkflowGenerator:
    def __init__(self, provider: Optional[BaseAIProvider] = None):
        self.provider = provider or get_ai_provider()

    async def from_text(self, text: str) -> Workflow:
        prompt = f"User request:\n{text.strip()}\n\nGenerate the complete agent workflow."
        generated: GeneratedWorkflowSchema = await self.provider.generate_structured(
            prompt=prompt,
            schema=GeneratedWorkflowSchema,
            system_prompt=WORKFLOW_TEXT_SYSTEM_PROMPT,
        )

        nodes: List[WorkflowNode] = []
        node_id_map = {}

        # Create canonical WorkflowNodes
        for i, gn in enumerate(generated.nodes):
            real_id = gn.id if gn.id else f"agent_{i+1}"
            node_id_map[gn.id] = real_id
            nodes.append(
                WorkflowNode(
                    id=real_id,
                    type="agent",
                    name=gn.name,
                    description=gn.description,
                    instructions=gn.instructions,
                    position=Position(x=0.0, y=float(i * 120)),
                )
            )

        # Create canonical WorkflowEdges
        edges: List[WorkflowEdge] = []
        if generated.edges:
            for ge in generated.edges:
                src = node_id_map.get(ge.source, ge.source)
                tgt = node_id_map.get(ge.target, ge.target)
                edges.append(WorkflowEdge(source=src, target=tgt))
        else:
            # Fallback linear connection if no edges returned
            for i in range(len(nodes) - 1):
                edges.append(WorkflowEdge(source=nodes[i].id, target=nodes[i + 1].id))

        return Workflow(
            id=f"wf_{uuid.uuid4().hex[:8]}",
            name=generated.name or "New Agent Workflow",
            description=generated.description,
            nodes=nodes,
            edges=edges,
        )
