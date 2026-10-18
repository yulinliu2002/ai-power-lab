"use client";

import { useState } from "react";

import {
  ARCHITECTURE_CHOICE_NAMES,
  CONDITIONAL_DECISIONS,
  DRIVERS,
  type DriverId,
} from "../lib/architectureChoicesData";
import { EvidenceTag } from "./EvidenceTag";

/**
 * "If this driver dominates" -- single-select over the seven requirement
 * drivers, revealing that driver's conditional decision. The only client
 * interaction on /architecture (SPEC-011 Scope item 5). Conditional and
 * qualitative: `favored` is a set under a stated condition, never a ranking.
 */
export function DominantDriverSelector() {
  const [selected, setSelected] = useState<DriverId>("rd1");
  const driver = DRIVERS.find((d) => d.id === selected)!;
  const decision = CONDITIONAL_DECISIONS[selected];

  return (
    <div className="flex flex-col gap-3">
      <fieldset className="flex flex-wrap gap-1.5">
        <legend className="sr-only">Which driver dominates</legend>
        {DRIVERS.map((d) => {
          const isSelected = d.id === selected;
          return (
            <label key={d.id} className="relative">
              <input
                type="radio"
                name="dominant-driver"
                value={d.id}
                checked={isSelected}
                data-testid={`driver-option-${d.id}`}
                onChange={() => setSelected(d.id)}
                className="peer sr-only"
              />
              <span
                className={`block cursor-pointer border px-2.5 py-1 font-sans text-[11px] font-semibold peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-secondary ${
                  isSelected
                    ? "border-primary bg-surface-raised text-primary"
                    : "border-hairline bg-surface text-secondary hover:text-primary"
                }`}
              >
                {d.title}
              </span>
            </label>
          );
        })}
      </fieldset>

      <div
        data-testid={`decision-card-${selected}`}
        className="flex max-w-3xl flex-col gap-2 border border-hairline bg-surface-raised px-3 py-3"
      >
        <p className="font-mono text-[10.5px] uppercase tracking-[0.06em] text-secondary">
          If &ldquo;{driver.title}&rdquo; dominates
        </p>
        <DecisionField
          label="Tends to favor"
          body={decision.favored.map((id) => ARCHITECTURE_CHOICE_NAMES[id]).join(" · ")}
        />
        <DecisionField label="Because" body={decision.because} />
        <div className="flex flex-col gap-0.5">
          <span className="font-sans text-[10.5px] font-semibold uppercase tracking-[0.04em] text-secondary">
            Unless
          </span>
          <ul className="flex flex-col gap-1">
            {decision.unless.map((u) => (
              <li key={u} className="flex gap-1.5 text-[12px] leading-relaxed text-secondary">
                <span aria-hidden="true" className="text-muted">&middot;</span>
                <span>{u}</span>
              </li>
            ))}
          </ul>
        </div>
        <DecisionField label="How it connects" body={decision.connects} />
        <DecisionField label="Decision it informs" body={decision.informs} />
        <EvidenceTag evidence={decision.evidence} basis={decision.basis} refs={decision.refs} />
      </div>
    </div>
  );
}

function DecisionField({ label, body }: { label: string; body: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-sans text-[10.5px] font-semibold uppercase tracking-[0.04em] text-secondary">
        {label}
      </span>
      <p className="text-[12px] leading-relaxed text-secondary">{body}</p>
    </div>
  );
}
