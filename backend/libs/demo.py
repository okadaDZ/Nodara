from __future__ import annotations

from libs.models.workflow import Workflow, WorkflowEdge, WorkflowNode

DEMO_WORKFLOW_ID = "wf_complex_parallel_demo"


def create_demo_workflow() -> Workflow:
    """Return the stable nine-node workflow paired with the onboarding image."""
    nodes = [
        WorkflowNode(id="brief", name="Brief Interpreter", description="Clarifies the goal and constraints", instructions="Turn the customer brief into goals, constraints, and acceptance criteria."),
        WorkflowNode(id="market", name="Market Research", description="Studies competitors and market signals", instructions="Research the market, competitors, positioning, and current demand signals."),
        WorkflowNode(id="risk", name="Risk Research", description="Identifies operational and compliance risks", instructions="Identify operational, delivery, compliance, and adoption risks."),
        WorkflowNode(id="customer", name="Customer Research", description="Finds audience needs and objections", instructions="Research audience needs, behaviors, objections, and buying triggers."),
        WorkflowNode(id="market_review", name="Market Reviewer", description="Checks market evidence and sources", instructions="Challenge the market findings and flag weak or unsupported evidence."),
        WorkflowNode(id="risk_review", name="Risk Reviewer", description="Challenges risk assumptions", instructions="Review the risk findings, severity, mitigations, and missing failure modes."),
        WorkflowNode(id="synthesis", name="Strategy Synthesizer", description="Merges all research streams", instructions="Merge the reviewed market, risk, and customer findings into one launch strategy."),
        WorkflowNode(id="writer", name="Report Writer", description="Turns strategy into a clear report", instructions="Write a concise, actionable launch report from the approved strategy."),
        WorkflowNode(id="quality", type="output", name="Quality Gate", description="Performs final accuracy and clarity review", instructions="Verify completeness, consistency, evidence, and clarity before publishing."),
    ]
    edges = [
        WorkflowEdge(id="edge_brief_market", source="brief", target="market"),
        WorkflowEdge(id="edge_brief_risk", source="brief", target="risk"),
        WorkflowEdge(id="edge_brief_customer", source="brief", target="customer"),
        WorkflowEdge(id="edge_market_market_review", source="market", target="market_review"),
        WorkflowEdge(id="edge_risk_risk_review", source="risk", target="risk_review"),
        WorkflowEdge(id="edge_market_review_synthesis", source="market_review", target="synthesis"),
        WorkflowEdge(id="edge_risk_review_synthesis", source="risk_review", target="synthesis"),
        WorkflowEdge(id="edge_customer_synthesis", source="customer", target="synthesis"),
        WorkflowEdge(id="edge_synthesis_writer", source="synthesis", target="writer"),
        WorkflowEdge(id="edge_writer_quality", source="writer", target="quality"),
    ]
    return Workflow(
        id=DEMO_WORKFLOW_ID,
        name="Parallel Market Launch Lab",
        description="A nine-agent workflow with research fan-out, parallel review lanes, a three-way merge, writing, and quality control.",
        nodes=nodes,
        edges=edges,
    )
