"""Shared test helpers for PEOS tests (not collected by pytest -- no
`test_` prefix). Builds a minimal, real, local Git repository so
preflight/hashing/workspace-cloning code can be exercised against real
`git` plumbing without touching the actual ai-power-lab repository.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_MINIMAL_CLAUDE_MD = "# AI Power Lab\n\nTest governance file.\n"
_MINIMAL_AGENTS_MD = "# Agent Roles\n\nTest governance file.\n"
_MINIMAL_ENGINEERING_MD = "# Engineering Workflow\n\nTest governance file.\n"


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True)


def make_minimal_repo(tmp_path: Path, spec_status: str = "Approved") -> Path:
    """Create a tiny real Git repo at `tmp_path` with the mandatory
    governance files, one approved spec (SPEC-001-x.md), and an empty
    `tests/` directory, with everything committed (clean working tree).
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(["init", "-q"], repo_root)
    _git(["config", "user.email", "test@example.com"], repo_root)
    _git(["config", "user.name", "Test"], repo_root)

    (repo_root / "CLAUDE.md").write_text(_MINIMAL_CLAUDE_MD, encoding="utf-8")
    (repo_root / "AGENTS.md").write_text(_MINIMAL_AGENTS_MD, encoding="utf-8")
    (repo_root / "ENGINEERING.md").write_text(_MINIMAL_ENGINEERING_MD, encoding="utf-8")
    # SPEC-004 Requirement 19: `.peos/runs/` is gitignored in any real
    # target repository. Several workflow tests reuse `repo_root` itself
    # as the "isolated workspace" (`_fake_workspace_factory`, for speed,
    # since a real `git clone` per test is unnecessary to exercise
    # routing logic) -- the Run Ledger, always written under the real
    # `repo_root`, would otherwise show up as an untracked file inside
    # that same fake "workspace" and confuse reconciliation's
    # untracked-file scan (`git ls-files --others --exclude-standard`),
    # exactly as a real target repository without this gitignore entry
    # would confuse real reconciliation too.
    (repo_root / ".gitignore").write_text(".peos/runs/\n.peos/run.lock\n", encoding="utf-8")

    specs_dir = repo_root / "docs" / "specifications"
    specs_dir.mkdir(parents=True)
    (specs_dir / "SPEC-001-x.md").write_text(
        f"# SPEC-001 -- X\n\n**Status:** {spec_status}\n\nbody\n", encoding="utf-8",
    )

    tests_dir = repo_root / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_placeholder.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    _git(["add", "-A"], repo_root)
    _git(["commit", "-q", "-m", "initial"], repo_root)
    return repo_root
