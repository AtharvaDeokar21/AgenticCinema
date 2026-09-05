from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.agents.audio import AudioAgent, AudioInputMode, AudioRequest
from app.agents.audio.schemas import (
    SegmentAnalysis,
    SegmentAnalysisReport,
    SegmentDecision,
)
from app.shared.models.project import ProjectState
from app.shared.models.script import ScriptBeat, ScriptVersion


def make_state() -> ProjectState:
    script = ScriptVersion(
        version=1,
        created_at=datetime.now(timezone.utc),
        full_text="Hello world.",
        beats=[
            ScriptBeat(
                beat_id="beat_001",
                start_time=0.0,
                end_time=2.0,
                text="Hello world.",
                audio_intent="warm and conversational",
            )
        ],
    )
    return ProjectState(
        project_id="p1",
        project_name="Demo",
        script=script,
    )


class FakeGemini:
    def __init__(self) -> None:
        self.uploaded: list[str] = []
        self.calls: list[dict] = []

    def upload_file(self, file_path: str):
        self.uploaded.append(file_path)
        return {"uploaded_audio": file_path}

    def generate_structured(self, prompt, response_schema, model):
        self.calls.append(
            {"prompt": prompt, "response_schema": response_schema, "model": model}
        )
        return SegmentAnalysisReport(
            segments=[
                SegmentAnalysis(
                    segment_id="beat_001",
                    decision=SegmentDecision.PASS,
                    reason="Line and delivery match the requested guidance.",
                    expected_expression="warm and conversational",
                    observed_delivery="warm and conversational",
                )
            ],
            overall_summary="Recording is usable.",
        )


@pytest.mark.asyncio
async def test_creator_voice_extracts_cleans_and_analyzes(tmp_path: Path) -> None:
    video = tmp_path / "creator.mp4"
    video.write_bytes(b"placeholder")

    calls: list[tuple[str, str]] = []

    def fake_extract(input_path: str, output_path: str) -> None:
        calls.append(("extract", input_path, output_path))
        Path(output_path).write_bytes(b"wav")

    def fake_clean(input_path: str, output_path: str) -> None:
        calls.append(("clean", input_path, output_path))
        Path(output_path).write_bytes(b"clean-wav")

    gemini = FakeGemini()
    state = make_state()
    result = await AudioAgent(
        extractor=fake_extract,
        cleaner=fake_clean,
        gemini=gemini,
    ).run(
        AudioRequest(
            mode=AudioInputMode.CREATOR_VOICE,
            video_path=str(video),
            project_state=state,
        )
    )

    assert result.status == "complete"
    assert result.extracted_audio_path is not None
    assert result.cleaned_audio_path is not None
    assert Path(result.extracted_audio_path).exists()
    assert Path(result.cleaned_audio_path).exists()
    assert calls == [
        ("extract", str(video), result.extracted_audio_path),
        ("clean", result.extracted_audio_path, result.cleaned_audio_path),
    ]
    assert gemini.uploaded == [result.cleaned_audio_path]
    assert len(gemini.calls) == 1
    assert gemini.calls[0]["model"] == "gemini-3.7-flash"
    assert gemini.calls[0]["response_schema"] is SegmentAnalysisReport
    assert result.segment_analysis is not None
    assert result.segment_analysis.segments[0].decision == SegmentDecision.PASS
    assert result.audio_master is not None
    assert result.audio_master.file_path == result.cleaned_audio_path
    assert result.audio_master.cleaned is True
    assert state.audio_master is result.audio_master


@pytest.mark.asyncio
async def test_creator_voice_requires_script(tmp_path: Path) -> None:
    video = tmp_path / "creator.mp4"
    video.write_bytes(b"placeholder")

    with pytest.raises(ValueError, match="requires ProjectState.script"):
        await AudioAgent(
            extractor=lambda *_: None,
            cleaner=lambda *_: None,
            gemini=FakeGemini(),
        ).run(
            AudioRequest(
                mode=AudioInputMode.CREATOR_VOICE,
                video_path=str(video),
                project_state=ProjectState(project_id="p1", project_name="Demo"),
            )
        )


