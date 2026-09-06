from typing import Optional

from app.agents.storyboard.schemas import (
    ProductionConstraints,
    ProductionAwareStoryboard,
    ShotAdaptation,
    AdaptedStoryboard,
)
from app.shared.models.storyboard import ShotPlan
from app.shared.tools.gemini.client import GeminiClient


class StoryboardAdaptationPlanner:
    """
    Adapts storyboard shots to realistic production constraints.

    Phase 5 responsibilities:

        1. Inspect the generated storyboard.
        2. Inspect production feasibility information.
        3. Identify shots that require adaptation.
        4. Preserve creative intent wherever possible.
        5. Modify execution rather than unnecessarily changing
           the creative concept.
        6. Return a final executable storyboard.

    The planner should NOT redesign the entire storyboard.
    """

    def __init__(
        self,
        gemini: Optional[GeminiClient] = None,
    ):
        self.gemini = gemini or GeminiClient()

    def adapt(
        self,
        production_storyboard: ProductionAwareStoryboard,
        constraints: ProductionConstraints,
    ) -> AdaptedStoryboard:

        prompt = self._build_prompt(
            production_storyboard=production_storyboard,
            constraints=constraints,
        )

        response = self.gemini.generate_structured(
            prompt=prompt,
            response_schema=AdaptedStoryboard,
        )

        return self._validate_result(
            response=response,
            original_storyboard=production_storyboard.storyboard,
        )

    @staticmethod
    def _build_prompt(
        production_storyboard: ProductionAwareStoryboard,
        constraints: ProductionConstraints,
    ) -> str:

        storyboard_text = (
            StoryboardAdaptationPlanner
            ._serialize_storyboard(
                production_storyboard.storyboard
            )
        )

        production_text = (
            StoryboardAdaptationPlanner
            ._serialize_production_plans(
                production_storyboard
            )
        )

        constraints_text = (
            StoryboardAdaptationPlanner
            ._serialize_constraints(
                constraints
            )
        )

        return f"""
You are a cinematic storyboard adaptation system.

Your task is to adapt an existing storyboard so that it can
actually be produced using the creator's available equipment,
location, and production constraints.

CORE PRINCIPLE:

PRESERVE CREATIVE INTENT.
CHANGE EXECUTION ONLY WHEN NECESSARY.

Do NOT redesign the story.

Do NOT change the script's meaning.

Do NOT arbitrarily change shot timing.

Do NOT introduce expensive equipment that is unavailable.

Do NOT remove a shot simply because it is inconvenient.

Instead, find the closest practical production method.

EXAMPLES:

If the storyboard requires:

    Slow gimbal push-in

but only a tripod is available:

    Adapt to a static shot with a controlled digital
    push-in in post-production, if appropriate.

If the storyboard requires:

    Tracking shot

but no moving camera support exists:

    Consider a static composition, reframing, or
    post-production movement when it preserves the intent.

If a lighting setup is unavailable:

    Recreate the visual character using available lights
    or natural light.

If a specific lens is unavailable:

    Select the closest available lens and compensate
    through camera position or framing.

ONLY ADAPT WHEN NECESSARY.

If a shot is already feasible, preserve it.

For every shot, determine whether an adaptation is required.

For adapted shots, record:

1. shot_id

2. original_movement

3. adapted_movement

4. original_camera

5. adapted_camera

6. original_lens

7. adapted_lens

8. changes

9. creative_intent_preserved

10. reason

If no meaningful adaptation is required, still provide an
adaptation entry with an empty `changes` list and explain
that the original execution is feasible.

The final `storyboard` MUST represent the adapted,
production-ready execution.

Do not change shot IDs, beat IDs, or shot timing.

PRODUCTION CONSTRAINTS

{constraints_text}

PRODUCTION ANALYSIS

{production_text}

ORIGINAL STORYBOARD

{storyboard_text}

FINAL FEASIBILITY CHECK:

For every shot, verify:

1. Camera exists in available cameras.
2. Lens exists in available lenses or has a practical equivalent.
3. Lighting can be created with available lights.
4. Support exists.
5. Camera movement can be performed by the stated operator.
6. Location requirements are compatible with the stated location.

If any condition fails, adapt the execution.

The final storyboard must never contain an unresolved production
constraint violation.

Return a structured AdaptedStoryboard.
""".strip()

    @staticmethod
    def _serialize_constraints(
        constraints: ProductionConstraints,
    ) -> str:

        return f"""
CAMERAS:
{StoryboardAdaptationPlanner._bullet_list(
    constraints.cameras
)}

LENSES:
{StoryboardAdaptationPlanner._bullet_list(
    constraints.lenses
)}

LIGHTS:
{StoryboardAdaptationPlanner._bullet_list(
    constraints.lights
)}

SUPPORT:
{StoryboardAdaptationPlanner._bullet_list(
    constraints.support
)}

LOCATION:
{constraints.location or "Not specified"}

OPERATOR:
{constraints.operator or "Not specified"}

PLATFORM:
{constraints.platform or "Not specified"}

ASPECT RATIO:
{constraints.aspect_ratio or "Not specified"}

BRAND GUIDELINES:
{constraints.brand_guidelines or "None"}

ADDITIONAL CONSTRAINTS:
{StoryboardAdaptationPlanner._bullet_list(
    constraints.constraints
)}
""".strip()

    @staticmethod
    def _serialize_production_plans(
        production_storyboard: ProductionAwareStoryboard,
    ) -> str:

        sections = []

        for plan in production_storyboard.production_plans:

            sections.append(
                f"""
SHOT: {plan.shot_id}

Camera:
{plan.camera or "Not specified"}

Lens:
{plan.lens or "Not specified"}

Support:
{plan.support or "Not specified"}

Lighting:
{plan.lighting_setup or "Not specified"}

Location requirements:
{StoryboardAdaptationPlanner._bullet_list(
    plan.location_requirements
)}

Equipment required:
{StoryboardAdaptationPlanner._bullet_list(
    plan.equipment_required
)}

Feasibility:
{plan.feasibility}

Issues:
{StoryboardAdaptationPlanner._bullet_list(
    plan.issues
)}

Notes:
{plan.notes or "None"}
""".strip()
            )

        if not sections:
            return "No production plans were provided."

        return "\n\n".join(sections)

    @staticmethod
    def _serialize_storyboard(
        storyboard: ShotPlan,
    ) -> str:

        sections = []

        for shot in storyboard.shots:

            sections.append(
                f"""
SHOT ID: {shot.shot_id}
BEAT ID: {shot.beat_id}

TIME:
{shot.start_time:.2f}s - {shot.end_time:.2f}s

SHOT TYPE:
{shot.shot_type}

CAMERA ANGLE:
{shot.camera_angle}

CAMERA MOVEMENT:
{shot.camera_movement}

FRAMING:
{shot.framing}

SUBJECT:
{shot.subject}

BACKGROUND:
{shot.background}

LIGHTING:
{shot.lighting}

VISUAL DESCRIPTION:
{shot.visual_description}

COLOUR PALETTE:
{", ".join(shot.colour_palette) or "None"}

MOOD:
{shot.mood or "None"}

ON-SCREEN TEXT:
{shot.on_screen_text or "None"}
""".strip()
            )

        return "\n\n".join(sections)

    @staticmethod
    def _bullet_list(
        values: list[str],
    ) -> str:

        if not values:
            return "- None"

        return "\n".join(
            f"- {value}"
            for value in values
        )

    @staticmethod
    def _validate_result(
        response: AdaptedStoryboard,
        original_storyboard: ShotPlan,
    ) -> AdaptedStoryboard:

        expected_ids = {
            shot.shot_id
            for shot in original_storyboard.shots
        }

        actual_ids = {
            shot.shot_id
            for shot in response.storyboard.shots
        }

        missing = expected_ids - actual_ids

        if missing:
            raise ValueError(
                "Adapted storyboard is missing shots: "
                + ", ".join(sorted(missing))
            )

        unknown = actual_ids - expected_ids

        if unknown:
            raise ValueError(
                "Adapted storyboard contains unknown shots: "
                + ", ".join(sorted(unknown))
            )

        # Preserve the original storyboard object if Gemini
        # somehow returns an empty adaptation.
        if not response.storyboard.shots:
            response.storyboard = original_storyboard

        return response