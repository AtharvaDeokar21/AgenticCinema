# 🎬 Syncer Agent — Layer 3

**Branch:** `feature/layer3-syncer-agent` | **Package:** `backend/app/agents/syncer/`

---

## 1. 🎬 High-Level Overview (In Plain English)

### The Problem It Solves

When a content creator records a video, they often record the **video silently** and the **audio separately** (in a quiet room, into a good microphone). The editor then has to manually drag each audio clip onto the video timeline so the creator's voice lines up precisely with their lip movement.

In traditional workflows this requires either:
- **Tedious manual scrubbing** — frame-by-frame searching for the exact frame where the mouth opens, or
- **Waveform mathematics** — generating mouth-movement proxy audio from the silent video and cross-correlating it with the recorded audio.

Both are slow, brittle, and require expensive editing software.

### What the Syncer Agent Does

The Syncer Agent acts like an **automated visual editor with eyes**.

1. It **watches** the silent video footage using Gemini's multimodal vision API.
2. For each line in the script (a **beat**), it **spots the exact timestamp** where the creator's mouth begins to move for that line.
3. It **maps the corresponding audio clip** onto that timestamp and returns a structured placement guide — the `SyncMap` — that tells a downstream editor or rendering engine exactly where to drop each audio file on the timeline.

```
Silent Video + Script Beats + Audio Clips
             │
             ▼
      [ Syncer Agent ]
             │
             ▼
  SyncMap: "Place clip_1.wav at 0.42s,
            clip_2.wav at 12.87s,
            clip_3.wav at 27.01s …"
```

### Why It Matters

| Traditional workflow | Syncer Agent |
|---|---|
| Manual scrubbing per beat | Fully autonomous |
| Requires waveform analysis tools | Zero waveform math — pure visual AI |
| Breaks on VFR footage | Auto-detects and corrects Variable Frame Rate |
| Crashes on occluded face | Graceful fallback to script timestamps |
| O(n) editor hours | O(1) API call |

---

## 2. 🗺️ File Interaction & Architecture Map

### Request Flow

```
SyncRequest
  ├── video_path     (str — path to silent video)
  ├── script_beats   (List[ScriptBeat] — from upstream Script Suggestor)
  └── audio_clips    (List[AudioClip]  — one per beat, matched by beat_id)
          │
          ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │  agent.py: SyncerAgent.run()                                        │
  │                                                                     │
  │  Step 1 ──► tools.py: resolve_clip_durations()                      │
  │               └──► shared/tools/media/ffprobe.py: probe_media()     │
  │                    (probes audio stream duration for each clip)     │
  │                                                                     │
  │  Step 2 ──► tools.py: prepare_video()                               │
  │               ├──► ffprobe.py: get_video_stream_info()              │
  │               │    (reads r_frame_rate vs avg_frame_rate)           │
  │               └──► ffmpeg.py: convert_to_cfr()  [if VFR detected]  │
  │                    (re-encodes to libx264 at target_fps)            │
  │                                                                     │
  │  Step 3 ──► tools.py: upload_video_to_gemini()                      │
  │               └──► Google GenAI File API: files.upload()            │
  │                    (polls files.get() until state == ACTIVE)        │
  │                                                                     │
  │  Step 4 ──► tools.py: call_gemini_multimodal()                      │
  │               ├──► prompts.py: SYSTEM_PROMPT + USER_PROMPT_TEMPLATE │
  │               │    (10-rule mouth-motion grounding instruction set)  │
  │               └──► Gemini Flash: generate_content()                 │
  │                    (response_schema=SyncMap → parsed Pydantic obj)  │
  │                                                                     │
  │  Step 5 ──► Gemini File API: files.delete()    [always in finally]  │
  │                                                                     │
  │  Step 6 ──► Stamp ffprobe ground-truth metadata onto SyncMap        │
  └─────────────────────────────────────────────────────────────────────┘
          │
          ▼
  SyncMap (Pydantic model)
  ├── status              ("complete" | "partial")
  ├── video_path          (final analysed path — CFR copy if converted)
  ├── video_duration      (seconds, from ffprobe)
  ├── video_fps           (fps, from ffprobe)
  ├── was_vfr_converted   (bool)
  ├── placements          (List[AudioPlacement])
  │     └── beat_id, audio_clip_path, video_start_time, video_end_time,
  │         confidence, mouth_motion_detected, notes,
  │         pacing_suggestion   ← NEW: editor fit advice per clip
  ├── unplaced_beat_ids   (beats Gemini could not visually ground)
  └── editor_timeline_text ← NEW: human-readable placement changelog
        e.g. "[00:00.42 - 00:01.42] -> Attach audio_beat_001.wav (Fits well)"
```

