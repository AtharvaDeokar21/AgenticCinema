"""Target-locale transcreation, safety review, and TTS for Cultural Dub."""
from __future__ import annotations

import json
from pathlib import Path
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
from app.shared.tools.audio.tts import (
    GeminiTTSService,
    TTSService,
    assemble_timed_wav,
    get_wav_duration,
)
from app.shared.tools.gemini.client import GeminiClient

from .transcreation_prompts import (
    SAFETY_SYSTEM_PROMPT,
    SAFETY_USER_TEMPLATE,
    TRANSCREATION_SYSTEM_PROMPT,
    TRANSCREATION_USER_TEMPLATE,
)


class TranscreationResponse:
    def __init__(self, candidates: list[LocalizationCandidate]):
        self.candidates = candidates


class SafetyResponse:
    def __init__(self, flags: list[ReviewFlag]):
        self.flags = flags


class CulturalDubTranscreator:
    """Generate localized dialogue, safety-review it, and synthesize WAV audio."""

    TTS_MODEL = GeminiTTSService.MODEL
    DEFAULT_VOICE = "Kore"
    MAX_TTS_REWRITES = 1

    def __init__(
        self,
        gemini: Optional[GeminiClient] = None,
        tts: Optional[TTSService] = None,
    ) -> None:
        self.gemini = gemini or GeminiClient()
        self.tts = tts or GeminiTTSService(self.gemini)
        self.last_candidates: list[LocalizationCandidate] = []

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
        return TranscreationResponse(_coerce_candidates(parsed))

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
        return SafetyResponse(_coerce_flags(parsed))

    def run(
        self,
        audio_master: Any,
        cultural_analysis: CulturalAnalysis,
        research: Iterable[CulturalSpanResearch],
        target_locale: TargetLocale,
        register: TargetRegister,
        brief: Optional[LocaleLocalizationBrief] = None,
    ) -> list[DubSegmentResult]:
        """Transcreate and perform the mandatory safety review."""
        transcreated = self.transcreate(
            audio_master, cultural_analysis, research, target_locale, register, brief
        )
        self.last_candidates = list(transcreated.candidates)
        flags = self.safety_review(
            transcreated.candidates, target_locale, register, brief
        ).flags
        return self._build_segment_results(audio_master, cultural_analysis, transcreated.candidates, flags)

    async def run_with_audio(
        self,
        audio_master: Any,
        cultural_analysis: CulturalAnalysis,
        research: Iterable[CulturalSpanResearch],
        target_locale: TargetLocale,
        register: TargetRegister,
        output_path: str,
        max_duration_overrun_seconds: float = 0.15,
        brief: Optional[LocaleLocalizationBrief] = None,
        voice: str = DEFAULT_VOICE,
    ) -> list[DubSegmentResult]:
        """Transcreate, safety-review, TTS each segment, and assemble a WAV track."""
        transcreated = self.transcreate(
            audio_master, cultural_analysis, research, target_locale, register, brief
        )
        self.last_candidates = list(transcreated.candidates)
        flags = self.safety_review(
            transcreated.candidates, target_locale, register, brief
        ).flags

        flag_by_id: dict[str, list[ReviewFlag]] = {}
        for flag in flags:
            flag_by_id.setdefault(flag.segment_id, []).append(flag)

        spans_by_id: dict[str, list[Any]] = {}
        for span in cultural_analysis.spans:
            spans_by_id.setdefault(span.segment_id, []).append(span)

        source_by_id = {s.segment_id: s for s in audio_master.segments}
        results: list[DubSegmentResult] = []
        timed_inputs: list[tuple[str, float, float]] = []
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        for candidate in transcreated.candidates:
            source = source_by_id.get(candidate.segment_id)
            if source is None:
                continue
            slot = source.end_time - source.start_time
            if slot <= 0:
                raise ValueError(f"Invalid source slot for segment {source.segment_id}")

            segment_path = output_dir / f"{Path(output_path).stem}_{candidate.segment_id}.wav"
            text = candidate.localized_text
            text, duration = await self._synthesize_with_duration_retry(
                text=text,
                segment_path=str(segment_path),
                target_language=target_locale.language,
                target_geography=target_locale.geography,
                register=register,
                slot=slot,
                max_overrun=max_duration_overrun_seconds,
                voice=voice,
                source_text=candidate.source_text,
            )

            results.append(
                DubSegmentResult(
                    segment_id=candidate.segment_id,
                    source_text=candidate.source_text,
                    localized_text=text,
                    language=target_locale.language,
                    geography=target_locale.geography,
                    source_start_time=source.start_time,
                    source_end_time=source.end_time,
                    target_duration_seconds=duration,
                    audio_path=str(segment_path),
                    cultural_spans=spans_by_id.get(candidate.segment_id, []),
                    review_flags=flag_by_id.get(candidate.segment_id, []),
                )
            )
            timed_inputs.append((str(segment_path), source.start_time, source.end_time))

        if not results:
            raise ValueError("No valid localized segments were produced")
        assemble_timed_wav(timed_inputs, output_path)
        return results

    async def _synthesize_with_duration_retry(
        self,
        *,
        text: str,
        segment_path: str,
        target_language: str,
        target_geography: str,
        register: TargetRegister,
        slot: float,
        max_overrun: float,
        voice: str,
        source_text: str,
    ) -> tuple[str, float]:
        current_text = text
        for attempt in range(self.MAX_TTS_REWRITES + 1):
            prompt = self._tts_prompt(current_text, target_language, target_geography, register)
            await self.tts.generate(
                prompt,
                segment_path,
                voice=voice,
                model=self.TTS_MODEL,
            )
            duration = get_wav_duration(segment_path)
            if duration <= slot + max_overrun:
                return current_text, duration
            if attempt >= self.MAX_TTS_REWRITES:
                return current_text, duration
            current_text = self._rewrite_for_duration(
                source_text=source_text,
                localized_text=current_text,
                target_language=target_language,
                target_geography=target_geography,
                register=register,
                target_duration=slot,
            )
        raise AssertionError("unreachable")

    def _rewrite_for_duration(
        self,
        *,
        source_text: str,
        localized_text: str,
        target_language: str,
        target_geography: str,
        register: TargetRegister,
        target_duration: float,
    ) -> str:
        prompt = f"""
Rewrite the localized dialogue below more concisely so spoken TTS fits within
{target_duration:.3f} seconds. Preserve meaning, intent, humour, register,
and target-locale naturalness. Do not solve the problem by recommending faster
speech. Return ONLY the replacement dialogue text.

TARGET LANGUAGE: {target_language}
TARGET GEOGRAPHY: {target_geography}
REGISTER: {register.value}
SOURCE: {source_text}
CURRENT LOCALIZATION: {localized_text}
""".strip()
        parsed = self.gemini.generate(prompt)
        value = getattr(parsed, "text", None)
        if not value:
            raise ValueError("Gemini returned no duration-constrained rewrite")
        return value.strip()

    @staticmethod
    def _tts_prompt(text: str, language: str, geography: str, register: TargetRegister) -> str:
        return (
            f"Speak the following text naturally in {language} for {geography}. "
            f"Use a {register.value} delivery. Preserve the exact words; do not translate. "
            f"Text: {text}"
        )

    @staticmethod
    def _build_segment_results(audio_master, cultural_analysis, candidates, flags):
        flags_by_segment: dict[str, list[ReviewFlag]] = {}
        for flag in flags:
            flags_by_segment.setdefault(flag.segment_id, []).append(flag)
        source_by_id = {s.segment_id: s for s in audio_master.segments}
        spans_by_id: dict[str, list[Any]] = {}
        for span in cultural_analysis.spans:
            spans_by_id.setdefault(span.segment_id, []).append(span)
        results = []
        for candidate in candidates:
            source = source_by_id.get(candidate.segment_id)
            if source is None:
                continue
            results.append(
                DubSegmentResult(
                    segment_id=candidate.segment_id,
                    source_text=candidate.source_text,
                    localized_text=candidate.localized_text,
                    language=candidate.language,
                    geography=candidate.geography,
                    source_start_time=source.start_time,
                    source_end_time=source.end_time,
                    target_duration_seconds=source.end_time - source.start_time,
                    cultural_spans=spans_by_id.get(candidate.segment_id, []),
                    review_flags=flags_by_segment.get(candidate.segment_id, []),
                )
            )
        return results


