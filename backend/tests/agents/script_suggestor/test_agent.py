import pytest

from app.agents.script_suggestor import ScriptSuggestorAgent
from app.agents.script_suggestor.schemas import ScriptRequest


@pytest.mark.asyncio
async def test_script_suggestor_agent():
    agent = ScriptSuggestorAgent()

    request = ScriptRequest(
        brief=(
            "Create a short cinematic video about a young "
            "photographer discovering Mumbai at night."
        ),
        target_audience="Young adults",
        genre="Cinematic short",
        tone="Emotional and atmospheric",
        language="English",
        duration_seconds=60,
        research_required=True,
        research_queries=[
            "Mumbai night photography locations",
            "Mumbai night culture",
        ],
    )

    result = await agent.run(request)

    assert result is not None
    assert result.status == "draft"

    assert result.title
    assert result.hook
    assert result.full_text

    assert result.beats
    assert len(result.beats) > 0

    assert result.beats[0].start_time == 0
    assert result.beats[-1].end_time <= request.duration_seconds

    for beat in result.beats:
        assert beat.beat_id
        assert beat.start_time < beat.end_time
        assert beat.text
        assert beat.purpose
        assert beat.visual_intent
        assert beat.audio_intent
    print("\nGenerated Script:")
    print(result.model_dump_json(indent=2))