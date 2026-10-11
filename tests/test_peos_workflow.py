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

import hashlib
import json
import os
import shutil
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


def _approve_review(resolves=()):
    """`resolves`: reference strings (e.g. "0.1") of prior outstanding
    findings this APPROVE closes via `historical_finding_dispositions`
    -- SPEC-004's Outstanding Findings Register (peos/findings_register.py)
    makes APPROVE contractually invalid while any historical BLOCKER/MAJOR
    finding remains OUTSTANDING, so a closure review approving after an
    earlier CHANGES_REQUIRED review raised one must now explicitly
    disposition it, exactly as a real Codex closure review would.
    """
    from peos.codex_agent import HistoricalFindingDisposition
    from peos.findings_register import RESOLVED

    dispositions = tuple(
        HistoricalFindingDisposition(reference=ref, disposition=RESOLVED, note="fixed")
        for ref in resolves
    ) or None
    return CodexReviewResult(
        returncode=0, verdict="APPROVE", summary="looks good", findings=(),
        acceptance_criteria=(), raw_stdout="", raw_stderr="", ok=True,
        historical_finding_dispositions=dispositions,
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
    review_sequence = [_changes_required_review(human_decision=False), _approve_review(resolves=("0.1",))]

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
    """SPEC-004 AC-1b: `--max-cycles 1` explicitly passed reproduces
    SPEC-001/SPEC-003's exact one-remediation-cycle-then-gate behavior
    (the V2 default of 3 is covered separately by
    test_default_max_cycles_exhausts_after_three_remediation_cycles).
    """
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
        max_cycles=1,
    )

    assert result.outcome == "HUMAN_GATE"
    assert result.gate_id == "8"
    assert result.remediation_performed is True
    assert result.max_cycles == 1
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
    review_sequence = [_changes_required_review(human_decision=False), _approve_review(resolves=("0.1",))]

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


# --- SPEC-004: bounded multi-cycle remediation loop ---------------------

def _sequenced_codex_runner(review_sequence):
    calls = []

    def codex_runner(prompt, cwd, env=None, **kwargs):
        calls.append(prompt)
        return review_sequence[len(calls) - 1]

    return codex_runner, calls


def _counting_claude_runner():
    calls = []

    def claude_runner(prompt, cwd, env=None):
        calls.append(prompt)
        return _ok_claude()

    return claude_runner, calls


