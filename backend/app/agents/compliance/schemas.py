"""
Schemas for the Compliance (ClearanceCheck) agent.

`ComplianceRequest` is the public input contract.
Everything below it is internal: response schemas for the two Gemini calls.
They are deliberately NOT in shared/models — no other agent consumes them.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from app.shared.models.compliance import AssetKind, ClearanceStatus, TrackedAsset
from app.shared.models.stages import ProjectStage


class ComplianceRequest(BaseModel):
    """One pass of ClearanceCheck, run immediately after another agent."""

    project_id: str

    # The stage that just finished. Drives which checks apply.
    stage: ProjectStage

    pass_number: int = 1

    # The finished agent's output, serialised. Usually
    # `state.script.model_dump_json(indent=2)` or similar.
    payload: str

    # The running asset list from earlier passes, so cleared assets are not
    # re-researched.
    prior_assets: List[TrackedAsset] = Field(default_factory=list)

    # Deterministic cross-reference failures computed by structural.py.
    structural_errors: List[str] = Field(default_factory=list)

    # --- context that changes the verdict ---

    target_markets: List[str] = Field(default_factory=lambda: ["India"])

    is_sponsored: bool = False

    sponsor_brand: Optional[str] = None

    # Generated thumbnails / concept art to scan for recognisable IP.
    image_paths: List[str] = Field(default_factory=list)

    # Recorded audio to scan for third-party music nobody meant to record.
    audio_paths: List[str] = Field(default_factory=list)

    # A synthetic or cloned voice was used somewhere in this project.
    synthetic_voice_used: bool = False

    consent_record_id: Optional[str] = None


# ----------------------------------------------------------------------
# Internal: Gemini call 1 — entity extraction
# ----------------------------------------------------------------------


class ExtractedEntity(BaseModel):
    label: str = Field(description="The thing itself, e.g. 'Midnight City — M83'")

    kind: AssetKind

    why_it_matters: str = Field(
        description="One sentence on the rights exposure this creates."
    )

    search_objective: str = Field(
        description="A precise research objective for a web search."
    )

    search_queries: List[str] = Field(
        default_factory=list,
        description="Two or three keyword queries.",
    )


class ExtractionResult(BaseModel):
    entities: List[ExtractedEntity] = Field(default_factory=list)


# ----------------------------------------------------------------------
# Internal: Gemini call 2 — traffic-light synthesis
# ----------------------------------------------------------------------


class CitedClaim(BaseModel):
    claim: str

    source_id: str = Field(
        description="A source label such as 'S3' from the SOURCES block. "
        "Never write a URL."
    )


class SynthesisFinding(BaseModel):
    label: str

    verdict: ClearanceStatus

    description: str

    recommended_action: Optional[str] = None

    substitutes: List[str] = Field(
        default_factory=list,
        description="Required whenever verdict is red.",
    )

    cited_claims: List[CitedClaim] = Field(default_factory=list)


class SynthesisResult(BaseModel):
    findings: List[SynthesisFinding] = Field(default_factory=list)


# ----------------------------------------------------------------------
# Internal: multimodal media scan
# ----------------------------------------------------------------------


class MediaObservation(BaseModel):
    label: str

    kind: AssetKind

    description: str

    confidence: float = Field(ge=0.0, le=1.0)

    search_objective: str

    search_queries: List[str] = Field(default_factory=list)


class MediaScanResult(BaseModel):
    observations: List[MediaObservation] = Field(default_factory=list)