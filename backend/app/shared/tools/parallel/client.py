import httpx

from app.config import get_settings


class ParallelClient:
    """Shared client for Parallel Web Systems APIs."""

    def __init__(self):
        settings = get_settings()

        self.api_key = settings.parallel_api_key
        self.base_url = "https://api.parallel.ai"

    @property
    def headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }

    async def request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ):
        url = f"{self.base_url}{endpoint}"

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                url,
                headers=self.headers,
                **kwargs,
            )

            response.raise_for_status()

            return response.json()