from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from api.v1.workflows.schemas import (
    AIEditWorkflowRequest,
    GeneratedInstructionResponse,
    GenerateAgentInstructionsRequest,
    ImproveAgentInstructionsRequest,
    WorkflowDetailResponse,
)
from libs.database.repositories import WorkflowRepository
from libs.database.session import get_db
from libs.langchain.chains.agent_chain import AgentChain
from libs.langchain.chains.workflow_chain import WorkflowChain
from libs.langchain.provider import BaseAIProvider
from core.request_provider import get_request_provider
from libs.langchain.chains.main_chain import enrich_workflow_prompts

logger = logging.getLogger(__name__)
editing_router = APIRouter()


@editing_router.post("/{workflow_id}/ai-edit", response_model=WorkflowDetailResponse)
async def ai_edit_workflow(
    workflow_id: str,
    payload: AIEditWorkflowRequest,
    db: Session = Depends(get_db),
    provider: BaseAIProvider = Depends(get_request_provider),
) -> WorkflowDetailResponse:
    """Modify existing workflow structure with natural language instructions."""
    repo = WorkflowRepository(db)
    workflow = repo.get_by_id(workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID '{workflow_id}' not found.",
        )

    try:
        chain = WorkflowChain(provider=provider)
        updated_workflow = await chain.edit_workflow(
            current_workflow=workflow, instruction=payload.instruction
        )
        updated_workflow = await enrich_workflow_prompts(provider, updated_workflow)
        saved = repo.update(updated_workflow)
        return WorkflowDetailResponse(workflow=saved or updated_workflow)
    except Exception as exc:
        logger.error("Failed to AI-edit workflow: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update workflow with AI. Please try again.",
        )


@editing_router.post(
    "/{workflow_id}/nodes/{node_id}/generate", response_model=GeneratedInstructionResponse
)
async def generate_node_instructions(
    workflow_id: str,
    node_id: str,
    payload: GenerateAgentInstructionsRequest,
    db: Session = Depends(get_db),
    provider: BaseAIProvider = Depends(get_request_provider),
) -> GeneratedInstructionResponse:
    """Generate comprehensive execution instructions for a specific agent node."""
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
            detail=f"Node '{node_id}' not found in workflow.",
        )

    try:
        agent_chain = AgentChain(provider=provider)
        instructions = await agent_chain.generate_instructions(
            workflow=workflow,
            node=target_node,
            user_hint=payload.user_hint,
        )
        return GeneratedInstructionResponse(instructions=instructions)
    except Exception as exc:
        logger.error("Failed to generate instructions: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate agent instructions.",
        )


@editing_router.post(
    "/{workflow_id}/nodes/{node_id}/improve", response_model=GeneratedInstructionResponse
)
async def improve_node_instructions(
    workflow_id: str,
    node_id: str,
    payload: ImproveAgentInstructionsRequest,
    db: Session = Depends(get_db),
    provider: BaseAIProvider = Depends(get_request_provider),
) -> GeneratedInstructionResponse:
    """Improve existing instructions based on user feedback."""
    repo = WorkflowRepository(db)
    workflow = repo.get_by_id(workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID '{workflow_id}' not found.",
        )

    try:
        agent_chain = AgentChain(provider=provider)
        instructions = await agent_chain.improve_instructions(
            current_instructions=payload.current_instructions,
            user_feedback=payload.user_feedback,
        )
        return GeneratedInstructionResponse(instructions=instructions)
    except Exception as exc:
        logger.error("Failed to improve instructions: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to improve agent instructions.",
        )
