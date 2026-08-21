from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from api.v1.workflows.schemas import CreateWorkflowFromTextRequest, WorkflowDetailResponse
from libs.database.repositories import WorkflowRepository
from libs.database.session import get_db
from libs.langchain.chains.workflow_chain import WorkflowChain
from libs.langchain.provider import BaseAIProvider
from core.request_provider import get_request_provider

logger = logging.getLogger(__name__)
creation_router = APIRouter()


@creation_router.post("/from-text", response_model=WorkflowDetailResponse)
async def create_workflow_from_text(
    payload: CreateWorkflowFromTextRequest,
    db: Session = Depends(get_db),
    provider: BaseAIProvider = Depends(get_request_provider),
) -> WorkflowDetailResponse:
    """Convert natural language description into structured multi-agent workflow."""
    if not payload.text or not payload.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workflow description cannot be empty.",
        )

    try:
        chain = WorkflowChain(provider=provider)
        workflow = await chain.generate_from_text(payload.text.strip())
        repo = WorkflowRepository(db)
        saved = repo.save(workflow)
        return WorkflowDetailResponse(workflow=saved)
    except Exception as exc:
        logger.error("Failed to generate workflow from text: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate workflow. Please try again.",
        )
