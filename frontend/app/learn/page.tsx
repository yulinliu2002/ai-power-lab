import type { Metadata } from "next";

import { BasisPanel } from "../components/BasisPanel";
import { LearnByExample } from "../components/LearnByExample";
import { SignalPathRail } from "../components/SignalPathRail";
import { DISCLOSURES } from "../lib/architectureChoicesData";
import { LEARN_DISCLOSURES } from "../lib/learnByExampleData";

export const metadata: Metadata = {
  title: "Learn by Example | AI Power Lab",
};

// The six SPEC-012 disclosures, verbatim, always visible (SPEC-012 §6.5, AC-6).
const DISCLOSURE_ITEMS = [
  { tag: "Simulation", text: DISCLOSURES.sim },
  { tag: "Blocks", text: DISCLOSURES.block },
  { tag: "Drivers", text: DISCLOSURES.illustrative },
  { tag: "Model", text: LEARN_DISCLOSURES.d1 },
  { tag: "Bus collapse", text: LEARN_DISCLOSURES.d2 },
  { tag: "Not modeled", text: LEARN_DISCLOSURES.d3 },
] as const;

/**
 * Learn by Example (SPEC-012, four-step shell per amendment A1). Five guided
 * cases over the five existing Sandbox scenarios; live model output comes
 * from the existing endpoints via the `LearnByExample` client component.
 * This server component holds the page header, the signal-path rail and the
 * visible disclosures.
 */
export default function LearnByExamplePage() {
  return (
    <main className="ic-page flex flex-col gap-6">
      <header className="flex flex-col gap-2 border-b border-hairline pb-5">
        <p className="ic-eyebrow">Cause and effect in one simplified power chain, and where the model stops</p>
        <h1 className="ic-h1">Learn by example</h1>
        <p className="ic-lede">
          Five guided cases, one for each Advanced Sandbox scenario. For each: predict, observe the model, explain the
          cause chain, name the limiting quantity, and separate what the model computes from what real equipment would
          do.
        </p>
        <p className="ic-small" style={{ marginTop: 6 }}>
          Next: Industry &amp; Career (planned)
        </p>
      </header>
      <BasisPanel items={DISCLOSURE_ITEMS} testId="learn-disclosures" />
      <SignalPathRail architecture="mv-to-800vdc" simulatedSlice note="Simulated slice of one conceptual architecture" />
      <LearnByExample />
    </main>
  );
}
