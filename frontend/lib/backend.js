// frontend/lib/backend.js
//
// One function per backend route, all going through the same-origin proxy.
// No component should ever call fetch() directly — if a route changes, it
// changes here and nowhere else.

import { PROXY_PREFIX, JOB_TIMEOUT_MS, POLL_START_MS, POLL_MAX_MS } from "@/lib/api";

async function request(path, options = {}) {
  const res = await fetch(`${PROXY_PREFIX}${path}`, {
    ...options,
    headers:
      options.body instanceof FormData || !options.body
        ? options.headers
        : { "Content-Type": "application/json", ...options.headers },
  });

  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${res.status} — ${detail.slice(0, 300)}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

/* ---------- projects ---------- */

export const listProjects = () => request("/projects");

export const createProject = (projectName, workflowConfig = {}) =>
  request("/projects", {
    method: "POST",
    body: JSON.stringify({
      project_name: projectName,
      workflow_config: {
        audio_mode: "AI_VOICE",
        target_locales: [],
        request_approval_for_yellow: true,
        ...workflowConfig,
      },
    }),
  });

// The single source of truth. Re-read this after every job completes.
export const getProject = (id) => request(`/projects/${id}`);

export const deleteProject = (id) => request(`/projects/${id}`, { method: "DELETE" });

// Which stages are legally runnable right now — use it to enable/disable UI.
export const getAvailableStages = (id) => request(`/projects/${id}/dag`);

export const runStage = (id, stage) =>
  request(`/projects/${id}/stages/${stage}`, { method: "POST", body: JSON.stringify({}), });

/* ---------- chat: a command channel, not a conversation API ---------- */

export const sendMessage = (id, message) =>
  request(`/projects/${id}/chat`, { method: "POST", body: JSON.stringify({ message }) });

/* ---------- jobs ---------- */

export const listJobs = (id) => request(`/projects/${id}/jobs`);
export const getJob = (id, jobId) => request(`/projects/${id}/jobs/${jobId}`);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// The chat response shape is not pinned down in the API docs, so accept any of
// the plausible carriers rather than guessing one and breaking on the others.
export function extractJobId(queued) {
  if (!queued) return null;
  if (Array.isArray(queued)) return extractJobId(queued[queued.length - 1]);
  return (
    queued.job_id ??
    queued.id ??
    queued.job?.job_id ??
    queued.job?.id ??
    (Array.isArray(queued.jobs) ? extractJobId(queued.jobs) : null)
  );
}

export async function waitForJob(projectId, jobId, { onTick } = {}) {
  const deadline = Date.now() + JOB_TIMEOUT_MS;
  let delay = POLL_START_MS;

  while (Date.now() < deadline) {
    const job = await getJob(projectId, jobId);
    onTick?.(job);

    const status = String(job.status ?? "").toLowerCase();
    if (status === "completed" || status === "succeeded") return job;
    if (status === "failed" || status === "error") {
      throw new Error(job.error ?? job.detail ?? "The job failed.");
    }
    // "blocked"/"awaiting_approval" is not a failure — the caller checks
    // compliance and surfaces an approval prompt instead of an error.
    if (status.includes("block") || status.includes("approval")) return job;

    await sleep(delay);
    delay = Math.min(delay * 1.4, POLL_MAX_MS);
  }
  throw new Error("Timed out waiting for the job to finish.");
}

/* ---------- compliance ---------- */

export const getPendingCheckpoints = (id) => request(`/projects/${id}/compliance/pending`);
export const getComplianceHistory = (id) => request(`/projects/${id}/compliance/history`);

export const approveCheckpoint = (id, checkpointId, comment = "Approved.") =>
  request(`/projects/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({ checkpoint_id: checkpointId, comment }),
  });

/* ---------- assets (binary) ---------- */

// Returns a same-origin URL. Hand it straight to <img>, <audio> or a download
// link — no fetch, no blob, no object URL to revoke.
export function assetUrl(projectId, { type, shotId, language, bust }) {
  const params = new URLSearchParams({ type });
  if (shotId) params.set("shot_id", shotId);
  if (language) params.set("language", language);
  if (bust) params.set("v", bust); // cache-buster after a regenerate
  return `${PROXY_PREFIX}/projects/${projectId}/assets?${params}`;
}

/* ---------- creator media ---------- */

export function uploadMedia(projectId, file) {
  const body = new FormData();
  body.append("file", file, file.name); // never set Content-Type by hand
  return request(`/projects/${projectId}/media`, { method: "POST", body });
}

export const getMedia = (projectId, mediaId) =>
  request(`/projects/${projectId}/media/${mediaId}`);

export const deleteMedia = (projectId, mediaId) =>
  request(`/projects/${projectId}/media/${mediaId}`, { method: "DELETE" });