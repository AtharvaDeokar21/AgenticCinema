from parallel import AsyncParallel

from app.config import get_settings


class ParallelClient:
    """Shared Parallel Web Systems client."""

    def __init__(self):
        settings = get_settings()

        if not settings.parallel_api_key:
            raise ValueError(
                "PARALLEL_API_KEY is not configured."
            )

        self.client = AsyncParallel(
            api_key=settings.parallel_api_key,
        )

    async def close(self):
        await self.client.close()