from dataclasses import dataclass

from libs.langchain.prompts.agents.workflow_prompt_reviewer import WORKFLOW_PROMPT_REVIEWER_PROMPT
from libs.langchain.provider import BaseAIProvider
from libs.langchain.response_models.agents.workflow_prompt_reviewer import WorkflowPromptReview


@dataclass(frozen=True)
class WorkflowPromptReviewerChain:
    provider: BaseAIProvider

    async def ainvoke(self, workflow_context: str) -> WorkflowPromptReview:
        return await self.provider.generate_structured(workflow_context, WorkflowPromptReview, WORKFLOW_PROMPT_REVIEWER_PROMPT)


def create_workflow_prompt_reviewer_chain(provider: BaseAIProvider) -> WorkflowPromptReviewerChain:
    return WorkflowPromptReviewerChain(provider)
