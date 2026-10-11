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


def _completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=["codex"], returncode=returncode, stdout=stdout, stderr=stderr)


def _runner_writing_last_message_exact(payload):
    """Write `payload` verbatim, with no modification -- used where a
    test needs exact control over which top-level keys are present (e.g.
    the SPEC-004 remediation Finding 7 tests below, which specifically
    test omitting one of the three nullable keys entirely).
    """
    def runner(command, **kwargs):
        last_message_path = Path(command[command.index("--output-last-message") + 1])
        last_message_path.write_text(json.dumps(payload), encoding="utf-8")
        return _completed(0)
    return runner


# SPEC-004 added three nullable-by-default top-level keys to REVIEW_SCHEMA
# (`reviewer_overrules_dispute`, `addressed_dispute_references`,
# `historical_finding_dispositions`). Finding 7's fix makes all three
# required KEYS (value may still be null) -- every payload literal in
# this file predates that change and only sets the four original keys,
# so `_runner_writing_last_message` fills in explicit nulls for whichever
# of the three a payload omits, the same way a real, schema-conformant
# `codex exec --output-schema` response always would. This is purely test
# infrastructure: it keeps ~30 existing payload literals representative
# of a schema-conformant response without hand-editing each one, while
# the omission itself is tested directly and explicitly, against the
# *exact* writer, in test_payload_missing_any_of_the_three_spec004_keys_
# entirely_is_rejected below.
_SPEC004_NULLABLE_DEFAULTS = {
    "reviewer_overrules_dispute": None,
    "addressed_dispute_references": None,
    "historical_finding_dispositions": None,
}


def _runner_writing_last_message(payload):
    merged = dict(_SPEC004_NULLABLE_DEFAULTS)
    merged.update(payload)
    return _runner_writing_last_message_exact(merged)


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


def test_run_codex_review_nonzero_exit_prefers_structured_error_message():
    """SPEC-003 AC-8a: when `stdout` happens to be valid JSON with an
    `error`/`message` field, that structured message is used instead of
    a raw-text tail.
    """
    payload = json.dumps({"error": "Not logged in · Please run /login"})

    def runner(command, **kwargs):
        return _completed(1, stdout=payload)

    result = run_codex_review("prompt", Path("."), runner=runner)
    assert not result.ok
    assert "[authentication]" in result.error
    assert "Not logged in" in result.error


def test_run_codex_review_nonzero_exit_falls_back_to_raw_tail_when_stdout_is_not_json():
    """SPEC-003 AC-8b: Codex's non-interactive stdout is not guaranteed
    to be JSON on a CLI-level failure -- the common case -- and the
    bounded raw-text fallback must still classify correctly.
    """
    def runner(command, **kwargs):
        return _completed(1, stderr="Not logged in · Please run /login")

    result = run_codex_review("prompt", Path("."), runner=runner)
    assert not result.ok
    assert "[authentication]" in result.error
    assert "Not logged in" in result.error


def test_run_codex_review_nonzero_exit_redacts_a_secret_shaped_string():
    """SPEC-003 AC-9."""
    secret = "sk-liveAbCdEfGhIjKlMnOpQrSt"

    def runner(command, **kwargs):
        return _completed(1, stderr=f"request failed, key={secret} was rejected")

    result = run_codex_review("prompt", Path("."), runner=runner)
    assert not result.ok
    assert secret not in result.error
    assert "[REDACTED]" in result.error


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


def test_run_codex_review_finding_description_is_redacted_of_a_secret_shaped_string():
    """Focused Codex review remediation, Finding 3 (MAJOR): a finding's
    `description` is agent-controlled free text that flows into
    workflow.py's gate reasons and report.py's rendered output -- it
    must pass through the same shared redaction mechanism `.error`
    already used.
    """
    secret = "sk-liveAbCdEfGhIjKlMnOpQrSt"
    runner = _runner_writing_last_message({
        "verdict": "CHANGES_REQUIRED",
        "summary": "issues found",
        "findings": [{
            "severity": "major", "category": "implementation_defect",
            "description": f"hardcoded credential key={secret} found in source",
            "requires_human_decision": False,
        }],
        "acceptance_criteria": None,
    })
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert result.ok
    assert secret not in result.findings[0].description
    assert "[REDACTED]" in result.findings[0].description


