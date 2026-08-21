from __future__ import annotations

from dataclasses import dataclass

from libs.langchain.prompts.agents import WORKFLOW_ARCHITECT_PROMPT
from libs.langchain.provider import BaseAIProvider
from libs.langchain.response_models.agents import DiagramObservation, WorkflowDraft


@dataclass(frozen=True)
class WorkflowArchitectChain:
    provider: BaseAIProvider

    async def ainvoke(self, observation: DiagramObservation) -> WorkflowDraft:
        prompt = "<diagram_observation>\n" + observation.model_dump_json(indent=2) + "\n</diagram_observation>"
        return await self.provider.generate_structured(
            prompt=prompt,
            schema=WorkflowDraft,
            system_prompt=WORKFLOW_ARCHITECT_PROMPT,
        )


def create_workflow_architect_chain(provider: BaseAIProvider) -> WorkflowArchitectChain:
    return WorkflowArchitectChain(provider)
