"""Tests for the `peos` CLI entry point (peos/cli.py, AC-001)."""

from pathlib import Path

import pytest

import peos.cli as cli
from peos.workflow import PhaseLog, RunResult

REPO_ROOT = Path(__file__).resolve().parent.parent


def _patch_workflow(monkeypatch, outcome: str):
    def fake_run_workflow(task, repo_root, explicit_spec=None):
        return RunResult(task=task, outcome=outcome, phases=(PhaseLog(phase="Intake"),))

    monkeypatch.setattr(cli, "run_workflow", fake_run_workflow)


@pytest.mark.parametrize("outcome,expected_exit", [("APPROVED", 0), ("HUMAN_GATE", 2), ("FAILED", 1)])
def test_exit_code_matches_outcome(monkeypatch, capsys, outcome, expected_exit):
    _patch_workflow(monkeypatch, outcome)
    code = cli.main(["some task", "--repo", str(REPO_ROOT)])
    assert code == expected_exit
    assert "some task" in capsys.readouterr().out


def test_rejects_non_git_repo(tmp_path, capsys):
    """Latest Codex review, Finding 5, directly reproduced: an invalid
    --repo/--spec input previously bypassed reporting entirely (a bare
    stderr line, `return 1`, no call to build_report at all). It must now
    still produce the required PEOS final report (AC-012) on stdout, the
    same shape every other FAILED outcome gets.
    """
    code = cli.main(["task", "--repo", str(tmp_path)])
    assert code == 1
    out = capsys.readouterr().out
    assert "PEOS Run Report" in out
    assert "FAILED" in out
    assert "not a Git repository" in out


def test_rejects_spec_path_that_is_a_directory(tmp_path, capsys):
    (tmp_path / ".git").mkdir()
    a_directory = tmp_path / "docs"
    a_directory.mkdir()
    code = cli.main(["task", "--repo", str(tmp_path), "--spec", str(a_directory)])
    assert code == 1
    out = capsys.readouterr().out
    assert "PEOS Run Report" in out
    assert "directory, not a file" in out


def test_rejects_missing_spec_path(tmp_path, capsys):
    (tmp_path / ".git").mkdir()
    code = cli.main(["task", "--repo", str(tmp_path), "--spec", "docs/specifications/SPEC-999-missing.md"])
    assert code == 1
    out = capsys.readouterr().out
    assert "PEOS Run Report" in out
    assert "does not exist" in out


def test_rejects_unresolvable_repo_path_with_a_full_report_not_a_bare_stderr_line(capsys):
    """The --repo-cannot-resolve path is the one invalid-input case where
    no real repo_root is ever established -- build_report must still
    succeed (peos/gitutil.py's _run_git degrades gracefully on a
    nonexistent/NUL-containing cwd instead of raising) rather than falling
    through to the inner "report itself could not be built" fallback.

    A path containing a NUL byte makes `Path.resolve()` raise
    `ValueError`, not `OSError` -- directly reproduced: this previously
    escaped uncaught as a Python traceback all the way out of `main()`
    (the same class of gap Finding 10, first pass, already fixed for
    `_canonicalize_spec`'s `UnicodeDecodeError`).
    """
    code = cli.main(["task", "--repo", "/tmp/\x00bad-repo-path"])
    assert code == 1
    out = capsys.readouterr().out
    assert "PEOS Run Report" in out
    assert "FAILED" in out
    assert "could not be resolved" in out


def test_spec_path_is_canonicalized_relative_to_repo(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    specs_dir = tmp_path / "docs" / "specifications"
    specs_dir.mkdir(parents=True)
    spec_file = specs_dir / "SPEC-001-x.md"
    spec_file.write_text("# SPEC-001 -- X\n\n**Status:** Approved\n", encoding="utf-8")

    captured = {}

    def fake_run_workflow(task, repo_root, explicit_spec=None):
        captured["explicit_spec"] = explicit_spec
        return RunResult(task=task, outcome="APPROVED", phases=(PhaseLog(phase="Intake"),))

    monkeypatch.setattr(cli, "run_workflow", fake_run_workflow)
    code = cli.main(["task", "--repo", str(tmp_path), "--spec", "docs/specifications/SPEC-001-x.md"])
    assert code == 0
    assert captured["explicit_spec"] == spec_file.resolve()


def test_rejects_spec_with_invalid_utf8_encoding_without_a_traceback(tmp_path, capsys):
    """Finding 10 (second pass), directly reproduced: an invalid-encoding
    spec file raised `UnicodeDecodeError` uncaught (not an `OSError`
    subclass), escaping `_canonicalize_spec` as a traceback instead of a
    clean `error: ...` exit.
    """
    (tmp_path / ".git").mkdir()
    bad_spec = tmp_path / "bad-encoding.md"
    bad_spec.write_bytes(b"\xff\xfe\x00bad utf-8 bytes")
    code = cli.main(["task", "--repo", str(tmp_path), "--spec", str(bad_spec)])
    assert code == 1
    out = capsys.readouterr().out
    assert "PEOS Run Report" in out
    assert "not readable as UTF-8" in out


def test_rejects_spec_path_with_nul_byte_without_a_traceback(tmp_path, capsys):
    """Final acceptance review, directly reproduced:
    `main(["review", "--spec", "bad\\0spec"])` raised an uncaught
    `ValueError: embedded null byte` out of `_canonicalize_spec`'s
    `candidate.resolve()`, which only caught `OSError` -- the same class
    of gap already fixed for `--repo` in `main()`
    (test_rejects_unresolvable_repo_path_...), but not yet applied to
    `--spec`. It must now fail through the normal final-report path.
    """
    (tmp_path / ".git").mkdir()
    code = cli.main(["review", "--repo", str(tmp_path), "--spec", "bad\x00spec"])
    assert code == 1
    out = capsys.readouterr().out
    assert "PEOS Run Report" in out
    assert "FAILED" in out
    assert "could not be resolved" in out


def test_unhandled_workflow_exception_is_reported_not_raised(tmp_path, monkeypatch, capsys):
    (tmp_path / ".git").mkdir()

    def exploding_run_workflow(task, repo_root, explicit_spec=None):
        raise RuntimeError("simulated orchestration bug")

    monkeypatch.setattr(cli, "run_workflow", exploding_run_workflow)
    code = cli.main(["task", "--repo", str(tmp_path)])
    assert code == 1
    out = capsys.readouterr().out
    assert "FAILED" in out
    assert "simulated orchestration bug" in out
