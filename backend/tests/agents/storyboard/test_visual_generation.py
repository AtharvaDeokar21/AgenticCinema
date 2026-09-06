import pytest

from app.agents.storyboard.schemas import (
    ProductionAwareStoryboard,
    ProductionConstraints,
)
from app.agents.storyboard.production import (
    StoryboardProductionPlanner,
)
from app.agents.storyboard.visual_generation import (
    StoryboardVisualGenerator,
)
from app.shared.models.storyboard import (
    Shot,
    ShotPlan,
)


class FakeGemini:
    pass


def build_storyboard():

    return ShotPlan(
        version=1,
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
                background="Deep black outer space",
                lighting="Low-key blue rim lighting",
                visual_description=(
                    "Earth suspended against the darkness of space."
                ),
                colour_palette=[
                    "Deep blue",
                    "Black",
                    "Golden yellow",
                    "Cyan",
                ],
                on_screen_text=None,
                mood="Cosmic and serene",
            ),
        ],
        visual_style=(
            "Cinematic documentary style with centered planetary framing."
        ),
        color_palette=(
            "Deep blue, Black, Golden yellow, Cyan"
        ),
        evidence=[],
    )


def build_production_storyboard():

    storyboard = build_storyboard()

    return ProductionAwareStoryboard(
        storyboard=storyboard,
        production_plans=[],
        overall_issues=[],
    )


def test_visual_generation_builds_three_thumbnail_variants():

    generator = StoryboardVisualGenerator(
        gemini=FakeGemini()
    )

    result = generator.generate(
        build_production_storyboard(),
        generate_concept_art=True,
    )

    assert len(result.thumbnails) == 3

    directions = {
        thumbnail.direction
        for thumbnail in result.thumbnails
    }

    assert directions == {
        "face-forward",
        "object-forward",
        "text-forward",
    }


def test_visual_generation_builds_storyboard_panels():

    generator = StoryboardVisualGenerator(
        gemini=FakeGemini()
    )

    result = generator.generate(
        build_production_storyboard(),
        generate_concept_art=False,
    )

    assert len(result.storyboard_panels) == 1

    panel = result.storyboard_panels[0]

    assert panel.shot_id == "shot_01"
    assert panel.beat_id == "beat_01"
    assert panel.prompt


def test_visual_generation_builds_concept_art():

    generator = StoryboardVisualGenerator(
        gemini=FakeGemini()
    )

    result = generator.generate(
        build_production_storyboard(),
        generate_concept_art=True,
    )

    assert len(result.concept_art) == 1
    assert result.concept_art[0].prompt