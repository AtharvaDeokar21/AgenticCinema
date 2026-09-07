"""
API routes for Phase 2 & 5: Chat and Compliance Approval
Phase 5: approve and pending endpoints now read/write from SQLite DB.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uuid

from app.orchestration.chat_router import ChatIntentRouter
from app.persistence.repository import (
    ProjectRepository,
    JobRepository,
    ComplianceCheckpointRepository,
)

router = APIRouter(prefix="/projects", tags=["projects"])

chat_router = ChatIntentRouter()


class ChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None


class ApprovalRequest(BaseModel):
    checkpoint_id: str
    decisions: List[Dict[str, Any]] = []


@router.post("/{project_id}/chat")
async def chat(project_id: str, req: ChatRequest):
    """Chat endpoint — parse message and route to workflow action."""
    project = await ProjectRepository.load(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    intent, action_params, response = await chat_router.route(
        req.message,
        project_data={
            "script": project.script,
            "storyboard": project.storyboard,
            "audio": project.audio_master,
            "dub_tracks": project.dub_tracks,
        },
    )

    # If the intent maps to a stage invocation, queue the job
    job_id = None
    if action_params.get("type") == "invoke_stage":
        stage_name = action_params.get("stage", "")
        from datetime import datetime
        job_id = str(uuid.uuid4())
        job = {
            "job_id": job_id,
            "project_id": project_id,
            "stage": stage_name,
            "status": "queued",
            "progress": 0.0,
            "phase": None,
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "result": None,
            "error": None,
        }
        await JobRepository.save(job)

    return {
        "message_id": str(uuid.uuid4())[:8],
        "intent": intent.value,
        "action": action_params,
        "response": response,
        "job_id": job_id,
    }


@router.post("/{project_id}/approve")
async def approve_compliance(project_id: str, req: ApprovalRequest):
    """
    Phase 5: Approve a YELLOW compliance checkpoint and unblock downstream stages.
    Updates the SQLite DB — the worker will pick up blocked jobs on its next poll.
    """
    project = await ProjectRepository.load(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Approve in the DB (replaces the old in-memory approach)
    success = await ComplianceCheckpointRepository.approve(
        req.checkpoint_id,
        req.decisions,
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail="Checkpoint not found or already approved",
        )

    return {
        "project_id": project_id,
        "checkpoint_id": req.checkpoint_id,
        "status": "approved",
        "message": "Checkpoint approved. Blocked jobs will resume within a few seconds.",
    }


@router.get("/{project_id}/compliance/pending")
async def get_pending_approvals(project_id: str):
    """
    Phase 5: Get all pending YELLOW compliance checkpoints for a project.
    Reads from SQLite — survives server restarts.
    """
    project = await ProjectRepository.load(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    pending = await ComplianceCheckpointRepository.get_pending(project_id)

    return {
        "project_id": project_id,
        "pending_approvals": [
            {
                "checkpoint_id": cp["checkpoint_id"],
                "stage": cp["stage"],
                "status": cp["status"],
                "created_at": cp["created_at"],
                "report_summary": (
                    f"Compliance check for {cp['stage']} requires approval"
                ),
            }
            for cp in pending
        ],
    }


@router.get("/{project_id}/compliance/history")
async def get_compliance_history(project_id: str):
    """Get all compliance checkpoints for a project (audit trail)."""
    project = await ProjectRepository.load(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    all_checkpoints = await ComplianceCheckpointRepository.get_all_for_project(project_id)

    return {
        "project_id": project_id,
        "checkpoints": [
            {
                "checkpoint_id": cp["checkpoint_id"],
                "stage": cp["stage"],
                "status": cp["status"],
                "created_at": cp["created_at"],
                "approved_at": cp["approved_at"],
            }
            for cp in all_checkpoints
        ],
    }
