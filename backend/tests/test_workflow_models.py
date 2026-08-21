from __future__ import annotations

import pytest
from pydantic import ValidationError

from libs.models.workflow import Workflow, WorkflowNode, WorkflowEdge, Position
from libs.models.run import WorkflowRun, NodeRun
from core.settings import settings


def test_nodes_inherit_the_backend_default_model():
    assert WorkflowNode(name="Defaulted").model == settings.llm_model
    assert WorkflowNode.model_validate({"name": "Old saved node"}).model == settings.llm_model


def test_agent_model_override_round_trips():
    node = WorkflowNode(name="Writer", model="special-model", model_override=True)
    restored = WorkflowNode.model_validate(node.model_dump())
    assert restored.model == "special-model"
    assert restored.model_override is True


def test_workflow_model_creation():
    node1 = WorkflowNode(id="node_1", type="agent", name="Researcher", description="Research info")
    node2 = WorkflowNode(id="node_2", type="agent", name="Writer", description="Draft post")
    edge = WorkflowEdge(id="edge_1", source="node_1", target="node_2")

    workflow = Workflow(
        id="wf_123",
        name="Test Workflow",
        description="Testing creation",
        nodes=[node1, node2],
        edges=[edge],
    )

    assert workflow.id == "wf_123"
    assert len(workflow.nodes) == 2
    assert len(workflow.edges) == 1
    assert workflow.edges[0].source == "node_1"
    assert workflow.edges[0].target == "node_2"


def test_workflow_run_model():
    run = WorkflowRun(
        id="run_123",
        workflow_id="wf_123",
        status="running",
        input="Find latest news",
        nodes=[
            NodeRun(
                workflow_run_id="run_123",
                node_id="node_1",
                node_name="Researcher",
                status="completed",
                output="Found 3 articles",
            )
        ],
    )
    assert run.id == "run_123"
    assert run.nodes[0].status == "completed"
    assert run.nodes[0].output == "Found 3 articles"


@pytest.mark.parametrize(
    "nodes,edges,message",
    [
        ([], [], "execution node"),
        ([WorkflowNode(id="a", name="A"), WorkflowNode(id="a", name="Again")], [], "unique"),
        ([WorkflowNode(id="a", name="A")], [WorkflowEdge(source="a", target="missing")], "missing"),
        ([WorkflowNode(id="a", name="A")], [WorkflowEdge(source="a", target="a")], "itself"),
        (
            [WorkflowNode(id="a", name="A"), WorkflowNode(id="b", name="B")],
            [WorkflowEdge(source="a", target="b"), WorkflowEdge(source="a", target="b")],
            "Duplicate",
        ),
        (
            [WorkflowNode(id="a", name="A"), WorkflowNode(id="b", name="B")],
            [WorkflowEdge(source="a", target="b"), WorkflowEdge(source="b", target="a")],
            "cycles",
        ),
    ],
)
def test_workflow_rejects_invalid_graphs(nodes, edges, message):
    with pytest.raises(ValidationError, match=message):
        Workflow(name="Invalid", nodes=nodes, edges=edges)


def test_workflow_accepts_matching_support_edge():
    workflow = Workflow(
        name="Support",
        nodes=[WorkflowNode(id="agent", name="Agent"), WorkflowNode(id="memory", name="Memory", type="memory")],
        edges=[WorkflowEdge(source="memory", target="agent", kind="memory")],
    )
    assert workflow.edges[0].kind == "memory"


def test_workflow_rejects_mismatched_support_edge():
    with pytest.raises(ValidationError, match="matching support"):
        Workflow(
            name="Invalid support",
            nodes=[WorkflowNode(id="agent", name="Agent"), WorkflowNode(id="tool", name="Tool", type="tool")],
            edges=[WorkflowEdge(source="tool", target="agent", kind="memory")],
        )
