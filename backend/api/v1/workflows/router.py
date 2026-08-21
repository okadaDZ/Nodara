from __future__ import annotations

from fastapi import APIRouter
from api.v1.workflows.handlers.creation import creation_router
from api.v1.workflows.handlers.management import management_router
from api.v1.workflows.handlers.editing import editing_router
from api.v1.workflows.handlers.export import export_router
from api.v1.workflows.handlers.scheduling import scheduling_router

router = APIRouter(tags=["Workflows"])

# Mount handlers with /workflows prefix so paths like "" and "/" both resolve cleanly
router.include_router(creation_router, prefix="/workflows")
router.include_router(management_router, prefix="/workflows")
router.include_router(editing_router, prefix="/workflows")
router.include_router(export_router, prefix="/workflows")
router.include_router(scheduling_router, prefix="/workflows")
