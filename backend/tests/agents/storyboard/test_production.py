import pytest

from app.agents.storyboard.production import (
    StoryboardProductionPlanner,
)
from app.agents.storyboard.schemas import (
    ProductionConstraints,
)
from app.shared.models.storyboard import (
    Shot,
    ShotPlan,
)


class FakeGemini:
    def generate_structured(
        self,
        prompt,
        response_schema,
    ):
        return response_schema(
            storyboard=self.storyboard,
            production_plans=[
                {
                    "shot_id": shot.shot_id,
                    "camera": "Sony FX3",
                    "lens": "24mm",
                    "support": "Tripod",
                    "lighting_setup": (
                        "Soft key light with subtle rim light"
                    ),
                    "location_requirements": [
                        "Open outdoor location"
                    ],
                    "equipment_required": [
                        "Sony FX3",
                        "24mm lens",
                        "Tripod",
                    ],
                    "feasibility": "high",
                    "issues": [],
                    "notes": (
                        "Maintain centered framing "
                        "throughout the shot."
                    ),
                }
                for shot in self.storyboard.shots
            ],
            overall_issues=[],
        )


@pytest.fixture
def storyboard():
    return ShotPlan(
        version=1,
        shots=[
            Shot(
                shot_id="shot_01",
                beat_id="beat_01",
                start_time=0.0,
                end_time=10.0,
                shot_type="Wide Shot",
                camera_angle="Eye Level",
                camera_movement="Static",
                framing="Centered",
                subject="Person standing outdoors",
                background="Open landscape",
                lighting="Natural daylight",
                visual_description=(
                    "A cinematic wide shot "
                    "of the subject outdoors."
                ),
                colour_palette=[
                    "Blue",
                    "Green",
                ],
                on_screen_text=None,
                mood="Calm",
                reference_images=[],
                generated_image=None,
            )
        ],
        visual_style="Cinematic",
        color_palette="Blue and green",
        evidence=[],
    )


def test_production_planning(storyboard):

    constraints = ProductionConstraints(
        cameras=["Sony FX3"],
        lenses=["24mm", "50mm"],
        lights=["LED panel"],
        support=["Tripod"],
        location="Outdoor park",
        operator="Single operator",
        platform="YouTube",
        aspect_ratio="16:9",
        constraints=[],
    )

    fake_gemini = FakeGemini()
    fake_gemini.storyboard = storyboard

    planner = StoryboardProductionPlanner(
        gemini=fake_gemini,
    )

    result = planner.plan(
        storyboard=storyboard,
        constraints=constraints,
    )

    assert result.storyboard == storyboard

    assert len(result.production_plans) == 1

    plan = result.production_plans[0]

    assert plan.shot_id == "shot_01"
    assert plan.camera == "Sony FX3"
    assert plan.lens == "24mm"
    assert plan.support == "Tripod"
    assert plan.feasibility == "high"

def test_production_planning_rejects_missing_shot(
    storyboard,
):

    constraints = ProductionConstraints(
        cameras=["Sony FX3"],
        lenses=["24mm"],
        lights=["LED panel"],
        support=["Tripod"],
    )

    class BrokenGemini:
        def generate_structured(
            self,
            prompt,
            response_schema,
        ):
            return response_schema(
                storyboard=storyboard,
                production_plans=[],
                overall_issues=[],
            )

    planner = StoryboardProductionPlanner(
        gemini=BrokenGemini(),
    )

    with pytest.raises(
        ValueError,
        match="missing shots",
    ):
        planner.plan(
            storyboard=storyboard,
            constraints=constraints,
        )