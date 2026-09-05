from typing import List, Optional

from pydantic import BaseModel, Field
from app.shared.models.storyboard import ShotPlan

class ProductionConstraints(BaseModel):
    """
    What the creator can realistically use during production.
    """

    cameras: List[str] = Field(default_factory=list)
    lenses: List[str] = Field(default_factory=list)
    lights: List[str] = Field(default_factory=list)
    support: List[str] = Field(default_factory=list)

    location: Optional[str] = None
    operator: Optional[str] = None

    platform: Optional[str] = None
    aspect_ratio: Optional[str] = None

    brand_guidelines: Optional[str] = None

    constraints: List[str] = Field(default_factory=list)


class CreatorStyleContext(BaseModel):
    """
    Optional context describing the creator's existing visual identity.
    """

    recent_thumbnails: List[str] = Field(default_factory=list)
    recent_stills: List[str] = Field(default_factory=list)

    style_notes: Optional[str] = None


class VisualReferenceAnalysis(BaseModel):
    """
    Structured observation of a reference frame or clip.

    These are observations of what is present in the reference,
    not recommendations.
    """

    reference_url: Optional[str] = None

    shot_size: Optional[str] = None
    camera_angle: Optional[str] = None
    subject_placement: Optional[str] = None
    background: Optional[str] = None
    lighting: Optional[str] = None

    colour_palette: List[str] = Field(default_factory=list)

    movement: Optional[str] = None
    on_screen_text: Optional[str] = None
    mood: Optional[str] = None


class VisualGrammar(BaseModel):
    """
    Aggregated visual patterns observed across references.
    """

    framing_patterns: List[str] = Field(default_factory=list)
    camera_patterns: List[str] = Field(default_factory=list)
    movement_patterns: List[str] = Field(default_factory=list)
    lighting_patterns: List[str] = Field(default_factory=list)
    colour_patterns: List[str] = Field(default_factory=list)
    pacing_patterns: List[str] = Field(default_factory=list)
    text_patterns: List[str] = Field(default_factory=list)

    summary: Optional[str] = None

    evidence: List[str] = Field(default_factory=list)

class ReferenceFrame(BaseModel):
    """
    Representative frame extracted from a reference video.
    """

    path: str
    timestamp: float
    shot_index: int


class ReferenceMediaResult(BaseModel):
    """
    Media-processing result for a storyboard reference.
    """

    reference_url: str

    local_path: Optional[str] = None
    processed_path: Optional[str] = None

    duration: Optional[float] = None
    was_vfr: bool = False

    frames: List[ReferenceFrame] = Field(
        default_factory=list
    )

    error: Optional[str] = None


class StoryboardReference(BaseModel):
    title: str
    url: str
    excerpts: list[str] = Field(default_factory=list)
    publish_date: Optional[str] = None
    content: Optional[str] = None

    media_path: Optional[str] = None
    frames: list[ReferenceFrame] = Field(default_factory=list)


class StoryboardReferenceResearch(BaseModel):
    query: str
    references: list[StoryboardReference] = Field(
        default_factory=list
    )

class ShotProductionPlan(BaseModel):
    shot_id: str

    camera: Optional[str] = None
    lens: Optional[str] = None
    support: Optional[str] = None
    lighting_setup: Optional[str] = None

    location_requirements: List[str] = Field(
        default_factory=list
    )

    equipment_required: List[str] = Field(
        default_factory=list
    )

    feasibility: str
    issues: List[str] = Field(
        default_factory=list
    )

    notes: Optional[str] = None

class ProductionAwareStoryboard(BaseModel):
    """
    Storyboard enhanced with production-aware planning.
    """

    storyboard: ShotPlan

    production_plans: List[ShotProductionPlan] = Field(
        default_factory=list
    )

    overall_issues: List[str] = Field(
        default_factory=list
    )