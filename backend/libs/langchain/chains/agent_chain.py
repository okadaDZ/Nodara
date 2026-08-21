from __future__ import annotations

from libs.langchain.prompts.templates import AGENT_INSTRUCTION_PROMPT
from libs.langchain.provider import BaseAIProvider, get_ai_provider
from libs.models.workflow import Workflow, WorkflowNode


class AgentChain:
    def __init__(self, provider: BaseAIProvider | None = None):
        self.provider = provider or get_ai_provider()

    async def generate_instructions(
        self,
        workflow: Workflow,
        node: WorkflowNode,
        user_hint: str = "",
    ) -> str:
        prev_nodes = [e.source for e in workflow.edges if e.target == node.id]
        next_nodes = [e.target for e in workflow.edges if e.source == node.id]

        node_map = {n.id: n.name for n in workflow.nodes}
        prev_names = [node_map.get(pid, pid) for pid in prev_nodes]
        next_names = [node_map.get(nid, nid) for nid in next_nodes]

        prompt = f"""
Workflow Objective: {workflow.name} - {workflow.description}
Agent: {node.name}
Role / Description: {node.description}
Preceding Agents: {", ".join(prev_names) if prev_names else "Initial User Input"}
Downstream Agents: {", ".join(next_names) if next_names else "Final Output"}
User Hint: {user_hint or "None"}

Write clear, structured execution instructions for this agent.
"""
        return await self.provider.generate_text(
            prompt=prompt, system_prompt=AGENT_INSTRUCTION_PROMPT
        )

    async def improve_instructions(
        self,
        current_instructions: str,
        user_feedback: str = "",
    ) -> str:
        prompt = f"""
Current Instructions:
{current_instructions}

User Feedback:
{user_feedback or "Make them clearer, more structured, and highly reliable."}

Return the refined instructions.
"""
        return await self.provider.generate_text(
            prompt=prompt, system_prompt=AGENT_INSTRUCTION_PROMPT
        )
