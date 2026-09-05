"""Parallel Monitor wrapper.

Provides a stable application-level interface over Parallel's Monitor API.
Monitor resources are long-lived and are therefore intentionally separate
from the per-run ``monitor`` convenience method used by older code.
"""

from typing import Any, Dict, Optional

import httpx

from .client import ParallelClient


class ParallelMonitor:
    """Create and manage scheduled web monitors."""

    def __init__(
        self,
        client: Optional[ParallelClient] = None,
    ):
        self.client = client or ParallelClient()

    async def create(
        self,
        query: str,
        frequency: str = "1w",
        metadata: Optional[Dict[str, Any]] = None,
        webhook: Optional[Dict[str, Any]] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        source_policy: Optional[Dict[str, Any]] = None,
        include_backfill: bool = False,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Create a web monitor.

        ``1w`` is the default because Cultural Dub uses one monitor per
        locale to keep localization knowledge fresh weekly.
        """
        payload: Dict[str, Any] = {
            "query": query,
            "frequency": frequency,
            "include_backfill": include_backfill,
        }

        optional_values = {
            "metadata": metadata,
            "webhook": webhook,
            "output_schema": output_schema,
            "source_policy": source_policy,
        }

        for key, value in optional_values.items():
            if value is not None:
                payload[key] = value

        payload.update(kwargs)

        response = await self._request("POST", "/v1alpha/monitors", payload)
        return _model_to_dict(response)

    async def get(self, monitor_id: str) -> Dict[str, Any]:
        """Retrieve a monitor by ID."""
        response = await self._request(
            "GET",
            f"/v1alpha/monitors/{monitor_id}",
        )
        return _model_to_dict(response)

    async def update(
        self,
        monitor_id: str,
        **updates: Any,
    ) -> Dict[str, Any]:
        """Update a monitor's supported configuration."""
        response = await self._request(
            "POST",
            f"/v1alpha/monitors/{monitor_id}",
            updates,
        )
        return _model_to_dict(response)

    async def cancel(self, monitor_id: str) -> Dict[str, Any]:
        """Cancel a monitor so it no longer executes."""
        response = await self._request(
            "DELETE",
            f"/v1alpha/monitors/{monitor_id}",
        )
        return _model_to_dict(response)

    async def monitor(
        self,
        target: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Backward-compatible alias for creating a monitor."""
        return await self.create(query=target, **kwargs)

    async def _request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Call the documented Monitor endpoint through the SDK client.

        The current Python SDK exposes Task directly but may not expose every
        Monitor endpoint in every release. Its documented low-level HTTP
        methods are therefore used here to keep this wrapper compatible across
        SDK versions.
        """
        sdk = self.client.client
        request_method = getattr(sdk, method.lower(), None)

        if not callable(request_method):
            raise RuntimeError(
                "The installed Parallel SDK does not expose its low-level "
                f"{method.lower()} HTTP method required for Monitor API access."
            )

        kwargs: Dict[str, Any] = {"path": path}
        if payload:
            kwargs["body"] = payload

        response = await request_method(
            **kwargs,
            cast_to=httpx.Response,
        )

        if hasattr(response, "json"):
            return response.json()

        return response

    async def close(self):
        """Close the underlying Parallel client."""
        await self.client.close()


def _model_to_dict(value: Any) -> Any:
    """Convert SDK/Pydantic response objects into plain dictionaries."""
    if value is None:
        return None

    if isinstance(value, dict):
        return value

    if hasattr(value, "model_dump"):
        return value.model_dump()

    if hasattr(value, "to_dict"):
        return value.to_dict()

    return value
