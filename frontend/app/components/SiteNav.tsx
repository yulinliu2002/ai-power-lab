"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/**
 * Minimal top-level navigation across AI Power Lab 2.0's four learning
 * areas plus the Advanced Sandbox. System Map, Architecture Choices
 * (SPEC-011), Learn by Example (SPEC-012), Industry & Career (SPEC-013)
 * and Advanced Sandbox (the preserved simulator, moved from `/` to
 * `/sandbox`) are implemented routes. An entry marked `disabled` would
 * render as plain "(planned)" text; none is currently.
 */
const NAV_ITEMS: ReadonlyArray<{ href: string; label: string; disabled?: boolean }> = [
  { href: "/system-map", label: "System Map" },
  { href: "/architecture", label: "Architecture Choices" },
  { href: "/learn", label: "Learn by Example" },
  { href: "/industry", label: "Industry & Career" },
  { href: "/sandbox", label: "Advanced Sandbox" },
];

export function SiteNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="Primary" className="flex flex-wrap items-center gap-x-2.5 gap-y-0.5 border-b border-hairline bg-surface px-4 py-2 sm:gap-x-5 sm:px-6">
      <Link
        href="/"
        aria-label="AI Power Lab home"
        className="font-sans text-[11px] font-semibold uppercase tracking-[0.08em] text-secondary hover:text-primary max-sm:tracking-normal"
      >
        <span aria-hidden="true" className="max-sm:hidden">AI POWER LAB</span>
        <span aria-hidden="true" className="sm:hidden">APL</span>
      </Link>
      <div className="flex flex-wrap gap-x-2.5 gap-y-0.5 max-sm:contents sm:gap-x-4">
        {NAV_ITEMS.map((item) => {
          if (item.disabled) {
            return (
              <span
                key={item.label}
                aria-disabled="true"
                className="cursor-default font-mono text-[11px] uppercase tracking-[0.04em] text-secondary max-sm:text-[10.5px] max-sm:tracking-normal"
              >
                {item.label} <span className="normal-case">(planned)</span>
              </span>
            );
          }

          const isActive = pathname === item.href;
          return (
            <Link
              key={item.label}
              href={item.href}
              aria-current={isActive ? "page" : undefined}
              className={`font-mono text-[11px] uppercase tracking-[0.04em] max-sm:text-[10.5px] max-sm:tracking-normal focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-secondary ${
                isActive
                  ? "text-primary border-b-2 border-primary"
                  : "text-secondary hover:text-primary"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
