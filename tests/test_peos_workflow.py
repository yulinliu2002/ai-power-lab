"""Tests for PEOS orchestration (peos/workflow.py).

These are "mocked workflow-routing" tests (SPEC-001 remediation Finding
9): Claude, Codex, the workspace factory, and the verifier are all
injected fakes, so these tests exercise the phase sequence, human gates,
and bounded remediation cycle without ever shelling out to `claude`,
`codex`, or performing a real Git clone. Repository preflight and
governance-artifact hashing *do* run for real, against a tiny real Git
repository built by `tests/_peos_fixtures.make_minimal_repo`, because
those are the SPEC-001 Finding 7 behavior actually under test here.

Real Git cloning/reconciliation behavior is covered separately in
tests/test_peos_sandbox.py; real CLI contract behavior (actual `claude`/
`codex` invocations) is covered, opt-in only, in
tests/test_peos_real_cli_contract.py.
"""

import os
import subprocess
import sys
from pathlib import Path

from peos.claude_agent import ClaudeRunResult
from peos.codex_agent import CodexReviewResult, Finding
from peos.sandbox import CLAUDE_AUTH_ENV_VAR, CODEX_AUTH_HOME_ENV_VAR, CODEX_AUTH_FILENAME, IsolatedWorkspace
from peos.spec import SpecCandidate, SpecResolution
from peos.verify import CommandResult, VerificationReport
from peos.workflow import run_workflow

from tests._peos_fixtures import make_minimal_repo


def _valid_environ(tmp_path: Path, *, with_claude: bool = True, with_codex: bool = True) -> dict:
    """A fake orchestrator environment with both agents' authentication
    preconditions satisfied (SPEC-003) -- the default every pre-existing
    routing test in this file now passes, since none of them are testing
    the *absence* of a credential. Tests that specifically exercise a
    missing/unusable bridge (SPEC-003 AC-3/AC-5) pass `with_claude=False`
    or `with_codex=False` instead of building their own environ by hand.
    """
    environ = {"PATH": "/usr/bin"}
    if with_claude:
        environ[CLAUDE_AUTH_ENV_VAR] = "fake-test-token"
    if with_codex:
        auth_dir = tmp_path / "codex-auth-home"
        auth_dir.mkdir(exist_ok=True)
        (auth_dir / CODEX_AUTH_FILENAME).write_text('{"fake": "auth"}', encoding="utf-8")
        environ[CODEX_AUTH_HOME_ENV_VAR] = str(auth_dir)
    return environ


def _spec_for(repo_root: Path) -> SpecCandidate:
    return SpecCandidate(path=repo_root / "docs" / "specifications" / "SPEC-001-x.md", title="X", status="Approved")


def _fake_workspace_factory(repo_root: Path, run_id: str) -> IsolatedWorkspace:
    # Routing tests don't need a real isolated clone -- reuse repo_root
    # itself as the "workspace" so hashing/mutation-detection operate on
    # real files without the cost of a real `git clone` per test. The
    # baseline commit must be a real, current HEAD so peos.sandbox's
    # diff-based reconciliation (tested for real in test_peos_sandbox.py)
    # behaves sensibly if a routing test also exercises it.
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo_root), capture_output=True, text=True,
    ).stdout.strip()
    return IsolatedWorkspace(path=repo_root, home_dir=repo_root, baseline_commit=head)


def _ok_claude(summary="done"):
    return ClaudeRunResult(
        returncode=0, stdout="", stderr="", status="COMPLETED",
        gate_category=None, gate_reason=None, summary=summary, ok=True,
    )


def _human_gate_claude(category="architecture", reason="needs a new architecture decision"):
    return ClaudeRunResult(
        returncode=0, stdout="", stderr="", status="HUMAN_GATE",
        gate_category=category, gate_reason=reason, summary="stopped", ok=False, error=reason,
    )


