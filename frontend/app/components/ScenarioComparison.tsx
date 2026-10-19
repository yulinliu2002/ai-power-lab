import { formatSeconds } from "../lib/formatSeconds";
import type { ScenarioComparisonEntry } from "../lib/simulationApi";
import { type StatusRole } from "../lib/statusRoles";
import { CoverageChecklist } from "./ProtectionCoverageChecklist";
import { ScrollRegion } from "./ScrollRegion";
import { SCENARIO_OPTIONS } from "./ScenarioSelector";

const SCENARIO_LABEL: Record<ScenarioComparisonEntry["scenario"], string> = Object.fromEntries(
  SCENARIO_OPTIONS.map((option) => [option.key, option.label]),
) as Record<ScenarioComparisonEntry["scenario"], string>;

/**
 * Renders the backend-derived cross-scenario comparison (SPEC-010) --
 * one row per fixed scenario, one column per already-authoritative
 * stress metric (§5). Every value is read verbatim from
 * `ScenarioComparisonEntry`; this component performs no classification
 * or recomputation of its own, and no column here compares unlike
 * physical domains or attaches a severity conclusion to an emphasized
 * value (§8).
 */

const DOT_BG_BY_ROLE: Record<StatusRole, string> = {
  good: "bg-status-good",
  warning: "bg-status-warning",
  critical: "bg-status-critical",
  neutral: "bg-status-neutral",
};

const OUTCOME_ROLE: Record<ScenarioComparisonEntry["protection_timeline"]["outcome"], StatusRole> = {
  RIDE_THROUGH: "good",
  PROTECTION_TRIP: "warning",
  BUS_COLLAPSE_UNPROTECTED: "critical",
};

function formatNullableSeconds(value: number | null): string {
  return value === null ? "—" : formatSeconds(value);
}

/** Null-semantics tooltip text, verbatim from SPEC-010 §5's own
 * "Null/missing semantics" column -- never invented wording. */
const TRIP_TIME_NULL_TITLE = "Thermal protection never latched TRIPPED in this run.";
const BUS_COLLAPSE_TIME_NULL_TITLE = "The bus never reached its numerical energy floor in this run.";

/**
 * The approved whitelist of eligible columns for presentation-only
 * extrema emphasis (§8) -- continuous physical quantities only. Never
 * a timestamp, a nullable boolean, an enum, or `grid_ever_unavailable`.
 */
type MetricColumn = {
  key: string;
  label: string;
  unit: string;
  getValue: (entry: ScenarioComparisonEntry) => number;
  format: (value: number) => string;
  emphasis: "max" | "min";
};

const METRIC_COLUMNS: MetricColumn[] = [
  {
    key: "min_v_dc_v",
    label: "Min V_dc",
    unit: "V",
    getValue: (e) => e.stress_profile.min_v_dc_v,
    format: (v) => v.toFixed(1),
    emphasis: "min",
  },
  {
    key: "max_v_dc_v",
    label: "Max V_dc",
    unit: "V",
    getValue: (e) => e.stress_profile.max_v_dc_v,
    format: (v) => v.toFixed(1),
    emphasis: "max",
  },
  {
    key: "max_voltage_deviation_v",
    label: "Max |ΔV_dc|",
    unit: "V",
    getValue: (e) => e.stress_profile.max_voltage_deviation_v,
    format: (v) => v.toFixed(1),
    emphasis: "max",
  },
  {
    key: "max_voltage_deviation_percent",
    label: "Max |ΔV_dc|",
    unit: "%",
    getValue: (e) => e.stress_profile.max_voltage_deviation_percent,
    format: (v) => v.toFixed(1),
    emphasis: "max",
  },
  {
    key: "peak_power_deficit_w",
    label: "Peak power deficit",
    unit: "kW",
    getValue: (e) => e.stress_profile.peak_power_deficit_w,
    format: (v) => (v / 1e3).toFixed(1),
    emphasis: "max",
  },
  {
    key: "dc_link_energy_excursion_j",
    label: "DC-link energy excursion",
    unit: "kJ",
    getValue: (e) => e.stress_profile.dc_link_energy_excursion_j,
    format: (v) => (v / 1e3).toFixed(2),
    emphasis: "max",
  },
  {
    key: "max_temperature_c",
    label: "Max temperature",
    unit: "°C",
    getValue: (e) => e.stress_profile.max_temperature_c,
    format: (v) => v.toFixed(1),
    emphasis: "max",
  },
  {
    key: "min_grid_voltage_pu",
    label: "Min grid voltage",
    unit: "p.u.",
    getValue: (e) => e.stress_profile.min_grid_voltage_pu,
    format: (v) => v.toFixed(2),
    emphasis: "min",
  },
];

/** Ties: every row sharing the exact (unrounded) extremal value is
 * emphasized -- never an arbitrarily "first" one (§8). */
function extremalValue(entries: ScenarioComparisonEntry[], column: MetricColumn): number {
  const values = entries.map(column.getValue);
  return column.emphasis === "max" ? Math.max(...values) : Math.min(...values);
}

