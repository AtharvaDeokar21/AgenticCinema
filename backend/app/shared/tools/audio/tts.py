"""Shared Gemini TTS utilities for Agentic Cinema."""

import base64
import wave
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence


class TTSService:
    """Shared text-to-speech interface."""

    async def generate(
        self,
        text: str,
        output_path: str,
        **kwargs: Any,
    ) -> str:
        raise NotImplementedError


class GeminiTTSService(TTSService):
    """Gemini 3.1 Flash TTS adapter.

    The service returns a standard 24 kHz, mono, 16-bit WAV file. Gemini's
    TTS model returns raw PCM audio, so wrapping it as WAV is a deterministic
    local operation rather than an LLM decision.
    """

    MODEL = "gemini-3.1-flash-tts-preview"
    SAMPLE_RATE = 24_000
    CHANNELS = 1
    SAMPLE_WIDTH = 2

    def __init__(self, gemini_client: Optional[Any] = None) -> None:
        self._gemini_client = gemini_client

    async def generate(
        self,
        text: str,
        output_path: str,
        *,
        voice: str = "Kore",
        model: str = MODEL,
        **_: Any,
    ) -> str:
        if not text.strip():
            raise ValueError("TTS text must not be empty")

        if self._gemini_client is None:
            from app.shared.tools.gemini.client import GeminiClient

            client = GeminiClient()
        else:
            client = self._gemini_client

        pcm = client.generate_tts(text=text, voice=voice, model=model)
        if not isinstance(pcm, bytes) or not pcm:
            raise ValueError("Gemini TTS returned no audio bytes")

        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._write_wav(destination, pcm)
        return str(destination)

    @classmethod
    def _write_wav(cls, path: Path, pcm: bytes) -> None:
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(cls.CHANNELS)
            wf.setsampwidth(cls.SAMPLE_WIDTH)
            wf.setframerate(cls.SAMPLE_RATE)
            wf.writeframes(pcm)


def get_wav_duration(file_path: str) -> float:
    """Return WAV duration in seconds."""

    with wave.open(file_path, "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        if rate <= 0:
            raise ValueError(f"Invalid WAV sample rate: {rate}")
        return frames / rate


def assemble_timed_wav(
    segments: Sequence[tuple[str, float, float]],
    output_path: str,
    *,
    sample_rate: int = GeminiTTSService.SAMPLE_RATE,
    channels: int = GeminiTTSService.CHANNELS,
    sample_width: int = GeminiTTSService.SAMPLE_WIDTH,
) -> str:
    """Place per-beat WAVs on a shared timeline and fill gaps with silence.

    ``segments`` contains ``(wav_path, start_time, end_time)``. Audio is
    clipped to its requested beat slot only when necessary; the Audio Agent
    is expected to flag an overlong generation before calling this function.
    """

    if not segments:
        raise ValueError("At least one generated audio segment is required")

    ordered = sorted(segments, key=lambda item: item[1])
    final_end = max(end for _, _, end in ordered)
    total_frames = max(0, round(final_end * sample_rate))
    silence = b"\x00" * channels * sample_width
    output = bytearray(silence * total_frames)

    for wav_path, start_time, end_time in ordered:
        with wave.open(wav_path, "rb") as wf:
            if wf.getnchannels() != channels:
                raise ValueError(f"Unexpected channel count in {wav_path}")
            if wf.getsampwidth() != sample_width:
                raise ValueError(f"Unexpected sample width in {wav_path}")
            if wf.getframerate() != sample_rate:
                raise ValueError(f"Unexpected sample rate in {wav_path}")
            pcm = wf.readframes(wf.getnframes())

        start_frame = max(0, round(start_time * sample_rate))
        slot_frames = max(0, round((end_time - start_time) * sample_rate))
        max_bytes = slot_frames * channels * sample_width
        pcm = pcm[:max_bytes]
        end_frame = min(total_frames, start_frame + len(pcm) // (channels * sample_width))
        if end_frame <= start_frame:
            continue
        byte_start = start_frame * channels * sample_width
        byte_end = end_frame * channels * sample_width
        output[byte_start:byte_end] = pcm[: byte_end - byte_start]

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destination), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(output)
    return str(destination)
