import Link from "next/link";

import { REFERENCES } from "../../lib/architectureChoicesData";
import { AreaHeader, BasisBar, EvidenceChip, EvidenceLegend, type Evidence } from "../ui";

/**
 * Industry & Career — interaction signature: TRACE.
 * Every industry statement is shown as a chain: who said it -> what kind
 * of source -> how strong -> what it does NOT show. Sources are the
 * audited REFERENCES (SPEC-011) plus the one Eaton catalog record already
 * in data/industry/. No new facts are introduced by this prototype.
 */
interface Trace {
  who: string;
  claim: string;
  kind: string;
  strength: Evidence;
  notShown: string;
  title: string;
  url: string;
  date: string;
}

const TRACES: readonly Trace[] = [
  {
    who: "NVIDIA",
    claim:
      "Describes a move from conventional AC data-center infrastructure toward an 800 VDC architecture for AI factories: an 800 VDC power rack, a row-level power center, and a future facility-scale DC power block with direct medium-voltage conversion.",
    kind: "Vendor statement",
    strength: "emerging",
    notShown: "Not a claim that NVIDIA builds or sells an SST. The facility-scale block is described as future, not deployed.",
    title: REFERENCES.NVIDIA.citation.replace(/ \(also recorded in .*\)$/, ""),
    url: REFERENCES.NVIDIA.url ?? "",
    date: "verified 2026-10-04",
  },
  {
    who: "Open Compute Project (Google, Microsoft, NVIDIA)",
    claim:
      "Is working on LVDC / 800 VDC standardization. The SST specification is a first draft (Rev 0.3.0, effective 22 June 2026) and the LVDC white paper is v1.0 (30 March 2026).",
    kind: "Consortium document",
    strength: "public-fact",
    notShown: "A draft specification is not an adopted standard. It is not a specific vendor's internal design.",
    title: REFERENCES.OCPSST.citation.replace(/ \(also recorded in .*\)$/, ""),
    url: REFERENCES.OCPSST.url ?? "",
    date: "read in the 2026-10-18 source audit",
  },
  {
    who: "Eaton",
    claim:
      "Lists a medium-voltage solid-state transformer: 15 kV class input, 2 MW overall load rating, more than 97% converter efficiency at 800 VDC output, liquid-cooled power section.",
    kind: "Vendor catalog claim",
    strength: "public-fact",
    notShown: "Efficiency is the vendor's figure, not independently measured. AI Power Lab's SST model is not calibrated to this or any product.",
    title: "Eaton — Medium-Voltage Solid-State Transformer (catalog page)",
    url: "https://www.eaton.com/us/en-us/catalog/medium-voltage-power-distribution-control-systems/medium-voltage-solid-state-transformer.html",
    date: "verified 2026-10-04",
  },
];

const COMPETENCIES = [
  { name: "Systems architecture", does: "Trace the chain and name the interface at each boundary.", where: "System Map", href: "/design-lab/system-map" },
  { name: "Technical trade studies", does: "State which driver dominates and what it favors, with the conditions that reverse it.", where: "Architecture Choices", href: "/design-lab/architecture" },
  { name: "Protection & reliability", does: "Compare protection response time against the failure time scale.", where: "Learn by Example", href: "/design-lab/learn" },
  { name: "Controls & integration", does: "Read how loop time constants shape a transient.", where: "Advanced Sandbox", href: "/design-lab/sandbox" },
  { name: "System validation", does: "Say what evidence a real design would need: analysis, factory test, site test.", where: "Learn by Example", href: "/design-lab/learn" },
  { name: "Power-conversion architecture", does: "Explain why consolidating conversion stages shifts, not removes, the problem.", where: "Architecture Choices", href: "/design-lab/architecture" },
] as const;

export default function IndustryLab() {
  return (
    <>
      <AreaHeader
        area="04 · Industry & Career"
        mode="Trace"
        question="Who is saying what about 800 VDC and SST, and what does it ask of an engineer?"
        answer="Follow each public claim back to its source, see how strong it is and what it leaves out, then see which skills the product asks you to practice."
      />
      <div className="lab-wrap">
        <BasisBar
          notes={[
            { tag: "Sources", text: "Three distinct public sources support this page. It is a context layer, not a live news feed." },
            { tag: "Attribution", text: "Vendor and consortium statements are attributed, not endorsed. Emerging architectures and draft specifications are marked as such." },
            { tag: "Competencies", text: "The competency map is an illustrative teaching framework, not a hiring standard or a statement about any employer." },
          ]}
          labels={<EvidenceLegend />}
        />
      </div>

      <section className="lab-wrap lab-section lab-first">
        <div className="lab-split r75">
          <div>
            <div className="lab-section-head" style={{ marginBottom: 12 }}>
              <div>
                <h2 className="lab-h2">Source trace</h2>
                <p className="lab-section-sub">Claim, source, strength, and what it does not show.</p>
              </div>
            </div>
            <div style={{ display: "grid", gap: 12 }}>
              {TRACES.map((t) => (
                <article key={t.who} className="lab-panel">
                  <header style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 8 }}>
                    <h3 className="lab-h3" style={{ fontSize: 15, margin: 0 }}>{t.who}</h3>
                    <span style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      <span className="lab-chip">{t.kind}</span>
                      <EvidenceChip kind={t.strength} />
                    </span>
                  </header>
                  <p className="lab-body" style={{ color: "var(--color-text-primary)" }}>{t.claim}</p>
                  <dl className="lab-kv" style={{ marginTop: 6 }}>
                    <dt>Does not show</dt>
                    <dd style={{ color: "var(--color-text-secondary)" }}>{t.notShown}</dd>
                    <dt>Source</dt>
                    <dd>
                      <a href={t.url} target="_blank" rel="noreferrer" style={{ textDecoration: "underline", textUnderlineOffset: 3 }}>
                        {t.title}
                      </a>
                      <span className="lab-mono" style={{ color: "var(--color-text-secondary)", fontSize: 11.5, marginLeft: 8 }}>{t.date}</span>
                    </dd>
                  </dl>
                </article>
              ))}
            </div>
          </div>

          <div>
            <div className="lab-section-head" style={{ marginBottom: 12 }}>
              <div>
                <h2 className="lab-h2">Competency map</h2>
                <p className="lab-section-sub">Where each skill is practiced in this product.</p>
              </div>
              <EvidenceChip kind="assumption" short />
            </div>
            <div className="lab-panel" style={{ padding: 0 }}>
              {COMPETENCIES.map((c, i) => (
                <Link
                  key={c.name}
                  href={c.href}
                  className="lab-area-link"
                  style={{ padding: "12px 16px", borderTop: i ? "1px solid var(--color-hairline)" : 0 }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "baseline" }}>
                    <span className="lab-h3" style={{ margin: 0 }}>{c.name}</span>
                    <span className="lab-mono" style={{ fontSize: 11, color: "var(--color-text-secondary)" }}>{c.where} →</span>
                  </div>
                  <p className="lab-body" style={{ margin: "2px 0 0", fontSize: 13 }}>{c.does}</p>
                </Link>
              ))}
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