def test_run_codex_review_acceptance_criteria_note_is_redacted_of_a_secret_shaped_string():
    """Finding 3 (continued): same requirement for an acceptance-
    criteria `note`."""
    secret = "sk-liveAbCdEfGhIjKlMnOpQrSt"
    runner = _runner_writing_last_message({
        "verdict": "CHANGES_REQUIRED",
        "summary": "issues found",
        "findings": [],
        "acceptance_criteria": [{"id": "AC-001", "met": False, "note": f"blocked by key={secret}"}],
    })
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert result.ok
    assert secret not in result.acceptance_criteria[0]["note"]
    assert "[REDACTED]" in result.acceptance_criteria[0]["note"]


def test_run_codex_review_acceptance_criteria_id_display_form_is_redacted_but_internal_id_is_unchanged():
    """Focused closure review, Finding 3 (remaining disclosure path):
    unlike `note`/`description`/`summary`, an acceptance-criterion `id`
    is also a machine-matched key (reconciliation/validation against the
    specification's own AC numbering), so it must NOT be mutated by
    redaction -- `result.acceptance_criteria[i]["id"]` must come back
    byte-for-byte identical to what Codex returned, including a
    credential-shaped value, so matching semantics are unaffected. The
    sanitized form is carried separately in `display_id`, which is what
    peos/report.py renders (see
    test_report_never_surfaces_a_secret_from_an_acceptance_criterion_id_
    end_to_end in tests/test_peos_report.py for the human-facing-output
    proof).
    """
    sk_secret = "sk-liveAbCdEfGhIjKlMnOpQrSt"
    generic_secret = "A" * 32  # the other supported credential-shaped pattern (GENERIC_TOKEN_MIN_LEN)
    runner = _runner_writing_last_message({
        "verdict": "APPROVE",
        "summary": "ok",
        "findings": [],
        "acceptance_criteria": [
            {"id": f"AC-001-{sk_secret}", "met": True, "note": "covered"},
            # Space (not in the generic pattern's `[A-Za-z0-9_\-\.]` class)
            # separates the AC label from the token run so only the token
            # itself -- not the whole id -- is swallowed by the match.
            {"id": f"AC-002 {generic_secret}", "met": True, "note": "covered"},
        ],
    })
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert result.ok
    assert result.approved

    ac_sk, ac_generic = result.acceptance_criteria

    # Internal `id`: unchanged, verbatim, for machine semantics.
    assert ac_sk["id"] == f"AC-001-{sk_secret}"
    assert ac_generic["id"] == f"AC-002 {generic_secret}"

    # Human-facing `display_id`: sanitized, secret never appears.
    assert sk_secret not in ac_sk["display_id"]
    assert "[REDACTED]" in ac_sk["display_id"]
    assert ac_sk["display_id"].startswith("AC-001-")
    assert generic_secret not in ac_generic["display_id"]
    assert "[REDACTED]" in ac_generic["display_id"]
    assert ac_generic["display_id"].startswith("AC-002 ")


def test_run_codex_review_summary_is_redacted_of_a_secret_shaped_string():
    """Finding 3 (continued): same requirement for the top-level
    `summary`, which peos/workflow.py also uses verbatim as a
    gate-reason fallback when no finding descriptions are present."""
    secret = "sk-liveAbCdEfGhIjKlMnOpQrSt"
    runner = _runner_writing_last_message({
        "verdict": "CHANGES_REQUIRED",
        "summary": f"found hardcoded key={secret} during review",
        "findings": [],
        "acceptance_criteria": None,
    })
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert result.ok
    assert secret not in result.summary
    assert "[REDACTED]" in result.summary


# --- SPEC-004 Requirement 8/16/22/25: dispute + register + AC-coverage --

def _approve_payload(**overrides):
    payload = {
        "verdict": "APPROVE", "summary": "ok", "findings": [],
        "acceptance_criteria": [{"id": "AC-1", "met": True, "note": "covered"}],
    }
    payload.update(overrides)
    return payload


