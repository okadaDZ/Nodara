from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from libs.database.repositories import WorkflowRepository
from libs.database.session import get_db
from libs.n8n.converter import workflow_to_n8n

logger = logging.getLogger(__name__)
export_router = APIRouter()


@export_router.get("/{workflow_id}/export/n8n")
async def export_workflow_to_n8n(
    workflow_id: str,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Export a workflow as an n8n-compatible JSON file ready to import."""
    repo = WorkflowRepository(db)
    workflow = repo.get_by_id(workflow_id)

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow '{workflow_id}' not found.",
        )

    try:
        n8n_json = workflow_to_n8n(workflow)
        safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in workflow.name)
        filename = f"{safe_name.replace(' ', '_')}_n8n.json"

        return JSONResponse(
            content=n8n_json,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except Exception as exc:
        logger.error("n8n export failed for %s: %s", workflow_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export workflow to n8n format.",
        )
