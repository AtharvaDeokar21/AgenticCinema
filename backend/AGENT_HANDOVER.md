# Agentic Cinema - AI Agent Handover Document

> **ATTENTION AI AGENT:** If you are reading this, you are picking up development on the Agentic Cinema project. Read this entire document carefully. It contains all the necessary context, architecture decisions, and current progress so you do not need to read the rest of the documentation markdown files.

## 1. Project Vision
Agentic Cinema is a multi-agent AI system designed to assist creators across the content-production lifecycle (scripting, storyboarding, audio, syncing, dubbing, and compliance). 
- **The Core Rule:** Agents **never** call each other directly. Instead, they read from and write to a shared SQLite database (`ProjectState`), and a central DAG-based Orchestrator determines which agent runs next.
- **LLMs vs. Tools:** Gemini handles reasoning and multimodal vision. Deterministic operations (like frame-rate conversion, audio cutting, and waveform math) are strictly handled by external tools like `ffmpeg` and `ffprobe`. We do not ask LLMs to do math or rendering.
- **Grounding Rule:** Claims about the outside world must have web evidence provided by Parallel Web Systems (Search/Extract APIs).

## 2. Technology Stack
- **AI/LLM:** Gemini (multimodal, text, audio, image) and Google GenAI File API.
- **Agent Framework:** Google ADK (Agent Engine).
- **Web Intelligence:** Parallel Web Systems.
- **Backend:** Python 3.11, FastAPI (REST API), Pydantic V2 (data validation).
- **Persistence:** SQLite (via standard Python, no complex ORMs currently used for `ProjectState`).
- **Media Processing:** FFmpeg & FFprobe (must be installed on the host system).

## 3. The 7 Agents
All agent logic lives in `backend/app/agents/`.
1. **Script Suggestor**: Transforms a brief into script beats.
2. **Storyboard**: Generates visual shot plans and concept art from the script.
3. **Syncer**: Matches separate high-quality audio clips to the visual mouth movements in a silent video using Gemini Vision (requires fixing Variable Frame Rate issues via ffmpeg first).
4. **Audio**: Generates AI voice TTS or extracts/cleans creator voice audio.
5. **Cultural Dub**: Localizes dialogue while preserving narrative intent.
6. **Compliance**: Cross-cutting agent that flags risks (GREEN/YELLOW/RED). YELLOW requires human approval.
7. **Creator Scout**: Discovers brand collaboration opportunities.

## 4. Current Architecture & Completed Phases (1-3)
The system currently has a fully working **DAG-based Orchestration Layer** implemented in `backend/app/orchestration/`.
- **Phase 1 (Core):** Implemented the `WorkflowDAG` which ensures stages run in the right order based on dependencies. `StageExecutor` handles async execution. `ProjectState` persists everything in SQLite.
- **Phase 2 (Compliance & Chat):** Implemented a `ComplianceDecorator` that runs after major stages. Added a `ChatIntentRouter` that parses user chat messages (e.g., "make beat 3 dramatic") and routes them to stage invocations. Added API endpoints for chatting and approving YELLOW compliance flags.
- **Phase 3 (Media & Creator Voice):** Added media upload endpoints. Built the DAG logic to support two paths: 
  - *AI Voice Path*: SCRIPT → STORYBOARD → AUDIO_AI → DUBBING
  - *Creator Voice Path*: SCRIPT → MEDIA_UPLOAD → SYNC → AUDIO_CREATOR → DUBBING

**Crucially:** 0 changes have been made to the internal logic of the existing agents. The orchestration layer wraps around them cleanly.

## 5. Immediate Next Goal: Phase 4 (Persistent Async Jobs)
**You are tasked with implementing Phase 4.**
Currently, when a stage is invoked via the API, the `StageExecutor` uses `asyncio.create_task()` to run the job in the background and tracks it in memory (in the `JobRepository`).
- **The Problem:** If the FastAPI server restarts or crashes, all running jobs are lost, and the state becomes orphaned.
- **The Solution:** We need to implement a **Task Queue** system.
- **Your Task:**
  1. Replace the in-memory job tracking with a persistent Database solution.
  2. Implement a proper async task queue. (Discuss the specific library stack with the user, e.g., Celery + Redis, APScheduler, or a lightweight DB-backed queue).
  3. Ensure jobs can be recovered on server restart.
  4. Ensure job progress tracking still works and status updates are persisted.
  5. Add timeout and cancellation handling for jobs.

## 6. Project Structure Overview
```text
backend/
├── app/
│   ├── agents/          # Internal logic for the 7 agents (DO NOT MODIFY without reason)
│   ├── api/routes/      # FastAPI REST endpoints (projects, chat, media, approvals)
│   ├── orchestration/   # DAG logic, StageExecutor, Compliance Decorator, Chat Router
│   ├── persistence/     # SQLite database logic (ProjectRepository, JobRepository)
│   ├── shared/          
│   │   ├── models/      # Shared Pydantic schemas (ProjectState is the core contract)
│   │   └── tools/       # Shared deterministic tools (ffmpeg, ffprobe, Parallel API, Gemini API)
│   └── main.py          # FastAPI application entry point
├── scripts/             # Testing and demo scripts (demo_simple.py, demo_phase2.py, demo_complete.py)
└── tests/               # 60+ individual agent unit/integration tests
```

## 7. Guidelines for Development
- Do not make changes to existing agent implementations (`backend/app/agents/`) unless strictly necessary for Phase 4.
- Follow the established pattern of using Pydantic for data validation.
- Maintain the strict separation of concerns: APIs handle HTTP, Orchestrator handles DAG logic, Persistence handles DB, Agents handle reasoning.
- When writing tests, avoid committing binary media files. Follow the Syncer agent's pattern of using `ffmpeg -f lavfi` to generate synthetic media fixtures in memory during tests.
