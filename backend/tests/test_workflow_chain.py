from __future__ import annotations

import pytest
from libs.langchain.chains.workflow_chain import WorkflowChain
from libs.langchain.chains.agent_chain import AgentChain
from libs.langchain.provider import MockAIProvider
from libs.models.workflow import Workflow, WorkflowNode, WorkflowEdge


@pytest.mark.asyncio
async def test_workflow_generation_from_text():
    provider = MockAIProvider()
    chain = WorkflowChain(provider=provider)
    workflow = await chain.generate_from_text("Research AI news and write a summary")

    assert workflow.name is not None
    assert len(workflow.nodes) >= 2
    assert len(workflow.edges) >= 1
    assert workflow.nodes[0].name != ""


@pytest.mark.asyncio
async def test_agent_instruction_generation():
    provider = MockAIProvider()
    agent_chain = AgentChain(provider=provider)
    wf = Workflow(
        id="wf_1",
        name="News Workflow",
        nodes=[WorkflowNode(id="n1", name="Researcher", description="Search topics")],
        edges=[],
    )

    instructions = await agent_chain.generate_instructions(
        workflow=wf, node=wf.nodes[0], user_hint="Focus on accuracy"
    )
    assert instructions is not None
    assert len(instructions) > 10
