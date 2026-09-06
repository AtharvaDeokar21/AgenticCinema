"""
The small structural pass ClearanceCheck carries.

This is deterministic code, not a model call. Schema validation is already done
by Pydantic at construction; what is left is cross-references — every storyboard
shot pointing at a script beat that exists, every dub segment pointing at an
audio segment that exists.

Takes milliseconds. Run it before spending anything on Gemini or Parallel.
"""

from typing import List

from app.shared.models.project import ProjectState

# Floating-point timestamps come from several agents; compare with tolerance.
EPS = 0.05


def check_cross_references(state: ProjectState) -> List[str]:
    errors: List[str] = []

    beat_ids = {b.beat_id for b in state.script.beats} if state.script else set()

    # --- script internal consistency ---
    if state.script:
        for beat in state.script.beats:
            if beat.start_time >= beat.end_time:
                errors.append(
                    f"script: beat {beat.beat_id} has start_time "
                    f">= end_time ({beat.start_time} >= {beat.end_time})"
                )

        ordered = sorted(state.script.beats, key=lambda b: b.start_time)
        for prev, nxt in zip(ordered, ordered[1:]):
            if nxt.start_time + EPS < prev.end_time:
                errors.append(
                    f"script: beats {prev.beat_id} and {nxt.beat_id} overlap"
                )

    # --- storyboard -> script ---
    if state.storyboard:
        if not state.script:
            errors.append("storyboard: exists but no script is present")
        else:
            for shot in state.storyboard.shots:
                if shot.beat_id not in beat_ids:
                    errors.append(
                        f"storyboard: shot {shot.shot_id} references unknown "
                        f"beat_id '{shot.beat_id}'"
                    )
                if shot.start_time >= shot.end_time:
                    errors.append(
                        f"storyboard: shot {shot.shot_id} has start_time "
                        f">= end_time"
                    )

    # --- audio master internal consistency ---
    audio_segment_ids = set()
    if state.audio_master:
        duration = state.audio_master.duration

        for seg in state.audio_master.segments:
            audio_segment_ids.add(seg.segment_id)

            if seg.start_time >= seg.end_time:
                errors.append(
                    f"audio: segment {seg.segment_id} has start_time >= end_time"
                )

            if duration is not None and seg.end_time > duration + EPS:
                errors.append(
                    f"audio: segment {seg.segment_id} ends at {seg.end_time}, "
                    f"past master duration {duration}"
                )

    # --- sync report sanity ---
    if state.sync_report:
        for seg in state.sync_report.segments:
            if not 0.0 <= seg.confidence <= 1.0:
                errors.append(
                    f"sync: segment {seg.segment_id} confidence "
                    f"{seg.confidence} is outside 0..1"
                )

    # --- dub -> audio ---
    for track in state.dub_tracks:
        for seg in track.segments:
            if audio_segment_ids and seg.segment_id not in audio_segment_ids:
                errors.append(
                    f"dub[{track.language}]: segment '{seg.segment_id}' does "
                    "not exist in the audio master"
                )
            if not seg.localized_text.strip():
                errors.append(
                    f"dub[{track.language}]: segment '{seg.segment_id}' has "
                    "empty localized_text"
                )

    return errors