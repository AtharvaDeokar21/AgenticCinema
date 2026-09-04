"""
Offline tests for CreatorScout.

No API keys, no network, no cost. Every external tool is faked. Covers the
agent, the deterministic hard rules, the polling watch, and the bridge that
wakes the agent on a signal.

    python -m pytest tests/agents/creator_scout -v

Each section has its own fakes, prefixed so they cannot shadow each other.
That prefixing is the cost of one test file instead of three.
"""

from datetime import date

import pytest
from pydantic import ValidationError

from app.agents.creator_scout.agent import (
    CreatorScoutAgent,
    apply_hard_rules,
    capacity_warning,
)
from app.agents.creator_scout.schemas import (
    BrandCandidate,
    CapacityWeek,
    CreatorScoutRequest,
    DiscoveryResult,
    EnrichmentResult,
    OutreachResult,
    RankingResult,
    WatchClassification,
)
from app.agents.creator_scout.watch import (
    MAX_SEEN_URLS,
    BrandWatcher,
    WatchState,
    WatchStore,
    event_id,
    render_watch,
    rescout_on_events,
    seeds_from_queue,
    watch_and_react,
)
from app.shared.models.creator_scout import (
    BrandOpportunity,
    DealMemo,
    ExclusivityClause,
    OpportunityQueue,
    SuppressionRule,
    VerificationTier,
    WatchEvent,
    WatchReport,
)
from app.shared.models.research import ResearchResult, ResearchSource

TODAY = date(2026, 9, 4)


# ====================================================================
# AGENT AND HARD RULES
# ====================================================================






# ----------------------------------------------------------------------
# fakes
# ----------------------------------------------------------------------


class FakeGemini:
    def __init__(self, discovery=None, enrichment=None, ranking=None, outreach=None):
        self._discovery = discovery or DiscoveryResult()
        self._enrichment = enrichment or EnrichmentResult()
        self._ranking = ranking or RankingResult()
        self._outreach = outreach
        self.calls = []

    def generate_structured(self, prompt, response_schema, model=None, **kwargs):
        self.calls.append(response_schema.__name__)

        if response_schema is DiscoveryResult:
            return self._discovery
        if response_schema is EnrichmentResult:
            return self._enrichment
        if response_schema is RankingResult:
            return self._ranking
        if response_schema is OutreachResult:
            return self._outreach

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
        return ResearchResult(query="q", sources=self._sources)


SOURCE = ResearchSource(
    title="Brand creator program",
    url="https://example.com/program",
    excerpts=["Applications open to creators with 50k+ followers."],
    publish_date="2026-08-01",
)


def candidate(name="PayGrid", category="personal finance"):
    return {
        "brand_name": name,
        "category": category,
        "why_relevant": "Runs explainer-format creator campaigns.",
        "spends_on_creators": True,
        "source_ids": ["S1"],
    }


def ranked(name="PayGrid", rank=1, cited=True):
    return {
        "brand_name": name,
        "rank": rank,
        "rationale": "61% of your audience is in their target band.",
        "cautions": ["Standard agreement asks for 6 months exclusivity."],
        "audience_fit": 0.8,
        "brand_fit": 0.7,
        "commercial_fit": 0.6,
        "cited_claims": (
            [{"claim": "Program open to creators.", "source_id": "S1"}]
            if cited
            else []
        ),
    }


def request(**kw):
    base = dict(
        creator_id="c1",
        creator_name="Asmiya",
        niche="personal finance",
        categories_of_interest=["personal finance"],
        audience_summary="61% aged 22-30, urban India",
        as_of=TODAY,
    )
    base.update(kw)
    return CreatorScoutRequest(**base)


def build(gemini, search=None, **kw):
    return CreatorScoutAgent(
        gemini=gemini, search=search or FakeSearch([SOURCE]), **kw
    )


def full_gemini(**kw):
    return FakeGemini(
        discovery=DiscoveryResult.model_validate(
            {"candidates": kw.get("candidates", [candidate()])}
        ),
        enrichment=EnrichmentResult.model_validate(
            {
                "records": [
                    {
                        "brand_name": "PayGrid",
                        "has_creator_program": True,
                        "contact_route": "creators@paygrid.example",
                        "cited_claims": [
                            {"claim": "Program exists.", "source_id": "S1"}
                        ],
                    }
                ]
            }
        ),
        ranking=RankingResult.model_validate({"items": kw.get("items", [ranked()])}),
    )


