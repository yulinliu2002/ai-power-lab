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

SPEC-004 (PEOS Autonomous Engineering Loop, Requirement 8/16/22) adds
three new, nullable-by-default top-level fields, following the same
strictness pattern every other nullable field in this schema already
uses: `reviewer_overrules_dispute` (bool, null only when no dispute is
active this cycle), `addressed_dispute_references` (list[str], null only
when no dispute is active -- required, non-null, and must name every
currently-active dispute reference otherwise), and
`historical_finding_dispositions` (a list of
`{reference, disposition, note}` closing an Outstanding Findings
Register entry -- see `peos/findings_register.py`). `_validate_review_
payload` now additionally takes `active_dispute_references` (to check
the null/non-null symmetry and completeness above) and `required_ac_ids`
(to reject an `APPROVE` whose acceptance-criteria assessment omits any
AC the governing specification declares -- SPEC-004 Requirement 5/
AC-25). Both default to empty, reproducing SPEC-001/SPEC-003's exact
behavior when V2's caller (`peos/workflow.py`) does not supply them
(e.g. cycle 0, or `--max-cycles 1` mode).

Finding 4 (adversarial-proof parsing): `_validate_review_payload` treats
a non-dict top level (e.g. `[]`), a missing/non-list `findings` (e.g.
`null`), any finding missing a required field or using an unrecognized
enum value, and any internally contradictory APPROVE (a finding with
`severity` in {blocking, major} or `requires_human_decision=true`, or an
acceptance-criteria item with `met=false`) as fail-closed parse errors --
`ok=False, verdict=None` -- never a guessed APPROVE and never an
uncaught `AttributeError`/`TypeError`.

