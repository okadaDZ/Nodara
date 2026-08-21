from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from api.v1.workflows.schemas import ImageWorkflowJobCreated, ImageWorkflowJobStatus, ImageWorkflowResponse
from libs.database.repositories import WorkflowRepository
from libs.database.session import get_db
from libs.langchain.chains.vision_chain import VisionChain
from libs.langchain.provider import BaseAIProvider
from core.request_provider import get_request_provider
from libs.langchain.chains.main_chain import CreatorPipelineResult, InvalidSchemeError

logger = logging.getLogger(__name__)
vision_router = APIRouter()


@dataclass
class _ImageJob:
    stage: str = "queued"
    status: str = "processing"
    result: CreatorPipelineResult | None = None
    saved_result: ImageWorkflowResponse | None = None
    error: str | None = None


_image_jobs: dict[str, _ImageJob] = {}
_image_tasks: set[asyncio.Task[None]] = set()


async def _process_image_job(
    job_id: str,
    image_bytes: bytes,
    mime_type: str,
    provider: BaseAIProvider,
) -> None:
    job = _image_jobs[job_id]
    try:
        chain = VisionChain(provider=provider)
        job.result = await chain.analyze_diagram_with_review(
            image_bytes=image_bytes,
            mime_type=mime_type,
            on_progress=lambda stage_name: setattr(job, "stage", stage_name),
        )
        job.stage = "complete"
        job.status = "completed"
    except InvalidSchemeError as exc:
        job.stage = "validate_image"
        job.status = "failed"
        job.error = str(exc)
    except Exception as exc:
        logger.error("Vision workflow job failed: %s", exc, exc_info=True)
        job.status = "failed"
        job.error = "Failed to analyze workflow diagram photo."


@vision_router.post("/workflows/from-image/jobs", response_model=ImageWorkflowJobCreated, status_code=status.HTTP_202_ACCEPTED)
async def start_workflow_from_image_job(
    image: UploadFile = File(...),
    provider: BaseAIProvider = Depends(get_request_provider),
) -> ImageWorkflowJobCreated:
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty image uploaded.")
    job_id = uuid.uuid4().hex
    _image_jobs[job_id] = _ImageJob()
    task = asyncio.create_task(_process_image_job(
        job_id, image_bytes, image.content_type or "image/jpeg", provider
    ))
    _image_tasks.add(task)
    task.add_done_callback(_image_tasks.discard)
    return ImageWorkflowJobCreated(job_id=job_id)


@vision_router.get("/workflows/from-image/jobs/{job_id}", response_model=ImageWorkflowJobStatus)
async def get_workflow_from_image_job(job_id: str, db: Session = Depends(get_db)) -> ImageWorkflowJobStatus:
    job = _image_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image processing job not found.")
    if job.status == "completed" and job.result and not job.saved_result:
        saved = WorkflowRepository(db).save(job.result.workflow)
        job.saved_result = ImageWorkflowResponse(workflow=saved, analysis=job.result.analysis)
    return ImageWorkflowJobStatus(
        job_id=job_id,
        status=job.status,
        stage=job.stage,
        result=job.saved_result,
        error=job.error,
    )


@vision_router.post("/workflows/from-image", response_model=ImageWorkflowResponse)
async def create_workflow_from_image(
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    provider: BaseAIProvider = Depends(get_request_provider),
) -> ImageWorkflowResponse:
    """Analyze photograph of hand-drawn workflow diagram and convert into workflow JSON."""
    try:
        image_bytes = await image.read()
        if not image_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty image uploaded.",
            )

        chain = VisionChain(provider=provider)
        result = await chain.analyze_diagram_with_review(
            image_bytes=image_bytes,
            mime_type=image.content_type or "image/jpeg",
        )

        repo = WorkflowRepository(db)
        saved = repo.save(result.workflow)

        return ImageWorkflowResponse(workflow=saved, analysis=result.analysis)
    except InvalidSchemeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Vision workflow creation failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to analyze workflow diagram photo.",
        )
