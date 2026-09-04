
"""
Parallel Extract wrapper.

⚠ VERIFY THE CALL SIGNATURE against the version of the `parallel` SDK pinned in
requirements.txt before you rely on this. The SDK surface has moved between
releases (top-level vs `beta` namespace), so `_invoke` tries the known call
paths in order and raises a single clear error if none exist, rather than
failing deep inside the agent with an AttributeError.

Design note: Extract never raises into the caller by default. Compliance has a
defined degraded mode — "I could not read the licence page" is a correct
output; a confident fabrication is not.
"""

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .client import ParallelClient

logger = logging.getLogger(__name__)

# Extract accepts a batch. Licence and permit checks routinely produce a dozen
# URLs, so batching matters for both latency and cost.
MAX_URLS_PER_CALL = 20


class ExtractedPage(BaseModel):
    url: str
    title: Optional[str] = None
    content: str = ""
    excerpts: List[str] = Field(default_factory=list)
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.content or self.excerpts)


class ParallelExtractUnavailable(RuntimeError):
    pass


class ParallelExtract:
    """Extract clean markdown from known URLs. Handles JS pages and PDFs."""

    def __init__(self, client: Optional[ParallelClient] = None):
        self.client = client or ParallelClient()

    async def _invoke(self, urls: List[str], **kwargs: Any) -> Any:
        sdk = self.client.client

        candidates = [
            getattr(sdk, "extract", None),
            getattr(getattr(sdk, "beta", None), "extract", None),
        ]

        for fn in candidates:
            if callable(fn):
                return await fn(urls=urls, **kwargs)

        raise ParallelExtractUnavailable(
            "No `extract` method found on the Parallel SDK client. "
            "Check the installed SDK version and update `_invoke`."
        )

    async def extract(
        self,
        urls: List[str],
        excerpts: bool = True,
        full_content: bool = True,
        raise_on_error: bool = False,
    ) -> List[ExtractedPage]:
        """
        Returns one ExtractedPage per requested URL, in request order.
        Failures come back as pages with `.error` set, not as exceptions.
        """

        urls = [u for u in dict.fromkeys(urls) if u][:MAX_URLS_PER_CALL]

        if not urls:
            return []

        try:
            response = await self._invoke(
                urls,
                excerpts=excerpts,
                full_content=full_content,
            )
        except Exception as exc:  # noqa: BLE001 — degraded mode is the contract
            logger.warning("Parallel Extract failed for %d URLs: %s", len(urls), exc)
            if raise_on_error:
                raise
            return [
                ExtractedPage(url=u, error=f"extract_failed: {exc}") for u in urls
            ]

        by_url: Dict[str, ExtractedPage] = {}

        for item in getattr(response, "results", None) or []:
            url = getattr(item, "url", None)
            if not url:
                continue

            by_url[url] = ExtractedPage(
                url=url,
                title=getattr(item, "title", None),
                content=(
                    getattr(item, "full_content", None)
                    or getattr(item, "content", None)
                    or ""
                ),
                excerpts=getattr(item, "excerpts", None) or [],
            )

        return [
            by_url.get(u, ExtractedPage(url=u, error="no_result"))
            for u in urls
        ]

    async def close(self):
        await self.client.close()