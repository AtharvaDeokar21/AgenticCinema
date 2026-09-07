/* ============================================================
   The only file that talks to your FastAPI backend.

   Point NEXT_PUBLIC_API_BASE at the backend, and correct the six
   paths below to match your actual routes. Nothing else needs to
   change anywhere in the frontend.
   ============================================================ */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

/* Every request goes through the Next route handler at /api/agent/[agent]
   so the browser never hits a different origin — no CORS setup needed on
   the FastAPI side. Set NEXT_PUBLIC_DIRECT=1 to bypass the proxy. */
const DIRECT = process.env.NEXT_PUBLIC_DIRECT === "1";

/* Demo mode returns the fixtures in lib/fixtures.js instead of calling
   the backend. NEXT_PUBLIC_DEMO=1 forces it; NEXT_PUBLIC_DEMO_FALLBACK=1
   only falls back when the backend is unreachable, which is the setting
   you want on stage. */
export const DEMO = process.env.NEXT_PUBLIC_DEMO === "1";
const FALLBACK = process.env.NEXT_PUBLIC_DEMO_FALLBACK === "1";

/* ---- change these to match your FastAPI routes ---- */
export const ENDPOINTS = {
  creator_scout: "/agents/creator-scout/run",
  script_suggestor: "/agents/script-suggestor/run",
  storyboard: "/agents/storyboard/run",
  audio: "/agents/audio/run",
  syncer: "/agents/syncer/run",
  cultural_dub: "/agents/cultural-dub/run",
  compliance: "/agents/compliance/run",
};

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function demoResult(agentKey) {
  const { fixtures } = await import("@/lib/fixtures");
  await sleep(1400 + Math.random() * 900);
  return { ...fixtures[agentKey], __demo: true };
}

/**
 * Run one agent.
 *
 * @param {string} agentKey  e.g. "script_suggestor"
 * @param {object} payload   { project_id, ...form values, ...upstream ProjectState }
 * @param {File}   [file]    optional upload; switches the request to multipart
 * @returns the agent's Pydantic object, parsed from JSON
 */
export async function runAgent(agentKey, payload, file) {
  if (DEMO) return demoResult(agentKey);

  const url = DIRECT
    ? `${API_BASE}${ENDPOINTS[agentKey]}`
    : `/api/agent/${agentKey}`;

  let response;
  try {
    if (file) {
      /* FastAPI side:
           async def run(payload: str = Form(...), file: UploadFile = File(None)) */
      const body = new FormData();
      body.append("payload", JSON.stringify(payload));
      body.append("file", file, file.name);
      response = await fetch(url, { method: "POST", body });
    } else {
      response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    }
  } catch (networkError) {
    if (FALLBACK) return demoResult(agentKey);
    throw new Error(
      `Could not reach the backend at ${API_BASE}. Is it running?`
    );
  }

  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    if (FALLBACK && response.status >= 500) return demoResult(agentKey);
    throw new Error(
      `${agentKey} returned ${response.status}. ${detail.slice(0, 220)}`
    );
  }

  return response.json();
}
