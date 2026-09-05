"""Audio Agent: creator-voice and AI-voice entry paths."""

import json
from pathlib import Path
from typing import Callable, Optional, TYPE_CHECKING

from app.agents.base import BaseAgent
from app.agents.audio.prompts import build_segment_analysis_prompt, build_tts_prompt
from app.agents.audio.schemas import (
    AudioInputMode,
    AudioRequest,
    AudioResult,
    GeneratedAudioSegment,
    SegmentAnalysisReport,
)
from app.shared.models.audio import AudioMaster
from app.shared.tools.audio.cleanup import clean_audio
from app.shared.tools.audio.tts import (
    GeminiTTSService,
    TTSService,
    assemble_timed_wav,
    get_wav_duration,
)
if TYPE_CHECKING:
    from app.shared.tools.gemini.client import GeminiClient
from app.shared.tools.media.ffmpeg import extract_audio


class AudioAgent(BaseAgent):
    """Coordinate deterministic audio work and Gemini audio reasoning."""

    name = "audio"
    ANALYSIS_MODEL = "gemini-3.7-flash"
    TTS_MODEL = "gemini-3.1-flash-tts-preview"
    DEFAULT_VOICE = "Kore"
    MAX_PACING_RETRIES = 1

    def __init__(
        self,
        extractor: Callable[[str, str], None] = extract_audio,
        cleaner: Callable[[str, str], None] = clean_audio,
        gemini: Optional["GeminiClient"] = None,
        tts: Optional[TTSService] = None,
    ) -> None:
        self.extractor = extractor
        self.cleaner = cleaner
        self.gemini = gemini
        self.tts = tts

    async def run(self, input_data: AudioRequest) -> AudioResult:
        if not isinstance(input_data, AudioRequest):
            raise TypeError("AudioAgent.run expects an AudioRequest")

        request = input_data
        video_path = Path(request.video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Audio source video not found: {video_path}")
        if not video_path.is_file():
            raise ValueError(f"Audio source path is not a file: {video_path}")

        if request.mode is AudioInputMode.CREATOR_VOICE:
            return await self._run_creator_voice(request)
        if request.mode is AudioInputMode.AI_VOICE:
            return await self._run_ai_voice(request)

        raise ValueError(f"Unsupported Audio input mode: {request.mode}")

    async def _run_creator_voice(self, request: AudioRequest) -> AudioResult:
        """Extract -> clean -> Gemini multimodal delivery analysis."""
        extracted_audio_path = self._derived_path(request.video_path, "extracted.wav")
        cleaned_audio_path = self._derived_path(request.video_path, "cleaned.wav")

        self.extractor(request.video_path, extracted_audio_path)
        self.cleaner(extracted_audio_path, cleaned_audio_path)

        if request.project_state.script is None:
            raise ValueError("Creator voice path requires ProjectState.script")
        if not request.project_state.script.beats:
            raise ValueError("Creator voice path requires at least one script beat")

        report = await self._analyse_creator_audio(cleaned_audio_path, request)
        audio_master = self._audio_master_from_file(cleaned_audio_path)
        audio_master.cleaned = True
        request.project_state.audio_master = audio_master

        return AudioResult(
            mode=AudioInputMode.CREATOR_VOICE,
            status="complete",
            source_video_path=request.video_path,
            extracted_audio_path=extracted_audio_path,
            cleaned_audio_path=cleaned_audio_path,
            segment_analysis=report,
            audio_master=audio_master,
            project_state=request.project_state,
        )

    async def _analyse_creator_audio(
        self,
        cleaned_audio_path: str,
        request: AudioRequest,
    ) -> SegmentAnalysisReport:
        script = request.project_state.script
        assert script is not None

        script_json = json.dumps(
            [beat.model_dump(mode="json") for beat in script.beats], indent=2
        )
        sync_json = json.dumps(
            request.project_state.sync_report.model_dump(mode="json")
            if request.project_state.sync_report
            else {"status": "not_available"},
            indent=2,
        )
        prompt = build_segment_analysis_prompt(script_json, sync_json)
        gemini = self._get_gemini()
        uploaded_audio = gemini.upload_file(cleaned_audio_path)
        result = gemini.generate_structured(
            prompt=[prompt, uploaded_audio],
            response_schema=SegmentAnalysisReport,
            model=self.ANALYSIS_MODEL,
        )
        if not isinstance(result, SegmentAnalysisReport):
            raise TypeError("Gemini returned an invalid SegmentAnalysisReport")
        return result

    async def _run_ai_voice(self, request: AudioRequest) -> AudioResult:
        """Generate speech beat-by-beat and place it on the script timeline."""
        script = request.project_state.script
        if script is None:
            raise ValueError("AI voice path requires ProjectState.script")
        if not script.beats:
            raise ValueError("AI voice path requires at least one script beat")

        tts = self.tts or GeminiTTSService(self._get_gemini())
        generated_segments: list[GeneratedAudioSegment] = []
        timed_inputs: list[tuple[str, float, float]] = []
        rewrite_required: list[str] = []

        for beat in script.beats:
            slot_duration = beat.end_time - beat.start_time
            if slot_duration <= 0:
                raise ValueError(
                    f"Script beat {beat.beat_id} has an invalid timestamp range"
                )

            beat_path = self._derived_path(
                request.video_path,
                f"tts_{beat.beat_id}.wav",
            )
            prompt = build_tts_prompt(
                beat.text,
                beat.expression or beat.audio_intent,
            )
            await tts.generate(
                prompt,
                beat_path,
                voice=self.DEFAULT_VOICE,
                model=self.TTS_MODEL,
            )
            duration = get_wav_duration(beat_path)
            pacing_adjusted = False

            # Never rewrite the script to solve a timing problem. First ask TTS
            # to change only the pacing while preserving the exact words.
            if duration > slot_duration:
                pacing_adjusted = True
                faster_prompt = build_tts_prompt(
                    beat.text,
                    beat.expression or beat.audio_intent,
                    pacing_tag=self._pacing_tag(duration, slot_duration),
                )
                await tts.generate(
                    faster_prompt,
                    beat_path,
                    voice=self.DEFAULT_VOICE,
                    model=self.TTS_MODEL,
                )
                duration = get_wav_duration(beat_path)

            within_slot = duration <= slot_duration
            rewrite = not within_slot
            if rewrite:
                rewrite_required.append(beat.beat_id)

            generated_segments.append(
                GeneratedAudioSegment(
                    beat_id=beat.beat_id,
                    start_time=beat.start_time,
                    end_time=beat.end_time,
                    generated_duration=duration,
                    within_slot=within_slot,
                    pacing_adjusted=pacing_adjusted,
                    rewrite_required=rewrite,
                    file_path=beat_path,
                )
            )
            timed_inputs.append((beat_path, beat.start_time, beat.end_time))

        final_audio_path = self._derived_path(request.video_path, "generated.wav")
        assemble_timed_wav(timed_inputs, final_audio_path)

        audio_master = self._audio_master_from_file(final_audio_path)
        audio_master.cleaned = False
        request.project_state.audio_master = audio_master

        status = "complete" if not rewrite_required else "complete_with_rewrite_required"
        return AudioResult(
            mode=AudioInputMode.AI_VOICE,
            status=status,
            source_video_path=request.video_path,
            generated_audio_path=final_audio_path,
            audio_master=audio_master,
            generated_segments=generated_segments,
            rewrite_required_beat_ids=rewrite_required,
            project_state=request.project_state,
        )

    @staticmethod
    def _pacing_tag(duration: float, slot_duration: float) -> str:
        ratio = duration / slot_duration
        if ratio >= 1.75:
            return "very fast"
        if ratio >= 1.35:
            return "faster"
        return "slightly faster"

    def _get_gemini(self):
        if self.gemini is None:
            from app.shared.tools.gemini.client import GeminiClient

            self.gemini = GeminiClient()
        return self.gemini

    @staticmethod
    def _derived_path(video_path: str, suffix: str) -> str:
        path = Path(video_path)
        return str(path.with_name(f"{path.stem}_{suffix}"))

    @staticmethod
    def _audio_master_from_file(path: str) -> AudioMaster:
        return AudioMaster(file_path=path, cleaned=False)
