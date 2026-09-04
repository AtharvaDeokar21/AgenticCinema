import subprocess
from pathlib import Path


def extract_frames(
    video_path: str,
    output_dir: str,
    fps: float = 1.0,
) -> None:
    """Extract sampled frames from a video."""

    Path(output_dir).mkdir(
        parents=True,
        exist_ok=True,
    )

    command = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-vf",
        f"fps={fps}",
        f"{output_dir}/frame_%06d.jpg",
    ]

    subprocess.run(
        command,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )