"use client";

import Link from "next/link";
import { useState } from "react";

import { EvidenceTag } from "../components/EvidenceTag";
import type { ReferenceId } from "../lib/architectureChoicesData";
import {
  CAREER_ROWS,
  INDUSTRY_REFERENCES,
  KIND_TEXT,
  QUESTIONS,
  READ_LOG,
  type ClaimSheetData,
  type QuestionId,
} from "../lib/industryCareerData";

const link =
  "underline underline-offset-2 hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary";

/**
 * One claim sheet (SPEC-013 E1-E4): the claim first, then a light
 * "What would you ask?" exercise, with sources, dates and limits behind a
 * native disclosure. Client-side only: no persistence, no free input.
 */
export function ClaimSheet({ sheet, index }: { sheet: ClaimSheetData; index: number }) {
  const [asked, setAsked] = useState<ReadonlySet<QuestionId>>(new Set());
  const [revealed, setRevealed] = useState(false);

  const ref = INDUSTRY_REFERENCES[sheet.sourceId];
  const log = READ_LOG[sheet.sourceId];
  const row = CAREER_ROWS.find((r) => r.priority === sheet.competency.priority)!;
  // Only registry sources can be passed to the shared evidence tag; Eaton is page-local.
  const tagRefs = sheet.sourceId === "EATON" ? undefined : [sheet.sourceId as ReferenceId];

  const toggle = (id: QuestionId) => {
    setRevealed(false);
    setAsked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <article
      id={sheet.id}
      data-testid={`claim-${sheet.id}`}
      className="flex flex-col gap-4 border border-hairline-strong bg-surface-raised p-4 sm:p-6"
    >
      <header className="flex flex-col gap-2">
        <p className="font-mono text-meta uppercase text-secondary">
          Source {index + 1} &middot; {KIND_TEXT[ref.kind]}
        </p>
        <h3 className="max-w-3xl text-[19px] font-semibold leading-snug tracking-tight text-primary sm:text-[22px]">
          {sheet.claim}
        </h3>
        <div className="max-w-3xl">
          <EvidenceTag evidence={sheet.evidence} basis={sheet.basis} refs={tagRefs} glyph />
        </div>
      </header>

      <section aria-labelledby={`${sheet.id}-ask`} className="flex flex-col gap-2 border-t border-hairline pt-3">
        <h4 id={`${sheet.id}-ask`} className="text-body font-semibold text-primary">
          Before you rely on it: what would you ask?
        </h4>
        <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
          {QUESTIONS.map((q) => {
            const on = asked.has(q.id);
            return (
              <li key={q.id}>
                <button
                  type="button"
                  aria-pressed={on}
                  onClick={() => toggle(q.id)}
                  className={`border px-2.5 py-1.5 text-left text-[12.5px] leading-snug focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary ${
                    on
                      ? "border-hairline-strong bg-surface-inset font-semibold text-primary"
                      : "border-hairline bg-surface text-secondary hover:border-primary hover:text-primary"
                  }`}
                >
                  <span aria-hidden="true" className="mr-1.5 font-mono">{on ? "[x]" : "[ ]"}</span>
                  {q.text}
                </button>
              </li>
            );
          })}
        </ul>
        <div>
          <button
            type="button"
            onClick={() => setRevealed(true)}
            disabled={asked.size === 0}
            className="border border-hairline bg-surface px-3 py-1.5 font-mono text-[12px] uppercase tracking-[0.04em] text-secondary hover:border-primary hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary disabled:cursor-not-allowed disabled:opacity-60"
          >
            Compare with the source
          </button>
          {asked.size === 0 && (
            <span className="ml-3 text-[12.5px] text-secondary">Pick at least one question first.</span>
          )}
        </div>
        <div aria-live="polite">
          {revealed && (
            <ul data-testid={`answers-${sheet.id}`} className="m-0 flex list-none flex-col gap-1.5 p-0 text-[13px] leading-snug text-secondary">
              {QUESTIONS.filter((q) => asked.has(q.id) || sheet.answers[q.id]).map((q) => {
                const picked = asked.has(q.id);
                return (
                  <li key={q.id} className="border-l-2 border-hairline-strong pl-3">
                    <span className="font-semibold text-primary">{q.text}</span>{" "}
                    <span className="font-mono text-meta uppercase">{picked ? "You asked" : "Also worth asking"}</span>
                    <br />
                    {sheet.answers[q.id] ?? "The passages audited for this page do not answer this."}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </section>

      <p className="text-body text-secondary">
        <span className="font-semibold text-primary">Competency this exercises: </span>
        {sheet.competency.text}{" "}
        <a href={`#career-${row.priority}`} className={`text-primary ${link}`}>
          {row.band} priority {row.priority} in the Career Map
        </a>
        .
      </p>
      <p className="text-body text-secondary">
        {sheet.relation.text}{" "}
        <Link href={sheet.relation.href} className={`text-primary ${link}`}>
          {sheet.relation.label}
        </Link>
      </p>

      <details className="border-t border-hairline pt-3">
        <summary className="cursor-pointer font-mono text-[12px] uppercase tracking-[0.04em] text-secondary hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary">
          Details: what the source says, dates, citation, limits
        </summary>
        <div className="mt-3 flex flex-col gap-4">
          <div>
            <h4 className="mb-1.5 text-body font-semibold text-primary">What the source says</h4>
            <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
              {sheet.claims.map((c) => (
                <li key={c.text} className="text-[13px] leading-snug text-secondary">
                  {c.text}
                  {c.span && (
                    <span className="mt-0.5 block border-l-2 border-hairline-strong pl-3 italic">
                      &ldquo;{c.span}&rdquo;
                    </span>
                  )}
                  <span className="mt-0.5 block font-mono text-meta">
                    Locator: {c.locator}
                    {c.audit === "paraphrase-checked" ? " (paraphrase carried from an earlier audit; no verbatim span for this page)" : ""}
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h4 className="mb-1.5 text-body font-semibold text-primary">What this does not tell you</h4>
            <ul className="m-0 flex list-disc flex-col gap-1 pl-5 text-[13px] leading-snug text-secondary">
              {sheet.doesNotTell.map((t) => (
                <li key={t}>{t}</li>
              ))}
            </ul>
          </div>
          <div>
            <h4 className="mb-1.5 text-body font-semibold text-primary">Source, dates and citation</h4>
            <p className="m-0 text-[13px] leading-snug text-secondary">
              {ref.citation}
              {ref.url && (
                <>
                  {" "}
                  <a href={log.readUrl ?? ref.url} rel="noreferrer" className={`text-primary ${link}`}>
                    {log.readUrl ?? ref.url}
                  </a>
                </>
              )}
            </p>
            <p className="m-0 mt-1 font-mono text-meta text-secondary">
              Page date: {log.pageDate ?? "none shown"} &middot; Read: {log.readDate}
            </p>
            {log.pageTitle && <p className="m-0 mt-1 text-[12.5px] text-secondary">Page title: {log.pageTitle}</p>}
            {log.note && <p className="m-0 mt-1 text-[12.5px] text-secondary">{log.note}</p>}
            {sheet.note && <p className="m-0 mt-1 text-[12.5px] text-secondary">{sheet.note}</p>}
          </div>
        </div>
      </details>
    </article>
  );
}
