"""Tests for peos/runtime_plan.py (SPEC-006 Sections 8/10/13/15).

AC-001/AC-002 (no-op vs. populated plan), AC-026-028 (Human Gate #12 for
unrecognized kind / missing parameter / orphaned ac=), AC-048 (per-round
check-count bound).
"""

from peos.runtime_catalog import ExperimentRunParams, PageLoadParams, ViewportOverflowParams
from peos.runtime_plan import (
    build_runtime_plan,
    parse_runtime_verification_declarations,
    runtime_evidenced_ac_ids,
)

_SPEC_TEMPLATE = """# SPEC-X

## Acceptance Criteria

- [ ] **AC-001** page load works
- [ ] **AC-002** experiment works
- [ ] **AC-012** no overflow

## Verification Requirements

### Runtime Verification

{body}
"""


def test_no_declaration_produces_empty_plan():
    plan = build_runtime_plan("# SPEC-X\n\nNo runtime section here.\n", ("AC-001",))
    assert plan.ok
    assert plan.declarations == ()


def test_parses_page_load_declaration():
    text = _SPEC_TEMPLATE.format(
        body='    runtime: page_load path=/ landmarks="A,B,C" ac=AC-001'
    )
    declarations = parse_runtime_verification_declarations(text)
    assert len(declarations) == 1
    assert declarations[0].kind == "page_load"

    plan = build_runtime_plan(text, ("AC-001", "AC-002", "AC-012"))
    assert plan.ok, plan.gate_reason
    assert len(plan.declarations) == 1
    decl = plan.declarations[0]
    assert decl.kind == "page_load"
    assert decl.related_ac_ids == ("AC-001",)
    assert isinstance(decl.params, PageLoadParams)
    assert decl.params.path == "/"
    assert decl.params.landmarks == ("A", "B", "C")


def test_parses_experiment_run_declaration():
    text = _SPEC_TEMPLATE.format(
        body='    runtime: experiment_run final_fraction=0.45 selector="[data-testid=x]" ac=AC-002'
    )
    plan = build_runtime_plan(text, ("AC-001", "AC-002", "AC-012"))
    assert plan.ok, plan.gate_reason
    decl = plan.declarations[0]
    assert isinstance(decl.params, ExperimentRunParams)
    assert decl.params.final_fraction == 0.45
    assert decl.params.selector == "[data-testid=x]"


def test_parses_viewport_overflow_with_preset():
    text = _SPEC_TEMPLATE.format(body="    runtime: viewport_overflow viewport=mobile ac=AC-012")
    plan = build_runtime_plan(text, ("AC-001", "AC-002", "AC-012"))
    assert plan.ok, plan.gate_reason
    decl = plan.declarations[0]
    assert isinstance(decl.params, ViewportOverflowParams)
    assert decl.params.viewport == "mobile"
    assert decl.params.resolve_dimensions() == (390, 844)


def test_parses_viewport_overflow_with_explicit_dimensions():
    text = _SPEC_TEMPLATE.format(body="    runtime: viewport_overflow width=1024 height=768 ac=AC-012")
    plan = build_runtime_plan(text, ("AC-001", "AC-002", "AC-012"))
    assert plan.ok, plan.gate_reason
    decl = plan.declarations[0]
    assert decl.params.resolve_dimensions() == (1024, 768)


def test_multiple_ac_references_on_one_line():
    text = _SPEC_TEMPLATE.format(body="    runtime: viewport_overflow viewport=desktop ac=AC-012 ac=AC-001")
    plan = build_runtime_plan(text, ("AC-001", "AC-002", "AC-012"))
    assert plan.ok, plan.gate_reason
    assert plan.declarations[0].related_ac_ids == ("AC-012", "AC-001")
    assert runtime_evidenced_ac_ids(plan) == frozenset({"AC-012", "AC-001"})


def test_ac026_unrecognized_kind_gates_human_gate_12():
    text = _SPEC_TEMPLATE.format(body="    runtime: open_arbitrary_url url=https://evil.example ac=AC-001")
    plan = build_runtime_plan(text, ("AC-001",))
    assert not plan.ok
    assert "open_arbitrary_url" in plan.gate_reason


def test_ac027_missing_required_parameter_gates_human_gate_12():
    text = _SPEC_TEMPLATE.format(body="    runtime: experiment_run selector=\"[data-testid=x]\" ac=AC-002")
    plan = build_runtime_plan(text, ("AC-001", "AC-002"))
    assert not plan.ok
    assert "final_fraction" in plan.gate_reason


def test_ac028_orphaned_ac_reference_gates_human_gate_12():
    text = _SPEC_TEMPLATE.format(body="    runtime: viewport_overflow viewport=mobile ac=AC-999")
    plan = build_runtime_plan(text, ("AC-001", "AC-002", "AC-012"))
    assert not plan.ok
    assert "AC-999" in plan.gate_reason


def test_viewport_overflow_rejects_both_preset_and_explicit_dimensions():
    text = _SPEC_TEMPLATE.format(
        body="    runtime: viewport_overflow viewport=mobile width=1024 height=768 ac=AC-012"
    )
    plan = build_runtime_plan(text, ("AC-001", "AC-002", "AC-012"))
    assert not plan.ok


def test_ac048_declaring_more_than_the_cap_gates_human_gate_12():
    lines = "\n".join(f"    runtime: viewport_overflow viewport=mobile ac=AC-012" for _ in range(21))
    text = _SPEC_TEMPLATE.format(body=lines)
    plan = build_runtime_plan(text, ("AC-001", "AC-002", "AC-012"))
    assert not plan.ok
    assert "21" in plan.gate_reason


def test_exactly_the_cap_is_accepted():
    lines = "\n".join(f"    runtime: viewport_overflow viewport=mobile ac=AC-012" for _ in range(20))
    text = _SPEC_TEMPLATE.format(body=lines)
    plan = build_runtime_plan(text, ("AC-001", "AC-002", "AC-012"))
    assert plan.ok, plan.gate_reason
    assert len(plan.declarations) == 20


def test_wrapped_prose_continuation_line_is_not_treated_as_a_declaration():
    """Mirrors peos/verification_plan.py's own SPEC-005-dogfood
    regression test: a wrapped list-item continuation line that merely
    lands at column >=4 must never be parsed as a declaration."""
    text = (
        "# SPEC-X\n\n## Verification Requirements\n\n### Runtime Verification\n\n"
        "- A manual check that wraps\n"
        "    onto a second physical line indented past column four.\n"
    )
    assert parse_runtime_verification_declarations(text) == ()
