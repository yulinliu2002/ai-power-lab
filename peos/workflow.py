"""PEOS orchestration -- SPEC-001 Section 6 Workflow, hardened by SPEC-003,
generalized by SPEC-004 (PEOS Autonomous Engineering Loop, V2).

`run_workflow` is the one place the phase sequence, human gates, and the
bounded multi-cycle remediation loop are implemented. Every external
effect -- resolving the governing spec, creating the isolated workspace,
invoking Claude, running local verification, invoking Codex, writing the
Run Ledger -- is injected as a callable or reached through a small,
replaceable module so this file can be unit-tested without ever shelling
out to `claude`, `codex`, real Git, or the real filesystem under
`.peos/` (see tests/test_peos_workflow.py).

Execution-boundary summary (SPEC-001 Finding 1; full rationale in
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
than guessing and continuing. Enumerated Human Gates (SPEC-001 Section 7,
extended by SPEC-004's Model section) -- including an implementation
agent's own structured HUMAN_GATE status -- stop the run with
outcome="HUMAN_GATE". Automation never proceeds past either state on its
own, and an unexpected exception anywhere in this function is itself
caught and converted to a FAILED outcome rather than propagating as a
traceback.

SPEC-004 cycle semantics (load-bearing -- see that spec's Model section):
**cycle 0** is Claude's initial implementation, deterministic
verification, and Codex's initial independent review; it always runs
exactly once and is never counted against `max_cycles`. A **remediation
cycle** is Claude remediation, deterministic re-verification, and
Codex's closure review; remediation cycles are numbered `1..max_cycles`,
and `max_cycles` counts remediation cycles only. `max_cycles=1`
reproduces SPEC-001/SPEC-003's exact observable behavior (one remediation
cycle, no more); the V2 default when `--max-cycles` is omitted is 3, a
deliberate behavior change from V1's effective "1" (Resolved Decision 2).

SPEC-003 (PEOS Agent Authentication Bridge), implementing
docs/decisions/0002: each agent's authentication precondition is checked
immediately before that agent's *first* invocation of a run, not both
checked together up front -- Claude's check (and the workspace creation
it gates) happens before Phase 4; Codex's check happens inside
`_codex_phase` on its first call only, so a run whose Claude credential
is fine but whose Codex credential is missing still completes the Claude
implementation phase before failing closed at the Codex phase, and
Codex's later closure-review calls do not redundantly repeat a check
that already passed earlier in the same run.
"""

from __future__ import annotations

import datetime
import functools
import hashlib
import os
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal

from peos.claude_agent import ClaudeRunResult, run_claude
from peos.codex_agent import CodexReviewResult, run_codex_review
from peos.context import ContextRecoveryResult, run_context_recovery
from peos.diagnostics import build_diagnostic
from peos.findings_register import FindingsRegister, HUMAN_DECISION_REQUIRED
from peos.gitutil import repo_state_fingerprint
from peos.ledger import (
    DEFAULT_RETENTION,
    SCHEMA_VERSION,
    LedgerError,
    LedgerWriter,
    RunLedger,
    cleanup_old_runs,
)
from peos.plan import MAX_MAX_CYCLES, MIN_MAX_CYCLES, PlanArtifact, build_plan
from peos.preflight import (
    InterpreterPreflightResult,
    PreflightResult,
    check_repository_safety,
    check_verification_interpreter,
    detect_mutations,
    hash_governance_artifacts,
)
from peos.prompts import (
    build_implementation_prompt,
    build_remediation_prompt,
    build_rereview_prompt,
    build_review_prompt,
)
from peos.round_packet import ActiveDispute, RoundPacket, StaticContextRef, build_round_packet
from peos.sandbox import (
    CLAUDE_AUTH_ENV_VAR,
    CODEX_AUTH_HOME_ENV_VAR,
    GOVERNANCE_ARTIFACTS,
    IsolatedWorkspace,
    ReconciliationResult,
    WorkspaceError,
    check_claude_auth_preflight,
    check_codex_auth_preflight,
    claude_sandboxed_env,
    codex_sandboxed_env,
    create_isolated_workspace,
    ensure_spec_in_workspace,
    reconcile_workspace_to_repo,
    sandboxed_env,
)
from peos.spec import SpecResolution, resolve_governing_spec
from peos.static_context import StaticContextArtifact, reverify_identity, stage_into_workspace
from peos.verification_plan import VerificationPlan, execute_plan, resolve_verification_plan
from peos.verify import VerificationReport
from peos.workflow_disputes import parse_disputes_from_summary

Outcome = Literal["APPROVED", "HUMAN_GATE", "FAILED"]

ClaudeRunner = Callable[..., ClaudeRunResult]
CodexRunner = Callable[..., CodexReviewResult]
Verifier = Callable[[IsolatedWorkspace, Path, VerificationPlan], VerificationReport]
SpecResolver = Callable[[str, Path, "Path | None"], SpecResolution]
WorkspaceFactory = Callable[[Path, str], IsolatedWorkspace]

DEFAULT_MAX_CYCLES = 3


class _LedgerWriteFailed(RuntimeError):
    """Internal signal only. SPEC-004 Requirement 20: a ledger write
    failure must produce a visible FAILED outcome; raising this and
    letting it reach the existing broad exception handler at the bottom
    of `_run_workflow` is the simplest way to guarantee that without
    special-casing every call site that writes the ledger."""


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
    # SPEC-004 additions.
    context_recovery: ContextRecoveryResult | None = None
    max_cycles: int = 1
    remediation_cycles_run: int = 0
    register: FindingsRegister | None = None
    dispute_log: tuple[str, ...] = field(default_factory=tuple)
    run_id: str | None = None
    ledger_path: str | None = None


def _verification_summary_text(report: VerificationReport) -> str:
    """Render one short, human-readable summary of a completed
    `VerificationReport` for Round Packet delivery (SPEC-004 remediation
    Finding 4) -- e.g. `"PASSED: pytest, lint"` or `"FAILED: typecheck"`
    -- rather than a hardcoded literal like `"passed"` that carries no
    actual evidence about which step(s) ran or failed.
    """
    names = ", ".join(r.name for r in report.results) or "(no verification steps)"
    return f"{'PASSED' if report.passed else 'FAILED'}: {names}"