### File Role Summary

| File | Role |
|---|---|
| [`schemas.py`](schemas.py) | **Contracts** — Pydantic V2 models for `SyncRequest` (input) and `SyncMap` / `AudioPlacement` (output). Includes `pacing_suggestion` (per-clip fit advice) and `editor_timeline_text` (human-readable changelog). The single source of truth for all field names, types, and descriptions used by both the agent and Gemini's structured output schema. |
| [`prompts.py`](prompts.py) | **Gemini Instruction Set** — 12-rule `SYSTEM_PROMPT`: Rules 1–10 govern mouth-motion grounding and fallbacks; Rule 11 defines the pacing analysis tolerance (±0.25 s); Rule 12 specifies the `[MM:SS.mm]` editor timeline format. Plus `USER_PROMPT_TEMPLATE` and two formatter helpers. |
| [`tools.py`](tools.py) | **Pipeline Primitives** — four focused functions (`resolve_clip_durations`, `prepare_video`, `upload_video_to_gemini`, `call_gemini_multimodal`), each independently testable and handling one discrete concern. |
| [`agent.py`](agent.py) | **Orchestrator** — `SyncerAgent.run()` sequences the four tools, wraps the Gemini call in `try/finally` for guaranteed cleanup, stamps ground-truth ffprobe metadata, and includes a `DEMO_MODE` circuit-breaker with a fully Pydantic-valid mock. |
| [`shared/tools/media/ffprobe.py`](../../shared/tools/media/ffprobe.py) | **Media Probing** — `probe_media()` (raw JSON), `get_video_stream_info()` (structured `VideoStreamInfo` dataclass), `detect_vfr()` (boolean VFR guard). |
| [`shared/tools/media/ffmpeg.py`](../../shared/tools/media/ffmpeg.py) | **Media Conversion** — `convert_to_cfr()` re-encodes VFR video to libx264 CFR using the `fps` filter; `extract_audio()` and `run_ffmpeg()` for general use. |
| [`tests/agents/syncer/test_agent.py`](../../../../tests/agents/syncer/test_agent.py) | **Integration Tests** — `sync_request` fixture synthesises real media files with `ffmpeg -f lavfi` into `tmp_path`; single `@pytest.mark.asyncio` test asserts structural guarantees including `pacing_suggestion` (non-empty string) and `editor_timeline_text` (non-empty string). |

---

## 3. ⚙️ Technical Deep Dive (Code Architecture)

### 3.1 Frame Rate Normalization — VFR vs. CFR

**The problem:** Modern smartphones (iPhone, Android) record video in **Variable Frame Rate (VFR)** mode. In VFR, the camera dynamically drops or duplicates frames based on scene complexity. Each frame carries its own timestamp (PTS — Presentation Timestamp) rather than being evenly spaced.

When you send a VFR video to the Gemini File API, the API indexes frames by their PTS. If a frame at visual second 5.0 has a PTS of 4.73 due to timestamp drift, Gemini will report the timestamp as `4.73s`, not `5.0s`. The Syncer Agent would then place audio clips ~270ms early — a perceptible desync that ruins the edit.

**How we detect it — `ffprobe.py`:**

