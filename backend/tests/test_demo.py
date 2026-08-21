from pathlib import Path

from libs.demo import DEMO_WORKFLOW_ID, create_demo_workflow


def test_demo_workflow_preserves_parallel_fan_out_and_three_way_merge() -> None:
    workflow = create_demo_workflow()
    assert workflow.id == DEMO_WORKFLOW_ID
    assert len(workflow.nodes) == 9
    assert {edge.target for edge in workflow.edges if edge.source == "brief"} == {
        "market", "risk", "customer"
    }
    assert {edge.source for edge in workflow.edges if edge.target == "synthesis"} == {
        "market_review", "risk_review", "customer"
    }


def test_demo_example_image_is_packaged() -> None:
    fixture = Path(__file__).parent / "fixtures" / "hand_drawn_parallel_quality_workflow.png"
    assert fixture.is_file()
