"""Tests for read-only Git inspection helpers (peos/gitutil.py).

Runs against the real repository working tree; every function here is
read-only by construction (no git command that mutates state), so this
is safe to run as part of the ordinary test suite.
"""

from pathlib import Path

from peos.gitutil import (
    git_current_branch,
    git_diff_name_status,
    git_status_porcelain,
    git_untracked_files,
    repo_state_fingerprint,
)

from tests._peos_fixtures import make_minimal_repo

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_git_status_porcelain_returns_string():
    assert isinstance(git_status_porcelain(REPO_ROOT), str)


def test_git_diff_name_status_returns_string():
    assert isinstance(git_diff_name_status(REPO_ROOT), str)


def test_git_current_branch_returns_nonempty_string():
    branch = git_current_branch(REPO_ROOT)
    assert isinstance(branch, str)
    assert branch != ""


def test_git_untracked_files_lists_new_file(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    assert git_untracked_files(repo_root) == ""
    (repo_root / "new_file.txt").write_text("x\n", encoding="utf-8")
    assert "new_file.txt" in git_untracked_files(repo_root)


def test_repo_state_fingerprint_is_stable_when_nothing_changes(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    assert repo_state_fingerprint(repo_root) == repo_state_fingerprint(repo_root)


def test_repo_state_fingerprint_changes_when_a_file_is_added(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    before = repo_state_fingerprint(repo_root)
    (repo_root / "sneaky.txt").write_text("x\n", encoding="utf-8")
    after = repo_state_fingerprint(repo_root)
    assert before != after


def test_repo_state_fingerprint_changes_when_a_tracked_file_is_modified(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    before = repo_state_fingerprint(repo_root)
    (repo_root / "CLAUDE.md").write_text("modified\n", encoding="utf-8")
    after = repo_state_fingerprint(repo_root)
    assert before != after


def test_repo_state_fingerprint_detects_a_further_edit_to_an_already_dirty_tracked_file(tmp_path):
    """Finding 3 (second pass), directly reproduced: a `git status`/
    `--name-status` based fingerprint shows the same "M CLAUDE.md" both
    before and after a *second* edit to a file that was already modified
    going in -- masking the re-edit. The content-based `git diff HEAD`
    fingerprint must not have this blind spot.
    """
    repo_root = make_minimal_repo(tmp_path)
    (repo_root / "CLAUDE.md").write_text("first edit\n", encoding="utf-8")
    before = repo_state_fingerprint(repo_root)

    assert "M CLAUDE.md" in git_status_porcelain(repo_root)
    (repo_root / "CLAUDE.md").write_text("second, different edit\n", encoding="utf-8")
    assert "M CLAUDE.md" in git_status_porcelain(repo_root)  # status line unchanged

    after = repo_state_fingerprint(repo_root)
    assert before != after


def test_repo_state_fingerprint_detects_a_further_edit_to_an_already_untracked_file(tmp_path):
    """The same gap, for an untracked (never-`git add`ed) file: its name
    appears in `git ls-files --others` both before and after a content
    edit, so a names-only fingerprint would miss the edit entirely.
    """
    repo_root = make_minimal_repo(tmp_path)
    (repo_root / "new_file.txt").write_text("first version\n", encoding="utf-8")
    before = repo_state_fingerprint(repo_root)

    assert "new_file.txt" in git_untracked_files(repo_root)
    (repo_root / "new_file.txt").write_text("second, different version\n", encoding="utf-8")
    assert "new_file.txt" in git_untracked_files(repo_root)  # untracked-file list unchanged

    after = repo_state_fingerprint(repo_root)
    assert before != after
