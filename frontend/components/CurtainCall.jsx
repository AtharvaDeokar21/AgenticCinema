"use client";

import { useEffect, useState } from "react";
import useReducedMotion from "@/hooks/useReducedMotion";

/* The one orchestrated page-load moment. Rendered closed on the server so
   there is no flash of the stage, then opened on mount. `struck` removes it
   from the compositor once the travel is finished. */
export default function CurtainCall() {
  const [open, setOpen] = useState(false);
  const [struck, setStruck] = useState(false);
  const reduced = useReducedMotion();

  useEffect(() => {
    const openTimer = setTimeout(() => setOpen(true), reduced ? 0 : 420);
    const strikeTimer = setTimeout(() => setStruck(true), reduced ? 100 : 2300);
    return () => {
      clearTimeout(openTimer);
      clearTimeout(strikeTimer);
    };
  }, [reduced]);

  return (
    <div
      className={`curtain-call${open ? " is-open" : ""}${struck ? " is-struck" : ""}`}
      aria-hidden="true"
    >
      <div className="curtain-call__half curtain-call__half--l" />
      <div className="curtain-call__half curtain-call__half--r" />
      <div className="curtain-call__slate">
        <p>HOUSE OPEN</p>
      </div>
    </div>
  );
}
