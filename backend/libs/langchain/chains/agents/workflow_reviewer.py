from __future__ import annotations

from dataclasses import dataclass

from libs.langchain.prompts.agents import WORKFLOW_REVIEWER_PROMPT
from libs.langchain.provider import BaseAIProvider
from libs.langchain.response_models.agents import DiagramObservation, WorkflowDraft, WorkflowReview


@dataclass(frozen=True)
class WorkflowReviewerChain:
    provider: BaseAIProvider

    async def ainvoke(self, observation: DiagramObservation, draft: WorkflowDraft) -> WorkflowReview:
        prompt = (
            "<diagram_observation>\n" + observation.model_dump_json(indent=2) + "\n</diagram_observation>\n"
            "<workflow_draft>\n" + draft.model_dump_json(indent=2) + "\n</workflow_draft>"
        )
        return await self.provider.generate_structured(
            prompt=prompt,
            schema=WorkflowReview,
            system_prompt=WORKFLOW_REVIEWER_PROMPT,
        )


def create_workflow_reviewer_chain(provider: BaseAIProvider) -> WorkflowReviewerChain:
    return WorkflowReviewerChain(provider)
