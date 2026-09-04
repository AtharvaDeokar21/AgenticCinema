"""
FFprobe utilities for Agentic Cinema.

Provides raw media probing as well as structured helpers for
extracting video stream information and detecting Variable Frame
Rate (VFR) content — a critical pre-flight check before uploading
video to the Gemini File API.
"""

import json
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from typing import Optional


# Maximum relative difference between declared and average FPS
# before a stream is flagged as VFR.
_VFR_TOLERANCE = 0.01


@dataclass
class VideoStreamInfo:
    """Structured summary of a single video stream."""

    codec_name: str
    width: int
    height: int

    # Declared frame rate as a rational string, e.g. "30000/1001"
    r_frame_rate: str
    # Computed average frame rate, e.g. "29.97"
    avg_frame_rate: str

    # Resolved float values
    declared_fps: float
    average_fps: float

    duration: Optional[float]
    is_vfr: bool


def probe_media(file_path: str) -> dict:
    """Return raw FFprobe metadata for a media file as a dict.

    Args:
        file_path: Absolute or relative path to the media file.

    Returns:
        Parsed JSON dict with 'format' and 'streams' keys.

    Raises:
        subprocess.CalledProcessError: If ffprobe exits non-zero.
    """

    command = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        file_path,
    ]

    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )

    return json.loads(result.stdout)


def _parse_rational_fps(rate_str: str) -> float:
    """Convert a rational string like '30000/1001' to a float.

    Args:
        rate_str: Frame rate in 'num/den' or plain float string form.

    Returns:
        Float fps value, or 0.0 if the string is unparseable / zero.
    """

    try:
        frac = Fraction(rate_str)
        return float(frac) if frac != 0 else 0.0
    except (ValueError, ZeroDivisionError):
        return 0.0


def get_video_stream_info(file_path: str) -> Optional[VideoStreamInfo]:
    """Extract structured metadata for the first video stream found.

    Args:
        file_path: Path to the media file.

    Returns:
        A VideoStreamInfo dataclass, or None if no video stream exists.

    Raises:
        subprocess.CalledProcessError: If ffprobe fails.
    """

    raw = probe_media(file_path)
    streams = raw.get("streams", [])

    video_stream = next(
        (s for s in streams if s.get("codec_type") == "video"),
        None,
    )

    if video_stream is None:
        return None

    r_frame_rate = video_stream.get("r_frame_rate", "0/1")
    avg_frame_rate = video_stream.get("avg_frame_rate", "0/1")

    declared_fps = _parse_rational_fps(r_frame_rate)
    average_fps = _parse_rational_fps(avg_frame_rate)

    # Guard against div-by-zero when both are zero
    if declared_fps > 0 and average_fps > 0:
        relative_diff = abs(declared_fps - average_fps) / declared_fps
        is_vfr = relative_diff > _VFR_TOLERANCE
    else:
        is_vfr = False

    raw_duration = video_stream.get("duration") or raw.get("format", {}).get("duration")
    duration: Optional[float] = float(raw_duration) if raw_duration else None

    return VideoStreamInfo(
        codec_name=video_stream.get("codec_name", "unknown"),
        width=int(video_stream.get("width", 0)),
        height=int(video_stream.get("height", 0)),
        r_frame_rate=r_frame_rate,
        avg_frame_rate=avg_frame_rate,
        declared_fps=declared_fps,
        average_fps=average_fps,
        duration=duration,
        is_vfr=is_vfr,
    )


def detect_vfr(file_path: str) -> bool:
    """Return True if the first video stream in the file is Variable Frame Rate.

    Compares the container's declared frame rate (r_frame_rate) against
    the per-frame average (avg_frame_rate).  A relative difference above
    _VFR_TOLERANCE (1 %) is treated as VFR.

    Args:
        file_path: Path to the media file.

    Returns:
        True if VFR is detected, False otherwise (including if no video
        stream is present).

    Raises:
        subprocess.CalledProcessError: If ffprobe fails.
    """

    info = get_video_stream_info(file_path)
    return info.is_vfr if info is not None else False