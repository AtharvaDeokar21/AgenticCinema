"""Parallel research for culturally meaningful source spans."""

import asyncio
import logging
from typing import Dict, List, Optional

from app.agents.cultural_dub.schemas import (
    CulturalSpan,
    CulturalSpanResearch,
)
from app.shared.models.research import ResearchResult
from app.shared.tools.parallel.search import ParallelSearch

logger = logging.getLogger(__name__)

MAX_SOURCES_PER_SPAN = 5
MAX_CONCURRENT_RESEARCH = 8
RESEARCH_MAX_AGE_SECONDS = 60 * 60 * 24 * 180


class CulturalDubResearcher:
    """Research target-specific cultural spans through Parallel Search."""

    def __init__(
        self,
        search: Optional[ParallelSearch] = None,
        max_concurrent: int = MAX_CONCURRENT_RESEARCH,
    ):
        self.search = search or ParallelSearch()
        self.max_concurrent = max_concurrent

    async def research(
        self,
        spans: List[CulturalSpan],
        target_language: str,
        target_geography: str,
    ) -> List[CulturalSpanResearch]:
        """Research each unique span that requires current evidence."""
        targets = self._deduplicate_targets(
            spans=spans,
            target_language=target_language,
            target_geography=target_geography,
        )

        if not targets:
            return []

        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def one(span: CulturalSpan) -> CulturalSpanResearch:
            async with semaphore:
                try:
                    result = await self._search_span(
                        span=span,
                        target_language=target_language,
                        target_geography=target_geography,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Cultural research failed for '%s': %s",
                        span.source_text,
                        exc,
                    )
                    return CulturalSpanResearch(
                        segment_id=span.segment_id,
                        source_text=span.source_text,
                    )

            return CulturalSpanResearch(
                segment_id=span.segment_id,
                source_text=span.source_text,
                sources=list(result.sources or [])[:MAX_SOURCES_PER_SPAN],
            )

        return await asyncio.gather(*(one(span) for span in targets))

    async def _search_span(
        self,
        span: CulturalSpan,
        target_language: str,
        target_geography: str,
    ) -> ResearchResult:
        queries = [
            (
                f'"{span.source_text}" meaning usage '
                f'{target_language} {target_geography}'
            ),
            (
                f'"{span.source_text}" {target_language} '
                f'localization equivalent'
            ),
        ]

        objective = (
            "Research the cultural meaning and current usage of the supplied "
            "source expression so it can be localized naturally into the "
            f"{target_language} ({target_geography}) market. "
            "Focus on meaning, register, humour, slang, meme status, and "
            "natural target-locale equivalents. Do not invent a translation. "
            "Prefer recent and authoritative sources when current usage matters."
        )

        return await self.search.search(
            search_queries=queries,
            objective=objective,
            mode="basic",
            fetch_policy={
                "max_age_seconds": RESEARCH_MAX_AGE_SECONDS,
            },
        )

    @staticmethod
    def _deduplicate_targets(
        spans: List[CulturalSpan],
        target_language: str,
        target_geography: str,
    ) -> List[CulturalSpan]:
        """Deduplicate identical source spans while preserving order."""
        seen = set()
        unique = []

        for span in spans:
            if not span.requires_research:
                continue

            key = (
                span.source_text.strip().casefold(),
                target_language.strip().casefold(),
                target_geography.strip().casefold(),
            )

            if key in seen:
                continue

            seen.add(key)
            unique.append(span)

        return unique
