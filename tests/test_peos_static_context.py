"""Tests for the Static External Context mechanism (peos/static_context.py,
SPEC-004 Requirement 21).

AC-6/AC-32 (missing/wrong-type declared artifact), AC-7 (resolved
artifact), AC-33 (containment violation fails closed, never gates),
AC-39 (identity drift fails closed before the next invocation).
"""

import shutil
from pathlib import Path

from peos.static_context import (
    parse_static_context_declaration,
    resolve_static_context,
    reverify_identity,
    stage_into_workspace,
)

_SPEC_TEMPLATE = """# SPEC-X

## Design Context

Required artifacts:

    {path}

## Verification

    python -m pytest -q
"""


def test_parse_static_context_declaration_extracts_indented_lines_under_the_heading():
    text = _SPEC_TEMPLATE.format(path="docs/design/export.json")
    assert parse_static_context_declaration(text) == ("docs/design/export.json",)


def test_parse_static_context_declaration_returns_empty_when_no_section():
    assert parse_static_context_declaration("# SPEC-X\n\nNo design context here.\n") == ()


def test_ac6_missing_artifact_gates_not_fails(tmp_path):
    spec_text = _SPEC_TEMPLATE.format(path="docs/design/missing.json")
    resolution = resolve_static_context(tmp_path, spec_text)
    assert resolution.gate_reason is not None
    assert resolution.fail_reason is None
    assert "missing.json" in resolution.gate_reason


def test_ac32_directory_instead_of_file_gates_not_fails(tmp_path):
    (tmp_path / "docs" / "design").mkdir(parents=True)
    spec_text = _SPEC_TEMPLATE.format(path="docs/design")
    resolution = resolve_static_context(tmp_path, spec_text)
    assert resolution.gate_reason is not None
    assert resolution.fail_reason is None


def test_ac7_resolved_artifact_records_path_and_content_identity(tmp_path):
    (tmp_path / "docs" / "design").mkdir(parents=True)
    artifact_path = tmp_path / "docs" / "design" / "export.json"
    artifact_path.write_text('{"a": 1}', encoding="utf-8")

    spec_text = _SPEC_TEMPLATE.format(path="docs/design/export.json")
    resolution = resolve_static_context(tmp_path, spec_text)
    assert resolution.ok
    assert len(resolution.artifacts) == 1
    artifact = resolution.artifacts[0]
    assert artifact.declared_path == "docs/design/export.json"
    assert artifact.resolved_path == artifact_path
    assert len(artifact.content_hash) == 64  # sha256 hex digest


def test_ac33_path_escaping_repo_root_via_dotdot_fails_not_gates(tmp_path):
    outside = tmp_path.parent / "outside_secret.json"
    outside.write_text("secret", encoding="utf-8")
    spec_text = _SPEC_TEMPLATE.format(path="../outside_secret.json")

    resolution = resolve_static_context(tmp_path, spec_text)
    assert resolution.fail_reason is not None
    assert resolution.gate_reason is None


def test_ac33_symlink_component_fails_not_gates(tmp_path):
    (tmp_path / "docs").mkdir()
    real_target_dir = tmp_path.parent / "real_target"
    real_target_dir.mkdir()
    (real_target_dir / "export.json").write_text("{}", encoding="utf-8")
    (tmp_path / "docs" / "design").symlink_to(real_target_dir)

    spec_text = _SPEC_TEMPLATE.format(path="docs/design/export.json")
    resolution = resolve_static_context(tmp_path, spec_text)
    assert resolution.fail_reason is not None
    assert resolution.gate_reason is None


