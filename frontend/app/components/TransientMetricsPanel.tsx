import type { TransientMetrics } from "../lib/transientMetrics";

interface TransientMetricsPanelProps {
  metrics: TransientMetrics;
  voltageReferenceV: number;
}

/**
 * Compact analysis strip summarizing the Scenario A transient -- see
 * `lib/transientMetrics.ts` for the exact definition of each value.
 * These are fixed analysis results over the whole run, not a live
 * value at the scrubber position, so -- like the KPI strip -- the
 * four results share one `divide-x` strip (one bordered surface)
 * instead of four separately boxed cards.
 *
 * Labels are phrased as the plain-English question each number
 * answers (e.g. "VOLTAGE DROP" rather than "MIN V_DC AFTER STEP");
 * the caption underneath still gives the precise technical
 * definition for a reader who wants it.
 */
export function TransientMetricsPanel({ metrics, voltageReferenceV }: TransientMetricsPanelProps) {
  const hasDeficit = metrics.peakDeficitKw > 0;

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-sans text-[12px] font-bold uppercase tracking-[0.04em] text-secondary">
          ENGINEERING RESULT
        </span>
        <span className="font-sans text-[10.5px] text-secondary">
          How severe was this event, and how fast did the system recover?
        </span>
      </div>
      <div className="grid grid-cols-2 gap-x-2 border-y border-hairline sm:grid-cols-4 sm:gap-x-0 sm:divide-x sm:divide-hairline">
        <MetricTile
          label="VOLTAGE DROP"
          value={metrics.minVdcV.toFixed(1)}
          unit="V"
          caption={`lowest V_dc, at t = ${metrics.minVdcTimeS.toFixed(3)} s`}
        />
        <MetricTile
          label="PEAK DEVIATION"
          value={metrics.maxDeviationV.toFixed(1)}
          unit="V"
          caption={`${metrics.maxDeviationPercent.toFixed(1)}% ${metrics.maxDeviationIsAbove ? "above" : "below"} the ${voltageReferenceV.toFixed(0)} V reference, at t = ${metrics.maxDeviationTimeS.toFixed(3)} s`}
        />
        <MetricTile
          label="POWER MISMATCH"
          value={hasDeficit ? metrics.peakDeficitKw.toFixed(1) : "0.0"}
          unit="kW"
          caption={
            hasDeficit
              ? `peak P_load − P_sst gap, at t = ${metrics.peakDeficitTimeS.toFixed(3)} s`
              : "P_sst never fell behind P_load"
          }
        />
        <MetricTile
          label="RECOVERY TIME"
          value={metrics.recoveryElapsedS === null ? "—" : metrics.recoveryElapsedS.toFixed(2)}
          unit={metrics.recoveryElapsedS === null ? "NOT SETTLED" : "s"}
          caption={
            metrics.recoveryElapsedS === null
              ? "V_dc did not settle within the simulated run"
              : "back within ±1% of V_ref and stays there"
          }
        />
      </div>
    </div>
  );
}

function MetricTile({
  label,
  value,
  unit,
  caption,
}: {
  label: string;
  value: string;
  unit: string;
  caption: string;
}) {
  return (
    <div className="flex flex-col gap-0.5 px-3 py-1.5">
      <span className="font-sans text-[10.5px] font-semibold uppercase tracking-[0.04em] text-muted">
        {label}
      </span>
      <span className="font-mono text-[16px] font-semibold leading-none tabular-nums text-primary">
        {value}
        <span className="ml-1 text-[11px] font-normal text-muted">{unit}</span>
      </span>
      <span className="font-mono text-[9.5px] leading-snug text-secondary">{caption}</span>
    </div>
  );
}
