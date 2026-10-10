"""Tests for governing-specification resolution (peos/spec.py)."""

from pathlib import Path

import pytest

from peos.spec import list_specs, resolve_governing_spec


def _write_spec(dir_: Path, filename: str, title: str, status: str) -> Path:
    path = dir_ / filename
    path.write_text(f"# {title}\n\n**Status:** {status}\n\nbody\n", encoding="utf-8")
    return path


@pytest.fixture
def specs_dir(tmp_path: Path) -> Path:
    d = tmp_path / "docs" / "specifications"
    d.mkdir(parents=True)
    (d / "TEMPLATE.md").write_text("# SPEC-NNN — <Title>\n\n**Status:** Draft\n", encoding="utf-8")
    return d


def test_list_specs_excludes_template(specs_dir: Path):
    _write_spec(specs_dir, "SPEC-001-foo.md", "SPEC-001 -- Foo", "Approved")
    candidates = list_specs(specs_dir)
    assert len(candidates) == 1
    assert candidates[0].path.name == "SPEC-001-foo.md"
    assert candidates[0].status == "Approved"


def test_explicit_spec_must_exist(tmp_path: Path, specs_dir: Path):
    missing = specs_dir / "SPEC-999-missing.md"
    result = resolve_governing_spec("do something", specs_dir, explicit_spec=missing)
    assert result.spec is None
    assert "does not exist" in result.gate_reason


def test_explicit_spec_must_be_approved(specs_dir: Path):
    draft = _write_spec(specs_dir, "SPEC-002-draft.md", "SPEC-002 -- Draft thing", "Draft")
    result = resolve_governing_spec("do something", specs_dir, explicit_spec=draft)
    assert result.spec is None
    assert "not Approved" in result.gate_reason


def test_explicit_approved_spec_is_used_directly(specs_dir: Path):
    approved = _write_spec(specs_dir, "SPEC-003-thing.md", "SPEC-003 -- Thing", "Approved")
    result = resolve_governing_spec("unrelated task text", specs_dir, explicit_spec=approved)
    assert result.spec is not None
    assert result.spec.path == approved


def test_no_approved_spec_gates(specs_dir: Path):
    _write_spec(specs_dir, "SPEC-004-thing.md", "SPEC-004 -- Thing", "Draft")
    result = resolve_governing_spec("implement thing", specs_dir)
    assert result.spec is None
    assert "No approved specification" in result.gate_reason


def test_unambiguous_auto_match(specs_dir: Path):
    _write_spec(specs_dir, "SPEC-005-scenario-a.md", "SPEC-005 -- Scenario A Experiment", "Approved")
    _write_spec(specs_dir, "SPEC-006-thermal.md", "SPEC-006 -- Thermal Protection", "Approved")
    result = resolve_governing_spec("Implement Scenario A comparative experiment", specs_dir)
    assert result.spec is not None
    assert result.spec.path.name == "SPEC-005-scenario-a.md"


def test_no_keyword_overlap_gates(specs_dir: Path):
    _write_spec(specs_dir, "SPEC-007-scenario-a.md", "SPEC-007 -- Scenario A Experiment", "Approved")
    result = resolve_governing_spec("completely unrelated xyz qux", specs_dir)
    assert result.spec is None
    assert "Could not identify" in result.gate_reason


def test_ambiguous_match_gates(specs_dir: Path):
    _write_spec(specs_dir, "SPEC-008-grid-fault.md", "SPEC-008 -- Grid Fault Response", "Approved")
    _write_spec(specs_dir, "SPEC-009-grid-recovery.md", "SPEC-009 -- Grid Recovery Behavior", "Approved")
    result = resolve_governing_spec("grid", specs_dir)
    assert result.spec is None
    assert "ambiguous" in result.gate_reason.lower()
