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
"""

from __future__ import annotations

import json
import re
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from peos.sandbox import IsolatedWorkspace, SandboxUnavailableError, sandboxed_env, sandboxed_verification_command
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
# literal command SPEC-001 requires PEOS to run. This is the exact
# convention SPEC-001's own Section 8 already uses for its example
# commands (`python -m pytest -q`, `npm run lint`, etc.) -- so parsing it
# reproduces today's default plan from the spec text itself, and a future
# spec can add further required commands the same way, with zero new
# authoring convention to learn.
_HEADING_RE = re.compile(r"^#{1,6}\s")
_VERIFICATION_HEADING_RE = re.compile(r"^#{1,6}\s*[\d.]*\s*Verification\b", re.IGNORECASE)


def _parse_spec_verification_commands(spec_text: str) -> list[str]:
    """Extract literal shell-command lines from the governing
    specification's Verification section(s). Deterministic text parsing
    only; never AI-interpreted. Order-preserving, de-duplicated.
    """
    commands: list[str] = []
    in_section = False
    for line in spec_text.splitlines():
        if _HEADING_RE.match(line):
            in_section = bool(_VERIFICATION_HEADING_RE.match(line))
            continue
        if not in_section:
            continue
        if line.startswith("    ") or line.startswith("\t"):
            stripped = line.strip()
            if stripped:
                commands.append(stripped)
    seen: set[str] = set()
    unique: list[str] = []
    for c in commands:
        if c not in seen:
            seen.add(c)
            unique.append(c)
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

    if spec_path is not None and spec_path.is_file():
        spec_text = spec_path.read_text(encoding="utf-8", errors="replace")
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

    return VerificationPlan(tuple(steps))


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
    """
    env = sandboxed_env(workspace.home_dir)
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
            sandboxed_command = sandbox_wrapper(list(step.command), workspace, repo_root, sandbox_profile_dir)
        except SandboxUnavailableError as exc:
            results.append(_hard_failure(step, step_cwd, str(exc)))
            continue

        results.append(command_runner(step.name, sandboxed_command, step_cwd, env=env))
    return VerificationReport(tuple(results))
