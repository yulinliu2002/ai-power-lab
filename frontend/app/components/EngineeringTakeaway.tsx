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

  const row = "grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-[13px]";
  return (
    <div data-testid="engineering-takeaway" className="ic-take">
      <div className="flex flex-col gap-6">
        <section className="flex flex-col gap-2">
          <h3 className="ic-eyebrow" style={{ margin: 0 }}>What happened</h3>
          <p className="ic-body" data-testid="takeaway-provenance">
            {provenance}
          </p>
          <dl className={row}>
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
        </section>

        <section className="flex flex-col gap-2" style={{ borderTop: "1px solid var(--ic-rule)", paddingTop: 20 }}>
          <h3 className="ic-eyebrow" style={{ margin: 0 }}>What the model reports</h3>
          <p className="ic-outcome">{timeline.outcome_label || NOT_AVAILABLE}</p>
          <dl className={row}>
            <dt className="text-secondary">Outcome</dt>
            <dd className="text-primary">{timeline.outcome_label || NOT_AVAILABLE}</dd>
            <dt className="text-secondary">Detail</dt>
            <dd className="text-secondary">{timeline.outcome_detail || NOT_AVAILABLE}</dd>
            <dt className="text-secondary">Recovery</dt>
            <dd className="text-secondary">{timeline.recovery_label || NOT_AVAILABLE}</dd>
            <dt className="text-secondary">Coordination</dt>
            <dd className="text-secondary">{timeline.coordination?.result_label || NOT_AVAILABLE}</dd>
          </dl>
          <EvidenceTag
            glyph
            evidence="model-output"
            basis="Classification strings supplied by the backend for this run, shown verbatim."
          />
        </section>
      </div>

      <div className="flex flex-col gap-6">
        <section className="flex flex-col gap-3">
          <h3 className="ic-eyebrow" style={{ margin: 0 }}>What the model does not represent</h3>
          <p className="text-[14px] leading-relaxed text-secondary">{MODEL_DOES_NOT_REPRESENT}</p>
          <p className="text-[14px] leading-relaxed text-secondary">{PROTECTION_COVERAGE_STATEMENT}</p>
          <p className="text-[14px] leading-relaxed text-secondary">{OUTCOME_CAUTION}</p>
          <p className="text-[14px] leading-relaxed text-secondary">{NOT_VALIDATED_STATEMENT}</p>
          <EvidenceTag
            glyph
            evidence="assumption"
            basis="Restates the documented limits of the simplified model; not a claim about real equipment."
          />
        </section>

        <section className="flex flex-col gap-2" style={{ borderTop: "1px solid var(--ic-rule)", paddingTop: 20 }}>
          <h3 className="ic-eyebrow" style={{ margin: 0 }}>What would need validating, and where to go next</h3>
          <p className="text-[14px] leading-relaxed text-secondary">
            <Link
              href="/architecture#step-validation"
              className="text-primary underline underline-offset-2 hover:opacity-80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary"
            >
              {VALIDATE_LINK_TEXT}
            </Link>
          </p>
          <ul className="flex flex-col gap-1 text-[14px] text-secondary">
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
        </section>
      </div>
    </div>
  );
}

const NOT_AVAILABLE = "not available for this run";
