"""
API routes for Phase 2: Chat and Compliance Approval
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uuid

from ..orchestration.chat_router import ChatIntentRouter
from ..orchestration.compliance_decorator import ComplianceDecorator
from ..persistence.repository import ProjectRepository
from ..agents.compliance.agent import ComplianceAgent

router = APIRouter(prefix="/projects", tags=["projects"])

# Initialize routers
chat_router = ChatIntentRouter()
compliance_agent = ComplianceAgent()
compliance_decorator = ComplianceDecorator(compliance_agent)


class ChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None


class ApprovalRequest(BaseModel):
    checkpoint_id: str
    decisions: List[Dict[str, Any]] = []


@router.post("/{project_id}/chat")
async def chat(project_id: str, req: ChatRequest):
    """Chat endpoint - parse message and route to workflow action"""
    project = await ProjectRepository.load(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Route the chat message
    intent, action_params, response = await chat_router.route(
        req.message,
        project_data={
            "script": project.script,
            "storyboard": project.storyboard,
            "audio": project.audio_master,
            "dub_tracks": project.dub_tracks,
        },
    )

    # Execute the action if it's a stage invocation
    job_id = None
    if action_params.get("type") == "invoke_stage":
        # TODO: Queue the stage for execution
        job_id = str(uuid.uuid4())[:12]

    return {
        "message_id": str(uuid.uuid4())[:8],
        "intent": intent.value,
        "action": action_params,
        "response": response,
        "job_id": job_id,
    }


@router.post("/{project_id}/approve")
async def approve_compliance(project_id: str, req: ApprovalRequest):
    """Approve compliance checkpoint and unblock downstream stages"""
    project = await ProjectRepository.load(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Approve the checkpoint
    success = compliance_decorator.approve_checkpoint(
        req.checkpoint_id,
        req.decisions,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Checkpoint not found")

    # Determine next ready stages
    ready_stages = []  # TODO: Calculate from DAG

    return {
        "project_id": project_id,
        "checkpoint_id": req.checkpoint_id,
        "status": "approved",
        "unblocked_stages": ready_stages,
    }


@router.get("/{project_id}/compliance/pending")
async def get_pending_approvals(project_id: str):
    """Get pending compliance approvals"""
    project = await ProjectRepository.load(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get pending checkpoint
    pending = compliance_decorator.get_approval_required()

    if not pending:
        return {"project_id": project_id, "pending_approvals": []}

    return {
        "project_id": project_id,
        "pending_approvals": [
            {
                "checkpoint_id": pending.checkpoint_id,
                "stage": pending.stage,
                "status": pending.status.value,
                "issues": [
                    {
                        "issue_id": issue.issue_id,
                        "severity": issue.severity.value,
                        "description": issue.description,
                    }
                    for issue in pending.report.issues
                ],
                "created_at": pending.created_at,
            }
        ],
    }
