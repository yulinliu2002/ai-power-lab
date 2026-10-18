import { formatEnergyDeficitKj, type TransientMetrics } from "../lib/transientMetrics";

interface EngineeringInterpretationProps {
  metrics: TransientMetrics;
  voltageReferenceV: number;
}

/**
 * The "why" for the Scenario A transient -- plain language, two
 * distinct lessons, each stated exactly once. Built from the same
 * `TransientMetrics` the ENGINEERING RESULT tiles below show -- see
 * `lib/transientMetrics.ts`. No number here is hardcoded; every figure
 * is read from the computed metrics for the run actually fetched, so
 * this describes whatever experiment is currently loaded, baseline or
 * not. The governing equations this prose describes live once, in
 * `TransientMetricsPanel`'s "Technical details" toggle, immediately
 * after the quantified results they explain -- not duplicated here.
 *
 *   1. WHY V_dc moves at all -- the SST can't track an instant load
 *      step, so the DC bus supplies/absorbs the gap and V_dc moves
 *      with it until the controller closes the gap.
 *   2. WHY the sag is as deep as it is -- severity tracks the
 *      *accumulated* energy deficit (an area), not the instantaneous
 *      peak power gap (a height). A previous revision stated this
 *      lesson in a separate card with its own near-duplicate
 *      "Engineering basis" footer and a numbered walkthrough that
 *      re-derived the same conclusion ENGINEERING RESULT already
 *      states as numbers -- folded in here instead.
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
      <p className="font-sans text-[12.5px] leading-snug text-secondary">
        How far V_dc sags is set by the <em>accumulated</em> energy deficit &mdash; the area under
        the power-mismatch curve while demand outruns delivery &mdash; not by how tall that gap&rsquo;s
        peak is: a tall but brief mismatch drains little; a modest one that lasts drains more. Here
        that works out to {formatEnergyDeficitKj(metrics)} kJ drawn from the DC link (the shaded
        area on the Power Balance chart below; every other number this derivation uses is in
        ENGINEERING RESULT, further down).
      </p>
    </section>
  );
}
