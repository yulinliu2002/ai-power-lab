"""Tests for peos/runtime_evidence.py (SPEC-006 Section 9/12/13).

AC-012 (console/page error forces FAIL -- exercised at the
runtime_browser layer, not here), AC-013 (secret redaction), AC-014/
AC-014a (cycle-qualified, non-overwriting persistence), AC-017 (bounds +
truncation metadata, never silent), AC-018/AC-019 (staged copy identity/
drift), AC-022-025 (four-state AC rollup).
"""

import pytest

from peos.runtime_evidence import (
    MAX_SCREENSHOT_BYTES,
    MAX_SERVICE_TAIL_CHARS,
    RuntimeEvidence,
    RuntimeEvidenceError,
    build_runtime_check,
    build_service_readiness,
    persist_evidence,
    reverify_evidence_identity,
    stage_evidence_into_workspace,
)


def _make_check(check_id="runtime.0.viewport_overflow.mobile", status="PASS", related_ac_ids=("AC-012",), screenshot=b"\x89PNG-fake"):
    check, screenshot_bytes = build_runtime_check(
        check_id=check_id, kind="viewport_overflow", related_ac_ids=related_ac_ids,
        parameters={"viewport": "mobile"}, status=status,
        action_performed="set viewport to mobile", observation="no overflow detected",
        measurements={"scroll_width_px": 390, "client_width_px": 390},
        screenshot_bytes=screenshot, started_at="2026-01-01T00:00:00Z", finished_at="2026-01-01T00:00:01Z",
    )
    return check, screenshot_bytes


def _make_evidence(run_id="run1", cycle_label="cycle 0", checks=()):
    return RuntimeEvidence(
        run_id=run_id, cycle_label=cycle_label, workspace_snapshot_identity="abc123",
        baseline_commit="deadbeef", catalog_version="1.0.0", playwright_version="1.49.1",
        browser_version="131.0.0.0", browser_environment={"viewport": "mobile"},
        service_readiness=(), checks=checks, execution_integrity_passed=True,
    )


def test_build_runtime_check_computes_screenshot_hash():
    check, screenshot_bytes = _make_check()
    assert check.status == "PASS"
    assert check.screenshot_path == "screenshots/runtime.0.viewport_overflow.mobile.png"
    assert check.screenshot_sha256 is not None
    assert screenshot_bytes == b"\x89PNG-fake"


def test_ac017_oversized_screenshot_is_truncated_with_reason_not_silently():
    check, screenshot_bytes = build_runtime_check(
        check_id="x", kind="viewport_overflow", related_ac_ids=("AC-012",), parameters={},
        status="PASS", action_performed="a", observation="o", measurements={},
        screenshot_bytes=b"x" * (MAX_SCREENSHOT_BYTES + 1),
    )
    assert check.truncated is True
    assert check.omitted_reason is not None
    assert check.screenshot_path is None
    assert screenshot_bytes is None


def test_ac013_console_error_secret_redacted():
    secret = "sk-" + "a" * 20
    check, _ = build_runtime_check(
        check_id="x", kind="page_load", related_ac_ids=("AC-001",), parameters={},
        status="FAIL", action_performed="a", observation="o", measurements={},
        screenshot_bytes=None, console_errors=(f"leaked token {secret}",),
    )
    assert secret not in check.console_errors[0]
    assert "[REDACTED]" in check.console_errors[0]


