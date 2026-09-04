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