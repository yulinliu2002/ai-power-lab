"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/**
 * Minimal top-level navigation across AI Power Lab 2.0's four learning
 * areas plus the Advanced Sandbox. System Map, Architecture Choices
 * (SPEC-011) and Advanced Sandbox (the preserved simulator, moved from
 * `/` to `/sandbox`) are implemented routes; Learn by Example and
 * Industry & Career are listed but disabled
 * rather than left off the nav, per the instruction not to build
 * unfinished pages just to populate it, while still showing the
 * intended shape of the site.
 */
const NAV_ITEMS: ReadonlyArray<{ href: string; label: string; disabled?: boolean }> = [
  { href: "/system-map", label: "System Map" },
  { href: "/architecture", label: "Architecture Choices" },
  { href: "/learn", label: "Learn by Example", disabled: true },
  { href: "/industry", label: "Industry & Career", disabled: true },
  { href: "/sandbox", label: "Advanced Sandbox" },
];

export function SiteNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="Primary" className="flex flex-wrap items-center gap-x-5 gap-y-1 border-b border-hairline bg-surface px-6 py-2">
      <Link
        href="/"
        className="font-sans text-[11px] font-semibold uppercase tracking-[0.08em] text-secondary hover:text-primary"
      >
        AI POWER LAB
      </Link>
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {NAV_ITEMS.map((item) => {
          if (item.disabled) {
            return (
              <span
                key={item.label}
                className="font-mono text-[11px] uppercase tracking-[0.04em] text-secondary"
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
              className={`font-mono text-[11px] uppercase tracking-[0.04em] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-secondary ${
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
