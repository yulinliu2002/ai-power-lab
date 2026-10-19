"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/**
 * Shared shell: five areas + the signal-path rail.
 *
 * The rail is the identity motif. It draws the real chain the product
 * teaches (grid -> MV switchgear -> SST / conversion -> 800 VDC bus ->
 * rack) and each area marks the span it works on. "Focus" is shown by
 * surface tier + text weight (DESIGN.md §19), never by a new color.
 */
const AREAS = [
  { href: "/design-lab/system-map", label: "System Map", n: "01" },
  { href: "/design-lab/architecture", label: "Architecture Choices", n: "02" },
  { href: "/design-lab/learn", label: "Learn by Example", n: "03" },
  { href: "/design-lab/industry", label: "Industry & Career", n: "04" },
] as const;

const SANDBOX = { href: "/design-lab/sandbox", label: "Advanced Sandbox" } as const;

const RAIL = ["Utility grid", "MV switchgear", "SST / conversion", "800 VDC bus", "Rack & compute"] as const;

/** Which rail nodes each area works on. */
const FOCUS: Record<string, readonly number[]> = {
  "/design-lab": [0, 1, 2, 3, 4],
  "/design-lab/system-map": [0, 1, 2, 3, 4],
  "/design-lab/architecture": [1, 2, 3],
  "/design-lab/learn": [2, 3, 4],
  "/design-lab/industry": [1, 2, 3],
  "/design-lab/sandbox": [2, 3, 4],
};

const FOCUS_NOTE: Record<string, string> = {
  "/design-lab": "Whole chain",
  "/design-lab/system-map": "Whole chain",
  "/design-lab/architecture": "Where architectures diverge",
  "/design-lab/learn": "Scenario slice",
  "/design-lab/industry": "Where the industry is moving",
  "/design-lab/sandbox": "Simulated slice",
};

export function LabNav() {
  const pathname = usePathname().replace(/\/$/, "");
  const focus = FOCUS[pathname] ?? FOCUS["/design-lab"];

  return (
    <>
      <header className="lab-top">
        <div className="lab-wrap lab-top-in">
          <Link href="/design-lab" className="lab-brand" aria-label="AI Power Lab — direction overview">
            <i aria-hidden />
            <span>AI Power Lab</span>
          </Link>
          <nav className="lab-tabs" aria-label="Primary">
            {AREAS.map((a) => (
              <Link key={a.href} href={a.href} className="lab-tab" aria-current={pathname === a.href ? "page" : undefined}>
                <small>{a.n}</small>
                {a.label}
              </Link>
            ))}
            <span className="lab-sep" aria-hidden />
            <Link
              href={SANDBOX.href}
              className="lab-tab lab-tab-tool"
              aria-current={pathname === SANDBOX.href ? "page" : undefined}
            >
              {SANDBOX.label}
            </Link>
          </nav>
        </div>
      </header>
      <div className="lab-rail" role="img" aria-label={`Signal path. Focus: ${FOCUS_NOTE[pathname] ?? ""}`}>
        <div className="lab-wrap lab-rail-in">
          <span className="lab-rail-label">{FOCUS_NOTE[pathname] ?? "Whole chain"}</span>
          <div className="lab-rail-track">
            {RAIL.map((name, i) => (
              <div key={name} style={{ display: "contents" }}>
                <span className="lab-rail-node" data-on={focus.includes(i)}>
                  <i />
                  {name}
                </span>
                {i < RAIL.length - 1 && <span className="lab-rail-link" />}
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
