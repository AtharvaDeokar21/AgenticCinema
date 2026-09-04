from datetime import datetime, timezone

from app.agents.base import BaseAgent
from app.agents.script_suggestor.prompts import (
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
)
from app.agents.script_suggestor.schemas import ScriptRequest
from app.shared.models.script import ScriptVersion
from app.shared.models.research import ResearchResult
from app.shared.tools.gemini.client import GeminiClient
from app.shared.tools.parallel.search import ParallelSearch


class ScriptSuggestorAgent(BaseAgent):
    """
    Generates production-oriented script drafts using Gemini
    and optionally researches current information using Parallel.
    """

    name = "script_suggestor"

    def __init__(self):
        self.gemini = GeminiClient()
        self.parallel = ParallelSearch()

    async def run(self, request: ScriptRequest) -> ScriptVersion:
        research = None

        if request.research_required:
            research = await self._research(request)

        research_context = (
            self._format_research(research)
            if research
            else "No research performed."
        )

        prompt = self._build_prompt(
            request=request,
            research_context=research_context,
        )

        print("\n" + "=" * 80)
        print("FINAL GEMINI PROMPT")
        print("=" * 80)
        print(prompt)
        print("=" * 80)

        script = self.gemini.generate_structured(
            prompt=prompt,
            response_schema=ScriptVersion,
        )

        script.version = 1
        script.created_at = datetime.now(timezone.utc)
        script.status = "draft"

        if research:
            script.evidence = [
                source.url
                for source in research.sources
                if source.url
            ]

        return script

    async def _research(
        self,
        request: ScriptRequest,
    ) -> ResearchResult:
        queries = request.research_queries

        if not queries:
            queries = [request.brief]

        return await self.parallel.search(
            search_queries=queries,
            objective=(
                "Find factual and contextual information that can "
                "improve a cinematic script based on the creator brief."
            ),
        )

    def _build_prompt(
        self,
        request: ScriptRequest,
        research_context: str,
    ) -> str:
        return (
            SYSTEM_PROMPT
            + "\n\n"
            + USER_PROMPT_TEMPLATE.format(
                brief=request.brief,
                target_audience=request.target_audience or "Not specified",
                genre=request.genre or "Not specified",
                tone=request.tone or "Not specified",
                language=request.language or "Not specified",
                duration_seconds=(
                    request.duration_seconds
                    if request.duration_seconds is not None
                    else "Not specified"
                ),
                research_context=research_context or "No research performed.",
            )
        )

    def _format_research(
        self,
        research: ResearchResult,
    ) -> str:
        if not research.sources:
            return "No relevant web research was found."

        sections = []

        for source in research.sources:
            excerpts = "\n".join(
                f"- {excerpt}"
                for excerpt in source.excerpts
            )

            sections.append(
                f"""
    SOURCE: {source.title}
    URL: {source.url}
    PUBLISHED: {source.publish_date or "Unknown"}

    EXCERPTS:
    {excerpts}
    """
            )

        return "\n".join(sections)