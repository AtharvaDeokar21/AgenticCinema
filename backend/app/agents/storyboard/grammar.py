from typing import List

from app.agents.storyboard.schemas import (
    VisualReferenceAnalysis,
    VisualGrammar,
)
from app.shared.tools.gemini.client import GeminiClient


class VisualGrammarBuilder:
    """
    Aggregates individual visual reference analyses into a
    coherent visual grammar.

    Phase 3B responsibilities:
        1. Collect observations from multiple reference frames.
        2. Identify recurring visual patterns.
        3. Produce structured VisualGrammar.
        4. Preserve evidence for traceability.

    This component does not generate the final storyboard.
    """

    def __init__(
        self,
        gemini: GeminiClient | None = None,
    ):
        self.gemini = gemini or GeminiClient()

    def build(
        self,
        analyses: List[VisualReferenceAnalysis],
    ) -> VisualGrammar:

        if not analyses:
            return VisualGrammar(
                summary="No visual reference analyses were provided.",
                evidence=[],
            )

        prompt = self._build_prompt(analyses)

        grammar = self.gemini.generate_structured(
            prompt=prompt,
            response_schema=VisualGrammar,
        )

        if grammar is None:
            raise ValueError(
                "Gemini returned no visual grammar."
            )

        return grammar

    @staticmethod
    def _build_prompt(
        analyses: List[VisualReferenceAnalysis],
    ) -> str:

        sections = []

        for index, analysis in enumerate(
            analyses,
            start=1,
        ):
            sections.append(
                f"""
REFERENCE FRAME {index}

Reference URL:
{analysis.reference_url or "Unknown"}

Shot size:
{analysis.shot_size or "Unknown"}

Camera angle:
{analysis.camera_angle or "Unknown"}

Subject placement:
{analysis.subject_placement or "Unknown"}

Background:
{analysis.background or "Unknown"}

Lighting:
{analysis.lighting or "Unknown"}

Colour palette:
{", ".join(analysis.colour_palette) or "Unknown"}

Movement:
{analysis.movement or "Unknown"}

On-screen text:
{analysis.on_screen_text or "None"}

Mood:
{analysis.mood or "Unknown"}
""".strip()
            )

        references = "\n\n".join(sections)

        return f"""
You are a visual language analysis system for a cinematic
storyboard pipeline.

Below are observations extracted from multiple reference frames.

Your task is to identify RECURRING VISUAL PATTERNS across the
references and convert them into a structured visual grammar.

IMPORTANT:

- Analyze patterns across the references.
- Do not simply repeat every individual observation.
- Do not invent patterns unsupported by the references.
- Do not recommend specific shots for the final storyboard.
- Do not copy individual references blindly.
- Identify tendencies that could inform consistent visual
  direction.
- If a category has no meaningful evidence, return an empty list.
- Every important pattern should be supported by evidence.

Analyze the following categories:

1. Framing patterns
   Recurring shot sizes and subject-placement tendencies.

2. Camera patterns
   Recurring camera angles and camera perspectives.

3. Movement patterns
   Recurring camera or subject movement when supported by
   the observations.

4. Lighting patterns
   Recurring lighting characteristics.

5. Colour patterns
   Recurring colour palettes and colour relationships.

6. Pacing patterns
   Infer only from available movement, shot structure, or
   temporal observations. Do not invent pacing information.

7. Text patterns
   Recurring on-screen text characteristics, if present.

8. Summary
   Give a concise description of the overall visual language.

9. Evidence
   Provide concise statements explaining which observations
   support the identified patterns.

REFERENCE OBSERVATIONS

{references}

Return only the structured VisualGrammar response.
""".strip()