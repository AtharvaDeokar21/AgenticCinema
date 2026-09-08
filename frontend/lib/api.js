// // file path= frontend/lib/api.js
// export const API_BASE = "http://localhost:8000"; // your FastAPI backend URL
// export const DEMO = false;



// frontend/lib/api.js
//
// Client-side constants only. The backend URL deliberately does NOT live here
// any more — it is read from process.env.BACKEND_URL inside the proxy route,
// which runs on the server. Anything exported from this file can end up in the
// browser bundle, so nothing secret or environment-specific belongs in it.
 
export const PROXY_PREFIX = "/api/backend";
 
// How long the UI waits for one generation job before giving up.
// Storyboards are the slow stage; 3 minutes is generous but finite.
export const JOB_TIMEOUT_MS = 900_000;
 
// Poll cadence, backing off so a slow stage does not hammer the API.
export const POLL_START_MS = 1_000;
export const POLL_MAX_MS = 5_000;
 
