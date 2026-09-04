from typing import List, Optional

from pydantic import BaseModel, Field


class DubSegment(BaseModel):
    segment_id: str

    source_text: str

    localized_text: str

    language: str

    geography: Optional[str] = None

    cultural_notes: List[str] = Field(default_factory=list)

    audio_path: Optional[str] = None


class DubTrack(BaseModel):
    language: str

    geography: str

    segments: List[DubSegment] = Field(default_factory=list)

    audio_path: Optional[str] = None

    subtitle_path: Optional[str] = None