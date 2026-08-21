from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from core.settings import settings
from libs.langchain.chains.main_chain import create_diagram_workflow_pipeline
from libs.langchain.provider import OpenAIProvider


FIXTURE = Path(__file__).parent / "fixtures" / "hand_drawn_parallel_quality_workflow.png"

EXPECTED_NODES = {
    "customer brief",
    "market research",
    "competitor research",
    "risk research",
    "synthesize findings",
    "evidence complete",
    "human review",
    "write launch plan",
    "publish report",
}

EXPECTED_EDGES = {
    ("customer brief", "market research"),
    ("customer brief", "competitor research"),
    ("customer brief", "risk research"),
    ("market research", "synthesize findings"),
    ("competitor research", "synthesize findings"),
    ("risk research", "synthesize findings"),
    ("synthesize findings", "evidence complete"),
    ("evidence complete", "write launch plan"),
    ("evidence complete", "human review"),
    ("human review", "write launch plan"),
    ("write launch plan", "publish report"),
}


def canonical_label(value: str) -> str:
    """Normalize punctuation and whitespace without hiding wording mistakes."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()


@pytest.mark.live_vision
@pytest.mark.asyncio
async def test_real_pipeline_extracts_every_fixture_node_and_connection() -> None:
    """Run manually after configuring a real multimodal provider.

    RUN_LIVE_VISION_TESTS=1 prevents normal test runs from spending tokens.
    The direct pipeline call intentionally bypasses VisionChain's POC fallback.
    """
    if os.getenv("RUN_LIVE_VISION_TESTS") != "1":
        pytest.skip("Set RUN_LIVE_VISION_TESTS=1 to call the configured vision model")
    if not settings.llm_api_key:
        pytest.skip("Set LLM_API_KEY before running the live vision fixture")

    provider = OpenAIProvider(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        vision_model=settings.vision_model,
        transcription_model=settings.transcription_model,
        temperature=0,
        timeout=settings.llm_request_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )

    workflow = await create_diagram_workflow_pipeline(provider).ainvoke(
        FIXTURE.read_bytes(), "image/png"
    )

    node_name_by_id = {node.id: canonical_label(node.name) for node in workflow.nodes}
    actual_nodes = set(node_name_by_id.values())
    actual_edges = {
        (node_name_by_id[edge.source], node_name_by_id[edge.target])
        for edge in workflow.edges
    }

    assert len(workflow.nodes) == 9, (
        f"Expected 9 nodes, received {len(workflow.nodes)}: {sorted(actual_nodes)}"
    )
    assert actual_nodes == EXPECTED_NODES, (
        f"Missing nodes: {sorted(EXPECTED_NODES - actual_nodes)}; "
        f"unexpected nodes: {sorted(actual_nodes - EXPECTED_NODES)}"
    )
    assert len(workflow.edges) == 11, (
        f"Expected 11 edges, received {len(workflow.edges)}: {sorted(actual_edges)}"
    )
    assert actual_edges == EXPECTED_EDGES, (
        f"Missing edges: {sorted(EXPECTED_EDGES - actual_edges)}; "
        f"unexpected edges: {sorted(actual_edges - EXPECTED_EDGES)}"
    )

    condition_edges = {
        node_name_by_id[edge.target]: canonical_label(edge.label)
        for edge in workflow.edges
        if node_name_by_id[edge.source] == "evidence complete"
    }
    assert condition_edges == {"write launch plan": "yes", "human review": "no"}