# ----------------------------------------------------------------------
# hard rules — pure functions, no agent
# ----------------------------------------------------------------------


def test_active_exclusivity_suppresses_the_category():
    clause = ExclusivityClause(
        category="personal finance",
        brand_name="RivalPay",
        expires_on=date(2026, 12, 1),
    )

    allowed, suppressed = apply_hard_rules(
        [BrandCandidate.model_validate(candidate())],
        excluded_categories=[],
        exclusivity_clauses=[clause],
        as_of=TODAY,
    )

    assert allowed == []
    assert suppressed[0].rule is SuppressionRule.ACTIVE_EXCLUSIVITY
    assert "2026-12-01" in suppressed[0].reason
    assert "RivalPay" in suppressed[0].reason


def test_expired_exclusivity_does_not_suppress():
    clause = ExclusivityClause(
        category="personal finance", expires_on=date(2026, 1, 1)
    )

    allowed, suppressed = apply_hard_rules(
        [BrandCandidate.model_validate(candidate())],
        excluded_categories=[],
        exclusivity_clauses=[clause],
        as_of=TODAY,
    )

    assert len(allowed) == 1
    assert suppressed == []


def test_exclusion_list_suppresses_with_reason():
    allowed, suppressed = apply_hard_rules(
        [BrandCandidate.model_validate(candidate(category="gambling"))],
        excluded_categories=["gambling"],
        exclusivity_clauses=[],
        as_of=TODAY,
    )

    assert allowed == []
    assert suppressed[0].rule is SuppressionRule.CREATOR_EXCLUSION_LIST


def test_category_matching_is_broad_in_both_directions():
    """A false suppression is visible; a false pass is a contract breach."""

    clause = ExclusivityClause(category="finance", expires_on=date(2026, 12, 1))

    allowed, suppressed = apply_hard_rules(
        [BrandCandidate.model_validate(candidate(category="personal finance app"))],
        excluded_categories=[],
        exclusivity_clauses=[clause],
        as_of=TODAY,
    )

    assert allowed == []


def test_capacity_flags_but_never_suppresses():
    weeks = [
        CapacityWeek(week_starting=date(2026, 9, 7), committed_deliverables=1, capacity=1)
    ]

    assert capacity_warning(weeks) is not None
    assert capacity_warning([]) is None
    assert (
        capacity_warning(
            [CapacityWeek(week_starting=date(2026, 9, 7), capacity=2)]
        )
        is None
    )


# ----------------------------------------------------------------------
# agent
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_produces_a_ranked_cited_queue():
    queue = await build(full_gemini()).run(request())

    assert len(queue.opportunities) == 1
    opp = queue.opportunities[0]

    assert opp.rank == 1
    assert opp.evidence[0].url == SOURCE.url
    assert opp.contact_route == "creators@paygrid.example"
    assert opp.overall_score == pytest.approx(0.7)


@pytest.mark.asyncio
async def test_suppressed_candidate_is_never_enriched():
    """Hard rules run before enrichment, so suppression saves the spend."""

    clause = ExclusivityClause(
        category="personal finance", expires_on=date(2026, 12, 1)
    )
    gemini = full_gemini()
    search = FakeSearch([SOURCE])

    queue = await build(gemini, search=search).run(
        request(exclusivity_clauses=[clause])
    )

    assert queue.opportunities == []
    assert len(queue.suppressed) == 1
    assert "EnrichmentResult" not in gemini.calls
    assert "RankingResult" not in gemini.calls


@pytest.mark.asyncio
async def test_uncited_entry_loses_its_enrichment_fields():
    gemini = full_gemini(items=[ranked(cited=False)])
    gemini._enrichment = EnrichmentResult.model_validate(
        {
            "records": [
                {
                    "brand_name": "PayGrid",
                    "contact_route": "made-up@paygrid.example",
                    "cited_claims": [],
                }
            ]
        }
    )

    queue = await build(gemini).run(request())
    opp = queue.opportunities[0]

    assert opp.contact_route is None
    assert opp.tier is VerificationTier.UNVERIFIED
    assert any("no resolvable source" in r for r in queue.degraded_reasons)


