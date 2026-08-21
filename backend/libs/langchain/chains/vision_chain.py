from __future__ import annotations

import uuid
import logging
from collections.abc import Callable
from core.settings import settings
from libs.langchain.chains.main_chain import CreatorAnalysis, CreatorPipelineResult, InvalidSchemeError, create_diagram_workflow_pipeline
from libs.langchain.chains.chain_store import get_chain_store
from libs.langchain.chains.workflow_chain import GeneratedWorkflow
from libs.langchain.prompts.templates import VISION_WORKFLOW_PROMPT
from libs.langchain.provider import BaseAIProvider, MockAIProvider
from libs.models.workflow import Workflow, WorkflowNode, WorkflowEdge, Position


logger = logging.getLogger(__name__)


class VisionChain:
    def __init__(self, provider: BaseAIProvider | None = None):
        self.provider = provider or get_chain_store().provider

    async def analyze_diagram(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> Workflow:
        return (await self.analyze_diagram_with_review(image_bytes, mime_type)).workflow

    async def analyze_diagram_with_review(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        on_progress: Callable[[str], None] | None = None,
    ) -> CreatorPipelineResult:
        if not isinstance(self.provider, MockAIProvider):
            try:
                return await create_diagram_workflow_pipeline(self.provider).analyze_with_review(
                    image_bytes, mime_type, on_progress
                )
            except InvalidSchemeError:
                raise
            except Exception as exc:
                if not settings.use_mock_ai_fallback:
                    raise
                logger.warning("Real diagram pipeline failed; using explicit POC demo fallback: %s", exc)
                if on_progress:
                    on_progress("build_graph")
                workflow = await self._analyze_demo(image_bytes, mime_type)
                if on_progress:
                    on_progress("finalize_workflow")
                return CreatorPipelineResult(workflow=workflow, analysis=CreatorAnalysis(summary="POC demo workflow used after the configured vision pipeline failed."))
        if on_progress:
            on_progress("read_diagram")
        workflow = await self._analyze_demo(image_bytes, mime_type)
        if on_progress:
            on_progress("finalize_workflow")
        return CreatorPipelineResult(workflow=workflow, analysis=CreatorAnalysis(summary="POC demo workflow. Configure a vision model for image-specific review."))

    async def _analyze_demo(self, image_bytes: bytes, mime_type: str) -> Workflow:
        demo_provider = self.provider if isinstance(self.provider, MockAIProvider) else MockAIProvider()
        prompt = VISION_WORKFLOW_PROMPT
        generated: GeneratedWorkflow = await demo_provider.analyze_image(
            image_bytes=image_bytes,
            prompt=prompt,
            schema=GeneratedWorkflow,
            mime_type=mime_type,
        )

        nodes: list[WorkflowNode] = []
        node_id_map: dict[str, str] = {}

        for i, gn in enumerate(generated.nodes):
            real_id = gn.id or f"agent_{i+1}"
            node_id_map[gn.id] = real_id
            nodes.append(
                WorkflowNode(
                    id=real_id,
                    type=gn.type,
                    name=gn.name,
                    description=gn.description,
                    instructions=gn.instructions,
                    position=Position(x=0.0, y=float(i * 130)),
                )
            )

        edges: list[WorkflowEdge] = []
        if generated.edges:
            for ge in generated.edges:
                src = node_id_map.get(ge.source, ge.source)
                tgt = node_id_map.get(ge.target, ge.target)
                kind = ge.kind if ge.kind in {"flow", "conditional", "tool", "memory", "parser"} else "flow"
                edges.append(WorkflowEdge(source=src, target=tgt, kind=kind, label=ge.label))
        else:
            for i in range(len(nodes) - 1):
                edges.append(WorkflowEdge(source=nodes[i].id, target=nodes[i + 1].id))

        return Workflow(
            id=f"wf_{uuid.uuid4().hex[:8]}",
            name=generated.name or "Hand-Drawn Workflow",
            description=generated.description,
            nodes=nodes,
            edges=edges,
        )
