"""PEOS Durable Run Resume -- `resume`/`inspect`/`abandon` (SPEC-007).

Three operations, built on `peos.run_lock` (the shared, one-run-per-
repository lock) and `peos.checkpoint` (the trusted `RunCheckpoint`):

- `inspect_run`: strictly read-only, never acquires the lock.
- `abandon_run`: acquires the lock, attempts orphaned-process
  reclamation *before* terminalizing (never the reverse), writes
  `terminal_outcome="ABANDONED"`, discards the candidate workspace,
  clears the lock.
- `run_resume_preflight` / `resume_run`: acquires the lock (SPEC-007
  Resume Preflight check 1), then runs checks 2-16 in the specified
  order (integrity/staged-copy checks before any drift classification),
  producing exactly one of: `FAILED` (fails closed, never guesses),
  `GATE_AUTHORITATIVE_DRIFT_ON_RESUME` (the one new, unified Human Gate
  this specification introduces -- ID `"13"`), or a successful
  continuation into `peos.workflow.run_workflow`'s own engineering loop,
  resumed at the correct phase/cycle boundary (never redoing a Claude
  call whose result was already durably `COMPLETED`).

Scope note (named, honest limitation -- not silently narrowed): resume's
continuation strategy is **cycle-boundary-granular**, not sub-phase-
granular. It never redoes already-`COMPLETED` Claude/verification/review
work (the core AC-006 guarantee), and it correctly accounts for cycle
allocation (AC-002/AC-008/AC-027). It does not attempt to reproduce every
single named phase-boundary resumption point as its own distinct code
path; the one documented residual gap is the narrow window between the
last allocated cycle's `CODEX_CLOSURE_REVIEW` `COMPLETED` write and
`TERMINAL_DECISION` itself (see `peos.workflow._cycle_zero_already_
completed`'s caller in `_run_workflow`), which fails closed with an
explicit, named reason rather than guessing.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from peos.checkpoint import CheckpointManager, RunCheckpoint, load_checkpoint
from peos.claude_agent import ClaudeRunResult, run_claude
from peos.codex_agent import CodexReviewResult, run_codex_review
from peos.findings_register import FindingRef
from peos.preflight import check_repository_safety, check_verification_interpreter
from peos.runtime_services import reclaim_orphaned_service
from peos.runtime_verification import RuntimeVerificationOutcome, run_runtime_verification
from peos.run_lock import RunLockError, acquire_for_abandon, acquire_for_resume
from peos.sandbox import (
    candidate_root_for_run,
    check_claude_auth_preflight,
    check_codex_auth_preflight,
    cleanup_reconciliation_debris,
    discard_workspace,
    IsolatedWorkspace,
)
from peos.spec import resolve_governing_spec
from peos.workflow import RunResult, SpecResolver, Verifier, _default_verifier, run_workflow

GATE_AUTHORITATIVE_DRIFT_ON_RESUME = "13"

_MUTATING_PHASES = frozenset({"CLAUDE_IMPLEMENTATION", "CLAUDE_REMEDIATION"})


@dataclass(frozen=True)
class PreflightOutcome:
    """`kind` is one of `"READY"`, `"FAILED"`, `"GATE_AUTHORITATIVE_DRIFT_
    ON_RESUME"`. `reason` is always set for the latter two."""

    kind: str
    reason: str | None = None


def _sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _candidate_workspace_for(repo_root: Path, checkpoint: RunCheckpoint) -> IsolatedWorkspace | None:
    if not checkpoint.workspace_root_relative_path:
        return None
    return IsolatedWorkspace(
        path=repo_root / checkpoint.workspace_root_relative_path,
        home_dir=repo_root / checkpoint.workspace_home_dir_relative_path,
        baseline_commit=checkpoint.workspace_baseline_commit,
    )


def run_resume_preflight(repo_root: Path, checkpoint: RunCheckpoint, environ: dict) -> PreflightOutcome:
    """Checks 2-16 of SPEC-007's "Resume Preflight" table (check 1 --
    lock acquisition and run_id/non-terminal matching -- is
    `peos.run_lock.acquire_for_resume`'s own job, already done by the
    caller before this runs)."""
    # Check 2/3 (checkpoint readable, non-terminal) already established
    # by the caller via acquire_for_resume + load_checkpoint.

    # Check 4: repository identity, fresh.
    preflight = check_repository_safety(repo_root)
    if not preflight.ok:
        return PreflightOutcome("FAILED", f"Repository safety check failed on resume: {preflight.reason}")

    # Check 5: checkpoint internal self-consistency.
    if not checkpoint.active_phase:
        return PreflightOutcome("FAILED", "Checkpoint internal self-consistency check failed: active_phase is empty.")
    if checkpoint.current_cycle > checkpoint.effective_max_cycles:
        return PreflightOutcome(
            "FAILED",
            f"Checkpoint internal self-consistency check failed: current_cycle "
            f"({checkpoint.current_cycle}) exceeds effective_max_cycles ({checkpoint.effective_max_cycles}).",
        )
    if checkpoint.active_phase not in ("PLANNING",) and not checkpoint.workspace_root_relative_path:
        return PreflightOutcome(
            "FAILED",
            "Checkpoint internal self-consistency check failed: active_phase is past PLANNING but no "
            "workspace was ever recorded.",
        )

    # Check 6: governance-artifact integrity against repo_root's current state.
    for name, expected_hash in checkpoint.governance_identities:
        current_hash = _sha256_file(repo_root / name)
        if current_hash != expected_hash:
            return PreflightOutcome(
                "FAILED",
                f"Governance artifact integrity check failed on resume: {name} no longer matches its "
                "recorded identity (governance mutation is never a drift-gate matter).",
            )

    workspace = _candidate_workspace_for(repo_root, checkpoint)

    # Check 7: workspace/snapshot integrity, or partial-candidate recovery.
    if workspace is not None:
        if not workspace.path.is_dir():
            return PreflightOutcome(
                "FAILED",
                f"Resume preflight check failed: the preserved candidate workspace is missing: {workspace.path}.",
            )
        interrupted_mutating_phase = (
            checkpoint.active_phase in _MUTATING_PHASES and checkpoint.active_phase_state == "ENTERED"
        )
        if not interrupted_mutating_phase:
            from peos.gitutil import repo_state_fingerprint
            current_identity = repo_state_fingerprint(workspace.path)
            if (
                checkpoint.current_workspace_snapshot_identity
                and current_identity != checkpoint.current_workspace_snapshot_identity
            ):
                return PreflightOutcome(
                    "FAILED",
                    "Resume preflight check failed: the preserved workspace's current snapshot identity "
                    "no longer matches the checkpoint's recorded identity for a non-mutating interrupted phase.",
                )
        else:
            # SPEC-007 "Partial Candidate Workspace Recovery": the
            # workspace's current, partial content is UNTRUSTED_PARTIAL_
            # CANDIDATE_STATE, not a failure on its own -- peos.workflow's
            # own resume re-entry redoes this exact phase from scratch,
            # which is this procedure's required recovery. But step 2 of
            # that procedure still requires revalidating every trust/
            # governance invariant against the workspace's own *staged*
            # copies specifically (a partial Claude attempt could have
            # mutated staged CLAUDE.md itself, distinct from repo_root's
            # copy, which check 6 above already covers) -- Codex
            # implementation review (confirmed, major): an earlier
            # revision skipped this entirely, letting exactly that
            # corruption (AC-056) pass preflight undetected.
            from peos.preflight import detect_mutations
            baseline_hashes = dict(checkpoint.governance_identities)
            if checkpoint.governing_spec_relative_path and checkpoint.governing_spec_content_hash:
                baseline_hashes[checkpoint.governing_spec_relative_path] = checkpoint.governing_spec_content_hash
            mutated = detect_mutations(baseline_hashes, workspace.path)
            if mutated:
                return PreflightOutcome(
                    "FAILED",
                    "Partial Candidate Workspace Recovery check failed: the workspace's own staged "
                    f"governance/spec copy was mutated during the interrupted phase: {', '.join(mutated)}.",
                )

    # Check 8: findings-register deserialization.
    for snapshot in checkpoint.findings_register_entries:
        if FindingRef.parse(snapshot.reference) is None:
            return PreflightOutcome(
                "FAILED", f"Findings-register deserialization failed on resume: malformed reference {snapshot.reference!r}.",
            )

    # Check 9: runtime evidence integrity (persisted-file hash vs. recorded hash).
    if checkpoint.runtime_evidence_history:
        latest = checkpoint.runtime_evidence_history[-1]
        from peos.runtime_evidence import EVIDENCE_FILENAME
        # The authoritative persisted copy lives at
        # .peos/runs/<run_id>/runtime-evidence/<cycle_slug>/ -- distinct
        # from the staged workspace copy `staged_relative_path` names;
        # the cycle slug is that path's own last component.
        cycle_slug = latest.staged_relative_path.rstrip("/").split("/")[-1]
        persisted_path = repo_root / ".peos" / "runs" / checkpoint.run_id / "runtime-evidence" / cycle_slug / EVIDENCE_FILENAME
        current_hash = _sha256_file(persisted_path)
        # Codex implementation review (confirmed, major): a missing
        # persisted file (current_hash is None) was previously treated
        # as passing this check -- it must fail exactly like a hash
        # mismatch, not be silently accepted as "nothing to compare".
        if current_hash != latest.evidence_json_sha256:
            return PreflightOutcome(
                "FAILED",
                "Runtime evidence integrity check failed on resume: persisted evidence.json is missing or "
                "its hash no longer matches the recorded identity (tamper/corruption).",
            )

    # Check 10: static-context STAGED-copy integrity only (never the
    # authoritative copy here -- deliberately deferred to check 15).
    if workspace is not None:
        for artifact in checkpoint.static_context_artifacts:
            if not artifact.staged_relative_path:
                continue
            staged_path = workspace.path / artifact.staged_relative_path
            staged_hash = _sha256_file(staged_path)
            if staged_hash != artifact.content_hash:
                return PreflightOutcome(
                    "FAILED",
                    f"Static-context staged-copy integrity check failed on resume: {artifact.declared_path}.",
                )

    # Check 11: dependency/tool availability.
    interpreter = check_verification_interpreter()
    if not interpreter.ok:
        return PreflightOutcome("FAILED", f"Dependency/tool availability check failed on resume: {interpreter.reason}")

    # Check 12: Claude/Codex authentication.
    claude_auth = check_claude_auth_preflight(environ)
    if not claude_auth.ok:
        return PreflightOutcome("FAILED", f"Claude authentication check failed on resume: {claude_auth.reason}")
    codex_auth = check_codex_auth_preflight(environ)
    if not codex_auth.ok:
        return PreflightOutcome("FAILED", f"Codex authentication check failed on resume: {codex_auth.reason}")

    # Check 13: Runtime Verification prerequisites. Codex implementation
    # review (confirmed, major): this was previously a pure no-op, which
    # let authoritative drift (check 15) produce GATE_AUTHORITATIVE_
    # DRIFT_ON_RESUME before an unrelated, more basic execution-
    # integrity problem (the sandbox mechanism itself unavailable) was
    # ever surfaced. A minimal, cheap, always-applicable check closes
    # the ordering gap without re-deriving the full Runtime Plan (left
    # to the resumed run's own ordinary Runtime Verification phase,
    # which still fails closed on any check-specific execution-integrity
    # problem this preflight cannot anticipate without that plan).
    if checkpoint.runtime_evidence_history:
        import shutil as _shutil
        import sys as _sys
        if _sys.platform != "darwin" or _shutil.which("sandbox-exec") is None:
            return PreflightOutcome(
                "FAILED",
                "Runtime Verification prerequisites check failed on resume: this run previously used "
                "Runtime Verification, but the macOS sandbox-exec mechanism is not available on this host.",
            )

    # Check 14: orphaned-process reclamation.
    for identity in checkpoint.service_process_identities:
        ok, reason = reclaim_orphaned_service(identity)
        if not ok:
            return PreflightOutcome("FAILED", f"Orphaned process reclamation failed on resume: {reason}")

    # Debris cleanup (SPEC-007 Round 3 Finding 4), before any drift
    # comparison runs -- PEOS's own reconciliation debris is never
    # unexplained dirtiness.
    if checkpoint.reconciliation_manifest:
        cleanup_reconciliation_debris(checkpoint.reconciliation_manifest, repo_root, checkpoint.run_id)

    # Check 15: authoritative-currency drift -- only now.
    if checkpoint.authoritative_baseline and preflight.head_commit != checkpoint.authoritative_baseline:
        return PreflightOutcome(
            "GATE_AUTHORITATIVE_DRIFT_ON_RESUME",
            f"HEAD has moved since this run started (was {checkpoint.authoritative_baseline}, now "
            f"{preflight.head_commit}); a human must decide how to proceed.",
        )
    # Codex closure review (confirmed, major): the HEAD-commit check
    # above cannot detect an *uncommitted* tracked-file edit or a new
    # untracked file made to the authoritative repository during the
    # pause (same HEAD, different content) -- a freshly-rebuilt
    # reconciliation manifest would otherwise silently adopt that edit
    # as "the original" and overwrite it without ever flagging it. This
    # broader, content-based fingerprint check catches that case too.
    if checkpoint.authoritative_repo_fingerprint:
        from peos.gitutil import repo_state_fingerprint
        current_repo_fingerprint = repo_state_fingerprint(repo_root)
        if current_repo_fingerprint != checkpoint.authoritative_repo_fingerprint:
            return PreflightOutcome(
                "GATE_AUTHORITATIVE_DRIFT_ON_RESUME",
                "The authoritative repository's working-tree content (tracked edits or new "
                "untracked files, not necessarily a new commit) has changed since this run started; "
                "a human must decide how to proceed.",
            )
    if checkpoint.governing_spec_relative_path and checkpoint.governing_spec_content_hash:
        spec_path = repo_root / checkpoint.governing_spec_relative_path
        if not spec_path.is_file():
            return PreflightOutcome(
                "FAILED", f"Governing specification is no longer present on disk: {spec_path}.",
            )
        current_spec_hash = _sha256_file(spec_path)
        if current_spec_hash != checkpoint.governing_spec_content_hash:
            return PreflightOutcome(
                "GATE_AUTHORITATIVE_DRIFT_ON_RESUME",
                f"The governing specification's content has changed on disk since this run started: {spec_path}.",
            )
    for artifact in checkpoint.static_context_artifacts:
        authoritative_path = repo_root / artifact.declared_path
        if not authoritative_path.is_file():
            return PreflightOutcome(
                "FAILED", f"Static-context artifact is no longer present on disk: {authoritative_path}.",
            )
        current_hash = _sha256_file(authoritative_path)
        if current_hash != artifact.content_hash:
            return PreflightOutcome(
                "GATE_AUTHORITATIVE_DRIFT_ON_RESUME",
                f"Static-context artifact's authoritative content has changed since this run started: "
                f"{artifact.declared_path}.",
            )

    # Check 16: evidence/plan binding currency -- not itself a failure;
    # the resumed engineering loop's own unconditional rules (fresh
    # Codex call, always-rerun deterministic verification) already
    # subsume this.
    return PreflightOutcome("READY")


def resume_run(
    repo_root: Path,
    run_id: str,
    *,
    environ: dict | None = None,
    log: Callable[[str], None] = lambda msg: None,
    spec_resolver: SpecResolver = resolve_governing_spec,
    claude_runner: Callable[..., ClaudeRunResult] = run_claude,
    codex_runner: Callable[..., CodexReviewResult] = run_codex_review,
    verifier: Verifier = _default_verifier,
    runtime_verifier: Callable[..., RuntimeVerificationOutcome] = run_runtime_verification,
) -> RunResult:
    """`./bin/peos resume <run_id>`. Acquires `.peos/run.lock`'s `flock`
    (non-blocking, held for this entire execution) as its very first
    step, exactly as SPEC-007 "Workspace Lifecycle" specifies."""
    import os
    environ = environ if environ is not None else dict(os.environ)

    pre_checkpoint, read_error = load_checkpoint(repo_root, run_id)
    task_for_errors = pre_checkpoint.task if pre_checkpoint is not None else ""

    try:
        lock = acquire_for_resume(repo_root, run_id)
    except RunLockError as exc:
        return RunResult(task=task_for_errors, outcome="FAILED", gate_reason=f"Could not resume run {run_id}: {exc}")

    # SPEC-007: everything from here on must release `lock` on *every*
    # exit path -- including an exception none of the code below
    # anticipates -- except the one success path that hands ownership of
    # the lock to `run_workflow` itself (which releases it in its own
    # `finally`, via `resume_lock`). Codex implementation review
    # (confirmed, major): an earlier revision only released the lock on
    # the specific paths it had explicitly written, leaving it held
    # forever if `load_checkpoint`/`run_resume_preflight`/`checkpoint.
    # terminal(...)` ever raised an unexpected exception.
    handed_off = False
    try:
        checkpoint, read_error = load_checkpoint(repo_root, run_id)
        if checkpoint is None:
            return RunResult(task=task_for_errors, outcome="FAILED", gate_reason=f"Could not resume run {run_id}: {read_error}")

        outcome = run_resume_preflight(repo_root, checkpoint, environ)
        if outcome.kind != "READY":
            manager = CheckpointManager(repo_root, run_id, require_fresh=False)
            manager.seed_from(checkpoint)
            if outcome.kind == "GATE_AUTHORITATIVE_DRIFT_ON_RESUME":
                manager.terminal("HUMAN_GATE", gate_id=GATE_AUTHORITATIVE_DRIFT_ON_RESUME, gate_reason=outcome.reason)
                result_outcome = "HUMAN_GATE"
            else:
                manager.terminal("FAILED", gate_reason=outcome.reason)
                result_outcome = "FAILED"
            workspace = _candidate_workspace_for(repo_root, checkpoint)
            _safely_discard(repo_root, run_id, workspace)
            return RunResult(
                task=checkpoint.task, outcome=result_outcome,
                gate_id=GATE_AUTHORITATIVE_DRIFT_ON_RESUME if outcome.kind == "GATE_AUTHORITATIVE_DRIFT_ON_RESUME" else None,
                gate_reason=outcome.reason, run_id=run_id,
            )

        # SPEC-007 "Partial Candidate Workspace Recovery" step 5: for an
        # interrupted mutating phase, compute and durably record a fresh
        # `resume_candidate_workspace_identity` before continuing.
        if checkpoint.active_phase in _MUTATING_PHASES and checkpoint.active_phase_state == "ENTERED":
            workspace = _candidate_workspace_for(repo_root, checkpoint)
            if workspace is not None:
                from peos.gitutil import repo_state_fingerprint
                manager = CheckpointManager(repo_root, run_id, require_fresh=False)
                manager.seed_from(checkpoint)
                checkpoint = manager.enter(
                    checkpoint.active_phase,
                    resume_candidate_workspace_identity=repo_state_fingerprint(workspace.path),
                )

        explicit_spec = (
            Path(checkpoint.governing_spec_original_path)
            if checkpoint.governing_spec_source == "explicit_path" and checkpoint.governing_spec_original_path
            else None
        )
        handed_off = True
        return run_workflow(
            checkpoint.task, repo_root, explicit_spec=explicit_spec, log=log,
            spec_resolver=spec_resolver,
            claude_runner=claude_runner, codex_runner=codex_runner, verifier=verifier,
            environ=environ, max_cycles=checkpoint.effective_max_cycles, runtime_verifier=runtime_verifier,
            resume_seed=checkpoint, resume_lock=lock,
        )
    except Exception as exc:  # noqa: BLE001 -- never leave the lock held on an unexpected failure.
        return RunResult(task=task_for_errors, outcome="FAILED", gate_reason=f"Unhandled exception while resuming run {run_id}: {exc}")
    finally:
        if not handed_off:
            lock.release()


def _safely_discard(repo_root: Path, run_id: str, workspace: IsolatedWorkspace | None) -> None:
    if workspace is None:
        return
    expected = candidate_root_for_run(repo_root, run_id).resolve()
    try:
        if workspace.path.parent.resolve() != expected:
            return
        discard_workspace(workspace)
    except OSError:
        pass


@dataclass(frozen=True)
class AbandonResult:
    ok: bool
    reason: str | None = None


def abandon_run(repo_root: Path, run_id: str) -> AbandonResult:
    """`./bin/peos abandon <run_id>`. Reclaims orphaned processes
    *before* terminalizing (never the reverse, SPEC-007 CLI/UX); on
    reclamation failure, the lock is released without having changed
    anything -- `abandon` itself fails, the run remains
    `PAUSED_RETRYABLE`. Scopes its "touches nothing outside X" guarantee
    to `.peos/` as a whole, which includes the shared lock file itself."""
    try:
        lock = acquire_for_abandon(repo_root, run_id)
    except RunLockError as exc:
        return AbandonResult(ok=False, reason=str(exc))

    # Codex closure review (confirmed, major): an earlier revision only
    # released the lock on the specific paths it explicitly coded,
    # leaving it held forever if `load_checkpoint`/`reclaim_orphaned_
    # service`/`checkpoint.terminal(...)`/`clear_reservation()` ever
    # raised an unexpected exception (e.g. a plain `OSError`) instead of
    # returning normally -- the same class of gap already fixed in
    # `resume_run`.
    try:
        checkpoint, read_error = load_checkpoint(repo_root, run_id)
        if checkpoint is None:
            return AbandonResult(ok=False, reason=f"could not read checkpoint for run {run_id}: {read_error}")

        for identity in checkpoint.service_process_identities:
            ok, reason = reclaim_orphaned_service(identity)
            if not ok:
                return AbandonResult(ok=False, reason=f"orphaned process reclamation failed: {reason}")

        # Codex closure review (confirmed, major): the terminal write
        # must be the *last* durable step, never the first -- an
        # earlier revision wrote `terminal_outcome="ABANDONED"` before
        # `clear_reservation()`, so an exception from it (still inside
        # this `try`) would report `ok=False` while the checkpoint
        # already, incorrectly, showed this run as concluded --
        # violating AC-041's "a failed abandon leaves the run
        # PAUSED_RETRYABLE" guarantee for that specific failure.
        # `clear_reservation()` is a real, propagating step (an
        # `OSError` here correctly blocks terminalization, caught by
        # this function's own `except Exception` below); only once it
        # has actually completed does this write the one truly
        # irreversible step.
        #
        # `_safely_discard`, by contrast, is deliberately best-effort
        # and non-raising (same as `peos/workflow.py`'s own
        # `_discard_candidate_workspace`, used for every *other*
        # terminal outcome): a workspace-cleanup failure wastes disk
        # space, never correctness, and is consistent with the rest of
        # this codebase's treatment of candidate-workspace discard as
        # non-blocking everywhere it happens -- a deliberate scope
        # decision, not an oversight. AC-041's own guarantee is scoped
        # to orphaned-process reclamation failure, already enforced
        # above, and to this function's own unexpected-exception
        # handling, enforced by placing the true terminal write last.
        workspace = _candidate_workspace_for(repo_root, checkpoint)
        _safely_discard(repo_root, run_id, workspace)
        lock.clear_reservation()

        manager = CheckpointManager(repo_root, run_id, require_fresh=False)
        manager.seed_from(checkpoint)
        manager.terminal("ABANDONED")
        return AbandonResult(ok=True)
    except Exception as exc:  # noqa: BLE001 -- never leave the lock held on an unexpected failure.
        return AbandonResult(ok=False, reason=f"unhandled exception while abandoning run {run_id}: {exc}")
    finally:
        lock.release()


@dataclass(frozen=True)
class InspectResult:
    found: bool
    checkpoint: RunCheckpoint | None = None
    is_paused_retryable: bool = False
    error: str | None = None


def inspect_run(repo_root: Path, run_id: str) -> InspectResult:
    """`./bin/peos inspect <run_id>`. Strictly read-only -- never
    acquires the lock at all (reading the checkpoint needs no
    exclusivity)."""
    checkpoint, error = load_checkpoint(repo_root, run_id)
    if checkpoint is None:
        return InspectResult(found=False, error=error)
    is_paused = checkpoint.terminal_outcome is None
    return InspectResult(found=True, checkpoint=checkpoint, is_paused_retryable=is_paused)
