import type { Metadata } from "next";
import Link from "next/link";

import { DominantDriverSelector } from "../components/DominantDriverSelector";
import { EvidenceTag } from "../components/EvidenceTag";
import {
  ARCHITECTURE_CHOICE_NAMES,
  ARCHITECTURE_ORDER,
  BOUNDARIES,
  CELLS,
  DISCLOSURES,
  DRIVERS,
  INTERFACES,
  REFERENCES,
  VALIDATION_NEEDS,
  VALIDATION_SECTION_EVIDENCE,
} from "../lib/architectureChoicesData";
import { ARCHITECTURES } from "../lib/infrastructureMapData";

export const metadata: Metadata = {
  title: "Architecture Choices | AI Power Lab",
};

/**
 * Architecture Choices V1 (SPEC-011). Static, qualitative, frontend-only:
 * requirement drivers, three architectures compared per driver, interfaces,
 * conditional decisions, and validation needs. No scores, no ranking, no
 * backend call. Server component; `DominantDriverSelector` is the only
 * client-interactive piece.
 */
export default function ArchitectureChoicesPage() {
  const nodeLabel = (id: string) =>
    ARCHITECTURES.flatMap((a) => a.nodes).find((n) => n.id === id)?.label ?? id;

  return (
    <main className="mx-auto flex w-full max-w-[1320px] flex-1 flex-col gap-6 px-6 py-5">
      <header className="flex flex-col gap-1.5 border-b border-hairline pb-3">
        <h1 className="text-lg font-bold tracking-tight text-primary">ARCHITECTURE CHOICES</h1>
        <p className="font-mono text-[10.5px] uppercase tracking-[0.08em] text-secondary">
          Which power architecture fits which requirement, and what would have to be validated
        </p>
        <p className="max-w-3xl text-[13px] leading-relaxed text-secondary">
          Three architectures from the <Link href="/system-map" className="underline underline-offset-2 hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary">System Map</Link>{" "}
          &mdash; {ARCHITECTURE_ORDER.map((id) => ARCHITECTURE_CHOICE_NAMES[id]).join(", ")} &mdash;
          are compared against seven requirement drivers. The aim is to practice reasoning from
          requirements to an architecture choice, and to name what must be validated before relying
          on it.
        </p>
        <ul className="flex max-w-3xl flex-col gap-1 pt-1" data-testid="disclosures">
          {Object.values(DISCLOSURES).map((text) => (
            <li key={text} className="flex gap-1.5 text-[12px] leading-relaxed text-secondary">
              <span aria-hidden="true" className="text-muted">&middot;</span>
              <span>{text}</span>
            </li>
          ))}
        </ul>
        <p className="max-w-3xl text-[11.5px] leading-relaxed text-secondary">
          Each item carries an evidence label: <em>Public fact</em> (principle or attributed source),{" "}
          <em>Illustrative assumption</em>, <em>Model output (simplified)</em>, or{" "}
          <em>Emerging / uncertain</em>. An item carries the label of its weakest claim.
        </p>
        <nav aria-label="On this page" className="flex flex-wrap gap-x-4 gap-y-1 pt-1 font-mono text-[11px] uppercase tracking-[0.04em]">
          {[
            ["#drivers", "1 Drivers"],
            ["#compared", "2 Compared by driver"],
            ["#interfaces", "3 Interfaces"],
            ["#dominates", "4 If a driver dominates"],
            ["#validation", "5 Validation needs"],
            ["#references", "References"],
          ].map(([href, label]) => (
            <a key={href} href={href} className="text-secondary hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-secondary">
              {label}
            </a>
          ))}
        </nav>
      </header>

      <section id="drivers" className="flex flex-col gap-2.5">
        <SectionHeading>1. Requirement drivers</SectionHeading>
        <p className="max-w-3xl text-[12.5px] leading-relaxed text-secondary">{DISCLOSURES.illustrative}</p>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {DRIVERS.map((d) => (
            <article key={d.id} data-testid={`driver-${d.id}`} className="flex flex-col gap-1.5 border border-hairline bg-surface px-3 py-3">
              <h3 className="text-[13px] font-semibold text-primary">{d.title}</h3>
              <p className="text-[12px] italic leading-snug text-secondary">{d.question}</p>
              <div className="flex flex-col gap-1.5">
                <Field label="What it is" body={d.what} />
                <Field label="Why it matters" body={d.why} />
                <Field label="System connection" body={d.system} />
                <Field label="Constraints and trade-offs" body={d.tradeoffs} />
                <Field label="Decision it informs" body={d.decision} />
              </div>
            </article>
          ))}
        </div>
      </section>

      <section id="compared" className="flex flex-col gap-3 border-t border-hairline pt-4">
        <SectionHeading>2. Architectures compared, driver by driver</SectionHeading>
        <p className="max-w-3xl text-[12.5px] leading-relaxed text-secondary">
          Qualitative only. &ldquo;Harder&rdquo; is what the architecture makes more difficult for
          that driver, not a score. {DISCLOSURES.sst}
        </p>
        {DRIVERS.map((d) => (
          <div key={d.id} data-testid={`compare-${d.id}`} className="flex flex-col gap-2">
            <h3 className="text-[13px] font-semibold text-primary">{d.title}</h3>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
              {ARCHITECTURE_ORDER.map((arch) => {
                const cell = CELLS[d.id][arch];
                return (
                  <article key={arch} className="flex flex-col gap-1.5 border border-hairline bg-surface px-3 py-2.5">
                    <h4 className="font-sans text-[11.5px] font-semibold uppercase tracking-[0.04em] text-secondary">
                      {ARCHITECTURE_CHOICE_NAMES[arch]}
                    </h4>
                    <Field label="How it is addressed" body={cell.how} />
                    <Field label="What it makes harder" body={cell.harder} />
                    <EvidenceTag evidence={cell.evidence} basis={cell.basis} refs={cell.refs} />
                    {cell.evidence === "model-output" && (
                      <Link href="/sandbox" className="self-start font-mono text-[10.5px] uppercase tracking-[0.04em] text-secondary underline underline-offset-2 hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary">
                        Open the Advanced Sandbox
                      </Link>
                    )}
                  </article>
                );
              })}
            </div>
          </div>
        ))}
        <p className="max-w-3xl text-[12px] leading-relaxed text-secondary">{DISCLOSURES.sim}</p>
      </section>

      <section id="interfaces" className="flex flex-col gap-3 border-t border-hairline pt-4">
        <SectionHeading>3. Interfaces</SectionHeading>
        <p className="max-w-3xl text-[12.5px] leading-relaxed text-secondary">
          The five boundaries where a choice becomes a specification. Node names are the System
          Map&rsquo;s. {DISCLOSURES.block}
        </p>
        {BOUNDARIES.map((b) => (
          <div key={b.id} data-testid={`boundary-${b.id}`} className="flex flex-col gap-2">
            <h3 className="text-[13px] font-semibold text-primary">{b.title}</h3>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
              {ARCHITECTURE_ORDER.map((arch) => {
                const item = INTERFACES[arch][b.id];
                return (
                  <article key={arch} className="flex flex-col gap-1.5 border border-hairline bg-surface px-3 py-2.5">
                    <h4 className="font-sans text-[11.5px] font-semibold uppercase tracking-[0.04em] text-secondary">
                      {ARCHITECTURE_CHOICE_NAMES[arch]}
                    </h4>
                    <p className="font-mono text-[10.5px] text-secondary">
                      {nodeLabel(item.nodeIds[0])} &rarr; {nodeLabel(item.nodeIds[1])}
                    </p>
                    <Field label="What crosses" body={item.crosses} />
                    <Field label="Concern" body={item.concern} />
                    <EvidenceTag evidence={item.evidence} basis={item.basis} refs={item.refs} />
                  </article>
                );
              })}
            </div>
          </div>
        ))}
      </section>

      <section id="dominates" className="flex flex-col gap-3 border-t border-hairline pt-4">
        <SectionHeading>4. If a driver dominates</SectionHeading>
        <p className="max-w-3xl text-[12.5px] leading-relaxed text-secondary">
          Pick the driver that matters most for a hypothetical site. The result is a conditional
          tendency with its exceptions, not a verdict. {DISCLOSURES.noWinner}
        </p>
        <DominantDriverSelector />
      </section>

      <section id="validation" className="flex flex-col gap-3 border-t border-hairline pt-4">
        <SectionHeading>5. Validation needs</SectionHeading>
        <p className="max-w-3xl text-[12.5px] leading-relaxed text-secondary">
          What would have to be shown, and by what kind of evidence, before relying on each
          architecture. Not a complete plan for any facility.
        </p>
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
          {ARCHITECTURE_ORDER.map((arch) => (
            <article key={arch} data-testid={`validation-${arch}`} className="flex flex-col gap-2 border border-hairline bg-surface px-3 py-2.5">
              <h3 className="font-sans text-[11.5px] font-semibold uppercase tracking-[0.04em] text-secondary">
                {ARCHITECTURE_CHOICE_NAMES[arch]}
              </h3>
              <ul className="flex flex-col gap-2">
                {VALIDATION_NEEDS[arch].map((v) => (
                  <li key={v.verifies} className="flex flex-col gap-0.5 text-[12px] leading-relaxed text-secondary">
                    <span>{v.verifies}</span>
                    <span className="font-mono text-[10.5px] uppercase tracking-[0.04em] text-secondary">
                      Evidence: {v.kinds.join(" + ")}
                    </span>
                  </li>
                ))}
              </ul>
              <EvidenceTag evidence={VALIDATION_SECTION_EVIDENCE.evidence} basis={VALIDATION_SECTION_EVIDENCE.basis} />
            </article>
          ))}
        </div>
      </section>

      <section id="references" className="flex flex-col gap-2 border-t border-hairline pt-4">
        <SectionHeading>References</SectionHeading>
        <p className="max-w-3xl text-[11.5px] leading-relaxed text-secondary">
          Textbook and standard references are title-level. Public industry sources are those
          recorded in this repository&rsquo;s industry data, with their verification date.
        </p>
        <ul className="flex flex-col gap-1.5">
          {Object.values(REFERENCES).map((r) => (
            <li key={r.id} className="text-[12px] leading-relaxed text-secondary">
              <span className="font-mono text-[11px] text-primary">{r.id}</span>{" "}
              &mdash; {r.url ? (
                <a href={r.url} className="underline underline-offset-2 hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary" rel="noreferrer">
                  {r.citation}
                </a>
              ) : (
                r.citation
              )}
              {r.verifiedDate ? ` (verified ${r.verifiedDate})` : ""}
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="font-sans text-[13px] font-semibold uppercase tracking-[0.04em] text-secondary">
      {children}
    </h2>
  );
}

function Field({ label, body }: { label: string; body: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-sans text-[10.5px] font-semibold uppercase tracking-[0.04em] text-secondary">{label}</span>
      <p className="text-[12px] leading-relaxed text-secondary">{body}</p>
    </div>
  );
}
