"""
Compliance Decorator - Cross-cutting checkpoint
Runs after each stage completes to verify outputs
Handles GREEN/YELLOW/RED blocking
"""
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime

from ..shared.models.compliance import ClearanceReport, ReportStatus


class ComplianceCheckpointStatus(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class ComplianceCheckpoint:
    """Represents a compliance check at a stage"""

    def __init__(
        self,
        checkpoint_id: str,
        stage: str,
        report: ClearanceReport,
        status: ComplianceCheckpointStatus,
    ):
        self.checkpoint_id = checkpoint_id
        self.stage = stage
        self.report = report
        self.status = status
        self.created_at = datetime.utcnow().isoformat()
        self.approved_at: Optional[str] = None
        self.approval_decisions: List[Dict[str, Any]] = []

    def approve(self, decisions: List[Dict[str, Any]]):
        """Approve YELLOW issues and unblock downstream stages"""
        self.approved_at = datetime.utcnow().isoformat()
        self.approval_decisions = decisions
        self.status = ComplianceCheckpointStatus.GREEN


class ComplianceDecorator:
    """
    Cross-cutting compliance checkpoint.
    Runs after specified stages complete.
    """

    # Stages that trigger compliance checks
    COMPLIANCE_STAGES = {
        "SCRIPT",
        "STORYBOARD",
        "AUDIO_AI",
        "AUDIO_CREATOR",
        "DUBBING",
    }

    def __init__(self, compliance_agent):
        self.agent = compliance_agent
        self.checkpoints: Dict[str, ComplianceCheckpoint] = {}

    async def check(
        self,
        stage: str,
        project_data: Dict[str, Any],
    ) -> ComplianceCheckpoint:
        """
        Run compliance check after stage completion.
        Returns checkpoint with GREEN/YELLOW/RED status.
        """

        if stage not in self.COMPLIANCE_STAGES:
            # No compliance needed for this stage
            return None

        try:
            # Build compliance request from stage output
            compliance_request = self._build_request(stage, project_data)

            # Run compliance agent
            report = await self.agent.run(compliance_request)

            # Create checkpoint
            checkpoint_id = f"checkpoint_{stage}_{datetime.utcnow().timestamp()}"
            
            if report.status == ReportStatus.PASSED:
                status = ComplianceCheckpointStatus.GREEN
            elif report.status == ReportStatus.PASSED_WITH_CONDITIONS:
                status = ComplianceCheckpointStatus.YELLOW
            else:
                status = ComplianceCheckpointStatus.RED

            checkpoint = ComplianceCheckpoint(
                checkpoint_id=checkpoint_id,
                stage=stage,
                report=report,
                status=status,
            )

            self.checkpoints[checkpoint_id] = checkpoint
            return checkpoint

        except Exception as e:
            # If compliance check fails, default to proceed (don't block)
            print(f"⚠ Compliance check failed for {stage}: {e}")
            return None

    def _build_request(self, stage: str, project_data: Dict[str, Any]):
        """Build ComplianceRequest from project data"""
        from app.agents.compliance.schemas import ComplianceRequest
        from app.shared.models.stages import ProjectStage
        import json

        payload_dict = {}

        # Extract relevant data based on stage
        if stage == "SCRIPT" and "script" in project_data:
            payload_dict = {
                "script_text": project_data["script"].full_text[:500]
                if hasattr(project_data["script"], "full_text")
                else "Script content"
            }

        elif stage == "STORYBOARD" and "storyboard" in project_data:
            payload_dict = {
                "num_shots": len(project_data["storyboard"].shots)
                if hasattr(project_data["storyboard"], "shots")
                else 0
            }

        elif stage in ("AUDIO_AI", "AUDIO_CREATOR") and "audio" in project_data:
            payload_dict = {
                "audio_segments": len(
                    project_data["audio"].segments
                    if hasattr(project_data["audio"], "segments")
                    else []
                )
            }

        elif stage == "DUBBING" and "dub_tracks" in project_data:
            payload_dict = {
                "dub_locales": len(project_data.get("dub_tracks", []))
            }

        try:
            stage_enum = ProjectStage(stage)
        except Exception:
            stage_enum = ProjectStage.SCRIPT

        return ComplianceRequest(
            project_id=project_data.get("project_id", "demo_project"),
            stage=stage_enum,
            payload=json.dumps(payload_dict),
            prior_assets=[],
        )

    def is_blocked(self, stage: str, project_data: Dict[str, Any]) -> bool:
        """Check if stage is blocked by compliance RED"""
        # Find most recent checkpoint for any completed stage
        for checkpoint in self.checkpoints.values():
            if checkpoint.status == ComplianceCheckpointStatus.RED:
                # RED blocks all downstream stages
                return True

        return False

    def get_approval_required(self) -> Optional[ComplianceCheckpoint]:
        """Get pending approval checkpoint if any"""
        for checkpoint in self.checkpoints.values():
            if (
                checkpoint.status == ComplianceCheckpointStatus.YELLOW
                and not checkpoint.approved_at
            ):
                return checkpoint
        return None

    def approve_checkpoint(
        self,
        checkpoint_id: str,
        decisions: List[Dict[str, Any]],
    ) -> bool:
        """Approve a YELLOW checkpoint"""
        checkpoint = self.checkpoints.get(checkpoint_id)
        if not checkpoint:
            return False

        checkpoint.approve(decisions)
        return True