def test_service_readiness_tail_bounded_and_truncation_flagged():
    # Realistic, non-token-shaped log text (spaces break up the generic
    # secret-redaction pattern, which only matches a contiguous run of
    # [A-Za-z0-9_-.] -- an all-one-character string would otherwise be
    # treated as one giant token and collapsed by redaction itself).
    long_log = "INFO request handled ok\n" * ((MAX_SERVICE_TAIL_CHARS // 24) + 50)
    sr = build_service_readiness(
        service="backend", command=("uvicorn",), resolved_port=54321, ready=True,
        waited_seconds=1.2, stdout=long_log, stderr="",
    )
    assert sr.truncated is True
    assert len(sr.captured_stdout_tail) <= MAX_SERVICE_TAIL_CHARS


def test_ac013_service_readiness_truncation_bound_is_64kib_not_500_chars():
    """Codex implementation review Finding 6, closed: previously,
    routing a tail through `sanitize_human_text` silently re-truncated
    it to 500 characters (that function's own, unrelated bound) while
    `truncated` was computed against the documented 64 KiB bound --
    a 2000-character tail was marked truncated=False despite having
    already lost everything past character 500. The same text used in
    the test above, sized to stay under 64 KiB but over 500 chars,
    must now survive intact and marked truncated=False.
    """
    text = "INFO ok\n" * 100  # 800 chars: over 500, comfortably under 64 KiB
    sr = build_service_readiness(
        service="backend", command=("uvicorn",), resolved_port=1, ready=True,
        waited_seconds=0.1, stdout=text, stderr="",
    )
    assert sr.truncated is False
    assert len(sr.captured_stdout_tail) == len(text)


def test_ac014_persist_writes_json_and_sidecar_hash(tmp_path):
    check, screenshot_bytes = _make_check()
    evidence = _make_evidence(checks=(check,))
    persisted = persist_evidence(tmp_path, "run1", evidence, {check.check_id: screenshot_bytes})

    assert persisted.evidence_json_path.is_file()
    assert persisted.evidence_hash_path.is_file()
    assert persisted.evidence_hash_path.read_text() == persisted.evidence_json_sha256
    assert (persisted.evidence_dir / "screenshots" / f"{check.check_id}.png").is_file()


def test_ac014a_two_rounds_produce_distinct_non_overwriting_directories(tmp_path):
    check0, s0 = _make_check(check_id="c0")
    check1, s1 = _make_check(check_id="c1")
    ev0 = _make_evidence(cycle_label="cycle 0", checks=(check0,))
    ev1 = _make_evidence(cycle_label="remediation cycle 1", checks=(check1,))

    p0 = persist_evidence(tmp_path, "run1", ev0, {"c0": s0})
    p1 = persist_evidence(tmp_path, "run1", ev1, {"c1": s1})

    assert p0.evidence_dir != p1.evidence_dir
    assert p0.evidence_json_path.is_file()
    assert p1.evidence_json_path.is_file()
    assert p0.evidence_json_path.read_text() != p1.evidence_json_path.read_text()


def test_persist_refuses_to_overwrite_same_cycle_twice(tmp_path):
    check, s = _make_check()
    evidence = _make_evidence(checks=(check,))
    persist_evidence(tmp_path, "run1", evidence, {check.check_id: s})
    with pytest.raises(RuntimeEvidenceError):
        persist_evidence(tmp_path, "run1", evidence, {check.check_id: s})


def test_ac018_ac019_staged_copy_identity_and_drift(tmp_path):
    check, s = _make_check()
    evidence = _make_evidence(checks=(check,))
    persisted = persist_evidence(tmp_path, "run1", evidence, {check.check_id: s})

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    staged_dir = stage_evidence_into_workspace(workspace, persisted, evidence.cycle_label)
    assert (staged_dir / "evidence.json").is_file()

    result = reverify_evidence_identity(persisted, staged_dir)
    assert result.ok

    # Simulate drift: the staged copy is altered after staging.
    staged_file = staged_dir / "evidence.json"
    import os
    import stat as statmod
    os.chmod(staged_file, statmod.S_IWUSR | statmod.S_IRUSR)
    staged_file.write_text("{}")
    drift = reverify_evidence_identity(persisted, staged_dir)
    assert not drift.ok
    assert "no longer matches" in drift.reason


def test_ac022_024_ac_rollup_pass_requires_all_mapped_checks_pass():
    passing, _ = _make_check(check_id="a", status="PASS", related_ac_ids=("AC-012",))
    evidence = _make_evidence(checks=(passing,))
    assert evidence.ac_status("AC-012") == "PASS"
    assert evidence.runtime_evidenced_ac_status() == {"AC-012": "PASS"}


def test_ac022_ac_rollup_fail_if_any_mapped_check_fails():
    passing, _ = _make_check(check_id="a", status="PASS", related_ac_ids=("AC-012",))
    failing, _ = _make_check(check_id="b", status="FAIL", related_ac_ids=("AC-012",))
    evidence = _make_evidence(checks=(passing, failing))
    assert evidence.ac_status("AC-012") == "FAIL"


def test_ac025_not_applicable_when_no_check_maps_the_ac():
    passing, _ = _make_check(check_id="a", status="PASS", related_ac_ids=("AC-012",))
    evidence = _make_evidence(checks=(passing,))
    assert evidence.ac_status("AC-999") == "NOT_APPLICABLE"
    assert "AC-999" not in evidence.runtime_evidenced_ac_status()


def test_not_executed_rollup_when_no_fail_but_a_check_never_ran():
    not_executed, _ = build_runtime_check(
        check_id="c", kind="page_load", related_ac_ids=("AC-001",), parameters={},
        status="NOT_EXECUTED", action_performed="a", observation="o", measurements={},
        screenshot_bytes=None,
    ), None
    evidence = _make_evidence(checks=(not_executed[0],))
    assert evidence.ac_status("AC-001") == "NOT_EXECUTED"


def test_ac017_console_error_list_is_bounded_and_flagged_truncated():
    """Codex implementation review Finding 6: a pathological page
    emitting far more than a handful of console errors must not blow
    the per-round evidence budget -- the list is capped, and the cap
    being hit is represented in `truncated`, never silent."""
    many_errors = tuple(f"error {i}" for i in range(50))
    check, _ = build_runtime_check(
        check_id="x", kind="page_load", related_ac_ids=("AC-001",), parameters={},
        status="FAIL", action_performed="a", observation="o", measurements={},
        screenshot_bytes=None, console_errors=many_errors,
    )
    assert len(check.console_errors) <= 20
    assert check.truncated is True


def test_ac017_measurements_dict_item_count_is_bounded_and_flagged_truncated():
    many_measurements = {f"k{i}": i for i in range(50)}
    check, _ = build_runtime_check(
        check_id="x", kind="viewport_overflow", related_ac_ids=("AC-012",), parameters={},
        status="PASS", action_performed="a", observation="o", measurements=many_measurements,
        screenshot_bytes=None,
    )
    assert len(check.measurements) <= 20
    assert check.truncated is True


def test_measurements_string_values_are_secret_redacted():
    secret = "sk-" + "b" * 20
    check, _ = build_runtime_check(
        check_id="x", kind="page_load", related_ac_ids=("AC-001",), parameters={},
        status="PASS", action_performed="a", observation="o",
        measurements={"leaked": secret}, screenshot_bytes=None,
    )
    assert secret not in check.measurements["leaked"]


def test_ac006_persist_rolls_up_check_and_service_truncation_into_package_flag(tmp_path):
    many_errors = tuple(f"error {i}" for i in range(50))
    check, screenshot_bytes = build_runtime_check(
        check_id="c0", kind="page_load", related_ac_ids=("AC-001",), parameters={},
        status="FAIL", action_performed="a", observation="o", measurements={},
        screenshot_bytes=None, console_errors=many_errors,
    )
    assert check.truncated is True  # precondition: the check itself is already flagged

    evidence = _make_evidence(checks=(check,))
    assert evidence.truncated is False  # the RuntimeEvidence record itself was built with the default

    persisted = persist_evidence(tmp_path, "run-rollup", evidence, {})
    import json
    payload = json.loads(persisted.evidence_json_path.read_text())
    assert payload["truncated"] is True  # rolled up from the check, not left False


def test_ac007_persist_rejects_screenshot_bytes_that_do_not_match_the_recorded_hash(tmp_path):
    check, _ = _make_check(check_id="c1")
    evidence = _make_evidence(checks=(check,))
    tampered_bytes = b"not-the-real-screenshot-bytes"
    persisted = persist_evidence(tmp_path, "run-tamper", evidence, {check.check_id: tampered_bytes})
    import json
    payload = json.loads(persisted.evidence_json_path.read_text())
    assert payload["checks"][0]["screenshot_path"] is None
    assert payload["checks"][0]["truncated"] is True
    assert "hash" in payload["checks"][0]["omitted_reason"]
