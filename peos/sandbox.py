"""Isolated implementation workspace (SPEC-001 remediation -- Finding 1, BLOCKER).

Prior to this module, Claude ran directly against the authoritative
repository with `--permission-mode bypassPermissions` and a Bash tool
grant restricted only by a prompt-level allowlist. That is not an
execution boundary: a prompt cannot stop `git push`, and
`bypassPermissions` + Bash gives Claude a real shell in the real repo.

This module creates a disposable local Git clone -- the "isolated
workspace" -- that the implementation agent (Claude) and the independent
reviewer (Codex) operate in instead of the authoritative repository. The
real execution boundary is layered:

1. Claude is invoked in `--restricted` mode with no Bash/shell tool at
   all (see peos/claude_agent.py). This was verified empirically against
   the installed `claude` CLI: with Bash omitted from `--tools`, no
   shell is exposed, and Read/Edit/Write are confined to the invocation's
   working directory (an attempt to touch a path outside it returns a
   tool error, not a silent bypass). This makes `git push`/`merge`/
   `tag`/history-rewrite structurally unreachable through any tool
   Claude has -- not a pattern-matched prompt restriction.
2. Even if that tool confinement were ever weakened, the working
   directory itself is this disposable clone, not the authoritative
   repository: `origin` (and every other remote) is removed from its
   `.git/config`, so there is no configured push destination.
3. Even if a remote were somehow reconfigured from inside the workspace,
   `sandboxed_env()` strips the environment variables that could supply
   push credentials (SSH agent socket, GitHub tokens, askpass/credential
   helpers) and redirects HOME to an empty directory, so no cached
   credential, SSH key, or `.netrc` from the real environment is
   reachable either.

None of this is a full OS sandbox (no container, no namespace, no
filesystem jail) -- CLAUDE.md rules out Docker/Kubernetes, and a
custom macOS `sandbox-exec` profile was deliberately not built here
because `sandbox-exec` is itself Apple-deprecated and `--restricted`
already gives a maintained, CLI-native equivalent for the one thing that
matters (no shell, path-confined file tools). The residual trust
boundary is documented in `peos/report.py`'s KNOWN_LIMITATIONS and must
be read alongside this module.

PEOS itself never pushes, merges, tags, or rewrites history anywhere,
in the workspace or the authoritative repository (AC-010); this module
only ever runs read-only or working-tree-local Git commands.

Second remediation pass (Finding 1, BLOCKER, re-opened): the above
boundary covers Claude and Codex's own tool calls, but it does **not**
cover deterministic verification (`pytest -q`, `npm run lint/typecheck/
build`). Those commands execute whatever Python/JS code lives in the
workspace at verification time -- including files Claude (an untrusted
implementation agent, by design) just edited. Running that as a plain
subprocess inheriting the orchestrator's real environment and with no
filesystem/network confinement means "Claude has no Bash" is beside the
point: a planted `conftest.py`, test file, or `package.json` script is
itself an arbitrary-code-execution path once `pytest`/`npm` runs it.

`build_verification_sandbox_profile` / `sandboxed_verification_command`
close this specific gap using a mechanism genuinely available on this
platform today -- macOS Seatbelt (`sandbox-exec`) -- verified empirically
(not assumed) against this repository's real `pytest -q` and real `npm
run lint`/`typecheck`/`build` before being adopted:

- `(deny network*)` -- verification never legitimately needs network
  (dependencies are provisioned into the workspace up front, see
  `node_modules provisioning` below); this makes a push, fetch, or
  network-based exfiltration structurally impossible from inside a
  verification subprocess, regardless of what credentials happen to be
  reachable.
- `(deny file-write* (subpath "/"))` with an explicit allow-list limited
  to the workspace directory, the isolated `home_dir`, and the OS's own
  temp directories -- verified live to still let real `pytest`/`eslint`/
  `tsc`/`next build` run to completion (they only need to write inside
  their own cwd and OS temp dirs); this makes mutating the authoritative
  repository (including its `.git` objects) from a verification
  subprocess structurally impossible, because the authoritative
  `repo_root` is never in the write allow-list.
- `(deny file-read* ...)` on `repo_root/.git` specifically (the
  authoritative Git metadata named in the finding) and a small, named,
  auditable list of well-known credential file locations under the real
  `$HOME` (`CREDENTIAL_PATH_DENYLIST`) -- not a blanket deny of the whole
  filesystem, which would also deny reading `repo_root`'s installed
  Python virtualenv / Node toolchain that verification legitimately
  needs (see below).

This is deliberately **not** a claim of a full OS sandbox: reads of the
rest of the real filesystem (other than the denied paths above) are not
blocked, so a sufficiently motivated malicious script could still read
and print an arbitrary file to stdout, which a human would see in the
PEOS report -- a disclosure risk, not the mutate/push risk this finding
is about. `sandbox-exec` is itself Apple-deprecated; if it is ever
removed, `sandboxed_verification_command` fails closed (raises
`SandboxUnavailableError`) rather than silently running verification
unconfined. See `peos/report.py`'s `KNOWN_LIMITATIONS` for the precise,
non-overclaimed statement of this boundary.

Dependency provisioning (Finding 7): the isolated workspace is a fresh
`git clone`, so gitignored dependency directories (`frontend/
node_modules`, the Python `.venv`) are not carried over by the clone
itself. `create_isolated_workspace` explicitly copies
`frontend/node_modules` into the workspace (a deliberate, named
provisioning step -- not an accidental reuse of the authoritative
checkout) because Node resolves dependencies relative to cwd and the
verification sandbox denies network, so there is no way to `npm install`
inside it. Python verification instead reuses the orchestrator's own
installed interpreter and site-packages (`sys.executable`, typically
`repo_root/.venv`) by path, read-only, from inside the sandboxed
subprocess -- which is why the verification sandbox's read-deny is
scoped to `repo_root/.git` specifically rather than all of `repo_root`.
The trust assumption either way: dependencies are taken as of run start
and never re-installed or updated by PEOS; if `frontend/node_modules` is
absent from the authoritative checkout, frontend verification fails
closed with an explicit message rather than attempting a network install
or silently skipping the check.

After the workflow reaches a terminal outcome, `reconcile_workspace_to_repo`
copies the net *working-tree* changes (never commits, never pushes) back
onto the authoritative repository so the Human Engineering Lead can
inspect them with ordinary `git status`/`git diff` exactly as before --
this is the "transferable back to the authoritative working tree for
review" requirement. Governance artifacts (CLAUDE.md/AGENTS.md/
ENGINEERING.md and the governing specification) are never copied back if
their content changed inside the workspace; that is reported as a
blocked mutation instead (see peos/preflight.py), because an
implementation agent must not be able to silently rewrite the rules it
is being held to.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# Environment variables that can carry Git/GitHub/SSH push credentials.
# This is a named, auditable deny-list, not a claim that every possible
# ambient credential source is covered -- see the trust-boundary note in
# peos/report.py.
CREDENTIAL_ENV_DENYLIST = (
    "SSH_AUTH_SOCK",
    "SSH_AGENT_PID",
    "SSH_ASKPASS",
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "GH_ENTERPRISE_TOKEN",
    "GIT_ASKPASS",
    "GIT_SSH_COMMAND",
    "GIT_SSH",
    "GIT_CREDENTIAL_HELPER",
    "NETRC",
)

GOVERNANCE_ARTIFACTS = ("CLAUDE.md", "AGENTS.md", "ENGINEERING.md")

_BASELINE_COMMIT_MESSAGE = "peos: isolated workspace baseline (local only, never pushed)"

# Named, auditable list of well-known credential file locations under the
# real (ambient) $HOME that the verification sandbox denies reading, in
# addition to `repo_root/.git`. Not a claim this is exhaustive -- see the
# module docstring and peos/report.py's KNOWN_LIMITATIONS.
CREDENTIAL_PATH_DENYLIST = (
    ".ssh",
    ".netrc",
    ".git-credentials",
    ".config/gh",
    ".aws",
    ".docker/config.json",
)


class WorkspaceError(RuntimeError):
    """Raised when the isolated workspace cannot be safely created or reconciled."""


class SandboxUnavailableError(WorkspaceError):
    """Raised when the OS-enforced verification sandbox cannot be built on
    this platform. Callers must fail closed (refuse to run verification
    unconfined), never fall back to an unsandboxed subprocess."""


@dataclass(frozen=True)
class IsolatedWorkspace:
    path: Path
    home_dir: Path
    baseline_commit: str


@dataclass(frozen=True)
class ReconciliationResult:
    copied: tuple[str, ...] = field(default_factory=tuple)
    deleted: tuple[str, ...] = field(default_factory=tuple)
    blocked_governance_changes: tuple[str, ...] = field(default_factory=tuple)


def sandboxed_env(home_dir: Path, base_env: dict | None = None) -> dict:
    """Build the subprocess environment used for every Claude/Codex
    invocation against an isolated workspace: the real process
    environment, minus `CREDENTIAL_ENV_DENYLIST`, with HOME redirected
    to an empty directory and Git told never to prompt or fall back to
    global/system config.
    """
    env = dict(base_env if base_env is not None else os.environ)
    for key in CREDENTIAL_ENV_DENYLIST:
        env.pop(key, None)
    env["HOME"] = str(home_dir)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = "/bin/false"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    return env


def _run_git(args: list[str], cwd: Path, check: bool = True, input_text: str | None = None) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=60,
        input=input_text,
    )
    if check and proc.returncode != 0:
        raise WorkspaceError(f"git {' '.join(args)} failed in {cwd}: {proc.stderr.strip()}")
    return proc


def create_isolated_workspace(repo_root: Path, run_id: str) -> IsolatedWorkspace:
    """Create a disposable local clone of `repo_root`, carrying over the
    exact uncommitted/untracked state the human had, with every remote
    removed and a local-only baseline commit recorded for later diffing.

    Raises WorkspaceError (fail closed) if any step cannot be completed;
    callers must treat that as a workflow failure, not a reason to fall
    back to operating on `repo_root` directly.
    """
    tmp_root = Path(tempfile.mkdtemp(prefix=f"peos-{run_id}-"))
    workspace = tmp_root / "workspace"
    home_dir = tmp_root / "home"
    home_dir.mkdir(parents=True)

    _run_git(["clone", "--no-hardlinks", "--quiet", str(repo_root), str(workspace)], tmp_root)

    remotes = _run_git(["remote"], workspace, check=False).stdout.split()
    for remote in remotes:
        _run_git(["remote", "remove", remote], workspace)
    subprocess.run(
        ["git", "config", "--unset-all", "credential.helper"],
        cwd=str(workspace), capture_output=True, text=True,
    )

    diff = _run_git(["diff", "HEAD", "--binary"], repo_root, check=False)
    if diff.stdout.strip():
        apply_proc = subprocess.run(
            ["git", "apply", "--whitespace=nowarn", "-"],
            cwd=str(workspace), input=diff.stdout, capture_output=True, text=True,
        )
        if apply_proc.returncode != 0:
            shutil.rmtree(tmp_root, ignore_errors=True)
            raise WorkspaceError(
                "Could not reproduce the working tree's uncommitted changes in "
                f"the isolated workspace: {apply_proc.stderr.strip()}"
            )

    untracked = _run_git(["ls-files", "--others", "--exclude-standard"], repo_root, check=False).stdout.splitlines()
    for rel in untracked:
        if not rel:
            continue
        src = repo_root / rel
        if not src.is_file():
            continue
        dst = workspace / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    # Dependency provisioning (Finding 7): explicitly copy frontend/
    # node_modules into the workspace. The clone above does not carry it
    # (it is gitignored); without this, frontend verification cannot run
    # at all inside the isolated workspace, and the verification sandbox
    # denies network so `npm install` cannot be used as a fallback either.
    frontend_node_modules = repo_root / "frontend" / "node_modules"
    if frontend_node_modules.is_dir():
        shutil.copytree(
            frontend_node_modules,
            workspace / "frontend" / "node_modules",
            symlinks=True,
            ignore_dangling_symlinks=True,
            dirs_exist_ok=True,  # untracked-file copy above may have already created the dir
        )

    _run_git(["add", "-A"], workspace)
    _run_git(
        [
            "-c", "user.email=peos@localhost",
            "-c", "user.name=PEOS",
            "commit", "--no-verify", "--allow-empty", "-q",
            "-m", _BASELINE_COMMIT_MESSAGE,
        ],
        workspace,
    )
    baseline_commit = _run_git(["rev-parse", "HEAD"], workspace).stdout.strip()

    return IsolatedWorkspace(path=workspace, home_dir=home_dir, baseline_commit=baseline_commit)


def discard_workspace(workspace: IsolatedWorkspace) -> None:
    """Remove the temporary directory tree backing `workspace`. Safe to
    call even if the run failed partway through; never touches repo_root.
    """
    shutil.rmtree(workspace.path.parent, ignore_errors=True)


def _changed_paths(workspace: IsolatedWorkspace) -> tuple[list[tuple[str, str]], list[str]]:
    """Return (tracked_changes, untracked_paths) where tracked_changes is
    a list of (status_char, relative_path) from `git diff --name-status
    HEAD` (status one of M/A/D; renames are split into a delete + add),
    and untracked_paths lists new files not yet known to Git.
    """
    diff_out = _run_git(["diff", "--name-status", workspace.baseline_commit], workspace.path, check=False).stdout
    tracked: list[tuple[str, str]] = []
    for line in diff_out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        if status.startswith("R") and len(parts) == 3:
            tracked.append(("D", parts[1]))
            tracked.append(("A", parts[2]))
        elif len(parts) == 2:
            tracked.append((status[0], parts[1]))
    untracked = [p for p in _run_git(["ls-files", "--others", "--exclude-standard"], workspace.path, check=False).stdout.splitlines() if p]
    return tracked, untracked


def reconcile_workspace_to_repo(
    workspace: IsolatedWorkspace,
    repo_root: Path,
    protected_relative_paths: frozenset[str] = frozenset(),
) -> ReconciliationResult:
    """Copy the net working-tree changes made inside `workspace` back
    onto `repo_root`'s working tree for human review. Never stages,
    commits, or pushes anything. `protected_relative_paths` (governance
    artifacts + the governing specification) are never copied back even
    if changed -- such a change is reported in
    `blocked_governance_changes` instead so it is visible, not silently
    applied or silently dropped.
    """
    tracked, untracked = _changed_paths(workspace)

    copied: list[str] = []
    deleted: list[str] = []
    blocked: list[str] = []

    for status, rel in tracked:
        if rel in protected_relative_paths:
            blocked.append(rel)
            continue
        src = workspace.path / rel
        dst = repo_root / rel
        if status == "D":
            if dst.exists():
                dst.unlink()
                deleted.append(rel)
            continue
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied.append(rel)

    for rel in untracked:
        if rel in protected_relative_paths:
            blocked.append(rel)
            continue
        src = workspace.path / rel
        if not src.is_file():
            continue
        dst = repo_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(rel)

    return ReconciliationResult(
        copied=tuple(sorted(set(copied))),
        deleted=tuple(sorted(set(deleted))),
        blocked_governance_changes=tuple(sorted(set(blocked))),
    )


def ensure_spec_in_workspace(workspace: IsolatedWorkspace, repo_root: Path, spec_path: Path) -> str:
    """Guarantee the governing specification is readable from *inside* the
    isolated workspace, at a path relative to `workspace.path`, and return
    that relative (POSIX) path (Finding 6).

    Claude and Codex run with `cwd=workspace.path` and (for Claude)
    `--restricted`, which confines file tools to that working directory.
    Before this fix, prompts referenced `spec_path` as an absolute path in
    the *authoritative* repository -- inaccessible from inside the
    workspace, or accidentally reachable only in the coincidental case
    where the spec happens to already exist at the identical relative
    path. This function makes it unconditionally correct:

    - If `spec_path` is inside `repo_root` (the normal case -- a tracked
      or newly-added specification under docs/specifications/), it should
      already exist inside the workspace at the same relative path
      (carried over by the clone + diff-apply + untracked-file copy in
      `create_isolated_workspace`); this function copies it in defensively
      if, for any reason, it does not.
    - If `spec_path` is outside `repo_root` (an explicit `--spec` pointing
      elsewhere), it is copied into a fixed location under
      `workspace.path/.peos/governing-spec/`.

    Either way, the returned relative path is what prompts must reference,
    and what `peos/preflight.py`'s governance hashing/mutation-detection
    must key the specification entry by -- so an externally-supplied spec
    is covered by integrity checking exactly like one discovered under
    docs/specifications/ (Finding 4).
    """
    try:
        rel = spec_path.resolve().relative_to(repo_root.resolve())
        inside_repo = True
    except ValueError:
        inside_repo = False

    if inside_repo:
        dst = workspace.path / rel
        if not dst.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(spec_path, dst)
        return rel.as_posix()

    dst = workspace.path / ".peos" / "governing-spec" / spec_path.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(spec_path, dst)
    return dst.relative_to(workspace.path).as_posix()


def build_verification_sandbox_profile(workspace: IsolatedWorkspace, repo_root: Path) -> str:
    """Build the macOS Seatbelt (`sandbox-exec`) profile text that confines
    a deterministic verification command (SPEC-001 remediation Finding 1,
    BLOCKER -- see the module docstring for the full rationale and the live
    empirical verification this was based on).

    Denies all network, denies writing anywhere except the workspace, the
    isolated `home_dir`, and the OS's own temp directories, and denies
    reading `repo_root/.git` plus a named list of real-$HOME credential
    paths. Everything else keeps its default (`allow default`) so the
    orchestrator's own installed Python/Node toolchain -- which commonly
    lives under `repo_root` (e.g. a `.venv`) -- remains importable.
    """
    real_home = Path(os.environ.get("HOME", str(Path.home())))
    credential_paths = [real_home / p for p in CREDENTIAL_PATH_DENYLIST]

    # Scoped to *this process's* actual temp directory (e.g.
    # /private/var/folders/<random>/<random>/T on macOS), not the whole
    # /private/var/folders tree -- that tree is shared across every user
    # and process on the machine, including wherever a repository being
    # operated on might itself happen to live (observed concretely: this
    # module's own test suite's tmp_path fixture lives under it), so
    # allowing writes to all of it would silently defeat the "cannot
    # write to the authoritative repo" guarantee for any repo_root that
    # happened to be under it.
    process_tmp_dir = str(Path(tempfile.gettempdir()).resolve())
    write_allow = "\n  ".join(
        f'(subpath "{p}")' for p in (
            str(workspace.path),
            str(workspace.home_dir),
            process_tmp_dir,
            "/private/tmp",
        )
    )
    read_deny = "\n  ".join(
        f'(subpath "{p}")' for p in (
            str((repo_root / ".git").resolve()) if (repo_root / ".git").exists() else str(repo_root / ".git"),
            *[str(p) for p in credential_paths],
        )
    )
    # repo_root must never be writable, even when it happens to be located
    # under one of the broad allow-subpaths above (e.g. the process's own
    # temp directory, or /private/tmp) -- otherwise a repo checked out
    # under /tmp (a common case: CI runners, some local setups) would be
    # mutable by a malicious verification command despite the write-allow
    # list being intended only for the isolated workspace/home/scratch
    # space. Placed *after* the allow block: Seatbelt resolves overlapping
    # file-write* rules by last-match-wins, so this re-deny takes
    # precedence over any broader allow that happens to contain
    # repo_root -- verified empirically (see tests/test_peos_sandbox.py::
    # test_malicious_command_cannot_write_to_a_repo_root_nested_under_an_allowed_temp_directory).
    repo_root_write_deny = str(repo_root.resolve())
    return (
        "(version 1)\n"
        "(allow default)\n"
        "(deny network*)\n"
        # Loopback-only exception (latest Codex review, Finding 4):
        # reproduced empirically that the real `npm run build` (Next.js/
        # Turbopack) spawns an internal worker it talks to over a
        # 127.0.0.1 TCP socket for its own IPC -- not a network call in
        # the sense this sandbox exists to prevent. Scoped narrowly to
        # "localhost:*" on both ends (bind/inbound/outbound), verified
        # live that a genuine external destination (e.g. 1.1.1.1:443) is
        # still denied -- see
        # tests/test_peos_sandbox.py::test_malicious_command_cannot_reach_the_network
        # (unchanged, still passes) and the new
        # test_benign_command_can_still_use_a_loopback_socket.
        '(allow network-bind (local ip "localhost:*"))\n'
        '(allow network-inbound (local ip "localhost:*"))\n'
        '(allow network-outbound (remote ip "localhost:*"))\n'
        '(deny file-write* (subpath "/"))\n'
        f"(allow file-write*\n  {write_allow}\n"
        '  (literal "/dev/null")\n'
        '  (literal "/dev/tty"))\n'
        f'(deny file-write* (subpath "{repo_root_write_deny}"))\n'
        f"(deny file-read*\n  {read_deny})\n"
    )


def sandboxed_verification_command(
    command: list[str],
    workspace: IsolatedWorkspace,
    repo_root: Path,
    profile_dir: Path,
) -> list[str]:
    """Wrap `command` with the verification sandbox (Finding 1). Fails
    closed with `SandboxUnavailableError` if `sandbox-exec` is not
    available on this platform -- callers must treat that as a reason to
    refuse running verification, never as a reason to run it unconfined.
    """
    if sys.platform != "darwin" or shutil.which("sandbox-exec") is None:
        raise SandboxUnavailableError(
            "The verification execution sandbox (macOS sandbox-exec) is not "
            "available on this platform/host. PEOS Automation V1's "
            "verification boundary is currently macOS-only (SPEC-001 "
            "remediation Finding 1); refusing to run verification "
            "unconfined rather than silently weakening the boundary."
        )
    profile_dir.mkdir(parents=True, exist_ok=True)
    profile_path = profile_dir / "verification.sb"
    profile_path.write_text(build_verification_sandbox_profile(workspace, repo_root), encoding="utf-8")
    return ["sandbox-exec", "-f", str(profile_path), *command]
