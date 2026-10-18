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

SPEC-003 (PEOS Agent Authentication Bridge), implementing
docs/decisions/0002: redirecting `HOME` to a disposable directory, as
`sandboxed_env()` always has, also deletes both CLIs' own login state --
Claude's OAuth session (resolved from `~/.claude.json`/the macOS
Keychain) and Codex's (`$CODEX_HOME/auth.json`, defaulting to
`$HOME/.codex`) -- which is what produced the "Not logged in" dogfood
failure this spec fixes. Decision 0002's governing rule is that
authentication is an *explicit, named exception* to that isolation, not
a side effect of what happens not to be stripped, and that neither
agent's subprocess environment may ever carry the *other* agent's
credential. `sandboxed_env()` therefore now also strips
`CLAUDE_AUTH_ENV_VAR`, `CODEX_AUTH_HOME_ENV_VAR`, and every entry of
`AMBIENT_AGENT_AUTH_DENYLIST` (`CODEX_HOME`, `ANTHROPIC_API_KEY`,
`ANTHROPIC_AUTH_TOKEN`, `OPENAI_API_KEY`) from its common, shared output
(on top of the pre-existing `CREDENTIAL_ENV_DENYLIST` stripping) --
making "neither agent sees a credential it doesn't need, and neither
sees a competing *ambient* auth variable it never asked for either"
true by construction rather than by every caller remembering not to
pass the wrong one through (focused Codex review remediation, Finding
1: an unstripped ambient `CODEX_HOME`/`ANTHROPIC_API_KEY`/etc. in the
orchestrator's own shell previously survived into whichever agent's
environment happened to be built from this common base). `claude_
sandboxed_env()` and `codex_sandboxed_env()` each take that common,
secret-free base and add back exactly one agent's own material: Claude's
token re-added as an environment variable, or Codex's `CODEX_HOME`
pointed at a dedicated, human-provisioned directory holding only
`auth.json` -- never the real `HOME`/`~/.codex`. `check_claude_
auth_preflight()`/`check_codex_auth_preflight()` are presence/existence
checks only (never read secret contents) that `peos/workflow.py` calls
immediately before each agent's first invocation of a run, failing
closed before any subprocess launches if the configured bridge is
missing or unusable -- never by falling back to a broader credential
source. This same common base, with no bridge ever added back, is also
what local verification's environment is built from directly (Finding 2
remediation: verification must never inherit either agent's credential
or configuration, including `PEOS_CODEX_AUTH_HOME` itself) --
`build_verification_sandbox_profile()` additionally denies verification
*filesystem reads* of the resolved Codex authentication directory, so
neither the environment variable nor a direct path read can disclose
it; see that function's docstring.
"""

from __future__ import annotations

import dataclasses
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from peos.checkpoint import ReconciliationOperation
from peos.ledger import RUNS_SUBDIR
from peos.run_lock import LOCK_RELATIVE_PATH

# SPEC-007 "Workspace Lifecycle and One-Run-Per-Repository": the
# candidate workspace/home now live *under* the run's own durable
# directory (`.peos/runs/<run_id>/candidate/{workspace,home}`), nested
# specifically so `discard_workspace`'s real, unmodified
# `shutil.rmtree(workspace.path.parent, ...)` removes exactly this
# subtree -- never the sibling `ledger.json`/`checkpoint.json`/
# `runtime-evidence/` -- and so it durably survives a process restart
# while `ACTIVE`/`PAUSED_RETRYABLE` (SPEC-001/SPEC-003's accidental
# system-temp-space durability is retired in favor of this explicit,
# resume-aware placement).
CANDIDATE_SUBDIR = "candidate"

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

# SPEC-003 Requirement 1a: the one, named, auditable exception to HOME
# isolation for Claude's officially supported non-interactive auth
# mechanism (claude setup-token / CLAUDE_CODE_OAUTH_TOKEN -- confirmed
# against Anthropic's own docs, authenticates against the existing
# Claude subscription, not pay-per-token API billing). Named here, not
# merely absent from CREDENTIAL_ENV_DENYLIST, so the exception is
# visible in code rather than an accident of what the denylist omits.
CLAUDE_AUTH_ENV_VAR = "CLAUDE_CODE_OAUTH_TOKEN"

# SPEC-003 Requirement 2a: the one, named configuration source for
# Codex's dedicated authentication directory. Set by the Human
# Engineering Lead outside PEOS; PEOS only ever reads it, never creates,
# populates, or defaults it to the real `$HOME/.codex`.
CODEX_AUTH_HOME_ENV_VAR = "PEOS_CODEX_AUTH_HOME"

# Focused Codex review remediation (Finding 1, MAJOR): named, auditable
# list of *competing/ambient* agent-authentication environment variables
# that `sandboxed_env()`'s common base must also strip, on top of
# `CREDENTIAL_ENV_DENYLIST` and `CLAUDE_AUTH_ENV_VAR`. These are a
# distinct class from the Git/SSH push-credential denylist above: each
# one is itself a *different, unapproved* way either CLI could resolve
# authentication, and if the orchestrator's own ambient shell happens to
# have one set (e.g. a developer's personal `CODEX_HOME` from using the
# `codex` CLI outside PEOS, or a stray `ANTHROPIC_API_KEY`/
# `ANTHROPIC_AUTH_TOKEN`/`OPENAI_API_KEY`), neither Claude's nor Codex's
# subprocess environment must inherit it:
#   - `CODEX_HOME`: Codex's own real auth-resolution variable. Must
#     never reach Claude (which has no use for it) and must never reach
#     Codex *ambiently* either -- Codex only ever gets a `CODEX_HOME`
#     that `codex_sandboxed_env()` sets explicitly, from the validated
#     `PEOS_CODEX_AUTH_HOME`, never from whatever happened to already be
#     in the orchestrator's shell.
#   - `ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN`: both outrank
#     `CLAUDE_CODE_OAUTH_TOKEN` in Claude Code's own documented
#     precedence order (Requirement 1b); letting either survive
#     ambiently would silently change which credential Claude actually
#     authenticates with.
#   - `OPENAI_API_KEY`: not a credential kind this spec adopts for Codex
#     at all (Out of Scope: "Migrating Codex to an OpenAI API key ...
#     explicitly deferred") -- an ambient one must not silently enable a
#     different Codex auth mode than the one this bridge is designed
#     around.
AMBIENT_AGENT_AUTH_DENYLIST = (
    "CODEX_HOME",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "OPENAI_API_KEY",
)

# The one file PEOS requires to exist under PEOS_CODEX_AUTH_HOME --
# confirmed against OpenAI's own Codex CLI docs: `$CODEX_HOME/auth.json`
# is where Codex's credential lives under the `file` credentials store.
CODEX_AUTH_FILENAME = "auth.json"

assert CLAUDE_AUTH_ENV_VAR not in CREDENTIAL_ENV_DENYLIST, (
    "CLAUDE_AUTH_ENV_VAR cannot also be a CREDENTIAL_ENV_DENYLIST entry -- "
    "that would make the explicit auth exception and the credential "
    "stripping rule contradict each other."
)

assert CLAUDE_AUTH_ENV_VAR not in AMBIENT_AGENT_AUTH_DENYLIST, (
    "CLAUDE_AUTH_ENV_VAR cannot also be an AMBIENT_AGENT_AUTH_DENYLIST "
    "entry -- it is re-added explicitly for Claude by claude_sandboxed_env(), "
    "so stripping it from the common base is correct, but it must not also "
    "be in the *ambient-only* denylist, which exists for variables no "
    "bridge ever re-adds to the common base."
)
assert "CODEX_HOME" not in CREDENTIAL_ENV_DENYLIST, (
    "CODEX_HOME belongs in AMBIENT_AGENT_AUTH_DENYLIST (re-added explicitly "
    "by codex_sandboxed_env()), not CREDENTIAL_ENV_DENYLIST (never re-added "
    "by anything)."
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
    # SPEC-007 "Reconciliation Crash-Safety": the complete, durably-
    # recordable manifest this reconciliation computed and applied --
    # every entry's `applied` reflects its final state. Empty for a
    # no-op reconciliation (no workspace, or nothing to reconcile).
    manifest: tuple[ReconciliationOperation, ...] = field(default_factory=tuple)


def sandboxed_env(home_dir: Path, base_env: dict | None = None) -> dict:
    """Build the *common* subprocess environment shared by every Claude/
    Codex invocation (and local verification) against an isolated
    workspace: the real process environment, minus
    `CREDENTIAL_ENV_DENYLIST`, with HOME redirected to an empty
    directory and Git told never to prompt or fall back to global/system
    config.

    SPEC-003: this common base also strips `CLAUDE_AUTH_ENV_VAR`,
    `CODEX_AUTH_HOME_ENV_VAR` (the `PEOS_CODEX_AUTH_HOME` *configuration*
    variable itself, not just the `CODEX_HOME` it resolves to), and
    every entry of `AMBIENT_AGENT_AUTH_DENYLIST` -- it deliberately
    carries *no* agent authentication material and *no* ambient,
    competing agent-auth configuration at all (Finding 1/Finding 2
    remediation: this base is also what local verification's
    environment is built from, directly, with no bridge ever added
    back -- see `peos/verification_plan.py::execute_plan` -- so anything
    left un-stripped here would otherwise be readable by whatever code
    verification happens to run). Callers add exactly one agent's own
    credential back via `claude_sandboxed_env()`/`codex_sandboxed_env()`,
    never by passing this function's output directly to a subprocess
    that needs auth.
    """
    env = dict(base_env if base_env is not None else os.environ)
    for key in CREDENTIAL_ENV_DENYLIST:
        env.pop(key, None)
    env.pop(CLAUDE_AUTH_ENV_VAR, None)
    env.pop(CODEX_AUTH_HOME_ENV_VAR, None)
    for key in AMBIENT_AGENT_AUTH_DENYLIST:
        env.pop(key, None)
    env["HOME"] = str(home_dir)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = "/bin/false"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    return env


def claude_sandboxed_env(env: dict, claude_token: str) -> dict:
    """Return a copy of the common `sandboxed_env()` base with
    `CLAUDE_AUTH_ENV_VAR` explicitly re-added -- the one named,
    auditable exception to HOME isolation for Claude (SPEC-003
    Requirement 1a). Must only be used to build Claude's subprocess
    environment; the result must never be handed to the Codex
    subprocess (Codex has no use for this token, and giving it one
    anyway would let Codex's shell read a credential that is not its
    own to read).
    """
    claude_env = dict(env)
    claude_env[CLAUDE_AUTH_ENV_VAR] = claude_token
    return claude_env


def codex_sandboxed_env(env: dict, codex_auth_home: str) -> dict:
    """Return a copy of the common `sandboxed_env()` base with
    `CODEX_HOME` pointed at `codex_auth_home` -- the dedicated, minimal,
    human-provisioned directory holding only `auth.json` (SPEC-003
    Requirement 2b). Never the real `HOME`/`~/.codex`, and never
    carrying Claude's token (the base this copies has none). Must only
    be used to build Codex's subprocess environment.
    """
    codex_env = dict(env)
    codex_env["CODEX_HOME"] = codex_auth_home
    return codex_env


@dataclass(frozen=True)
class AuthPreflightResult:
    ok: bool
    reason: str | None = None


def check_claude_auth_preflight(environ: dict) -> AuthPreflightResult:
    """Presence/non-emptiness check only (SPEC-003 Requirement 3a/3d) --
    never reads, logs, or returns the token's value. Called by
    `peos/workflow.py` immediately before Claude's first invocation of a
    run, before any subprocess is launched.
    """
    token = environ.get(CLAUDE_AUTH_ENV_VAR, "")
    if not token:
        return AuthPreflightResult(
            False,
            f"{CLAUDE_AUTH_ENV_VAR} is not set (or is empty) in the orchestrator's "
            "environment. PEOS fails closed rather than falling back to the real "
            "HOME, the macOS Keychain, or any broader credential source.",
        )
    return AuthPreflightResult(True)


def check_codex_auth_preflight(environ: dict) -> AuthPreflightResult:
    """Presence/existence/non-emptiness checks only (SPEC-003 Requirement
    3b/3d) -- never reads or parses `auth.json`'s contents. Called by
    `peos/workflow.py` immediately before Codex's first invocation of a
    run, before any subprocess is launched.
    """
    auth_home_value = environ.get(CODEX_AUTH_HOME_ENV_VAR, "")
    if not auth_home_value:
        return AuthPreflightResult(
            False,
            f"{CODEX_AUTH_HOME_ENV_VAR} is not set in the orchestrator's "
            "environment. PEOS fails closed rather than defaulting to the real "
            "$HOME/.codex.",
        )
    auth_home = Path(auth_home_value)
    if not auth_home.is_dir():
        return AuthPreflightResult(
            False, f"Configured Codex authentication directory does not exist: {auth_home}",
        )
    auth_file = auth_home / CODEX_AUTH_FILENAME
    try:
        is_usable = auth_file.is_file() and auth_file.stat().st_size > 0
    except OSError:
        is_usable = False
    if not is_usable:
        return AuthPreflightResult(
            False, f"Configured Codex authentication file is missing or empty: {auth_file}",
        )
    return AuthPreflightResult(True)


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


def candidate_root_for_run(repo_root: Path, run_id: str) -> Path:
    """The durable `candidate/` directory for `run_id` -- a sibling of
    `ledger.json`/`checkpoint.json` under the same run directory (SPEC-007
    "Workspace Lifecycle"). Exposed so `peos/resume.py` and tests can
    reference it without hardcoding the path convention twice."""
    return repo_root / RUNS_SUBDIR / run_id / CANDIDATE_SUBDIR


def create_isolated_workspace(repo_root: Path, run_id: str) -> IsolatedWorkspace:
    """Create a disposable local clone of `repo_root`, carrying over the
    exact uncommitted/untracked state the human had, with every remote
    removed and a local-only baseline commit recorded for later diffing.

    SPEC-007: the workspace/home now live under the run's own durable
    `candidate/` directory (`.peos/runs/<run_id>/candidate/...`), not
    system temp space -- see `CANDIDATE_SUBDIR`'s module-level docstring
    note. `.peos/runs/` is gitignored, so cloning `repo_root` into a path
    nested beneath it does not self-reference: `git diff`/`git ls-files
    --others --exclude-standard` (used below, and by reconciliation) both
    respect `.gitignore` and never see the candidate directory itself.

    Raises WorkspaceError (fail closed) if any step cannot be completed;
    callers must treat that as a workflow failure, not a reason to fall
    back to operating on `repo_root` directly.
    """
    candidate_root = candidate_root_for_run(repo_root, run_id)
    workspace = candidate_root / "workspace"
    home_dir = candidate_root / "home"
    try:
        home_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise WorkspaceError(f"could not create isolated workspace home directory {home_dir}: {exc}") from exc

    _run_git(["clone", "--no-hardlinks", "--quiet", str(repo_root), str(workspace)], candidate_root)

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
            shutil.rmtree(candidate_root, ignore_errors=True)
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


def _is_orchestrator_owned_run_state(rel: str) -> bool:
    """SPEC-004 remediation Finding 2 (BLOCKER): `.peos/runs/` is
    orchestrator-owned Run Ledger state (peos/ledger.py), never content
    an implementation agent's workspace edits are allowed to introduce
    into the authoritative repository. This check is structural --
    a fixed path-prefix comparison -- and is applied unconditionally,
    before `protected_relative_paths` is even consulted and regardless
    of whatever `.gitignore` says. Previously, reconciliation relied
    entirely on `.peos/runs/` being gitignored for this property: an
    agent that removed (or never had) that gitignore entry could make
    `git ls-files --others --exclude-standard` see a forged
    `.peos/runs/<run>/ledger.json` as an ordinary untracked file, which
    reconciliation would then copy straight into the authoritative
    repository -- agent-authored content masquerading as orchestrator
    ledger state. A `.gitignore` change inside the workspace cannot
    affect this check at all, because it never looks at ignore rules in
    the first place.
    """
    return rel == RUNS_SUBDIR or rel.startswith(f"{RUNS_SUBDIR}/")


def _is_run_lock_path(rel: str) -> bool:
    """SPEC-007 "Workspace Lifecycle": `.peos/run.lock` is orchestrator-
    owned shared-lock state, a sibling of `.peos/runs/` that
    `_is_orchestrator_owned_run_state` above does not cover (it only
    matches paths under `.peos/runs/`). Excluded structurally, before
    `protected_relative_paths` is even consulted, exactly like run-state
    -- never copied, never reported as blocked (routine, expected
    orchestrator state, not a suspicious mutation)."""
    return rel == LOCK_RELATIVE_PATH


# SPEC-006 Section 9: the fixed, cycle-qualified path Runtime
# Verification stages its read-only evidence copy at inside the
# isolated workspace -- see `peos.runtime_evidence.staged_evidence_path`
# (".peos/runtime-evidence/<cycle_slug>/"). This is a *sibling* of
# `RUNS_SUBDIR` (".peos/runs/"), not a descendant of it, so
# `_is_orchestrator_owned_run_state` above does not cover it.
STAGED_RUNTIME_EVIDENCE_SUBDIR = ".peos/runtime-evidence"


def _is_staged_runtime_evidence_path(rel: str) -> bool:
    """Codex implementation review Finding 5: without this check, the
    staged evidence copy is ordinary untracked content from
    reconciliation's point of view, and would be copied onto the
    authoritative repository's working tree on any terminal outcome --
    exactly the property Requirement 19's `.peos/runs/` exclusion
    already prevents for the Run Ledger, for the identical reason (this
    is orchestrator-written diagnostic/evidence state, never
    implementation source). Treated the same way: excluded silently,
    before `protected_relative_paths` is even consulted, never reported
    as a blocked governance change (unlike `peos/` control-plane edits,
    which *are* reported) -- staged evidence is expected, routine
    per-round output, not a suspicious mutation.
    """
    return rel == STAGED_RUNTIME_EVIDENCE_SUBDIR or rel.startswith(f"{STAGED_RUNTIME_EVIDENCE_SUBDIR}/")


PEOS_CONTROL_PLANE_SUBDIR = "peos"


def _is_peos_control_plane_path(rel: str) -> bool:
    """SPEC-006 Section 10 hardening item A / ADR-0003 Decision 6 (Codex
    Round 1 Finding 1): `peos/` is the trusted PEOS control plane --
    the check catalog, the harness, the classification/evidence-
    integrity logic, and every other orchestrator module. A candidate
    workspace's edit to any file under it is **reported** as a blocked
    governance mutation (`blocked_governance_changes`), exactly like a
    `CLAUDE.md`/`AGENTS.md`/`ENGINEERING.md` change already is -- never
    silently copied back onto the authoritative repository's working
    tree, under any outcome (`APPROVED`, `FAILED`, or `HUMAN_GATE`).

    This closes a real gap: `reconcile_workspace_to_repo` already runs
    on every terminal outcome, and before this check existed, nothing
    stopped a candidate change to `peos/` itself from being copied back
    as an ordinary, uncommitted working-tree change -- before any human
    had reviewed it, let alone approved or merged it. Structural and
    unconditional, like `_is_orchestrator_owned_run_state` above, but
    reported (never silently skipped) -- an agent is allowed to *know*
    it touched the control plane; it is just never allowed to have that
    touch take effect without a human applying it, exactly like today's
    governance-artifact treatment.
    """
    return rel == PEOS_CONTROL_PLANE_SUBDIR or rel.startswith(f"{PEOS_CONTROL_PLANE_SUBDIR}/")


class ReconciliationConflictError(WorkspaceError):
    """SPEC-007 "Reconciliation Crash-Safety" step 4: an authoritative
    file matches neither a manifest entry's `target_content_hash` nor
    its `original_content_hash`, and its path is not recognized
    reconciliation debris -- some interference the manifest cannot
    account for. Callers (`peos/workflow.py`) must treat this as
    `FAILED`, naming `relative_path`, never guessing."""

    def __init__(self, relative_path: str):
        super().__init__(
            f"reconciliation cannot safely proceed: {relative_path} matches neither the "
            "manifest's recorded original nor target content, and is not recognized "
            "reconciliation debris -- failing closed rather than guessing."
        )
        self.relative_path = relative_path


def _hash_file_or_none(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reconciliation_debris_name(run_id: str, relative_path: str) -> str:
    """SPEC-007 Round 3 Finding 4: a fixed, recognizable temp-file naming
    convention PEOS's own recovery logic specifically looks for and
    safely removes -- excluded from "unexplained drift" by construction."""
    return f".peos-reconcile-{run_id}-{hashlib.sha256(relative_path.encode('utf-8')).hexdigest()}.tmp"


def is_reconciliation_debris_name(run_id: str, name: str) -> bool:
    return name.startswith(f".peos-reconcile-{run_id}-") and name.endswith(".tmp")


def build_reconciliation_manifest(
    workspace: IsolatedWorkspace,
    repo_root: Path,
    protected_relative_paths: frozenset[str] = frozenset(),
) -> tuple[tuple[ReconciliationOperation, ...], tuple[str, ...]]:
    """Compute the full list of `ReconciliationOperation`s from the
    candidate workspace's diff against `repo_root`, **before** any file
    is touched (SPEC-007 "Reconciliation Crash-Safety" step 1) -- this is
    what `RECONCILIATION`'s own `ENTERED` checkpoint write durably
    records. Returns `(manifest, blocked_governance_changes)` -- a
    governance/control-plane-path change is reported, never included in
    the manifest at all (it is never applied, with or without a crash).
    """
    tracked, untracked = _changed_paths(workspace)
    manifest: list[ReconciliationOperation] = []
    blocked: list[str] = []
    seen: set[str] = set()

    def _consider(rel: str, is_delete: bool) -> None:
        if rel in seen:
            return
        seen.add(rel)
        if _is_orchestrator_owned_run_state(rel) or _is_staged_runtime_evidence_path(rel) or _is_run_lock_path(rel):
            return
        if _is_peos_control_plane_path(rel) or rel in protected_relative_paths:
            blocked.append(rel)
            return
        dst = repo_root / rel
        original_hash = _hash_file_or_none(dst)
        if is_delete:
            manifest.append(ReconciliationOperation(
                relative_path=rel, action="delete", target_content_hash=None, original_content_hash=original_hash,
            ))
            return
        src = workspace.path / rel
        if not src.is_file():
            return
        manifest.append(ReconciliationOperation(
            relative_path=rel, action="write",
            target_content_hash=_hash_file_or_none(src), original_content_hash=original_hash,
        ))

    for status, rel in tracked:
        _consider(rel, is_delete=(status == "D"))
    for rel in untracked:
        _consider(rel, is_delete=False)

    return tuple(manifest), tuple(sorted(set(blocked)))


def apply_reconciliation_operation(
    op: ReconciliationOperation, workspace: IsolatedWorkspace, repo_root: Path, run_id: str,
) -> ReconciliationOperation:
    """Apply one not-yet-`applied` manifest entry (SPEC-007 "Reconciliation
    Crash-Safety" steps 2/4), classifying the authoritative file's
    *current* state against the durable manifest entry rather than
    re-diffing or fingerprint-guessing:

    - already matches `target_content_hash` (or already absent, for a
      delete): correctly applied already -- confirmed, `applied=True`.
    - matches `original_content_hash` (untouched) or is already correctly
      absent for a not-yet-applied delete: safely (re-)applied now,
      idempotently.
    - matches neither, and is not recognized reconciliation debris: some
      third, unexplained interference -- raises `ReconciliationConflictError`.

    A `"write"` is applied via temp-file-in-the-target's-own-directory +
    `os.replace` (atomic, never `shutil.copy2`'s in-place, non-atomic
    write); a `"delete"` is an ordinary `os.unlink` (already atomic for a
    single file).
    Codex implementation review (confirmed, major): an earlier revision
    returned an already-`applied=True` entry immediately, trusting the
    flag without checking the authoritative file's *current* content at
    all -- meaning anything that changed that file after the flag was
    set (and before this call) would go completely unnoticed, exactly
    the "unexplained interference" case this mechanism exists to catch.
    This function therefore always re-derives the classification from
    the file's current content, regardless of what `op.applied` claims:
    an already-`applied` entry is only ever *confirmed* applied (never
    trusted blindly), and a mismatch found after being marked applied is
    itself an unexplained-interference failure.
    """
    dst = repo_root / op.relative_path
    current_hash = _hash_file_or_none(dst)

    if op.action == "delete":
        if current_hash is None:
            return dataclasses.replace(op, applied=True)
        if op.applied:
            raise ReconciliationConflictError(op.relative_path)
        if current_hash == op.original_content_hash:
            dst.unlink()
            return dataclasses.replace(op, applied=True)
        raise ReconciliationConflictError(op.relative_path)

    # action == "write"
    if current_hash == op.target_content_hash:
        return dataclasses.replace(op, applied=True)
    if op.applied:
        # Previously confirmed applied, but the authoritative file no
        # longer matches the recorded target -- something changed it
        # since. Never silently re-apply over unexplained interference.
        raise ReconciliationConflictError(op.relative_path)
    if current_hash == op.original_content_hash:
        src = workspace.path / op.relative_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp_name = _reconciliation_debris_name(run_id, op.relative_path)
        tmp_path = dst.parent / tmp_name
        content = src.read_bytes()
        tmp_fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        try:
            with os.fdopen(tmp_fd, "wb") as fh:
                fh.write(content)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(str(tmp_path), str(dst))
        except OSError:
            try:
                tmp_path.unlink()
            except OSError:
                pass
            raise
        return dataclasses.replace(op, applied=True)
    raise ReconciliationConflictError(op.relative_path)


def cleanup_reconciliation_debris(
    manifest: tuple[ReconciliationOperation, ...], repo_root: Path, run_id: str,
) -> tuple[str, ...]:
    """SPEC-007 Round 3 Finding 4: remove any leftover temp file matching
    this run's recognized naming convention, in exactly the directories
    this manifest could have written debris into -- never a broader,
    unbounded filesystem walk. Called before reconciliation is reported
    `COMPLETED`, and again by resume preflight (check 15) before any
    drift comparison runs, so this debris never counts toward
    "unexplained" dirtiness."""
    removed: list[str] = []
    candidate_dirs = {(repo_root / op.relative_path).parent for op in manifest}
    for d in candidate_dirs:
        if not d.is_dir():
            continue
        try:
            entries = list(d.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_file() and is_reconciliation_debris_name(run_id, entry.name):
                try:
                    entry.unlink()
                    removed.append(str(entry.relative_to(repo_root)))
                except OSError:
                    pass
    return tuple(sorted(removed))


def reconcile_workspace_to_repo(
    workspace: IsolatedWorkspace,
    repo_root: Path,
    protected_relative_paths: frozenset[str] = frozenset(),
    *,
    run_id: str = "",
    manifest: tuple[ReconciliationOperation, ...] | None = None,
    on_manifest_built: Callable[[tuple[ReconciliationOperation, ...]], None] | None = None,
    on_operation_applied: Callable[[ReconciliationOperation], None] | None = None,
) -> ReconciliationResult:
    """Copy the net working-tree changes made inside `workspace` back
    onto `repo_root`'s working tree for human review. Never stages,
    commits, or pushes anything. `protected_relative_paths` (governance
    artifacts + the governing specification) are never copied back even
    if changed -- such a change is reported in
    `blocked_governance_changes` instead so it is visible, not silently
    applied or silently dropped. Anything under `.peos/runs/`
    (`_is_orchestrator_owned_run_state`) is excluded structurally, before
    `protected_relative_paths` is even consulted. Anything under `peos/`
    itself (`_is_peos_control_plane_path`, SPEC-006 hardening item A) is
    similarly excluded structurally, but -- unlike run-state -- reported
    in `blocked_governance_changes`, never silently skipped.

    SPEC-007 "Reconciliation Crash-Safety": restructured around a
    durable, per-file manifest of atomically-applied operations rather
    than `shutil.copy2`'s non-atomic in-place writes. `manifest`, when
    given (a resume re-entering an interrupted reconciliation), is used
    exactly as recorded -- no re-diffing, no fingerprint-guessing; the
    manifest is otherwise (re-)computed fresh via
    `build_reconciliation_manifest`. `on_manifest_built`/
    `on_operation_applied` let a caller (`peos/workflow.py`) persist each
    step as its own durable checkpoint write -- this function itself has
    no checkpoint access, by design, so it stays unit-testable without one.
    """
    blocked: tuple[str, ...] = ()
    if manifest is None:
        manifest, blocked = build_reconciliation_manifest(workspace, repo_root, protected_relative_paths)
        if on_manifest_built is not None:
            on_manifest_built(manifest)

    updated: list[ReconciliationOperation] = []
    copied: list[str] = []
    deleted: list[str] = []
    for op in manifest:
        new_op = apply_reconciliation_operation(op, workspace, repo_root, run_id)
        updated.append(new_op)
        if on_operation_applied is not None and not op.applied:
            on_operation_applied(new_op)
        (copied if new_op.action == "write" else deleted).append(new_op.relative_path)

    cleanup_reconciliation_debris(tuple(updated), repo_root, run_id)

    return ReconciliationResult(
        copied=tuple(sorted(set(copied))),
        deleted=tuple(sorted(set(deleted))),
        blocked_governance_changes=blocked,
        manifest=tuple(updated),
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


def build_verification_sandbox_profile(
    workspace: IsolatedWorkspace,
    repo_root: Path,
    extra_deny_read_paths: tuple[Path, ...] = (),
) -> str:
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

    `extra_deny_read_paths` (SPEC-003 remediation Finding 2, MAJOR): the
    resolved Codex authentication directory (`PEOS_CODEX_AUTH_HOME`),
    when configured, is passed here by `peos/verification_plan.py` so
    verification cannot read it even though it is not under the real
    `$HOME` (`CREDENTIAL_PATH_DENYLIST` only covers well-known paths
    under the real `$HOME`; the Codex auth directory is an independently
    configured, arbitrary path). The accepted V1 residual risk in
    `docs/specifications/SPEC-003-peos-agent-auth-bridge.md`'s Known
    Limitations is scoped to Codex's *own* shell tool reading its *own*
    scoped `auth.json` during a Codex invocation -- it does not extend
    to local verification, which runs untrusted implementation-agent
    code and must not be able to read a credential it has no business
    touching at all.
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
    # SPEC-007 Round 2 Finding 6 / ADR-0004 Decision 2: `workspace.path`/
    # `workspace.home_dir` now live *under* `repo_root`
    # (`.peos/runs/<run_id>/candidate/...`), so they cannot be granted in
    # the same, single allow-before-deny block as the broader, pre-
    # existing scratch-space allows below -- moving the *entire* combined
    # block to after the `repo_root` write-deny (as an earlier revision
    # did) would reopen writes to all of `repo_root` for any repository
    # nested inside the broader temp-space allowances. Only this run's
    # own narrow candidate paths move after the deny; the broader allows
    # keep their original position, before it.
    broad_write_allow = "\n  ".join(
        f'(subpath "{p}")' for p in (
            process_tmp_dir,
            "/private/tmp",
        )
    )
    narrow_write_allow = "\n  ".join(
        f'(subpath "{p}")' for p in (
            str(workspace.path),
            str(workspace.home_dir),
        )
    )
    read_deny = "\n  ".join(
        f'(subpath "{p}")' for p in (
            str((repo_root / ".git").resolve()) if (repo_root / ".git").exists() else str(repo_root / ".git"),
            *[str(p) for p in credential_paths],
            *[str(Path(p).resolve()) if Path(p).exists() else str(p) for p in extra_deny_read_paths],
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
        f"(allow file-write*\n  {broad_write_allow}\n"
        '  (literal "/dev/null")\n'
        '  (literal "/dev/tty"))\n'
        f'(deny file-write* (subpath "{repo_root_write_deny}"))\n'
        f"(allow file-write*\n  {narrow_write_allow})\n"
        f"(deny file-read*\n  {read_deny})\n"
    )


def sandboxed_verification_command(
    command: list[str],
    workspace: IsolatedWorkspace,
    repo_root: Path,
    profile_dir: Path,
    extra_deny_read_paths: tuple[Path, ...] = (),
) -> list[str]:
    """Wrap `command` with the verification sandbox (Finding 1). Fails
    closed with `SandboxUnavailableError` if `sandbox-exec` is not
    available on this platform -- callers must treat that as a reason to
    refuse running verification, never as a reason to run it unconfined.

    `extra_deny_read_paths`: forwarded verbatim to
    `build_verification_sandbox_profile` (SPEC-003 remediation Finding 2).
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
    profile_path.write_text(
        build_verification_sandbox_profile(workspace, repo_root, extra_deny_read_paths=extra_deny_read_paths),
        encoding="utf-8",
    )
    return ["sandbox-exec", "-f", str(profile_path), *command]


def build_runtime_verification_sandbox_profile(
    workspace: IsolatedWorkspace,
    repo_root: Path,
    extra_deny_read_paths: tuple[Path, ...] = (),
) -> str:
    """Build the Seatbelt profile that confines the backend/frontend
    service subprocesses PEOS Runtime Verification starts (SPEC-006
    Section 11; extends `build_verification_sandbox_profile`'s pattern,
    never replaces it -- deterministic verification's own profile above
    is untouched by this function).

    The write-allow set, the `repo_root` re-deny, the `.git`/credential-
    path read-deny, and the loopback-only network exception are
    identical in kind to the existing verification profile -- both
    confine untrusted candidate-run code to the isolated workspace with
    no network beyond loopback. This is a deliberately separate function
    (not a reuse of `build_verification_sandbox_profile` under a second
    name) so the two call sites can evolve independently without one
    change silently affecting the other's guarantees.

    The evidence output directory (`.peos/runs/<run_id>/runtime-
    evidence/`) is deliberately **not** in the write-allow set here
    (Codex Round 1 Finding 4): backend/frontend service subprocesses have
    no legitimate reason to write there, and granting it would let
    untrusted candidate-run code write directly into the evidence PEOS
    is about to hand Codex. Only the orchestrator's own unsandboxed
    process (`peos/runtime_evidence.py`) ever writes there.

    `extra_deny_read_paths` (Codex Round 1 Finding 7): forwarded, exactly
    like `build_verification_sandbox_profile` already does, so a
    configured `PEOS_CODEX_AUTH_HOME` is denied to these service
    processes too -- the fixed `CREDENTIAL_PATH_DENYLIST` alone does not
    cover an arbitrarily-located Codex auth directory.
    """
    real_home = Path(os.environ.get("HOME", str(Path.home())))
    credential_paths = [real_home / p for p in CREDENTIAL_PATH_DENYLIST]

    process_tmp_dir = str(Path(tempfile.gettempdir()).resolve())
    # SPEC-007 Round 2 Finding 6 / ADR-0004 Decision 2: `workspace.path`/
    # `workspace.home_dir` now live *under* `repo_root`
    # (`.peos/runs/<run_id>/candidate/...`), so they cannot be granted in
    # the same, single allow-before-deny block as the broader, pre-
    # existing scratch-space allows below -- moving the *entire* combined
    # block to after the `repo_root` write-deny (as an earlier revision
    # did) would reopen writes to all of `repo_root` for any repository
    # nested inside the broader temp-space allowances. Only this run's
    # own narrow candidate paths move after the deny; the broader allows
    # keep their original position, before it.
    broad_write_allow = "\n  ".join(
        f'(subpath "{p}")' for p in (
            process_tmp_dir,
            "/private/tmp",
        )
    )
    # The browser-worker subprocess (python -m peos.runtime_browser)
    # writes its own transient input/output temp directory as a
    # *sibling* of `workspace.path` (`_run_browser_worker`'s
    # `tempfile.TemporaryDirectory(dir=workspace.path.parent)`), so the
    # write-allow here is the whole candidate directory
    # (`workspace.path.parent`), not just `workspace.path`/`home_dir`
    # individually -- still strictly narrower than `repo_root` itself
    # (test_ac032 below). A real `sandbox-exec` run first caught this:
    # the narrower form denied that temp directory with
    # `PermissionError: Operation not permitted`.
    narrow_write_allow = f'(subpath "{workspace.path.parent}")'
    read_deny = "\n  ".join(
        f'(subpath "{p}")' for p in (
            str((repo_root / ".git").resolve()) if (repo_root / ".git").exists() else str(repo_root / ".git"),
            *[str(p) for p in credential_paths],
            *[str(Path(p).resolve()) if Path(p).exists() else str(p) for p in extra_deny_read_paths],
        )
    )
    repo_root_write_deny = str(repo_root.resolve())
    return (
        "(version 1)\n"
        "(allow default)\n"
        "(deny network*)\n"
        '(allow network-bind (local ip "localhost:*"))\n'
        '(allow network-inbound (local ip "localhost:*"))\n'
        '(allow network-outbound (remote ip "localhost:*"))\n'
        '(deny file-write* (subpath "/"))\n'
        f"(allow file-write*\n  {broad_write_allow}\n"
        '  (literal "/dev/null")\n'
        '  (literal "/dev/tty"))\n'
        f'(deny file-write* (subpath "{repo_root_write_deny}"))\n'
        f"(allow file-write*\n  {narrow_write_allow})\n"
        f"(deny file-read*\n  {read_deny})\n"
    )


def sandboxed_runtime_verification_command(
    command: list[str],
    workspace: IsolatedWorkspace,
    repo_root: Path,
    profile_dir: Path,
    extra_deny_read_paths: tuple[Path, ...] = (),
) -> list[str]:
    """Wrap `command` (a backend or frontend service launch) with the
    Runtime Verification sandbox. Fails closed with
    `SandboxUnavailableError` on any non-macOS platform or a missing
    `sandbox-exec` -- never an unsandboxed fallback (SPEC-006 Section 11).
    """
    if sys.platform != "darwin" or shutil.which("sandbox-exec") is None:
        raise SandboxUnavailableError(
            "The Runtime Verification execution sandbox (macOS sandbox-exec) is not "
            "available on this platform/host. PEOS Runtime Verification is "
            "macOS-only (SPEC-006 Section 11, inheriting SPEC-001 Finding 1's "
            "boundary); refusing to start a backend/frontend service process "
            "unconfined rather than silently weakening the boundary."
        )
    profile_dir.mkdir(parents=True, exist_ok=True)
    profile_path = profile_dir / "runtime-verification.sb"
    profile_path.write_text(
        build_runtime_verification_sandbox_profile(workspace, repo_root, extra_deny_read_paths=extra_deny_read_paths),
        encoding="utf-8",
    )
    return ["sandbox-exec", "-f", str(profile_path), *command]
