from typing import Any


class MusicGenerationService:
    """Shared interface for music/audio generation."""

    async def generate(
        self,
        prompt: str,
        output_path: str,
        **kwargs: Any,
    ) -> str:
        raise NotImplementedError