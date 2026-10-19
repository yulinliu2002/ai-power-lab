"use client";

import Link from "next/link";
import { useState } from "react";

import { AreaHeader } from "./AreaHeader";
import { BasisPanel } from "./BasisPanel";
import { EvidenceTag } from "./EvidenceTag";
import { SignalPathRail } from "./SignalPathRail";
import { StageNav } from "./StageNav";
import {
  ARCHITECTURE_CHOICE_NAMES,
  ARCHITECTURE_ORDER,
  BOUNDARIES,
  CELLS,
  CONDITIONAL_DECISIONS,
  DISCLOSURES,
  DRIVERS,
  INTERFACES,
  REFERENCES,
  SOURCE_KIND_TEXT,
  VALIDATION_NEEDS,
  VALIDATION_SECTION_EVIDENCE,
  type BoundaryId,
  type Driver,
  type DriverId,
} from "../lib/architectureChoicesData";
import { ARCHITECTURES, type ArchitectureId } from "../lib/infrastructureMapData";

/**
 * Architecture Choices as a four-step evaluation (SPEC-014 Scope B):
 * identify the requirement, compare the architectures for it, understand
 * the trade-offs, define the validation needs. Same data module and the
 * same content as SPEC-011 -- only the disclosure of it is progressive:
 * the selected driver's content is shown, and "Show all" controls render
 * the complete reference view (all seven drivers, all 21 comparison
 * cells, all seven decisions, all five boundaries). No scores, no ranking
 * and no "best" statement (SPEC-011 AC-8).
 */
const STAGES = [
  { id: "step-requirement", n: 1, label: "Identify the requirement" },
  { id: "step-compare", n: 2, label: "Compare architectures" },
  { id: "step-tradeoffs", n: 3, label: "Understand trade-offs" },
  { id: "step-validation", n: 4, label: "Define validation needs" },
  { id: "references", label: "References" },
] as const;

const DISCLOSURE_ITEMS = [
  { tag: "SST", text: DISCLOSURES.sst },
  { tag: "Blocks", text: DISCLOSURES.block },
  { tag: "Simulation", text: DISCLOSURES.sim },
  { tag: "Drivers", text: DISCLOSURES.illustrative },
  { tag: "No winner", text: DISCLOSURES.noWinner },
] as const;

const link =
  "underline underline-offset-2 hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary";

