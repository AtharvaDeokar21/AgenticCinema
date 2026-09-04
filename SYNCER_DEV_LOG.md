# SYNCER AGENT — DEVELOPMENT LOG

> **Self-Recovery Rule:** If context resets, read this file first.
> Resume work at the section marked **Current Status** and execute the **Pending Tasks** checklist.

---

## Current Status

**Active Phase:** Phase 4 — Testing (awaiting approval)
**Branch:** `feature/layer3-syncer-agent`

---

## Completed Tasks

### Phase 1 — Repository Audit & Branching
- [x] Read entire repo structure
- [x] Read `script_suggestor` agent, schemas, prompts, and tests (canonical patterns)
- [x] Read all shared models and tools
- [x] Created and checked out branch `feature/layer3-syncer-agent`

### Phase 1.5 — Media Foundations
- [x] `shared/tools/media/ffprobe.py` — `VideoStreamInfo` dataclass, `get_video_stream_info()`,
      `detect_vfr()`; VFR flag = 1% relative tolerance on r_frame_rate vs avg_frame_rate
- [x] `shared/tools/media/ffmpeg.py` — `convert_to_cfr()`; libx264 + fps filter; raises
      ValueError on src==dst; creates parent dirs; returns resolved path
- [x] `shared/tools/media/__init__.py` — exported all new symbols

### Phase 2 — Schemas & Prompts
- [x] `syncer/schemas.py` — `AudioClip`, `SyncRequest` (input); `AudioPlacement`, `SyncMap` (output)
- [x] `syncer/prompts.py` — 10-rule `SYSTEM_PROMPT`, `USER_PROMPT_TEMPLATE`,
      `format_script_beats_block()`, `format_audio_clips_block()`

### Phase 3 — Agent Logic ✅
- [x] `syncer/tools.py` — four pipeline functions:
      - `resolve_clip_durations()`: ffprobe audio stream duration; falls back to container duration
      - `prepare_video()`: VFR + fps-mismatch guard; CFR output written as `<stem>_cfr.mp4`
      - `upload_video_to_gemini()`: File API upload; polls state every 3s; max 100 attempts (~5 min);
        raises RuntimeError on FAILED or timeout
      - `call_gemini_multimodal()`: composes `types.Part.from_uri` + `types.Part.from_text`;
        calls `client.client.models.generate_content` with `response_schema=SyncMap`;
        raises RuntimeError if `response.parsed` is None
- [x] `syncer/agent.py` — `SyncerAgent` (standalone, no BaseAgent):
      - 6-step `async run()`: resolve → prepare → upload → call → cleanup → stamp metadata
      - `finally` block guarantees Gemini file deletion even on exception
      - ground-truth ffprobe values (video_path, fps, duration, was_vfr_converted) stamped
        onto SyncMap after parse to prevent Gemini estimates leaking into output contract
      - full debug print block matching `script_suggestor` style
- [x] `syncer/__init__.py` — exports `SyncerAgent`, `SyncMap`, `SyncRequest`
- [x] All three files pass `python3 -m py_compile`

---

## Pending Tasks

### Phase 4 — Testing (ACTIVE — awaiting approval)
- [ ] Create `backend/tests/agents/syncer/__init__.py`
- [ ] Write `backend/tests/agents/syncer/test_agent.py`
      Mirror `script_suggestor` test style exactly:
      - `@pytest.mark.asyncio` single async test function
      - Instantiate `SyncerAgent()` directly
      - Build a `SyncRequest` with realistic fixture data
        (short test video + per-beat audio clips)
      - `await agent.run(request)` — live Gemini call
      - Assert: `result.status` in `{"complete", "partial"}`
      - Assert: `len(result.placements) > 0`
      - Assert: all `beat_id`s in placements are present in request
      - Assert: for each placement — `video_start_time < video_end_time`
      - Assert: for each placement — `0.0 <= confidence <= 1.0`
      - Assert: `result.video_fps > 0`
      - Assert: `result.video_duration > 0`
      - `print(result.model_dump_json(indent=2))`
- [ ] Update this log
- [ ] Commit Phase 4

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
                     ↓ (polls until ACTIVE)
               call_gemini_multimodal()
                 [types.Part.from_uri(video) + types.Part.from_text(prompt)]
                 [response_schema=SyncMap]
                     ↓
               files.delete(name)   ← always runs in finally block
                     ↓
               SyncMap (stamped with ffprobe ground-truth values)
```

### File Inventory
| File | Status |
|---|---|
| `shared/tools/media/ffprobe.py` | ✅ Complete |
| `shared/tools/media/ffmpeg.py` | ✅ Complete |
| `shared/tools/media/__init__.py` | ✅ Complete |
| `syncer/schemas.py` | ✅ Complete |
| `syncer/prompts.py` | ✅ Complete |
| `syncer/tools.py` | ✅ Complete |
| `syncer/agent.py` | ✅ Complete |
| `syncer/__init__.py` | ✅ Complete |
| `tests/agents/syncer/__init__.py` | ⏳ Phase 4 |
| `tests/agents/syncer/test_agent.py` | ⏳ Phase 4 |

---

*Log updated: Phase 3 complete*
