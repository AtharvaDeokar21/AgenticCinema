from __future__ import annotations

from pathlib import Path

from app.shared.tools.media.ffmpeg import run_ffmpeg


def clean_audio(input_path: str, output_path: str) -> None:
    """Clean a voice recording using deterministic FFmpeg filters.

    The operation is intentionally deterministic; Gemini decides what
    should be done, while FFmpeg performs the actual media transformation.
    """
    input_file = Path(input_path)
    output_file = Path(output_path)

    if not input_file.exists():
        raise FileNotFoundError(f"Input audio file does not exist: {input_path}")

    output_file.parent.mkdir(parents=True, exist_ok=True)

    run_ffmpeg(
        str(input_file),
        str(output_file),
        [
            "-af",
            (
                "highpass=f=80,"
                "lowpass=f=12000,"
                "afftdn=nr=12:nf=-50"
            ),
            "-acodec",
            "pcm_s16le",
        ],
    )