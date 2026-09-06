import pytest
from pathlib import Path

from app.shared.tools.gemini.client import GeminiClient


@pytest.mark.integration
def test_gemini_image_generation(tmp_path):

    client = GeminiClient()

    output_path = (
        tmp_path
        / "gemini_test.png"
    )

    result = client.generate_image(
        prompt=(
            "A cinematic extreme wide shot of planet Earth "
            "floating in deep black space, subtle blue "
            "atmospheric rim light, realistic documentary "
            "cinematography."
        ),
        output_path=str(output_path),
        aspect_ratio="16:9",
        image_size="1K",
    )

    assert result == str(output_path)

    assert output_path.exists()

    assert output_path.stat().st_size > 0