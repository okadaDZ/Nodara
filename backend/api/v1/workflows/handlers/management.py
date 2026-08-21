from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from api.v1.workflows.schemas import (
    WorkflowDetailResponse,
    WorkflowListResponse,
    WorkflowSummary,
    SetWorkflowEnabledRequest,
    RenameWorkflowRequest,
)
from libs.database.repositories import WorkflowRepository
from libs.database.session import get_db
from libs.models.workflow import Workflow

logger = logging.getLogger(__name__)
management_router = APIRouter()


@management_router.get("", response_model=WorkflowListResponse)
@management_router.get("/", response_model=WorkflowListResponse, include_in_schema=False)
async def list_workflows(db: Session = Depends(get_db)) -> WorkflowListResponse:
    """List all saved workflows."""
    repo = WorkflowRepository(db)
    summaries = repo.list_all()
    return WorkflowListResponse(
        workflows=[WorkflowSummary(**s) for s in summaries]
    )


@management_router.get("/{workflow_id}", response_model=WorkflowDetailResponse)
async def get_workflow(workflow_id: str, db: Session = Depends(get_db)) -> WorkflowDetailResponse:
    """Get single workflow by ID."""
    repo = WorkflowRepository(db)
    workflow = repo.get_by_id(workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID '{workflow_id}' not found.",
        )
    return WorkflowDetailResponse(workflow=workflow)


@management_router.put("/{workflow_id}", response_model=WorkflowDetailResponse)
async def update_workflow(
    workflow_id: str,
    payload: Workflow,
    db: Session = Depends(get_db),
) -> WorkflowDetailResponse:
    """Update workflow structure, nodes, edges, or instructions."""
    repo = WorkflowRepository(db)
    existing = repo.get_by_id(workflow_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID '{workflow_id}' not found.",
        )

    payload.id = workflow_id
    updated = repo.update(payload)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update workflow.",
        )
    return WorkflowDetailResponse(workflow=updated)


@management_router.patch("/{workflow_id}/enabled", response_model=WorkflowDetailResponse)
async def set_workflow_enabled(
    workflow_id: str,
    payload: SetWorkflowEnabledRequest,
    db: Session = Depends(get_db),
) -> WorkflowDetailResponse:
    """Enable or disable a saved workflow without replacing its graph."""
    repo = WorkflowRepository(db)
    workflow = repo.get_by_id(workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID '{workflow_id}' not found.",
        )
    workflow.enabled = payload.enabled
    updated = repo.update(workflow)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update workflow status.",
        )
    return WorkflowDetailResponse(workflow=updated)


@management_router.patch("/{workflow_id}/name", response_model=WorkflowDetailResponse)
async def rename_workflow(
    workflow_id: str,
    payload: RenameWorkflowRequest,
    db: Session = Depends(get_db),
) -> WorkflowDetailResponse:
    """Rename a workflow without replacing its graph."""
    updated = WorkflowRepository(db).rename(workflow_id, payload.name)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID '{workflow_id}' not found.",
        )
    return WorkflowDetailResponse(workflow=updated)


@management_router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str, db: Session = Depends(get_db)) -> dict[str, bool]:
    """Delete a workflow."""
    repo = WorkflowRepository(db)
    deleted = repo.delete(workflow_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID '{workflow_id}' not found.",
        )
    return {"ok": True}
