import type { StatusRole } from "../lib/statusRoles";

const DOT_BY_ROLE: Record<StatusRole, string> = {
  good: "bg-status-good",
  warning: "bg-status-warning",
  critical: "bg-status-critical",
  neutral: "bg-status-neutral",
};

interface KpiReadoutProps {
  label: string;
  value: string;
  unit: string;
  role: StatusRole;
}

/**
 * One instrument readout in the KPI strip -- see DESIGN.md section 13.
 * Unlike a card, this carries no border of its own: six of these sit
 * inside one shared `divide-x` strip (see `page.tsx`'s `KpiStrip`),
 * so the strip itself is the single bordered surface, not six nested
 * ones. Status is still a real, derived signal -- the colored dot
 * reads the same `role` the power-flow schematic uses -- it is just
 * rendered as the one round glyph DESIGN.md permits instead of a
 * per-tile colored border.
 */
export function KpiReadout({ label, value, unit, role }: KpiReadoutProps) {
  return (
    <div className="flex flex-col justify-center gap-0.5 px-3 py-1.5">
      <span className="flex items-center gap-1.5 font-sans text-[10px] font-semibold uppercase tracking-[0.04em] text-muted">
        <span className={`h-[5px] w-[5px] shrink-0 rounded-full ${DOT_BY_ROLE[role]}`} />
        {label}
      </span>
      <span className="font-mono text-[18px] font-semibold leading-none tabular-nums text-primary">
        {value}
        <span className="ml-1 text-[10.5px] font-normal text-muted">{unit}</span>
      </span>
    </div>
  );
}
