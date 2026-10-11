"""Tests for the Outstanding Findings Register (peos/findings_register.py,
SPEC-004 Requirement 16).

AC-18/AC-19/AC-38 directly: a historical BLOCKER/MAJOR finding must never
disappear from `OUTSTANDING` by omission or a silent severity downgrade,
and `HUMAN_DECISION_REQUIRED` must be sticky and terminally
non-converged.
"""

from peos.codex_agent import Finding, HistoricalFindingDisposition
from peos.findings_register import (
    ACCEPTED_RECLASSIFICATION,
    HUMAN_DECISION_REQUIRED,
    RESOLVED,
    FindingRef,
    FindingsRegister,
)


def _major(description="x", requires_human_decision=False):
    return Finding(severity="major", category="missing_test", description=description, requires_human_decision=requires_human_decision)


def _minor(description="y"):
    return Finding(severity="minor", category="non_blocking_improvement", description=description, requires_human_decision=False)


def _blocking(description="z"):
    return Finding(severity="blocking", category="implementation_defect", description=description, requires_human_decision=False)


def test_finding_ref_str_and_parse_roundtrip():
    ref = FindingRef(origin_review_number=2, finding_position=1)
    assert str(ref) == "2.1"
    assert FindingRef.parse("2.1") == ref
    assert FindingRef.parse("not-a-ref") is None
    assert FindingRef.parse("2.1.3") is None


def test_record_review_findings_only_tracks_blocking_and_major_but_preserves_position_numbering():
    register = FindingsRegister()
    register.record_review_findings(0, (_major("m1"), _minor("skip"), _blocking("b1")))
    entries = register.all_entries()
    assert [str(e.ref) for e in entries] == ["0.1", "0.3"]
    assert register.get("0.2") is None


def test_omission_never_closes_a_finding_ac18():
    """AC-18: a finding raised at blocking severity, left unmentioned in
    every subsequent review's historical_finding_dispositions, remains
    OUTSTANDING through every later cycle and blocks APPROVE even though
    that cycle's own findings list is empty.
    """
    register = FindingsRegister()
    register.record_review_findings(0, (_blocking("original issue"),))
    assert register.has_outstanding()

    # A later review raises nothing new and dispositions nothing.
    register.record_review_findings(1, ())
    register.apply_dispositions(())
    assert register.has_outstanding()
    assert str(register.outstanding()[0].ref) == "0.1"


def test_silent_severity_downgrade_does_not_close_a_finding_ac19():
    """AC-19: a finding raised at blocking severity on one cycle,
    re-reported by a later review as a *new*, differently-worded minor
    finding with no ACCEPTED_RECLASSIFICATION disposition referencing the
    original, leaves the original reference OUTSTANDING at blocking
    severity.
    """
    register = FindingsRegister()
    register.record_review_findings(0, (_blocking("the real issue"),))
    # Cycle 1's review re-reports a reworded, milder version as a *new* finding.
    register.record_review_findings(1, (_minor("a milder rewording of the same thing"),))
    assert register.has_outstanding(severities=("blocking", "major"))
    entry = register.get("0.1")
    assert entry.outstanding
    assert entry.severity == "blocking"


def test_explicit_resolved_disposition_closes_a_finding():
    register = FindingsRegister()
    register.record_review_findings(0, (_major("fixable"),))
    register.apply_dispositions((HistoricalFindingDisposition(reference="0.1", disposition=RESOLVED, note="fixed"),))
    assert not register.has_outstanding()
    assert register.get("0.1").disposition == RESOLVED


def test_accepted_reclassification_closes_outstanding_but_is_a_distinct_disposition():
    register = FindingsRegister()
    register.record_review_findings(0, (_major("actually minor"),))
    register.apply_dispositions(
        (HistoricalFindingDisposition(reference="0.1", disposition=ACCEPTED_RECLASSIFICATION, note="downgraded"),)
    )
    assert not register.has_outstanding()
    assert register.get("0.1").disposition == ACCEPTED_RECLASSIFICATION
    assert not register.has_human_decision_required()


def test_human_decision_required_clears_outstanding_but_is_terminally_non_converged_ac38():
    """AC-38: HUMAN_DECISION_REQUIRED clears OUTSTANDING the same way
    RESOLVED/ACCEPTED_RECLASSIFICATION do, but is separately, permanently
    recorded -- `has_human_decision_required()` stays true even after the
    OUTSTANDING flag clears.
    """
    register = FindingsRegister()
    register.record_review_findings(0, (_major("needs a human"),))
    register.apply_dispositions(
        (HistoricalFindingDisposition(reference="0.1", disposition=HUMAN_DECISION_REQUIRED, note="architecture call"),)
    )
    assert not register.has_outstanding()  # cleared
    assert register.has_human_decision_required()  # but never resolved


def test_human_decision_required_is_sticky_across_a_later_disposition_on_the_same_reference():
    """"There is no later disposition that un-sets a HUMAN_DECISION_
    REQUIRED record within the same run" -- even if a later review tries
    to mark the same reference RESOLVED, the sticky flag must remain set.
    """
    register = FindingsRegister()
    register.record_review_findings(0, (_major("needs a human"),))
    register.apply_dispositions(
        (HistoricalFindingDisposition(reference="0.1", disposition=HUMAN_DECISION_REQUIRED, note="architecture call"),)
    )
    register.apply_dispositions(
        (HistoricalFindingDisposition(reference="0.1", disposition=RESOLVED, note="human resolved it"),)
    )
    assert register.has_human_decision_required()


def test_disposition_referencing_unknown_entry_is_silently_ignored_not_an_error():
    register = FindingsRegister()
    register.record_review_findings(0, (_major("real"),))
    # Should not raise, should not affect the real entry.
    register.apply_dispositions((HistoricalFindingDisposition(reference="9.9", disposition=RESOLVED, note="n/a"),))
    assert register.has_outstanding()


def test_all_entries_is_sorted_by_origin_then_position():
    register = FindingsRegister()
    register.record_review_findings(1, (_major("later-origin"),))
    register.record_review_findings(0, (_major("a"), _blocking("b")))
    refs = [str(e.ref) for e in register.all_entries()]
    assert refs == ["0.1", "0.2", "1.1"]
