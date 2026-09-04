from typing import Any, Dict

from .client import ParallelClient


class ParallelTask:
    """Execute deeper web research/enrichment tasks."""

    def __init__(self):
        self.client = ParallelClient()

    async def run(
        self,
        task: str,
        **kwargs: Any,
    ) -> Dict:
        raise NotImplementedError(
            "Implement using the verified Parallel Task API contract."
        )