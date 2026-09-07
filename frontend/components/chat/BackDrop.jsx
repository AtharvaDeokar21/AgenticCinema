"use client";

import { useEffect, useRef } from "react";
import { FilmReel, Projector, StageLamp } from "@/components/props";
import Motes from "@/components/Motes";
import useReducedMotion from "@/hooks/useReducedMotion";

/* Four parallax planes behind the conversation. The page itself barely
   scrolls, so these are driven by the pointer rather than by scroll — plus
   a slow drift from the transcript's own scroll position, passed down as
   the CSS variable --drift by ChatRoom. */
export default function Backdrop() {
  const rootRef = useRef(null);
  const reduced = useReducedMotion();

  useEffect(() => {
    if (reduced) return;
    const root = rootRef.current;
    if (!root) return;

    const layers = Array.from(root.querySelectorAll("[data-depth]"));
    let x = 0;
    let y = 0;
    let ticking = false;

    function paint() {
      ticking = false;
      for (const layer of layers) {
        const depth = parseFloat(layer.dataset.depth) || 0;
        layer.style.transform =
          `translate3d(${(x * depth).toFixed(2)}px, ${(y * depth).toFixed(2)}px, 0)`;
      }
    }

    function onMove(event) {
      x = (event.clientX / window.innerWidth - 0.5) * 2;
      y = (event.clientY / window.innerHeight - 0.5) * 2;
      if (!ticking) {
        ticking = true;
        requestAnimationFrame(paint);
      }
    }

    window.addEventListener("mousemove", onMove, { passive: true });
    return () => {
      window.removeEventListener("mousemove", onMove);
      for (const layer of layers) layer.style.transform = "";
    };
  }, [reduced]);

  return (
    <div className="room-back" ref={rootRef} aria-hidden="true">
      {/* 1 — back wall glow */}
      <div className="room-back__wall" data-depth="6" />

      {/* 2 — the projector beam, cast from the back of the house */}
      <div className="room-back__beam" data-depth="14" />

      {/* 3 — props, deliberately few and faint */}
      <div className="room-back__props" data-depth="26">
        <StageLamp />
        <FilmReel className="room-back__reel" />
        <Projector className="room-back__projector" />
      </div>

      {/* 4 — dust in the beam, then the stage floor in front of everything */}
      <div className="room-back__motes">
        <Motes count={14} />
      </div>
      <div className="room-back__floor" data-depth="40" />
    </div>
  );
}
