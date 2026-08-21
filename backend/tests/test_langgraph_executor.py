from __future__ import annotations

import asyncio
import json

import pytest
from sqlalchemy.orm import Session

from libs.database.repositories import RunRepository, WorkflowRepository
from libs.langchain.provider import MockAIProvider
from libs.langgraph import LangGraphWorkflowExecutor, WorkflowCompilationError, WorkflowGraphCompiler
from libs.models.workflow import Workflow, WorkflowEdge, WorkflowNode
from libs.runtime.agent_executor import AgentExecutionResult, AgentExecutor
from libs.runtime.rss_source import MockRssSource, RssFeedItem, RssTriggerExecutor


class RecordingExecutor:
    def __init__(self):
        self.active = 0
        self.max_active = 0
        self.calls: list[str] = []
        self.inputs: dict[str, str | None] = {}

    async def execute(self, node, original_input: str, previous_output: str | None = None):
        self.calls.append(node.id)
        self.inputs[node.id] = previous_output
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1
        return AgentExecutionResult(success=True, output=f"output:{node.id}")


@pytest.mark.asyncio
async def test_langgraph_runs_parallel_branches_and_one_join(db_session: Session):
    nodes = [
        WorkflowNode(id="input", type="input", name="Input"),
        WorkflowNode(id="research", name="Research"),
        WorkflowNode(id="risk", name="Risk"),
        WorkflowNode(id="risk_review", name="Risk review"),
        WorkflowNode(id="join", name="Synthesis"),
        WorkflowNode(id="output", type="output", name="Output"),
    ]
    workflow = Workflow(
        name="Compiled parallel graph",
        nodes=nodes,
        edges=[
            WorkflowEdge(source="input", target="research"),
            WorkflowEdge(source="input", target="risk"),
            WorkflowEdge(source="research", target="join"),
            WorkflowEdge(source="risk", target="risk_review"),
            WorkflowEdge(source="risk_review", target="join"),
            WorkflowEdge(source="join", target="output"),
        ],
    )
    workflow = WorkflowRepository(db_session).save(workflow)
    run_repo = RunRepository(db_session)
    run = run_repo.create_run(workflow.id, "Investigate launch", nodes)
    recorder = RecordingExecutor()

    finished = await LangGraphWorkflowExecutor(agent_executor=recorder).run(  # type: ignore[arg-type]
        workflow, run.id, "Investigate launch", run_repo
    )

    assert finished.status == "completed"
    assert recorder.max_active == 2
    assert recorder.calls.count("join") == 1
    assert "output:research" in (recorder.inputs["join"] or "")
    assert "output:risk_review" in (recorder.inputs["join"] or "")
    assert finished.final_output == "output:join"


class RouteProvider(MockAIProvider):
    async def generate_text(self, prompt, system_prompt=None, model_name=None):
        if "Choose exactly one route" in prompt:
            return "approved"
        return await super().generate_text(prompt, system_prompt, model_name)


@pytest.mark.asyncio
async def test_langgraph_router_runs_only_selected_branch(db_session: Session):
    nodes = [
        WorkflowNode(id="router", type="condition", name="Quality gate", instructions="Route good work."),
        WorkflowNode(id="approved", name="Publish"),
        WorkflowNode(id="redraw", name="Redraw"),
    ]
    workflow = Workflow(
        name="Conditional graph",
        nodes=nodes,
        edges=[
            WorkflowEdge(source="router", target="approved", kind="conditional", label="approved"),
            WorkflowEdge(source="router", target="redraw", kind="conditional", label="redraw"),
        ],
    )
    workflow = WorkflowRepository(db_session).save(workflow)
    run_repo = RunRepository(db_session)
    run = run_repo.create_run(workflow.id, "Review this", nodes)
    executor = LangGraphWorkflowExecutor(agent_executor=AgentExecutor(provider=RouteProvider()))

    finished = await executor.run(workflow, run.id, "Review this", run_repo)

    assert finished.status == "completed"
    statuses = {node.node_id: node.status for node in finished.nodes}
    assert statuses["router"] == "completed"
    assert statuses["approved"] == "completed"
    assert statuses["redraw"] == "skipped"
    assert finished.final_output


