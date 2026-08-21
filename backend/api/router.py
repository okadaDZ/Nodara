from __future__ import annotations

from fastapi import APIRouter
from api.v1.router import router as v1_router
from api.v1.workflows.router import router as workflows_router
from api.v1.runs.router import router as runs_router
from api.v1.media.router import router as media_router
from api.v1.models.router import router as models_router
from api.v1.demo.router import router as demo_router

router = APIRouter(prefix="/api")

# Mount versioned sub-router
router.include_router(v1_router)

# Mount direct alias for /api/workflows, /api/runs, etc.
router.include_router(workflows_router)
router.include_router(runs_router)
router.include_router(media_router)
router.include_router(models_router)
router.include_router(demo_router)
