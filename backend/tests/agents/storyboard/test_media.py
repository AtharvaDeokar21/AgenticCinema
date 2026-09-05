from pathlib import Path

import pytest

from app.agents.storyboard.media import (
    ReferenceMediaProcessor,
    ExtractedFrame,
)

from app.shared.tools.media.ffprobe import (
    get_video_stream_info,
)


TEST_VIDEO = Path(
    "tests/agents/storyboard/fixtures/test_reference.mp4"
)


@pytest.mark.skipif(
    not TEST_VIDEO.exists(),
    reason="Test video fixture not available",
)
def test_reference_media_processing(tmp_path):
    processor = ReferenceMediaProcessor(
        output_root=str(tmp_path / "storyboard")
    )

    result = processor.process(
        source_url="https://example.com/test-reference",
        local_path=str(TEST_VIDEO),
        reference_id="reference_01",
    )

    print("\n=== MEDIA RESULT ===")
    print(f"source_url={result.source_url}")
    print(f"local_path={result.local_path}")
    print(f"processed_path={result.processed_path}")
    print(f"duration={result.duration}")
    print(f"was_vfr={result.was_vfr}")
    print(f"error={result.error}")

    print("\n=== FRAMES ===")

    for frame in result.frames:
        print(
            f"shot={frame.shot_index} "
            f"time={frame.timestamp:.2f}s "
            f"path={frame.path}"
        )

    assert result.error is None
    assert result.local_path is not None
    assert result.processed_path is not None
    assert result.duration is not None
    assert result.duration > 0

    assert len(result.frames) > 0

    for frame in result.frames:
        assert Path(frame.path).exists()
        assert frame.timestamp >= 0
        assert frame.shot_index >= 1

@pytest.mark.skipif(
    not TEST_VIDEO.exists(),
    reason="Test video fixture not available",
)
def test_video_probe():
    info = get_video_stream_info(
        str(TEST_VIDEO)
    )

    assert info is not None
    assert info.width > 0
    assert info.height > 0
    assert info.duration is not None
    assert info.duration > 0
    assert info.average_fps > 0

    print("\n=== VIDEO INFO ===")
    print(info)

@pytest.mark.skipif(
    not TEST_VIDEO.exists(),
    reason="Test video fixture not available",
)
def test_scene_detection(tmp_path):
    processor = ReferenceMediaProcessor(
        output_root=str(tmp_path / "storyboard")
    )

    timestamps = processor._detect_shot_boundaries(
        str(TEST_VIDEO)
    )

    print("\n=== SCENE BOUNDARIES ===")

    for timestamp in timestamps:
        print(f"{timestamp:.2f}s")

    assert timestamps
    assert timestamps[0] == 0.0

    assert all(
        timestamps[index] <= timestamps[index + 1]
        for index in range(len(timestamps) - 1)
    )

@pytest.mark.skipif(
    not TEST_VIDEO.exists(),
    reason="Test video fixture not available",
)
def test_frame_extraction(tmp_path):
    processor = ReferenceMediaProcessor(
        output_root=str(tmp_path / "storyboard")
    )

    timestamps = [0.0]

    frames = processor._extract_representative_frames(
        video_path=str(TEST_VIDEO),
        timestamps=timestamps,
        output_dir=tmp_path / "frames",
    )

    print("\n=== EXTRACTED FRAMES ===")

    for frame in frames:
        print(
            f"shot={frame.shot_index} "
            f"time={frame.timestamp:.2f}s "
            f"path={frame.path}"
        )

    assert len(frames) == 1
    assert Path(frames[0].path).exists()

def test_duplicate_frame_removal(tmp_path):
    image_a = tmp_path / "a.jpg"
    image_b = tmp_path / "b.jpg"

    image_a.write_bytes(b"same-image-data")
    image_b.write_bytes(b"same-image-data")

    frames = [
        ExtractedFrame(
            path=str(image_a),
            timestamp=0.0,
            shot_index=1,
        ),
        ExtractedFrame(
            path=str(image_b),
            timestamp=1.0,
            shot_index=2,
        ),
    ]

    processor = ReferenceMediaProcessor()

    result = processor._remove_near_duplicates(
        frames
    )

    assert len(result) == 1