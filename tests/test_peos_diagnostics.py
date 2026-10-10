"""Tests for the shared, bounded, sanitized failure diagnostic helper
(peos/diagnostics.py, SPEC-003 Requirement 4).

Covers SPEC-003 acceptance criteria AC-7, AC-8a, AC-8b, AC-9 at the
helper level; peos/claude_agent.py and peos/codex_agent.py's own test
files cover the same criteria at the wiring level (that `run_claude`/
`run_codex_review` actually route through this helper correctly).
"""

from peos.diagnostics import (
    GENERIC_TOKEN_MIN_LEN,
    MAX_DIAGNOSTIC_CHARS,
    bound,
    build_diagnostic,
    classify,
    redact,
)


def test_bound_leaves_short_text_untouched():
    assert bound("short") == "short"


def test_bound_keeps_the_tail_of_long_text():
    text = "a" * 10 + "b" * (MAX_DIAGNOSTIC_CHARS + 50)
    result = bound(text)
    assert len(result) == MAX_DIAGNOSTIC_CHARS
    assert result == "b" * MAX_DIAGNOSTIC_CHARS
    assert "a" not in result


def test_redact_masks_a_bearer_token():
    text = "request failed: Authorization: Bearer abc123.def456-ghi789 rejected"
    redacted = redact(text)
    assert "abc123" not in redacted
    assert "[REDACTED]" in redacted


def test_redact_masks_an_sk_prefixed_key():
    text = "invalid key sk-liveAbCdEfGhIjKlMnOp supplied"
    redacted = redact(text)
    assert "sk-liveAbCdEfGhIjKlMnOp" not in redacted
    assert "[REDACTED]" in redacted


def test_redact_masks_a_generic_long_token_shaped_run():
    long_token = "x" * GENERIC_TOKEN_MIN_LEN
    redacted = redact(f"token={long_token} end")
    assert long_token not in redacted
    assert "[REDACTED]" in redacted


def test_redact_does_not_mask_legitimate_schema_vocabulary_below_the_threshold():
    """Deviation from SPEC-003's illustrative "20+ character" example,
    recorded in peos/diagnostics.py's module docstring: this codebase's
    own field/enum names (acceptance_criteria=20 chars,
    missing_validation_evidence=28 chars) must survive redaction, or
    legitimate, non-secret error messages become unreadable.
    """
    text = (
        "Codex returned a contradictory APPROVE: verdict=APPROVE but no "
        "acceptance_criteria evidence was provided, category "
        "missing_validation_evidence, requires_human_decision"
    )
    redacted = redact(text)
    assert "acceptance_criteria" in redacted
    assert "missing_validation_evidence" in redacted
    assert "requires_human_decision" in redacted
    assert "[REDACTED]" not in redacted


def test_classify_authentication_phrase():
    assert classify("Not logged in · Please run /login") == "authentication"


def test_classify_cli_invocation_phrase():
    assert classify("bash: claude: command not found") == "cli_invocation"


def test_classify_defaults_to_runtime():
    assert classify("some other unexpected failure text") == "runtime"


def test_build_diagnostic_prefers_structured_message_over_raw_tail():
    diagnostic = build_diagnostic(
        stdout="raw garbage that should be ignored",
        stderr="more raw garbage",
        structured_message="Not logged in · Please run /login",
    )
    assert "[authentication]" in diagnostic
    assert "Not logged in" in diagnostic
    assert "raw garbage" not in diagnostic


def test_build_diagnostic_falls_back_to_raw_tail_when_no_structured_message():
    diagnostic = build_diagnostic(stdout="", stderr="Not logged in · Please run /login")
    assert "[authentication]" in diagnostic
    assert "Not logged in" in diagnostic


def test_build_diagnostic_fallback_gives_stderr_priority_on_truncation():
    # Space-separated filler (not a single long token-shaped run, so this
    # test isolates truncation priority from the redaction behavior
    # covered separately above) with a unique marker at the very start
    # of stdout -- far enough from the tail that a 500-char bound drops
    # it, while stderr (placed last, so it survives truncation) and its
    # content fully remain.
    stdout = "STDOUT_HEAD_MARKER " + ("filler word " * 100)
    stderr = "distinctive stderr tail content"
    diagnostic = build_diagnostic(stdout=stdout, stderr=stderr)
    assert "distinctive stderr tail content" in diagnostic
    assert "STDOUT_HEAD_MARKER" not in diagnostic


def test_build_diagnostic_redacts_a_secret_even_straddling_the_truncation_boundary():
    """Regression for the exact failure mode that makes bound-then-redact
    unsafe: a token placed right at the truncation boundary must still
    be fully redacted, not leaked as a truncated fragment that no longer
    matches the redaction pattern.
    """
    token = "s3cr3t-token-" + ("a" * 40)
    stdout = ("padding " * 100) + token
    diagnostic = build_diagnostic(stdout=stdout, stderr="")
    assert token not in diagnostic
    assert "a" * 40 not in diagnostic


def test_build_diagnostic_is_bounded_even_for_a_structured_message():
    diagnostic = build_diagnostic(structured_message="z" * (MAX_DIAGNOSTIC_CHARS * 2))
    assert len(diagnostic) <= MAX_DIAGNOSTIC_CHARS


def test_build_diagnostic_complete_string_including_prefix_never_exceeds_the_bound():
    """Focused Codex review remediation, Finding 5 (MINOR): the fixed
    500-character budget covers the *complete* returned diagnostic,
    including the `[category]`/`exit=N: ` prefix this function
    prepends -- not just the message body. A long body plus a non-empty
    prefix must still fit, with the prefix's space reserved out of the
    budget rather than appended on top of an already-500-character body.
    """
    diagnostic = build_diagnostic(
        stdout="", stderr="z" * (MAX_DIAGNOSTIC_CHARS * 2), exit_code=12345,
    )
    assert len(diagnostic) <= MAX_DIAGNOSTIC_CHARS


def test_build_diagnostic_total_length_assertion_direct():
    """Same requirement as above, phrased as the direct assertion the
    finding specifically asks for."""
    final_diagnostic = build_diagnostic(
        structured_message="Not logged in · Please run /login " + ("x" * MAX_DIAGNOSTIC_CHARS),
        exit_code=1,
    )
    assert len(final_diagnostic) <= 500


def test_build_diagnostic_category_override_skips_phrase_matching():
    diagnostic = build_diagnostic(
        structured_message="could not parse Codex JSON output: not logged in happens to appear here",
        category_override="schema",
    )
    assert diagnostic.startswith("[schema]")


def test_build_diagnostic_includes_exit_code_when_given():
    diagnostic = build_diagnostic(stdout="", stderr="crashed", exit_code=1)
    assert "exit=1" in diagnostic
    assert "crashed" in diagnostic


def test_build_diagnostic_omits_exit_code_part_when_not_given():
    diagnostic = build_diagnostic(structured_message="no exit code here", category_override="schema")
    assert "exit=" not in diagnostic
