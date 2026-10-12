"""Tests for the final PEOS report (peos/report.py, AC-012, remediated
per SPEC-001 Finding 10)."""

import json
import subprocess
from pathlib import Path

from peos.claude_agent import ClaudeRunResult, run_claude
from peos.codex_agent import CodexReviewResult, Finding, run_codex_review
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


def test_report_shows_no_runtime_evidence_section_when_none_ran():
    result = RunResult(
        task="do the thing", outcome="APPROVED",
        phases=(PhaseLog(phase="Complete"),), spec=SPEC, claude_runs=(),
        verification_reports=(), review_results=(), remediation_performed=False,
    )
    report = build_report(result, REPO_ROOT)
    assert "## Runtime evidence" in report
    assert "no runtime checks declared" in report


def test_ac021_report_shows_every_rounds_runtime_evidence_not_only_the_latest():
    from peos.runtime_evidence import PersistedEvidence, RuntimeEvidence, build_runtime_check
    from peos.runtime_verification import RuntimeVerificationOutcome

    check, _ = build_runtime_check(
        check_id="runtime.cycle-0.0.viewport_overflow", kind="viewport_overflow",
        related_ac_ids=("AC-012",), parameters={}, status="PASS",
        action_performed="x", observation="x", measurements={}, screenshot_bytes=None,
    )
    evidence0 = RuntimeEvidence(
        run_id="r", cycle_label="cycle 0", workspace_snapshot_identity="fp", baseline_commit="bc",
        catalog_version="1.0.0", playwright_version="1.49.1", browser_version="fake",
        browser_environment={}, service_readiness=(), checks=(check,), execution_integrity_passed=True,
    )
    evidence1 = RuntimeEvidence(**{**evidence0.__dict__, "cycle_label": "remediation cycle 1"})
    persisted0 = PersistedEvidence(
        evidence_dir=Path("/tmp/e0"), evidence_json_path=Path("/tmp/e0/evidence.json"),
        evidence_hash_path=Path("/tmp/e0/evidence.json.sha256"), evidence_json_sha256="a" * 64,
    )
    persisted1 = PersistedEvidence(
        evidence_dir=Path("/tmp/e1"), evidence_json_path=Path("/tmp/e1/evidence.json"),
        evidence_hash_path=Path("/tmp/e1/evidence.json.sha256"), evidence_json_sha256="b" * 64,
    )
    result = RunResult(
        task="do the thing", outcome="APPROVED",
        phases=(PhaseLog(phase="Complete"),), spec=SPEC, claude_runs=(),
        verification_reports=(), review_results=(), remediation_performed=True,
        runtime_verification_history=(
            RuntimeVerificationOutcome(ran=True, execution_integrity_passed=True, failure_reason=None,
                                        evidence=evidence0, persisted=persisted0, staged_dir=Path("/tmp/s0")),
            RuntimeVerificationOutcome(ran=True, execution_integrity_passed=True, failure_reason=None,
                                        evidence=evidence1, persisted=persisted1, staged_dir=Path("/tmp/s1")),
        ),
    )
    report = build_report(result, REPO_ROOT)
    assert "cycle 0" in report
    assert "remediation cycle 1" in report
    assert "a" * 64 in report
    assert "b" * 64 in report


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


def test_report_shows_manual_verification_items_distinctly_and_marks_them_not_executed():
    """Manual/observational verification requirements from the governing
    spec must remain visible in the frozen verification plan rendered
    into the report, clearly labeled as not executed by PEOS -- distinct
    from the executable steps list.
    """
    plan = VerificationPlan(
        (VerificationStep(name="python tests (pytest -q)", command=("pytest", "-q"), cwd_relative=".", required_input="tests"),),
        ("Manual run of the dev server exercising AC-001 through AC-014 visually.",),
    )
    result = RunResult(task="t", outcome="APPROVED", spec=SPEC, verification_plan=plan)
    report = build_report(result, REPO_ROOT)
    assert "python tests (pytest -q)" in report
    assert "not executed by PEOS" in report
    assert "Manual run of the dev server exercising AC-001 through AC-014 visually." in report


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


