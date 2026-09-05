from pathlib import Path

from app.agents.storyboard.asset_generator import (
    StoryboardAssetGenerator,
)
from app.agents.storyboard.schemas import (
    ProductionAwareStoryboard,
    ShotProductionPlan,
)
from app.shared.models.storyboard import (
    Shot,
    ShotPlan,
)


class FakeImageGenerationClient:

    def __init__(self):
        self.calls = []

    def generate_image(
        self,
        prompt: str,
        output_path: str,
        *,
        aspect_ratio: str = "16:9",
        image_size: str = "1K",
        model: str | None = None,
    ) -> str:

        self.calls.append(
            {
                "prompt": prompt,
                "output_path": output_path,
                "aspect_ratio": aspect_ratio,
                "image_size": image_size,
                "model": model,
            }
        )

        path = Path(output_path)
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_bytes(b"fake-image")

        return str(path)


def _build_storyboard() -> ShotPlan:

    return ShotPlan(
        version=1,
        visual_style="Cinematic documentary",
        color_palette="Deep blue, black, cyan",
        evidence=[],
        shots=[
            Shot(
                shot_id="shot_01",
                beat_id="beat_01",
                start_time=0.0,
                end_time=10.0,
                shot_type="Extreme Wide Shot",
                camera_angle="Eye Level",
                camera_movement="Static",
                framing="Centered",
                subject="Planet Earth",
                background="Deep black space",
                lighting="Low-key blue rim lighting",
                visual_description=(
                    "Earth suspended against the darkness "
                    "of space."
                ),
                colour_palette=[
                    "Deep blue",
                    "Black",
                    "Cyan",
                ],
                mood="Serene",
            ),
        ],
    )


def _build_production() -> ProductionAwareStoryboard:

    storyboard = _build_storyboard()

    return ProductionAwareStoryboard(
        storyboard=storyboard,
        production_plans=[
            ShotProductionPlan(
                shot_id="shot_01",
                camera="Virtual camera",
                lens="Wide",
                support="Tripod",
                lighting_setup=(
                    "Soft blue rim light"
                ),
                location_requirements=[],
                equipment_required=[],
                feasibility="high",
                issues=[],
                notes="",
            ),
        ],
        overall_issues=[],
    )


def test_storyboard_asset_generation(tmp_path):

    fake_image_client = FakeImageGenerationClient()

    generator = StoryboardAssetGenerator(
        image_client=fake_image_client,
        output_root=str(tmp_path),
    )

    result = generator.generate(
        storyboard=_build_storyboard(),
        production=_build_production(),
        project_id="test_project",
        generate_shots=True,
    )

    assert len(result.thumbnails) == 3

    assert len(result.storyboard_assets) == 1

    assert len(fake_image_client.calls) == 4

    variants = {
        thumbnail.variant
        for thumbnail in result.thumbnails
    }

    assert variants == {
        "face-forward",
        "object-forward",
        "text-forward",
    }

    for thumbnail in result.thumbnails:
        assert thumbnail.image_path is not None
        assert Path(
            thumbnail.image_path
        ).exists()

    asset = result.storyboard_assets[0]

    assert asset.shot_id == "shot_01"
    assert asset.asset_type == "storyboard_keyframe"
    assert asset.image_path is not None
    assert Path(
        asset.image_path
    ).exists()