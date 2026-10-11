"""Tests for the Round Packet (peos/round_packet.py, SPEC-004 Requirement
17, AC-37): all ten elements (plus the governance-identity/baseline-commit
elements added by remediation Finding 4's closure review) must be present
and sourced from orchestrator state (ledger/repository), never from a
prior subprocess's captured stdout/transcript.
"""

from peos.codex_agent import Finding, HistoricalFindingDisposition
from peos.findings_register import RESOLVED, FindingsRegister
from peos.round_packet import (
    ActiveDispute,
    StaticContextRef,
    build_round_packet,
    render_historical_dispositions_for_prompt,
    render_round_packet_header,
)


def test_round_packet_carries_all_ten_elements():
    register = FindingsRegister()
    register.record_review_findings(0, (Finding(severity="major", category="missing_test", description="d", requires_human_decision=False),))

    packet = build_round_packet(
        task="implement the thing",
        spec_relative_path="docs/specifications/SPEC-001-x.md",
        spec_content_hash="deadbeef",
        decision_identities=(("docs/decisions/0002-foo.md", "cafef00d"),),
        cycle_number=1,
        max_cycles=3,
        workspace_snapshot_identity="fingerprint123",
        verification_passed=True,
        verification_summary="passed",
        register=register,
        active_disputes=(ActiveDispute(reference="0.1", evidence="it's fine", raised_in_remediation_cycle=1),),
        acceptance_criteria_ids=("AC-1", "AC-2"),
        static_context_artifacts=(StaticContextRef("docs/design/export.json", "docs/design/export.json", "abc123"),),
        governance_identities=(("CLAUDE.md", "claudehash"), ("AGENTS.md", "agentshash"), ("ENGINEERING.md", "enghash")),
        baseline_commit="basecommitsha",
    )

    # 1. task
    assert packet.task == "implement the thing"
    # 2. governing spec path + hash
    assert packet.spec_relative_path == "docs/specifications/SPEC-001-x.md"
    assert packet.spec_content_hash == "deadbeef"
    # 3. decision identities
    assert packet.decision_identities == (("docs/decisions/0002-foo.md", "cafef00d"),)
    # 4. cycle number + remaining budget
    assert packet.cycle_number == 1
    assert packet.max_cycles == 3
    assert packet.remaining_budget == 2
    # 5. workspace snapshot identity
    assert packet.workspace_snapshot_identity == "fingerprint123"
    # 6. verification result/evidence
    assert packet.verification_passed is True
    assert packet.verification_summary == "passed"
    # 7. complete Outstanding Findings Register
    assert len(packet.register_snapshot) == 1
    assert packet.register_snapshot[0].reference == "0.1"
    # 8. active disputes + evidence
    assert len(packet.active_disputes) == 1
    assert packet.active_disputes[0].evidence == "it's fine"
    # 9. complete AC set
    assert packet.acceptance_criteria_ids == ("AC-1", "AC-2")
    # 10. static-context artifacts
    assert len(packet.static_context_artifacts) == 1
    assert packet.static_context_artifacts[0].content_hash == "abc123"
    # 11. governance identities (SPEC-004 remediation Finding 4)
    assert packet.governance_identities == (
        ("CLAUDE.md", "claudehash"), ("AGENTS.md", "agentshash"), ("ENGINEERING.md", "enghash"),
    )
    # 12. authoritative baseline Git commit SHA
    assert packet.baseline_commit == "basecommitsha"


def test_round_packet_remaining_budget_never_negative():
    packet = build_round_packet(
        task="t", spec_relative_path="s", spec_content_hash="h", decision_identities=(),
        cycle_number=5, max_cycles=3, workspace_snapshot_identity="w",
        verification_passed=True, verification_summary="", register=FindingsRegister(),
        active_disputes=(), acceptance_criteria_ids=(), static_context_artifacts=(),
        governance_identities=(), baseline_commit="",
    )
    assert packet.remaining_budget == 0


