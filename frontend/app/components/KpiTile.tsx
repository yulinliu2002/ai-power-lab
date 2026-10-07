import type { StatusRole } from "../lib/statusRoles";

const BORDER_BY_ROLE: Record<StatusRole, string> = {
  good: "border-t-status-good",
  warning: "border-t-status-warning",
  critical: "border-t-status-critical",
  neutral: "border-t-hairline",
};

interface KpiTileProps {
  label: string;
  value: string;
  unit: string;
  role: StatusRole;
}

/** One instrument tile -- see DESIGN.md section 13. */
export function KpiTile({ label, value, unit, role }: KpiTileProps) {
  return (
    <div
      className={`flex flex-col gap-1 border border-hairline ${BORDER_BY_ROLE[role]} border-t-2 bg-surface px-3 py-2`}
    >
      <span className="font-sans text-[10.5px] font-semibold uppercase tracking-[0.04em] text-muted">
        {label}
      </span>
      <span className="font-mono text-[22px] font-semibold leading-none tabular-nums text-primary">
        {value}
        <span className="ml-1 text-[11px] font-normal text-muted">{unit}</span>
      </span>
    </div>
  );
}