@pytest.mark.asyncio
async def test_hallucinated_source_label_is_dropped():
    gemini = full_gemini(
        items=[
            {
                **ranked(),
                "cited_claims": [
                    {"claim": "x", "source_id": "S99"},
                    {"claim": "y", "source_id": "https://made-up.example"},
                ],
            }
        ]
    )
    gemini._enrichment = EnrichmentResult()

    queue = await build(gemini).run(request())

    assert queue.opportunities[0].evidence == []


@pytest.mark.asyncio
async def test_candidate_without_creator_spend_is_dropped():
    gemini = full_gemini(
        candidates=[{**candidate(), "spends_on_creators": False}]
    )

    queue = await build(gemini).run(request())

    assert queue.opportunities == []
    assert any("no evidence of actual creator spend" in r for r in queue.degraded_reasons)


@pytest.mark.asyncio
async def test_discovered_but_unranked_candidate_survives_unranked():
    gemini = full_gemini(items=[])

    queue = await build(gemini).run(request())

    assert len(queue.opportunities) == 1
    assert queue.opportunities[0].rank is None
    assert any("not ranked" in r for r in queue.degraded_reasons)


@pytest.mark.asyncio
async def test_ranking_a_brand_that_was_never_a_candidate_is_dropped():
    gemini = full_gemini(items=[ranked(name="InventedCo")])

    queue = await build(gemini).run(request())

    names = {o.brand_name for o in queue.opportunities}
    assert "InventedCo" not in names
    assert any("not in the candidate list" in r for r in queue.degraded_reasons)


@pytest.mark.asyncio
async def test_search_failure_degrades_rather_than_crashing():
    queue = await build(full_gemini(), search=FakeSearch(fail=True)).run(request())

    assert queue.opportunities == []
    assert any("Search failed" in r for r in queue.degraded_reasons)


@pytest.mark.asyncio
async def test_missing_findall_is_declared_not_hidden():
    queue = await build(full_gemini()).run(request())

    assert any("FindAll not enabled" in r for r in queue.degraded_reasons)
    assert queue.opportunities[0].tier is not VerificationTier.VERIFIED


@pytest.mark.asyncio
async def test_capacity_warning_reaches_every_opportunity():
    weeks = [
        CapacityWeek(week_starting=date(2026, 9, 7), committed_deliverables=1, capacity=1)
    ]

    queue = await build(full_gemini()).run(request(capacity=weeks))

    assert queue.opportunities[0].capacity_warning
    assert queue.actionable == []


@pytest.mark.asyncio
async def test_outreach_refused_without_evidence():
    from app.shared.models.creator_scout import BrandOpportunity

    agent = build(full_gemini())
    bare = BrandOpportunity(brand_name="PayGrid")

    assert await agent.draft_outreach(request(), bare) is None


# ----------------------------------------------------------------------
# safety invariants
# ----------------------------------------------------------------------


def test_deal_memo_always_requires_a_human_signature():
    memo = DealMemo(brand_name="PayGrid")
    assert memo.requires_human_signature is True

    with pytest.raises(ValidationError):
        DealMemo(brand_name="PayGrid", requires_human_signature=False)


def test_perpetuity_is_detected_in_usage_rights():
    memo = DealMemo(
        brand_name="PayGrid",
        usage_rights_scope="Worldwide, in perpetuity, all media",
    )
    assert memo.perpetuity_requested is True


def test_monitor_plan_carries_no_dates_in_the_query():
    agent = build(full_gemini())
    plan = agent.describe_monitor_plan(["PayGrid"], "https://example.com/hook")

    assert plan["frequency"] == "1d"
    assert not any(ch.isdigit() for ch in plan["settings"]["query"])


# ====================================================================
# BACKGROUND WATCH
# ====================================================================




# ----------------------------------------------------------------------
# fakes
# ----------------------------------------------------------------------


class WatchGemini :
    def __init__ (self ,watch_classification =None ,fail =False ):
        self ._classification =watch_classification or WatchClassification ()
        self .fail =fail 
        self .calls =0 

    def generate_structured (self ,prompt ,response_schema ,model =None ,**kwargs ):
        self .calls +=1 
        if self .fail :
            raise RuntimeError ("gemini down")
        return self ._classification 


