from datetime import datetime, timezone

from app.agents.storyboard.agent import StoryboardAgent
from app.shared.models.script import ScriptBeat, ScriptVersion
from app.agents.storyboard.schemas import CreatorStyleContext, ProductionConstraints, VisualReferenceAnalysis, VisualGrammar


def test_storyboard_agent():
    script = ScriptVersion(
        version=1,
        created_at=datetime.now(timezone.utc),
        title="Photographer of Mumbai",
        hook="A photographer discovers Mumbai through the lens.",
        full_text=(
            "A photographer walks through Mumbai, capturing the city "
            "as day turns into night."
        ),
        beats=[
            ScriptBeat(
                beat_id="beat_01",
                start_time=0.0,
                end_time=10.0,
                text="The photographer begins exploring Mumbai.",
                purpose="Introduction",
                visual_intent=(
                    "Early morning Mumbai streets with the photographer "
                    "walking with a camera."
                ),
                audio_intent="Soft morning city ambience.",
            ),
            ScriptBeat(
                beat_id="beat_02",
                start_time=10.0,
                end_time=25.0,
                text="The photographer captures the energy of the city.",
                purpose="Discovery",
                visual_intent=(
                    "Busy Mumbai streets, local trains, markets and "
                    "people moving through the city."
                ),
                audio_intent="Increasing city ambience.",
            ),
            ScriptBeat(
                beat_id="beat_03",
                start_time=25.0,
                end_time=40.0,
                text="The photographer reaches Marine Drive at sunset.",
                purpose="Climax",
                visual_intent=(
                    "Marine Drive at golden hour with the Arabian Sea "
                    "and Mumbai skyline."
                ),
                audio_intent="Emotional cinematic music.",
            ),
        ],
        status="draft",
    )

    agent = StoryboardAgent()

    result = agent.generate(script)

    print("\n=== STORYBOARD ===")
    print(result)

    assert result.version == 1
    assert len(result.shots) > 0
    assert result.visual_style
    assert result.color_palette

    beat_ids = {beat.beat_id for beat in script.beats}

    for shot in result.shots:
        assert shot.beat_id in beat_ids
        assert shot.end_time > shot.start_time

    print("\n=== SHOTS ===")
    for shot in result.shots:
        print(
            f"{shot.shot_id} | "
            f"{shot.beat_id} | "
            f"{shot.start_time}-{shot.end_time} | "
            f"{shot.shot_type}"
        )

def test_storyboard_agent_with_production_constraints():

    script = ScriptVersion(
        version=1,
        created_at=datetime.now(timezone.utc),
        title="Photographer of Mumbai",
        hook="A photographer discovers Mumbai through the lens.",
        full_text=(
            "A photographer walks through Mumbai, capturing the city "
            "as day turns into night."
        ),
        beats=[
            ScriptBeat(
                beat_id="beat_01",
                start_time=0.0,
                end_time=10.0,
                text="The photographer begins exploring Mumbai.",
                purpose="Introduction",
                visual_intent=(
                    "Early morning Mumbai streets with the photographer "
                    "walking with a camera."
                ),
                audio_intent="Soft morning city ambience.",
            ),
            ScriptBeat(
                beat_id="beat_02",
                start_time=10.0,
                end_time=25.0,
                text="The photographer captures the energy of the city.",
                purpose="Discovery",
                visual_intent=(
                    "Busy Mumbai streets, local trains, markets and "
                    "people moving through the city."
                ),
                audio_intent="Increasing city ambience.",
            ),
            ScriptBeat(
                beat_id="beat_03",
                start_time=25.0,
                end_time=40.0,
                text="The photographer reaches Marine Drive at sunset.",
                purpose="Climax",
                visual_intent=(
                    "Marine Drive at golden hour with the Arabian Sea "
                    "and Mumbai skyline."
                ),
                audio_intent="Emotional cinematic music.",
            ),
        ],
        status="draft",
    )

    constraints = ProductionConstraints(
        cameras=["iPhone 15"],
        lenses=["1x", "2x"],
        lights=["Natural light"],
        support=["Handheld"],
        location="Mumbai streets and Marine Drive",
        operator="Solo creator",
        platform="YouTube",
        aspect_ratio="16:9",
    )

    creator_style = CreatorStyleContext(
        style_notes=(
            "Authentic documentary photography with natural lighting "
            "and minimal staged compositions."
        )
    )

    agent = StoryboardAgent()

    result = agent.generate(
        script,
        production_constraints=constraints,
        creator_style=creator_style,
    )

    assert result.version == 1
    assert result.shots

    beat_ids = {
        beat.beat_id
        for beat in script.beats
    }

    for shot in result.shots:
        assert shot.beat_id in beat_ids
        assert shot.end_time > shot.start_time

