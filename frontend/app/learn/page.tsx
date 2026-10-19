import type { Metadata } from "next";

import { LearnByExample } from "../components/LearnByExample";
import { DISCLOSURES } from "../lib/architectureChoicesData";
import { LEARN_DISCLOSURES } from "../lib/learnByExampleData";

export const metadata: Metadata = {
  title: "Learn by Example | AI Power Lab",
};

/**
 * Learn by Example (SPEC-012). Five guided cases over the five existing
 * Sandbox scenarios; live model output comes from the existing endpoints via
 * the `LearnByExample` client component. This server component holds the
 * page header and the visible disclosures (SPEC-012 §6.5).
 */
export default function LearnByExamplePage() {
  return (
    <main className="mx-auto flex w-full max-w-[1320px] flex-1 flex-col gap-6 px-6 py-5">
      <header className="flex flex-col gap-1.5 border-b border-hairline pb-3">
        <h1 className="text-lg font-bold tracking-tight text-primary">LEARN BY EXAMPLE</h1>
        <p className="font-mono text-[10.5px] uppercase tracking-[0.08em] text-secondary">
          Cause and effect in one simplified power chain, and where the model stops
        </p>
        <p className="max-w-3xl text-[13px] leading-relaxed text-secondary">
          Five guided cases, one for each Advanced Sandbox scenario. For each: predict, observe the
          model, explain the cause chain, name the limiting quantity, and separate what the model
          computes from what real equipment would do.
        </p>
        <ul className="flex max-w-3xl flex-col gap-1 pt-1" data-testid="learn-disclosures">
          {[
            DISCLOSURES.illustrative,
            LEARN_DISCLOSURES.d1,
            DISCLOSURES.sim,
            DISCLOSURES.block,
            LEARN_DISCLOSURES.d2,
            LEARN_DISCLOSURES.d3,
          ].map((text) => (
            <li key={text} className="flex gap-1.5 text-[12px] leading-relaxed text-secondary">
              <span aria-hidden="true" className="text-muted">&middot;</span>
              <span>{text}</span>
            </li>
          ))}
        </ul>
      </header>
      <LearnByExample />
    </main>
  );
}
