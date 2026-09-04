"""
Shared compliance contracts.

SHARED MODEL CHANGE (Rule 3) — coordinate before merging.

Changes from the previous version:
  - `severity: str`          -> `severity: ClearanceStatus`   (green/yellow/red/unverified)
  - `category: str`          -> `kind: AssetKind`
  - `evidence: List[str]`    -> `List[EvidenceRef]`  (claim -> source, not a bare URL list)
  - `ClearanceReport.status` -> `ReportStatus` enum, so the gate rule is enforceable in code
  - `checked_assets`         -> `List[TrackedAsset]`, the running ledger carried across all six passes
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ClearanceStatus(str, Enum):
    """The traffic light for a single asset."""

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    # Not a clearance opinion. Means: we could not verify this, and we are
    # saying so rather than guessing. Never treat UNVERIFIED as GREEN.
    UNVERIFIED = "unverified"


class ReportStatus(str, Enum):
    """The gate decision for one pass of the pipeline."""

    PASSED = "passed"
    PASSED_WITH_CONDITIONS = "passed_with_conditions"
    BLOCKED = "blocked"
    # Tools failed or returned nothing usable. The pipeline should not treat
    # this as a pass.
    DEGRADED = "degraded"


class AssetKind(str, Enum):
    MUSIC = "music"
    BRAND = "brand"
    PERSON = "person"
    LOCATION = "location"
    STOCK_MEDIA = "stock_media"
    GENERATED_IMAGE = "generated_image"
    TRADEMARK_PHRASE = "trademark_phrase"
    CLAIM = "claim"
    DEAL_TERM = "deal_term"
    BACKGROUND_AUDIO = "background_audio"
    VOICE_CONSENT = "voice_consent"
    DISCLOSURE = "disclosure"
    OTHER = "other"


class EvidenceRef(BaseModel):
    """
    A single claim bound to the source that supports it.

    The application populates `url`, `title` and `excerpt` from real research
    results. The model is never allowed to write a URL directly.
    """

    claim: str

    url: str

    title: Optional[str] = None

    excerpt: Optional[str] = None

    retrieved_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class TrackedAsset(BaseModel):
    """
    One entry in the running asset list. ClearanceCheck appends to this as the
    pipeline moves, so a track cleared after Script is not re-researched after
    Audio.
    """

    asset_key: str  # normalised dedup key, e.g. "music::midnight city|m83"

    kind: AssetKind

    label: str  # human-readable, e.g. "Midnight City — M83"

    first_seen_stage: str

    status: ClearanceStatus = ClearanceStatus.UNVERIFIED

    last_checked_at: Optional[datetime] = None


class ComplianceIssue(BaseModel):
    issue_id: str

    asset_key: Optional[str] = None

    label: str = ""  # the asset itself, e.g. "Midnight City — M83"

    kind: AssetKind = AssetKind.OTHER

    severity: ClearanceStatus

    description: str

    recommended_action: Optional[str] = None

    # A red without a substitute just blocks the creator.
    substitutes: List[str] = Field(default_factory=list)

    evidence: List[EvidenceRef] = Field(default_factory=list)

    @property
    def blocking(self) -> bool:
        return self.severity is ClearanceStatus.RED


class ClearanceReport(BaseModel):
    status: ReportStatus

    stage: str  # the stage that just finished, e.g. "storyboard"

    pass_number: int = 1  # 1..6

    issues: List[ComplianceIssue] = Field(default_factory=list)

    checked_assets: List[TrackedAsset] = Field(default_factory=list)

    # Deterministic schema / cross-reference failures. Milliseconds to compute,
    # and they are bugs rather than rights problems, so they are kept separate.
    structural_errors: List[str] = Field(default_factory=list)

    # Why the run was degraded, if it was. e.g. "Parallel Extract unavailable".
    degraded_reasons: List[str] = Field(default_factory=list)

    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def reds(self) -> List[ComplianceIssue]:
        return [i for i in self.issues if i.severity is ClearanceStatus.RED]

    @property
    def yellows(self) -> List[ComplianceIssue]:
        return [i for i in self.issues if i.severity is ClearanceStatus.YELLOW]

    @property
    def blocks_pipeline(self) -> bool:
        return self.status in (ReportStatus.BLOCKED, ReportStatus.DEGRADED)