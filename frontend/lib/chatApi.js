// frontend/lib/chatApi.js
//
// One chat turn:
//   upload attachments -> send the command -> if a job was queued, wait for it
//   -> re-read project state -> turn what changed into a message the crew "said"
//
// The backend's chat router answers in `response` and queues work via `job_id`.
// A `clarify` turn has no job, so its text is shown directly instead of polling
// for work that was never queued.

import {
  assetUrl,
  createProject,
  extractJobId,
  getPendingCheckpoints,
  getProject,
  runStage,
  sendMessage,
  uploadMedia,
  waitForJob,
} from "@/lib/backend";

const STORAGE_KEY = "agentic-cinema:project-id";

/* ---------- project lifecycle ---------- */

export async function ensureProject(name = "Untitled project") {
  if (typeof window !== "undefined") {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved) {
      try {
        const existing = await getProject(saved);
        return existing.project_id ?? existing.id ?? saved;
      } catch {
        window.localStorage.removeItem(STORAGE_KEY); // stale after a backend wipe
      }
    }
  }

  const created = await createProject(name);
  const id = created.project_id ?? created.id;
  if (!id) throw new Error("POST /projects did not return a project id.");
  if (typeof window !== "undefined") window.localStorage.setItem(STORAGE_KEY, id);
  return id;
}

export function forgetProject() {
  if (typeof window !== "undefined") window.localStorage.removeItem(STORAGE_KEY);
}

/* ---------- intent fallback ----------
   The NL router currently answers "clarify" for messages that plainly name a
   stage. When that happens and the wording is unambiguous, drive the stage
   endpoint directly rather than leaving the user stuck. Delete this map once
   the router is fixed. */

const STAGE_HINTS = [
  [/\b(script|write|beats?)\b/i, "SCRIPT"],
  [/\b(storyboard|shots?|board)\b/i, "STORYBOARD"],
  [/\b(voice ?over|audio|narrat)/i, "AUDIO_AI"],
  [/\b(dub|translate)\b/i, "DUBBING"],
  [/\b(brand deals?|sponsor|scout)\b/i, "CREATOR_SCOUT"],
  [/\bsync\b/i, "SYNC"],
];

const guessStage = (text) => STAGE_HINTS.find(([re]) => re.test(text))?.[1] ?? null;

/* ---------- one turn ---------- */

export async function sendToCrew({ project_id, message, files = [], onStatus }) {
  if (!project_id) throw new Error("No project id — the workspace was not created.");

  const before = await getProject(project_id).catch(() => ({}));
  const uploaded = [];

  for (const file of files) {
    onStatus?.(`Uploading ${file.name}…`);
    uploaded.push(await uploadMedia(project_id, file));
  }

  const text = message?.trim();
  if (!text) {
    return reply({
      agent: "Media",
      text: `Uploaded ${uploaded.length} file${uploaded.length === 1 ? "" : "s"}. Say what to do with it — "sync audio" or "extract my voice".`,
    });
  }

  onStatus?.("Sending to the crew…");
  const queued = await sendMessage(project_id, text);

  let jobId = queued.job_id ?? extractJobId(queued);
  let stage = queued.action?.stage ?? null;

  // No job queued. Either the router genuinely wants a clarification, or it
  // failed to parse something obvious — in which case run the stage directly.
  if (!jobId) {
    const fallback = guessStage(text);
    if (!fallback) {
      return reply({
        agent: queued.intent ?? "Orchestrator",
        text: queued.response ?? "No job was queued for that message.",
      });
    }
    onStatus?.(`Running ${fallback}…`);
    const forced = await runStage(project_id, fallback);
    jobId = forced.job_id ?? extractJobId(forced);
    stage = forced.stage ?? fallback;
    if (!jobId) {
      return reply({ agent: "Orchestrator", text: queued.response ?? "Could not start that stage." });
    }
  }

  onStatus?.("Working…");
  const job = await waitForJob(project_id, jobId, {
    onTick: (j) => onStatus?.(j.stage ? `${j.stage}: ${j.status}` : j.status),
  });

  // Compliance can hold a job instead of finishing it.
  const raw = await getPendingCheckpoints(project_id).catch(() => []);
  const pending = Array.isArray(raw) ? raw : raw?.checkpoints ?? raw?.pending ?? [];
  if (pending.length > 0) {
    const cp = pending[pending.length - 1];
    return reply({
      agent: "Compliance",
      text: `Held for review — ${cp.reason ?? cp.description ?? "flagged YELLOW"}. Approve it to let the job continue.`,
      checkpoint: cp,
    });
  }

  const after = await getProject(project_id);
  return describe(before, after, project_id, job?.stage ?? stage);
}

/* ---------- state -> transcript ---------- */