def test_ac39_identity_drift_after_staging_fails_closed(tmp_path):
    (tmp_path / "docs" / "design").mkdir(parents=True)
    artifact_path = tmp_path / "docs" / "design" / "export.json"
    artifact_path.write_text('{"a": 1}', encoding="utf-8")
    spec_text = _SPEC_TEMPLATE.format(path="docs/design/export.json")

    resolution = resolve_static_context(tmp_path, spec_text)
    assert resolution.ok
    artifact = resolution.artifacts[0]

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    staged = stage_into_workspace(workspace, artifact, tmp_path)

    # No drift yet.
    assert reverify_identity(staged, tmp_path, workspace).ok

    # Mutate the authoritative copy -- content identity B != pinned A.
    artifact_path.write_text('{"a": 2}', encoding="utf-8")
    drift = reverify_identity(staged, tmp_path, workspace)
    assert not drift.ok
    assert "drifted" in drift.reason


def test_f5_staged_copy_replaced_by_matching_content_symlink_fails_closed(tmp_path):
    """SPEC-004 remediation Finding 5: a staged copy that is byte-for-byte
    identical to the authoritative artifact is still rejected if it is a
    symlink (here, pointing straight at the authoritative file itself,
    guaranteeing identical bytes) -- matching content is not sufficient;
    the staged path must also be structurally a regular file with no
    symlink at any component.
    """
    (tmp_path / "docs" / "design").mkdir(parents=True)
    artifact_path = tmp_path / "docs" / "design" / "export.json"
    artifact_path.write_text('{"a": 1}', encoding="utf-8")
    spec_text = _SPEC_TEMPLATE.format(path="docs/design/export.json")

    resolution = resolve_static_context(tmp_path, spec_text)
    assert resolution.ok
    artifact = resolution.artifacts[0]

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    staged = stage_into_workspace(workspace, artifact, tmp_path)
    assert reverify_identity(staged, tmp_path, workspace).ok

    # Replace the staged copy with a symlink to the authoritative file --
    # same bytes, same hash, but the staged path is no longer a regular
    # file.
    staged_path = workspace / staged.staged_relative_path
    staged_path.unlink()
    staged_path.symlink_to(artifact_path)

    drift = reverify_identity(staged, tmp_path, workspace)
    assert not drift.ok
    assert "symlink" in drift.reason.lower()


def test_f5_staged_parent_directory_replaced_by_symlink_fails_closed(tmp_path):
    """SPEC-004 remediation Finding 5: a symlink at an *ancestor* of the
    staged path (not only the final file) must also be rejected.
    """
    (tmp_path / "docs" / "design").mkdir(parents=True)
    artifact_path = tmp_path / "docs" / "design" / "export.json"
    artifact_path.write_text('{"a": 1}', encoding="utf-8")
    spec_text = _SPEC_TEMPLATE.format(path="docs/design/export.json")

    resolution = resolve_static_context(tmp_path, spec_text)
    artifact = resolution.artifacts[0]

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    staged = stage_into_workspace(workspace, artifact, tmp_path)
    assert reverify_identity(staged, tmp_path, workspace).ok

    staged_parent = workspace / "docs" / "design"
    shutil.rmtree(staged_parent)
    staged_parent.symlink_to(artifact_path.parent, target_is_directory=True)

    drift = reverify_identity(staged, tmp_path, workspace)
    assert not drift.ok
    assert "symlink" in drift.reason.lower()


def test_ac39_staged_copy_mismatch_also_fails_closed(tmp_path):
    (tmp_path / "docs" / "design").mkdir(parents=True)
    artifact_path = tmp_path / "docs" / "design" / "export.json"
    artifact_path.write_text('{"a": 1}', encoding="utf-8")
    spec_text = _SPEC_TEMPLATE.format(path="docs/design/export.json")

    resolution = resolve_static_context(tmp_path, spec_text)
    artifact = resolution.artifacts[0]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    staged = stage_into_workspace(workspace, artifact, tmp_path)

    # Corrupt only the staged copy, leaving the authoritative file intact.
    (workspace / staged.staged_relative_path).write_text("corrupted", encoding="utf-8")
    drift = reverify_identity(staged, tmp_path, workspace)
    assert not drift.ok
    assert "staged" in drift.reason.lower()
