from typing import Optional

from app.agents.storyboard.schemas import (
    ProductionConstraints,
    ShotProductionPlan,
    ProductionAwareStoryboard,
)
from app.shared.models.storyboard import ShotPlan
from app.shared.tools.gemini.client import GeminiClient


class StoryboardProductionPlanner:
    """
    Converts a generated ShotPlan into a production-aware plan.

    Phase 4 responsibilities:
        1. Inspect every storyboard shot.
        2. Compare shot requirements against available production
           constraints.
        3. Identify required equipment and setup.
        4. Identify feasibility issues.
        5. Preserve the original storyboard while adding
           production planning information.

    This class does NOT regenerate the storyboard.
    """

    def __init__(
        self,
        gemini: Optional[GeminiClient] = None,
    ):
        self.gemini = gemini or GeminiClient()

    def plan(
        self,
        storyboard: ShotPlan,
        constraints: ProductionConstraints,
    ) -> ProductionAwareStoryboard:

        prompt = self._build_prompt(
            storyboard=storyboard,
            constraints=constraints,
        )

        response = self.gemini.generate_structured(
            prompt=prompt,
            response_schema=ProductionAwareStoryboard,
        )

        return self._validate_result(
            response=response,
            storyboard=storyboard,
        )

    @staticmethod
    def _build_prompt(
        storyboard: ShotPlan,
        constraints: ProductionConstraints,
    ) -> str:

        storyboard_text = (
            StoryboardProductionPlanner
            ._serialize_storyboard(storyboard)
        )

        constraints_text = (
            StoryboardProductionPlanner
            ._serialize_constraints(constraints)
        )

        return f"""
You are a production planning system for a cinematic
storyboard generation pipeline.

Your task is to convert an existing storyboard into a
REALISTIC production plan.

IMPORTANT:

- Do NOT rewrite the storyboard.
- Do NOT change shot timing.
- Do NOT invent equipment that the creator does not have
  unless absolutely necessary.
- Prefer available equipment from the production constraints.
- If a requested shot is difficult or impossible with the
  available setup, clearly identify the issue.
- Suggest the closest practical production approach.
- Keep the original creative intent intact.
- Be conservative when determining feasibility.
- Do not assume equipment is available unless explicitly listed.

For EVERY storyboard shot, create exactly one
ShotProductionPlan.

The production plan should determine:

1. Camera
   Select an available camera appropriate for the shot.

2. Lens
   Select an available lens appropriate for framing.

3. Support
   Select an available support system such as tripod,
   handheld, gimbal, slider, etc.

4. Lighting setup
   Describe how the available lights should be positioned
   or used.

5. Location requirements
   Identify practical location requirements.

6. Equipment required
   List equipment actually needed to execute the shot.

7. Feasibility
   Classify the shot as one of:
   - "high"
   - "medium"
   - "low"

8. Issues
   List any practical production limitations.

9. Notes
   Add concise execution guidance when useful.

FEASIBILITY GUIDELINES

high:
    The shot can realistically be produced using the
    supplied equipment and constraints.

medium:
    The shot is achievable but requires compromises,
    careful setup, or additional effort.

low:
    The shot cannot realistically be produced with the
    available setup without significant additional
    equipment, location access, or technical capability.

PRODUCTION CONSTRAINTS

{constraints_text}

EXISTING STORYBOARD

{storyboard_text}

Return a ProductionAwareStoryboard using the provided
structured schema.

The `storyboard` field MUST preserve the existing storyboard
content and MUST NOT be creatively rewritten.
""".strip()

    @staticmethod
    def _serialize_constraints(
        constraints: ProductionConstraints,
    ) -> str:

        sections = []

        sections.append(
            "CAMERAS:\n"
            + (
                "\n".join(
                    f"- {camera}"
                    for camera in constraints.cameras
                )
                or "- None specified"
            )
        )

        sections.append(
            "LENSES:\n"
            + (
                "\n".join(
                    f"- {lens}"
                    for lens in constraints.lenses
                )
                or "- None specified"
            )
        )

        sections.append(
            "LIGHTS:\n"
            + (
                "\n".join(
                    f"- {light}"
                    for light in constraints.lights
                )
                or "- None specified"
            )
        )

        sections.append(
            "SUPPORT:\n"
            + (
                "\n".join(
                    f"- {support}"
                    for support in constraints.support
                )
                or "- None specified"
            )
        )

        sections.append(
            f"LOCATION:\n"
            f"- {constraints.location or 'Not specified'}"
        )

        sections.append(
            f"OPERATOR:\n"
            f"- {constraints.operator or 'Not specified'}"
        )

        sections.append(
            f"PLATFORM:\n"
            f"- {constraints.platform or 'Not specified'}"
        )

        sections.append(
            f"ASPECT RATIO:\n"
            f"- {constraints.aspect_ratio or 'Not specified'}"
        )

        sections.append(
            f"BRAND GUIDELINES:\n"
            f"- {constraints.brand_guidelines or 'None'}"
        )

        sections.append(
            "ADDITIONAL CONSTRAINTS:\n"
            + (
                "\n".join(
                    f"- {constraint}"
                    for constraint in constraints.constraints
                )
                or "- None"
            )
        )

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
TIME: {shot.start_time:.2f}s - {shot.end_time:.2f}s

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
    def _validate_result(
        response: ProductionAwareStoryboard,
        storyboard: ShotPlan,
    ) -> ProductionAwareStoryboard:

        expected_shot_ids = {
            shot.shot_id
            for shot in storyboard.shots
        }

        actual_shot_ids = {
            plan.shot_id
            for plan in response.production_plans
        }

        missing = expected_shot_ids - actual_shot_ids

        if missing:
            raise ValueError(
                "Production planning is missing shots: "
                + ", ".join(sorted(missing))
            )

        unknown = actual_shot_ids - expected_shot_ids

        if unknown:
            raise ValueError(
                "Production planning contains unknown shots: "
                + ", ".join(sorted(unknown))
            )

        if response.storyboard is None:
            response.storyboard = storyboard

        return response