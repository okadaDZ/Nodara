from __future__ import annotations

import pytest

from libs.langchain.chains.main_chain import InvalidSchemeError, create_diagram_workflow_pipeline, workflow_from_draft
from libs.langchain.chains.base_chain import create_image_formated_prompt
from libs.langchain.prompts.agents import DIAGRAM_OBSERVER_PROMPT, NODE_PROMPT_ENGINEER_PROMPT, WORKFLOW_ARCHITECT_PROMPT, WORKFLOW_REVIEWER_PROMPT
from libs.langchain.provider import BaseAIProvider
from libs.langchain.response_models.agents import (
    DiagramEdgeEvidence,
    DiagramNodeEvidence,
    DiagramObservation,
    WorkflowDraft,
    WorkflowDraftEdge,
    WorkflowDraftNode,
    WorkflowReview,
    SchemeClassification,
    WorkflowLogicReview,
    NodePromptDraft,
    WorkflowPromptReview,
    NodePromptEnhancement,
    EnhancedNodePrompt,
)
from libs.n8n.converter import workflow_to_n8n
from libs.models.workflow import Workflow, WorkflowEdge, WorkflowNode


def observation() -> DiagramObservation:
    return DiagramObservation(
        diagram_title="Launch flow",
        nodes=[
            DiagramNodeEvidence(ref="n1", visible_text="Start", shape="circle", node_type_hint="trigger", confidence=0.98),
            DiagramNodeEvidence(ref="n2", visible_text="Research", shape="rectangle", node_type_hint="agent", confidence=0.95),
            DiagramNodeEvidence(ref="n3", visible_text="Risk", shape="rectangle", node_type_hint="agent", confidence=0.94),
            DiagramNodeEvidence(ref="n4", visible_text="Draft", shape="rectangle", node_type_hint="output", confidence=0.96),
        ],
        edges=[
            DiagramEdgeEvidence(source_ref="n1", target_ref="n2", confidence=0.98),
            DiagramEdgeEvidence(source_ref="n1", target_ref="n3", confidence=0.98),
            DiagramEdgeEvidence(source_ref="n2", target_ref="n4", confidence=0.97),
            DiagramEdgeEvidence(source_ref="n3", target_ref="n4", confidence=0.97),
        ],
        confidence=0.95,
    )


def draft() -> WorkflowDraft:
    instructions = "INPUT: prior output. TASK: process the visible step. RULES: stay grounded. OUTPUT: concise result."
    return WorkflowDraft(
        name="Launch flow",
        description="Parallel research and risk workflow.",
        nodes=[
            WorkflowDraftNode(id="start", type="trigger", name="Start", instructions=instructions, source_ref="n1"),
            WorkflowDraftNode(id="research", type="agent", name="Research", instructions=instructions, source_ref="n2"),
            WorkflowDraftNode(id="risk", type="agent", name="Risk", instructions=instructions, source_ref="n3"),
            WorkflowDraftNode(id="draft", type="output", name="Draft", instructions=instructions, source_ref="n4"),
        ],
        edges=[
            WorkflowDraftEdge(source="start", target="research"),
            WorkflowDraftEdge(source="start", target="risk"),
            WorkflowDraftEdge(source="research", target="draft"),
            WorkflowDraftEdge(source="risk", target="draft"),
        ],
    )


