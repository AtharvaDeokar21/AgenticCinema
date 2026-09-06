"""
ClearanceCheck — the Compliance Agent.

Pipeline for one pass:

    structural check (deterministic, milliseconds)
        ↓
    entity extraction        Gemini, cheap model
        ↓
    media scan               Gemini multimodal, only when assets are attached
        ↓
    dedup against ledger     no API calls for already-cleared assets
        ↓
    Parallel Search          find who owns it / what the terms are
        ↓
    Parallel Extract         read the licence page itself — OPTIONAL
        ↓
    synthesis                Gemini, stronger model, traffic light per entity
        ↓
    citation enforcement     uncited red/yellow -> unverified (in code)
        ↓
    gate                     red blocks, yellow passes with a task attached
"""

import asyncio
import hashlib
import logging
import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from app.agents.base import BaseAgent
from app.agents.compliance.prompts import (
    AUDIO_SCAN_INSTRUCTION,
    DEFAULT_FOCUS,
    EXTRACTION_SYSTEM_PROMPT,
    EXTRACTION_USER_TEMPLATE,
    IMAGE_SCAN_INSTRUCTION,
    MEDIA_SCAN_PROMPT,
    STAGE_FOCUS,
    SYNTHESIS_SYSTEM_PROMPT,
    SYNTHESIS_USER_TEMPLATE,
)
from app.agents.compliance.schemas import (
    ComplianceRequest,
    ExtractedEntity,
    ExtractionResult,
    MediaScanResult,
    SynthesisResult,
)
from app.shared.models.compliance import (
    AssetKind,
    ClearanceReport,
    ClearanceStatus,
    ComplianceIssue,
    EvidenceRef,
    ReportStatus,
    TrackedAsset,
)
from app.shared.models.research import ResearchSource
from app.shared.tools.gemini.client import GeminiClient
from app.shared.tools.parallel.search import ParallelSearch

logger = logging.getLogger(__name__)

MAX_CONCURRENT_RESEARCH = 4
MAX_SOURCES_PER_ENTITY = 4
MAX_URLS_TO_EXTRACT = 12
MAX_EXTRACT_CHARS = 4_000

# Inline media bytes are capped by the request size limit. Larger files need
# the Files API; we fail loudly rather than silently truncating.
MAX_INLINE_BYTES = 18 * 1024 * 1024

SOURCE_LABEL_RE = re.compile(r"^S\d+$")


