from enum import Enum
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.shared.models.audio import AudioMaster
from app.shared.models.project import ProjectState


class AudioInputMode(str, Enum):
    """Entry path selected by the creator for the Audio stage."""

    CREATOR_VOICE = "creator_voice"
    AI_VOICE = "ai_voice"


class AudioRequest(BaseModel):
    """Input contract for the Audio Agent.

    The uploaded source video is staged under the repository root's ``data``
    directory. ``project_state`` supplies the upstream script/storyboard/sync
    information already accumulated by the pipeline.
    """

    mode: AudioInputMode
    video_path: str
    project_state: ProjectState

    @field_validator("video_path")
    @classmethod
    def validate_video_path(cls, value: str) -> str:
        path = Path(value)
        if not path.is_absolute():
            raise ValueError("video_path must be an absolute path to the staged video")
        return str(path)


class SegmentDecision(str, Enum):
    PASS = "PASS"
    PASS_WITH_FIX = "PASS_WITH_FIX"
    RE_RECORD = "RE_RECORD"


class SegmentAnalysis(BaseModel):
    """Gemini's comparison of one recorded segment against the script."""

    segment_id: str
    decision: SegmentDecision
    reason: str
    expected_expression: Optional[str] = None
    observed_delivery: Optional[str] = None
    missing: bool = False
    out_of_order: bool = False
    ad_lib: bool = False
    timing_issue: bool = False
    mic_distance_issue: bool = False


class SegmentAnalysisReport(BaseModel):
    """Structured report returned to the creator for creator-voice input."""

    status: str = "complete"
    segments: List[SegmentAnalysis] = Field(default_factory=list)
    overall_summary: str = ""


class GeneratedAudioSegment(BaseModel):
    """Result of generating one script beat."""

    beat_id: str
    start_time: float
    end_time: float
    generated_duration: float
    within_slot: bool
    pacing_adjusted: bool = False
    rewrite_required: bool = False
    file_path: str


class AudioResult(BaseModel):
    """Audio-stage result plus the updated shared project state."""

    mode: AudioInputMode
    status: str
    source_video_path: str
    extracted_audio_path: Optional[str] = None
    generated_audio_path: Optional[str] = None
    cleaned_audio_path: Optional[str] = None
    segment_analysis: Optional[SegmentAnalysisReport] = None
    rewrite_required_beat_ids: List[str] = Field(default_factory=list)
    audio_master: Optional[AudioMaster] = None
    generated_segments: List[GeneratedAudioSegment] = Field(default_factory=list)
    project_state: ProjectState
