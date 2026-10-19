import { OUTCOME_CAUTION } from "../lib/sandboxTakeawayData";
import { formatSeconds } from "../lib/formatSeconds";
import type {
  ProtectionTimeline as ProtectionTimelineData,
  StateSegment,
  TimelineEvent,
} from "../lib/simulationApi";
import { sstStatus, type StatusRole } from "../lib/statusRoles";

/**
 * Renders the backend-derived Protection & Ride-Through Timeline
 * (SPEC-008) for whichever scenario is active -- segments, events,
 * and the outcome/recovery banner are all read verbatim from
 * `protection_timeline`; this component performs no classification,
 * recomputation, or rewording of its own (AC-011, AC-014). The one
 * educational caption is fixed and present for every scenario
 * regardless of outcome (AC-020), per CLAUDE.md's integrity rules:
 * V1 has no DC-bus undervoltage/overvoltage protection, so
 * `BUS_COLLAPSE_UNPROTECTED` is an illustrative model result, never a
 * claim about real SST/protection-system behavior.
 */

const DOT_BG_BY_ROLE: Record<StatusRole, string> = {
  good: "bg-status-good",
  warning: "bg-status-warning",
  critical: "bg-status-critical",
  neutral: "bg-status-neutral",
};

const SEGMENT_BG_BY_ROLE: Record<StatusRole, string> = {
  good: "bg-status-good",
  warning: "bg-status-warning",
  critical: "bg-status-critical",
  neutral: "bg-status-neutral",
};

const OUTCOME_ROLE: Record<ProtectionTimelineData["outcome"], StatusRole> = {
  RIDE_THROUGH: "good",
  PROTECTION_TRIP: "warning",
  BUS_COLLAPSE_UNPROTECTED: "critical",
};

export function ProtectionTimeline({ timeline }: { timeline: ProtectionTimelineData }) {
  const totalDurationS = timeline.segments.reduce((sum, s) => sum + s.duration_s, 0);

  return (
    <section
      data-testid="protection-timeline"
      className="flex flex-col gap-2 border-t border-hairline pt-2"
    >
      <span className="font-sans text-[12px] font-bold uppercase tracking-[0.04em] text-secondary">
        PROTECTION TIMELINE
      </span>

      <SegmentBar segments={timeline.segments} totalDurationS={totalDurationS} />
      <EventList events={timeline.events} />
      <OutcomeBanner timeline={timeline} />

      <p className="font-sans text-[12px] leading-snug text-secondary">
        V1 models only sustained thermal overtemperature protection. It has no DC-bus
        undervoltage/overvoltage protection. Thresholds and the outcomes shown here are
        illustrative, educational model results &mdash; not a claim about how a real SST and its
        surrounding protection system would necessarily behave.
      </p>
      <p data-testid="outcome-caution" className="font-sans text-[12px] leading-snug text-secondary">
        {OUTCOME_CAUTION}
      </p>
    </section>
  );
}

function SegmentBar({
  segments,
  totalDurationS,
}: {
  segments: StateSegment[];
  totalDurationS: number;
}) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex h-6 w-full overflow-hidden border border-hairline">
        {segments.map((segment, i) => {
          const role = sstStatus(segment.state).role;
          const widthPercent =
            totalDurationS > 0 ? (segment.duration_s / totalDurationS) * 100 : 100 / segments.length;
          return (
            <div
              key={i}
              className={`flex items-center justify-center ${SEGMENT_BG_BY_ROLE[role]}`}
              style={{ width: `${widthPercent}%` }}
            />
          );
        })}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-0.5">
        {segments.map((segment, i) => (
          <span key={i} className="font-mono text-[11px] text-secondary">
            {segment.state} &mdash; {segment.is_open_ended ? "at least " : ""}
            {formatSeconds(segment.duration_s)}
            {segment.is_open_ended ? " (ongoing)" : ""}
          </span>
        ))}
      </div>
    </div>
  );
}

function EventList({ events }: { events: TimelineEvent[] }) {
  if (events.length === 0) {
    return (
      <p className="font-mono text-[11px] text-secondary">No timeline events recorded for this run.</p>
    );
  }
  return (
    <ul className="flex flex-col gap-1 border-y border-hairline py-1.5">
      {events.map((event, i) => (
        <li key={i} className="flex flex-wrap items-baseline gap-x-2 font-mono text-[11px]">
          <span className="text-secondary">t = {formatSeconds(event.time_s)}</span>
          <span className="font-semibold text-primary">{event.label}</span>
          {event.detail && <span className="text-secondary">{event.detail}</span>}
        </li>
      ))}
    </ul>
  );
}

function OutcomeBanner({ timeline }: { timeline: ProtectionTimelineData }) {
  const role = OUTCOME_ROLE[timeline.outcome];
  return (
    <div data-testid="outcome-banner" className="flex flex-col gap-1 border border-hairline px-3 py-1.5">
      <div className="flex items-center gap-1.5">
        <span className={`h-[6px] w-[6px] shrink-0 rounded-full ${DOT_BG_BY_ROLE[role]}`} />
        <span className="font-sans text-[12px] font-bold uppercase tracking-[0.04em] text-primary">
          {timeline.outcome_label}
        </span>
      </div>
      <p className="font-sans text-[11px] leading-snug text-secondary">{timeline.outcome_detail}</p>
      <p className="font-mono text-[11px] text-secondary">RECOVERY: {timeline.recovery_label}</p>
    </div>
  );
}
