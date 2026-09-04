from datetime import datetime, timezone

from app.agents.storyboard.agent import StoryboardAgent
from app.shared.models.script import ScriptBeat, ScriptVersion


def test_storyboard_agent():
    script = ScriptVersion(
        version=1,
        created_at=datetime.now(timezone.utc),
        title="Photographer of Mumbai",
        hook="A photographer discovers Mumbai through the lens.",
        full_text=(
            "A photographer walks through Mumbai, capturing the city "
            "as day turns into night."
        ),
        beats=[
            ScriptBeat(
                beat_id="beat_01",
                start_time=0.0,
                end_time=10.0,
                text="The photographer begins exploring Mumbai.",
                purpose="Introduction",
                visual_intent=(
                    "Early morning Mumbai streets with the photographer "
                    "walking with a camera."
                ),
                audio_intent="Soft morning city ambience.",
            ),
            ScriptBeat(
                beat_id="beat_02",
                start_time=10.0,
                end_time=25.0,
                text="The photographer captures the energy of the city.",
                purpose="Discovery",
                visual_intent=(
                    "Busy Mumbai streets, local trains, markets and "
                    "people moving through the city."
                ),
                audio_intent="Increasing city ambience.",
            ),
            ScriptBeat(
                beat_id="beat_03",
                start_time=25.0,
                end_time=40.0,
                text="The photographer reaches Marine Drive at sunset.",
                purpose="Climax",
                visual_intent=(
                    "Marine Drive at golden hour with the Arabian Sea "
                    "and Mumbai skyline."
                ),
                audio_intent="Emotional cinematic music.",
            ),
        ],
        status="draft",
    )

    agent = StoryboardAgent()

    result = agent.generate(script)

    print("\n=== STORYBOARD ===")
    print(result)

    assert result.version == 1
    assert len(result.shots) > 0
    assert result.visual_style
    assert result.color_palette

    beat_ids = {beat.beat_id for beat in script.beats}

    for shot in result.shots:
        assert shot.beat_id in beat_ids
        assert shot.end_time > shot.start_time

    print("\n=== SHOTS ===")
    for shot in result.shots:
        print(
            f"{shot.shot_id} | "
            f"{shot.beat_id} | "
            f"{shot.start_time}-{shot.end_time} | "
            f"{shot.shot_type}"
        )