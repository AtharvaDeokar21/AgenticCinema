"""
Gemini prompt templates for the Syncer Agent.

These prompts drive the multimodal visual-to-script alignment call.
The agent uploads the silent video alongside the script beats and
asks Gemini to identify the timestamp at which the creator's mouth
begins moving for each beat, returning a structured SyncMap.
"""

# ---------------------------------------------------------------------------
# System prompt — establishes the agent's role and output rules
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are the Syncer Agent for Agentic Cinema.

Your job is to analyse a SILENT video of a creator and a written script,
then produce a precise timing map that tells an editor exactly where on the
video timeline each audio clip should be placed.

You have been given:
1. A silent video in which the creator performs the script without audio.
2. A list of script beats — ordered segments of the script with their
   expected start and end timestamps.
3. A list of audio clips, each matched to a script beat by beat_id.

Your primary task:
  For every script beat, find the exact video timestamp (in seconds) at
  which the creator's MOUTH BEGINS TO MOVE for that beat. This is the
  video_start_time for the corresponding audio placement.

Rules you MUST follow:

1. Watch the video carefully.  Identify the creator's face and track
   lip/mouth movement throughout.

2. For each beat (in order), find the first frame where the mouth clearly
   begins to open for that segment of dialogue.  Report this as
   video_start_time.

3. Compute video_end_time as:
     video_start_time + (audio clip duration from the beat context provided)
   If no duration is available, use (beat.end_time - beat.start_time) from
   the script as a fallback estimate.

4. Set mouth_motion_detected = true only when you can clearly see lip
   movement at that timestamp.  If the face is occluded, cut away, or the
   mouth motion is ambiguous, set mouth_motion_detected = false and fall back
   to the beat's expected start_time as video_start_time.

5. Set confidence as a float 0.0–1.0 reflecting how certain you are about
   the placement.  If confidence < 0.5, add a note explaining why.

6. If you cannot place a beat at all (e.g. the creator never appears
   on-screen during that window), add the beat_id to unplaced_beat_ids
   and do NOT include it in placements.

7. Set status to:
   - "complete"  — all beats were placed with confidence >= 0.5
   - "partial"   — some beats are in unplaced_beat_ids
   - "failed"    — no beats could be placed

8. Populate the top-level notes list with any observations about overall
   sync quality (e.g. "Creator left frame at 00:45", "Jump cut between
   beats 3 and 4 makes alignment uncertain").

9. Do NOT invent timestamps.  Only report timestamps you can visually ground
   in the video content.

10. The output must be valid JSON matching the SyncMap schema exactly.
    Do not add fields that are not in the schema.
"""


# ---------------------------------------------------------------------------
# User prompt template — filled in per-request at runtime
# ---------------------------------------------------------------------------

USER_PROMPT_TEMPLATE = """
Analyse the attached silent video and produce a SyncMap for the following
script beats and audio clips.

VIDEO METADATA:
  Duration  : {video_duration:.2f} seconds
  Frame Rate : {video_fps:.2f} fps
  Path       : {video_path}

SCRIPT BEATS (ordered):
{script_beats_block}

AUDIO CLIPS (matched by beat_id):
{audio_clips_block}

Instructions:
  - For each audio clip, identify the video timestamp where the creator's
    mouth begins moving for that beat.
  - Follow all rules in your system instructions.
  - Return only the SyncMap JSON object — nothing else.
"""


# ---------------------------------------------------------------------------
# Helper to format the beats block inside the user prompt
# ---------------------------------------------------------------------------

def format_script_beats_block(script_beats) -> str:
    """Render script beats as a numbered text block for the prompt.

    Args:
        script_beats: Iterable of ScriptBeat objects (or dicts with the
                      same fields).

    Returns:
        A multi-line string with one beat per entry.
    """

    lines = []

    for i, beat in enumerate(script_beats, start=1):
        # Support both Pydantic models and plain dicts
        if hasattr(beat, "beat_id"):
            beat_id = beat.beat_id
            start = beat.start_time
            end = beat.end_time
            text = beat.text
        else:
            beat_id = beat["beat_id"]
            start = beat["start_time"]
            end = beat["end_time"]
            text = beat["text"]

        lines.append(
            f"  [{i}] beat_id={beat_id!r}  "
            f"expected_window={start:.2f}s–{end:.2f}s\n"
            f"      text: {text}"
        )

    return "\n".join(lines)


def format_audio_clips_block(audio_clips) -> str:
    """Render audio clips as a text block for the prompt.

    Args:
        audio_clips: Iterable of AudioClip objects (or dicts).

    Returns:
        A multi-line string with one clip per entry.
    """

    lines = []

    for clip in audio_clips:
        if hasattr(clip, "beat_id"):
            beat_id = clip.beat_id
            path = clip.file_path
            duration = clip.duration
        else:
            beat_id = clip["beat_id"]
            path = clip["file_path"]
            duration = clip.get("duration")

        dur_str = f"{duration:.2f}s" if duration is not None else "unknown"
        lines.append(
            f"  beat_id={beat_id!r}  file={path!r}  duration={dur_str}"
        )

    return "\n".join(lines)