def _default_verifier(
    workspace: IsolatedWorkspace, repo_root: Path, plan: VerificationPlan, environ: dict | None = None,
) -> VerificationReport:
    """SPEC-003 remediation Finding 2 (MAJOR): `environ` -- the same
    orchestrator environment `_run_workflow` resolves its own agent
    preconditions from, not a second independent read of `os.environ` --
    is threaded through to `execute_plan` so verification's subprocess
    environment is built from (and stripped via) that same environment,
    and so the resolved `PEOS_CODEX_AUTH_HOME` directory (if configured)
    is added to the verification sandbox's filesystem read-deny list.
    Defaults to `os.environ` (via `execute_plan`'s own default) only
    when no `environ` is supplied, matching every other default in this
    module.
    """
    return execute_plan(
        plan, workspace, repo_root,
        sandbox_profile_dir=workspace.path.parent / "sandbox-profiles",
        environ=environ,
    )


# Human Gate IDs. 1-9 match SPEC-001 Section 7 verbatim; 10/11 are
# SPEC-004 additions (Model section, "Human Gate catalog").
GATE_NO_SPEC = "1"
GATE_AMBIGUOUS_SPEC = "2"
GATE_PHYSICS = "3"
GATE_CONTROL_OR_PROTECTION = "4"
GATE_ARCHITECTURE = "5"
GATE_HUMAN_OWNED_FINDING = "6"
GATE_UNRESOLVED_AFTER_REMEDIATION = "8"
GATE_RELEASE_ACTION = "9"
GATE_PERSISTENT_DISPUTE = "10"
GATE_STATIC_CONTEXT_MISSING = "11"

_CLAUDE_GATE_CATEGORY_TO_ID = {
    "physics": GATE_PHYSICS,
    "control": GATE_CONTROL_OR_PROTECTION,
    "protection": GATE_CONTROL_OR_PROTECTION,
    "architecture": GATE_ARCHITECTURE,
    "specification_intent": GATE_AMBIGUOUS_SPEC,
    "ambiguous_specification": GATE_AMBIGUOUS_SPEC,
    "git_release_action": GATE_RELEASE_ACTION,
}


def _evaluate_cycle(
    review: CodexReviewResult,
    origin_review_number: int,
    register: FindingsRegister,
    active_dispute_refs: frozenset,
) -> tuple[str, str | None]:
    """SPEC-004 Requirement 22, Evaluation Precedence stages 3/5/6 (stages
    1/2 -- contract/schema validity and dispute validity -- are already
    enforced by the caller before this is ever reached: `review.ok` is
    guaranteed true, and `active_dispute_refs` is already the validated
    reference set). Returns `(outcome_kind, detail)` where `outcome_kind`
    is one of `"APPROVED"`, `"FAILED"`, `"HUMAN_GATE_6"`,
    `"HUMAN_GATE_10"`, or `"CHANGES_REQUIRED"`.

    Mutates `register` (recording this review's own findings, then
    applying its `historical_finding_dispositions`) as a side effect --
    this is the one place in the run that advances the Outstanding
    Findings Register, by design.
    """
    register.record_review_findings(origin_review_number, review.findings)
    if review.historical_finding_dispositions:
        register.apply_dispositions(review.historical_finding_dispositions)

    # Stage 3a: HUMAN_DECISION_REQUIRED is terminally non-converged and is
    # checked first, unconditionally, before any verdict is interpreted --
    # including an APPROVE verdict in this very same payload.
    if register.has_human_decision_required():
        return "HUMAN_GATE_6", (
            "a historical finding was dispositioned HUMAN_DECISION_REQUIRED and has not "
            "been resolved by a human outside PEOS"
        )

    # Stage 3b: APPROVE is contractually invalid while any historical
    # BLOCKER/MAJOR remains OUTSTANDING -- a contract violation (FAILED),
    # not a loop iteration.
    if review.verdict == "APPROVE" and register.has_outstanding():
        outstanding = ", ".join(str(e.ref) for e in register.outstanding())
        return "FAILED", (
            f"Codex returned APPROVE while the Outstanding Findings Register still has "
            f"BLOCKER/MAJOR entries: {outstanding}. Failing closed rather than trusting "
            "the verdict field alone."
        )

    # Stage 3c: APPROVE combined with an overruled active dispute is also
    # contractually invalid (FAILED). codex_agent.py's own schema
    # validation already rejects this combination before `review.ok` can
    # even be true, so this branch is unreachable today -- kept as the
    # orchestrator-level, defense-in-depth check SPEC-004's own precedence
    # pseudocode calls for.
    if review.verdict == "APPROVE" and active_dispute_refs and review.reviewer_overrules_dispute:
        return "FAILED", "Codex returned APPROVE alongside an overruled active dispute."

    if review.verdict == "APPROVE":
        return "APPROVED", None

    if review.human_decision_findings:
        reasons = "; ".join(f.description for f in review.human_decision_findings)
        return "HUMAN_GATE_6", (
            f"Codex review found issues that require a human-owned engineering decision "
            f"and cannot be auto-remediated: {reasons}"
        )

    if active_dispute_refs and review.reviewer_overrules_dispute:
        return "HUMAN_GATE_10", (
            "Codex's closure review found at least one disputed finding still a real, "
            "unresolved issue after considering the implementer's evidence "
            f"(disputed reference(s): {', '.join(sorted(active_dispute_refs))})."
        )

    return "CHANGES_REQUIRED", None


