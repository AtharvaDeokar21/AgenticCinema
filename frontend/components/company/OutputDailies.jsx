"use client";

import { useState } from "react";

/* The right half of the stage: the agent's actual return value, rendered
   per Pydantic model. `raw` opens the untouched JSON, because on a judging
   panel someone always asks to see it. */

const time = (s) => {
  const n = Number(s) || 0;
  return `${String(Math.floor(n / 60)).padStart(2, "0")}:${String(Math.floor(n % 60)).padStart(2, "0")}`;
};
const pct = (n) => `${Math.round((Number(n) || 0) * 100)}%`;
const compact = (n) =>
  Number(n) >= 1000 ? `${(Number(n) / 1000).toFixed(Number(n) >= 100000 ? 0 : 1)}k` : String(n ?? "—");

/* Accept either the bare model or a wrapper around it, since the exact
   envelope depends on how your FastAPI route returns it. */
function unwrap(kind, data) {
  if (!data) return data;
  if (kind === "creators") return data.creator_recommendations || data.recommendations || data;
  if (kind === "dub") return data.dub_tracks || data.tracks || data;
  return data;
}

export default function OutputDailies({ kind, data, model }) {
  const [showRaw, setShowRaw] = useState(false);
  const body = unwrap(kind, data);

  return (
    <div className="dailies">
      <div className="dailies__bar">
        <h4 className="deck__cap">Output</h4>
        <div className="dailies__meta">
          {data?.__demo && <span className="chip chip--warn">sample data</span>}
          <span className="chip">{model}</span>
          <button type="button" className="ghost" onClick={() => setShowRaw((v) => !v)}>
            {showRaw ? "Hide JSON" : "View JSON"}
          </button>
        </div>
      </div>

      {showRaw ? (
        <pre className="raw">{JSON.stringify(data, null, 2)}</pre>
      ) : (
        <div className="dailies__body">
          {kind === "creators" && <Creators list={body} />}
          {kind === "script" && <Script script={body} />}
          {kind === "shotplan" && <ShotPlan plan={body} />}
          {kind === "audio" && <Audio master={body} />}
          {kind === "sync" && <Sync report={body} />}
          {kind === "dub" && <Dub tracks={body} />}
          {kind === "clearance" && <Clearance report={body} />}
        </div>
      )}
    </div>
  );
}

/* ---------------- CreatorRecommendation[] ---------------- */
function Creators({ list }) {
  const items = Array.isArray(list) ? list : [];
  return (
    <ul className="rows">
      {items.map((c, i) => (
        <li className="row" key={c.creator_name || i}>
          <div className="row__head">
            <b>{c.creator_name}</b>
            <span className="row__tag">{c.platform}</span>
          </div>
          <div className="stats">
            <span><i>followers</i>{compact(c.follower_count)}</span>
            <span><i>engagement</i>{pct(c.engagement_rate)}</span>
            <span><i>fit</i>{pct(c.overall_score)}</span>
          </div>
          <div className="meter" aria-hidden="true">
            <span style={{ width: pct(c.overall_score) }} />
          </div>
          <p className="row__note">{c.rationale}</p>
        </li>
      ))}
    </ul>
  );
}

/* ---------------- ScriptVersion ---------------- */
function Script({ script }) {
  const beats = script?.beats || [];
  return (
    <>
      {script?.hook && <p className="hook">&ldquo;{script.hook}&rdquo;</p>}
      <ul className="beats">
        {beats.map((b) => (
          <li key={b.beat_id}>
            <span className="beats__tc">
              {time(b.start_time)}–{time(b.end_time)}
            </span>
            <span>
              <b>{b.text}</b>
              <em>
                {[b.visual_intent, b.expression].filter(Boolean).join(" · ")}
              </em>
            </span>
          </li>
        ))}
      </ul>
    </>
  );
}

/* ---------------- ShotPlan ---------------- */
function ShotPlan({ plan }) {
  const shots = plan?.shots || [];
  return (
    <>
      {plan?.visual_style && <p className="hook">{plan.visual_style}</p>}
      <ul className="rows">
        {shots.map((s) => (
          <li className="row" key={s.shot_id}>
            <div className="row__head">
              <b>{s.shot_type}</b>
              <span className="row__tag">
                {s.beat_id} · {time(s.start_time)}
              </span>
            </div>
            <div className="stats">
              <span><i>angle</i>{s.camera_angle}</span>
              <span><i>move</i>{s.camera_movement}</span>
              <span><i>light</i>{s.lighting}</span>
            </div>
            <p className="row__note">{s.visual_description}</p>
            {Array.isArray(s.colour_palette) && s.colour_palette.length > 0 && (
              <div className="swatches" aria-hidden="true">
                {s.colour_palette.map((c) => (
                  <span key={c} style={{ background: c }} />
                ))}
              </div>
            )}
          </li>
        ))}
      </ul>
    </>
  );
}

