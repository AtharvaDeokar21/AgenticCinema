"""
Background watch, by polling.

This file holds three things that belong to one loop:

    WatchStore / WatchState   local JSON memory of what has been seen
    BrandWatcher              the poll -> diff -> classify cycle
    rescout_on_events         the bridge that wakes the agent

WHY POLLING RATHER THAN PARALLEL MONITOR
----------------------------------------
Monitor pushes to a webhook, which needs a publicly reachable HTTPS endpoint,
which in the workflow doc means Cloud Run plus Pub/Sub. This is the same idea
without the infrastructure: search the watchlist on a schedule, diff against
what was seen last run, classify what is new. The creator gets the same
artifact from a scheduled task on a laptop.

What is genuinely lost: server-side change detection (we pay for searches on
quiet days), push latency (one poll cycle instead of minutes), and durability
(a sleeping laptop does not poll). Swapping Monitor in later means replacing
`poll()` with a webhook handler that calls `_classify()`; classification,
dedup and storage are unchanged.

IDEMPOTENCY
-----------
Dedup is on source URL, held in the store. The same page never produces two
events, which matters because re-classifying costs a Gemini call and
re-reporting trains the creator to ignore the feed.
"""
import asyncio
import hashlib
import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from pydantic import BaseModel, Field

from app.agents.creator_scout.agent import CreatorScoutAgent
from app.agents.creator_scout.prompts import (
    WATCH_SYSTEM_PROMPT,
    WATCH_USER_TEMPLATE,
)
from app.agents.creator_scout.schemas import (
    BrandCandidate,
    CreatorScoutRequest,
    WatchClassification,
)
from app.shared.models.creator_scout import (
    BrandOpportunity,
    EvidenceRef,
    OpportunityQueue,
    WatchEvent,
    WatchReport,
)
from app.shared.models.research import ResearchSource
from app.shared.tools.gemini.client import GeminiClient
from app.shared.tools.parallel.search import ParallelSearch

logger = logging.getLogger(__name__)


# ====================================================================
# STORE — local memory, so a repeat page is not a repeat event
# ====================================================================





DEFAULT_STORE_PATH = Path(".watch") / "creator_scout.json"

# Unbounded growth would make every run slower and the file harder to read.
# Oldest URLs fall off first; re-reporting a year-old page is an acceptable
# failure mode.
MAX_SEEN_URLS = 5_000

MAX_STORED_EVENTS = 500


class WatchState(BaseModel):
    watchlist: List[str] = Field(default_factory=list)

    # Insertion-ordered. Oldest first, so trimming from the front drops the
    # least recently discovered.
    seen_urls: List[str] = Field(default_factory=list)

    events: List[WatchEvent] = Field(default_factory=list)

    last_run: Optional[datetime] = None

    def seen(self) -> Set[str]:
        return set(self.seen_urls)

    def mark_seen(self, urls: Iterable[str]) -> int:
        """Returns how many were genuinely new."""

        existing = self.seen()
        added = 0

        for url in urls:
            if url and url not in existing:
                self.seen_urls.append(url)
                existing.add(url)
                added += 1

        if len(self.seen_urls) > MAX_SEEN_URLS:
            self.seen_urls = self.seen_urls[-MAX_SEEN_URLS:]

        return added

    def record(self, events: Iterable[WatchEvent]) -> None:
        known = {e.event_id for e in self.events}

        for event in events:
            if event.event_id not in known:
                self.events.append(event)
                known.add(event.event_id)

        if len(self.events) > MAX_STORED_EVENTS:
            self.events = self.events[-MAX_STORED_EVENTS:]


