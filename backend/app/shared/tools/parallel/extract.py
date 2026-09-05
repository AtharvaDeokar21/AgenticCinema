"""
Parallel Extract wrapper.

Provides a stable application-level interface over the installed
Parallel SDK.

The SDK surface differs between releases, so this wrapper intentionally
does not assume that optional arguments such as `excerpts` or
`full_content` are accepted by the SDK method.

The application still exposes excerpts/full_content in ExtractedPage,
but SDK invocation is kept compatible with the installed version.
"""

import inspect
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .client import ParallelClient

logger = logging.getLogger(__name__)

MAX_URLS_PER_CALL = 20


class ExtractedPage(BaseModel):
    url: str
    title: Optional[str] = None
    content: str = ""
    excerpts: List[str] = Field(default_factory=list)
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return (
            self.error is None
            and bool(self.content or self.excerpts)
        )


class ParallelExtractUnavailable(RuntimeError):
    pass


class ParallelExtract:
    """
    Extract clean markdown from known URLs.

    The wrapper normalizes the installed Parallel SDK response into
    ExtractedPage objects.
    """

    def __init__(
        self,
        client: Optional[ParallelClient] = None,
    ):
        self.client = client or ParallelClient()

    async def _invoke(
        self,
        urls: List[str],
    ) -> Any:

        sdk = self.client.client

        candidates = [
            getattr(sdk, "extract", None),
            getattr(
                getattr(sdk, "beta", None),
                "extract",
                None,
            ),
        ]

        for fn in candidates:

            if not callable(fn):
                continue

            # -----------------------------------------------------
            # IMPORTANT:
            #
            # Different Parallel SDK versions expose different
            # extract signatures.
            #
            # The installed version currently does NOT accept:
            #
            #     excerpts=
            #     full_content=
            #
            # Therefore determine which arguments are actually
            # accepted instead of blindly passing them.
            # -----------------------------------------------------

            try:
                signature = inspect.signature(fn)

                parameters = signature.parameters

                kwargs = {}

                if "urls" in parameters:
                    kwargs["urls"] = urls
                else:
                    # Some SDK variants may accept urls positionally.
                    return await fn(urls)

                # Only pass optional arguments if the installed
                # SDK explicitly exposes them.
                if "excerpts" in parameters:
                    kwargs["excerpts"] = True

                if "full_content" in parameters:
                    kwargs["full_content"] = True

                return await fn(**kwargs)

            except (TypeError, ValueError):

                # Some SDK callables do not expose an inspectable
                # signature. Fall back to the minimal supported call.
                return await fn(urls=urls)

        raise ParallelExtractUnavailable(
            "No `extract` method found on the Parallel SDK client. "
            "Check the installed Parallel SDK version."
        )

    async def extract(
        self,
        urls: List[str],
        excerpts: bool = True,
        full_content: bool = True,
        raise_on_error: bool = False,
    ) -> List[ExtractedPage]:
        """
        Returns one ExtractedPage per requested URL.

        SDK failures are converted into degraded-mode pages unless
        raise_on_error=True.
        """

        del excerpts
        del full_content

        urls = [
            url
            for url in dict.fromkeys(urls)
            if url
        ][:MAX_URLS_PER_CALL]

        if not urls:
            return []

        try:
            response = await self._invoke(urls)

        except Exception as exc:

            logger.warning(
                "Parallel Extract failed for %d URLs: %s",
                len(urls),
                exc,
            )

            if raise_on_error:
                raise

            return [
                ExtractedPage(
                    url=url,
                    error=f"extract_failed: {exc}",
                )
                for url in urls
            ]

        by_url: Dict[str, ExtractedPage] = {}

        results = getattr(
            response,
            "results",
            None,
        )

        for item in results or []:

            url = getattr(
                item,
                "url",
                None,
            )

            if not url:
                continue

            content = (
                getattr(
                    item,
                    "full_content",
                    None,
                )
                or getattr(
                    item,
                    "content",
                    None,
                )
                or ""
            )

            item_excerpts = (
                getattr(
                    item,
                    "excerpts",
                    None,
                )
                or []
            )

            by_url[url] = ExtractedPage(
                url=url,
                title=getattr(
                    item,
                    "title",
                    None,
                ),
                content=content,
                excerpts=item_excerpts,
            )

        return [
            by_url.get(
                url,
                ExtractedPage(
                    url=url,
                    error="no_result",
                ),
            )
            for url in urls
        ]

    async def close(self):
        await self.client.close()