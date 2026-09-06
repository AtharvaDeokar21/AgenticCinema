"""
Schemas for the CreatorScout agent.

`CreatorScoutRequest` is the public input contract. Everything below it is
internal: response schemas for the three Gemini calls.

Creator constraints (rate floor, exclusion list, capacity) live here rather
than in `shared/models/creator.py` because no other agent consumes them.
"""

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field

from app.shared.models.creator_scout import ExclusivityClause, WatchSignal


class PastDeal(BaseModel):
    brand_name: str
    category: Optional[str] = None
    fee: Optional[str] = None
    deliverables: List[str] = Field(default_factory=list)
    paid_on_time: Optional[bool] = None
    completed_on: Optional[date] = None


class CapacityWeek(BaseModel):
    week_starting: date
    committed_deliverables: int = 0
    capacity: int = 1

    @property
    def free_slots(self) -> int:
        return max(0, self.capacity - self.committed_deliverables)


class CreatorScoutRequest(BaseModel):
    creator_id: str

    creator_name: str

    # --- audience, ideally from connected analytics rather than intuition ---

    platforms: List[str] = Field(default_factory=list)

    niche: Optional[str] = None

    audience_summary: Optional[str] = Field(
        default=None,
        description=(
            "Age, gender, geography split. Concrete numbers make the ranking "
            "arguable; vague descriptions make it decorative."
        ),
    )

    median_views: Optional[int] = None

    engagement_rate: Optional[float] = None

    languages: List[str] = Field(default_factory=list)

    formats: List[str] = Field(default_factory=list)

    # --- commercial constraints ---

    categories_of_interest: List[str] = Field(default_factory=list)

    # Hard rule: anything in here is suppressed, with the reason shown.
    excluded_categories: List[str] = Field(default_factory=list)

    rate_floor: Optional[str] = None

    preferred_deal_structure: Optional[str] = None

    # Hard rule: an active clause suppresses its whole category.
    exclusivity_clauses: List[ExclusivityClause] = Field(default_factory=list)

    # Soft rule: a deadline that does not fit is flagged, not suppressed.
    capacity: List[CapacityWeek] = Field(default_factory=list)

    past_deals: List[PastDeal] = Field(default_factory=list)

    # --- run configuration ---

    target_geography: str = "India"

    lookback_days: int = 180

    max_candidates: int = 12

    # Always test a new query on the cheapest generator before spending on a
    # stronger one. Passed through to FindAll when it is available.
    findall_generator: str = "preview"

    as_of: Optional[date] = None


# ----------------------------------------------------------------------
# Internal: Gemini call 1 — candidate discovery from search results
# ----------------------------------------------------------------------


class BrandCandidate(BaseModel):
    brand_name: str

    category: Optional[str] = Field(
        default=None,
        description="Core product category, e.g. 'personal finance'.",
    )

    why_relevant: str = Field(
        description="One sentence tying this brand to the creator's niche."
    )

    spends_on_creators: bool = Field(
        description=(
            "True only if a source shows a sponsored creator collaboration, "
            "not merely that the company advertises."
        )
    )

    source_ids: List[str] = Field(
        default_factory=list,
        description="Source labels such as 'S2'. Never write a URL.",
    )


class DiscoveryResult(BaseModel):
    candidates: List[BrandCandidate] = Field(default_factory=list)


# ----------------------------------------------------------------------
# Internal: Gemini call 2 — enrichment
# ----------------------------------------------------------------------


class CitedClaim(BaseModel):
    claim: str
    source_id: str = Field(
        description="A source label such as 'S3'. Never write a URL."
    )


class EnrichmentRecord(BaseModel):
    brand_name: str

    has_creator_program: Optional[bool] = None

    program_url_source_id: Optional[str] = Field(
        default=None,
        description="Source label for the creator-program page, if one exists.",
    )

    booking_agency: Optional[str] = None

    recent_campaigns: List[str] = Field(default_factory=list)

    contact_route: Optional[str] = None

    typical_deliverables: Optional[str] = None

    exclusivity_practice: Optional[str] = None

    campaign_seasonality: Optional[str] = None

    cited_claims: List[CitedClaim] = Field(default_factory=list)


class EnrichmentResult(BaseModel):
    records: List[EnrichmentRecord] = Field(default_factory=list)


# ----------------------------------------------------------------------
# Internal: Gemini call 3 — ranking
# ----------------------------------------------------------------------


class RankedItem(BaseModel):
    brand_name: str

    rank: int

    rationale: str = Field(
        description=(
            "Prose the creator can argue with. Name the specific audience "
            "overlap, format match or timing signal."
        )
    )

    cautions: List[str] = Field(default_factory=list)

    audience_fit: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    brand_fit: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    commercial_fit: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    cited_claims: List[CitedClaim] = Field(default_factory=list)


class RankingResult(BaseModel):
    items: List[RankedItem] = Field(default_factory=list)


# ----------------------------------------------------------------------
# Internal: Gemini call 4 — outreach drafting (optional)
# ----------------------------------------------------------------------


class OutreachResult(BaseModel):
    subject: Optional[str] = None
    body: str
    personalisation_claims: List[CitedClaim] = Field(default_factory=list)


# ----------------------------------------------------------------------
# Internal: Gemini call 5 — background watch classification
# ----------------------------------------------------------------------


class ClassifiedSignal(BaseModel):
    brand_name: str = Field(description="Must be a brand on the watchlist.")

    signal: WatchSignal

    summary: str = Field(description="One sentence on what happened.")

    act_now: bool = Field(
        description="True only when the campaign window is open right now."
    )

    why_it_matters: Optional[str] = Field(
        default=None,
        description="Why this changes what the creator should do this week.",
    )

    source_id: str = Field(
        description="The source label, e.g. 'S2'. Never write a URL."
    )


class WatchClassification(BaseModel):
    signals: List[ClassifiedSignal] = Field(default_factory=list)