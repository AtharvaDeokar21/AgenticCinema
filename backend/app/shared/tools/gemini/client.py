from typing import Any, Optional

from google import genai

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