class WatchSearch :
    def __init__ (self ,sources =None ,fail =False ):
        self ._sources =sources or []
        self .fail =fail 
        self .calls =0 

    async def search (self ,search_queries ,objective =None ,**kwargs ):
        self .calls +=1 
        if self .fail :
            raise RuntimeError ("parallel down")
        return ResearchResult (query ="q",sources =self ._sources )


def watch_source (url ="https://example.com/launch",title ="PayGrid launches UPI credit"):
    return ResearchSource (
    title =title ,
    url =url ,
    excerpts =["PayGrid announced a new credit product this week."],
    publish_date ="2026-09-01",
    )


def watch_classification (url_label ="S1",brand ="PayGrid",act_now =True ):
    return WatchClassification .model_validate (
    {
    "signals":[
    {
    "brand_name":brand ,
    "signal":"product_launch",
    "summary":"Launched a UPI credit product.",
    "act_now":act_now ,
    "why_it_matters":"Campaign budgets move at launch.",
    "source_id":url_label ,
    }
    ]
    }
    )


def build_watcher (tmp_path ,gemini =None ,search =None ):
    return BrandWatcher (
    gemini =gemini or WatchGemini (watch_classification ()),
    search =search or WatchSearch ([watch_source ()]),
    store =WatchStore (tmp_path /"watch.json"),
    )


    # ----------------------------------------------------------------------
    # store
    # ----------------------------------------------------------------------


def test_missing_store_is_an_empty_state_not_an_error (tmp_path ):
    state =WatchStore (tmp_path /"nope.json").load ()
    assert state .watchlist ==[]
    assert state .seen_urls ==[]


def test_corrupt_store_starts_fresh_rather_than_crashing (tmp_path ):
    path =tmp_path /"watch.json"
    path .write_text ("{ this is not json",encoding ="utf-8")

    state =WatchStore (path ).load ()

    assert state .seen_urls ==[]


def test_store_round_trips (tmp_path ):
    store =WatchStore (tmp_path /"watch.json")

    state =WatchState (watchlist =["PayGrid"])
    state .mark_seen (["https://a.example","https://b.example"])
    store .save (state )

    loaded =store .load ()

    assert loaded .watchlist ==["PayGrid"]
    assert len (loaded .seen_urls )==2 
    assert loaded .last_run is not None 


def test_mark_seen_counts_only_new_urls ():
    state =WatchState ()

    assert state .mark_seen (["https://a.example"])==1 
    assert state .mark_seen (["https://a.example"])==0 
    assert state .mark_seen (["https://a.example","https://b.example"])==1 


def test_seen_urls_are_capped ():
    state =WatchState ()
    state .mark_seen (f"https://example.com/{i }"for i in range (MAX_SEEN_URLS +50 ))

    assert len (state .seen_urls )==MAX_SEEN_URLS 
    # Oldest fall off first.
    assert "https://example.com/0"not in state .seen_urls 
    assert f"https://example.com/{MAX_SEEN_URLS +49 }"in state .seen_urls 


def test_event_id_is_stable_across_runs ():
    a =event_id ("PayGrid","https://example.com/x")
    b =event_id ("  paygrid ","https://example.com/x")
    assert a ==b 


    # ----------------------------------------------------------------------
    # polling
    # ----------------------------------------------------------------------


@pytest .mark .asyncio 
async def test_empty_watchlist_spends_nothing (tmp_path ):
    search =WatchSearch ([watch_source ()])
    watcher =build_watcher (tmp_path ,search =search )

    report =await watcher .poll ()

    assert search .calls ==0 
    assert report .new_events ==[]
    assert any ("Watchlist is empty"in r for r in report .degraded_reasons )


@pytest .mark .asyncio 
async def test_first_run_reports_the_event (tmp_path ):
    watcher =build_watcher (tmp_path )

    report =await watcher .poll (watchlist =["PayGrid"])

    assert len (report .new_events )==1 
    assert report .new_events [0 ].brand_name =="PayGrid"
    assert report .new_events [0 ].evidence [0 ].url ==watch_source ().url 
    assert report .urgent 


