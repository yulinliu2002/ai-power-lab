"""Dispute-line parsing (SPEC-004 Requirement 8, "lightweight Option A").

`peos/workflow.py` deterministically scans a Claude remediation result's
dispute-attempt lines for the fixed text convention
`DISPUTE[<origin_review_number>.<finding_position>]: <evidence>` -- the
same "fixed, auditable text convention" style `peos/verification_plan.py`
already uses for spec-declared verification commands. Kept in its own
small module (rather than inline in `peos/workflow.py`, which is already
large) so the parsing/validation rules can be unit-tested directly
against a `FindingsRegister` without spinning up a full workflow run.

A line that does not even superficially look like an attempt at the
convention (does not start with `DISPUTE[`) is not a dispute at all --
business as usual, the normal, expected case for most remediation
summaries (SPEC-004 Known Limitations). A line that *does* start with
`DISPUTE[` but is malformed, references an unknown or non-outstanding
finding, or carries empty/sanitizer-truncated evidence is a deliberate
strengthening: invalid structured output, surfaced as a parse error the
caller must treat as `FAILED` for that remediation cycle (SPEC-004
AC-22/AC-23) -- never silently treated as "no dispute".

SPEC-004 remediation Finding 6 (MAJOR): `peos.claude_agent.run_claude`
applies `peos.diagnostics.sanitize_human_text` -- redact, then bound to
the last `MAX_DIAGNOSTIC_CHARS` characters -- to Claude's raw `summary`
*as a whole*. `bound()` keeps the *tail* of an over-length string, so a
dispute attempt near the start of a long summary can be pushed out of
the kept window entirely, and the parser below, seeing only ordinary
trailing text, would otherwise conclude no dispute was ever attempted --
silently bypassing the fail-closed malformed-dispute path this module
exists to provide. The fix lives at the extraction boundary, not here:
`extract_dispute_attempt_lines` is called by `run_claude` on the *raw*
summary, before that destructive whole-string bound is applied, and each
matched line is individually redacted+bounded on its own (so secrets are
still never persisted, and no single pathological line is unbounded) --
preserving every dispute attempt's existence and content independently
of whatever happens to the rest of the summary. `parse_disputes_from_
summary` below consumes that already-extracted, order-preserved tuple of
candidate lines directly, so it can no longer lose a dispute attempt to
the surrounding summary's own truncation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from peos.diagnostics import sanitize_human_text
from peos.findings_register import FindingsRegister

_DISPUTE_ATTEMPT_RE = re.compile(r"^DISPUTE\[")
_DISPUTE_VALID_RE = re.compile(r"^DISPUTE\[(\d+)\.(\d+)\]:\s*(\S.*)$")


@dataclass(frozen=True)
class ParsedDispute:
    reference: str
    evidence: str


@dataclass(frozen=True)
class DisputeParseError:
    line: str
    reason: str


def extract_dispute_attempt_lines(summary: str) -> tuple[str, ...]:
    """Extract every line of the *raw* `summary` that at least
    superficially attempts the `DISPUTE[...]` convention (starts with
    `DISPUTE[`), order-preserved, each individually sanitized
    (`peos.diagnostics.sanitize_human_text`) on its own -- called by
    `peos.claude_agent.run_claude` before the destructive whole-summary
    bound, specifically so a dispute attempt's existence and structure
    survive that later truncation (SPEC-004 remediation Finding 6; see
    module docstring).
    """
    return tuple(
        sanitize_human_text(raw_line.strip())
        for raw_line in summary.splitlines()
        if _DISPUTE_ATTEMPT_RE.match(raw_line.strip())
    )


def parse_disputes_from_summary(
    dispute_attempt_lines: tuple[str, ...], register: FindingsRegister,
) -> tuple[tuple[ParsedDispute, ...], DisputeParseError | None]:
    """Returns `(disputes, None)` on success (`disputes` may be empty --
    the normal case) or `((), error)` on the first malformed/invalid
    dispute attempt found. Never raises.

    `dispute_attempt_lines` is the already-extracted, already
    individually-sanitized tuple `extract_dispute_attempt_lines` produced
    from Claude's *raw* summary (see
    `peos.claude_agent.ClaudeRunResult.dispute_attempt_lines`) -- not a
    raw summary string to re-split here. Every element is already known
    to at least superficially attempt the convention (it matched
    `extract_dispute_attempt_lines`'s own filter), so this function only
    validates full syntax/reference/evidence structure.
    """
    disputes: list[ParsedDispute] = []
    for line in dispute_attempt_lines:
        match = _DISPUTE_VALID_RE.match(line)
        if match is None:
            return (), DisputeParseError(line=line, reason="malformed DISPUTE[...] syntax")

        origin_raw, position_raw, evidence_raw = match.groups()
        reference = f"{int(origin_raw)}.{int(position_raw)}"
        entry = register.get(reference)
        if entry is None or not entry.outstanding:
            return (), DisputeParseError(
                line=line,
                reason=f"references an unknown or non-outstanding finding: {reference}",
            )

        # `evidence_raw` was already extracted from an already-sanitized
        # `line`, so this second `sanitize_human_text` call is idempotent
        # bounding/redaction, not a second independent redaction pass.
        evidence = sanitize_human_text(evidence_raw).strip()
        if not evidence:
            return (), DisputeParseError(
                line=line,
                reason=f"evidence for DISPUTE[{reference}] is empty after sanitization",
            )

        disputes.append(ParsedDispute(reference=reference, evidence=evidence))

    return tuple(disputes), None
