import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "AI Power Lab",
};

/**
 * AI Power Lab 2.0's learning-first homepage. Replaces the former
 * simulator-first root (now at `/sandbox`, unchanged behavior). Server
 * component -- static content and navigation only, no client state,
 * no fetch.
 *
 * Positioning per the Phase 1B reboot: a personal, career-oriented
 * learning platform for the AI data-center power infrastructure
 * industry, built from public information -- not a research-grade
 * digital twin. The four learning areas are introduced here; System
 * Map is the primary entry point. System Map, Architecture Choices
 * (SPEC-011) and the Sandbox are the implemented destinations today.
 */
export default function HomePage() {
  return (
    <main className="mx-auto flex w-full max-w-[1320px] flex-1 flex-col gap-8 px-6 py-10">
      <header className="flex flex-col gap-3 border-b border-hairline pb-6">
        <p className="font-mono text-[10.5px] uppercase tracking-[0.08em] text-secondary">
          A personal learning platform
        </p>
        <h1 className="max-w-3xl text-2xl font-bold leading-tight tracking-tight text-primary sm:text-3xl">
          Understanding AI data-center power infrastructure, from the grid to the rack.
        </h1>
        <p className="max-w-2xl text-[13.5px] leading-relaxed text-secondary">
          AI Power Lab is built from public engineering and industry sources to develop a
          systems-architecture and executive-level understanding of how AI data centers are
          actually powered &mdash; the equipment, the architecture trade-offs, how the chain
          behaves under real events, and what is happening in the industry around it.
        </p>
        <div className="flex flex-wrap gap-3 pt-1">
          <Link
            href="/system-map"
            className="border border-accent bg-accent px-4 py-2 font-mono text-[11.5px] font-semibold uppercase tracking-[0.04em] text-canvas hover:opacity-90"
          >
            Start with the System Map &rarr;
          </Link>
          <Link
            href="/sandbox"
            className="border border-hairline px-4 py-2 font-mono text-[11.5px] font-semibold uppercase tracking-[0.04em] text-secondary hover:border-primary hover:text-primary"
          >
            Open the Advanced Sandbox
          </Link>
        </div>
      </header>

      <section className="flex flex-col gap-3">
        <h2 className="font-sans text-[13px] font-semibold uppercase tracking-[0.04em] text-secondary">
          Four learning areas
        </h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {LEARNING_AREAS.map((area) => (
            <LearningAreaCard key={area.title} {...area} />
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-2 border-t border-hairline pt-6">
        <h2 className="font-sans text-[13px] font-semibold uppercase tracking-[0.04em] text-secondary">
          What this is, and isn&rsquo;t
        </h2>
        <p className="max-w-3xl text-[12.5px] leading-relaxed text-secondary">
          This project uses only public engineering principles, standards, and industry
          sources &mdash; textbooks, published papers, datasheets, and public company/standards
          disclosures. It is <strong className="text-primary">not</strong> a commercial
          product, a research-grade digital twin, or a source of proprietary information from
          any employer. The underlying simulation (grid &rarr; SST &rarr; 800&nbsp;VDC bus
          &rarr; AI load) is a deliberately simple, lumped-parameter, system-level model of
          one conceptual, emerging architecture, built to teach how the chain behaves
          &mdash; not to reproduce a specific vendor&rsquo;s hardware or to imply that this
          architecture is widely deployed.
        </p>
      </section>
    </main>
  );
}

interface LearningArea {
  title: string;
  question: string;
  description: string;
  href: string | null;
  status: "live" | "planned";
}

const LEARNING_AREAS: ReadonlyArray<LearningArea> = [
  {
    title: "System Map",
    question: "What are the pieces, and how do they connect?",
    description:
      "The physical power path from the utility grid through substations, conversion, " +
      "distribution, and racks, to AI compute and cooling — plus where architectures " +
      "diverge, such as conventional AC distribution versus emerging 800 VDC concepts.",
    href: "/system-map",
    status: "live",
  },
  {
    title: "Architecture Choices",
    question: "Why these designs, and what are the trade-offs?",
    description:
      "How Conventional AC, AC-fed 800 VDC, and a Conceptual MV-to-800 VDC architecture via " +
      "solid-state transformer (one optional way to do the grid-side conversion, not a " +
      "requirement for 800 VDC) compare against illustrative requirement drivers, and what " +
      "interfaces and validation each would need.",
    href: "/architecture",
    status: "live",
  },
  {
    title: "Learn by Example",
    question: "Show me the chain responding to a real event.",
    description:
      "Annotated walkthroughs of the simulated chain under load steps, grid faults, and " +
      "thermal trips — the same engine the Advanced Sandbox exposes in full.",
    href: "/learn",
    status: "live",
  },
  {
    title: "Industry & Career",
    question: "What's happening in industry, and what does it mean for me?",
    description:
      "Public company, product, and standards developments in AI data-center power, " +
      "tracked over time, framed for an engineer building a systems-architecture career path.",
    href: null,
    status: "planned",
  },
];

function LearningAreaCard({ title, question, description, href, status }: LearningArea) {
  const body = (
    <>
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-[14px] font-semibold text-primary">{title}</h3>
        <span
          className={`font-mono text-[9.5px] uppercase tracking-[0.06em] ${
            status === "live" ? "text-status-good" : "text-secondary"
          }`}
        >
          {status === "live" ? "available" : "planned"}
        </span>
      </div>
      <p className="mt-1 text-[12px] italic leading-snug text-secondary">{question}</p>
      <p className="mt-1.5 text-[12px] leading-relaxed text-secondary">{description}</p>
    </>
  );

  if (href) {
    return (
      <Link
        href={href}
        className="flex flex-col border border-hairline bg-surface px-4 py-3 hover:border-primary"
      >
        {body}
      </Link>
    );
  }

  return (
    <div className="flex flex-col border border-hairline bg-surface-raised px-4 py-3 opacity-80">
      {body}
    </div>
  );
}