const stagesOf = (state) => new Set(state?.completed_stages ?? []);

function describe(before, after, projectId, stage) {
  // Trust the job's stage when we have it, so regenerating an already
  // completed stage still produces a reply. Fall back to a state diff.
  const gained = stage
    ? [stage]
    : [...stagesOf(after)].filter((s) => !stagesOf(before).has(s));

  const bust = Date.now(); // defeats the browser cache after a regenerate

  if (gained.includes("SCRIPT")) {
    return reply({ agent: "Script", text: scriptText(after) });
  }

      if (gained.some((s) => s.includes("STORYBOARD"))) {
    const shots = shotsOf(after);
    return reply({
      agent: "Storyboard",
      text: shots.map((s) => `${s.id}. ${s.meta}\n${s.caption}\n"${s.line}"`).join("\n\n"),
      images: shots.filter((s) => s.hasImage).map((shot) => ({
        url: assetUrl(projectId, { type: "storyboard", shotId: shot.id, bust }),
      })),
    });
  }

  if (gained.some((s) => s.includes("AUDIO"))) {
    return reply({
      agent: "Audio",
      text: "Voiceover is ready.",
      audio: [{ label: "Master", url: assetUrl(projectId, { type: "audio_master", bust }) }],
    });
  }

    if (gained.some((s) => s.includes("DUB"))) {
    const dubs = dubsOf(after);
    return reply({
      agent: "Cultural dub",
      text: dubs.length ? `Dubbed into ${dubs.map((d) => d.label).join(", ")}.` : "Dub track is ready.",
      audio: dubs.map((d) => ({
        label: d.label,
        url: assetUrl(projectId, { type: "dub_track", language: d.key, bust }),
      })),
    });
  }

  if (gained.includes("CREATOR_SCOUT")) {
    const opps = after.opportunity_queue?.opportunities ?? [];
    const fit = (o) => (o.overall_score == null ? "" : ` · fit ${Math.round(o.overall_score * 100)}%`);
    return reply({
      agent: "CreatorScout",
      text: opps.length
        ? opps.map((o) => `${o.rank ?? "•"}. ${o.brand_name}${o.category ? " · " + o.category : ""}${fit(o)}\n${o.rationale ?? ""}`).join("\n\n")
        : "No brand opportunities cleared the bar.",
      files: opps.filter((o) => o.program_url).map((o) => ({ name: `${o.brand_name} — creator program`, url: o.program_url })),
    });
  }

  if (gained.includes("SYNC")) {
    const notes = after.sync_report?.notes ?? [];
    return reply({
      agent: "Syncer",
      text: [`Sync ${after.sync_report?.status ?? "done"}.`, ...notes].join("\n"),
    });
  }

  return reply({
    agent: "Orchestrator",
    text: gained.length
      ? `Finished: ${gained.join(", ")}.`
      : "Done, but nothing new landed in project state. Check the jobs list.",
  });
}

/* ---------- field readers, pinned to the real ProjectState ---------- */

function scriptText(state) {
  const s = state.script;
  if (!s) return "Script generated.";
  const beats = (s.beats ?? []).map((b) => `${b.start_time}–${b.end_time}s   ${b.text}`);
  return [s.title, "", ...beats].join("\n");
}

// function shotsOf(state) {
//   // State stores "shot_1" or "shot_01" depending on the run; the asset route
//   // builds thumbnail_{shot_id}.png and wants the zero-padded form.
//   return (state.storyboard?.shots ?? []).map((shot) => ({
//     id: String(shot.shot_id).replace(/^shot_/, "").padStart(2, "0"),
//     caption: shot.visual_description ?? shot.subject ?? `Shot ${shot.shot_id}`,
//     line: shot.subject ?? "",
//     meta: [shot.shot_type, shot.camera_angle, shot.camera_movement].filter(Boolean).join(" · "),
//   }));
// }
function shotsOf(state) {
  return (state.storyboard?.shots ?? []).map((shot) => ({
    id: shot.shot_id,                                  // "shot_1", not padded
    caption: shot.visual_description ?? shot.subject ?? shot.shot_id,
    line: shot.subject ?? "",
    hasImage: shot.generated_image != null,
    meta: [shot.shot_type, shot.camera_angle, shot.camera_movement].filter(Boolean).join(" · "),
  }));
}

function dubsOf(state) {
  return (state.dub_tracks ?? [])
    .filter((t) => t.language)
    .map((t) => ({
      label: [t.language, t.geography].filter(Boolean).join("-"),
      key: `${t.language}-${t.geography}`,
    }));
}

const reply = (partial) => ({
  agent: null,
  text: "",
  images: [],
  audio: [],
  files: [],
  ...partial,
});