@pytest .mark .asyncio 
async def test_second_run_on_the_same_page_reports_nothing (tmp_path ):
    """Idempotency. This is the whole point of the store."""

    gemini =WatchGemini (watch_classification ())
    watcher =build_watcher (tmp_path ,gemini =gemini )

    first =await watcher .poll (watchlist =["PayGrid"])
    second =await watcher .poll (watchlist =["PayGrid"])

    assert len (first .new_events )==1 
    assert second .new_events ==[]
    assert second .urls_new ==0 
    # No second Gemini call: nothing new means nothing to classify.
    assert gemini .calls ==1 


@pytest .mark .asyncio 
async def test_a_genuinely_new_url_does_report (tmp_path ):
    gemini =WatchGemini (watch_classification ())
    search =WatchSearch ([watch_source ()])
    watcher =build_watcher (tmp_path ,gemini =gemini ,search =search )

    await watcher .poll (watchlist =["PayGrid"])

    search ._sources =[watch_source (url ="https://example.com/funding")]
    report =await watcher .poll (watchlist =["PayGrid"])

    assert len (report .new_events )==1 
    assert report .new_events [0 ].evidence [0 ].url .endswith ("/funding")


@pytest .mark .asyncio 
async def test_watchlist_is_remembered (tmp_path ):
    watcher =build_watcher (tmp_path )

    await watcher .poll (watchlist =["PayGrid"])
    report =await watcher .poll ()

    assert report .brands_checked ==["PayGrid"]


@pytest .mark .asyncio 
async def test_signal_for_an_unwatched_brand_is_dropped (tmp_path ):
    watcher =build_watcher (tmp_path ,gemini =WatchGemini (watch_classification (brand ="InventedCo")))

    report =await watcher .poll (watchlist =["PayGrid"])

    assert report .new_events ==[]
    assert any ("not on the watchlist"in r for r in report .degraded_reasons )


@pytest .mark .asyncio 
async def test_uncited_signal_is_dropped (tmp_path ):
    watcher =build_watcher (tmp_path ,gemini =WatchGemini (watch_classification (url_label ="S99")))

    report =await watcher .poll (watchlist =["PayGrid"])

    assert report .new_events ==[]
    assert any ("no resolvable source"in r for r in report .degraded_reasons )


@pytest .mark .asyncio 
async def test_noisy_page_is_marked_seen_so_it_is_not_reclassified (tmp_path ):
    """A page that classified as noise must not cost a second Gemini call."""

    gemini =WatchGemini (WatchClassification ())
    watcher =build_watcher (tmp_path ,gemini =gemini )

    await watcher .poll (watchlist =["PayGrid"])
    await watcher .poll (watchlist =["PayGrid"])

    assert gemini .calls ==1 


@pytest .mark .asyncio 
async def test_search_failure_degrades_rather_than_crashing (tmp_path ):
    watcher =build_watcher (tmp_path ,search =WatchSearch (fail =True ))

    report =await watcher .poll (watchlist =["PayGrid"])

    assert report .new_events ==[]
    assert any ("Search failed"in r for r in report .degraded_reasons )


@pytest .mark .asyncio 
async def test_classification_failure_still_marks_urls_seen (tmp_path ):
    watcher =build_watcher (tmp_path ,gemini =WatchGemini (fail =True ))

    report =await watcher .poll (watchlist =["PayGrid"])

    assert any ("classification failed"in r for r in report .degraded_reasons )
    assert watcher .store .load ().seen_urls # not retried forever


@pytest .mark .asyncio 
async def test_history_filters_by_brand (tmp_path ):
    watcher =build_watcher (tmp_path )
    await watcher .poll (watchlist =["PayGrid"])

    assert len (watcher .history ("PayGrid"))==1 
    assert watcher .history ("LedgerUp")==[]


@pytest .mark .asyncio 
async def test_render_says_nothing_new_plainly (tmp_path ):
    watcher =build_watcher (tmp_path ,gemini =WatchGemini (WatchClassification ()))

    report =await watcher .poll (watchlist =["PayGrid"])

    assert "Nothing new"in render_watch (report )


# ====================================================================
# WAKE — SIGNAL TO RE-SCOUT
# ====================================================================






