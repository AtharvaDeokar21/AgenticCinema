SEGMENT_ANALYSIS_SYSTEM_PROMPT = """
You are the Audio Agent's creator-voice Segment Analyser for a social-media
video production pipeline.

The attached audio is the creator's cleaned recording. Compare what is spoken
and how it is delivered against the supplied script beats, their timestamps,
expression/delivery guidance, and any Syncer timing information.

For every script beat, return exactly one decision:
- PASS: the line and delivery are acceptable.
- PASS_WITH_FIX: usable, but a small fix is recommended.
- RE_RECORD: the creator should record this beat again.

Check, where evidence is available:
1. missing lines;
2. lines spoken out of order;
3. ad-libs or extra speech — FLAG them, never delete them;
4. whether the segment lands in the expected timestamp slot / Syncer timing;
5. whether delivery matches the requested expression (for example, an
   energetic build should not be read flat, and a requested pause should not
   be rushed);
6. inconsistent microphone distance / room or level changes that materially
   affect continuity.

Do not rewrite the creator's words. Do not invent problems when the audio does
not provide enough evidence. Keep reasons concise and actionable.
""".strip()


def build_segment_analysis_prompt(script_json: str, sync_json: str) -> str:
    return f"""
{SEGMENT_ANALYSIS_SYSTEM_PROMPT}

SCRIPT BEATS (JSON):
{script_json}

SYNC REPORT (JSON):
{sync_json}

Return a structured report for the attached cleaned audio.
""".strip()


def build_tts_prompt(text: str, expression: str | None, pacing_tag: str | None = None) -> str:
    """Build a Gemini TTS prompt while preserving the exact spoken words."""

    tags: list[str] = []
    if expression and expression.strip():
        tags.append(expression.strip().strip("[]"))
    if pacing_tag:
        tags.append(pacing_tag.strip().strip("[]"))

    prefix = f"[{', '.join(tags)}] " if tags else ""
    return (
        "Perform the following narration naturally. Preserve the spoken words "
        "exactly; do not rewrite, summarize, or add words. Apply only the "
        "delivery guidance in the bracketed tags.\n\n"
        f"{prefix}{text}"
    )
