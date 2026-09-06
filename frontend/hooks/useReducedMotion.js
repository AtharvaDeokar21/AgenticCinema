"use client";

import { useEffect, useState } from "react";

/* Reports the user's motion preference, and keeps up if they change it
   mid-session. Starts `false` so the server and first client render match. */
export default function useReducedMotion() {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setReduced(query.matches);
    sync();
    query.addEventListener("change", sync);
    return () => query.removeEventListener("change", sync);
  }, []);

  return reduced;
}
