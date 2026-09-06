"use client";

import { useEffect, useState } from "react";
import useReducedMotion from "@/hooks/useReducedMotion";

/* Dust in the beam. Positions are random, so they are generated after mount
   rather than during render — otherwise the server and client markup would
   disagree and React would throw a hydration mismatch. */
export default function Motes({ count = 26 }) {
  const [motes, setMotes] = useState([]);
  const reduced = useReducedMotion();

  useEffect(() => {
    if (reduced) {
      setMotes([]);
      return;
    }
    setMotes(
      Array.from({ length: count }, (_, i) => ({
        id: i,
        left: `${(Math.random() * 100).toFixed(2)}%`,
        top: `${(60 + Math.random() * 40).toFixed(2)}%`,
        animationDuration: `${(12 + Math.random() * 16).toFixed(1)}s`,
        animationDelay: `${(-Math.random() * 20).toFixed(1)}s`,
        opacity: (0.12 + Math.random() * 0.32).toFixed(2),
      }))
    );
  }, [count, reduced]);

  return (
    <div className="plane plane--motes" data-par data-speed="0.12" aria-hidden="true">
      {motes.map(({ id, ...style }) => (
        <span key={id} className="mote" style={style} />
      ))}
    </div>
  );
}
