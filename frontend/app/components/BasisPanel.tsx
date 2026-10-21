/**
 * "Basis & limits" panel (DESIGN.md section 1, SPEC-014 F4). Structured,
 * always visible on initial load, never collapsed, paraphrased or placed
 * behind an interaction. Callers pass the specification's canonical
 * strings (for example `DISCLOSURES` from `architectureChoicesData.ts`);
 * this component never authors disclosure wording.
 */
export function BasisPanel({
  title = "Basis and limits",
  items,
  testId = "disclosures",
}: {
  title?: string;
  items: ReadonlyArray<{ tag: string; text: string }>;
  testId?: string;
}) {
  return (
    <section
      aria-label={title}
      data-testid={testId}
      className="flex flex-col gap-2.5 border border-hairline bg-surface px-4 py-3"
    >
      <h2 className="text-heading text-primary">{title}</h2>
      <ul className="grid grid-cols-1 gap-x-8 gap-y-2.5 md:grid-cols-2">
        {items.map((item) => (
          <li key={item.tag} className="flex flex-col gap-0.5 sm:grid sm:grid-cols-[88px_1fr] sm:gap-3">
            <span className="font-mono text-meta uppercase text-primary sm:pt-0.5">{item.tag}</span>
            <span className="text-[13px] leading-relaxed text-secondary">{item.text}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
