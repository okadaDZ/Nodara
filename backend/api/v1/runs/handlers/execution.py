from __future__ import annotations

import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from api.v1.runs.schemas import RunWorkflowRequest, WorkflowRunListResponse, WorkflowRunResponse
from libs.database.repositories import RunRepository, WorkflowRepository
from libs.database.session import SessionLocal, get_db
from libs.runtime.agent_executor import AgentExecutor
from libs.langgraph import LangGraphWorkflowExecutor, WorkflowGraphCompiler, WorkflowCompilationError
from libs.langchain.provider import BaseAIProvider
from core.request_provider import get_request_provider
from libs.reports import build_run_report_pdf

logger = logging.getLogger(__name__)
runs_router = APIRouter(tags=["Runs"])


async def _run_workflow_background(workflow_id: str, run_id: str, input_text: str, provider: BaseAIProvider) -> None:
    """Execute workflow dependencies in parallel-ready waves using an isolated DB session."""
    db = SessionLocal()
    try:
        wf_repo = WorkflowRepository(db)
        run_repo = RunRepository(db)
        workflow = wf_repo.get_by_id(workflow_id)
        if not workflow:
            logger.error("Background task: workflow %s not found", workflow_id)
            run_repo.finish_run(run_id=run_id, status="failed", error="Workflow not found")
            return

        executor = LangGraphWorkflowExecutor(agent_executor=AgentExecutor(provider=provider))
        await executor.run(
            workflow=workflow,
            run_id=run_id,
            input_text=input_text,
            run_repo=run_repo,
        )
    except Exception as exc:
        logger.error("Unhandled error in background workflow run %s: %s", run_id, exc, exc_info=True)
        try:
            run_repo = RunRepository(db)
            run_repo.finish_run(
                run_id=run_id,
                status="failed",
                error=f"Execution error: {str(exc)}",
            )
        except Exception:
            pass
    finally:
        db.close()


@runs_router.post("/workflows/{workflow_id}/run", response_model=WorkflowRunResponse)
async def run_workflow(
    workflow_id: str,
    payload: RunWorkflowRequest,
    db: Session = Depends(get_db),
    provider: BaseAIProvider = Depends(get_request_provider),
) -> WorkflowRunResponse:
    """Trigger a dependency-aware execution run for a workflow."""
    wf_repo = WorkflowRepository(db)
    workflow = wf_repo.get_by_id(workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID '{workflow_id}' not found.",
        )

    if not workflow.nodes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workflow contains no agents to execute.",
        )

    if not workflow.enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This workflow is turned off. Turn it on before running it.",
        )

    try:
        WorkflowGraphCompiler().validate(workflow)
    except WorkflowCompilationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    run_repo = RunRepository(db)
    run = run_repo.create_run(
        workflow_id=workflow_id,
        input_text=payload.input,
        nodes=workflow.nodes,
    )

    # Launch background executor
    asyncio.create_task(
        _run_workflow_background(
            workflow_id=workflow_id,
            run_id=run.id,
            input_text=payload.input,
            provider=provider,
        )
    )

    return WorkflowRunResponse.model_validate(run.model_dump())


@runs_router.get("/runs/{run_id}", response_model=WorkflowRunResponse)
async def get_run_status(
    run_id: str,
    db: Session = Depends(get_db),
) -> WorkflowRunResponse:
    """Get the current execution status and intermediate outputs of a run."""
    run_repo = RunRepository(db)
    run = run_repo.get_run(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run with ID '{run_id}' not found.",
        )
    return WorkflowRunResponse.model_validate(run.model_dump())


@runs_router.get("/workflows/{workflow_id}/runs", response_model=WorkflowRunListResponse)
async def list_workflow_runs(
    workflow_id: str,
    db: Session = Depends(get_db),
) -> WorkflowRunListResponse:
    """Return newest-first persisted run history, including node inputs and outputs."""
    if not WorkflowRepository(db).get_by_id(workflow_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found.")
    runs = RunRepository(db).list_runs(workflow_id)
    return WorkflowRunListResponse(
        runs=[WorkflowRunResponse.model_validate(run.model_dump()) for run in runs]
    )


def _pdf_response(content: bytes, filename: str) -> Response:
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@runs_router.get("/runs/{run_id}/report.pdf")
async def export_run_report(run_id: str, db: Session = Depends(get_db)) -> Response:
    run = RunRepository(db).get_run(run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    workflow = WorkflowRepository(db).get_by_id(run.workflow_id)
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found.")
    return _pdf_response(build_run_report_pdf(workflow, [run]), f"{workflow.id}-{run.id}.pdf")


@runs_router.get("/workflows/{workflow_id}/runs/report.pdf")
async def export_workflow_runs_report(workflow_id: str, db: Session = Depends(get_db)) -> Response:
    workflow = WorkflowRepository(db).get_by_id(workflow_id)
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found.")
    runs = RunRepository(db).list_runs(workflow_id)
    return _pdf_response(build_run_report_pdf(workflow, runs), f"{workflow.id}-all-runs.pdf")