def test_register_snapshot_is_a_frozen_copy_not_the_live_mutable_register():
    register = FindingsRegister()
    register.record_review_findings(0, (Finding(severity="major", category="missing_test", description="d", requires_human_decision=False),))
    packet = build_round_packet(
        task="t", spec_relative_path="s", spec_content_hash="h", decision_identities=(),
        cycle_number=0, max_cycles=3, workspace_snapshot_identity="w",
        verification_passed=None, verification_summary="", register=register,
        active_disputes=(), acceptance_criteria_ids=(), static_context_artifacts=(),
        governance_identities=(), baseline_commit="",
    )
    # Mutating the live register afterward must not retroactively change
    # a packet already built from it.
    register.entries["0.1"].outstanding = False
    assert packet.register_snapshot[0].outstanding is True


# --- SPEC-004 remediation Finding 4: every element actually renders ----

def test_render_round_packet_header_includes_every_non_register_element():
    packet = build_round_packet(
        task="implement the thing",
        spec_relative_path="docs/specifications/SPEC-001-x.md",
        spec_content_hash="deadbeef",
        decision_identities=(("docs/decisions/0002-foo.md", "cafef00d"),),
        cycle_number=1, max_cycles=3, workspace_snapshot_identity="fingerprint123",
        verification_passed=True, verification_summary="PASSED: pytest",
        register=FindingsRegister(),
        active_disputes=(), acceptance_criteria_ids=("AC-1", "AC-2"),
        static_context_artifacts=(StaticContextRef("docs/design/export.json", "docs/design/export.json", "abc123"),),
        governance_identities=(("CLAUDE.md", "claudehash"), ("AGENTS.md", "agentshash"), ("ENGINEERING.md", "enghash")),
        baseline_commit="basecommitsha",
    )
    header = render_round_packet_header(packet)
    assert "docs/specifications/SPEC-001-x.md" in header
    assert "deadbeef" in header
    assert "docs/decisions/0002-foo.md" in header
    assert "cafef00d" in header
    assert "1" in header and "3" in header  # cycle/max_cycles
    assert "fingerprint123" in header
    assert "PASSED: pytest" in header
    assert "AC-1" in header and "AC-2" in header
    assert "docs/design/export.json" in header
    assert "abc123" in header
    # Governance identities + baseline commit (SPEC-004 remediation Finding 4).
    assert "CLAUDE.md" in header and "claudehash" in header
    assert "AGENTS.md" in header and "agentshash" in header
    assert "ENGINEERING.md" in header and "enghash" in header
    assert "basecommitsha" in header


def test_render_round_packet_header_represents_no_verification_yet_explicitly():
    packet = build_round_packet(
        task="t", spec_relative_path="s", spec_content_hash="h", decision_identities=(),
        cycle_number=0, max_cycles=3, workspace_snapshot_identity="w",
        verification_passed=None, verification_summary="", register=FindingsRegister(),
        active_disputes=(), acceptance_criteria_ids=(), static_context_artifacts=(),
        governance_identities=(), baseline_commit="",
    )
    header = render_round_packet_header(packet)
    assert "no deterministic verification result yet" in header


def test_render_historical_dispositions_shows_resolved_entries_not_only_outstanding():
    register = FindingsRegister()
    register.record_review_findings(0, (
        Finding(severity="major", category="missing_test", description="fixable", requires_human_decision=False),
    ))
    register.apply_dispositions(
        (HistoricalFindingDisposition(reference="0.1", disposition=RESOLVED, note="fixed in cycle 1"),),
    )
    packet = build_round_packet(
        task="t", spec_relative_path="s", spec_content_hash="h", decision_identities=(),
        cycle_number=1, max_cycles=3, workspace_snapshot_identity="w",
        verification_passed=True, verification_summary="", register=register,
        active_disputes=(), acceptance_criteria_ids=(), static_context_artifacts=(),
        governance_identities=(), baseline_commit="",
    )
    rendered = render_historical_dispositions_for_prompt(packet)
    assert "0.1" in rendered
    assert RESOLVED in rendered
    assert "fixed in cycle 1" in rendered
    assert "fixable" in rendered


def test_render_historical_dispositions_empty_when_nothing_closed_yet():
    packet = build_round_packet(
        task="t", spec_relative_path="s", spec_content_hash="h", decision_identities=(),
        cycle_number=0, max_cycles=3, workspace_snapshot_identity="w",
        verification_passed=None, verification_summary="", register=FindingsRegister(),
        active_disputes=(), acceptance_criteria_ids=(), static_context_artifacts=(),
        governance_identities=(), baseline_commit="",
    )
    assert "no historical finding has been dispositioned yet" in render_historical_dispositions_for_prompt(packet)
