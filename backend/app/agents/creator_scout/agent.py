"""
CreatorScout — brand and collaboration discovery.

This file holds the agent, the deterministic hard rules, and report
rendering. They are separate concerns kept in one file to keep the
drop-in small.

Pipeline for one run:

    discovery          FindAll if available, else Search + Gemini
        ↓
    hard rules         deterministic suppression, BEFORE enrichment spend
        ↓
    enrichment         Task if available, else Search + Gemini
        ↓
    capacity check     flagged, never suppressed
        ↓
    ranking            Gemini reasoning, prose the creator can argue with
        ↓
    citation enforcement   uncited commercial claims are dropped
        ↓
    OpportunityQueue


SHARED-FOLDER FOOTPRINT
-----------------------
Nothing in shared/tools/ is modified. `GeminiClient` and `ParallelSearch` are
used exactly as they exist. FindAll, Entity Search, Task and Monitor are
optional and duck-typed:

    ComplianceAgent-style injection:
        CreatorScoutAgent(findall=MyFindAll(), task=MyTask())

    With none of them (the default), the agent runs on ParallelSearch alone
    and marks every candidate as DERIVED tier, which is the weakest.

New shared model file: `shared/models/creator_scout.py`, added additively —
`CreatorRecommendation` keeps its exact shape.


WHAT IS DELIBERATELY NOT BUILT
------------------------------
  - Monitor / background watch. Needs Pub/Sub, a Cloud Run webhook endpoint
    and a persistent deal store. `describe_monitor_plan()` returns the config
    that would be registered, so the design is inspectable without the
    infrastructure.
  - Negotiation. The state machine and DealMemo exist; automated counter-
    offers do not. The agent never signs and never agrees to exclusivity.


DESIGN INVARIANTS
-----------------
  - The model never writes a URL. It cites source labels; Python resolves them.
  - Suppression is shown with its reason, never silent.
  - Capacity is flagged, not enforced. That call belongs to the creator.
  - Every tool has a degraded path, and degradation is declared in the output.
"""
import asyncio
import logging
import re
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.agents.base import BaseAgent
from app.agents.creator_scout.prompts import (
    DISCOVERY_SYSTEM_PROMPT,
    DISCOVERY_USER_TEMPLATE,
    ENRICHMENT_SYSTEM_PROMPT,
    ENRICHMENT_USER_TEMPLATE,
    OUTREACH_SYSTEM_PROMPT,
    OUTREACH_USER_TEMPLATE,
    RANKING_SYSTEM_PROMPT,
    RANKING_USER_TEMPLATE,
)
from app.agents.creator_scout.schemas import (
    BrandCandidate,
    CapacityWeek,
    CreatorScoutRequest,
    DiscoveryResult,
    EnrichmentRecord,
    EnrichmentResult,
    OutreachResult,
    RankingResult,
)
from app.shared.models.creator_scout import (
    BrandOpportunity,
    EvidenceRef,
    ExclusivityClause,
    OpportunityQueue,
    OutreachDraft,
    SuppressedOpportunity,
    SuppressionRule,
    VerificationTier,
    WatchEvent,
)
from app.shared.models.research import ResearchSource
from app.shared.tools.gemini.client import GeminiClient
from app.shared.tools.parallel.search import ParallelSearch

logger = logging.getLogger(__name__)


# ====================================================================
# HARD RULES — deterministic, applied before Gemini sees anything
# ====================================================================




def _norm(text: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower())


def _category_matches(candidate: Optional[str], rule: str) -> bool:
    """
    Substring match in both directions, so "personal finance" catches
    "personal finance app" and "finance" catches "personal finance".

    Deliberately broad. A false suppression is visible and reversible — it
    appears in the report with its reason. A false pass sends the creator into
    a contract breach.
    """

    a, b = _norm(candidate), _norm(rule)

    if not a or not b:
        return False

    return a in b or b in a


def active_clauses(
    clauses: Sequence[ExclusivityClause],
    as_of: Optional[date] = None,
) -> List[ExclusivityClause]:
    on = as_of or date.today()
    return [c for c in clauses if c.is_active(on)]