class WakeGemini :
    def __init__ (self ,ranking =None ):
        self ._ranking =ranking or RankingResult .model_validate (
        {
        "items":[
        {
        "brand_name":"PayGrid",
        "rank":1 ,
        "rationale":"Funding just closed.",
        "cautions":[],
        "cited_claims":[
        {"claim":"Raised Series B.","source_id":"S1"}
        ],
        }
        ]
        }
        )
        self .calls =[]
        self .prompts =[]

    def generate_structured (self ,prompt ,response_schema ,model =None ,**kwargs ):
        self .calls .append (response_schema .__name__ )
        self .prompts .append (prompt )

        if response_schema is DiscoveryResult :
            return DiscoveryResult .model_validate (
            {
            "candidates":[
            {
            "brand_name":"PayGrid",
            "category":"personal finance",
            "why_relevant":"Runs creator campaigns.",
            "spends_on_creators":True ,
            "source_ids":["S1"],
            }
            ]
            }
            )
        if response_schema is EnrichmentResult :
            return EnrichmentResult .model_validate (
            {
            "records":[
            {
            "brand_name":"PayGrid",
            "has_creator_program":True ,
            "cited_claims":[
            {"claim":"Program exists.","source_id":"S1"}
            ],
            }
            ]
            }
            )
        if response_schema is RankingResult :
            return self ._ranking 

        raise AssertionError (f"unexpected schema {response_schema }")


class WakeSearch :
    def __init__ (self ):
        self .calls =0 

    async def search (self ,search_queries ,objective =None ,**kwargs ):
        self .calls +=1 
        return ResearchResult (
        query ="q",
        sources =[
        ResearchSource (
        title ="PayGrid raises Series B",
        url ="https://example.com/funding",
        excerpts =["Closed a $40M round."],
        )
        ],
        )


class WakeWatcher :
    def __init__ (self ,report ):
        self ._report =report 
        self .calls =0 

    async def poll (self ,watchlist =None ,persist =True ):
        self .calls +=1 
        return self ._report 


def wake_event (brand ="PayGrid",act_now =True ):
    return WatchEvent (
    event_id ="evt_1",
    brand_name =brand ,
    signal ="funding_round",
    summary ="Raised a $40M Series B.",
    act_now =act_now ,
    why_it_matters ="Budget exists now.",
    )


def wake_previous_queue (category ="personal finance"):
    return OpportunityQueue (
    opportunities =[
    BrandOpportunity (brand_name ="PayGrid",category =category ,rank =3 )
    ]
    )


def wake_request (**kw ):
    base =dict (
    creator_id ="c1",
    creator_name ="Asmiya",
    niche ="personal finance",
    categories_of_interest =["personal finance"],
    as_of =TODAY ,
    )
    base .update (kw )
    return CreatorScoutRequest (**base )


def wake_agent (gemini =None ,search =None ):
    return CreatorScoutAgent (
    gemini =gemini or WakeGemini (),search =search or WakeSearch ()
    )


    # ----------------------------------------------------------------------
    # seeding
    # ----------------------------------------------------------------------


def test_seeds_carry_category_from_the_previous_queue ():
    seeds ,unknown =seeds_from_queue ([wake_event ()],wake_previous_queue ())

    assert unknown ==[]
    assert seeds [0 ].brand_name =="PayGrid"
    assert seeds [0 ].category =="personal finance"
    assert "funding round"in seeds [0 ].why_relevant 


def test_brand_with_no_prior_record_is_flagged_not_seeded_blind ():
    seeds ,unknown =seeds_from_queue ([wake_event (brand ="NewCo")],wake_previous_queue ())

    assert seeds ==[]
    assert unknown ==["NewCo"]


def test_duplicate_events_seed_once ():
    seeds ,_ =seeds_from_queue ([wake_event (),wake_event ()],wake_previous_queue ())
    assert len (seeds )==1 


    # ----------------------------------------------------------------------
    # reacting
    # ----------------------------------------------------------------------


@pytest .mark .asyncio 
async def test_no_events_means_no_rescout_and_no_spend ():
    gemini =WakeGemini ()
    search =WakeSearch ()

    result =await rescout_on_events (
    wake_agent (gemini ,search ),wake_request (),WatchReport (),wake_previous_queue ()
    )

    assert result is None 
    assert gemini .calls ==[]
    assert search .calls ==0 


