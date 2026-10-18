"""Deterministic verification plan, frozen before implementation (SPEC-001
remediation -- Finding 8; execution boundary strengthened in Finding 1 and
Finding 5 of the second remediation pass).

`resolve_verification_plan` captures the plan (which commands, what
repository-relative path each command's applicability depends on, and --
for npm-script-backed commands -- the literal script string each command
depends on) from `repo_root` exactly once, at Phase 1, before any
implementation agent runs. `execute_plan` then runs that frozen plan
against the isolated workspace at each verification point:

- If a step's required input has disappeared, that step is recorded as a
  hard failure, not skipped (Finding 8: "the plan's step count never
  shrinks").
- If a step's npm script definition (e.g. `scripts.build` in
  `frontend/package.json`) has changed since the plan was frozen, that
  step is also recorded as a hard failure rather than being run as
  whatever it now resolves to (Finding 5: an implementation agent must
  not be able to redefine `npm run build` into a successful no-op and
  have that silently satisfy verification -- "preserve the meaning of
  verification, not only command strings").
- Every command runs through `peos.sandbox.sandboxed_verification_command`
  and `peos.sandbox.sandboxed_env` (Finding 1, BLOCKER): verification
  executes whatever code is in the workspace at this point, which is not
  trusted, so it must never run with the orchestrator's real environment
  or without filesystem/network confinement. If the sandbox cannot be
  built on this platform, every remaining step fails closed (Finding 1 --
  "if this cannot be robustly enforced ... must stop"), never falling
  back to an unsandboxed subprocess.

`resolve_verification_plan` also parses the governing specification's
Verification section(s) for two distinct kinds of requirement (SPEC-005
dogfood remediation -- a natural-language verification requirement was
previously misparsed as literal shell commands and nearly handed to
`sandbox-exec`):

- **Executable commands** (`VerificationPlan.steps`): only a line that is
  part of an isolated Markdown indented-code-block run (preceded by a
  blank line, the heading, or another such line) is ever treated as a
  literal command. A wrapped continuation line of ordinary list/paragraph
  prose, even though it may land at column >=4, is never inferred to be a
  command.
- **Manual/observational requirements** (`VerificationPlan.manual_items`):
  the text of every list item in the Verification section(s) that is not
  such a code-block line, e.g. "run the dev server and visually confirm
  AC-001 through AC-014". These are carried for visibility in the frozen
  plan and the final report only -- `execute_plan` never reads this
  field, so they are never run through `sandbox-exec` or any other
  command runner, and never silently counted as having passed.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from peos.sandbox import (
    CODEX_AUTH_HOME_ENV_VAR,
    IsolatedWorkspace,
    SandboxUnavailableError,
    sandboxed_env,
    sandboxed_verification_command,
)
from peos.verify import CommandResult, VerificationReport, run_command

CommandRunner = Callable[..., CommandResult]
SandboxWrapper = Callable[[list, IsolatedWorkspace, Path, Path], list]

_FRONTEND_PACKAGE_JSON = "frontend/package.json"

# Latest Codex review, Finding 3: the verification plan was derived
# entirely from repository structure (pytest always, npm scripts if
# frontend/ exists) and never looked at the governing specification's own
# text at all -- a spec declaring an additional required verification
# command had no way to make that command actually run. This is a
# deliberately narrow, deterministic text convention (not an open-ended
# AI-generated verification system, per the review's own constraint):
# a line indented by at least 4 spaces or a tab, inside a heading section
# whose text contains the word "Verification" (case-insensitive), is a
# literal command SPEC-001 requires PEOS to run -- but ONLY when that line
# sits in an isolated block of such lines, i.e. a genuine Markdown
# indented code block (preceded by a blank line, the section heading, or
# another such line; CommonMark's own rule for what makes a 4-space
# indentation a code block rather than a list item's wrapped continuation
# text). This is the exact convention SPEC-001's own Section 8 already
# uses for its example commands (`python -m pytest -q`, `npm run lint`,
# etc.) -- so parsing it reproduces today's default plan from the spec
# text itself, and a future spec can add further required commands the
# same way, with zero new authoring convention to learn.
#
# SPEC-005 dogfood defect (this module's regression tests): a Verification
# Requirements section written as an ordinary Markdown numbered/bulleted
# list has bullet text wrapped across physical lines, with the wrapped
# continuation lines indented to align under the bullet marker -- e.g.
#     - `python -m pytest -q` at the repository root (confirms AC-015
#       — expect no change in results).
# Without the blank-line-isolation check, the second physical line above
# (indented >=4 spaces, but a continuation of a list item's prose, not a
# code block) was indistinguishable from a literal command and was fed
# straight to `shlex.split` and then `sandbox-exec` -- i.e. PEOS inferred
# an executable shell command from prose, which it must never do. The
# isolation check excludes it: the line immediately before it is neither
# blank nor itself part of an open code-block run, so it is prose, not a
# command candidate.
_HEADING_RE = re.compile(r"^#{1,6}\s")
_VERIFICATION_HEADING_RE = re.compile(r"^#{1,6}\s*[\d.]*\s*Verification\b", re.IGNORECASE)

# Deterministic list-item marker convention used by
# `_parse_spec_manual_verification_items` below: `- `, `* `, `+ `, or
# `1. ` / `1) ` at the start of the line (after leading whitespace).
_LIST_MARKER_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")


def _is_indented_line(line: str) -> bool:
    return line.startswith("    ") or line.startswith("\t")


def _parse_spec_verification_commands(spec_text: str) -> list[str]:
    """Extract literal shell-command lines from the governing
    specification's Verification section(s). Deterministic text parsing
    only; never AI-interpreted. Order-preserving, de-duplicated.

    A line only counts as a command line when it is part of an isolated
    run of indented lines -- a genuine Markdown indented code block, per
    the module-level comment above -- never a wrapped continuation line
    of ordinary list/paragraph prose that merely happens to land at
    column >=4.
    """
    commands: list[str] = []
    in_section = False
    prev_blank = True
    in_code_block = False
    for line in spec_text.splitlines():
        if _HEADING_RE.match(line):
            in_section = bool(_VERIFICATION_HEADING_RE.match(line))
            prev_blank = True
            in_code_block = False
            continue
        if not in_section:
            continue
        if not line.strip():
            prev_blank = True
            in_code_block = False
            continue
        if _is_indented_line(line) and (prev_blank or in_code_block):
            stripped = line.strip()
            if stripped:
                commands.append(stripped)
            in_code_block = True
        else:
            in_code_block = False
        prev_blank = False
    seen: set[str] = set()
    unique: list[str] = []
    for c in commands:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def _parse_spec_manual_verification_items(spec_text: str) -> list[str]:
    """Extract manual/observational verification requirements from the
    governing specification's Verification section(s): the text of every
    top-level list item (`- `, `* `, `+ `, or `N. `/`N) `), with its
    wrapped continuation lines rejoined into one logical line.

    These are never parsed into shell commands and never executed --
    they are carried into the frozen `VerificationPlan` purely for
    visibility (Finding: "manual verification requirements must remain
    visible ... but must not be passed to sandbox-exec"). A line that is
    part of an isolated indented-code-block run (see
    `_parse_spec_verification_commands`) is excluded here: it is already
    represented as an executable step, not a manual one. Order-preserving,
    de-duplicated.
    """
    items: list[str] = []
    in_section = False
    current: list[str] | None = None

    def flush() -> None:
        nonlocal current
        if current:
            text = " ".join(part.strip() for part in current if part.strip())
            if text:
                items.append(text)
        current = None

    prev_blank = True
    in_code_block = False
    for line in spec_text.splitlines():
        if _HEADING_RE.match(line):
            flush()
            in_section = bool(_VERIFICATION_HEADING_RE.match(line))
            prev_blank = True
            in_code_block = False
            continue
        if not in_section:
            continue
        if not line.strip():
            flush()
            prev_blank = True
            in_code_block = False
            continue

        is_code_block_line = _is_indented_line(line) and (prev_blank or in_code_block)
        marker_match = _LIST_MARKER_RE.match(line) if not is_code_block_line else None

        if is_code_block_line:
            # Belongs to `_parse_spec_verification_commands` instead.
            flush()
            in_code_block = True
        elif marker_match is not None:
            flush()
            current = [marker_match.group(1)]
            in_code_block = False
        elif current is not None:
            current.append(line)
            in_code_block = False
        else:
            # Prose outside any list item (e.g. the section's lead-in
            # paragraph) -- not a verification requirement of its own.
            flush()
            in_code_block = False
        prev_blank = False
    flush()

    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


@dataclass(frozen=True)
class VerificationStep:
    name: str
    command: tuple[str, ...]
    cwd_relative: str
    required_input: str  # path, relative to the workspace root, that must exist
    extra_required_inputs: tuple[str, ...] = field(default_factory=tuple)
    # For npm-script-backed steps: the literal `scripts.<key>` string value
    # read from `repo_root`'s package.json when the plan was frozen, or
    # None for steps not backed by an npm script (e.g. pytest). Finding 5.
    frozen_npm_script_key: str | None = None
    frozen_npm_script_value: str | None = None
    # Set when a spec-declared verification command (Finding 3) could not
    # be parsed into a runnable argv at freeze time (e.g. unbalanced
    # quoting). The step is still included in the frozen plan -- never
    # silently dropped -- and always hard-fails with this message at
    # execute_plan time, rather than being skipped.
    parse_error: str | None = None


@dataclass(frozen=True)
class VerificationPlan:
    steps: tuple[VerificationStep, ...] = field(default_factory=tuple)
    # Manual/observational verification requirements found in the
    # governing specification's Verification section(s) (e.g. "run the
    # dev server and visually confirm AC-001 through AC-014"). Carried
    # for visibility only -- `execute_plan` never reads this field, so
    # these items are never run through `sandbox-exec` or any other
    # command runner, and never contribute to `VerificationReport.passed`.
    manual_items: tuple[str, ...] = field(default_factory=tuple)


def _command_key(command: tuple[str, ...]) -> tuple[str, ...]:
    """Normalize a command tuple for duplicate detection: the executable
    is compared by basename, not by its exact (possibly interpreter-
    specific, e.g. `sys.executable`'s absolute venv path) string, so a
    spec-declared `python -m pytest -q` is recognized as the same
    requirement as the default plan's
    `<sys.executable> -m pytest -q` rather than added as a redundant
    second step that might resolve to a different interpreter inside the
    sandbox.
    """
    if not command:
        return command
    return (Path(command[0]).name, *command[1:])


def _read_npm_script(package_json: Path, key: str) -> str | None:
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    scripts = data.get("scripts")
    if not isinstance(scripts, dict):
        return None
    value = scripts.get(key)
    return value if isinstance(value, str) else None


def resolve_verification_plan(repo_root: Path, spec_path: Path | None = None) -> VerificationPlan:
    """Freeze the verification plan from `repo_root`'s state, once,
    before any implementation agent runs. Mirrors
    `.github/workflows/ci.yml`: the Python test suite always, and the
    frontend lint/typecheck/build scripts if `frontend/` exists now.

    If `spec_path` is given, the governing specification's own
    Verification section(s) (Finding 3) are parsed for additional
    required commands, read once here (from `repo_root`'s authoritative
    copy, before any implementation agent runs) and appended to the
    frozen plan; a command already present in the default plan is not
    duplicated.
    """
    steps = [
        VerificationStep(
            name="python tests (pytest -q)",
            command=(sys.executable, "-m", "pytest", "-q"),
            cwd_relative=".",
            required_input="tests",
        ),
    ]
    frontend_dir = repo_root / "frontend"
    if frontend_dir.is_dir():
        package_json = frontend_dir / "package.json"
        for step_name, script_key in (
            ("frontend lint", "lint"),
            ("frontend typecheck", "typecheck"),
            ("frontend build", "build"),
        ):
            steps.append(
                VerificationStep(
                    name=step_name,
                    command=("npm", "run", script_key),
                    cwd_relative="frontend",
                    required_input=_FRONTEND_PACKAGE_JSON,
                    extra_required_inputs=("frontend/node_modules",),
                    frozen_npm_script_key=script_key,
                    frozen_npm_script_value=_read_npm_script(package_json, script_key),
                )
            )

    manual_items: list[str] = []
    if spec_path is not None and spec_path.is_file():
        spec_text = spec_path.read_text(encoding="utf-8", errors="replace")
        manual_items = _parse_spec_manual_verification_items(spec_text)
        existing_commands = {_command_key(step.command) for step in steps}
        for raw_command in _parse_spec_verification_commands(spec_text):
            try:
                parsed = tuple(shlex.split(raw_command))
            except ValueError as exc:
                # Unparseable spec-declared command: never silently
                # dropped (that would be exactly the "spec-specific
                # verification requirement disappears" gap this exists to
                # close) -- included as a step that always hard-fails.
                steps.append(
                    VerificationStep(
                        name=f"spec-required verification (unparseable): {raw_command!r}",
                        command=(),
                        cwd_relative=".",
                        required_input=".",
                        parse_error=(
                            f"governing specification declared a verification command "
                            f"that could not be parsed: {raw_command!r} ({exc})"
                        ),
                    )
                )
                continue
            if not parsed or _command_key(parsed) in existing_commands:
                continue
            steps.append(
                VerificationStep(
                    name=f"spec-required verification: {raw_command}",
                    command=parsed,
                    cwd_relative=".",
                    required_input=".",
                )
            )
            existing_commands.add(_command_key(parsed))

    return VerificationPlan(tuple(steps), tuple(manual_items))


def _missing_input(step: VerificationStep, workspace_root: Path) -> str | None:
    for rel in (step.required_input, *step.extra_required_inputs):
        if not (workspace_root / rel).exists():
            return rel
    return None


def _npm_script_definition_changed(step: VerificationStep, workspace_root: Path) -> str | None:
    if step.frozen_npm_script_key is None:
        return None
    current = _read_npm_script(workspace_root / _FRONTEND_PACKAGE_JSON, step.frozen_npm_script_key)
    if current != step.frozen_npm_script_value:
        return (
            f"scripts.{step.frozen_npm_script_key} changed after the verification plan was "
            f"frozen: expected {step.frozen_npm_script_value!r}, found {current!r}"
        )
    return None


def _hard_failure(step: VerificationStep, step_cwd: Path, reason: str) -> CommandResult:
    return CommandResult(
        name=step.name,
        command=step.command,
        cwd=str(step_cwd),
        returncode=-1,
        stdout="",
        stderr="",
        ran=False,
        error=reason,
    )


def execute_plan(
    plan: VerificationPlan,
    workspace: IsolatedWorkspace,
    repo_root: Path,
    sandbox_profile_dir: Path,
    command_runner: CommandRunner = run_command,
    sandbox_wrapper: SandboxWrapper = sandboxed_verification_command,
    environ: dict | None = None,
    extra_deny_read_paths: tuple[Path, ...] = (),
) -> VerificationReport:
    """Execute a previously frozen `plan` against `workspace.path`, with
    every command confined by the verification sandbox (Finding 1) and
    run with the isolated environment (`sandboxed_env`).

    `sandbox_profile_dir` is a scratch directory (not inside the
    workspace, so it is never mistaken for a workspace change) used to
    write the per-run Seatbelt profile file. `sandbox_wrapper` defaults to
    the real OS-enforced wrapper; routing/logic tests that don't need a
    real `sandbox-exec` invocation may inject a trivial one (see
    tests/test_peos_verification_plan.py) -- the real sandbox boundary
    itself is exercised for real, platform-gated, in
    tests/test_peos_sandbox.py.

    SPEC-003 remediation Finding 2 (MAJOR): `environ` is the
    orchestrator's own environment (defaulting to `os.environ`, exactly
    like `sandboxed_env()`'s own `base_env` default) -- `sandboxed_env`
    already strips `PEOS_CODEX_AUTH_HOME`/`CODEX_HOME`/every other
    agent-auth variable from the environment this builds, so
    verification never *inherits* either agent's credential or
    configuration. `extra_deny_read_paths` additionally denies
    verification *filesystem reads* of the resolved Codex authentication
    directory (when `PEOS_CODEX_AUTH_HOME` is configured in `environ`),
    closing the complementary gap: an environment variable can be
    stripped, but the directory it would have pointed to is still a real
    path on disk that untrusted verification code could otherwise open
    directly. Neither the accepted-residual-risk carve-out for Codex's
    own shell tool (SPEC-003 Known Limitations) nor anything else
    widens this -- verification has no legitimate reason to read that
    directory at all.
    """
    environ = environ if environ is not None else os.environ
    env = sandboxed_env(workspace.home_dir, base_env=environ)
    codex_auth_home_value = environ.get(CODEX_AUTH_HOME_ENV_VAR)
    deny_read_paths = tuple(extra_deny_read_paths) + (
        (Path(codex_auth_home_value),) if codex_auth_home_value else ()
    )
    results = []
    for step in plan.steps:
        step_cwd = workspace.path / step.cwd_relative
        if step.parse_error is not None:
            results.append(_hard_failure(step, step_cwd, step.parse_error))
            continue

        missing = _missing_input(step, workspace.path)
        if missing is not None:
            results.append(
                _hard_failure(
                    step, step_cwd,
                    f"required verification input missing: {missing} (the verification "
                    "plan was frozen before implementation began and cannot be silently "
                    "reduced -- SPEC-001 Finding 8)",
                )
            )
            continue

        script_changed = _npm_script_definition_changed(step, workspace.path)
        if script_changed is not None:
            results.append(_hard_failure(step, step_cwd, f"{script_changed} (SPEC-001 Finding 5)"))
            continue

        try:
            sandboxed_command = sandbox_wrapper(
                list(step.command), workspace, repo_root, sandbox_profile_dir,
                extra_deny_read_paths=deny_read_paths,
            )
        except SandboxUnavailableError as exc:
            results.append(_hard_failure(step, step_cwd, str(exc)))
            continue

        results.append(command_runner(step.name, sandboxed_command, step_cwd, env=env))
    return VerificationReport(tuple(results))