export function ArchitectureChoices() {
  const [driverId, setDriverId] = useState<DriverId>("rd1");
  const [railArch, setRailArch] = useState<ArchitectureId>(ARCHITECTURE_ORDER[0]);
  const [boundaryId, setBoundaryId] = useState<BoundaryId>(BOUNDARIES[0].id);
  const [showAllDrivers, setShowAllDrivers] = useState(false);
  const [showAllBoundaries, setShowAllBoundaries] = useState(false);

  const driver = DRIVERS.find((d) => d.id === driverId)!;
  const nodeLabel = (id: string) =>
    ARCHITECTURES.flatMap((a) => a.nodes).find((n) => n.id === id)?.label ?? id;

  return (
    <main className="mx-auto flex w-full max-w-[1320px] flex-1 flex-col gap-6 px-4 py-5 sm:px-6">
      <AreaHeader
        title="Architecture choices"
        role="Evaluate alternatives against requirements"
        lede={
          <>
            Three architectures from the{" "}
            <Link href="/system-map" className={link}>
              System Map
            </Link>{" "}
            &mdash; {ARCHITECTURE_ORDER.map((id) => ARCHITECTURE_CHOICE_NAMES[id]).join(", ")}{" "}
            &mdash; are compared against seven requirement drivers. The aim is to practice reasoning
            from requirements to an architecture choice, and to name what must be validated before
            relying on it.
          </>
        }
        next={{ href: "/learn", label: "Learn by Example: see how the system behaves under a disturbance" }}
      />

      <BasisPanel items={DISCLOSURE_ITEMS} />
      <p className="max-w-3xl text-[12px] leading-relaxed text-secondary">
        Each item carries an evidence label: <em>Public fact</em> (principle or attributed source),{" "}
        <em>Illustrative assumption</em>, <em>Model output (simplified)</em>, or{" "}
        <em>Emerging / uncertain</em>. An item carries the label of its weakest claim.
      </p>

      <section aria-label="Power path context" className="flex flex-col gap-2">
        <fieldset className="flex flex-wrap items-center gap-2">
          <legend className="sr-only">Architecture shown in the power path</legend>
          <span className="font-mono text-meta uppercase text-secondary">Power path for</span>
          {ARCHITECTURE_ORDER.map((id) => (
            <label key={id} className="relative">
              <input
                type="radio"
                name="rail-architecture"
                value={id}
                checked={railArch === id}
                onChange={() => setRailArch(id)}
                className="peer sr-only"
                data-testid={`rail-option-${id}`}
              />
              <span
                className={`block cursor-pointer border px-2.5 py-1 text-[12px] font-semibold peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-secondary ${
                  railArch === id
                    ? "border-hairline-strong bg-surface-raised text-primary"
                    : "border-hairline bg-surface text-secondary hover:text-primary"
                }`}
              >
                {ARCHITECTURE_CHOICE_NAMES[id]}
              </span>
            </label>
          ))}
        </fieldset>
        <SignalPathRail architecture={railArch} note="Representative path, not a universal one" />
      </section>

      <StageNav label="Steps on this page" stages={STAGES} />

      <section id="step-requirement" className="flex flex-col gap-3" aria-labelledby="h-requirement">
        <StepHeading id="h-requirement" n={1} title="Identify the requirement" question="What matters most for the hypothetical site?" />
        <DriverChooser selected={driverId} onSelect={setDriverId} />
        <ShowAllToggle
          pressed={showAllDrivers}
          onToggle={() => setShowAllDrivers((v) => !v)}
          offLabel="Show all seven drivers, comparisons and decisions"
          onLabel="Back to the selected driver"
          testId="show-all-drivers"
        />
        {showAllDrivers ? (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {DRIVERS.map((d) => (
              <DriverCard key={d.id} driver={d} />
            ))}
          </div>
        ) : (
          <div className="max-w-3xl">
            <DriverCard driver={driver} />
          </div>
        )}
      </section>

      <section id="step-compare" className="flex flex-col gap-3 border-t border-hairline pt-4" aria-labelledby="h-compare">
        <StepHeading id="h-compare" n={2} title="Compare architectures" question="How does each architecture meet this driver?" />
        <p className="max-w-3xl text-body text-secondary">
          Qualitative only. &ldquo;Harder&rdquo; is what the architecture makes more difficult for
          that driver, not a score. {DISCLOSURES.sst}
        </p>
        {(showAllDrivers ? DRIVERS : [driver]).map((d) => (
          <CompareBlock key={d.id} driver={d} />
        ))}
        <p className="max-w-3xl text-[12px] leading-relaxed text-secondary">{DISCLOSURES.sim}</p>
      </section>

      <section id="step-tradeoffs" className="flex flex-col gap-3 border-t border-hairline pt-4" aria-labelledby="h-tradeoffs">
        <StepHeading id="h-tradeoffs" n={3} title="Understand trade-offs" question="What does this driver favor, under what condition, and where does the choice become a specification?" />
        <p className="max-w-3xl text-body text-secondary">
          A conditional tendency with its exceptions, not a verdict. {DISCLOSURES.noWinner}
        </p>
        {(showAllDrivers ? DRIVERS : [driver]).map((d) => (
          <DecisionCard key={d.id} driver={d} />
        ))}

        <div className="flex flex-col gap-3 pt-2">
          <h3 className="text-heading text-primary">Interfaces</h3>
          <p className="max-w-3xl text-body text-secondary">
            The five boundaries where a choice becomes a specification. These are the same for every
            driver. Node names are the System Map&rsquo;s. {DISCLOSURES.block}
          </p>
          <fieldset className="flex flex-wrap gap-1.5">
            <legend className="sr-only">Interface boundary</legend>
            {BOUNDARIES.map((b) => (
              <label key={b.id} className="relative">
                <input
                  type="radio"
                  name="boundary"
                  value={b.id}
                  checked={boundaryId === b.id}
                  onChange={() => setBoundaryId(b.id)}
                  className="peer sr-only"
                  data-testid={`boundary-option-${b.id}`}
                />
                <span
                  className={`block cursor-pointer border px-2.5 py-1 text-[12px] font-semibold peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-secondary ${
                    boundaryId === b.id
                      ? "border-hairline-strong bg-surface-raised text-primary"
                      : "border-hairline bg-surface text-secondary hover:text-primary"
                  }`}
                >
                  {b.title}
                </span>
              </label>
            ))}
          </fieldset>
          <ShowAllToggle
            pressed={showAllBoundaries}
            onToggle={() => setShowAllBoundaries((v) => !v)}
            offLabel="Show all five boundaries"
            onLabel="Back to the selected boundary"
            testId="show-all-boundaries"
          />
          {(showAllBoundaries ? BOUNDARIES : BOUNDARIES.filter((b) => b.id === boundaryId)).map((b) => (
            <div key={b.id} data-testid={`boundary-${b.id}`} className="flex flex-col gap-2">
              <h4 className="text-[13px] font-semibold text-primary">{b.title}</h4>
              <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
                {ARCHITECTURE_ORDER.map((arch) => {
                  const item = INTERFACES[arch][b.id];
                  return (
                    <article key={arch} className="flex flex-col gap-1.5 border border-hairline bg-surface px-3 py-2.5">
                      <h5 className="text-[12px] font-semibold text-secondary">{ARCHITECTURE_CHOICE_NAMES[arch]}</h5>
                      <p className="font-mono text-meta text-secondary">
                        {nodeLabel(item.nodeIds[0])} &rarr; {nodeLabel(item.nodeIds[1])}
                      </p>
                      <Field label="What crosses" body={item.crosses} />
                      <Field label="Concern" body={item.concern} />
                      <EvidenceTag glyph evidence={item.evidence} basis={item.basis} refs={item.refs} />
                    </article>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section id="step-validation" className="flex flex-col gap-3 border-t border-hairline pt-4" aria-labelledby="h-validation">
        <StepHeading id="h-validation" n={4} title="Define validation needs" question="What would have to be shown before relying on it?" />
        <p className="max-w-3xl text-body text-secondary">
          What would have to be shown, and by what kind of evidence, before relying on each
          architecture. Validation needs are defined per architecture, not per driver. Not a
          complete plan for any facility.
        </p>
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
          {ARCHITECTURE_ORDER.map((arch) => (
            <article key={arch} data-testid={`validation-${arch}`} className="flex flex-col gap-2 border border-hairline bg-surface px-3 py-2.5">
              <h3 className="text-[12px] font-semibold text-secondary">{ARCHITECTURE_CHOICE_NAMES[arch]}</h3>
              <ul className="flex flex-col gap-2">
                {VALIDATION_NEEDS[arch].map((v) => (
                  <li key={v.verifies} className="flex flex-col gap-0.5 text-[13px] leading-relaxed text-secondary">
                    <span>{v.verifies}</span>
                    <span className="font-mono text-meta uppercase text-secondary">Evidence: {v.kinds.join(" + ")}</span>
                  </li>
                ))}
              </ul>
              <EvidenceTag glyph evidence={VALIDATION_SECTION_EVIDENCE.evidence} basis={VALIDATION_SECTION_EVIDENCE.basis} />
            </article>
          ))}
        </div>
      </section>

      <section id="references" className="flex flex-col gap-2 border-t border-hairline pt-4" aria-labelledby="h-references">
        <h2 id="h-references" data-stage-heading tabIndex={-1} className="text-heading text-primary">
          References
        </h2>
        <p className="max-w-3xl text-[12px] leading-relaxed text-secondary">
          Each reference states what was actually inspected in the 2026-10-18 source audit. Textbook
          and standard references that were not opened are background for general principles and are
          not verified against their text. Vendor and consortium statements are attributed, not
          endorsed.
        </p>
        <ul className="flex flex-col gap-1.5">
          {Object.values(REFERENCES).map((r) => (
            <li key={r.id} className="text-[12px] leading-relaxed text-secondary">
              <span className="font-mono text-[11px] text-primary">{r.id}</span>{" "}
              <span className="font-mono text-meta uppercase">[{SOURCE_KIND_TEXT[r.kind]}]</span> &mdash;{" "}
              {r.url ? (
                <a href={r.url} className={link} rel="noreferrer">
                  {r.citation}
                </a>
              ) : (
                r.citation
              )}
              {r.verifiedDate ? ` (recorded in industry data, verified ${r.verifiedDate})` : ""}
              <span className="block text-[12px]">Inspection: {r.inspection}</span>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}

function StepHeading({ id, n, title, question }: { id: string; n: number; title: string; question: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <h2 id={id} data-stage-heading tabIndex={-1} className="text-heading text-primary focus:outline-none">
        <span className="mr-2 font-mono text-meta text-secondary">{n}</span>
        {title}
      </h2>
      <p className="text-[13px] text-secondary">{question}</p>
    </div>
  );
}

function DriverChooser({ selected, onSelect }: { selected: DriverId; onSelect: (id: DriverId) => void }) {
  return (
    <fieldset className="flex flex-wrap gap-1.5">
      <legend className="sr-only">Which requirement driver to examine</legend>
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
              onChange={() => onSelect(d.id)}
              className="peer sr-only"
            />
            <span
              className={`block cursor-pointer border px-2.5 py-1 text-[12px] font-semibold peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-secondary ${
                isSelected
                  ? "border-hairline-strong bg-surface-raised text-primary"
                  : "border-hairline bg-surface text-secondary hover:text-primary"
              }`}
            >
              {d.title}
            </span>
          </label>
        );
      })}
    </fieldset>
  );
}

function ShowAllToggle({
  pressed,
  onToggle,
  offLabel,
  onLabel,
  testId,
}: {
  pressed: boolean;
  onToggle: () => void;
  offLabel: string;
  onLabel: string;
  testId: string;
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onToggle}
      data-testid={testId}
      className="self-start border border-hairline bg-surface px-2.5 py-1 font-mono text-meta uppercase text-secondary hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary"
    >
      {pressed ? onLabel : offLabel}
    </button>
  );
}

function DriverCard({ driver: d }: { driver: Driver }) {
  return (
    <article data-testid={`driver-${d.id}`} className="flex flex-col gap-1.5 border border-hairline bg-surface px-3 py-3">
      <h3 className="text-[14px] font-semibold text-primary">{d.title}</h3>
      <p className="text-[13px] italic leading-snug text-secondary">{d.question}</p>
      <div className="flex flex-col gap-1.5">
        <Field label="What it is" body={d.what} />
        <Field label="Why it matters" body={d.why} />
        <Field label="System connection" body={d.system} />
        <Field label="Constraints and trade-offs" body={d.tradeoffs} />
        <Field label="Decision it informs" body={d.decision} />
      </div>
    </article>
  );
}

function CompareBlock({ driver: d }: { driver: Driver }) {
  return (
    <div data-testid={`compare-${d.id}`} className="flex flex-col gap-2">
      <h3 className="text-[14px] font-semibold text-primary">{d.title}</h3>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        {ARCHITECTURE_ORDER.map((arch) => {
          const cell = CELLS[d.id][arch];
          return (
            <article key={arch} className="flex flex-col gap-1.5 border border-hairline bg-surface px-3 py-2.5">
              <h4 className="text-[12px] font-semibold text-secondary">{ARCHITECTURE_CHOICE_NAMES[arch]}</h4>
              <Field label="How it is addressed" body={cell.how} />
              <Field label="What it makes harder" body={cell.harder} />
              <EvidenceTag glyph evidence={cell.evidence} basis={cell.basis} refs={cell.refs} />
              {cell.evidence === "model-output" && (
                <Link href="/sandbox" className={`self-start font-mono text-meta uppercase text-secondary ${link}`}>
                  Open the Advanced Sandbox
                </Link>
              )}
            </article>
          );
        })}
      </div>
    </div>
  );
}

function DecisionCard({ driver }: { driver: Driver }) {
  const decision = CONDITIONAL_DECISIONS[driver.id];
  return (
    <div
      data-testid={`decision-card-${driver.id}`}
      className="flex max-w-3xl flex-col gap-2 border border-hairline bg-surface-raised px-3 py-3"
    >
      <p className="font-mono text-meta uppercase text-secondary">If &ldquo;{driver.title}&rdquo; dominates</p>
      <Field label="Tends to favor" body={decision.favored.map((id) => ARCHITECTURE_CHOICE_NAMES[id]).join(" · ")} />
      <Field label="Because" body={decision.because} />
      <div className="flex flex-col gap-0.5">
        <span className="text-[12px] font-semibold text-secondary">Unless</span>
        <ul className="flex flex-col gap-1">
          {decision.unless.map((u) => (
            <li key={u} className="flex gap-1.5 text-[13px] leading-relaxed text-secondary">
              <span aria-hidden="true" className="text-secondary">&middot;</span>
              <span>{u}</span>
            </li>
          ))}
        </ul>
      </div>
      <Field label="How it connects" body={decision.connects} />
      <Field label="Decision it informs" body={decision.informs} />
      <EvidenceTag glyph evidence={decision.evidence} basis={decision.basis} refs={decision.refs} />
    </div>
  );
}

function Field({ label, body }: { label: string; body: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[12px] font-semibold text-secondary">{label}</span>
      <p className="text-[13px] leading-relaxed text-secondary">{body}</p>
    </div>
  );
}
