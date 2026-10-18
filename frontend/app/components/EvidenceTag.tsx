import {
  EVIDENCE_LABEL_TEXT,
  REFERENCES,
  type EvidenceLabel,
  type ReferenceId,
} from "../lib/architectureChoicesData";

/**
 * Neutral-text evidence label plus the basis for a content item
 * (Blueprint §5.1). Deliberately not a status color (DESIGN.md): the
 * label says what kind of claim this is, not how healthy anything is.
 */
export function EvidenceTag({
  evidence,
  basis,
  refs,
}: {
  evidence: EvidenceLabel;
  basis: string;
  refs?: readonly ReferenceId[];
}) {
  return (
    <p className="flex flex-col gap-0.5 border-t border-hairline pt-1.5 text-[10.5px] leading-snug text-secondary">
      <span>
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
              {i < refs.length - 1 ? ", " : ""}
            </span>
          ))}
        </span>
      )}
    </p>
  );
}
