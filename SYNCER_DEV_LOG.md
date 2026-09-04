# SYNCER AGENT — DEVELOPMENT LOG

> **Self-Recovery Rule:** If context resets, read this file first.
> Resume work at the section marked **Current Status** and execute the **Pending Tasks** checklist.

---

## Current Status

**Active Phase:** Phase 2 COMPLETE — awaiting user approval before Phase 3
**Branch:** `feature/layer3-syncer-agent`

---

## Completed Tasks

### Phase 1 — Repository Audit & Branching
- [x] Read entire repo structure (`backend/app/agents/`, `shared/`, `tests/`)
- [x] Read `script_suggestor` agent, schemas, prompts (canonical pattern)
- [x] Read `tests/agents/script_suggestor/test_agent.py` (test pattern to mirror)
- [x] Read all shared models: `script.py`, `sync.py`, `audio.py`, `media.py`
- [x] Read shared tools: `gemini/client.py`, `media/ffprobe.py`, `media/ffmpeg.py`, `media/frames.py`
- [x] Created and checked out branch `feature/layer3-syncer-agent`

### Phase 1.5 — Media Foundations
- [x] `backend/app/shared/tools/media/ffprobe.py` — added `VideoStreamInfo` dataclass,
      `get_video_stream_info()`, `detect_vfr()`, `_parse_rational_fps()`;
      VFR flag uses 1% relative tolerance between r_frame_rate and avg_frame_rate
- [x] `backend/app/shared/tools/media/ffmpeg.py` — added `convert_to_cfr()`;
      uses `-vf fps=N -c:v libx264 -c:a copy`; raises ValueError if src==dst;
      creates parent dirs automatically; returns resolved output path
- [x] `backend/app/shared/tools/media/__init__.py` — exported all new symbols:
      `VideoStreamInfo`, `detect_vfr`, `get_video_stream_info`, `convert_to_cfr`

### Phase 2 — Schemas & Prompts
- [x] `backend/app/agents/syncer/schemas.py` — wrote:
      - `AudioClip` (input: beat_id, file_path, optional duration)
      - `SyncRequest` (input: video_path, script_beats, audio_clips, target_fps)
      - `AudioPlacement` (output: beat_id, audio_clip_path, video_start/end_time,
        confidence, mouth_motion_detected, notes)
      - `SyncMap` (output: status, video_path, video_duration, video_fps,
        was_vfr_converted, placements, unplaced_beat_ids, notes)
- [x] `backend/app/agents/syncer/prompts.py` — wrote:
      - `SYSTEM_PROMPT` (10-rule mouth-motion grounding spec for Gemini)
      - `USER_PROMPT_TEMPLATE` (per-request fill: duration, fps, path, beats, clips)
      - `format_script_beats_block()` helper (Pydantic model or dict)
      - `format_audio_clips_block()` helper (Pydantic model or dict)

---

## Pending Tasks

### Phase 3 — Agent Logic (NEXT — awaiting approval)
- [ ] Write `backend/app/agents/syncer/tools.py`
      - `prepare_video()` — probe VFR, convert if needed, return final path + metadata
      - `upload_video_to_gemini()` — upload via `client.files.upload()`, poll until ACTIVE
      - `call_gemini_multimodal()` — compose prompt parts (video + text), call generate_structured()
      - `resolve_clip_durations()` — ffprobe each AudioClip with unknown duration
- [ ] Write `backend/app/agents/syncer/agent.py`
      - `SyncerAgent` class (no BaseAgent, direct Gemini usage per spec)
      - `run(request: SyncRequest) -> SyncMap` async method
      - Debug print block mirroring script_suggestor pattern
- [ ] Write `backend/app/agents/syncer/__init__.py`
      - Export `SyncerAgent`

### Phase 4 — Testing (after Phase 3 approval)
- [ ] Write `backend/tests/agents/syncer/__init__.py`
- [ ] Write `backend/tests/agents/syncer/test_agent.py`
      - Mirror script_suggestor test style exactly
      - Use a real short video + real audio clips (or fixture paths)
      - Assert: status in valid set, placements non-empty, all beat_ids present,
        video_start_time < video_end_time, confidence in [0,1]
- [ ] Update this log

---

## Architecture Reference

### Data Flow
```
SyncRequest
  └─ video_path  ──► prepare_video() ──► VFR? ──► convert_to_cfr() ──► CFR copy
  └─ audio_clips ──► resolve_clip_durations() ──► clips with known durations
  └─ script_beats
                     ↓
               upload_video_to_gemini()
                     ↓
               call_gemini_multimodal()
                 [SYSTEM_PROMPT + USER_PROMPT_TEMPLATE + video FileData]
                     ↓
               SyncMap (parsed Pydantic model)
```

### Key Shared Components Used
| Component | Import Path |
|---|---|
| `GeminiClient` | `app.shared.tools.gemini.client` |
| `probe_media`, `detect_vfr`, `get_video_stream_info` | `app.shared.tools.media.ffprobe` |
| `convert_to_cfr` | `app.shared.tools.media.ffmpeg` |
| `ScriptBeat` | `app.shared.models.script` |

### Gemini File Upload Pattern (Phase 3 plan)
```python
file_ref = client.files.upload(path=video_path)
# Poll until state == "ACTIVE"
while file_ref.state.name == "PROCESSING":
    time.sleep(2)
    file_ref = client.files.get(name=file_ref.name)

# Compose multimodal content
contents = [
    types.Part.from_uri(file_uri=file_ref.uri, mime_type="video/mp4"),
    types.Part.from_text(prompt_text),
]
```

---

*Log updated: Phase 2 complete*
