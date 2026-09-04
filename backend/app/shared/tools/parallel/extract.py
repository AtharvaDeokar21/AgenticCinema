from typing import Any, Dict

from .client import ParallelClient


class ParallelExtract:
    """Extract content from web pages using Parallel."""

    def __init__(self):
        self.client = ParallelClient()

    async def extract(
        self,
        url: str,
        **kwargs: Any,
    ) -> Dict:
        raise NotImplementedError(
            "Implement using the verified Parallel Extract API contract."
        )