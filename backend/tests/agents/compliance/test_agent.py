

import pytest

from app.agents.compliance.agent import ComplianceAgent, asset_key
from app.agents.compliance.schemas import (
    ComplianceRequest,
    ExtractedEntity,
    ExtractionResult,
    MediaScanResult,
    SynthesisResult,
)
from app.shared.models.compliance import (
    AssetKind,
    ClearanceStatus,
    ReportStatus,
    TrackedAsset,
)
from app.shared.models.research import ResearchResult, ResearchSource
from app.shared.models.stages import ProjectStage


# ----------------------------------------------------------------------
# fakes
# ----------------------------------------------------------------------


class FakeGemini:
    def __init__(self, extraction=None, synthesis=None, media=None):
        self._extraction = extraction or ExtractionResult()
        self._synthesis = synthesis or SynthesisResult()
        self._media = media or MediaScanResult()
        self.calls = []

    # Matches the shared GeminiClient's public method, so the agent is
    # exercised through the same surface it uses in production.
    def generate_structured(self, prompt, response_schema, model=None, **kwargs):
        self.calls.append(response_schema.__name__)

        if response_schema is ExtractionResult:
            return self._extraction
        if response_schema is SynthesisResult:
            return self._synthesis
        if response_schema is MediaScanResult:
            return self._media

        raise AssertionError(f"unexpected schema {response_schema}")


class FakeSearch:
    def __init__(self, sources=None, fail=False):
        self._sources = sources or []
        self.fail = fail
        self.calls = 0

    async def search(self, search_queries, objective=None, **kwargs):
        self.calls += 1
        if self.fail:
            raise RuntimeError("parallel down")
        return ResearchResult(query="; ".join(search_queries), sources=self._sources)


class FakePage:
    """Duck-typed stand-in for whatever ParallelExtract ends up returning."""

    def __init__(self, url, content="", excerpts=None, error=None):
        self.url = url
        self.content = content
        self.excerpts = excerpts or []
        self.error = error


class FakeExtract:
    def __init__(self, pages=None, fail=False):
        self._pages = pages or []
        self.fail = fail
        self.calls = 0

    async def extract(self, urls, **kwargs):
        self.calls += 1
        if self.fail:
            raise RuntimeError("extract down")
        by_url = {p.url: p for p in self._pages}
        return [by_url.get(u, FakePage(u, error="no_result")) for u in urls]


SOURCE = ResearchSource(
    title="Library licence terms",
    url="https://example.com/licence",
    excerpts=["Free tier excludes sponsored content."],
    publish_date="2026-03-01",
)


def entity(label="Midnight Drive — Someone", kind=AssetKind.MUSIC):
    return ExtractedEntity(
        label=label,
        kind=kind,
        why_it_matters="Commercial track used under dialogue.",
        search_objective="Licensing terms for the track",
        search_queries=["midnight drive sync licence"],
    )


def finding(label, verdict, cited=True, substitutes=None):
    return {
        "label": label,
        "verdict": verdict,
        "description": "Free tier does not cover sponsored video.",
        "recommended_action": "Replace the bed.",
        "substitutes": substitutes if substitutes is not None else ["Generate a bed"],
        "cited_claims": (
            [{"claim": "Free tier excludes sponsored use.", "source_id": "S1"}]
            if cited
            else []
        ),
    }


def request(**kw):
    base = dict(
        project_id="p1",
        stage=ProjectStage.AUDIO,
        pass_number=5,
        payload="{}",
    )
    base.update(kw)
    return ComplianceRequest(**base)


def build(gemini, search=None, extract=None):
    return ComplianceAgent(
        gemini=gemini,
        search=search or FakeSearch([SOURCE]),
        extract=extract,
    )


# ----------------------------------------------------------------------
# tests
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_entities_passes_without_spending_anything():
    search = FakeSearch([SOURCE])
    agent = build(FakeGemini(), search=search)

    report = await agent.run(request())

    assert report.status is ReportStatus.PASSED
    assert report.issues == []
    assert search.calls == 0


@pytest.mark.asyncio
async def test_cited_red_blocks_the_pipeline():
    gemini = FakeGemini(
        extraction=ExtractionResult(entities=[entity()]),
        synthesis=SynthesisResult.model_validate(
            {"findings": [finding("Midnight Drive — Someone", "red")]}
        ),
    )

    report = await build(gemini).run(request())

    assert report.status is ReportStatus.BLOCKED
    assert len(report.reds) == 1
    assert report.reds[0].evidence[0].url == SOURCE.url
    assert report.reds[0].substitutes


@pytest.mark.asyncio
async def test_uncited_red_is_downgraded_not_trusted():
    """The compiler check: an uncited external claim is rejected, not softened."""

    gemini = FakeGemini(
        extraction=ExtractionResult(entities=[entity()]),
        synthesis=SynthesisResult.model_validate(
            {"findings": [finding("Midnight Drive — Someone", "red", cited=False)]}
        ),
    )

    report = await build(gemini).run(request())

    assert report.issues[0].severity is ClearanceStatus.UNVERIFIED
    assert report.status is ReportStatus.DEGRADED
    assert any("no resolvable source" in r for r in report.degraded_reasons)


