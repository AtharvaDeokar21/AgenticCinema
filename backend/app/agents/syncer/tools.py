"""
Tool functions for the Syncer Agent.

Each function handles one discrete step of the sync pipeline so that
agent.py stays thin and each concern can be unit-tested independently.

Pipeline steps:
    1. resolve_clip_durations  — ffprobe any clip whose duration is missing
    2. prepare_video           — VFR detection + CFR conversion if required
    3. upload_video_to_gemini  — File API upload with ACTIVE-state polling
    4. call_gemini_multimodal  — compose parts, call model, return SyncMap
"""

import time
from pathlib import Path
from typing import List, Optional, Tuple

from google.genai import types

from app.agents.syncer.prompts import (
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    format_audio_clips_block,
    format_script_beats_block,
)
from app.agents.syncer.schemas import AudioClip, SyncMap, SyncRequest
from app.shared.tools.gemini.client import GeminiClient
from app.shared.tools.media.ffmpeg import convert_to_cfr
from app.shared.tools.media.ffprobe import (
    VideoStreamInfo,
    get_video_stream_info,
    probe_media,
)


# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------

# Seconds to sleep between Gemini File API state polls.
_POLL_INTERVAL_SECONDS: int = 3

# Maximum number of poll iterations before giving up (~5 minutes).
_MAX_POLL_ATTEMPTS: int = 100

# Terminal states returned by the Gemini File API.
_STATE_ACTIVE = "ACTIVE"
_STATE_FAILED = "FAILED"

# Tolerance in fps when comparing declared fps to target_fps.
# 0.5 is wide enough to treat 29.97 and 30 as equivalent but narrow
# enough to catch genuine mismatches like 24 vs 30.
_FPS_TOLERANCE = 0.5


# ---------------------------------------------------------------------------
# Step 1 — resolve_clip_durations
# ---------------------------------------------------------------------------


def resolve_clip_durations(
    audio_clips: List[AudioClip],
) -> List[AudioClip]:
    """Return a new list where every AudioClip has a populated duration.

    Clips that already carry a duration are returned unchanged.
    Clips with ``duration=None`` are probed with ffprobe: the audio
    stream duration is preferred; the container duration is used as a
    fallback.

    Args:
        audio_clips: List of AudioClip objects from the SyncRequest.

    Returns:
        New list of AudioClip objects with duration fields populated.

    Raises:
        subprocess.CalledProcessError: If ffprobe fails for any clip.
    """

    resolved: List[AudioClip] = []

    for clip in audio_clips:
        if clip.duration is not None:
            resolved.append(clip)
            continue

        raw = probe_media(clip.file_path)
        duration: Optional[float] = None

        # Prefer the duration reported by the audio stream itself.
        for stream in raw.get("streams", []):
            if stream.get("codec_type") == "audio":
                raw_dur = stream.get("duration")
                if raw_dur is not None:
                    duration = float(raw_dur)
                    break

        # Fall back to the container (format) duration.
        if duration is None:
            raw_dur = raw.get("format", {}).get("duration")
            if raw_dur is not None:
                duration = float(raw_dur)

        resolved.append(clip.model_copy(update={"duration": duration}))

    return resolved


# ---------------------------------------------------------------------------
# Step 2 — prepare_video
# ---------------------------------------------------------------------------


def prepare_video(
    video_path: str,
    target_fps: int,
) -> Tuple[str, bool, VideoStreamInfo]:
    """Probe the video and convert it to CFR if needed.

    The Gemini File API requires stable frame timestamps for accurate
    frame-level grounding.  This function detects Variable Frame Rate
    content and any fps mismatch against ``target_fps``, then triggers
    ``convert_to_cfr`` when either condition is true.

    The CFR output is written alongside the source file with ``_cfr.mp4``
    appended to the stem:
        ``/path/to/creator_raw.mov``  →  ``/path/to/creator_raw_cfr.mp4``

    Args:
        video_path:  Path to the source video (may be VFR).
        target_fps:  Desired constant frame rate for Gemini analysis.

    Returns:
        Tuple of:
            - final_path (str)      — path to the video to upload
            - was_converted (bool)  — True if CFR conversion was performed
            - info (VideoStreamInfo) — ffprobe data for the final video

    Raises:
        ValueError: If the source file has no detectable video stream, or
                    if CFR conversion produces no usable stream.
        subprocess.CalledProcessError: If ffprobe or ffmpeg fails.
    """

    info = get_video_stream_info(video_path)

    if info is None:
        raise ValueError(
            f"No video stream found in source file: {video_path!r}"
        )

    fps_mismatch = abs(info.declared_fps - target_fps) > _FPS_TOLERANCE
    needs_conversion = info.is_vfr or fps_mismatch

    if needs_conversion:
        reason = "VFR detected" if info.is_vfr else f"fps mismatch ({info.declared_fps:.3f} ≠ {target_fps})"
        print(f"[prepare_video] {reason} — converting to {target_fps} fps CFR")

        src = Path(video_path).resolve()
        cfr_path = str(src.parent / (src.stem + "_cfr.mp4"))

        convert_to_cfr(
            input_path=str(src),
            output_path=cfr_path,
            target_fps=target_fps,
        )

        cfr_info = get_video_stream_info(cfr_path)

        if cfr_info is None:
            raise RuntimeError(
                f"CFR conversion succeeded but produced no video stream: {cfr_path!r}"
            )

        return cfr_path, True, cfr_info

    print(f"[prepare_video] Video is already CFR at {info.declared_fps:.3f} fps — no conversion needed")
    return video_path, False, info


