from dataclasses import dataclass
from typing import List

from app.agents.storyboard.grammar import (
    VisualGrammarBuilder,
)
from app.agents.storyboard.schemas import (
    VisualGrammar,
    VisualReferenceAnalysis,
)
from app.agents.storyboard.vision import (
    StoryboardReferenceVisionAnalyzer,
)
from app.agents.storyboard.media import (
    ExtractedFrame,
)


@dataclass
class ReferenceVisualAnalysisResult:
    analyses: List[VisualReferenceAnalysis]
    grammar: VisualGrammar


class StoryboardReferenceAnalyzer:
    """
    Coordinates frame-level visual analysis and visual grammar
    construction.
    """

    def __init__(
        self,
        vision_analyzer: (
            StoryboardReferenceVisionAnalyzer | None
        ) = None,
        grammar_builder: (
            VisualGrammarBuilder | None
        ) = None,
    ):
        self.vision_analyzer = (
            vision_analyzer
            or StoryboardReferenceVisionAnalyzer()
        )

        self.grammar_builder = (
            grammar_builder
            or VisualGrammarBuilder()
        )

    async def analyze(
        self,
        frames: List[ExtractedFrame],
        reference_url: str | None = None,
    ) -> ReferenceVisualAnalysisResult:

        analyses = self.vision_analyzer.analyze_frames(
            frames=frames,
            reference_url=reference_url,
        )

        if hasattr(analyses, "__await__"):
            analyses = await analyses

        grammar = self.grammar_builder.build(
            analyses
        )

        return ReferenceVisualAnalysisResult(
            analyses=analyses,
            grammar=grammar,
        )