"""Claude Code as the implementation agent (SPEC-001 Phase 2/4, AC-003/AC-006,
remediated per Findings 1-4).

Invokes the local `claude` CLI non-interactively as a controlled
subprocess against an isolated workspace (peos/sandbox.py), not the
authoritative repository, and requires a machine-validated structured
result instead of trusting free text.

Real capability restriction (Finding 2), verified against the installed
CLI (`claude --version` 2.1.296) rather than assumed:

- `--restricted` with Bash omitted from `--tools` leaves Claude with no
  shell/code-execution tool at all. Verified empirically: with only
  "Read Edit Write Grep Glob" granted, an attempt to run a shell command
  has no tool to call, and an attempt to Read/Write a path outside the
  invocation's working directory is rejected with a tool error
  ("--restricted confines the file tools to the working directory"),
  recorded in the CLI's own `permission_denials` list -- not merely
  discouraged by the prompt.
- `--permission-mode acceptEdits --permission-prompts none` lets ordinary
  Read/Edit/Write proceed non-interactively while `--restricted` still
  "refuses bypassPermissions" outright (confirmed: passing both is a
  hard CLI error), so this run can never fall back to the old
  no-restriction mode by accident.
- `--strict-mcp-config` with no `--mcp-config` passed means zero MCP
  servers load, and no `--plugin-dir`/`--plugin-url` means no plugin is
  requested; `--restricted` additionally ignores user/project/local
  settings files (managed settings and `--settings` would still apply,
  and neither is passed here).

Structured result contract (Finding 3): `--json-schema` is the CLI's own
native structured-output mechanism (parallel to Codex's
`--output-schema`), verified to populate a top-level `structured_output`
key in `--output-format json` output. `run_claude` fails closed
(`ok=False, status=None`) on anything that is not a valid, fully-formed
`structured_output` matching `CLAUDE_RESULT_SCHEMA` -- a missing or
malformed result is never treated as success, and `status="HUMAN_GATE"`
is a terminal signal the caller (peos/workflow.py) must stop on
immediately, never advance past.

Residual trust boundary: see peos/sandbox.py's module docstring and
peos/report.py's KNOWN_LIMITATIONS for what this does and does not
guarantee.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ALLOWED_TOOLS = "Read Edit Write Grep Glob"

VALID_STATUSES = ("COMPLETED", "HUMAN_GATE", "FAILED")
VALID_GATE_CATEGORIES = (
    "physics",
    "control",
    "protection",
    "architecture",
    "specification_intent",
    "ambiguous_specification",
    "git_release_action",
    "other",
)

CLAUDE_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": list(VALID_STATUSES)},
        "gate_category": {
            "type": ["string", "null"],
            "enum": [*VALID_GATE_CATEGORIES, None],
        },
        "gate_reason": {"type": ["string", "null"]},
        "summary": {"type": "string"},
    },
    "required": ["status", "gate_category", "gate_reason", "summary"],
    "additionalProperties": False,
}

Runner = Callable[..., subprocess.CompletedProcess]


@dataclass(frozen=True)
class ClaudeRunResult:
    returncode: int
    stdout: str
    stderr: str
    status: str | None  # "COMPLETED" | "HUMAN_GATE" | "FAILED" | None (uninterpretable)
    gate_category: str | None
    gate_reason: str | None
    summary: str
    ok: bool
    error: str | None = None

    @property
    def human_gate(self) -> bool:
        return self.status == "HUMAN_GATE"


def _uninterpretable(error: str, returncode: int = -1, stdout: str = "", stderr: str = "") -> ClaudeRunResult:
    return ClaudeRunResult(
        returncode=returncode, stdout=stdout, stderr=stderr,
        status=None, gate_category=None, gate_reason=None, summary="",
        ok=False, error=error,
    )


def build_claude_command(prompt: str) -> list[str]:
    return [
        "claude",
        "-p",
        "--output-format", "json",
        "--restricted",
        "--tools", ALLOWED_TOOLS,
        "--permission-mode", "acceptEdits",
        "--permission-prompts", "none",
        "--strict-mcp-config",
        "--json-schema", json.dumps(CLAUDE_RESULT_SCHEMA),
        prompt,
    ]


def run_claude(
    prompt: str,
    cwd: Path,
    runner: Runner = subprocess.run,
    timeout: int = 3600,
    env: dict | None = None,
) -> ClaudeRunResult:
    """Invoke Claude Code non-interactively against `cwd` (the isolated
    workspace, never the authoritative repository) and capture a
    strictly validated structured result.

    Fails closed (SPEC-001 Section 11, Finding 4): any subprocess error,
    non-zero exit, unparseable JSON, non-object top-level output, missing
    or malformed `structured_output`, unrecognized `status`, or a
    `HUMAN_GATE` status without a `gate_reason` all yield
    `ok=False, status=None-or-"HUMAN_GATE"` with `error` set -- never a
    guessed success and never an uncaught exception.
    """
    command = build_claude_command(prompt)
    try:
        proc = runner(
            command, cwd=str(cwd), capture_output=True, text=True,
            timeout=timeout, env=env, stdin=subprocess.DEVNULL,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        return _uninterpretable(f"Claude Code subprocess failed to run: {exc}")

    if proc.returncode != 0:
        return _uninterpretable(
            f"claude exited with status {proc.returncode}",
            returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr,
        )

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return _uninterpretable(
            f"could not parse Claude Code JSON output: {exc}",
            returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr,
        )

    if not isinstance(data, dict):
        return _uninterpretable(
            f"Claude Code top-level output was not a JSON object (got {type(data).__name__})",
            returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr,
        )

    if bool(data.get("is_error", False)):
        return _uninterpretable(
            "Claude Code reported is_error=true",
            returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr,
        )

    structured = data.get("structured_output")
    if not isinstance(structured, dict):
        return _uninterpretable(
            "Claude Code did not return a structured result (structured_output "
            "missing or not a JSON object); cannot determine status",
            returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr,
        )

    # Latest Codex review, Finding 2: local validation must strictly match
    # CLAUDE_RESULT_SCHEMA, including `additionalProperties: False` -- an
    # extra, unrecognized field must be rejected rather than silently
    # ignored, since this code (not the CLI's own schema enforcement) is
    # the actual trust boundary for anything downstream of `run_claude`.
    unexpected_keys = set(structured.keys()) - {"status", "gate_category", "gate_reason", "summary"}
    if unexpected_keys:
        return _uninterpretable(
            f"Claude Code structured result contains unexpected field(s) not in "
            f"the schema: {sorted(unexpected_keys)!r}",
            returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr,
        )

    # Final acceptance review: `gate_category` and `gate_reason` are
    # schema-required KEYS even though their VALUES may be null. Using
    # `.get()` below cannot distinguish an omitted key from an explicit
    # `null` value, so presence must be checked against
    # CLAUDE_RESULT_SCHEMA["required"] before any value is read, or a
    # payload missing the keys entirely is silently treated the same as
    # one that supplied them as null.
    missing_keys = set(CLAUDE_RESULT_SCHEMA["required"]) - set(structured.keys())
    if missing_keys:
        return _uninterpretable(
            f"Claude Code structured result is missing required field(s): "
            f"{sorted(missing_keys)!r}",
            returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr,
        )

    status = structured.get("status")
    if status not in VALID_STATUSES:
        return _uninterpretable(
            f"Claude Code returned an uninterpretable status: {status!r}",
            returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr,
        )

    summary = structured.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return _uninterpretable(
            "Claude Code structured result is missing a non-empty summary",
            returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr,
        )

    raw_gate_category = structured.get("gate_category")
    raw_gate_reason = structured.get("gate_reason")

    # Latest Codex review, Finding 2, directly reproduced: a schema-invalid
    # gate_reason (e.g. a number or boolean -- the schema requires string
    # or null) was previously silently coerced to None by the isinstance
    # check below, rather than rejected -- which let a self-contradictory
    # or malformed COMPLETED result slip through as ok=True because the
    # coerced None made the status/gate consistency check downstream see
    # nothing to object to. The type itself must be validated before any
    # coercion, or the coercion IS the silent-acceptance bug.
    if raw_gate_reason is not None and not isinstance(raw_gate_reason, str):
        return _uninterpretable(
            f"Claude Code structured result has an invalid gate_reason type "
            f"(expected string or null, got {type(raw_gate_reason).__name__}): "
            f"{raw_gate_reason!r}",
            returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr,
        )
    gate_reason = raw_gate_reason if isinstance(raw_gate_reason, str) and raw_gate_reason.strip() else None

    # SPEC-001 remediation Finding 2 (second pass): status and the gate
    # fields must be internally consistent, not independently validated.
    # Previously an invalid/missing gate_category was silently coerced to
    # None (hiding a malformed HUMAN_GATE), and COMPLETED alongside a
    # populated gate_category/gate_reason was accepted outright (hiding a
    # self-contradictory result). Both are now fail-closed.
    if status == "HUMAN_GATE":
        if raw_gate_category not in VALID_GATE_CATEGORIES:
            return _uninterpretable(
                f"Claude Code returned status=HUMAN_GATE with a missing or invalid "
                f"gate_category: {raw_gate_category!r}",
                returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr,
            )
        if gate_reason is None:
            return _uninterpretable(
                "Claude Code returned status=HUMAN_GATE without a non-empty gate_reason",
                returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr,
            )
        gate_category = raw_gate_category
    else:
        if raw_gate_category is not None or gate_reason is not None:
            return _uninterpretable(
                f"Claude Code returned status={status!r} but also set a human-gate "
                f"gate_category/gate_reason ({raw_gate_category!r}/{raw_gate_reason!r}); "
                "this is internally inconsistent and is rejected rather than guessed at",
                returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr,
            )
        gate_category = None

    ok = status == "COMPLETED"
    return ClaudeRunResult(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        status=status,
        gate_category=gate_category,
        gate_reason=gate_reason,
        summary=summary,
        ok=ok,
        error=None if ok else (gate_reason or f"Claude Code returned status={status}"),
    )
