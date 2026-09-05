from typing import Optional

from app.agents.storyboard.prompts import (
    SYSTEM_PROMPT,
    build_storyboard_prompt,
)
from app.shared.models.storyboard import Shot, ShotPlan
from app.shared.models.script import ScriptVersion
from app.shared.tools.gemini.client import GeminiClient
from app.agents.storyboard.schemas import (
    ProductionConstraints,
    CreatorStyleContext,
    VisualReferenceAnalysis,
    VisualGrammar,
    ProductionAwareStoryboard,
)
from app.agents.storyboard.research import (
    StoryboardReferenceResearcher,
)
from app.agents.storyboard.reference_analyzer import (
    StoryboardReferenceAnalyzer,
)

from app.agents.storyboard.production import (
    StoryboardProductionPlanner,
)

from app.agents.storyboard.adaptation import (
    StoryboardAdaptationPlanner,
)

from app.agents.storyboard.asset_generator import (
    StoryboardAssetGenerator,
)

class StoryboardAgent:
    """
    Converts a ScriptVersion into a production-ready ShotPlan.

    Optional production and creator context can be supplied to make
    the generated storyboard executable within the creator's actual
    setup and consistent with their visual identity.
    """

    def __init__(self):
        self.gemini = GeminiClient()
        self.reference_researcher = StoryboardReferenceResearcher()
        self.reference_analyzer = StoryboardReferenceAnalyzer()
        self.production_planner = StoryboardProductionPlanner()
        self.adaptation_planner = StoryboardAdaptationPlanner()
        self.asset_generator = StoryboardAssetGenerator()

    async def research_references(
        self,
        script: ScriptVersion,
        max_references: int = 10,
    ):
        topic = self._build_reference_topic(script)

        return await self.reference_researcher.research(
            script_text=self._serialize_script(script),
            topic=topic,
            max_references=max_references,
        )

    def plan_production(
        self,
        storyboard: ShotPlan,
        production_constraints: ProductionConstraints,
    ):
        return self.production_planner.plan(
            storyboard=storyboard,
            constraints=production_constraints,
        )
    
    def adapt_storyboard(
        self,
        production_storyboard: ProductionAwareStoryboard,
        production_constraints: ProductionConstraints,
    ):
        return self.adaptation_planner.adapt(
            production_storyboard=production_storyboard,
            constraints=production_constraints,
        )
    
    def generate(
        self,
        script: ScriptVersion,
        production_constraints: ProductionConstraints | None = None,
        creator_style: CreatorStyleContext | None = None,
        visual_references: list[VisualReferenceAnalysis] | None = None,
        visual_grammar: VisualGrammar | None = None,
    ) -> ShotPlan:

        prompt = build_storyboard_prompt(
            self._serialize_script(script),
            len(script.beats),
            self._serialize_production_constraints(
                production_constraints
            ),
            self._serialize_creator_style(
                creator_style
            ),
            self._serialize_visual_references(
                visual_references
            ),
            self._serialize_visual_grammar(
                visual_grammar
            ),
        )

        response = self.gemini.generate_structured(
            prompt=f"{SYSTEM_PROMPT}\n\n{prompt}",
            response_schema=ShotPlan,
        )

        if not response.shots:
            response = self._fallback_storyboard(
                script,
                production_constraints,
            )

        self._validate_storyboard(response, script)

        return response

    async def generate_full_pipeline(
        self,
        script: ScriptVersion,
        production_constraints: ProductionConstraints,
        *,
        max_references: int = 10,
        generate_thumbnails: bool = True,
        generate_shots: bool = True,
        generate_concept_art: bool = False,
        project_id: str = "storyboard_demo",
    ):
        """
        Execute the complete demo storyboard pipeline.

        Script
            -> Parallel Search
            -> Parallel Extract
            -> media/reference analysis
            -> visual grammar
            -> storyboard
            -> production planning
            -> adaptation
            -> real visual asset generation
        """

        research = await self.research_references(
            script=script,
            max_references=max_references,
        )

        storyboard = self.generate(
            script=script,
            production_constraints=production_constraints,
        )

        production = self.plan_production(
            storyboard=storyboard,
            production_constraints=production_constraints,
        )

        adapted = self.adapt_storyboard(
            production_storyboard=production,
            production_constraints=production_constraints,
        )

        assets = self.asset_generator.generate(
            storyboard=adapted.storyboard,
            production=ProductionAwareStoryboard(
                storyboard=adapted.storyboard,
                production_plans=production.production_plans,
                overall_issues=production.overall_issues,
            ),
            project_id=project_id,
            generate_shots=generate_shots,
            generate_thumbnails=generate_thumbnails,
            generate_concept_art=generate_concept_art,
        )

        return {
            "research": research,
            "storyboard": storyboard,
            "production": production,
            "adapted": adapted,
            "assets": assets,
        }

    @staticmethod
    def _serialize_script(script: ScriptVersion) -> str:
        lines = [
            f"Title: {script.title or 'Untitled'}",
            f"Hook: {script.hook or ''}",
            f"Full Text: {script.full_text}",
            "",
            "SCRIPT BEATS:",
        ]

        for beat in script.beats:
            lines.append(
                f"""
Beat ID: {beat.beat_id}
Time: {beat.start_time:.2f}s - {beat.end_time:.2f}s
Text: {beat.text}
Purpose: {beat.purpose or ''}
Visual Intent: {beat.visual_intent or ''}
Audio Intent: {beat.audio_intent or ''}
Expression: {beat.expression or ''}
""".strip()
            )

        return "\n".join(lines)

    @staticmethod
    def _serialize_production_constraints(
        constraints: ProductionConstraints | None,
    ) -> str:

        if constraints is None:
            return ""

        lines = []

        if constraints.cameras:
            lines.append(
                f"Cameras: {', '.join(constraints.cameras)}"
            )

        if constraints.lenses:
            lines.append(
                f"Lenses: {', '.join(constraints.lenses)}"
            )

        if constraints.lights:
            lines.append(
                f"Lights: {', '.join(constraints.lights)}"
            )

        if constraints.support:
            lines.append(
                f"Support: {', '.join(constraints.support)}"
            )

        if constraints.location:
            lines.append(
                f"Location: {constraints.location}"
            )

        if constraints.operator:
            lines.append(
                f"Camera operator: {constraints.operator}"
            )

        if constraints.platform:
            lines.append(
                f"Platform: {constraints.platform}"
            )

        if constraints.aspect_ratio:
            lines.append(
                f"Aspect ratio: {constraints.aspect_ratio}"
            )

        if constraints.brand_guidelines:
            lines.append(
                f"Brand guidelines: {constraints.brand_guidelines}"
            )

        if constraints.constraints:
            lines.append(
                "Additional constraints: "
                + "; ".join(constraints.constraints)
            )

        return "\n".join(lines)

    @staticmethod
    def _serialize_creator_style(
        creator_style: CreatorStyleContext | None,
    ) -> str:

        if creator_style is None:
            return ""

        lines = []

        if creator_style.style_notes:
            lines.append(
                f"Style notes: {creator_style.style_notes}"
            )

        if creator_style.recent_thumbnails:
            lines.append(
                "Recent thumbnails available: "
                f"{len(creator_style.recent_thumbnails)}"
            )

        if creator_style.recent_stills:
            lines.append(
                "Recent stills available: "
                f"{len(creator_style.recent_stills)}"
            )

        return "\n".join(lines)

    @staticmethod
    def _serialize_visual_grammar(
        visual_grammar: Optional[VisualGrammar],
    ) -> str:
        if visual_grammar is None:
            return "No reference-derived visual grammar was provided."

        return f"""
FRAMING PATTERNS:
{chr(10).join(visual_grammar.framing_patterns) or "None"}

CAMERA PATTERNS:
{chr(10).join(visual_grammar.camera_patterns) or "None"}

MOVEMENT PATTERNS:
{chr(10).join(visual_grammar.movement_patterns) or "None"}

LIGHTING PATTERNS:
{chr(10).join(visual_grammar.lighting_patterns) or "None"}

COLOUR PATTERNS:
{chr(10).join(visual_grammar.colour_patterns) or "None"}

PACING PATTERNS:
{chr(10).join(visual_grammar.pacing_patterns) or "None"}

TEXT PATTERNS:
{chr(10).join(visual_grammar.text_patterns) or "None"}

SUMMARY:
{visual_grammar.summary or "None"}

EVIDENCE:
{chr(10).join(visual_grammar.evidence) or "None"}
""".strip()

    @staticmethod
    def _validate_storyboard(
        storyboard: ShotPlan,
        script: ScriptVersion,
    ) -> None:

        if not storyboard.shots:
            raise ValueError(
                "Storyboard generation returned no shots."
            )

        beat_map = {
            beat.beat_id: beat
            for beat in script.beats
        }

        covered_beats = set()

        for shot in storyboard.shots:
            if shot.beat_id not in beat_map:
                raise ValueError(
                    f"Storyboard shot '{shot.shot_id}' references "
                    f"unknown beat '{shot.beat_id}'."
                )

            beat = beat_map[shot.beat_id]

            if shot.start_time < beat.start_time:
                raise ValueError(
                    f"Shot '{shot.shot_id}' starts before "
                    f"its beat '{beat.beat_id}'."
                )

            if shot.end_time > beat.end_time:
                raise ValueError(
                    f"Shot '{shot.shot_id}' ends after "
                    f"its beat '{beat.beat_id}'."
                )

            if shot.start_time >= shot.end_time:
                raise ValueError(
                    f"Shot '{shot.shot_id}' has invalid timing."
                )

            covered_beats.add(shot.beat_id)

        missing_beats = set(beat_map) - covered_beats

        if missing_beats:
            raise ValueError(
                "Storyboard is missing visual coverage for beats: "
                + ", ".join(sorted(missing_beats))
            )

    @staticmethod
    def _fallback_storyboard(
        script: ScriptVersion,
        production_constraints: ProductionConstraints | None = None,
    ) -> ShotPlan:

        shots = []

        for index, beat in enumerate(script.beats, start=1):

            visual_intent = (
                beat.visual_intent
                or beat.text
                or "Scene described by script."
            )

            duration = beat.end_time - beat.start_time

            shot_type = "Medium Shot"
            camera_angle = "Eye Level"
            camera_movement = "Static"
            framing = "Centered"

            if duration >= 8:
                camera_movement = "Slow Tracking"

            intent = visual_intent.lower()

            if any(
                word in intent
                for word in [
                    "street",
                    "landscape",
                    "city",
                    "coast",
                    "skyline",
                ]
            ):
                shot_type = "Wide Shot"
                framing = "Wide Framing"

            if any(
                word in intent
                for word in [
                    "close",
                    "face",
                    "detail",
                    "hands",
                ]
            ):
                shot_type = "Close-up"
                framing = "Tight Framing"

            if any(
                word in intent
                for word in [
                    "sunset",
                    "golden hour",
                    "sunrise",
                ]
            ):
                lighting = "Natural golden-hour lighting"
            else:
                lighting = "Natural lighting appropriate to the scene"

            shots.append(
                Shot(
                    shot_id=f"shot_{index:02d}",
                    beat_id=beat.beat_id,
                    start_time=beat.start_time,
                    end_time=beat.end_time,
                    shot_type=shot_type,
                    camera_angle=camera_angle,
                    camera_movement=camera_movement,
                    framing=framing,
                    subject=beat.text,
                    background=visual_intent,
                    lighting=lighting,
                    visual_description=visual_intent,
                    colour_palette=[],
                    on_screen_text=None,
                    mood=beat.purpose,
                    reference_images=[],
                    generated_image=None,
                )
            )

        return ShotPlan(
            version=script.version,
            shots=shots,
            visual_style=(
                "Natural cinematic documentary style guided by "
                "the script's visual intent."
            ),
            color_palette=(
                "Natural scene-appropriate colours with "
                "consistent visual continuity."
            ),
            evidence=[
                f"Fallback storyboard generated from script beat "
                f"{beat.beat_id}."
                for beat in script.beats
            ],
        )

    @staticmethod
    def _serialize_visual_references(
        references: list[VisualReferenceAnalysis] | None,
    ) -> str:

        if not references:
            return "No visual reference analyses were provided."

        sections = []

        for index, reference in enumerate(references, start=1):
            sections.append(
                f"""
    REFERENCE {index}
    URL: {reference.reference_url or "Unknown"}

    Shot size: {reference.shot_size or "Unknown"}
    Camera angle: {reference.camera_angle or "Unknown"}
    Subject placement: {reference.subject_placement or "Unknown"}
    Background: {reference.background or "Unknown"}
    Lighting: {reference.lighting or "Unknown"}
    Colour palette: {", ".join(reference.colour_palette) or "Unknown"}
    Movement: {reference.movement or "Unknown"}
    On-screen text: {reference.on_screen_text or "None"}
    Mood: {reference.mood or "Unknown"}
    """.strip()
            )

        return "\n\n".join(sections)

    @staticmethod
    def _build_reference_topic(script: ScriptVersion) -> str:
        if script.title:
            return script.title

        visual_intents = [
            beat.visual_intent
            for beat in script.beats
            if beat.visual_intent
        ]

        if visual_intents:
            return visual_intents[0]

        return script.full_text[:300]