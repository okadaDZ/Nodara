from __future__ import annotations

import logging
import re
import uuid
import asyncio
from collections.abc import Callable

from pydantic import BaseModel, Field

from libs.langchain.chains.agents import (
    create_diagram_observer_chain,
    create_workflow_architect_chain,
    create_workflow_reviewer_chain,
    create_scheme_classifier_chain,
    create_workflow_logic_validator_chain,
    create_node_prompt_engineer_chain,
    create_workflow_prompt_reviewer_chain,
    create_node_prompt_enhancer_chain,
)
from libs.langchain.provider import BaseAIProvider
from libs.langchain.langfuse_client import trace_scope
from libs.langchain.response_models.agents import WorkflowDraft, WorkflowLogicReview, WorkflowRecommendation
from libs.models.workflow import Position, Workflow, WorkflowEdge, WorkflowNode

logger = logging.getLogger(__name__)

SUPPORT_TYPES = {"tool", "memory", "parser"}
NODE_TYPES = {"trigger", "query_builder", "agent", "condition", "action", "output", *SUPPORT_TYPES}
EDGE_KINDS = {"flow", "conditional", *SUPPORT_TYPES}


class InvalidSchemeError(ValueError):
    pass


class CreatorAnalysis(BaseModel):
    summary: str = ""
    confidence: float = 0
    requires_redraw: bool = False
    requires_user_decision: bool = False
    recommendations: list[WorkflowRecommendation] = Field(default_factory=list)


class CreatorPipelineResult(BaseModel):
    workflow: Workflow
    analysis: CreatorAnalysis


