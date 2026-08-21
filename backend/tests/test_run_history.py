from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from libs.database.repositories import RunRepository, WorkflowRepository
from libs.models.workflow import Workflow, WorkflowEdge, WorkflowNode


@pytest.mark.asyncio
async def test_run_history_summary_details_and_pdf_exports(
    client: AsyncClient,
    db_session: Session,
) -> None:
    workflow = WorkflowRepository(db_session).save(Workflow(
        name="Research and summarize",
        nodes=[
            WorkflowNode(id="research", name="Research"),
            WorkflowNode(id="summary", name="Summary"),
        ],
        edges=[WorkflowEdge(source="research", target="summary")],
    ))
    repo = RunRepository(db_session)
    run = repo.create_run(workflow.id, "Investigate the Dubai market", workflow.nodes)
    repo.update_node_status(
        run.id, "research", "completed",
        input_data="Investigate the Dubai market",
        output_data="Research findings",
    )
    repo.update_node_status(
        run.id, "summary", "completed",
        input_data="Research findings",
        output_data="Concise final summary",
    )
    repo.finish_run(run.id, "completed", final_output="Concise final summary")

    workflows_response = await client.get("/api/workflows")
    summary = next(item for item in workflows_response.json()["workflows"] if item["id"] == workflow.id)
    assert summary["run_count"] == 1
    assert summary["last_run_at"] is not None

    history_response = await client.get(f"/api/workflows/{workflow.id}/runs")
    assert history_response.status_code == 200
    history = history_response.json()["runs"]
    assert history[0]["input"] == "Investigate the Dubai market"
    assert history[0]["final_output"] == "Concise final summary"
    assert history[0]["nodes"][0]["output"] == "Research findings"

    run_pdf = await client.get(f"/api/runs/{run.id}/report.pdf")
    assert run_pdf.status_code == 200
    assert run_pdf.headers["content-type"] == "application/pdf"
    assert run_pdf.content.startswith(b"%PDF")
    assert len(run_pdf.content) > 1500

    all_pdf = await client.get(f"/api/workflows/{workflow.id}/runs/report.pdf")
    assert all_pdf.status_code == 200
    assert all_pdf.content.startswith(b"%PDF")
