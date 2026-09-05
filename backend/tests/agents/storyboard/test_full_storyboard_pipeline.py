from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.agents.storyboard.pipeline import (
    StoryboardPipeline,
)
from app.agents.storyboard.media import (
    ReferenceMediaProcessor,
)
from app.agents.storyboard.asset_generator import (
    StoryboardAssetGenerator,
)
from app.agents.storyboard.schemas import (
    ProductionConstraints,
)
from app.shared.models.script import (
    ScriptBeat,
    ScriptVersion,
)


TEST_VIDEO = Path(
    "tests/agents/storyboard/fixtures/test_reference.mp4"
)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(
    not TEST_VIDEO.exists(),
    reason="Test video fixture not available",
)
async def test_full_storyboard_pipeline(
    tmp_path,
):
    """
    Real end-to-end Storyboard pipeline.

    Real services:

        Parallel Search
        Parallel Extract
        FFmpeg
        Gemini Vision
        Gemini Storyboard Generation
        Gemini Production Planning
        Gemini Adaptation
        Hugging Face Image Generation
    """

    # =========================================================
    # 1. LOCKED SCRIPT
    # =========================================================

    script = ScriptVersion(
        version=1,
        created_at=datetime.now(
            timezone.utc
        ),
        title="Journey Through Earth",
        hook=(
            "Our planet, seen from the darkness of space."
        ),
        full_text=(
            "Our planet, seen from the darkness of space, "
            "reveals a world full of light and life."
        ),
        beats=[
            ScriptBeat(
                beat_id="beat_01",
                start_time=0.0,
                end_time=10.0,
                text=(
                    "Our planet appears against "
                    "the darkness of space."
                ),
                purpose="Establish the world",
                visual_intent=(
                    "A cinematic view of Earth surrounded "
                    "by deep space."
                ),
                audio_intent=None,
                expression=None,
            ),
            ScriptBeat(
                beat_id="beat_02",
                start_time=10.0,
                end_time=20.0,
                text=(
                    "Lights begin to reveal the cities "
                    "across the night side."
                ),
                purpose="Reveal human presence",
                visual_intent=(
                    "Glowing city lights visible across "
                    "the dark side of Earth."
                ),
                audio_intent=None,
                expression=None,
            ),
            ScriptBeat(
                beat_id="beat_03",
                start_time=20.0,
                end_time=30.0,
                text=(
                    "The planet slowly turns beneath "
                    "the quiet darkness."
                ),
                purpose="Closing",
                visual_intent=(
                    "Slow planetary movement with a calm "
                    "and expansive cinematic feeling."
                ),
                audio_intent=None,
                expression=None,
            ),
        ],
    )

    # =========================================================
    # 2. PRODUCTION CONSTRAINTS
    # =========================================================

    constraints = ProductionConstraints(
        cameras=[
            "Smartphone",
        ],
        lenses=[
            "Standard phone lens",
            "Phone telephoto lens",
        ],
        lights=[
            "LED key light",
            "Practical lamp",
        ],
        support=[
            "Tripod",
        ],
        location="Small indoor room",
        operator="Solo creator",
        platform="YouTube",
        aspect_ratio="16:9",
        constraints=[
            "No second camera operator",
            "No cinema camera",
            "No gimbal",
            "Use only available equipment",
        ],
    )

    # =========================================================
    # 3. PIPELINE COMPONENTS
    # =========================================================

    media_processor = ReferenceMediaProcessor(
        output_root=str(
            tmp_path / "media"
        )
    )

    asset_generator = StoryboardAssetGenerator(
        output_root=str(
            tmp_path / "generated"
        )
    )

    pipeline = StoryboardPipeline(
        media_processor=media_processor,
        asset_generator=asset_generator,
    )

    # =========================================================
    # 4. RUN EVERYTHING
    # =========================================================

    result = await pipeline.run(
        script=script,
        production_constraints=constraints,
        project_id="full_pipeline",
        fallback_reference_media=str(
            TEST_VIDEO
        ),
        max_references=1,
        generate_thumbnails=True,
        generate_shots=True,
    )

    # =========================================================
    # 5. PARALLEL RESEARCH
    # =========================================================

    assert result.research is not None
    assert result.research.references

    print("\n=== PARALLEL REFERENCES ===")

    for reference in (
        result.research.references
    ):
        print(
            f"- {reference.title}"
        )
        print(
            f"  {reference.url}"
        )

    # =========================================================
    # 6. FFMPEG MEDIA PROCESSING
    # =========================================================

    assert result.media_results
    assert all(
        media.error is None
        for media in result.media_results
    )

    assert any(
        media.frames
        for media in result.media_results
    )

    print("\n=== MEDIA ===")

    for media in result.media_results:
        print(media)

    # =========================================================
    # 7. GEMINI VISION
    # =========================================================

    assert result.visual_analyses

    print("\n=== VISUAL ANALYSES ===")

    for analysis in (
        result.visual_analyses
    ):
        print(analysis)

    # =========================================================
    # 8. VISUAL GRAMMAR
    # =========================================================

    assert result.visual_grammar is not None
    assert result.visual_grammar.summary

    print("\n=== VISUAL GRAMMAR ===")
    print(result.visual_grammar)

    # =========================================================
    # 9. STORYBOARD
    # =========================================================

    assert result.storyboard is not None
    assert result.storyboard.shots

    assert len(result.storyboard.shots) >= len(script.beats)

    for shot in result.storyboard.shots:
        assert shot.shot_id
        assert shot.beat_id
        assert shot.start_time < shot.end_time
        assert shot.visual_description
        assert shot.shot_type
        assert shot.framing
        assert shot.camera_movement
        assert shot.colour_palette

    expected_beats = {
        beat.beat_id
        for beat in script.beats
    }

    generated_beats = {
        shot.beat_id
        for shot in result.storyboard.shots
    }

    assert expected_beats.issubset(
        generated_beats
    )

    print("\n=== STORYBOARD ===")

    for shot in result.storyboard.shots:
        print(
            f"""
Shot: {shot.shot_id}
Beat: {shot.beat_id}
Time: {shot.start_time:.2f}s - {shot.end_time:.2f}s
Type: {shot.shot_type}
Angle: {shot.camera_angle}
Movement: {shot.camera_movement}
Framing: {shot.framing}
Subject: {shot.subject}
Background: {shot.background}
Lighting: {shot.lighting}
Mood: {shot.mood}
Description: {shot.visual_description}
Colour: {shot.colour_palette}
"""
        )

    # =========================================================
    # 10. PRODUCTION PLANNING
    # =========================================================

    assert (
        result.production_storyboard
        is not None
    )

    assert result.production_storyboard.production_plans

    # =========================================================
    # 11. ADAPTATION
    # =========================================================

    assert (
        result.adapted_storyboard
        is not None
    )

    assert (
        result.adapted_storyboard.storyboard
        is not None
    )

    assert len(
        result.adapted_storyboard.storyboard.shots
    ) == len(
        result.storyboard.shots
    )

    # =========================================================
    # 12. REAL HF IMAGE GENERATION
    # =========================================================

    assert result.assets is not None

    assert result.assets.errors == []

    assert len(
        result.assets.thumbnails
    ) == 3

    assert result.assets.storyboard_assets

    # =========================================================
    # 13. VERIFY ACTUAL FILES
    # =========================================================

    for thumbnail in (
        result.assets.thumbnails
    ):
        assert thumbnail.image_path

        path = Path(
            thumbnail.image_path
        )

        assert path.exists()
        assert path.is_file()
        assert path.stat().st_size > 0

    for asset in (
        result.assets.storyboard_assets
    ):
        assert asset.image_path

        path = Path(
            asset.image_path
        )

        assert path.exists()
        assert path.is_file()
        assert path.stat().st_size > 0

    # =========================================================
    # 14. VERIFY DIRECTORY STRUCTURE
    # =========================================================

    project_root = (
        tmp_path
        / "generated"
        / "full_pipeline"
    )

    thumbnails_dir = (
        project_root
        / "thumbnails"
    )

    shots_dir = (
        project_root
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
    assert len(shot_files) == len(
        result.assets.storyboard_assets
    )

    # =========================================================
    # 15. FINAL DEMO SUMMARY
    # =========================================================

    print("\n")
    print("=" * 70)
    print("FULL STORYBOARD PIPELINE PASSED")
    print("=" * 70)

    print(
        f"Parallel references: "
        f"{len(result.research.references)}"
    )

    print(
        f"Media results: "
        f"{len(result.media_results)}"
    )

    print(
        f"Vision analyses: "
        f"{len(result.visual_analyses)}"
    )

    print(
        f"Storyboard shots: "
        f"{len(result.storyboard.shots)}"
    )

    print(
        f"Production plans: "
        f"{len(result.production_storyboard.production_plans)}"
    )

    print(
        f"Thumbnails: "
        f"{len(result.assets.thumbnails)}"
    )

    print(
        f"Storyboard assets: "
        f"{len(result.assets.storyboard_assets)}"
    )

    print(
        f"Output directory: "
        f"{project_root}"
    )

    print("=" * 70)