from __future__ import annotations

import json
from datetime import datetime, timezone
from sqlalchemy.orm import Session, selectinload
from libs.database.models import DBWorkflow, DBWorkflowRun, DBNodeRun
from libs.models.workflow import Workflow, WorkflowNode
from libs.models.run import WorkflowRun, NodeRun


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WorkflowRepository:
    def __init__(self, db: Session):
        self.db = db

    def save(self, workflow: Workflow) -> Workflow:
        definition_json = workflow.model_dump_json()
        now = utc_now()
        db_workflow = DBWorkflow(
            id=workflow.id,
            name=workflow.name,
            description=workflow.description,
            definition_json=definition_json,
            created_at=now,
            updated_at=now,
        )
        self.db.add(db_workflow)
        self.db.commit()
        self.db.refresh(db_workflow)
        return workflow

    def get_by_id(self, workflow_id: str) -> Workflow | None:
        db_workflow = self.db.query(DBWorkflow).filter(DBWorkflow.id == workflow_id).first()
        if not db_workflow:
            return None
        data = json.loads(db_workflow.definition_json)
        return Workflow.model_validate(data)

    def list_all(self) -> list[dict]:
        db_workflows = self.db.query(DBWorkflow).order_by(DBWorkflow.updated_at.desc()).all()
        summaries = []
        for wf in db_workflows:
            try:
                data = json.loads(wf.definition_json)
                node_count = len(data.get("nodes", []))
                enabled = data.get("enabled", True)
            except Exception:
                node_count = 0
                enabled = True
            summaries.append(
                {
                    "id": wf.id,
                    "name": wf.name,
                    "description": wf.description,
                    "node_count": node_count,
                    "run_count": len(wf.runs or []),
                    "last_run_at": (
                        max((run.finished_at or run.created_at for run in wf.runs), default=None)
                        if wf.runs else None
                    ),
                    "enabled": enabled,
                    "schedule_enabled": bool(wf.schedule and wf.schedule.enabled),
                    "schedule_mode": wf.schedule.mode if wf.schedule else None,
                    "next_run_at": (
                        wf.schedule.next_run_at.replace(tzinfo=timezone.utc)
                        if wf.schedule and wf.schedule.next_run_at else None
                    ),
                    "created_at": wf.created_at,
                    "updated_at": wf.updated_at,
                }
            )
        return summaries

    def update(self, workflow: Workflow) -> Workflow | None:
        db_workflow = self.db.query(DBWorkflow).filter(DBWorkflow.id == workflow.id).first()
        if not db_workflow:
            return None
        db_workflow.name = workflow.name
        db_workflow.description = workflow.description
        db_workflow.definition_json = workflow.model_dump_json()
        db_workflow.updated_at = utc_now()
        self.db.commit()
        return workflow

    def rename(self, workflow_id: str, name: str) -> Workflow | None:
        db_workflow = self.db.query(DBWorkflow).filter(DBWorkflow.id == workflow_id).first()
        if not db_workflow:
            return None
        data = json.loads(db_workflow.definition_json)
        data["name"] = name
        db_workflow.name = name
        db_workflow.definition_json = json.dumps(data)
        db_workflow.updated_at = utc_now()
        self.db.commit()
        return Workflow.model_validate(data)

    def delete(self, workflow_id: str) -> bool:
        db_workflow = self.db.query(DBWorkflow).filter(DBWorkflow.id == workflow_id).first()
        if not db_workflow:
            return False
        self.db.delete(db_workflow)
        self.db.commit()
        return True


class RunRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_run(self, workflow_id: str, input_text: str, nodes: list[WorkflowNode]) -> WorkflowRun:
        now = utc_now()
        run = WorkflowRun(
            workflow_id=workflow_id,
            status="running",
            input=input_text,
            created_at=now,
        )

        db_run = DBWorkflowRun(
            id=run.id,
            workflow_id=workflow_id,
            status="running",
            input=input_text,
            created_at=now,
        )
        self.db.add(db_run)

        node_runs: list[NodeRun] = []
        for node in nodes:
            if node.type in {"tool", "memory", "parser"}:
                continue
            n_run = NodeRun(
                workflow_run_id=run.id,
                node_id=node.id,
                node_name=node.name,
                status="waiting",
            )
            node_runs.append(n_run)
            db_node_run = DBNodeRun(
                id=n_run.id,
                workflow_run_id=run.id,
                node_id=node.id,
                node_name=node.name,
                status="waiting",
            )
            self.db.add(db_node_run)

        self.db.commit()
        run.nodes = node_runs
        return run

    def get_run(self, run_id: str) -> WorkflowRun | None:
        db_run = (
            self.db.query(DBWorkflowRun)
            .options(selectinload(DBWorkflowRun.node_runs))
            .filter(DBWorkflowRun.id == run_id)
            .first()
        )
        if not db_run:
            return None

        node_runs: list[NodeRun] = []
        for dnr in (db_run.node_runs or []):
            node_runs.append(
                NodeRun(
                    id=dnr.id,
                    workflow_run_id=dnr.workflow_run_id,
                    node_id=dnr.node_id,
                    node_name=dnr.node_name,
                    status=dnr.status,
                    input=dnr.input,
                    output=dnr.output,
                    error=dnr.error,
                    started_at=dnr.started_at,
                    finished_at=dnr.finished_at,
                )
            )

        return WorkflowRun(
            id=db_run.id,
            workflow_id=db_run.workflow_id,
            status=db_run.status,
            input=db_run.input,
            final_output=db_run.final_output,
            error=db_run.error,
            created_at=db_run.created_at,
            finished_at=db_run.finished_at,
            nodes=node_runs,
        )

    def list_runs(self, workflow_id: str) -> list[WorkflowRun]:
        run_ids = [
            row.id
            for row in self.db.query(DBWorkflowRun.id)
            .filter(DBWorkflowRun.workflow_id == workflow_id)
            .order_by(DBWorkflowRun.created_at.desc())
            .all()
        ]
        return [run for run_id in run_ids if (run := self.get_run(run_id)) is not None]

    def update_node_status(
        self,
        run_id: str,
        node_id: str,
        status: str,
        input_data: str | None = None,
        output_data: str | None = None,
        error: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> None:
        db_node_run = (
            self.db.query(DBNodeRun)
            .filter(DBNodeRun.workflow_run_id == run_id, DBNodeRun.node_id == node_id)
            .first()
        )
        if db_node_run:
            db_node_run.status = status
            if input_data is not None:
                db_node_run.input = input_data
            if output_data is not None:
                db_node_run.output = output_data
            if error is not None:
                db_node_run.error = error
            if started_at is not None:
                db_node_run.started_at = started_at
            if finished_at is not None:
                db_node_run.finished_at = finished_at
            self.db.commit()

    def finish_run(
        self,
        run_id: str,
        status: str,
        final_output: str | None = None,
        error: str | None = None,
    ) -> None:
        db_run = self.db.query(DBWorkflowRun).filter(DBWorkflowRun.id == run_id).first()
        if db_run:
            db_run.status = status
            db_run.final_output = final_output
            db_run.error = error
            db_run.finished_at = utc_now()
            self.db.commit()
