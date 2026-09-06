# Agentic Cinema — Agent Handover Document

> **ATTENTION AI AGENT:** Read this entire document before touching any code. It is the single source of truth for project state, architecture, and the next task.

---

## 1. Project Vision
Agentic Cinema is a multi-agent AI system for the content-production lifecycle (scripting → storyboarding → audio → sync → dubbing → compliance review).

**Core Rules (never break these):**
- Agents **never call each other directly**. They read/write from `ProjectState` in SQLite; the DAG Orchestrator decides what runs next.
- LLMs (Gemini) handle reasoning. Deterministic work (ffmpeg, math) uses tools in `app/shared/tools/`.
- All external claims need web evidence via Parallel Web Systems API.
- **Do NOT modify agent internals** (`app/agents/`) unless strictly required.

---

## 2. Technology Stack
- **AI/LLM:** Gemini (multimodal, text, audio, image) + Google GenAI File API
- **Agent Framework:** Google ADK
- **Web Intelligence:** Parallel Web Systems (Search/Extract APIs)
- **Backend:** Python 3.11, FastAPI, Pydantic V2
- **Persistence:** SQLite (via `app/persistence/repository.py`) — no ORM
- **Media Processing:** FFmpeg & FFprobe (must be installed on host)
- **Virtual env:** `.venv` inside `backend/` — activate with `source .venv/bin/activate`

---

## 3. The 7 Agents (`backend/app/agents/`)
1. **script_suggestor** — Transforms brief → structured script beats
2. **storyboard** — Generates visual shot plan from script
3. **audio** — AI voice TTS or creator voice extraction/cleaning
4. **syncer** — Matches audio to visual mouth movements (requires ffmpeg VFR fix)
5. **cultural_dub** — Localises dialogue preserving narrative intent
6. **compliance** — Cross-cutting risk flagging: GREEN/YELLOW/RED
7. **creator_scout** — Discovers brand collaboration opportunities

---

## 4. Project Structure
```
backend/
├── app/
│   ├── agents/           # 7 agents — DO NOT modify without reason
│   ├── api/routes/       # FastAPI endpoints (projects, chat_approval, media)
│   ├── orchestration/    # dag.py, executor.py, compliance_decorator.py, chat_router.py
│   ├── persistence/      # repository.py (ProjectRepository + JobRepository)
│   ├── worker.py         # Phase 4: background async worker loop
│   ├── shared/
│   │   ├── models/       # Pydantic schemas (project.py is the core contract)
│   │   └── tools/        # ffmpeg.py, ffprobe.py, Parallel API, Gemini API
│   └── main.py           # FastAPI entry point + lifespan (starts worker)
├── demo_complete.py      # Runs full Phase 1-3 demo (no server needed)
├── AGENT_HANDOVER.md     # This file
└── tests/                # 60+ unit/integration tests
```

---

## 5. Completed Phases

### Phase 1 — Core DAG Orchestration ✅
- `WorkflowDAG` in `dag.py` — stage dependency resolution
- `StageExecutor` in `executor.py` — enqueues jobs
- `ProjectRepository` + `JobRepository` in `repository.py` — SQLite persistence
- REST API: create project, invoke stage, get project state

### Phase 2 — Compliance & Chat ✅
- `ComplianceDecorator` (`orchestration/compliance_decorator.py`) — runs after each stage, returns GREEN/YELLOW/RED `ComplianceCheckpoint`
- `ChatIntentRouter` (`orchestration/chat_router.py`) — parses user messages and routes to DAG actions
- API endpoints: `/projects/{id}/chat`, `/projects/{id}/approve`, `/projects/{id}/compliance/pending`

### Phase 3 — Media Upload & Creator Voice ✅
- Media upload endpoint: `POST /projects/{id}/media`
- Two audio paths in DAG:
  - AI Voice: SCRIPT → STORYBOARD → AUDIO_AI → DUBBING
  - Creator Voice: SCRIPT → MEDIA_UPLOAD → SYNC → AUDIO_CREATOR → DUBBING

### Phase 4 — Persistent Async Jobs ✅
- **Problem solved:** Jobs were in-memory, lost on server restart.
- **Solution:** `app/worker.py` — asyncio loop polling SQLite `jobs` table every 3s (no Celery, no Redis).
- Startup (`main.py` lifespan): reset interrupted `running` jobs → `queued`, then start worker.
- Shutdown: gracefully cancel the worker task.
- `executor.py` writes jobs to SQLite and reads status from SQLite (no in-memory dict).
- **Verified:** Live test confirmed `queued → running → completed` in under 6 seconds.

---

## 6. Immediate Next Goal: Phase 5 — Human Review Loop

### The Problem
When Compliance returns `YELLOW` (e.g. a risky brand mention), the workflow must **pause** for human approval before downstream stages run.

Currently broken:
- Checkpoints live in memory only (in `ComplianceDecorator` instance) — lost on restart.
- The worker does NOT check for pending YELLOW blocks before running a job.
- Approval endpoint updates memory only, not the DB.

### What Phase 5 Must Build
1. **`compliance_checkpoints` table** in SQLite — persist every checkpoint after each stage.
2. **Block the worker** — before running a job, check if the project has a `YELLOW` checkpoint awaiting approval. If yes, skip the job until it's approved.
3. **Fix the approval API** — `POST /projects/{id}/approve` must update the DB checkpoint (not memory), so the worker unblocks automatically.
4. **Fix the pending approvals API** — `GET /projects/{id}/compliance/pending` must read from the DB, not memory.
5. **Run compliance in the worker** — after each stage completes, the worker should run the `ComplianceDecorator.check()` and save the checkpoint.

### Key Files to Change
| File | Change |
|---|---|
| `app/persistence/repository.py` | Add `ComplianceCheckpointRepository` (save, load, list_pending, approve) |
| `app/orchestration/compliance_decorator.py` | Optionally accept a `repository` to persist checkpoints |
| `app/worker.py` | After stage completes: run compliance check + save checkpoint. Before running: check for YELLOW blocks. |
| `app/api/routes/chat_approval.py` | Fix `/approve` and `/compliance/pending` to use DB |
| `app/main.py` | Add `compliance_checkpoints` table to `init_db()` |

---

## 7. Development Guidelines
- Pydantic V2: use `.model_dump()` not `.dict()`, use `.model_validate()` not `.parse_obj()`
- SQLite DB is at `backend/cinema.db` (auto-created on first `init_db()`)
- Run server: `source .venv/bin/activate && python -m uvicorn app.main:app --port 8000`
- Run full demo (no server): `source .venv/bin/activate && python demo_complete.py`
- No new pip packages without strong justification
- Active git branch: `integration`
