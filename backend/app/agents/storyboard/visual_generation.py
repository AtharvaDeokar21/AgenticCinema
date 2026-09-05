from typing import Optional

from app.agents.storyboard.schemas import (
    ProductionAwareStoryboard,
)


class StoryboardVisualGenerator:
    """
    Builds image-generation prompts from the final
    production-aware storyboard.

    This class does NOT call the image model.

    It produces deterministic generation instructions
    consumed by StoryboardAssetGenerator.
    """

    THUMBNAIL_VARIANTS = (
        "face-forward",
        "object-forward",
        "text-forward",
    )

    def generate(
        self,
        production_storyboard: ProductionAwareStoryboard,
        *,
        generate_concept_art: bool = False,
    ) -> dict:

        thumbnails = self._build_thumbnail_variants(
            production_storyboard
        )

        storyboard_panels = (
            self._build_storyboard_panels(
                production_storyboard
            )
        )

        concept_art = []

        if generate_concept_art:
            concept_art.append(
                self._build_concept_art(
                    production_storyboard
                )
            )

        return {
            "thumbnails": thumbnails,
            "storyboard_panels": storyboard_panels,
            "concept_art": concept_art,
        }

    def _build_thumbnail_variants(
        self,
        production_storyboard: ProductionAwareStoryboard,
    ) -> list[dict]:

        storyboard = production_storyboard.storyboard

        context = self._build_visual_context(
            production_storyboard
        )

        variants = []

        for direction in self.THUMBNAIL_VARIANTS:

            prompt = self._build_thumbnail_prompt(
                context=context,
                direction=direction,
            )

            variants.append(
                {
                    "variant": direction,
                    "concept": (
                        f"{direction.replace('-', ' ').title()} "
                        "thumbnail composition"
                    ),
                    "headline": self._thumbnail_text(
                        storyboard
                    ),
                    "prompt": prompt,
                }
            )

        return variants

    def _build_storyboard_panels(
        self,
        production_storyboard: ProductionAwareStoryboard,
    ) -> list[dict]:

        storyboard = production_storyboard.storyboard

        panels = []

        for shot in storyboard.shots:

            production_plan = (
                self._find_production_plan(
                    production_storyboard,
                    shot.shot_id,
                )
            )

            panels.append(
                {
                    "shot_id": shot.shot_id,
                    "beat_id": shot.beat_id,
                    "prompt": self._build_panel_prompt(
                        shot=shot,
                        production_plan=production_plan,
                        storyboard=storyboard,
                    ),
                }
            )

        return panels

    def _build_concept_art(
        self,
        production_storyboard: ProductionAwareStoryboard,
    ) -> dict:

        storyboard = production_storyboard.storyboard

        prompt = f"""
Create original cinematic concept art representing the
overall visual identity of this storyboard.

VISUAL STYLE:
{storyboard.visual_style or "Cinematic"}

COLOUR PALETTE:
{storyboard.color_palette or "Not specified"}

STORYBOARD VISUAL LANGUAGE:

{
    chr(10).join(
        f"- {shot.shot_type}: "
        f"{shot.visual_description or shot.subject or 'Unknown'}"
        for shot in storyboard.shots
    )
}

REQUIREMENTS:

- Establish a coherent cinematic visual identity.
- Preserve the storyboard's visual language.
- Maintain colour continuity.
- Create an original composition.
- Do not reproduce reference imagery.
- Do not copy recognizable compositions.
- Do not include unrelated objects.

This is concept art for production direction,
not final footage.
""".strip()

        return {
            "concept_id": "concept_01",
            "prompt": prompt,
        }

    @staticmethod
    def _build_visual_context(
        production_storyboard: ProductionAwareStoryboard,
    ) -> str:

        storyboard = production_storyboard.storyboard

        shots = []

        for shot in storyboard.shots:

            shots.append(
                f"""
SHOT {shot.shot_id}

Type:
{shot.shot_type or "Unknown"}

Angle:
{shot.camera_angle or "Unknown"}

Movement:
{shot.camera_movement or "Unknown"}

Framing:
{shot.framing or "Unknown"}

Subject:
{shot.subject or "Unknown"}

Background:
{shot.background or "Unknown"}

Lighting:
{shot.lighting or "Unknown"}

Visual description:
{shot.visual_description or "Unknown"}

Colour palette:
{", ".join(shot.colour_palette) or "Unknown"}

Mood:
{shot.mood or "Unknown"}

On-screen text:
{shot.on_screen_text or "None"}
""".strip()
            )

        return f"""
VISUAL STYLE:
{storyboard.visual_style or "Not specified"}

COLOUR PALETTE:
{storyboard.color_palette or "Not specified"}

SHOT PLAN:

{chr(10).join(shots)}
""".strip()

    @staticmethod
    def _build_thumbnail_prompt(
        context: str,
        direction: str,
    ) -> str:

        direction_instruction = {
            "face-forward": """
Make the human face or presenter the dominant
visual anchor.

Use expression and eye direction to create
immediate emotional engagement.
""",
            "object-forward": """
Make the primary object, location, product,
or visual subject the dominant element.

The subject must be understandable immediately
at small thumbnail size.
""",
            "text-forward": """
Create a strong composition around a short,
high-impact text area.

Text must remain secondary to the image.
""",
        }[direction]

        return f"""
Create an original cinematic social-video thumbnail.

CREATIVE AXIS:
{direction}

{direction_instruction}

STORYBOARD CONTEXT:
{context}

REQUIREMENTS:

- Readable at very small size.
- Use no more than 3-5 words of text.
- Keep text highly legible.
- Keep important information away from the lower-right corner.
- Preserve the storyboard colour palette.
- Preserve the storyboard cinematic mood.
- Establish a strong focal hierarchy.
- Avoid clutter.
- Create an original composition.
- Do not reproduce reference imagery.
- Do not copy recognizable compositions.

The thumbnail should visually promise the same
video represented by the storyboard.
""".strip()

    @staticmethod
    def _build_panel_prompt(
        shot,
        production_plan,
        storyboard,
    ) -> str:

        production_text = ""

        if production_plan is not None:
            production_text = f"""
PRODUCTION PLAN:

Camera:
{production_plan.camera or "Not specified"}

Lens:
{production_plan.lens or "Not specified"}

Support:
{production_plan.support or "Not specified"}

Lighting:
{production_plan.lighting_setup or "Not specified"}

Location:
{", ".join(production_plan.location_requirements) or "None"}

Equipment:
{", ".join(production_plan.equipment_required) or "None"}
""".strip()

        return f"""
Create an original cinematic storyboard panel.

SHOT:
{shot.shot_id}

BEAT:
{shot.beat_id}

TIMING:
{shot.start_time:.2f}s - {shot.end_time:.2f}s

SHOT TYPE:
{shot.shot_type or "Unknown"}

CAMERA ANGLE:
{shot.camera_angle or "Unknown"}

CAMERA MOVEMENT:
{shot.camera_movement or "Unknown"}

FRAMING:
{shot.framing or "Unknown"}

SUBJECT:
{shot.subject or "Unknown"}

BACKGROUND:
{shot.background or "Unknown"}

LIGHTING:
{shot.lighting or "Unknown"}

VISUAL DESCRIPTION:
{shot.visual_description or "Unknown"}

COLOUR PALETTE:
{", ".join(shot.colour_palette) or "Unknown"}

MOOD:
{shot.mood or "Unknown"}

OVERALL VISUAL STYLE:
{storyboard.visual_style or "Cinematic"}

{production_text}

REQUIREMENTS:

- Preserve the intended composition.
- Follow framing, camera angle and lighting.
- Respect the production plan.
- Preserve colour continuity.
- Do not add unrelated objects.
- Create an original visual interpretation.
- Do not reproduce reference frames.

This is storyboard concept art,
not final footage.
""".strip()

    @staticmethod
    def _thumbnail_text(
        storyboard,
    ) -> Optional[str]:

        for shot in storyboard.shots:

            if shot.on_screen_text:
                return shot.on_screen_text

        return None

    @staticmethod
    def _find_production_plan(
        production_storyboard,
        shot_id: str,
    ):

        for plan in production_storyboard.production_plans:

            if plan.shot_id == shot_id:
                return plan

        return None