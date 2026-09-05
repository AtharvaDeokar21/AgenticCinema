from pathlib import Path
from typing import Optional

from huggingface_hub import InferenceClient

from app.config import get_settings


class ImageGenerationClient:
    """
    Provider-neutral image generation client.

    Development provider:
        Hugging Face Inference Providers

    The configured Hugging Face model is used for text-to-image
    generation and the resulting image is persisted locally.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        model: Optional[str] = None,
    ):
        settings = get_settings()

        hf_token = token or settings.hf_token

        if not hf_token:
            raise ValueError("HF_TOKEN is not configured.")

        self.client = InferenceClient(
            api_key=hf_token,
            provider="auto",
        )

        self.default_model = (
            model
            or settings.hf_image_model
        )

        if not self.default_model:
            raise ValueError(
                "HF_IMAGE_MODEL is not configured."
            )

    def generate_image(
        self,
        prompt: str,
        output_path: str,
        *,
        aspect_ratio: str = "16:9",
        image_size: str = "1K",
        model: Optional[str] = None,
    ) -> str:
        """
        Generate an image from a text prompt and save it locally.

        Returns:
            Path to the generated image.
        """

        if not prompt or not prompt.strip():
            raise ValueError(
                "Image generation prompt cannot be empty."
            )

        path = Path(output_path)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        selected_model = (
            model
            or self.default_model
        )

        image = self.client.text_to_image(
            prompt=prompt.strip(),
            model=selected_model,
        )

        image.save(path)

        if not path.exists():
            raise RuntimeError(
                f"Image generation completed but output "
                f"was not written: {path}"
            )

        if path.stat().st_size == 0:
            raise RuntimeError(
                f"Generated image is empty: {path}"
            )

        return str(path)