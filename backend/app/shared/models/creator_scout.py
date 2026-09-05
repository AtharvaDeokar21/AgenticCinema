"""
CreatorScout contracts.

ADDITIVE CHANGE. `CreatorRecommendation` is untouched and keeps its exact
shape, so `ProjectState.creator_recommendations` and anything reading it keep
working. Everything below it is new.

Naming note worth raising with the team: `CreatorRecommendation` describes a
creator being recommended, but Layer 1 of the workflow doc has CreatorScout
finding *brands* for a creator. Those are two different products. Rather than
overload one model, brand-side output uses `BrandOpportunity`. If the creator-
discovery half of the agent gets built later, `CreatorRecommendation` is
already the right shape for it.
"""

from datetime import date, datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class EvidenceRef(BaseModel):
    """
    A claim bound to the source that supports it.

    Defined here rather than imported so CreatorScout needs no change to any
    other shared file. When a second agent needs the same primitive, promote it
    to shared/models/research.py and import it from both.
    """

    claim: str
    url: str
    title: Optional[str] = None
    excerpt: Optional[str] = None
    retrieved_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )



class CreatorRecommendation(BaseModel):
    """Unchanged. For recommending creators, not brands."""

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


# ----------------------------------------------------------------------
# Exclusivity — the term that damages future income and is invisible now
# ----------------------------------------------------------------------


class ExclusivityClause(BaseModel):
    """
    One live restriction from a signed deal. The ledger of these is both an
    output of CreatorScout and an input to its next run: today's signature is
    tomorrow's suppression rule.
    """

    category: str  # e.g. "personal finance"

    brand_name: Optional[str] = None

    territory: Optional[str] = None

    expires_on: date

    source_deal_id: Optional[str] = None

    def is_active(self, on: Optional[date] = None) -> bool:
        return self.expires_on >= (on or date.today())


class VerificationTier(str, Enum):
    """
    How much a candidate has been checked. Entity Search trades verification
    for speed, so its results must not be presented as equal to FindAll's.
    """

    VERIFIED = "verified"  # matched against explicit conditions
    UNVERIFIED = "unverified"  # fast lookup, not yet confirmed
    DERIVED = "derived"  # inferred from general search, weakest


# ----------------------------------------------------------------------
# Opportunities
# ----------------------------------------------------------------------


class BrandOpportunity(BaseModel):
    """A brand the creator could realistically work with, and why."""

    brand_name: str

    category: Optional[str] = None

    tier: VerificationTier = VerificationTier.DERIVED

    # --- enrichment: what turns a name into something actionable ---

    has_creator_program: Optional[bool] = None

    program_url: Optional[str] = None

    booking_agency: Optional[str] = None

    recent_campaigns: List[str] = Field(default_factory=list)

    contact_route: Optional[str] = None

    typical_deliverables: Optional[str] = None

    exclusivity_practice: Optional[str] = None

    campaign_seasonality: Optional[str] = None

    # --- ranking: Gemini's judgement, stated so the creator can argue ---

    rank: Optional[int] = None

    audience_fit: Optional[float] = None

    brand_fit: Optional[float] = None

    commercial_fit: Optional[float] = None

    overall_score: Optional[float] = None

    rationale: Optional[str] = None

    cautions: List[str] = Field(default_factory=list)

    # Flagged, never suppressed — the creator decides whether to stretch.
    capacity_warning: Optional[str] = None

    evidence: List[EvidenceRef] = Field(default_factory=list)


class SuppressionRule(str, Enum):
    ACTIVE_EXCLUSIVITY = "active_exclusivity"
    CREATOR_EXCLUSION_LIST = "creator_exclusion_list"


class SuppressedOpportunity(BaseModel):
    """
    A candidate removed by a hard rule, kept with its reason.

    Suppression is shown, not hidden. A creator who cannot see why a brand
    disappeared cannot tell a bug from a rule.
    """

    brand_name: str

    category: Optional[str] = None

    rule: SuppressionRule

    reason: str


