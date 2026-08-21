from dataclasses import dataclass

from libs.langchain.prompts.agents.scheme_classifier import SCHEME_CLASSIFIER_PROMPT
from libs.langchain.provider import BaseAIProvider
from libs.langchain.response_models.agents.scheme_classifier import SchemeClassification


@dataclass(frozen=True)
class SchemeClassifierChain:
    provider: BaseAIProvider

    async def ainvoke(self, image_bytes: bytes, mime_type: str) -> SchemeClassification:
        return await self.provider.analyze_image(image_bytes, SCHEME_CLASSIFIER_PROMPT, SchemeClassification, mime_type)


def create_scheme_classifier_chain(provider: BaseAIProvider) -> SchemeClassifierChain:
    return SchemeClassifierChain(provider)
