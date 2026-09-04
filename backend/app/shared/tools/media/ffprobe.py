import json
import subprocess


def probe_media(file_path: str) -> dict:
    """Return FFprobe metadata for a media file."""

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