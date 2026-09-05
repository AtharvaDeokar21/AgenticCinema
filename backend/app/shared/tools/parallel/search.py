from typing import Any, List, Optional

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
        fetch_policy: Optional[dict[str, Any]] = None,
    ) -> ResearchResult:
        kwargs: dict[str, Any] = {
            "search_queries": search_queries,
            "objective": objective,
            "mode": mode,
        }

        if fetch_policy is not None:
            kwargs["fetch_policy"] = fetch_policy

        response = await self.client.client.search(**kwargs)

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
