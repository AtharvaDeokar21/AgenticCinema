from typing import Any


class TranscriptionService:
    """
    Shared transcription interface.

    Concrete Gemini/Google speech implementation will be
    connected once the exact transcription workflow is finalized.
    """

    async def transcribe(
        self,
        audio_path: str,
        **kwargs: Any,
    ) -> dict:
        raise NotImplementedError