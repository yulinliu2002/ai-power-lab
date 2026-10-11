"""Outstanding Findings Register (SPEC-004 Requirement 16 -- NEW).

A multi-cycle Claude <-> Codex loop that only ever looks at the *latest*
Codex review's findings list can converge on `APPROVED` after a serious
problem simply stops being repeated, without anyone having decided it was
actually fixed. This module is the orchestrator-owned, run-local fix:
every `blocking`/`major` finding any review in the current run has ever
raised is tracked here by a PEOS-assigned reference, and the only way to
retire one is an explicit disposition against that exact reference --
never an absence, never a differently-worded new finding, never a bare
severity downgrade.

Identity: `(origin_review_number, finding_position)`, written as the
string `"{origin_review_number}.{finding_position}"` (e.g. `"0.3"` is the
3rd finding of the initial, cycle-0 review; `"2.1"` is the 1st finding of
remediation cycle 2's closure review). `origin_review_number` is `0` for
the initial review, `N` for remediation cycle `N`'s closure review.
`finding_position` is the finding's 1-based position in that review's own
`findings` array, exactly as Codex returned it -- including minor/info
findings, so position numbering is stable even though only
`blocking`/`major` findings get a register entry at all. PEOS assigns
this reference; neither agent is ever asked to invent or carry one.

Lifecycle (see SPEC-004 "Outstanding Findings Register" section): a
finding enters the register the first time it is seen, `OUTSTANDING`. It
leaves `OUTSTANDING` only when a *later* review's
`historical_finding_dispositions` explicitly names its reference with
`RESOLVED`, `ACCEPTED_RECLASSIFICATION`, or `HUMAN_DECISION_REQUIRED`.
`HUMAN_DECISION_REQUIRED` is terminally non-converged: it clears
`OUTSTANDING` the same way the other two do, but is also recorded
separately and permanently (`human_decision_required_ever`), and that
record is never unset by any later disposition on the same reference
within this run -- only a human acting outside PEOS (or a fresh PEOS
invocation) moves the underlying issue forward.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from peos.diagnostics import sanitize_human_text

RESOLVED = "RESOLVED"
ACCEPTED_RECLASSIFICATION = "ACCEPTED_RECLASSIFICATION"
HUMAN_DECISION_REQUIRED = "HUMAN_DECISION_REQUIRED"
VALID_DISPOSITIONS = (RESOLVED, ACCEPTED_RECLASSIFICATION, HUMAN_DECISION_REQUIRED)

_OUTSTANDING_SEVERITIES = ("blocking", "major")

_REF_RE = re.compile(r"^(\d+)\.(\d+)$")


@dataclass(frozen=True)
class FindingRef:
    origin_review_number: int
    finding_position: int

    def __str__(self) -> str:
        return f"{self.origin_review_number}.{self.finding_position}"

    @classmethod
    def parse(cls, text: str) -> "FindingRef | None":
        match = _REF_RE.match(text.strip())
        if match is None:
            return None
        return cls(origin_review_number=int(match.group(1)), finding_position=int(match.group(2)))


@dataclass(frozen=True)
class HistoricalFindingDisposition:
    """One entry of Codex's `historical_finding_dispositions` field
    (peos/codex_agent.py), already schema-validated: `reference` is a
    raw string matching `FindingRef`'s `N.P` shape (validated again here
    defensively, since this module must not trust any caller), `disposition`
    is one of `VALID_DISPOSITIONS`, and `note` is already sanitized.
    """

    reference: str
    disposition: str
    note: str


@dataclass
class RegisterEntry:
    ref: FindingRef
    severity: str
    description: str
    outstanding: bool = True
    disposition: str | None = None
    disposition_note: str | None = None
    human_decision_required_ever: bool = False


@dataclass
class FindingsRegister:
    """Run-local, orchestrator-owned. Not thread-safe (PEOS is single-
    threaded, single-run); not cross-run (see SPEC-004 Known Limitations)."""

    entries: dict[str, RegisterEntry] = field(default_factory=dict)

    def record_review_findings(self, origin_review_number: int, findings: tuple) -> None:
        """Add a register entry for every `blocking`/`major` finding in
        `findings` (a `peos.codex_agent.Finding` tuple) that is not
        already present, keyed by this review's own 1-based position in
        its `findings` array -- computed over *every* finding, including
        minor/info ones, so position numbering matches exactly what Codex
        returned even though only blocking/major findings get an entry.
        """
        for position, finding in enumerate(findings, start=1):
            if finding.severity not in _OUTSTANDING_SEVERITIES:
                continue
            ref = FindingRef(origin_review_number=origin_review_number, finding_position=position)
            key = str(ref)
            if key in self.entries:
                continue
            self.entries[key] = RegisterEntry(
                ref=ref, severity=finding.severity,
                description=sanitize_human_text(finding.description),
            )

    def apply_dispositions(self, dispositions: tuple) -> None:
        """Apply a closure review's `historical_finding_dispositions`
        (already schema-validated `HistoricalFindingDisposition` tuple).
        A reference naming an entry not present in the register is
        ignored (not an error here -- `peos/codex_agent.py`'s own
        validation only ever requires well-formed references; cross-
        checking against *this specific run's* register state at
        validation time is intentionally not required by SPEC-004 for
        `historical_finding_dispositions`, unlike dispute references,
        which must name a currently-OUTSTANDING entry).
        """
        for disposition in dispositions:
            key = disposition.reference
            entry = self.entries.get(key)
            if entry is None:
                continue
            entry.outstanding = False
            entry.disposition = disposition.disposition
            entry.disposition_note = disposition.note
            if disposition.disposition == HUMAN_DECISION_REQUIRED:
                entry.human_decision_required_ever = True

    def has_outstanding(self, severities: tuple[str, ...] = _OUTSTANDING_SEVERITIES) -> bool:
        return any(e.outstanding and e.severity in severities for e in self.entries.values())

    def outstanding(self, severities: tuple[str, ...] = _OUTSTANDING_SEVERITIES) -> tuple[RegisterEntry, ...]:
        return tuple(
            e for e in sorted(self.entries.values(), key=lambda e: (e.ref.origin_review_number, e.ref.finding_position))
            if e.outstanding and e.severity in severities
        )

    def has_human_decision_required(self) -> bool:
        return any(e.human_decision_required_ever for e in self.entries.values())

    def get(self, reference: str) -> RegisterEntry | None:
        return self.entries.get(reference)

    def all_entries(self) -> tuple[RegisterEntry, ...]:
        return tuple(
            sorted(self.entries.values(), key=lambda e: (e.ref.origin_review_number, e.ref.finding_position))
        )
