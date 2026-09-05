"""Cultural Dub Agent: source-side cultural analysis."""

from typing import Optional

from app.agents.base import BaseAgent
from app.agents.cultural_dub.prompts import build_cultural_analysis_prompt
from app.agents.cultural_dub.schemas import (
    CulturalAnalysis,
    DubRequest,
)
from app.shared.tools.gemini.client import GeminiClient


class CulturalDubAgent(BaseAgent):
    """Analyze source dialogue for culturally sensitive localization spans."""

    name = "cultural_dub"
    ANALYSIS_MODEL = "gemini-3.7-flash"

    def __init__(
        self,
        gemini: Optional[GeminiClient] = None,
    ):
        self.gemini = gemini or GeminiClient()

    async def run(self, request: DubRequest) -> CulturalAnalysis:
        """Identify source spans requiring cultural localization handling.

        This phase intentionally stops before target-language generation.
        The existing AudioMaster transcript is treated as the canonical
        timestamped source when it is available.
        """
        if not request.audio_master.segments:
            raise ValueError(
                "Cultural Dub requires timestamped AudioMaster segments."
            )

        prompt = build_cultural_analysis_prompt(
            audio_master=request.audio_master,
            source_language=request.source_language,
        )

        analysis = self.gemini.generate_structured(
            prompt=prompt,
            response_schema=CulturalAnalysis,
            model=self.ANALYSIS_MODEL,
        )

        if analysis is None:
            raise ValueError(
                "Gemini returned no cultural analysis."
            )

        return analysis
