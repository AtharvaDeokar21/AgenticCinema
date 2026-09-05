"""Parallel Task wrapper.

Provides a stable application-level interface over Parallel's Task API.
"""

from typing import Any, Dict, Optional

from .client import ParallelClient


class ParallelTask:
    """Execute deeper web research/enrichment tasks."""

    def __init__(
        self,
        client: Optional[ParallelClient] = None,
    ):
        self.client = client or ParallelClient()

    async def run(
        self,
        task: str,
        processor: str = "base",
        task_spec: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        source_policy: Optional[Dict[str, Any]] = None,
        advanced_settings: Optional[Dict[str, Any]] = None,
        previous_interaction_id: Optional[str] = None,
        api_timeout: int = 3600,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Run a Parallel Task and wait for its completed result.

        Args:
            task: Research instructions supplied as the task input.
            processor: Parallel processor tier, e.g. ``base`` or ``ultra``.
            task_spec: Optional Parallel task specification. Use this for
                structured JSON output or explicit input/output schemas.
            metadata: Optional application metadata attached to the run.
            source_policy: Optional Parallel source policy.
            advanced_settings: Optional advanced search configuration.
            previous_interaction_id: Optional prior interaction to continue.
            api_timeout: Maximum time to wait for the completed result.
            **kwargs: Forward-compatible options supported by newer SDKs.

        Returns:
            A normalized dictionary containing the run metadata and output.
        """
        create_kwargs: Dict[str, Any] = {
            "input": task,
            "processor": processor,
        }

        optional_values = {
            "task_spec": task_spec,
            "metadata": metadata,
            "source_policy": source_policy,
            "advanced_settings": advanced_settings,
            "previous_interaction_id": previous_interaction_id,
        }

        for key, value in optional_values.items():
            if value is not None:
                create_kwargs[key] = value

        create_kwargs.update(kwargs)

        task_run = await self.client.client.task_run.create(
            **create_kwargs,
        )

        result = await self.client.client.task_run.result(
            run_id=task_run.run_id,
            api_timeout=api_timeout,
        )

        output = getattr(result, "output", None)
        content = getattr(output, "content", None)

        if content is None and isinstance(output, dict):
            content = output.get("content")

        return {
            "run": _model_to_dict(getattr(result, "run", None)),
            "run_id": task_run.run_id,
            "output": content if content is not None else _model_to_dict(output),
        }

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