def test_reviewer_overrules_dispute_true_with_active_dispute_is_accepted_as_changes_required():
    runner = _runner_writing_last_message({
        "verdict": "CHANGES_REQUIRED", "summary": "still an issue", "findings": [],
        "acceptance_criteria": None,
        "reviewer_overrules_dispute": True, "addressed_dispute_references": ["0.1"],
        "historical_finding_dispositions": None,
    })
    result = run_codex_review("prompt", Path("."), runner=runner, active_dispute_references=frozenset({"0.1"}))
    assert result.ok
    assert result.reviewer_overrules_dispute is True
    assert result.addressed_dispute_references == ("0.1",)


def test_ac21_approve_with_reviewer_overrules_dispute_true_is_rejected():
    runner = _runner_writing_last_message({
        "verdict": "APPROVE", "summary": "ok", "findings": [], "acceptance_criteria": None,
        "reviewer_overrules_dispute": True, "addressed_dispute_references": ["0.1"],
        "historical_finding_dispositions": None,
    })
    result = run_codex_review("prompt", Path("."), runner=runner, active_dispute_references=frozenset({"0.1"}))
    assert not result.ok
    assert result.verdict is None


def test_ac10_dispute_fields_set_while_no_dispute_active_is_rejected():
    runner = _runner_writing_last_message({
        "verdict": "CHANGES_REQUIRED", "summary": "x", "findings": [], "acceptance_criteria": None,
        "reviewer_overrules_dispute": False, "addressed_dispute_references": ["0.1"],
        "historical_finding_dispositions": None,
    })
    result = run_codex_review("prompt", Path("."), runner=runner)  # no active_dispute_references
    assert not result.ok


def test_ac10_dispute_fields_null_while_dispute_active_is_rejected():
    runner = _runner_writing_last_message({
        "verdict": "CHANGES_REQUIRED", "summary": "x", "findings": [], "acceptance_criteria": None,
        "reviewer_overrules_dispute": None, "addressed_dispute_references": None,
        "historical_finding_dispositions": None,
    })
    result = run_codex_review("prompt", Path("."), runner=runner, active_dispute_references=frozenset({"0.1"}))
    assert not result.ok


def test_ac24_addressed_dispute_references_omitting_an_active_reference_is_rejected():
    runner = _runner_writing_last_message({
        "verdict": "CHANGES_REQUIRED", "summary": "x", "findings": [], "acceptance_criteria": None,
        "reviewer_overrules_dispute": False, "addressed_dispute_references": ["0.1"],
        "historical_finding_dispositions": None,
    })
    result = run_codex_review(
        "prompt", Path("."), runner=runner, active_dispute_references=frozenset({"0.1", "0.2"}),
    )
    assert not result.ok
    assert "omits" in result.error


def test_addressed_dispute_references_covering_every_active_reference_is_accepted():
    runner = _runner_writing_last_message({
        "verdict": "CHANGES_REQUIRED", "summary": "x", "findings": [], "acceptance_criteria": None,
        "reviewer_overrules_dispute": False, "addressed_dispute_references": ["0.1", "0.2"],
        "historical_finding_dispositions": None,
    })
    result = run_codex_review(
        "prompt", Path("."), runner=runner, active_dispute_references=frozenset({"0.1", "0.2"}),
    )
    assert result.ok


def test_historical_finding_dispositions_well_formed_is_accepted():
    runner = _runner_writing_last_message({
        "verdict": "CHANGES_REQUIRED", "summary": "x", "findings": [], "acceptance_criteria": None,
        "reviewer_overrules_dispute": None, "addressed_dispute_references": None,
        "historical_finding_dispositions": [
            {"reference": "0.1", "disposition": "RESOLVED", "note": "fixed"},
        ],
    })
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert result.ok
    assert len(result.historical_finding_dispositions) == 1
    assert result.historical_finding_dispositions[0].disposition == "RESOLVED"


def test_historical_finding_dispositions_with_malformed_reference_is_rejected():
    runner = _runner_writing_last_message({
        "verdict": "CHANGES_REQUIRED", "summary": "x", "findings": [], "acceptance_criteria": None,
        "reviewer_overrules_dispute": None, "addressed_dispute_references": None,
        "historical_finding_dispositions": [
            {"reference": "not-a-ref", "disposition": "RESOLVED", "note": "fixed"},
        ],
    })
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert not result.ok


