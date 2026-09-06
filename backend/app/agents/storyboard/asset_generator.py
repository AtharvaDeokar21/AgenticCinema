from pathlib import Path
from typing import Optional

from app.agents.storyboard.schemas import (
    ProductionAwareStoryboard,
    StoryboardAssetGenerationResult,
    ThumbnailVariant,
    GeneratedStoryboardAsset,
)

from app.agents.storyboard.visual_generation import (
    StoryboardVisualGenerator,
)

from app.shared.tools.image.client import (
    ImageGenerationClient,
)


class StoryboardAssetGenerator:
    """
    Executes Phase 7 visual generation.

    Pipeline:

        ProductionAwareStoryboard
                |
                v
        StoryboardVisualGenerator
                |
                v
        generation prompts
                |
                v
        ImageGenerationClient
                |
                v
        real PNG assets
    """

    def __init__(
        self,
        image_client: Optional[
            ImageGenerationClient
        ] = None,
        visual_generator: Optional[
            StoryboardVisualGenerator
        ] = None,
        output_root: str = (
            "storage/storyboard/generated"
        ),
    ):

        self.image_client = (
            image_client
            or ImageGenerationClient()
        )

        self.visual_generator = (
            visual_generator
            or StoryboardVisualGenerator()
        )

        self.output_root = Path(output_root)

    def generate(
        self,
        storyboard,
        production: ProductionAwareStoryboard,
        project_id: str,
        *,
        generate_shots: bool = True,
        generate_thumbnails: bool = True,
        generate_concept_art: bool = False,
    ) -> StoryboardAssetGenerationResult:

        del storyboard

        output_dir = (
            self.output_root
            / project_id
        )

        thumbnails_dir = (
            output_dir / "thumbnails"
        )

        shots_dir = (
            output_dir / "shots"
        )

        concept_dir = (
            output_dir / "concept_art"
        )

        if generate_thumbnails:
            thumbnails_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

        if generate_shots:
            shots_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

        if generate_concept_art:
            concept_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

        result = StoryboardAssetGenerationResult()

        prompt_bundle = self.visual_generator.generate(
            production,
            generate_concept_art=generate_concept_art,
        )

        if generate_thumbnails:

            self._generate_thumbnails(
                prompt_bundle=prompt_bundle,
                output_dir=thumbnails_dir,
                result=result,
            )

        if generate_shots:

            self._generate_storyboard_assets(
                prompt_bundle=prompt_bundle,
                output_dir=shots_dir,
                project_id=project_id,
                result=result,
            )

        if generate_concept_art:

            self._generate_concept_art(
                prompt_bundle=prompt_bundle,
                output_dir=concept_dir,
                project_id=project_id,
                result=result,
            )

        return result

    def _generate_thumbnails(
        self,
        *,
        prompt_bundle: dict,
        output_dir: Path,
        result: StoryboardAssetGenerationResult,
    ) -> None:

        for index, thumbnail in enumerate(
            prompt_bundle["thumbnails"],
            start=1,
        ):

            variant = thumbnail["variant"]
            prompt = thumbnail["prompt"]

            output_path = (
                output_dir
                / f"thumbnail_{index:02d}.png"
            )

            try:

                generated_path = (
                    self.image_client.generate_image(
                        prompt=prompt,
                        output_path=str(output_path),
                        aspect_ratio="16:9",
                        image_size="1K",
                    )
                )

                result.thumbnails.append(
                    ThumbnailVariant(
                        variant=variant,
                        concept=thumbnail["concept"],
                        headline=thumbnail.get(
                            "headline"
                        ),
                        prompt=prompt,
                        image_path=generated_path,
                        aspect_ratio="16:9",
                    )
                )

            except Exception as exc:

                result.errors.append(
                    "Thumbnail generation failed "
                    f"for variant '{variant}': {exc}"
                )

    def _generate_storyboard_assets(
        self,
        *,
        prompt_bundle: dict,
        output_dir: Path,
        project_id: str,
        result: StoryboardAssetGenerationResult,
    ) -> None:

        for panel in prompt_bundle[
            "storyboard_panels"
        ]:

            shot_id = panel["shot_id"]
            beat_id = panel["beat_id"]
            prompt = panel["prompt"]

            output_path = (
                output_dir
                / f"{shot_id}.png"
            )

            try:

                generated_path = (
                    self.image_client.generate_image(
                        prompt=prompt,
                        output_path=str(output_path),
                        aspect_ratio="16:9",
                        image_size="1K",
                    )
                )

                result.storyboard_assets.append(
                    GeneratedStoryboardAsset(
                        asset_id=(
                            f"{project_id}_{shot_id}"
                        ),
                        shot_id=shot_id,
                        asset_type=(
                            "storyboard_keyframe"
                        ),
                        prompt=prompt,
                        image_path=generated_path,
                        aspect_ratio="16:9",
                        notes=(
                            f"Generated from beat "
                            f"{beat_id}."
                        ),
                    )
                )

            except Exception as exc:

                result.errors.append(
                    "Storyboard image generation "
                    f"failed for shot '{shot_id}': {exc}"
                )

    def _generate_concept_art(
        self,
        *,
        prompt_bundle: dict,
        output_dir: Path,
        project_id: str,
        result: StoryboardAssetGenerationResult,
    ) -> None:

        for concept in prompt_bundle[
            "concept_art"
        ]:

            concept_id = concept["concept_id"]
            prompt = concept["prompt"]

            output_path = (
                output_dir
                / f"{concept_id}.png"
            )

            try:

                generated_path = (
                    self.image_client.generate_image(
                        prompt=prompt,
                        output_path=str(output_path),
                        aspect_ratio="16:9",
                        image_size="1K",
                    )
                )

                result.concept_art.append(
                    GeneratedStoryboardAsset(
                        asset_id=(
                            f"{project_id}_{concept_id}"
                        ),
                        shot_id=None,
                        asset_type="concept_art",
                        prompt=prompt,
                        image_path=generated_path,
                        aspect_ratio="16:9",
                        notes=(
                            "Overall storyboard visual "
                            "direction."
                        ),
                    )
                )

            except Exception as exc:

                result.errors.append(
                    "Concept art generation failed "
                    f"for '{concept_id}': {exc}"
                )