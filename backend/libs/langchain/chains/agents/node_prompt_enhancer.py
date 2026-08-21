from dataclasses import dataclass

from libs.langchain.prompts.agents.node_prompt_enhancer import NODE_PROMPT_ENHANCER_PROMPT
from libs.langchain.provider import BaseAIProvider
from libs.langchain.response_models.agents.node_prompt_enhancer import EnhancedNodePrompt


@dataclass(frozen=True)
class NodePromptEnhancerChain:
    provider: BaseAIProvider

    async def ainvoke(self, node_context: str) -> EnhancedNodePrompt:
        return await self.provider.generate_structured(node_context, EnhancedNodePrompt, NODE_PROMPT_ENHANCER_PROMPT)


def create_node_prompt_enhancer_chain(provider: BaseAIProvider) -> NodePromptEnhancerChain:
    return NodePromptEnhancerChain(provider)
