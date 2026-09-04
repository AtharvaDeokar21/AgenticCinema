from typing import Any, Dict

from .client import ParallelClient


class ParallelMonitor:
    """Monitor changes on the open web."""

    def __init__(self):
        self.client = ParallelClient()

    async def monitor(
        self,
        target: str,
        **kwargs: Any,
    ) -> Dict:
        raise NotImplementedError(
            "Implement using the verified Parallel Monitor API contract."
        )