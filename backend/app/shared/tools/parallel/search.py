from typing import List, Optional

from app.shared.models.research import (
    ResearchResult,
    ResearchSource,
)

from .client import ParallelClient


class ParallelSearch:
    """
    Runtime web search through Parallel Web Systems.
    """

    def __init__(self):
        self.client = ParallelClient()

    async def search(
        self,
        search_queries: List[str],
        objective: Optional[str] = None,
        mode: str = "basic",
    ) -> ResearchResult:
        response = await self.client.client.search(
            search_queries=search_queries,
            objective=objective,
            mode=mode,
        )

        sources = []

        for result in response.results:
            sources.append(
                ResearchSource(
                    title=result.title,
                    url=result.url,
                    excerpts=result.excerpts or [],
                    publish_date=result.publish_date,
                )
            )

        return ResearchResult(
            query="; ".join(search_queries),
            sources=sources,
        )

    async def close(self):
        await self.client.close()