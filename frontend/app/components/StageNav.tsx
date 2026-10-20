"use client";

import { useEffect, useState, type MouseEvent } from "react";

/**
 * In-page stage navigation (SPEC-014 R3/R20): native anchor links, one per
 * stage, in a fixed order. Activating a link scrolls to the section and
 * moves keyboard focus to its heading (headings carry tabIndex -1), so the
 * flow is operable by keyboard alone. Moving between stages never changes
 * page state (R42).
 */
export function StageNav({
  label,
  stages,
  observeKey,
}: {
  label: string;
  stages: ReadonlyArray<{ id: string; label: string; n?: number }>;
  /** Changes when the stage sections are re-rendered (for example a different selection), so the observer re-attaches. */
  observeKey?: string;
}) {
  const [current, setCurrent] = useState<string | null>(stages[0]?.id ?? null);

  // The current stage is the last one whose top has passed the upper third of the viewport. It is recomputed from the
  // live DOM on scroll/resize (and when the section content changes), so it cannot go stale after a re-render.
  useEffect(() => {
    let raf = 0;
    const compute = () => {
      raf = 0;
      const line = window.innerHeight * 0.33;
      const tops = stages.map((st) => {
        const el = document.getElementById(st.id);
        return { id: st.id, top: el ? el.getBoundingClientRect().top : Infinity };
      });
      const passed = tops.filter((t) => t.top <= line);
      // Stages shown side by side (the requirement list and the board) start at the same height; the earliest of
      // such a group is the current one, so the order of the steps is respected.
      let active = stages[0]?.id ?? null;
      if (passed.length > 0) {
        const lastTop = passed[passed.length - 1].top;
        active = (passed.find((t) => t.top >= lastTop - 40) ?? passed[passed.length - 1]).id;
      }
      setCurrent(active);
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(compute);
    };
    compute();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [stages, observeKey]);

  const go = (e: MouseEvent<HTMLAnchorElement>, id: string) => {
    const section = document.getElementById(id);
    if (!section) return;
    e.preventDefault();
    setCurrent(id);
    section.scrollIntoView({ block: "start" });
    const heading = section.querySelector<HTMLElement>("[data-stage-heading]");
    heading?.focus({ preventScroll: true });
    history.replaceState(null, "", `#${id}`);
  };

  return (
    <nav aria-label={label} className="flex flex-wrap gap-x-5 gap-y-1 font-mono text-meta uppercase">
      {stages.map((s) => (
        <a
          key={s.id}
          href={`#${s.id}`}
          aria-current={current === s.id ? "location" : undefined}
          onClick={(e) => go(e, s.id)}
          className="py-1 text-secondary hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-secondary"
        >
          {s.n !== undefined && <span className="text-primary">{s.n} </span>}
          {s.label}
        </a>
      ))}
    </nav>
  );
}
