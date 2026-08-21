from __future__ import annotations

from functools import lru_cache

from libs.langchain.chains.main_chain import DiagramWorkflowPipeline, create_diagram_workflow_pipeline
from libs.langchain.provider import BaseAIProvider, get_ai_provider


class ChainStore:
    """Single registry for configured providers and composed chains."""

    def __init__(self, provider: BaseAIProvider | None = None):
        self.provider = provider or get_ai_provider()
        self.diagram_workflow_pipeline: DiagramWorkflowPipeline = create_diagram_workflow_pipeline(self.provider)


@lru_cache
def get_chain_store() -> ChainStore:
    return ChainStore()
