from __future__ import annotations

from fastapi import APIRouter
from api.v1.media.handlers.audio import audio_router
from api.v1.media.handlers.vision import vision_router

router = APIRouter(tags=["Media"])
router.include_router(audio_router)
router.include_router(vision_router)
