"""Integration tests for SPEC-006's wiring into peos/workflow.py: the
Runtime Verification phase at cycle 0 and every remediation cycle, the
Human Gate #12 routing, and the Round Packet/Codex-contract routing of
runtime evidence. Mocked-workflow-routing style, matching
tests/test_peos_workflow.py's own stated scope (SPEC-001 remediation
Finding 9) -- Claude, Codex, the workspace factory, the verifier, AND
now the runtime verifier are all injected fakes.
"""

import subprocess
from pathlib import Path

from peos.codex_agent import CodexReviewResult
from peos.round_packet import RuntimeEvidenceRef
from peos.runtime_evidence import RuntimeEvidence, build_runtime_check
from peos.runtime_verification import RuntimeVerificationOutcome
from peos.sandbox import CLAUDE_AUTH_ENV_VAR, CODEX_AUTH_FILENAME, CODEX_AUTH_HOME_ENV_VAR, IsolatedWorkspace
from peos.spec import SpecCandidate, SpecResolution
from peos.verify import CommandResult, VerificationReport
from peos.workflow import run_workflow

from tests._peos_fixtures import make_minimal_repo


def _valid_environ(tmp_path: Path) -> dict:
    environ = {"PATH": "/usr/bin", CLAUDE_AUTH_ENV_VAR: "fake-test-token"}
    auth_dir = tmp_path / "codex-auth-home"
    auth_dir.mkdir(exist_ok=True)
    (auth_dir / CODEX_AUTH_FILENAME).write_text('{"fake": "auth"}', encoding="utf-8")
    environ[CODEX_AUTH_HOME_ENV_VAR] = str(auth_dir)
    return environ


def _fake_workspace_factory(repo_root: Path, run_id: str) -> IsolatedWorkspace:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo_root), capture_output=True, text=True).stdout.strip()
    return IsolatedWorkspace(path=repo_root, home_dir=repo_root, baseline_commit=head)


def _spec_with_runtime_declaration(repo_root: Path, runtime_line: str) -> SpecCandidate:
    spec_path = repo_root / "docs" / "specifications" / "SPEC-RV-x.md"
    spec_path.write_text(
        "# SPEC-RV -- Runtime Verification Test\n\n**Status:** Approved\n\n"
        "## Acceptance Criteria\n\n- [ ] **AC-012** no overflow\n\n"
        "## Verification Requirements\n\n### Runtime Verification\n\n"
        f"    {runtime_line}\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=str(repo_root), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "add runtime spec"],
        cwd=str(repo_root), check=True, capture_output=True,
    )
    return SpecCandidate(path=spec_path, title="RV", status="Approved")


def _resolver_returns(spec):
    def resolver(task, specs_dir, explicit_spec):
        return SpecResolution(spec=spec)
    return resolver


def _ok_claude():
    from peos.claude_agent import ClaudeRunResult
    return ClaudeRunResult(
        returncode=0, stdout="", stderr="", status="COMPLETED",
        gate_category=None, gate_reason=None, summary="done", ok=True,
    )


def _pass_verification():
    return VerificationReport((CommandResult(name="pytest", command=(), cwd=".", returncode=0, stdout="", stderr=""),))


def _passing_runtime_outcome(workspace_path: Path, cycle_label: str, ac_status: str = "PASS", repo_root: Path | None = None) -> RuntimeVerificationOutcome:
    """Builds real, on-disk evidence (via the real `persist_evidence`/
    `stage_evidence_into_workspace`) rather than a fabricated
    `PersistedEvidence` pointing at a non-existent file -- required since
    `peos/workflow.py` now re-verifies staged evidence identity for real
    (Codex implementation review Finding 4) before every consuming
    invocation; a fake that doesn't actually write the staged file
    correctly fails that check.
    """
    from peos.runtime_evidence import persist_evidence, stage_evidence_into_workspace

    check_status = "PASS" if ac_status == "PASS" else "FAIL"
    check, screenshot = build_runtime_check(
        check_id=f"runtime.{cycle_label}.0.viewport_overflow", kind="viewport_overflow",
        related_ac_ids=("AC-012",), parameters={"viewport": "mobile"}, status=check_status,
        action_performed="measured", observation="x", measurements={}, screenshot_bytes=None,
    )
    evidence = RuntimeEvidence(
        run_id="r", cycle_label=cycle_label, workspace_snapshot_identity="fp", baseline_commit="bc",
        catalog_version="1.0.0", playwright_version="1.49.1", browser_version="fake",
        browser_environment={}, service_readiness=(), checks=(check,), execution_integrity_passed=True,
    )
    repo_root = repo_root if repo_root is not None else workspace_path
    persisted = persist_evidence(repo_root, "r", evidence, {})
    staged_dir = stage_evidence_into_workspace(workspace_path, persisted, cycle_label)
    return RuntimeVerificationOutcome(
        ran=True, execution_integrity_passed=True, failure_reason=None,
        evidence=evidence, persisted=persisted, staged_dir=staged_dir,
    )


