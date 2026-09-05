"""Target-language transcreation for the Cultural Dub Agent."""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping, Optional

from app.agents.cultural_dub.prompts import format_segments
from app.agents.cultural_dub.schemas import (
    CulturalAnalysis,
    CulturalSpanResearch,
    DubSegmentResult,
    LocaleLocalizationBrief,
    LocalizationCandidate,
    ReviewFlag,
    TargetLocale,
    TargetRegister,
)
from app.shared.tools.gemini.client import GeminiClient

from .transcreation_prompts import (
    SAFETY_SYSTEM_PROMPT,
    SAFETY_USER_TEMPLATE,
    TRANSCREATION_SYSTEM_PROMPT,
    TRANSCREATION_USER_TEMPLATE,
)


class TranscreationResponse:
    """Structured container returned by the transcreation pass."""

    def __init__(self, candidates: list[LocalizationCandidate]):
        self.candidates = candidates


class SafetyResponse:
    """Structured container returned by the target-locale safety pass."""

    def __init__(self, flags: list[ReviewFlag]):
        self.flags = flags


class CulturalDubTranscreator:
    """Generate and safety-review localized dialogue without generating audio."""

    def __init__(self, gemini: Optional[GeminiClient] = None):
        self.gemini = gemini or GeminiClient()

    def transcreate(
        self,
        audio_master: Any,
        cultural_analysis: CulturalAnalysis,
        research: Iterable[CulturalSpanResearch],
        target_locale: TargetLocale,
        register: TargetRegister,
        brief: Optional[LocaleLocalizationBrief] = None,
    ) -> TranscreationResponse:
        research_list = list(research)
        prompt = TRANSCREATION_SYSTEM_PROMPT.strip() + "\n\n" + TRANSCREATION_USER_TEMPLATE.format(
            language=target_locale.language,
            geography=target_locale.geography,
            register=register.value,
            brief=_dump(brief),
            analysis=_dump(cultural_analysis),
            research=_dump(research_list),
            segments=_duration_annotated_segments(audio_master),
        ).strip()

        parsed = self.gemini.generate_structured(
            prompt=prompt,
            response_schema=list[LocalizationCandidate],
        )
        candidates = _coerce_candidates(parsed)
        return TranscreationResponse(candidates=candidates)

    def safety_review(
        self,
        candidates: Iterable[LocalizationCandidate],
        target_locale: TargetLocale,
        register: TargetRegister,
        brief: Optional[LocaleLocalizationBrief] = None,
    ) -> SafetyResponse:
        candidates_list = list(candidates)
        source_and_proposed = "\n\n".join(
            f"SEGMENT ID: {candidate.segment_id}\n"
            f"SOURCE: {candidate.source_text}\n"
            f"PROPOSED: {candidate.localized_text}"
            for candidate in candidates_list
        )

        prompt = SAFETY_SYSTEM_PROMPT.strip() + "\n\n" + SAFETY_USER_TEMPLATE.format(
            language=target_locale.language,
            geography=target_locale.geography,
            register=register.value,
            brief=_dump(brief),
            segments=source_and_proposed or "No candidates supplied.",
        ).strip()

        parsed = self.gemini.generate_structured(
            prompt=prompt,
            response_schema=list[ReviewFlag],
        )
        flags = _coerce_flags(parsed)
        return SafetyResponse(flags=flags)

    def run(
        self,
        audio_master: Any,
        cultural_analysis: CulturalAnalysis,
        research: Iterable[CulturalSpanResearch],
        target_locale: TargetLocale,
        register: TargetRegister,
        brief: Optional[LocaleLocalizationBrief] = None,
    ) -> list[DubSegmentResult]:
        """Transcreate, run the mandatory safety review, and attach flags."""
        transcreated = self.transcreate(
            audio_master=audio_master,
            cultural_analysis=cultural_analysis,
            research=research,
            target_locale=target_locale,
            register=register,
            brief=brief,
        )
        flags = self.safety_review(
            candidates=transcreated.candidates,
            target_locale=target_locale,
            register=register,
            brief=brief,
        ).flags

        flags_by_segment: dict[str, list[ReviewFlag]] = {}
        for flag in flags:
            flags_by_segment.setdefault(flag.segment_id, []).append(flag)

        source_by_id = {
            segment.segment_id: segment
            for segment in audio_master.segments
        }

        spans_by_id: dict[str, list[Any]] = {}
        for span in cultural_analysis.spans:
            spans_by_id.setdefault(span.segment_id, []).append(span)

        results = []
        for candidate in transcreated.candidates:
            source = source_by_id.get(candidate.segment_id)
            if source is None:
                continue

            candidate_flags = flags_by_segment.get(candidate.segment_id, [])
            results.append(
                DubSegmentResult(
                    segment_id=candidate.segment_id,
                    source_text=candidate.source_text,
                    localized_text=candidate.localized_text,
                    language=candidate.language,
                    geography=candidate.geography,
                    source_start_time=source.start_time,
                    source_end_time=source.end_time,
                    target_duration_seconds=getattr(
                        candidate, "target_duration_seconds", None
                    ),
                    cultural_spans=spans_by_id.get(candidate.segment_id, []),
                    review_flags=candidate_flags,
                )
            )

        return results


def _duration_annotated_segments(audio_master: Any) -> str:
    """Add explicit target-duration slots without changing the source model."""
    sections = []
    for segment in audio_master.segments:
        duration = max(0.0, segment.end_time - segment.start_time)
        sections.append(
            f"SEGMENT ID: {segment.segment_id}\n"
            f"SOURCE TIME: {segment.start_time:.3f}-{segment.end_time:.3f}\n"
            f"TARGET DURATION BUDGET: {duration:.3f} seconds\n"
            f"TRANSCRIPT: {segment.transcript}"
        )
    return "\n\n".join(sections) or "No transcript segments supplied."


def _dump(value: Any) -> str:
    """Serialize Pydantic models/lists for prompt context."""
    if value is None:
        return "None"
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    elif isinstance(value, list):
        value = [
            item.model_dump() if hasattr(item, "model_dump") else item
            for item in value
        ]
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _coerce_candidates(parsed: Any) -> list[LocalizationCandidate]:
    if parsed is None:
        return []
    if isinstance(parsed, list):
        return [
            item if isinstance(item, LocalizationCandidate)
            else LocalizationCandidate.model_validate(item)
            for item in parsed
        ]
    if isinstance(parsed, Mapping) and "candidates" in parsed:
        return _coerce_candidates(parsed["candidates"])
    return [LocalizationCandidate.model_validate(parsed)]


def _coerce_flags(parsed: Any) -> list[ReviewFlag]:
    if parsed is None:
        return []
    if isinstance(parsed, list):
        return [
            item if isinstance(item, ReviewFlag)
            else ReviewFlag.model_validate(item)
            for item in parsed
        ]
    if isinstance(parsed, Mapping) and "flags" in parsed:
        return _coerce_flags(parsed["flags"])
    return [ReviewFlag.model_validate(parsed)]
