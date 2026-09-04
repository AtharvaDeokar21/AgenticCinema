from typing import List, Optional

from pydantic import BaseModel, Field


class SyncSegment(BaseModel):
    segment_id: str

    video_start: float

    video_end: float

    audio_start: float

    audio_end: float

    offset: float

    confidence: float

    recommended_take: Optional[str] = None


class SyncReport(BaseModel):
    status: str

    global_offset: Optional[float] = None

    drift_detected: bool = False

    drift_rate: Optional[float] = None

    segments: List[SyncSegment] = Field(default_factory=list)

    fallback_used: bool = False

    notes: List[str] = Field(default_factory=list)