from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class DBWorkflow(Base):
    __tablename__ = "workflows"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    definition_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    runs = relationship("DBWorkflowRun", back_populates="workflow", cascade="all, delete-orphan")


class DBWorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id = Column(String, primary_key=True, index=True)
    workflow_id = Column(String, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    status = Column(String, default="running")
    input = Column(Text, nullable=False)
    final_output = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)

    workflow = relationship("DBWorkflow", back_populates="runs")
    node_runs = relationship("DBNodeRun", back_populates="workflow_run", cascade="all, delete-orphan")


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