def test_ac002_runtime_verification_phase_runs_at_cycle0_before_codex(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    spec = _spec_with_runtime_declaration(repo_root, "runtime: viewport_overflow viewport=mobile ac=AC-012")

    runtime_calls = []

    def fake_runtime_verifier(runtime_plan, **kwargs):
        runtime_calls.append(kwargs["cycle_label"])
        return _passing_runtime_outcome(kwargs["workspace"].path, kwargs["cycle_label"], repo_root=kwargs["repo_root"])

    def fake_codex_runner(prompt, cwd, env=None, **kwargs):
        return CodexReviewResult(
            returncode=0, verdict="APPROVE", summary="ok", findings=(),
            acceptance_criteria=[{"id": "AC-012", "met": True, "note": "ok", "display_id": "AC-012"}],
            raw_stdout="", raw_stderr="", ok=True,
        )

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(spec),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=fake_codex_runner,
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
        runtime_verifier=fake_runtime_verifier,
    )

    assert result.outcome == "APPROVED", result.gate_reason
    assert runtime_calls == ["cycle 0"]
    assert any("Runtime verification" in p.phase for p in result.phases)
    assert len(result.runtime_verification_history) == 1


def test_ac003_runtime_verification_phase_also_runs_on_remediation_cycle(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    spec = _spec_with_runtime_declaration(repo_root, "runtime: viewport_overflow viewport=mobile ac=AC-012")

    runtime_calls = []
    codex_call_count = {"n": 0}

    def fake_runtime_verifier(runtime_plan, **kwargs):
        runtime_calls.append(kwargs["cycle_label"])
        return _passing_runtime_outcome(kwargs["workspace"].path, kwargs["cycle_label"], repo_root=kwargs["repo_root"])

    def fake_codex_runner(prompt, cwd, env=None, **kwargs):
        codex_call_count["n"] += 1
        if codex_call_count["n"] == 1:
            from peos.codex_agent import Finding
            return CodexReviewResult(
                returncode=0, verdict="CHANGES_REQUIRED", summary="issues", findings=(
                    Finding(severity="major", category="missing_test", description="x", requires_human_decision=False),
                ), acceptance_criteria=(), raw_stdout="", raw_stderr="", ok=True,
            )
        from peos.codex_agent import HistoricalFindingDisposition
        from peos.findings_register import RESOLVED
        return CodexReviewResult(
            returncode=0, verdict="APPROVE", summary="ok", findings=(),
            acceptance_criteria=[{"id": "AC-012", "met": True, "note": "ok", "display_id": "AC-012"}],
            raw_stdout="", raw_stderr="", ok=True,
            historical_finding_dispositions=(
                HistoricalFindingDisposition(reference="0.1", disposition=RESOLVED, note="fixed"),
            ),
        )

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(spec),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=fake_codex_runner,
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
        max_cycles=1,
        runtime_verifier=fake_runtime_verifier,
    )

    assert result.outcome == "APPROVED", result.gate_reason
    assert runtime_calls == ["cycle 0", "remediation cycle 1"]
    assert len(result.runtime_verification_history) == 2


def test_ac005_runtime_verification_execution_integrity_failure_fails_the_run(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    spec = _spec_with_runtime_declaration(repo_root, "runtime: viewport_overflow viewport=mobile ac=AC-012")

    def fake_runtime_verifier(runtime_plan, **kwargs):
        return RuntimeVerificationOutcome(
            ran=True, execution_integrity_passed=False, failure_reason="backend never became ready",
        )

    codex_calls = []
    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(spec),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None, **kwargs: codex_calls.append(1),
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
        runtime_verifier=fake_runtime_verifier,
    )

    assert result.outcome == "FAILED"
    assert "backend never became ready" in result.gate_reason
    assert codex_calls == []  # never reaches Codex


