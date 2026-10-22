import type { Metadata } from "next";
import Link from "next/link";

import { BasisPanel } from "../components/BasisPanel";
import { LearnByExample } from "../components/LearnByExample";
import { SignalPathRail } from "../components/SignalPathRail";
import { DISCLOSURES } from "../lib/architectureChoicesData";
import { LEARN_DISCLOSURES } from "../lib/learnByExampleData";

export const metadata: Metadata = {
  title: "Learn by Example | AI Power Lab",
};

// The six SPEC-012 disclosures, verbatim (SPEC-012 §6.5, AC-6). They sit in an expandable section (amendment A3).
const DISCLOSURE_ITEMS = [
  { tag: "Simulation", text: DISCLOSURES.sim },
  { tag: "Blocks", text: DISCLOSURES.block },
  { tag: "Drivers", text: DISCLOSURES.illustrative },
  { tag: "Model", text: LEARN_DISCLOSURES.d1 },
  { tag: "Bus collapse", text: LEARN_DISCLOSURES.d2 },
  { tag: "Not modeled", text: LEARN_DISCLOSURES.d3 },
] as const;

/**
 * Learn by Example (SPEC-012, four-step shell per amendment A1, interactive
 * Load Step per A2, compact layout per A3). The case selector and the four
 * steps sit high on the page. One concise limitation statement is always
 * visible; the six full disclosures and the signal-path rail are in a native
 * expandable section (collapsed by default, content in the DOM).
 */
export default function LearnByExamplePage() {
  return (
    <main className="ic-page flex flex-col gap-5">
      <header className="flex flex-col gap-1.5">
        <h1 className="ic-h1">Learn by example</h1>
        <p className="ic-lede">
          Five guided cases, one per Advanced Sandbox scenario: predict, observe the model, explain the cause chain, then
          apply it as an engineering judgment.{" "}
          <Link href="/industry" className="text-primary underline underline-offset-2 hover:opacity-80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary">
            Next: Industry &amp; Career
          </Link>
        </p>
      </header>

      <section aria-label="Model limitations" className="flex flex-col gap-2 border-y border-hairline py-3">
        <p className="text-[14px] leading-relaxed text-primary" data-testid="learn-limitation">
          <span className="font-semibold">Model limitation: </span>
          a simplified average-value model with illustrative values. It shows how the model behaves, not how real
          equipment behaves.
        </p>
        <details data-testid="learn-basis">
          <summary className="cursor-pointer font-mono text-meta uppercase text-secondary hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary">
            Basis and limits: all six disclosures and the signal path
          </summary>
          <div className="mt-3 flex flex-col gap-3">
            <BasisPanel title="Disclosures" items={DISCLOSURE_ITEMS} testId="learn-disclosures" />
            <SignalPathRail architecture="mv-to-800vdc" simulatedSlice note="Simulated slice of one conceptual architecture" />
          </div>
        </details>
      </section>

      <LearnByExample />
    </main>
  );
}
