import base64
from pathlib import Path
from typing import Any, Optional

from google import genai
from google.genai import types

from app.config import get_settings


class GeminiClient:
    """
    Shared Gemini client for Agentic Cinema.

    Development:
        Gemini Developer API + API key

    Future:
        Vertex AI / Google Cloud authentication
    """

    def __init__(self):
        settings = get_settings()

        if not settings.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is not configured."
            )

        self.client = genai.Client(
            api_key=settings.gemini_api_key
        )

        self.default_model = settings.gemini_model

    @staticmethod
    def _get_image_mime_type(path: Path) -> str:
        """
        Determine MIME type for a supported image file.
        """

        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }

        mime_type = mime_types.get(path.suffix.lower())

        if mime_type is None:
            raise ValueError(
                f"Unsupported image format: {path.suffix}"
            )

        return mime_type

    def upload_file(self, file_path: str):
        """Upload a local media file through the shared Gemini client."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Gemini upload file not found: {path}")
        return self.client.files.upload(file=path)

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        **kwargs: Any,
    ):
        """
        Generate a Gemini response.
        """

        return self.client.models.generate_content(
            model=model or self.default_model,
            contents=prompt,
            **kwargs,
        )

    def generate_image_analysis(
        self,
        prompt: str,
        image_path: str,
        response_schema=None,
        model: Optional[str] = None,
        **kwargs: Any,
    ):
        """
        Analyze a local image using Gemini vision.

        Optionally returns a structured Pydantic response.
        """

        path = Path(image_path)

        if not path.is_file():
            raise FileNotFoundError(
                f"Gemini image file not found: {path}"
            )

        image_part = types.Part.from_bytes(
            data=path.read_bytes(),
            mime_type=self._get_image_mime_type(path),
        )

        config = {}

        if response_schema is not None:
            config = {
                "response_mime_type": "application/json",
                "response_schema": response_schema,
            }

        response = self.client.models.generate_content(
            model=model or self.default_model,
            contents=[
                image_part,
                prompt,
            ],
            config=config or None,
            **kwargs,
        )

        if response_schema is not None:
            return response.parsed

        return response

    def generate_tts(
        self,
        text: str,
        *,
        voice: str = "Kore",
        model: str = "gemini-3.1-flash-tts-preview",
    ) -> bytes:
        """Generate raw PCM speech using Gemini 3.1 Flash TTS."""

        from google.genai import types

        response = self.client.models.generate_content(
            model=model,
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice,
                        )
                    )
                ),
            ),
        )

        try:
            data = response.candidates[0].content.parts[0].inline_data.data
        except (AttributeError, IndexError, TypeError) as exc:
            raise ValueError("Gemini TTS response did not contain audio data") from exc

        if isinstance(data, str):
            return base64.b64decode(data)
        return data

    def generate_structured(
        self,
        prompt: str,
        response_schema,
        model: Optional[str] = None,
        **kwargs: Any,
    ):
        """
        Generate a structured response validated against
        a Pydantic model.
        """

        response = self.client.models.generate_content(
            model=model or self.default_model,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": response_schema,
            },
            **kwargs,
        )

        return response.parsed