def test_ac1_default_max_cycles_converges_using_two_remediation_cycles(tmp_path):
    """AC-1: omitting --max-cycles uses the V2 default of 3, and this
    fixture specifically requires two remediation cycles -- it would
    reach HUMAN_GATE #8 under a reintroduced default of 1."""
    repo_root = make_minimal_repo(tmp_path)
    review_sequence = [
        _changes_required_review(),
        _changes_required_review(),
        _approve_review(resolves=("0.1", "1.1")),
    ]
    codex_runner, codex_calls = _sequenced_codex_runner(review_sequence)
    claude_runner, claude_calls = _counting_claude_runner()

    result = run_workflow(
        "task", repo_root, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=claude_runner,
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=codex_runner,
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "APPROVED"
    assert result.max_cycles == 3
    assert result.remediation_cycles_run == 2
    assert len(claude_calls) == 3  # implementation + 2 remediation cycles
    assert len(codex_calls) == 3


def test_ac1_same_fixture_under_explicit_max_cycles_1_gates_instead():
    """Same scenario as above but with --max-cycles 1 explicit: must
    stop at HUMAN_GATE #8 after exactly one remediation cycle -- this is
    what catches a silent reintroduction of "default behaves like
    max_cycles=1"."""
    import tempfile
    tmp_path = Path(tempfile.mkdtemp())
    repo_root = make_minimal_repo(tmp_path)
    review_sequence = [_changes_required_review(), _changes_required_review()]
    codex_runner, codex_calls = _sequenced_codex_runner(review_sequence)
    claude_runner, claude_calls = _counting_claude_runner()

    result = run_workflow(
        "task", repo_root, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=claude_runner,
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=codex_runner,
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
        max_cycles=1,
    )

    assert result.outcome == "HUMAN_GATE"
    assert result.gate_id == "8"
    assert len(claude_calls) == 2
    assert len(codex_calls) == 2


def test_ac2_converges_only_on_the_last_of_three_remediation_cycles(tmp_path):
    """AC-2: max_cycles=3, CHANGES_REQUIRED through remediation cycles 1
    and 2, APPROVE only after remediation cycle 3's closure review -- 4
    total Claude calls, 4 total Codex calls, never an early stop."""
    repo_root = make_minimal_repo(tmp_path)
    review_sequence = [
        _changes_required_review(),
        _changes_required_review(),
        _changes_required_review(),
        _approve_review(resolves=("0.1", "1.1", "2.1")),
    ]
    codex_runner, codex_calls = _sequenced_codex_runner(review_sequence)
    claude_runner, claude_calls = _counting_claude_runner()

    result = run_workflow(
        "task", repo_root, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=claude_runner,
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=codex_runner,
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
        max_cycles=3,
    )

    assert result.outcome == "APPROVED"
    assert result.remediation_cycles_run == 3
    assert len(claude_calls) == 4
    assert len(codex_calls) == 4


def test_ac3_exhausting_max_cycles_always_changes_required_gates_never_approves(tmp_path):
    """AC-3: max_cycles=3, Codex always CHANGES_REQUIRED -> HUMAN_GATE #8
    after exactly 1 initial + 3 closure Codex calls, never a 4th
    remediation cycle, never APPROVED."""
    repo_root = make_minimal_repo(tmp_path)
    codex_calls = []

    def codex_runner(prompt, cwd, env=None, **kwargs):
        codex_calls.append(prompt)
        return _changes_required_review()

    claude_runner, claude_calls = _counting_claude_runner()

    result = run_workflow(
        "task", repo_root, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=claude_runner,
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=codex_runner,
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
        max_cycles=3,
    )

    assert result.outcome == "HUMAN_GATE"
    assert result.gate_id == "8"
    assert len(claude_calls) == 4  # implementation + 3 remediation cycles, never a 4th
    assert len(codex_calls) == 4  # initial + 3 closure reviews, never a 5th
    assert "3" in result.gate_reason


def test_ac4_run_workflow_rejects_out_of_range_max_cycles_defensively(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    for bad in (0, -1, 6):
        result = run_workflow(
            "task", repo_root, log=lambda msg: None,
            spec_resolver=_resolver_returns(_spec_for(repo_root)),
            claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
            verifier=lambda workspace, repo_root, plan: _pass_verification(),
            codex_runner=lambda prompt, cwd, env=None: _approve_review(),
            workspace_factory=_fake_workspace_factory,
            environ=_valid_environ(tmp_path),
            max_cycles=bad,
        )
        assert result.outcome == "FAILED"


def test_ac5_context_recovery_output_present_even_when_no_spec_resolves(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    result = run_workflow(
        "task", repo_root, log=lambda msg: None,
        spec_resolver=_resolver_gates("No approved specification was found"),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: _approve_review(),
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )
    assert result.outcome == "HUMAN_GATE"
    assert result.context_recovery is not None
    assert "SPEC-001-x.md" in result.context_recovery.related_specs


def test_ac6_design_context_missing_artifact_gates_11_before_any_workspace_or_agent(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    spec_path = repo_root / "docs" / "specifications" / "SPEC-001-x.md"
    spec_path.write_text(
        spec_path.read_text(encoding="utf-8") + "\n## Design Context\n\n    docs/design/missing.json\n",
        encoding="utf-8",
    )
    workspace_calls = []
    claude_calls = []

    def tracking_workspace_factory(repo_root_arg, run_id):
        workspace_calls.append(1)
        return _fake_workspace_factory(repo_root_arg, run_id)

    result = run_workflow(
        "task", repo_root, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: (claude_calls.append(1), _ok_claude())[1],
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: _approve_review(),
        workspace_factory=tracking_workspace_factory,
        environ=_valid_environ(tmp_path),
    )
    assert result.outcome == "HUMAN_GATE"
    assert result.gate_id == "11"
    assert workspace_calls == []
    assert claude_calls == []


def test_ac7_design_context_resolved_artifact_proceeds_and_is_staged(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    (repo_root / "docs" / "design").mkdir(parents=True)
    (repo_root / "docs" / "design" / "export.json").write_text("{}", encoding="utf-8")
    spec_path = repo_root / "docs" / "specifications" / "SPEC-001-x.md"
    spec_path.write_text(
        spec_path.read_text(encoding="utf-8") + "\n## Design Context\n\n    docs/design/export.json\n",
        encoding="utf-8",
    )

    def real_ish_workspace_factory(repo_root_arg: Path, run_id: str) -> IsolatedWorkspace:
        workspace_dir = tmp_path / f"fake-workspace-{run_id}"
        (workspace_dir / "docs" / "specifications").mkdir(parents=True)
        spec_src = repo_root_arg / "docs" / "specifications" / "SPEC-001-x.md"
        (workspace_dir / "docs" / "specifications" / "SPEC-001-x.md").write_text(
            spec_src.read_text(encoding="utf-8"), encoding="utf-8",
        )
        for governance_file in ("CLAUDE.md", "AGENTS.md", "ENGINEERING.md"):
            (workspace_dir / governance_file).write_text(
                (repo_root_arg / governance_file).read_text(encoding="utf-8"), encoding="utf-8",
            )
        return IsolatedWorkspace(path=workspace_dir, home_dir=workspace_dir, baseline_commit="deadbeef")

    result = run_workflow(
        "task", repo_root, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: _approve_review(),
        workspace_factory=real_ish_workspace_factory,
        environ=_valid_environ(tmp_path),
    )
    assert result.outcome == "APPROVED"


def test_ac26_verification_failure_on_remediation_cycle_fails_immediately_no_codex_call(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    codex_calls = []
    verifier_calls = []

    def codex_runner(prompt, cwd, env=None, **kwargs):
        codex_calls.append(prompt)
        return _changes_required_review()

    def verifier(workspace, repo_root, plan):
        verifier_calls.append(1)
        if len(verifier_calls) == 1:
            return _pass_verification()
        return _fail_verification()

    result = run_workflow(
        "task", repo_root, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=verifier,
        codex_runner=codex_runner,
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
        max_cycles=3,
    )

    assert result.outcome == "FAILED"
    assert len(codex_calls) == 1  # only the cycle-0 initial review -- no closure review
    assert len(verifier_calls) == 2  # cycle-0 verification + the failing remediation-cycle-1 verification


def test_ac34_fingerprint_mismatch_detected_only_on_remediation_cycle_2(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    codex_calls = []

    def codex_runner(prompt, cwd, env=None, **kwargs):
        codex_calls.append(1)
        if len(codex_calls) == 3:
            # Simulate an out-of-band mutation during remediation cycle 2's closure review.
            (Path(cwd) / "sneaky_cycle_2.txt").write_text("should not be here\n", encoding="utf-8")
        return _changes_required_review()

    result = run_workflow(
        "task", repo_root, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=codex_runner,
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
        max_cycles=3,
    )
    assert result.outcome == "FAILED"
    assert "read-only reviewer boundary" in result.gate_reason


def test_ac35_governing_spec_mutated_on_disk_before_remediation_cycle_fails_closed(tmp_path):
    """AC-35 is specifically about a mutation to the *authoritative*
    spec file that a workspace-vs-frozen-baseline comparison alone would
    not catch (the workspace's own copy, cloned before the mutation,
    stays unchanged) -- exercised here with a workspace factory that
    genuinely uses a separate directory from repo_root, unlike
    `_fake_workspace_factory`'s speed shortcut.
    """
    repo_root = make_minimal_repo(tmp_path)
    spec_path = repo_root / "docs" / "specifications" / "SPEC-001-x.md"

    def real_ish_workspace_factory(repo_root_arg: Path, run_id: str) -> IsolatedWorkspace:
        workspace_dir = tmp_path / f"fake-workspace-{run_id}"
        (workspace_dir / "docs" / "specifications").mkdir(parents=True)
        (workspace_dir / "docs" / "specifications" / "SPEC-001-x.md").write_text(
            spec_path.read_text(encoding="utf-8"), encoding="utf-8",
        )
        for governance_file in ("CLAUDE.md", "AGENTS.md", "ENGINEERING.md"):
            (workspace_dir / governance_file).write_text(
                (repo_root_arg / governance_file).read_text(encoding="utf-8"), encoding="utf-8",
            )
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(repo_root_arg), capture_output=True, text=True,
        ).stdout.strip()
        return IsolatedWorkspace(path=workspace_dir, home_dir=workspace_dir, baseline_commit=head)

    verifier_calls = []

    def verifier(workspace, repo_root, plan):
        verifier_calls.append(1)
        if len(verifier_calls) == 1:
            # Mutate the *authoritative* spec file on disk right after
            # cycle 0's own verification -- i.e. between cycle 0's review
            # and remediation cycle 1's Claude call -- not the workspace copy.
            spec_path.write_text(spec_path.read_text(encoding="utf-8") + "\nmutated\n", encoding="utf-8")
        return _pass_verification()

    result = run_workflow(
        "task", repo_root, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=verifier,
        codex_runner=lambda prompt, cwd, env=None, **kwargs: _changes_required_review(),
        workspace_factory=real_ish_workspace_factory,
        environ=_valid_environ(tmp_path),
        max_cycles=3,
    )
    assert result.outcome == "FAILED"
    assert "no longer matches the identity frozen at Planning" in result.gate_reason


def test_ac36_reconciliation_behavior_identical_at_cycle_0_and_cycle_n_convergence(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    repo_root_a = make_minimal_repo(tmp_path / "a")
    result_a = run_workflow(
        "task", repo_root_a, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root_a)),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: _approve_review(),
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path / "a"),
    )

    repo_root_b = make_minimal_repo(tmp_path / "b")
    review_sequence_b = [_changes_required_review() for _ in range(5)] + [
        _approve_review(resolves=tuple(f"{i}.1" for i in range(5)))
    ]
    codex_runner_b, _ = _sequenced_codex_runner(review_sequence_b)
    result_b = run_workflow(
        "task", repo_root_b, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root_b)),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=codex_runner_b,
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path / "b"),
        max_cycles=5,
    )

    assert result_a.outcome == "APPROVED"
    assert result_b.outcome == "APPROVED"
    assert result_b.remediation_cycles_run == 5
    # Reconciliation ran in both cases, with the same shape of result.
    assert result_a.reconciliation is not None
    assert result_b.reconciliation is not None
    assert result_a.blocked_governance_mutation == ()
    assert result_b.blocked_governance_mutation == ()
    # `.peos/runs` is never part of what reconciliation copies/reports.
    assert not any(".peos" in p for p in result_a.reconciliation.copied)
    assert not any(".peos" in p for p in result_b.reconciliation.copied)


def test_ac38_human_decision_required_with_same_payload_approve_gates_6_never_approved_never_failed(tmp_path):
    """AC-38: cycle 0 raises a major finding (ref 0.1); a later closure
    review's historical_finding_dispositions sets 0.1 to
    HUMAN_DECISION_REQUIRED while that *same* payload's verdict is
    APPROVE -- must produce HUMAN_GATE #6, never APPROVED, never FAILED.
    """
    from peos.codex_agent import HistoricalFindingDisposition
    from peos.findings_register import HUMAN_DECISION_REQUIRED

    repo_root = make_minimal_repo(tmp_path)

    def contradictory_approve():
        return CodexReviewResult(
            returncode=0, verdict="APPROVE", summary="ok", findings=(),
            acceptance_criteria=(), raw_stdout="", raw_stderr="", ok=True,
            historical_finding_dispositions=(
                HistoricalFindingDisposition(reference="0.1", disposition=HUMAN_DECISION_REQUIRED, note="architecture call"),
            ),
        )

    review_sequence = [_changes_required_review(), contradictory_approve()]
    codex_runner, codex_calls = _sequenced_codex_runner(review_sequence)

    result = run_workflow(
        "task", repo_root, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=codex_runner,
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
        max_cycles=3,
    )
    assert result.outcome == "HUMAN_GATE"
    assert result.gate_id == "6"


def test_ac20_approve_with_outstanding_register_entry_fails_not_gates(tmp_path):
    """AC-20: APPROVE while the register still has an OUTSTANDING
    blocking/major entry is FAILED (a contract violation), never a plain
    convergence/APPROVED."""
    repo_root = make_minimal_repo(tmp_path)
    review_sequence = [_changes_required_review(), _approve_review()]  # does NOT resolve 0.1
    codex_runner, _ = _sequenced_codex_runner(review_sequence)

    result = run_workflow(
        "task", repo_root, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=codex_runner,
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
        max_cycles=3,
    )
    assert result.outcome == "FAILED"
    assert "Outstanding Findings Register" in result.gate_reason


# --- SPEC-004 Requirement 8: end-to-end dispute mechanics ----------------

def _claude_disputing(reference: str, evidence: str = "already covered by test_foo"):
    # SPEC-004 remediation Finding 6: production `run_claude` populates
    # `dispute_attempt_lines` by extracting DISPUTE[...] lines from the
    # *raw* summary before it is destructively bounded as a whole (see
    # peos/claude_agent.py and peos/workflow_disputes.py) -- a hand-built
    # `ClaudeRunResult` fixture must do the same, since peos/workflow.py
    # now parses disputes from that field, never from `summary` text.
    dispute_line = f"DISPUTE[{reference}]: {evidence}"
    return ClaudeRunResult(
        returncode=0, stdout="", stderr="", status="COMPLETED", gate_category=None, gate_reason=None,
        summary=f"Addressed everything else.\n{dispute_line}", ok=True,
        dispute_attempt_lines=(dispute_line,),
    )


def test_ac8_reviewer_overrules_dispute_gates_10_even_with_budget_remaining(tmp_path):
    repo_root = make_minimal_repo(tmp_path)

    def overruling_closure_review():
        return CodexReviewResult(
            returncode=0, verdict="CHANGES_REQUIRED", summary="still an issue", findings=(),
            acceptance_criteria=(), raw_stdout="", raw_stderr="", ok=True,
            reviewer_overrules_dispute=True, addressed_dispute_references=("0.1",),
        )

    review_sequence = [_changes_required_review(), overruling_closure_review()]
    codex_runner, codex_calls = _sequenced_codex_runner(review_sequence)

    claude_calls = []

    def claude_runner(prompt, cwd, env=None):
        claude_calls.append(prompt)
        if len(claude_calls) == 1:
            return _ok_claude()
        return _claude_disputing("0.1")

    result = run_workflow(
        "task", repo_root, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=claude_runner,
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=codex_runner,
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
        max_cycles=5,  # plenty of budget remaining -- must still gate immediately
    )
    assert result.outcome == "HUMAN_GATE"
    assert result.gate_id == "10"


def test_ac9_conceded_dispute_proceeds_through_normal_convergence(tmp_path):
    from peos.codex_agent import HistoricalFindingDisposition

    repo_root = make_minimal_repo(tmp_path)

    def conceding_closure_review():
        return CodexReviewResult(
            returncode=0, verdict="APPROVE", summary="fair point", findings=(),
            acceptance_criteria=(), raw_stdout="", raw_stderr="", ok=True,
            reviewer_overrules_dispute=False, addressed_dispute_references=("0.1",),
            historical_finding_dispositions=(
                HistoricalFindingDisposition(reference="0.1", disposition="RESOLVED", note="conceded"),
            ),
        )

    review_sequence = [_changes_required_review(), conceding_closure_review()]
    codex_runner, _ = _sequenced_codex_runner(review_sequence)

    claude_calls = []

    def claude_runner(prompt, cwd, env=None):
        claude_calls.append(prompt)
        if len(claude_calls) == 1:
            return _ok_claude()
        return _claude_disputing("0.1")

    result = run_workflow(
        "task", repo_root, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=claude_runner,
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=codex_runner,
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )
    assert result.outcome == "APPROVED"


def test_ac22_malformed_dispute_line_fails_the_remediation_cycle(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    review_sequence = [_changes_required_review()]
    codex_runner, codex_calls = _sequenced_codex_runner(review_sequence)

    claude_calls = []

    def claude_runner(prompt, cwd, env=None):
        claude_calls.append(prompt)
        if len(claude_calls) == 1:
            return _ok_claude()
        return ClaudeRunResult(
            returncode=0, stdout="", stderr="", status="COMPLETED", gate_category=None, gate_reason=None,
            summary="DISPUTE[abc]: malformed reference", ok=True,
            dispute_attempt_lines=("DISPUTE[abc]: malformed reference",),
        )

    result = run_workflow(
        "task", repo_root, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=claude_runner,
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=codex_runner,
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )
    assert result.outcome == "FAILED"
    assert "DISPUTE" in result.gate_reason
    assert len(codex_calls) == 1  # closure review never reached


# =========================================================================
# PEOS V2 implementation review remediation (SPEC-004 remediation, Codex
# findings F1-F11). Each test below reproduces the exact failure
# mechanism Codex's review described, exercised through the production
# `run_workflow` orchestration path (not a narrower helper), per that
# remediation's "do not repeat the mistake of testing only helpers"
# requirement.
# =========================================================================


# --- F1 (BLOCKER): governing-spec identity frozen at Planning ----------

def test_f1_spec_drift_during_workspace_creation_fails_closed_with_zero_consuming_invocations(tmp_path):
    """Reproduces the exact F1 race: Planning parses the governing
    specification's bytes (spec A) and freezes their hash
    (`peos.plan.build_plan`'s `governing_spec_content_hash`). The
    authoritative file then changes to spec B -- here, simulated as
    happening *during* workspace creation, adding a new acceptance
    criterion -- before the workspace's own staged copy and any
    consuming agent ever sees it. The run must fail closed, and neither
    Claude nor Codex may be invoked even once: there is no "mixed
    A-parsed/B-baseline" execution. Uses the real, default spec resolver
    (`peos.spec.resolve_governing_spec`, via `explicit_spec`) so Planning
    genuinely reads the file from disk, not a mocked resolution.
    """
    repo_root = make_minimal_repo(tmp_path)
    spec_path = repo_root / "docs" / "specifications" / "SPEC-001-x.md"
    original_text = spec_path.read_text(encoding="utf-8")

    claude_calls = []
    codex_calls = []

    def mutating_workspace_factory(repo_root_arg, run_id):
        # The authoritative spec changes to B *during* workspace
        # creation -- after Planning already parsed and hashed A.
        spec_path.write_text(
            original_text + "\n### AC-999 -- A brand-new acceptance criterion added after Planning\n",
            encoding="utf-8",
        )
        return _fake_workspace_factory(repo_root_arg, run_id)

    result = run_workflow(
        "implement x", repo_root,
        log=lambda msg: None,
        explicit_spec=spec_path,
        claude_runner=lambda prompt, cwd, env=None: (claude_calls.append(prompt), _ok_claude())[1],
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None, **kwargs: (codex_calls.append(prompt), _approve_review())[1],
        workspace_factory=mutating_workspace_factory,
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "FAILED"
    assert "identity frozen at Planning" in result.gate_reason
    assert claude_calls == []  # zero consuming agent invocations
    assert codex_calls == []


def test_f1_no_drift_still_proceeds_normally_to_approval(tmp_path):
    """Sanity counterpart: when nothing drifts, the frozen-identity
    checks introduced by this fix must not themselves block a normal
    run -- the governing spec's content never changes here.
    """
    repo_root = make_minimal_repo(tmp_path)
    spec_path = repo_root / "docs" / "specifications" / "SPEC-001-x.md"

    result = run_workflow(
        "implement x", repo_root, log=lambda msg: None,
        explicit_spec=spec_path,
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None, **kwargs: _approve_review(),
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )
    assert result.outcome == "APPROVED"


# --- F4 (MAJOR): Round Packet actually delivered in every prompt -------

def test_f4_round_packet_content_is_rendered_in_every_actual_prompt(tmp_path):
    """Captures the REAL prompts `run_workflow` passes to the injected
    Claude/Codex runners across a multi-cycle run (initial Claude,
    initial Codex, remediation Claude, closure Codex) and asserts the
    Round Packet's required elements are literal text in every one of
    them -- not merely held in an orchestrator-side dataclass
    (SPEC-004 remediation Finding 4/AC-37).
    """
    repo_root = make_minimal_repo(tmp_path)
    spec_path = repo_root / "docs" / "specifications" / "SPEC-001-x.md"
    spec_path.write_text(
        spec_path.read_text(encoding="utf-8")
        + "\n### AC-1 -- Do the thing\n\n### AC-2 -- Do the other thing\n",
        encoding="utf-8",
    )
    decisions_dir = repo_root / "docs" / "decisions"
    decisions_dir.mkdir(parents=True)
    (decisions_dir / "0001-example.md").write_text("# Decision\n\nbody\n", encoding="utf-8")
    # Commit both additions so the working tree is clean: `_fake_workspace_
    # factory` reuses repo_root itself as the "workspace" (for speed), so
    # an *untracked* file here would make reconciliation's untracked-file
    # copy-back try to copy repo_root onto itself (a `shutil.SameFileError`)
    # -- a fake-workspace-factory artifact unrelated to what this test is
    # about, avoided the same way test_ac7_design_context_resolved_
    # artifact_proceeds_and_is_staged avoids it (committing/pre-existing
    # state rather than leaving new files untracked).
    subprocess.run(["git", "add", "-A"], cwd=str(repo_root), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-q", "-m", "fixtures"],
        cwd=str(repo_root), check=True, capture_output=True,
    )
    baseline_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo_root), capture_output=True, text=True, check=True,
    ).stdout.strip()

    claude_prompts = []
    codex_prompts = []
    review_sequence = [_changes_required_review(), _approve_review(resolves=("0.1",))]

    def claude_runner(prompt, cwd, env=None):
        claude_prompts.append(prompt)
        return _ok_claude()

    def codex_runner(prompt, cwd, env=None, **kwargs):
        codex_prompts.append(prompt)
        return review_sequence[len(codex_prompts) - 1]

    result = run_workflow(
        "task", repo_root, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=claude_runner,
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=codex_runner,
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "APPROVED"
    assert len(claude_prompts) == 2  # initial implementation + 1 remediation
    assert len(codex_prompts) == 2  # initial review + closure review
    initial_claude_prompt, remediation_prompt = claude_prompts
    initial_review_prompt, closure_prompt = codex_prompts

    spec_hash = hashlib.sha256(spec_path.read_bytes()).hexdigest()
    claude_md_hash = hashlib.sha256((repo_root / "CLAUDE.md").read_bytes()).hexdigest()
    agents_md_hash = hashlib.sha256((repo_root / "AGENTS.md").read_bytes()).hexdigest()
    engineering_md_hash = hashlib.sha256((repo_root / "ENGINEERING.md").read_bytes()).hexdigest()
    for prompt in (initial_claude_prompt, initial_review_prompt, remediation_prompt, closure_prompt):
        # Governing-spec identity.
        assert spec_hash in prompt
        # Governance/decision identity.
        assert "docs/decisions/0001-example.md" in prompt
        # Complete governing acceptance-criteria set.
        assert "AC-1" in prompt
        assert "AC-2" in prompt
        # Workspace snapshot identity (the `_round_packet` helper always
        # renders a repo_state_fingerprint, a non-empty string).
        assert "Isolated workspace snapshot identity:" in prompt
        # SPEC-004 remediation Finding 4 (closure review): governance
        # artifact identities -- AGENTS.md, CLAUDE.md, ENGINEERING.md --
        # and the authoritative baseline Git commit SHA must be literal
        # text in every one of the four production prompts, not merely
        # held in an orchestrator-side RoundPacket the agent never reads.
        assert "CLAUDE.md" in prompt and claude_md_hash in prompt
        assert "AGENTS.md" in prompt and agents_md_hash in prompt
        assert "ENGINEERING.md" in prompt and engineering_md_hash in prompt
        assert baseline_commit in prompt

    # Initial Claude: no verification has run yet -- represented
    # explicitly, not omitted.
    assert "no deterministic verification result yet" in initial_claude_prompt

    # Initial Codex: receives the ACTUAL just-completed cycle-0
    # verification result.
    assert "PASSED" in initial_review_prompt

    # Remediation Claude: must receive the real LATEST verification
    # result (cycle 0's) -- never a hardcoded "no result yet" once
    # verification has actually happened.
    assert "PASSED" in remediation_prompt
    assert "no deterministic verification result yet" not in remediation_prompt

    # Closure Codex: the historical disposition that resolved 0.1 must
    # be rendered, not only the (now empty) outstanding-findings list.
    assert "RESOLVED" in closure_prompt
    assert "0.1" in closure_prompt


# --- F5 (MAJOR): static context re-verified before the FIRST Claude call

def test_f5_static_context_drift_before_initial_claude_fails_closed_with_zero_claude_calls(tmp_path):
    """Reproduces F5 exactly: the static-context artifact's identity is
    pinned during Planning. It then drifts before the isolated workspace
    stages it -- i.e. before cycle 0's Claude call, the very first
    consuming invocation of this run. Before this fix, the first re-
    verification of static-context identity happened only right before
    the *Codex* independent review (after Claude had already run once);
    this proves Claude is never invoked at all when the drift happens
    this early.
    """
    repo_root = make_minimal_repo(tmp_path)
    (repo_root / "docs" / "design").mkdir(parents=True)
    artifact_path = repo_root / "docs" / "design" / "export.json"
    artifact_path.write_text('{"a": 1}', encoding="utf-8")
    spec_path = repo_root / "docs" / "specifications" / "SPEC-001-x.md"
    spec_path.write_text(
        spec_path.read_text(encoding="utf-8") + "\n## Design Context\n\n    docs/design/export.json\n",
        encoding="utf-8",
    )

    claude_calls = []

    def mutating_workspace_factory(repo_root_arg, run_id):
        # The static-context artifact drifts between Planning (where it
        # was pinned) and workspace creation/staging. A genuinely
        # separate workspace directory is used (not the `_fake_workspace_
        # factory` shortcut that reuses repo_root itself) because staging
        # a Design Context artifact copies the artifact *into* the
        # workspace at the same relative path -- reusing repo_root as the
        # workspace would make source and destination the same file.
        artifact_path.write_text('{"a": 2}', encoding="utf-8")
        workspace_dir = tmp_path / f"fake-workspace-{run_id}"
        (workspace_dir / "docs" / "specifications").mkdir(parents=True)
        (workspace_dir / "docs" / "specifications" / "SPEC-001-x.md").write_text(
            spec_path.read_text(encoding="utf-8"), encoding="utf-8",
        )
        for governance_file in ("CLAUDE.md", "AGENTS.md", "ENGINEERING.md"):
            (workspace_dir / governance_file).write_text(
                (repo_root_arg / governance_file).read_text(encoding="utf-8"), encoding="utf-8",
            )
        return IsolatedWorkspace(path=workspace_dir, home_dir=workspace_dir, baseline_commit="deadbeef")

    result = run_workflow(
        "task", repo_root, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: (claude_calls.append(prompt), _ok_claude())[1],
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: _approve_review(),
        workspace_factory=mutating_workspace_factory,
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "FAILED"
    assert "identity check failed before Claude implementation" in result.gate_reason
    assert "drifted" in result.gate_reason
    assert claude_calls == []


def _real_ish_workspace_factory_with_design_context(repo_root: Path, spec_path: Path, tmp_path: Path, holder: dict):
    """Shared by the F5-A/F5-B tests below: a workspace factory that
    builds a genuinely separate workspace directory (never `repo_root`
    itself, since Design Context staging copies a file *into* the
    workspace at the same relative path) and records its path in
    `holder["path"]` so a later `claude_runner` hook -- invoked only
    after staging has already completed -- can tamper with the staged
    copy.
    """
    def factory(repo_root_arg: Path, run_id: str) -> IsolatedWorkspace:
        workspace_dir = tmp_path / f"fake-workspace-{run_id}"
        (workspace_dir / "docs" / "specifications").mkdir(parents=True)
        (workspace_dir / "docs" / "specifications" / "SPEC-001-x.md").write_text(
            spec_path.read_text(encoding="utf-8"), encoding="utf-8",
        )
        for governance_file in ("CLAUDE.md", "AGENTS.md", "ENGINEERING.md"):
            (workspace_dir / governance_file).write_text(
                (repo_root_arg / governance_file).read_text(encoding="utf-8"), encoding="utf-8",
            )
        holder["path"] = workspace_dir
        return IsolatedWorkspace(path=workspace_dir, home_dir=workspace_dir, baseline_commit="deadbeef")
    return factory


def test_f5a_staged_artifact_swapped_for_matching_content_symlink_fails_before_codex(tmp_path):
    """F5-A: Planning/staging succeeds normally. Between cycle 0's Claude
    call (which runs after staging) and the Codex independent review
    that follows it, the staged artifact is replaced by a symlink to the
    authoritative file itself -- guaranteeing byte-for-byte-identical
    content. The static-context re-verification that already runs
    before every Codex/Claude invocation (`_check_static_context_
    identity`) must catch this on structure alone and fail closed before
    Codex is ever invoked -- its invocation count must stay zero.
    """
    repo_root = make_minimal_repo(tmp_path)
    (repo_root / "docs" / "design").mkdir(parents=True)
    artifact_path = repo_root / "docs" / "design" / "export.json"
    artifact_path.write_text('{"a": 1}', encoding="utf-8")
    spec_path = repo_root / "docs" / "specifications" / "SPEC-001-x.md"
    spec_path.write_text(
        spec_path.read_text(encoding="utf-8") + "\n## Design Context\n\n    docs/design/export.json\n",
        encoding="utf-8",
    )

    holder: dict = {}
    codex_calls = []

    def claude_runner(prompt, cwd, env=None):
        staged_path = holder["path"] / "docs" / "design" / "export.json"
        staged_path.unlink()
        staged_path.symlink_to(artifact_path)
        return _ok_claude()

    result = run_workflow(
        "task", repo_root, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=claude_runner,
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None, **kwargs: (codex_calls.append(prompt), _approve_review())[1],
        workspace_factory=_real_ish_workspace_factory_with_design_context(repo_root, spec_path, tmp_path, holder),
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "FAILED"
    assert "symlink" in result.gate_reason.lower()
    assert codex_calls == []


def test_f5b_staged_parent_directory_swapped_for_symlink_fails_before_codex(tmp_path):
    """F5-B: same as F5-A, but the swap replaces the staged artifact's
    *parent directory* with a symlink (pointing at the real
    `docs/design` directory, so the file found through it still has
    matching content) rather than the leaf file itself. Must still fail
    closed before Codex is invoked.
    """
    repo_root = make_minimal_repo(tmp_path)
    (repo_root / "docs" / "design").mkdir(parents=True)
    artifact_path = repo_root / "docs" / "design" / "export.json"
    artifact_path.write_text('{"a": 1}', encoding="utf-8")
    spec_path = repo_root / "docs" / "specifications" / "SPEC-001-x.md"
    spec_path.write_text(
        spec_path.read_text(encoding="utf-8") + "\n## Design Context\n\n    docs/design/export.json\n",
        encoding="utf-8",
    )

    holder: dict = {}
    codex_calls = []

    def claude_runner(prompt, cwd, env=None):
        staged_parent = holder["path"] / "docs" / "design"
        shutil.rmtree(staged_parent)
        staged_parent.symlink_to(artifact_path.parent, target_is_directory=True)
        return _ok_claude()

    result = run_workflow(
        "task", repo_root, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=claude_runner,
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None, **kwargs: (codex_calls.append(prompt), _approve_review())[1],
        workspace_factory=_real_ish_workspace_factory_with_design_context(repo_root, spec_path, tmp_path, holder),
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "FAILED"
    assert "symlink" in result.gate_reason.lower()
    assert codex_calls == []


def test_f5c_normal_regular_staged_copy_continues_normally_to_approval(tmp_path):
    """F5-C: the sanity counterpart -- an ordinary, untampered staged
    copy (a real regular file with a matching hash, no symlink anywhere)
    must not itself be blocked by the structural check introduced for
    F5-A/F5-B. Equivalent in spirit to
    `test_ac7_design_context_resolved_artifact_proceeds_and_is_staged`,
    repeated here under the F5 label for direct traceability to the
    closure review's required regressions.
    """
    repo_root = make_minimal_repo(tmp_path)
    (repo_root / "docs" / "design").mkdir(parents=True)
    (repo_root / "docs" / "design" / "export.json").write_text('{"a": 1}', encoding="utf-8")
    spec_path = repo_root / "docs" / "specifications" / "SPEC-001-x.md"
    spec_path.write_text(
        spec_path.read_text(encoding="utf-8") + "\n## Design Context\n\n    docs/design/export.json\n",
        encoding="utf-8",
    )

    holder: dict = {}
    result = run_workflow(
        "task", repo_root, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None, **kwargs: _approve_review(),
        workspace_factory=_real_ish_workspace_factory_with_design_context(repo_root, spec_path, tmp_path, holder),
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "APPROVED"
    staged_path = holder["path"] / "docs" / "design" / "export.json"
    assert staged_path.is_file()
    assert not staged_path.is_symlink()


# --- F8 (MAJOR): unexpected exception terminalizes the ledger ----------

def test_f8_unexpected_verifier_exception_persists_a_terminal_failed_ledger(tmp_path):
    """Reproduces F8: an unexpected exception from an injected agent/
    verifier must not only make `run_workflow` *return* FAILED -- the
    *persisted* Run Ledger on disk must also show the terminal outcome,
    not whatever non-terminal phase (outcome=null) it last reached before
    the exception. Checked by reading the real ledger.json this run
    actually wrote, via `result.ledger_path`.
    """
    repo_root = make_minimal_repo(tmp_path)

    def exploding_verifier(workspace, repo_root, plan):
        raise RuntimeError("simulated verifier crash")

    result = run_workflow(
        "task", repo_root, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=exploding_verifier,
        codex_runner=lambda prompt, cwd, env=None: _approve_review(),
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "FAILED"
    assert "simulated verifier crash" in result.gate_reason
    assert result.ledger_path is not None
    ledger_data = json.loads(Path(result.ledger_path).read_text(encoding="utf-8"))
    assert ledger_data["outcome"] == "FAILED"
    assert "simulated verifier crash" in ledger_data["gate_reason"]
    # The run is now recognized terminal by retention's own validator.
    from peos.ledger import SCHEMA_VERSION
    assert ledger_data["schema_version"] == SCHEMA_VERSION


def test_f8_ledger_write_failure_itself_does_not_recurse(tmp_path, monkeypatch):
    """The companion requirement: if the ledger subsystem itself is why a
    terminal write cannot be persisted, `peos/workflow.py` must not retry
    it (no recursive failure) -- it still returns FAILED with a sanitized
    diagnostic. Demonstrated by making every ledger write fail and
    confirming the run still completes (promptly, without hanging) with
    a sane FAILED result.
    """
    import peos.workflow as workflow_module
    from peos.ledger import LedgerError

    repo_root = make_minimal_repo(tmp_path)

    def always_failing_write(self, ledger):
        raise LedgerError("simulated ledger write failure")

    monkeypatch.setattr(workflow_module.LedgerWriter, "write", always_failing_write)

    result = run_workflow(
        "task", repo_root, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: _approve_review(),
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "FAILED"
    assert "simulated ledger write failure" in result.gate_reason


# --- F10 (MINOR): retention cap enforced AFTER the current run completes

def test_f10_current_run_completion_does_not_leave_cap_plus_one_retained(tmp_path):
    """Reproduces F10's retention-timing gap: with exactly
    `DEFAULT_RETENTION` pre-existing valid-terminal runs already on disk,
    a new run that itself terminalizes must not leave `DEFAULT_RETENTION
    + 1` runs retained -- retention must be enforced again *after* this
    run's own terminal ledger write, not only at the top of the run
    before it started.
    """
    from peos.ledger import DEFAULT_RETENTION, LedgerWriter, RunLedger, SCHEMA_VERSION

    repo_root = make_minimal_repo(tmp_path)
    for i in range(DEFAULT_RETENTION):
        writer = LedgerWriter(repo_root, f"preexisting{i}")
        writer.write(RunLedger(
            run_id=f"preexisting{i}", schema_version=SCHEMA_VERSION,
            created_at=f"2024-01-{i + 1:02d}T00:00:00+00:00",
            updated_at=f"2024-01-{i + 1:02d}T00:00:00+00:00",
            max_cycles=1, authoritative_baseline="", governing_spec_identity="",
            active_phase="Complete", last_completed_phase="Complete", current_cycle=0,
            outcome="FAILED",
        ))

    result = run_workflow(
        "task", repo_root, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None: _approve_review(),
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )
    assert result.outcome == "APPROVED"

    remaining = {p.name for p in (repo_root / ".peos" / "runs").iterdir()}
    assert len(remaining) == DEFAULT_RETENTION
    assert result.run_id in remaining  # the just-completed run survives as the most recent


# --- F11 (MINOR test gap): AC-14 Delivery Report retained regression ---

def test_f11_delivery_report_shows_unresolved_minors_and_resolved_history(tmp_path):
    """A retained, automated regression for AC-14: a multi-cycle APPROVED
    run whose final Codex review carries MINOR/INFO findings must have
    them explicitly surfaced in the Delivery Report, alongside the
    resolved historical BLOCKER finding from an earlier cycle -- both
    read back from the real `build_report()` output, not an ad hoc
    in-memory check.
    """
    from peos.codex_agent import HistoricalFindingDisposition
    from peos.findings_register import RESOLVED
    from peos.report import build_report

    repo_root = make_minimal_repo(tmp_path)

    def changes_required_with_blocker():
        findings = (
            Finding(
                severity="blocking", category="implementation_defect",
                description="a real blocker finding", requires_human_decision=False,
            ),
        )
        return CodexReviewResult(
            returncode=0, verdict="CHANGES_REQUIRED", summary="blocker found", findings=findings,
            acceptance_criteria=(), raw_stdout="", raw_stderr="", ok=True,
        )

    def approve_with_minor_and_info():
        minor_info = (
            Finding(
                severity="minor", category="non_blocking_improvement",
                description="could rename a local variable", requires_human_decision=False,
            ),
            Finding(
                severity="info", category="non_blocking_improvement",
                description="consider adding a clarifying comment", requires_human_decision=False,
            ),
        )
        return CodexReviewResult(
            returncode=0, verdict="APPROVE", summary="ok now", findings=minor_info,
            acceptance_criteria=(), raw_stdout="", raw_stderr="", ok=True,
            historical_finding_dispositions=(
                HistoricalFindingDisposition(reference="0.1", disposition=RESOLVED, note="fixed the blocker"),
            ),
        )

    review_sequence = [changes_required_with_blocker(), approve_with_minor_and_info()]
    codex_runner, codex_calls = _sequenced_codex_runner(review_sequence)

    result = run_workflow(
        "task", repo_root, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=codex_runner,
        workspace_factory=_fake_workspace_factory,
        environ=_valid_environ(tmp_path),
    )

    assert result.outcome == "APPROVED"
    report = build_report(result, repo_root)

    # Explicit unresolved MINOR/INFO findings section, with both names present.
    assert "## Unresolved MINOR findings" in report
    minor_section = report.split("## Unresolved MINOR findings", 1)[1]
    assert "could rename a local variable" in minor_section
    assert "consider adding a clarifying comment" in minor_section

    # Resolved historical BLOCKER is represented, with its disposition.
    assert "a real blocker finding" in report
    assert "RESOLVED" in report
    assert "fixed the blocker" in report

    # Readiness/outcome is accurate.
    assert "**Outcome:** APPROVED" in report
