"""PEOS Automation V1 orchestration (SPEC-001 Section 6 Workflow),
remediated per the 11-finding Codex review (Findings 1, 3, 4, 6, 7, 8).

`run_workflow` is the one place the phase sequence, human gates, and the
bounded (at most one) remediation cycle are implemented. Every external
effect -- resolving the governing spec, creating the isolated workspace,
invoking Claude, running local verification, invoking Codex -- is
injected as a callable or reached through a small, replaceable module so
this file can be unit-tested without ever shelling out to `claude`,
`codex`, or real Git (see tests/test_peos_workflow.py).

Execution-boundary summary (Finding 1; full rationale in
peos/sandbox.py): Claude and Codex never operate on the authoritative
repository. They operate in a disposable local Git clone -- the
"isolated workspace" -- created fresh for this run, with every remote
removed and push-capable credentials stripped from the subprocess
environment. The authoritative working tree is only ever touched once,
at the very end of this function, by `reconcile_workspace_to_repo`,
which copies working-tree changes back for human review -- it never
stages, commits, or pushes.

Fail-closed policy (SPEC-001 Section 11): any unexpected command failure,
uninterpretable agent output, unsafe repository state, or detected
governance-artifact mutation stops the run with outcome="FAILED" rather
than guessing and continuing. Enumerated Human Gates (SPEC-001 Section 7)
-- including an implementation agent's own structured HUMAN_GATE status
(Finding 3) -- stop the run with outcome="HUMAN_GATE". Automation never
proceeds past either state on its own, and an unexpected exception
anywhere in this function is itself caught and converted to a FAILED
outcome (Finding 11) rather than propagating as a traceback.
"""

from __future__ import annotations

import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal

from peos.claude_agent import ClaudeRunResult, run_claude
from peos.codex_agent import CodexReviewResult, run_codex_review
from peos.gitutil import repo_state_fingerprint
from peos.preflight import (
    PreflightResult,
    check_repository_safety,
    detect_mutations,
    hash_governance_artifacts,
)
from peos.prompts import (
    build_implementation_prompt,
    build_remediation_prompt,
    build_rereview_prompt,
    build_review_prompt,
)
from peos.sandbox import (
    IsolatedWorkspace,
    ReconciliationResult,
    WorkspaceError,
    create_isolated_workspace,
    ensure_spec_in_workspace,
    reconcile_workspace_to_repo,
    sandboxed_env,
)
from peos.spec import SpecResolution, resolve_governing_spec
from peos.verification_plan import VerificationPlan, execute_plan, resolve_verification_plan
from peos.verify import VerificationReport

Outcome = Literal["APPROVED", "HUMAN_GATE", "FAILED"]

ClaudeRunner = Callable[..., ClaudeRunResult]
CodexRunner = Callable[..., CodexReviewResult]
Verifier = Callable[[IsolatedWorkspace, Path, VerificationPlan], VerificationReport]
SpecResolver = Callable[[str, Path, "Path | None"], SpecResolution]
WorkspaceFactory = Callable[[Path, str], IsolatedWorkspace]


@dataclass(frozen=True)
class PhaseLog:
    phase: str
    detail: str = ""


@dataclass(frozen=True)
class RunResult:
    task: str
    outcome: Outcome
    phases: tuple[PhaseLog, ...] = field(default_factory=tuple)
    spec: object | None = None
    gate_id: str | None = None
    gate_reason: str | None = None
    claude_runs: tuple[ClaudeRunResult, ...] = field(default_factory=tuple)
    verification_reports: tuple[VerificationReport, ...] = field(default_factory=tuple)
    verification_plan: VerificationPlan | None = None
    review_results: tuple[CodexReviewResult, ...] = field(default_factory=tuple)
    remediation_performed: bool = False
    workspace_path: str | None = None
    reconciliation: ReconciliationResult | None = None
    blocked_governance_mutation: tuple[str, ...] = field(default_factory=tuple)
    reconciliation_error: str | None = None


def _default_verifier(workspace: IsolatedWorkspace, repo_root: Path, plan: VerificationPlan) -> VerificationReport:
    return execute_plan(plan, workspace, repo_root, sandbox_profile_dir=workspace.path.parent / "sandbox-profiles")


