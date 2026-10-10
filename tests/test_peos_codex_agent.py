"""Tests for the Codex subprocess wrapper (peos/codex_agent.py).

Adversarial cases directly reproduce the failures SPEC-001 remediation
Finding 4 lists as previously accepted bugs: `{}`, a top-level `[]`,
`findings: null`, an incomplete APPROVE, an APPROVE that contradicts a
human-decision/major finding, and an APPROVE alongside an unmet
acceptance criterion. Every one of these must now yield `ok=False,
verdict=None` -- never a crash, never a guessed APPROVE.
"""

import json
import subprocess
from pathlib import Path

from peos.codex_agent import REVIEW_SCHEMA, build_codex_command, run_codex_review


def _completed(returncode=0):
    return subprocess.CompletedProcess(args=["codex"], returncode=returncode, stdout="", stderr="")


def _runner_writing_last_message(payload):
    def runner(command, **kwargs):
        last_message_path = Path(command[command.index("--output-last-message") + 1])
        last_message_path.write_text(json.dumps(payload), encoding="utf-8")
        return _completed(0)
    return runner


def _runner_writing_raw(raw_text: str):
    def runner(command, **kwargs):
        last_message_path = Path(command[command.index("--output-last-message") + 1])
        last_message_path.write_text(raw_text, encoding="utf-8")
        return _completed(0)
    return runner


def test_build_codex_command_is_read_only_and_structured():
    cmd = build_codex_command("review this", Path("/tmp/schema.json"), Path("/tmp/last.json"), Path("/tmp/workspace"))
    assert cmd[:2] == ["codex", "exec"]
    assert "--sandbox" in cmd and "read-only" in cmd
    assert "-C" in cmd and str(Path("/tmp/workspace")) in cmd
    assert "--output-schema" in cmd
    assert "--output-last-message" in cmd
    assert cmd[-1] == "review this"


def test_build_codex_command_reduces_inherited_external_capabilities():
    # Finding 3 (second pass): skip configured MCP servers (loaded from
    # $CODEX_HOME/config.toml) and any user/project execpolicy .rules file.
    cmd = build_codex_command("review this", Path("/tmp/schema.json"), Path("/tmp/last.json"), Path("/tmp/workspace"))
    assert "--ignore-user-config" in cmd
    assert "--ignore-rules" in cmd


def test_review_schema_requires_every_property_and_uses_nullable_optionals():
    # Finding 5: strict Structured Outputs requires every property to be
    # listed in `required`; optional semantics use nullable types instead
    # of omission. This shape was verified against the installed Codex
    # CLI (see tests/test_peos_real_cli_contract.py).
    assert set(REVIEW_SCHEMA["required"]) == set(REVIEW_SCHEMA["properties"].keys())
    assert REVIEW_SCHEMA["additionalProperties"] is False
    ac_schema = REVIEW_SCHEMA["properties"]["acceptance_criteria"]
    assert ac_schema["type"] == ["array", "null"]
    finding_item_schema = REVIEW_SCHEMA["properties"]["findings"]["items"]
    assert set(finding_item_schema["required"]) == set(finding_item_schema["properties"].keys())
    assert finding_item_schema["additionalProperties"] is False


def test_run_codex_review_approve():
    runner = _runner_writing_last_message({
        "verdict": "APPROVE", "summary": "ok", "findings": [],
        "acceptance_criteria": [{"id": "AC-001", "met": True, "note": "covered"}],
    })
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert result.ok
    assert result.approved
    assert result.findings == ()


def test_run_codex_review_changes_required_with_findings():
    runner = _runner_writing_last_message({
        "verdict": "CHANGES_REQUIRED",
        "summary": "issues found",
        "findings": [
            {
                "severity": "major",
                "category": "missing_test",
                "description": "no test for new branch",
                "requires_human_decision": False,
            },
            {
                "severity": "blocking",
                "category": "architecture_concern",
                "description": "changes control loop topology",
                "requires_human_decision": True,
            },
        ],
        "acceptance_criteria": None,
    })
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert result.ok
    assert not result.approved
    assert len(result.findings) == 2
    assert len(result.human_decision_findings) == 1
    assert result.human_decision_findings[0].category == "architecture_concern"


def test_run_codex_review_invalid_verdict_fails_closed():
    runner = _runner_writing_last_message({"verdict": "MAYBE", "summary": "", "findings": [], "acceptance_criteria": None})
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert not result.ok
    assert result.verdict is None


def test_run_codex_review_unparseable_last_message_fails_closed():
    runner = _runner_writing_raw("not json")
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert not result.ok
    assert result.verdict is None


