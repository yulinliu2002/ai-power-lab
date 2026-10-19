"use client";

import { useState } from "react";

import { useArch } from "../ArchContext";

import { ARCHITECTURES, CATEGORIES, LANE_META, type Lane } from "../../lib/infrastructureMapData";
import { AreaHeader, BasisBar } from "../ui";

/**
 * System Map — interaction signature: INSPECT.
 * Structure first (the path), detail on demand (the inspector). Reuses
 * infrastructureMapData unchanged; nothing here is a live reading.
 */
const LANES: Lane[] = ["backup", "cooling", "monitoring"];

export default function SystemMapLab() {
  const { arch: archId, setArch: setArchId } = useArch();
  const arch = ARCHITECTURES.find((a) => a.id === archId)!;
  const main = arch.nodes.filter((n) => n.lane === "main");
  const [selId, setSelId] = useState<string | null>(null);
  const sel = arch.nodes.find((n) => n.id === selId) ?? main[Math.min(2, main.length - 1)];
  const cat = CATEGORIES[sel.categoryId];

  return (
    <>
      <AreaHeader
        area="01 · System Map"
        mode="Inspect"
        question="Where does the power go between the grid and the GPU?"
        answer="Trace one representative power path stage by stage. Pick a stage to see what it does, why it exists, and how this architecture implements it."
      />
      <div className="lab-wrap" style={{ paddingBottom: 8 }}>
        <BasisBar
          notes={[
            { tag: "Not universal", text: "Each view is one representative, simplified pattern. Real facilities vary in redundancy, UPS topology and distribution voltage. An SST is one candidate for the MV-to-DC stage, not a requirement." },
            { tag: "Conceptual", text: "This map is reference content. It is not a live reading and no value on it comes from the simulation." },
          ]}
        />
      </div>

      <section className="lab-wrap lab-section lab-first">
        <div className="lab-section-head">
          <div>
            <h2 className="lab-h2">{arch.name}</h2>
            <p className="lab-section-sub" style={{ maxWidth: "70ch" }}>{arch.tagline}</p>
          </div>
          <div className="lab-seg" role="group" aria-label="Architecture view">
            {ARCHITECTURES.map((a) => (
              <button key={a.id} aria-pressed={a.id === archId} onClick={() => { setArchId(a.id); setSelId(null); }}>
                {a.id === "conventional-ac" ? "Conventional AC" : a.id === "ac-to-800vdc" ? "AC-fed 800 VDC" : "MV-to-800 VDC via SST"}
              </button>
            ))}
          </div>
        </div>

        <p className="lab-label">{LANE_META.main.label}</p>
        <div className="lab-path">
          {main.map((n, i) => (
            <button key={n.id} className="lab-node" aria-pressed={n.id === sel.id} onClick={() => setSelId(n.id)}>
              <span className="n">{String(i + 1).padStart(2, "0")}</span>
              <span className="t">{n.label}</span>
              <span className="d">{n.detail}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="lab-wrap lab-section">
        <div className="lab-split">
          <div style={{ display: "grid", gap: 20 }}>
            {LANES.map((lane) => {
              const nodes = arch.nodes.filter((n) => n.lane === lane);
              if (!nodes.length) return null;
              return (
                <div key={lane}>
                  <p className="lab-label">{LANE_META[lane].label}</p>
                  <div className="lab-lane">
                    {nodes.map((n) => (
                      <button key={n.id} className="lab-node" aria-pressed={n.id === sel.id} onClick={() => setSelId(n.id)}>
                        <span className="t">{n.label}</span>
                        <span className="d">{n.detail}</span>
                      </button>
                    ))}
                  </div>
                  <p className="lab-section-sub" style={{ fontSize: 12, marginTop: 6 }}>{LANE_META[lane].description}</p>
                </div>
              );
            })}
          </div>

          <article className="lab-panel raised" aria-live="polite">
            <p className="lab-label" style={{ marginBottom: 2 }}>Stage inspector · {LANE_META[sel.lane].label}</p>
            <h2 className="lab-h2" style={{ fontSize: 22 }}>{cat.title}</h2>
            <p className="lab-body" style={{ color: "var(--color-text-primary)", marginTop: 8 }}>
              <strong style={{ fontWeight: 600 }}>In this architecture. </strong>
              {sel.instantiation}
            </p>
            <div className="lab-grid lab-g2" style={{ marginTop: 14 }}>
              <div>
                <p className="lab-label">What it is</p>
                <p className="lab-body">{cat.what}</p>
                <p className="lab-label">Why it exists</p>
                <p className="lab-body">{cat.why}</p>
              </div>
              <div>
                <p className="lab-label">Design considerations</p>
                <ul className="lab-body" style={{ paddingLeft: 18, margin: "0 0 10px" }}>
                  {cat.considerations.slice(0, 2).map((c) => (
                    <li key={c}>{c}</li>
                  ))}
                </ul>
                <p className="lab-label">Alternatives</p>
                <ul className="lab-body" style={{ paddingLeft: 18, margin: 0 }}>
                  {cat.alternatives.slice(0, 2).map((c) => (
                    <li key={c}>{c}</li>
                  ))}
                </ul>
              </div>
            </div>
          </article>
        </div>
      </section>
    </>
  );
}
