"""Codex as the independent reviewer (SPEC-001 Phase 3/5, AC-005/AC-007,
remediated per Findings 4-6).

Invokes the local `codex exec` CLI non-interactively against the same
isolated workspace Claude implemented in (peos/sandbox.py) -- never the
authoritative repository directly -- constrained to `--sandbox
read-only`. This was verified empirically against the installed CLI
(`codex-cli 0.162.1`): asked to write a file via its shell tool under
`--sandbox read-only`, the write failed with "operation not permitted"
and the file was never created. That is an OS-enforced sandbox denial of
*that one write attempt*, not a prompt instruction Codex chose to honor --
but it is not a claim that `--sandbox read-only` is a full OS sandbox in
every other respect (e.g. network policy for shell commands it runs was
not independently characterized here). The structural backstop that does
not depend on characterizing every property of `--sandbox read-only` is
the before/after repository and workspace fingerprint comparison in
`peos/workflow.py::_codex_phase` (Finding 3): if nothing Git can see
changed, no write occurred, regardless of which sandbox mechanism
prevented it. `--ignore-user-config`/`--ignore-rules` additionally skip
loading `$CODEX_HOME/config.toml` (where MCP servers would be configured)
and any execpolicy `.rules` file, reducing inherited external
capabilities where the installed CLI exposes a flag to do so.

Finding 5 (strict Structured Outputs schema): `REVIEW_SCHEMA` lists every
property in `required` and expresses optional semantics with nullable
types (`"type": ["array", "null"]`) instead of omitting them from
`required`. This exact shape (all-required + nullable-for-optional,
`additionalProperties: false` at every object level) was verified
end-to-end against the installed `codex exec --output-schema` /
`--output-last-message` contract with a live invocation; the model's
JSON conformed with no schema-rejection and no coercion needed.

Finding 4 (adversarial-proof parsing): `_validate_review_payload` treats
a non-dict top level (e.g. `[]`), a missing/non-list `findings` (e.g.
`null`), any finding missing a required field or using an unrecognized
enum value, and any internally contradictory APPROVE (a finding with
`severity` in {blocking, major} or `requires_human_decision=true`, or an
acceptance-criteria item with `met=false`) as fail-closed parse errors --
`ok=False, verdict=None` -- never a guessed APPROVE and never an
uncaught `AttributeError`/`TypeError`.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

Runner = Callable[..., subprocess.CompletedProcess]

_SEVERITIES = ("blocking", "major", "minor", "info")
_CATEGORIES = (
    "implementation_defect",
    "specification_ambiguity",
    "missing_test",
    "missing_validation_evidence",
    "architecture_concern",
    "non_blocking_improvement",
)
_BLOCKING_SEVERITIES = ("blocking", "major")

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["APPROVE", "CHANGES_REQUIRED"]},
        "summary": {"type": "string"},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": list(_SEVERITIES)},
                    "category": {"type": "string", "enum": list(_CATEGORIES)},
                    "description": {"type": "string"},
                    "requires_human_decision": {"type": "boolean"},
                },
                "required": ["severity", "category", "description", "requires_human_decision"],
                "additionalProperties": False,
            },
        },
        "acceptance_criteria": {
            "type": ["array", "null"],
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "met": {"type": "boolean"},
                    "note": {"type": ["string", "null"]},
                },
                "required": ["id", "met", "note"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["verdict", "summary", "findings", "acceptance_criteria"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class Finding:
    severity: str
    category: str
    description: str
    requires_human_decision: bool


@dataclass(frozen=True)
class CodexReviewResult:
    returncode: int
    verdict: str | None
    summary: str
    findings: tuple[Finding, ...]
    acceptance_criteria: tuple[dict, ...]
    raw_stdout: str
    raw_stderr: str
    ok: bool
    error: str | None = None

    @property
    def approved(self) -> bool:
        return self.ok and self.verdict == "APPROVE"

    @property
    def human_decision_findings(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.requires_human_decision)


def build_codex_command(prompt: str, schema_path: Path, last_message_path: Path, cwd: Path) -> list[str]:
    return [
        "codex",
        "exec",
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
        # Finding 3 (second pass): reduce inherited external capabilities
        # where the installed CLI supports doing so. `--ignore-user-config`
        # skips loading `$CODEX_HOME/config.toml` -- the file that would
        # otherwise configure MCP servers for this invocation (auth still
        # works; per `codex exec --help`, it is read from $CODEX_HOME
        # independently of config.toml). `--ignore-rules` skips loading any
        # user/project execpolicy `.rules` file, so a file planted inside
        # the workspace by the implementation agent cannot loosen what the
        # reviewer is later allowed to execute.
        "--ignore-user-config",
        "--ignore-rules",
        "-C",
        str(cwd),
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(last_message_path),
        prompt,
    ]


def _fail(returncode: int, error: str, stdout: str = "", stderr: str = "") -> CodexReviewResult:
    return CodexReviewResult(
        returncode=returncode, verdict=None, summary="", findings=(), acceptance_criteria=(),
        raw_stdout=stdout, raw_stderr=stderr, ok=False, error=error,
    )


_FINDING_KEYS = {"severity", "category", "description", "requires_human_decision"}
_AC_KEYS = {"id", "met", "note"}


def _validate_finding(raw: object) -> Finding | None:
    if not isinstance(raw, dict):
        return None
    # Latest Codex review, Finding 2: enforce `additionalProperties: False`
    # locally, not only in the CLI's own schema -- an extra/unrecognized
    # key must be rejected, not silently dropped.
    if set(raw.keys()) - _FINDING_KEYS:
        return None
    # Final acceptance review: every key in _FINDING_KEYS is schema-required
    # (none are nullable), so a missing key must be rejected rather than
    # silently treated as the value `None` that `.get()` would also return
    # for an explicit null -- same class of defect as the AC `note` gap
    # below, audited here for completeness even though the non-nullable
    # type/enum checks already happen to catch it.
    if _FINDING_KEYS - set(raw.keys()):
        return None
    severity = raw.get("severity")
    category = raw.get("category")
    description = raw.get("description")
    requires = raw.get("requires_human_decision")
    if severity not in _SEVERITIES:
        return None
    if category not in _CATEGORIES:
        return None
    if not isinstance(description, str) or not description.strip():
        return None
    if not isinstance(requires, bool):
        return None
    return Finding(severity=severity, category=category, description=description, requires_human_decision=requires)


def _validate_acceptance_criteria(raw: object) -> tuple[dict, ...] | None:
    """Returns None (invalid) or a tuple of validated AC dicts. `raw` may
    be `None` (nullable per schema) which validates to an empty tuple.
    """
    if raw is None:
        return ()
    if not isinstance(raw, list):
        return None
    result = []
    for item in raw:
        if not isinstance(item, dict):
            return None
        if set(item.keys()) - _AC_KEYS:
            return None
        # Latest final acceptance review, directly reproduced:
        # {"id":"AC-001","met":true} (no "note" key) was accepted because
        # `.get("note")` returns `None` for a missing key -- indistinguishable
        # from an explicit `"note": null`, which the nullable-type check below
        # treats as valid. `note` is schema-required (nullable value, but the
        # key itself must be present), so presence is checked first.
        if _AC_KEYS - set(item.keys()):
            return None
        ac_id, met, note = item.get("id"), item.get("met"), item.get("note")
        if not isinstance(ac_id, str) or not ac_id.strip() or not isinstance(met, bool):
            return None
        # Latest Codex review, Finding 2, directly reproduced: a
        # schema-invalid `note` (e.g. a number -- the schema requires
        # string or null) was previously silently coerced to "" instead of
        # being rejected, letting a malformed acceptance-criteria payload
        # through as a well-formed (if unhelpfully blank-noted) result.
        if note is not None and not isinstance(note, str):
            return None
        result.append({"id": ac_id, "met": met, "note": note if isinstance(note, str) else ""})
    return tuple(result)


def _validate_review_payload(data: object) -> CodexReviewResult:
    """Strictly validate a parsed Codex payload. Fails closed on every
    reproduced adversarial case (SPEC-001 remediation Finding 4): a
    non-dict top level, an incomplete/missing `findings`, an unrecognized
    enum, and an internally contradictory APPROVE (a blocking/major or
    human-decision finding, or an unmet acceptance criterion, alongside
    verdict=APPROVE) all yield `ok=False`.
    """
    if not isinstance(data, dict):
        return _fail(0, f"Codex top-level output was not a JSON object (got {type(data).__name__})")

    _TOP_LEVEL_KEYS = {"verdict", "summary", "findings", "acceptance_criteria"}
    unexpected_keys = set(data.keys()) - _TOP_LEVEL_KEYS
    if unexpected_keys:
        return _fail(
            0,
            f"Codex top-level output contains unexpected field(s) not in the "
            f"schema: {sorted(unexpected_keys)!r}",
        )

    # Final acceptance review: all four top-level keys are schema-required
    # (REVIEW_SCHEMA["required"]), including `acceptance_criteria` whose
    # VALUE may be null but whose KEY must still be present. A missing key
    # must not be treated the same as an explicit null via `.get()`.
    missing_keys = set(REVIEW_SCHEMA["required"]) - set(data.keys())
    if missing_keys:
        return _fail(
            0,
            f"Codex top-level output is missing required field(s): {sorted(missing_keys)!r}",
        )

    verdict = data.get("verdict")
    if verdict not in ("APPROVE", "CHANGES_REQUIRED"):
        return _fail(0, f"Codex returned an uninterpretable verdict: {verdict!r}")

    summary = data.get("summary")
    if not isinstance(summary, str):
        return _fail(0, "Codex output is missing a string `summary` field")

    raw_findings = data.get("findings")
    if not isinstance(raw_findings, list):
        return _fail(0, f"Codex `findings` field must be a list, got {type(raw_findings).__name__}")

    findings = []
    for raw in raw_findings:
        finding = _validate_finding(raw)
        if finding is None:
            return _fail(0, f"Codex returned a malformed finding object: {raw!r}")
        findings.append(finding)
    findings = tuple(findings)

    acceptance_criteria = _validate_acceptance_criteria(data.get("acceptance_criteria"))
    if acceptance_criteria is None:
        return _fail(0, f"Codex `acceptance_criteria` field is malformed: {data.get('acceptance_criteria')!r}")

    if verdict == "APPROVE":
        contradicting = [f for f in findings if f.severity in _BLOCKING_SEVERITIES or f.requires_human_decision]
        if contradicting:
            return _fail(
                0,
                "Codex returned a contradictory APPROVE: verdict=APPROVE but "
                f"{len(contradicting)} finding(s) are blocking/major or require a "
                "human decision. Failing closed rather than trusting the verdict field alone.",
            )
        # SPEC-001 remediation Finding 2 (second pass): an APPROVE accepted
        # alongside a null/empty acceptance_criteria was reproduced as a
        # gap. The review prompt still permits null acceptance_criteria
        # for CHANGES_REQUIRED (a specification may define none), but an
        # APPROVE must be backed by actual acceptance-criteria evidence --
        # a specification with zero numbered ACs cannot be APPROVEd
        # through this path.
        if data.get("acceptance_criteria") is None or not acceptance_criteria:
            return _fail(
                0,
                "Codex returned a contradictory APPROVE: verdict=APPROVE but no "
                "acceptance_criteria evidence was provided. APPROVE requires a "
                "non-empty acceptance-criteria assessment; failing closed rather "
                "than trusting the verdict field alone.",
            )
        unmet = [ac for ac in acceptance_criteria if not ac["met"]]
        if unmet:
            ids = ", ".join(ac["id"] for ac in unmet)
            return _fail(
                0,
                f"Codex returned a contradictory APPROVE: verdict=APPROVE but "
                f"acceptance criteria not met: {ids}. Failing closed rather than "
                "trusting the verdict field alone.",
            )

    return CodexReviewResult(
        returncode=0, verdict=verdict, summary=summary, findings=findings,
        acceptance_criteria=acceptance_criteria, raw_stdout="", raw_stderr="", ok=True,
    )


def run_codex_review(
    prompt: str,
    cwd: Path,
    runner: Runner = subprocess.run,
    timeout: int = 3600,
    env: dict | None = None,
) -> CodexReviewResult:
    """Invoke Codex for an independent review of `cwd` (the isolated
    workspace, never the authoritative repository directly) and capture
    a strictly validated structured result.

    Fails closed: any subprocess error, non-zero exit, output that
    cannot be read/parsed, or output that fails `_validate_review_payload`
    yields `ok=False, verdict=None` rather than guessing APPROVE
    (SPEC-001 Section 11, AC-011).
    """
    with tempfile.TemporaryDirectory(prefix="peos-codex-") as tmp:
        schema_path = Path(tmp) / "review_schema.json"
        last_message_path = Path(tmp) / "last_message.json"
        schema_path.write_text(json.dumps(REVIEW_SCHEMA), encoding="utf-8")

        command = build_codex_command(prompt, schema_path, last_message_path, cwd)
        try:
            proc = runner(
                command, cwd=str(cwd), capture_output=True, text=True,
                timeout=timeout, env=env, stdin=subprocess.DEVNULL,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
            return _fail(-1, f"Codex subprocess failed to run: {exc}")

        if proc.returncode != 0:
            return _fail(
                proc.returncode, f"codex exec exited with status {proc.returncode}",
                stdout=proc.stdout, stderr=proc.stderr,
            )

        try:
            last_message = last_message_path.read_text(encoding="utf-8")
        except OSError as exc:
            return _fail(
                proc.returncode, f"could not read Codex last-message file: {exc}",
                stdout=proc.stdout, stderr=proc.stderr,
            )

        try:
            data = json.loads(last_message)
        except json.JSONDecodeError as exc:
            return _fail(
                proc.returncode, f"could not parse Codex JSON output: {exc}",
                stdout=proc.stdout, stderr=proc.stderr,
            )

        result = _validate_review_payload(data)
        if not result.ok:
            return CodexReviewResult(
                returncode=proc.returncode, verdict=None, summary="", findings=(),
                acceptance_criteria=(), raw_stdout=proc.stdout, raw_stderr=proc.stderr,
                ok=False, error=result.error,
            )
        return CodexReviewResult(
            returncode=proc.returncode, verdict=result.verdict, summary=result.summary,
            findings=result.findings, acceptance_criteria=result.acceptance_criteria,
            raw_stdout=proc.stdout, raw_stderr=proc.stderr, ok=True,
        )
