from dataclasses import dataclass

from libs.langchain.prompts.agents.node_prompt_engineer import NODE_PROMPT_ENGINEER_PROMPT
from libs.langchain.provider import BaseAIProvider
from libs.langchain.response_models.agents.node_prompt_engineer import NodePromptDraft


@dataclass(frozen=True)
class NodePromptEngineerChain:
    provider: BaseAIProvider

    async def ainvoke(self, node_context: str) -> NodePromptDraft:
        return await self.provider.generate_structured(node_context, NodePromptDraft, NODE_PROMPT_ENGINEER_PROMPT)


def create_node_prompt_engineer_chain(provider: BaseAIProvider) -> NodePromptEngineerChain:
    return NodePromptEngineerChain(provider)
