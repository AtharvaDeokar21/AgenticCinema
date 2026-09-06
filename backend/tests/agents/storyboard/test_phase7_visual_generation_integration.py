import pytest
from pathlib import Path

from app.agents.storyboard.agent import StoryboardAgent
from app.agents.storyboard.schemas import ProductionConstraints
from app.shared.models.script import ScriptVersion
from app.agents.storyboard.visual._generation import (
    StoryboardVisualGenerator,
)


@pytest.mark.integration
def test_phase7_real_visual_generation(tmp_path):

    script = _build_script()

    constraints = ProductionConstraints(
        cameras=["Sony FX3"],
        lenses=["24mm", "35mm", "50mm"],
        lights=["LED panel"],
        support=["Tripod", "Gimbal"],
        location="Controlled indoor location",
        operator="Single operator",
        platform="YouTube",
        aspect_ratio="16:9",
    )

    # Phase 1-3: storyboard generation
    agent = StoryboardAgent()

    storyboard = agent.generate(
        script=script,
        production_constraints=constraints,
    )

    assert storyboard.shots

    # Production planning
    production_storyboard = agent.plan_production(
        storyboard=storyboard,
        production_constraints=constraints,
    )

    assert production_storyboard.production_plans

    # Phase 7
    generator = StoryboardVisualGenerator()

    result = generator.generate(
        production_storyboard,
        output_dir=str(tmp_path),
        generate_concept_art=True,
    )

    # Verify thumbnails
    assert result.thumbnails

    for thumbnail in result.thumbnails:
        assert thumbnail.image_path is not None
        assert Path(thumbnail.image_path).exists()
        assert Path(thumbnail.image_path).stat().st_size > 0

    # Verify storyboard panels
    assert result.storyboard_panels

    for panel in result.storyboard_panels:
        assert panel.image_path is not None
        assert Path(panel.image_path).exists()
        assert Path(panel.image_path).stat().st_size > 0

    # Verify concept art
    for concept in result.concept_art:
        assert concept.image_path is not None
        assert Path(concept.image_path).exists()
        assert Path(concept.image_path).stat().st_size > 0

    assert not result.errors