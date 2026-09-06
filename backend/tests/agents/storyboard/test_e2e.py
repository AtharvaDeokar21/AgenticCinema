import pytest
from datetime import datetime, timezone
from pathlib import Path

from app.agents.storyboard.agent import StoryboardAgent
from app.agents.storyboard.grammar import VisualGrammarBuilder
from app.agents.storyboard.schemas import (
    VisualReferenceAnalysis,
)
from app.agents.storyboard.vision import StoryboardReferenceVisionAnalyzer
from app.agents.storyboard.media import ReferenceMediaProcessor
from app.shared.models.script import (
    ScriptBeat,
    ScriptVersion,
)


TEST_VIDEO = Path(
    "tests/agents/storyboard/fixtures/test_reference.mp4"
)


@pytest.mark.asyncio
@pytest.mark.skipif(
    not TEST_VIDEO.exists(),
    reason="Test video fixture not available",
)
async def test_storyboard_end_to_end(tmp_path):

    # ---------------------------------------------------------
    # 1. Create a realistic script
    # ---------------------------------------------------------

    script = ScriptVersion(
        version=1,
        created_at=datetime.now(timezone.utc),
        title="Journey Through Earth",
        hook="Our planet, seen from the darkness of space.",
        full_text=(
            "Our planet, seen from the darkness of space, "
            "reveals a world full of light and life."
        ),
        beats=[
            ScriptBeat(
                beat_id="beat_01",
                start_time=0.0,
                end_time=10.0,
                text=(
                    "Our planet appears against the darkness "
                    "of space."
                ),
                purpose="Establish the world",
                visual_intent=(
                    "A cinematic view of Earth surrounded "
                    "by deep space."
                ),
                audio_intent=None,
                expression=None,
            ),
            ScriptBeat(
                beat_id="beat_02",
                start_time=10.0,
                end_time=20.0,
                text=(
                    "Lights begin to reveal the cities "
                    "across the night side."
                ),
                purpose="Reveal human presence",
                visual_intent=(
                    "Glowing city lights visible across "
                    "the dark side of Earth."
                ),
                audio_intent=None,
                expression=None,
            ),
            ScriptBeat(
                beat_id="beat_03",
                start_time=20.0,
                end_time=30.0,
                text=(
                    "The planet slowly turns beneath "
                    "the quiet darkness."
                ),
                purpose="Closing",
                visual_intent=(
                    "Slow planetary movement with a calm "
                    "and expansive cinematic feeling."
                ),
                audio_intent=None,
                expression=None,
            ),
        ],
    )

    # ---------------------------------------------------------
    # 2. Process reference video
    # ---------------------------------------------------------

    media_processor = ReferenceMediaProcessor(
        output_root=str(
            tmp_path / "storyboard"
        )
    )

    media = media_processor.process(
        source_url="https://example.com/test-reference",
        local_path=str(TEST_VIDEO),
        reference_id="e2e_reference",
    )

    print("\n=== MEDIA ===")
    print(media)

    assert media.error is None
    assert media.processed_path is not None
    assert media.frames

    # ---------------------------------------------------------
    # 3. Analyze extracted frames with Gemini Vision
    # ---------------------------------------------------------

    vision = StoryboardReferenceVisionAnalyzer()

    analyses = await vision.analyze_frames(
        frames=media.frames,
        reference_url=media.source_url,
    )

    print("\n=== FRAME ANALYSES ===")

    for analysis in analyses:
        print(analysis)

    assert analyses
    assert all(
        isinstance(
            analysis,
            VisualReferenceAnalysis,
        )
        for analysis in analyses
    )

    # ---------------------------------------------------------
    # 4. Build visual grammar
    # ---------------------------------------------------------

    grammar_builder = VisualGrammarBuilder()

    grammar = grammar_builder.build(
        analyses
    )

    print("\n=== VISUAL GRAMMAR ===")
    print(grammar)

    assert grammar is not None
    assert grammar.summary

    # ---------------------------------------------------------
    # 5. Generate the actual storyboard
    # ---------------------------------------------------------

    storyboard_agent = StoryboardAgent()

    shot_plan = storyboard_agent.generate(
        script=script,
        visual_references=analyses,
        visual_grammar=grammar,
    )

    # ---------------------------------------------------------
    # 6. Validate the generated ShotPlan
    # ---------------------------------------------------------

    assert shot_plan is not None
    assert shot_plan.shots

    assert len(shot_plan.shots) >= len(
        script.beats
    )

    beat_ids = {
        beat.beat_id
        for beat in script.beats
    }

    generated_beat_ids = {
        shot.beat_id
        for shot in shot_plan.shots
    }

    assert beat_ids.issubset(
        generated_beat_ids
    )

    # ---------------------------------------------------------
    # 7. Print generated storyboard
    # ---------------------------------------------------------

    print("\n=== GENERATED STORYBOARD ===")

    for shot in shot_plan.shots:

        print(
            f"""
Shot: {shot.shot_id}
Beat: {shot.beat_id}
Time: {shot.start_time:.2f}s - {shot.end_time:.2f}s
Type: {shot.shot_type}
Angle: {shot.camera_angle}
Movement: {shot.camera_movement}
Framing: {shot.framing}
Subject: {shot.subject}
Background: {shot.background}
Lighting: {shot.lighting}
Mood: {shot.mood}
Description: {shot.visual_description}
Colour: {shot.colour_palette}
"""
        )

    print("\n=== STORYBOARD STYLE ===")
    print(shot_plan.visual_style)

    print("\n=== STORYBOARD PALETTE ===")
    print(shot_plan.color_palette)

    print("\n=== STORYBOARD EVIDENCE ===")
    for evidence in shot_plan.evidence:
        print("-", evidence)