```python
from fractions import Fraction

r_frame_rate  = "30000/1001"   # Declared FPS (what the container claims)
avg_frame_rate = "29.94"       # Computed average (measured from actual PTSes)

declared_fps = float(Fraction(r_frame_rate))   # 29.9700...
average_fps  = float(Fraction(avg_frame_rate)) # 29.94

relative_diff = abs(declared_fps - average_fps) / declared_fps
is_vfr = relative_diff > 0.01  # 1% tolerance
```

`fractions.Fraction` is used deliberately — it handles rational strings like `"30000/1001"` (NTSC timecode) exactly, without floating-point rounding errors that would produce false VFR flags on perfectly CFR 29.97fps footage.

The **1% tolerance** (`_VFR_TOLERANCE = 0.01`) is the practical threshold: anything within 1% is treated as measurement noise in the container; above 1% indicates genuine per-frame timestamp variance.

**How we fix it — `ffmpeg.py`:**

```python
command = [
    "ffmpeg", "-y", "-i", str(src),
    "-vf", f"fps={target_fps}",   # Forces uniform frame spacing
    "-c:v", "libx264",             # Full re-encode rewrites all PTSes
    "-c:a", "copy",                # Audio is unchanged
    str(dst),
]
```

The `fps` video filter **duplicates or drops frames** to produce exactly `target_fps` frames per second. Combined with a full libx264 re-encode (which regenerates all PTSes from scratch), the output container has perfectly uniform timestamps — exactly what the Gemini File API needs for accurate frame grounding.

---

### 3.2 Gemini Multimodal Lifecycle & File API

**Why the File API and not inline base64?**

The Gemini API has a per-request content size limit. A 60-second 1080p video can be 50–200 MB — far beyond what can be embedded inline. The File API solves this:

1. The file is **uploaded once** and stored on Google's servers.
2. A **URI reference** (`files/abc123`) is embedded in the API request instead of the raw bytes.
3. Google streams the file directly into the model's context without it transiting through the client machine again.

**The polling loop — `tools.py: upload_video_to_gemini()`:**

The File API processes uploads **asynchronously**. After `files.upload()` returns, the file is in state `"PROCESSING"` — Gemini is transcoding and indexing it. Calling `generate_content()` before it reaches `"ACTIVE"` will fail.

```python
while file_ref.state.name not in ("ACTIVE", "FAILED"):
    time.sleep(3)
    file_ref = client.client.files.get(name=file_ref.name)
    attempts += 1
    if attempts >= 100:          # ~5 minute hard timeout
        raise RuntimeError(...)
```

The loop checks every 3 seconds with a ceiling of 100 attempts (≈ 5 minutes). If the file reaches `"FAILED"`, a `RuntimeError` is raised immediately rather than waiting for the timeout.

**The guaranteed cleanup — `agent.py: run()` try/finally:**

```python
file_ref = upload_video_to_gemini(...)

try:
    sync_map = call_gemini_multimodal(...)
finally:
    # Runs even if call_gemini_multimodal() raises an exception.
    self.gemini.client.files.delete(name=file_ref.name)
```

Without the `finally` block, any exception during the Gemini call (network error, schema parse failure, timeout) would leave the video file sitting on Google's servers indefinitely, consuming storage quota. The `finally` ensures deletion is **always** attempted, and deletion errors are caught and logged as warnings rather than re-raised — because the primary error (from the model call) is more important.

---

### 3.3 Structured Schemas & Ground-Truth Metadata Stamping

**Schema as a living contract — `schemas.py`:**

Every field in `SyncMap` and `AudioPlacement` carries a `description=` in its `Field()` definition. This serves two purposes simultaneously:

1. **Human documentation** — readable by any engineer inspecting the model.
2. **Gemini prompt injection** — when `response_schema=SyncMap` is passed to `generate_content()`, the SDK serialises the schema (including descriptions) into the system context. Gemini reads the field descriptions as instructions for what to populate and how.

This means the schema file is **both the data contract and part of the prompt** — a single source of truth.

**Why we stamp over Gemini's values (Step 6):**

