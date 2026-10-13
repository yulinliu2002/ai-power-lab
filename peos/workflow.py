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

from peos.checkpoint import CheckpointManager, RuntimeEvidenceRefSnapshot
from peos.claude_agent import ClaudeRunResult, run_claude
from peos.codex_agent import CodexReviewResult, run_codex_review
from peos.context import ContextRecoveryResult, run_context_recovery
from peos.diagnostics import build_diagnostic, classify_transient_failure
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
from peos.round_packet import (
    ActiveDispute,
    RegisterEntrySnapshot,
    RoundPacket,
    RuntimeCheckSummary,
    RuntimeEvidenceRef,
    StaticContextRef,
    build_round_packet,
)
from peos.run_lock import RunLock, RunLockError, acquire_for_new_task
from peos.runtime_evidence import reverify_evidence_identity
from peos.runtime_verification import RuntimeVerificationOutcome, run_runtime_verification
from peos.sandbox import (
    CLAUDE_AUTH_ENV_VAR,
    CODEX_AUTH_HOME_ENV_VAR,
    GOVERNANCE_ARTIFACTS,
    IsolatedWorkspace,
    ReconciliationResult,
    WorkspaceError,
    candidate_root_for_run,
    check_claude_auth_preflight,
    check_codex_auth_preflight,
    claude_sandboxed_env,
    codex_sandboxed_env,
    create_isolated_workspace,
    discard_workspace,
    ensure_spec_in_workspace,
    reconcile_workspace_to_repo,
    sandboxed_env,
)
from peos.spec import SpecResolution, resolve_governing_spec
from peos.static_context import StaticContextArtifact, reverify_identity, stage_into_workspace
from peos.verification_plan import VerificationPlan, execute_plan, resolve_verification_plan
from peos.verify import VerificationReport
from peos.workflow_disputes import parse_disputes_from_summary

# SPEC-007 Decision 9: MAX_CYCLES_REACHED is a distinct terminal outcome,
# never HUMAN_GATE -- supersedes SPEC-004's GATE_UNRESOLVED_AFTER_
# REMEDIATION encoding of convergence exhaustion (see "max_cycles_reached"
# below and the removed call site in the remediation loop).
Outcome = Literal["APPROVED", "HUMAN_GATE", "FAILED", "MAX_CYCLES_REACHED", "PAUSED_RETRYABLE"]

ClaudeRunner = Callable[..., ClaudeRunResult]
CodexRunner = Callable[..., CodexReviewResult]
Verifier = Callable[[IsolatedWorkspace, Path, VerificationPlan], VerificationReport]
SpecResolver = Callable[[str, Path, "Path | None"], SpecResolution]
WorkspaceFactory = Callable[[Path, str], IsolatedWorkspace]

DEFAULT_MAX_CYCLES = 3


def _cycle_zero_already_completed(seed) -> bool:
    """SPEC-007 resume re-entry: `True` iff cycle 0's `CODEX_INDEPENDENT_
    REVIEW` phase had already reached `COMPLETED` by the time of
    interruption -- i.e. resume must skip cycle 0 entirely and continue
    straight into the remediation loop, never redoing a Claude call
    whose result was already durably recorded (AC-006).

    Codex implementation review (confirmed, major): an earlier revision
    of this function tried to disambiguate `LOCAL_VERIFICATION`/
    `RUNTIME_VERIFICATION` (the one phase *name* shared between cycle 0
    and every remediation cycle alike) via "the immediately-preceding
    completed phase" -- which is wrong specifically for the case where
    cycle 0's own `LOCAL_VERIFICATION` has just completed and
    `RUNTIME_VERIFICATION` is `ENTERED`: `last_safely_completed_phase`
    then reads `"LOCAL_VERIFICATION"`, which that heuristic's exclusion
    list did not recognize as "still cycle 0", wrongly concluding cycle 0
    had already completed. **Fixed with a genuinely unambiguous signal
    already in the schema**: `codex_review_verdict_history`'s first entry
    is written *only* by `CODEX_INDEPENDENT_REVIEW`'s own `COMPLETED`
    write (see the cycle-0 block below) -- before that entry exists,
    cycle 0 cannot have completed, by construction; once it exists,
    cycle 0 is done, regardless of whatever phase/state is currently
    `active_phase`/`active_phase_state`.
    """
    return len(seed.codex_review_verdict_history) >= 1


def _cycle_zero_claude_already_completed(seed) -> bool:
    """SPEC-007 resume re-entry, within cycle 0 specifically (only ever
    called once the caller has already established cycle 0 is *not*
    fully done, i.e. `not _cycle_zero_already_completed(seed)` -- so
    `active_phase` can only be one of `PLANNING`, `CLAUDE_IMPLEMENTATION`,
    `LOCAL_VERIFICATION`, `RUNTIME_VERIFICATION`, or a not-yet-`COMPLETED`
    `CODEX_INDEPENDENT_REVIEW`, with no ambiguity left to resolve).
    `True` iff `CLAUDE_IMPLEMENTATION` had already reached `COMPLETED` --
    resume must then skip re-issuing that Claude call, while still
    rerunning verification and obtaining a fresh Codex review (AC-003/
    AC-005). Codex implementation review (confirmed, major): an earlier
    revision had no such middle state at all -- it either skipped all of
    cycle 0, or redid all of it including a completed Claude call,
    violating AC-003/AC-006 whenever interruption landed during
    verification or the independent review specifically.
    """
    if seed.active_phase == "CLAUDE_IMPLEMENTATION":
        return seed.active_phase_state == "COMPLETED"
    return seed.active_phase in ("LOCAL_VERIFICATION", "RUNTIME_VERIFICATION", "CODEX_INDEPENDENT_REVIEW")


