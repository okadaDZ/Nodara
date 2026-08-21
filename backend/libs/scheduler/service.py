from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from libs.database.repositories import RunRepository, WorkflowRepository
from libs.database.schedule_repository import ScheduleRepository
from libs.database.session import SessionLocal
from libs.langchain.provider import get_ai_provider
from libs.langgraph import LangGraphWorkflowExecutor
from libs.runtime.agent_executor import AgentExecutor

logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(self, poll_seconds: float = 5.0):
        self.poll_seconds = poll_seconds
        self._runner: asyncio.Task | None = None
        self._runs: set[asyncio.Task] = set()

    async def start(self) -> None:
        if self._runner and not self._runner.done():
            return
        self._runner = asyncio.create_task(self._loop(), name="nodara-scheduler")
        logger.info("Workflow scheduler started.")

    async def stop(self) -> None:
        if self._runner:
            self._runner.cancel()
            await asyncio.gather(self._runner, return_exceptions=True)
            self._runner = None
        if self._runs:
            await asyncio.gather(*self._runs, return_exceptions=True)
        logger.info("Workflow scheduler stopped.")

    async def _loop(self) -> None:
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Scheduler tick failed.")
            await asyncio.sleep(self.poll_seconds)

    async def tick(self, now: datetime | None = None) -> int:
        now = now or datetime.now(timezone.utc)
        db = SessionLocal()
        claimed = []
        try:
            schedules = ScheduleRepository(db)
            workflows = WorkflowRepository(db)
            for schedule in schedules.due(now):
                workflow = workflows.get_by_id(schedule.workflow_id)
                if not workflow:
                    schedules.advance(schedule, "Workflow no longer exists.")
                    continue
                if not workflow.enabled:
                    schedules.advance(schedule, "Workflow was off at the scheduled time.")
                    continue
                # Advance before execution so a slow run cannot be claimed twice.
                schedules.advance(schedule)
                claimed.append(schedule)
        finally:
            db.close()

        for schedule in claimed:
            task = asyncio.create_task(self._execute(schedule.workflow_id, schedule.input_text))
            self._runs.add(task)
            task.add_done_callback(self._runs.discard)
        return len(claimed)

    async def _execute(self, workflow_id: str, input_text: str) -> None:
        db = SessionLocal()
        try:
            workflow = WorkflowRepository(db).get_by_id(workflow_id)
            if not workflow or not workflow.enabled:
                return
            run_repo = RunRepository(db)
            run = run_repo.create_run(workflow.id, input_text, workflow.nodes)
            executor = LangGraphWorkflowExecutor(
                agent_executor=AgentExecutor(provider=get_ai_provider())
            )
            await executor.run(workflow, run.id, input_text, run_repo)
        except Exception:
            logger.exception("Scheduled workflow %s failed to start.", workflow_id)
        finally:
            db.close()


scheduler_service = SchedulerService()
