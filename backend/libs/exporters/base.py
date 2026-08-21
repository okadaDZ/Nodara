from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from libs.models.workflow import Workflow


class WorkflowExporter(ABC):
    """Abstract base class for workflow export targets (n8n, Make, LangGraph, JSON)."""

    @abstractmethod
    def export(self, workflow: Workflow) -> dict[str, Any]:
        """Convert a canonical Workflow into target format dictionary/schema."""
        raise NotImplementedError
