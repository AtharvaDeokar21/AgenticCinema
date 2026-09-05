import pytest

from app.agents.storyboard.research import StoryboardReferenceResearcher
from app.shared.models.research import (
    ResearchResult,
    ResearchSource,
)


class FakeSearch:

    async def search(self, *args, **kwargs):
        return ResearchResult(
            query="Photographer of Mumbai",
            sources=[
                ResearchSource(
                    title="Mumbai Street Photography",
                    url="https://example.com/mumbai",
                    excerpts=[
                        "A visual exploration of Mumbai streets."
                    ],
                )
            ],
        )

    async def close(self):
        pass


class FakeExtract:

    async def extract(self, urls, **kwargs):
        from app.shared.tools.parallel.extract import ExtractedPage

        return [
            ExtractedPage(
                url=urls[0],
                title="Mumbai Street Photography",
                content="Full extracted reference content.",
                excerpts=[
                    "A visual exploration of Mumbai streets."
                ],
            )
        ]

    async def close(self):
        pass


@pytest.mark.asyncio
async def test_storyboard_reference_research():

    researcher = StoryboardReferenceResearcher(
        search=FakeSearch(),
        extract=FakeExtract(),
    )

    result = await researcher.research(
        script_text="A photographer explores Mumbai.",
        topic="Photographer of Mumbai",
    )

    assert result.query == "Photographer of Mumbai"
    assert len(result.references) == 1

    reference = result.references[0]

    assert reference.title == "Mumbai Street Photography"
    assert reference.url == "https://example.com/mumbai"
    assert reference.content == (
        "Full extracted reference content."
    )
    assert reference.excerpts