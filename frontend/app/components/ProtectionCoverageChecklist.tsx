import type { CoverageEntry } from "../lib/simulationApi";

/**
 * Static protection-coverage checklist (SPEC-009 §5/§7), shared by
 * `ProtectionCoordination.tsx` (per-scenario) and `ScenarioComparison.tsx`
 * (rendered once, since `coverage` is identical across every scenario,
 * SPEC-010 §8). Reads `coverage` verbatim -- no classification or
 * rewording of its own.
 */
export function CoverageChecklist({ coverage }: { coverage: CoverageEntry[] }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="font-sans text-[10.5px] font-semibold uppercase tracking-[0.04em] text-muted">
        Protection Coverage (V1 model)
      </span>
      <ul className="flex flex-col gap-1">
        {coverage.map((entry, i) => (
          <li key={i} className="flex flex-wrap items-baseline gap-x-2 font-mono text-[10.5px]">
            <span className={entry.modeled ? "text-status-good" : "text-status-critical"}>
              {entry.modeled ? "✓" : "✕"}
            </span>
            <span className="font-semibold text-primary">{entry.function}</span>
            <span className="text-muted">{entry.detail}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
