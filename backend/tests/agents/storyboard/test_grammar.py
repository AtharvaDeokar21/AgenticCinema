import pytest

from app.agents.storyboard.grammar import (
    VisualGrammarBuilder,
)
from app.agents.storyboard.schemas import (
    VisualReferenceAnalysis,
    VisualGrammar,
)


def test_visual_grammar_builder():

    analyses = [
        VisualReferenceAnalysis(
            reference_url="https://example.com/reference-1",
            shot_size="Extreme Wide Shot",
            camera_angle="Eye Level",
            subject_placement="Center frame",
            background="Black outer space",
            lighting="Low-key lighting with atmospheric rim light",
            colour_palette=[
                "Black",
                "Navy Blue",
                "Gold",
                "Cyan",
            ],
            movement="Slow planetary rotation",
            on_screen_text=None,
            mood="Serene, cosmic, awe-inspiring",
        ),
        VisualReferenceAnalysis(
            reference_url="https://example.com/reference-2",
            shot_size="Extreme Wide Shot",
            camera_angle="Eye Level",
            subject_placement="Centered in the frame",
            background="Deep black outer space",
            lighting="Low-key lighting with soft rim light",
            colour_palette=[
                "Black",
                "Dark Blue",
                "Gold",
                "Light Blue",
            ],
            movement="Slow planetary rotation",
            on_screen_text=None,
            mood="Serene, majestic, cosmic",
        ),
    ]

    builder = VisualGrammarBuilder()

    grammar = builder.build(
        analyses=analyses
    )

    print("\n=== VISUAL GRAMMAR ===")

    print("\nFraming:")
    for item in grammar.framing_patterns:
        print("-", item)

    print("\nCamera:")
    for item in grammar.camera_patterns:
        print("-", item)

    print("\nMovement:")
    for item in grammar.movement_patterns:
        print("-", item)

    print("\nLighting:")
    for item in grammar.lighting_patterns:
        print("-", item)

    print("\nColour:")
    for item in grammar.colour_patterns:
        print("-", item)

    print("\nPacing:")
    for item in grammar.pacing_patterns:
        print("-", item)

    print("\nText:")
    for item in grammar.text_patterns:
        print("-", item)

    print("\nSummary:")
    print(grammar.summary)

    print("\nEvidence:")
    for item in grammar.evidence:
        print("-", item)

    assert isinstance(
        grammar,
        VisualGrammar,
    )

    assert grammar.summary is not None

    assert (
        len(grammar.framing_patterns)
        + len(grammar.camera_patterns)
        + len(grammar.lighting_patterns)
        + len(grammar.colour_patterns)
    ) > 0