import Link from "next/link";

import type { ScenarioRunResponse } from "../lib/simulationApi";
import { formatSeconds } from "../lib/formatSeconds";
import {
  MODEL_DOES_NOT_REPRESENT,
  NOT_VALIDATED_STATEMENT,
  OUTCOME_CAUTION,
  PROTECTION_COVERAGE_STATEMENT,
  VALIDATE_LINK_TEXT,
} from "../lib/sandboxTakeawayData";
import { formatEnergyDeficitKj, type TransientMetrics } from "../lib/transientMetrics";
import { EvidenceTag } from "./EvidenceTag";

/**
 * Stage 4: Engineering takeaway (SPEC-014 section 6.3). Every live field
 * is read from the already-fetched response (outcome, recovery and
 * coordination labels verbatim from the backend) or, for Load Step only,
 * from the existing `computeTransientMetrics` object. Scenarios B-E show
 * no derived numbers. No comparison-response data is shown, because the
 * comparison covers fixed presets only and cannot describe an overridden
 * run. The fixed strings come from `lib/sandboxTakeawayData.ts` (spec
 * Appendix A) and make no claim about real equipment.
 */
export function EngineeringTakeaway({
  data,
  metrics,
  provenance,
}: {
  data: ScenarioRunResponse;
  metrics: TransientMetrics | null;
  provenance: string;
}) {
  const timeline = data.protection_timeline;
  const firstEvent = data.events[0];

  return (
    <div data-testid="engineering-takeaway" className="grid grid-cols-1 gap-3 lg:grid-cols-2">
      <TakeawayBlock title="What happened">
        <p className="text-[13px] text-secondary" data-testid="takeaway-provenance">
          {provenance}
        </p>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-[13px]">
          <dt className="text-secondary">First event</dt>
          <dd className="font-mono tabular-nums text-primary">
            {firstEvent ? `${firstEvent.label} at t = ${formatSeconds(firstEvent.time_s)}` : "no event recorded"}
          </dd>
          {metrics && (
            <>
              <dt className="text-secondary">Lowest V_dc</dt>
              <dd className="font-mono tabular-nums text-primary">
                {metrics.minVdcV.toFixed(1)} V at t = {metrics.minVdcTimeS.toFixed(3)} s
              </dd>
              <dt className="text-secondary">Energy deficit</dt>
              <dd className="font-mono tabular-nums text-primary">{formatEnergyDeficitKj(metrics)} kJ</dd>
              <dt className="text-secondary">Recovery time</dt>
              <dd className="font-mono tabular-nums text-primary">
                {metrics.recoveryElapsedS === null
                  ? "not settled before this run ends"
                  : `${metrics.recoveryElapsedS.toFixed(2)} s`}
              </dd>
            </>
          )}
        </dl>
        <EvidenceTag
          glyph
          evidence="model-output"
          basis="Values calculated by this repository's simplified model for the displayed run."
        />
      </TakeawayBlock>

      <TakeawayBlock title="What the model reports">
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-[13px]">
          <dt className="text-secondary">Outcome</dt>
          <dd className="text-primary">{timeline.outcome_label}</dd>
          <dt className="text-secondary">Detail</dt>
          <dd className="text-secondary">{timeline.outcome_detail}</dd>
          <dt className="text-secondary">Recovery</dt>
          <dd className="text-secondary">{timeline.recovery_label}</dd>
          <dt className="text-secondary">Coordination</dt>
          <dd className="text-secondary">{timeline.coordination.result_label}</dd>
        </dl>
        <p className="text-[12px] leading-snug text-secondary">{OUTCOME_CAUTION}</p>
        <EvidenceTag
          glyph
          evidence="model-output"
          basis="Classification strings supplied by the backend for this run, shown verbatim."
        />
      </TakeawayBlock>

      <TakeawayBlock title="What the model does not represent">
        <p className="text-[13px] leading-relaxed text-secondary">{MODEL_DOES_NOT_REPRESENT}</p>
        <p className="text-[13px] leading-relaxed text-secondary">{PROTECTION_COVERAGE_STATEMENT}</p>
        <p className="text-[13px] leading-relaxed text-secondary">{NOT_VALIDATED_STATEMENT}</p>
        <EvidenceTag
          glyph
          evidence="assumption"
          basis="Restates the documented limits of the simplified model; not a claim about real equipment."
        />
      </TakeawayBlock>

      <TakeawayBlock title="What would need validating, and where to go next">
        <p className="text-[13px] leading-relaxed text-secondary">
          <Link
            href="/architecture#step-validation"
            className="text-primary underline underline-offset-2 hover:opacity-80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary"
          >
            {VALIDATE_LINK_TEXT}
          </Link>
          .
        </p>
        <ul className="flex flex-col gap-1 text-[13px] text-secondary">
          <li>
            <Link
              href="/learn"
              className="text-primary underline underline-offset-2 hover:opacity-80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary"
            >
              Learn by Example
            </Link>{" "}
            for a guided walkthrough of a disturbance.
          </li>
          <li>
            <Link
              href="/architecture"
              className="text-primary underline underline-offset-2 hover:opacity-80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary"
            >
              Architecture Choices
            </Link>{" "}
            to compare the three architectures against a requirement.
          </li>
        </ul>
      </TakeawayBlock>
    </div>
  );
}

function TakeawayBlock({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2 border border-hairline bg-surface px-4 py-3">
      <h3 className="text-heading text-primary">{title}</h3>
      {children}
    </section>
  );
}