def test_report_never_surfaces_a_secret_from_raw_claude_or_codex_output():
    """SPEC-003 AC-10: a secret-shaped value sitting in raw stdout/stderr
    (the internal-only fields carried on ClaudeRunResult/CodexReviewResult
    for debugging -- never meant for the human-facing report) must not
    appear in build_report()'s rendered output, even though `.error` is
    reported.
    """
    secret = "sk-liveAbCdEfGhIjKlMnOpQrSt"
    claude_run = ClaudeRunResult(
        returncode=1, stdout=f"leaked secret {secret} in stdout", stderr=f"leaked secret {secret} in stderr",
        status=None, gate_category=None, gate_reason=None, summary="",
        ok=False, error="[authentication] [REDACTED]",
    )
    review = CodexReviewResult(
        returncode=1, verdict=None, summary="", findings=(), acceptance_criteria=(),
        raw_stdout=f"leaked secret {secret} in raw_stdout", raw_stderr=f"leaked secret {secret} in raw_stderr",
        ok=False, error="[authentication] [REDACTED]",
    )
    result = RunResult(
        task="t", outcome="FAILED", spec=SPEC, gate_reason="auth preflight failed",
        claude_runs=(claude_run,), review_results=(review,),
    )
    report = build_report(result, REPO_ROOT)
    assert secret not in report


def test_report_formatting_functions_do_not_read_raw_stdout_or_stderr_fields():
    """SPEC-003 AC-11: build_report()'s rendered output must be identical
    whether or not a result object's raw stdout/stderr fields are
    populated -- proving `_format_claude_runs`/`_format_reviews` never
    read them, locking in what is already true today as a tested
    invariant rather than an incidental fact.
    """
    def make_result(claude_stdout, claude_stderr, codex_raw_stdout, codex_raw_stderr):
        claude_run = ClaudeRunResult(
            returncode=0, stdout=claude_stdout, stderr=claude_stderr, status="COMPLETED",
            gate_category=None, gate_reason=None, summary="did the thing", ok=True,
        )
        review = CodexReviewResult(
            returncode=0, verdict="APPROVE", summary="ok", findings=(), acceptance_criteria=(),
            raw_stdout=codex_raw_stdout, raw_stderr=codex_raw_stderr, ok=True,
        )
        return RunResult(
            task="t", outcome="APPROVED", spec=SPEC,
            claude_runs=(claude_run,), review_results=(review,),
        )

    populated = build_report(make_result("some stdout", "some stderr", "raw out", "raw err"), REPO_ROOT)
    empty = build_report(make_result("", "", "", ""), REPO_ROOT)
    assert populated == empty


