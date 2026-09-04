from typing import List, Optional

from pydantic import BaseModel, Field


class ResearchSource(BaseModel):
    title: str
    url: str
    excerpts: List[str] = Field(default_factory=list)
    publish_date: Optional[str] = None


class ResearchResult(BaseModel):
    query: str
    sources: List[ResearchSource] = Field(default_factory=list)