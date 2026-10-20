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

  // Track which stage is nearest the top of the viewport so the matching
  // link can expose aria-current="location".
  useEffect(() => {
    const els = stages.map((s) => document.getElementById(s.id)).filter((e): e is HTMLElement => !!e);
    if (els.length === 0 || typeof IntersectionObserver === "undefined") return;
    const visible = new Set<string>();
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) visible.add(entry.target.id);
          else visible.delete(entry.target.id);
        }
        const first = stages.find((s) => visible.has(s.id));
        if (first) setCurrent(first.id);
      },
      { rootMargin: "0px 0px -60% 0px" },
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
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
