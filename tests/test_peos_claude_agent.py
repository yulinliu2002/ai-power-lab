"""Tests for the Claude Code subprocess wrapper (peos/claude_agent.py).

Adversarial-parsing cases here correspond to SPEC-001 remediation
Finding 4 (applied to Claude's structured-result contract, Finding 3):
a missing structured_output, a non-dict structured_output, an invalid
status enum, and a HUMAN_GATE status without a gate_reason must all fail
closed (ok=False, status=None-or-"HUMAN_GATE" but never ok=True).
"""

import json
import subprocess
from pathlib import Path

from peos.claude_agent import ALLOWED_TOOLS, CLAUDE_RESULT_SCHEMA, build_claude_command, run_claude


def _completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=["claude"], returncode=returncode, stdout=stdout, stderr=stderr)


def _wrap(structured: dict, is_error: bool = False) -> str:
    return json.dumps({"is_error": is_error, "result": structured.get("summary", ""), "structured_output": structured})


def test_build_claude_command_is_restricted_with_no_bash():
    cmd = build_claude_command("do the thing")
    assert cmd[:2] == ["claude", "-p"]
    assert "--output-format" in cmd and "json" in cmd
    assert "--restricted" in cmd
    assert "--tools" in cmd
    assert cmd[cmd.index("--tools") + 1] == ALLOWED_TOOLS
    assert "Bash" not in ALLOWED_TOOLS.split()
    assert "--permission-mode" in cmd and "acceptEdits" in cmd
    assert "--permission-prompts" in cmd and "none" in cmd
    assert "--strict-mcp-config" in cmd
    assert "--mcp-config" not in cmd
    assert "--json-schema" in cmd
    schema_arg = cmd[cmd.index("--json-schema") + 1]
    assert json.loads(schema_arg) == CLAUDE_RESULT_SCHEMA
    assert cmd[-1] == "do the thing"
    # Finding 1: bypassPermissions must never be requested again.
    assert "bypassPermissions" not in cmd


def test_run_claude_passes_devnull_stdin_and_env():
    captured = {}

    def runner(command, **kwargs):
        captured.update(kwargs)
        return _completed(0, stdout=_wrap({"status": "COMPLETED", "gate_category": None, "gate_reason": None, "summary": "done"}))

    env = {"HOME": "/isolated"}
    result = run_claude("task", Path("."), runner=runner, env=env)
    assert result.ok
    assert captured["stdin"] is subprocess.DEVNULL
    assert captured["env"] is env


def test_run_claude_completed_status():
    payload = _wrap({"status": "COMPLETED", "gate_category": None, "gate_reason": None, "summary": "did the thing"})

    def runner(command, **kwargs):
        return _completed(0, stdout=payload)

    result = run_claude("task", Path("."), runner=runner)
    assert result.ok
    assert result.status == "COMPLETED"
    assert result.summary == "did the thing"
    assert result.gate_category is None
    assert not result.human_gate


def test_run_claude_human_gate_status():
    payload = _wrap({
        "status": "HUMAN_GATE", "gate_category": "physics",
        "gate_reason": "would change the DC-bus energy equation", "summary": "stopped",
    })

    def runner(command, **kwargs):
        return _completed(0, stdout=payload)

    result = run_claude("task", Path("."), runner=runner)
    assert not result.ok
    assert result.human_gate
    assert result.status == "HUMAN_GATE"
    assert result.gate_category == "physics"
    assert "DC-bus" in result.gate_reason


def test_run_claude_human_gate_without_reason_fails_closed():
    payload = _wrap({"status": "HUMAN_GATE", "gate_category": "architecture", "gate_reason": None, "summary": "stopped"})

    def runner(command, **kwargs):
        return _completed(0, stdout=payload)

    result = run_claude("task", Path("."), runner=runner)
    assert not result.ok
    assert result.status is None  # uninterpretable, not a usable HUMAN_GATE
    assert "gate_reason" in result.error