def test_report_never_surfaces_a_secret_from_claude_gate_reason_or_codex_finding_end_to_end():
    """Focused Codex review remediation, Finding 3 (MAJOR), end to end:
    a secret-shaped string embedded in Claude's own structured
    `gate_reason` (the HUMAN_GATE path specifically) or Codex's own
    finding `description` must not survive into `build_report()`'s
    rendered output. Unlike `test_report_never_surfaces_a_secret_from_
    raw_claude_or_codex_output` above (which hand-builds already-clean
    dataclasses to prove report.py trusts them), this test drives the
    secret through the real `run_claude`/`run_codex_review` structured-
    result construction and peos/workflow.py's own gate-reason string
    shape, proving the sanitization actually happens where the field is
    extracted -- not merely assumed by report.py.
    """
    secret = "sk-liveAbCdEfGhIjKlMnOpQrSt"

    claude_payload = json.dumps({
        "is_error": False, "result": "stopped",
        "structured_output": {
            "status": "HUMAN_GATE", "gate_category": "architecture",
            "gate_reason": f"found hardcoded key={secret} in config, needs a human decision",
            "summary": "stopped",
        },
    })

    def claude_runner(command, **kwargs):
        return subprocess.CompletedProcess(args=["claude"], returncode=0, stdout=claude_payload, stderr="")

    claude_run = run_claude("task", Path("."), runner=claude_runner)
    assert claude_run.human_gate
    assert secret not in claude_run.gate_reason

    def codex_runner(command, **kwargs):
        last_message_path = Path(command[command.index("--output-last-message") + 1])
        last_message_path.write_text(json.dumps({
            "verdict": "CHANGES_REQUIRED",
            "summary": "issues found",
            "findings": [{
                "severity": "major", "category": "implementation_defect",
                "description": f"hardcoded credential key={secret} found in source",
                "requires_human_decision": False,
            }],
            "acceptance_criteria": None,
            "reviewer_overrules_dispute": None,
            "addressed_dispute_references": None,
            "historical_finding_dispositions": None,
        }), encoding="utf-8")
        return subprocess.CompletedProcess(args=["codex"], returncode=0, stdout="", stderr="")

    review = run_codex_review("prompt", Path("."), runner=codex_runner)
    assert not review.approved
    assert secret not in review.findings[0].description

    # peos/workflow.py's own gate() message shape for Claude's HUMAN_GATE
    # (see _run_workflow's "Claude escalated during implementation"
    # f-string) and for a Codex human-owned finding, both reproduced here
    # verbatim rather than assumed.
    result = RunResult(
        task="t", outcome="HUMAN_GATE", spec=SPEC,
        gate_id="5",
        gate_reason=f"Claude escalated during implementation [architecture]: {claude_run.gate_reason}",
        claude_runs=(claude_run,),
        review_results=(review,),
    )
    report = build_report(result, REPO_ROOT)
    assert secret not in report
    assert "[REDACTED]" in report


def test_report_never_surfaces_a_secret_from_an_acceptance_criterion_id_end_to_end():
    """Focused closure review, Finding 3 (remaining disclosure path):
    Codex acceptance-criterion `id` values are schema-valid, arbitrary,
    nonempty strings and were previously rendered verbatim by
    `_format_reviews` (peos/report.py), unlike `note`/`description`/
    `summary`, which Finding 3's original remediation already covered.
    Reproduced directly: a schema-valid APPROVE payload whose AC `id`
    contains an sk-prefixed synthetic credential must not leak that
    credential into `build_report()`'s output, while the internal `id`
    (machine semantics -- matching/reconciliation/validation) stays
    byte-for-byte unchanged on the `CodexReviewResult` itself.
    """
    secret = "sk-liveAbCdEfGhIjKlMnOpQrSt"

    def codex_runner(command, **kwargs):
        last_message_path = Path(command[command.index("--output-last-message") + 1])
        last_message_path.write_text(json.dumps({
            "verdict": "APPROVE",
            "summary": "ok",
            "findings": [],
            "acceptance_criteria": [
                {"id": f"AC-001-{secret}", "met": True, "note": "covered"},
            ],
            "reviewer_overrules_dispute": None,
            "addressed_dispute_references": None,
            "historical_finding_dispositions": None,
        }), encoding="utf-8")
        return subprocess.CompletedProcess(args=["codex"], returncode=0, stdout="", stderr="")

    review = run_codex_review("prompt", Path("."), runner=codex_runner)
    assert review.approved

    # Internal `id` is exactly what Codex returned -- unredacted, for
    # machine semantics -- even though it contains the synthetic secret.
    assert review.acceptance_criteria[0]["id"] == f"AC-001-{secret}"

    result = RunResult(
        task="t", outcome="APPROVED", spec=SPEC,
        review_results=(review,),
    )
    report = build_report(result, REPO_ROOT)
    assert secret not in report
    assert "[REDACTED]" in report


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
