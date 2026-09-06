from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from app.agents.storyboard.adaptation import (
    StoryboardAdaptationPlanner,
)
from app.agents.storyboard.agent import StoryboardAgent
from app.agents.storyboard.asset_generator import (
    StoryboardAssetGenerator,
)
from app.agents.storyboard.grammar import (
    VisualGrammarBuilder,
)
from app.agents.storyboard.media import (
    ReferenceMediaProcessor,
)
from app.agents.storyboard.reference_analyzer import (
    StoryboardReferenceAnalyzer,
)
from app.agents.storyboard.schemas import (
    AdaptedStoryboard,
    CreatorStyleContext,
    ProductionAwareStoryboard,
    ProductionConstraints,
    StoryboardReferenceResearch,
    StoryboardAssetGenerationResult,
    VisualGrammar,
    VisualReferenceAnalysis,
)
from app.shared.models.script import ScriptVersion
from app.shared.models.storyboard import ShotPlan


@dataclass
class StoryboardPipelineResult:
    """
    Complete result of the end-to-end Storyboard pipeline.
    """

    research: StoryboardReferenceResearch

    media_results: list = field(
        default_factory=list
    )

    visual_analyses: List[
        VisualReferenceAnalysis
    ] = field(default_factory=list)

    visual_grammar: Optional[
        VisualGrammar
    ] = None

    storyboard: Optional[
        ShotPlan
    ] = None

    production_storyboard: Optional[
        ProductionAwareStoryboard
    ] = None

    adapted_storyboard: Optional[
        AdaptedStoryboard
    ] = None

    assets: Optional[
        StoryboardAssetGenerationResult
    ] = None


