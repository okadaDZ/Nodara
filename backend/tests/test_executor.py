from __future__ import annotations

import asyncio
import pytest
from sqlalchemy.orm import Session
from libs.database.repositories import RunRepository, WorkflowRepository
from libs.models.workflow import Workflow, WorkflowNode, WorkflowEdge
from libs.runtime.agent_executor import AgentExecutor
from libs.runtime.agent_executor import AgentExecutionResult
from libs.runtime.executor import SequentialWorkflowExecutor
from libs.langchain.provider import MockAIProvider


class ModelRecordingProvider(MockAIProvider):
    def __init__(self):
        self.model_names: list[str | None] = []

    async def generate_text(self, prompt, system_prompt=None, model_name=None):
        self.model_names.append(model_name)
        return "done"


@pytest.mark.asyncio
async def test_agent_executor_uses_the_nodes_selected_model():
    provider = ModelRecordingProvider()
    result = await AgentExecutor(provider=provider).execute(
        WorkflowNode(name="Writer", model="small-writing-model"), "Write a summary"
    )
    assert result.success is True
    assert provider.model_names == ["small-writing-model"]


@pytest.mark.asyncio
async def test_sequential_workflow_execution(db_session: Session):
    wf_repo = WorkflowRepository(db_session)
    run_repo = RunRepository(db_session)

    workflow = Workflow(
        name="Sequential Test",
        nodes=[
            WorkflowNode(id="n1", name="Agent1", instructions="Step 1 instructions"),
            WorkflowNode(id="n2", name="Agent2", instructions="Step 2 instructions"),
        ],
        edges=[WorkflowEdge(source="n1", target="n2")],
    )
    saved_wf = wf_repo.save(workflow)

    run = run_repo.create_run(workflow_id=saved_wf.id, input_text="Initial Prompt", nodes=saved_wf.nodes)
    assert run.status == "running"
    assert len(run.nodes) == 2

    provider = MockAIProvider()
    agent_executor = AgentExecutor(provider=provider)
    executor = SequentialWorkflowExecutor(agent_executor=agent_executor)

    finished_run = await executor.run(
        workflow=saved_wf,
        run_id=run.id,
        input_text="Initial Prompt",
        run_repo=run_repo,
    )

    assert finished_run.status == "completed"
    assert finished_run.final_output is not None
    assert len(finished_run.nodes) == 2
    assert all(n.status == "completed" for n in finished_run.nodes)


class RecordingParallelExecutor:
    def __init__(self):
        self.active = 0
        self.max_active = 0
        self.inputs: dict[str, str | None] = {}

    async def execute(self, node, original_input: str, previous_output: str | None = None):
        self.inputs[node.id] = previous_output
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1
        return AgentExecutionResult(success=True, output=f"output:{node.id}")


@pytest.mark.asyncio
async def test_complex_workflow_runs_parallel_branches_and_merges(db_session: Session):
    """A 9-node research flow fans out twice and merges both branches."""
    wf_repo = WorkflowRepository(db_session)
    run_repo = RunRepository(db_session)
    nodes = [
        WorkflowNode(id="brief", name="Brief", instructions="Normalize input"),
        WorkflowNode(id="market", name="Market Research", instructions="Research market"),
        WorkflowNode(id="risk", name="Risk Research", instructions="Research risks"),
        WorkflowNode(id="customer", name="Customer Research", instructions="Research customers"),
        WorkflowNode(id="market_review", name="Market Reviewer", instructions="Review market"),
        WorkflowNode(id="risk_review", name="Risk Reviewer", instructions="Review risk"),
        WorkflowNode(id="synthesis", name="Synthesis", instructions="Merge research"),
        WorkflowNode(id="writer", name="Writer", instructions="Draft report"),
        WorkflowNode(id="quality", name="Quality Gate", instructions="Approve report"),
    ]
    edges = [
        WorkflowEdge(source="brief", target="market"),
        WorkflowEdge(source="brief", target="risk"),
        WorkflowEdge(source="brief", target="customer"),
        WorkflowEdge(source="market", target="market_review"),
        WorkflowEdge(source="risk", target="risk_review"),
        WorkflowEdge(source="market_review", target="synthesis"),
        WorkflowEdge(source="risk_review", target="synthesis"),
        WorkflowEdge(source="customer", target="synthesis"),
        WorkflowEdge(source="synthesis", target="writer"),
        WorkflowEdge(source="writer", target="quality"),
    ]
    workflow = wf_repo.save(Workflow(name="Complex Parallel Test", nodes=nodes, edges=edges))
    run = run_repo.create_run(workflow_id=workflow.id, input_text="Build a launch plan", nodes=nodes)
    recording_executor = RecordingParallelExecutor()
    executor = SequentialWorkflowExecutor(agent_executor=recording_executor)  # type: ignore[arg-type]

    finished = await executor.run(workflow, run.id, "Build a launch plan", run_repo)

    assert finished.status == "completed"
    assert recording_executor.max_active == 3
    assert recording_executor.inputs["synthesis"] is not None
    assert "output:market_review" in recording_executor.inputs["synthesis"]
    assert "output:risk_review" in recording_executor.inputs["synthesis"]
    assert "output:customer" in recording_executor.inputs["synthesis"]
    assert all(node.status == "completed" for node in finished.nodes)
