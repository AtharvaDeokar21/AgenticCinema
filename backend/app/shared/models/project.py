from typing import List, Optional

from pydantic import BaseModel, Field
from datetime import datetime, timezone

from .creator import CreatorProfile
from .deal import DealContext
from .script import ScriptVersion
from .storyboard import ShotPlan
from .media import MediaManifest
from .sync import SyncReport
from .audio import AudioMaster
from .dub import DubTrack
from .compliance import ClearanceReport
from .creator_scout import CreatorRecommendation
from .stages import ProjectStage


class WorkflowConfig(BaseModel):
    """Workflow configuration for a project"""
    audio_mode: str = "AI_VOICE"  # AI_VOICE or CREATOR_VOICE
    enable_creator_scout: bool = False
    target_locales: List[str] = Field(default_factory=list)
    request_approval_for_yellow: bool = True


class ProjectState(BaseModel):
    project_id: str

    project_name: str

    creator_profile: Optional[CreatorProfile] = None

    deal_context: Optional[DealContext] = None

    script: Optional[ScriptVersion] = None

    storyboard: Optional[ShotPlan] = None

    media_manifest: Optional[MediaManifest] = None

    sync_report: Optional[SyncReport] = None

    audio_master: Optional[AudioMaster] = None

    dub_tracks: List[DubTrack] = Field(default_factory=list)

    clearance_report: Optional[ClearanceReport] = None

    creator_recommendations: List[CreatorRecommendation] = Field(
        default_factory=list
    )

    current_stage: ProjectStage = ProjectStage.CREATED

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    errors: List[str] = Field(default_factory=list)

    # New fields for DAG-based execution
    completed_stages: List[str] = Field(default_factory=list)
    blocked_stages: List[str] = Field(default_factory=list)
    workflow_config: WorkflowConfig = Field(default_factory=WorkflowConfig)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    version: int = 1