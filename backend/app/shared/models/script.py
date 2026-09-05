from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ScriptBeat(BaseModel):
    beat_id: str

    start_time: float

    end_time: float

    text: str

    purpose: Optional[str] = None

    visual_intent: Optional[str] = None

    audio_intent: Optional[str] = None

    expression: Optional[str] = None


class ScriptVersion(BaseModel):
    version: int

    created_at: datetime

    title: Optional[str] = None

    hook: Optional[str] = None

    full_text: str

    beats: List[ScriptBeat] = Field(default_factory=list)

    evidence: List[str] = Field(default_factory=list)

    status: str = "draft"