def test_storyboard_agent_with_visual_grammar():

    script = ScriptVersion(
        version=1,
        created_at=datetime.now(timezone.utc),
        title="Photographer of Mumbai",
        hook="A photographer discovers Mumbai through the lens.",
        full_text=(
            "A photographer walks through Mumbai, capturing the city "
            "as day turns into night."
        ),
        beats=[
            ScriptBeat(
                beat_id="beat_01",
                start_time=0.0,
                end_time=10.0,
                text="The photographer begins exploring Mumbai.",
                purpose="Introduction",
                visual_intent=(
                    "Early morning Mumbai streets with the photographer "
                    "walking with a camera."
                ),
                audio_intent="Soft morning city ambience.",
            ),
            ScriptBeat(
                beat_id="beat_02",
                start_time=10.0,
                end_time=25.0,
                text="The photographer captures the energy of the city.",
                purpose="Discovery",
                visual_intent=(
                    "Busy Mumbai streets, local trains, markets and "
                    "people moving through the city."
                ),
                audio_intent="Increasing city ambience.",
            ),
            ScriptBeat(
                beat_id="beat_03",
                start_time=25.0,
                end_time=40.0,
                text="The photographer reaches Marine Drive at sunset.",
                purpose="Climax",
                visual_intent=(
                    "Marine Drive at golden hour with the Arabian Sea "
                    "and Mumbai skyline."
                ),
                audio_intent="Emotional cinematic music.",
            ),
        ],
        status="draft",
    )

    constraints = ProductionConstraints(
        cameras=["iPhone 15"],
        lenses=["1x", "2x"],
        lights=["Natural light"],
        support=["Handheld"],
        location="Mumbai streets and Marine Drive",
        operator="Solo creator",
        platform="YouTube",
        aspect_ratio="16:9",
    )

    creator_style = CreatorStyleContext(
        style_notes=(
            "Authentic documentary photography with natural lighting "
            "and minimal staged compositions."
        )
    )

    references = [
        VisualReferenceAnalysis(
            reference_url="https://example.com/reference-video",
            shot_size="Medium close-up",
            camera_angle="Eye level",
            subject_placement="Upper third",
            background="Environment visible with moderate separation",
            lighting="Natural soft key light",
            colour_palette=[
                "#1B2A3A",
                "#E8703A",
                "#F2E8D5",
            ],
            movement="Mostly static with occasional slow push",
            on_screen_text="Upper third",
            mood="Direct and observational",
        ),
    ]

    grammar = VisualGrammar(
        framing_patterns=[
            "Medium close-ups dominate speaking and hook moments.",
            "Wide establishing shots introduce locations.",
        ],
        camera_patterns=[
            "Mostly eye-level camera placement.",
        ],
        movement_patterns=[
            "Static framing dominates.",
            "Slow push-ins are used for emphasis.",
        ],
        lighting_patterns=[
            "Natural soft key lighting.",
        ],
        colour_patterns=[
            "Cool environmental tones with warm accents.",
        ],
        pacing_patterns=[
            "Shots generally hold for several seconds.",
        ],
        text_patterns=[
            "Short text appears in the upper third.",
        ],
        summary=(
            "Observational documentary grammar using eye-level framing, "
            "natural light, restrained movement, and warm accent colours."
        ),
        evidence=[
            "Observed across supplied reference analyses."
        ],
    )

    agent = StoryboardAgent()

    result = agent.generate(
        script,
        production_constraints=constraints,
        creator_style=creator_style,
        visual_references=references,
        visual_grammar=grammar,
    )

    assert result.version == 1
    assert result.shots
    assert len(result.shots) >= len(script.beats)
    assert result.visual_style
    assert result.color_palette

    beat_ids = {
        beat.beat_id
        for beat in script.beats
    }

    for shot in result.shots:
        assert shot.beat_id in beat_ids
        assert shot.end_time > shot.start_time
        assert shot.start_time >= next(
            beat.start_time
            for beat in script.beats
            if beat.beat_id == shot.beat_id
        )
        assert shot.end_time <= next(
            beat.end_time
            for beat in script.beats
            if beat.beat_id == shot.beat_id
        )

def test_visual_reference_serialization():

    references = [
        VisualReferenceAnalysis(
            reference_url="https://example.com/reference",
            shot_size="Medium close-up",
            camera_angle="Eye level",
            subject_placement="Upper third",
            background="Environment visible",
            lighting="Natural soft key light",
            colour_palette=["#1B2A3A", "#E8703A"],
            movement="Slow push",
            on_screen_text="Upper third",
            mood="Observational",
        )
    ]

    result = StoryboardAgent._serialize_visual_references(
        references
    )

    assert "REFERENCE 1" in result
    assert "Medium close-up" in result
    assert "Eye level" in result
    assert "Upper third" in result
    assert "Natural soft key light" in result
    assert "#1B2A3A" in result
    assert "Slow push" in result
    assert "Observational" in result

def test_visual_grammar_serialization():

    grammar = VisualGrammar(
        framing_patterns=[
            "Wide establishing shots introduce locations."
        ],
        camera_patterns=[
            "Mostly eye-level camera placement."
        ],
        movement_patterns=[
            "Static framing dominates."
        ],
        lighting_patterns=[
            "Natural soft key lighting."
        ],
        colour_patterns=[
            "Cool tones with warm accents."
        ],
        pacing_patterns=[
            "Shots generally hold for several seconds."
        ],
        text_patterns=[
            "Short text appears in the upper third."
        ],
        summary=(
            "Observational documentary grammar."
        ),
        evidence=[
            "Observed across supplied references."
        ],
    )

    result = StoryboardAgent._serialize_visual_grammar(
        grammar
    )

    assert "Wide establishing shots" in result
    assert "eye-level camera" in result
    assert "Static framing" in result
    assert "Natural soft key lighting" in result
    assert "Cool tones with warm accents" in result
    assert "Shots generally hold" in result
    assert "upper third" in result
    assert "Observational documentary grammar" in result
    assert "Observed across supplied references" in result