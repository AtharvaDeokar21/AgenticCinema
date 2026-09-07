# Agentic Cinema: Creator Workflow & Routing Guide

Welcome to the **Agentic Cinema API Workflow Guide**. This document walks you through a real-world scenario of navigating the application as a Content Creator from start to finish using the Swagger UI.

---

## The Scenario
Imagine you are a Content Creator. You want the AI to write a script for a "Cyberpunk Coffee Commercial," generate a storyboard, and then you want to upload a video of yourself reading the script so the AI can sync your lip movements (Creator Voice) and dub it into Spanish!

Here is how you navigate that entire flow using our API.

---

## Step 1: Open Swagger UI
1. Ensure your backend server is running: `uvicorn app.main:app --reload`
2. Open your browser and navigate to: **http://127.0.0.1:8000/docs**
*(Note: Swagger UI sometimes hides `UploadFile` (multipart/form-data) forms depending on how the route is categorized, but you can find it under the `media` tag!)*

---

## Step 2: Initialize the Project
First, we need to create a blank canvas for our video.

1. **Endpoint:** `POST /projects`
2. **Payload:**
   ```json
   {
     "project_name": "Cyberpunk Coffee Ad",
     "audio_mode": "CREATOR_VOICE" 
   }
   ```
   *(We set `CREATOR_VOICE` because we intend to upload our own video later!)*
3. **Response:** Copy the `"project_id"` returned. You will use this ID for every subsequent step.

---

## Step 3: Chat Router (Trigger Script Generation)
Instead of manually triggering the script stage via the stage endpoint, let's use the intelligent Chat Router.

1. **Endpoint:** `POST /projects/{project_id}/chat`
2. **Payload:**
   ```json
   {
     "message": "Write script about a futuristic cyberpunk coffee brand."
   }
   ```
   *(Note: The router looks for specific intent phrases like "write script", "generate script", "redo script", or "start over").*
3. **What happens:** The Natural Language Router analyzes your intent. It realizes you want to generate a script and automatically queues a background job for the `SCRIPT` stage.
4. **Response:** It returns a `job_id`. 
5. **Wait for it:** You can poll `GET /projects/{project_id}/jobs/{job_id}` until the status is `"completed"`.

**See the Output:**
- Hit `GET /projects/{project_id}`
- Look at the `"script"` field in the response JSON. You will see the AI-generated 5-beat script!

---

## Step 4: Generate the Storyboard
Now let's tell the AI to create visuals for our script.

1. **Endpoint:** `POST /projects/{project_id}/chat`
2. **Payload:**
   ```json
   {
     "message": "Generate storyboard for this script."
   }
   ```
   *(Note: The router looks for intent phrases like "generate storyboard", "create storyboard", "redo shots", or "different visual").*
3. **What happens:** The Router triggers the `STORYBOARD` stage. The background worker runs `generate_full_pipeline` (which searches the web for visual references, plans shots, and generates image thumbnails).
4. **See the Output:** Wait for the job to complete, then hit `GET /projects/{project_id}`. Look at the `"storyboard"` field to see your Shot IDs, visual descriptions, and thumbnail paths!

---

## Step 5: Upload Your Creator Video
Since you chose `CREATOR_VOICE`, the AI expects a video of *you* speaking the script before it can proceed to Audio Sync.

1. **Endpoint:** `POST /projects/{project_id}/media`
2. **How to use in Swagger:** 
   - Expand the endpoint in Swagger.
   - Click "Try it out".
   - You will see a "Choose File" button. 
   - Select an `.mp4` video of yourself from your computer.
   - Click "Execute".
3. **What happens:** The file is saved to the `/storage` directory and marked in your `media_manifest`.

---

## Step 6: Sync & Extract Audio (The AUDIO / SYNC Stage)

**If using `AI_VOICE`:**
Let's trigger the Audio Agent via the Chat Router!
1. **Endpoint:** `POST /projects/{project_id}/chat`
2. **Payload:**
   ```json
   {
     "message": "Generate audio for this script."
   }
   ```
   *(Note: The router looks for intent phrases like "generate audio", "create voice", or "do audio").*
3. **What happens:** The Natural Language Router queues a background job for the `AUDIO_AI` stage.

**If using `CREATOR_VOICE` (You uploaded a video):**
Let's trigger the Sync Agent to extract your voice and lip sync timestamps.
1. **Endpoint:** `POST /projects/{project_id}/chat`
2. **Payload:**
   ```json
   {
     "message": "Sync audio."
   }
   ```
   *(Note: The router looks for intent phrases like "generate sync", "extract audio", or "sync audio").*
3. **What happens:** The `SyncerAgent` is invoked. It analyzes the video, finds where your lips move, maps the timestamps, and extracts the `.wav` audio.

**See the Output:** Hit `GET /projects/{project_id}` and look at the `"audio"` or `"sync_report"` section!

---

## Step 7: Cultural Dubbing
Finally, let's dub your generated audio into Spanish.

1. **Endpoint:** `POST /projects/{project_id}/chat`
2. **Payload:**
   ```json
   {
     "message": "Generate dubbing."
   }
   ```
   *(Note: The router looks for intent phrases like "generate dub", "create translation", or "translate").*
3. **What happens:** The Router triggers the `DUBBING` stage. The `CulturalDubAgent` takes the synced audio, translates it, adjusts it for cultural nuances, and generates the Spanish dub track.
4. **See the Output:** Hit `GET /projects/{project_id}` and check the `"dub_tracks"` array.

---

## Summary of How to See Input/Output
Because Agentic Cinema uses a background asynchronous worker:
- **Inputs** are provided via `POST` requests to `/chat` or `/stages/{stage_name}`.
- **Outputs** are ALWAYS stored in the central Project State.
- To see the **latest output of any agent**, you simply call `GET /projects/{project_id}`. The JSON returned is a massive nested object that acts as the "single source of truth" containing the script, storyboard, audio, sync map, and dubs!