def _failed_claude(error="boom"):
    return ClaudeRunResult(
        returncode=1, stdout="", stderr="", status="FAILED",
        gate_category=None, gate_reason=None, summary="", ok=False, error=error,
    )


def _pass_verification():
    return VerificationReport((CommandResult(name="pytest", command=(), cwd=".", returncode=0, stdout="", stderr=""),))


def _fail_verification():
    return VerificationReport((CommandResult(name="pytest", command=(), cwd=".", returncode=1, stdout="", stderr="e"),))


def _approve_review():
    return CodexReviewResult(
        returncode=0, verdict="APPROVE", summary="looks good", findings=(),
        acceptance_criteria=(), raw_stdout="", raw_stderr="", ok=True,
    )


def _changes_required_review(human_decision=False):
    findings = (
        Finding(severity="major", category="missing_test", description="add a test",
                requires_human_decision=human_decision),
    )
    return CodexReviewResult(
        returncode=0, verdict="CHANGES_REQUIRED", summary="issues found", findings=findings,
        acceptance_criteria=(), raw_stdout="", raw_stderr="", ok=True,
    )


def _uninterpretable_review():
    return CodexReviewResult(
        returncode=0, verdict=None, summary="", findings=(), acceptance_criteria=(),
        raw_stdout="garbage", raw_stderr="", ok=False, error="could not parse",
    )


def _resolver_returns(spec):
    def resolver(task, specs_dir, explicit_spec):
        return SpecResolution(spec=spec)
    return resolver


def _resolver_gates(reason):
    def resolver(task, specs_dir, explicit_spec):
        return SpecResolution(gate_reason=reason)
    return resolver


