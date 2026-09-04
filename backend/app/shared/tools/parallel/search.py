from typing import Any, Dict

from .client import ParallelClient


class ParallelSearch:
    """Runtime web search through Parallel Web Systems."""

    def __init__(self):
        self.client = ParallelClient()

    async def search(
        self,
        query: str,
        **kwargs: Any,
    ) -> Dict:
        """
        Search the web using Parallel.

        The exact API payload will be finalized against the
        current Parallel Search API contract.
        """

        raise NotImplementedError(
            "Implement using the verified Parallel Search API contract."
        )