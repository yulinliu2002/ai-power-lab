"""Deterministic local verification primitives (SPEC-001 Section 8, AC-004).

PEOS must not treat an agent's claim that "tests should pass" as
verification evidence. `run_command` executes one verification command as
a subprocess and records its exit status/output; it introduces no policy
about *which* commands to run or *how* to confine them -- that is
`peos/verification_plan.py` (the frozen plan, SPEC-001 Finding 8) and
`peos/sandbox.py` (the execution boundary, SPEC-001 Finding 1), the only
two callers of this module. This module has no other entry point:
verification must never run outside the frozen, sandboxed path.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

CommandRunner = Callable[..., "CommandResult"]


@dataclass(frozen=True)
class CommandResult:
    name: str
    command: tuple[str, ...]
    cwd: str
    returncode: int
    stdout: str
    stderr: str
    ran: bool = True
    error: str | None = None

    @property
    def passed(self) -> bool:
        return self.ran and self.returncode == 0


@dataclass(frozen=True)
class VerificationReport:
    results: tuple[CommandResult, ...] = field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def failures(self) -> tuple[CommandResult, ...]:
        return tuple(r for r in self.results if not r.passed)


def run_command(
    name: str,
    command: list[str],
    cwd: Path,
    timeout: int = 900,
    env: dict | None = None,
) -> CommandResult:
    """Run one verification command and capture its exit status/output.

    `env`, when given, is used verbatim as the subprocess environment
    (SPEC-001 remediation Finding 1): verification commands execute
    whatever code lives in the workspace at this point, so they must run
    with the same stripped/isolated environment (`peos.sandbox.
    sandboxed_env`) as the Claude/Codex invocations, not the orchestrator's
    real environment.
    """
    try:
        proc = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        return CommandResult(
            name=name,
            command=tuple(command),
            cwd=str(cwd),
            returncode=-1,
            stdout="",
            stderr="",
            ran=False,
            error=str(exc),
        )
    return CommandResult(
        name=name,
        command=tuple(command),
        cwd=str(cwd),
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )
