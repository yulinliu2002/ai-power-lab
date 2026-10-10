"""Repository safety preflight and governance-artifact integrity (SPEC-001
remediation -- Finding 7).

Runs before any agent is invoked. Two separate concerns, kept in one
module because they share the "inspect repo_root before trusting it"
theme:

1. `check_repository_safety` -- is `repo_root` in a state PEOS can safely
   operate on at all (HEAD resolvable, no interrupted merge/rebase/
   cherry-pick, mandatory governance files present and readable)? A
   dirty working tree is explicitly *not* prohibited here (SPEC-001:
   "Dirty state does not necessarily need to be prohibited, but behavior
   must be explicit and safe") -- the isolated workspace
   (peos/sandbox.py) is built to carry that exact dirty state over
   faithfully, so nothing from it is silently dropped.

2. `hash_governance_artifacts` / `detect_mutations` -- a tamper-evidence
   check. The governing specification and CLAUDE.md/AGENTS.md/
   ENGINEERING.md are hashed in `repo_root` before implementation starts;
   after each agent phase, the same files are re-hashed inside the
   isolated workspace. Any mismatch means an agent edited a document it
   has no authority to change (CLAUDE.md Integrity Rules / SPEC-001
   Section 4), and workflow.py must fail closed rather than silently
   proceeding or silently copying the edit back.

Every Git command here is read-only. A Git command failing is itself
treated as an unsafe-repository signal (fail closed), per SPEC-001
Section 11 ("if ... the orchestrator cannot determine whether a human
gate applies, PEOS must stop").
"""

from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from peos.sandbox import GOVERNANCE_ARTIFACTS

_UNSAFE_GIT_STATE_MARKERS = (
    "MERGE_HEAD",
    "CHERRY_PICK_HEAD",
    "REVERT_HEAD",
    "BISECT_LOG",
    "rebase-merge",
    "rebase-apply",
)


@dataclass(frozen=True)
class PreflightResult:
    ok: bool
    reason: str | None = None
    head_commit: str | None = None
    dirty: bool = False
    missing_governance_files: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class InterpreterPreflightResult:
    ok: bool
    reason: str | None = None


