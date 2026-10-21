import type { Metadata } from "next";
import Link from "next/link";

import { EvidenceTag } from "../components/EvidenceTag";
import { DISCLOSURES } from "../lib/architectureChoicesData";
import {
  BACKGROUND_STANDARDS,
  CAREER_ROWS,
  CHARTER_LADDER,
  CLAIM_SHEETS,
  INDUSTRY_REFERENCES,
  INDUSTRY_REF_ORDER,
  KIND_TEXT,
  QUESTIONS_TO_ASK,
  READ_LOG,
  SE_ACTIVITIES,
  SPEC_STATUS_ROWS,
} from "../lib/industryCareerData";
import { ClaimSheet } from "./ClaimSheet";

export const metadata: Metadata = {
  title: "Industry & Career | AI Power Lab",
};

const link =
  "underline underline-offset-2 hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary";

function QuestionsToAsk({ items, label }: { items: readonly string[]; label: string }) {
  return (
    <div className="max-w-3xl border-t border-hairline pt-3">
      <h3 className="mb-1.5 text-body font-semibold text-primary">Questions to ask: {label}</h3>
      <ul className="m-0 flex list-disc flex-col gap-1 pl-5 text-[13px] leading-snug text-secondary">
        {items.map((q) => (
          <li key={q}>{q}</li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Industry & Career (SPEC-013). A reading-and-judgment page: public claims to
 * read critically, the status of the standards around them, and a map from
 * the project's career-learning priorities to where this app exercises them.
 * Static server component; only the claim sheets carry client state. No
 * charts, diagrams, comparison tables or simulation output appear here.
 */
export default function IndustryPage() {
  return (
    <main className="ic-page">
      <header className="flex flex-col gap-2 border-b border-hairline pb-5">
        <p className="ic-eyebrow">Connect knowledge to industry and competencies</p>
        <h1 className="ic-h1">Industry &amp; career</h1>
        <p className="ic-lede">
          Read public 800&nbsp;VDC and solid-state-transformer claims the way an engineer would: what each one says, how
          strong the evidence is, and which systems-engineering competency it exercises. Five sources, each read on the
          date shown; this is not an industry survey.
        </p>
        <p className="ic-small">
          Where to practise: the{" "}
          <Link href="/system-map" className={`text-primary ${link}`}>System Map</Link> for structure,{" "}
          <Link href="/architecture" className={`text-primary ${link}`}>Architecture Choices</Link> for trade-offs, and{" "}
          <Link href="/learn" className={`text-primary ${link}`}>Learn by Example</Link> for cause and effect.
        </p>
      </header>

      <section aria-label="Basis and limits" className="mt-6 flex flex-col gap-2 border-b border-hairline pb-5" data-testid="industry-disclosures">
        <ul className="m-0 flex list-none flex-col gap-2 p-0 text-[13px] leading-snug text-secondary">
          <li><span className="font-semibold text-primary">SST. </span>{DISCLOSURES.sst}</li>
          <li><span className="font-semibold text-primary">Blocks. </span>{DISCLOSURES.block}</li>
          <li>
            <span className="font-semibold text-primary">Attribution. </span>
            Vendor and consortium statements are attributed, not endorsed. Nothing here validates the performance of any
            product, and the Advanced Sandbox is not calibrated to any product.
          </li>
          <li>
            <span className="font-semibold text-primary">Currency. </span>
            Content is as read on the dates shown and has no update mechanism; sources may have changed since.
          </li>
        </ul>
      </section>

      <section id="claims" aria-labelledby="h-claims" className="mt-8 flex flex-col gap-4">
        <h2 id="h-claims" className="ic-h2"><b>Claims to read</b><span>Five sources, one claim sheet each</span></h2>
        <p className="ic-small max-w-3xl">
          Each sheet leads with one claim. Decide what you would need answered before relying on it, then compare with what
          the source says and does not say.
        </p>
        {CLAIM_SHEETS.map((s, i) => (
          <ClaimSheet key={s.id} sheet={s} index={i} />
        ))}
        <QuestionsToAsk items={QUESTIONS_TO_ASK.claims} label="reading a vendor or consortium document" />
      </section>

      <section id="standards" aria-labelledby="h-standards" className="mt-10 flex flex-col gap-4 border-t border-hairline pt-8">
        <h2 id="h-standards" className="ic-h2"><b>Standards and specifications</b><span>Draft or published, opened or not</span></h2>
        <div>
          <h3 className="mb-2 text-body font-semibold text-primary">Documents read for this site</h3>
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {SPEC_STATUS_ROWS.map((r) => (
              <li key={r.sourceId} className="flex flex-col gap-0.5 border border-hairline bg-surface px-4 py-3 text-[13px] leading-snug text-secondary">
                <span className="font-semibold text-primary">{r.title}</span>
                <span>
                  <span className="font-mono text-meta uppercase text-primary">{r.status}</span> &mdash; {r.statusLine}{" "}
                  <a href={`#${r.sheetId}`} className={`text-primary ${link}`}>Read its claim sheet</a>
                </span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="mb-1 text-body font-semibold text-primary">Background standards to read next</h3>
          <p className="ic-small mb-2 max-w-3xl">
            Title-level entries only. None of these documents was opened for this site, so nothing here is verified against
            their text.
          </p>
          <ul className="m-0 flex list-none flex-col gap-2 p-0" data-testid="background-standards">
            {BACKGROUND_STANDARDS.map((s) => (
              <li key={s.name} className="flex flex-col gap-1 border border-hairline bg-surface px-4 py-3 text-[13px] leading-snug text-secondary">
                <span>
                  <span className="font-semibold text-primary">{s.name}</span>{" "}
                  <span className="font-mono text-meta uppercase">not opened</span>
                </span>
                <span>{s.title}</span>
                <span>{s.topic}</span>
                {s.basis === "sourced" ? (
                  <span className="font-mono text-meta">Locator: {s.locator}</span>
                ) : (
                  <EvidenceTag evidence="assumption" basis="Generic topic note from the standard's title; not taken from a source read for this site." glyph />
                )}
              </li>
            ))}
          </ul>
        </div>
        <QuestionsToAsk items={QUESTIONS_TO_ASK.standards} label="reading a standard or specification" />
      </section>

      <section id="career-map" aria-labelledby="h-career" className="mt-10 flex flex-col gap-4 border-t border-hairline pt-8">
        <h2 id="h-career" className="ic-h2"><b>Career map</b><span>Where the app exercises each learning priority</span></h2>
        <p className="ic-small max-w-3xl">
          The ten learning priorities come from the project charter. Role-activity sentences are generic educational
          assumptions, not descriptions of any employer or job. A row says &ldquo;not yet exercised&rdquo; where the app has
          no exercise point.
        </p>
        <ol className="m-0 flex list-none flex-col p-0" data-testid="career-map">
          {CAREER_ROWS.map((r) => (
            <li
              key={r.priority}
              id={`career-${r.priority}`}
              className="grid grid-cols-1 gap-1 border-t border-hairline py-3 sm:grid-cols-[minmax(0,5fr)_minmax(0,4fr)_minmax(0,6fr)] sm:gap-6"
            >
              <p className="m-0 text-[14px] font-semibold leading-snug text-primary">
                <span className="mr-2 font-mono text-meta text-secondary">{r.band} &middot; {r.priority}</span>
                {r.title}
              </p>
              <p className="m-0 text-[13px] leading-snug text-secondary">
                {r.exercised.length === 0 ? (
                  <span className="font-mono text-meta uppercase">Not yet exercised</span>
                ) : (
                  r.exercised.map((e, i) => (
                    <span key={e.href}>
                      {i > 0 && ", "}
                      {e.href.startsWith("#") ? (
                        <a href={e.href} className={`text-primary ${link}`}>{e.label}</a>
                      ) : (
                        <Link href={e.href} className={`text-primary ${link}`}>{e.label}</Link>
                      )}
                    </span>
                  ))
                )}
              </p>
              <p className="m-0 text-[13px] leading-snug text-secondary">{r.activity}</p>
            </li>
          ))}
        </ol>
        <EvidenceTag evidence="assumption" basis="Role-activity sentences are generic educational assumptions; the exercise points are links to this app." glyph />

        <div className="border-t border-hairline pt-4">
          <h3 className="mb-2 text-body font-semibold text-primary">Systems-engineering activities</h3>
          <ul className="m-0 flex list-none flex-col gap-1.5 p-0 text-[13px] leading-snug text-secondary">
            {SE_ACTIVITIES.map((a) => (
              <li key={a.activity}>
                <span className="font-semibold text-primary">{a.activity}. </span>
                {a.note}{" "}
                {a.where.map((w, i) => (
                  <span key={w.href}>
                    {i > 0 && ", "}
                    <Link href={w.href} className={`text-primary ${link}`}>{w.label}</Link>
                  </span>
                ))}
              </li>
            ))}
          </ul>
        </div>
        <div className="border-t border-hairline pt-4">
          <h3 className="mb-1 text-body font-semibold text-primary">Growth of responsibility, as the charter describes it</h3>
          <p className="m-0 text-[13px] leading-snug text-secondary" data-testid="ladder">
            {CHARTER_LADDER.join(" → ")}
          </p>
          <p className="ic-small mt-1 max-w-3xl">
            A description of activities that widen in scope, taken from the project charter. It is not a statement about
            any job or about demand for any role.
          </p>
        </div>
        <QuestionsToAsk items={QUESTIONS_TO_ASK.career} label="using this map" />
      </section>

      <section id="references" aria-labelledby="h-refs" className="mt-10 flex flex-col gap-3 border-t border-hairline pt-8">
        <h2 id="h-refs" className="ic-h2"><b>References</b></h2>
        <p className="ic-small max-w-3xl">
          Each entry states what was read and when. A page date is the date printed on the source; a read date is when it
          was last read for this page. The standards listed above are background only and are not references here.
        </p>
        <ul className="ic-refs">
          {INDUSTRY_REF_ORDER.map((id) => {
            const r = INDUSTRY_REFERENCES[id];
            const log = READ_LOG[id];
            return (
              <li key={id}>
                <b style={{ color: "var(--color-text-primary)" }}>{r.id}</b>{" "}
                <span className="ic-mono" style={{ fontSize: 11 }}>[{KIND_TEXT[r.kind]}]</span> &mdash;{" "}
                {r.url ? (
                  <a href={log.readUrl ?? r.url} className={link} rel="noreferrer">{r.citation}</a>
                ) : (
                  r.citation
                )}
                <span className="block">Inspection: {r.inspection}</span>
                <span className="block ic-mono" style={{ fontSize: 11 }}>
                  Page date: {log.pageDate ?? "none shown"} &middot; Read: {log.readDate}
                </span>
              </li>
            );
          })}
        </ul>
      </section>
    </main>
  );
}
