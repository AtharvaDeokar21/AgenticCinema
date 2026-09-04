from typing import List, Optional

from pydantic import BaseModel, Field


class ComplianceIssue(BaseModel):
    issue_id: str

    category: str

    severity: str

    description: str

    evidence: List[str] = Field(default_factory=list)

    recommended_action: Optional[str] = None


class ClearanceReport(BaseModel):
    status: str

    stage: str

    issues: List[ComplianceIssue] = Field(default_factory=list)

    checked_assets: List[str] = Field(default_factory=list)

    evidence: List[str] = Field(default_factory=list)