```python
# In agent.py, after response.parsed returns:
sync_map.video_path = video_path              # actual path used
sync_map.was_vfr_converted = was_converted    # boolean from prepare_video()
sync_map.video_fps = video_info.declared_fps  # measured by ffprobe
if video_info.duration is not None:
    sync_map.video_duration = video_info.duration
```

Gemini estimates `video_fps` and `video_duration` from the information in the prompt (which is provided as text context). These estimates can be imprecise — Gemini might round 29.97 to 30, or infer duration from the beat timestamps rather than the actual file length.

By **overwriting** those fields with values directly measured by `ffprobe` after the API call, we guarantee that the `SyncMap` the downstream editor receives always contains **ground-truth, machine-measured metadata** — never model-estimated values.

---

### 3.4 Mouth-Motion Grounding & Fallback Logic

The `SYSTEM_PROMPT` in `prompts.py` teaches Gemini a precise visual grounding task with explicit fallback rules.

**Rule 4 — Fallback when face is occluded:**

> *"If the face is occluded, cut away, or the mouth motion is ambiguous, set `mouth_motion_detected = false` and fall back to the beat's expected `start_time` as `video_start_time`."*

This covers the common cases where:
- The creator **looks away** briefly
- A **jump cut** occurs mid-beat
- The **camera shakes** and the face is blurry
- The **video is a synthetic black screen** (as in the test fixture)

In all these cases the agent does **not crash** — it produces a placement with a timestamp derived from the script and marks it clearly as ungrounded (`mouth_motion_detected = False`, low `confidence`).

**Rule 7 — Status determination:**

> *"Set status to `complete` if all beats were placed with confidence ≥ 0.5, `partial` if some beats are in `unplaced_beat_ids`."*

The `unplaced_beat_ids` field exists for situations where Gemini cannot even produce a fallback estimate (e.g. the creator's face never appears on screen during that beat's window). These beats require human intervention and the field exposes them explicitly rather than silently dropping them.

The **confidence threshold of 0.5** is a deliberate design choice: above 0.5, the automated placement is trusted; below 0.5, the placement is still provided (better than nothing) but flagged in `notes` so a human reviewer knows to check it.

---

### 3.5 Pacing Analysis & Editor Timeline Text

Two fields were added to make the `SyncMap` immediately usable by human editors without requiring them to parse JSON or write custom tooling.

#### `pacing_suggestion` — per-clip fit analysis (Rule 11)

For every `AudioPlacement`, Gemini compares the audio clip's known duration against the visual window it identified:

```
visual_window = video_end_time - video_start_time
```

| Condition | `pacing_suggestion` output |
|---|---|
| `\|visual_window − audio_duration\| ≤ 0.25 s` | `"Fits well"` |
| `audio_duration > visual_window + 0.25 s` | `"Audio is too long; consider cutting the dialogue or freezing the video frame"` |
| `audio_duration < visual_window − 0.25 s` | `"Audio is too short; consider slowing the video or adding a pause before the next beat"` |

The **±0.25 s tolerance** absorbs natural variation in mouth-open detection without false-positive pacing warnings — a 250 ms slip is inaudible to most listeners. The field is **never null**; Gemini must always output one of the three categories.

#### `editor_timeline_text` — human-readable placement changelog (Rule 12)

Gemini assembles a plain-text summary of all placements in a changelog format that any editor can read at a glance:

```
[00:00.42 - 00:01.42] -> Attach audio_beat_001.wav (Fits well)
[00:01.50 - 00:02.80] -> Attach audio_beat_002.wav (Audio is too long; consider cutting the dialogue or freezing the video frame)
[00:02.90 - 00:03.90] -> Attach audio_beat_003.wav (Fits well)
```

Timestamp format: `MM:SS.mm` where `mm` is centiseconds (hundredths of a second). Basenames only — no absolute paths — so the text is portable across machines. If all beats are unplaced, the field is set to:

```
No placements — all beats require manual sync.
```

This field is also printed separately to stdout at the end of the pipeline, making it visible in pytest `-s` output without having to parse the JSON dump.