def _slug(value: str, fallback: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return result or fallback


def _would_cycle(edges: list[WorkflowEdge], source: str, target: str) -> bool:
    outgoing: dict[str, list[str]] = {}
    for edge in edges:
        if edge.kind in {"flow", "conditional"}:
            outgoing.setdefault(edge.source, []).append(edge.target)
    pending = [target]
    seen: set[str] = set()
    while pending:
        current = pending.pop()
        if current == source:
            return True
        if current in seen:
            continue
        seen.add(current)
        pending.extend(outgoing.get(current, []))
    return False


def workflow_from_draft(draft: WorkflowDraft) -> Workflow:
    """Deterministic safety gate after probabilistic extraction and review."""
    nodes: list[WorkflowNode] = []
    used_ids: set[str] = set()
    id_map: dict[str, str] = {}
    for index, candidate in enumerate(draft.nodes):
        base_id = _slug(candidate.id or candidate.name, f"node_{index + 1}")
        node_id = base_id
        suffix = 2
        while node_id in used_ids:
            node_id = f"{base_id}_{suffix}"
            suffix += 1
        used_ids.add(node_id)
        id_map.setdefault(candidate.id, node_id)
        nodes.append(
            WorkflowNode(
                id=node_id,
                type=candidate.type if candidate.type in NODE_TYPES else "agent",
                name=candidate.name.strip() or f"Step {index + 1}",
                description=candidate.description.strip(),
                instructions=candidate.instructions.strip(),
                position=Position(x=0, y=index * 130),
            )
        )

    if not any(node.type not in SUPPORT_TYPES for node in nodes):
        raise ValueError("The diagram did not contain an executable workflow node")

    node_types = {node.id: node.type for node in nodes}
    edges: list[WorkflowEdge] = []
    signatures: set[tuple[str, str, str, str]] = set()
    for candidate in draft.edges:
        source = id_map.get(candidate.source, _slug(candidate.source, ""))
        target = id_map.get(candidate.target, _slug(candidate.target, ""))
        if source not in node_types or target not in node_types or source == target:
            continue
        kind = candidate.kind if candidate.kind in EDGE_KINDS else "flow"
        source_support = node_types[source] in SUPPORT_TYPES
        target_support = node_types[target] in SUPPORT_TYPES
        if source_support or target_support:
            if source_support == target_support:
                continue
            support_id = source if source_support else target
            kind = node_types[support_id]
        elif kind in SUPPORT_TYPES:
            continue
        signature = (source, target, kind, candidate.label.strip())
        if signature in signatures:
            continue
        edge = WorkflowEdge(
            id=f"edge_{uuid.uuid4().hex[:8]}",
            source=source,
            target=target,
            kind=kind,
            label=candidate.label.strip(),
        )
        if kind in {"flow", "conditional"} and _would_cycle(edges, source, target):
            logger.warning("Removed cyclic draft edge %s -> %s", source, target)
            continue
        signatures.add(signature)
        edges.append(edge)

    return Workflow(
        id=f"wf_{uuid.uuid4().hex[:8]}",
        name=draft.name.strip() or "Hand-Drawn Workflow",
        description=draft.description.strip() or "Workflow extracted from a hand-drawn diagram",
        nodes=nodes,
        edges=edges,
    )


class DiagramWorkflowPipeline:
    def __init__(self, provider: BaseAIProvider):
        self.observer = create_diagram_observer_chain(provider)
        self.architect = create_workflow_architect_chain(provider)
        self.reviewer = create_workflow_reviewer_chain(provider)
        self.classifier = create_scheme_classifier_chain(provider)
        self.logic_validator = create_workflow_logic_validator_chain(provider)
        self.prompt_engineer = create_node_prompt_engineer_chain(provider)
        self.prompt_reviewer = create_workflow_prompt_reviewer_chain(provider)
        self.prompt_enhancer = create_node_prompt_enhancer_chain(provider)

    @staticmethod
    def _node_context(draft: WorkflowDraft, node_id: str) -> str:
        node = next(node for node in draft.nodes if node.id == node_id)
        predecessors = [edge.source for edge in draft.edges if edge.target == node_id]
        successors = [{"node_id": edge.target, "label": edge.label} for edge in draft.edges if edge.source == node_id]
        return (
            f"<workflow_name>{draft.name}</workflow_name>\n"
            f"<node>{node.model_dump_json(indent=2)}</node>\n"
            f"<predecessor_ids>{predecessors}</predecessor_ids>\n"
            f"<successors>{successors}</successors>"
        )

    async def _write_and_review_prompts(
        self,
        draft: WorkflowDraft,
        on_progress: Callable[[str], None] | None = None,
    ) -> WorkflowDraft:
        execution_nodes = [node for node in draft.nodes if node.type not in SUPPORT_TYPES]
        try:
            if on_progress:
                on_progress("write_prompts")
            prompt_drafts = await asyncio.gather(*[
                self.prompt_engineer.ainvoke(self._node_context(draft, node.id))
                for node in execution_nodes
            ])
            prompt_by_id = {item.node_id: item.instructions for item in prompt_drafts}
            for node in draft.nodes:
                if node.id in prompt_by_id:
                    node.instructions = prompt_by_id[node.id]

            if on_progress:
                on_progress("review_prompts")
            review = await self.prompt_reviewer.ainvoke(
                f"<workflow>\n{draft.model_dump_json(indent=2)}\n</workflow>"
            )
            improvements = {item.node_id: item.improvements for item in review.enhancements}
            if on_progress:
                on_progress("enhance_prompts")
            enhanced = await asyncio.gather(*[
                self.prompt_enhancer.ainvoke(
                    self._node_context(draft, node.id)
                    + f"\n<current_prompt>{node.instructions}</current_prompt>"
                    + f"\n<reviewed_improvements>{improvements.get(node.id, [])}</reviewed_improvements>"
                )
                for node in execution_nodes
            ])
            final_by_id = {item.node_id: item.instructions for item in enhanced}
            for node in draft.nodes:
                if node.id in final_by_id:
                    node.instructions = final_by_id[node.id]
        except Exception as exc:
            logger.warning("Prompt production stage failed; retaining grounded architect prompts: %s", exc)
        return draft

    async def analyze_with_review(
        self,
        image_bytes: bytes,
        mime_type: str,
        on_progress: Callable[[str], None] | None = None,
    ) -> CreatorPipelineResult:
        with trace_scope(
            "workflow.create-from-diagram",
            input={"mime_type": mime_type, "image_bytes": len(image_bytes)},
            tags=["workflow-creation", "vision"],
            metadata={"source": "diagram"},
            as_type="agent",
        ) as trace:
            if on_progress:
                on_progress("validate_image")
            classification = await self.classifier.ainvoke(image_bytes, mime_type)
            if not classification.is_workflow_scheme:
                raise InvalidSchemeError(classification.user_message)

            if on_progress:
                on_progress("read_diagram")
            observation = await self.observer.ainvoke(image_bytes, mime_type)
            if not observation.nodes:
                raise ValueError("No workflow nodes were visible in the image")
            if on_progress:
                on_progress("build_graph")
            draft = await self.architect.ainvoke(observation)
            try:
                if on_progress:
                    on_progress("review_structure")
                review = await self.reviewer.ainvoke(observation, draft)
                final_draft = review.workflow
            except Exception as exc:
                logger.warning("Workflow reviewer failed; applying deterministic validation to architect draft: %s", exc)
                final_draft = draft
            try:
                if on_progress:
                    on_progress("validate_logic")
                logic_review = await self.logic_validator.ainvoke(observation, final_draft)
            except Exception as exc:
                logger.warning("Logic review failed; continuing with structural review: %s", exc)
                logic_review = WorkflowLogicReview(
                    workflow=final_draft,
                    is_logical=True,
                    summary="The workflow structure was extracted. Logic recommendations were unavailable.",
                    confidence=observation.confidence,
                    requires_redraw=False,
                    requires_user_decision=False,
                )
            prompted_draft = await self._write_and_review_prompts(logic_review.workflow, on_progress)
            if on_progress:
                on_progress("finalize_workflow")
            result = CreatorPipelineResult(
                workflow=workflow_from_draft(prompted_draft),
                analysis=CreatorAnalysis(
                    summary=logic_review.summary,
                    confidence=logic_review.confidence,
                    requires_redraw=logic_review.requires_redraw,
                    requires_user_decision=logic_review.requires_user_decision,
                    recommendations=logic_review.recommendations,
                ),
            )
            trace.update(output={
                "workflow_id": result.workflow.id,
                "node_count": len(result.workflow.nodes),
                "edge_count": len(result.workflow.edges),
                "confidence": result.analysis.confidence,
            })
            return result

    async def ainvoke(self, image_bytes: bytes, mime_type: str) -> Workflow:
        return (await self.analyze_with_review(image_bytes, mime_type)).workflow


def create_diagram_workflow_pipeline(provider: BaseAIProvider) -> DiagramWorkflowPipeline:
    return DiagramWorkflowPipeline(provider)


async def enrich_workflow_prompts(provider: BaseAIProvider, workflow: Workflow) -> Workflow:
    """Run the per-node engineer, whole-graph reviewer, and per-node enhancer on an existing workflow."""
    draft = WorkflowDraft(
        name=workflow.name,
        description=workflow.description,
        nodes=[
            {
                "id": node.id,
                "type": node.type,
                "name": node.name,
                "description": node.description,
                "instructions": node.instructions,
            }
            for node in workflow.nodes
        ],
        edges=[
            {"source": edge.source, "target": edge.target, "kind": edge.kind, "label": edge.label}
            for edge in workflow.edges
        ],
    )
    prompted = await DiagramWorkflowPipeline(provider)._write_and_review_prompts(draft)
    instructions = {node.id: node.instructions for node in prompted.nodes}
    return workflow.model_copy(
        update={
            "nodes": [
                node.model_copy(update={"instructions": instructions.get(node.id, node.instructions)})
                for node in workflow.nodes
            ]
        }
    )
