from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from libs.database.repositories import WorkflowRepository
from libs.database.schedule_repository import ScheduleRepository
from libs.database.session import get_db
from libs.models.schedule import ScheduleUpsert, WorkflowSchedule

scheduling_router = APIRouter()


@scheduling_router.get("/{workflow_id}/schedule", response_model=WorkflowSchedule | None)
async def get_schedule(workflow_id: str, db: Session = Depends(get_db)) -> WorkflowSchedule | None:
    if not WorkflowRepository(db).get_by_id(workflow_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found.")
    return ScheduleRepository(db).get_for_workflow(workflow_id)


@scheduling_router.put("/{workflow_id}/schedule", response_model=WorkflowSchedule)
async def save_schedule(
    workflow_id: str,
    payload: ScheduleUpsert,
    db: Session = Depends(get_db),
) -> WorkflowSchedule:
    if not WorkflowRepository(db).get_by_id(workflow_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found.")
    try:
        return ScheduleRepository(db).upsert(workflow_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@scheduling_router.delete("/{workflow_id}/schedule")
async def delete_schedule(workflow_id: str, db: Session = Depends(get_db)) -> dict[str, bool]:
    return {"ok": ScheduleRepository(db).delete(workflow_id)}
