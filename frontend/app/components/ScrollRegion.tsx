"use client";

import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

/**
 * Named, keyboard-focusable horizontal scroller with a visible text hint
 * (DESIGN.md section 21, SPEC-014 F8/R30). Used so wide tables, charts
 * and diagrams are never silently clipped: when the content is wider
 * than its container the hint appears; it never uses a gradient
 * (DESIGN.md section 22). It carries no data props.
 */
export function ScrollRegion({
  label,
  children,
  className = "",
  style,
}: {
  label: string;
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [scrollable, setScrollable] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => setScrollable(el.scrollWidth > el.clientWidth + 1);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    if (el.firstElementChild) ro.observe(el.firstElementChild);
    return () => ro.disconnect();
  }, []);

  return (
    <div className="flex min-w-0 flex-col gap-1">
      {scrollable && (
        <span className="font-mono text-meta text-secondary" data-testid="scroll-hint">
          Scroll sideways to see all of this &rarr;
        </span>
      )}
      <div
        ref={ref}
        role="region"
        aria-label={label}
        tabIndex={0}
        style={style}
        className={`min-w-0 overflow-x-auto focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary ${className}`}
      >
        {children}
      </div>
    </div>
  );
}
