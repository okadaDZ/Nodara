from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from api.v1.workflows.schemas import WorkflowDetailResponse
from libs.database.repositories import WorkflowRepository
from libs.database.session import get_db
from libs.demo import DEMO_WORKFLOW_ID, create_demo_workflow

router = APIRouter(prefix="/demo", tags=["Demo"])
_EXAMPLE_IMAGE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "hand_drawn_parallel_quality_workflow.png"
)


@router.get("/example-image", response_class=FileResponse)
async def get_example_image() -> FileResponse:
    return FileResponse(
        _EXAMPLE_IMAGE,
        media_type="image/png",
        filename="hand-drawn-parallel-workflow.png",
    )


@router.get("/workflow", response_model=WorkflowDetailResponse)
async def get_demo_workflow(db: Session = Depends(get_db)) -> WorkflowDetailResponse:
    repo = WorkflowRepository(db)
    workflow = repo.get_by_id(DEMO_WORKFLOW_ID)
    if workflow is None:
        workflow = repo.save(create_demo_workflow())
    return WorkflowDetailResponse(workflow=workflow)
