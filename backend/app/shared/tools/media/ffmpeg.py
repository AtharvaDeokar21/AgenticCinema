import subprocess
from pathlib import Path


def run_ffmpeg(
    input_path: str,
    output_path: str,
    args: list[str],
) -> None:
    """Run an FFmpeg operation."""

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
    run_ffmpeg(
        input_path=video_path,
        output_path=output_path,
        args=[
            "-vn",
            "-acodec",
            "pcm_s16le",
        ],
    )