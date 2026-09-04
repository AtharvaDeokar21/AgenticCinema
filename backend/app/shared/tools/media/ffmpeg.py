"""
FFmpeg utilities for Agentic Cinema.

Provides subprocess wrappers around common ffmpeg operations used
across agents, including audio extraction and Variable Frame Rate
(VFR) to Constant Frame Rate (CFR) conversion — required before
uploading video to the Gemini File API.
"""

import subprocess
from pathlib import Path


# Default CFR target used when no explicit fps is requested.
# 30 fps is a safe, widely supported value that preserves visual
# fidelity for typical creator-shot content.
_DEFAULT_CFR_FPS = 30


def run_ffmpeg(
    input_path: str,
    output_path: str,
    args: list[str],
) -> None:
    """Run an FFmpeg operation with a single input and output.

    Args:
        input_path:  Path to the source media file.
        output_path: Desired destination path.
        args:        Extra ffmpeg arguments inserted between the input
                     and the output path (e.g. codec flags, filters).

    Raises:
        subprocess.CalledProcessError: If ffmpeg exits non-zero.
    """

    command = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        *args,
        output_path,
    ]

    subprocess.run(
        command,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def extract_audio(
    video_path: str,
    output_path: str,
) -> None:
    """Extract a raw PCM audio track from a video file.

    Args:
        video_path:  Path to the source video.
        output_path: Destination WAV path.

    Raises:
        subprocess.CalledProcessError: If ffmpeg fails.
    """

    run_ffmpeg(
        input_path=video_path,
        output_path=output_path,
        args=[
            "-vn",
            "-acodec",
            "pcm_s16le",
        ],
    )


def convert_to_cfr(
    input_path: str,
    output_path: str,
    target_fps: int = _DEFAULT_CFR_FPS,
) -> str:
    """Re-encode a VFR video to a Constant Frame Rate (CFR) copy.

    The Gemini File API requires predictable timestamps for accurate
    frame-level grounding.  VFR content causes seek errors and
    misaligned visual timestamps, so any VFR source must be conformed
    to CFR before upload.

    The output is re-encoded with libx264 using the ``fps`` video
    filter so that every output frame has a uniform presentation
    timestamp (PTS).  The original file is never modified.

    Args:
        input_path:  Path to the VFR source video.
        output_path: Destination path for the CFR output.  Must be
                     different from ``input_path``.
        target_fps:  Target constant frame rate.  Defaults to 30 fps.

    Returns:
        The resolved absolute output path as a string.

    Raises:
        ValueError: If input_path and output_path are the same file.
        subprocess.CalledProcessError: If ffmpeg exits non-zero.
    """

    src = Path(input_path).resolve()
    dst = Path(output_path).resolve()

    if src == dst:
        raise ValueError(
            "input_path and output_path must be different files. "
            "convert_to_cfr() never overwrites the original."
        )

    dst.parent.mkdir(parents=True, exist_ok=True)

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        # Force constant frame rate by duplicating/dropping frames.
        "-vf",
        f"fps={target_fps}",
        # Use libx264 so timestamps are fully rewritten.
        "-c:v",
        "libx264",
        # Copy audio stream as-is — we only care about video timing.
        "-c:a",
        "copy",
        # Suppress console spam; errors still surface via CalledProcessError.
        "-loglevel",
        "error",
        str(dst),
    ]

    subprocess.run(
        command,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    return str(dst)