import pytest
from pathlib import Path

from app.shared.tools.image.client import (
    ImageGenerationClient,
)


@pytest.mark.integration
def test_real_image_generation(tmp_path):

    client = ImageGenerationClient()

    output_path = (
        tmp_path
        / "image_test.png"
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

    assert Path(result).exists()

    assert Path(result).stat().st_size > 0