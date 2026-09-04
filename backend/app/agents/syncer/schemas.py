"""
Pydantic schemas for the Syncer Agent.

Defines the input and output contracts for Layer 3 of the
Agentic Cinema pipeline.  The agent accepts a silent video,
a list of script beats, and matched audio clips, then returns
a structured SyncMap — a placement guide telling the editor
exactly where to drop each audio clip on the video timeline.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from app.shared.models.script import ScriptBeat


# ---------------------------------------------------------------------------
# Input schemas
# ---------------------------------------------------------------------------


class AudioClip(BaseModel):
    """A single audio recording that corresponds to one script beat."""

    beat_id: str = Field(
        ...,
        description=(
            "The beat_id from the associated ScriptBeat. "
            "Used to correlate this clip with the correct script segment."
        ),
    )

    file_path: str = Field(
        ...,
        description="Absolute or relative path to the audio clip file.",
    )

    duration: Optional[float] = Field(
        default=None,
        description=(
            "Known duration of the clip in seconds. "
            "If None, the agent will probe it with ffprobe."
        ),
    )


class SyncRequest(BaseModel):
    """Input provided to the Syncer Agent."""

    video_path: str = Field(
        ...,
        description=(
            "Absolute or relative path to the silent video file. "
            "May be VFR — the agent will handle CFR conversion internally."
        ),
    )

    script_beats: List[ScriptBeat] = Field(
        ...,
        description=(
            "Ordered list of script beats produced by the Script Suggestor. "
            "Each beat carries the text the creator was meant to say and its "
            "expected start/end window in the final edit."
        ),
    )

    audio_clips: List[AudioClip] = Field(
        ...,
        description=(
            "One AudioClip per script beat, matched by beat_id. "
            "Clips are independent recordings assumed to follow the script."
        ),
    )

    target_fps: int = Field(
        default=30,
        description=(
            "CFR target used if the input video is detected as VFR. "
            "Defaults to 30 fps."
        ),
    )


# ---------------------------------------------------------------------------
# Output schemas
# ---------------------------------------------------------------------------


class AudioPlacement(BaseModel):
    """The computed placement for a single audio clip on the video timeline."""

    beat_id: str = Field(
        ...,
        description="The script beat this placement corresponds to.",
    )

    audio_clip_path: str = Field(
        ...,
        description="Path to the audio clip being placed.",
    )

    video_start_time: float = Field(
        ...,
        description=(
            "Timestamp in the video (seconds) where the clip should begin. "
            "Derived from the moment Gemini detects the creator's mouth "
            "beginning to move for this beat."
        ),
    )

    video_end_time: float = Field(
        ...,
        description=(
            "Timestamp in the video (seconds) where the clip should end. "
            "Typically video_start_time + audio clip duration."
        ),
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Gemini's confidence that this visual window corresponds to the "
            "correct script beat.  Values below 0.5 should be flagged for "
            "human review."
        ),
    )

    mouth_motion_detected: bool = Field(
        ...,
        description=(
            "True if Gemini observed clear lip/mouth movement at this "
            "timestamp.  False means the placement fell back to the script "
            "beat's expected start_time."
        ),
    )

    notes: Optional[str] = Field(
        default=None,
        description=(
            "Any caveats from Gemini — e.g. occluded face, quick cut, "
            "or beat text not visually identifiable."
        ),
    )


class SyncMap(BaseModel):
    """The complete output of the Syncer Agent.

    This document is the authoritative placement guide for the editing
    stage.  Every AudioPlacement tells the editor precisely where on the
    video timeline to place the corresponding audio clip.
    """

    status: str = Field(
        default="complete",
        description=(
            "Pipeline status: 'complete', 'partial' (some beats could not "
            "be placed), or 'failed'."
        ),
    )

    video_path: str = Field(
        ...,
        description=(
            "Path to the video that was actually analysed.  If the input was "
            "VFR and converted, this points to the CFR copy."
        ),
    )

    video_duration: float = Field(
        ...,
        description="Total duration of the analysed video in seconds.",
    )

    video_fps: float = Field(
        ...,
        description="Frame rate of the analysed video (post CFR-conversion if applied).",
    )

    was_vfr_converted: bool = Field(
        default=False,
        description=(
            "True if the original video was Variable Frame Rate and was "
            "re-encoded to CFR before analysis."
        ),
    )

    placements: List[AudioPlacement] = Field(
        default_factory=list,
        description="One AudioPlacement per input audio clip, in beat order.",
    )

    unplaced_beat_ids: List[str] = Field(
        default_factory=list,
        description=(
            "beat_ids for which no confident placement could be determined. "
            "These require manual sync."
        ),
    )

    notes: List[str] = Field(
        default_factory=list,
        description="Agent-level observations about the overall sync quality.",
    )
