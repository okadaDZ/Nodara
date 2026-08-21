from typing import Optional
from app.ai.provider import BaseAIProvider, get_ai_provider
from app.models.workflow import Workflow, WorkflowNode


AGENT_INSTRUCTION_SYSTEM_PROMPT = """
You are an expert agent instruction architect for a mobile AI workflow app.
You write crystal-clear, structured instructions that guide an individual AI agent node in a sequential workflow.

Guidelines:
1. Explain the agent's core purpose in simple language.
2. Outline specific step-by-step guidance.
3. Specify what kind of output it must produce for the downstream agent.
4. Avoid exposing developer jargon like JSON schemas or temperature.
"""


class AgentGenerator:
    def __init__(self, provider: Optional[BaseAIProvider] = None):
        self.provider = provider or get_ai_provider()

    async def generate_instructions(
        self,
        workflow: Workflow,
        node: WorkflowNode,
        user_hint: Optional[str] = None,
    ) -> str:
        # Provide workflow context (previous agents, next agents)
        prev_nodes = []
        next_nodes = []
        for edge in workflow.edges:
            if edge.target == node.id:
                prev_nodes.append(edge.source)
            if edge.source == node.id:
                next_nodes.append(edge.target)

        node_map = {n.id: n.name for n in workflow.nodes}
        prev_names = [node_map.get(pid, pid) for pid in prev_nodes]
        next_names = [node_map.get(nid, nid) for nid in next_nodes]

        prompt = f"""
Workflow Goal: {workflow.name} - {workflow.description}
Agent Name: {node.name}
Agent Role: {node.description}
Preceding Agents: {", ".join(prev_names) if prev_names else "Initial Input"}
Subsequent Agents: {", ".join(next_names) if next_names else "Final Output"}
Additional User Guidance: {user_hint or "None specified"}

Write comprehensive yet concise instructions for what this agent should do when executed.
"""
        return await self.provider.generate_text(
            prompt=prompt, system_prompt=AGENT_INSTRUCTION_SYSTEM_PROMPT
        )

    async def improve_instructions(
        self,
        current_instructions: str,
        user_feedback: Optional[str] = None,
    ) -> str:
        prompt = f"""
Current Agent Instructions:
{current_instructions}

User Feedback / Request:
{user_feedback or "Make the instructions clearer, more reliable, and structured."}

Return the refined, improved instructions.
"""
        return await self.provider.generate_text(
            prompt=prompt, system_prompt=AGENT_INSTRUCTION_SYSTEM_PROMPT
        )

    async def apply_audio_edit(
        self,
        current_instructions: str,
        transcription: str,
    ) -> str:
        prompt = f"""
Current Agent Instructions:
{current_instructions}

User's Spoken Modification:
"{transcription}"

Update the agent instructions to seamlessly incorporate the user's spoken change while keeping existing functionality intact.
"""
        return await self.provider.generate_text(
            prompt=prompt, system_prompt=AGENT_INSTRUCTION_SYSTEM_PROMPT
        )
