import type { ReactNode } from "react";

import {
  EVIDENCE_LABEL_TEXT,
  SOURCE_KIND_TEXT,
  REFERENCES,
  type EvidenceLabel,
  type ReferenceId,
} from "../lib/architectureChoicesData";

/**
 * Neutral-text evidence label plus the basis for a content item
 * (Blueprint §5.1). Deliberately not a status color (DESIGN.md): the
 * label says what kind of claim this is, not how healthy anything is.
 */
const GLYPH: Record<EvidenceLabel, ReactNode> = {
  "public-fact": <rect x="1" y="1" width="8" height="8" />,
  assumption: <circle cx="5" cy="5" r="4" />,
  "model-output": <path d="M5 0.5 9.5 5 5 9.5 0.5 5z" />,
  emerging: <path d="M5 1 9.5 9H0.5z" />,
};

export function EvidenceTag({
  evidence,
  basis,
  refs,
  glyph = false,
}: {
  evidence: EvidenceLabel;
  basis: string;
  refs?: readonly ReferenceId[];
  /** Presentation option (DESIGN.md section 16): prefix the canonical
   * label with a neutral shape. Default keeps the original rendering. */
  glyph?: boolean;
}) {
  return (
    <p className="flex flex-col gap-0.5 border-t border-hairline pt-1.5 text-[10.5px] leading-snug text-secondary">
      <span>
        {glyph && (
          <svg viewBox="0 0 10 10" width="9" height="9" aria-hidden="true" className="mr-1.5 inline-block fill-none stroke-current text-primary">
            {GLYPH[evidence]}
          </svg>
        )}
        <span className="font-mono uppercase tracking-[0.06em] text-primary">
          {EVIDENCE_LABEL_TEXT[evidence]}
        </span>
        {" — "}
        {basis}
      </span>
      {refs && refs.length > 0 && (
        <span>
          Refs:{" "}
          {refs.map((id, i) => (
            <span key={id}>
              <a href="#references" className="font-mono text-primary underline underline-offset-2 hover:opacity-80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary">
                {REFERENCES[id].id}
              </a>
              <span className="text-secondary"> ({SOURCE_KIND_TEXT[REFERENCES[id].kind]})</span>
              {i < refs.length - 1 ? ", " : ""}
            </span>
          ))}
        </span>
      )}
    </p>
  );
}
