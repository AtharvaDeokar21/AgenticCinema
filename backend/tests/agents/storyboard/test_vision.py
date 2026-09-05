import pytest
from pathlib import Path

from app.agents.storyboard.media import ExtractedFrame
from app.agents.storyboard.vision import (
    StoryboardReferenceVisionAnalyzer,
)
from app.agents.storyboard.schemas import VisualReferenceAnalysis


TEST_FRAME = Path(
    "tests/agents/storyboard/fixtures/test_frame.jpg"
)


@pytest.mark.asyncio
@pytest.mark.skipif(
    not TEST_FRAME.exists(),
    reason="Test frame fixture not available",
)
async def test_analyze_frame():

    analyzer = StoryboardReferenceVisionAnalyzer()

    frame = ExtractedFrame(
        path=str(TEST_FRAME),
        timestamp=0.0,
        shot_index=1,
    )

    result = await analyzer.analyze_frame(
        frame=frame,
        reference_url="https://example.com/test-reference",
    )

    print("\n=== VISION ANALYSIS ===")
    print(f"Reference URL: {result.reference_url}")
    print(f"Shot size: {result.shot_size}")
    print(f"Camera angle: {result.camera_angle}")
    print(f"Subject placement: {result.subject_placement}")
    print(f"Background: {result.background}")
    print(f"Lighting: {result.lighting}")
    print(f"Colour palette: {result.colour_palette}")
    print(f"Movement: {result.movement}")
    print(f"On-screen text: {result.on_screen_text}")
    print(f"Mood: {result.mood}")

    assert result is not None
    assert result.reference_url == (
        "https://example.com/test-reference"
    )

@pytest.mark.asyncio
@pytest.mark.skipif(
    not TEST_FRAME.exists(),
    reason="Test frame fixture not available",
)
async def test_analyze_frames():

    analyzer = StoryboardReferenceVisionAnalyzer()

    frames = [
        ExtractedFrame(
            path=str(TEST_FRAME),
            timestamp=0.0,
            shot_index=1,
        ),
        ExtractedFrame(
            path=str(TEST_FRAME),
            timestamp=1.0,
            shot_index=2,
        ),
    ]

    results = await analyzer.analyze_frames(
        frames=frames,
        reference_url="https://example.com/test-reference",
    )

    print("\n=== MULTI-FRAME ANALYSIS ===")

    for result in results:
        print(result)

    assert len(results) == 2

    for result in results:
        assert isinstance(
            result,
            VisualReferenceAnalysis,
        )