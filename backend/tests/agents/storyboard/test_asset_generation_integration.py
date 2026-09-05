from pathlib import Path

import pytest

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
                lighting=(
                    "Subtle blue atmospheric rim light"
                ),
                visual_description=(
                    "Earth suspended against deep black "
                    "space with a subtle blue atmospheric "
                    "rim light."
                ),
                colour_palette=[
                    "Deep blue",
                    "Black",
                    "Cyan",
                ],
                mood="Serene",
                on_screen_text=None,
                reference_images=[],
                generated_image=None,
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
                    "Soft blue rim lighting "
                    "around the subject."
                ),
                location_requirements=[],
                equipment_required=[],
                feasibility="high",
                issues=[],
                notes=(
                    "Static wide cinematic composition."
                ),
            ),
        ],
        overall_issues=[],
    )


@pytest.mark.integration
def test_real_phase7_asset_generation(
    tmp_path,
):

    generator = StoryboardAssetGenerator(
        output_root=str(tmp_path),
    )

    result = generator.generate(
        storyboard=_build_storyboard(),
        production=_build_production(),
        project_id="phase7_integration",
        generate_shots=True,
        generate_thumbnails=True,
        generate_concept_art=False,
    )

    assert result.errors == []

    # ---------------------------------------------------------
    # THREE REAL THUMBNAILS
    # ---------------------------------------------------------

    assert len(result.thumbnails) == 3

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

        image_path = Path(
            thumbnail.image_path
        )

        assert image_path.exists()
        assert image_path.is_file()
        assert image_path.stat().st_size > 0

    # ---------------------------------------------------------
    # ONE REAL STORYBOARD KEYFRAME
    # ---------------------------------------------------------

    assert len(
        result.storyboard_assets
    ) == 1

    asset = result.storyboard_assets[0]

    assert asset.asset_type == (
        "storyboard_keyframe"
    )

    assert asset.shot_id == "shot_01"

    assert asset.image_path is not None

    image_path = Path(
        asset.image_path
    )

    assert image_path.exists()
    assert image_path.is_file()
    assert image_path.stat().st_size > 0

    # ---------------------------------------------------------
    # EXPECTED DIRECTORY STRUCTURE
    # ---------------------------------------------------------

    project_dir = (
        tmp_path
        / "phase7_integration"
    )

    thumbnails_dir = (
        project_dir
        / "thumbnails"
    )

    shots_dir = (
        project_dir
        / "shots"
    )

    assert thumbnails_dir.exists()
    assert shots_dir.exists()

    thumbnail_files = list(
        thumbnails_dir.glob("*.png")
    )

    shot_files = list(
        shots_dir.glob("*.png")
    )

    assert len(thumbnail_files) == 3
    assert len(shot_files) == 1