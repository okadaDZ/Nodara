from __future__ import annotations

from dataclasses import dataclass

from libs.langchain.prompts.agents import DIAGRAM_OBSERVER_PROMPT
from libs.langchain.provider import BaseAIProvider
from libs.langchain.response_models.agents import DiagramObservation


@dataclass(frozen=True)
class DiagramObserverChain:
    provider: BaseAIProvider

    async def ainvoke(self, image_bytes: bytes, mime_type: str) -> DiagramObservation:
        return await self.provider.analyze_image(
            image_bytes=image_bytes,
            mime_type=mime_type,
            prompt=DIAGRAM_OBSERVER_PROMPT,
            schema=DiagramObservation,
        )


def create_diagram_observer_chain(provider: BaseAIProvider) -> DiagramObserverChain:
    return DiagramObserverChain(provider)
