from typing import List, Optional

from pydantic import BaseModel, Field


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