---

## 4. 🧪 How to Test & Run the Agent

### System Prerequisites

You need **Python 3.11+** and **ffmpeg** installed on the host machine.

---

#### 🍎 macOS

```bash
# Install ffmpeg and Python 3.11 via Homebrew
brew install ffmpeg python@3.11

# Verify
ffmpeg -version | head -1
python3.11 --version
```

---

#### 🐧 Linux (Ubuntu / Debian)

```bash
# Update package index and install ffmpeg
sudo apt-get update
sudo apt-get install -y ffmpeg

# Install Python 3.11 (if not already available)
sudo apt-get install -y python3.11 python3.11-venv python3.11-pip

# Verify
ffmpeg -version | head -1
python3.11 --version
```

> **Other distros:** Use your package manager — `dnf install ffmpeg python3.11` (Fedora/RHEL),
> `pacman -S ffmpeg python` (Arch). Make sure ffmpeg includes libx264 support
> (`ffmpeg -encoders | grep libx264`).

---

#### 🪟 Windows

**Option A — Winget (Windows 11 / Windows 10 with App Installer):**

```powershell
# Run in PowerShell (as Administrator if needed)
winget install -e --id Gyan.FFmpeg
winget install -e --id Python.Python.3.11
```

**Option B — Manual install:**

1. Download ffmpeg from [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)
   → *Windows builds by gyan.dev* → `ffmpeg-release-full.zip`
2. Extract to `C:\ffmpeg\` and add `C:\ffmpeg\bin` to your **System PATH**
3. Download Python 3.11 from [https://python.org](https://python.org) and install
   (check *"Add to PATH"* during setup)

```powershell
# Verify (in a new PowerShell/CMD window after PATH update)
ffmpeg -version
python --version
```

---

### Environment Setup

#### 🍎 macOS / 🐧 Linux

```bash
cd backend

# Create and activate virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set your Gemini API key
export GEMINI_API_KEY="your-api-key-here"
```

#### 🪟 Windows — PowerShell

```powershell
cd backend

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# If you see an execution policy error, run this first (once per machine):
# Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

# Install dependencies
pip install -r requirements.txt

# Set your Gemini API key (current session only)
$env:GEMINI_API_KEY = "your-api-key-here"
```

#### 🪟 Windows — CMD

```cmd
cd backend

.venv\Scripts\activate.bat

pip install -r requirements.txt

set GEMINI_API_KEY=your-api-key-here
```

---

### Execution

The pytest command is identical on all platforms:

```bash
# macOS / Linux
pytest tests/agents/syncer/ -v -s

# Windows (PowerShell or CMD — same command)
pytest tests/agents/syncer/ -v -s
```

> **Tip:** If `pytest` is not found after activating the venv, use the module form:
> ```bash
> python -m pytest tests/agents/syncer/ -v -s
> ```

---

Expected output structure (all platforms):

```
tests/agents/syncer/test_agent.py::test_syncer_agent
  [prepare_video] Video is already CFR at 30.000 fps — no conversion needed
  [upload_video_to_gemini] Uploading: '/tmp/.../test_video.mp4'
  [upload_video_to_gemini] File is ACTIVE — URI: https://...
  ════════════════════════════════════════════════
  SYNCER — GEMINI MULTIMODAL PROMPT (text portion)
  ════════════════════════════════════════════════
  ...
  [SyncerAgent] Deleted: 'files/abc123'
  Generated SyncMap:
  {
    "status": "partial",
    "video_path": "/tmp/.../test_video.mp4",
    "video_duration": 3.0,
    "video_fps": 30.0,
    ...
  }
PASSED
```

---

### How the Synthetic Fixture Works

The `sync_request` fixture in `test_agent.py` uses **ffmpeg's built-in signal generators**
(`-f lavfi`) to create real media files entirely in memory, without any stored binary assets
in the repository:

```python
# 3-second black video @ 30fps + silent stereo audio
ffmpeg -f lavfi -i "color=c=black:s=640x480:r=30" \
       -f lavfi -i "anullsrc=r=44100:cl=stereo"   \
       -t 3.0 -c:v libx264 -c:a aac test_video.mp4

