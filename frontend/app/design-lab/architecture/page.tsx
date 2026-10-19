"use client";

import { useState } from "react";

import { useArch } from "../ArchContext";

import {
  ARCHITECTURE_CHOICE_NAMES,
  ARCHITECTURE_ORDER,
  CELLS,
  CONDITIONAL_DECISIONS,
  DISCLOSURES,
  DRIVERS,
  REFERENCES,
  SOURCE_KIND_TEXT,
  type DriverId,
  type ReferenceId,
} from "../../lib/architectureChoicesData";
import Link from "next/link";

import { AreaHeader, BasisBar, EvidenceChip, EvidenceLegend } from "../ui";

/** Basis text and reference links stay attached to every evidence-labelled statement. */
function BasisLine({ basis, refs }: { basis: string; refs?: readonly ReferenceId[] }) {
  return (
    <p className="lab-section-sub" style={{ fontSize: 12, marginTop: 8 }}>
      <b style={{ fontWeight: 600 }}>Basis.</b> {basis}
      {refs && refs.length > 0 && (
        <>
          {" "}
          <b style={{ fontWeight: 600 }}>Refs:</b>{" "}
          {refs.map((r, i) => (
            <span key={r}>
              {i > 0 && ", "}
              <a href={`#ref-${r}`} style={{ textDecoration: "underline", textUnderlineOffset: 2 }}>{r}</a>
            </span>
          ))}
        </>
      )}
    </p>
  );
}

/**
 * Architecture Choices — interaction signature: COMPARE.
 * Requirement driver = lens. The evidence grid shows how well-supported
 * each cell is (never a score or ranking); the lens then opens the
 * three architectures side by side. Content: architectureChoicesData
 * (SPEC-011), unchanged.
 */
