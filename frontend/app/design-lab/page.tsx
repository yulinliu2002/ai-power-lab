import Link from "next/link";

import { BasisBar, EvidenceLegend } from "./ui";

/**
 * Direction overview: the rationale, the one recommended direction, the
 * shared tokens, and how it applies across all five areas.
 */
const AREAS = [
  { n: "01", name: "System Map", mode: "Inspect", href: "/design-lab/system-map", pattern: "Structure first. A spatial path with an inspector; select a stage, read it.", question: "Where does the power go?" },
  { n: "02", name: "Architecture Choices", mode: "Compare", href: "/design-lab/architecture", pattern: "Requirement driver as lens. Evidence grid, then three architectures side by side.", question: "Which architecture fits which requirement?" },
  { n: "03", name: "Learn by Example", mode: "Predict", href: "/design-lab/learn", pattern: "One case, one step at a time: Predict, Discover, Explain, Apply.", question: "Why does it behave this way?" },
  { n: "04", name: "Industry & Career", mode: "Trace", href: "/design-lab/industry", pattern: "Claim to source to strength to limits; competencies link back into the product.", question: "Who says so, and how strong is it?" },
  { n: "—", name: "Advanced Sandbox", mode: "Experiment", href: "/design-lab/sandbox", pattern: "Workbench: parameter rail left, instruments right. A tool, not a destination.", question: "What if I change this?" },
] as const;

const TOKENS = [
  ["canvas", "#0a0e14"], ["surface", "#121820"], ["surface-raised", "#1a232e"], ["inset", "#0d131a"],
  ["hairline", "#24303c"], ["accent", "#3987e5"], ["good", "#0ca30c"], ["warning", "#fab219"], ["critical", "#d03b3b"],
] as const;

export default function Direction() {
  return (
    <>
      <div className="lab-wrap lab-head" style={{ paddingTop: 56 }}>
        <div className="lab-mode"><b>Direction</b> Signal Path</div>
        <h1 className="lab-h1">Every page follows the power.</h1>
        <p className="lab-lede">
          One identity for five areas: an editorial question at the top, an instrument underneath, and the grid-to-rack signal path as the thread that
          shows where you are in the chain. Each area keeps its own way of interacting.
        </p>
      </div>

      <section className="lab-wrap lab-section">
        <div className="lab-section-head">
          <h2 className="lab-h2">Five areas, one language, five interaction verbs</h2>
        </div>
        <div className="lab-panel" style={{ padding: 0, overflowX: "auto" }}>
          <table className="lab-table" style={{ minWidth: 720 }}>
            <thead>
              <tr><th style={{ paddingLeft: 16 }}>Area</th><th>Verb</th><th>Page opens with</th><th>Interaction pattern</th></tr>
            </thead>
            <tbody>
              {AREAS.map((a) => (
                <tr key={a.name}>
                  <td style={{ paddingLeft: 16 }}><Link href={a.href} style={{ textDecoration: "underline", textUnderlineOffset: 3 }}>{a.n} {a.name}</Link></td>
                  <td><span className="lab-chip">{a.mode}</span></td>
                  <td>{a.question}</td>
                  <td>{a.pattern}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="lab-wrap lab-section">
        <div className="lab-section-head"><h2 className="lab-h2">The shared system</h2></div>
        <div className="lab-grid lab-g3">
          <div className="lab-panel">
            <h3 className="lab-h3">1 · The signal path</h3>
            <p className="lab-body" style={{ marginBottom: 0 }}>The strip under the nav draws the selected architecture&apos;s own main path, never one universal chain. Each area highlights the span it works on with surface tier and weight. Pages that run the model pin it to the conceptual SST architecture and mark the simulated slice.</p>
          </div>
          <div className="lab-panel">
            <h3 className="lab-h3">2 · Question, then instrument</h3>
            <p className="lab-body" style={{ marginBottom: 0 }}>Every page leads with one engineering question and a one-sentence answer, followed immediately by the instrument. Mandatory caveats stay visible on load, verbatim, in one structured Basis &amp; limits panel.</p>
          </div>
          <div className="lab-panel">
            <h3 className="lab-h3">3 · Quiet type, loud structure</h3>
            <p className="lab-body" style={{ marginBottom: 0 }}>IBM Plex Sans in sentence case replaces the uppercase mono wall. Mono is kept for numbers, tags and equations. Hierarchy comes from scale and weight (never above 600 here).</p>
          </div>
        </div>
        <div className="lab-grid lab-g2" style={{ marginTop: 16 }}>
          <div className="lab-panel inset">
            <h3 className="lab-h3" style={{ marginBottom: 12 }}>Tokens (unchanged from DESIGN.md)</h3>
            <div className="lab-grid lab-g3" style={{ gap: 10 }}>
              {TOKENS.map(([n, v]) => (
                <div key={n} className="lab-swatch"><i style={{ background: v }} /><span><b style={{ fontWeight: 600 }}>{n}</b><br /><span className="lab-mono" style={{ color: "var(--color-text-secondary)", fontSize: 11 }}>{v}</span></span></div>
              ))}
            </div>
          </div>
          <div className="lab-panel inset">
            <h3 className="lab-h3" style={{ marginBottom: 12 }}>Type scale</h3>
            <div style={{ display: "grid", gap: 8 }}>
              <div style={{ fontSize: 40, lineHeight: 1.08, letterSpacing: "-0.022em", fontWeight: 600 }}>Display 40 / 600</div>
              <div style={{ fontSize: 18, fontWeight: 600 }}>Section 18 / 600</div>
              <div style={{ fontSize: 14, color: "var(--color-text-secondary)" }}>Body 14 / 400 · secondary</div>
              <div style={{ fontSize: 12, fontWeight: 500, color: "var(--color-text-secondary)" }}>Label 12 / 500</div>
              <div className="lab-mono" style={{ fontSize: 22, fontWeight: 600 }}>812.4<span className="lab-unit">V</span> <span style={{ fontSize: 12, fontWeight: 400, color: "var(--color-text-secondary)" }}>Mono 22 / 600, tabular</span></div>
            </div>
          </div>
        </div>
        <div style={{ marginTop: 16 }}>
          <h3 className="lab-h3" style={{ marginBottom: 8 }}>Evidence labels: neutral, glyph plus text</h3>
          <EvidenceLegend />
          <p className="lab-section-sub" style={{ marginTop: 8 }}>Evidence is not health, so it never borrows a status color. Status colors stay reserved for engineering state.</p>
        </div>
      </section>

      <section className="lab-wrap lab-section">
        <BasisBar
          notes={[
            { tag: "Provenance", text: "Content in the five area pages reuses existing repository data; Learn and Sandbox read live model runs from the existing API." },
            { tag: "Status", text: "Design demonstration only, not feature-parity replacements. No engine, API or numeric changes." },
          ]}
        />
      </section>
    </>
  );
}