def test_run_claude_human_gate_without_category_fails_closed():
    """Finding 2 (second pass), directly reproduced: "Claude COMPLETED
    accepted with missing required gate fields" -- the HUMAN_GATE
    counterpart. A missing/invalid gate_category was previously silently
    coerced to None instead of being rejected.
    """
    payload = _wrap({"status": "HUMAN_GATE", "gate_category": None, "gate_reason": "something needs a human", "summary": "stopped"})

    def runner(command, **kwargs):
        return _completed(0, stdout=payload)

    result = run_claude("task", Path("."), runner=runner)
    assert not result.ok
    assert result.status is None
    assert "gate_category" in result.error


def test_run_claude_human_gate_with_invalid_category_fails_closed():
    payload = _wrap({"status": "HUMAN_GATE", "gate_category": "not_a_real_category", "gate_reason": "x", "summary": "stopped"})

    def runner(command, **kwargs):
        return _completed(0, stdout=payload)

    result = run_claude("task", Path("."), runner=runner)
    assert not result.ok
    assert result.status is None


def test_run_claude_completed_with_populated_gate_fields_is_rejected_as_inconsistent():
    """Finding 2 (second pass), directly reproduced: "Claude COMPLETED
    accepted alongside gate_category='physics' and a gate reason" -- a
    self-contradictory result must be rejected, not accepted at face
    value.
    """
    payload = _wrap({
        "status": "COMPLETED", "gate_category": "physics",
        "gate_reason": "would change the DC-bus energy equation", "summary": "did the thing",
    })

    def runner(command, **kwargs):
        return _completed(0, stdout=payload)

    result = run_claude("task", Path("."), runner=runner)
    assert not result.ok
    assert result.status is None
    assert "inconsistent" in result.error


def test_run_claude_failed_with_populated_gate_fields_is_rejected_as_inconsistent():
    payload = _wrap({
        "status": "FAILED", "gate_category": "architecture",
        "gate_reason": "x", "summary": "could not finish",
    })

    def runner(command, **kwargs):
        return _completed(0, stdout=payload)

    result = run_claude("task", Path("."), runner=runner)
    assert not result.ok
    assert result.status is None


def test_run_claude_missing_structured_output_fails_closed():
    payload = json.dumps({"is_error": False, "result": "done"})

    def runner(command, **kwargs):
        return _completed(0, stdout=payload)

    result = run_claude("task", Path("."), runner=runner)
    assert not result.ok
    assert result.status is None


def test_run_claude_structured_output_not_a_dict_fails_closed():
    payload = json.dumps({"is_error": False, "result": "done", "structured_output": "COMPLETED"})

    def runner(command, **kwargs):
        return _completed(0, stdout=payload)

    result = run_claude("task", Path("."), runner=runner)
    assert not result.ok
    assert result.status is None


def test_run_claude_invalid_status_enum_fails_closed():
    payload = _wrap({"status": "MAYBE", "gate_category": None, "gate_reason": None, "summary": "x"})

    def runner(command, **kwargs):
        return _completed(0, stdout=payload)

    result = run_claude("task", Path("."), runner=runner)
    assert not result.ok
    assert result.status is None


def test_run_claude_top_level_not_a_dict_fails_closed():
    def runner(command, **kwargs):
        return _completed(0, stdout=json.dumps(["unexpected", "array"]))

    result = run_claude("task", Path("."), runner=runner)
    assert not result.ok
    assert result.status is None


def test_run_claude_reports_is_error():
    payload = json.dumps({"is_error": True, "result": "could not comply"})

    def runner(command, **kwargs):
        return _completed(0, stdout=payload)

    result = run_claude("task", Path("."), runner=runner)
    assert not result.ok


def test_run_claude_nonzero_exit_fails_closed():
    def runner(command, **kwargs):
        return _completed(1, stdout="", stderr="crashed")

    result = run_claude("task", Path("."), runner=runner)
    assert not result.ok
    assert "1" in result.error


def test_run_claude_unparseable_output_fails_closed():
    def runner(command, **kwargs):
        return _completed(0, stdout="not json")

    result = run_claude("task", Path("."), runner=runner)
    assert not result.ok
    assert "parse" in result.error


