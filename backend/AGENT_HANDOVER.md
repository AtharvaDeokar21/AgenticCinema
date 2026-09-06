# Agentic Cinema — Agent Handover Document

> **ATTENTION AI AGENT:** Read this entire document before touching any code. It is the single source of truth for project state, architecture, and the next task.

---

## 1. Project Vision
Agentic Cinema is a multi-agent AI system for the content-production lifecycle (scripting → storyboarding → audio → sync → dubbing → compliance review).

**Core Rules (never break these):**
- Agents **never call each other directly**. They read/write via `ProjectState` in SQLite; the DAG Orchestrator decides what runs next.
- LLMs (Gemini) handle reasoning. Deterministic work (ffmpeg, math) uses tools in `app/shared/tools/`.
- All external claims need web evidence via Parallel Web Systems API.
- **Do NOT modify agent internals** (`app/agents/`) unless strictly required.

---

## 2. Technology Stack
- **AI/LLM:** Gemini (multimodal) + Google GenAI File API
- **Agent Framework:** Google ADK
- **Web Intelligence:** Parallel Web Systems (Search/Extract APIs)
- **Backend:** Python 3.11, FastAPI, Pydantic V2
- **Persistence:** SQLite at `backend/cinema.db` (via `app/persistence/repository.py`)
- **Media Processing:** FFmpeg & FFprobe
- **Virtual env:** `.venv` inside `backend/` — `source .venv/bin/activate`

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
│   ├── api/routes/       # FastAPI endpoints
│   │   ├── chat_approval.py  # /chat, /approve, /compliance/pending, /compliance/history
│   │   ├── media.py          # /media upload
│   │   └── projects.py       # secondary router (partially used)
│   ├── orchestration/    # dag.py, executor.py, compliance_decorator.py, chat_router.py
│   ├── persistence/      # repository.py: ProjectRepository, JobRepository, ComplianceCheckpointRepository
│   ├── worker.py         # Phase 4+5: background async worker loop
│   ├── shared/
│   │   ├── models/       # Pydantic schemas — project.py is the core contract
│   │   └── tools/        # ffmpeg, ffprobe, Parallel API, Gemini API wrappers
│   └── main.py           # FastAPI entry point + lifespan (starts worker, registers routers)
├── demo_complete.py      # Standalone demo: Phase 1-3, no server needed
├── AGENT_HANDOVER.md     # This file — read before anything
├── COMPLETION_TODO.md    # Post-phase checklist (run demo, verify, clean up)
└── tests/                # 60+ unit/integration tests
```

---

## 5. Complete API Surface (all frontend-ready)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/health` | Liveness check |
| POST | `/projects` | Create project |
| GET | `/projects/{id}` | Full state + script/storyboard/audio content |
| POST | `/projects/{id}/stages/{stage}` | Queue a stage job |
| GET | `/projects/{id}/jobs/{job_id}` | Poll job status (queued/running/completed/failed) |
| POST | `/projects/{id}/chat` | Chat intent routing |
| GET | `/projects/{id}/compliance/pending` | Check for YELLOW blocks awaiting approval |
| POST | `/projects/{id}/approve` | Approve a YELLOW, unblock worker |
| GET | `/projects/{id}/compliance/history` | Full compliance audit trail |
| GET | `/projects/{id}/dag` | DAG visualization (nodes + edges) |
| POST | `/projects/{id}/media` | Upload creator video |

All endpoints read/write SQLite — fully persistent across server restarts.

---

## 6. Completed Phases ✅

### Phase 1 — Core DAG Orchestration
- `WorkflowDAG` (dag.py) — dependency resolution for all 8 stages
- `StageExecutor` (executor.py) — enqueues jobs to SQLite
- REST API: create project, invoke stage, get state

### Phase 2 — Compliance & Chat
- `ComplianceDecorator` — runs after each stage, GREEN/YELLOW/RED checkpoint
- `ChatIntentRouter` — parses user messages → DAG actions
- API: `/chat`, `/approve`, `/compliance/pending`

### Phase 3 — Media Upload & Creator Voice
- `POST /projects/{id}/media` endpoint
- DAG supports two paths:
  - AI Voice: SCRIPT → STORYBOARD → AUDIO_AI → DUBBING
  - Creator Voice: SCRIPT → MEDIA_UPLOAD → SYNC → AUDIO_CREATOR → DUBBING

### Phase 4 — Persistent Async Jobs
- `app/worker.py` — asyncio loop polling `jobs` table every 3s (no Celery/Redis)
- Startup: resets interrupted `running` → `queued` for auto-recovery
- Executor writes to DB; status reads from DB (no in-memory dict)
- **Verified:** `queued → running → completed` in <6s

### Phase 5 — Human Review Loop
- `compliance_checkpoints` SQLite table (persists across restarts)
- Worker pre-run check: if YELLOW pending → skip job, retry next poll
- Worker post-run: runs compliance check, saves checkpoint to DB
- `/approve` and `/compliance/pending` both read/write DB
- **Verified:** YELLOW blocks downstream, approval unblocks within 3s

### Critical Bug Fix — ProjectRepository.load()
- Previous: all fields returned as `None` (hardcoded stubs)
- Fixed: full Pydantic deserialization of every column
- Impact: worker can now chain stages (STORYBOARD reads script); frontend gets real content

---

## 7. What Remains (in priority order)

### Phase 6 — API Polish & Missing Endpoints
**Priority: HIGH — needed before frontend integration**
- [ ] `GET /projects` — list all projects (currently missing)
- [ ] Proper 422 validation error responses
- [ ] `DELETE /projects/{id}` — cleanup endpoint
- [ ] `GET /projects/{id}/jobs` — list all jobs for a project
- [ ] Consolidate `main.py` inline routes + `app/api/routes/projects.py` (currently duplicated)
- [ ] Consistent error response schema `{ "error": "...", "detail": "..." }` across all endpoints

### Phase 7 — E2E API Integration Tests
**Priority: HIGH — nothing meaningful is tested through the HTTP layer**
- [ ] `tests/e2e/test_ai_voice_workflow.py` — create → script → storyboard → audio via API
- [ ] `tests/e2e/test_compliance_flow.py` — YELLOW block → approve → unblock
- [ ] `tests/e2e/test_chat_routing.py` — all 3 chat intents via API
- [ ] `tests/e2e/test_job_recovery.py` — interrupt + restart + verify recovery

### Phase 8 — WebSocket Real-Time Updates (optional for prototype)
- [ ] `GET /ws/projects/{id}` — push job status changes without polling

### Phase 9 — Structured Logging
- [ ] Replace `print()` statements with `logging` across worker and API
- [ ] Request trace IDs

---

## 8. Development Guidelines
- Pydantic V2: `.model_dump()` not `.dict()`, `.model_validate()` not `.parse_obj()`
- SQLite DB: `backend/cinema.db` (auto-created by `init_db()` on startup)
- Run server: `source .venv/bin/activate && python -m uvicorn app.main:app --port 8000 --reload`
- Run standalone demo (no server): `source .venv/bin/activate && python demo_complete.py`
- No new pip packages without strong justification
- Active branch: `integration`
