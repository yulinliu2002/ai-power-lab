"""Shared, bounded, sanitized failure diagnostics for Claude/Codex
subprocess failures (SPEC-003 Requirement 4).

This is workflow tooling, not an engineering model -- CLAUDE.md's
governing-equation/units documentation requirement does not apply here.
What does apply is the Human Engineering Lead's explicit direction for
this exact module: a fixed, small, reviewable rule set, not a
speculative/general secret-detection framework (SPEC-003 Known
Limitations). Every rule below is enumerated in full in this file; none
of it is configurable at runtime.

`build_diagnostic` is the single entry point both `peos/claude_agent.py`
and `peos/codex_agent.py` route every failure message through, in this
order:

1. **Structured first.** A caller that already extracted the CLI's own
   structured error field (e.g. Claude's `result` string when
   `is_error` is true) passes it as `structured_message`. That text is
   used as the basis instead of a raw-text guess -- it is the CLI's own
   statement of what went wrong, not output grepped for clues.
2. **Raw-text fallback.** Absent a structured message, the basis is the
   combined `stdout`+`stderr` (stdout first, stderr last, so truncation
   below preferentially keeps stderr -- SPEC-003 Requirement 4a).
3. **Redaction.** The basis is redacted *before* bounding, not after:
   bounding first could truncate a token-shaped substring down to a
   length the redaction patterns below no longer match, leaking a
   partial secret. Redacting the full text first means a token is
   always either fully matched (and replaced) or not present at all.
4. **Classification.** The redacted (but not yet bounded) text is
   matched against a small, fixed set of literal, non-secret CLI
   phrases to produce one of `authentication`, `cli_invocation`,
   `schema`, or `runtime` -- unless the caller already knows the
   category (e.g. a JSON-parse failure) and passes `category_override`,
   skipping phrase-matching entirely. Classifying before bounding (not
   after) means a late-appearing phrase is never dropped by truncation
   before it has a chance to be matched.
5. **Bounding.** Focused Codex review remediation (Finding 5, MINOR):
   the *complete* diagnostic -- including the `[category]`/`exit=N:`
   prefix this function prepends -- must fit in `MAX_DIAGNOSTIC_CHARS`
   (the fixed, non-configurable 500-character bound SPEC-003 requires),
   not merely the message body. The prefix's length is computed first
   and reserved out of the fixed budget, so the body is bounded to
   whatever remains, keeping the tail (most recent output) when
   truncating.

Deviation from the spec's own illustrative redaction example, recorded
here rather than left to a diff: SPEC-003 Requirement 4a's example
pattern was "a 20+ character run of `[A-Za-z0-9_\\-\\.]`" (an "e.g.",
not a dictated exact value, unlike the 500-character bound, which is
dictated and fixed). A literal 20-character threshold false-positives on
this codebase's own schema vocabulary used throughout legitimate,
non-secret error messages -- `acceptance_criteria` is exactly 20
characters, `missing_validation_evidence` is 28. `GENERIC_TOKEN_MIN_LEN`
below is therefore 32: safely above the longest such identifier in this
codebase, still well below realistic API-key/OAuth-token lengths.
"""

from __future__ import annotations

import re

MAX_DIAGNOSTIC_CHARS = 500

# See the module docstring's "Deviation" note: 32, not the spec text's
# illustrative "20+", to avoid redacting this codebase's own field/enum
# vocabulary (e.g. `missing_validation_evidence`, 28 characters).
GENERIC_TOKEN_MIN_LEN = 32

_REDACTED = "[REDACTED]"

# Fixed, reviewable redaction rules -- intentionally not exhaustive (see
# module docstring). Order matters only in that each is applied in turn
# to the (cumulatively redacted) text.
_REDACTION_PATTERNS = (
    re.compile(r"Bearer\s+\S+", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"[A-Za-z0-9_\-\.]{" + str(GENERIC_TOKEN_MIN_LEN) + r",}"),
)

# Fixed, literal, non-secret CLI phrases -- matched case-insensitively
# against the already bounded/redacted text. Order matters: the first
# matching category wins.
_AUTHENTICATION_PHRASES = (
    "not logged in",
    "please run /login",
    "please run /auth",
    "invalid bearer token",
    "401",
    "unauthorized",
    "login expired",
)
_CLI_INVOCATION_PHRASES = (
    "no such file or directory",
    "command not found",
    "timed out",
    "permission denied",
)


def redact(text: str) -> str:
    """Replace every token-shaped substring matching `_REDACTION_PATTERNS`
    with a fixed placeholder. Pure function, no I/O, never raises."""
    redacted = text
    for pattern in _REDACTION_PATTERNS:
        redacted = pattern.sub(_REDACTED, redacted)
    return redacted


def bound(text: str, limit: int = MAX_DIAGNOSTIC_CHARS) -> str:
    """Truncate `text` to at most `limit` characters, keeping the tail."""
    if len(text) <= limit:
        return text
    return text[-limit:]


