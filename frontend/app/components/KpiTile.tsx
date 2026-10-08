import type { StatusRole } from "../lib/statusRoles";

const DOT_BY_ROLE: Record<StatusRole, string> = {
  good: "bg-status-good",
  warning: "bg-status-warning",
  critical: "bg-status-critical",
  neutral: "bg-status-neutral",
};

interface KpiReadoutProps {
  label: string;
  caption?: string;
  value: string;
  unit: string;
  role: StatusRole;
}

/**
 * One instrument readout in the KPI strip -- see DESIGN.md section 13.
 * Unlike a card, this carries no border of its own: these sit inside
 * one shared `divide-x` strip (see `page.tsx`'s `KpiStrip`), so the
 * strip itself is the single bordered surface, not several nested
 * ones. Status is still a real, derived signal -- the colored dot
 * reads the same `role` the power-flow schematic uses -- it is just
 * rendered as the one round glyph DESIGN.md permits instead of a
 * per-tile colored border.
 *
 * `caption`, when given, pairs the engineering notation in `label`
 * (e.g. "P_SST") with its plain-language meaning (e.g. "SST
 * delivered power") -- a first-time reader should not need to
 * already know the notation to read the strip.
 */
export function KpiReadout({ label, caption, value, unit, role }: KpiReadoutProps) {
  return (
    <div className="flex flex-col justify-center gap-0.5 px-3 py-1.5">
      <span className="flex items-center gap-1.5 font-mono text-[10px] font-semibold uppercase tracking-[0.04em] text-muted">
        <span className={`h-[5px] w-[5px] shrink-0 rounded-full ${DOT_BY_ROLE[role]}`} />
        {label}
      </span>
      <span className="font-mono text-[18px] font-semibold leading-none tabular-nums text-primary">
        {value}
        <span className="ml-1 text-[10.5px] font-normal text-muted">{unit}</span>
      </span>
      {caption && (
        <span className="font-sans text-[9.5px] leading-tight text-muted">{caption}</span>
      )}
    </div>
  );
}
