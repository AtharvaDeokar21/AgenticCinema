"use client";

import { useEffect, useRef, useState } from "react";
import { slateStages } from "@/data/slateStages";
import useReducedMotion from "@/hooks/useReducedMotion";

/* The clapperboard. Clicking advances one pipeline stage; a full lap bumps
   the take number. This is the only non-scroll interaction on the page. */
export default function Slate() {
  const [index, setIndex] = useState(0);
  const [take, setTake] = useState(1);
  const [snapping, setSnapping] = useState(false);
  const timerRef = useRef(null);
  const reduced = useReducedMotion();

  const stage = slateStages[index];

  useEffect(() => () => clearTimeout(timerRef.current), []);

  function markIt() {
    const next = (index + 1) % slateStages.length;
    setIndex(next);
    if (next === 0) setTake((t) => t + 1);
    if (reduced) return;
    setSnapping(true);
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setSnapping(false), 300);
  }

  return (
    <section className="slate-bay" id="slate">
      <div className="slate-stack">
        <p className="slug slug--centre">
          <span>The slate</span>
        </p>
        <h2 className="playbill">Mark it.</h2>

        <button
          type="button"
          className={`slate-btn${snapping ? " snap" : ""}`}
          onClick={markIt}
          aria-describedby="slate-read"
        >
          <svg
            viewBox="0 0 480 300"
            role="img"
            aria-label="Clapperboard. Advances to the next stage of the pipeline."
          >
            <g className="clapper">
              <rect x="20" y="16" width="440" height="46" rx="4" fill="#151517" />
              <g fill="#EDE6D6">
                <path d="M40 16h44l-30 46H24z" />
                <path d="M110 16h44l-30 46h-30z" />
                <path d="M180 16h44l-30 46h-30z" />
                <path d="M250 16h44l-30 46h-30z" />
                <path d="M320 16h44l-30 46h-30z" />
                <path d="M390 16h44l-30 46h-30z" />
              </g>
              <rect
                x="20"
                y="16"
                width="440"
                height="46"
                rx="4"
                fill="none"
                stroke="#C8992F"
                strokeWidth="2"
              />
            </g>

            <rect
              x="20"
              y="70"
              width="440"
              height="212"
              rx="6"
              fill="#1B2422"
              stroke="#C8992F"
              strokeWidth="2"
            />
            <g stroke="#3E524D" strokeWidth="1.5">
              <path d="M20 132h440M20 190h440M20 240h440M170 70v62M310 70v62M240 132v58" />
            </g>

            <g className="slate-label">
              <text x="34" y="90">PRODUCTION</text>
              <text x="184" y="90">DIRECTOR</text>
              <text x="324" y="90">CAMERA</text>
              <text x="34" y="150">SCENE</text>
              <text x="254" y="150">TAKE</text>
              <text x="34" y="208">AGENT ON CALL</text>
              <text x="34" y="258">STATE WRITTEN</text>
            </g>

            <g className="slate-field">
              <text x="34" y="118">AGENTIC CINEMA</text>
              <text x="184" y="118">{stage.dir}</text>
              <text x="324" y="118">A</text>
              <text x="34" y="178">{stage.scene}</text>
              <text x="254" y="178">{take}</text>
              <text x="34" y="230">{stage.agent}</text>
              <text x="34" y="274">{stage.state}</text>
            </g>
          </svg>
        </button>

        <p className="slate-read" id="slate-read" aria-live="polite">
          <b>{stage.title}</b>
          {stage.line}
        </p>
        <p className="slate-hint">CLICK THE CLAPPER</p>
      </div>
    </section>
  );
}
