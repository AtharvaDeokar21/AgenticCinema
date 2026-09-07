"use client";

import { useCallback, useRef, useState } from "react";
import { agents } from "@/data/agents";
import { propsByName } from "@/components/props";

/* The call board.
   Left: the cast, as a roving tablist. Right: one panel that reads
   left to right — what you hand over, what the agent does, what comes back.
   Nothing here scrolls; picking a name swaps the panel in place. */
export default function AgentConsole() {
  const [active, setActive] = useState(0);
  const castRef = useRef(null);

  const agent = agents[active];
  const Prop = propsByName[agent.prop];

  const focusTab = useCallback((index) => {
    setActive(index);
    const tabs = castRef.current?.querySelectorAll("[role=tab]");
    tabs?.[index]?.focus();
  }, []);

  function onCastKeyDown(event) {
    const last = agents.length - 1;
    if (event.key === "ArrowDown" || event.key === "ArrowRight") {
      event.preventDefault();
      focusTab(active === last ? 0 : active + 1);
    } else if (event.key === "ArrowUp" || event.key === "ArrowLeft") {
      event.preventDefault();
      focusTab(active === 0 ? last : active - 1);
    } else if (event.key === "Home") {
      event.preventDefault();
      focusTab(0);
    } else if (event.key === "End") {
      event.preventDefault();
      focusTab(last);
    }
  }

  return (
    <div className="board" data-act>
      {/* ---------------- the cast ---------------- */}
      <div
        className="board__cast"
        role="tablist"
        aria-label="The seven agents"
        aria-orientation="vertical"
        onKeyDown={onCastKeyDown}
        ref={castRef}
      >
        <p className="board__caption">Call board</p>

        {agents.map((entry, index) => (
          <button
            type="button"
            key={entry.name}
            id={`cast-${index}`}
            role="tab"
            aria-selected={index === active}
            aria-controls="board-panel"
            tabIndex={index === active ? 0 : -1}
            className={`cast${index === active ? " is-on" : ""}`}
            onClick={() => setActive(index)}
          >
            <span className="cast__no">{entry.numeral}</span>
            <span className="cast__text">
              <span className="cast__name">{entry.name}</span>
              <span className="cast__role">{entry.role}</span>
            </span>
          </button>
        ))}
      </div>

      {/* ---------------- the panel ---------------- */}
      <div
        className="board__panel"
        id="board-panel"
        role="tabpanel"
        aria-labelledby={`cast-${active}`}
        tabIndex={0}
      >
        <header className="panel__head">
          <div className="panel__prop" data-par data-speed="0.05">
            <Prop />
          </div>
          <div>
            <h3 className="panel__name">
              <span>{agent.numeral}</span>
              {agent.name}
            </h3>
            <p className="panel__role">{agent.role}</p>
            <p className="panel__body">{agent.body}</p>
            <p className="panel__cost">{agent.bottleneck}</p>
          </div>
        </header>

        <div className="flow">
          <section className="flow__col flow__col--in">
            <h4 className="flow__cap">You hand over</h4>
            <dl className="flow__list">
              {agent.intake.map(([label, detail]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{detail}</dd>
                </div>
              ))}
            </dl>
          </section>

          <section className="flow__col flow__col--do">
            <h4 className="flow__cap">What it does</h4>
            <ol className="flow__steps">
              {agent.working.map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ol>
          </section>

          <section className="flow__col flow__col--out">
            <h4 className="flow__cap">You get back</h4>
            <dl className="flow__list">
              {agent.delivery.map(([label, detail]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{detail}</dd>
                </div>
              ))}
            </dl>
          </section>
        </div>

        <footer className="panel__foot">
          <p className="panel__handoff">{agent.handoff}</p>
          <div className="panel__meta">
            <span className="chip">writes {agent.model}</span>
            <span className="panel__step">
              {active + 1} of {agents.length}
            </span>
            <span className="panel__arrows">
              <button
                type="button"
                onClick={() => focusTab(active === 0 ? agents.length - 1 : active - 1)}
                aria-label="Previous agent"
              >
                &#8592;
              </button>
              <button
                type="button"
                onClick={() => focusTab(active === agents.length - 1 ? 0 : active + 1)}
                aria-label="Next agent"
              >
                &#8594;
              </button>
            </span>
          </div>
        </footer>
      </div>
    </div>
  );
}