/* ---------------- AudioMaster ---------------- */
function Audio({ master }) {
  const segments = master?.segments || [];
  return (
    <>
      <div className="stats stats--wide">
        <span><i>duration</i>{time(master?.duration)}</span>
        <span><i>sample rate</i>{master?.sample_rate || "—"} Hz</span>
        <span><i>channels</i>{master?.channels || "—"}</span>
        <span><i>cleaned</i>{master?.cleaned ? "yes" : "no"}</span>
      </div>
      {master?.file_path && (
        <p className="path">
          {master.file_path}
          {/^https?:\/\//.test(master.file_path) && (
            <audio controls src={master.file_path} />
          )}
        </p>
      )}
      <ul className="beats">
        {segments.map((s) => (
          <li key={s.segment_id}>
            <span className="beats__tc">
              {time(s.start_time)}–{time(s.end_time)}
            </span>
            <span>
              <b>{s.transcript}</b>
              <em>{(s.words?.length || 0)} word timestamps</em>
            </span>
          </li>
        ))}
      </ul>
    </>
  );
}

/* ---------------- SyncReport ---------------- */
function Sync({ report }) {
  const segments = report?.segments || [];
  return (
    <>
      <div className="stats stats--wide">
        <span><i>status</i>{report?.status || "—"}</span>
        <span><i>global offset</i>{report?.global_offset ?? "—"}s</span>
        <span><i>drift</i>{report?.drift_detected ? "detected" : "none"}</span>
      </div>
      <ul className="rows">
        {segments.map((s) => (
          <li className="row" key={s.segment_id}>
            <div className="row__head">
              <b>{s.segment_id}</b>
              <span className={`row__tag${s.confidence < 0.5 ? " is-warn" : ""}`}>
                {pct(s.confidence)} confident
              </span>
            </div>
            <div className="stats">
              <span><i>offset</i>{s.offset}s</span>
              <span><i>video</i>{time(s.video_start)}–{time(s.video_end)}</span>
              <span><i>audio</i>{time(s.audio_start)}–{time(s.audio_end)}</span>
            </div>
            {s.recommended_take && <p className="row__note">{s.recommended_take}</p>}
          </li>
        ))}
      </ul>
      {(report?.notes || []).map((n, i) => (
        <p className="row__note row__note--loose" key={i}>{n}</p>
      ))}
    </>
  );
}

/* ---------------- DubTrack[] ---------------- */
function Dub({ tracks }) {
  const list = Array.isArray(tracks) ? tracks : [];
  return (
    <ul className="rows">
      {list.map((t, i) => (
        <li className="row" key={`${t.language}-${i}`}>
          <div className="row__head">
            <b>{t.language}{t.geography ? ` · ${t.geography}` : ""}</b>
            <span className="row__tag">{t.segments?.length || 0} lines</span>
          </div>
          {t.audio_path && /^https?:\/\//.test(t.audio_path) && (
            <audio controls src={t.audio_path} />
          )}
          <ul className="beats beats--dub">
            {(t.segments || []).map((s) => (
              <li key={s.segment_id}>
                <span className="beats__tc">{s.segment_id}</span>
                <span>
                  <b>{s.localized_text}</b>
                  <em>{s.source_text}</em>
                  {(s.cultural_notes || []).map((n, k) => (
                    <em key={k} className="note">{n}</em>
                  ))}
                </span>
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ul>
  );
}

/* ---------------- ClearanceReport ---------------- */
function Clearance({ report }) {
  const issues = report?.issues || [];
  const order = { red: 0, yellow: 1, unverified: 2, green: 3 };
  const sorted = [...issues].sort(
    (a, b) => (order[a.severity] ?? 9) - (order[b.severity] ?? 9)
  );
  return (
    <>
      <p className={`verdict is-${report?.status || "unknown"}`}>
        {(report?.status || "unknown").replace(/_/g, " ")}
        <span>
          pass {report?.pass_number ?? "?"} of 6 · after {report?.stage || "—"}
        </span>
      </p>
      <ul className="rows">
        {sorted.map((issue) => (
          <li className={`row lamp lamp--${issue.severity}`} key={issue.issue_id}>
            <div className="row__head">
              <b>{issue.label}</b>
              <span className="row__tag">{issue.severity}</span>
            </div>
            <p className="row__note">{issue.description}</p>
            {issue.recommended_action && (
              <p className="row__note"><b>Do this:</b> {issue.recommended_action}</p>
            )}
            {(issue.substitutes || []).map((s, i) => (
              <p className="row__note" key={i}><b>Instead:</b> {s}</p>
            ))}
            {(issue.evidence || []).map((e, i) => (
              <a className="src" key={i} href={e.url} target="_blank" rel="noreferrer">
                {e.claim || e.url}
              </a>
            ))}
          </li>
        ))}
      </ul>
      {(report?.structural_errors || []).map((e, i) => (
        <p className="row__note row__note--loose" key={i}>{e}</p>
      ))}
    </>
  );
}