class ScriptedProvider(BaseAIProvider):
    def __init__(self):
        self.calls: list[str] = []

    async def analyze_image(self, image_bytes, prompt, schema=None, mime_type="image/jpeg"):
        assert image_bytes == b"diagram"
        if schema is SchemeClassification:
            self.calls.append("classifier")
            return SchemeClassification(is_workflow_scheme=True, confidence=0.99, reason="Visible connected nodes", user_message="Workflow detected")
        self.calls.append("observer")
        assert "Do not design agents" in prompt
        return observation()

    async def generate_structured(self, prompt, schema, system_prompt=None):
        if schema is WorkflowDraft:
            self.calls.append("architect")
            assert "diagram_observation" in prompt
            return draft()
        if schema is WorkflowReview:
            self.calls.append("reviewer")
            assert "workflow_draft" in prompt
            return WorkflowReview(workflow=draft(), corrections=[], requires_user_review=False, confidence=0.95)
        if schema is WorkflowLogicReview:
            self.calls.append("logic")
            return WorkflowLogicReview(workflow=draft(), is_logical=True, requires_redraw=False, requires_user_decision=False, summary="Logical workflow", confidence=0.96)
        if schema is NodePromptDraft:
            self.calls.append("prompt_engineer")
            node_id = next(node.id for node in draft().nodes if f'"id": "{node.id}"' in prompt)
            return NodePromptDraft(node_id=node_id, instructions="INPUT: upstream. TASK: execute role. RULES: do not invent. OUTPUT: structured result.")
        if schema is WorkflowPromptReview:
            self.calls.append("prompt_reviewer")
            return WorkflowPromptReview(enhancements=[NodePromptEnhancement(node_id=node.id, improvements=[]) for node in draft().nodes])
        if schema is EnhancedNodePrompt:
            self.calls.append("prompt_enhancer")
            node_id = next(node.id for node in draft().nodes if f'"id": "{node.id}"' in prompt)
            return EnhancedNodePrompt(node_id=node_id, instructions="INPUT: upstream. TASK: execute role. RULES: do not invent. OUTPUT: structured result.")
        raise AssertionError(f"Unexpected schema {schema}")

    async def generate_text(self, prompt, system_prompt=None, model_name=None):
        raise NotImplementedError

    async def transcribe_audio(self, audio_bytes, filename="recording.m4a", mime_type="audio/m4a"):
        raise NotImplementedError


@pytest.mark.asyncio
async def test_diagram_pipeline_decomposes_observe_architect_review():
    provider = ScriptedProvider()
    workflow = await create_diagram_workflow_pipeline(provider).ainvoke(b"diagram", "image/jpeg")
    assert provider.calls[:5] == ["classifier", "observer", "architect", "reviewer", "logic"]
    assert provider.calls.count("prompt_engineer") == 4
    assert provider.calls.count("prompt_reviewer") == 1
    assert provider.calls.count("prompt_enhancer") == 4
    assert len(workflow.nodes) == 4
    assert {(edge.source, edge.target) for edge in workflow.edges} == {
        ("start", "research"), ("start", "risk"), ("research", "draft"), ("risk", "draft")
    }


@pytest.mark.asyncio
async def test_diagram_pipeline_rejects_non_scheme_before_extraction():
    provider = ScriptedProvider()

    async def reject_image(image_bytes, prompt, schema=None, mime_type="image/jpeg"):
        return SchemeClassification(
            is_workflow_scheme=False,
            confidence=0.99,
            reason="No connected process elements",
            user_message="Use a photo with boxes and connecting arrows.",
        )

    provider.analyze_image = reject_image  # type: ignore[method-assign]
    with pytest.raises(InvalidSchemeError, match="boxes and connecting arrows"):
        await create_diagram_workflow_pipeline(provider).ainvoke(b"not-a-scheme", "image/jpeg")
    assert provider.calls == []


def test_deterministic_gate_removes_cycles_dangling_and_duplicate_edges():
    unsafe = draft().model_copy(deep=True)
    unsafe.edges.extend([
        WorkflowDraftEdge(source="draft", target="start"),
        WorkflowDraftEdge(source="missing", target="draft"),
        WorkflowDraftEdge(source="start", target="risk"),
    ])
    workflow = workflow_from_draft(unsafe)
    assert len(workflow.edges) == 4
    assert not any(edge.source == "draft" and edge.target == "start" for edge in workflow.edges)


def test_prompts_are_decomposed_and_small_model_explicit():
    assert "Do not design agents" in DIAGRAM_OBSERVER_PROMPT
    assert "INPUT, TASK, RULES, and OUTPUT" in NODE_PROMPT_ENGINEER_PROMPT
    assert "directed acyclic graph" in WORKFLOW_REVIEWER_PROMPT


def test_image_prompt_uses_falcon_eye_multimodal_message_shape():
    message = create_image_formated_prompt("read diagram", "image/jpeg").format_messages(base64_image="YWJj")[0]
    assert message.content[0] == {"type": "text", "text": "read diagram"}
    assert message.content[1]["image_url"]["url"] == "data:image/jpeg;base64,YWJj"


def test_n8n_export_preserves_parallel_roots_and_omits_support_as_agents():
    workflow = workflow_from_draft(draft())
    # Deliberately unattached here: export must not turn support config into an AI Agent.
    workflow.nodes.append(WorkflowNode(id="memory", type="memory", name="Memory"))
    exported = workflow_to_n8n(workflow)
    names = {node["name"] for node in exported["nodes"]}
    assert "Start" not in names
    assert "Memory" not in names
    set_targets = exported["connections"]["Set Input"]["main"][0]
    assert {target["node"] for target in set_targets} == {"Research", "Risk"}


