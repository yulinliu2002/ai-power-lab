"""Integration tests for peos/resume.py (SPEC-007 PEOS Durable Run Resume
V1) -- `resume`/`inspect`/`abandon` against real `run_workflow` runs,
genuinely interrupted (an injected agent callable raises `KeyboardInterrupt`,
which `run_workflow` never catches, so the run dies leaving a real,
durable, non-terminal checkpoint and candidate workspace on disk) and
then resumed, inspected, or abandoned for real.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from peos.checkpoint import load_checkpoint
from peos.claude_agent import ClaudeRunResult
from peos.resume import abandon_run, inspect_run, resume_run
from peos.run_lock import LOCK_RELATIVE_PATH
from peos.workflow import run_workflow

from tests._peos_fixtures import make_minimal_repo
from tests.test_peos_workflow import (
    _approve_review,
    _changes_required_review,
    _execution_not_completed_claude,
    _ok_claude,
    _pass_verification,
    _resolver_returns,
    _spec_for,
    _valid_environ,
)


def _find_run_id(repo_root) -> str:
    runs_dir = repo_root / ".peos" / "runs"
    candidates = [p.name for p in runs_dir.iterdir() if p.is_dir()]
    assert len(candidates) == 1, f"expected exactly one run directory, found {candidates}"
    return candidates[0]


def _interrupt_during_claude_implementation(tmp_path, repo_root):
    def exploding_claude(prompt, cwd, env=None, **kwargs):
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        run_workflow(
            "task", repo_root, log=lambda msg: None,
            spec_resolver=_resolver_returns(_spec_for(repo_root)),
            claude_runner=exploding_claude,
            verifier=lambda workspace, repo_root, plan: _pass_verification(),
            codex_runner=lambda prompt, cwd, env=None, **kwargs: _approve_review(),
            environ=_valid_environ(tmp_path),
        )
    return _find_run_id(repo_root)


def test_interruption_leaves_a_durable_non_terminal_checkpoint_and_frees_the_lock(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    run_id = _interrupt_during_claude_implementation(tmp_path, repo_root)

    checkpoint, error = load_checkpoint(repo_root, run_id)
    assert error is None
    assert checkpoint.terminal_outcome is None
    assert checkpoint.active_phase == "CLAUDE_IMPLEMENTATION"
    assert checkpoint.active_phase_state == "ENTERED"
    assert checkpoint.last_safely_completed_phase == "PLANNING"
    # The candidate workspace survived, durably, under this run's own directory.
    assert (repo_root / checkpoint.workspace_root_relative_path).is_dir()
    # The lock was released on the way out (run_workflow's finally).
    import fcntl
    import os
    fd = os.open(str(repo_root / LOCK_RELATIVE_PATH), os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)  # must not raise
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def test_ordinary_new_task_is_blocked_while_the_interrupted_run_is_still_paused(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    _interrupt_during_claude_implementation(tmp_path, repo_root)

    result = run_workflow(
        "a different task", repo_root, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None, **kwargs: _approve_review(),
        environ=_valid_environ(tmp_path),
    )
    assert result.outcome == "FAILED"
    assert "resume" in (result.gate_reason or "").lower() or "abandon" in (result.gate_reason or "").lower()


def test_resume_completes_the_interrupted_run_without_redoing_cycle_zero_as_a_new_cycle(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    run_id = _interrupt_during_claude_implementation(tmp_path, repo_root)

    result = resume_run(
        repo_root, run_id, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None, **kwargs: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None, **kwargs: _approve_review(),
        environ=_valid_environ(tmp_path),
    )
    assert result.outcome == "APPROVED"
    assert result.run_id == run_id
    # Cycle 0 is never counted against max_cycles -- confirmed unaffected.
    assert result.remediation_cycles_run == 0

    checkpoint, _ = load_checkpoint(repo_root, run_id)
    assert checkpoint.terminal_outcome == "APPROVED"


def test_resume_after_claude_implementation_completed_does_not_redo_it(tmp_path):
    """Codex implementation review (confirmed, major): an earlier
    revision of the resume re-entry logic had no middle ground between
    'skip cycle 0 entirely' and 'redo all of cycle 0' -- interrupting
    specifically during LOCAL_VERIFICATION or CODEX_INDEPENDENT_REVIEW,
    *after* CLAUDE_IMPLEMENTATION had already reached COMPLETED, would
    wrongly re-invoke Claude implementation on resume (violating
    AC-003/AC-005/AC-006). This reproduces that exact scenario and
    confirms Claude is never called again."""
    repo_root = make_minimal_repo(tmp_path)
    claude_calls = []

    def claude_once_then_explode(prompt, cwd, env=None, **kwargs):
        claude_calls.append(prompt)
        return _ok_claude()

    def exploding_codex(prompt, cwd, env=None, **kwargs):
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        run_workflow(
            "task", repo_root, log=lambda msg: None,
            spec_resolver=_resolver_returns(_spec_for(repo_root)),
            claude_runner=claude_once_then_explode,
            verifier=lambda workspace, repo_root, plan: _pass_verification(),
            codex_runner=exploding_codex,
            environ=_valid_environ(tmp_path),
        )
    assert len(claude_calls) == 1
    run_id = _find_run_id(repo_root)
    checkpoint, _ = load_checkpoint(repo_root, run_id)
    assert checkpoint.active_phase == "CODEX_INDEPENDENT_REVIEW"
    assert checkpoint.active_phase_state == "ENTERED"
    assert checkpoint.last_safely_completed_phase == "LOCAL_VERIFICATION"

    resumed_claude_calls = []

    def resumed_claude(prompt, cwd, env=None, **kwargs):
        resumed_claude_calls.append(prompt)
        return _ok_claude()

    result = resume_run(
        repo_root, run_id, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=resumed_claude,
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None, **kwargs: _approve_review(),
        environ=_valid_environ(tmp_path),
    )
    assert result.outcome == "APPROVED"
    assert len(resumed_claude_calls) == 0  # Claude's completed result is never redone.


def test_resume_mid_remediation_cycle_redoes_exactly_that_cycle_never_a_new_one(tmp_path):
    """Interrupt mid-CLAUDE_REMEDIATION cycle 1 (after cycle 0 fully
    completed with CHANGES_REQUIRED); resume must redo cycle 1's Claude
    call exactly once, never allocate cycle 2 for the same logical work
    (SPEC-007 AC-002/AC-008/AC-027)."""
    repo_root = make_minimal_repo(tmp_path)

    claude_calls = []

    def claude_then_explode(prompt, cwd, env=None, **kwargs):
        claude_calls.append(prompt)
        if len(claude_calls) == 1:
            return _ok_claude()
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        run_workflow(
            "task", repo_root, log=lambda msg: None,
            spec_resolver=_resolver_returns(_spec_for(repo_root)),
            claude_runner=claude_then_explode,
            verifier=lambda workspace, repo_root, plan: _pass_verification(),
            codex_runner=lambda prompt, cwd, env=None, **kwargs: _changes_required_review(),
            environ=_valid_environ(tmp_path),
            max_cycles=3,
        )
    run_id = _find_run_id(repo_root)
    checkpoint, _ = load_checkpoint(repo_root, run_id)
    assert checkpoint.active_phase == "CLAUDE_REMEDIATION"
    assert checkpoint.active_phase_state == "ENTERED"
    assert checkpoint.current_cycle == 0  # cycle 1 allocated, not yet countable

    resumed_claude_calls = []

    def resumed_claude(prompt, cwd, env=None, **kwargs):
        resumed_claude_calls.append(prompt)
        return _ok_claude()

    result = resume_run(
        repo_root, run_id, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=resumed_claude,
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None, **kwargs: _approve_review(resolves=("0.1",)),
        environ=_valid_environ(tmp_path),
    )
    assert result.outcome == "APPROVED"
    assert result.remediation_cycles_run == 1  # exactly cycle 1, never cycle 2
    assert len(resumed_claude_calls) == 1  # cycle 1's own Claude call, redone exactly once


def test_resume_after_claude_remediation_completed_does_not_redo_it_and_preserves_disputes(tmp_path):
    """The remediation-cycle analogue of
    test_resume_after_claude_implementation_completed_does_not_redo_it:
    interrupting during remediation cycle 1's own LOCAL_VERIFICATION or
    CODEX_CLOSURE_REVIEW, after CLAUDE_REMEDIATION already COMPLETED,
    must never redo that Claude call on resume -- and any dispute it
    raised must survive (persisted as part of CLAUDE_REMEDIATION's own
    COMPLETED write, not only at CODEX_CLOSURE_REVIEW's)."""
    repo_root = make_minimal_repo(tmp_path)
    claude_calls = []

    def claude_raises_a_dispute(prompt, cwd, env=None, **kwargs):
        claude_calls.append(prompt)
        return ClaudeRunResult(
            returncode=0, stdout="", stderr="", status="COMPLETED",
            gate_category=None, gate_reason=None, summary="done", ok=True,
            dispute_attempt_lines=("DISPUTE[0.1]: this finding is already fixed",),
        )

    codex_calls = []

    def codex_then_explode(prompt, cwd, env=None, **kwargs):
        codex_calls.append(prompt)
        if len(codex_calls) == 1:
            return _changes_required_review()
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        run_workflow(
            "task", repo_root, log=lambda msg: None,
            spec_resolver=_resolver_returns(_spec_for(repo_root)),
            claude_runner=claude_raises_a_dispute,
            verifier=lambda workspace, repo_root, plan: _pass_verification(),
            codex_runner=codex_then_explode,
            environ=_valid_environ(tmp_path),
            max_cycles=3,
        )
    assert len(claude_calls) == 2  # cycle 0 implementation + cycle 1 remediation
    run_id = _find_run_id(repo_root)
    checkpoint, _ = load_checkpoint(repo_root, run_id)
    assert checkpoint.active_phase == "CODEX_CLOSURE_REVIEW"
    assert checkpoint.active_phase_state == "ENTERED"
    assert len(checkpoint.active_disputes) == 1
    assert checkpoint.active_disputes[0].reference == "0.1"

    resumed_claude_calls = []

    def resumed_claude(prompt, cwd, env=None, **kwargs):
        resumed_claude_calls.append(prompt)
        return _ok_claude()

    resumed_codex_calls = []

    def resumed_codex(prompt, cwd, env=None, **kwargs):
        resumed_codex_calls.append(kwargs)
        return _approve_review(resolves=("0.1",))

    result = resume_run(
        repo_root, run_id, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=resumed_claude,
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=resumed_codex,
        environ=_valid_environ(tmp_path),
    )
    assert result.outcome == "APPROVED"
    assert len(resumed_claude_calls) == 0  # the completed remediation call is never redone
    # The dispute raised before the interruption is still active and
    # passed through to the fresh closure-review call.
    assert resumed_codex_calls
    assert resumed_codex_calls[0].get("active_dispute_references") == frozenset({"0.1"})


def test_inspect_reports_paused_retryable_for_a_non_terminal_run(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    run_id = _interrupt_during_claude_implementation(tmp_path, repo_root)

    result = inspect_run(repo_root, run_id)
    assert result.found is True
    assert result.is_paused_retryable is True
    assert result.checkpoint.run_id == run_id


def test_inspect_reports_not_found_for_an_unknown_run_id(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    result = inspect_run(repo_root, "no-such-run-id")
    assert result.found is False


def test_abandon_terminalizes_discards_workspace_and_frees_the_lock(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    run_id = _interrupt_during_claude_implementation(tmp_path, repo_root)
    checkpoint, _ = load_checkpoint(repo_root, run_id)
    candidate_dir = (repo_root / checkpoint.workspace_root_relative_path).parent
    assert candidate_dir.is_dir()

    result = abandon_run(repo_root, run_id)
    assert result.ok is True

    assert not candidate_dir.exists()
    reloaded, _ = load_checkpoint(repo_root, run_id)
    assert reloaded.terminal_outcome == "ABANDONED"

    # A subsequent ordinary task now proceeds normally (AC-037).
    new_result = run_workflow(
        "another task", repo_root, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None, **kwargs: _approve_review(),
        environ=_valid_environ(tmp_path),
    )
    assert new_result.outcome == "APPROVED"


def test_abandon_never_writes_outside_dot_peos(tmp_path):
    """SPEC-007 AC-040: abandon never writes/modifies/stages anything
    under repo_root outside .peos/ (a scope that includes the shared
    lock file itself)."""
    repo_root = make_minimal_repo(tmp_path)
    run_id = _interrupt_during_claude_implementation(tmp_path, repo_root)

    before = {
        p.relative_to(repo_root) for p in repo_root.rglob("*")
        if ".peos" not in p.parts and ".git" not in p.parts
    }
    abandon_run(repo_root, run_id)
    after = {
        p.relative_to(repo_root) for p in repo_root.rglob("*")
        if ".peos" not in p.parts and ".git" not in p.parts
    }
    assert before == after


def test_abandon_releases_the_lock_even_on_an_unexpected_exception(tmp_path, monkeypatch):
    """Codex closure review (confirmed, major, new issue): an earlier
    revision of `abandon_run` had no enclosing `finally` -- an
    unexpected exception from checkpoint persistence or
    `clear_reservation()` would have left the flock held forever (even
    though the run's checkpoint itself is correctly left non-terminal,
    still blocking an *ordinary* new task -- this test isolates the
    flock specifically, via a direct, unlocked probe, from that
    separate, correctly-unchanged reservation state)."""
    import fcntl
    import os

    import peos.resume as resume_module
    from peos.run_lock import LOCK_RELATIVE_PATH

    repo_root = make_minimal_repo(tmp_path)
    run_id = _interrupt_during_claude_implementation(tmp_path, repo_root)

    def exploding_checkpoint_manager(*args, **kwargs):
        raise OSError("simulated unexpected failure building the checkpoint manager")

    monkeypatch.setattr(resume_module, "CheckpointManager", exploding_checkpoint_manager)

    result = abandon_run(repo_root, run_id)
    assert result.ok is False
    assert "simulated unexpected failure" in (result.reason or "")

    # The flock itself was still released on the way out.
    fd = os.open(str(repo_root / LOCK_RELATIVE_PATH), os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)  # must not raise
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)

    # AC-041: a failed abandon leaves the run PAUSED_RETRYABLE -- the
    # checkpoint must never show ABANDONED when the operation itself
    # reported failure.
    checkpoint, _ = load_checkpoint(repo_root, run_id)
    assert checkpoint.terminal_outcome is None


def test_abandon_never_terminalizes_if_clear_reservation_fails_after_discard(tmp_path, monkeypatch):
    """Codex closure review (confirmed, major): an earlier revision
    wrote `terminal_outcome="ABANDONED"` *before* workspace discard and
    `clear_reservation()` -- an exception from either would report
    `ok=False` while the checkpoint already, incorrectly, showed this
    run as concluded. Fixed by making the terminal write strictly the
    last step. Reproduced here by forcing `clear_reservation()` itself
    to fail, which runs *after* workspace discard but *before* the
    (now-reordered) terminal write."""
    from peos.run_lock import RunLock

    repo_root = make_minimal_repo(tmp_path)
    run_id = _interrupt_during_claude_implementation(tmp_path, repo_root)

    def exploding_clear_reservation(self):
        raise OSError("simulated disk error clearing the reservation")

    monkeypatch.setattr(RunLock, "clear_reservation", exploding_clear_reservation)

    result = abandon_run(repo_root, run_id)
    assert result.ok is False

    checkpoint, _ = load_checkpoint(repo_root, run_id)
    assert checkpoint.terminal_outcome is None


def test_resuming_an_already_abandoned_run_fails_closed(tmp_path):
    repo_root = make_minimal_repo(tmp_path)
    run_id = _interrupt_during_claude_implementation(tmp_path, repo_root)
    abandon_run(repo_root, run_id)

    result = resume_run(repo_root, run_id, environ=_valid_environ(tmp_path))
    assert result.outcome == "FAILED"


def test_checkpoint_persistence_survives_a_real_process_boundary_via_the_cli(tmp_path):
    """SPEC-007's core persistence guarantee, verified across a genuine
    OS process boundary -- every other test in this module calls
    `inspect_run`/`resume_run`/`abandon_run` directly, in the same
    interpreter that wrote the checkpoint. Here, the checkpoint is read
    (and then terminalized) by a freshly spawned `python -m peos.cli`
    process that never shared memory with the process that paused the
    run -- proving the on-disk checkpoint, not any in-process cache or
    object graph, is what `inspect`/`abandon` actually depend on. No
    live Claude/Codex is invoked (both are the same injected fakes every
    other test in this file uses)."""
    repo_root = make_minimal_repo(tmp_path)
    run_id = _interrupt_during_claude_implementation(tmp_path, repo_root)

    inspect_proc = subprocess.run(
        [sys.executable, "-m", "peos.cli", "inspect", run_id, "--repo", str(repo_root)],
        capture_output=True, text=True, timeout=30,
    )
    assert inspect_proc.returncode == 0, inspect_proc.stderr
    assert "PAUSED_RETRYABLE" in inspect_proc.stdout
    assert "CLAUDE_IMPLEMENTATION" in inspect_proc.stdout

    abandon_proc = subprocess.run(
        [sys.executable, "-m", "peos.cli", "abandon", run_id, "--repo", str(repo_root)],
        capture_output=True, text=True, timeout=30,
    )
    assert abandon_proc.returncode == 0, abandon_proc.stderr
    assert "abandoned" in abandon_proc.stdout.lower()

    checkpoint, error = load_checkpoint(repo_root, run_id)
    assert error is None
    assert checkpoint.terminal_outcome == "ABANDONED"


def test_authoritative_drift_on_resume_routes_to_the_human_gate(tmp_path):
    """SPEC-007 AC-012: a new commit landing on HEAD between the
    original run and resume, with every integrity check already passing,
    routes to GATE_AUTHORITATIVE_DRIFT_ON_RESUME."""
    repo_root = make_minimal_repo(tmp_path)
    run_id = _interrupt_during_claude_implementation(tmp_path, repo_root)

    import subprocess
    (repo_root / "new_file.txt").write_text("drift\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=str(repo_root), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "drift"], cwd=str(repo_root), check=True, capture_output=True,
    )

    result = resume_run(repo_root, run_id, environ=_valid_environ(tmp_path))
    assert result.outcome == "HUMAN_GATE"
    assert result.gate_id == "13"


def test_uncommitted_working_tree_drift_on_resume_also_routes_to_the_human_gate(tmp_path):
    """Codex closure review (confirmed, major): the HEAD-commit check
    alone cannot detect an *uncommitted* tracked-file edit (same HEAD,
    different content) made to the authoritative repository during the
    pause -- a freshly-rebuilt reconciliation manifest would otherwise
    silently adopt that edit as "the original" and overwrite it without
    ever flagging it. A content-based fingerprint, captured at Planning
    and re-checked at resume, must catch this too."""
    repo_root = make_minimal_repo(tmp_path)
    run_id = _interrupt_during_claude_implementation(tmp_path, repo_root)

    before_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo_root), capture_output=True, text=True, check=True,
    ).stdout.strip()

    # An uncommitted edit to an already-tracked, non-governance file --
    # HEAD is unchanged (a governance-file edit would instead be caught
    # as governance mutation by check 6, a distinct, earlier case).
    (repo_root / "tests" / "test_placeholder.py").write_text(
        "def test_ok():\n    assert True  # edited while paused, never committed\n", encoding="utf-8",
    )

    after_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo_root), capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert before_head == after_head

    result = resume_run(
        repo_root, run_id,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        environ=_valid_environ(tmp_path),
    )
    assert result.outcome == "HUMAN_GATE"
    assert result.gate_id == "13"
    assert "working-tree" in (result.gate_reason or "").lower()


