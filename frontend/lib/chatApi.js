/* ============================================================
   The chat endpoint. Same pattern as lib/api.js: one place that
   knows how to reach the backend.
   ============================================================ */
import { API_BASE, DEMO } from "@/lib/api";

/* ---- change this to match your FastAPI route ---- */
export const CHAT_ENDPOINT = "/chat";

const DIRECT = process.env.NEXT_PUBLIC_DIRECT === "1";
const FALLBACK = process.env.NEXT_PUBLIC_DEMO_FALLBACK === "1";

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function demoReply(text, files) {
  await sleep(900 + Math.random() * 700);
  const named = files.length
    ? `I have ${files.length} attachment${files.length > 1 ? "s" : ""} — ${files
        .map((f) => f.name)
        .join(", ")}. `
    : "";
  return {
    agent: "Orchestrator",
    text:
      `${named}The backend is not reachable, so this is a sample reply. ` +
      `Once it is running, this is where the crew answers, and any images, ` +
      `audio or files an agent produces appear underneath.`,
    images: [],
    audio: [],
    files: [],
    __demo: true,
  };
}

/**
 * Send one turn to the crew.
 *
 * @param {object}  turn
 * @param {string}  turn.project_id
 * @param {string}  turn.message      what the creator typed
 * @param {Array}   turn.history      [{role:"you"|"crew", text}] earlier turns
 * @param {File[]}  turn.files        images, video, audio, documents
 *
 * Response may be a bare string, {reply|text|message}, or the full shape:
 *   { agent, text, images:[{url,caption}], audio:[{url,label}],
 *     files:[{url,name}], state:{…ProjectState patch} }
 */
export async function sendToCrew({ project_id, message, history = [], files = [] }) {
  if (DEMO) return demoReply(message, files);

  const url = DIRECT ? `${API_BASE}${CHAT_ENDPOINT}` : "/api/chat";
  const payload = { project_id, message, history };

  let response;
  try {
    if (files.length) {
      /* FastAPI:
           async def chat(payload: str = Form(...),
                          files: list[UploadFile] = File(default=[])) */
      const body = new FormData();
      body.append("payload", JSON.stringify(payload));
      for (const file of files) body.append("files", file, file.name);
      response = await fetch(url, { method: "POST", body });
    } else {
      response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    }
  } catch {
    if (FALLBACK) return demoReply(message, files);
    throw new Error(`Could not reach the crew at ${API_BASE}${CHAT_ENDPOINT}.`);
  }

  if (!response.ok) {
    if (FALLBACK && response.status >= 500) return demoReply(message, files);
    const detail = await response.text().catch(() => "");
    throw new Error(`The crew returned ${response.status}. ${detail.slice(0, 200)}`);
  }

  const data = await response.json().catch(() => null);
  return normalise(data);
}

/* Accept whatever shape the backend already returns. */
function normalise(data) {
  if (typeof data === "string") return { text: data, images: [], audio: [], files: [] };
  if (!data) return { text: "(empty reply)", images: [], audio: [], files: [] };
  return {
    agent: data.agent || data.agent_name || null,
    text: data.text || data.reply || data.message || data.content || "",
    images: data.images || [],
    audio: data.audio || [],
    files: data.files || data.attachments || [],
    state: data.state || null,
  };
}
