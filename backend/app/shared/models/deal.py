from pydantic import BaseModel
from typing import List, Optional


class DealContext(BaseModel):
    brand_name: Optional[str] = None

    campaign_name: Optional[str] = None

    campaign_objective: Optional[str] = None

    target_audience: Optional[str] = None

    target_geographies: List[str] = []

    target_languages: List[str] = []

    budget_range: Optional[str] = None

    mandatory_requirements: List[str] = []

    restrictions: List[str] = []