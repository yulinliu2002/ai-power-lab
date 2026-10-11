"""Tests for DISPUTE[...] line parsing (peos/workflow_disputes.py,
SPEC-004 Requirement 8, AC-22/AC-23) and its SPEC-004 remediation Finding
6 fix (a dispute attempt surviving Claude's own whole-summary bounding).
"""

from peos.codex_agent import Finding
from peos.diagnostics import MAX_DIAGNOSTIC_CHARS
from peos.findings_register import FindingsRegister
from peos.workflow_disputes import extract_dispute_attempt_lines, parse_disputes_from_summary


def _register_with_one_outstanding():
    register = FindingsRegister()
    register.record_review_findings(0, (Finding(severity="major", category="missing_test", description="d", requires_human_decision=False),))
    return register


def _lines(summary: str) -> tuple[str, ...]:
    """Mirror production usage: `peos.claude_agent.run_claude` always
    extracts dispute-attempt lines first and passes that tuple to
    `parse_disputes_from_summary`, never the raw summary string itself.
    """
    return extract_dispute_attempt_lines(summary)


def test_no_dispute_line_is_simply_no_dispute():
    register = _register_with_one_outstanding()
    disputes, error = parse_disputes_from_summary(_lines("Fixed everything, no disputes here."), register)
    assert error is None
    assert disputes == ()


def test_well_formed_dispute_line_parses_successfully():
    register = _register_with_one_outstanding()
    summary = "Did some work.\nDISPUTE[0.1]: this is already fixed, see test_foo.\nDone."
    disputes, error = parse_disputes_from_summary(_lines(summary), register)
    assert error is None
    assert len(disputes) == 1
    assert disputes[0].reference == "0.1"
    assert "already fixed" in disputes[0].evidence


def test_malformed_index_syntax_is_a_parse_error_ac22():
    register = _register_with_one_outstanding()
    disputes, error = parse_disputes_from_summary(_lines("DISPUTE[abc]: bad reference"), register)
    assert disputes == ()
    assert error is not None
    assert "malformed" in error.reason


def test_wrong_delimiter_is_a_parse_error_ac22():
    register = _register_with_one_outstanding()
    disputes, error = parse_disputes_from_summary(_lines("DISPUTE[0,1]: wrong delimiter"), register)
    assert error is not None


def test_unknown_reference_is_a_parse_error_ac22():
    register = _register_with_one_outstanding()
    disputes, error = parse_disputes_from_summary(_lines("DISPUTE[5.9]: nonexistent finding"), register)
    assert error is not None
    assert "unknown" in error.reason


def test_non_outstanding_reference_is_a_parse_error_ac22():
    register = _register_with_one_outstanding()
    register.entries["0.1"].outstanding = False
    disputes, error = parse_disputes_from_summary(_lines("DISPUTE[0.1]: already closed"), register)
    assert error is not None
    assert "non-outstanding" in error.reason


def test_empty_evidence_is_a_parse_error_ac22_ac23():
    register = _register_with_one_outstanding()
    disputes, error = parse_disputes_from_summary(_lines("DISPUTE[0.1]:"), register)
    assert error is not None


def test_whitespace_only_evidence_is_a_parse_error_ac23():
    register = _register_with_one_outstanding()
    disputes, error = parse_disputes_from_summary(_lines("DISPUTE[0.1]:    \t  "), register)
    assert error is not None


def test_multiple_valid_disputes_in_one_summary():
    register = FindingsRegister()
    register.record_review_findings(0, (
        Finding(severity="major", category="missing_test", description="d1", requires_human_decision=False),
        Finding(severity="major", category="missing_test", description="d2", requires_human_decision=False),
    ))
    summary = "DISPUTE[0.1]: evidence one\nDISPUTE[0.2]: evidence two"
    disputes, error = parse_disputes_from_summary(_lines(summary), register)
    assert error is None
    assert {d.reference for d in disputes} == {"0.1", "0.2"}


# --- SPEC-004 remediation Finding 6: survives whole-summary bounding ----

def test_extract_dispute_attempt_lines_ignores_non_dispute_text():
    summary = "Line one.\nDISPUTE[0.1]: evidence here.\nLine three, not a dispute."
    assert extract_dispute_attempt_lines(summary) == ("DISPUTE[0.1]: evidence here.",)


def test_well_formed_dispute_at_the_start_of_an_over_length_summary_is_not_lost():
    """Reproduces the exact Finding 6 failure mechanism: a well-formed
    DISPUTE[...] line sits at the very start of a summary long enough
    that `peos.diagnostics.sanitize_human_text`'s whole-string `bound()`
    (keeps the *tail*) would, if applied before dispute extraction,
    discard the dispute line entirely. `extract_dispute_attempt_lines`
    is what `peos.claude_agent.run_claude` calls on the *raw* summary,
    before that destructive bound -- so the dispute attempt must still
    be found and must still parse successfully here.
    """
    register = _register_with_one_outstanding()
    padding = "x" * (MAX_DIAGNOSTIC_CHARS + 500)
    summary = f"DISPUTE[0.1]: this is already fixed, see test_foo.\n{padding}"
    assert len(summary) > MAX_DIAGNOSTIC_CHARS  # the whole-string bound would discard the dispute line

    lines = extract_dispute_attempt_lines(summary)
    assert lines == ("DISPUTE[0.1]: this is already fixed, see test_foo.",)

    disputes, error = parse_disputes_from_summary(lines, register)
    assert error is None
    assert len(disputes) == 1
    assert disputes[0].reference == "0.1"


def test_malformed_dispute_at_the_start_of_an_over_length_summary_still_fails_closed():
    """The companion case: a *malformed* dispute attempt (same shape as
    `test_malformed_index_syntax_is_a_parse_error_ac22`) buried at the
    start of an over-length summary must still be detected and rejected
    -- not silently swallowed into "no dispute attempted" by the
    surrounding summary's own truncation.
    """
    register = _register_with_one_outstanding()
    padding = "y" * (MAX_DIAGNOSTIC_CHARS + 500)
    summary = f"DISPUTE[abc]: malformed reference\n{padding}"

    lines = extract_dispute_attempt_lines(summary)
    assert lines == ("DISPUTE[abc]: malformed reference",)

    disputes, error = parse_disputes_from_summary(lines, register)
    assert disputes == ()
    assert error is not None
    assert "malformed" in error.reason