def test_compiler_rejects_unlabeled_router_edges():
    workflow = Workflow(
        name="Invalid router",
        nodes=[
            WorkflowNode(id="route", type="router", name="Router"),
            WorkflowNode(id="a", name="A"),
            WorkflowNode(id="b", name="B"),
        ],
        edges=[
            WorkflowEdge(source="route", target="a", kind="conditional"),
            WorkflowEdge(source="route", target="b", kind="conditional", label="b"),
        ],
    )

    with pytest.raises(WorkflowCompilationError, match="unique non-empty label"):
        WorkflowGraphCompiler().validate(workflow)


@pytest.mark.asyncio
async def test_rss_triggers_emit_distinct_mock_feeds_and_join_all_sources(db_session: Session):
    nodes = [
        WorkflowNode(id="youtube", type="trigger", name="RSS YouTube Source"),
        WorkflowNode(id="x", type="trigger", name="RSS X"),
        WorkflowNode(id="web", type="trigger", name="RSS Web (XML)"),
        WorkflowNode(id="normalize", name="Normalize feeds"),
    ]
    workflow = Workflow(
        name="RSS multisource summarizer",
        nodes=nodes,
        edges=[
            WorkflowEdge(source="youtube", target="normalize"),
            WorkflowEdge(source="x", target="normalize"),
            WorkflowEdge(source="web", target="normalize"),
        ],
    )
    workflow = WorkflowRepository(db_session).save(workflow)
    run_repo = RunRepository(db_session)
    run = run_repo.create_run(workflow.id, "", nodes)
    recorder = RecordingExecutor()

    finished = await LangGraphWorkflowExecutor(
        agent_executor=recorder,  # type: ignore[arg-type]
        rss_trigger_executor=RssTriggerExecutor(MockRssSource()),
    ).run(
        workflow, run.id, "", run_repo
    )

    assert finished.status == "completed"
    combined = recorder.inputs["normalize"] or ""
    assert "[RSS YouTube Source]" in combined
    assert "[RSS X]" in combined
    assert "[RSS Web (XML)]" in combined
    assert '"source": "youtube"' in combined
    assert '"source": "x"' in combined
    assert '"source": "web_xml"' in combined
    for node_id, expected_source in (("youtube", "youtube"), ("x", "x"), ("web", "web_xml")):
        node_run = next(item for item in finished.nodes if item.node_id == node_id)
        payload = json.loads(node_run.output or "[]")
        assert payload
        assert {item["source"] for item in payload} == {expected_source}


class RecordingSearchSource:
    def __init__(self):
        self.queries: list[str] = []

    async def fetch(self, node, query=""):
        self.queries.append(query)
        return [RssFeedItem(source="news", title="Result", link="https://example.com", pub_date="", description="")]


@pytest.mark.asyncio
async def test_query_builder_plan_fans_out_to_search_nodes(db_session: Session):
    nodes = [
        WorkflowNode(id="plan", type="query_builder", name="Build search query"),
        WorkflowNode(id="news_a", type="trigger", name="News source A"),
        WorkflowNode(id="news_b", type="trigger", name="News source B"),
    ]
    workflow = Workflow(
        name="Planned parallel search",
        nodes=nodes,
        edges=[
            WorkflowEdge(source="plan", target="news_a"),
            WorkflowEdge(source="plan", target="news_b"),
        ],
    )
    WorkflowRepository(db_session).save(workflow)
    run_repo = RunRepository(db_session)
    run = run_repo.create_run(workflow.id, "Latest Tesla news for the last 7 days", nodes)
    source = RecordingSearchSource()

    finished = await LangGraphWorkflowExecutor(
        rss_trigger_executor=RssTriggerExecutor(source),
    ).run(workflow, run.id, "Latest Tesla news for the last 7 days", run_repo)

    assert finished.status == "completed"
    assert len(source.queries) == 2
    plans = [json.loads(query) for query in source.queries]
    assert {plan["kind"] for plan in plans} == {"news_search_plan"}
    assert {plan["topic"] for plan in plans} == {"Tesla"}
