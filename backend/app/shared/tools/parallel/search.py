from typing import List, Optional

from .client import ParallelClient


class ParallelSearch:
    """
    Runtime web search through Parallel Web Systems.

    This is the primary Parallel integration required
    by the Agentic Cinema hackathon.
    """

    def __init__(self):
        self.client = ParallelClient()

    async def search(
        self,
        search_queries: List[str],
        objective: Optional[str] = None,
        mode: str = "basic",
    ):
        """
        Search the live web through Parallel.

        Parameters
        ----------
        search_queries:
            Concise search probes.

        objective:
            Overall research objective.

        mode:
            Parallel search quality/latency mode.
        """

        response = await self.client.client.search(
            search_queries=search_queries,
            objective=objective,
            mode=mode,
        )

        return response