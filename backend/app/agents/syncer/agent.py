"""
Syncer Agent for Agentic Cinema — Layer 3.

Accepts a silent video, an ordered list of script beats, and a set of
audio clips matched by beat_id.  Uses the Gemini multimodal API to
visually ground each beat to the moment the creator's mouth begins
moving, then returns a SyncMap — the authoritative placement guide for
the editing stage.

This agent does NOT extend BaseAgent (per architecture spec for Layer 3)
and calls the Gemini API directly without ADK orchestration.

DEMO_MODE
----------
Set the environment variable DEMO_MODE=true to bypass all external API
calls and return a deterministic mock SyncMap.  Useful for offline demos
or CI environments where no GEMINI_API_KEY is available.
"""

import os
from pathlib import Path

from app.agents.syncer.schemas import AudioPlacement, SyncMap, SyncRequest
from app.agents.syncer.tools import (
    call_gemini_multimodal,
    prepare_video,
    resolve_clip_durations,
    upload_video_to_gemini,
)
from app.shared.tools.gemini.client import GeminiClient


class SyncerAgent:
    """Layer 3 Syncer Agent.

    Pipeline:
        1. Resolve missing audio clip durations via ffprobe.
        2. Check video for VFR; convert to CFR if needed.
        3. Upload the (possibly converted) video to the Gemini File API
           and wait until it is in ACTIVE state.
        4. Call Gemini multimodal with the video + script to produce a
           structured SyncMap.
        5. Delete the uploaded file from Gemini's servers (cleanup).
        6. Stamp ground-truth video metadata onto the returned SyncMap.

    Usage::

        agent = SyncerAgent()
        sync_map = await agent.run(request)
    """

    name = "syncer"

    def __init__(self) -> None:
        self.gemini = GeminiClient()

    async def run(self, request: SyncRequest) -> SyncMap:
        """Execute the full sync pipeline for a given SyncRequest.

        Set the environment variable DEMO_MODE=true to skip the live
        Gemini API call and return a deterministic mock SyncMap instead.

        Args:
            request: SyncRequest containing the video path, script beats,
                     and matched audio clips.

        Returns:
            SyncMap with one AudioPlacement per clip, stamped with the
            actual video path and metadata used during analysis.

        Raises:
            ValueError: If the source video has no detectable video stream.
            RuntimeError: If the Gemini File API upload fails or times out,
                          or if the model response cannot be parsed.
            subprocess.CalledProcessError: If ffprobe or ffmpeg fail.
        """

        # ------------------------------------------------------------------
        # DEMO_MODE circuit breaker
        # ------------------------------------------------------------------

        if os.getenv("DEMO_MODE", "").lower() == "true":
            print("[SyncerAgent] DEMO_MODE active — returning mock SyncMap")
            return self._mock_sync_map(request)

        print("\n" + "=" * 80)
        print("SYNCER AGENT — STARTING PIPELINE")
        print("=" * 80)
        print(f"  Video     : {request.video_path!r}")
        print(f"  Beats     : {len(request.script_beats)}")
        print(f"  Clips     : {len(request.audio_clips)}")
        print(f"  Target FPS: {request.target_fps}")
        print("=" * 80)

        # ------------------------------------------------------------------
        # Step 1: Resolve missing audio clip durations
        # ------------------------------------------------------------------

        print("\n[SyncerAgent] Step 1 — resolving audio clip durations …")

        resolved_clips = resolve_clip_durations(request.audio_clips)

        for clip in resolved_clips:
            dur_str = f"{clip.duration:.2f}s" if clip.duration is not None else "unknown"
            print(f"  {clip.beat_id!r}: {dur_str}")

        # Build a copy of the request with resolved durations so the prompt
        # formatter has accurate duration values for every clip.
        resolved_request = request.model_copy(
            update={"audio_clips": resolved_clips}
        )

        # ------------------------------------------------------------------
        # Step 2: VFR check / CFR conversion
        # ------------------------------------------------------------------

        print("\n[SyncerAgent] Step 2 — checking video frame rate …")

        video_path, was_converted, video_info = prepare_video(
            video_path=request.video_path,
            target_fps=request.target_fps,
        )

        if was_converted:
            print(f"[SyncerAgent] Using CFR copy: {video_path!r}")

        # ------------------------------------------------------------------
        # Step 3: Upload video to Gemini File API
        # ------------------------------------------------------------------

        print("\n[SyncerAgent] Step 3 — uploading video to Gemini …")

        file_ref = upload_video_to_gemini(
            client=self.gemini,
            video_path=video_path,
        )

        # ------------------------------------------------------------------
        # Step 4 & 5: Call model, then clean up regardless of outcome
        # ------------------------------------------------------------------

        print("\n[SyncerAgent] Step 4 — calling Gemini multimodal …")

        try:
            sync_map = call_gemini_multimodal(
                client=self.gemini,
                file_ref=file_ref,
                video_info=video_info,
                request=resolved_request,
            )
        finally:
            # Step 5: Always delete the uploaded file from Gemini's servers,
            # even if the model call raised an exception.
            print("\n[SyncerAgent] Step 5 — cleaning up Gemini file …")

            try:
                self.gemini.client.files.delete(name=file_ref.name)
                print(f"[SyncerAgent] Deleted: {file_ref.name!r}")
            except Exception as exc:  # noqa: BLE001
                # Deletion failure is non-fatal; log and continue.
                print(
                    f"[SyncerAgent] Warning — could not delete Gemini file "
                    f"{file_ref.name!r}: {exc}"
                )

        # ------------------------------------------------------------------
        # Step 6: Stamp ground-truth metadata from ffprobe onto the result
        # ------------------------------------------------------------------

        # Override fields that Gemini estimated from the prompt context with
        # the values we actually measured from the file.
        sync_map.video_path = video_path
        sync_map.was_vfr_converted = was_converted
        sync_map.video_fps = video_info.declared_fps

        if video_info.duration is not None:
            sync_map.video_duration = video_info.duration

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------

        print("\n" + "=" * 80)
        print("SYNCER AGENT — PIPELINE COMPLETE")
        print("=" * 80)
        print(f"  Status   : {sync_map.status!r}")
        print(f"  Placed   : {len(sync_map.placements)}")
        print(f"  Unplaced : {len(sync_map.unplaced_beat_ids)}")
        print(f"  VFR conv : {sync_map.was_vfr_converted}")
        print("=" * 80)
        print(sync_map.model_dump_json(indent=2))

        return sync_map

    # ------------------------------------------------------------------
    # DEMO_MODE helpers
    # ------------------------------------------------------------------

    def _mock_sync_map(self, request: SyncRequest) -> SyncMap:
        """Return a deterministic SyncMap for offline / demo use.

        Skips all ffprobe, ffmpeg, and Gemini API calls.  Every placement
        uses the script beat's expected start/end times and is labelled
        with a 'Fits well' pacing suggestion so both new fields pass
        Pydantic validation.

        Args:
            request: The original SyncRequest (used for beat/clip metadata).

        Returns:
            A fully populated SyncMap with mock data.
        """

        placements = []
        timeline_lines = []

        for beat, clip in zip(request.script_beats, request.audio_clips):
            start = beat.start_time
            end = beat.end_time

            placement = AudioPlacement(
                beat_id=beat.beat_id,
                audio_clip_path=clip.file_path,
                video_start_time=start,
                video_end_time=end,
                confidence=0.95,
                mouth_motion_detected=False,
                notes="DEMO_MODE: fallback to script timestamps",
                pacing_suggestion="Fits well",
            )
            placements.append(placement)

            # Build [MM:SS.mm - MM:SS.mm] -> Attach <file> (<pacing>) line
            def _fmt(t: float) -> str:
                mins = int(t) // 60
                secs = int(t) % 60
                cs = int(round((t - int(t)) * 100))
                return f"{mins:02d}:{secs:02d}.{cs:02d}"

            filename = Path(clip.file_path).name
            timeline_lines.append(
                f"[{_fmt(start)} - {_fmt(end)}] -> Attach {filename} (Fits well)"
            )

        video_duration = (
            request.script_beats[-1].end_time if request.script_beats else 0.0
        )

        return SyncMap(
            status="complete",
            video_path=request.video_path,
            video_duration=video_duration,
            video_fps=float(request.target_fps),
            was_vfr_converted=False,
            placements=placements,
            editor_timeline_text="\n".join(timeline_lines),
        )
