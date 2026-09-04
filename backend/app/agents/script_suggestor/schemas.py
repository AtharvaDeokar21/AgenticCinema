from typing import List, Optional

from pydantic import BaseModel, Field


class ScriptRequest(BaseModel):
    """Input provided to the Script Suggestor Agent."""

    brief: str = Field(
        ...,
        description="The creator's description or idea for the content.",
    )

    target_audience: Optional[str] = None

    genre: Optional[str] = None

    tone: Optional[str] = None

    language: Optional[str] = None

    duration_seconds: Optional[float] = None

    research_required: bool = True

    research_queries: List[str] = Field(
        default_factory=list
    )