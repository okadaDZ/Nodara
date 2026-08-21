from __future__ import annotations

from fastapi import APIRouter
from api.v1.health.router import router as health_router
from api.v1.workflows.router import router as workflows_router
from api.v1.runs.router import router as runs_router
from api.v1.media.router import router as media_router
from api.v1.models.router import router as models_router

router = APIRouter(prefix="/v1")
router.include_router(health_router)
router.include_router(workflows_router)
router.include_router(runs_router)
router.include_router(media_router)
router.include_router(models_router)