def _remediation_claude_already_completed(seed) -> bool:
    """The `CLAUDE_REMEDIATION` analogue of `_cycle_zero_claude_already_
    completed`, for the one specific remediation cycle currently being
    resumed (`resume_starting_cycle = seed.current_cycle + 1` -- only
    safe to call for that one cycle, see its call site).

    Codex closure review (confirmed, major): an earlier revision treated
    `active_phase == "CODEX_CLOSURE_REVIEW"` as unconditional proof that
    `resume_starting_cycle`'s own Claude call had completed -- true only
    while that closure review is still `ENTERED` (it then belongs to
    `resume_starting_cycle` itself, since `current_cycle` has not yet
    advanced to reflect it). Once it reaches `COMPLETED`,
    `current_cycle` *has* advanced, so that same closure review now
    belongs to `resume_starting_cycle - 1` -- a different, already-
    finished cycle -- and `resume_starting_cycle` is actually a brand
    new cycle whose Claude call was never even issued. Treating it as
    "already completed" in that case would wrongly skip a cycle's only
    Claude call entirely.
    """
    if seed.active_phase == "CLAUDE_REMEDIATION":
        return seed.active_phase_state == "COMPLETED"
    if seed.active_phase in ("LOCAL_VERIFICATION", "RUNTIME_VERIFICATION"):
        return True
    if seed.active_phase == "CODEX_CLOSURE_REVIEW":
        return seed.active_phase_state == "ENTERED"
    return False


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
    # SPEC-006 addition: every round's Runtime Verification outcome, in
    # round order -- cycle 0 first, then each remediation cycle that ran
    # one -- never only the latest, so the Delivery Report (peos/report.py)
    # can show every round's own evidence, not just the final one.
    runtime_verification_history: tuple["RuntimeVerificationOutcome", ...] = field(default_factory=tuple)


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
# SPEC-006 Section 15: a declared Runtime Verification check that cannot
# be deterministically interpreted (an unsupported `kind`, a missing
# required parameter, or an orphaned `ac=` reference) -- a decision-
# bearing specification defect, never a capability gap (those are
# execution-integrity `FAILED`, per SPEC-006 Section 6/15).
GATE_RUNTIME_CHECK_UNSUPPORTED = "12"

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
    runtime_evidenced_ac_status: dict | None = None,
) -> CodexReviewResult:
    """Only pass the SPEC-004/SPEC-006 keyword arguments when non-empty,
    so every pre-SPEC-004/SPEC-006 `codex_runner` fake (the overwhelming
    majority of existing tests, and any caller that injects a plain
    `(prompt, cwd, env=None)` callable) keeps working unmodified -- those
    sets are genuinely always empty for a `--max-cycles 1`/no-dispute/
    no-AC/no-runtime-check run against this repository's own minimal test
    fixture specification.
    """
    kwargs: dict = {}
    if active_dispute_references:
        kwargs["active_dispute_references"] = active_dispute_references
    if required_ac_ids:
        kwargs["required_ac_ids"] = required_ac_ids
    if runtime_evidenced_ac_status:
        kwargs["runtime_evidenced_ac_status"] = runtime_evidenced_ac_status
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
    runtime_verifier: Callable[..., RuntimeVerificationOutcome] = run_runtime_verification,
    resume_seed=None,
    resume_lock: RunLock | None = None,
) -> RunResult:
    # SPEC-007 "Workspace Lifecycle and One-Run-Per-Repository": the
    # shared run lock is acquired deep inside `_run_workflow` (immediately
    # after `run_id` is generated, before any other run state is
    # created) but must be released on *every* exit path from this
    # function, including an exception `_run_workflow` itself does not
    # catch -- a mutable one-element list, populated the instant
    # acquisition succeeds, lets this outer `finally` release it
    # regardless of how `_run_workflow` returns or raises, without
    # reindenting that function's own large, pre-existing try/except
    # structure around a second try/finally level.
    #
    # `resume_seed`/`resume_lock` (SPEC-007 `peos/resume.py`): a resumed
    # run's lock was already acquired by `acquire_for_resume` before its
    # own preflight ran (resume preflight itself needs the lock held) --
    # `lock_holder` is pre-populated with it here instead of acquiring a
    # fresh one via `acquire_for_new_task`.
    lock_holder: list[RunLock] = [resume_lock] if resume_lock is not None else []
    try:
        return _run_workflow(
            task, repo_root, explicit_spec, specs_dir, log,
            spec_resolver, claude_runner, codex_runner, verifier, workspace_factory, environ,
            max_cycles, runtime_verifier, lock_holder, resume_seed,
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
    finally:
        if lock_holder:
            try:
                lock_holder[0].release()
            except Exception:  # noqa: BLE001 -- releasing the lock must never raise past this point.
                pass


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
    runtime_verifier: Callable[..., RuntimeVerificationOutcome] = run_runtime_verification,
    lock_holder: list | None = None,
    resume_seed=None,
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
    remediation_cycles_run = resume_seed.current_cycle if resume_seed is not None else 0
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
    if resume_seed is not None:
        # SPEC-007 resume re-entry: rebuild the Outstanding Findings
        # Register and dispute log from the durably-recorded checkpoint
        # snapshot, never from any prior subprocess's transcript (there
        # is none -- this is a fresh process).
        from peos.findings_register import FindingRef, RegisterEntry
        for snapshot in resume_seed.findings_register_entries:
            ref = FindingRef.parse(snapshot.reference)
            if ref is None:
                continue
            register.entries[snapshot.reference] = RegisterEntry(
                ref=ref, severity=snapshot.severity, description=snapshot.description,
                outstanding=snapshot.outstanding, disposition=snapshot.disposition,
                disposition_note=snapshot.disposition_note,
                human_decision_required_ever=snapshot.human_decision_required_ever,
            )
    dispute_log: list[str] = list(resume_seed.dispute_log) if resume_seed is not None else []
    required_ac_ids: frozenset = frozenset()
    staged_static_artifacts: tuple[StaticContextArtifact, ...] = ()
    preflight: PreflightResult | None = None
    spec_workspace_rel: str | None = None
    # SPEC-006: the most recently completed round's Runtime Verification
    # outcome -- consumed by `_round_packet`/`_runtime_evidenced_ac_status`
    # for the very next Codex call, and reset to `None` at the start of
    # every round before that round's own Runtime Verification runs, so a
    # round that declares no checks never carries a prior round's
    # evidence forward by accident.
    runtime_outcome: RuntimeVerificationOutcome | None = None
    runtime_verification_history: list[RuntimeVerificationOutcome] = []

    # SPEC-004 Requirement 20: one Run Ledger per run, at
    # .peos/runs/<run_id>/ledger.json. `run_id` is also reused as the
    # isolated workspace's identifier, so both artifacts of one run share
    # one identity.
    if resume_seed is not None:
        # SPEC-007 resume re-entry: `run_id` is the interrupted run's own
        # id, and the shared run lock was already acquired by
        # `peos.run_lock.acquire_for_resume` *before* this call (resume
        # preflight itself needs the lock held) -- `lock_holder` was
        # pre-populated with it by `run_workflow`, above. The checkpoint
        # manager is seeded from the resumed checkpoint, not given a
        # fresh PLANNING bootstrap write, and `require_fresh=False` lets
        # it tolerantly reuse this run's own, already-existing directory.
        run_id = resume_seed.run_id
        ledger_writer = LedgerWriter(repo_root, run_id)
        ledger_created_at = resume_seed.created_at
        last_completed_phase = resume_seed.last_safely_completed_phase
        checkpoint = CheckpointManager(repo_root, run_id, require_fresh=False)
        checkpoint.seed_from(resume_seed)
        checkpoint.load_resume_generation(resume_seed.resume_generation + 1)
    else:
        run_id = uuid.uuid4().hex[:12]

        # SPEC-007 "Workspace Lifecycle and One-Run-Per-Repository": the
        # shared run lock is acquired immediately after `run_id` is
        # generated, before any other run state exists -- a failure here
        # (another run is active/paused, or genuinely still bootstrapping)
        # fails this attempt closed immediately, before Planning, naming
        # the blocking run, with no ledger/checkpoint ever created for
        # this attempted `run_id` (AC-034/035/059/060/061).
        try:
            run_lock = acquire_for_new_task(repo_root, run_id)
        except RunLockError as exc:
            reason = f"Could not start a new PEOS run: {exc}"
            log(f"[PEOS GATE] {reason}")
            return RunResult(task=task, outcome="FAILED", gate_reason=reason)
        if lock_holder is not None:
            lock_holder.append(run_lock)

        ledger_writer = LedgerWriter(repo_root, run_id)
        ledger_created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        last_completed_phase = ""

        # SPEC-007 "Durable Phase-State Semantics" §PLANNING: the
        # checkpoint's own **first** write -- PLANNING's `ENTERED` record
        # -- happens here, immediately after lock acquisition and before
        # any spec resolution or other Planning work begins, carrying
        # only the raw inputs already known at this instant. `peos/
        # resume.py`'s bootstrap-gap handling depends on this ordering: a
        # lock naming a `run_id` with no checkpoint behind it at all is
        # exactly "an interruption in this narrow window."
        checkpoint = CheckpointManager(repo_root, run_id)
        checkpoint.enter(
            "PLANNING",
            task=task,
            governing_spec_source="explicit_path" if explicit_spec is not None else "auto_detected",
            governing_spec_original_path=str(explicit_spec) if explicit_spec is not None else "",
        )

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
            runtime_verification_history=tuple(runtime_verification_history),
        )

    def _reconcile() -> tuple[ReconciliationResult | None, tuple[str, ...], str | None]:
        if workspace is None:
            return None, (), None
        checkpoint.enter("RECONCILIATION")

        # SPEC-007 "Reconciliation Crash-Safety": if reconciliation
        # itself was interrupted before this execution (the checkpoint's
        # `active_phase` was still `RECONCILIATION` at the moment of
        # interruption), reuse that *exact* durable manifest -- never
        # rebuild one fresh. Codex implementation review (confirmed,
        # major): rebuilding fresh recomputes `original_content_hash`
        # from the authoritative file's *current* state, which can
        # already reflect a partially-applied prior attempt (or any
        # other change made during the pause) -- silently adopting that
        # as the new "original" and losing the ability to ever detect it
        # as unexplained interference. Reusing the old manifest's own
        # recorded hashes, unchanged, is what lets
        # `apply_reconciliation_operation`'s three-way classification
        # actually catch that case.
        resumed_manifest = (
            resume_seed.reconciliation_manifest
            if resume_seed is not None and resume_seed.active_phase == "RECONCILIATION" and resume_seed.reconciliation_manifest
            else None
        )
        running_manifest: list = list(resumed_manifest) if resumed_manifest is not None else []

        def _on_manifest_built(manifest) -> None:
            running_manifest[:] = list(manifest)
            checkpoint.enter("RECONCILIATION", reconciliation_manifest=tuple(running_manifest))

        def _on_operation_applied(op) -> None:
            # SPEC-007 "Reconciliation Crash-Safety" step 2: each applied
            # operation's `applied=True` update is its own full, atomic
            # checkpoint write -- the accepted cost of per-operation
            # crash-safety (an interruption between any two operations
            # still has a durable, exact record of which ones already
            # completed).
            for i, existing in enumerate(running_manifest):
                if existing.relative_path == op.relative_path and existing.action == op.action:
                    running_manifest[i] = op
                    break
            checkpoint.enter("RECONCILIATION", reconciliation_manifest=tuple(running_manifest))

        try:
            result = reconcile_workspace_to_repo(
                workspace, repo_root, protected_relative_paths=frozenset(baseline_hashes.keys()),
                run_id=run_id, manifest=resumed_manifest,
                on_manifest_built=_on_manifest_built, on_operation_applied=_on_operation_applied,
            )
        except Exception as exc:  # noqa: BLE001
            log(f"[PEOS ERROR] Could not reconcile isolated workspace back to {repo_root}: {exc}")
            return None, (), str(exc)
        checkpoint.complete("RECONCILIATION", reconciliation_manifest=result.manifest)
        if result.blocked_governance_changes:
            log(
                "[PEOS GATE] Governance artifact(s) were modified inside the isolated "
                f"workspace and were NOT copied back: {', '.join(result.blocked_governance_changes)}"
            )
        return result, result.blocked_governance_changes, None

    def _discard_candidate_workspace() -> None:
        # SPEC-007 "Workspace Lifecycle": discarded immediately upon
        # reaching any terminal outcome, as part of that same
        # transition, while ledger/checkpoint/evidence are retained
        # under the existing cap. Best-effort -- never turns a
        # successfully-determined terminal outcome into a different one.
        #
        # Safety guard: `discard_workspace`'s real, unmodified
        # implementation is `shutil.rmtree(workspace.path.parent, ...)`,
        # which is only safe when `workspace.path` is actually nested
        # under this run's own dedicated `candidate/` directory (true for
        # every real `create_isolated_workspace` call). A test (or any
        # future caller) that injects a `workspace_factory` violating
        # that convention -- e.g. one that reuses `repo_root` itself as
        # "the workspace" -- must never have this call blindly `rmtree`
        # whatever `workspace.path`'s *actual* parent happens to be; this
        # containment check is what makes that structurally impossible
        # rather than merely unlikely.
        if workspace is None:
            return
        try:
            expected_candidate_root = candidate_root_for_run(repo_root, run_id).resolve()
            if workspace.path.parent.resolve() != expected_candidate_root:
                log(
                    "[PEOS] Skipping candidate workspace discard: workspace.path is not nested "
                    f"under this run's expected candidate/ directory ({workspace.path!r}) -- "
                    "never the case for the real create_isolated_workspace, so this is a non-fatal "
                    "no-op here (e.g. a test's injected workspace_factory)."
                )
                return
            discard_workspace(workspace)
        except Exception as exc:  # noqa: BLE001
            log(f"[PEOS] Could not discard the candidate workspace (non-fatal): {exc}")

    def gate(gate_id: str, reason: str) -> RunResult:
        log(f"[PEOS GATE] {reason}")
        phases.append(PhaseLog(phase="Human gate", detail=reason))
        _write_ledger(active_phase="Human gate", outcome="HUMAN_GATE", gate_id=gate_id, gate_reason=reason)
        reconciliation, blocked, recon_error = _reconcile()
        checkpoint.terminal("HUMAN_GATE", gate_id=gate_id, gate_reason=reason)
        _discard_candidate_workspace()
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
        checkpoint.terminal("FAILED", gate_reason=reason)
        _discard_candidate_workspace()
        return RunResult(
            **_base_kwargs(), outcome="FAILED", gate_reason=reason,
            reconciliation=reconciliation, blocked_governance_mutation=blocked,
            reconciliation_error=recon_error,
        )

    def max_cycles_reached(reason: str) -> RunResult:
        """SPEC-007 Decision 9: a distinct terminal outcome, never
        `HUMAN_GATE` -- supersedes SPEC-004's `GATE_UNRESOLVED_AFTER_
        REMEDIATION` encoding of convergence exhaustion (AC-043)."""
        log(f"[PEOS] Remediation budget exhausted without convergence: {reason}")
        phases.append(PhaseLog(phase="Max cycles reached", detail=reason))
        _write_ledger(active_phase="Max cycles reached", outcome="MAX_CYCLES_REACHED", gate_reason=reason)
        reconciliation, blocked, recon_error = _reconcile()
        checkpoint.terminal("MAX_CYCLES_REACHED", gate_reason=reason)
        _discard_candidate_workspace()
        return RunResult(
            **_base_kwargs(), outcome="MAX_CYCLES_REACHED", gate_reason=reason,
            reconciliation=reconciliation, blocked_governance_mutation=blocked,
            reconciliation_error=recon_error,
        )

    def pause_retryable(reason: str) -> RunResult:
        """SPEC-007 "Resumable vs. Non-Resumable Interruption
        Classification" / Decision 3: a positively-identified, stable-
        signal transient agent-execution failure (`classify_transient_
        failure(...) == "execution_not_completed"`) is resumable, never
        `FAILED` -- deliberately does **not** call `checkpoint.
        terminal(...)` (so `terminal_outcome` stays `None`, exactly like
        any other interruption -- this is what makes the run
        `PAUSED_RETRYABLE`) and does **not** discard the candidate
        workspace or reconcile -- there is nothing yet to reconcile, and
        the workspace must survive for `peos resume` to reuse. The
        shared lock is still released on return (via `run_workflow`'s
        own `finally`), representing "no one is actively executing this
        right now", not "this run concluded".
        """
        log(f"[PEOS] Transient agent-execution failure classified resumable; pausing: {reason}")
        phases.append(PhaseLog(phase="Paused (retryable)", detail=reason))
        return RunResult(**_base_kwargs(), outcome="PAUSED_RETRYABLE", gate_reason=reason)

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
            checkpoint.terminal("FAILED", gate_reason=reason)
            _discard_candidate_workspace()
            return RunResult(
                **_base_kwargs(), outcome="FAILED", gate_reason=reason,
                reconciliation=reconciliation, blocked_governance_mutation=blocked,
                reconciliation_error=recon_error,
            )
        _write_ledger(active_phase="Complete", outcome="APPROVED")
        checkpoint.terminal("APPROVED")
        _discard_candidate_workspace()
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

        # SPEC-006 Section 8 step 1/Section 15: a Runtime Verification
        # declaration that cannot be deterministically interpreted
        # (unsupported kind, missing required parameter, orphaned ac=
        # reference, or more than the fixed per-round check-count bound)
        # gates here -- a decision-bearing specification defect, before
        # any workspace is created or either agent invoked. Never a
        # Human Gate merely because a check kind happens to be
        # unsupported *and also* genuinely unavailable on this host --
        # that distinct case is an execution-integrity FAILED, raised
        # later, from inside Runtime Verification itself, not here.
        if plan.runtime_plan.gate_reason is not None:
            return gate(GATE_RUNTIME_CHECK_UNSUPPORTED, plan.runtime_plan.gate_reason)

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

        if resume_seed is not None and resume_seed.workspace_root_relative_path:
            # SPEC-007 "Workspace Lifecycle": PLANNING had already
            # completed and created the candidate workspace before the
            # interruption -- reuse it in place (it durably survived
            # under `.peos/runs/<run_id>/candidate/`, exactly because it
            # is nested there), never create a second, fresh one.
            workspace = IsolatedWorkspace(
                path=repo_root / resume_seed.workspace_root_relative_path,
                home_dir=repo_root / resume_seed.workspace_home_dir_relative_path,
                baseline_commit=resume_seed.workspace_baseline_commit,
            )
            if not workspace.path.is_dir():
                return fail(
                    f"Resumed run's preserved candidate workspace is missing: {workspace.path} "
                    "(AC-018 -- failing closed, never silently reconstructing one)."
                )
        else:
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

        def _check_runtime_evidence_identity(before_what: str) -> RunResult | None:
            """SPEC-006 Section 9 identity re-verification (Codex
            implementation review Finding 4, closed): the previous
            round's staged evidence copy is a consumable artifact, just
            like a static-context artifact, and must be re-verified
            before every subsequent Claude/Codex invocation that could
            consume it -- a mismatch means it was altered by some means
            since staging, and the run fails closed immediately, never a
            silent re-hash and never a Human Gate. A `None`
            `runtime_outcome` (no round has produced evidence yet, or the
            most recent round declared no checks) is not a drift -- there
            is nothing to re-verify.
            """
            if runtime_outcome is None or not runtime_outcome.ran or runtime_outcome.persisted is None:
                return None
            drift = reverify_evidence_identity(runtime_outcome.persisted, runtime_outcome.staged_dir)
            if not drift.ok:
                return fail(
                    f"Runtime Verification evidence identity check failed before {before_what}: {drift.reason}"
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
                runtime_evidenced_ac_status=(
                    runtime_outcome.evidence.runtime_evidenced_ac_status()
                    if runtime_outcome is not None and runtime_outcome.evidence is not None
                    else None
                ),
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

        # SPEC-007 "Durable Phase-State Semantics" §PLANNING: the single
        # atomic `COMPLETED` write carries every identity the checkpoint
        # records about this run's starting point -- baseline, spec
        # identity, decision/governance/static-context identities, AC
        # set, effective max cycles, and the (now durable, candidate/-
        # nested) workspace's own identity.
        checkpoint.complete(
            "PLANNING",
            authoritative_baseline=baseline_commit,
            governing_spec_relative_path=spec_workspace_rel or "",
            governing_spec_content_hash=governing_spec_content_hash,
            effective_max_cycles=effective_max_cycles,
            workspace_root_relative_path=str(workspace.path.relative_to(repo_root)) if workspace.path.is_relative_to(repo_root) else "",
            workspace_home_dir_relative_path=str(workspace.home_dir.relative_to(repo_root)) if workspace.home_dir.is_relative_to(repo_root) else "",
            workspace_baseline_commit=workspace.baseline_commit,
            current_workspace_snapshot_identity=repo_state_fingerprint(workspace.path),
            decision_identities=decision_identities,
            governance_identities=governance_identities,
            static_context_artifacts=static_context_refs,
            acceptance_criteria_ids=tuple(sorted(required_ac_ids)),
            # SPEC-007 "Resume Preflight" check 15: a content-based
            # fingerprint of the authoritative repository itself, so
            # resume can detect an uncommitted/untracked edit made
            # during the pause -- not just a HEAD commit change -- before
            # reconciliation would otherwise silently adopt it as "the
            # original" and overwrite it.
            authoritative_repo_fingerprint=repo_state_fingerprint(repo_root),
        )

        def _run_runtime_verification_phase(cycle_label: str) -> RunResult | None:
            """SPEC-006 Section 8: run this round's Runtime Verification
            pass if the Runtime Plan declares any check, cycle 0 and
            every remediation cycle alike -- after Local Verification has
            already passed for this round, before the corresponding
            Codex call. Sets the enclosing `runtime_outcome` (consumed by
            `_round_packet`/`_codex_phase` for the *next* Codex call
            only) and returns a `FAILED` `RunResult` if execution
            integrity did not hold, or `None` to continue.
            """
            nonlocal runtime_outcome
            if not plan.runtime_plan.declarations:
                runtime_outcome = None
                # SPEC-006 AC-001 / Codex implementation review (minor
                # finding): the no-op is documented and visible in the
                # Delivery Report, not silently skipped -- logged exactly
                # like any other phase, just never started.
                stage(f"Runtime verification ({cycle_label}): no runtime checks declared")
                return None
            stage(f"Runtime verification ({cycle_label})")
            checkpoint.enter("RUNTIME_VERIFICATION")

            def _on_service_started(identity) -> None:
                # SPEC-007 Decision 7: a durable checkpoint write the
                # instant each backend/frontend service handle is
                # created -- before readiness waiting, the build, or
                # anything else that could be interrupted -- so a
                # process this orchestrator cannot itself tear down
                # (because *it* was the one that got killed) still has a
                # recorded identity for `peos resume`/`peos abandon` to
                # reclaim. Codex implementation review (confirmed,
                # major): an earlier revision built
                # `capture_service_process_identity` but never called it
                # from anywhere, leaving `service_process_identities`
                # permanently empty.
                checkpoint.enter(
                    "RUNTIME_VERIFICATION",
                    service_process_identities=checkpoint.current.service_process_identities + (identity,),
                )

            runtime_outcome = runtime_verifier(
                plan.runtime_plan, cycle_label=cycle_label, run_id=run_id, repo_root=repo_root,
                workspace=workspace, profile_dir=workspace.path.parent / "sandbox-profiles",
                environ=environ, workspace_snapshot_identity=repo_state_fingerprint(workspace.path),
                baseline_commit=baseline_commit, on_service_started=_on_service_started,
            )
            runtime_verification_history.append(runtime_outcome)
            if runtime_outcome.ran and not runtime_outcome.execution_integrity_passed:
                return fail(
                    f"Runtime Verification failed for {cycle_label}: {runtime_outcome.failure_reason}"
                )
            # SPEC-007: `COMPLETED` is written only once both
            # `persist_evidence` and `stage_evidence_into_workspace` have
            # already succeeded -- true here by construction, since
            # `runtime_verifier` (SPEC-006's `run_runtime_verification`)
            # never returns `execution_integrity_passed=True` with
            # `persisted`/`staged_dir` unset for a round that actually ran.
            history_entry = None
            if runtime_outcome.ran and runtime_outcome.persisted is not None and runtime_outcome.staged_dir is not None:
                history_entry = RuntimeEvidenceRefSnapshot(
                    cycle_label=cycle_label,
                    staged_relative_path=runtime_outcome.staged_dir.relative_to(workspace.path).as_posix(),
                    evidence_json_sha256=runtime_outcome.persisted.evidence_json_sha256,
                    execution_integrity_passed=runtime_outcome.execution_integrity_passed,
                )
            checkpoint.complete(
                "RUNTIME_VERIFICATION",
                runtime_evidence_history=(
                    checkpoint.current.runtime_evidence_history + (history_entry,)
                    if history_entry is not None else checkpoint.current.runtime_evidence_history
                ),
                # This round's own services are already confirmed torn
                # down by `run_runtime_verification`'s own `finally`
                # (true whenever this point is reached at all -- the
                # function never returns normally otherwise) -- cleared
                # back to empty so a later resume's orphan-reclamation
                # check never attempts a pointless no-op reclaim against
                # a long-dead, already-cleaned-up round.
                service_process_identities=(),
                # Codex closure review (confirmed, major): Runtime
                # Verification stages new, non-ignored evidence files
                # directly into the candidate workspace
                # (`.peos/runtime-evidence/<cycle>/...`, a sibling of
                # `.peos/runs/`, not covered by that exclusion) -- a real,
                # expected change to the workspace's own content
                # fingerprint. Without refreshing it here, resume
                # preflight's check 7 (non-mutating-phase snapshot
                # integrity) would compare against the *stale*,
                # pre-staging fingerprint recorded at
                # CLAUDE_IMPLEMENTATION/CLAUDE_REMEDIATION's own
                # COMPLETED write and wrongly fail closed on a resume
                # interrupted during or after this phase.
                current_workspace_snapshot_identity=repo_state_fingerprint(workspace.path),
            )
            return None

        def _runtime_evidence_ref() -> RuntimeEvidenceRef | None:
            """SPEC-006 Section 14: the Round Packet's thirteenth element
            for the *next* Claude/Codex call -- `None` if the most
            recently completed round's Runtime Verification found no
            checks to run (the documented no-op), never a placeholder.
            """
            if runtime_outcome is None or not runtime_outcome.ran or runtime_outcome.evidence is None:
                return None
            staged_relative = runtime_outcome.staged_dir.relative_to(workspace.path).as_posix()
            return RuntimeEvidenceRef(
                staged_relative_path=staged_relative,
                evidence_json_sha256=runtime_outcome.persisted.evidence_json_sha256,
                execution_integrity_passed=runtime_outcome.execution_integrity_passed,
                checks=tuple(
                    RuntimeCheckSummary(
                        check_id=c.check_id, kind=c.kind, status=c.status, related_ac_ids=c.related_ac_ids,
                    )
                    for c in runtime_outcome.evidence.checks
                ),
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
                runtime_evidence=_runtime_evidence_ref(),
            )

        # Codex closure review (confirmed, major, new issue found during
        # remediation of an earlier finding): `active_phase ==
        # "RECONCILIATION"` can *only* mean the main engineering loop
        # (cycle 0 and every remediation cycle) had *already* reached a
        # terminal decision and was in the middle of `_reconcile()`
        # itself when interrupted -- regardless of how much cycle budget
        # happened to remain unused. Falling through to the ordinary
        # cycle-0/remediation-loop re-entry logic below would have
        # wrongly started a brand new remediation cycle (an extra Claude
        # call Codex had never asked for) instead of recognizing the run
        # was already done with its engineering work. This is the exact
        # same "cannot safely re-enter this interruption point" situation
        # as the max-cycles-exhausted-at-TERMINAL_DECISION case below,
        # generalized to fire on `RECONCILIATION` specifically,
        # regardless of remaining budget.
        if resume_seed is not None and resume_seed.active_phase == "RECONCILIATION":
            return fail(
                "Resume cannot safely re-enter this exact interruption point: the engineering loop "
                "had already reached a terminal decision and was in the middle of reconciling the "
                "candidate workspace back onto the authoritative repository when interrupted. "
                "Restarting the remediation loop from here would wrongly redo engineering work Codex "
                "never asked for; this specific window (during RECONCILIATION itself) is a named, "
                "accepted residual limitation of this resume implementation, not a HUMAN_GATE or a "
                "guess -- inspect this run's checkpoint.json codex_review_verdict_history and "
                "reconciliation_manifest and decide manually."
            )

        # SPEC-007 resume re-entry: skip cycle 0 entirely if its own
        # CODEX_INDEPENDENT_REVIEW phase had already reached COMPLETED
        # before the interruption -- never redo a Claude call whose
        # result was already durably recorded (AC-006/AC-001).
        if resume_seed is None or not _cycle_zero_already_completed(resume_seed):
            # SPEC-007 resume re-entry: skip re-issuing the Claude
            # call specifically if it already reached COMPLETED before
            # the interruption -- verification and the Codex review
            # below still always rerun (AC-003/AC-005).
            if resume_seed is None or not _cycle_zero_claude_already_completed(resume_seed):
                # Phase 4 -- Claude implementation (cycle 0)
                stage("Claude implementation")
                checkpoint.enter("CLAUDE_IMPLEMENTATION")
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
                runtime_evidence_failure = _check_runtime_evidence_identity("Claude implementation")
                if runtime_evidence_failure is not None:
                    return runtime_evidence_failure
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
                    if classify_transient_failure(impl_result) == "execution_not_completed":
                        return pause_retryable(f"Claude implementation did not complete execution: {impl_result.error}")
                    return fail(f"Claude implementation did not complete successfully: {impl_result.error}")

                mutation_failure = _check_governance_mutation("implementation")
                if mutation_failure is not None:
                    return mutation_failure
                checkpoint.complete("CLAUDE_IMPLEMENTATION", current_workspace_snapshot_identity=repo_state_fingerprint(workspace.path))

            # Phase 5 -- Local verification (cycle 0)
            stage("Local verification")
            checkpoint.enter("LOCAL_VERIFICATION")
            identity_failure = _check_governing_spec_identity("local verification", check_staged=True)
            if identity_failure is not None:
                return identity_failure
            vreport = verifier(workspace, repo_root, vplan)
            verification_reports.append(vreport)
            latest_verification = vreport
            if not vreport.passed:
                failing = ", ".join(r.name for r in vreport.failures)
                return fail(f"Local verification failed after implementation: {failing}")
            checkpoint.complete("LOCAL_VERIFICATION")

            mutation_failure = _check_governance_mutation("post-implementation verification")
            if mutation_failure is not None:
                return mutation_failure
            identity_failure = _check_governing_spec_identity("Codex independent review", check_staged=True)
            if identity_failure is not None:
                return identity_failure
            static_context_failure = _check_static_context_identity("Codex independent review")
            if static_context_failure is not None:
                return static_context_failure

            # Phase 5b -- Runtime verification (cycle 0, SPEC-006)
            runtime_failure = _run_runtime_verification_phase("cycle 0")
            if runtime_failure is not None:
                return runtime_failure
            runtime_evidence_failure = _check_runtime_evidence_identity("Codex independent review")
            if runtime_evidence_failure is not None:
                return runtime_evidence_failure

            # Phase 6 -- Codex independent review (cycle 0)
            stage("Codex independent review")
            checkpoint.enter("CODEX_INDEPENDENT_REVIEW")
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
                if classify_transient_failure(review) == "execution_not_completed":
                    return pause_retryable(f"Codex independent review did not complete execution: {review.error}")
                return fail(f"Codex review produced uninterpretable output: {review.error}")

            outcome_kind, detail = _evaluate_cycle(review, 0, register, frozenset())
            # SPEC-007: the single atomic `COMPLETED` write for a Codex phase
            # carries the validated payload's hash, its verdict, and the
            # Outstanding Findings Register exactly as this review's own
            # `_evaluate_cycle` call just updated it -- all together, one
            # write, after the register mutation above, before any terminal
            # decision below is reached.
            checkpoint.complete(
                "CODEX_INDEPENDENT_REVIEW",
                codex_review_payload_hashes=checkpoint.current.codex_review_payload_hashes + (hashlib.sha256(review.raw_stdout.encode("utf-8", errors="replace")).hexdigest(),),
                codex_review_verdict_history=checkpoint.current.codex_review_verdict_history + (review.verdict,),
                findings_register_entries=tuple(RegisterEntrySnapshot.from_entry(e) for e in register.all_entries()),
            )
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
        #
        # SPEC-007 "Remediation-cycle allocation, specified exactly":
        # `checkpoint.current_cycle` only ever advances at a cycle's own
        # CODEX_CLOSURE_REVIEW COMPLETED write, so `current_cycle + 1` is
        # correct whether cycle `current_cycle + 1` never started at all,
        # or started (CLAUDE_REMEDIATION ENTERED) but did not finish --
        # either way, resuming at `current_cycle + 1` redoes that one
        # cycle's full work exactly once, never allocating a second
        # identity for the same logical cycle (AC-002/AC-008/AC-027).
        resume_starting_cycle = (resume_seed.current_cycle + 1) if resume_seed is not None else 1
        if resume_seed is not None and resume_starting_cycle > effective_max_cycles:
            # SPEC-007 Final Delivery Gate / AC-054, the one narrow
            # residual edge case this coarse-grained, cycle-boundary
            # resume strategy does not re-enter surgically: the
            # interruption happened between the *last* allocated cycle's
            # CODEX_CLOSURE_REVIEW COMPLETED write and TERMINAL_DECISION
            # itself -- every cycle's Claude/verification/review work is
            # already durably recorded, but no terminal outcome was ever
            # reached. A resumed run must never resume directly to
            # APPROVED from a pre-interruption verdict alone (even an
            # APPROVE) -- rather than guessing which terminal outcome the
            # original run would have reached, this fails closed with an
            # explicit, named reason, directing a human to inspect the
            # checkpoint's own recorded verdict history and decide.
            return fail(
                "Resume cannot safely re-enter this exact interruption point: every allocated "
                f"remediation cycle (1..{resume_seed.current_cycle}) already completed its own "
                "Codex closure review before the interruption, but no terminal decision was ever "
                "reached. Per the Final Delivery Gate, a resumed run may never proceed directly to "
                "APPROVED from a pre-interruption verdict alone; this specific narrow window "
                "(between a closure review's own COMPLETED write and TERMINAL_DECISION) is a named, "
                "accepted residual limitation of this resume implementation, not a HUMAN_GATE or a "
                "guess -- inspect this run's checkpoint.json codex_review_verdict_history and "
                "decide manually."
            )
        for remediation_cycle in range(resume_starting_cycle, effective_max_cycles + 1):
            remediation_cycles_run = remediation_cycle
            cycle_label = f"{remediation_cycle}/{effective_max_cycles}"

            # SPEC-007 resume re-entry: skip re-issuing this cycle's
            # Claude remediation call specifically if it already reached
            # COMPLETED before the interruption -- only ever applies to
            # the one cycle currently being resumed (AC-002/AC-003).
            # Codex implementation review (confirmed, major): an earlier
            # revision had no such middle state, unconditionally redoing
            # a completed Claude call on resume. Disputes raised by an
            # already-`COMPLETED` Claude remediation call must also
            # survive resume even if `CODEX_CLOSURE_REVIEW` itself never
            # completed -- fixed by persisting `active_disputes`/
            # `dispute_log` as part of *this* phase's own `COMPLETED`
            # write (a real durable consequence of this phase's result,
            # not merely the workspace identity), reconstructed from the
            # checkpoint here on the skip path instead of re-deriving
            # from a Claude call this process never made.
            skip_remediation_claude = (
                resume_seed is not None and remediation_cycle == resume_starting_cycle
                and _remediation_claude_already_completed(resume_seed)
            )
            if not skip_remediation_claude:
                stage(f"Claude remediation (remediation cycle {cycle_label})")
                # SPEC-007 "Remediation-cycle allocation, specified exactly":
                # cycle `remediation_cycle` is *allocated* by this `ENTERED`
                # write but does not become *countable* -- i.e. `current_cycle`
                # does not advance -- until this same cycle's `CODEX_CLOSURE_
                # REVIEW` `COMPLETED` write, below. `checkpoint.current_cycle`
                # deliberately still reads `remediation_cycle - 1` here.
                checkpoint.enter("CLAUDE_REMEDIATION")
                identity_failure = _check_governing_spec_identity(
                    f"Claude remediation cycle {remediation_cycle}", check_staged=True,
                )
                if identity_failure is not None:
                    return identity_failure
                static_context_failure = _check_static_context_identity(f"Claude remediation cycle {remediation_cycle}")
                if static_context_failure is not None:
                    return static_context_failure
                runtime_evidence_failure = _check_runtime_evidence_identity(f"Claude remediation cycle {remediation_cycle}")
                if runtime_evidence_failure is not None:
                    return runtime_evidence_failure

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
                    if classify_transient_failure(remediation_result) == "execution_not_completed":
                        return pause_retryable(f"Claude remediation did not complete execution: {remediation_result.error}")
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
                active_disputes_for_packet = tuple(
                    ActiveDispute(reference=d.reference, evidence=d.evidence, raised_in_remediation_cycle=remediation_cycle)
                    for d in disputes
                )

                mutation_failure = _check_governance_mutation("remediation")
                if mutation_failure is not None:
                    return mutation_failure
                checkpoint.complete(
                    "CLAUDE_REMEDIATION",
                    current_workspace_snapshot_identity=repo_state_fingerprint(workspace.path),
                    dispute_log=tuple(dispute_log), active_disputes=active_disputes_for_packet,
                )
            else:
                log(f"[PEOS] Resuming: Claude remediation cycle {remediation_cycle} already completed; not redoing it.")
                active_disputes_for_packet = resume_seed.active_disputes
                active_dispute_refs = frozenset(d.reference for d in active_disputes_for_packet)

            stage(f"Local verification (remediation cycle {cycle_label})")
            checkpoint.enter("LOCAL_VERIFICATION")
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
            checkpoint.complete("LOCAL_VERIFICATION")

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

            runtime_failure = _run_runtime_verification_phase(f"remediation cycle {remediation_cycle}")
            if runtime_failure is not None:
                return runtime_failure
            runtime_evidence_failure = _check_runtime_evidence_identity(
                f"Codex closure review (remediation cycle {remediation_cycle})"
            )
            if runtime_evidence_failure is not None:
                return runtime_evidence_failure

            stage(f"Codex closure review (remediation cycle {cycle_label})")
            checkpoint.enter("CODEX_CLOSURE_REVIEW")
            # `active_disputes_for_packet`/`active_dispute_refs` were
            # already established above -- either freshly, from this
            # cycle's own (just-made) Claude call, or reconstructed from
            # the checkpoint if that call was already COMPLETED before
            # resume and correctly skipped.
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
                if classify_transient_failure(closure_review) == "execution_not_completed":
                    return pause_retryable(f"Codex closure review did not complete execution: {closure_review.error}")
                return fail(f"Codex closure review produced uninterpretable output: {closure_review.error}")

            if active_dispute_refs:
                verdict_word = "overruled" if closure_review.reviewer_overrules_dispute else "conceded"
                dispute_log.append(
                    f"Codex {verdict_word} dispute(s) {sorted(active_dispute_refs)} in remediation cycle {remediation_cycle}"
                )

            outcome_kind, detail = _evaluate_cycle(closure_review, remediation_cycle, register, active_dispute_refs)
            # SPEC-007: the single atomic `COMPLETED` write for
            # `CODEX_CLOSURE_REVIEW` carries the validated payload's
            # hash, its verdict, the register state `_evaluate_cycle`
            # just updated, and `current_cycle`'s own advancement --
            # all together, one write. This is the instant cycle
            # `remediation_cycle` becomes *countable* (SPEC-007
            # "Remediation-cycle allocation, specified exactly").
            checkpoint.complete(
                "CODEX_CLOSURE_REVIEW",
                current_cycle=remediation_cycle,
                codex_review_payload_hashes=checkpoint.current.codex_review_payload_hashes + (hashlib.sha256(closure_review.raw_stdout.encode("utf-8", errors="replace")).hexdigest(),),
                codex_review_verdict_history=checkpoint.current.codex_review_verdict_history + (closure_review.verdict,),
                findings_register_entries=tuple(RegisterEntrySnapshot.from_entry(e) for e in register.all_entries()),
                dispute_log=tuple(dispute_log),
            )
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
                # SPEC-007 Decision 9: convergence exhaustion is now its
                # own distinct terminal outcome, never HUMAN_GATE --
                # supersedes SPEC-004's GATE_UNRESOLVED_AFTER_REMEDIATION
                # encoding (AC-043/AC-025).
                return max_cycles_reached(
                    f"Codex still returned CHANGES_REQUIRED after {effective_max_cycles} remediation "
                    f"cycle(s) (the configured max_cycles): outstanding register entries: {outstanding}; "
                    f"active disputes: {sorted(active_dispute_refs) or '(none)'}."
                )
            # Otherwise: CHANGES_REQUIRED with budget remaining -- loop.

        # Unreachable: the loop above always returns on its last
        # iteration (either converging or reaching MAX_CYCLES_REACHED).
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
        try:
            checkpoint.terminal("FAILED", gate_reason=diagnostic)
        except Exception:  # noqa: BLE001 -- best-effort; never mask the already-determined outcome.
            pass
        _discard_candidate_workspace()
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
        # SPEC-007: mirror the ledger's own "a genuine unexpected failure
        # must never be left looking resumable" fix for the checkpoint --
        # a `terminal_outcome` of `None` is exactly what resume preflight
        # treats as a safely-resumable paused run (AC-061/AC-062), so an
        # unhandled exception must positively record FAILED here, never
        # leave it absent.
        try:
            checkpoint.terminal("FAILED", gate_reason=reason)
        except Exception:  # noqa: BLE001 -- best-effort; never mask the already-determined outcome.
            pass
        _discard_candidate_workspace()
        return RunResult(**_base_kwargs(), outcome="FAILED", gate_reason=reason)