def apply_hard_rules(
    candidates: Iterable[BrandCandidate],
    excluded_categories: Sequence[str],
    exclusivity_clauses: Sequence[ExclusivityClause],
    as_of: Optional[date] = None,
) -> Tuple[List[BrandCandidate], List[SuppressedOpportunity]]:
    """Split candidates into those that survive the hard rules and those that don't."""

    on = as_of or date.today()
    live = active_clauses(exclusivity_clauses, on)

    allowed: List[BrandCandidate] = []
    suppressed: List[SuppressedOpportunity] = []

    for candidate in candidates:
        blocked = False

        # 1 — exclusivity. Checked first because it carries a date the creator
        # will want to see.
        for clause in live:
            if _category_matches(candidate.category, clause.category):
                held_by = f" held by {clause.brand_name}" if clause.brand_name else ""
                territory = f" in {clause.territory}" if clause.territory else ""

                suppressed.append(
                    SuppressedOpportunity(
                        brand_name=candidate.brand_name,
                        category=candidate.category,
                        rule=SuppressionRule.ACTIVE_EXCLUSIVITY,
                        reason=(
                            f"'{clause.category}' exclusivity{held_by}{territory} "
                            f"runs until {clause.expires_on.isoformat()}. "
                            f"Free to approach after that date."
                        ),
                    )
                )
                blocked = True
                break

        if blocked:
            continue

        # 2 — the creator's own exclusion list
        for excluded in excluded_categories:
            if _category_matches(candidate.category, excluded):
                suppressed.append(
                    SuppressedOpportunity(
                        brand_name=candidate.brand_name,
                        category=candidate.category,
                        rule=SuppressionRule.CREATOR_EXCLUSION_LIST,
                        reason=f"'{excluded}' is on your exclusion list.",
                    )
                )
                blocked = True
                break

        if blocked:
            continue

        allowed.append(candidate)

    return allowed, suppressed


def capacity_warning(
    capacity: Sequence[CapacityWeek],
    deliverables_required: int = 1,
) -> Optional[str]:
    """
    Flag, never suppress. Returns a sentence for the creator, or None.

    Deliberately does not know a deadline: enrichment rarely produces a
    reliable one, and inventing a date to check against would be worse than
    reporting the shape of the next few weeks honestly.
    """

    if not capacity:
        return None

    free = sum(week.free_slots for week in capacity)

    if free >= deliverables_required:
        return None

    weeks = len(capacity)
    plural = "s" if weeks != 1 else ""

    if free == 0:
        return (
            f"Your next {weeks} week{plural} are fully committed. Taking this "
            "means moving something already promised."
        )

    return (
        f"Only {free} free slot{'s' if free != 1 else ''} across the next "
        f"{weeks} week{plural}, against {deliverables_required} needed here."
    )


# ====================================================================
# THE AGENT
# ====================================================================




MAX_CONCURRENT_RESEARCH = 4
MAX_SOURCES_PER_QUERY = 5
MAX_EXCERPTS_SHOWN = 4

SOURCE_LABEL_RE = re.compile(r"^S\d+$")