def test_run_codex_review_nonzero_exit_fails_closed():
    def runner(command, **kwargs):
        return _completed(1)

    result = run_codex_review("prompt", Path("."), runner=runner)
    assert not result.ok


def test_run_codex_review_subprocess_error_fails_closed():
    def runner(command, **kwargs):
        raise FileNotFoundError("codex not found")

    result = run_codex_review("prompt", Path("."), runner=runner)
    assert not result.ok
    assert "codex" in result.error.lower()


# --- SPEC-001 remediation Finding 4: adversarial reproductions ---------

def test_empty_object_is_rejected_not_accepted():
    runner = _runner_writing_last_message({})
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert not result.ok
    assert result.verdict is None


def test_top_level_array_does_not_crash_and_fails_closed():
    runner = _runner_writing_raw(json.dumps(["unexpected", "array"]))
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert not result.ok
    assert result.verdict is None
    assert "JSON object" in result.error


def test_findings_null_does_not_crash_and_fails_closed():
    runner = _runner_writing_last_message({
        "verdict": "APPROVE", "summary": "ok", "findings": None, "acceptance_criteria": None,
    })
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert not result.ok
    assert result.verdict is None


def test_incomplete_approve_missing_findings_key_is_rejected():
    runner = _runner_writing_last_message({"verdict": "APPROVE", "summary": "ok"})
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert not result.ok
    assert result.verdict is None


def test_approve_with_human_decision_major_finding_is_rejected():
    runner = _runner_writing_last_message({
        "verdict": "APPROVE",
        "summary": "looks fine",
        "findings": [
            {
                "severity": "major",
                "category": "architecture_concern",
                "description": "actually changes the control topology",
                "requires_human_decision": True,
            },
        ],
        "acceptance_criteria": None,
    })
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert not result.ok
    assert result.verdict is None
    assert "contradictory APPROVE" in result.error


def test_approve_with_blocking_finding_is_rejected_even_without_human_decision_flag():
    runner = _runner_writing_last_message({
        "verdict": "APPROVE",
        "summary": "looks fine",
        "findings": [
            {
                "severity": "blocking",
                "category": "implementation_defect",
                "description": "crashes on empty input",
                "requires_human_decision": False,
            },
        ],
        "acceptance_criteria": None,
    })
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert not result.ok
    assert "contradictory APPROVE" in result.error


def test_approve_with_unmet_acceptance_criterion_is_rejected():
    runner = _runner_writing_last_message({
        "verdict": "APPROVE",
        "summary": "looks fine",
        "findings": [],
        "acceptance_criteria": [{"id": "AC-001", "met": False, "note": "not actually implemented"}],
    })
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert not result.ok
    assert "AC-001" in result.error


def test_approve_without_acceptance_criteria_is_rejected():
    """Finding 2 (second pass), directly reproduced by Codex: "Codex
    APPROVE accepted without required acceptance_criteria". A
    specification with numbered ACs cannot be APPROVEd with no AC
    evidence at all -- acceptance_criteria=null is only valid for
    CHANGES_REQUIRED (a spec with zero ACs)."""
    runner = _runner_writing_last_message({
        "verdict": "APPROVE", "summary": "looks fine", "findings": [], "acceptance_criteria": None,
    })
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert not result.ok
    assert "acceptance_criteria" in result.error


def test_approve_with_empty_acceptance_criteria_list_is_rejected():
    runner = _runner_writing_last_message({
        "verdict": "APPROVE", "summary": "looks fine", "findings": [], "acceptance_criteria": [],
    })
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert not result.ok
    assert "acceptance_criteria" in result.error


def test_changes_required_without_acceptance_criteria_is_still_accepted():
    # Null acceptance_criteria remains valid for CHANGES_REQUIRED.
    runner = _runner_writing_last_message({
        "verdict": "CHANGES_REQUIRED",
        "summary": "needs work",
        "findings": [{"severity": "minor", "category": "non_blocking_improvement", "description": "x", "requires_human_decision": False}],
        "acceptance_criteria": None,
    })
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert result.ok
    assert result.verdict == "CHANGES_REQUIRED"


def test_acceptance_criteria_note_with_invalid_type_is_rejected_not_coerced():
    """Latest Codex review, Finding 2, directly reproduced: an
    acceptance-criteria `note` of a schema-invalid type (the schema
    requires string or null; this payload supplies an int) was previously
    silently coerced to an empty string by `_validate_acceptance_criteria`
    rather than rejected -- a malformed payload was accepted as a
    well-formed result. Must now fail closed.
    """
    runner = _runner_writing_last_message({
        "verdict": "CHANGES_REQUIRED",
        "summary": "needs work",
        "findings": [{"severity": "minor", "category": "non_blocking_improvement", "description": "x", "requires_human_decision": False}],
        "acceptance_criteria": [{"id": "AC-001", "met": False, "note": 42}],
    })
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert not result.ok
    assert result.verdict is None


