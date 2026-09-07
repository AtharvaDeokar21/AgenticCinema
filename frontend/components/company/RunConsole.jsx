"use client";

import { useEffect, useState } from "react";

/* The working steps are not a wall of text on the page — they are the
   loading state. Each lights up as the run progresses, so the creator sees
   what the agent is doing while it does it. */
export default function RunConsole({ steps, running, done, error }) {
  const [lit, setLit] = useState(0);

  useEffect(() => {
    if (!running) {
      setLit(done ? steps.length : 0);
      return;
    }
    setLit(1);
    const id = setInterval(() => {
      /* Hold on the last step rather than claiming to be finished. */
      setLit((n) => (n >= steps.length ? steps.length : n + 1));
    }, 1100);
    return () => clearInterval(id);
  }, [running, done, steps.length]);

  if (!running && !done && !error) return null;

  return (
    <ol className={`console${running ? " is-running" : ""}`} aria-live="polite">
      {steps.map((step, i) => {
        const state = i < lit ? (running && i === lit - 1 ? "now" : "done") : "wait";
        return (
          <li key={i} className={`console__step is-${state}`}>
            <span className="console__mark" aria-hidden="true" />
            {step}
          </li>
        );
      })}
    </ol>
  );
}