def test_historical_finding_dispositions_with_invalid_disposition_value_is_rejected():
    runner = _runner_writing_last_message({
        "verdict": "CHANGES_REQUIRED", "summary": "x", "findings": [], "acceptance_criteria": None,
        "reviewer_overrules_dispute": None, "addressed_dispute_references": None,
        "historical_finding_dispositions": [
            {"reference": "0.1", "disposition": "MAYBE_FIXED", "note": None},
        ],
    })
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert not result.ok


def test_ac20_approve_payload_shape_is_unaffected_by_register_state_itself():
    """`_validate_review_payload` never sees the Outstanding Findings
    Register directly (that check lives at the orchestrator level in
    peos/workflow.py's `_evaluate_cycle` -- see test_peos_workflow.py);
    this schema-level payload alone, with no dispute/AC-set context, must
    still validate normally.
    """
    runner = _runner_writing_last_message(_approve_payload())
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert result.ok
    assert result.approved


def test_ac25_approve_with_incomplete_ac_coverage_is_rejected():
    runner = _runner_writing_last_message(_approve_payload(
        acceptance_criteria=[{"id": "AC-1", "met": True, "note": "covered"}],
    ))
    result = run_codex_review(
        "prompt", Path("."), runner=runner, required_ac_ids=frozenset({"AC-1", "AC-2"}),
    )
    assert not result.ok
    assert "AC-2" in result.error


def test_ac25_approve_with_complete_ac_coverage_is_accepted():
    runner = _runner_writing_last_message(_approve_payload(
        acceptance_criteria=[
            {"id": "AC-1", "met": True, "note": "covered"},
            {"id": "AC-2", "met": True, "note": "covered"},
        ],
    ))
    result = run_codex_review(
        "prompt", Path("."), runner=runner, required_ac_ids=frozenset({"AC-1", "AC-2"}),
    )
    assert result.ok
    assert result.approved


def test_payload_missing_any_of_the_three_spec004_keys_entirely_is_rejected():
    """SPEC-004 remediation Finding 7 (MAJOR): REVIEW_SCHEMA requires all
    seven top-level keys, including `reviewer_overrules_dispute`/
    `addressed_dispute_references`/`historical_finding_dispositions`
    (value may be null, but the KEY must be present). Local validation
    previously required only the four pre-SPEC-004 keys, so a payload
    omitting one of these three entirely -- not merely setting it to
    null -- was silently accepted. Each omission, individually, must now
    be rejected the same way omitting `verdict`/`summary`/`findings`/
    `acceptance_criteria` already was and remains.
    """
    base = {
        "verdict": "APPROVE", "summary": "ok", "findings": [],
        "acceptance_criteria": [{"id": "AC-001", "met": True, "note": "covered"}],
        "reviewer_overrules_dispute": None,
        "addressed_dispute_references": None,
        "historical_finding_dispositions": None,
    }
    for omitted_key in (
        "reviewer_overrules_dispute", "addressed_dispute_references", "historical_finding_dispositions",
    ):
        payload = dict(base)
        del payload[omitted_key]
        runner = _runner_writing_last_message_exact(payload)
        result = run_codex_review("prompt", Path("."), runner=runner)
        assert not result.ok, f"omitting {omitted_key!r} entirely must be rejected"
        assert result.verdict is None
        assert "missing required field" in result.error.lower()
        assert omitted_key in result.error


def test_payload_with_all_seven_keys_present_and_the_three_new_ones_explicit_null_is_accepted():
    """The positive counterpart: a payload that supplies all seven keys,
    with the three SPEC-004 keys explicitly null (no dispute active,
    nothing dispositioned this cycle), is well-formed and must validate
    normally -- "required KEY, nullable VALUE" is satisfied exactly as
    REVIEW_SCHEMA intends.
    """
    payload = {
        "verdict": "APPROVE", "summary": "ok", "findings": [],
        "acceptance_criteria": [{"id": "AC-001", "met": True, "note": "covered"}],
        "reviewer_overrules_dispute": None,
        "addressed_dispute_references": None,
        "historical_finding_dispositions": None,
    }
    runner = _runner_writing_last_message_exact(payload)
    result = run_codex_review("prompt", Path("."), runner=runner)
    assert result.ok
    assert result.reviewer_overrules_dispute is None
    assert result.addressed_dispute_references is None
    assert result.historical_finding_dispositions == ()


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