def _call_codex_runner(
    codex_runner: CodexRunner,
    prompt: str,
    cwd: Path,
    env: dict | None,
    active_dispute_references: frozenset,
    required_ac_ids: frozenset,
) -> CodexReviewResult:
    """Only pass the SPEC-004 keyword arguments when non-empty, so every
    pre-SPEC-004 `codex_runner` fake (the overwhelming majority of
    existing tests, and any caller that injects a plain `(prompt, cwd,
    env=None)` callable) keeps working unmodified -- those sets are
    genuinely always empty for a `--max-cycles 1`/no-dispute/no-AC run
    against this repository's own minimal test fixture specification.
    """
    kwargs: dict = {}
    if active_dispute_references:
        kwargs["active_dispute_references"] = active_dispute_references
    if required_ac_ids:
        kwargs["required_ac_ids"] = required_ac_ids
    return codex_runner(prompt, cwd, env=env, **kwargs)


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
    environ: dict | None = None,
    max_cycles: int | None = None,
) -> RunResult:
    try:
        return _run_workflow(
            task, repo_root, explicit_spec, specs_dir, log,
            spec_resolver, claude_runner, codex_runner, verifier, workspace_factory, environ,
            max_cycles,
        )
    except Exception as exc:  # noqa: BLE001 -- SPEC-001 Finding 11: never propagate a traceback
        # SPEC-004 remediation Finding 8: route the raw exception text
        # through the same sanitized/bounded diagnostic path every other
        # failure in this module uses, rather than interpolating `exc`
        # directly -- an unexpected exception's own message is not
        # trusted free text either (it could, in principle, echo
        # environment/credential content from whatever failed).
        diagnostic = build_diagnostic(structured_message=str(exc), category_override="runtime")
        log(f"[PEOS ERROR] Unhandled exception: {diagnostic}")
        return RunResult(
            task=task, outcome="FAILED",
            phases=(PhaseLog(phase="Failure", detail=diagnostic),),
            gate_reason=f"Unhandled exception during orchestration: {diagnostic}",
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
    environ: dict | None,
    max_cycles: int | None,
) -> RunResult:
    # SPEC-004 Requirement 6/AC-4: an explicitly out-of-range --max-cycles
    # is a hard input-validation failure, checked before anything else --
    # before repository preflight, before Context Recovery, before any
    # state is established. `peos/cli.py` already validates this too (the
    # primary, user-facing enforcement point); this is defense in depth
    # for any direct caller of `run_workflow`.
    if max_cycles is not None and not (MIN_MAX_CYCLES <= max_cycles <= MAX_MAX_CYCLES):
        reason = (
            f"--max-cycles must be between {MIN_MAX_CYCLES} and {MAX_MAX_CYCLES} "
            f"(inclusive), got {max_cycles}."
        )
        log(f"[PEOS ERROR] {reason}")
        return RunResult(
            task=task, outcome="FAILED",
            phases=(PhaseLog(phase="Failure", detail=reason),), gate_reason=reason,
        )

    # SPEC-003: the orchestrator's own ambient environment is where both
    # agents' authentication preconditions are checked and where their
    # credential material is read from -- defaulting to `os.environ`
    # exactly like `sandboxed_env()` already defaults its own `base_env`,
    # and injectable here for the same reason every other external effect
    # in this function is injectable (tests never touch process-wide
    # `os.environ`).
    environ = environ if environ is not None else os.environ
    if verifier is _default_verifier:
        verifier = functools.partial(_default_verifier, environ=environ)
    specs_dir = specs_dir or (repo_root / "docs" / "specifications")
    phases: list[PhaseLog] = []
    claude_runs: list[ClaudeRunResult] = []
    verification_reports: list[VerificationReport] = []
    review_results: list[CodexReviewResult] = []
    remediation_cycles_run = 0
    workspace: IsolatedWorkspace | None = None
    baseline_hashes: dict[str, str] = {}
    vplan: VerificationPlan | None = None
    # SPEC-004 remediation Finding 4: the most recently *completed*
    # deterministic verification report, updated immediately after every
    # `verifier(...)` call -- what a remediation-cycle Round Packet's
    # "latest deterministic verification status/evidence" element must
    # carry (the real last-known result, never a hardcoded `None` once
    # verification has actually run at least once).
    latest_verification: VerificationReport | None = None
    current_spec: object | None = None
    base_env: dict | None = None
    codex_env: dict | None = None
    codex_preflight_checked = False
    context_recovery: ContextRecoveryResult | None = None
    plan: PlanArtifact | None = None
    effective_max_cycles = 1
    register = FindingsRegister()
    dispute_log: list[str] = []
    required_ac_ids: frozenset = frozenset()
    staged_static_artifacts: tuple[StaticContextArtifact, ...] = ()
    preflight: PreflightResult | None = None
    spec_workspace_rel: str | None = None

    # SPEC-004 Requirement 20: one Run Ledger per run, at
    # .peos/runs/<run_id>/ledger.json. `run_id` is also reused as the
    # isolated workspace's identifier, so both artifacts of one run share
    # one identity.
    run_id = uuid.uuid4().hex[:12]
    ledger_writer = LedgerWriter(repo_root, run_id)
    ledger_created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    last_completed_phase = ""

    try:
        cleanup_old_runs(repo_root, active_run_id=run_id, keep=DEFAULT_RETENTION)
    except Exception as exc:  # noqa: BLE001 -- retention hygiene must never block a run.
        log(f"[PEOS] Run Ledger retention cleanup skipped (non-fatal): {exc}")

    def _write_ledger(active_phase: str, outcome: str | None = None, gate_id: str | None = None, gate_reason: str | None = None) -> None:
        nonlocal last_completed_phase
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        governing_spec_identity = ""
        if current_spec is not None and spec_workspace_rel is not None:
            governing_spec_identity = f"{current_spec.path}:{baseline_hashes.get(spec_workspace_rel, '')}"
        ledger = RunLedger(
            run_id=run_id, schema_version=SCHEMA_VERSION,
            created_at=ledger_created_at, updated_at=now,
            max_cycles=effective_max_cycles,
            authoritative_baseline=(preflight.head_commit or "") if preflight else "",
            governing_spec_identity=governing_spec_identity,
            active_phase=active_phase, last_completed_phase=last_completed_phase,
            current_cycle=remediation_cycles_run,
            sanitized_phase_history=tuple(p.phase for p in phases),
            sanitized_register_state=tuple(
                f"{e.ref}:{e.severity}:{'OUTSTANDING' if e.outstanding else (e.disposition or '')}"
                for e in register.all_entries()
            ),
            sanitized_dispute_state=tuple(dispute_log),
            sanitized_verification_summaries=tuple(
                f"round{i}:{'PASS' if r.passed else 'FAIL'}" for i, r in enumerate(verification_reports, start=1)
            ),
            outcome=outcome, gate_id=gate_id, gate_reason=gate_reason,
        )
        try:
            ledger_writer.write(ledger)
        except LedgerError as exc:
            raise _LedgerWriteFailed(f"Run Ledger write failed: {exc}") from exc
        last_completed_phase = active_phase
        if outcome is not None:
            # SPEC-004 remediation Finding 10 (MINOR): the pre-run cleanup
            # at the top of this function only ever protects against an
            # ever-growing backlog *before* this run starts -- with
            # exactly `DEFAULT_RETENTION` pre-existing valid-terminal runs
            # already present, this run's own eventual terminal ledger
            # would otherwise make 21 until some *future* run's pre-run
            # cleanup finally trims it back down. Retention is therefore
            # also enforced immediately after every terminal write, with
            # no run excluded this time (`active_run_id=None`) -- the
            # just-terminalized run is itself now eligible, and survives
            # purely because it is the most recent by `created_at`.
            try:
                cleanup_old_runs(repo_root, active_run_id=None, keep=DEFAULT_RETENTION)
            except Exception as exc:  # noqa: BLE001 -- retention hygiene must never block a run.
                log(f"[PEOS] Run Ledger retention cleanup skipped (non-fatal): {exc}")

    def _safe_terminal_ledger_write(sanitized_reason: str) -> None:
        """SPEC-004 remediation Finding 8 (MAJOR): an unexpected exception
        caught by this function's own broad `except` clauses below must
        not leave the *persisted* ledger stuck at `outcome=None` while
        the in-memory `RunResult` already reports `FAILED` -- a run in
        that state looks, from the ledger alone, like it is still active,
        which also corrupts retention (SPEC-004 remediation Finding 10's
        fix only ever counts a *valid terminal* ledger). Called from the
        exception handlers below, after they have already produced a
        sanitized/bounded diagnostic string (never a raw exception
        object/traceback), to persist exactly that terminal write.

        Deliberately best-effort and non-recursive: if the ledger itself
        is *why* a terminal write cannot be persisted (e.g. the
        filesystem containment/TOCTOU guards in peos/ledger.py reject the
        run directory), this does not retry and does not raise -- it
        logs and returns, so a broken ledger subsystem degrades to "no
        persisted ledger" rather than compounding into a second,
        unhandled failure.
        """
        try:
            _write_ledger(active_phase="Failure", outcome="FAILED", gate_reason=sanitized_reason)
        except _LedgerWriteFailed as exc:
            log(f"[PEOS] Could not persist a terminal ledger after an unexpected exception (non-fatal): {exc}")

    def stage(name: str) -> None:
        log(f"[PEOS] {name}")
        phases.append(PhaseLog(phase=name))
        _write_ledger(active_phase=name)

    def _base_kwargs() -> dict:
        return dict(
            task=task, phases=tuple(phases),
            spec=current_spec,
            claude_runs=tuple(claude_runs),
            verification_reports=tuple(verification_reports),
            verification_plan=vplan,
            review_results=tuple(review_results),
            remediation_performed=remediation_cycles_run > 0,
            workspace_path=str(workspace.path) if workspace is not None else None,
            context_recovery=context_recovery,
            max_cycles=effective_max_cycles,
            remediation_cycles_run=remediation_cycles_run,
            register=register,
            dispute_log=tuple(dispute_log),
            run_id=run_id,
            ledger_path=str(ledger_writer.run_dir / "ledger.json"),
        )

    def _reconcile() -> tuple[ReconciliationResult | None, tuple[str, ...], str | None]:
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
        _write_ledger(active_phase="Human gate", outcome="HUMAN_GATE", gate_id=gate_id, gate_reason=reason)
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
        _write_ledger(active_phase="Failure", outcome="FAILED", gate_reason=reason)
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
            reason = (
                "Codex approved the implementation, but reconciling the isolated "
                f"workspace back onto {repo_root} failed, so the authoritative working "
                f"tree was not safely updated: {recon_error}"
            )
            log(f"[PEOS ERROR] {reason}")
            phases.append(PhaseLog(phase="Failure", detail=reason))
            _write_ledger(active_phase="Failure", outcome="FAILED", gate_reason=reason)
            return RunResult(
                **_base_kwargs(), outcome="FAILED", gate_reason=reason,
                reconciliation=reconciliation, blocked_governance_mutation=blocked,
                reconciliation_error=recon_error,
            )
        _write_ledger(active_phase="Complete", outcome="APPROVED")
        return RunResult(
            **_base_kwargs(), outcome="APPROVED",
            reconciliation=reconciliation, blocked_governance_mutation=blocked,
        )

    try:
        # Phase 0 -- Repository preflight (SPEC-001 Finding 7)
        stage("Repository preflight")
        preflight = check_repository_safety(repo_root)
        if not preflight.ok:
            return fail(f"Repository preflight failed: {preflight.reason}")
        if preflight.dirty:
            log("[PEOS] Repository working tree is dirty; the isolated workspace will carry that state over faithfully.")

        # Phase 0b -- Verification interpreter preflight
        stage("Verification interpreter preflight")
        interpreter_preflight: InterpreterPreflightResult = check_verification_interpreter()
        if not interpreter_preflight.ok:
            return fail(f"Verification interpreter preflight failed: {interpreter_preflight.reason}")

        # Phase 1 -- Context Recovery (SPEC-004 NEW, deterministic, no
        # agent call; runs and is reflected in the eventual report even if
        # Planning never resolves a governing spec -- AC-5).
        stage("Context recovery")
        context_recovery = run_context_recovery(repo_root, specs_dir)
        log(
            f"[PEOS] Context recovered: {len(context_recovery.related_specs)} approved spec(s), "
            f"{len(context_recovery.related_decisions)} decision record(s), "
            f"{len(context_recovery.related_validation_records)} validation record(s)."
        )

        # Phase 2 -- Planning (SPEC-004: renamed, extended Intake; still
        # spec-resolution only -- Human Gates #1/#2 unchanged).
        stage("Planning")
        plan = build_plan(task, specs_dir, explicit_spec, repo_root, spec_resolver=spec_resolver)
        resolution = plan.resolution
        if resolution.spec is None:
            gate_id = GATE_AMBIGUOUS_SPEC if "ambiguous" in (resolution.gate_reason or "").lower() else GATE_NO_SPEC
            return gate(gate_id, resolution.gate_reason or "No governing specification could be resolved.")
        current_spec = resolution.spec
        log(f"[PEOS] Governing specification: {resolution.spec.path}")

        # SPEC-004 remediation Finding 1 (BLOCKER): the governing
        # specification's identity for the rest of this run is fixed,
        # right now, to the hash of the exact bytes `build_plan` just
        # parsed -- never re-derived later from whatever happens to be on
        # disk after the isolated workspace is created. See
        # `_check_governing_spec_identity` below, defined here (rather
        # than after workspace creation, where the old `_check_spec_hash_
        # unchanged` lived) specifically so it can also be called *before*
        # the workspace is created -- closing the exact race this finding
        # describes: Planning parses spec A, the authoritative file
        # changes to B while the workspace is being built, and the
        # workspace/baseline ends up reflecting B while the already-
        # parsed AC set and prompts still describe A.
        governing_spec_content_hash = plan.governing_spec_content_hash

        # SPEC-004 Requirement 21/AC-6/AC-33: Static External Context is
        # resolved during Planning, before any workspace is created or
        # either agent invoked. A containment/safety violation fails
        # closed (never a Human Gate); a missing/wrong-type declared
        # artifact gates to Human Gate #11.
        if plan.static_context.fail_reason is not None:
            return fail(
                "Static external-context artifact failed a containment/safety check "
                f"during Planning: {plan.static_context.fail_reason}"
            )
        if plan.static_context.gate_reason is not None:
            return gate(GATE_STATIC_CONTEXT_MISSING, plan.static_context.gate_reason)

        effective_max_cycles = (
            max_cycles if max_cycles is not None
            else (plan.max_cycles_override if plan.max_cycles_override is not None else DEFAULT_MAX_CYCLES)
        )
        required_ac_ids = frozenset(plan.acceptance_criteria_ids)

        vplan = resolve_verification_plan(repo_root, resolution.spec.path)

        def _check_governing_spec_identity(before_what: str, check_staged: bool) -> RunResult | None:
            """SPEC-004 remediation Finding 1 (BLOCKER): re-verify, fresh,
            immediately before every single consuming Claude/Codex
            invocation of this run -- including the very first one, and
            including the point just before the isolated workspace that
            will carry a staged copy is even created (`check_staged=
            False` then; `check_staged=True` for every call once a
            workspace exists) -- that the governing specification's
            identity still matches `governing_spec_content_hash`, the
            hash Planning computed from the exact bytes it parsed. This
            is never refreshed/replaced from whatever happens to be on
            disk, and a mismatch here is always `FAILED`, never a Human
            Gate (Requirement 1's "9. Do not substitute HUMAN_GATE for
            identity drift").
            """
            if not governing_spec_content_hash:
                return None
            if not resolution.spec.path.is_file():
                return fail(
                    f"The governing specification {resolution.spec.path} is no longer "
                    f"present on disk; failing closed before {before_what}."
                )
            current_hash = hashlib.sha256(resolution.spec.path.read_bytes()).hexdigest()
            if current_hash != governing_spec_content_hash:
                return fail(
                    f"The governing specification's content on disk no longer matches the "
                    f"identity frozen at Planning (before {before_what}); failing closed "
                    "rather than continuing with a mixed/stale specification state "
                    "(CLAUDE.md Integrity Rules)."
                )
            if not check_staged:
                return None
            if workspace is None or spec_workspace_rel is None:
                return fail(
                    "No isolated workspace copy of the governing specification is available "
                    f"to verify before {before_what}; failing closed."
                )
            staged_path = workspace.path / spec_workspace_rel
            if not staged_path.is_file():
                return fail(
                    "The isolated workspace's staged copy of the governing specification is "
                    f"missing; failing closed before {before_what}."
                )
            staged_hash = hashlib.sha256(staged_path.read_bytes()).hexdigest()
            if staged_hash != governing_spec_content_hash:
                return fail(
                    "The isolated workspace's staged copy of the governing specification no "
                    f"longer matches the identity frozen at Planning; failing closed before "
                    f"{before_what}."
                )
            return None

        # SPEC-004 remediation Finding 1: verify the *authoritative* spec
        # still matches the Planning identity one more time right before
        # the isolated workspace (and its own staged copy of the spec) is
        # created -- zero consuming agent invocations have happened yet,
        # so a mismatch here means the workspace is never even built.
        identity_failure = _check_governing_spec_identity("isolated workspace creation", check_staged=False)
        if identity_failure is not None:
            return identity_failure

        # SPEC-003 Requirement 3a/3e: Claude's authentication precondition
        # is checked immediately before Claude's first invocation of this
        # run, and before `create_isolated_workspace` runs.
        stage("Claude authentication preflight")
        claude_auth = check_claude_auth_preflight(environ)
        if not claude_auth.ok:
            return fail(f"Claude Code authentication preflight failed: {claude_auth.reason}")

        try:
            workspace = workspace_factory(repo_root, run_id)
        except WorkspaceError as exc:
            return fail(f"Could not create isolated implementation workspace: {exc}")
        log(f"[PEOS] Isolated workspace: {workspace.path}")
        base_env = sandboxed_env(workspace.home_dir, base_env=environ)
        claude_env = claude_sandboxed_env(base_env, environ[CLAUDE_AUTH_ENV_VAR])

        spec_workspace_rel = ensure_spec_in_workspace(workspace, repo_root, resolution.spec.path)

        # SPEC-004 remediation Finding 1: verify both the authoritative
        # spec *and* the workspace's own freshly-staged copy against the
        # Planning identity before anything derives a "baseline" from
        # either -- the baseline below is then set directly to the frozen
        # Planning hash, never re-read from either copy.
        identity_failure = _check_governing_spec_identity("establishing the governing-spec baseline", check_staged=True)
        if identity_failure is not None:
            return identity_failure

        baseline_hashes = hash_governance_artifacts(repo_root, resolution.spec.path, spec_workspace_rel)
        # Never establish/replace the governing-spec baseline from
        # whatever `hash_governance_artifacts` just re-read off disk --
        # the one authoritative identity for the spec is, and remains,
        # the Planning-time hash already verified above.
        baseline_hashes[spec_workspace_rel] = governing_spec_content_hash

        # SPEC-004 Requirement 21: stage every resolved static-context
        # artifact into the isolated workspace so either agent's ordinary
        # file tools can read it (unlike the Run Ledger, never staged).
        if plan.static_context.artifacts:
            staged_static_artifacts = tuple(
                stage_into_workspace(workspace.path, artifact, repo_root)
                for artifact in plan.static_context.artifacts
            )

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

        def _check_static_context_identity(before_what: str) -> RunResult | None:
            """SPEC-004 Requirement 21/AC-39: identity drift fails the run
            closed, immediately, before the next agent invocation that
            would have consumed the artifact -- never a silent re-hash,
            never a Human Gate.
            """
            for artifact in staged_static_artifacts:
                drift = reverify_identity(artifact, repo_root, workspace.path)
                if not drift.ok:
                    return fail(
                        f"Static external-context artifact identity check failed before "
                        f"{before_what}: {drift.reason}"
                    )
            return None

        def _codex_phase(
            name: str, prompt: str,
            active_dispute_references: frozenset = frozenset(),
        ) -> tuple[CodexReviewResult | None, RunResult | None]:
            """Run one Codex phase with a before/after fingerprint of both
            the authoritative repository and the isolated workspace
            itself (SPEC-001 Finding 3, re-run on every round -- AC-34).

            SPEC-003 Requirement 3b/3c: Codex's authentication
            precondition is checked once, on this function's first call
            in the run -- not redundantly repeated on later calls once it
            has already passed.
            """
            nonlocal codex_env, codex_preflight_checked
            if not codex_preflight_checked:
                stage("Codex authentication preflight")
                codex_auth = check_codex_auth_preflight(environ)
                if not codex_auth.ok:
                    return None, fail(f"Codex authentication preflight failed: {codex_auth.reason}")
                codex_env = codex_sandboxed_env(base_env, environ[CODEX_AUTH_HOME_ENV_VAR])
                codex_preflight_checked = True

            pre_repo = repo_state_fingerprint(repo_root)
            pre_workspace = repo_state_fingerprint(workspace.path)
            result = _call_codex_runner(
                codex_runner, prompt, workspace.path, codex_env,
                active_dispute_references, required_ac_ids,
            )
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

        def _governance_identities() -> tuple[tuple[str, str], ...]:
            # SPEC-004 remediation Finding 4 (closure review): sourced
            # directly from `baseline_hashes`, the orchestrator's own
            # frozen `hash_governance_artifacts` snapshot taken before
            # any agent ran -- never re-hashed from whatever is on disk
            # (or in the workspace) at prompt-build time.
            return tuple(
                (name, baseline_hashes[name]) for name in GOVERNANCE_ARTIFACTS if name in baseline_hashes
            )

        governance_identities = _governance_identities()
        baseline_commit = (preflight.head_commit or "") if preflight else ""

        def _decision_identities() -> tuple[tuple[str, str], ...]:
            decisions_dir = repo_root / "docs" / "decisions"
            identities = []
            for name in context_recovery.related_decisions if context_recovery else ():
                path = decisions_dir / name
                try:
                    identities.append((f"docs/decisions/{name}", hashlib.sha256(path.read_bytes()).hexdigest()))
                except OSError:
                    continue
            return tuple(identities)

        decision_identities = _decision_identities()
        static_context_refs = tuple(
            StaticContextRef(a.declared_path, a.staged_relative_path, a.content_hash)
            for a in staged_static_artifacts
        )

        def _round_packet(cycle_number: int, verification_passed: bool | None, verification_summary: str, active_disputes: tuple[ActiveDispute, ...]) -> RoundPacket:
            return build_round_packet(
                task=task,
                spec_relative_path=spec_workspace_rel or "",
                spec_content_hash=baseline_hashes.get(spec_workspace_rel or "", ""),
                decision_identities=decision_identities,
                cycle_number=cycle_number,
                max_cycles=effective_max_cycles,
                workspace_snapshot_identity=repo_state_fingerprint(workspace.path),
                verification_passed=verification_passed,
                verification_summary=verification_summary,
                register=register,
                active_disputes=active_disputes,
                acceptance_criteria_ids=tuple(sorted(required_ac_ids)),
                static_context_artifacts=static_context_refs,
                governance_identities=governance_identities,
                baseline_commit=baseline_commit,
            )

        # Phase 4 -- Claude implementation (cycle 0)
        stage("Claude implementation")
        identity_failure = _check_governing_spec_identity("Claude implementation", check_staged=True)
        if identity_failure is not None:
            return identity_failure
        # SPEC-004 remediation Finding 5 (MAJOR): re-verify every staged
        # static-context artifact's identity before this run's *very
        # first* consuming invocation too -- not only before later Codex/
        # remediation rounds, where this check already ran. Without this,
        # drift between Planning (where the artifact was pinned) and this
        # point could already have been consumed by cycle 0's Claude call
        # before any check caught it.
        static_context_failure = _check_static_context_identity("Claude implementation")
        if static_context_failure is not None:
            return static_context_failure
        # SPEC-004 remediation Finding 4 (MAJOR): cycle 0's Claude call
        # receives a real Round Packet too -- register/disputes are
        # empty by construction (nothing has happened yet) and
        # verification_passed is explicitly None (no verification has
        # run yet), but every other element (spec identity, governance/
        # decision identities, workspace snapshot identity, the complete
        # AC set, static-context identities) is real and rendered into
        # the prompt, not merely held in this dataclass.
        impl_packet = _round_packet(0, None, "", ())
        impl_result = claude_runner(
            build_implementation_prompt(task, spec_workspace_rel, impl_packet), workspace.path, env=claude_env,
        )
        claude_runs.append(impl_result)
        if impl_result.status == "HUMAN_GATE":
            gate_id = _CLAUDE_GATE_CATEGORY_TO_ID.get(impl_result.gate_category or "", GATE_HUMAN_OWNED_FINDING)
            return gate(gate_id, f"Claude escalated during implementation [{impl_result.gate_category}]: {impl_result.gate_reason}")
        if not impl_result.ok:
            return fail(f"Claude implementation did not complete successfully: {impl_result.error}")

        mutation_failure = _check_governance_mutation("implementation")
        if mutation_failure is not None:
            return mutation_failure

        # Phase 5 -- Local verification (cycle 0)
        stage("Local verification")
        identity_failure = _check_governing_spec_identity("local verification", check_staged=True)
        if identity_failure is not None:
            return identity_failure
        vreport = verifier(workspace, repo_root, vplan)
        verification_reports.append(vreport)
        latest_verification = vreport
        if not vreport.passed:
            failing = ", ".join(r.name for r in vreport.failures)
            return fail(f"Local verification failed after implementation: {failing}")

        mutation_failure = _check_governance_mutation("post-implementation verification")
        if mutation_failure is not None:
            return mutation_failure
        identity_failure = _check_governing_spec_identity("Codex independent review", check_staged=True)
        if identity_failure is not None:
            return identity_failure
        static_context_failure = _check_static_context_identity("Codex independent review")
        if static_context_failure is not None:
            return static_context_failure

        # Phase 6 -- Codex independent review (cycle 0)
        stage("Codex independent review")
        # SPEC-004 remediation Finding 4: cycle 0's Codex call also
        # receives a real Round Packet, now carrying the just-completed
        # verification result (register/disputes still empty -- this is
        # the initial review, before any historical finding exists).
        review_packet = _round_packet(0, vreport.passed, _verification_summary_text(vreport), ())
        review, gate_or_fail = _codex_phase(
            "independent review", build_review_prompt(task, spec_workspace_rel, review_packet),
        )
        if gate_or_fail is not None:
            return gate_or_fail
        review_results.append(review)
        if not review.ok:
            return fail(f"Codex review produced uninterpretable output: {review.error}")

        outcome_kind, detail = _evaluate_cycle(review, 0, register, frozenset())
        if outcome_kind == "APPROVED":
            return approve()
        if outcome_kind == "FAILED":
            return fail(detail or "Codex review payload failed convergence evaluation.")
        if outcome_kind == "HUMAN_GATE_6":
            return gate(GATE_HUMAN_OWNED_FINDING, detail or "Codex review requires a human-owned decision.")
        # outcome_kind == "CHANGES_REQUIRED" (HUMAN_GATE_10 is unreachable
        # at cycle 0 -- no dispute can exist before any remediation runs).

        # SPEC-004 Phase 7-9 -- bounded remediation-cycle loop
        # (remediation cycles 1..effective_max_cycles). This is a direct
        # generalization of SPEC-001's unrolled single remediation cycle:
        # effective_max_cycles=1 reproduces that exact behavior.
        for remediation_cycle in range(1, effective_max_cycles + 1):
            remediation_cycles_run = remediation_cycle
            cycle_label = f"{remediation_cycle}/{effective_max_cycles}"

            stage(f"Claude remediation (remediation cycle {cycle_label})")
            identity_failure = _check_governing_spec_identity(
                f"Claude remediation cycle {remediation_cycle}", check_staged=True,
            )
            if identity_failure is not None:
                return identity_failure
            static_context_failure = _check_static_context_identity(f"Claude remediation cycle {remediation_cycle}")
            if static_context_failure is not None:
                return static_context_failure

            # SPEC-004 remediation Finding 4 (MAJOR): this round's packet
            # must carry the *actual* latest verification result once one
            # exists -- `latest_verification` was set after cycle 0's own
            # verification (and, for remediation_cycle > 1, after the
            # previous remediation cycle's) -- never a hardcoded `None`
            # that misrepresents verification as never having happened.
            remediation_packet = _round_packet(
                remediation_cycle,
                latest_verification.passed if latest_verification is not None else None,
                _verification_summary_text(latest_verification) if latest_verification is not None else "",
                (),
            )
            remediation_result = claude_runner(
                build_remediation_prompt(task, spec_workspace_rel, remediation_packet), workspace.path, env=claude_env,
            )
            claude_runs.append(remediation_result)
            if remediation_result.status == "HUMAN_GATE":
                gate_id = _CLAUDE_GATE_CATEGORY_TO_ID.get(remediation_result.gate_category or "", GATE_HUMAN_OWNED_FINDING)
                return gate(gate_id, f"Claude escalated during remediation [{remediation_result.gate_category}]: {remediation_result.gate_reason}")
            if not remediation_result.ok:
                return fail(f"Claude remediation did not complete successfully: {remediation_result.error}")

            # SPEC-004 Requirement 8 (AC-22/AC-23): parse any DISPUTE[...]
            # lines in this cycle's remediation summary against the
            # register as it stood entering this cycle. SPEC-004
            # remediation Finding 6: parsed from `dispute_attempt_lines`
            # (extracted from the *raw* summary before its own
            # destructive whole-string bound -- see
            # peos/workflow_disputes.py), never by re-splitting the
            # already-sanitized `summary` field, which could have lost a
            # dispute attempt near its start to that truncation.
            disputes, dispute_error = parse_disputes_from_summary(remediation_result.dispute_attempt_lines, register)
            if dispute_error is not None:
                return fail(
                    f"Claude's remediation cycle {remediation_cycle} summary contained an "
                    f"invalid DISPUTE[...] line: {dispute_error.reason} (line: {dispute_error.line!r})"
                )
            active_dispute_refs = frozenset(d.reference for d in disputes)
            for d in disputes:
                dispute_log.append(f"DISPUTE[{d.reference}] raised in remediation cycle {remediation_cycle}: {d.evidence}")

            mutation_failure = _check_governance_mutation("remediation")
            if mutation_failure is not None:
                return mutation_failure

            stage(f"Local verification (remediation cycle {cycle_label})")
            identity_failure = _check_governing_spec_identity(
                f"verification after remediation cycle {remediation_cycle}", check_staged=True,
            )
            if identity_failure is not None:
                return identity_failure
            vreport_n = verifier(workspace, repo_root, vplan)
            verification_reports.append(vreport_n)
            latest_verification = vreport_n
            if not vreport_n.passed:
                # SPEC-004 AC-26: a verification failure on a remediation
                # cycle is FAILED immediately -- never a Codex call for
                # this cycle, never counted toward/confused with
                # iteration exhaustion.
                failing = ", ".join(r.name for r in vreport_n.failures)
                return fail(f"Local verification failed after remediation cycle {remediation_cycle}: {failing}")

            mutation_failure = _check_governance_mutation(f"post-remediation-cycle-{remediation_cycle} verification")
            if mutation_failure is not None:
                return mutation_failure
            identity_failure = _check_governing_spec_identity(
                f"Codex closure review (remediation cycle {remediation_cycle})", check_staged=True,
            )
            if identity_failure is not None:
                return identity_failure
            static_context_failure = _check_static_context_identity(f"Codex closure review (remediation cycle {remediation_cycle})")
            if static_context_failure is not None:
                return static_context_failure

            stage(f"Codex closure review (remediation cycle {cycle_label})")
            active_disputes_for_packet = tuple(
                ActiveDispute(reference=d.reference, evidence=d.evidence, raised_in_remediation_cycle=remediation_cycle)
                for d in disputes
            )
            closure_packet = _round_packet(
                remediation_cycle, vreport_n.passed, _verification_summary_text(vreport_n), active_disputes_for_packet,
            )
            closure_review, gate_or_fail = _codex_phase(
                f"closure review (remediation cycle {remediation_cycle})",
                build_rereview_prompt(task, spec_workspace_rel, closure_packet),
                active_dispute_references=active_dispute_refs,
            )
            if gate_or_fail is not None:
                return gate_or_fail
            review_results.append(closure_review)
            if not closure_review.ok:
                return fail(f"Codex closure review produced uninterpretable output: {closure_review.error}")

            if active_dispute_refs:
                verdict_word = "overruled" if closure_review.reviewer_overrules_dispute else "conceded"
                dispute_log.append(
                    f"Codex {verdict_word} dispute(s) {sorted(active_dispute_refs)} in remediation cycle {remediation_cycle}"
                )

            outcome_kind, detail = _evaluate_cycle(closure_review, remediation_cycle, register, active_dispute_refs)
            if outcome_kind == "APPROVED":
                return approve()
            if outcome_kind == "FAILED":
                return fail(detail or "Codex closure review payload failed convergence evaluation.")
            if outcome_kind == "HUMAN_GATE_6":
                return gate(GATE_HUMAN_OWNED_FINDING, detail or "Codex closure review requires a human-owned decision.")
            if outcome_kind == "HUMAN_GATE_10":
                return gate(GATE_PERSISTENT_DISPUTE, detail or "Codex's closure review overruled an active dispute.")

            if remediation_cycle == effective_max_cycles:
                outstanding = ", ".join(str(e.ref) for e in register.outstanding()) or "(none)"
                return gate(
                    GATE_UNRESOLVED_AFTER_REMEDIATION,
                    f"Codex still returned CHANGES_REQUIRED after {effective_max_cycles} remediation "
                    f"cycle(s) (the configured max_cycles): outstanding register entries: {outstanding}; "
                    f"active disputes: {sorted(active_dispute_refs) or '(none)'}."
                )
            # Otherwise: CHANGES_REQUIRED with budget remaining -- loop.

        # Unreachable: the loop above always returns on its last
        # iteration (either converging or hitting GATE_UNRESOLVED_AFTER_REMEDIATION).
        return fail("Internal error: remediation loop exited without a terminal outcome.")
    except _LedgerWriteFailed as exc:
        # SPEC-004 remediation Finding 8: the ledger subsystem itself is
        # what failed here -- `_safe_terminal_ledger_write` would just
        # hit the identical failure again, so it is deliberately not
        # called on this path (the "ledger-write failure does not
        # recurse" requirement); the sanitized diagnostic still becomes
        # this run's FAILED gate_reason even though it could not be
        # persisted.
        diagnostic = build_diagnostic(structured_message=str(exc), category_override="runtime")
        log(f"[PEOS ERROR] {diagnostic}")
        phases.append(PhaseLog(phase="Failure", detail=diagnostic))
        return RunResult(**_base_kwargs(), outcome="FAILED", gate_reason=diagnostic)
    except Exception as exc:  # noqa: BLE001 -- SPEC-001 Finding 11, strengthened by SPEC-004:
        # never propagate a traceback, and never lose already-accumulated
        # evidence by building the FAILED result from a fresh,
        # context-free RunResult.
        #
        # SPEC-004 remediation Finding 8 (MAJOR): also persist this
        # terminal outcome to the Run Ledger itself (not only the
        # in-memory RunResult returned below) -- otherwise a run that hit
        # an unexpected exception here reports FAILED to its caller while
        # its on-disk ledger is left at whatever non-terminal
        # `outcome=None` phase it last reached, which both misrepresents
        # the run as still active and breaks retention (SPEC-004
        # remediation Finding 10). The raw exception is never persisted
        # or logged directly -- `build_diagnostic` redacts/bounds it
        # first, exactly like every other failure path in this module.
        diagnostic = build_diagnostic(structured_message=str(exc), category_override="runtime")
        reason = f"Unhandled exception during orchestration: {diagnostic}"
        log(f"[PEOS ERROR] Unhandled exception: {diagnostic}")
        phases.append(PhaseLog(phase="Failure", detail=reason))
        _safe_terminal_ledger_write(reason)
        return RunResult(**_base_kwargs(), outcome="FAILED", gate_reason=reason)