def test_run_claude_subprocess_error_fails_closed():
    def runner(command, **kwargs):
        raise FileNotFoundError("claude not found")

    result = run_claude("task", Path("."), runner=runner)
    assert not result.ok
    assert "claude" in result.error.lower()


def test_run_claude_completed_with_non_string_gate_reason_is_rejected_not_coerced():
    """Latest Codex review, Finding 2, directly reproduced: a schema-
    invalid gate_reason (the schema requires string or null; this payload
    supplies an int) was previously silently coerced to None by the
    isinstance check, which then made the status/gate consistency check
    see nothing wrong -- a malformed payload was accepted as a
    well-formed COMPLETED result (ok=True). Must now fail closed.
    """
    payload = _wrap({"status": "COMPLETED", "gate_category": None, "gate_reason": 12345, "summary": "did the thing"})

    def runner(command, **kwargs):
        return _completed(0, stdout=payload)

    result = run_claude("task", Path("."), runner=runner)
    assert not result.ok
    assert result.status is None
    assert "gate_reason" in result.error


def test_run_claude_structured_output_with_unexpected_extra_field_is_rejected():
    """Local validation must enforce `additionalProperties: False` from
    CLAUDE_RESULT_SCHEMA, not merely the fields it happens to read.
    """
    payload = json.dumps({
        "is_error": False,
        "result": "done",
        "structured_output": {
            "status": "COMPLETED", "gate_category": None, "gate_reason": None,
            "summary": "did the thing", "unexpected_field": "should not be here",
        },
    })

    def runner(command, **kwargs):
        return _completed(0, stdout=payload)

    result = run_claude("task", Path("."), runner=runner)
    assert not result.ok
    assert result.status is None
    assert "unexpected" in result.error.lower()


def test_run_claude_missing_required_keys_is_rejected_not_treated_as_null():
    """Final acceptance review, directly reproduced:
    {"status":"COMPLETED","summary":"ok"} (gate_category and gate_reason
    keys omitted entirely, not set to null) was previously accepted,
    because `.get()` cannot distinguish an absent key from an explicit
    null value. gate_category and gate_reason are schema-required KEYS
    even though their VALUES may be null, so this must fail closed.
    """
    payload = json.dumps({
        "is_error": False,
        "result": "ok",
        "structured_output": {"status": "COMPLETED", "summary": "ok"},
    })

    def runner(command, **kwargs):
        return _completed(0, stdout=payload)

    result = run_claude("task", Path("."), runner=runner)
    assert not result.ok
    assert result.status is None
    assert "gate_category" in result.error
    assert "gate_reason" in result.error


def test_run_claude_nonzero_exit_prefers_structured_result_message():
    """SPEC-003 AC-8a: on a non-zero exit, when `stdout` is valid JSON
    with `is_error`/`result`, the CLI's own structured error message is
    used -- not a raw-text tail -- and is classified `authentication`.
    This is the exact incident this spec fixes: a bare "claude exited
    with status 1" previously hid the actionable "Not logged in" text.
    """
    payload = json.dumps({"is_error": True, "result": "Not logged in · Please run /login"})

    def runner(command, **kwargs):
        return _completed(1, stdout=payload, stderr="")

    result = run_claude("task", Path("."), runner=runner)
    assert not result.ok
    assert "[authentication]" in result.error
    assert "Not logged in" in result.error


def test_run_claude_nonzero_exit_falls_back_to_raw_tail_when_stdout_is_not_json():
    """SPEC-003 AC-8b: when `stdout` is not parseable JSON, the bounded
    raw-text fallback is still classified correctly from its content.
    """
    def runner(command, **kwargs):
        return _completed(1, stdout="", stderr="Not logged in · Please run /login")

    result = run_claude("task", Path("."), runner=runner)
    assert not result.ok
    assert "[authentication]" in result.error
    assert "Not logged in" in result.error


