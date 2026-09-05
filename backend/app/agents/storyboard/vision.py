from typing import List

from app.agents.storyboard.schemas import (
    VisualReferenceAnalysis,
)
from app.agents.storyboard.media import (
    ExtractedFrame,
)
from app.shared.tools.gemini.client import GeminiClient


class StoryboardReferenceVisionAnalyzer:
    """
    Analyzes extracted storyboard reference frames using Gemini Vision.

    Phase 3 responsibilities:
        1. Accept extracted frames.
        2. Analyze each frame independently.
        3. Return structured VisualReferenceAnalysis objects.

    The analyzer intentionally does not generate recommendations.
    It only describes what is visually present in the reference.
    """

    def __init__(
        self,
        gemini: GeminiClient | None = None,
    ):
        self.gemini = gemini or GeminiClient()

    async def analyze_frame(
        self,
        frame: ExtractedFrame,
        reference_url: str | None = None,
    ) -> VisualReferenceAnalysis:

        prompt = self._build_prompt(
            reference_url=reference_url,
            timestamp=frame.timestamp,
            shot_index=frame.shot_index,
        )

        analysis = self.gemini.generate_image_analysis(
            prompt=prompt,
            image_path=frame.path,
            response_schema=VisualReferenceAnalysis,
        )

        if analysis.reference_url is None:
            analysis.reference_url = reference_url

        return analysis

    async def analyze_frames(
        self,
        frames: List[ExtractedFrame],
        reference_url: str | None = None,
    ) -> List[VisualReferenceAnalysis]:

        analyses = []

        for frame in frames:
            analysis = await self.analyze_frame(
                frame=frame,
                reference_url=reference_url,
            )

            analyses.append(analysis)

        return analyses

    @staticmethod
    def _build_prompt(
        reference_url: str | None,
        timestamp: float,
        shot_index: int,
    ) -> str:

        return f"""
You are a visual cinematography analysis system.

Analyze the provided video frame as a VISUAL REFERENCE.

Your task is observation, not recommendation.

Do not suggest how the frame should be recreated.
Do not judge whether the frame is good or bad.
Do not invent information that cannot be reasonably observed.

Extract only visible cinematic and visual properties.

Analyze:

1. Shot size
   Examples:
   - Extreme Wide Shot
   - Wide Shot
   - Medium Shot
   - Medium Close-up
   - Close-up
   - Extreme Close-up

2. Camera angle
   Examples:
   - Eye Level
   - Low Angle
   - High Angle
   - Overhead
   - Dutch Angle

3. Subject placement
   Describe where the primary subject appears within the frame.

4. Background
   Describe the visible environment and important background elements.

5. Lighting
   Describe the apparent lighting characteristics.

6. Colour palette
   Identify the dominant visible colours.

7. Movement
   Only describe movement if it can reasonably be inferred from the frame
   or visible motion cues. Otherwise return null.

8. On-screen text
   Transcribe clearly visible text if present.
   Otherwise return null.

9. Mood
   Describe the apparent visual mood or atmosphere.

REFERENCE METADATA

Reference URL:
{reference_url or "Unknown"}

Frame timestamp:
{timestamp:.2f}s

Shot index:
{shot_index}

Return the result using the provided structured schema.
""".strip()