from dataclasses import dataclass

from libs.langchain.prompts.agents.workflow_logic_validator import WORKFLOW_LOGIC_VALIDATOR_PROMPT
from libs.langchain.provider import BaseAIProvider
from libs.langchain.response_models.agents import DiagramObservation, WorkflowDraft
from libs.langchain.response_models.agents.workflow_logic_validator import WorkflowLogicReview


@dataclass(frozen=True)
class WorkflowLogicValidatorChain:
    provider: BaseAIProvider

    async def ainvoke(self, observation: DiagramObservation, workflow: WorkflowDraft) -> WorkflowLogicReview:
        prompt = f"<diagram_observation>\n{observation.model_dump_json(indent=2)}\n</diagram_observation>\n<workflow>\n{workflow.model_dump_json(indent=2)}\n</workflow>"
        return await self.provider.generate_structured(prompt, WorkflowLogicReview, WORKFLOW_LOGIC_VALIDATOR_PROMPT)


def create_workflow_logic_validator_chain(provider: BaseAIProvider) -> WorkflowLogicValidatorChain:
    return WorkflowLogicValidatorChain(provider)
