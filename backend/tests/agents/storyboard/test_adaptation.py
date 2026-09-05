from app.agents.storyboard.adaptation import (
    StoryboardAdaptationPlanner,
)
from app.agents.storyboard.schemas import (
    ProductionConstraints,
    ProductionAwareStoryboard,
)
from app.shared.models.storyboard import (
    Shot,
    ShotPlan,
)


def test_storyboard_adaptation():

    storyboard = ShotPlan(
        version=1,
        shots=[
            Shot(
                shot_id="shot_01",
                beat_id="beat_01",
                start_time=0.0,
                end_time=10.0,
                shot_type="Wide Shot",
                camera_angle="Eye Level",
                camera_movement="Slow Push-in",
                framing="Centered",
                subject="Person walking through a city",
                background="Urban street",
                lighting="Natural daylight",
                visual_description=(
                    "A cinematic tracking shot "
                    "following the subject."
                ),
                colour_palette=[
                    "Blue",
                    "Grey",
                ],
                on_screen_text=None,
                mood="Cinematic",
                reference_images=[],
                generated_image=None,
            )
        ],
        visual_style="Cinematic",
        color_palette="Blue and grey",
        evidence=[],
    )

    production_storyboard = ProductionAwareStoryboard(
        storyboard=storyboard,
        production_plans=[
            {
                "shot_id": "shot_01",
                "camera": "Sony FX3",
                "lens": "24mm",
                "support": "Tripod",
                "lighting_setup": (
                    "Natural daylight"
                ),
                "location_requirements": [
                    "Urban street"
                ],
                "equipment_required": [
                    "Sony FX3",
                    "24mm lens",
                    "Tripod",
                ],
                "feasibility": "medium",
                "issues": [
                    "No gimbal available"
                ],
                "notes": (
                    "Original push-in movement "
                    "may require adaptation."
                ),
            }
        ],
        overall_issues=[
            "Camera movement equipment unavailable."
        ],
    )

    constraints = ProductionConstraints(
        cameras=["Sony FX3"],
        lenses=["24mm", "50mm"],
        lights=["LED panel"],
        support=["Tripod"],
        location="Urban street",
        operator="Single operator",
        platform="YouTube",
        aspect_ratio="16:9",
        constraints=[],
    )

    class FakeGemini:

        def generate_structured(
            self,
            prompt,
            response_schema,
        ):

            return response_schema(
                storyboard=storyboard,
                adaptations=[
                    {
                        "shot_id": "shot_01",
                        "original_movement": "Slow Push-in",
                        "adapted_movement": (
                            "Static shot with "
                            "digital push-in"
                        ),
                        "original_camera": "Sony FX3",
                        "adapted_camera": "Sony FX3",
                        "original_lens": "24mm",
                        "adapted_lens": "24mm",
                        "changes": [
                            "Replaced physical camera "
                            "movement with digital "
                            "push-in during post."
                        ],
                        "creative_intent_preserved": True,
                        "reason": (
                            "No gimbal is available."
                        ),
                    }
                ],
                overall_notes=[
                    "Storyboard adapted to tripod-only setup."
                ],
            )

    planner = StoryboardAdaptationPlanner(
        gemini=FakeGemini()
    )

    result = planner.adapt(
        production_storyboard=production_storyboard,
        constraints=constraints,
    )

    assert result.storyboard is not None
    assert len(result.storyboard.shots) == 1

    assert len(result.adaptations) == 1

    adaptation = result.adaptations[0]

    assert adaptation.shot_id == "shot_01"

    assert (
        adaptation.original_movement
        == "Slow Push-in"
    )

    assert (
        adaptation.adapted_movement
        == "Static shot with digital push-in"
    )

    assert adaptation.creative_intent_preserved is True