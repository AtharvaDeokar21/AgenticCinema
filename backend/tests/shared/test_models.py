from datetime import datetime

from app.shared.models import (
    CreatorProfile,
    ProjectState,
    ScriptBeat,
    ScriptVersion,
)


def test_creator_profile():
    creator = CreatorProfile(
        creator_id="creator_001",
        name="Test Creator",
        platform="YouTube",
        niche="Technology",
        audience_geographies=["India"],
        audience_languages=["English", "Hindi"],
    )

    assert creator.name == "Test Creator"


def test_script_version():
    beat = ScriptBeat(
        beat_id="beat_001",
        start_time=0.0,
        end_time=5.0,
        text="This is the opening hook.",
    )

    script = ScriptVersion(
        version=1,
        created_at=datetime.now(),
        full_text="This is the opening hook.",
        beats=[beat],
    )

    assert len(script.beats) == 1
    assert script.beats[0].start_time == 0.0


def test_project_state():
    state = ProjectState(
        project_id="project_001",
        project_name="Demo Project",
    )

    assert state.current_stage == "created"
    assert state.script is None