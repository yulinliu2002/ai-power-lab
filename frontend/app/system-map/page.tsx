import type { Metadata } from "next";
import Link from "next/link";

import { AreaHeader } from "../components/AreaHeader";
import { BasisPanel } from "../components/BasisPanel";
import { InfrastructureMap } from "../components/InfrastructureMap";
import { PowerFlowSchematic } from "../components/PowerFlowSchematic";
import { DISCLOSURES } from "../lib/architectureChoicesData";

export const metadata: Metadata = {
  title: "System Map | AI Power Lab",
};

/**
 * System Map -- the first of AI Power Lab 2.0's four learning areas
 * (REBOOT_ARCHITECTURE.md §2/§4): "What are the pieces of an AI
 * data-center power chain, and how do they connect?"
 *
 * Phase 1C expands this from the narrow grid→SST→bus→load view into a
 * broader, interactive infrastructure map (`InfrastructureMap`) covering
 * the ten major infrastructure categories across three representative
 * architectures. The original simplified schematic stays on the page,
 * demoted to a clearly-labeled secondary section describing exactly
 * what this project's own simulation models -- one instance of the
 * "Conceptual MV-to-800VDC" architecture view above, not a second,
 * competing topology.
 *
 * Server component -- `InfrastructureMap` is the only client-interactive
 * piece (architecture/node selection); everything else here is static
 * prose, no fetch.
 */
export default function SystemMapPage() {
  return (
    <main className="mx-auto flex w-full max-w-[1320px] flex-1 flex-col gap-5 px-4 py-5 sm:px-6">
      <AreaHeader
        title="System map"
        role="Explore system structure, equipment and interfaces"
        lede="How an AI data center is powered and cooled. This map covers the major electrical and cooling infrastructure categories from the utility grid to the compute rack, and three representative architectures showing where they diverge."
        next={{ href: "/architecture", label: "Architecture Choices: compare these three architectures" }}
      />

      <BasisPanel
        title="Basis and limits"
        items={[
          { tag: "Blocks", text: DISCLOSURES.block },
          { tag: "Simulation", text: DISCLOSURES.sim },
        ]}
      />

      <InfrastructureMap />

      <section className="flex flex-col gap-2 border-t border-hairline pt-3">
        <h2 className="text-heading text-primary">Thirty seconds on what this is</h2>
        <dl className="flex flex-col divide-y divide-hairline">
          {QA.map(({ question, answer }) => (
            <div key={question} className="flex flex-col gap-1 py-2.5">
              <dt className="text-[13px] font-semibold text-primary">{question}</dt>
              <dd className="max-w-3xl text-[12.5px] leading-relaxed text-secondary">{answer}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="flex flex-col gap-2.5 border-t border-hairline pt-3">
        <div className="flex flex-col gap-1">
          <h2 className="text-heading text-primary">What this project actually simulates</h2>
          <p className="max-w-3xl text-[12.5px] leading-relaxed text-secondary">
            The map above is a broad infrastructure overview. This project&rsquo;s live simulation
            (the Advanced Sandbox) models one narrow, specific slice of it: the grid →
            SST → 800&nbsp;VDC bus → AI compute chain, drawn below exactly as the simulator
            draws it -- an instance of the <strong className="text-primary">Conceptual
            MV-to-800 VDC via SST</strong> architecture view above, not a fourth, separate topology.
          </p>
        </div>

        <PowerFlowSchematic />

        <p className="max-w-3xl text-[12px] leading-relaxed text-secondary">
          Educational, system-level, average-value model &mdash; <strong className="text-primary">not</strong>{" "}
          calibrated to any commercial SST, and no switching-level, AFE, DC/DC,
          medium-frequency-transformer, or semiconductor physics. AI COMPUTE is one lumped load, not
          a literal rack: real GPUs/ASICs don&rsquo;t run at 800&nbsp;V directly, and the
          rack-/point-of-load conversion stages between the bus and the silicon are abstracted into
          this one block. Thermal (loss &rarr; heat &rarr; temperature) and protection
          (temperature &rarr; derate &rarr; available power) effects are part of the model but only
          visible as a live trace in the Advanced Sandbox.
        </p>
        <p className="max-w-3xl text-[13px] leading-relaxed text-secondary">
          The three architecture views above are the subject of Architecture Choices, where they are
          compared against seven requirement drivers.
        </p>
        <div className="flex flex-wrap gap-2.5">
          <Link
            href="/architecture"
            className="border border-accent bg-accent px-3.5 py-1.5 font-mono text-[12px] font-semibold uppercase tracking-[0.04em] text-canvas hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary"
          >
            Compare these three architectures &rarr;
          </Link>
          <Link
            href="/sandbox"
            className="border border-hairline-strong bg-surface-raised px-3.5 py-1.5 font-mono text-[12px] font-semibold uppercase tracking-[0.04em] text-primary hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary"
          >
            Open the Advanced Sandbox &rarr;
          </Link>
        </div>
      </section>
    </main>
  );
}

const QA: ReadonlyArray<{ question: string; answer: string }> = [
  {
    question: "What is an SST?",
    answer:
      "A power-electronic converter that performs voltage transformation (and often AC/DC " +
      "conversion) using active semiconductor switching and a medium-frequency transformer, " +
      "instead of a passive line-frequency transformer. It is one candidate for the medium-voltage-to-DC " +
      "stage, proposed to reduce the number of conversion stages; it is not required for 800 VDC " +
      "(Architecture Choices compares the options).",
  },
  {
    question: "Why does 800 VDC matter?",
    answer:
      "Public industry sources (NVIDIA, the Open Compute Project) describe an industry shift " +
      "toward centralized power conversion and an 800 VDC distribution bus for high-density AI " +
      "racks, aiming to cut the number of conversion stages between the grid and the compute " +
      "load.",
  },
  {
    question: "Why do AI data centers create new power challenges?",
    answer:
      "AI compute workloads can swing power demand fast and hard -- the Advanced Sandbox " +
      "(linked at the end of this page) runs this project's AI load-step scenario, showing that " +
      "kind of transient and how the model responds to it.",
  },
  {
    question: "What does this project simulate?",
    answer:
      "The full causal chain Grid → SST (average-value model) → 800 VDC bus → AI load, " +
      "including a PI voltage controller, a lumped thermal model, and thermal-driven " +
      "protection/derating -- run it in the Advanced Sandbox (linked at the end of this page).",
  },
  {
    question: "What does it NOT simulate yet?",
    answer:
      "No switching-level semiconductor behavior, no detailed SiC/GaN device physics, no " +
      "medium-frequency-transformer electromagnetics, no AC power flow -- the SST is one " +
      "aggregate average-value block. The Advanced Sandbox (linked at the end of this page) shows the live model.",
  },
];