def test_n8n_export_positions_parallel_branches_in_one_stage_and_join_in_next_stage():
    workflow = Workflow(
        name="RSS to Slack summary",
        nodes=[
            WorkflowNode(id="rss_x", name="RSS X"),
            WorkflowNode(id="rss_youtube", name="RSS YouTube"),
            WorkflowNode(id="rss_web", name="RSS Web XML"),
            WorkflowNode(id="normalize", name="Open AI"),
            WorkflowNode(id="summary", name="Summarize Report"),
            WorkflowNode(id="slack", type="output", name="Slack Channel"),
        ],
        edges=[
            WorkflowEdge(source="rss_x", target="normalize"),
            WorkflowEdge(source="rss_youtube", target="normalize"),
            WorkflowEdge(source="rss_web", target="normalize"),
            WorkflowEdge(source="normalize", target="summary"),
            WorkflowEdge(source="summary", target="slack"),
        ],
    )

    exported = workflow_to_n8n(workflow)
    node_by_name = {node["name"]: node for node in exported["nodes"]}
    rss_positions = [node_by_name[name]["position"] for name in ("RSS X", "RSS YouTube", "RSS Web XML")]

    assert len({position[0] for position in rss_positions}) == 1
    assert len({position[1] for position in rss_positions}) == 3
    assert node_by_name["Open AI"]["position"][0] > rss_positions[0][0]
    assert node_by_name["Open AI"]["position"][1] == node_by_name["Set Input"]["position"][1]
    assert {
        connection["node"]
        for connection in exported["connections"]["Set Input"]["main"][0]
    } == {"RSS X", "RSS YouTube", "RSS Web XML"}
    for source in ("RSS X", "RSS YouTube", "RSS Web XML"):
        assert exported["connections"][source]["main"][0][0]["node"] == "Open AI"


def test_n8n_export_turns_rss_sources_into_newsapi_http_requests_without_models():
    workflow = Workflow(
        name="External news search",
        nodes=[
            WorkflowNode(id="rss", name="RSS Web XML", description="Fetch recent company news"),
            WorkflowNode(id="summary", name="Summarize Report"),
        ],
        edges=[WorkflowEdge(source="rss", target="summary")],
    )

    exported = workflow_to_n8n(workflow)
    rss = next(node for node in exported["nodes"] if node["name"] == "RSS Web XML")
    assert rss["type"] == "n8n-nodes-base.httpRequest"
    assert rss["parameters"]["url"] == "https://newsapi.org/v2/everything"
    query = {item["name"]: item["value"] for item in rss["parameters"]["queryParameters"]["parameters"]}
    assert query["searchIn"] == "title,description"
    assert query["sortBy"] == "relevancy"
    headers = {item["name"]: item["value"] for item in rss["parameters"]["headerParameters"]["parameters"]}
    assert headers["X-Api-Key"] == "={{ $env.NEWS_API_KEY }}"
    assert not any(node["name"] == "OpenAI Chat Model (RSS Web XML)" for node in exported["nodes"])
    assert exported["connections"]["Set Input"]["main"][0][0]["node"] == "RSS Web XML"


def test_n8n_export_uses_each_agents_selected_model():
    workflow = workflow_from_draft(draft())
    next(node for node in workflow.nodes if node.id == "research").model = "model-for-research"
    exported = workflow_to_n8n(workflow)
    model_node = next(node for node in exported["nodes"] if node["name"] == "OpenAI Chat Model (Research)")
    assert model_node["parameters"]["model"] == "model-for-research"


def test_n8n_export_turns_condition_branches_into_switch_outputs():
    conditional = WorkflowDraft(
        name="Approval",
        nodes=[
            WorkflowDraftNode(id="review", type="condition", name="Approved?"),
            WorkflowDraftNode(id="publish", type="output", name="Publish"),
            WorkflowDraftNode(id="revise", type="action", name="Revise"),
        ],
        edges=[
            WorkflowDraftEdge(source="review", target="publish", kind="conditional", label="yes"),
            WorkflowDraftEdge(source="review", target="revise", kind="conditional", label="no"),
        ],
    )
    exported = workflow_to_n8n(workflow_from_draft(conditional))
    switch = next(node for node in exported["nodes"] if node["type"] == "n8n-nodes-base.switch")
    outputs = exported["connections"][switch["name"]]["main"]
    assert outputs[0][0]["node"] == "Publish"
    assert outputs[1][0]["node"] == "Revise"
