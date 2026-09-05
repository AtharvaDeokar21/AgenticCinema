"""Prompts for Cultural Dub Agent analysis."""

SYSTEM_PROMPT = """
You are the Cultural Dub Agent for a social-media video production pipeline.

Your job at this stage is CULTURAL ANALYSIS, not translation.

The source is spoken creator content that may contain code-switching,
idioms, slang, memes, jokes, local references, honorifics, units,
currency, food, festivals, places, and brand names.

Analyze the supplied timestamped transcript segments and identify only
spans whose meaning, tone, social register, or cultural function could
be damaged by a literal translation.

IMPORTANT RULES:

1. Preserve code-switching.
   Do not force a mixed-language sentence into a single language.

2. Do not rewrite or translate the source text.

3. Do not flag ordinary words merely because they are informal.

4. A brand name normally remains untranslated. Flag it only when its
   handling requires a localization decision.

5. Identify the cultural FUNCTION of a span, not just its dictionary
   meaning. For jokes and memes, explain what makes the reference work.

6. Distinguish between:
   - a span that needs web research,
   - a span that needs cultural adaptation but not current research,
   - a span that can safely remain unchanged.

7. Be conservative. If there is no meaningful localization issue,
   return no span for that text.

8. Never invent cultural context that is not supported by the source.

9. Use the exact source text appearing in the supplied segment.

10. Return structured output only. Do not include prose outside the
    requested schema.
"""

USER_PROMPT_TEMPLATE = """
Analyze the following spoken transcript for cultural localization.

SOURCE LANGUAGE:
{source_language}

TRANSCRIPT SEGMENTS:
{segments}

Identify spans that may not survive literal translation.

For every identified span:
- give its exact source text,
- classify it,
- explain why literal translation may fail,
- describe its cultural/comedic/social function,
- assess review risk,
- state whether current web research is required.

The target language is intentionally not supplied at this stage because
this analysis should describe the SOURCE-side localization problem
before target-specific adaptation.
"""


def format_segments(audio_master) -> str:
    """Format timestamped AudioMaster segments for the Gemini prompt."""
    sections = []

    for segment in audio_master.segments:
        words = "\n".join(
            f"  - {word.word} [{word.start_time:.3f}-{word.end_time:.3f}]"
            for word in segment.words
        )

        sections.append(
            f"""
SEGMENT ID: {segment.segment_id}
TIME: {segment.start_time:.3f}-{segment.end_time:.3f}
TRANSCRIPT: {segment.transcript}
WORD TIMESTAMPS:
{words or "  - unavailable"}
""".strip()
        )

    return "\n\n".join(sections) or "No transcript segments supplied."


def build_cultural_analysis_prompt(
    audio_master,
    source_language: str | None = None,
) -> str:
    """Build the complete cultural-analysis prompt."""
    return (
        SYSTEM_PROMPT.strip()
        + "\n\n"
        + USER_PROMPT_TEMPLATE.format(
            source_language=source_language or "mixed/unknown",
            segments=format_segments(audio_master),
        ).strip()
    )
