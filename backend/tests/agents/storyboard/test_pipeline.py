from datetime import datetime, timezone

from app.agents.storyboard.schemas import VisualGrammar
from app.orchestration.storyboard_pipeline import StoryboardPipeline
from app.shared.models.script import (
    ScriptBeat,
    ScriptVersion,
)
from app.shared.models.storyboard import Shot, ShotPlan


class FakeStoryboardAgent:

    def __init__(self):
        self.received_kwargs = None

    def generate(self, **kwargs):
        self.received_kwargs = kwargs

        script = kwargs["script"]

        shots = [
            Shot(
                shot_id="shot_01",
                beat_id=script.beats[0].beat_id,
                start_time=script.beats[0].start_time,
                end_time=script.beats[0].end_time,
                shot_type="Extreme Wide Shot",
                camera_angle="Eye Level",
                camera_movement="Slow",
                framing="Centered",
                subject="Earth",
                background="Deep black space",
                lighting="Low-key atmospheric lighting",
                colour_palette=[
                    "Black",
                    "Dark Blue",
                    "Gold",
                ],
                on_screen_text=None,
                mood="Serene",
                visual_description=(
                    "A centered Earth floating in deep space."
                ),
                reference_images=[],
                generated_image=None,
            )
        ]

        return ShotPlan(
            version=script.version,
            shots=shots,
            visual_style="Cosmic cinematic style",
            color_palette="Black, dark blue, gold",
            evidence=[
                "Generated using reference-derived visual grammar."
            ],
        )


def test_storyboard_pipeline_passes_visual_grammar():

    script = ScriptVersion(
        version=1,
        created_at=datetime.now(timezone.utc),
        title="Cosmic Journey",
        hook="A journey across the stars.",
        full_text="A journey across the stars.",
        beats=[
            ScriptBeat(
                beat_id="beat_01",
                start_time=0.0,
                end_time=5.0,
                text="Earth appears against the darkness.",
                purpose="Opening",
                visual_intent="Earth in deep space",
                audio_intent=None,
                expression=None,
            )
        ],
    )

    grammar = VisualGrammar(
        framing_patterns=[
            "Extreme Wide Shots",
            "Centered framing",
        ],
        camera_patterns=[
            "Eye-level camera angle",
        ],
        movement_patterns=[
            "Slow planetary rotation",
        ],
        lighting_patterns=[
            "Low-key atmospheric lighting",
        ],
        colour_patterns=[
            "Black and dark blue base",
            "Gold highlights",
        ],
        pacing_patterns=[
            "Slow contemplative pacing",
        ],
        text_patterns=[],
        summary="Cosmic cinematic visual language.",
        evidence=[
            "Pattern observed across reference frames."
        ],
    )

    fake_agent = FakeStoryboardAgent()

    pipeline = StoryboardPipeline(
        storyboard_agent=fake_agent
    )

    result = pipeline.generate(
        script=script,
        visual_grammar=grammar,
    )

    assert result is not None
    assert len(result.shots) == 1

    assert (
        fake_agent.received_kwargs["visual_grammar"]
        == grammar
    )

    assert (
        fake_agent.received_kwargs["script"]
        == script
    )