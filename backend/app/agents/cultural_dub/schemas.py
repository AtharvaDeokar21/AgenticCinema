"""Pydantic schemas for the Cultural Dub Agent."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from app.shared.models.audio import AudioMaster
from app.shared.models.research import ResearchSource


class TargetRegister(str, Enum):
    """Target speaking register for localization."""

    FORMAL = "formal"
    CONVERSATIONAL = "conversational"
    STREET = "street"


class CulturalSpanType(str, Enum):
    """Cultural span categories identified during localization."""

    NONE = "none"
    IDIOM = "idiom"
    SLANG = "slang"
    MEME_REFERENCE = "meme_reference"
    JOKE = "joke"
    CURRENCY_UNIT = "currency_unit"
    FOOD = "food"
    FESTIVAL = "festival"
    PLACE = "place"
    HONORIFIC = "honorific"
    BRAND_NAME = "brand_name"


class ReviewSeverity(str, Enum):
    """Severity of a human-review flag."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TargetLocale(BaseModel):
    """Target language and geography for a dub track."""

    language: str
    geography: str

    @property
    def locale(self) -> str:
        return f"{self.language}-{self.geography}"


class DubRequest(BaseModel):
    """Input contract for a Cultural Dub run."""

    project_id: Optional[str] = None
    audio_master: AudioMaster
    target_locales: List[TargetLocale] = Field(min_length=1)
    register: TargetRegister = TargetRegister.CONVERSATIONAL
    source_language: Optional[str] = None
    generate_audio: bool = True
    max_duration_overrun_seconds: float = Field(default=0.15, ge=0.0)
    creator_voice: bool = False
    creator_voice_consent_record: Optional[str] = None


class CulturalSpan(BaseModel):
    """A culturally meaningful source span."""

    segment_id: str
    source_text: str
    span_type: CulturalSpanType
    explanation: str
    cultural_function: str
    risk: ReviewSeverity = ReviewSeverity.LOW
    requires_research: bool = False


class CulturalAnalysis(BaseModel):
    """Structured source-side cultural analysis returned by Gemini."""

    spans: List[CulturalSpan] = Field(default_factory=list)


class CulturalSpanResearch(BaseModel):
    """Research retrieved for one culturally meaningful source span."""

    segment_id: str
    source_text: str
    sources: List[ResearchSource] = Field(default_factory=list)


class LocalizationEvidence(BaseModel):
    """Research evidence supporting a localization decision."""

    source: ResearchSource
    supports: str


class LocalizationCandidate(BaseModel):
    """A candidate localization for one source segment."""

    segment_id: str
    source_text: str
    localized_text: str
    language: str
    geography: str
    register: TargetRegister
    adaptation_reason: str
    cultural_strategy: str
    evidence: List[LocalizationEvidence] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    review_required: bool = False
    review_reason: Optional[str] = None


class ReviewFlag(BaseModel):
    """A localization issue requiring human review."""

    segment_id: str
    language: str
    geography: str
    severity: ReviewSeverity
    reason: str
    source_text: str
    proposed_text: str
    evidence: List[LocalizationEvidence] = Field(default_factory=list)


class LocaleLocalizationBrief(BaseModel):
    """Structured locale guidance returned by Parallel Task."""

    language: str
    geography: str
    register_guidance: List[str] = Field(default_factory=list)
    humour_conventions: List[str] = Field(default_factory=list)
    slang_guidance: List[str] = Field(default_factory=list)
    taboo_topics: List[str] = Field(default_factory=list)
    localization_rules: List[str] = Field(default_factory=list)
    retain_terms: List[str] = Field(default_factory=list)
    evidence: List[LocalizationEvidence] = Field(default_factory=list)


class LocaleMonitorConfig(BaseModel):
    """Configuration for the recurring Parallel Monitor of a locale."""

    language: str
    geography: str
    query: str
    frequency: str = "1w"
    monitor_id: Optional[str] = None


class DubSegmentResult(BaseModel):
    """Localized result for one source audio segment."""

    segment_id: str
    source_text: str
    localized_text: str
    language: str
    geography: str
    source_start_time: float
    source_end_time: float
    target_duration_seconds: Optional[float] = None
    audio_path: Optional[str] = None
    cultural_spans: List[CulturalSpan] = Field(default_factory=list)
    review_flags: List[ReviewFlag] = Field(default_factory=list)


class CulturalDubTrackResult(BaseModel):
    """Localized segments and artifacts for one target locale."""

    language: str
    geography: str
    segments: List[DubSegmentResult] = Field(default_factory=list)
    audio_path: Optional[str] = None
    subtitle_path: Optional[str] = None


class CulturalDubResult(BaseModel):
    """Complete result returned by the Cultural Dub Agent."""

    project_id: Optional[str] = None
    tracks: List[CulturalDubTrackResult] = Field(default_factory=list)
    localization_notes: List[LocalizationCandidate] = Field(default_factory=list)
    review_flags: List[ReviewFlag] = Field(default_factory=list)
    locale_briefs: List[LocaleLocalizationBrief] = Field(default_factory=list)
    monitor_configs: List[LocaleMonitorConfig] = Field(default_factory=list)
    degraded_reasons: List[str] = Field(default_factory=list)
