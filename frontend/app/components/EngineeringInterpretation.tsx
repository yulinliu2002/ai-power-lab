import type { TransientMetrics } from "../lib/transientMetrics";

interface EngineeringInterpretationProps {
  metrics: TransientMetrics;
  voltageReferenceV: number;
}

/**
 * One restrained causal-chain readout for the Scenario A transient,
 * built from the same `TransientMetrics` the tiles above show -- see
 * `lib/transientMetrics.ts`. No number here is hardcoded; every
 * figure is read from the computed metrics for the run actually
 * fetched.
 */
export function EngineeringInterpretation({
  metrics,
  voltageReferenceV,
}: EngineeringInterpretationProps) {
  const recoveryClause =
    metrics.recoveryElapsedS === null
      ? "does not settle back within ±1% of V_ref before the simulated run ends"
      : `recovers to within ±1% of V_ref roughly ${metrics.recoveryElapsedS.toFixed(2)} s after the step`;

  return (
    <section className="flex flex-col gap-2 border border-hairline bg-surface px-4 py-3">
      <span className="font-sans text-[11.5px] font-semibold uppercase tracking-[0.04em] text-muted">
        ENGINEERING INTERPRETATION
      </span>
      <p className="font-sans text-[12.5px] leading-relaxed text-secondary">
        At t = {metrics.eventTimeS.toFixed(2)} s the AI load steps upward. Demand (P_load) rises
        faster than the SST&rsquo;s control loop can supply it, so P_load briefly exceeds P_sst by up
        to {Math.max(metrics.peakDeficitKw, 0).toFixed(1)} kW. The 800 VDC bus&rsquo;s own stored
        energy covers that deficit, so V_dc droops &mdash; reaching a minimum of{" "}
        {metrics.minVdcV.toFixed(1)} V ({metrics.maxDeviationPercent.toFixed(1)}% below the{" "}
        {voltageReferenceV.toFixed(0)} V reference) at t = {metrics.minVdcTimeS.toFixed(3)} s. As the
        controller drives P_sst back up to match demand, the deficit closes and V_dc {recoveryClause}.
      </p>
      <p className="font-mono text-[10px] text-muted">
        Simplified, average-value system-level model: no switching/semiconductor dynamics, no
        calibration to any commercial SST, and no claim about real hardware protection performance.
        Recovery time is defined as the first instant after the load step at which V_dc returns to
        and remains within ±1% of V_ref for the rest of the run.
      </p>
    </section>
  );
}
