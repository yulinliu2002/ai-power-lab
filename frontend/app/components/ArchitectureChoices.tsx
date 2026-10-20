"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

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
 * Architecture Choices as a four-step evaluation (SPEC-014 Scope B) in the
 * "instrument console" composition: a requirement list on the left, and one
 * decision board on the right where the three architectures sit in aligned
 * columns so they can be compared at a glance. Same data module and the same
 * content as SPEC-011; progressive disclosure only. A marked column is a
 * *conditional tendency* (the data's `favored` set, which can name several
 * architectures) and never a ranking, score or winner (SPEC-011 AC-8).
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
  // Below 960px the comparison reads as labeled cards (each cell names its architecture and aspect), so the
  // table roles are dropped there instead of leaving a table whose headers are hidden.
  const [narrow, setNarrow] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 960px)");
    const update = () => setNarrow(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);
  const [driverId, setDriverId] = useState<DriverId>("rd1");
  const [railArch, setRailArch] = useState<ArchitectureId>(ARCHITECTURE_ORDER[0]);
  const [boundaryId, setBoundaryId] = useState<BoundaryId>(BOUNDARIES[0].id);
  const [showAllDrivers, setShowAllDrivers] = useState(false);
  const [showAllBoundaries, setShowAllBoundaries] = useState(false);

  const nodeLabel = (id: string) =>
    ARCHITECTURES.flatMap((a) => a.nodes).find((n) => n.id === id)?.label ?? id;
  const boards: readonly Driver[] = showAllDrivers ? DRIVERS : [DRIVERS.find((d) => d.id === driverId)!];

  return (
    <main className="ic-page">
      <header className="ic-head">
        <div>
          <p className="ic-eyebrow">Evaluate alternatives against requirements</p>
          <h1 className="ic-h1">Architecture choices</h1>
          <p className="ic-lede">
            Pick a requirement. See how three architectures from the{" "}
            <Link href="/system-map" className={link}>
              System Map
            </Link>{" "}
            meet it, side by side, what each makes harder, and what would have to be validated before relying on it.
          </p>
          <p className="ic-small" style={{ marginTop: 10 }}>
            Next:{" "}
            <Link href="/learn" className={`text-primary ${link}`}>
              Learn by Example: see how the system behaves under a disturbance
            </Link>
          </p>
        </div>
        <ol className="ic-small" style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 6 }}>
          <li><b style={{ color: "var(--color-text-primary)" }}>Identify</b> the requirement that matters most for a hypothetical site.</li>
          <li><b style={{ color: "var(--color-text-primary)" }}>Compare</b> the three architectures against it.</li>
          <li><b style={{ color: "var(--color-text-primary)" }}>Understand</b> the trade-off and the interfaces it creates.</li>
          <li><b style={{ color: "var(--color-text-primary)" }}>Define</b> the validation needs.</li>
        </ol>
      </header>

      <section aria-label="Basis and limits" data-testid="disclosures-panel">
        <ul className="ic-basis" data-testid="disclosures">
          {DISCLOSURE_ITEMS.map((d) => (
            <li key={d.tag}>
              <b>{d.tag}</b>
              <p>{d.text}</p>
            </li>
          ))}
        </ul>
      </section>
      <p className="ic-small" style={{ marginTop: 10, maxWidth: "75ch" }}>
        Each item carries an evidence label: <em>Public fact</em> (principle or attributed source),{" "}
        <em>Illustrative assumption</em>, <em>Model output (simplified)</em>, or <em>Emerging / uncertain</em>. An item
        carries the label of its weakest claim.
      </p>

      <section aria-label="Power path context" style={{ marginTop: 22, display: "grid", gap: 8 }}>
        <fieldset className="flex flex-wrap items-center gap-2">
          <legend className="sr-only">Architecture shown in the power path</legend>
          <span className="ic-eyebrow" style={{ margin: 0 }}>Power path for</span>
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
              <span className="ic-chipbtn peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-secondary" data-on={railArch === id}>
                {ARCHITECTURE_CHOICE_NAMES[id]}
              </span>
            </label>
          ))}
        </fieldset>
        <SignalPathRail architecture={railArch} note="Representative path, not a universal one" />
      </section>

      <StageNav label="Steps on this page" stages={STAGES} observeKey={`${driverId}-${showAllDrivers}`} />

      <div className="ic-arch">
        <section id="step-requirement" aria-labelledby="h-requirement" className="ic-reqs">
          <div className="ic-reqs-in">
          <h2 id="h-requirement" data-stage-heading tabIndex={-1} className="ic-eyebrow focus:outline-none" style={{ paddingLeft: 14 }}>
            1 · Identify the requirement
          </h2>
          <fieldset>
            <legend className="sr-only">Which requirement driver to examine</legend>
            {DRIVERS.map((d, i) => (
              <label key={d.id} className="relative block">
                <input
                  type="radio"
                  name="dominant-driver"
                  value={d.id}
                  checked={d.id === driverId}
                  data-testid={`driver-option-${d.id}`}
                  onChange={() => setDriverId(d.id)}
                  className="peer sr-only"
                />
                <span className="ic-reqbtn peer-focus-visible:outline-2 peer-focus-visible:outline-offset-[-2px] peer-focus-visible:outline-secondary" data-on={d.id === driverId}>
                  <small>RD{i + 1}</small>
                  {d.title}
                </span>
              </label>
            ))}
          </fieldset>
          <button
            type="button"
            aria-pressed={showAllDrivers}
            onClick={() => setShowAllDrivers((v) => !v)}
            data-testid="show-all-drivers"
            className="ic-ghost"
            style={{ marginTop: 14 }}
          >
            {showAllDrivers ? "Back to the selected driver" : "Show all seven drivers, comparisons and decisions"}
          </button>
          </div>
        </section>

        <div className="ic-boards">
          {boards.map((d, bi) => (
            <Board key={d.id} driver={d} first={bi === 0} narrow={narrow} />
          ))}
        </div>
      </div>

      <hr className="ic-rule" />
      <section aria-label="Interfaces" className="flex flex-col gap-3">
        <h2 className="ic-h2"><b>Interfaces</b> where a choice becomes a specification · the same for every requirement</h2>
        <p className="ic-body" style={{ maxWidth: "75ch" }}>
          The five boundaries where a choice becomes a specification. Node names are the System Map&rsquo;s. {DISCLOSURES.block}
        </p>
        <fieldset className="ic-seg">
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
              <span className="ic-segbtn peer-focus-visible:outline-2 peer-focus-visible:outline-offset-[-2px] peer-focus-visible:outline-secondary" data-on={boundaryId === b.id}>
                {b.title}
              </span>
            </label>
          ))}
        </fieldset>
        <button
          type="button"
          aria-pressed={showAllBoundaries}
          onClick={() => setShowAllBoundaries((v) => !v)}
          data-testid="show-all-boundaries"
          className="ic-ghost"
          style={{ width: "auto", alignSelf: "flex-start" }}
        >
          {showAllBoundaries ? "Back to the selected boundary" : "Show all five boundaries"}
        </button>
        {(showAllBoundaries ? BOUNDARIES : BOUNDARIES.filter((b) => b.id === boundaryId)).map((b) => (
          <div key={b.id} data-testid={`boundary-${b.id}`} className="flex flex-col gap-2">
            <h3 className="ic-h3">{b.title}</h3>
            <div className="ic-three">
              {ARCHITECTURE_ORDER.map((arch) => {
                const item = INTERFACES[arch][b.id];
                return (
                  <article key={arch}>
                    <h4 className="ic-h4">{ARCHITECTURE_CHOICE_NAMES[arch]}</h4>
                    <p className="ic-small" style={{ marginBottom: 10, color: "var(--color-text-primary)" }}>
                      {nodeLabel(item.nodeIds[0])} &rarr; {nodeLabel(item.nodeIds[1])}
                    </p>
                    <Field label="What crosses" body={item.crosses} />
                    <Field label="Concern" body={item.concern} />
                    <Link href="/system-map" className={`ic-small ${link}`}>
                      See these nodes on the System Map
                    </Link>
                    <EvidenceTag glyph evidence={item.evidence} basis={item.basis} refs={item.refs} />
                  </article>
                );
              })}
            </div>
          </div>
        ))}
      </section>

      <hr className="ic-rule" />
      <section id="step-validation" aria-labelledby="h-validation" className="flex flex-col gap-3">
        <h2 id="h-validation" data-stage-heading tabIndex={-1} className="ic-h2 focus:outline-none">
          <b>4 · Define validation needs</b> what would have to be shown before relying on it
        </h2>
        <p className="ic-body" style={{ maxWidth: "75ch" }}>
          What would have to be shown, and by what kind of evidence, before relying on each architecture. Validation
          needs are defined per architecture, not per driver. Not a complete plan for any facility.
        </p>
        <div className="ic-three">
          {ARCHITECTURE_ORDER.map((arch) => (
            <article key={arch} data-testid={`validation-${arch}`}>
              <h3 className="ic-h3">{ARCHITECTURE_CHOICE_NAMES[arch]}</h3>
              <ul className="flex flex-col gap-3">
                {VALIDATION_NEEDS[arch].map((v) => (
                  <li key={v.verifies} className="flex flex-col gap-1">
                    <span className="ic-body" style={{ color: "var(--color-text-primary)" }}>{v.verifies}</span>
                    <span className="ic-kinds">
                      Evidence: {v.kinds.join(" + ")}
                    </span>
                  </li>
                ))}
              </ul>
              <EvidenceTag glyph evidence={VALIDATION_SECTION_EVIDENCE.evidence} basis={VALIDATION_SECTION_EVIDENCE.basis} />
            </article>
          ))}
        </div>
      </section>

      <hr className="ic-rule" />
      <section id="references" aria-labelledby="h-references" className="flex flex-col gap-2">
        <h2 id="h-references" data-stage-heading tabIndex={-1} className="ic-h2 focus:outline-none">
          <b>References</b>
        </h2>
        <p className="ic-small" style={{ maxWidth: "75ch" }}>
          Each reference states what was actually inspected in the 2026-10-18 source audit. Textbook and standard
          references that were not opened are background for general principles and are not verified against their text.
          Vendor and consortium statements are attributed, not endorsed.
        </p>
        <ul className="ic-refs">
          {Object.values(REFERENCES).map((r) => (
            <li key={r.id}>
              <b style={{ color: "var(--color-text-primary)" }}>{r.id}</b>{" "}
              <span className="ic-mono" style={{ fontSize: 11 }}>[{SOURCE_KIND_TEXT[r.kind]}]</span> &mdash;{" "}
              {r.url ? (
                <a href={r.url} className={link} rel="noreferrer">
                  {r.citation}
                </a>
              ) : (
                r.citation
              )}
              {r.verifiedDate ? ` (recorded in industry data, verified ${r.verifiedDate})` : ""}
              <span className="block">Inspection: {r.inspection}</span>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}

/** One decision board: the selected (or every) driver, with the three architectures in aligned columns. */
function Board({ driver: d, first, narrow }: { driver: Driver; first: boolean; narrow: boolean }) {
  const decision = CONDITIONAL_DECISIONS[d.id];
  const role = (r: string) => (narrow ? undefined : r);
  return (
    <div className="ic-board">
      <div id={first ? "step-compare" : undefined} className="ic-board-head">
        <h2 {...(first ? { id: "h-compare", "data-stage-heading": true, tabIndex: -1 } : {})} className="ic-eyebrow focus:outline-none" style={{ margin: 0 }}>
          2 · Compare architectures
        </h2>
        <p className="ic-q">{d.question}</p>
        <p className="ic-small">
          {d.title}. Qualitative only: &ldquo;harder&rdquo; is what an architecture makes more difficult for this
          requirement, not a score. {DISCLOSURES.sst}
        </p>
        <article data-testid={`driver-${d.id}`} className="ic-driverfields">
          <h3 className="sr-only">{d.title}</h3>
          <Field label="What it is" body={d.what} />
          <Field label="Why it matters" body={d.why} />
          <Field label="System connection" body={d.system} />
          <Field label="Constraints and trade-offs" body={d.tradeoffs} />
          <Field label="Decision it informs" body={d.decision} />
        </article>
      </div>

      <div data-testid={`compare-${d.id}`} className="ic-cols" role={role("table")} aria-label={narrow ? undefined : `${d.title}: the three architectures compared`}>
        <p className="ic-legend">
          Columns marked <b>Tends to favor</b> are a <b>conditional tendency</b> if this requirement dominates for a
          site, with the exceptions below. They are not a ranking, a score or a winner.
        </p>
        <div className="ic-row" role={role("row")}>
        <div role={role("columnheader")} aria-label={narrow ? undefined : "Aspect"} />
        {ARCHITECTURE_ORDER.map((arch) => {
          const fav = decision.favored.includes(arch);
          return (
            <div key={arch} className="ic-colhead" data-fav={fav} role={role("columnheader")}>
              {fav ? (
                <span className="ic-favor">
                  Tends to favor<span className="sr-only"> if this requirement dominates; a conditional tendency, not a ranking or a winner</span>
                </span>
              ) : (
                <span className="ic-favor-none" aria-hidden="true">&nbsp;</span>
              )}
              <h3>{ARCHITECTURE_CHOICE_NAMES[arch]}</h3>
            </div>
          );
        })}
        </div>

        <div className="ic-row" role={role("row")}>
        <div className="ic-rowlabel" role={role("rowheader")}>How it is addressed</div>
        {ARCHITECTURE_ORDER.map((arch) => (
          <div key={arch} className="ic-cell" role={role("cell")}>
            {decision.favored.includes(arch) && (
              <span className="ic-favor ic-mfavor">Tends to favor · conditional<span className="sr-only"> if this requirement dominates; not a ranking or a winner</span></span>
            )}
            <span className="ic-mlabel">{ARCHITECTURE_CHOICE_NAMES[arch]} · how it is addressed</span>
            {CELLS[d.id][arch].how}
          </div>
        ))}
        </div>

        <div className="ic-row" role={role("row")}>
        <div className="ic-rowlabel" role={role("rowheader")}>What it makes harder</div>
        {ARCHITECTURE_ORDER.map((arch) => (
          <div key={arch} className="ic-cell" data-kind="harder" role={role("cell")}>
            <span className="ic-mlabel">{ARCHITECTURE_CHOICE_NAMES[arch]} · what it makes harder</span>
            {CELLS[d.id][arch].harder}
          </div>
        ))}
        </div>

        <div className="ic-row" role={role("row")}>
        <div className="ic-rowlabel" role={role("rowheader")}>Evidence</div>
        {ARCHITECTURE_ORDER.map((arch) => {
          const c = CELLS[d.id][arch];
          return (
            <div key={arch} className="ic-cell" data-kind="evidence" role={role("cell")}>
              <span className="ic-evlabel">{ARCHITECTURE_CHOICE_NAMES[arch]} · evidence</span>
              <EvidenceTag glyph evidence={c.evidence} basis={c.basis} refs={c.refs} />
              {c.evidence === "model-output" && (
                <Link href="/sandbox" className={`ic-small ${link}`}>
                  Open the Advanced Sandbox
                </Link>
              )}
            </div>
          );
        })}
        </div>
      </div>

      <div id={first ? "step-tradeoffs" : undefined} data-testid={`decision-card-${d.id}`} className="ic-decision">
        <h2 {...(first ? { id: "h-tradeoffs", "data-stage-heading": true, tabIndex: -1 } : {})} className="ic-rowlabel focus:outline-none" style={{ border: 0, padding: "4px 14px 0 0" }}>
          3 · Understand trade-offs
        </h2>
        <div>
          <h4 className="ic-h4">If &ldquo;{d.title}&rdquo; dominates, this tends to favor</h4>
          <p className="ic-q" style={{ fontSize: 22, marginBottom: 12 }}>
            {decision.favored.map((id) => ARCHITECTURE_CHOICE_NAMES[id]).join(" · ")}
          </p>
          <p className="ic-small" style={{ marginBottom: 12 }}>
            A conditional tendency with its exceptions, not a verdict. {DISCLOSURES.noWinner}
          </p>
          <Field label="Because" body={decision.because} />
          <Field label="How it connects" body={decision.connects} />
          <Field label="Decision it informs" body={decision.informs} />
        </div>
        <div>
          <h4 className="ic-h4">Unless</h4>
          <ul className="ic-unless">
            {decision.unless.map((u) => (
              <li key={u}>{u}</li>
            ))}
          </ul>
          <EvidenceTag glyph evidence={decision.evidence} basis={decision.basis} refs={decision.refs} />
        </div>
      </div>
      <p className="ic-small" style={{ padding: "0 28px 20px" }}>{DISCLOSURES.sim}</p>
    </div>
  );
}

function Field({ label, body }: { label: string; body: string }) {
  return (
    <div className="flex flex-col gap-0.5" style={{ marginBottom: 8 }}>
      <span className="ic-flabel">{label}</span>
      <p className="ic-body">{body}</p>
    </div>
  );
}