# Human Gate IDs, matching SPEC-001 Section 7 verbatim.
GATE_NO_SPEC = "1"
GATE_AMBIGUOUS_SPEC = "2"
GATE_PHYSICS = "3"
GATE_CONTROL_OR_PROTECTION = "4"
GATE_ARCHITECTURE = "5"
GATE_HUMAN_OWNED_FINDING = "6"
GATE_UNRESOLVED_AFTER_REMEDIATION = "8"
GATE_RELEASE_ACTION = "9"

_CLAUDE_GATE_CATEGORY_TO_ID = {
    "physics": GATE_PHYSICS,
    "control": GATE_CONTROL_OR_PROTECTION,
    "protection": GATE_CONTROL_OR_PROTECTION,
    "architecture": GATE_ARCHITECTURE,
    "specification_intent": GATE_AMBIGUOUS_SPEC,
    "ambiguous_specification": GATE_AMBIGUOUS_SPEC,
    "git_release_action": GATE_RELEASE_ACTION,
}


def run_workflow(
    task: str,
    repo_root: Path,
    explicit_spec: Path | None = None,
    specs_dir: Path | None = None,
    log: Callable[[str], None] = lambda msg: print(msg, file=sys.stderr),
    spec_resolver: SpecResolver = resolve_governing_spec,
    claude_runner: ClaudeRunner = run_claude,
    codex_runner: CodexRunner = run_codex_review,
    verifier: Verifier = _default_verifier,
    workspace_factory: WorkspaceFactory = create_isolated_workspace,
) -> RunResult:
    try:
        return _run_workflow(
            task, repo_root, explicit_spec, specs_dir, log,
            spec_resolver, claude_runner, codex_runner, verifier, workspace_factory,
        )
    except Exception as exc:  # noqa: BLE001 -- SPEC-001 Finding 11: never propagate a traceback
        log(f"[PEOS ERROR] Unhandled exception: {exc}")
        return RunResult(
            task=task, outcome="FAILED",
            phases=(PhaseLog(phase="Failure", detail=f"Unhandled exception: {exc}"),),
            gate_reason=f"Unhandled exception during orchestration: {exc}",
        )


