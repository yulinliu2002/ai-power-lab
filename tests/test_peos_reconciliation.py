"""Tests for the manifest-based reconciliation mechanism (SPEC-007
"Reconciliation Crash-Safety")."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from peos.checkpoint import ReconciliationOperation
from peos.sandbox import (
    apply_reconciliation_operation,
    build_reconciliation_manifest,
    cleanup_reconciliation_debris,
    create_isolated_workspace,
    discard_workspace,
    is_reconciliation_debris_name,
    reconcile_workspace_to_repo,
    ReconciliationConflictError,
)

from tests._peos_fixtures import make_minimal_repo


def test_manifest_write_operation_is_applied_atomically_via_temp_file_and_rename(tmp_path, monkeypatch):
    """Codex implementation review (confirmed, minor): an earlier
    revision of this test only checked the final content and the
    absence of leftover debris -- an in-place, non-atomic write would
    have passed it too. Instrumented here instead: `os.open` must be
    called with this run's own recognized debris-naming convention
    (never the destination path directly), and `os.replace` must be
    the actual rename call, in that order -- proving the real mechanism,
    not just its eventual result.
    """
    import peos.sandbox as sandbox_module

    repo_root = make_minimal_repo(tmp_path)
    workspace = create_isolated_workspace(repo_root, "run1")
    try:
        (workspace.path / "new_file.txt").write_text("candidate content\n", encoding="utf-8")
        manifest, blocked = build_reconciliation_manifest(workspace, repo_root)
        assert blocked == ()
        ops = [op for op in manifest if op.relative_path == "new_file.txt"]
        assert len(ops) == 1
        op = ops[0]
        assert op.action == "write"
        assert op.applied is False

        calls: list = []
        real_open = sandbox_module.os.open
        real_replace = sandbox_module.os.replace

        def spying_open(path, *args, **kwargs):
            calls.append(("open", path))
            return real_open(path, *args, **kwargs)

        def spying_replace(src, dst, *args, **kwargs):
            calls.append(("replace", src, dst))
            return real_replace(src, dst, *args, **kwargs)

        monkeypatch.setattr(sandbox_module.os, "open", spying_open)
        monkeypatch.setattr(sandbox_module.os, "replace", spying_replace)

        applied_op = apply_reconciliation_operation(op, workspace, repo_root, "run1")

        assert len(calls) == 2
        assert calls[0][0] == "open"
        assert is_reconciliation_debris_name("run1", Path(calls[0][1]).name)
        assert calls[1] == ("replace", calls[0][1], str(repo_root / "new_file.txt"))

        assert applied_op.applied is True
        assert (repo_root / "new_file.txt").read_text(encoding="utf-8") == "candidate content\n"
        # No leftover debris after a successful apply.
        assert not any(is_reconciliation_debris_name("run1", p.name) for p in repo_root.iterdir())
    finally:
        discard_workspace(workspace)


def test_manifest_resume_classifies_already_applied_entries_as_a_safe_skip(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    workspace = create_isolated_workspace(repo_root, "run1")
    try:
        (workspace.path / "a.txt").write_text("candidate\n", encoding="utf-8")
        manifest, _ = build_reconciliation_manifest(workspace, repo_root)
        op = next(o for o in manifest if o.relative_path == "a.txt")
        applied_op = apply_reconciliation_operation(op, workspace, repo_root, "run1")

        # Simulate resuming with the *same* manifest entry, now already applied.
        already_applied_op = apply_reconciliation_operation(applied_op, workspace, repo_root, "run1")
        assert already_applied_op == applied_op  # unchanged, correctly a no-op

        # Simulate resuming with a FRESH (not-yet-applied) copy of the
        # same entry, but the authoritative file already matches
        # target_content_hash (interrupted after rename, before the
        # manifest's own applied=True flag was durably written).
        not_yet_marked = dataclasses.replace(op, applied=False)
        reclassified = apply_reconciliation_operation(not_yet_marked, workspace, repo_root, "run1")
        assert reclassified.applied is True
    finally:
        discard_workspace(workspace)


def test_manifest_detects_an_unexplained_third_state_and_fails_closed(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    workspace = create_isolated_workspace(repo_root, "run1")
    try:
        (workspace.path / "a.txt").write_text("candidate\n", encoding="utf-8")
        manifest, _ = build_reconciliation_manifest(workspace, repo_root)
        op = next(o for o in manifest if o.relative_path == "a.txt")

        # Interference: the authoritative file now has content matching
        # neither the original nor the target.
        (repo_root / "a.txt").write_text("something else entirely\n", encoding="utf-8")

        try:
            apply_reconciliation_operation(op, workspace, repo_root, "run1")
            assert False, "expected ReconciliationConflictError"
        except ReconciliationConflictError as exc:
            assert exc.relative_path == "a.txt"
    finally:
        discard_workspace(workspace)


def test_debris_matching_this_runs_naming_convention_is_removed_never_misclassified(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    workspace = create_isolated_workspace(repo_root, "run1")
    try:
        (workspace.path / "a.txt").write_text("candidate\n", encoding="utf-8")
        manifest, _ = build_reconciliation_manifest(workspace, repo_root)

        # Simulate an interruption between a temp-file write and its rename.
        debris_name = ".peos-reconcile-run1-deadbeef.tmp"
        (repo_root / debris_name).write_text("partial\n", encoding="utf-8")
        assert is_reconciliation_debris_name("run1", debris_name)

        removed = cleanup_reconciliation_debris(manifest, repo_root, "run1")
        assert debris_name in removed
        assert not (repo_root / debris_name).exists()

        # Debris from a *different* run_id is never touched.
        other_debris = ".peos-reconcile-otherrun-deadbeef.tmp"
        (repo_root / other_debris).write_text("partial\n", encoding="utf-8")
        cleanup_reconciliation_debris(manifest, repo_root, "run1")
        assert (repo_root / other_debris).exists()
        (repo_root / other_debris).unlink()
    finally:
        discard_workspace(workspace)


def test_manifest_delete_operation_classifies_already_absent_as_applied(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    (repo_root / "to_delete.txt").write_text("will be deleted\n", encoding="utf-8")
    import subprocess
    subprocess.run(["git", "add", "-A"], cwd=str(repo_root), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "add file"], cwd=str(repo_root), check=True, capture_output=True)

    workspace = create_isolated_workspace(repo_root, "run1")
    try:
        (workspace.path / "to_delete.txt").unlink()
        import subprocess as sp
        sp.run(["git", "add", "-A"], cwd=str(workspace.path), check=True, capture_output=True)

        manifest, _ = build_reconciliation_manifest(workspace, repo_root)
        op = next(o for o in manifest if o.relative_path == "to_delete.txt")
        assert op.action == "delete"

        result = reconcile_workspace_to_repo(workspace, repo_root, run_id="run1")
        assert "to_delete.txt" in result.deleted
        assert not (repo_root / "to_delete.txt").exists()

        # Re-applying the already-deleted entry (simulated resume) is a safe no-op.
        deleted_op = next(o for o in result.manifest if o.relative_path == "to_delete.txt")
        reapplied = apply_reconciliation_operation(dataclasses.replace(deleted_op, applied=False), workspace, repo_root, "run1")
        assert reapplied.applied is True
    finally:
        discard_workspace(workspace)


def test_reconcile_workspace_to_repo_returns_the_full_applied_manifest(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    workspace = create_isolated_workspace(repo_root, "run1")
    try:
        (workspace.path / "new_file.txt").write_text("hello\n", encoding="utf-8")
        result = reconcile_workspace_to_repo(workspace, repo_root, run_id="run1")
        assert "new_file.txt" in result.copied
        assert all(op.applied for op in result.manifest)
    finally:
        discard_workspace(workspace)
