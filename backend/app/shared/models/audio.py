from typing import List, Optional

from pydantic import BaseModel, Field


class TranscriptWord(BaseModel):
    word: str

    start_time: float

    end_time: float

    confidence: Optional[float] = None


class AudioSegment(BaseModel):
    segment_id: str

    start_time: float

    end_time: float

    transcript: str

    words: List[TranscriptWord] = Field(default_factory=list)


class AudioMaster(BaseModel):
    file_path: Optional[str] = None

    duration: Optional[float] = None

    sample_rate: Optional[int] = None

    channels: Optional[int] = None

    segments: List[AudioSegment] = Field(default_factory=list)

    cleaned: bool = False

    synced: bool = False