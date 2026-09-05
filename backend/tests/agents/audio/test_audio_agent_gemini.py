from pathlib import Path
from datetime import datetime, timezone

import pytest

from app.agents.audio import AudioAgent, AudioInputMode, AudioRequest
from app.shared.models.project import ProjectState
from app.shared.models.script import ScriptBeat, ScriptVersion


@pytest.mark.asyncio
async def test_ai_voice_real_gemini_request():


    backend_dir = Path(__file__).resolve().parents[2]
    video_path = backend_dir / "data" / "test_video.mp4"

    if not video_path.exists():
        pytest.fail(
            f"Test video not found: {video_path}\n"
            "Place a real video at backend/data/test_video.mp4"
        )

    script = ScriptVersion(
    version=1,
    created_at=datetime.now(timezone.utc),
    title="Gemini TTS Integration Test",
    full_text="This is a real Gemini audio generation test.",
    beats=[
        ScriptBeat(
            beat_id="test_beat_001",
            start_time=0.0,
            end_time=5.0,
            text="This is a real Gemini audio generation test.",
            expression="warm, conversational",
        )
    ],
)

    project_state = ProjectState(
        project_id="gemini-tts-test",
        project_name="Gemini TTS Integration Test",
        script=script,
    )

    request = AudioRequest(
        mode=AudioInputMode.AI_VOICE,
        video_path=str(video_path.resolve()),
        project_state=project_state,
    )

    print("\n========================================")
    print("REAL GEMINI AUDIO AGENT TEST")
    print("========================================")
    print(f"Video: {video_path}")
    print("Beat: test_beat_001")
    print("Expression: warm, conversational")
    print("Calling AudioAgent...")
    print("")

    agent = AudioAgent()

    result = await agent.run(request)

    print("")
    print("========================================")
    print("RESULT")
    print("========================================")
    print(f"Status: {result.status}")
    print(f"Generated audio: {result.generated_audio_path}")

    assert result.generated_audio_path is not None

    generated_path = Path(result.generated_audio_path)

    assert generated_path.exists(), (
        f"Gemini-generated audio was not created: {generated_path}"
    )

    assert generated_path.stat().st_size > 0

    assert result.audio_master is not None
    assert result.audio_master.file_path == str(generated_path)

    assert len(result.generated_segments) == 1

    segment = result.generated_segments[0]

    print(f"Generated duration: {segment.generated_duration:.2f}s")
    print(f"Beat slot: {segment.end_time - segment.start_time:.2f}s")
    print(f"Within slot: {segment.within_slot}")
    print(f"Pacing adjusted: {segment.pacing_adjusted}")
    print(f"Rewrite required: {segment.rewrite_required}")

    print("")
    print("REAL GEMINI REQUEST SUCCEEDED.")