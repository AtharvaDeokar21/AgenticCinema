# Agentic Cinema Backend — API Reference

This document provides a detailed breakdown of all available API routes, their methods, payloads, and responsibilities within the Agentic Cinema pipeline.

---

## 1. Projects Router (`/projects`)
**File:** `app/api/routes/projects.py`
**Responsibility:** Project lifecycle management, status retrieval, and pipeline overview.

### `POST /projects`
* **Description:** Create a new project workspace.
* **Payload:**
  ```json
  {
    "project_name": "My Epic Short Film",
    "workflow_config": {
      "audio_mode": "AI_VOICE",
      "target_locales": ["es-ES", "fr-FR"]
    }
  }
  ```
* **Returns:** The newly created `ProjectState` with `current_stage: CREATED`.

### `GET /projects/{project_id}`
* **Description:** Fetch the complete state of a project.
* **Returns:** A highly detailed JSON payload containing:
  - `completed_stages` & `ready_stages`
  - `script` (including all beats and timestamps)
  - `storyboard` (including all shots and descriptions)
  - `audio` (metadata for generated/extracted voices)
  - `sync_report` (the exact mapping of audio to lip movements)
  - `dub_tracks` (paths to the translated audio)

### `DELETE /projects/{project_id}`
* **Description:** Delete a project and completely wipe its directory in `/storage`.
* **Returns:** `200 OK`

---

## 2. Media Router (`/projects/{project_id}/media`)
**File:** `app/api/routes/media.py`
**Responsibility:** Handling file uploads (videos/audio).

### `POST /projects/{project_id}/media`
* **Description:** Upload a media asset (e.g., the creator's video performance).
* **Payload:** `multipart/form-data` with a file attached.
* **Returns:**
  ```json
  {
    "media_id": "media_abc123",
    "file_path": "/storage/ee7675.../media_abc123.mp4",
    "file_size": 1048576,
    "completed_stages": ["...", "MEDIA_UPLOAD"],
    "ready_stages": ["SYNC"]
  }
  ```

---

## 3. Chat Router (`/projects/{project_id}/chat`)
**File:** `app/api/routes/chat_approval.py` & `app/orchestration/chat_router.py`
**Responsibility:** The natural language interface for controlling the entire pipeline. The router parses the intent of the message and automatically queues background jobs or updates configurations.

### `POST /projects/{project_id}/chat`
* **Description:** Send a natural language message to the orchestration layer.

**Supported Intents & Payloads:**

1. **Write Script (`SCRIPT` stage)**
   - **Payload:** `{ "message": "Write a 3-beat script about cyberpunk coffee." }`
   - **Action:** Triggers the Script Suggestor Agent.

2. **Generate Storyboard (`STORYBOARD` stage)**
   - **Payload:** `{ "message": "Generate storyboard for this script." }`
   - **Action:** Triggers the Storyboard Agent.

3. **Generate AI Audio (`AUDIO_AI` stage)**
   - **Payload:** `{ "message": "Generate audio for this script." }`
   - **Action:** Triggers the Audio Agent to generate TTS voices via Gemini.

4. **Sync Audio (`SYNC` stage)**
   - **Payload:** `{ "message": "Sync audio." }`
   - **Action:** Triggers the Syncer Agent to analyze the uploaded video and map lip movements to the audio clips.

5. **Generate Dubbing (`DUBBING` stage)**
   - **Payload:** `{ "message": "Generate dubbing." }`
   - **Action:** Triggers the Cultural Dubbing Agent.

6. **Switch to Creator Voice**
   - **Payload:** `{ "message": "Use my voice instead." }`
   - **Action:** Updates `project.workflow_config.audio_mode` to `CREATOR_VOICE`.

---

## 4. Background Worker (Internal)
**File:** `app/worker.py`
**Responsibility:** Continuously polls the `JobRepository` SQLite database for queued jobs (submitted by the Chat Router). When it picks up a job, it executes the corresponding Python Agent logic (e.g., `SyncerAgent.run()`), saves the result to the `ProjectRepository`, and updates `completed_stages`.