# ---------------------------------------------------------------------------
# Step 3 — upload_video_to_gemini
# ---------------------------------------------------------------------------


def upload_video_to_gemini(
    client: GeminiClient,
    video_path: str,
):
    """Upload a video to the Gemini File API and block until ACTIVE.

    The File API processes uploads asynchronously.  This function polls
    ``client.files.get()`` every ``_POLL_INTERVAL_SECONDS`` seconds until
    the file reaches state ACTIVE (success) or FAILED (error), or until
    ``_MAX_POLL_ATTEMPTS`` is exceeded.

    Args:
        client:     Initialised GeminiClient (uses ``client.client`` internally).
        video_path: Local path to the video file to upload.

    Returns:
        The active File resource object (has ``.name``, ``.uri``, ``.state``).

    Raises:
        RuntimeError: If the file reaches FAILED state or polling times out.
        subprocess.CalledProcessError / OSError: If the file cannot be read.
    """

    print(f"\n[upload_video_to_gemini] Uploading: {video_path!r}")

    file_ref = client.client.files.upload(file=video_path)

    print(f"[upload_video_to_gemini] Upload accepted — file name: {file_ref.name}")

    attempts = 0

    while file_ref.state.name not in (_STATE_ACTIVE, _STATE_FAILED):
        if attempts >= _MAX_POLL_ATTEMPTS:
            raise RuntimeError(
                f"Timed out waiting for Gemini file to become ACTIVE after "
                f"{attempts * _POLL_INTERVAL_SECONDS}s. "
                f"File name: {file_ref.name!r}, last state: {file_ref.state.name!r}"
            )

        print(
            f"[upload_video_to_gemini] State: {file_ref.state.name!r} — "
            f"retrying in {_POLL_INTERVAL_SECONDS}s (attempt {attempts + 1}/{_MAX_POLL_ATTEMPTS}) …"
        )

        time.sleep(_POLL_INTERVAL_SECONDS)
        file_ref = client.client.files.get(name=file_ref.name)
        attempts += 1

    if file_ref.state.name == _STATE_FAILED:
        raise RuntimeError(
            f"Gemini File API processing failed for {video_path!r}. "
            f"File name: {file_ref.name!r}"
        )

    print(f"[upload_video_to_gemini] File is ACTIVE — URI: {file_ref.uri}")
    return file_ref


# ---------------------------------------------------------------------------
# Step 4 — call_gemini_multimodal
# ---------------------------------------------------------------------------


def call_gemini_multimodal(
    client: GeminiClient,
    file_ref,
    video_info: VideoStreamInfo,
    request: SyncRequest,
) -> SyncMap:
    """Assemble multimodal content and call Gemini for a structured SyncMap.

    Combines the uploaded video File reference with the rendered text
    prompt (SYSTEM_PROMPT + USER_PROMPT_TEMPLATE), then calls
    ``client.models.generate_content`` with ``response_schema=SyncMap``
    so the SDK validates and parses the JSON output into a Pydantic model.

    Args:
        client:     Initialised GeminiClient.
        file_ref:   Active Gemini File resource (returned by upload step).
        video_info: ffprobe metadata for the analysed video.
        request:    The SyncRequest (with resolved audio clip durations).

    Returns:
        Parsed SyncMap Pydantic model.

    Raises:
        RuntimeError: If the model returns an unparseable response.
    """

    beats_block = format_script_beats_block(request.script_beats)
    clips_block = format_audio_clips_block(request.audio_clips)

    user_prompt = USER_PROMPT_TEMPLATE.format(
        video_duration=video_info.duration or 0.0,
        video_fps=video_info.declared_fps,
        video_path=request.video_path,
        script_beats_block=beats_block,
        audio_clips_block=clips_block,
    )

    full_prompt_text = SYSTEM_PROMPT.strip() + "\n\n" + user_prompt.strip()

    print("\n" + "=" * 80)
    print("SYNCER — GEMINI MULTIMODAL PROMPT (text portion)")
    print("=" * 80)
    print(full_prompt_text)
    print("=" * 80 + "\n")

    # Compose multimodal content: video file reference + text prompt.
    # The video Part is built from the File API URI so Gemini can
    # natively seek through frames without us having to extract them.
    contents = [
        types.Part.from_uri(
            file_uri=file_ref.uri,
            mime_type="video/mp4",
        ),
        types.Part.from_text(text=full_prompt_text),
    ]

    response = client.client.models.generate_content(
        model=client.default_model,
        contents=contents,
        config={
            "response_mime_type": "application/json",
            "response_schema": SyncMap,
        },
    )

    if response.parsed is None:
        raise RuntimeError(
            "Gemini returned a response but it could not be parsed into a "
            f"SyncMap. Raw text: {response.text!r}"
        )

    return response.parsed