# 1-second silent mono WAV per beat
ffmpeg -f lavfi -i "anullsrc=r=44100:cl=mono" \
       -t 1.0 -c:a pcm_s16le audio_beat_001.wav
```

Files are written to pytest's `tmp_path` (a uniquely named temp directory per test run) and are automatically deleted by pytest after the test completes.

**Why this matters for CI:** no binary video files are committed to the repository — the test suite is entirely self-contained and reproducible on any machine with ffmpeg installed.

---

## 5. 🚨 Live Demo Safety Nets (Hackathon Circuit Breaker)

Live demos can hit unexpected problems: venue Wi-Fi drops, Gemini API rate limits are reached, or `PROCESSING` states time out at the worst moment.

### DEMO_MODE Pattern

Set the `DEMO_MODE` environment variable before running the agent to activate a **deterministic mock path** that bypasses all external API calls and returns a pre-built `SyncMap`:

```bash
export DEMO_MODE=true
export GEMINI_API_KEY="placeholder"   # still required by Settings validation

pytest tests/agents/syncer/ -v -s
```

> **Note:** `DEMO_MODE` is documented here as an **integration pattern** for the team to implement before a live presentation. The production code in `agent.py` does not yet check for this flag — see the implementation guide below.

### Implementing DEMO_MODE in `agent.py`

Add the following guard at the top of `SyncerAgent.run()`:

```python
import os
from app.agents.syncer.schemas import AudioPlacement, SyncMap

async def run(self, request: SyncRequest) -> SyncMap:
    if os.getenv("DEMO_MODE", "").lower() == "true":
        return self._mock_sync_map(request)
    # ... rest of live pipeline

def _mock_sync_map(self, request: SyncRequest) -> SyncMap:
    """Return a deterministic SyncMap for offline/demo use."""
    placements = [
        AudioPlacement(
            beat_id=beat.beat_id,
            audio_clip_path=clip.file_path,
            video_start_time=beat.start_time,
            video_end_time=beat.end_time,
            confidence=0.95,
            mouth_motion_detected=False,
            notes="DEMO_MODE: fallback to script timestamps",
        )
        for beat, clip in zip(request.script_beats, request.audio_clips)
    ]
    return SyncMap(
        status="complete",
        video_path=request.video_path,
        video_duration=request.script_beats[-1].end_time,
        video_fps=float(request.target_fps),
        was_vfr_converted=False,
        placements=placements,
    )
```

### Pre-Demo Checklist

| Check | Command |
|---|---|
| ffmpeg installed | `ffmpeg -version` |
| API key set | `echo $GEMINI_API_KEY` |
| Test suite passes (live) | `pytest tests/agents/syncer/ -v -s` |
| DEMO_MODE works | `DEMO_MODE=true pytest tests/agents/syncer/ -v` |
| Branch is clean | `git status` |

---

## 6. 📁 Full File Inventory

```
backend/
├── app/
│   ├── agents/
│   │   └── syncer/
│   │       ├── __init__.py     ← exports SyncerAgent, SyncMap, SyncRequest
│   │       ├── agent.py        ← SyncerAgent orchestrator (6-step run())
│   │       ├── prompts.py      ← SYSTEM_PROMPT + USER_PROMPT_TEMPLATE
│   │       ├── schemas.py      ← SyncRequest, SyncMap, AudioPlacement, AudioClip
│   │       ├── tools.py        ← 4 pipeline functions
│   │       └── README.md       ← this file
│   └── shared/
│       └── tools/
│           └── media/
│               ├── ffprobe.py  ← probe_media, get_video_stream_info, detect_vfr
│               └── ffmpeg.py   ← run_ffmpeg, extract_audio, convert_to_cfr
└── tests/
    └── agents/
        └── syncer/
            ├── __init__.py
            └── test_agent.py   ← integration test with lavfi fixtures
```