def _duration_annotated_segments(audio_master: Any) -> str:
    lines = []
    for segment in audio_master.segments:
        duration = segment.end_time - segment.start_time
        lines.append(
            f"SEGMENT ID: {segment.segment_id}\n"
            f"TIME: {segment.start_time:.3f}-{segment.end_time:.3f}\n"
            f"TARGET DURATION BUDGET: {duration:.3f} seconds\n"
            f"TRANSCRIPT: {segment.transcript}"
        )
    return "\n\n".join(lines) or "No transcript segments supplied."


def _dump(value: Any) -> str:
    if value is None:
        return "None"
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    elif isinstance(value, list):
        value = [item.model_dump() if hasattr(item, "model_dump") else item for item in value]
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _coerce_candidates(parsed: Any) -> list[LocalizationCandidate]:
    if parsed is None:
        return []
    if isinstance(parsed, list):
        return [item if isinstance(item, LocalizationCandidate) else LocalizationCandidate.model_validate(item) for item in parsed]
    if isinstance(parsed, Mapping) and "candidates" in parsed:
        return _coerce_candidates(parsed["candidates"])
    return [LocalizationCandidate.model_validate(parsed)]


def _coerce_flags(parsed: Any) -> list[ReviewFlag]:
    if parsed is None:
        return []
    if isinstance(parsed, list):
        return [item if isinstance(item, ReviewFlag) else ReviewFlag.model_validate(item) for item in parsed]
    if isinstance(parsed, Mapping) and "flags" in parsed:
        return _coerce_flags(parsed["flags"])
    return [ReviewFlag.model_validate(parsed)]