class OpportunityQueue(BaseModel):
    """The ranked queue, plus everything that was removed and why."""

    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    opportunities: List[BrandOpportunity] = Field(default_factory=list)

    suppressed: List[SuppressedOpportunity] = Field(default_factory=list)

    exclusivity_ledger: List[ExclusivityClause] = Field(default_factory=list)

    # Why the run was imperfect: unavailable tools, failed lookups, dropped
    # uncited claims.
    degraded_reasons: List[str] = Field(default_factory=list)

    @property
    def actionable(self) -> List[BrandOpportunity]:
        return [o for o in self.opportunities if not o.capacity_warning]


# ----------------------------------------------------------------------
# Deals
# ----------------------------------------------------------------------


class DealState(str, Enum):
    DISCOVERED = "discovered"
    QUALIFIED = "qualified"
    OUTREACH_SENT = "outreach_sent"
    REPLIED = "replied"
    NEGOTIATING = "negotiating"
    TERMS_AGREED = "terms_agreed"
    # A human signs here. No transition past TERMS_AGREED is automated.
    IN_PRODUCTION = "in_production"
    DELIVERED = "delivered"
    INVOICED = "invoiced"
    PAID = "paid"
    EXCLUSIVITY_TRACKING = "exclusivity_tracking"
    DECLINED = "declined"


class OutreachDraft(BaseModel):
    brand_name: str

    subject: Optional[str] = None

    body: str

    # What in the enrichment record this was personalised from, so the creator
    # can check the pitch is not built on a hallucinated campaign.
    personalisation_basis: List[EvidenceRef] = Field(default_factory=list)


class DealMemo(BaseModel):
    """
    What a human reads before signing. Every field the workflow doc names as
    expensive-later is explicit rather than buried in prose.
    """

    brand_name: str

    state: DealState = DealState.NEGOTIATING

    fee: Optional[str] = None

    deliverables: List[str] = Field(default_factory=list)

    revision_limit: Optional[int] = None

    usage_rights_scope: Optional[str] = None

    usage_rights_months: Optional[int] = None

    exclusivity_scope: Optional[str] = None

    exclusivity_months: Optional[int] = None

    payment_terms: Optional[str] = None

    disclosure_obligation: Optional[str] = None

    open_questions: List[str] = Field(default_factory=list)

    evidence: List[EvidenceRef] = Field(default_factory=list)

    # Not configurable. The agent never signs, and never agrees to exclusivity
    # on its own. Enforced in code rather than asked for in a prompt.
    requires_human_signature: bool = True

    @field_validator("requires_human_signature")
    @classmethod
    def _always_requires_signature(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError(
                "A deal memo always requires a human signature. This is a "
                "safety invariant, not a default."
            )
        return True

    @property
    def perpetuity_requested(self) -> bool:
        text = (self.usage_rights_scope or "").lower()
        return "perpetu" in text or "in perpetuity" in text


# ----------------------------------------------------------------------
# Background watch
# ----------------------------------------------------------------------


class WatchSignal(str, Enum):
    """
    Why these four and not "any news".

    A funding round means budget exists. A new marketing head means vendor
    relationships get reset and an outsider can get in. A product launch means
    a live campaign window. A published creator campaign proves the brand
    actually spends on creators rather than merely advertising.

    Creator marketing is won on timing more than on pitch quality, so the
    watch is tuned for timing signals and deliberately ignores general
    company news.
    """

    FUNDING_ROUND = "funding_round"
    PRODUCT_LAUNCH = "product_launch"
    MARKETING_LEADERSHIP_CHANGE = "marketing_leadership_change"
    CREATOR_CAMPAIGN = "creator_campaign"


class WatchEvent(BaseModel):
    """One timing signal, deduplicated by source URL."""

    event_id: str

    brand_name: str

    signal: WatchSignal

    summary: str

    # Whether the window is open now, or this is just context.
    act_now: bool = False

    why_it_matters: Optional[str] = None

    detected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    evidence: List[EvidenceRef] = Field(default_factory=list)


class WatchReport(BaseModel):
    """The result of one polling run."""

    ran_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    brands_checked: List[str] = Field(default_factory=list)

    new_events: List[WatchEvent] = Field(default_factory=list)

    urls_seen: int = 0

    urls_new: int = 0

    degraded_reasons: List[str] = Field(default_factory=list)

    @property
    def urgent(self) -> List[WatchEvent]:
        return [e for e in self.new_events if e.act_now]