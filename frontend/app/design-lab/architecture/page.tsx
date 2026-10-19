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
  type DriverId,
} from "../../lib/architectureChoicesData";
import { AreaHeader, BasisBar, EvidenceChip, EvidenceLegend } from "../ui";

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
            <div className="lab-panel" style={{ padding: 0, overflowX: "auto" }}>
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
          </div>
        </div>
      </section>
    </>
  );
}
