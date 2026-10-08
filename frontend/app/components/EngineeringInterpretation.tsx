import type { TransientMetrics } from "../lib/transientMetrics";

interface EngineeringInterpretationProps {
  metrics: TransientMetrics;
  voltageReferenceV: number;
}

/**
 * The "why" for the Scenario A transient -- plain language first,
 * the governing equations second as reinforcement, never the other
 * way around. Built from the same `TransientMetrics` the tiles below
 * show -- see `lib/transientMetrics.ts`. No number here is
 * hardcoded; every figure is read from the computed metrics for the
 * run actually fetched, so this describes whatever experiment is
 * currently loaded, baseline or not.
 *
 * Only cites the minimum voltage as its one proof-point -- the exact
 * deficit/deviation/recovery-time figures are the metrics tiles'
 * job, not this prose's, so the two don't just restate each other.
 *
 * Deliberately not a boxed card: a top hairline is enough separation
 * from the section above it, consistent with reserving full bordered
 * panels for places (the schematic, the charts) where containment
 * genuinely aids comprehension.
 */
export function EngineeringInterpretation({
  metrics,
  voltageReferenceV,
}: EngineeringInterpretationProps) {
  return (
    <section className="flex flex-col gap-2 border-t border-hairline pt-2">
      <span className="font-sans text-[12px] font-bold uppercase tracking-[0.04em] text-secondary">
        WHY THIS HAPPENED
      </span>
      <p className="font-sans text-[12.5px] leading-snug text-secondary">
        At t = {metrics.eventTimeS.toFixed(2)} s, AI demand jumps almost instantly &mdash; far
        faster than this model&rsquo;s SST (solid-state transformer) response time constant lets
        delivered power follow. While demand outruns delivery, the DC bus supplies the missing
        power from its own stored energy, and V_dc falls as that energy drains &mdash; reaching a
        minimum of {metrics.minVdcV.toFixed(1)} V. To close the gap, the controller doesn&rsquo;t
        just raise SST power to match demand &mdash; it pushes SST power{" "}
        <em>above</em> demand for a while, which is what actually refills the bus&rsquo;s stored
        energy and drives V_dc back up toward the {voltageReferenceV.toFixed(0)} V reference; once
        the bus is recharged, SST power settles back down to match demand again.
      </p>
      <div className="flex flex-col gap-0.5 border-t border-hairline pt-1.5">
        <span className="font-sans text-[9.5px] font-semibold uppercase tracking-[0.04em] text-muted">
          Engineering basis
        </span>
        <p className="font-mono text-[10.5px] text-secondary">
          dE_dc/dt = P_sst &minus; P_load &nbsp;&nbsp;&middot;&nbsp;&nbsp; E_dc = &#189; C_dc V_dc&sup2;
        </p>
        <p className="font-mono text-[9px] leading-snug text-muted">
          Simplified, average-value system-level model &mdash; the SST response time is a tunable
          modeling assumption, not a real hardware bandwidth limit; no calibration to any
          commercial SST; no claim about real hardware protection performance. Recovery time (in
          the result below): first instant after the load step at which V_dc returns to and
          remains within &plusmn;1% of V_ref for the rest of the run.
        </p>
      </div>
    </section>
  );
}