def test_finding_with_unexpected_extra_field_is_rejected():
    """Latest Codex review, Finding 2: local validation must enforce
    `additionalProperties: False` from REVIEW_SCHEMA, not merely the
    fields it happens to read -- an extra/unrecognized key on a finding
    object must be rejected, not silently dropped.
    """
    runner = _runner_writing_last_message({
        "verdict": "CHANGES_REQUIRED",
        "summary": "needs work",
        "findings": [{
            "severity": "minor", "category": "non_blocking_improvement",
            "description": "x", "requires_human_decision": False,
            "unexpected_field": "should not be here",
        }],
        "acceptance_criteria": None,
    })
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert not result.ok
    assert result.verdict is None


def test_acceptance_criterion_with_unexpected_extra_field_is_rejected():
    runner = _runner_writing_last_message({
        "verdict": "CHANGES_REQUIRED",
        "summary": "needs work",
        "findings": [],
        "acceptance_criteria": [{"id": "AC-001", "met": True, "note": None, "extra": "x"}],
    })
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert not result.ok
    assert result.verdict is None


def test_top_level_payload_with_unexpected_extra_field_is_rejected():
    runner = _runner_writing_last_message({
        "verdict": "CHANGES_REQUIRED", "summary": "needs work", "findings": [],
        "acceptance_criteria": None, "unexpected_top_level_field": "x",
    })
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert not result.ok
    assert result.verdict is None
    assert "unexpected" in result.error.lower()


def test_malformed_finding_missing_required_field_is_rejected():
    runner = _runner_writing_last_message({
        "verdict": "CHANGES_REQUIRED",
        "summary": "x",
        "findings": [{"severity": "major", "category": "missing_test", "description": "no description of human decision field"}],
        "acceptance_criteria": None,
    })
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert not result.ok


def test_finding_with_unrecognized_severity_enum_is_rejected():
    runner = _runner_writing_last_message({
        "verdict": "CHANGES_REQUIRED",
        "summary": "x",
        "findings": [{"severity": "catastrophic", "category": "missing_test", "description": "d", "requires_human_decision": False}],
        "acceptance_criteria": None,
    })
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert not result.ok


def test_acceptance_criteria_not_a_list_is_rejected():
    runner = _runner_writing_last_message({
        "verdict": "CHANGES_REQUIRED", "summary": "x", "findings": [], "acceptance_criteria": "yes",
    })
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert not result.ok


def test_acceptance_criterion_missing_note_key_is_rejected_not_treated_as_null():
    """Final acceptance review, directly reproduced:
    {"id":"AC-001","met":true} (no "note" key at all) was previously
    accepted as a well-formed APPROVE, because `.get("note")` cannot
    distinguish an absent key from an explicit `"note": null`, which the
    nullable-type check treats as valid. `note` is a schema-required KEY
    even though its VALUE may be null, so this must fail closed.
    """
    runner = _runner_writing_last_message({
        "verdict": "APPROVE",
        "summary": "ok",
        "findings": [],
        "acceptance_criteria": [{"id": "AC-001", "met": True}],
    })
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert not result.ok
    assert result.verdict is None
    assert "acceptance_criteria" in result.error


def test_top_level_payload_missing_acceptance_criteria_key_is_rejected():
    """The top-level `acceptance_criteria` key is schema-required (its
    VALUE may be null), so omitting the key entirely must not be treated
    the same as `"acceptance_criteria": null`.
    """
    runner = _runner_writing_last_message({
        "verdict": "CHANGES_REQUIRED", "summary": "x", "findings": [],
    })
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert not result.ok
    assert result.verdict is None
    assert "missing required field" in result.error.lower()


def test_finding_missing_requires_human_decision_key_is_rejected():
    """A finding missing the `requires_human_decision` key entirely (not
    set to a boolean) must fail closed, same class of defect as the AC
    `note` gap above.
    """
    runner = _runner_writing_last_message({
        "verdict": "CHANGES_REQUIRED",
        "summary": "x",
        "findings": [{"severity": "minor", "category": "non_blocking_improvement", "description": "x"}],
        "acceptance_criteria": None,
    })
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert not result.ok
    assert result.verdict is None
