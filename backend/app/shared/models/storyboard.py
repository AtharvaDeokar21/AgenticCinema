from typing import List, Optional

from pydantic import BaseModel, Field


class Shot(BaseModel):
    shot_id: str
    beat_id: str

    start_time: float
    end_time: float

    shot_type: Optional[str] = None
    camera_angle: Optional[str] = None
    camera_movement: Optional[str] = None
    framing: Optional[str] = None

    subject: Optional[str] = None
    background: Optional[str] = None
    lighting: Optional[str] = None

    visual_description: Optional[str] = None

    colour_palette: List[str] = Field(default_factory=list)

    on_screen_text: Optional[str] = None
    mood: Optional[str] = None

    reference_images: List[str] = Field(default_factory=list)
    generated_image: Optional[str] = None


class ShotPlan(BaseModel):
    version: int

    shots: List[Shot] = Field(default_factory=list)

    visual_style: Optional[str] = None
    color_palette: Optional[str] = None

    evidence: List[str] = Field(default_factory=list)