@pytest.mark.asyncio
async def test_hallucinated_source_label_is_dropped():
    gemini = FakeGemini(
        extraction=ExtractionResult(entities=[entity()]),
        synthesis=SynthesisResult.model_validate(
            {
                "findings": [
                    {
                        **finding("Midnight Drive — Someone", "yellow"),
                        "cited_claims": [
                            {"claim": "x", "source_id": "S99"},
                            {"claim": "y", "source_id": "https://made-up.example"},
                        ],
                    }
                ]
            }
        ),
    )

    report = await build(gemini).run(request())

    assert report.issues[0].evidence == []
    assert report.issues[0].severity is ClearanceStatus.UNVERIFIED


@pytest.mark.asyncio
async def test_yellow_passes_with_conditions_without_extract():
    """Extract being unavailable is a note, not a verification gap."""

    gemini = FakeGemini(
        extraction=ExtractionResult(entities=[entity()]),
        synthesis=SynthesisResult.model_validate(
            {"findings": [finding("Midnight Drive — Someone", "yellow")]}
        ),
    )

    report = await build(gemini).run(request())

    assert report.status is ReportStatus.PASSED_WITH_CONDITIONS
    assert any("Extract not enabled" in r for r in report.degraded_reasons)


@pytest.mark.asyncio
async def test_extract_content_reaches_the_synthesis_sources():
    pages = [FakePage(SOURCE.url, content="Clause 4: sponsored use excluded.")]
    extract = FakeExtract(pages)

    gemini = FakeGemini(
        extraction=ExtractionResult(entities=[entity()]),
        synthesis=SynthesisResult.model_validate(
            {"findings": [finding("Midnight Drive — Someone", "green")]}
        ),
    )

    report = await build(gemini, extract=extract).run(request())

    assert extract.calls == 1
    assert report.status is ReportStatus.PASSED
    assert not any("Extract not enabled" in r for r in report.degraded_reasons)


@pytest.mark.asyncio
async def test_extract_failure_is_not_a_verification_gap():
    gemini = FakeGemini(
        extraction=ExtractionResult(entities=[entity()]),
        synthesis=SynthesisResult.model_validate(
            {"findings": [finding("Midnight Drive — Someone", "green")]}
        ),
    )

    report = await build(gemini, extract=FakeExtract(fail=True)).run(request())

    assert report.status is ReportStatus.PASSED
    assert any("Extract failed" in r for r in report.degraded_reasons)


@pytest.mark.asyncio
async def test_cleared_asset_is_not_researched_again():
    label = "Midnight Drive — Someone"
    key = asset_key(AssetKind.MUSIC, label)

    prior = TrackedAsset(
        asset_key=key,
        kind=AssetKind.MUSIC,
        label=label,
        first_seen_stage="script",
        status=ClearanceStatus.GREEN,
    )

    search = FakeSearch([SOURCE])
    gemini = FakeGemini(extraction=ExtractionResult(entities=[entity(label)]))

    report = await build(gemini, search=search).run(request(prior_assets=[prior]))

    assert search.calls == 0
    assert "SynthesisResult" not in gemini.calls
    assert any(a.asset_key == key for a in report.checked_assets)


@pytest.mark.asyncio
async def test_unverified_prior_asset_is_retried():
    label = "Midnight Drive — Someone"
    prior = TrackedAsset(
        asset_key=asset_key(AssetKind.MUSIC, label),
        kind=AssetKind.MUSIC,
        label=label,
        first_seen_stage="script",
        status=ClearanceStatus.UNVERIFIED,
    )

    search = FakeSearch([SOURCE])
    gemini = FakeGemini(
        extraction=ExtractionResult(entities=[entity(label)]),
        synthesis=SynthesisResult.model_validate(
            {"findings": [finding(label, "green")]}
        ),
    )

    await build(gemini, search=search).run(request(prior_assets=[prior]))

    assert search.calls == 1


@pytest.mark.asyncio
async def test_search_failure_degrades_rather_than_crashing():
    gemini = FakeGemini(
        extraction=ExtractionResult(entities=[entity()]),
        synthesis=SynthesisResult.model_validate(
            {"findings": [finding("Midnight Drive — Someone", "green", cited=False)]}
        ),
    )

    report = await build(gemini, search=FakeSearch(fail=True)).run(request())

    assert report.status is ReportStatus.DEGRADED
    assert any("Search failed" in r for r in report.degraded_reasons)


@pytest.mark.asyncio
async def test_entity_with_no_verdict_becomes_unverified():
    gemini = FakeGemini(
        extraction=ExtractionResult(entities=[entity(), entity("Second Thing")]),
        synthesis=SynthesisResult.model_validate(
            {"findings": [finding("Midnight Drive — Someone", "green")]}
        ),
    )

    report = await build(gemini).run(request())

    severities = {i.severity for i in report.issues}
    assert ClearanceStatus.UNVERIFIED in severities
    assert report.status is ReportStatus.DEGRADED


@pytest.mark.asyncio
async def test_structural_errors_block_immediately():
    report = await build(FakeGemini()).run(
        request(structural_errors=["storyboard: shot s1 references unknown beat"])
    )

    assert report.status is ReportStatus.BLOCKED