SPEC-003 (Failure Diagnostics, Requirement 4): every `error` string this
module builds is routed through `peos.diagnostics.build_diagnostic` --
bounded, redacted, and classified -- rather than built as an ad hoc
f-string. On a non-zero exit, `_extract_codex_error_message` makes a
best-effort attempt to parse `stdout` as JSON for a structured error
field before falling back to a raw-text tail; unlike Claude's
`--output-format json`, `codex exec`'s non-interactive stdout is not
guaranteed to be JSON on a CLI-level failure, so this degrades to the
raw-text fallback in practice -- which is itself the behavior SPEC-003
Requirement 4a specifies for exactly this case.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from peos.diagnostics import build_diagnostic, sanitize_human_text
from peos.findings_register import VALID_DISPOSITIONS, FindingRef

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
        # SPEC-004 Requirement 8/22: null only when no dispute is active
        # this cycle.
        "reviewer_overrules_dispute": {"type": ["boolean", "null"]},
        # SPEC-004 Requirement 8: null only when no dispute is active;
        # otherwise required to list every active dispute's reference.
        "addressed_dispute_references": {"type": ["array", "null"], "items": {"type": "string"}},
        # SPEC-004 Requirement 16: closes Outstanding Findings Register
        # entries. Null is valid whether or not any entry is closed this
        # cycle (most cycles close nothing -- omission, not an error).
        "historical_finding_dispositions": {
            "type": ["array", "null"],
            "items": {
                "type": "object",
                "properties": {
                    "reference": {"type": "string"},
                    "disposition": {"type": "string", "enum": list(VALID_DISPOSITIONS)},
                    "note": {"type": ["string", "null"]},
                },
                "required": ["reference", "disposition", "note"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "verdict", "summary", "findings", "acceptance_criteria",
        "reviewer_overrules_dispute", "addressed_dispute_references",
        "historical_finding_dispositions",
    ],
    "additionalProperties": False,
}

_TOP_LEVEL_KEYS = frozenset(REVIEW_SCHEMA["required"])

# SPEC-004 remediation Finding 7 (MAJOR): the CLI-facing REVIEW_SCHEMA
# (above) requires all seven top-level keys -- matching the "strict
# Structured Outputs" shape the real `codex exec --output-schema`
# contract needs (Finding 5) -- but this module's own local Python-side
# payload validator previously only required the four pre-SPEC-004 keys
# (`_LEGACY_REQUIRED_KEYS`, now removed), silently treating a payload
# that omitted `reviewer_overrules_dispute`/`addressed_dispute_
# references`/`historical_finding_dispositions` entirely the same as one
# that supplied them as an explicit `null`. That is a real gap, not a
# harmless convenience: a payload is validated locally by this function
# on every path (there is no separate "trust the CLI's own schema
# enforcement" path), so a payload that happened to omit a required-but-
# nullable key -- whether from a CLI/model inconsistency or a crafted
# adversarial input -- was accepted here even though it violates
# REVIEW_SCHEMA's own `required` list. "Required-but-nullable" means the
# KEY must be present; only its VALUE may be `null`. `missing_keys` below
# is therefore checked against the complete `_TOP_LEVEL_KEYS` set, with
# no exception for these three -- the fail-closed behavior already
# enforced for `verdict`/`summary`/`findings`/`acceptance_criteria` now
# applies identically to all seven.


@dataclass(frozen=True)
class Finding:
    severity: str
    category: str
    description: str
    requires_human_decision: bool


@dataclass(frozen=True)
class HistoricalFindingDisposition:
    reference: str
    disposition: str
    note: str


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
    reviewer_overrules_dispute: bool | None = None
    addressed_dispute_references: tuple[str, ...] | None = None
    historical_finding_dispositions: tuple[HistoricalFindingDisposition, ...] | None = None

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


def _extract_codex_error_message(stdout: str) -> str | None:
    """Best-effort extraction of Codex's own structured error message
    (SPEC-003 Requirement 4a). Returns None (never raises) if `stdout`
    is not parseable JSON, is not an object, or has no non-empty
    `error`/`message` string field -- callers fall back to a raw-text
    tail of stdout/stderr in that case, which is the expected, common
    case for Codex (see module docstring).
    """
    try:
        data = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    for field_name in ("error", "message"):
        value = data.get(field_name)
        if isinstance(value, str) and value.strip():
            return value
    return None


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
    # SPEC-003 remediation Finding 3 (MAJOR): `description` is
    # agent-controlled free text that flows into workflow.py's gate
    # reasons and report.py's rendered output -- sanitized once here,
    # at validation time, via the same shared redaction mechanism
    # `build_diagnostic` already uses for `.error`.
    description = sanitize_human_text(description)
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
        # Finding 3 (continued): acceptance-criteria `note` is the same
        # class of agent-controlled free text as `description` above.
        #
        # Focused closure review, Finding 3 (remaining disclosure path):
        # unlike `description`/`note`/`summary`, `id` is not free text --
        # it is also a machine-matched key (reconciliation/validation
        # against the specification's own AC numbering), so it must stay
        # exactly as Codex returned it for that purpose. `display_id`
        # carries the sanitized form for human-facing rendering only
        # (peos/report.py); `id` itself is never redacted or bounded.
        result.append({
            "id": ac_id, "met": met,
            "note": sanitize_human_text(note) if isinstance(note, str) else "",
            "display_id": sanitize_human_text(ac_id),
        })
    return tuple(result)


def _validate_historical_finding_dispositions(raw: object) -> tuple[HistoricalFindingDisposition, ...] | None:
    """Returns `None` (invalid) or a validated tuple; `raw=None` (nullable
    per schema) validates to an empty tuple -- most cycles close no
    historical finding, which is not itself an error (SPEC-004 Outstanding
    Findings Register: "omission never closes a finding").
    """
    if raw is None:
        return ()
    if not isinstance(raw, list):
        return None
    result = []
    for item in raw:
        if not isinstance(item, dict):
            return None
        if set(item.keys()) != {"reference", "disposition", "note"}:
            return None
        reference, disposition, note = item.get("reference"), item.get("disposition"), item.get("note")
        if not isinstance(reference, str) or FindingRef.parse(reference) is None:
            return None
        if disposition not in VALID_DISPOSITIONS:
            return None
        if note is not None and not isinstance(note, str):
            return None
        result.append(HistoricalFindingDisposition(
            reference=reference, disposition=disposition,
            note=sanitize_human_text(note) if isinstance(note, str) else "",
        ))
    return tuple(result)


def _validate_review_payload(
    data: object,
    *,
    active_dispute_references: frozenset = frozenset(),
    required_ac_ids: frozenset = frozenset(),
    runtime_evidenced_ac_status: dict | None = None,
) -> CodexReviewResult:
    """Strictly validate a parsed Codex payload. Fails closed on every
    reproduced adversarial case (SPEC-001 remediation Finding 4): a
    non-dict top level, an incomplete/missing `findings`, an unrecognized
    enum, and an internally contradictory APPROVE (a blocking/major or
    human-decision finding, or an unmet acceptance criterion, alongside
    verdict=APPROVE) all yield `ok=False`.

    SPEC-004 Requirement 8/22/25: `active_dispute_references` (the set of
    currently-active dispute references this cycle, per the Round Packet)
    and `required_ac_ids` (the complete governing AC set) are supplied by
    `peos/workflow.py` from orchestrator-owned state, never from this
    payload itself -- both default to empty, reproducing SPEC-001/
    SPEC-003's exact behavior (no dispute mechanism, no AC-completeness
    check) when a caller does not supply them.

    SPEC-006 Section 14 "Contract: a runtime-evidenced AC's `met=true`
    requires a PASS rollup": `runtime_evidenced_ac_status` is the
    orchestrator-computed, per-round mapping from AC ID to its four-state
    runtime rollup (`peos.runtime_evidence.RuntimeEvidence.
    runtime_evidenced_ac_status`), supplied by `peos/workflow.py`. For
    every AC ID present in this mapping, a `met=true` assertion is a
    contract violation -- the same `FAILED` treatment every other
    "contradictory APPROVE" case in this function already receives --
    unless that AC's rollup is exactly `"PASS"`. This check applies
    regardless of the overall `verdict` (a `CHANGES_REQUIRED` payload
    asserting `met=true` for a FAIL/NOT_EXECUTED-backed AC is just as
    invalid as an `APPROVE` one would be); `met=false` for the same AC
    is never affected. Defaults to `None` (treated as empty), reproducing
    unchanged behavior for every caller/specification that does not
    declare Runtime Verification checks.
    """
    runtime_evidenced_ac_status = runtime_evidenced_ac_status or {}
    if not isinstance(data, dict):
        return _fail(0, build_diagnostic(
            structured_message=f"Codex top-level output was not a JSON object (got {type(data).__name__})",
            category_override="schema",
        ))

    unexpected_keys = set(data.keys()) - _TOP_LEVEL_KEYS
    if unexpected_keys:
        return _fail(
            0,
            build_diagnostic(
                structured_message=(
                    f"Codex top-level output contains unexpected field(s) not in the "
                    f"schema: {sorted(unexpected_keys)!r}"
                ),
                category_override="schema",
            ),
        )

    # SPEC-004 remediation Finding 7: all seven top-level keys are
    # schema-required (REVIEW_SCHEMA["required"]), including the four
    # nullable ones whose VALUE may be null but whose KEY must still be
    # present. A missing key must not be treated the same as an explicit
    # null via `.get()`.
    missing_keys = _TOP_LEVEL_KEYS - set(data.keys())
    if missing_keys:
        return _fail(
            0,
            build_diagnostic(
                structured_message=f"Codex top-level output is missing required field(s): {sorted(missing_keys)!r}",
                category_override="schema",
            ),
        )

    verdict = data.get("verdict")
    if verdict not in ("APPROVE", "CHANGES_REQUIRED"):
        return _fail(0, build_diagnostic(
            structured_message=f"Codex returned an uninterpretable verdict: {verdict!r}",
            category_override="schema",
        ))

    summary = data.get("summary")
    if not isinstance(summary, str):
        return _fail(0, build_diagnostic(
            structured_message="Codex output is missing a string `summary` field",
            category_override="schema",
        ))
    # Finding 3 (continued): `summary` is used verbatim by
    # peos/workflow.py as a gate-reason fallback (`rereview.summary`)
    # when no finding descriptions are present, and is agent-controlled
    # free text like the fields above.
    summary = sanitize_human_text(summary)

    raw_findings = data.get("findings")
    if not isinstance(raw_findings, list):
        return _fail(0, build_diagnostic(
            structured_message=f"Codex `findings` field must be a list, got {type(raw_findings).__name__}",
            category_override="schema",
        ))

    findings = []
    for raw in raw_findings:
        finding = _validate_finding(raw)
        if finding is None:
            return _fail(0, build_diagnostic(
                structured_message=f"Codex returned a malformed finding object: {raw!r}",
                category_override="schema",
            ))
        findings.append(finding)
    findings = tuple(findings)

    acceptance_criteria = _validate_acceptance_criteria(data.get("acceptance_criteria"))
    if acceptance_criteria is None:
        return _fail(0, build_diagnostic(
            structured_message=f"Codex `acceptance_criteria` field is malformed: {data.get('acceptance_criteria')!r}",
            category_override="schema",
        ))

    # SPEC-006 Section 14: a runtime-evidenced AC's met=true requires a
    # PASS rollup -- checked unconditionally (not only within an APPROVE
    # verdict), since asserting a specific criterion is satisfied while
    # the orchestrator's own machine evidence proves otherwise is a
    # contract violation regardless of what the overall verdict says.
    for ac in acceptance_criteria:
        ac_id = ac["id"]
        if ac["met"] is not True or ac_id not in runtime_evidenced_ac_status:
            continue
        rollup = runtime_evidenced_ac_status[ac_id]
        if rollup != "PASS":
            return _fail(0, build_diagnostic(
                structured_message=(
                    f"Codex asserted met=true for {ac['display_id']}, but SPEC-006 Runtime "
                    f"Verification evidence for this round rolls that AC up to {rollup!r} "
                    "(not PASS). Failing closed rather than trusting the acceptance_criteria "
                    "field alone."
                ),
                category_override="schema",
            ))

    # SPEC-004 Requirement 8 (AC-10): `reviewer_overrules_dispute` and
    # `addressed_dispute_references` must be null together (no dispute
    # active) or non-null together (dispute(s) active) -- never one
    # without the other, and never non-null when nothing is active.
    raw_overrules = data.get("reviewer_overrules_dispute")
    if raw_overrules is not None and not isinstance(raw_overrules, bool):
        return _fail(0, build_diagnostic(
            structured_message=f"Codex `reviewer_overrules_dispute` must be boolean or null, got {raw_overrules!r}",
            category_override="schema",
        ))

    raw_addressed = data.get("addressed_dispute_references")
    if raw_addressed is not None:
        if not isinstance(raw_addressed, list) or not all(isinstance(r, str) for r in raw_addressed):
            return _fail(0, build_diagnostic(
                structured_message=f"Codex `addressed_dispute_references` must be a list of strings or null, got {raw_addressed!r}",
                category_override="schema",
            ))
    addressed_dispute_references = tuple(raw_addressed) if raw_addressed is not None else None

    if not active_dispute_references:
        if raw_overrules is not None or addressed_dispute_references is not None:
            return _fail(0, build_diagnostic(
                structured_message=(
                    "Codex set reviewer_overrules_dispute/addressed_dispute_references "
                    "while no dispute is active this cycle; both must be null"
                ),
                category_override="schema",
            ))
    else:
        if raw_overrules is None or addressed_dispute_references is None:
            return _fail(0, build_diagnostic(
                structured_message=(
                    "Codex left reviewer_overrules_dispute/addressed_dispute_references null "
                    "while a dispute is active this cycle; both are required"
                ),
                category_override="schema",
            ))
        missing_refs = active_dispute_references - set(addressed_dispute_references)
        if missing_refs:
            return _fail(0, build_diagnostic(
                structured_message=(
                    "Codex `addressed_dispute_references` omits active dispute reference(s): "
                    f"{sorted(missing_refs)!r}"
                ),
                category_override="schema",
            ))

    historical_finding_dispositions = _validate_historical_finding_dispositions(
        data.get("historical_finding_dispositions")
    )
    if historical_finding_dispositions is None:
        return _fail(0, build_diagnostic(
            structured_message=(
                f"Codex `historical_finding_dispositions` field is malformed: "
                f"{data.get('historical_finding_dispositions')!r}"
            ),
            category_override="schema",
        ))

    if verdict == "APPROVE":
        # SPEC-004 Requirement 8 (AC-21): an earlier draft allowed APPROVE
        # and reviewer_overrules_dispute=true to coexist as merely
        # inconsistent rather than invalid -- a persistent, reviewer-
        # overruled dispute is never a valid approval.
        if raw_overrules is True:
            return _fail(0, build_diagnostic(
                structured_message=(
                    "Codex returned a contradictory APPROVE: verdict=APPROVE but "
                    "reviewer_overrules_dispute=true for an active dispute. Failing closed "
                    "rather than trusting the verdict field alone."
                ),
                category_override="schema",
            ))
        contradicting = [f for f in findings if f.severity in _BLOCKING_SEVERITIES or f.requires_human_decision]
        if contradicting:
            return _fail(
                0,
                build_diagnostic(
                    structured_message=(
                        "Codex returned a contradictory APPROVE: verdict=APPROVE but "
                        f"{len(contradicting)} finding(s) are blocking/major or require a "
                        "human decision. Failing closed rather than trusting the verdict field alone."
                    ),
                    category_override="schema",
                ),
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
                build_diagnostic(
                    structured_message=(
                        "Codex returned a contradictory APPROVE: verdict=APPROVE but no "
                        "acceptance_criteria evidence was provided. APPROVE requires a "
                        "non-empty acceptance-criteria assessment; failing closed rather "
                        "than trusting the verdict field alone."
                    ),
                    category_override="schema",
                ),
            )
        unmet = [ac for ac in acceptance_criteria if not ac["met"]]
        if unmet:
            ids = ", ".join(ac["id"] for ac in unmet)
            return _fail(
                0,
                build_diagnostic(
                    structured_message=(
                        f"Codex returned a contradictory APPROVE: verdict=APPROVE but "
                        f"acceptance criteria not met: {ids}. Failing closed rather than "
                        "trusting the verdict field alone."
                    ),
                    category_override="schema",
                ),
            )
        # SPEC-004 Requirement 5/25: an AC assessment covering fewer than
        # the complete governing AC set the Round Packet supplied is
        # itself a contract violation, not a passing review -- a partial-
        # coverage APPROVE is rejected here, before it can ever reach
        # convergence as an approval.
        if required_ac_ids:
            covered = {ac["id"] for ac in acceptance_criteria}
            uncovered = set(required_ac_ids) - covered
            if uncovered:
                return _fail(
                    0,
                    build_diagnostic(
                        structured_message=(
                            "Codex returned a contradictory APPROVE: verdict=APPROVE but the "
                            f"acceptance-criteria assessment omits required AC(s): "
                            f"{sorted(uncovered)!r}. Failing closed rather than trusting the "
                            "verdict field alone."
                        ),
                        category_override="schema",
                    ),
                )

    return CodexReviewResult(
        returncode=0, verdict=verdict, summary=summary, findings=findings,
        acceptance_criteria=acceptance_criteria, raw_stdout="", raw_stderr="", ok=True,
        reviewer_overrules_dispute=raw_overrules,
        addressed_dispute_references=addressed_dispute_references,
        historical_finding_dispositions=historical_finding_dispositions,
    )


def run_codex_review(
    prompt: str,
    cwd: Path,
    runner: Runner = subprocess.run,
    timeout: int = 3600,
    env: dict | None = None,
    active_dispute_references: frozenset = frozenset(),
    required_ac_ids: frozenset = frozenset(),
    runtime_evidenced_ac_status: dict | None = None,
) -> CodexReviewResult:
    """Invoke Codex for an independent review of `cwd` (the isolated
    workspace, never the authoritative repository directly) and capture
    a strictly validated structured result.

    Fails closed: any subprocess error, non-zero exit, output that
    cannot be read/parsed, or output that fails `_validate_review_payload`
    yields `ok=False, verdict=None` rather than guessing APPROVE
    (SPEC-001 Section 11, AC-011).

    `active_dispute_references`/`required_ac_ids` (SPEC-004) and
    `runtime_evidenced_ac_status` (SPEC-006 Section 14) are
    orchestrator-owned state forwarded verbatim to
    `_validate_review_payload`; see that function's docstring.
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
            return _fail(-1, build_diagnostic(
                structured_message=f"Codex subprocess failed to run: {exc}",
                category_override="cli_invocation",
            ))

        if proc.returncode != 0:
            structured_message = _extract_codex_error_message(proc.stdout)
            diagnostic = build_diagnostic(
                stdout=proc.stdout, stderr=proc.stderr,
                structured_message=structured_message, exit_code=proc.returncode,
            )
            return _fail(proc.returncode, diagnostic, stdout=proc.stdout, stderr=proc.stderr)

        try:
            last_message = last_message_path.read_text(encoding="utf-8")
        except OSError as exc:
            return _fail(
                proc.returncode,
                build_diagnostic(
                    structured_message=f"could not read Codex last-message file: {exc}",
                    category_override="schema",
                ),
                stdout=proc.stdout, stderr=proc.stderr,
            )

        try:
            data = json.loads(last_message)
        except json.JSONDecodeError as exc:
            return _fail(
                proc.returncode,
                build_diagnostic(
                    structured_message=f"could not parse Codex JSON output: {exc}",
                    category_override="schema",
                ),
                stdout=proc.stdout, stderr=proc.stderr,
            )

        result = _validate_review_payload(
            data, active_dispute_references=active_dispute_references, required_ac_ids=required_ac_ids,
            runtime_evidenced_ac_status=runtime_evidenced_ac_status,
        )
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
            reviewer_overrules_dispute=result.reviewer_overrules_dispute,
            addressed_dispute_references=result.addressed_dispute_references,
            historical_finding_dispositions=result.historical_finding_dispositions,
        )
