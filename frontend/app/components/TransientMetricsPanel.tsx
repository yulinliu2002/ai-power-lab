import { formatEnergyDeficitKj, type TransientMetrics } from "../lib/transientMetrics";

interface TransientMetricsPanelProps {
  metrics: TransientMetrics;
  voltageReferenceV: number;
}

/**
 * Compact analysis strip summarizing the Scenario A transient -- see
 * `lib/transientMetrics.ts` for the exact definition of each value.
 * These are fixed analysis results over the whole run, not a live
 * value at the scrubber position, so -- like the KPI strip -- all
 * five results share one `divide-x` strip (one bordered surface)
 * instead of five separately boxed cards. This is the one place in
 * the console every quantified result of the Scenario A transient is
 * stated -- `EngineeringInterpretation` (WHY THIS HAPPENED, above)
 * references these same numbers in prose rather than restating them.
 *
 * Labels are phrased as the plain-English question each number
 * answers (e.g. "VOLTAGE DROP" rather than "MIN V_DC AFTER STEP");
 * the caption underneath still gives the precise technical
 * definition for a reader who wants it.
 *
 * The governing equations behind these results sit directly below the
 * tiles, always visible rather than behind a toggle -- last in the
 * What happened (`EventBanner`) → Why (`EngineeringInterpretation`) →
 * Engineering result (here) → governing equations sequence, and the
 * one place those equations and the model-fidelity disclaimer are
 * stated (a previous revision had a near-duplicate copy of both
 * attached to a second, now-removed explanatory card). They stay
 * unconditionally rendered, not gated behind a show/hide control, so
 * the physics a learner needs to check the causal account above is
 * never hidden behind interaction.
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
      <div className="grid grid-cols-2 gap-x-2 border-y border-hairline sm:grid-cols-5 sm:gap-x-0 sm:divide-x sm:divide-hairline">
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
              ? `peak P_load − P_sst gap (instantaneous), at t = ${metrics.peakDeficitTimeS.toFixed(3)} s`
              : "P_sst never fell behind P_load"
          }
        />
        <MetricTile
          label="ENERGY DEFICIT"
          value={formatEnergyDeficitKj(metrics)}
          unit="kJ"
          caption="drawn from the DC link, event to V_dc minimum (accumulated, not instantaneous)"
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

      <div className="flex flex-col gap-0.5 border-t border-hairline pt-1.5">
        <span className="font-sans text-[11px] font-semibold uppercase tracking-[0.04em] text-secondary">
          Engineering basis
        </span>
        <p className="font-mono text-[10.5px] text-secondary">
          dE_dc/dt = P_sst &minus; P_load &nbsp;&nbsp;&middot;&nbsp;&nbsp; E_dc = &#189; C_dc
          V_dc&sup2;
        </p>
        <p className="font-mono text-[10.5px] text-secondary">
          &Delta;E = &int;(P_load &minus; P_sst) dt = &#189; C_dc (V_ref&sup2; &minus;
          V_dc,min&sup2;)
        </p>
        <p className="font-mono text-[11px] leading-snug text-secondary">
          Simplified, average-value system-level model: the SST response time is a tunable
          modeling assumption, not a real hardware bandwidth limit, and the lumped DC-link
          capacitor is the only energy path modeled &mdash; no calibration to any commercial SST
          or DC-link design, no claim about real hardware protection performance. The energy
          deficit above is evaluated through the capacitor&rsquo;s own closed-form energy
          equation at this run&rsquo;s C_dc, not by summing samples, so it won&rsquo;t include
          later ripple-deficit sub-intervals a numerical integral would. Recovery time is the
          first instant after the load step at which V_dc returns to and remains within
          &plusmn;1% of V_ref for the rest of the run.
        </p>
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
      <span className="font-sans text-[10.5px] font-semibold uppercase tracking-[0.04em] text-secondary">
        {label}
      </span>
      <span className="font-mono text-[16px] font-semibold leading-none tabular-nums text-primary">
        {value}
        <span className="ml-1 text-[11px] font-normal text-secondary">{unit}</span>
      </span>
      <span className="font-mono text-[11px] leading-snug text-secondary">{caption}</span>
    </div>
  );
}
