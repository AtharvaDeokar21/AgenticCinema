"""
Integration tests for the Syncer Agent.

Exercises the full end-to-end pipeline:
    resolve_clip_durations → prepare_video → upload_video_to_gemini
    → call_gemini_multimodal → SyncMap output validation

Fixture strategy
----------------
A 3-second silent black MP4 video and three per-beat silent WAV audio
clips are generated with ffmpeg into pytest's ``tmp_path`` directory.
Using real (albeit synthetic) media files ensures that the ffprobe
duration resolution, VFR detection, and Gemini File API upload all
receive genuine file handles without requiring any pre-existing assets
in the repository.

Important note on the test video
---------------------------------
The fixture produces a synthetic black screen with no human face.
Gemini will not find mouth motion and may fall back to using the
script beat's expected start timestamps, returning status "partial".
All assertions in the test are written to hold for both "complete"
and "partial" outcomes so the test is not brittle against the model's
creative judgement.
"""

import subprocess
from pathlib import Path

import pytest

from app.agents.syncer import SyncerAgent, SyncMap, SyncRequest
from app.agents.syncer.schemas import AudioClip
from app.shared.models.script import ScriptBeat


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _generate_silent_video(output_path: Path, duration: float = 3.0) -> None:
    """Write a silent black MP4 to *output_path* using ffmpeg's lavfi source.

    Uses two lavfi inputs (color + anullsrc) so the output container has
    both a video and an audio stream — matching the format of a real
    creator recording and exercising the full ffprobe stream-detection
    path in ``get_video_stream_info``.

    Args:
        output_path: Destination path for the generated MP4.
        duration:    Video duration in seconds.

    Raises:
        subprocess.CalledProcessError: If ffmpeg is not on PATH or fails.
    """

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            # Black video at a constant 30 fps
            "-f", "lavfi",
            "-i", "color=c=black:s=640x480:r=30",
            # Silent stereo audio at 44.1 kHz
            "-f", "lavfi",
            "-i", "anullsrc=r=44100:cl=stereo",
            "-t", str(duration),
            "-c:v", "libx264",
            "-c:a", "aac",
            # Stop when the shorter source ends
            "-shortest",
            # Suppress informational output; errors still surface
            "-loglevel", "error",
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )


