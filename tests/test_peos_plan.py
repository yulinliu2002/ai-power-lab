"""Tests for Planning (peos/plan.py, SPEC-004 Requirement 2, remediated
per SPEC-004 remediation Finding 1)."""

import hashlib
from pathlib import Path

from peos.plan import build_plan, parse_acceptance_criteria_ids, parse_max_cycles_override
from peos.spec import SpecCandidate, SpecResolution


def test_parse_max_cycles_override_valid_value():
    text = "# SPEC-X\n\nMax Cycles Override: 4\n"
    assert parse_max_cycles_override(text) == 4


def test_parse_max_cycles_override_absent_returns_none():
    assert parse_max_cycles_override("# SPEC-X\n\nNothing here.\n") is None


def test_parse_max_cycles_override_out_of_range_is_ignored_not_an_error():
    assert parse_max_cycles_override("Max Cycles Override: 99\n") is None
    assert parse_max_cycles_override("Max Cycles Override: 0\n") is None


def test_parse_acceptance_criteria_ids_heading_style():
    text = (
        "## 15. Acceptance Criteria\n\n"
        "### AC-001 -- Single Entry Point\n\nbody\n\n"
        "### AC-002 -- Specification Enforcement\n\nbody\n"
    )
    assert parse_acceptance_criteria_ids(text) == ("AC-001", "AC-002")


def test_parse_acceptance_criteria_ids_bullet_style():
    text = (
        "## Acceptance Criteria\n\n"
        "- [ ] **AC-1** does a thing\n"
        "- [ ] **AC-1b** does another thing\n"
        "- [ ] **AC-2** does a third thing\n"
    )
    assert parse_acceptance_criteria_ids(text) == ("AC-1", "AC-1b", "AC-2")


def test_parse_acceptance_criteria_ids_deduplicates_cross_references():
    text = (
        "## Acceptance Criteria\n\n"
        "- [ ] **AC-1** does a thing (see also AC-1 above)\n"
        "- [ ] **AC-1** duplicate line, should not double count\n"
    )
    assert parse_acceptance_criteria_ids(text) == ("AC-1",)


def test_parse_acceptance_criteria_ids_empty_when_none_declared():
    assert parse_acceptance_criteria_ids("# SPEC-X\n\n**Status:** Approved\n\nbody\n") == ()


def _resolver_returns(spec):
    def resolver(task, specs_dir, explicit_spec):
        return SpecResolution(spec=spec)
    return resolver


def _resolver_gates(reason):
    def resolver(task, specs_dir, explicit_spec):
        return SpecResolution(gate_reason=reason)
    return resolver


def test_build_plan_stops_at_spec_resolution_gate_without_further_parsing(tmp_path):
    plan = build_plan("task", tmp_path, None, tmp_path, spec_resolver=_resolver_gates("no spec"))
    assert plan.resolution.spec is None
    assert plan.max_cycles_override is None
    assert plan.static_context.declared == ()
    assert plan.governing_spec_content_hash == ""


def test_build_plan_extracts_max_cycles_override_and_ac_ids(tmp_path):
    spec_path = tmp_path / "SPEC-X.md"
    spec_path.write_text(
        "# SPEC-X\n\n**Status:** Approved\n\nMax Cycles Override: 2\n\n"
        "## Acceptance Criteria\n\n- [ ] **AC-1** thing\n",
        encoding="utf-8",
    )
    candidate = SpecCandidate(path=spec_path, title="X", status="Approved")
    plan = build_plan("task", tmp_path, None, tmp_path, spec_resolver=_resolver_returns(candidate))
    assert plan.max_cycles_override == 2
    assert plan.acceptance_criteria_ids == ("AC-1",)
    assert plan.static_context.declared == ()
    assert plan.governing_spec_content_hash == hashlib.sha256(spec_path.read_bytes()).hexdigest()


# --- SPEC-004 remediation Finding 1: identity hash is the exact bytes --

def test_governing_spec_content_hash_is_the_exact_bytes_parsed_not_a_re_read(tmp_path):
    """The identity hash and the parsed `spec_text` must come from one
    read of one set of bytes -- never two independent reads that could,
    in principle, observe different content if the file changed between
    them.
    """
    spec_path = tmp_path / "SPEC-X.md"
    original_bytes = "# SPEC-X\n\n**Status:** Approved\n\nbody\n".encode("utf-8")
    spec_path.write_bytes(original_bytes)
    candidate = SpecCandidate(path=spec_path, title="X", status="Approved")

    plan = build_plan("task", tmp_path, None, tmp_path, spec_resolver=_resolver_returns(candidate))

    assert plan.governing_spec_content_hash == hashlib.sha256(original_bytes).hexdigest()

    # Mutating the file afterward must not retroactively change the
    # already-computed Planning identity -- it is frozen, not a live
    # property.
    spec_path.write_bytes(original_bytes + b"\nmutated\n")
    assert plan.governing_spec_content_hash == hashlib.sha256(original_bytes).hexdigest()
