# Agentic Cinema Backend: Developer Guide

Welcome to the backend of Agentic Cinema! This guide is designed to help you run the server locally, execute the test suites, and seamlessly integrate the frontend with the backend APIs.

## 1. Setup & Environment

**Prerequisites:** Python 3.11+ 

1. **Activate the Virtual Environment:**
   ```bash
   source .venv/bin/activate
   ```
2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Environment Variables:**
   Ensure your `.env` file is populated in the `backend/` directory. You will need your Gemini API key:
   ```env
   GEMINI_API_KEY="your_actual_key_here"
   GEMINI_MODEL="gemini-1.5-flash"
   ```

---

## 2. Running the Backend Locally

The backend relies on two components that run concurrently in a single process:
1. **The FastAPI HTTP Server**: Handles incoming requests from the frontend.
2. **The Async Background Worker**: Polls the SQLite database for queued jobs and executes AI stages.

**To start the server:**
```bash
uvicorn app.main:app --reload --port 8000
```
- The API will be available at: `http://localhost:8000`
- Interactive API Documentation (Swagger UI): `http://localhost:8000/docs`

*(Note: The background worker automatically starts up and shuts down via FastAPI's `lifespan` manager, so you only need to run the `uvicorn` command).*

---

## 3. Running the Test Suite

The backend has a comprehensive E2E (End-to-End) test suite utilizing Pytest. 

**To run the tests:**
```bash
pytest tests/e2e/ -v --tb=short
```

### What Happens in the Tests & Mocks?
Our tests are designed to validate the **entire orchestration logic** (the worker, compliance loop, routing, and schema validation) without actually hitting external AI APIs. This ensures rapid test execution and prevents exhausting API quotas.

- **What is Mocked:** The `GeminiClient` in `conftest.py` is fully mocked. Instead of calling out to Google's LLM, it intercepts the call and directly returns hardcoded, valid Pydantic models (like `ScriptVersion`, `ProductionAwareStoryboard`, `AudioSegment`, and `SyncMap`). 
- **What is NOT Mocked:** The actual agent execution logic, the Pydantic schema validation, the Background Worker loop, and the SQLite persistence are **all real**. If a mock returns invalid data, the exact same Pydantic validation errors will trigger as if the real LLM hallucinated the wrong schema!
- **Agent Integration:** All agents (`ScriptAgent`, `StoryboardAgent`, `AudioAgent`, `SyncerAgent`, `CulturalDubAgent`) are currently wired into the `worker.py` execution loop and fully utilize their complete functional logic (e.g., storyboard runs its `generate_full_pipeline`, audio utilizes `AI_VOICE` and `CREATOR_VOICE` modes).

### Test Coverage:
- `test_ai_voice_workflow.py`: Simulates the frontend driving the **FULL pipeline**: `SCRIPT` → `STORYBOARD` → `AUDIO_AI` → `SYNC` → `DUBBING`.
- `test_compliance_flow.py`: Injects a `YELLOW` risk, ensures the worker blocks, triggers the `/approve` API, and verifies the worker resumes.
- `test_chat_routing.py`: Validates that AI chat intents accurately map to the correct backend actions.
- `test_job_recovery.py`: Validates that crashed jobs automatically revert to `queued` on server startup.

---

## 4. Frontend Integration Guide

The system uses an asynchronous, polling-based architecture. The frontend **never** waits for an AI job to complete during the initial HTTP request.

### A. The Core Workflow Loop

Whenever the frontend wants the AI to do something, it follows a 3-step loop:

1. **Trigger an Action:** The frontend calls a `POST` endpoint (e.g., `POST /projects/{id}/stages/SCRIPT`).
2. **Receive a Job ID:** The API returns immediately with a `job_id` and a `status: "queued"`.
3. **Poll for Completion:** The frontend repeatedly hits `GET /projects/{id}/jobs/{job_id}` every 2-3 seconds until the status is `completed` or `failed`.

### B. Essential API Endpoints

#### Project Management
- `POST /projects` — Create a new empty project. Returns `{ "project_id": "uuid" }`.
- `GET /projects` — List all projects.
- `GET /projects/{id}` — Fetch the full `ProjectState` (contains the actual generated script, storyboard, etc.).

#### Driving the Pipeline (Stages)
- `POST /projects/{id}/stages/{stage_name}` — Queues an AI agent to run.
  - *Valid stages:* `SCRIPT`, `STORYBOARD`, `AUDIO_AI`, `SYNC_PREP`, `DUB_TRACKS`.
  - *Response:* `{ "job_id": "...", "status": "queued" }`

#### Monitoring Jobs (Polling)
- `GET /projects/{id}/jobs/{job_id}` — Check the progress of a job.
  - Returns: `{ "status": "running", "progress": 45.0, ... }`
  - *Note: Stop polling when status hits `completed` or `failed`.*

#### Compliance & Human-in-the-Loop
After every stage, the backend runs a compliance check. If it flags a `YELLOW` risk, the pipeline pauses.
- `GET /projects/{id}/compliance/pending` — Fetch any blocked checkpoints waiting for human approval.
- `POST /projects/{id}/approve` — Send the user's approval decision.
  - Payload: `{ "checkpoint_id": "uuid", "decisions": [] }`
  - Once approved, the worker automatically unblocks and resumes.

#### Conversational Interface (Chat)
- `POST /projects/{id}/chat` — The user types a message (e.g., "Regenerate the storyboard!").
  - Payload: `{ "message": "..." }`
  - Response: `{ "intent": "regenerate_storyboard", "job_id": "uuid" }`
  - *Note: If `job_id` is present, the backend automatically queued the action. The frontend should immediately start polling that `job_id`.*

---

## 5. Important Notes for Frontend Developers

- **State is King:** The single source of truth is the `ProjectState`. When a job completes, hit `GET /projects/{id}` to download the fresh data (the script text, the image URLs, etc.) and update your React/Vue state.
- **Handling 503s:** The backend uses the free tier of the Gemini API, which often throws `503 Unavailable` or `429 Resource Exhausted` errors. If a job fails with this error, simply show a toast message to the user ("AI is busy") and let them click the button to try again.
- **Data Schemas:** Familiarize yourself with the data models in `backend/app/shared/models/`. This dictates exactly how the JSON payload will be structured when you fetch a project.