class WatchStore:
    """Load and save WatchState. Missing file means an empty state, not an error."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else DEFAULT_STORE_PATH

    def load(self) -> WatchState:
        if not self.path.exists():
            return WatchState()

        try:
            raw = self.path.read_text(encoding="utf-8")
            return WatchState.model_validate_json(raw)
        except Exception as exc:  # noqa: BLE001
            # A corrupt store must not stop the watch. Starting fresh
            # re-reports old events, which is noisy but harmless; refusing to
            # run means the creator silently stops getting signals.
            logger.warning(
                "Watch store at %s is unreadable (%s); starting fresh.",
                self.path,
                exc,
            )
            return WatchState()

    def save(self, state: WatchState) -> None:
        state.last_run = datetime.now(timezone.utc)

        self.path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic: a crash mid-write leaves the previous file intact rather
        # than a truncated one that fails to parse on the next run.
        fd, tmp = tempfile.mkstemp(
            dir=str(self.path.parent), prefix=".tmp_", suffix=".json"
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(state.model_dump_json(indent=2))
            os.replace(tmp, self.path)
        except Exception:
            Path(tmp).unlink(missing_ok=True)
            raise


# ====================================================================
# WATCHER — poll, diff, classify
# ====================================================================




MAX_CONCURRENT_SEARCHES = 4
MAX_SOURCES_PER_BRAND = 5
MAX_NEW_SOURCES_PER_RUN = 30

SOURCE_LABEL_RE = re.compile(r"^S\d+$")

# One query per brand covering all four signal types. No dates in the query —
# recency is handled by diffing against what we have already seen, so a date
# filter would only narrow the candidate pool for no benefit.
BRAND_QUERY = (
    "{brand} funding round OR product launch OR new marketing head "
    "OR creator campaign announcement"
)

WATCH_OBJECTIVE = (
    "Find recent developments at these brands that indicate creator marketing "
    "budget is available or about to move: funding, product launches, "
    "marketing leadership changes, and published creator campaigns."
)


def event_id(brand: str, url: str) -> str:
    """Stable across runs, so the same page never fires twice."""
    raw = f"{brand.strip().lower()}|{url.strip()}"
    return "evt_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


class BrandWatcher:
    """
    Polls a watchlist and reports what is new.

    Run it from Task Scheduler, cron, or by hand:

        python -m scripts.run_watch --brands "PayGrid,LedgerUp"
    """

    def __init__(
        self,
        gemini: Optional[GeminiClient] = None,
        search: Optional[ParallelSearch] = None,
        store: Optional[WatchStore] = None,
        model: Optional[str] = None,
    ):
        self.gemini = gemini or GeminiClient()
        self.search = search or ParallelSearch()
        self.store = store or WatchStore()
        self.model = model

    # ------------------------------------------------------------------

    def _classify_sync(self, prompt: str):
        return self.gemini.generate_structured(
            prompt=prompt,
            response_schema=WatchClassification,
            model=self.model,
        )

    async def _classify_call(self, prompt: str):
        return await asyncio.to_thread(self._classify_sync, prompt)

    # ------------------------------------------------------------------
    # entry point
    # ------------------------------------------------------------------

    async def poll(
        self,
        watchlist: Optional[Sequence[str]] = None,
        persist: bool = True,
    ) -> WatchReport:
        state = self.store.load()

        brands = list(watchlist or state.watchlist)

        if not brands:
            return WatchReport(
                degraded_reasons=[
                    "Watchlist is empty. Pass --brands, or add brands to the "
                    "store, and nothing will be polled until you do."
                ]
            )

        # Remember the watchlist so the next run needs no arguments.
        state.watchlist = brands

        degraded: List[str] = []

        sources = await self._search_brands(brands, degraded)

        already = state.seen()
        fresh = [s for s in sources if s.url not in already][
            :MAX_NEW_SOURCES_PER_RUN
        ]

        report = WatchReport(
            brands_checked=brands,
            urls_seen=len(sources),
            urls_new=len(fresh),
            degraded_reasons=degraded,
        )

        if not fresh:
            # Nothing new is the expected outcome on most days. Record the run
            # so `last_run` stays honest, and spend nothing on Gemini.
            if persist:
                self.store.save(state)
            return report

        events = await self._classify(brands, fresh, degraded)

        # Mark seen regardless of whether anything classified. A page that was
        # noise this run is still noise next run, and re-classifying it would
        # pay for the same answer twice.
        state.mark_seen(s.url for s in fresh)
        state.record(events)

        if persist:
            self.store.save(state)

        report.new_events = events
        report.degraded_reasons = degraded

        return report

    # ------------------------------------------------------------------

    async def _search_brands(
        self,
        brands: Sequence[str],
        degraded: List[str],
    ) -> List[ResearchSource]:
        sem = asyncio.Semaphore(MAX_CONCURRENT_SEARCHES)

        async def one(brand: str) -> List[ResearchSource]:
            async with sem:
                try:
                    result = await self.search.search(
                        search_queries=[BRAND_QUERY.format(brand=brand)],
                        objective=WATCH_OBJECTIVE,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Watch search failed for %s: %s", brand, exc)
                    degraded.append(f"Search failed for '{brand}': {exc}")
                    return []

            return list(result.sources or [])[:MAX_SOURCES_PER_BRAND]

        batches = await asyncio.gather(*(one(b) for b in brands))

        by_url: Dict[str, ResearchSource] = {}
        for batch in batches:
            for source in batch:
                if source.url:
                    by_url.setdefault(source.url, source)

        return list(by_url.values())

    # ------------------------------------------------------------------

    async def _classify(
        self,
        brands: Sequence[str],
        sources: Sequence[ResearchSource],
        degraded: List[str],
    ) -> List[WatchEvent]:
        registry, block = self._build_source_registry(sources)

        prompt = WATCH_SYSTEM_PROMPT + "\n\n" + WATCH_USER_TEMPLATE.format(
            watchlist=", ".join(brands),
            sources=block,
        )

        try:
            result = await self._classify_call(prompt)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Watch classification failed")
            degraded.append(f"Signal classification failed: {exc}")
            return []

        known = {b.strip().lower() for b in brands}
        events: List[WatchEvent] = []
        seen_ids: set = set()

        for signal in getattr(result, "signals", []) or []:
            # A signal about a brand nobody is watching is either a
            # misattribution or a hallucination. Either way, drop it.
            if signal.brand_name.strip().lower() not in known:
                degraded.append(
                    f"Signal attributed to '{signal.brand_name}', which is not "
                    "on the watchlist. Dropped."
                )
                continue

            label = (signal.source_id or "").strip().upper()

            if not SOURCE_LABEL_RE.match(label) or label not in registry:
                degraded.append(
                    f"Signal for '{signal.brand_name}' had no resolvable "
                    "source. Dropped."
                )
                continue

            source = registry[label]
            eid = event_id(signal.brand_name, source.url)

            if eid in seen_ids:
                continue
            seen_ids.add(eid)

            events.append(
                WatchEvent(
                    event_id=eid,
                    brand_name=signal.brand_name,
                    signal=signal.signal,
                    summary=signal.summary,
                    act_now=signal.act_now,
                    why_it_matters=signal.why_it_matters,
                    evidence=[
                        EvidenceRef(
                            claim=signal.summary,
                            url=source.url,
                            title=source.title,
                            excerpt=source.excerpts[0] if source.excerpts else None,
                        )
                    ],
                )
            )

        return events

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
                "\n".join(f"  - {e}" for e in source.excerpts[:3]) or "  (none)"
            )

            blocks.append(
                f"[{label}] {source.title}\n"
                f"  published: {source.publish_date or 'unknown'}\n"
                f"{excerpts}"
            )

        return registry, "\n\n".join(blocks) or "No sources."

    # ------------------------------------------------------------------

    def history(self, brand: Optional[str] = None) -> List[WatchEvent]:
        """Everything recorded so far, optionally for one brand."""

        events = self.store.load().events

        if brand:
            key = brand.strip().lower()
            events = [e for e in events if e.brand_name.strip().lower() == key]

        return events


def render_watch(report: WatchReport) -> str:
    """What the creator reads over coffee."""

    lines = [
        f"WATCH — {len(report.brands_checked)} brand(s), "
        f"{report.urls_new} new source(s) of {report.urls_seen}",
        "",
    ]

    if not report.new_events:
        lines.append("Nothing new. This is the expected result most days.")
        lines.append("")
    else:
        for event in sorted(
            report.new_events, key=lambda e: (not e.act_now, e.brand_name)
        ):
            marker = "→ ACT NOW" if event.act_now else "  context"
            lines.append(f"{marker}  {event.brand_name} — {event.signal.value}")
            lines.append(f"     {event.summary}")

            if event.why_it_matters:
                lines.append(f"     {event.why_it_matters}")

            for ref in event.evidence:
                lines.append(f"     → {ref.url}")

            lines.append("")

    if report.degraded_reasons:
        lines.append("GAPS")
        for reason in report.degraded_reasons:
            lines.append(f"   • {reason}")
        lines.append("")

    lines.append(
        f"SUMMARY: {len(report.urgent)} urgent, "
        f"{len(report.new_events) - len(report.urgent)} context."
    )

    return "\n".join(lines)


# ====================================================================
# WAKE — the bridge from a signal to a re-scout
# ====================================================================





def _slug(text: str) -> str:
    return (text or "").strip().lower()


def seeds_from_queue(
    events: Sequence[WatchEvent],
    previous: Optional[OpportunityQueue],
) -> tuple[List[BrandCandidate], List[str]]:
    """
    Turn watch events into candidates, carrying category from the previous
    queue so hard rules can still be applied.

    Returns (seeds, unknown_brand_names). A brand with no prior record is
    returned in the second list rather than seeded blind: without a category
    it would slip past every suppression rule.
    """

    by_name = {}
    if previous:
        by_name = {_slug(o.brand_name): o for o in previous.opportunities}

    seeds: List[BrandCandidate] = []
    unknown: List[str] = []
    seen: set = set()

    for event in events:
        key = _slug(event.brand_name)

        if key in seen:
            continue
        seen.add(key)

        prior: Optional[BrandOpportunity] = by_name.get(key)

        if prior is None:
            unknown.append(event.brand_name)
            continue

        seeds.append(
            BrandCandidate(
                brand_name=prior.brand_name,
                category=prior.category,
                why_relevant=(
                    f"{event.signal.value.replace('_', ' ')}: {event.summary}"
                ),
                spends_on_creators=True,
            )
        )

    return seeds, unknown


async def rescout_on_events(
    agent: CreatorScoutAgent,
    request: CreatorScoutRequest,
    report: WatchReport,
    previous: Optional[OpportunityQueue] = None,
    urgent_only: bool = True,
) -> Optional[OpportunityQueue]:
    """
    Re-rank the brands a signal fired for.

    Returns None when there is nothing to do, which is the common case. A watch
    that triggers a re-scout every day is a watch that is too loose.

    `urgent_only` restricts this to events where the campaign window is open
    now. Context events are worth recording but not worth a Gemini call.
    """

    events = report.urgent if urgent_only else report.new_events

    if not events:
        return None

    seeds, unknown = seeds_from_queue(events, previous)

    if not seeds and not unknown:
        return None

    # A brand with no prior record needs full discovery, not a blind seed.
    # Falling back to a normal run is the honest handling: it costs more, but
    # it establishes the category that the hard rules depend on.
    if unknown and not seeds:
        logger.info(
            "Signals for %s have no prior record; running full discovery.",
            ", ".join(unknown),
        )
        queue = await agent.run(request, signals=events)
        queue.degraded_reasons.append(
            "Triggered by watch signals for "
            + ", ".join(unknown)
            + ", which had no prior record. Ran full discovery to establish "
            "their categories."
        )
        return queue

    queue = await agent.run(request, seed_brands=seeds, signals=events)

    if unknown:
        queue.degraded_reasons.append(
            "Signals also fired for "
            + ", ".join(unknown)
            + ", which are not in the previous queue. They were not re-scouted "
            "because their category is unknown and the suppression rules could "
            "not be applied. Run a full scout to pick them up."
        )

    return queue


async def watch_and_react(
    watcher,
    agent: CreatorScoutAgent,
    request: CreatorScoutRequest,
    previous: Optional[OpportunityQueue] = None,
    watchlist: Optional[Sequence[str]] = None,
    urgent_only: bool = True,
) -> tuple[WatchReport, Optional[OpportunityQueue]]:
    """
    One scheduled cycle: poll, then react if anything fired.

    This is the whole loop. Point cron at it.
    """

    report = await watcher.poll(watchlist=watchlist)

    queue = await rescout_on_events(
        agent=agent,
        request=request,
        report=report,
        previous=previous,
        urgent_only=urgent_only,
    )

    return report, queue