"""Tests for the deterministic local verification primitive (peos/verify.py).

`run_verification` (a convenience wrapper that re-derived "which commands
to run" on every call) was removed in the SPEC-001 second remediation
pass: it was dead code from the real workflow's point of view (the only
caller was its own test file) and its existence risked being mistaken for
a supported, sandboxed verification entry point. `peos/verification_plan.py`
is the sole supported entry point now; see tests/test_peos_verification_plan.py.
"""

from pathlib import Path

from peos.verify import CommandResult, VerificationReport, run_command


def test_command_result_passed_requires_ran_and_zero_exit():
    assert CommandResult(name="x", command=(), cwd=".", returncode=0, stdout="", stderr="").passed
    assert not CommandResult(name="x", command=(), cwd=".", returncode=1, stdout="", stderr="").passed
    assert not CommandResult(
        name="x", command=(), cwd=".", returncode=0, stdout="", stderr="", ran=False, error="nope"
    ).passed


def test_verification_report_passed_and_failures(tmp_path: Path):
    ok = CommandResult(name="ok", command=(), cwd=".", returncode=0, stdout="", stderr="")
    bad = CommandResult(name="bad", command=(), cwd=".", returncode=1, stdout="", stderr="boom")
    report = VerificationReport((ok, bad))
    assert not report.passed
    assert report.failures == (bad,)
    assert VerificationReport((ok,)).passed


def test_run_command_executes_and_captures_exit_status(tmp_path: Path):
    result = run_command("echo ok", ["python3", "-c", "print('hi')"], tmp_path)
    assert result.passed
    assert "hi" in result.stdout


def test_run_command_fails_closed_on_nonzero_exit(tmp_path: Path):
    result = run_command("fail", ["python3", "-c", "import sys; sys.exit(1)"], tmp_path)
    assert not result.passed
    assert result.ran
    assert result.returncode == 1


def test_run_command_passes_env_through_to_subprocess(tmp_path: Path):
    result = run_command(
        "env check",
        ["python3", "-c", "import os; print(os.environ.get('PEOS_TEST_MARKER', '<missing>'))"],
        tmp_path,
        env={"PEOS_TEST_MARKER": "present", "PATH": "/usr/bin:/bin"},
    )
    assert result.passed
    assert "present" in result.stdout


def test_run_command_uninterpretable_command_does_not_crash(tmp_path: Path):
    result = run_command("missing binary", ["peos-definitely-not-a-real-binary"], tmp_path)
    assert not result.ran
    assert not result.passed
    assert result.error