def _run_git(args: list[str], repo_root: Path) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(
            ["git", *args], cwd=str(repo_root), capture_output=True, text=True, timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def check_repository_safety(repo_root: Path) -> PreflightResult:
    """Phase-0 check: is `repo_root` in a state PEOS may safely operate
    on? Fails closed on any Git inspection failure.
    """
    git_dir_proc = _run_git(["rev-parse", "--git-dir"], repo_root)
    if git_dir_proc is None or git_dir_proc.returncode != 0:
        return PreflightResult(ok=False, reason=f"{repo_root} is not a Git repository, or `git` is unavailable.")
    git_dir = (repo_root / git_dir_proc.stdout.strip()).resolve()

    head_proc = _run_git(["rev-parse", "HEAD"], repo_root)
    if head_proc is None or head_proc.returncode != 0:
        return PreflightResult(
            ok=False,
            reason=(
                "Could not resolve HEAD in the repository (git rev-parse HEAD "
                f"failed: {head_proc.stderr.strip() if head_proc else 'git did not run'}). "
                "Repository Git state cannot be determined; failing closed."
            ),
        )
    head_commit = head_proc.stdout.strip()

    for marker in _UNSAFE_GIT_STATE_MARKERS:
        if (git_dir / marker).exists():
            return PreflightResult(
                ok=False,
                reason=(
                    f"Repository has an interrupted Git operation in progress "
                    f"(found {marker} under {git_dir}). Resolve it (finish or "
                    "abort the merge/rebase/cherry-pick) before running PEOS."
                ),
                head_commit=head_commit,
            )

    status_proc = _run_git(["status", "--porcelain"], repo_root)
    if status_proc is None or status_proc.returncode != 0:
        return PreflightResult(
            ok=False,
            reason="Could not read `git status --porcelain`; failing closed.",
            head_commit=head_commit,
        )
    dirty = bool(status_proc.stdout.strip())

    missing = tuple(name for name in GOVERNANCE_ARTIFACTS if not (repo_root / name).is_file())
    if missing:
        return PreflightResult(
            ok=False,
            reason=(
                "Mandatory governance file(s) missing or unreadable: "
                f"{', '.join(missing)}. PEOS requires CLAUDE.md, AGENTS.md, "
                "and ENGINEERING.md to be present before invoking any agent."
            ),
            head_commit=head_commit,
            dirty=dirty,
            missing_governance_files=missing,
        )

    return PreflightResult(ok=True, head_commit=head_commit, dirty=dirty)


def check_verification_interpreter(
    find_spec: Callable[[str], object | None] = importlib.util.find_spec,
) -> InterpreterPreflightResult:
    """Phase-0 check (PEOS infrastructure maintenance -- dogfooding
    finding, not from any SPEC-00x document): can the interpreter
    currently running PEOS (`sys.executable`) satisfy the Python
    verification step the frozen plan will later run --
    `sys.executable -m pytest -q`, see
    `peos/verification_plan.py::resolve_verification_plan`?

    Checked in-process via `find_spec` rather than by spawning
    `sys.executable` as a subprocess: this process already *is*
    `sys.executable`, so "can this interpreter import pytest" is
    answered directly, with no extra process. Deliberately does not
    fall back to, or auto-select, any other interpreter (e.g. a
    repository `.venv`) -- it only ever reports on the interpreter
    already running this process, and leaves choosing that interpreter
    to whoever invokes `peos`.

    Failing here, before Intake/Claude/workspace creation, turns a
    pytest step that would otherwise fail deep inside a later
    `CommandResult` with a bare `ModuleNotFoundError` into an early,
    actionable, fail-closed PEOS result (SPEC-001 Section 11).
    """
    if find_spec("pytest") is not None:
        return InterpreterPreflightResult(ok=True)
    return InterpreterPreflightResult(
        ok=False,
        reason=(
            f"The interpreter currently running PEOS ({sys.executable}) does not "
            "have pytest installed, so the frozen verification plan's "
            f"`{sys.executable} -m pytest -q` step cannot run. Activate the "
            "project virtual environment before running `peos` (e.g. `source "
            ".venv/bin/activate`), or otherwise invoke `peos` with an interpreter "
            "that already has the project's dependencies installed "
            "(`pip install -r requirements.txt`)."
        ),
    )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hash_governance_artifacts(repo_root: Path, spec_path: Path, spec_workspace_rel: str) -> dict[str, str]:
    """Hash CLAUDE.md/AGENTS.md/ENGINEERING.md (keyed by path relative to
    `repo_root`) plus the governing specification (keyed by
    `spec_workspace_rel`, its path relative to the isolated workspace --
    see `peos.sandbox.ensure_spec_in_workspace`), so the same keys can be
    checked against a workspace copy via `detect_mutations`.

    `spec_workspace_rel` is required (not re-derived here) so a
    specification supplied via an explicit `--spec` path *outside*
    `repo_root` is still covered by mutation detection (SPEC-001
    remediation Finding 4) -- the original implementation silently
    dropped the spec from hashing entirely in that case.
    """
    hashes: dict[str, str] = {}
    for name in GOVERNANCE_ARTIFACTS:
        path = repo_root / name
        if path.is_file():
            hashes[name] = _sha256_file(path)
    if spec_path.is_file():
        hashes[spec_workspace_rel] = _sha256_file(spec_path)
    return hashes


def detect_mutations(baseline_hashes: dict[str, str], workspace_root: Path) -> tuple[str, ...]:
    """Return the relative paths (subset of baseline_hashes' keys) whose
    content differs inside `workspace_root`, or is missing entirely,
    compared to the baseline hash recorded before implementation began.
    """
    mutated = []
    for rel, baseline_hash in baseline_hashes.items():
        candidate = workspace_root / rel
        if not candidate.is_file():
            mutated.append(rel)
            continue
        if _sha256_file(candidate) != baseline_hash:
            mutated.append(rel)
    return tuple(sorted(mutated))
