"use client";

import type { MouseEvent } from "react";

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
}: {
  label: string;
  stages: ReadonlyArray<{ id: string; label: string; n?: number }>;
}) {
  const go = (e: MouseEvent<HTMLAnchorElement>, id: string) => {
    const section = document.getElementById(id);
    if (!section) return;
    e.preventDefault();
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