def _run_workflow(
    task: str,
    repo_root: Path,
    explicit_spec: Path | None,
    specs_dir: Path | None,
    log: Callable[[str], None],
    spec_resolver: SpecResolver,
    claude_runner: ClaudeRunner,
    codex_runner: CodexRunner,
    verifier: Verifier,
    workspace_factory: WorkspaceFactory,
) -> RunResult:
    specs_dir = specs_dir or (repo_root / "docs" / "specifications")
    phases: list[PhaseLog] = []
    claude_runs: list[ClaudeRunResult] = []
    verification_reports: list[VerificationReport] = []
    review_results: list[CodexReviewResult] = []
    remediation_performed = False
    workspace: IsolatedWorkspace | None = None
    baseline_hashes: dict[str, str] = {}
    vplan: VerificationPlan | None = None
    current_spec: object | None = None

    def stage(name: str) -> None:
        log(f"[PEOS] {name}")
        phases.append(PhaseLog(phase=name))

    def _base_kwargs() -> dict:
        return dict(
            task=task, phases=tuple(phases),
            spec=current_spec,
            claude_runs=tuple(claude_runs),
            verification_reports=tuple(verification_reports),
            verification_plan=vplan,
            review_results=tuple(review_results),
            remediation_performed=remediation_performed,
            workspace_path=str(workspace.path) if workspace is not None else None,
        )

    def _reconcile() -> tuple[ReconciliationResult | None, tuple[str, ...], str | None]:
        """Returns (result, blocked_governance_paths, error). `error` is
        set only when reconciliation itself could not be completed (an
        exception during copy-back) -- distinct from `blocked_governance_
        paths`, which is the normal, expected, and visible rejection of a
        governance-artifact edit. Callers (`approve()` in particular) must
        treat a non-None `error` as a reason this run cannot be APPROVED
        (Finding 8): the human-reviewable authoritative working tree would
        not actually reflect what Codex approved.
        """
        if workspace is None:
            return None, (), None
        try:
            result = reconcile_workspace_to_repo(
                workspace, repo_root, protected_relative_paths=frozenset(baseline_hashes.keys()),
            )
        except Exception as exc:  # noqa: BLE001
            log(f"[PEOS ERROR] Could not reconcile isolated workspace back to {repo_root}: {exc}")
            return None, (), str(exc)
        if result.blocked_governance_changes:
            log(
                "[PEOS GATE] Governance artifact(s) were modified inside the isolated "
                f"workspace and were NOT copied back: {', '.join(result.blocked_governance_changes)}"
            )
        return result, result.blocked_governance_changes, None

    def gate(gate_id: str, reason: str) -> RunResult:
        log(f"[PEOS GATE] {reason}")
        phases.append(PhaseLog(phase="Human gate", detail=reason))
        reconciliation, blocked, recon_error = _reconcile()
        return RunResult(
            **_base_kwargs(), outcome="HUMAN_GATE",
            gate_id=gate_id, gate_reason=reason,
            reconciliation=reconciliation, blocked_governance_mutation=blocked,
            reconciliation_error=recon_error,
        )

    def fail(reason: str) -> RunResult:
        log(f"[PEOS ERROR] {reason}")
        phases.append(PhaseLog(phase="Failure", detail=reason))
        reconciliation, blocked, recon_error = _reconcile()
        return RunResult(
            **_base_kwargs(), outcome="FAILED", gate_reason=reason,
            reconciliation=reconciliation, blocked_governance_mutation=blocked,
            reconciliation_error=recon_error,
        )

    def approve() -> RunResult:
        stage("Complete")
        reconciliation, blocked, recon_error = _reconcile()
        if recon_error is not None:
            # Finding 8: reconciliation failure must NEVER produce
            # APPROVED -- the authoritative working tree would not
            # actually reflect what Codex approved. Build the FAILED
            # result directly from the reconciliation outcome already
            # computed above rather than calling fail() (which would
            # re-run reconciliation a second time).
            reason = (
                "Codex approved the implementation, but reconciling the isolated "
                f"workspace back onto {repo_root} failed, so the authoritative working "
                f"tree was not safely updated: {recon_error}"
            )
            log(f"[PEOS ERROR] {reason}")
            phases.append(PhaseLog(phase="Failure", detail=reason))
            return RunResult(
                **_base_kwargs(), outcome="FAILED", gate_reason=reason,
                reconciliation=reconciliation, blocked_governance_mutation=blocked,
                reconciliation_error=recon_error,
            )
        return RunResult(
            **_base_kwargs(), outcome="APPROVED",
            reconciliation=reconciliation, blocked_governance_mutation=blocked,
        )

    # Latest Codex review, Finding 5: an unexpected exception raised
    # anywhere below (e.g. from workspace_factory, ensure_spec_in_workspace,
    # hash_governance_artifacts, the verifier, or either agent runner) must
    # still produce a FAILED RunResult carrying whatever spec/claude_runs/
    # verification_reports/review_results had already been accumulated at
    # the point of failure -- not an empty, context-free RunResult. This
    # try/except lives *inside* _run_workflow (not only in the outer
    # run_workflow wrapper) specifically so its `except` clause can still
    # reach `_base_kwargs()` and the other closures above, which already
    # reflect everything resolved so far.
    try:
        # Phase 0 -- Repository preflight (Finding 7)
        stage("Repository preflight")
        preflight: PreflightResult = check_repository_safety(repo_root)
        if not preflight.ok:
            return fail(f"Repository preflight failed: {preflight.reason}")
        if preflight.dirty:
            log("[PEOS] Repository working tree is dirty; the isolated workspace will carry that state over faithfully.")

        # Phase 1 -- Intake
        stage("Intake")
        resolution = spec_resolver(task, specs_dir, explicit_spec)
        if resolution.spec is None:
            gate_id = GATE_AMBIGUOUS_SPEC if "ambiguous" in (resolution.gate_reason or "").lower() else GATE_NO_SPEC
            return gate(gate_id, resolution.gate_reason or "No governing specification could be resolved.")
        current_spec = resolution.spec
        log(f"[PEOS] Governing specification: {resolution.spec.path}")

        # Finding 3 (latest Codex review): the governing spec's own
        # Verification section(s) can declare additional required commands;
        # read from repo_root's authoritative copy now, before any
        # implementation agent runs, so they are frozen into the plan exactly
        # like the default pytest/npm steps.
        vplan = resolve_verification_plan(repo_root, resolution.spec.path)

        try:
            workspace = workspace_factory(repo_root, uuid.uuid4().hex[:12])
        except WorkspaceError as exc:
            return fail(f"Could not create isolated implementation workspace: {exc}")
        log(f"[PEOS] Isolated workspace: {workspace.path}")
        env = sandboxed_env(workspace.home_dir)

        # Finding 6: the governing spec must be readable from *inside* the
        # workspace at a relative path, since Claude/Codex run with
        # cwd=workspace.path (and Claude additionally with --restricted,
        # which confines file tools to that cwd) -- an absolute authoritative-
        # repo path is not reliably reachable from inside either agent.
        spec_path = ensure_spec_in_workspace(workspace, repo_root, resolution.spec.path)

        # Finding 4: hashed *after* the spec is guaranteed to exist at
        # `spec_path` inside the workspace, keyed by that same relative path,
        # so an externally-supplied (--spec outside repo_root) specification
        # is covered by mutation detection exactly like a discovered one.
        baseline_hashes = hash_governance_artifacts(repo_root, resolution.spec.path, spec_path)

        def _check_governance_mutation(after_phase: str) -> RunResult | None:
            mutated = detect_mutations(baseline_hashes, workspace.path)
            if mutated:
                return fail(
                    f"Governance artifact(s) were mutated inside the isolated workspace "
                    f"during {after_phase} and were rejected: {', '.join(mutated)}. An "
                    "implementation agent must not silently change an approved "
                    "specification or governance document (CLAUDE.md Integrity Rules)."
                )
            return None

        def _codex_phase(name: str, prompt: str) -> tuple[CodexReviewResult | None, RunResult | None]:
            """Run one Codex phase with a before/after fingerprint of both the
            authoritative repository and the isolated workspace itself (Finding
            3): Codex must not modify either. The fingerprint is content-based
            (full diff text + untracked-file content hashes, not just names/
            status -- see peos/gitutil.py), so it also catches a mutation to a
            file that was already dirty/untracked going in.
            """
            pre_repo = repo_state_fingerprint(repo_root)
            pre_workspace = repo_state_fingerprint(workspace.path)
            result = codex_runner(prompt, workspace.path, env=env)
            if repo_state_fingerprint(repo_root) != pre_repo:
                return None, fail(
                    f"Codex's {name} appears to have changed the authoritative repository "
                    "working tree, which violates the read-only reviewer boundary "
                    "(SPEC-001 Section 9). Failing closed."
                )
            if repo_state_fingerprint(workspace.path) != pre_workspace:
                return None, fail(
                    f"Codex's {name} appears to have changed the isolated workspace, which "
                    "violates the read-only reviewer boundary (SPEC-001 Section 9) even "
                    "though the authoritative repository was untouched. Failing closed."
                )
            return result, None

        # Phase 2 -- Implementation
        stage("Claude implementation")
        impl_result = claude_runner(build_implementation_prompt(task, spec_path), workspace.path, env=env)
        claude_runs.append(impl_result)
        if impl_result.status == "HUMAN_GATE":
            gate_id = _CLAUDE_GATE_CATEGORY_TO_ID.get(impl_result.gate_category or "", GATE_HUMAN_OWNED_FINDING)
            return gate(gate_id, f"Claude escalated during implementation [{impl_result.gate_category}]: {impl_result.gate_reason}")
        if not impl_result.ok:
            return fail(f"Claude implementation did not complete successfully: {impl_result.error}")

        mutation_failure = _check_governance_mutation("implementation")
        if mutation_failure is not None:
            return mutation_failure

        # Local verification after implementation
        stage("Local verification")
        vreport = verifier(workspace, repo_root, vplan)
        verification_reports.append(vreport)
        if not vreport.passed:
            failing = ", ".join(r.name for r in vreport.failures)
            return fail(f"Local verification failed after implementation: {failing}")

        # Finding 4: re-check governance-artifact integrity after deterministic
        # verification too, before review/approval -- not just right after
        # each Claude phase -- so a mutation introduced by anything that ran
        # in between (however unlikely) cannot slip through to Codex/approval.
        mutation_failure = _check_governance_mutation("post-implementation verification")
        if mutation_failure is not None:
            return mutation_failure

        # Phase 3 -- Independent Review
        stage("Codex independent review")
        review, gate_or_fail = _codex_phase("independent review", build_review_prompt(task, spec_path))
        if gate_or_fail is not None:
            return gate_or_fail
        review_results.append(review)
        if not review.ok:
            return fail(f"Codex review produced uninterpretable output: {review.error}")

        if review.approved:
            return approve()

        human_findings = review.human_decision_findings
        if human_findings:
            reasons = "; ".join(f.description for f in human_findings)
            return gate(
                GATE_HUMAN_OWNED_FINDING,
                "Codex review found issues that require a human-owned engineering "
                f"decision and cannot be auto-remediated: {reasons}",
            )

        # Phase 4 -- Remediation (bounded: exactly one automatic cycle)
        remediation_performed = True
        stage("Claude remediation")
        remediation_result = claude_runner(
            build_remediation_prompt(task, spec_path, review.findings), workspace.path, env=env,
        )
        claude_runs.append(remediation_result)
        if remediation_result.status == "HUMAN_GATE":
            gate_id = _CLAUDE_GATE_CATEGORY_TO_ID.get(remediation_result.gate_category or "", GATE_HUMAN_OWNED_FINDING)
            return gate(gate_id, f"Claude escalated during remediation [{remediation_result.gate_category}]: {remediation_result.gate_reason}")
        if not remediation_result.ok:
            return fail(f"Claude remediation did not complete successfully: {remediation_result.error}")

        mutation_failure = _check_governance_mutation("remediation")
        if mutation_failure is not None:
            return mutation_failure

        stage("Local verification (post-remediation)")
        vreport2 = verifier(workspace, repo_root, vplan)
        verification_reports.append(vreport2)
        if not vreport2.passed:
            failing = ", ".join(r.name for r in vreport2.failures)
            return fail(f"Local verification failed after remediation: {failing}")

        mutation_failure = _check_governance_mutation("post-remediation verification")
        if mutation_failure is not None:
            return mutation_failure

        # Phase 5 -- Re-review (focused, final automatic cycle)
        stage("Codex re-review")
        rereview, gate_or_fail = _codex_phase("re-review", build_rereview_prompt(task, spec_path, review.findings))
        if gate_or_fail is not None:
            return gate_or_fail
        review_results.append(rereview)
        if not rereview.ok:
            return fail(f"Codex re-review produced uninterpretable output: {rereview.error}")

        if rereview.approved:
            return approve()

        remaining = "; ".join(f.description for f in rereview.findings) or rereview.summary
        return gate(
            GATE_UNRESOLVED_AFTER_REMEDIATION,
            "Codex still returned CHANGES_REQUIRED after one remediation cycle: "
            f"{remaining}",
        )
    except Exception as exc:  # noqa: BLE001 -- SPEC-001 Finding 11, strengthened by the
        # latest Codex review's Finding 5: never propagate a traceback, and
        # never lose already-accumulated evidence (spec, claude_runs,
        # verification_reports, review_results) by building the FAILED
        # result from a fresh, context-free RunResult the way the outer
        # run_workflow() wrapper below is forced to when an exception
        # escapes *this* handler too (e.g. a bug in _base_kwargs itself).
        log(f"[PEOS ERROR] Unhandled exception: {exc}")
        phases.append(PhaseLog(phase="Failure", detail=f"Unhandled exception: {exc}"))
        return RunResult(
            **_base_kwargs(), outcome="FAILED",
            gate_reason=f"Unhandled exception during orchestration: {exc}",
        )
