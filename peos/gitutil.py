"""Read-only Git inspection helpers.

PEOS Automation V1 (SPEC-001) is only permitted to *inspect* Git state --
it must never merge, push, tag, commit, or rewrite history (AC-010). Every
function in this module runs a read-only `git` subcommand and returns its
output as text; none of them mutate repository state.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


def _run_git(args: list[str], repo_root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, ValueError) as exc:
        # Latest Codex review, Finding 5: `cwd=` pointing at a
        # nonexistent/unreadable directory (OSError) or one containing a
        # NUL byte (ValueError, not an OSError subclass -- the same class
        # of gap Finding 10, first pass, already fixed for
        # _canonicalize_spec's UnicodeDecodeError) makes `subprocess.run`
        # itself raise instead of returning a nonzero exit. Previously
        # escaped uncaught; a build_report() call for an invalid --repo
        # path must still produce the required final report, not a bare
        # traceback.
        return f"<git {' '.join(args)} failed: {exc}>"
    if proc.returncode != 0:
        return f"<git {' '.join(args)} failed: {proc.stderr.strip()}>"
    return proc.stdout.strip()


def git_status_porcelain(repo_root: Path) -> str:
    """Return `git status --porcelain` output (empty string if clean)."""
    return _run_git(["status", "--porcelain"], repo_root)


def git_diff_name_status(repo_root: Path) -> str:
    """Return `git diff --name-status` for unstaged + staged changes."""
    unstaged = _run_git(["diff", "--name-status"], repo_root)
    staged = _run_git(["diff", "--name-status", "--cached"], repo_root)
    parts = [p for p in (unstaged, staged) if p]
    return "\n".join(parts)


def git_current_branch(repo_root: Path) -> str:
    """Return the current branch name."""
    return _run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo_root)


def git_untracked_files(repo_root: Path) -> str:
    """Return newline-separated untracked (non-ignored) file paths.

    `git diff --name-status` never reports brand-new files that have not
    been `git add`ed, so the "Changed files" report section needs this
    too (SPEC-001 remediation Finding 10) or new files an agent created
    would be invisible to the Human Engineering Lead's review.
    """
    return _run_git(["ls-files", "--others", "--exclude-standard"], repo_root)


def _untracked_content_fingerprint(repo_root: Path) -> str:
    """For every untracked (non-ignored) file, hash its actual content,
    not just its path -- so a content edit to a file that was *already*
    untracked before a reviewer phase began is detected, not masked by an
    unchanged file list (SPEC-001 remediation Finding 3, second pass:
    "detect content mutation of ... existing untracked files, not merely
    names/status").
    """
    parts = []
    for rel in sorted(p for p in git_untracked_files(repo_root).splitlines() if p):
        path = repo_root / rel
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "<non-file>"
        except OSError as exc:
            digest = f"<unreadable: {exc}>"
        parts.append(f"{rel}:{digest}")
    return "\n".join(parts)


def repo_state_fingerprint(repo_root: Path) -> str:
    """A read-only, content-based fingerprint of `repo_root`'s current
    Git state, used to prove a supposedly read-only phase (e.g. Codex's
    independent review) made no change to the working tree it was invoked
    against (SPEC-001 remediation Finding 6, strengthened per Finding 3
    of the second remediation pass).

    Uses the *full* `git diff HEAD` text (not `--name-status`) for tracked
    content, so a further edit to a file that was *already* modified
    before the phase began is detected -- `--name-status` alone would
    still show that same file as "M" both before and after and miss the
    re-edit. Untracked files are fingerprinted by content hash
    (`_untracked_content_fingerprint`), not just by name, for the same
    reason. Two calls returning the same fingerprint is evidence of "no
    write occurred" for everything Git can see (tracked content and
    non-ignored untracked files); it is not a claim about ignored files.
    """
    parts = [
        _run_git(["rev-parse", "HEAD"], repo_root),
        _run_git(["diff", "HEAD", "--binary"], repo_root),
        _run_git(["diff", "--cached", "--binary"], repo_root),
        _untracked_content_fingerprint(repo_root),
    ]
    return hashlib.sha256("\n".join(parts).encode("utf-8", errors="replace")).hexdigest()
