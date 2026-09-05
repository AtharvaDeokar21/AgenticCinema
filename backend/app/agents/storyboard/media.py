from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
import hashlib
import math
import subprocess

from app.shared.tools.media.ffmpeg import convert_to_cfr, extract_frame_at
from app.shared.tools.media.ffprobe import get_video_stream_info


@dataclass
class ExtractedFrame:
    """
    A representative frame extracted from a reference video.
    """

    path: str
    timestamp: float
    shot_index: int


@dataclass
class ReferenceMedia:
    """
    Processed media for a single storyboard reference.
    """

    source_url: str
    local_path: Optional[str] = None
    duration: Optional[float] = None
    was_vfr: bool = False
    processed_path: Optional[str] = None

    frames: List[ExtractedFrame] = field(default_factory=list)

    error: Optional[str] = None


class ReferenceMediaProcessor:
    """
    Phase 2 storyboard media processor.

    Responsibilities:
        1. Inspect reference video.
        2. Convert VFR media to CFR when required.
        3. Detect shot boundaries using FFmpeg scene detection.
        4. Extract representative frames.
        5. Remove near-duplicate frames.

    Downloading is intentionally kept separate because the exact
    media source/download mechanism may vary by reference URL.
    """

    SCENE_THRESHOLD = 0.4
    DEFAULT_SAMPLE_INTERVAL = 1.0

    def __init__(self, output_root: str = "storage/storyboard/references"):
        self.output_root = Path(output_root)

    def process(
        self,
        source_url: str,
        local_path: str,
        reference_id: str,
    ) -> ReferenceMedia:

        result = ReferenceMedia(
            source_url=source_url,
            local_path=local_path,
        )

        try:
            info = get_video_stream_info(local_path)

            if info is None:
                result.error = "no_video_stream"
                return result

            result.duration = info.duration
            result.was_vfr = info.is_vfr

            processed_path = self._prepare_video(
                local_path=local_path,
                reference_id=reference_id,
                is_vfr=info.is_vfr,
            )

            result.processed_path = processed_path

            frame_dir = (
                self.output_root
                / reference_id
                / "frames"
            )

            frame_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            timestamps = self._detect_shot_boundaries(
                processed_path
            )

            frames = self._extract_representative_frames(
                video_path=processed_path,
                timestamps=timestamps,
                output_dir=frame_dir,
            )

            result.frames = self._remove_near_duplicates(frames)

            return result

        except Exception as exc:
            result.error = f"media_processing_failed: {exc}"
            return result

    def _prepare_video(
        self,
        local_path: str,
        reference_id: str,
        is_vfr: bool,
    ) -> str:

        if not is_vfr:
            return str(Path(local_path).resolve())

        output_path = (
            self.output_root
            / reference_id
            / "cfr.mp4"
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        return convert_to_cfr(
            input_path=local_path,
            output_path=str(output_path),
        )

    def _detect_shot_boundaries(
        self,
        video_path: str,
    ) -> List[float]:

        command = [
            "ffmpeg",
            "-i",
            video_path,
            "-vf",
            (
                f"select='gt(scene,{self.SCENE_THRESHOLD})',"
                "showinfo"
            ),
            "-an",
            "-f",
            "null",
            "-",
        ]

        result = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        timestamps = []

        for line in result.stderr.splitlines():
            if "showinfo" not in line:
                continue

            timestamp = self._parse_showinfo_timestamp(line)

            if timestamp is not None:
                timestamps.append(timestamp)

        # The first frame is always a useful representative.
        if not timestamps:
            return [0.0]

        return sorted(
            set(
                [0.0] + timestamps
            )
        )

    @staticmethod
    def _parse_showinfo_timestamp(
        line: str,
    ) -> Optional[float]:

        # Example:
        #
        # showinfo ... pts_time:12.5333 ...
        #
        marker = "pts_time:"

        if marker not in line:
            return None

        value = line.split(
            marker,
            1,
        )[1].split(
            " ",
            1,
        )[0]

        try:
            return float(value)
        except ValueError:
            return None

    def _extract_representative_frames(
        self,
        video_path: str,
        timestamps: List[float],
        output_dir: Path,
    ) -> List[ExtractedFrame]:

        frames = []

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        for index, timestamp in enumerate(
            timestamps,
            start=1,
        ):

            output_path = (
                output_dir
                / f"shot_{index:04d}.jpg"
            )

            command = [
                "ffmpeg",
                "-y",
                "-ss",
                str(timestamp),
                "-i",
                str(video_path),
                "-map",
                "0:v:0",
                "-frames:v",
                "1",
                "-q:v",
                "2",
                "-update",
                "1",
                str(output_path),
            ]

            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            if result.returncode != 0:
                raise RuntimeError(
                    "FFmpeg frame extraction failed "
                    f"at timestamp {timestamp}s:\n"
                    f"{result.stderr}"
                )

            if output_path.exists():
                frames.append(
                    ExtractedFrame(
                        path=str(output_path),
                        timestamp=timestamp,
                        shot_index=index,
                    )
                )

        return frames

    @staticmethod
    def _remove_near_duplicates(
        frames: List[ExtractedFrame],
    ) -> List[ExtractedFrame]:

        """
        Lightweight perceptual duplicate filtering.

        We intentionally keep this dependency-free for Phase 2.
        A small image hash is sufficient for the first pass.

        Phase 3 can replace this with a stronger perceptual
        similarity mechanism if required.
        """

        if len(frames) <= 1:
            return frames

        kept = []
        hashes = set()

        for frame in frames:

            frame_hash = ReferenceMediaProcessor._image_hash(
                frame.path
            )

            if frame_hash in hashes:
                continue

            hashes.add(frame_hash)
            kept.append(frame)

        return kept

    @staticmethod
    def _image_hash(
        image_path: str,
    ) -> str:

        """
        Deterministic content hash.

        This is deliberately not described as a perceptual hash.
        It removes exact duplicate files while keeping the Phase 2
        implementation dependency-free.
        """

        digest = hashlib.sha256()

        with open(image_path, "rb") as image:
            while chunk := image.read(8192):
                digest.update(chunk)

        return digest.hexdigest()