export function ScenarioComparison({ entries }: { entries: ScenarioComparisonEntry[] }) {
  return (
    <section data-testid="scenario-comparison" className="flex flex-col gap-2">
      <span className="font-sans text-[12px] font-bold uppercase tracking-[0.04em] text-secondary">
        SCENARIO COMPARISON
      </span>

      <p className="font-sans text-[12px] leading-snug text-secondary">
        V1 models only sustained thermal overtemperature protection. It has no DC-bus
        undervoltage/overvoltage protection. Thresholds and outcomes shown here are illustrative,
        educational model results &mdash; not a claim about how a real SST and its surrounding
        protection system would necessarily behave. Three scenarios may show the identical DC-link
        energy excursion because all three saturate at the same numerical energy floor; this metric
        does not quantify how long unmet demand continued afterward.
      </p>
      <p data-testid="outcome-caution" className="font-sans text-[12px] leading-snug text-secondary">
        Outcome labels are this simplified model&rsquo;s classification of the run, not certified hardware fault-ride-through performance. The model has no fault ride-through dynamics.
      </p>

      <ScrollRegion label="Scenario comparison table" className="border border-hairline">
        <table className="w-full min-w-[1080px] border-collapse font-mono text-[10.5px]">
          <thead>
            <tr className="border-b border-hairline bg-surface-raised">
              <Th label="Scenario" sticky />
              <Th label="Outcome" />
              <Th label="Recovery" />
              <Th label="Coordination" />
              <Th label="Trip time (s)" />
              <Th label="Bus collapse (s)" />
              <Th label="States reached" />
              {METRIC_COLUMNS.map((c) => (
                <Th key={c.key} label={`${c.label} (${c.unit})`} />
              ))}
              <Th label="Grid ever lost" />
              <Th label="Dominant stress" />
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <Row key={entry.scenario} entry={entry} entries={entries} />
            ))}
          </tbody>
        </table>
      </ScrollRegion>

      <CoverageChecklist coverage={entries[0]?.protection_timeline.coverage ?? []} />
    </section>
  );
}

function Th({ label, sticky = false }: { label: string; sticky?: boolean }) {
  return (
    <th className={`whitespace-nowrap px-2 py-1.5 text-left font-sans text-[11px] font-semibold uppercase tracking-[0.04em] text-secondary ${
      sticky ? "sticky left-0 z-10 bg-surface-raised" : ""
    }`}>
      {label}
    </th>
  );
}

function Row({
  entry,
  entries,
}: {
  entry: ScenarioComparisonEntry;
  entries: ScenarioComparisonEntry[];
}) {
  const timeline = entry.protection_timeline;
  const role = OUTCOME_ROLE[timeline.outcome];

  return (
    <tr className="border-b border-hairline last:border-b-0" data-testid={`comparison-row-${entry.scenario}`}>
      <td className="sticky left-0 z-10 whitespace-nowrap bg-surface px-2 py-1.5 font-semibold text-primary">
        {SCENARIO_LABEL[entry.scenario]}
      </td>
      <td className="whitespace-nowrap px-2 py-1.5">
        <span className="flex items-center gap-1.5">
          <span className={`h-[6px] w-[6px] shrink-0 rounded-full ${DOT_BG_BY_ROLE[role]}`} />
          {timeline.outcome_label}
        </span>
      </td>
      <td className="whitespace-nowrap px-2 py-1.5 text-secondary">{timeline.recovery_label}</td>
      <td className="px-2 py-1.5 text-secondary">{timeline.coordination.result_label}</td>
      <td
        className="whitespace-nowrap px-2 py-1.5 text-secondary"
        title={timeline.trip_event_time_s === null ? TRIP_TIME_NULL_TITLE : undefined}
      >
        {formatNullableSeconds(timeline.trip_event_time_s)}
      </td>
      <td
        className="whitespace-nowrap px-2 py-1.5 text-secondary"
        title={timeline.bus_collapse_event_time_s === null ? BUS_COLLAPSE_TIME_NULL_TITLE : undefined}
      >
        {formatNullableSeconds(timeline.bus_collapse_event_time_s)}
      </td>
      <td className="whitespace-nowrap px-2 py-1.5 text-secondary">
        {entry.stress_profile.protection_states_reached.join(" → ")}
      </td>
      {METRIC_COLUMNS.map((c) => {
        const value = c.getValue(entry);
        const isExtreme = value === extremalValue(entries, c);
        return (
          <td
            key={c.key}
            className={`whitespace-nowrap px-2 py-1.5 tabular-nums ${
              isExtreme ? "font-bold text-primary" : "text-secondary"
            }`}
            title={isExtreme ? `${c.emphasis === "max" ? "Largest" : "Smallest"} in this column` : undefined}
          >
            {c.format(value)}
          </td>
        );
      })}
      <td className="whitespace-nowrap px-2 py-1.5 text-secondary">
        {entry.stress_profile.grid_ever_unavailable ? "Yes" : "No"}
      </td>
      <td className="px-2 py-1.5 text-secondary">
        <span className="font-semibold text-primary">{entry.stress_profile.dominant_stress_label}</span>
        <span className="block text-[11px] text-secondary">{entry.stress_profile.dominant_stress_detail}</span>
      </td>
    </tr>
  );
}
