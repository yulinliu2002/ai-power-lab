"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { ARCHITECTURES, type ArchitectureId, type CategoryId } from "../lib/infrastructureMapData";
import { useArch } from "./ArchContext";

/**
 * Shared shell: five areas + the signal-path rail.
 *
 * The rail is architecture-aware. It draws the *selected* architecture's
 * own main power path (Conventional AC, AC-fed 800 VDC, or the conceptual
 * MV-to-800 VDC via SST), never a single universal chain; an SST appears
 * only in the SST architecture. Pages that run the simulation (Learn,
 * Sandbox) pin the rail to the SST architecture and mark the simulated
 * slice with a dashed bracket and an explicit "simulated slice" label.
 * Focus is shown by surface tier + weight (DESIGN.md §19), not color.
 */
const AREAS = [
  { href: "/design-lab/system-map", label: "System Map", n: "01" },
  { href: "/design-lab/architecture", label: "Architecture Choices", n: "02" },
  { href: "/design-lab/learn", label: "Learn by Example", n: "03" },
  { href: "/design-lab/industry", label: "Industry & Career", n: "04" },
] as const;

const SANDBOX = { href: "/design-lab/sandbox", label: "Advanced Sandbox" } as const;

const SHORT: Record<ArchitectureId, string> = {
  "conventional-ac": "Conventional AC",
  "ac-to-800vdc": "AC-fed 800 VDC",
  "mv-to-800vdc": "MV-to-800 VDC via SST (conceptual)",
};

interface RailSpec {
  note: string;
  focus: readonly CategoryId[];
  pinned?: ArchitectureId;
  slice?: boolean;
}

const RAIL_SPEC: Record<string, RailSpec> = {
  "/design-lab": { note: "Context", focus: [] },
  "/design-lab/system-map": { note: "Whole path", focus: [] },
  "/design-lab/architecture": {
    note: "Where architectures diverge",
    focus: ["substation", "power_conversion", "distribution", "rack_power"],
  },
  "/design-lab/learn": {
    note: "Simulated slice: SST, 800 VDC bus, lumped AI load",
    focus: ["power_conversion", "distribution", "compute"],
    pinned: "mv-to-800vdc",
    slice: true,
  },
  "/design-lab/industry": { note: "Industry attention", focus: ["power_conversion", "distribution", "rack_power"] },
  "/design-lab/sandbox": {
    note: "Simulated slice: SST, 800 VDC bus, lumped AI load",
    focus: ["power_conversion", "distribution", "compute"],
    pinned: "mv-to-800vdc",
    slice: true,
  },
};

export function LabNav() {
  const pathname = usePathname().replace(/\/$/, "");
  const { arch } = useArch();
  const spec = RAIL_SPEC[pathname] ?? RAIL_SPEC["/design-lab"];
  const archId = spec.pinned ?? arch;
  const archDef = ARCHITECTURES.find((a) => a.id === archId)!;
  const main = archDef.nodes.filter((n) => n.lane === "main");
  const allOn = spec.focus.length === 0 && pathname === "/design-lab/system-map";

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
      <div
        className="lab-rail"
        role="img"
        aria-label={`Power path for ${SHORT[archId]}. ${spec.note}. ${spec.pinned ? "Simulated slice only; not evidence for other architectures." : "One representative architecture, not universal."}`}
      >
        <div className="lab-wrap lab-rail-in">
          <span className="lab-rail-label">
            <b>{SHORT[archId]}</b>
            <span className="lab-rail-note">{spec.note}</span>
          </span>
          <div className="lab-rail-track" data-slice={spec.slice ? "true" : undefined}>
            {main.map((n, i) => {
              const on = allOn || spec.focus.includes(n.categoryId);
              return (
                <div key={n.id} style={{ display: "contents" }}>
                  <span className="lab-rail-node" data-on={on} data-slice={on && spec.slice ? "true" : undefined}>
                    <i />
                    {n.label}
                  </span>
                  {i < main.length - 1 && <span className="lab-rail-link" />}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </>
  );
}
