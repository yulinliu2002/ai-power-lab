import { formatEnergyDeficitKj, type TransientMetrics } from "../lib/transientMetrics";

interface EnergyDeficitAnalysisProps {
  metrics: TransientMetrics;
  voltageReferenceV: number;
}

/**
 * ANALYZE / Energy Deficit (SPEC-005 §10): why the transient was as
 * severe as it was. Severity follows the *accumulated* energy drawn
 * from the DC link, not the instantaneous peak power mismatch.
 *
 * Governing relations (stated in prose, not computed here):
 *   dE_dc/dt = P_sst - P_load,  so  deficit = integral(P_load - P_sst) dt
 *   E_dc = 1/2 C_dc V_dc^2,     so  dE = 1/2 C_dc (V_ref^2 - V_dc,min^2)
 * Units: power kW, energy kJ, voltage V, time s.
 *
 * Every number is read from `TransientMetrics` (the energy figure via
 * the shared `formatEnergyDeficitKj`, the same string the Power
 * Balance chart caption uses). Nothing is integrated or recomputed in
 * this component. Whole-run result: does not follow the scrubber.
 */
export function EnergyDeficitAnalysis({ metrics, voltageReferenceV }: EnergyDeficitAnalysisProps) {
  const hasDeficit = metrics.peakDeficitKw > 0;
  const deficitKj = formatEnergyDeficitKj(metrics);

  return (
    <section className="flex flex-col gap-2 border-t border-hairline pt-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-sans text-[12px] font-bold uppercase tracking-[0.04em] text-secondary">
          ENERGY DEFICIT
        </span>
        <span className="font-sans text-[10.5px] text-secondary">
          Is severity set by the peak gap, or by how long the gap lasts?
        </span>
      </div>

      <p className="font-sans text-[12.5px] leading-snug text-secondary">
        How far V_dc sags is set by the <em>area</em> under the power-mismatch curve &mdash; the
        total energy the bus gives up while demand outruns delivery &mdash; not by how tall the
        curve&rsquo;s peak is. A tall but brief gap drains little; a modest gap that lasts drains
        more.
      </p>

      <div className="grid grid-cols-1 gap-x-2 border-y border-hairline sm:grid-cols-2 sm:gap-x-0 sm:divide-x sm:divide-hairline">
        <div className="flex flex-col gap-0.5 px-3 py-1.5">
          <span className="font-sans text-[10.5px] font-semibold uppercase tracking-[0.04em] text-muted">
            PEAK MISMATCH &mdash; INSTANTANEOUS
          </span>
          <span className="font-mono text-[16px] font-semibold leading-none tabular-nums text-primary">
            {hasDeficit ? metrics.peakDeficitKw.toFixed(1) : "0.0"}
            <span className="ml-1 text-[11px] font-normal text-muted">kW</span>
          </span>
          <span className="font-mono text-[9.5px] leading-snug text-secondary">
            {hasDeficit
              ? `largest P_load − P_sst at one instant, t = ${metrics.peakDeficitTimeS.toFixed(3)} s (power)`
              : "P_sst never fell behind P_load"}
          </span>
        </div>
        <div className="flex flex-col gap-0.5 px-3 py-1.5">
          <span className="font-sans text-[10.5px] font-semibold uppercase tracking-[0.04em] text-muted">
            ENERGY DEFICIT &mdash; ACCUMULATED
          </span>
          <span className="font-mono text-[16px] font-semibold leading-none tabular-nums text-primary">
            {deficitKj}
            <span className="ml-1 text-[11px] font-normal text-muted">kJ</span>
          </span>
          <span className="font-mono text-[9.5px] leading-snug text-secondary">
            drawn from the DC link between the step and the V_dc minimum (energy)
          </span>
        </div>
      </div>

      <ol className="flex list-decimal flex-col gap-0.5 pl-5 font-sans text-[12.5px] leading-snug text-secondary">
        <li>Power mismatch: P_load exceeds P_sst, and the DC bus covers the difference.</li>
        <li>
          Accumulated over time, that mismatch is an energy deficit of {deficitKj} kJ (the shaded
          area on the Power Balance chart).
        </li>
        <li>The stored DC-link energy E_dc falls by exactly that amount.</li>
        <li>
          Because E_dc = &#189; C_dc V_dc&sup2;, V_dc sags &mdash; here to a minimum of{" "}
          {metrics.minVdcV.toFixed(1)} V at t = {metrics.minVdcTimeS.toFixed(3)} s, from the{" "}
          {voltageReferenceV.toFixed(0)} V reference.
        </li>
        <li>
          The controller raises SST power until it passes demand, the mismatch closes, and V_dc
          recovers
          {metrics.recoveryElapsedS === null
            ? " (it did not settle within the simulated run)."
            : ` to within ±1% of V_ref after ${metrics.recoveryElapsedS.toFixed(2)} s.`}
        </li>
      </ol>

      <div className="flex flex-col gap-0.5 border-t border-hairline pt-1.5">
        <span className="font-sans text-[9.5px] font-semibold uppercase tracking-[0.04em] text-muted">
          Engineering basis
        </span>
        <p className="font-mono text-[10.5px] text-secondary">
          &Delta;E = &int;(P_load &minus; P_sst) dt
        </p>
        <p className="font-mono text-[10.5px] text-secondary">
          dE_dc/dt = P_sst &minus; P_load &nbsp;&nbsp;&middot;&nbsp;&nbsp; E_dc = &#189; C_dc
          V_dc&sup2; &nbsp;&nbsp;&middot;&nbsp;&nbsp; &Delta;E = &#189; C_dc (V_ref&sup2; &minus;
          V_dc,min&sup2;)
        </p>
        <p className="font-mono text-[9px] leading-snug text-muted">
          The integral is the governing relationship; the value shown is evaluated through the
          capacitor&rsquo;s own energy equation, using this run&rsquo;s C_dc, rather than by
          summing samples. Lumped DC-link capacitor, no other energy path; educational model, not
          calibrated to any hardware.
        </p>
      </div>
    </section>
  );
}
