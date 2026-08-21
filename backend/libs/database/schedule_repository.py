from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from libs.database.models import DBWorkflowSchedule
from libs.models.schedule import ScheduleUpsert, WorkflowSchedule
from libs.scheduler.timing import calculate_next_run, utc_aware


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _model(row: DBWorkflowSchedule) -> WorkflowSchedule:
    return WorkflowSchedule(
        id=row.id,
        workflow_id=row.workflow_id,
        mode=row.mode,
        enabled=row.enabled,
        input_text=row.input_text,
        timezone=row.timezone,
        run_at=utc_aware(row.run_at) if row.run_at else None,
        window_start=row.window_start,
        window_end=row.window_end,
        interval_minutes=row.interval_minutes,
        next_run_at=utc_aware(row.next_run_at) if row.next_run_at else None,
        last_run_at=utc_aware(row.last_run_at) if row.last_run_at else None,
        last_error=row.last_error,
        created_at=utc_aware(row.created_at) if row.created_at else None,
        updated_at=utc_aware(row.updated_at) if row.updated_at else None,
    )


class ScheduleRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_for_workflow(self, workflow_id: str) -> WorkflowSchedule | None:
        row = self.db.query(DBWorkflowSchedule).filter(DBWorkflowSchedule.workflow_id == workflow_id).first()
        return _model(row) if row else None

    def upsert(self, workflow_id: str, payload: ScheduleUpsert) -> WorkflowSchedule:
        now = utc_now()
        next_run = calculate_next_run(
            mode=payload.mode,
            now_utc=now,
            run_at=payload.run_at,
            timezone_name=payload.timezone,
            window_start=payload.window_start,
            window_end=payload.window_end,
            interval_minutes=payload.interval_minutes,
        ) if payload.enabled else None
        row = self.db.query(DBWorkflowSchedule).filter(DBWorkflowSchedule.workflow_id == workflow_id).first()
        if not row:
            draft = WorkflowSchedule(workflow_id=workflow_id, **payload.model_dump())
            row = DBWorkflowSchedule(id=draft.id, workflow_id=workflow_id, created_at=now)
            self.db.add(row)
        row.mode = payload.mode
        row.enabled = payload.enabled
        row.input_text = payload.input_text.strip()
        row.timezone = payload.timezone
        row.run_at = utc_aware(payload.run_at).replace(tzinfo=None) if payload.run_at else None
        row.window_start = payload.window_start
        row.window_end = payload.window_end
        row.interval_minutes = payload.interval_minutes
        row.next_run_at = next_run.replace(tzinfo=None) if next_run else None
        row.last_error = None
        row.updated_at = now.replace(tzinfo=None)
        self.db.commit()
        self.db.refresh(row)
        return _model(row)

    def delete(self, workflow_id: str) -> bool:
        row = self.db.query(DBWorkflowSchedule).filter(DBWorkflowSchedule.workflow_id == workflow_id).first()
        if not row:
            return False
        self.db.delete(row)
        self.db.commit()
        return True

    def due(self, now: datetime) -> list[WorkflowSchedule]:
        naive_now = utc_aware(now).replace(tzinfo=None)
        rows = self.db.query(DBWorkflowSchedule).filter(
            DBWorkflowSchedule.enabled.is_(True),
            DBWorkflowSchedule.next_run_at.is_not(None),
            DBWorkflowSchedule.next_run_at <= naive_now,
        ).all()
        return [_model(row) for row in rows]

    def advance(self, schedule: WorkflowSchedule, error: str | None = None) -> WorkflowSchedule | None:
        row = self.db.query(DBWorkflowSchedule).filter(DBWorkflowSchedule.id == schedule.id).first()
        if not row:
            return None
        now = utc_now()
        row.last_run_at = now.replace(tzinfo=None)
        row.last_error = error
        if schedule.mode == "once":
            row.enabled = False
            row.next_run_at = None
        else:
            next_run = calculate_next_run(
                mode="window",
                now_utc=now,
                timezone_name=schedule.timezone,
                window_start=schedule.window_start,
                window_end=schedule.window_end,
                interval_minutes=schedule.interval_minutes,
            )
            row.next_run_at = next_run.replace(tzinfo=None) if next_run else None
        self.db.commit()
        self.db.refresh(row)
        return _model(row)