@pytest .mark .asyncio 
async def test_context_only_events_do_not_trigger_a_rescout ():
    report =WatchReport (new_events =[wake_event (act_now =False )])

    result =await rescout_on_events (
    wake_agent (),wake_request (),report ,wake_previous_queue ()
    )

    assert result is None 


@pytest .mark .asyncio 
async def test_urgent_event_reranks_without_rediscovering ():
    gemini =WakeGemini ()
    report =WatchReport (new_events =[wake_event ()])

    queue =await rescout_on_events (
    wake_agent (gemini ),wake_request (),report ,wake_previous_queue ()
    )

    assert queue is not None 
    assert queue .opportunities [0 ].rank ==1 
    # Discovery skipped: the brand was already known.
    assert "DiscoveryResult"not in gemini .calls 
    assert "RankingResult"in gemini .calls 
    assert any ("discovery skipped"in r for r in queue .degraded_reasons )


@pytest .mark .asyncio 
async def test_the_signal_reaches_the_ranking_prompt ():
    """Without this the ranker never sees the timing evidence it asks for."""

    gemini =WakeGemini ()
    report =WatchReport (new_events =[wake_event ()])

    await rescout_on_events (wake_agent (gemini ),wake_request (),report ,wake_previous_queue ())

    ranking_prompt =next (
    p 
    for p ,c in zip (gemini .prompts ,gemini .calls )
    if c =="RankingResult"
    )

    assert "RECENT SIGNALS"in ranking_prompt 
    assert "Series B"in ranking_prompt 
    assert "WINDOW OPEN NOW"in ranking_prompt 


@pytest .mark .asyncio 
async def test_a_watch_event_does_not_override_exclusivity ():
    """The safety rule. Seeding skips discovery, never the hard rules."""

    clause =ExclusivityClause (
    category ="personal finance",expires_on =date (2026 ,12 ,1 )
    )
    report =WatchReport (new_events =[wake_event ()])

    queue =await rescout_on_events (
    wake_agent (),
    wake_request (exclusivity_clauses =[clause ]),
    report ,
    wake_previous_queue (),
    )

    assert queue .opportunities ==[]
    assert queue .suppressed [0 ].rule is SuppressionRule .ACTIVE_EXCLUSIVITY 


@pytest .mark .asyncio 
async def test_uncategorised_seed_is_declared_not_silently_passed ():
    report =WatchReport (new_events =[wake_event ()])

    queue =await rescout_on_events (
    wake_agent (),wake_request (),report ,wake_previous_queue (category =None )
    )

    assert any ("Category unknown"in r for r in queue .degraded_reasons )
    assert any ("could NOT be applied"in r for r in queue .degraded_reasons )


@pytest .mark .asyncio 
async def test_unknown_brand_falls_back_to_full_discovery ():
    gemini =WakeGemini ()
    report =WatchReport (new_events =[wake_event (brand ="NewCo")])

    queue =await rescout_on_events (
    wake_agent (gemini ),wake_request (),report ,wake_previous_queue ()
    )

    assert "DiscoveryResult"in gemini .calls 
    assert any ("had no prior record"in r for r in queue .degraded_reasons )


@pytest .mark .asyncio 
async def test_rescout_without_a_previous_queue_still_works ():
    gemini =WakeGemini ()
    report =WatchReport (new_events =[wake_event ()])

    queue =await rescout_on_events (wake_agent (gemini ),wake_request (),report ,None )

    assert "DiscoveryResult"in gemini .calls 
    assert queue is not None 


    # ----------------------------------------------------------------------
    # the full cycle
    # ----------------------------------------------------------------------


@pytest .mark .asyncio 
async def test_watch_and_react_returns_both_halves ():
    watcher =WakeWatcher (WatchReport (new_events =[wake_event ()]))

    report ,queue =await watch_and_react (
    watcher ,wake_agent (),wake_request (),wake_previous_queue ()
    )

    assert watcher .calls ==1 
    assert report .urgent 
    assert queue is not None 


@pytest .mark .asyncio 
async def test_quiet_day_returns_a_report_and_no_queue ():
    watcher =WakeWatcher (WatchReport ())

    report ,queue =await watch_and_react (
    watcher ,wake_agent (),wake_request (),wake_previous_queue ()
    )

    assert report .new_events ==[]
    assert queue is None