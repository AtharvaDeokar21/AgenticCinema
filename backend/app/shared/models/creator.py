from pydantic import BaseModel, Field
from typing import List, Optional


class CreatorProfile(BaseModel):
    creator_id: str

    name: str

    platform: Optional[str] = None

    niche: Optional[str] = None

    audience_geographies: List[str] = Field(default_factory=list)

    audience_languages: List[str] = Field(default_factory=list)

    follower_count: Optional[int] = None

    engagement_rate: Optional[float] = None

    content_style: Optional[str] = None