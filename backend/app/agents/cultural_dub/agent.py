"""Cultural Dub Agent: analysis -> research -> transcreation -> safety -> TTS."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional
from unittest import result

from app.agents.base import BaseAgent
from app.agents.cultural_dub.prompts import build_cultural_analysis_prompt
from app.agents.cultural_dub.research import CulturalDubResearcher
from app.agents.cultural_dub.schemas import (
    CulturalAnalysis,
    CulturalDubResult,
    CulturalDubTrackResult,
    DubRequest,
    LocaleLocalizationBrief,
    LocaleMonitorConfig,
    ReviewSeverity,
)
from app.agents.cultural_dub.transcreation import CulturalDubTranscreator
from app.shared.tools.gemini.client import GeminiClient
from app.shared.tools.parallel.monitor import ParallelMonitor
from app.shared.tools.parallel.task import ParallelTask
import os


class CulturalDubAgent(BaseAgent):
    """Localize timestamped creator dialogue and generate target-language WAV tracks."""

    name = "cultural_dub"
    ANALYSIS_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.7-flash")
    LOCALE_TASK_PROCESSOR = "base"

    def __init__(
        self,
        gemini: Optional[GeminiClient] = None,
        researcher: Optional[CulturalDubResearcher] = None,
        task: Optional[ParallelTask] = None,
        monitor: Optional[ParallelMonitor] = None,
        transcreator: Optional[CulturalDubTranscreator] = None,
    ) -> None:
        self.gemini = gemini or GeminiClient()
        self.researcher = researcher or CulturalDubResearcher()
        self.task = task or ParallelTask()
        self.monitor = monitor or ParallelMonitor()
        self.transcreator = transcreator or CulturalDubTranscreator(self.gemini)

    async def run(self, request: DubRequest) -> CulturalDubResult:
        if not request.audio_master.segments:
            raise ValueError("Cultural Dub requires timestamped AudioMaster segments.")

        if request.creator_voice and not request.creator_voice_consent_record:
            raise ValueError(
                "creator_voice=True requires creator_voice_consent_record."
            )

        analysis = self._analyse(request)
        result = CulturalDubResult(project_id=request.project_id)

        for locale in request.target_locales:
            brief = await self._locale_brief(locale, result)
            if brief is not None:
                result.locale_briefs.append(brief)
            research = await self.researcher.research(
                spans=analysis.spans,
                target_language=locale.language,
                target_geography=locale.geography,
            )

            output_path = self._output_path(request, locale)
            try:
                segments = await self.transcreator.run_with_audio(
                    audio_master=request.audio_master,
                    cultural_analysis=analysis,
                    research=research,
                    target_locale=locale,
                    register=request.register,
                    output_path=output_path,
                    max_duration_overrun_seconds=request.max_duration_overrun_seconds,
                    brief=brief,
                    voice=getattr(self.transcreator, "DEFAULT_VOICE", "Kore"),
                ) if request.generate_audio else self.transcreator.run(
                    audio_master=request.audio_master,
                    cultural_analysis=analysis,
                    research=research,
                    target_locale=locale,
                    register=request.register,
                    brief=brief,
                )
            except Exception as exc:  # noqa: BLE001
                result.degraded_reasons.append(
                    f"Localization failed for {locale.locale}: {exc}"
                )
                continue

            track = CulturalDubTrackResult(
                language=locale.language,
                geography=locale.geography,
                segments=segments,
                audio_path=output_path if request.generate_audio else None,
            )
            result.tracks.append(track)
            if request.generate_audio and any(s.review_flags for s in segments):
                result.degraded_reasons.append(
                    f"{locale.locale} contains human-review safety flags; audio must not be published until reviewed."
                )
            result.localization_notes.extend(
                getattr(self.transcreator, "last_candidates", [])
            )
            result.review_flags.extend(
                flag for segment in segments for flag in segment.review_flags
            )

        return result

    def _analyse(self, request: DubRequest) -> CulturalAnalysis:
        prompt = build_cultural_analysis_prompt(
            audio_master=request.audio_master,
            source_language=request.source_language,
        )
        analysis = self.gemini.generate_structured(
            prompt=prompt,
            response_schema=CulturalAnalysis,
            model=self.ANALYSIS_MODEL,
        )
        if not isinstance(analysis, CulturalAnalysis):
            raise TypeError("Gemini returned an invalid CulturalAnalysis")
        return analysis

    async def _locale_brief(self, locale, result: CulturalDubResult) -> Optional[LocaleLocalizationBrief]:
        query = (
            f"{locale.language} {locale.geography} creator-content localization "
            "register slang humour taboo topics conventions"
        )
        try:
            monitor_response = await self.monitor.create(
                query=query,
                frequency="1w",
                metadata={
                    "agent": self.name,
                    "language": locale.language,
                    "geography": locale.geography,
                },
            )
            monitor_id = _extract_id(monitor_response)
            result.monitor_configs.append(
                LocaleMonitorConfig(
                    language=locale.language,
                    geography=locale.geography,
                    query=query,
                    frequency="1w",
                    monitor_id=monitor_id,
                )
            )
        except Exception as exc:  # noqa: BLE001
            result.degraded_reasons.append(
                f"Locale monitor setup failed for {locale.locale}: {exc}"
            )

        task_prompt = f"""
            Prepare a concise localization brief for creator dialogue targeting
            {locale.language} in {locale.geography}.

            Cover:
            - natural {locale.language} register norms
            - humour conventions
            - current slang guidance
            - taboo or sensitive topics
            - localization rules
            - terms that should normally be retained

            Return only the localization guidance fields:
            language, geography, register_guidance, humour_conventions,
            slang_guidance, taboo_topics, localization_rules, retain_terms.

            Do not return an evidence field. The task system's own research basis
            will provide supporting web evidence.
            """.strip()
        try:
            response = await self.task.run(
                task=task_prompt,
                processor=self.LOCALE_TASK_PROCESSOR,
                task_spec=_locale_brief_task_spec(),
            )
            output = response.get("output") if isinstance(response, dict) else response
            print("\n=== PARALLEL TASK RAW OUTPUT ===")
            print(repr(response))
            print("=== PARALLEL TASK OUTPUT ===")
            print(repr(output))
            brief = _parse_brief(output, locale.language, locale.geography)
            if brief is None:
                raise ValueError("Parallel Task returned no usable localization brief")
            return brief
        except Exception as exc:  # noqa: BLE001
            result.degraded_reasons.append(
                f"Locale brief research failed for {locale.locale}: {exc}"
            )
            return None

    @staticmethod
    def _output_path(request: DubRequest, locale) -> str:
        if request.audio_master.file_path:
            base = Path(request.audio_master.file_path)
            root = base.parent / "cultural_dub" / locale.locale
        else:
            root = Path("outputs") / "cultural_dub" / locale.locale
        return str(root / "dubbed_audio.wav")


def _locale_brief_task_spec() -> dict[str, Any]:
    return {
        "output_schema": {
            "type": "json",
            "json_schema": {
                "type": "object",
                "properties": {
                    "language": {"type": "string"},
                    "geography": {"type": "string"},
                    "register_guidance": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "humour_conventions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "slang_guidance": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "taboo_topics": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "localization_rules": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "retain_terms": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "language",
                    "geography",
                    "register_guidance",
                    "humour_conventions",
                    "slang_guidance",
                    "taboo_topics",
                    "localization_rules",
                    "retain_terms",
                    "evidence",
                ],
                "additionalProperties": False,
            },
        }
    }

def _extract_id(value: Any) -> Optional[str]:
    if isinstance(value, dict):
        for key in ("monitor_id", "id"):
            if value.get(key):
                return str(value[key])
        monitor = value.get("monitor")
        if isinstance(monitor, dict):
            return _extract_id(monitor)
    return None


def _parse_brief(
    value: Any,
    language: str,
    geography: str,
) -> Optional[LocaleLocalizationBrief]:
    if value is None:
        return None

    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None

    if isinstance(value, dict) and "output" in value:
        return _parse_brief(value["output"], language, geography)

    if isinstance(value, dict) and "content" in value and len(value) == 1:
        return _parse_brief(value["content"], language, geography)

    if not isinstance(value, dict):
        return None

    value = dict(value)

    value["language"] = language

    value["geography"] = geography

    value.pop("evidence", None)

    try:
        return LocaleLocalizationBrief.model_validate(value)
    except Exception as exc:
        print("LocaleLocalizationBrief validation failed:", exc)
        print("Candidate brief:", value)
        return None
