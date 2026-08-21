from __future__ import annotations

from fastapi import APIRouter
from api.v1.runs.handlers.execution import runs_router

router = APIRouter()
router.include_router(runs_router)
