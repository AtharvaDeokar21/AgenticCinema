"""
CreatorScout CLI — scouting, the background watch, and history in one script.

    cd backend

    # rank brands for a creator (real Gemini + Parallel, costs money)
    python -m scripts.creator_scout scout

    # poll the watchlist. First run seeds it; later runs remember it.
    python -m scripts.creator_scout watch --brands "PayGrid,LedgerUp"
    python -m scripts.creator_scout watch

    # poll, and re-rank anything an urgent signal fired for
    python -m scripts.creator_scout watch --rescout

    # free: no API calls
    python -m scripts.creator_scout history
    python -m scripts.creator_scout watch --dry-run

Exit codes, so a scheduler can alert:
    0 fine   1 ran but degraded   2 could not run

SCHEDULING

  Windows Task Scheduler, daily:
    Program:   C:\\...\\AgenticCinema\\myenv\\Scripts\\python.exe
    Arguments: -m scripts.creator_scout watch --rescout
    Start in:  C:\\...\\AgenticCinema\\backend

  cron, daily at 07:00:
    0 7 * * * cd /path/to/AgenticCinema/backend && \\
      /path/to/myenv/bin/python -m scripts.creator_scout watch >> watch.log 2>&1
"""

import argparse
import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

from app.agents.creator_scout import (
    BrandWatcher,
    CapacityWeek,
    CreatorScoutAgent,
    CreatorScoutRequest,
    PastDeal,
    WatchStore,
    render_queue,
    render_watch,
    rescout_on_events,
)
from app.shared.models.creator_scout import ExclusivityClause

TODAY = date.today()


def demo_request() -> CreatorScoutRequest:
    """
    Replace this with the real creator profile. Ranking quality depends
    directly on how concrete the audience numbers are — "61% aged 22-30"
    produces an arguable rationale, "young audience" produces a decorative one.
    """

    return CreatorScoutRequest(
        creator_id="creator_001",
        creator_name="Asmiya",
        platforms=["YouTube", "Instagram"],
        niche="personal finance explainers",
        audience_summary="61% aged 22-30, 74% urban India, 58% male",
        median_views=180_000,
        engagement_rate=0.047,
        languages=["English", "Hindi"],
        formats=["explainer", "long-form"],
        categories_of_interest=["personal finance", "investing"],
        excluded_categories=["gambling", "crypto trading"],
        rate_floor="Rs 1,50,000 per long-form integration",
        preferred_deal_structure="flat fee, no perpetual usage",
        exclusivity_clauses=[
            ExclusivityClause(
                category="insurance",
                brand_name="SafeCover",
                territory="India",
                expires_on=TODAY + timedelta(days=90),
            )
        ],
        capacity=[
            CapacityWeek(week_starting=TODAY, committed_deliverables=1, capacity=1),
            CapacityWeek(
                week_starting=TODAY + timedelta(days=7),
                committed_deliverables=0,
                capacity=2,
            ),
        ],
        past_deals=[
            PastDeal(
                brand_name="LedgerUp",
                category="personal finance",
                fee="Rs 1,80,000",
                paid_on_time=True,
            )
        ],
        target_geography="India",
        max_candidates=6,
    )


async def cmd_scout(args) -> int:
    agent = CreatorScoutAgent()
    request = demo_request()

    try:
        queue = await agent.run(request)
    finally:
        try:
            await agent.search.close()
        except Exception:  # noqa: BLE001
            pass

    if args.json:
        print(queue.model_dump_json(indent=2))
    else:
        print(render_queue(queue, creator_name=request.creator_name))

    return 1 if queue.degraded_reasons else 0


async def cmd_watch(args) -> int:
    store = WatchStore(Path(args.store) if args.store else None)
    brands = (
        [b.strip() for b in args.brands.split(",") if b.strip()]
        if args.brands
        else None
    )

    if args.dry_run:
        state = store.load()
        watchlist = brands or state.watchlist
        print(f"Store:     {store.path}")
        print(f"Watchlist: {', '.join(watchlist) or '(empty)'}")
        print(f"Last run:  {state.last_run or 'never'}")
        print(f"URLs seen: {len(state.seen_urls)}")
        print(f"Events:    {len(state.events)}")
        return 0 if watchlist else 2

    # Building the watcher constructs the real clients, so a credential
    # problem surfaces here with a clear message rather than deep in the poll.
    try:
        watcher = BrandWatcher(store=store)
    except Exception as exc:  # noqa: BLE001
        print(f"Could not start the watch: {exc}", file=sys.stderr)
        return 2

    try:
        report = await watcher.poll(watchlist=brands)
    finally:
        try:
            await watcher.search.close()
        except Exception:  # noqa: BLE001
            pass

    if args.json:
        print(report.model_dump_json(indent=2))
    else:
        print(render_watch(report))

    if not report.brands_checked:
        return 2

    # Polling alone is a news feed. This is the half that makes it an agent.
    if args.rescout and report.urgent:
        agent = CreatorScoutAgent()
        request = demo_request()

        try:
            queue = await rescout_on_events(
                agent=agent,
                request=request,
                report=report,
                previous=None,  # pass the last OpportunityQueue when you have one
            )
        finally:
            try:
                await agent.search.close()
            except Exception:  # noqa: BLE001
                pass

        if queue:
            print()
            print("=" * 72)
            print(render_queue(queue, creator_name=request.creator_name))

    return 1 if report.degraded_reasons else 0


async def cmd_history(args) -> int:
    events = WatchStore(Path(args.store) if args.store else None).load().events

    if not events:
        print("No events recorded yet.")
        return 0

    for event in events:
        flag = "ACT NOW" if event.act_now else "context"
        print(f"[{flag}] {event.brand_name} - {event.signal.value}")
        print(f"  {event.summary}")
        for ref in event.evidence:
            print(f"  -> {ref.url}")

    return 0


def parse_args():
    parser = argparse.ArgumentParser(description="CreatorScout")
    parser.add_argument("--store", default=None, help="Watch state file path.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("scout", help="Rank brands for the creator.")

    watch = sub.add_parser("watch", help="Poll the watchlist for timing signals.")
    watch.add_argument("--brands", help="Comma-separated watchlist. Remembered.")
    watch.add_argument(
        "--rescout",
        action="store_true",
        help="Re-rank brands an urgent signal fired for. Costs API calls.",
    )
    watch.add_argument(
        "--dry-run", action="store_true", help="Show state, call nothing."
    )

    sub.add_parser("history", help="Print recorded events. Free.")

    return parser.parse_args()


async def main() -> int:
    args = parse_args()

    if args.command == "scout":
        return await cmd_scout(args)
    if args.command == "watch":
        return await cmd_watch(args)
    return await cmd_history(args)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))