def _slug(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


class _Notes:
    """
    Why the run was imperfect, and whether that means a claim went unverified.

    Same split as ClearanceCheck: a missing optional tool is a note, a failed
    lookup that leaves a commercial claim uncited is a gap.
    """

    def __init__(self) -> None:
        self.reasons: List[str] = []
        self.blocking = False

    def note(self, message: str) -> None:
        self.reasons.append(message)

    def gap(self, message: str) -> None:
        self.reasons.append(message)
        self.blocking = True


class CreatorScoutAgent(BaseAgent):
    """
    Finds brands worth approaching and ranks them against this specific creator.

    All Parallel products beyond Search are optional:

        findall  — verified entity discovery against explicit match conditions
        entity   — synchronous lookup for "who's in skincare right now"
        task     — multi-hop enrichment with per-field citations
        monitor  — background watch (config only; needs Pub/Sub to run)
    """

    name = "creator_scout"

    def __init__(
        self,
        gemini: Optional[GeminiClient] = None,
        search: Optional[ParallelSearch] = None,
        findall: Optional[Any] = None,
        entity_search: Optional[Any] = None,
        task: Optional[Any] = None,
        monitor: Optional[Any] = None,
        discovery_model: Optional[str] = None,
        ranking_model: Optional[str] = None,
    ):
        self.gemini = gemini or GeminiClient()
        self.search = search or ParallelSearch()

        self.findall = findall
        self.entity_search = entity_search
        self.task = task
        self.monitor = monitor

        # Discovery and enrichment are extraction work. Ranking is judgement.
        self.discovery_model = discovery_model
        self.ranking_model = ranking_model

    # ------------------------------------------------------------------
    # Gemini access — uses the shared client as it exists today
    # ------------------------------------------------------------------

    def _structured_sync(self, prompt: str, schema, model: Optional[str]):
        return self.gemini.generate_structured(
            prompt=prompt,
            response_schema=schema,
            model=model,
        )

    async def _structured(self, prompt: str, schema, model: Optional[str] = None):
        return await asyncio.to_thread(self._structured_sync, prompt, schema, model)

    # ------------------------------------------------------------------
    # entry point
    # ------------------------------------------------------------------

    async def run(
        self,
        request: CreatorScoutRequest,
        seed_brands: Optional[Sequence[BrandCandidate]] = None,
        signals: Optional[Sequence[WatchEvent]] = None,
    ) -> OpportunityQueue:
        """
        `seed_brands` skips discovery and re-scouts a known list. This is what
        the background watch uses: when a signal fires for a brand already in
        the queue, there is no reason to rediscover the universe.

        `signals` are passed into the ranking prompt as timing evidence. A
        funding round three days old is exactly the kind of thing the ranker is
        asked to weigh, and without this it never sees one.

        Hard rules still apply to seeded brands. A watch event does not
        override an exclusivity clause.
        """

        notes = _Notes()
        as_of = request.as_of or date.today()

        # 1 — build the candidate universe
        candidates, discovery_sources, tier = await self._discover(
            request, notes, seed_brands
        )

        if not candidates:
            return OpportunityQueue(
                exclusivity_ledger=active_clauses(request.exclusivity_clauses, as_of),
                degraded_reasons=notes.reasons
                or ["No candidate brands were found."],
            )

        # 2 — hard rules, before spending anything on enrichment
        allowed, suppressed = apply_hard_rules(
            candidates=candidates,
            excluded_categories=request.excluded_categories,
            exclusivity_clauses=request.exclusivity_clauses,
            as_of=as_of,
        )

        if not allowed:
            return OpportunityQueue(
                suppressed=suppressed,
                exclusivity_ledger=active_clauses(request.exclusivity_clauses, as_of),
                degraded_reasons=notes.reasons
                + [
                    "Every candidate was suppressed by a hard rule. Widen the "
                    "categories of interest, or wait for an exclusivity clause "
                    "to expire."
                ],
            )

        # 3 — enrichment
        records, enrichment_sources = await self._enrich(request, allowed, notes)

        # 4 — one registry across both research phases, so ranking can cite
        #     discovery evidence too
        registry, sources_block = self._build_source_registry(
            discovery_sources + enrichment_sources
        )

        if not registry:
            notes.gap(
                "No usable web sources were returned; nothing in this queue "
                "can be cited."
            )

        # 5 — ranking
        ranked = await self._rank(
            request, allowed, records, sources_block, notes, signals
        )

        # 6 — assemble, enforcing citations
        opportunities = self._compile(
            request, allowed, records, ranked, registry, tier, notes
        )

        return OpportunityQueue(
            opportunities=opportunities,
            suppressed=suppressed,
            exclusivity_ledger=active_clauses(request.exclusivity_clauses, as_of),
            degraded_reasons=notes.reasons,
        )

    # ------------------------------------------------------------------
    # 1 — discovery
    # ------------------------------------------------------------------

    async def _discover(
        self,
        request: CreatorScoutRequest,
        notes: _Notes,
        seed_brands: Optional[Sequence[BrandCandidate]] = None,
    ) -> Tuple[List[BrandCandidate], List[ResearchSource], VerificationTier]:
        if seed_brands:
            notes.note(
                f"Re-scouting {len(seed_brands)} known brand(s); discovery "
                "skipped."
            )

            # Hard rules match on category. A seed without one silently passes
            # every suppression check, which is exactly the failure that puts a
            # creator into a contract breach. Say so rather than let it through
            # quietly.
            uncategorised = [c.brand_name for c in seed_brands if not c.category]
            if uncategorised:
                notes.gap(
                    "Category unknown for "
                    + ", ".join(uncategorised)
                    + ". Exclusivity and exclusion rules could NOT be applied "
                    "to these. Confirm manually before pitching."
                )

            return list(seed_brands), [], VerificationTier.UNVERIFIED

        if self.findall is not None:
            candidates = await self._discover_via_findall(request, notes)
            if candidates:
                return candidates, [], VerificationTier.VERIFIED
            notes.note("FindAll returned nothing; falling back to Search.")

        else:
            notes.note(
                "Parallel FindAll not enabled. Candidates are derived from "
                "general search rather than matched against explicit "
                "conditions, so treat them as unconfirmed leads."
            )

        sources = await self._search_many(
            queries=[
                f"{cat} brands sponsored creator campaign {request.target_geography}"
                for cat in (
                    request.categories_of_interest or [request.niche or "brands"]
                )
            ],
            objective=(
                f"Find brands that ran paid creator campaigns targeting "
                f"{request.target_geography} audiences in "
                f"{request.niche or 'this creator category'}."
            ),
            notes=notes,
        )

        if not sources:
            return [], [], VerificationTier.DERIVED

        _, sources_block = self._build_source_registry(sources)

        prompt = DISCOVERY_SYSTEM_PROMPT + "\n\n" + DISCOVERY_USER_TEMPLATE.format(
            niche=request.niche or "Not specified",
            audience=request.audience_summary or "Not specified",
            geography=request.target_geography,
            categories=", ".join(request.categories_of_interest) or "Not specified",
            lookback_days=request.lookback_days,
            max_candidates=request.max_candidates,
            sources=sources_block,
        )

        try:
            result = await self._structured(
                prompt, DiscoveryResult, self.discovery_model
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Candidate discovery failed")
            notes.gap(f"Candidate discovery failed: {exc}")
            return [], sources, VerificationTier.DERIVED

        candidates = [
            c
            for c in (getattr(result, "candidates", []) or [])
            if c.spends_on_creators
        ][: request.max_candidates]

        dropped = len(getattr(result, "candidates", []) or []) - len(candidates)
        if dropped > 0:
            notes.note(
                f"{dropped} candidate(s) dropped: no evidence of actual creator "
                "spend, only general advertising."
            )

        return candidates, sources, VerificationTier.DERIVED

    async def _discover_via_findall(
        self,
        request: CreatorScoutRequest,
        notes: _Notes,
    ) -> List[BrandCandidate]:
        """
        FindAll matches against explicit, testable conditions, which is what
        makes its results VERIFIED rather than merely plausible.
        """

        objective = (
            f"Brands in {', '.join(request.categories_of_interest) or request.niche} "
            f"that ran paid creator campaigns targeting "
            f"{request.target_geography} audiences in the last "
            f"{request.lookback_days} days"
        )

        match_conditions = [
            {
                "name": "active_creator_spend",
                "description": (
                    "Company shows evidence of a sponsored creator "
                    f"collaboration published within the last "
                    f"{request.lookback_days} days"
                ),
            },
            {
                "name": "geo_match",
                "description": (
                    f"Company sells or operates in {request.target_geography}"
                ),
            },
            {
                "name": "category_fit",
                "description": (
                    "Core product is in "
                    f"{', '.join(request.categories_of_interest) or 'the creator category'} "
                    "— not merely adjacent to it"
                ),
            },
        ]

        try:
            result = await self.findall.create(
                objective=objective,
                entity_type="companies",
                match_conditions=match_conditions,
                generator=request.findall_generator,
                match_limit=request.max_candidates,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("FindAll failed: %s", exc)
            notes.note(f"FindAll failed ({exc}); falling back to Search.")
            return []

        candidates: List[BrandCandidate] = []

        for item in getattr(result, "results", None) or []:
            name = getattr(item, "name", None) or getattr(item, "entity_name", None)
            if not name:
                continue

            candidates.append(
                BrandCandidate(
                    brand_name=name,
                    category=getattr(item, "category", None),
                    why_relevant=(
                        getattr(item, "reason", None)
                        or "Matched the FindAll conditions."
                    ),
                    spends_on_creators=True,
                )
            )

        return candidates

    # ------------------------------------------------------------------
    # 3 — enrichment
    # ------------------------------------------------------------------

    async def _enrich(
        self,
        request: CreatorScoutRequest,
        candidates: Sequence[BrandCandidate],
        notes: _Notes,
    ) -> Tuple[List[EnrichmentRecord], List[ResearchSource]]:
        if self.task is None:
            notes.note(
                "Parallel Task not enabled. Enrichment is synthesised from "
                "search excerpts rather than multi-hop research with per-field "
                "citations, so contact routes and deliverable expectations are "
                "weaker."
            )

        sources = await self._search_many(
            queries=[
                f"{c.brand_name} creator program influencer collaboration"
                for c in candidates
            ],
            objective=(
                "Find each brand's creator program, booking agency, recent "
                "campaigns, contact route, and how it handles exclusivity."
            ),
            notes=notes,
        )

        if not sources:
            notes.gap("No enrichment sources found for any candidate.")
            return [], []

        _, sources_block = self._build_source_registry(sources)

        prompt = ENRICHMENT_SYSTEM_PROMPT + "\n\n" + ENRICHMENT_USER_TEMPLATE.format(
            niche=request.niche or "Not specified",
            geography=request.target_geography,
            brands="\n".join(
                f"- {c.brand_name} ({c.category or 'category unknown'})"
                for c in candidates
            ),
            sources=sources_block,
        )

        try:
            result = await self._structured(
                prompt, EnrichmentResult, self.discovery_model
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Enrichment failed")
            notes.gap(f"Enrichment failed: {exc}")
            return [], sources

        return list(getattr(result, "records", []) or []), sources

    # ------------------------------------------------------------------
    # 5 — ranking
    # ------------------------------------------------------------------

    async def _rank(
        self,
        request: CreatorScoutRequest,
        candidates: Sequence[BrandCandidate],
        records: Sequence[EnrichmentRecord],
        sources_block: str,
        notes: _Notes,
        signals: Optional[Sequence[WatchEvent]] = None,
    ) -> List:
        by_name = {_slug(r.brand_name): r for r in records}

        candidate_block = "\n\n".join(
            self._format_candidate(c, by_name.get(_slug(c.brand_name)))
            for c in candidates
        )

        past = (
            "\n".join(
                f"- {d.brand_name} ({d.category or 'category unknown'}), "
                f"fee {d.fee or 'undisclosed'}, "
                f"paid on time: {d.paid_on_time if d.paid_on_time is not None else 'unknown'}"
                for d in request.past_deals
            )
            or "None recorded."
        )

        exclusivity = (
            "\n".join(
                f"- {c.category} until {c.expires_on.isoformat()}"
                f"{f' ({c.brand_name})' if c.brand_name else ''}"
                for c in active_clauses(request.exclusivity_clauses, request.as_of)
            )
            or "None active."
        )

        signal_block = (
            "\n".join(
                f"- {e.brand_name}: {e.signal.value} — {e.summary}"
                + (f" ({e.why_it_matters})" if e.why_it_matters else "")
                + ("  [WINDOW OPEN NOW]" if e.act_now else "")
                for e in (signals or [])
            )
            or "None detected."
        )

        prompt = RANKING_SYSTEM_PROMPT + "\n\n" + RANKING_USER_TEMPLATE.format(
            creator_name=request.creator_name,
            niche=request.niche or "Not specified",
            audience=request.audience_summary or "Not specified",
            median_views=request.median_views or "Not specified",
            engagement_rate=request.engagement_rate or "Not specified",
            formats=", ".join(request.formats) or "Not specified",
            languages=", ".join(request.languages) or "Not specified",
            rate_floor=request.rate_floor or "Not specified",
            deal_structure=request.preferred_deal_structure or "Not specified",
            past_deals=past,
            exclusivity=exclusivity,
            signals=signal_block,
            candidates=candidate_block,
            sources=sources_block,
        )

        try:
            result = await self._structured(prompt, RankingResult, self.ranking_model)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Ranking failed")
            notes.gap(f"Ranking failed: {exc}")
            return []

        return list(getattr(result, "items", []) or [])

    @staticmethod
    def _format_candidate(
        candidate: BrandCandidate,
        record: Optional[EnrichmentRecord],
    ) -> str:
        lines = [
            f"- BRAND: {candidate.brand_name}",
            f"  CATEGORY: {candidate.category or 'unknown'}",
            f"  RELEVANCE: {candidate.why_relevant}",
        ]

        if record:
            if record.has_creator_program is not None:
                lines.append(f"  CREATOR PROGRAM: {record.has_creator_program}")
            if record.booking_agency:
                lines.append(f"  AGENCY: {record.booking_agency}")
            if record.recent_campaigns:
                lines.append(
                    f"  RECENT CAMPAIGNS: {'; '.join(record.recent_campaigns[:3])}"
                )
            if record.typical_deliverables:
                lines.append(f"  DELIVERABLES: {record.typical_deliverables}")
            if record.exclusivity_practice:
                lines.append(f"  EXCLUSIVITY PRACTICE: {record.exclusivity_practice}")
            if record.campaign_seasonality:
                lines.append(f"  SEASONALITY: {record.campaign_seasonality}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 6 — assembly with citation enforcement
    # ------------------------------------------------------------------

    def _compile(
        self,
        request: CreatorScoutRequest,
        candidates: Sequence[BrandCandidate],
        records: Sequence[EnrichmentRecord],
        ranked: Sequence,
        registry: Dict[str, ResearchSource],
        tier: VerificationTier,
        notes: _Notes,
    ) -> List[BrandOpportunity]:
        by_name = {_slug(c.brand_name): c for c in candidates}
        records_by_name = {_slug(r.brand_name): r for r in records}

        warning = capacity_warning(request.capacity)

        opportunities: List[BrandOpportunity] = []
        seen: set = set()

        for item in ranked:
            key = _slug(item.brand_name)
            candidate = by_name.get(key)

            if not candidate:
                notes.note(
                    f"Ranking returned '{item.brand_name}', which was not in "
                    "the candidate list. Dropped."
                )
                continue

            seen.add(key)
            record = records_by_name.get(key)

            evidence = self._resolve(item.cited_claims, registry)
            if record:
                evidence += self._resolve(record.cited_claims, registry)

            if not evidence:
                notes.note(
                    f"'{item.brand_name}' has no resolvable source. Enrichment "
                    "fields were dropped and the entry is marked unverified."
                )

            opportunities.append(
                BrandOpportunity(
                    brand_name=candidate.brand_name,
                    category=candidate.category,
                    tier=tier if evidence else VerificationTier.UNVERIFIED,
                    # Enrichment fields survive only with a source behind them.
                    has_creator_program=(
                        record.has_creator_program if record and evidence else None
                    ),
                    program_url=self._resolve_url(
                        record.program_url_source_id if record else None, registry
                    ),
                    booking_agency=(
                        record.booking_agency if record and evidence else None
                    ),
                    recent_campaigns=(
                        list(record.recent_campaigns) if record and evidence else []
                    ),
                    contact_route=(
                        record.contact_route if record and evidence else None
                    ),
                    typical_deliverables=(
                        record.typical_deliverables if record and evidence else None
                    ),
                    exclusivity_practice=(
                        record.exclusivity_practice if record and evidence else None
                    ),
                    campaign_seasonality=(
                        record.campaign_seasonality if record and evidence else None
                    ),
                    rank=item.rank,
                    audience_fit=item.audience_fit,
                    brand_fit=item.brand_fit,
                    commercial_fit=item.commercial_fit,
                    overall_score=self._overall(item),
                    rationale=item.rationale,
                    cautions=list(item.cautions or []),
                    capacity_warning=warning,
                    evidence=evidence,
                )
            )

        # A candidate the ranker silently dropped is still a lead, just an
        # unranked one. Losing it would hide work the creator paid for.
        for candidate in candidates:
            if _slug(candidate.brand_name) in seen:
                continue

            notes.note(
                f"'{candidate.brand_name}' was discovered but not ranked. "
                "Listed unranked."
            )

            opportunities.append(
                BrandOpportunity(
                    brand_name=candidate.brand_name,
                    category=candidate.category,
                    tier=VerificationTier.UNVERIFIED,
                    rationale=candidate.why_relevant,
                    capacity_warning=warning,
                )
            )

        opportunities.sort(key=lambda o: (o.rank is None, o.rank or 0))

        return opportunities

    @staticmethod
    def _resolve(
        claims: Sequence,
        registry: Dict[str, ResearchSource],
    ) -> List[EvidenceRef]:
        out: List[EvidenceRef] = []

        for cited in claims or []:
            label = (getattr(cited, "source_id", "") or "").strip().upper()

            if not SOURCE_LABEL_RE.match(label):
                continue

            source = registry.get(label)
            if not source:
                continue

            out.append(
                EvidenceRef(
                    claim=cited.claim,
                    url=source.url,
                    title=source.title,
                    excerpt=source.excerpts[0] if source.excerpts else None,
                )
            )

        return out

    @staticmethod
    def _resolve_url(
        source_id: Optional[str],
        registry: Dict[str, ResearchSource],
    ) -> Optional[str]:
        if not source_id:
            return None

        label = source_id.strip().upper()
        if not SOURCE_LABEL_RE.match(label):
            return None

        source = registry.get(label)
        return source.url if source else None

    @staticmethod
    def _overall(item) -> Optional[float]:
        parts = [
            v
            for v in (item.audience_fit, item.brand_fit, item.commercial_fit)
            if v is not None
        ]
        return round(sum(parts) / len(parts), 3) if parts else None

    # ------------------------------------------------------------------
    # search helper
    # ------------------------------------------------------------------

    async def _search_many(
        self,
        queries: Sequence[str],
        objective: str,
        notes: _Notes,
    ) -> List[ResearchSource]:
        sem = asyncio.Semaphore(MAX_CONCURRENT_RESEARCH)

        async def one(query: str) -> List[ResearchSource]:
            async with sem:
                try:
                    result = await self.search.search(
                        search_queries=[query],
                        objective=objective,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Search failed for '%s': %s", query, exc)
                    notes.gap(f"Search failed for '{query}': {exc}")
                    return []

            return list(result.sources or [])[:MAX_SOURCES_PER_QUERY]

        batches = await asyncio.gather(*(one(q) for q in queries))

        by_url: Dict[str, ResearchSource] = {}
        for batch in batches:
            for source in batch:
                by_url.setdefault(source.url, source)

        return list(by_url.values())

    @staticmethod
    def _build_source_registry(
        sources: Sequence[ResearchSource],
    ) -> Tuple[Dict[str, ResearchSource], str]:
        registry: Dict[str, ResearchSource] = {}
        blocks: List[str] = []
        seen: set = set()

        index = 0
        for source in sources:
            if source.url in seen:
                continue
            seen.add(source.url)

            index += 1
            label = f"S{index}"
            registry[label] = source

            excerpts = (
                "\n".join(f"  - {e}" for e in source.excerpts[:MAX_EXCERPTS_SHOWN])
                or "  (none)"
            )

            blocks.append(
                f"[{label}] {source.title}\n"
                f"  published: {source.publish_date or 'unknown'}\n"
                f"{excerpts}"
            )

        return registry, "\n\n".join(blocks) or "No sources were retrieved."

    # ------------------------------------------------------------------
    # outreach
    # ------------------------------------------------------------------

    async def draft_outreach(
        self,
        request: CreatorScoutRequest,
        opportunity: BrandOpportunity,
    ) -> Optional[OutreachDraft]:
        """
        Draft a first-contact message from the enrichment record.

        Returns None for an opportunity with no evidence behind it: a pitch
        built on an unverified campaign is worse than no pitch.
        """

        if not opportunity.evidence:
            logger.info(
                "Refusing to draft outreach for '%s': no evidence.",
                opportunity.brand_name,
            )
            return None

        enrichment = "\n".join(
            f"- {label}: {value}"
            for label, value in (
                ("Creator program", opportunity.has_creator_program),
                ("Agency", opportunity.booking_agency),
                ("Recent campaigns", "; ".join(opportunity.recent_campaigns)),
                ("Typical deliverables", opportunity.typical_deliverables),
                ("Seasonality", opportunity.campaign_seasonality),
            )
            if value
        )

        registry = {
            f"S{i}": ResearchSource(
                title=ref.title or ref.url,
                url=ref.url,
                excerpts=[ref.excerpt] if ref.excerpt else [],
            )
            for i, ref in enumerate(opportunity.evidence, start=1)
        }

        _, sources_block = self._build_source_registry(list(registry.values()))

        prompt = OUTREACH_SYSTEM_PROMPT + "\n\n" + OUTREACH_USER_TEMPLATE.format(
            creator_name=request.creator_name,
            niche=request.niche or "Not specified",
            audience=request.audience_summary or "Not specified",
            median_views=request.median_views or "Not specified",
            formats=", ".join(request.formats) or "Not specified",
            brand_name=opportunity.brand_name,
            enrichment=enrichment or "Little is known beyond the category.",
            sources=sources_block,
        )

        try:
            result = await self._structured(prompt, OutreachResult, self.ranking_model)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Outreach drafting failed")
            return None

        return OutreachDraft(
            brand_name=opportunity.brand_name,
            subject=result.subject,
            body=result.body,
            personalisation_basis=self._resolve(
                result.personalisation_claims, registry
            ),
        )

    # ------------------------------------------------------------------
    # background watch — config only
    # ------------------------------------------------------------------

    def describe_monitor_plan(
        self,
        watchlist: Sequence[str],
        webhook_url: str,
    ) -> Dict[str, Any]:
        """
        The Monitor config that would be registered, without registering it.

        Running this for real needs Pub/Sub and a Cloud Run endpoint, which is
        out of scope for a local build. Returning the config keeps the design
        inspectable and makes the eventual wiring a one-line change.

        Why these signals: a funding round means budget, a new marketing head
        means vendors get reset, a product launch means a live campaign window.
        Creator marketing is won on timing more than on pitch quality.

        No dates go in the query — freshness is handled server-side.
        """

        return {
            "type": "event_stream",
            "frequency": "1d",
            "processor": "base",
            "settings": {
                "query": (
                    "Product launches, funding rounds, marketing-head changes, "
                    "and creator campaign announcements at "
                    + ", ".join(watchlist)
                ),
            },
            "webhook": {
                "url": webhook_url,
                "event_types": ["monitor.event.detected"],
            },
            "_note": (
                "Cancel monitors for brands the creator has ruled out — each "
                "active monitor consumes usage on every run."
            ),
        }


# ====================================================================
# RENDERING
# ====================================================================



TIER_MARK = {
    VerificationTier.VERIFIED: "",
    VerificationTier.UNVERIFIED: "  [unverified]",
    VerificationTier.DERIVED: "  [lead, not confirmed]",
}


def _wrap(text: str, indent: str = "     ", width: int = 70) -> str:
    words = (text or "").split()
    lines: List[str] = []
    current = ""

    for word in words:
        if len(current) + len(word) + 1 > width:
            lines.append(indent + current)
            current = word
        else:
            current = f"{current} {word}".strip()

    if current:
        lines.append(indent + current)

    return "\n".join(lines)


def _render_opportunity(opp: BrandOpportunity) -> str:
    rank = f"Rank {opp.rank}" if opp.rank is not None else "Unranked"
    category = f" — {opp.category}" if opp.category else ""

    out = [f"{rank} — {opp.brand_name}{category}{TIER_MARK.get(opp.tier, '')}"]

    if opp.rationale:
        out.append(_wrap(opp.rationale))

    facts = [
        ("Program", opp.program_url),
        ("Agency", opp.booking_agency),
        ("Contact", opp.contact_route),
        ("Deliverables", opp.typical_deliverables),
        ("Exclusivity practice", opp.exclusivity_practice),
        ("Timing", opp.campaign_seasonality),
    ]

    for label, value in facts:
        if value:
            out.append(_wrap(f"{label}: {value}"))

    for caution in opp.cautions:
        out.append(_wrap(f"Caution: {caution}"))

    if opp.capacity_warning:
        out.append(_wrap(f"Capacity: {opp.capacity_warning}"))

    for ref in opp.evidence[:4]:
        out.append(_wrap(f"{ref.claim}  → {ref.url}"))

    if not opp.evidence:
        out.append(_wrap("No source attached — treat every claim above as unconfirmed."))

    return "\n".join(out)


def render_queue(queue: OpportunityQueue, creator_name: str = "") -> str:
    lines: List[str] = ["OPPORTUNITY QUEUE"]

    if creator_name:
        lines.append(f"Creator: {creator_name}")

    lines.append("")

    if queue.opportunities:
        for opp in queue.opportunities:
            lines.append(_render_opportunity(opp))
            lines.append("")
    else:
        lines.append("No opportunities in this run.")
        lines.append("")

    if queue.suppressed:
        lines.append("SUPPRESSED")
        for item in queue.suppressed:
            lines.append(f"   {item.brand_name} — {item.rule.value}")
            lines.append(_wrap(item.reason, indent="      "))
        lines.append("")

    if queue.exclusivity_ledger:
        lines.append("EXCLUSIVITY LEDGER")
        for clause in queue.exclusivity_ledger:
            held = f" ({clause.brand_name})" if clause.brand_name else ""
            lines.append(
                f"   {clause.category}{held} — until {clause.expires_on.isoformat()}"
            )
        lines.append("")

    if queue.degraded_reasons:
        lines.append("VERIFICATION GAPS")
        for reason in queue.degraded_reasons:
            lines.append(_wrap(f"• {reason}", indent="   "))
        lines.append("")

    ranked = sum(1 for o in queue.opportunities if o.rank is not None)
    lines.append(
        f"SUMMARY: {ranked} ranked, "
        f"{len(queue.opportunities) - ranked} unranked, "
        f"{len(queue.suppressed)} suppressed."
    )

    return "\n".join(lines)