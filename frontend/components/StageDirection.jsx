"use client";

import { useEffect, useRef } from "react";
import useReducedMotion from "@/hooks/useReducedMotion";

/* Runs the whole page's scroll choreography in a single rAF loop:
     - parallax planes           [data-par][data-speed]
     - mouse drift on the hero   [data-mouse]
     - horizontal filmstrip      #reel / #strip-track
     - the follow spot           centres on the nearest act
     - nav rail active state     .rail a
   Reading layout and writing transforms in one frame keeps it to a single
   reflow per scroll event. */
export default function StageDirection() {
  const spotRef = useRef(null);
  const reduced = useReducedMotion();

  useEffect(() => {
    const spot = spotRef.current;
    const planes = Array.from(document.querySelectorAll("[data-par]"));
    const acts = Array.from(document.querySelectorAll("[data-act]"));
    const links = Array.from(document.querySelectorAll(".rail a"));
    const reel = document.getElementById("reel");
    const strip = document.getElementById("strip-track");

    let mouseX = 0;
    let ticking = false;

    const clamp = (v, min, max) => (v < min ? min : v > max ? max : v);

    function frame() {
      ticking = false;
      const vh = window.innerHeight;

      if (!reduced) {
        for (const el of planes) {
          const speed = parseFloat(el.dataset.speed) || 0;
          const drift = parseFloat(el.dataset.mouse) || 0;
          const box = el.getBoundingClientRect();
          const rel = box.top + box.height / 2 - vh / 2;
          el.style.transform =
            `translate3d(${(mouseX * drift).toFixed(2)}px,` +
            `${(-rel * speed).toFixed(2)}px,0)`;
        }

        if (reel && strip) {
          const box = reel.getBoundingClientRect();
          const total = reel.offsetHeight - vh;
          const progress = clamp(-box.top / (total || 1), 0, 1);
          const travel = Math.max(strip.scrollWidth - window.innerWidth + 40, 0);
          strip.style.transform = `translate3d(${(-progress * travel).toFixed(1)}px,0,0)`;
        }
      }

      if (spot) {
        let nearest = null;
        let nearestDistance = Infinity;
        for (const act of acts) {
          const box = act.getBoundingClientRect();
          const distance = Math.abs(box.top + box.height / 2 - vh / 2);
          if (distance < nearestDistance) {
            nearestDistance = distance;
            nearest = box;
          }
        }
        if (nearest && nearestDistance < vh) {
          spot.style.opacity = "1";
          spot.style.top = `${(nearest.top + nearest.height / 2).toFixed(0)}px`;
        } else {
          spot.style.opacity = "0";
        }
      }

      for (const link of links) {
        const section = document.getElementById(link.hash.slice(1));
        if (!section) continue;
        const box = section.getBoundingClientRect();
        const active = box.top <= vh * 0.45 && box.bottom >= vh * 0.45;
        link.classList.toggle("is-on", active);
      }
    }

    function request() {
      if (!ticking) {
        ticking = true;
        requestAnimationFrame(frame);
      }
    }

    function onMouseMove(event) {
      mouseX = (event.clientX / window.innerWidth - 0.5) * 2;
      request();
    }

    window.addEventListener("scroll", request, { passive: true });
    window.addEventListener("resize", request);
    if (!reduced) {
      window.addEventListener("mousemove", onMouseMove, { passive: true });
    }
    frame();

    return () => {
      window.removeEventListener("scroll", request);
      window.removeEventListener("resize", request);
      window.removeEventListener("mousemove", onMouseMove);
      for (const el of planes) el.style.transform = "";
      if (strip) strip.style.transform = "";
    };
  }, [reduced]);

  return <div className="follow-spot" ref={spotRef} aria-hidden="true" />;
}
