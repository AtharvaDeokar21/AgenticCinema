from typing import Optional

from app.agents.storyboard.agent import StoryboardAgent
from app.agents.storyboard.schemas import (
    CreatorStyleContext,
    ProductionConstraints,
    ProductionAwareStoryboard,
    AdaptedStoryboard,
    VisualGrammar,
    VisualReferenceAnalysis,
    StoryboardAssetGenerationResult,
)
from app.shared.models.script import ScriptVersion
from app.shared.models.storyboard import ShotPlan
from app.agents.storyboard.asset_generator import (
    StoryboardAssetGenerator,
)

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
        asset_generator: Optional[StoryboardAssetGenerator] = None,
    ):
        self.storyboard_agent = (
            storyboard_agent or StoryboardAgent()
        )
        self.asset_generator = (
            asset_generator or StoryboardAssetGenerator()
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

    def adapt_storyboard(
        self,
        production_storyboard: ProductionAwareStoryboard,
        production_constraints: ProductionConstraints,
    ) -> AdaptedStoryboard:

        return self.storyboard_agent.adapt_storyboard(
            production_storyboard=production_storyboard,
            production_constraints=production_constraints,
        )

    def generate_assets(
        self,
        storyboard: ShotPlan,
        *,
        production: ProductionAwareStoryboard | None = None,
        creator_style: CreatorStyleContext | None = None,
        project_id: str = "default",
        generate_shots: bool = True,
    ) -> StoryboardAssetGenerationResult:

        return self.asset_generator.generate(
            storyboard=storyboard,
            production=production,
            creator_style=creator_style,
            project_id=project_id,
            generate_shots=generate_shots,
        )