from typing import Any


class TTSService:
    """Shared text-to-speech interface."""

    async def generate(
        self,
        text: str,
        output_path: str,
        **kwargs: Any,
    ) -> str:
        raise NotImplementedError