@pytest.mark.asyncio
async def test_creator_voice_requires_script_beats(tmp_path: Path) -> None:
    video = tmp_path / "creator.mp4"
    video.write_bytes(b"placeholder")
    state = ProjectState(
        project_id="p1",
        project_name="Demo",
        script=ScriptVersion(
            version=1,
            created_at=datetime.now(timezone.utc),
            full_text="Hello world.",
        ),
    )

    with pytest.raises(ValueError, match="at least one script beat"):
        await AudioAgent(
            extractor=lambda *_: None,
            cleaner=lambda *_: None,
            gemini=FakeGemini(),
        ).run(
            AudioRequest(
                mode=AudioInputMode.CREATOR_VOICE,
                video_path=str(video),
                project_state=state,
            )
        )


@pytest.mark.asyncio
async def test_ai_voice_still_validates_script_and_routes(tmp_path: Path) -> None:
    video = tmp_path / "creator.mp4"
    video.write_bytes(b"placeholder")

    result = await AudioAgent(
        extractor=lambda *_: None,
        cleaner=lambda *_: None,
        gemini=FakeGemini(),
        tts=FakeTTS([1.5]),
    ).run(
        AudioRequest(
            mode=AudioInputMode.AI_VOICE,
            video_path=str(video),
            project_state=make_state(),
        )
    )

    assert result.status == "complete"
    assert result.generated_audio_path is not None


class FakeTTS:
    def __init__(self, durations: list[float]) -> None:
        self.durations = iter(durations)
        self.calls: list[dict] = []

    async def generate(self, text: str, output_path: str, **kwargs):
        import wave

        duration = next(self.durations)
        self.calls.append({"text": text, "output_path": output_path, **kwargs})
        with wave.open(output_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(b"\x00\x00" * round(duration * 24000))
        return output_path


@pytest.mark.asyncio
async def test_ai_voice_generates_each_beat_and_aligns_timeline(tmp_path: Path) -> None:
    video = tmp_path / "creator.mp4"
    video.write_bytes(b"placeholder")
    state = make_state()
    state.script.beats[0].expression = "warm, conversational"
    tts = FakeTTS([1.5])

    result = await AudioAgent(tts=tts, gemini=FakeGemini()).run(
        AudioRequest(
            mode=AudioInputMode.AI_VOICE,
            video_path=str(video),
            project_state=state,
        )
    )

    assert result.status == "complete"
    assert result.generated_audio_path is not None
    assert Path(result.generated_audio_path).exists()
    assert result.generated_segments[0].within_slot is True
    assert result.rewrite_required_beat_ids == []
    assert len(tts.calls) == 1
    assert "[warm, conversational]" in tts.calls[0]["text"]
    assert "Hello world." in tts.calls[0]["text"]
    assert result.audio_master is not None
    assert result.audio_master.file_path == result.generated_audio_path
    assert state.audio_master is result.audio_master


@pytest.mark.asyncio
async def test_ai_voice_retries_with_pacing_before_requesting_rewrite(tmp_path: Path) -> None:
    video = tmp_path / "creator.mp4"
    video.write_bytes(b"placeholder")
    tts = FakeTTS([2.8, 2.3])

    result = await AudioAgent(tts=tts, gemini=FakeGemini()).run(
        AudioRequest(
            mode=AudioInputMode.AI_VOICE,
            video_path=str(video),
            project_state=make_state(),
        )
    )

    assert result.status == "complete_with_rewrite_required"
    assert result.rewrite_required_beat_ids == ["beat_001"]
    assert len(tts.calls) == 2
    assert "[warm and conversational]" in tts.calls[0]["text"]
    assert "[warm and conversational, faster]" in tts.calls[1]["text"]
    assert result.generated_segments[0].pacing_adjusted is True
    assert result.generated_segments[0].rewrite_required is True
