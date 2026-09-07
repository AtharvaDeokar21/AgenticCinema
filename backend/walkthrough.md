1. **Activate the Virtual Environment:**

   ```bash
   source .venv/bin/activate
   ```

2. **Install Dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

**To start the server:**

```bash
uvicorn app.main:app --reload --port 8000
```

- The API will be available at: `http://localhost:8000`
- Interactive API Documentation (Swagger UI): `http://localhost:8000/docs`

# Agentic Cinema: Chat & Workflow Scenarios Walkthrough

This document outlines all possible scenarios, prompts, outputs, and subsequent steps when testing the Agentic Cinema backend via the Swagger UI.

## Scenario 1: AI-Generated Voice Workflow

In this scenario, you want to generate a script, storyboard, and use Google Gemini to generate **AI Voices** (Text-to-Speech) for your characters.

### 1. Generate the Script

* **Endpoint:** `POST /projects/{id}/chat`
- **Payload:** `{ "message": "Write a 3-beat script about a futuristic cyberpunk coffee brand." }`
- **Output:** A background job is queued for the `SCRIPT` stage.
- **Next Step:** Hit `GET /projects/{id}` to see the generated `script.beats`.

### 2. Generate the Storyboard

* **Endpoint:** `POST /projects/{id}/chat`
- **Payload:** `{ "message": "Generate storyboard for this script." }`
- **Output:** A background job is queued for the `STORYBOARD` stage.
- **Next Step:** Hit `GET /projects/{id}` to see the generated `storyboard.shots`.

### 3. Generate AI Voices (Audio)

* **Endpoint:** `POST /projects/{id}/chat`
- **Payload:** `{ "message": "Generate audio for this script." }`
- **Output:** A background job is queued for the `AUDIO_AI` stage. The `AudioAgent` generates voice lines using Gemini TTS and creates `AudioMaster` segments.
- **Next Step:** Upload a video to sync the AI voices to.

### 4. Upload a Video

* **Endpoint:** `POST /projects/{id}/media` (multipart/form-data)
- **Payload:** Attach an `.mp4` video.
- **Output:** The video is saved to `project.media_manifest.assets`.
- **Next Step:** Tell the agent to sync the audio to the video.

### 5. Sync the Audio to the Video

* **Endpoint:** `POST /projects/{id}/chat`
- **Payload:** `{ "message": "Sync audio." }`
- **Output:** The `SyncerAgent` watches the video using Gemini Vision, identifies lip movements, and returns a `sync_report` with exact placement timestamps.
- **Next Step:** Hit `GET /projects/{id}` to see the `sync_report`. If successful, proceed to Dubbing!

### 6. Cultural Dubbing

* **Endpoint:** `POST /projects/{id}/chat`
- **Payload:** `{ "message": "Generate dubbing." }`
- **Output:** The `CulturalDubAgent` translates the synced audio track into the target locales (default: Spanish) and returns `dub_tracks`.
- **Next Step:** Hit `GET /projects/{id}` to see the `dub_tracks`.

---

## Scenario 2: Creator Voice Workflow

In this scenario, you perform the script yourself on camera, and the backend extracts **your voice** from the video!

### 1. Set Audio Mode to Creator Voice

* **Endpoint:** `POST /projects/{id}/chat`
- **Payload:** `{ "message": "Use my voice." }`
- **Output:** Returns a response indicating `audio_mode` was updated to `CREATOR_VOICE`.

### 2. Upload Your Performance Video

* **Endpoint:** `POST /projects/{id}/media` (multipart/form-data)
- **Payload:** Attach your `.mp4` video of you speaking the lines.
- **Output:** The video is saved to `project.media_manifest.assets`.

### 3. Extract & Sync (AUDIO_CREATOR -> SYNC)

* **Endpoint:** `POST /projects/{id}/chat`
- **Payload:** `{ "message": "Sync audio." }`
- **Output:** Because you are in `CREATOR_VOICE` mode, the `AudioAgent` extracts your real voice from the video, and the `SyncerAgent` maps your lip movements to the script beats.
- **Next Step:** Hit `GET /projects/{id}` to see both the `audio_master` and the `sync_report`.

---

## Scenario 3: Regenerating / Iterating

If you are unhappy with the script or the storyboard, you can ask the router to redo it!

### Redoing the Script

* **Endpoint:** `POST /projects/{id}/chat`
- **Payload:** `{ "message": "Regenerate the script, make it more upbeat." }`
- **Output:** The `SCRIPT` stage is re-triggered with the `regenerate: true` parameter.

### Redoing the Storyboard

* **Endpoint:** `POST /projects/{id}/chat`
- **Payload:** `{ "message": "Redo the shots, use a different visual style." }`
- **Output:** The `STORYBOARD` stage is re-triggered.

---

## Scenario 4: Creator Scout Workflow (Brand Sponsorships)

In this scenario, you want to use the `CreatorScoutAgent` to discover relevant brands and collaboration opportunities based on your niche. This runs completely independently of the video-creation pipeline!

### Discovering Brands

* **Endpoint:** `POST /projects/{id}/chat`
- **Payload:** `{ "message": "Scout brands for a cinematic tech creator on YouTube with 500k views and 5% engagement." }`
- **Output:** A background job is queued for the `CREATOR_SCOUT` stage. The Chat Router will extract the context you provided and pass it directly to the Scout Agent! The agent searches the web and ranks the best sponsorship deals for your specific niche.
- **Next Step:** Hit `GET /projects/{id}` and look at the huge `"opportunity_queue"` JSON object at the bottom to see your deals!

---

## Handled Fallbacks

- **No Video Uploaded:** If you run `SYNC` without uploading a video, the worker gracefully falls back to a dummy video. Gemini Vision will detect it's a dummy video (e.g. grass) and intelligently place the audio clips back-to-back using their raw durations instead of lip-syncing!
- **Rate Limits:** If Gemini throws a `503 UNAVAILABLE` during audio generation, it will gracefully save whatever segments it *did* manage to generate as a "partial" success!
