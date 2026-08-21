from __future__ import annotations

import logging
from pydantic import BaseModel
from libs.langchain.provider import BaseAIProvider, get_ai_provider
from libs.models.workflow import WorkflowNode

logger = logging.getLogger(__name__)


class AgentExecutionResult(BaseModel):
    success: bool
    output: str
    error: str | None = None


class AgentExecutor:
    def __init__(self, provider: BaseAIProvider | None = None):
        self.provider = provider or get_ai_provider()

    async def execute(
        self,
        node: WorkflowNode,
        original_input: str,
        previous_output: str | None = None,
    ) -> AgentExecutionResult:
        """Execute a single agent runnable given its instructions, initial input, and previous output."""
        system_prompt = f"""
You are the '{node.name}' AI Agent.
Role: {node.description}

Specific Execution Instructions:
{node.instructions or 'Analyze the input and provide high-quality output based on your role.'}
"""

        user_content = f"Initial Workflow Request: {original_input}"
        if previous_output:
            user_content += f"\n\nOutput from Preceding Agent:\n{previous_output}"

        try:
            output = await self.provider.generate_text(
                prompt=user_content, system_prompt=system_prompt, model_name=node.model
            )
            return AgentExecutionResult(success=True, output=output)
        except Exception as exc:
            logger.error("Error executing agent %s (%s): %s", node.name, node.id, exc, exc_info=True)
            return AgentExecutionResult(
                success=False,
                output="",
                error=f"Something went wrong while running the {node.name} agent: {str(exc)}",
            )