def classify(text: str) -> str:
    """Return one of `authentication`, `cli_invocation`, or `runtime` by
    matching fixed literal phrases against `text` (case-insensitive).
    Never returns `schema` -- that category is only ever supplied by a
    caller that already knows it (`category_override`), since there is
    no literal-phrase signature for "the CLI's structured output failed
    to parse/validate" distinct from the message text itself.
    """
    lowered = text.lower()
    if any(phrase in lowered for phrase in _AUTHENTICATION_PHRASES):
        return "authentication"
    if any(phrase in lowered for phrase in _CLI_INVOCATION_PHRASES):
        return "cli_invocation"
    return "runtime"


def build_diagnostic(
    stdout: str = "",
    stderr: str = "",
    structured_message: str | None = None,
    category_override: str | None = None,
    exit_code: int | None = None,
) -> str:
    """Build the bounded, sanitized, classified diagnostic string used as
    `ClaudeRunResult.error`/`CodexReviewResult.error` on every failure
    path (SPEC-003 Requirement 4). See the module docstring for the exact
    rule order. `exit_code`, when given, is included in the output
    verbatim (it is not secret and is useful operational context) and
    counts toward the fixed `MAX_DIAGNOSTIC_CHARS` budget exactly like
    the rest of the prefix (Finding 5 remediation: the budget covers the
    *complete* returned string, not just the message body).
    """
    if structured_message:
        basis = structured_message
    else:
        basis = (stdout or "") + ("\n" if stdout and stderr else "") + (stderr or "")
    sanitized = redact(basis)
    category = category_override or classify(sanitized)
    exit_part = f"exit={exit_code}: " if exit_code is not None else ""
    prefix = f"[{category}] {exit_part}"
    body_budget = max(MAX_DIAGNOSTIC_CHARS - len(prefix), 0)
    bounded_text = bound(sanitized, limit=body_budget)
    return f"{prefix}{bounded_text}"


_HASH_TOKEN_RE = re.compile(r"\b[0-9a-f]{40}\b|\b[0-9a-f]{64}\b")


def sanitize_identity_text(text: str) -> str:
    """Sanitize an orchestrator-computed machine-identity string (a Run
    Ledger field such as `authoritative_baseline`/`governing_spec_
    identity`: a Git commit hash, a content hash, or a `path:hash` pair
    joining the two) for persistence -- SPEC-004 remediation Finding 9.

    `sanitize_human_text`'s generic token-redaction rule
    (`GENERIC_TOKEN_MIN_LEN`-or-longer run of `[A-Za-z0-9_\\-\\.]`) cannot
    tell a 40-character Git SHA-1 or 64-character SHA-256 content hash
    apart from a secret-shaped token of the same length, and redacting it
    destroys identity information the ledger's own retention/integrity
    logic depends on (SPEC-004 Requirement 20).

    The boundary this function relies on is structural, not content-
    based: it must only ever be called on the two orchestrator-*computed*
    ledger fields, never on agent-authored free text (a finding
    description, a Claude summary, a gate reason) -- those remain on
    `sanitize_human_text`/`redact`'s ordinary generic-token redaction with
    no exception. Given that boundary, a substring that exactly matches
    the expected hash shape (40 or 64 lowercase hex characters) is
    preserved verbatim; everything else in the string (e.g. a file path
    joined to the hash by `:`) still goes through the same `redact()` a
    human-text field would. A malformed candidate (wrong length, any
    non-hex character) does not match the hash-shape pattern at all, so
    it falls through to ordinary `redact()` like any other text and is
    still redacted if it happens to also match the generic token
    pattern -- this function does not create a general "claim to be a
    hash and skip sanitization" bypass for arbitrary text.
    """
    pieces: list[str] = []
    last = 0
    for match in _HASH_TOKEN_RE.finditer(text):
        pieces.append(redact(text[last:match.start()]))
        pieces.append(match.group(0))
        last = match.end()
    pieces.append(redact(text[last:]))
    return bound("".join(pieces))


def sanitize_human_text(text: str) -> str:
    """Redact and bound one agent-controlled, human-facing free-text
    field -- SPEC-003 remediation Finding 3 (MAJOR): Claude's `summary`/
    `gate_reason` and Codex's finding `description`/acceptance-criteria
    `note`/`summary` are text the CLI itself generated, not a failure
    diagnostic, but they flow into the exact same human-facing surfaces
    (`peos/workflow.py`'s log/gate/fail messages, `peos/report.py`'s
    rendered output) that `build_diagnostic`'s output already does, and
    so far passed through unredacted. This reuses the same fixed,
    reviewable `redact`/`bound` mechanism rather than inventing a second
    one. Unlike `build_diagnostic`, no classification/exit-code prefix
    is added -- this is plain text, not a `[category] ...` diagnostic.

    Callers apply this at the point a structured field is extracted and
    validated (`peos/claude_agent.py`, `peos/codex_agent.py`), not to
    `.stdout`/`.raw_stdout`/`.stderr`/`.raw_stderr`, which remain exactly
    as captured for internal/debugging use (SPEC-003 Requirement 4b) --
    this function never mutates raw subprocess output, only the
    already-extracted structured text fields built from it.
    """
    return bound(redact(text))
