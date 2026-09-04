from typing import Optional

from app.agents.storyboard.prompts import (
    SYSTEM_PROMPT,
    build_storyboard_prompt,
)
from app.agents.storyboard.schemas import (
    CreatorStyleContext,
    ProductionConstraints,
    VisualGrammar,
)
from app.shared.models.script import ScriptVersion
from app.shared.models.storyboard import ShotPlan
from app.shared.tools.gemini.client import GeminiClient


class StoryboardAgent:
    """
    Converts a ScriptVersion into a production-ready ShotPlan.

    Optional production, creator-style, and visual-grammar context
    allows the storyboard to adapt to the creator's actual setup
    and established visual identity.
    """

    def __init__(self):
        self.gemini = GeminiClient()

    def generate(
        self,
        script: ScriptVersion,
        production_constraints: Optional[ProductionConstraints] = None,
        creator_style: Optional[CreatorStyleContext] = None,
        visual_grammar: Optional[VisualGrammar] = None,
    ) -> ShotPlan:

        prompt = build_storyboard_prompt(
            script_text=self._serialize_script(script),
            beat_count=len(script.beats),
            production_constraints=self._serialize_production_constraints(
                production_constraints
            ),
            creator_style=self._serialize_creator_style(
                creator_style
            ),
            visual_grammar=self._serialize_visual_grammar(
                visual_grammar
            ),
        )

        response = self.gemini.generate_structured(
            prompt=f"{SYSTEM_PROMPT}\n\n{prompt}",
            response_schema=ShotPlan,
        )

        if not response.shots:
            response = self._build_fallback_storyboard(
                script,
                response,
            )

        self._validate_storyboard(response, script)

        return response

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
""".strip()
            )

        return "\n".join(lines)

    @staticmethod
    def _serialize_production_constraints(
        constraints: Optional[ProductionConstraints],
    ) -> str:
        if constraints is None:
            return "No production constraints were provided."

        return f"""
CAMERAS:
{", ".join(constraints.cameras) or "None specified"}

LENSES:
{", ".join(constraints.lenses) or "None specified"}

LIGHTS:
{", ".join(constraints.lights) or "None specified"}

SUPPORT:
{", ".join(constraints.support) or "None specified"}

LOCATION:
{constraints.location or "Not specified"}

OPERATOR:
{constraints.operator or "Not specified"}

PLATFORM:
{constraints.platform or "Not specified"}

ASPECT RATIO:
{constraints.aspect_ratio or "Not specified"}

BRAND GUIDELINES:
{constraints.brand_guidelines or "None specified"}
""".strip()

    @staticmethod
    def _serialize_creator_style(
        creator_style: Optional[CreatorStyleContext],
    ) -> str:
        if creator_style is None:
            return "No creator style context was provided."

        return f"""
STYLE NOTES:
{creator_style.style_notes or "None specified"}

RECENT THUMBNAILS:
{", ".join(creator_style.recent_thumbnails) or "None provided"}

RECENT STILLS:
{", ".join(creator_style.recent_stills) or "None provided"}
""".strip()

    @staticmethod
    def _serialize_visual_grammar(
        visual_grammar: Optional[VisualGrammar],
    ) -> str:
        if visual_grammar is None:
            return "No reference-derived visual grammar was provided."

        return f"""
FRAMING PATTERNS:
{", ".join(visual_grammar.framing_patterns) or "None"}

CAMERA PATTERNS:
{", ".join(visual_grammar.camera_patterns) or "None"}

MOVEMENT PATTERNS:
{", ".join(visual_grammar.movement_patterns) or "None"}

LIGHTING PATTERNS:
{", ".join(visual_grammar.lighting_patterns) or "None"}

COLOUR PATTERNS:
{", ".join(visual_grammar.colour_patterns) or "None"}

PACING PATTERNS:
{", ".join(visual_grammar.pacing_patterns) or "None"}

TEXT PATTERNS:
{", ".join(visual_grammar.text_patterns) or "None"}

SUMMARY:
{visual_grammar.summary or "None"}

EVIDENCE:
{", ".join(visual_grammar.evidence) or "None"}
""".strip()

    @staticmethod
    def _build_fallback_storyboard(
        script: ScriptVersion,
        partial: ShotPlan,
    ) -> ShotPlan:
        shots = []

        for index, beat in enumerate(script.beats, start=1):
            shots.append(
                {
                    "shot_id": f"shot_{index:02d}",
                    "beat_id": beat.beat_id,
                    "start_time": beat.start_time,
                    "end_time": beat.end_time,
                    "shot_type": "Wide Shot",
                    "camera_angle": "Eye Level",
                    "camera_movement": "Static",
                    "framing": "Wide Framing",
                    "subject": beat.visual_intent or beat.text,
                    "background": (
                        "Environment described by the script beat."
                    ),
                    "lighting": (
                        "Natural cinematic lighting appropriate "
                        "to the scene."
                    ),
                    "visual_description": (
                        beat.visual_intent or beat.text
                    ),
                    "colour_palette": [],
                    "on_screen_text": None,
                    "mood": beat.purpose or "Cinematic",
                    "reference_images": [],
                    "generated_image": None,
                }
            )

        return ShotPlan(
            version=script.version,
            shots=shots,
            visual_style=partial.visual_style,
            color_palette=partial.color_palette,
            evidence=partial.evidence + [
                "Fallback storyboard generated because Gemini "
                "returned no shots."
            ],
        )

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