export default function ArchitectureLab() {
  const [driverId, setDriverId] = useState<DriverId>("rd2");
  const { arch, setArch } = useArch();
  const driver = DRIVERS.find((d) => d.id === driverId)!;
  const decision = CONDITIONAL_DECISIONS[driverId];
  const usedRefs = new Set<ReferenceId>();
  for (const a of ARCHITECTURE_ORDER) CELLS[driverId][a].refs?.forEach((r) => usedRefs.add(r));
  decision.refs?.forEach((r) => usedRefs.add(r));

  return (
    <>
      <AreaHeader
        area="02 · Architecture Choices"
        mode="Compare"
        question="Which architecture fits which requirement?"
        answer="Choose a requirement driver and read the three architectures against it. The answer is conditional on which driver dominates for a site. Nothing here ranks or scores."
      />
      <div className="lab-wrap">
        <BasisBar
          notes={[
            { tag: "SST optional", text: DISCLOSURES.sst },
            { tag: "Blocks", text: DISCLOSURES.block },
            { tag: "Simulation scope", text: DISCLOSURES.sim },
            { tag: "Drivers", text: DISCLOSURES.illustrative },
            { tag: "No ranking", text: DISCLOSURES.noWinner },
          ]}
          labels={<EvidenceLegend />}
        />
      </div>

      <section className="lab-wrap lab-section lab-first">
        <div className="lab-split r57">
          <div>
            <div className="lab-section-head" style={{ marginBottom: 10 }}>
              <div>
                <h2 className="lab-h2">Evidence by driver</h2>
                <p className="lab-section-sub">How well supported each statement is. Select a row to open it.</p>
              </div>
            </div>
            <div className="lab-panel" style={{ padding: 0, overflowX: "auto" }} tabIndex={0} role="region" aria-label="Evidence by driver table (scrolls sideways on narrow screens)">
              <table className="lab-matrix">
                <thead>
                  <tr>
                    <th>Requirement driver</th>
                    {ARCHITECTURE_ORDER.map((a) => (
                      <th key={a}>{a === "conventional-ac" ? "AC" : a === "ac-to-800vdc" ? "AC-fed 800 VDC" : "SST"}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {DRIVERS.map((d) => (
                    <tr key={d.id} data-on={d.id === driverId}>
                      <td className="row">
                        <button aria-pressed={d.id === driverId} onClick={() => setDriverId(d.id)}>
                          {d.title}
                        </button>
                      </td>
                      {ARCHITECTURE_ORDER.map((a) => (
                        <td key={a} className="cell">
                          <EvidenceChip kind={CELLS[d.id][a].evidence} short />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="lab-scrollhint">Scroll the table sideways for all columns.</p>
          </div>

          <div>
            <div className="lab-section-head" style={{ marginBottom: 10 }}>
              <div>
                <h2 className="lab-h2">{driver.title}</h2>
                <p className="lab-section-sub">{driver.question}</p>
              </div>
            </div>
            <div className="lab-panel inset" style={{ marginBottom: 12 }}>
              <p className="lab-label">What it is</p>
              <p className="lab-body" style={{ marginBottom: 6 }}>{driver.what}</p>
              <p className="lab-label">Why it matters</p>
              <p className="lab-body" style={{ marginBottom: 6 }}>{driver.why}</p>
              <p className="lab-label">System connection</p>
              <p className="lab-body" style={{ marginBottom: 6 }}>{driver.system}</p>
              <p className="lab-label">Trade-off</p>
              <p className="lab-body" style={{ marginBottom: 0 }}>{driver.tradeoffs}</p>
            </div>
          </div>
        </div>
      </section>

      <section className="lab-wrap lab-section">
        <div className="lab-section-head">
          <div>
            <h2 className="lab-h2">Side by side · {driver.title.toLowerCase()}</h2>
            <p className="lab-section-sub">Each column keeps its own evidence label: the label of its weakest claim.</p>
          </div>
        </div>
        <div className="lab-grid lab-g3">
          {ARCHITECTURE_ORDER.map((a) => {
            const c = CELLS[driverId][a];
            return (
              <article key={a} className="lab-col" data-on={a === arch}>
                <header>
                  <button className="lab-link-btn" aria-pressed={a === arch} onClick={() => setArch(a)} title="Show this architecture's path in the rail">
                    <h3 className="lab-h3" style={{ fontSize: 14, margin: 0 }}>{ARCHITECTURE_CHOICE_NAMES[a]}</h3>
                  </button>
                  <EvidenceChip kind={c.evidence} short />
                </header>
                <div>
                  <p className="lab-label">How it addresses this driver</p>
                  <p className="lab-body" style={{ marginBottom: 0 }}>{c.how}</p>
                </div>
                <div>
                  <p className="lab-label">What gets harder</p>
                  <p className="lab-body" style={{ marginBottom: 0 }}>{c.harder}</p>
                </div>
                <BasisLine basis={c.basis} refs={c.refs} />
                {c.evidence === "model-output" && (
                  <p style={{ margin: 0 }}>
                    <Link className="lab-btn" href="/design-lab/sandbox">Open the Sandbox slice</Link>
                  </p>
                )}
              </article>
            );
          })}
        </div>
      </section>

      <section className="lab-wrap lab-section">
        <div className="lab-section-head">
          <div>
            <h2 className="lab-h2">If {driver.title.toLowerCase()} dominates</h2>
            <p className="lab-section-sub">A conditional reading, not a verdict.</p>
          </div>
          <EvidenceChip kind={decision.evidence} />
        </div>
        <div className="lab-grid lab-g2">
          <blockquote className="lab-quote">
            <p className="lab-label">Favored when this driver dominates</p>
            <p style={{ margin: "0 0 10px", fontWeight: 600 }}>
              {decision.favored.map((f) => ARCHITECTURE_CHOICE_NAMES[f]).join(" · ")}
            </p>
            <p className="lab-body" style={{ marginBottom: 0 }}>{decision.because}</p>
          </blockquote>
          <div>
            <p className="lab-label">Unless</p>
            <ul className="lab-body" style={{ paddingLeft: 18, margin: "0 0 10px" }}>
              {decision.unless.map((u) => (
                <li key={u}>{u}</li>
              ))}
            </ul>
            <p className="lab-label">Decision it informs</p>
            <p className="lab-body" style={{ marginBottom: 0 }}>{decision.informs}</p>
            <BasisLine basis={decision.basis} refs={decision.refs} />
          </div>
        </div>
        <p className="lab-section-sub" style={{ marginTop: 14 }}>
          <b style={{ fontWeight: 600 }}>Driver decision.</b> {driver.decision}
        </p>
      </section>

      <section className="lab-wrap lab-section">
        <div className="lab-section-head">
          <div>
            <h2 className="lab-h2">References for this driver</h2>
            <p className="lab-section-sub">
              Interfaces by boundary, validation needs by architecture and the full reference list are not part of this demonstration; production keeps all of them.
            </p>
          </div>
        </div>
        <ul style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 8 }}>
          {[...usedRefs].map((id) => {
            const r = REFERENCES[id];
            return (
              <li key={id} id={`ref-${id}`} className="lab-body" style={{ marginBottom: 0 }}>
                <b style={{ color: "var(--color-text-primary)", fontWeight: 600 }}>{id}</b> [{SOURCE_KIND_TEXT[r.kind]}] {r.citation}.{" "}
                {r.url && (
                  <a href={r.url} target="_blank" rel="noreferrer" style={{ textDecoration: "underline", textUnderlineOffset: 2 }}>Source</a>
                )}{" "}
                <span style={{ fontSize: 12 }}>Inspection: {r.inspection}</span>
              </li>
            );
          })}
        </ul>
      </section>
    </>
  );
}