def _generate_silent_audio(output_path: Path, duration: float = 1.0) -> None:
    """Write a silent mono WAV clip to *output_path* using ffmpeg's anullsrc.

    Args:
        output_path: Destination path for the generated WAV.
        duration:    Clip duration in seconds.

    Raises:
        subprocess.CalledProcessError: If ffmpeg is not on PATH or fails.
    """

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f", "lavfi",
            "-i", "anullsrc=r=44100:cl=mono",
            "-t", str(duration),
            "-c:a", "pcm_s16le",
            "-loglevel", "error",
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sync_request(tmp_path: Path) -> SyncRequest:
    """Build a SyncRequest backed by ffmpeg-generated media files.

    File layout inside *tmp_path*::

        test_video.mp4       3-second silent black CFR video (640x480 @ 30fps)
        audio_beat_001.wav   1-second silent mono WAV for beat_001
        audio_beat_002.wav   1-second silent mono WAV for beat_002
        audio_beat_003.wav   1-second silent mono WAV for beat_003

    Returns:
        A fully populated SyncRequest with three ScriptBeats and three
        matching AudioClips.
    """

    # --- Generate media files ------------------------------------------------

    video_path = tmp_path / "test_video.mp4"
    _generate_silent_video(video_path, duration=3.0)

    audio_paths: list[Path] = []
    for i in range(1, 4):
        audio_path = tmp_path / f"audio_beat_{i:03d}.wav"
        _generate_silent_audio(audio_path, duration=1.0)
        audio_paths.append(audio_path)

    # --- Script beats --------------------------------------------------------

    beats = [
        ScriptBeat(
            beat_id="beat_001",
            start_time=0.0,
            end_time=1.0,
            text=(
                "Welcome to this short tutorial. "
                "Today we are going to cover something exciting."
            ),
            purpose="Hook and introduction",
            visual_intent="Creator faces the camera with a confident smile",
            audio_intent="Warm, inviting opening tone",
        ),
        ScriptBeat(
            beat_id="beat_002",
            start_time=1.0,
            end_time=2.0,
            text=(
                "Let us start with the first key idea "
                "and break it down step by step."
            ),
            purpose="Transition to core content",
            visual_intent="Creator gestures towards the concept on screen",
            audio_intent="Clear, deliberate instructional tone",
        ),
        ScriptBeat(
            beat_id="beat_003",
            start_time=2.0,
            end_time=3.0,
            text=(
                "And that is all for today. "
                "Thank you for watching — see you next time."
            ),
            purpose="Closing and call to action",
            visual_intent="Creator smiles and gives a small wave goodbye",
            audio_intent="Warm, grateful closing tone",
        ),
    ]

    # --- Audio clips ---------------------------------------------------------

    clips = [
        AudioClip(beat_id="beat_001", file_path=str(audio_paths[0])),
        AudioClip(beat_id="beat_002", file_path=str(audio_paths[1])),
        AudioClip(beat_id="beat_003", file_path=str(audio_paths[2])),
    ]

    # --- Assemble request ----------------------------------------------------

    return SyncRequest(
        video_path=str(video_path),
        script_beats=beats,
        audio_clips=clips,
        target_fps=30,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_syncer_agent(sync_request: SyncRequest) -> None:
    """End-to-end integration test for the full Syncer Agent pipeline.

    Exercises every step from duration resolution through to the final
    SyncMap output, including a live Gemini API call with multimodal
    video + text content.

    Assertions are intentionally permissive about *which* beats get
    placed vs. flagged as unplaced, because a synthetic black-screen
    video contains no face for Gemini to ground against.  What we
    guarantee is that the SyncMap *structure* is always valid.
    """

    agent = SyncerAgent()

    result = await agent.run(sync_request)

    # ------------------------------------------------------------------
    # Top-level structure
    # ------------------------------------------------------------------

    assert result is not None
    assert isinstance(result, SyncMap)

    # Terminal status must be one of the two expected values.
    # "failed" would indicate a complete inability to produce any output,
    # which should not happen even for a no-face video.
    assert result.status in {"complete", "partial"}, (
        f"Unexpected status {result.status!r}. "
        "Expected 'complete' or 'partial'."
    )

    # Gemini must have produced *some* output — at minimum either placed
    # beats or an explicit list of unplaceable beat IDs.
    total_accounted = len(result.placements) + len(result.unplaced_beat_ids)
    assert total_accounted > 0, (
        "SyncMap has neither placements nor unplaced_beat_ids. "
        "Gemini appears to have returned empty output."
    )

    # ------------------------------------------------------------------
    # ffprobe metadata was stamped correctly by the agent (Step 6)
    # ------------------------------------------------------------------

    assert result.video_fps > 0, (
        f"video_fps must be positive — got {result.video_fps}. "
        "Check that prepare_video() returned valid VideoStreamInfo."
    )

    assert result.video_duration > 0, (
        f"video_duration must be positive — got {result.video_duration}. "
        "Check that ffprobe found a valid duration for the test video."
    )

    # ------------------------------------------------------------------
    # AudioPlacement structural invariants
    # ------------------------------------------------------------------

    request_beat_ids = {beat.beat_id for beat in sync_request.script_beats}

    for placement in result.placements:
        # Every placed beat must correspond to one we actually sent
        assert placement.beat_id in request_beat_ids, (
            f"Placement contains unknown beat_id {placement.beat_id!r}. "
            f"Valid IDs: {request_beat_ids}"
        )

        # Temporal ordering: start must precede end
        assert placement.video_start_time < placement.video_end_time, (
            f"beat_id={placement.beat_id!r}: "
            f"video_start_time ({placement.video_start_time:.3f}s) "
            f"must be < video_end_time ({placement.video_end_time:.3f}s)"
        )

        # Confidence must be a valid probability
        assert 0.0 <= placement.confidence <= 1.0, (
            f"beat_id={placement.beat_id!r}: "
            f"confidence ({placement.confidence}) is outside [0.0, 1.0]"
        )

    # ------------------------------------------------------------------
    # Unplaced beats must also reference valid beat IDs
    # ------------------------------------------------------------------

    for unplaced_id in result.unplaced_beat_ids:
        assert unplaced_id in request_beat_ids, (
            f"unplaced_beat_ids contains unknown beat_id {unplaced_id!r}. "
            f"Valid IDs: {request_beat_ids}"
        )

    # ------------------------------------------------------------------
    # Human-readable output for inspection (mirrors script_suggestor style)
    # ------------------------------------------------------------------

    print("\nGenerated SyncMap:")
    print(result.model_dump_json(indent=2))