def test_run_claude_nonzero_exit_redacts_a_secret_shaped_string():
    """SPEC-003 AC-9: a token-shaped substring in captured output must
    not appear verbatim in `.error`.
    """
    secret = "sk-liveAbCdEfGhIjKlMnOpQrSt"

    def runner(command, **kwargs):
        return _completed(1, stdout="", stderr=f"request failed, key={secret} was rejected")

    result = run_claude("task", Path("."), runner=runner)
    assert not result.ok
    assert secret not in result.error
    assert "[REDACTED]" in result.error


def test_run_claude_zero_exit_structured_is_error_retains_authentication_classification():
    """Focused Codex review remediation, Finding 6 (MINOR): a zero-
    returncode response whose structured payload is `is_error: true`
    with an actionable `result` message (e.g. the literal "Not logged
    in · Please run /login" from the dogfood incident SPEC-003 fixes)
    must fail closed with `authentication` classification and that
    phrase retained -- not collapse to the generic, unclassified
    "[schema] Claude Code reported is_error=true" this previously always
    produced regardless of what the CLI actually said.
    """
    payload = json.dumps({"is_error": True, "result": "Not logged in · Please run /login"})

    def runner(command, **kwargs):
        return _completed(0, stdout=payload)

    result = run_claude("task", Path("."), runner=runner)
    assert not result.ok
    assert "[authentication]" in result.error
    assert "Not logged in" in result.error


def test_run_claude_zero_exit_structured_is_error_without_result_field_falls_back_closed():
    """Companion case: is_error=true with no usable `result` string must
    still fail closed (never ok=True), falling back to the raw-text
    path rather than crashing or guessing a success.
    """
    payload = json.dumps({"is_error": True})

    def runner(command, **kwargs):
        return _completed(0, stdout=payload)

    result = run_claude("task", Path("."), runner=runner)
    assert not result.ok
    assert result.error


def test_run_claude_completed_summary_is_redacted_of_a_secret_shaped_string():
    """Focused Codex review remediation, Finding 3 (MAJOR): `summary` is
    agent-controlled free text that flows straight into workflow.py's
    logs and report.py's rendered output -- unlike `.error`, it
    previously never passed through the shared redaction mechanism at
    all.
    """
    secret = "sk-liveAbCdEfGhIjKlMnOpQrSt"
    payload = _wrap({
        "status": "COMPLETED", "gate_category": None, "gate_reason": None,
        "summary": f"Implemented the thing using key={secret} for testing",
    })

    def runner(command, **kwargs):
        return _completed(0, stdout=payload)

    result = run_claude("task", Path("."), runner=runner)
    assert result.ok
    assert secret not in result.summary
    assert "[REDACTED]" in result.summary


def test_run_claude_human_gate_reason_is_redacted_of_a_secret_shaped_string():
    """Finding 3 (continued): same requirement for `gate_reason`, the
    exact string peos/workflow.py embeds verbatim into its human-gate
    log message and report.py then renders under "## Human gate".
    """
    secret = "sk-liveAbCdEfGhIjKlMnOpQrSt"
    payload = _wrap({
        "status": "HUMAN_GATE", "gate_category": "architecture",
        "gate_reason": f"found hardcoded credential key={secret} in config, needs a human decision",
        "summary": "stopped",
    })

    def runner(command, **kwargs):
        return _completed(0, stdout=payload)

    result = run_claude("task", Path("."), runner=runner)
    assert not result.ok
    assert result.human_gate
    assert secret not in result.gate_reason
    assert "[REDACTED]" in result.gate_reason
    assert secret not in (result.error or "")


def test_run_claude_missing_summary_key_is_rejected():
    payload = json.dumps({
        "is_error": False,
        "result": "",
        "structured_output": {"status": "COMPLETED", "gate_category": None, "gate_reason": None},
    })

    def runner(command, **kwargs):
        return _completed(0, stdout=payload)

    result = run_claude("task", Path("."), runner=runner)
    assert not result.ok
    assert result.status is None
    assert "summary" in result.error
