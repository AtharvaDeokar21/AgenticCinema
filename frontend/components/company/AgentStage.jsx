"use client";

import { useMemo, useState } from "react";
import { agents } from "@/data/agents";
import { propsByName, FilmReel } from "@/components/props";
import { runAgent } from "@/lib/api";
import { useProject } from "@/context/ProjectState";
import InputDeck from "@/components/company/InputDeck";
import RunConsole from "@/components/company/RunConsole";
import OutputDailies from "@/components/company/OutputDailies";

/* One agent on stage at a time.
   Left: the prop, the name, and the form. Right: what came back.
   Between them, the run console — the agent's working steps, lighting up
   while it executes. */
export default function AgentStage() {
  const [active, setActive] = useState(0);
  const [forms, setForms] = useState(() =>
    Object.fromEntries(
      agents.map((a) => [
        a.key,
        Object.fromEntries(a.fields.map((f) => [f.name, f.value ?? (f.type === "chips" ? [] : "")])),
      ])
    )
  );
  const [files, setFiles] = useState({});
  const [runs, setRuns] = useState({});

  const { state, write } = useProject();
  const agent = agents[active];
  const Prop = propsByName[agent.prop];
  const run = runs[agent.key] || {};

  const missing = useMemo(
    () => agent.needs.filter((field) => !state[field]),
    [agent, state]
  );

  const emptyRequired = agent.fields
    .filter((f) => f.required && f.type !== "file")
    .filter((f) => {
      const v = forms[agent.key][f.name];
      return Array.isArray(v) ? v.length === 0 : String(v ?? "").trim() === "";
    });

  const missingFile = agent.fields.some(
    (f) => f.type === "file" && f.required && !files[`${agent.key}:${f.name}`]
  );

  const blocked = missing.length > 0 || emptyRequired.length > 0 || missingFile;

  function setField(name, value) {
    setForms((prev) => ({
      ...prev,
      [agent.key]: { ...prev[agent.key], [name]: value },
    }));
  }

  function setFile(name, file) {
    setFiles((prev) => ({ ...prev, [`${agent.key}:${name}`]: file }));
  }

  async function action() {
    const key = agent.key;
    setRuns((prev) => ({ ...prev, [key]: { running: true } }));

    /* This is the request: the form values, plus every ProjectState field
       this agent declares it needs, plus the project id. */
    const payload = {
      project_id: state.project_id,
      ...forms[key],
      ...Object.fromEntries(agent.needs.map((field) => [field, state[field]])),
    };
    const upload = agent.fields
      .filter((f) => f.type === "file")
      .map((f) => files[`${key}:${f.name}`])
      .find(Boolean);

    try {
      const result = await runAgent(key, payload, upload);
      /* And this is the response: written into the shared project state,
         where the next agent picks it up. */
      write(agent.produces, result);
      setRuns((prev) => ({ ...prev, [key]: { done: true, result } }));
    } catch (error) {
      setRuns((prev) => ({ ...prev, [key]: { error: error.message } }));
    }
  }

  return (
    <div className="booth" data-act>
      {/* ---------- the prop rail: pick your agent ---------- */}
      <div className="rail-props" role="tablist" aria-label="The seven agents">
        {agents.map((entry, i) => {
          const Icon = propsByName[entry.prop];
          const filled = Boolean(state[entry.produces]);
          return (
            <button
              type="button"
              key={entry.key}
              role="tab"
              aria-selected={i === active}
              tabIndex={i === active ? 0 : -1}
              className={`rail-prop${i === active ? " is-on" : ""}${filled ? " is-done" : ""}`}
              onClick={() => setActive(i)}
              onKeyDown={(e) => {
                if (e.key === "ArrowRight") setActive((i + 1) % agents.length);
                if (e.key === "ArrowLeft") setActive((i - 1 + agents.length) % agents.length);
              }}
            >
              <span className="rail-prop__art"><Icon /></span>
              <span className="rail-prop__no">{entry.numeral}</span>
              <span className="rail-prop__name">{entry.name}</span>
            </button>
          );
        })}
      </div>

      {/* ---------- the stage ---------- */}
      <div className="booth__stage">
        <div className="booth__art" data-par data-speed="0.06" data-mouse="18" aria-hidden="true">
          <Prop />
        </div>
        <div className="booth__glow" data-par data-speed="0.03" aria-hidden="true" />

        <div className="booth__left">
          <p className="booth__no">{agent.numeral}</p>
          <h3 className="booth__name">{agent.name}</h3>
          <p className="booth__role">{agent.role}</p>
          <p className="booth__body">{agent.body}</p>

          <InputDeck
            agent={agent}
            values={forms[agent.key]}
            files={Object.fromEntries(
              agent.fields
                .filter((f) => f.type === "file")
                .map((f) => [f.name, files[`${agent.key}:${f.name}`]])
            )}
            onChange={setField}
            onFile={setFile}
            state={state}
          />

          <div className="action">
            <button
              type="button"
              className="action__btn"
              onClick={action}
              disabled={blocked || run.running}
            >
              {run.running ? (
                <>
                  <span className="spin"><FilmReel /></span>
                  Rolling
                </>
              ) : (
                <>Action</>
              )}
            </button>
            <span className="action__why">
              {run.running
                ? `POST ${agent.key} · writes ${agent.produces}`
                : missing.length
                  ? `Waiting on ${missing.join(" and ")}`
                  : emptyRequired.length || missingFile
                    ? "Fill the required fields"
                    : `Sends your input to ${agent.name}`}
            </span>
          </div>
        </div>

        <div className="booth__right">
          {run.error && (
            <p className="failure">
              {run.error}
              <b>Nothing was written to the project. Fix it and roll again.</b>
            </p>
          )}

          {run.done && (
            <>
              <OutputDailies kind={agent.outputKind} data={run.result} model={agent.model} />
              <p className="booth__handoff">{agent.handoff}</p>
            </>
          )}

          {run.running && (
            <div className="empty empty--live">
              <p className="empty__cap">Running {agent.name}</p>
              <RunConsole steps={agent.working} running done={false} error={null} />
            </div>
          )}

          {!run.running && !run.done && !run.error && (
            <div className="empty">
              <p className="empty__cap">Output</p>
              <p>
                Nothing shot yet. Fill the input on the left and press Action —
                the result lands here and is written to{" "}
                <b>ProjectState.{agent.produces}</b>.
              </p>
              <p className="empty__model">Returns {agent.model}</p>
            </div>
          )}
        </div>
      </div>

      {/* ---------- what the project holds so far ---------- */}
      <div className="ledger">
        <span className="ledger__cap">Project state</span>
        {agents.map((entry) => (
          <button
            type="button"
            key={entry.produces}
            className={`ledger__cell${state[entry.produces] ? " is-filled" : ""}`}
            onClick={() => setActive(agents.indexOf(entry))}
          >
            {entry.produces}
          </button>
        ))}
      </div>
    </div>
  );
}
