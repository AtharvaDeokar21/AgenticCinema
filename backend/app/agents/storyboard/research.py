from typing import Optional

from app.shared.tools.parallel.search import ParallelSearch
from app.shared.tools.parallel.extract import ParallelExtract

from app.agents.storyboard.schemas import (
    StoryboardReference,
    StoryboardReferenceResearch,
)

from app.agents.storyboard.media import (
    ReferenceMediaProcessor,
)


class StoryboardReferenceResearcher:
    """
    Finds, extracts, and processes reference content relevant
    to a storyboard.

    Phase 1:
        Search -> Extract

    Phase 2:
        Media -> FFprobe -> CFR -> Scene detection -> Frames
    """

    def __init__(
        self,
        search: Optional[ParallelSearch] = None,
        extract: Optional[ParallelExtract] = None,
        media_processor: Optional[ReferenceMediaProcessor] = None,
    ):
        self.search = search or ParallelSearch()
        self.extract = extract or ParallelExtract()
        self.media_processor = (
            media_processor
            or ReferenceMediaProcessor()
        )

    async def research(
        self,
        script_text: str,
        topic: str,
        max_references: int = 10,
    ) -> StoryboardReferenceResearch:

        search_result = await self.search.search(
            search_queries=[
                topic,
                f"{topic} cinematic video",
                f"{topic} storytelling video",
            ],
            objective=(
                "Find high-performing visual/video references relevant "
                "to the topic that can inform cinematic storyboard "
                "decisions. Prioritize references with useful visual "
                "and storytelling patterns."
            ),
            mode="basic",
        )

        sources = search_result.sources[:max_references]

        if not sources:
            return StoryboardReferenceResearch(
                query=topic,
                references=[],
            )

        urls = [source.url for source in sources]

        extracted_pages = await self.extract.extract(
            urls=urls,
            excerpts=True,
            full_content=True,
        )

        pages_by_url = {
            page.url: page
            for page in extracted_pages
        }

        references = []

        for source in sources:

            page = pages_by_url.get(source.url)

            references.append(
                StoryboardReference(
                    title=source.title,
                    url=source.url,
                    excerpts=(
                        page.excerpts
                        if page and page.excerpts
                        else source.excerpts
                    ),
                    publish_date=source.publish_date,
                    content=(
                        page.content
                        if page and page.ok
                        else None
                    ),
                )
            )

        return StoryboardReferenceResearch(
            query=topic,
            references=references,
        )

    async def process_media(
        self,
        source_url: str,
        local_path: str,
        reference_id: str,
    ):
        """
        Process a locally available reference video.

        Downloading is intentionally outside this class for now.
        """

        return self.media_processor.process(
            source_url=source_url,
            local_path=local_path,
            reference_id=reference_id,
        )

    async def close(self):
        await self.search.close()
        await self.extract.close()