def _slug(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def asset_key(kind: AssetKind, label: str) -> str:
    """Stable dedup key so the same track is researched once per project."""
    digest = hashlib.sha1(_slug(label).encode("utf-8")).hexdigest()[:10]
    return f"{kind.value}::{digest}"


def media_part(path: Union[str, Path]):
    """
    Read a local file into a Gemini content part.

    Lives here rather than in the shared Gemini client so that a change in the
    SDK's `types` module can only break compliance, not every agent's imports.
    """

    from google.genai import types  # local import: contains the blast radius

    p = Path(path)

    if not p.exists():
        raise FileNotFoundError(f"Media file not found: {p}")

    size = p.stat().st_size
    if size > MAX_INLINE_BYTES:
        raise ValueError(
            f"{p.name} is {size / 1e6:.1f} MB; too large to inline. "
            "Upload via the Files API and pass the file reference instead."
        )

    mime, _ = mimetypes.guess_type(p.name)

    return types.Part.from_bytes(
        data=p.read_bytes(),
        mime_type=mime or "application/octet-stream",
    )


class _Notes:
    """
    Accumulates why a pass was imperfect, and whether that imperfection means
    we failed to reach a verdict.

    The distinction drives the gate. Extract being unavailable while search
    excerpts still supported a cited verdict is worth reporting but is not a
    verification gap. Search failing outright is, because it means we do not
    know the answer and must not imply that we do.
    """

    def __init__(self) -> None:
        self.reasons: List[str] = []
        self.blocking = False

    def note(self, message: str) -> None:
        self.reasons.append(message)

    def gap(self, message: str) -> None:
        self.reasons.append(message)
        self.blocking = True


class ComplianceAgent(BaseAgent):
    """
    Runs after every other agent. Six passes per project.

    Tools are injectable so the agent is testable without spending money:

        agent = ComplianceAgent(gemini=FakeGemini(), search=FakeSearch())
    """

    name = "compliance"

    def __init__(
        self,
        gemini: Optional[GeminiClient] = None,
        search: Optional[ParallelSearch] = None,
        extract: Optional[Any] = None,
        extraction_model: Optional[str] = None,
        synthesis_model: Optional[str] = None,
    ):
        self.gemini = gemini or GeminiClient()
        self.search = search or ParallelSearch()

        # Optional. Duck-typed: anything with
        # `async extract(urls) -> [obj with .url/.content/.excerpts]` works.
        # None means excerpt-only mode, which the report declares.
        self.extract = extract

        # Extraction and media captioning do not need the strongest model.
        # Reserve it for the traffic-light judgement.
        self.extraction_model = extraction_model
        self.synthesis_model = synthesis_model

    # ------------------------------------------------------------------
    # Gemini access — uses the shared client as it exists today
    # ------------------------------------------------------------------

    def _structured_sync(self, prompt, schema, model: Optional[str]):
        # Text-only: straight through the shared wrapper.
        if isinstance(prompt, str):
            return self.gemini.generate_structured(
                prompt=prompt,
                response_schema=schema,
                model=model,
            )

        # Multimodal: the shared wrapper takes a string, so use the SDK session
        # it already exposes. Same config shape, no new shared method.
        response = self.gemini.client.models.generate_content(
            model=model or self.gemini.default_model,
            contents=list(prompt),
            config={
                "response_mime_type": "application/json",
                "response_schema": schema,
            },
        )
        return response.parsed

    async def _structured(self, prompt, schema, model: Optional[str] = None):
        """The SDK call is blocking, so keep it off the event loop."""
        return await asyncio.to_thread(self._structured_sync, prompt, schema, model)

    # ------------------------------------------------------------------
    # entry point
    # ------------------------------------------------------------------

    async def run(self, request: ComplianceRequest) -> ClearanceReport:
        notes = _Notes()

        known = {a.asset_key: a for a in request.prior_assets}

        # 1 — find what needs verification
        entities = await self._extract_entities(request, known, notes)
        entities += await self._scan_media(request, notes)

        # 2 — drop anything already cleared, and collapse duplicates
        entities, reused = self._dedup(entities, known)

        if not entities:
            return self._empty_report(request, known, reused, notes)

        # 3 — research each one
        research = await self._research(entities, notes)

        # 4 — build the numbered source registry the model cites against
        registry, sources_block = self._build_source_registry(research)

        if not registry:
            notes.gap(
                "No usable web sources were returned; findings cannot be cited."
            )

        # 5 — traffic light
        findings = await self._synthesise(request, entities, sources_block, notes)

        # 6 — enforce citations in code, then assemble
        issues, ledger_updates = self._compile(entities, findings, registry, notes)

        assets = self._merge_ledger(request, known, ledger_updates, reused)

        return ClearanceReport(
            status=self._gate(issues, request.structural_errors, notes.blocking),
            stage=request.stage.value,
            pass_number=request.pass_number,
            issues=issues,
            checked_assets=assets,
            structural_errors=list(request.structural_errors),
            degraded_reasons=notes.reasons,
        )

    # ------------------------------------------------------------------
    # 1a — text entity extraction
    # ------------------------------------------------------------------

    async def _extract_entities(
        self,
        request: ComplianceRequest,
        known: Dict[str, TrackedAsset],
        notes: _Notes,
    ) -> List[ExtractedEntity]:
        focus = STAGE_FOCUS.get(request.stage, DEFAULT_FOCUS)

        known_block = (
            "\n".join(f"- {a.label} ({a.status.value})" for a in known.values())
            or "None."
        )

        prompt = EXTRACTION_SYSTEM_PROMPT + "\n\n" + EXTRACTION_USER_TEMPLATE.format(
            stage=request.stage.value,
            pass_number=request.pass_number,
            target_markets=", ".join(request.target_markets) or "Not specified",
            sponsored=(
                f"yes — sponsor is {request.sponsor_brand or 'unnamed'}"
                if request.is_sponsored
                else "no"
            ),
            focus=focus,
            known_assets=known_block,
            payload=request.payload,
        )

        try:
            result = await self._structured(
                prompt, ExtractionResult, self.extraction_model
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Entity extraction failed")
            notes.gap(f"Entity extraction failed: {exc}")
            return []

        return list(getattr(result, "entities", []) or [])

    # ------------------------------------------------------------------
    # 1b — multimodal scan of generated images / recorded audio
    # ------------------------------------------------------------------

    async def _scan_media(
        self,
        request: ComplianceRequest,
        notes: _Notes,
    ) -> List[ExtractedEntity]:
        jobs: List[Tuple[str, str, AssetKind]] = []

        for path in request.image_paths:
            jobs.append((path, IMAGE_SCAN_INSTRUCTION, AssetKind.GENERATED_IMAGE))

        for path in request.audio_paths:
            jobs.append((path, AUDIO_SCAN_INSTRUCTION, AssetKind.BACKGROUND_AUDIO))

        if not jobs:
            return []

        async def scan(path: str, instruction: str, fallback_kind: AssetKind):
            try:
                part = media_part(path)
            except Exception as exc:  # noqa: BLE001
                notes.gap(f"Could not read media '{path}': {exc}")
                return []

            try:
                result = await self._structured(
                    [MEDIA_SCAN_PROMPT.format(instruction=instruction), part],
                    MediaScanResult,
                    self.extraction_model,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Media scan failed for %s", path)
                notes.gap(f"Media scan failed for '{path}': {exc}")
                return []

            out: List[ExtractedEntity] = []

            for obs in getattr(result, "observations", []) or []:
                out.append(
                    ExtractedEntity(
                        label=f"{obs.label} (in {Path(path).name})",
                        kind=obs.kind or fallback_kind,
                        why_it_matters=(
                            f"{obs.description} "
                            f"[detection confidence {obs.confidence:.2f}]"
                        ),
                        search_objective=obs.search_objective,
                        search_queries=obs.search_queries,
                    )
                )

            return out

        sem = asyncio.Semaphore(MAX_CONCURRENT_RESEARCH)

        async def guarded(args):
            async with sem:
                return await scan(*args)

        batches = await asyncio.gather(*(guarded(j) for j in jobs))

        return [e for batch in batches for e in batch]

    # ------------------------------------------------------------------
    # 2 — dedup
    # ------------------------------------------------------------------

    def _dedup(
        self,
        entities: Sequence[ExtractedEntity],
        known: Dict[str, TrackedAsset],
    ) -> Tuple[List[ExtractedEntity], List[TrackedAsset]]:
        fresh: List[ExtractedEntity] = []
        reused: List[TrackedAsset] = []
        seen: set = set()

        for entity in entities:
            key = asset_key(entity.kind, entity.label)

            if key in seen:
                continue
            seen.add(key)

            prior = known.get(key)

            # Only skip if a previous pass actually reached a verdict. An
            # UNVERIFIED asset gets another attempt.
            if prior and prior.status is not ClearanceStatus.UNVERIFIED:
                reused.append(prior)
                continue

            fresh.append(entity)

        return fresh, reused

    # ------------------------------------------------------------------
    # 3 — research: Search finds the page, Extract reads it (if available)
    # ------------------------------------------------------------------

    async def _research(
        self,
        entities: Sequence[ExtractedEntity],
        notes: _Notes,
    ) -> List[ResearchSource]:
        sem = asyncio.Semaphore(MAX_CONCURRENT_RESEARCH)

        async def one(entity: ExtractedEntity) -> List[ResearchSource]:
            queries = entity.search_queries or [entity.label]

            async with sem:
                try:
                    # Current shared signature only. See RECENCY LIMITATION.
                    result = await self.search.search(
                        search_queries=queries[:3],
                        objective=entity.search_objective,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Search failed for '%s': %s", entity.label, exc)
                    notes.gap(f"Search failed for '{entity.label}': {exc}")
                    return []

            return list(result.sources or [])[:MAX_SOURCES_PER_ENTITY]

        batches = await asyncio.gather(*(one(e) for e in entities))

        # Deduplicate by URL, preserving order.
        by_url: Dict[str, ResearchSource] = {}
        for batch in batches:
            for source in batch:
                by_url.setdefault(source.url, source)

        sources = list(by_url.values())

        if not sources:
            return []

        await self._enrich_with_extract(sources, notes)

        return sources

    async def _enrich_with_extract(
        self,
        sources: List[ResearchSource],
        notes: _Notes,
    ) -> None:
        """
        Search finds the page; Extract reads it. Licence terms are routinely
        published as PDFs, and an excerpt is not a licence.

        Optional by design: if `shared/tools/parallel/extract.py` has not been
        implemented yet, the agent runs on excerpts and says so.
        """

        if self.extract is None:
            notes.note(
                "Parallel Extract not enabled; verdicts rest on search excerpts "
                "only, which are weaker evidence for licence and permit terms."
            )
            return

        urls = [s.url for s in sources][:MAX_URLS_TO_EXTRACT]

        try:
            pages = await self.extract.extract(urls=urls)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Parallel Extract failed: %s", exc)
            notes.note(f"Parallel Extract failed ({exc}); using search excerpts.")
            return

        usable = {
            getattr(p, "url", None): p
            for p in (pages or [])
            if getattr(p, "url", None)
            and (getattr(p, "content", "") or getattr(p, "excerpts", []))
            and not getattr(p, "error", None)
        }

        if not usable:
            notes.note(
                "Parallel Extract returned nothing usable; verdicts rest on "
                "search excerpts only."
            )
            return

        for source in sources:
            page = usable.get(source.url)
            if not page:
                continue

            content = getattr(page, "content", "") or ""

            if content:
                source.excerpts = list(source.excerpts) + [
                    content[:MAX_EXTRACT_CHARS]
                ]
            else:
                source.excerpts = list(source.excerpts) + list(
                    getattr(page, "excerpts", []) or []
                )

    # ------------------------------------------------------------------
    # 4 — source registry: labels in, real URLs out
    # ------------------------------------------------------------------

    @staticmethod
    def _build_source_registry(
        sources: Sequence[ResearchSource],
    ) -> Tuple[Dict[str, ResearchSource], str]:
        registry: Dict[str, ResearchSource] = {}
        blocks: List[str] = []

        for index, source in enumerate(sources, start=1):
            label = f"S{index}"
            registry[label] = source

            excerpts = (
                "\n".join(f"  - {e}" for e in source.excerpts[:6]) or "  (none)"
            )

            blocks.append(
                f"[{label}] {source.title}\n"
                f"  published: {source.publish_date or 'unknown'}\n"
                f"{excerpts}"
            )

        return registry, "\n\n".join(blocks) or "No sources were retrieved."

    # ------------------------------------------------------------------
    # 5 — synthesis
    # ------------------------------------------------------------------

    async def _synthesise(
        self,
        request: ComplianceRequest,
        entities: Sequence[ExtractedEntity],
        sources_block: str,
        notes: _Notes,
    ) -> List:
        entity_block = "\n\n".join(
            f"- LABEL: {e.label}\n"
            f"  KIND: {e.kind.value}\n"
            f"  EXPOSURE: {e.why_it_matters}\n"
            f"  QUESTION: {e.search_objective}"
            for e in entities
        )

        prompt = SYNTHESIS_SYSTEM_PROMPT + "\n\n" + SYNTHESIS_USER_TEMPLATE.format(
            stage=request.stage.value,
            target_markets=", ".join(request.target_markets) or "Not specified",
            sponsored="yes" if request.is_sponsored else "no",
            sponsor_brand=request.sponsor_brand or "n/a",
            entities=entity_block,
            sources=sources_block,
        )

        try:
            result = await self._structured(
                prompt, SynthesisResult, self.synthesis_model
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Clearance synthesis failed")
            notes.gap(f"Clearance synthesis failed: {exc}")
            return []

        return list(getattr(result, "findings", []) or [])

    # ------------------------------------------------------------------
    # 6 — citation enforcement + assembly
    # ------------------------------------------------------------------

    def _compile(
        self,
        entities: Sequence[ExtractedEntity],
        findings: Sequence,
        registry: Dict[str, ResearchSource],
        notes: _Notes,
    ) -> Tuple[List[ComplianceIssue], List[TrackedAsset]]:
        by_label = {_slug(e.label): e for e in entities}
        covered: set = set()

        issues: List[ComplianceIssue] = []
        ledger: List[TrackedAsset] = []
        now = datetime.now(timezone.utc)

        for index, finding in enumerate(findings, start=1):
            entity = by_label.get(_slug(finding.label))
            kind = entity.kind if entity else AssetKind.OTHER

            if entity:
                covered.add(_slug(entity.label))

            evidence: List[EvidenceRef] = []

            for cited in finding.cited_claims or []:
                label = (cited.source_id or "").strip().upper()

                if not SOURCE_LABEL_RE.match(label):
                    continue

                source = registry.get(label)
                if not source:
                    continue

                evidence.append(
                    EvidenceRef(
                        claim=cited.claim,
                        url=source.url,
                        title=source.title,
                        excerpt=source.excerpts[0] if source.excerpts else None,
                        retrieved_at=now,
                    )
                )

            verdict = finding.verdict
            description = finding.description

            # The compiler check. An uncited claim about the outside world is
            # rejected, not softened.
            if (
                verdict in (ClearanceStatus.RED, ClearanceStatus.YELLOW)
                and not evidence
            ):
                notes.note(
                    f"'{finding.label}' was returned as {verdict.value} with no "
                    "resolvable source; downgraded to unverified."
                )
                verdict = ClearanceStatus.UNVERIFIED
                description = (
                    "Could not be verified against a retrievable source. "
                    "Original assessment, retained for a human to check: "
                    + description
                )

            substitutes = list(finding.substitutes or [])
            action = finding.recommended_action

            if verdict is ClearanceStatus.RED and not substitutes:
                action = (
                    (action + " " if action else "")
                    + "No substitute was proposed — do not proceed until one is "
                    "chosen."
                )

            key = asset_key(kind, finding.label)

            issues.append(
                ComplianceIssue(
                    issue_id=f"clr_{index:03d}",
                    asset_key=key,
                    label=finding.label,
                    kind=kind,
                    severity=verdict,
                    description=description,
                    recommended_action=action,
                    substitutes=substitutes,
                    evidence=evidence,
                )
            )

            ledger.append(
                TrackedAsset(
                    asset_key=key,
                    kind=kind,
                    label=finding.label,
                    first_seen_stage="",  # filled in by _merge_ledger
                    status=verdict,
                    last_checked_at=now,
                )
            )

        # Anything the model silently dropped is unverified, not cleared.
        for entity in entities:
            if _slug(entity.label) in covered:
                continue

            key = asset_key(entity.kind, entity.label)

            notes.note(f"'{entity.label}' was extracted but received no verdict.")

            issues.append(
                ComplianceIssue(
                    issue_id=f"clr_x{len(issues) + 1:03d}",
                    asset_key=key,
                    label=entity.label,
                    kind=entity.kind,
                    severity=ClearanceStatus.UNVERIFIED,
                    description=(
                        f"{entity.why_it_matters} No verdict was produced for "
                        "this asset."
                    ),
                    recommended_action="Check manually before publish.",
                )
            )

            ledger.append(
                TrackedAsset(
                    asset_key=key,
                    kind=entity.kind,
                    label=entity.label,
                    first_seen_stage="",
                    status=ClearanceStatus.UNVERIFIED,
                    last_checked_at=now,
                )
            )

        return issues, ledger

    def _merge_ledger(
        self,
        request: ComplianceRequest,
        known: Dict[str, TrackedAsset],
        updates: Sequence[TrackedAsset],
        reused: Sequence[TrackedAsset],
    ) -> List[TrackedAsset]:
        merged: Dict[str, TrackedAsset] = dict(known)

        for asset in reused:
            merged[asset.asset_key] = asset

        for asset in updates:
            prior = merged.get(asset.asset_key)
            asset.first_seen_stage = (
                prior.first_seen_stage if prior else request.stage.value
            )
            merged[asset.asset_key] = asset

        return list(merged.values())

    # ------------------------------------------------------------------
    # gate
    # ------------------------------------------------------------------

    @staticmethod
    def _gate(
        issues: Sequence[ComplianceIssue],
        structural_errors: Sequence[str],
        blocking_gap: bool,
    ) -> ReportStatus:
        if structural_errors:
            return ReportStatus.BLOCKED

        if any(i.severity is ClearanceStatus.RED for i in issues):
            return ReportStatus.BLOCKED

        if blocking_gap or any(
            i.severity is ClearanceStatus.UNVERIFIED for i in issues
        ):
            return ReportStatus.DEGRADED

        if any(i.severity is ClearanceStatus.YELLOW for i in issues):
            return ReportStatus.PASSED_WITH_CONDITIONS

        return ReportStatus.PASSED

    def _empty_report(
        self,
        request: ComplianceRequest,
        known: Dict[str, TrackedAsset],
        reused: Sequence[TrackedAsset],
        notes: _Notes,
    ) -> ClearanceReport:
        return ClearanceReport(
            status=self._gate([], request.structural_errors, notes.blocking),
            stage=request.stage.value,
            pass_number=request.pass_number,
            issues=[],
            checked_assets=self._merge_ledger(request, known, [], reused),
            structural_errors=list(request.structural_errors),
            degraded_reasons=notes.reasons,
        )