def test_happy_path_single_approve(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    claude_calls = []
    codex_calls = []

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: (claude_calls.append(prompt), _ok_claude())[1],
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: (codex_calls.append(prompt), _approve_review())[1],
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "APPROVED"
    assert result.remediation_performed is False
    assert len(claude_calls) == 1
    assert len(codex_calls) == 1
    assert result.verification_plan is not None
    assert result.reconciliation is not None


def test_preflight_failure_stops_before_intake(tmp_path):
    # Not even a Git repository at all -- preflight must fail closed
    # before resolving a spec or invoking any agent.
    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()
    spec_calls = []

    def resolver(task, specs_dir, explicit_spec):
        spec_calls.append(1)
        return SpecResolution(gate_reason="unused")

    result = run_workflow(
        "task", not_a_repo,
        log=lambda msg: None,
        spec_resolver=resolver,
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: _approve_review(),
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "FAILED"
    assert "preflight" in result.gate_reason.lower()
    assert spec_calls == []


def test_preflight_failure_on_missing_governance_file(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    (repo_root / "AGENTS.md").unlink()

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: _approve_review(),
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "FAILED"
    assert "AGENTS.md" in result.gate_reason


def test_interpreter_preflight_failure_stops_before_claude_or_workspace(tmp_path, monkeypatch):
    """PEOS infrastructure maintenance (dogfooding finding): if the
    interpreter running PEOS cannot satisfy the frozen plan's pytest
    step, that must fail closed immediately, before Intake resolves a
    spec, before Claude's authentication preflight, before the isolated
    workspace is created, and before Claude is invoked at all -- not
    deep inside a later verification CommandResult.
    """
    import peos.workflow as workflow_module
    from peos.preflight import InterpreterPreflightResult

    monkeypatch.setattr(
        workflow_module,
        "check_verification_interpreter",
        lambda: InterpreterPreflightResult(
            ok=False,
            reason=f"The interpreter currently running PEOS ({sys.executable}) does not have pytest installed.",
        ),
    )

    repo_root = make_minimal_repo(tmp_path)
    spec_calls = []
    claude_calls = []
    workspace_calls = []

    def resolver(task, specs_dir, explicit_spec):
        spec_calls.append(1)
        return SpecResolution(spec=_spec_for(repo_root))

    def workspace_factory(repo_root_arg, run_id):
        workspace_calls.append(1)
        return _fake_workspace_factory(repo_root_arg, run_id)

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=resolver,
        claude_runner=lambda prompt, cwd, env=None: (claude_calls.append(1), _ok_claude())[1],
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: _approve_review(),
        workspace_factory=workspace_factory,
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "FAILED"
    assert "interpreter preflight" in result.gate_reason.lower()
    assert sys.executable in result.gate_reason
    assert "pytest" in result.gate_reason.lower()
    # Fails before Intake even resolves the governing spec.
    assert spec_calls == []
    assert claude_calls == []
    assert workspace_calls == []
    assert result.workspace_path is None


def test_interpreter_preflight_passes_normally_when_pytest_importable(tmp_path):
    """The default, real `check_verification_interpreter` (no injection)
    must not block a normal run on an interpreter that does have pytest
    -- the interpreter actually running this test suite always does.
    """
    repo_root = make_minimal_repo(tmp_path)
    claude_calls = []

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: (claude_calls.append(1), _ok_claude())[1],
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: _approve_review(),
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "APPROVED"
    assert claude_calls == [1]


def test_intake_gate_when_no_spec_found(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    claude_calls = []

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_gates("No approved specification was found"),
        claude_runner=lambda prompt, cwd, env=None: (claude_calls.append(prompt), _ok_claude())[1],
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: _approve_review(),
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "HUMAN_GATE"
    assert result.gate_id == "1"
    assert claude_calls == []  # never invoked -- stopped at Intake


def test_intake_gate_id_for_ambiguous_match(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_gates("Specification identification is ambiguous: ..."),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: _approve_review(),
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )
    assert result.outcome == "HUMAN_GATE"
    assert result.gate_id == "2"


def test_claude_implementation_failure_stops_before_verification(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    verifier_calls = []

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: _failed_claude("crashed"),
        verifier=lambda workspace, repo_root, plan: (verifier_calls.append(1), _pass_verification())[1],
        codex_runner=lambda prompt, cwd, env=None: _approve_review(),
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "FAILED"
    assert verifier_calls == []


def test_claude_human_gate_during_implementation_maps_gate_category(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    verifier_calls = []

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: _human_gate_claude(category="physics", reason="would change E=1/2 C V^2 assumptions"),
        verifier=lambda workspace, repo_root, plan: (verifier_calls.append(1), _pass_verification())[1],
        codex_runner=lambda prompt, cwd, env=None: _approve_review(),
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "HUMAN_GATE"
    assert result.gate_id == "3"  # physics
    assert verifier_calls == []  # stopped before verification/review entirely


def test_claude_human_gate_unmapped_category_falls_back_to_gate_6(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: _human_gate_claude(category="other", reason="unclear"),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: _approve_review(),
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )
    assert result.outcome == "HUMAN_GATE"
    assert result.gate_id == "6"


def test_verification_failure_stops_before_review(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    codex_calls = []

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _fail_verification(),
        codex_runner=lambda prompt, cwd, env=None: (codex_calls.append(prompt), _approve_review())[1],
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "FAILED"
    assert codex_calls == []
    assert "verification failed" in result.gate_reason.lower()


def test_codex_uninterpretable_output_fails_closed(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: _uninterpretable_review(),
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )
    assert result.outcome == "FAILED"


def test_codex_mutating_repo_root_fails_closed(tmp_path):
    repo_root = make_minimal_repo(tmp_path)

    def sneaky_codex_runner(prompt, cwd, env=None):
        # Simulate a reviewer that somehow wrote to the authoritative
        # repository despite the read-only boundary.
        (repo_root / "sneaky.txt").write_text("should not be here\n", encoding="utf-8")
        return _approve_review()

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=sneaky_codex_runner,
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )
    assert result.outcome == "FAILED"
    assert "read-only reviewer boundary" in result.gate_reason


def test_human_owned_finding_gates_without_remediation(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    claude_calls = []

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: (claude_calls.append(prompt), _ok_claude())[1],
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: _changes_required_review(human_decision=True),
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "HUMAN_GATE"
    assert result.gate_id == "6"
    assert result.remediation_performed is False
    assert len(claude_calls) == 1  # remediation never attempted


def test_remediation_cycle_then_approve(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    claude_calls = []
    codex_calls = []
    review_sequence = [_changes_required_review(human_decision=False), _approve_review()]

    def codex_runner(prompt, cwd, env=None):
        codex_calls.append(prompt)
        return review_sequence[len(codex_calls) - 1]

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: (claude_calls.append(prompt), _ok_claude())[1],
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=codex_runner,
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "APPROVED"
    assert result.remediation_performed is True
    assert len(claude_calls) == 2  # implementation + exactly one remediation
    assert len(codex_calls) == 2  # review + re-review


def test_bounded_remediation_still_changes_required_gates(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    claude_calls = []
    codex_calls = []

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: (claude_calls.append(prompt), _ok_claude())[1],
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: (codex_calls.append(prompt), _changes_required_review())[1],
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "HUMAN_GATE"
    assert result.gate_id == "8"
    assert result.remediation_performed is True
    # exactly one remediation cycle -- never a third Claude call or third review
    assert len(claude_calls) == 2
    assert len(codex_calls) == 2


def test_remediation_failure_stops_before_rereview(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    codex_calls = []
    claude_sequence = [_ok_claude(), _failed_claude("remediation crashed")]

    def claude_runner(prompt, cwd, env=None):
        return claude_sequence[len(codex_calls)]

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=claude_runner,
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: (codex_calls.append(prompt), _changes_required_review())[1],
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "FAILED"
    assert len(codex_calls) == 1  # re-review never reached


def test_remediation_human_gate_maps_gate_category(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    claude_sequence = [_ok_claude(), _human_gate_claude(category="control", reason="would change PI gains")]
    calls = []

    def claude_runner(prompt, cwd, env=None):
        result = claude_sequence[len(calls)]
        calls.append(1)
        return result

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=claude_runner,
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: _changes_required_review(),
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "HUMAN_GATE"
    assert result.gate_id == "4"  # control/protection


def test_governance_mutation_during_implementation_fails_closed(tmp_path):
    repo_root = make_minimal_repo(tmp_path)

    def mutating_claude_runner(prompt, cwd, env=None):
        (Path(cwd) / "CLAUDE.md").write_text("mutated by an agent\n", encoding="utf-8")
        return _ok_claude()

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=mutating_claude_runner,
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: _approve_review(),
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "FAILED"
    assert "CLAUDE.md" in result.gate_reason
    assert result.blocked_governance_mutation == ("CLAUDE.md",)
    # This fake workspace_factory reuses repo_root as the "workspace" path
    # (for speed), so there is no real copy-back to assert on here; that
    # the reconciliation step never copies a governance-artifact change
    # onto a *separate* authoritative repo_root is verified for real
    # (distinct clone directory) in test_peos_sandbox.py.


def test_approved_run_spec_path_in_prompts_is_workspace_relative_not_absolute(tmp_path):
    """Finding 6: Claude/Codex run with cwd=workspace.path (Claude also
    --restricted, confined to that cwd), so the prompt must reference the
    spec by a path relative to the workspace, not the authoritative
    repo's absolute path -- which, with the fake workspace factory that
    reuses repo_root as "the workspace" for speed, happens to be the same
    string either way *in this specific test fixture*, so this is checked
    with a workspace factory that genuinely uses a different directory.
    """
    repo_root = make_minimal_repo(tmp_path)
    prompts_seen = []

    def real_ish_workspace_factory(repo_root: Path, run_id: str) -> IsolatedWorkspace:
        # A distinct directory from repo_root, with the spec file for
        # real present at the identical relative path (as a real `git
        # clone`-backed workspace would have it) -- enough to exercise
        # ensure_spec_in_workspace's "already there, same relative path"
        # branch without the cost of a real clone.
        workspace_dir = tmp_path / f"fake-workspace-{run_id}"
        (workspace_dir / "docs" / "specifications").mkdir(parents=True)
        spec_src = repo_root / "docs" / "specifications" / "SPEC-001-x.md"
        (workspace_dir / "docs" / "specifications" / "SPEC-001-x.md").write_text(
            spec_src.read_text(encoding="utf-8"), encoding="utf-8",
        )
        for governance_file in ("CLAUDE.md", "AGENTS.md", "ENGINEERING.md"):
            (workspace_dir / governance_file).write_text(
                (repo_root / governance_file).read_text(encoding="utf-8"), encoding="utf-8",
            )
        return IsolatedWorkspace(path=workspace_dir, home_dir=workspace_dir, baseline_commit="deadbeef")

    def claude_runner(prompt, cwd, env=None):
        prompts_seen.append(prompt)
        return _ok_claude()

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=claude_runner,
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: _approve_review(),
        workspace_factory=real_ish_workspace_factory,
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "APPROVED"
    assert len(prompts_seen) == 1
    assert str(repo_root) not in prompts_seen[0]
    assert "docs/specifications/SPEC-001-x.md" in prompts_seen[0]


def test_failed_outcome_still_carries_the_resolved_spec(tmp_path):
    """Finding 9: a FAILED/HUMAN_GATE outcome reached after Phase 1 must
    still carry the resolved governing specification in the report-level
    result -- exercised via the real `_run_workflow` control flow (a
    verification failure), not by constructing a RunResult by hand.
    """
    repo_root = make_minimal_repo(tmp_path)
    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _fail_verification(),
        codex_runner=lambda prompt, cwd, env=None: _approve_review(),
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )
    assert result.outcome == "FAILED"
    assert result.spec is not None
    assert result.spec.path == _spec_for(repo_root).path


def test_human_gate_outcome_still_carries_the_resolved_spec(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: (_ok_claude()),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: _changes_required_review(human_decision=True),
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )
    assert result.outcome == "HUMAN_GATE"
    assert result.spec is not None


def test_unhandled_exception_after_implementation_still_carries_accumulated_evidence(tmp_path):
    """Latest Codex review, Finding 5, directly reproduced: an unexpected
    exception raised after Phase 1 (spec resolved) and Phase 2
    (implementation completed, verification report recorded) must still
    produce a FAILED RunResult carrying `spec`, `claude_runs`, and
    `verification_reports` already accumulated at the point of failure --
    not a bare, context-free RunResult, which is what a bug in the
    previous version of this function produced because the broad
    exception handler lived in the outer `run_workflow()` wrapper, outside
    the closures that held that state.
    """
    repo_root = make_minimal_repo(tmp_path)

    def exploding_codex_runner(prompt, cwd, env=None):
        raise RuntimeError("simulated unexpected failure deep inside a Codex call")

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=exploding_codex_runner,
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )
    assert result.outcome == "FAILED"
    assert "simulated unexpected failure" in result.gate_reason
    # The evidence accumulated before the exception must survive it.
    assert result.spec is not None
    assert result.spec.path == _spec_for(repo_root).path
    assert len(result.claude_runs) == 1
    assert result.claude_runs[0].ok
    assert len(result.verification_reports) == 1
    assert result.verification_reports[0].passed


def test_governance_mutation_detected_after_verification_not_just_after_claude(tmp_path):
    """Finding 4 (second pass): governance integrity is re-checked after
    deterministic verification too, before review/approval -- not only
    right after each Claude phase.
    """
    repo_root = make_minimal_repo(tmp_path)

    def mutating_verifier(workspace, repo_root, plan):
        (Path(workspace.path) / "CLAUDE.md").write_text("mutated during verification\n", encoding="utf-8")
        return _pass_verification()

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=mutating_verifier,
        codex_runner=lambda prompt, cwd, env=None: _approve_review(),
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )
    assert result.outcome == "FAILED"
    assert "CLAUDE.md" in result.gate_reason
    assert result.blocked_governance_mutation == ("CLAUDE.md",)


def test_codex_mutating_the_isolated_workspace_itself_fails_closed(tmp_path):
    """Finding 3 (second pass): Codex must not modify the isolated
    workspace either, not only the authoritative repository -- a reviewer
    that edits a file inside the workspace it was invoked against (while
    leaving repo_root itself untouched) must still fail closed.
    """
    repo_root = make_minimal_repo(tmp_path)

    def sneaky_codex_runner(prompt, cwd, env=None):
        (Path(cwd) / "sneaky_in_workspace.txt").write_text("should not be here\n", encoding="utf-8")
        return _approve_review()

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=sneaky_codex_runner,
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )
    assert result.outcome == "FAILED"
    assert "read-only reviewer boundary" in result.gate_reason


def test_reconciliation_failure_never_produces_approved(tmp_path, monkeypatch):
    """Finding 8, BLOCKER-adjacent MAJOR: reconciliation failing after
    Codex approves must never surface as outcome=APPROVED -- the
    authoritative working tree would not actually reflect what was
    approved.
    """
    import peos.workflow as workflow_module

    repo_root = make_minimal_repo(tmp_path)

    def exploding_reconcile(workspace, repo_root, protected_relative_paths=frozenset()):
        raise RuntimeError("disk full, could not copy workspace changes back")

    monkeypatch.setattr(workflow_module, "reconcile_workspace_to_repo", exploding_reconcile)

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: _approve_review(),
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "FAILED"
    assert result.reconciliation_error is not None
    assert "disk full" in result.reconciliation_error
    assert "Codex approved" in result.gate_reason


def test_reconciliation_failure_during_a_gate_is_reported_but_keeps_the_gate_outcome(tmp_path, monkeypatch):
    """A reconciliation failure while stopping for an unrelated reason
    (e.g. a human gate) must be surfaced (reconciliation_error set) but
    must not itself change that outcome -- only approve() has the "must
    never be APPROVED" constraint; a gate/fail outcome is already not an
    approval.
    """
    import peos.workflow as workflow_module

    repo_root = make_minimal_repo(tmp_path)

    def exploding_reconcile(workspace, repo_root, protected_relative_paths=frozenset()):
        raise RuntimeError("copy-back exploded")

    monkeypatch.setattr(workflow_module, "reconcile_workspace_to_repo", exploding_reconcile)

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: _changes_required_review(human_decision=True),
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "HUMAN_GATE"
    assert result.reconciliation_error is not None


def test_unhandled_exception_is_caught_and_reported_as_failed(tmp_path):
    repo_root = make_minimal_repo(tmp_path)

    def exploding_claude_runner(prompt, cwd, env=None):
        raise RuntimeError("boom, unexpected bug")

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=exploding_claude_runner,
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: _approve_review(),
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "FAILED"
    assert "boom" in result.gate_reason


# --- SPEC-003: per-agent authentication preflight -----------------------

def test_claude_auth_preflight_failure_stops_before_workspace_creation(tmp_path):
    """AC-3: a missing Claude credential fails closed before the isolated
    workspace is even created, and before claude_runner is ever called.
    """
    repo_root = make_minimal_repo(tmp_path)
    workspace_calls = []
    claude_calls = []

    def tracking_workspace_factory(repo_root, run_id):
        workspace_calls.append(1)
        return _fake_workspace_factory(repo_root, run_id)

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: (claude_calls.append(prompt), _ok_claude())[1],
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: _approve_review(),
        workspace_factory=tracking_workspace_factory,
        environ=_valid_environ(tmp_path, with_claude=False),
    )

    assert result.outcome == "FAILED"
    assert CLAUDE_AUTH_ENV_VAR in result.gate_reason
    assert workspace_calls == []
    assert claude_calls == []


def test_codex_auth_preflight_failure_stops_before_codex_call_but_after_claude_phase(tmp_path):
    """AC-5a: Claude's phase is never blocked or pre-checked against
    Codex's credential state -- a run with a valid Claude credential but
    a missing Codex one must still complete implementation and local
    verification before failing closed at the Codex phase.
    """
    repo_root = make_minimal_repo(tmp_path)
    claude_calls = []
    verifier_calls = []
    codex_calls = []

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: (claude_calls.append(prompt), _ok_claude())[1],
        verifier=lambda workspace, repo_root, plan: (verifier_calls.append(1), _pass_verification())[1],
        codex_runner=lambda prompt, cwd, env=None: (codex_calls.append(prompt), _approve_review())[1],
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path, with_codex=False),
    )

    assert result.outcome == "FAILED"
    assert CODEX_AUTH_HOME_ENV_VAR in result.gate_reason
    assert len(claude_calls) == 1  # Claude's phase was allowed to run
    assert len(verifier_calls) == 1  # local verification was allowed to run
    assert codex_calls == []  # Codex was never actually invoked


def test_codex_auth_preflight_is_not_redundantly_rechecked_on_rereview(tmp_path, monkeypatch):
    """AC-5b: once Codex's precondition has passed once in a run, it is
    not re-checked before the re-review call, even though a bounded
    remediation cycle invokes Codex a second time.
    """
    import peos.workflow as workflow_module

    repo_root = make_minimal_repo(tmp_path)
    preflight_calls = []
    real_check = workflow_module.check_codex_auth_preflight

    def counting_check(environ):
        preflight_calls.append(1)
        return real_check(environ)

    monkeypatch.setattr(workflow_module, "check_codex_auth_preflight", counting_check)

    claude_calls = []
    codex_calls = []
    review_sequence = [_changes_required_review(human_decision=False), _approve_review()]

    def codex_runner(prompt, cwd, env=None):
        codex_calls.append(prompt)
        return review_sequence[len(codex_calls) - 1]

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: (claude_calls.append(prompt), _ok_claude())[1],
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=codex_runner,
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "APPROVED"
    assert len(codex_calls) == 2  # review + re-review
    assert len(preflight_calls) == 1  # but the preflight check ran only once


def test_claude_env_carries_the_token_and_never_codex_home(tmp_path):
    """AC-2/AC-4 at the workflow wiring level."""
    repo_root = make_minimal_repo(tmp_path)
    captured_envs = []

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: (captured_envs.append(env), _ok_claude())[1],
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: _approve_review(),
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "APPROVED"
    assert len(captured_envs) == 1
    assert captured_envs[0][CLAUDE_AUTH_ENV_VAR] == "fake-test-token"
    assert "CODEX_HOME" not in captured_envs[0]


def test_codex_env_carries_codex_home_and_never_the_claude_token(tmp_path):
    """AC-4/AC-6 at the workflow wiring level: Codex's subprocess
    environment has CODEX_HOME pointed at the dedicated auth directory
    and never carries Claude's own token.
    """
    repo_root = make_minimal_repo(tmp_path)
    environ = _valid_environ(tmp_path)
    captured_envs = []

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: (captured_envs.append(env), _approve_review())[1],
        workspace_factory=_fake_workspace_factory,
        environ=environ,
    )

    assert result.outcome == "APPROVED"
    assert len(captured_envs) == 1
    assert captured_envs[0]["CODEX_HOME"] == environ[CODEX_AUTH_HOME_ENV_VAR]
    assert CLAUDE_AUTH_ENV_VAR not in captured_envs[0]


def test_no_real_home_or_credential_denylist_var_ever_reaches_either_agent_even_on_failure(tmp_path, monkeypatch):
    """AC-6: neither agent's environment ever carries the real HOME or a
    CREDENTIAL_ENV_DENYLIST variable, including on a failure path (here,
    Codex's auth preflight failing after Claude's phase already ran).

    Regression (PEOS infrastructure maintenance, dogfooding finding): this
    test's `with_codex=False` intent must hold even when the orchestrator's
    real ambient environment already has a *valid* PEOS_CODEX_AUTH_HOME
    exported, exactly as a developer's own shell legitimately might.
    `dict(os.environ)` followed by `dict.update(_valid_environ(..., with_codex=False))`
    only ever adds/overwrites keys present in the overlay -- it never
    removes a key the overlay omits -- so a real ambient
    PEOS_CODEX_AUTH_HOME previously survived untouched into `environ`, made
    Codex's auth preflight pass, and flipped this test's outcome from the
    intended FAILED to APPROVED. `monkeypatch.setenv` below reproduces that
    exact ambient-pollution scenario deterministically (a real, valid,
    on-disk auth directory), independent of whatever the actual invoking
    shell happens to have exported, and the explicit `.pop(...)` after the
    overlay is what makes `with_codex=False` authoritative again.
    """
    import peos.workflow as workflow_module

    repo_root = make_minimal_repo(tmp_path)
    monkeypatch.setenv("SSH_AUTH_SOCK", "/tmp/should-never-leak.sock")
    real_ambient_codex_auth_home = tmp_path / "real-ambient-codex-auth-home"
    real_ambient_codex_auth_home.mkdir()
    (real_ambient_codex_auth_home / CODEX_AUTH_FILENAME).write_text('{"real": "auth"}', encoding="utf-8")
    monkeypatch.setenv(CODEX_AUTH_HOME_ENV_VAR, str(real_ambient_codex_auth_home))

    environ = dict(os.environ)
    environ.update(_valid_environ(tmp_path, with_codex=False))
    # Make the with_codex=False intent authoritative: dict.update() only
    # adds/overwrites keys present in its argument, it never deletes one
    # absent from it, so the real ambient PEOS_CODEX_AUTH_HOME set above
    # (or exported in the real invoking shell) would otherwise survive
    # into `environ` untouched and silently contradict this scenario.
    environ.pop(CODEX_AUTH_HOME_ENV_VAR, None)
    captured_claude_envs = []

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: (captured_claude_envs.append(env), _ok_claude())[1],
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: _approve_review(),
        workspace_factory=_fake_workspace_factory,
        environ=environ,
    )

    assert result.outcome == "FAILED"
    assert "SSH_AUTH_SOCK" not in captured_claude_envs[0]
    assert captured_claude_envs[0]["HOME"] != os.environ.get("HOME")


def test_default_verifier_is_bound_to_this_runs_resolved_environ(tmp_path, monkeypatch):
    """Focused Codex review remediation, Finding 2 (MAJOR): when the
    caller does not override `verifier`, `_run_workflow` must bind this
    run's own already-resolved `environ` into the real default verifier
    -- not a second, independent `os.environ` read that could diverge
    from an injected/test environ -- so verification's environment and
    sandbox deny-list are built from the same source everything else in
    this run uses.
    """
    import peos.workflow as workflow_module

    repo_root = make_minimal_repo(tmp_path)
    fake_environ = _valid_environ(tmp_path)
    captured = {}

    def fake_execute_plan(plan, workspace, repo_root_arg, sandbox_profile_dir, environ=None, **kwargs):
        captured["environ"] = environ
        return _pass_verification()

    monkeypatch.setattr(workflow_module, "execute_plan", fake_execute_plan)

    result = run_workflow(
        "task", repo_root,
        log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        codex_runner=lambda prompt, cwd, env=None: _approve_review(),
        workspace_factory=_fake_workspace_factory,
        environ=fake_environ,
        # `verifier` deliberately left at its default (_default_verifier)
        # -- this is specifically testing that real default path, not a
        # routing fake.
    )

    assert result.outcome == "APPROVED"
    assert captured["environ"] is fake_environ
