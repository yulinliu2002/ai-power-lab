import { formatSeconds } from "../lib/formatSeconds";
import type { ProtectionTimeline as ProtectionTimelineData } from "../lib/simulationApi";
import { type StatusRole } from "../lib/statusRoles";

/**
 * Renders the backend-derived Protection Coordination / Event Analysis
 * view (SPEC-009) immediately below the existing Protection Timeline
 * section, for every scenario -- the coordination result, event
 * separations, and protection coverage matrix are all read verbatim
 * from `protection_timeline`; this component performs no
 * classification, recomputation, or rewording of its own (SPEC-009
 * §8). Its own headings, empty-state text, and ✓/✕ glyph presentation
 * are frontend-owned static/presentation text, not engineering labels.
 */

const DOT_BG_BY_ROLE: Record<StatusRole, string> = {
  good: "bg-status-good",
  warning: "bg-status-warning",
  critical: "bg-status-critical",
  neutral: "bg-status-neutral",
};

const COORDINATION_ROLE: Record<ProtectionTimelineData["coordination"]["result"], StatusRole> = {
  NO_TERMINAL_EVENT: "neutral",
  PROTECTION_ACTED_NO_VIABILITY_LOSS: "good",
  PROTECTION_ACTED_BEFORE_VIABILITY_LOSS: "warning",
  VIABILITY_LOST_NO_PROTECTION_ACTION: "critical",
  VIABILITY_LOST_BEFORE_PROTECTION_ACTION: "critical",
};

export function ProtectionCoordination({ timeline }: { timeline: ProtectionTimelineData }) {
  const { coordination, coverage } = timeline;
  const role = COORDINATION_ROLE[coordination.result];

  return (
    <section
      data-testid="protection-coordination"
      className="flex flex-col gap-2 border-t border-hairline pt-2"
    >
      <span className="font-sans text-[12px] font-bold uppercase tracking-[0.04em] text-secondary">
        PROTECTION COORDINATION
      </span>

      <div className="flex flex-col gap-1 border border-hairline px-3 py-1.5">
        <div className="flex items-center gap-1.5">
          <span className={`h-[6px] w-[6px] shrink-0 rounded-full ${DOT_BG_BY_ROLE[role]}`} />
          <span className="font-sans text-[12px] font-bold uppercase tracking-[0.04em] text-primary">
            {coordination.result_label}
          </span>
        </div>
        <p className="font-sans text-[11px] leading-snug text-secondary">
          {coordination.result_detail}
        </p>
      </div>

      {coordination.separations.length > 0 && (
        <ul className="flex flex-col gap-0.5 border-y border-hairline py-1.5">
          {coordination.separations.map((sep, i) => (
            <li key={i} className="flex flex-wrap items-baseline gap-x-2 font-mono text-[10.5px]">
              <span className="font-semibold text-primary">{sep.label}</span>
              <span className="text-secondary">{formatSeconds(sep.duration_s)}</span>
            </li>
          ))}
        </ul>
      )}

      <CoverageChecklist coverage={coverage} />
    </section>
  );
}

function CoverageChecklist({ coverage }: { coverage: ProtectionTimelineData["coverage"] }) {
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
