from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DBWorkflow(Base):
    __tablename__ = "workflows"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    definition_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    runs = relationship(
        "DBWorkflowRun",
        back_populates="workflow",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    schedule = relationship(
        "DBWorkflowSchedule",
        back_populates="workflow",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )


class DBWorkflowSchedule(Base):
    __tablename__ = "workflow_schedules"

    id = Column(String, primary_key=True, index=True)
    workflow_id = Column(String, ForeignKey("workflows.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    mode = Column(String, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    input_text = Column(Text, nullable=False)
    timezone = Column(String, nullable=False, default="UTC")
    run_at = Column(DateTime, nullable=True)
    window_start = Column(String, nullable=True)
    window_end = Column(String, nullable=True)
    interval_minutes = Column(Integer, nullable=True)
    next_run_at = Column(DateTime, nullable=True, index=True)
    last_run_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    workflow = relationship("DBWorkflow", back_populates="schedule")


class DBWorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id = Column(String, primary_key=True, index=True)
    workflow_id = Column(String, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    status = Column(String, default="running")
    input = Column(Text, nullable=False)
    final_output = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    finished_at = Column(DateTime, nullable=True)

    workflow = relationship("DBWorkflow", back_populates="runs")
    node_runs = relationship(
        "DBNodeRun",
        back_populates="workflow_run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class DBNodeRun(Base):
    __tablename__ = "node_runs"

    id = Column(String, primary_key=True, index=True)
    workflow_run_id = Column(String, ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False)
    node_id = Column(String, nullable=False)
    node_name = Column(String, default="")
    status = Column(String, default="waiting")
    input = Column(Text, nullable=True)
    output = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    workflow_run = relationship("DBWorkflowRun", back_populates="node_runs")
