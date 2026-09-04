from typing import List, Optional

from pydantic import BaseModel, Field


class CreatorRecommendation(BaseModel):
    creator_id: Optional[str] = None

    creator_name: str

    platform: Optional[str] = None

    niche: Optional[str] = None

    audience_fit: Optional[float] = None

    brand_fit: Optional[float] = None

    commercial_fit: Optional[float] = None

    overall_score: Optional[float] = None

    rationale: Optional[str] = None

    evidence: List[str] = Field(default_factory=list)