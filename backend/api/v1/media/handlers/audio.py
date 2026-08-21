from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from api.v1.workflows.schemas import AudioWorkflowResponse, GeneratedInstructionResponse
from libs.database.repositories import WorkflowRepository
from libs.database.session import get_db
from libs.langchain.chains.workflow_chain import WorkflowChain
from libs.langchain.provider import BaseAIProvider
from core.request_provider import get_request_provider

logger = logging.getLogger(__name__)
audio_router = APIRouter()


@audio_router.post("/workflows/from-audio", response_model=AudioWorkflowResponse)
async def create_workflow_from_audio(
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
    provider: BaseAIProvider = Depends(get_request_provider),
) -> AudioWorkflowResponse:
    """Transcribe spoken voice recording and convert into a multi-agent workflow."""
    try:
        audio_bytes = await audio.read()
        if not audio_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty audio recording.",
            )

        transcription = await provider.transcribe_audio(
            audio_bytes=audio_bytes,
            filename=audio.filename or "recording.m4a",
            mime_type=audio.content_type or "audio/m4a",
        )

        if not transcription or not transcription.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not transcribe audio.",
            )

        chain = WorkflowChain(provider=provider)
        workflow = await chain.generate_from_text(transcription)

        repo = WorkflowRepository(db)
        saved = repo.save(workflow)

        return AudioWorkflowResponse(transcription=transcription, workflow=saved)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Audio workflow creation failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process voice workflow.",
        )


@audio_router.post(
    "/workflows/{workflow_id}/nodes/{node_id}/audio-edit",
    response_model=GeneratedInstructionResponse,
)
async def edit_node_with_audio(
    workflow_id: str,
    node_id: str,
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
    provider: BaseAIProvider = Depends(get_request_provider),
) -> GeneratedInstructionResponse:
    """Update agent node instructions using spoken audio instructions."""
    repo = WorkflowRepository(db)
    workflow = repo.get_by_id(workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID '{workflow_id}' not found.",
        )

    target_node = next((n for n in workflow.nodes if n.id == node_id), None)
    if not target_node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node '{node_id}' not found.",
        )

    try:
        audio_bytes = await audio.read()
        transcription = await provider.transcribe_audio(
            audio_bytes=audio_bytes,
            filename=audio.filename or "recording.m4a",
            mime_type=audio.content_type or "audio/m4a",
        )

        from libs.langchain.chains.agent_chain import AgentChain

        agent_chain = AgentChain(provider=provider)
        new_instructions = await agent_chain.improve_instructions(
            current_instructions=target_node.instructions,
            user_feedback=f"User's spoken change: {transcription}",
        )

        target_node.instructions = new_instructions
        repo.update(workflow)

        return GeneratedInstructionResponse(instructions=new_instructions)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Audio edit node failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process audio edit.",
        )