def test_ac026_human_gate_12_for_unsupported_runtime_check_kind(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    spec = _spec_with_runtime_declaration(repo_root, "runtime: open_arbitrary_url ac=AC-012")

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(spec),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None, **kwargs: None,
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "HUMAN_GATE"
    assert result.gate_id == "12"
    assert "open_arbitrary_url" in result.gate_reason


def test_ac021_round_packet_routing_carries_runtime_evidence_to_codex(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    spec = _spec_with_runtime_declaration(repo_root, "runtime: viewport_overflow viewport=mobile ac=AC-012")

    def fake_runtime_verifier(runtime_plan, **kwargs):
        return _passing_runtime_outcome(kwargs["workspace"].path, kwargs["cycle_label"], repo_root=kwargs["repo_root"])

    captured_kwargs = {}

    def fake_codex_runner(prompt, cwd, env=None, **kwargs):
        captured_kwargs.update(kwargs)
        captured_kwargs["prompt"] = prompt
        return CodexReviewResult(
            returncode=0, verdict="APPROVE", summary="ok", findings=(),
            acceptance_criteria=[{"id": "AC-012", "met": True, "note": "ok", "display_id": "AC-012"}],
            raw_stdout="", raw_stderr="", ok=True,
        )

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(spec),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=fake_codex_runner,
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
        runtime_verifier=fake_runtime_verifier,
    )

    assert result.outcome == "APPROVED"
    # AC-022's routing half: runtime_evidenced_ac_status threaded to codex_runner
    assert captured_kwargs.get("runtime_evidenced_ac_status") == {"AC-012": "PASS"}
    # AC-021: the Round Packet's rendered prompt text carries the staged evidence reference
    assert "runtime-evidence" in captured_kwargs["prompt"]
    assert "viewport_overflow" in captured_kwargs["prompt"]


def test_ac043_spec005_style_dogfood_scenario_end_to_end(tmp_path):
    """SPEC-006 Section 17: page_load + viewport_overflow checks produce
    evidence, that evidence reaches the Codex call's routing, and a
    faked APPROVE with met=true for the viewport AC is only reachable
    when the fake runtime_verifier reports that AC as PASS."""
    repo_root = make_minimal_repo(tmp_path)
    spec_path = repo_root / "docs" / "specifications" / "SPEC-RV-dogfood.md"
    spec_path.write_text(
        "# SPEC-RV-dogfood\n\n**Status:** Approved\n\n"
        "## Acceptance Criteria\n\n- [ ] **AC-001** page load\n- [ ] **AC-012** no overflow\n\n"
        "## Verification Requirements\n\n### Runtime Verification\n\n"
        '    runtime: page_load path=/ landmarks="EventBanner,TelemetryChart" ac=AC-001\n'
        "    runtime: viewport_overflow viewport=desktop ac=AC-012\n"
        "    runtime: viewport_overflow viewport=mobile ac=AC-012\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=str(repo_root), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "dogfood spec"],
        cwd=str(repo_root), check=True, capture_output=True,
    )
    spec = SpecCandidate(path=spec_path, title="RV-dogfood", status="Approved")

    def fake_runtime_verifier(runtime_plan, **kwargs):
        assert len(runtime_plan.declarations) == 3
        checks = []
        for decl in runtime_plan.declarations:
            check, _ = build_runtime_check(
                check_id=f"runtime.0.{decl.declaration_index}.{decl.kind}", kind=decl.kind,
                related_ac_ids=decl.related_ac_ids, parameters={}, status="PASS",
                action_performed="x", observation="x", measurements={}, screenshot_bytes=None,
            )
            checks.append(check)
        evidence = RuntimeEvidence(
            run_id="r", cycle_label=kwargs["cycle_label"], workspace_snapshot_identity="fp",
            baseline_commit="bc", catalog_version="1.0.0", playwright_version="1.49.1",
            browser_version="fake", browser_environment={}, service_readiness=(),
            checks=tuple(checks), execution_integrity_passed=True,
        )
        from peos.runtime_evidence import persist_evidence, stage_evidence_into_workspace
        persisted = persist_evidence(kwargs["repo_root"], "r", evidence, {})
        staged_dir = stage_evidence_into_workspace(kwargs["workspace"].path, persisted, kwargs["cycle_label"])
        return RuntimeVerificationOutcome(
            ran=True, execution_integrity_passed=True, failure_reason=None,
            evidence=evidence, persisted=persisted, staged_dir=staged_dir,
        )

    def fake_codex_runner(prompt, cwd, env=None, **kwargs):
        rollup = kwargs.get("runtime_evidenced_ac_status", {})
        met_ac001 = rollup.get("AC-001") == "PASS"
        met_ac012 = rollup.get("AC-012") == "PASS"
        return CodexReviewResult(
            returncode=0, verdict="APPROVE", summary="ok", findings=(),
            acceptance_criteria=[
                {"id": "AC-001", "met": met_ac001, "note": "x", "display_id": "AC-001"},
                {"id": "AC-012", "met": met_ac012, "note": "x", "display_id": "AC-012"},
            ],
            raw_stdout="", raw_stderr="", ok=True,
        )

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(spec),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=fake_codex_runner,
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
        runtime_verifier=fake_runtime_verifier,
    )

    assert result.outcome == "APPROVED", result.gate_reason
