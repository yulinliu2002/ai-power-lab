"""Tests for the final PEOS report (peos/report.py, AC-012, remediated
per SPEC-001 Finding 10)."""

from pathlib import Path

from peos.codex_agent import CodexReviewResult, Finding
from peos.report import build_report
from peos.sandbox import ReconciliationResult
from peos.spec import SpecCandidate
from peos.verification_plan import VerificationStep, VerificationPlan
from peos.verify import CommandResult, VerificationReport
from peos.workflow import PhaseLog, RunResult

from tests._peos_fixtures import make_minimal_repo

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC = SpecCandidate(path=Path("docs/specifications/SPEC-001-x.md"), title="X", status="Approved")


def test_report_contains_core_sections_for_approved_run():
    result = RunResult(
        task="do the thing",
        outcome="APPROVED",
        phases=(PhaseLog(phase="Intake"), PhaseLog(phase="Complete")),
        spec=SPEC,
        claude_runs=(),
        verification_reports=(VerificationReport((CommandResult(
            name="pytest", command=(), cwd=".", returncode=0, stdout="", stderr=""),)),),
        review_results=(CodexReviewResult(
            returncode=0, verdict="APPROVE", summary="ok", findings=(), acceptance_criteria=(),
            raw_stdout="", raw_stderr="", ok=True,
        ),),
        remediation_performed=False,
    )
    report = build_report(result, REPO_ROOT)
    assert "do the thing" in report
    assert "SPEC-001-x.md" in report
    assert "APPROVED" in report
    assert "Known limitations" in report
    assert "Recommended next human action" in report


def test_report_surfaces_gate_reason_and_findings():
    finding = Finding(severity="blocking", category="architecture_concern",
                       description="changes control topology", requires_human_decision=True)
    result = RunResult(
        task="do the thing",
        outcome="HUMAN_GATE",
        phases=(PhaseLog(phase="Intake"),),
        spec=SPEC,
        gate_id="6",
        gate_reason="requires a human-owned engineering decision",
        review_results=(CodexReviewResult(
            returncode=0, verdict="CHANGES_REQUIRED", summary="issues", findings=(finding,),
            acceptance_criteria=(), raw_stdout="", raw_stderr="", ok=True,
        ),),
    )
    report = build_report(result, REPO_ROOT)
    assert "Gate #6" in report
    assert "human-owned engineering decision" in report
    assert "HUMAN DECISION" in report
    assert "changes control topology" in report


def test_report_includes_git_status_section():
    result = RunResult(task="t", outcome="FAILED", gate_reason="boom")
    report = build_report(result, REPO_ROOT)
    assert "Git working-tree status" in report
    assert "Branch:" in report


def test_report_includes_untracked_files_in_changed_files_section(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    (repo_root / "brand_new_file.py").write_text("x = 1\n", encoding="utf-8")
    result = RunResult(task="t", outcome="APPROVED", spec=SPEC)
    report = build_report(result, repo_root)
    assert "brand_new_file.py" in report


def test_report_includes_frozen_verification_plan():
    plan = VerificationPlan((
        VerificationStep(name="python tests (pytest -q)", command=("pytest", "-q"), cwd_relative=".", required_input="tests"),
    ))
    result = RunResult(task="t", outcome="APPROVED", spec=SPEC, verification_plan=plan)
    report = build_report(result, REPO_ROOT)
    assert "Frozen verification plan" in report
    assert "python tests (pytest -q)" in report


def test_report_includes_reconciliation_and_workspace_path():
    reconciliation = ReconciliationResult(copied=("a.py",), deleted=("b.py",), blocked_governance_changes=("CLAUDE.md",))
    result = RunResult(
        task="t", outcome="APPROVED", spec=SPEC,
        workspace_path="/tmp/peos-abc123/workspace",
        reconciliation=reconciliation,
        blocked_governance_mutation=("CLAUDE.md",),
    )
    report = build_report(result, REPO_ROOT)
    assert "a.py" in report
    assert "b.py" in report
    assert "/tmp/peos-abc123/workspace" in report
    assert "CLAUDE.md" in report
    assert "Task-specific limitations" in report


def test_report_always_shows_resolved_spec_even_on_failure():
    result = RunResult(task="t", outcome="FAILED", spec=SPEC, gate_reason="verification failed")
    report = build_report(result, REPO_ROOT)
    assert "SPEC-001-x.md" in report


def test_report_surfaces_reconciliation_error(tmp_path):
    """Finding 9 (second pass): a reconciliation failure (distinct from
    a normal blocked-governance-change) must be visible in the report,
    explaining why an outcome that might otherwise look like a clean
    approval is FAILED instead (Finding 8)."""
    result = RunResult(
        task="t", outcome="FAILED", spec=SPEC,
        gate_reason="Codex approved the implementation, but reconciling ... failed: disk full",
        reconciliation_error="disk full, could not copy workspace changes back",
    )
    report = build_report(result, REPO_ROOT)
    assert "reconciliation failed" in report.lower()
    assert "disk full" in report


def test_report_surfaces_unavailable_sandbox_as_a_task_specific_limitation():
    plan = VerificationPlan((
        VerificationStep(name="python tests (pytest -q)", command=("pytest", "-q"), cwd_relative=".", required_input="tests"),
    ))
    failure = CommandResult(
        name="python tests (pytest -q)", command=(), cwd=".", returncode=-1, stdout="", stderr="",
        ran=False, error="The verification execution sandbox (macOS sandbox-exec) is not available",
    )
    result = RunResult(
        task="t", outcome="FAILED", spec=SPEC, verification_plan=plan,
        verification_reports=(VerificationReport((failure,)),),
        gate_reason="Local verification failed after implementation: python tests (pytest -q)",
    )
    report = build_report(result, REPO_ROOT)
    assert "sandbox-exec" in report
    assert "Task-specific limitations" in report
