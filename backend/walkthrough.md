# Agentic Cinema: Final Demo Walkthrough

This document outlines the exact endpoints and payloads you should use during your final demo presentation to showcase the Agentic Cinema backend. It assumes the server is running locally on port 8000.

## Setup & Initialization

**1. Start the server:**
```bash
uvicorn app.main:app --reload --port 8000
```
- API will be available at: `http://localhost:8000`
- Swagger UI (for demoing): `http://localhost:8000/docs`

**2. Create a new Project (Workspace):**
- **Endpoint:** `POST /projects`
- **Payload:**
```json
{
  "project_name": "Cyberpunk Coffee Ad",
  "workflow_config": {
    "audio_mode": "AI_VOICE",
    "request_approval_for_yellow": true
  }
}
```
*Note down the `project_id` returned for the rest of the demo.*

---

## Scenario 1: The Core Pipeline (Script -> Storyboard -> Audio)
Showcase the primary multi-agent workflow where users orchestrate generation entirely via natural language chat.

### 1. Generate the Script
- **Endpoint:** `POST /projects/{project_id}/chat`
- **Payload:** 
```json
{ 
  "message": "Write a 3-beat script about a futuristic cyberpunk coffee brand." 
}
```
*Wait ~10 seconds. Check progress via `GET /projects/{project_id}` until `"SCRIPT"` appears in `completed_stages`.*

### 2. Generate the Storyboard & Thumbnails
- **Endpoint:** `POST /projects/{project_id}/chat`
- **Payload:** 
```json
{ 
  "message": "Generate storyboard for this script." 
}
```
*Wait ~15 seconds. Check progress via `GET /projects/{project_id}`.*

### 3. Generate the AI Voiceover
- **Endpoint:** `POST /projects/{project_id}/chat`
- **Payload:** 
```json
{ 
  "message": "Generate audio for this script." 
}
```

---

## Scenario 2: Dynamic Cultural Dubbing
Demonstrate the LLM-driven Regex parsing by passing natural language instructions to perform cultural translation and dubbing.

- **Endpoint:** `POST /projects/{project_id}/chat`
- **Payload:** 
```json
{ 
  "message": "Translate the audio into Japanese." 
}
```
*(You can also use "Dub in Spanish", "Translate to Hindi", etc. The regex engine will extract the exact language and dynamically inject it into the pipeline).*

---

## Scenario 3: Human-in-the-Loop Compliance
Demonstrate how the system blocks on sensitive topics (e.g. Creator Scouting) and waits for human approval before proceeding.

### 1. Trigger a sensitive job
- **Endpoint:** `POST /projects/{project_id}/chat`
- **Payload:** 
```json
{ 
  "message": "Find brand deals for a cinematic filmmaker." 
}
```

### 2. View Blocked Jobs
- **Endpoint:** `GET /projects/{project_id}/compliance/pending`
- *Shows a YELLOW flagged compliance checkpoint waiting for approval.*

### 3. Approve the Job
- **Endpoint:** `POST /projects/{project_id}/approve`
- **Payload:** 
```json
{ 
  "checkpoint_id": "<COPY_CHECKPOINT_ID_FROM_PREVIOUS_STEP>",
  "comment": "Approved for demo."
}
```

---

## Scenario 4: Fetching Generated Media Assets
Demonstrate how the API serves binary files directly from the internal filesystem database.

### 1. Fetch AI Audio Master
```bash
curl -X GET "http://127.0.0.1:8000/projects/{project_id}/assets?type=audio_master" --output master.wav
```

### 2. Fetch Storyboard Video Thumbnail
```bash
curl -X GET "http://127.0.0.1:8000/projects/{project_id}/assets?type=video_thumbnail&shot_id=01" --output thumbnail_01.png
```

### 3. Fetch Culturally Dubbed Track
```bash
curl -X GET "http://127.0.0.1:8000/projects/{project_id}/assets?type=dub_track&language=Japanese-Generic" --output dub_ja.wav
```

---

## Scenario 5: Creator Voice Workflow
Demonstrate how users can override the default AI Voice pipeline and upload their own media for lip-syncing and dubbing.

### 1. Override Workflow Mode via Chat
- **Endpoint:** `POST /projects/{project_id}/chat`
- **Payload:** 
```json
{ 
  "message": "Use my voice instead." 
}
```

### 2. Upload Creator Media
- **Endpoint:** `POST /projects/{project_id}/media`
- **Payload:** Upload a `.mp4` or `.wav` file as `multipart/form-data`.

### 3. Sync Audio
- **Endpoint:** `POST /projects/{project_id}/chat`
- **Payload:** 
```json
{ 
  "message": "Sync audio." 
}
```

### 4. Extract Creator Voice
- **Endpoint:** `POST /projects/{project_id}/chat`
- **Payload:** 
```json
{ 
  "message": "Extract my voice." 
}
```
