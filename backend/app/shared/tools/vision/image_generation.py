from typing import Any


class ImageGenerationService:
    """Shared interface for storyboard/concept image generation."""

    async def generate(
        self,
        prompt: str,
        output_path: str,
        **kwargs: Any,
    ) -> str:
        raise NotImplementedError