class StoryboardPipeline:
    """
    End-to-end Storyboard Agent orchestration.

    Pipeline:

        Script
          |
          v
        Parallel Search
          |
          v
        Parallel Extract
          |
          v
        FFmpeg media processing
          |
          v
        Gemini Vision
          |
          v
        Visual Grammar
          |
          v
        StoryboardAgent
          |
          v
        Production Planning
          |
          v
        Production Adaptation
          |
          v
        Hugging Face Image Generation
          |
          v
        Final Assets

    Creator thumbnail history and feedback-loop learning are
    intentionally outside the demo pipeline.
    """

    def __init__(
        self,
        *,
        storyboard_agent: Optional[
            StoryboardAgent
        ] = None,
        media_processor: Optional[
            ReferenceMediaProcessor
        ] = None,
        reference_analyzer: Optional[
            StoryboardReferenceAnalyzer
        ] = None,
        grammar_builder: Optional[
            VisualGrammarBuilder
        ] = None,
        adaptation_planner: Optional[
            StoryboardAdaptationPlanner
        ] = None,
        asset_generator: Optional[
            StoryboardAssetGenerator
        ] = None,
    ):
        self.storyboard_agent = (
            storyboard_agent
            or StoryboardAgent()
        )

        self.media_processor = (
            media_processor
            or ReferenceMediaProcessor()
        )

        self.reference_analyzer = (
            reference_analyzer
            or StoryboardReferenceAnalyzer()
        )

        self.grammar_builder = (
            grammar_builder
            or VisualGrammarBuilder()
        )

        self.adaptation_planner = (
            adaptation_planner
            or StoryboardAdaptationPlanner()
        )

        self.asset_generator = (
            asset_generator
            or StoryboardAssetGenerator()
        )

    async def run(
        self,
        script: ScriptVersion,
        production_constraints: ProductionConstraints,
        project_id: str,
        *,
        creator_style: Optional[CreatorStyleContext] = None,
        max_references: int = 10,
        fallback_reference_media: Optional[str] = None,
        reference_media_paths: Optional[dict[str, str]] = None,
        generate_thumbnails: bool = True,
        generate_shots: bool = True,
    ) -> StoryboardPipelineResult:
        """
        Execute the complete Storyboard workflow.

        Parameters
        ----------
        script:
            Locked timestamped ScriptVersion.

        production_constraints:
            Creator's actual production capabilities.

        project_id:
            Output namespace for generated assets.

        reference_media_paths:
            Mapping:

                reference URL -> local video path

            Parallel Search/Extract discover and describe
            references. Media processing operates on locally
            available video files.

        creator_style:
            Optional creator-style context.

        max_references:
            Maximum number of Parallel references to use.

        generate_thumbnails:
            Generate three thumbnail variants.

        generate_shots:
            Generate storyboard keyframes.
        """

        # ---------------------------------------------------------
        # 1. PARALLEL SEARCH + EXTRACT
        # ---------------------------------------------------------

        research = await (
            self.storyboard_agent
            .research_references(
                script=script,
                max_references=max_references,
            )
        )

        # ---------------------------------------------------------
        # 2. PROCESS REFERENCE MEDIA WITH FFMPEG
        # ---------------------------------------------------------

        media_results = []

        media_paths = (
            reference_media_paths
            or {}
        )

        for index, reference in enumerate(
            research.references,
            start=1,
        ):
            local_path = media_paths.get(
                reference.url
            )

            # Demo/local-fixture fallback.
            #
            # In production this would be replaced by a download
            # or Cloud Run media acquisition step.
            if (
                not local_path
                and fallback_reference_media
                and index == 1
            ):
                local_path = (
                    fallback_reference_media
                )

            if not local_path:
                continue

            path = Path(local_path)

            if not path.exists():
                raise FileNotFoundError(
                    "Reference media path does not exist: "
                    f"{local_path}"
                )

            media_result = await (
                self.storyboard_agent
                .reference_researcher
                .process_media(
                    source_url=reference.url,
                    local_path=str(path),
                    reference_id=(
                        f"{project_id}_reference_{index}"
                    ),
                )
            )

            if media_result.error:
                raise RuntimeError(
                    "Reference media processing failed "
                    f"for {reference.url}: "
                    f"{media_result.error}"
                )

            reference.media_path = (
                media_result.processed_path
                or media_result.local_path
            )

            reference.frames = (
                media_result.frames
            )

            media_results.append(
                media_result
            )

        # ---------------------------------------------------------
        # 3. GEMINI VISION
        # ---------------------------------------------------------

        visual_analyses = []

        for media_result in media_results:
            if not media_result.frames:
                continue

            reference_url = (
                getattr(
                    media_result,
                    "reference_url",
                    None,
                )
                or getattr(
                    media_result,
                    "source_url",
                    None,
                )
            )

            analysis_result = (
                await self.reference_analyzer.analyze(
                    frames=media_result.frames,
                    reference_url=reference_url,
                )
            )

            visual_analyses.extend(
                analysis_result.analyses
            )

        # ---------------------------------------------------------
        # 4. BUILD VISUAL GRAMMAR
        # ---------------------------------------------------------

        visual_grammar = (
            self.grammar_builder.build(
                visual_analyses
            )
            if visual_analyses
            else VisualGrammar(
                summary=(
                    "No reference media frames were "
                    "available for visual analysis."
                ),
                evidence=[],
            )
        )

        # ---------------------------------------------------------
        # 5. GENERATE STORYBOARD
        # ---------------------------------------------------------

        storyboard = (
            self.storyboard_agent.generate(
                script=script,
                production_constraints=(
                    production_constraints
                ),
                creator_style=creator_style,
                visual_references=(
                    visual_analyses
                ),
                visual_grammar=visual_grammar,
            )
        )

        # ---------------------------------------------------------
        # 6. PRODUCTION PLANNING
        # ---------------------------------------------------------

        production_storyboard = (
            self.storyboard_agent.plan_production(
                storyboard=storyboard,
                production_constraints=(
                    production_constraints
                ),
            )
        )

        # ---------------------------------------------------------
        # 7. PRODUCTION ADAPTATION
        # ---------------------------------------------------------

        adapted_storyboard = (
            self.storyboard_agent.adapt_storyboard(
                production_storyboard=(
                    production_storyboard
                ),
                production_constraints=(
                    production_constraints
                ),
            )
        )

        # ---------------------------------------------------------
        # 8. FINAL ASSET GENERATION
        # ---------------------------------------------------------
        #
        # The asset generator works from a
        # ProductionAwareStoryboard.
        #
        # Rebuild it using the adapted ShotPlan while
        # preserving the production plans.

        final_production_storyboard = (
            ProductionAwareStoryboard(
                storyboard=(
                    adapted_storyboard.storyboard
                ),
                production_plans=(
                    production_storyboard
                    .production_plans
                ),
                overall_issues=(
                    production_storyboard
                    .overall_issues
                ),
            )
        )

        assets = self.asset_generator.generate(
            storyboard=(
                adapted_storyboard.storyboard
            ),
            production=(
                final_production_storyboard
            ),
            project_id=project_id,
            generate_shots=generate_shots,
            generate_thumbnails=(
                generate_thumbnails
            ),
        )

        return StoryboardPipelineResult(
            research=research,
            media_results=media_results,
            visual_analyses=visual_analyses,
            visual_grammar=visual_grammar,
            storyboard=storyboard,
            production_storyboard=(
                production_storyboard
            ),
            adapted_storyboard=(
                adapted_storyboard
            ),
            assets=assets,
        )