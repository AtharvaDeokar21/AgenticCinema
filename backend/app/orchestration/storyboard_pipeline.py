from typing import Optional

from app.agents.storyboard.agent import StoryboardAgent
from app.agents.storyboard.schemas import (
    CreatorStyleContext,
    ProductionConstraints,
    ProductionAwareStoryboard,
    VisualGrammar,
    VisualReferenceAnalysis,
)
from app.shared.models.script import ScriptVersion
from app.shared.models.storyboard import ShotPlan


class StoryboardPipeline:
    """
    End-to-end storyboard generation pipeline.

    Phase 3:
        Script
          -> visual references
          -> reference analysis
          -> visual grammar
          -> storyboard generation
    """

    def __init__(
        self,
        storyboard_agent: Optional[StoryboardAgent] = None,
    ):
        self.storyboard_agent = (
            storyboard_agent or StoryboardAgent()
        )

    def generate(
        self,
        script: ScriptVersion,
        *,
        production_constraints: ProductionConstraints | None = None,
        creator_style: CreatorStyleContext | None = None,
        visual_references: list[VisualReferenceAnalysis] | None = None,
        visual_grammar: VisualGrammar | None = None,
    ) -> ShotPlan:

        return self.storyboard_agent.generate(
            script=script,
            production_constraints=production_constraints,
            creator_style=creator_style,
            visual_references=visual_references,
            visual_grammar=visual_grammar,
        )

    def plan_production(
        self,
        storyboard: ShotPlan,
        production_constraints: ProductionConstraints,
    ) -> ProductionAwareStoryboard:

        return self.storyboard_agent.plan_production(
            storyboard=storyboard,
            production_constraints=production_constraints,
        )