def test_ac056_partial_claude_mutation_of_staged_governance_fails_closed(tmp_path):
    """SPEC-007 AC-056: a partial CLAUDE_IMPLEMENTATION/REMEDIATION
    attempt that mutated the workspace's own *staged* CLAUDE.md copy
    (while repo_root's own copy is untouched) must be detected by the
    staged-copy governance check during partial-candidate recovery and
    fail closed, never silently proceed into resumed execution."""
    repo_root = make_minimal_repo(tmp_path)
    run_id = _interrupt_during_claude_implementation(tmp_path, repo_root)

    checkpoint, _ = load_checkpoint(repo_root, run_id)
    staged_claude_md = repo_root / checkpoint.workspace_root_relative_path / "CLAUDE.md"
    assert staged_claude_md.is_file()
    staged_claude_md.write_text("mutated by a partial Claude attempt\n", encoding="utf-8")

    result = resume_run(
        repo_root, run_id,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        environ=_valid_environ(tmp_path),
    )
    assert result.outcome == "FAILED"
    assert "staged" in (result.gate_reason or "").lower() or "CLAUDE.md" in (result.gate_reason or "")


def test_a_paused_retryable_run_from_a_transient_claude_failure_is_resumable(tmp_path):
    """SPEC-007 Decision 3: a run paused by a positively-identified
    transient agent-execution failure (PAUSED_RETRYABLE) is just as
    resumable as one interrupted by a real process kill -- both leave
    the identical durable checkpoint shape (non-terminal, candidate
    workspace preserved, lock released)."""
    repo_root = make_minimal_repo(tmp_path)

    result = run_workflow(
        "task", repo_root, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None: _execution_not_completed_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None, **kwargs: _approve_review(),
        environ=_valid_environ(tmp_path),
    )
    assert result.outcome == "PAUSED_RETRYABLE"
    run_id = _find_run_id(repo_root)

    inspected = inspect_run(repo_root, run_id)
    assert inspected.is_paused_retryable is True

    resumed_result = resume_run(
        repo_root, run_id, log=lambda msg: None,
        spec_resolver=_resolver_returns(_spec_for(repo_root)),
        claude_runner=lambda prompt, cwd, env=None, **kwargs: _ok_claude(),
        verifier=lambda workspace, repo_root, plan: _pass_verification(),
        codex_runner=lambda prompt, cwd, env=None, **kwargs: _approve_review(),
        environ=_valid_environ(tmp_path),
    )
    assert resumed_result.outcome == "APPROVED"
