"""Tests for peos/run_lock.py (SPEC-007 "Workspace Lifecycle and
One-Run-Per-Repository")."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os

import pytest

from peos.checkpoint import CheckpointWriter, RunCheckpoint
from peos.run_lock import (
    ActiveRunExistsError,
    BootstrapInProgressError,
    LockBusyError,
    LockCorruptedError,
    LOCK_RELATIVE_PATH,
    NoSuchRunError,
    NothingToResumeError,
    RunAlreadyConcludedError,
    acquire_for_abandon,
    acquire_for_new_task,
    acquire_for_resume,
)


def _write_checkpoint(repo_root, run_id, *, terminal_outcome=None, active_phase="PLANNING"):
    writer = CheckpointWriter(repo_root, run_id)
    writer.write(RunCheckpoint(
        schema_version="1", run_id=run_id, resume_generation=0, created_at="t0", updated_at="t0",
        task="", authoritative_baseline="", governing_spec_relative_path="", governing_spec_content_hash="",
        governing_spec_source="auto_detected", governing_spec_original_path="", effective_max_cycles=1,
        active_phase=active_phase, active_phase_state="ENTERED", last_safely_completed_phase="",
        current_cycle=0, workspace_root_relative_path="", workspace_home_dir_relative_path="",
        workspace_baseline_commit="", current_workspace_snapshot_identity="",
        terminal_outcome=terminal_outcome,
    ))


def test_acquire_for_new_task_succeeds_when_slot_is_free(tmp_path):
    lock = acquire_for_new_task(tmp_path, "run1")
    try:
        content = json.loads((tmp_path / LOCK_RELATIVE_PATH).read_bytes()[:-64])
        assert content["run_id"] == "run1"
        assert content["pid"] == os.getpid()
    finally:
        lock.release()


def test_acquire_for_new_task_blocks_on_an_active_non_terminal_run(tmp_path):
    lock1 = acquire_for_new_task(tmp_path, "run1")
    _write_checkpoint(tmp_path, "run1", terminal_outcome=None)
    try:
        # Simulate a second, independent process attempting a new task:
        # open a *second* fd on the same lock file and try to flock it
        # non-blocking -- this is what `acquire_for_new_task` does
        # internally, so reproduce the EWOULDBLOCK condition directly.
        fd = os.open(str(tmp_path / LOCK_RELATIVE_PATH), os.O_RDWR)
        try:
            with pytest.raises(OSError):
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(fd)
    finally:
        lock1.release()


def test_acquire_for_new_task_reclaims_a_terminal_checkpoint(tmp_path):
    lock1 = acquire_for_new_task(tmp_path, "run1")
    _write_checkpoint(tmp_path, "run1", terminal_outcome="APPROVED")
    lock1.release()

    lock2 = acquire_for_new_task(tmp_path, "run2")
    try:
        content = json.loads((tmp_path / LOCK_RELATIVE_PATH).read_bytes()[:-64])
        assert content["run_id"] == "run2"
    finally:
        lock2.release()


def test_acquire_for_new_task_fails_closed_on_non_terminal_checkpoint_even_with_dead_pid(tmp_path):
    """SPEC-007 AC-059: a PAUSED_RETRYABLE run's lock (most commonly with
    its process already dead) is NOT reclaimed by ordinary execution --
    proven here by using a pid that is provably dead (a freshly
    `os.fork`ed-and-waited child's pid is guaranteed gone) alongside a
    *non-terminal* checkpoint."""
    lock1 = acquire_for_new_task(tmp_path, "run1")
    lock1.write_reservation(run_id="run1", pid=_dead_pid())
    lock1.release()
    _write_checkpoint(tmp_path, "run1", terminal_outcome=None)

    with pytest.raises(ActiveRunExistsError) as excinfo:
        acquire_for_new_task(tmp_path, "run2")
    assert excinfo.value.run_id == "run1"


def _dead_pid() -> int:
    pid = os.fork()
    if pid == 0:
        os._exit(0)
    os.waitpid(pid, 0)
    return pid


def test_acquire_for_new_task_bootstrap_gap_blocks_while_pid_alive(tmp_path):
    """No checkpoint at all yet (the bootstrap gap) + a genuinely live
    recorded pid (this test process itself) must fail closed, never
    reclaimed, regardless of the fact that no checkpoint exists."""
    lock1 = acquire_for_new_task(tmp_path, "run1")
    lock1.write_reservation(run_id="run1", pid=os.getpid())
    lock1.release()
    # No checkpoint written for run1 at all.

    with pytest.raises(BootstrapInProgressError):
        acquire_for_new_task(tmp_path, "run2")


def test_acquire_for_new_task_bootstrap_gap_reclaims_once_pid_is_dead(tmp_path):
    lock1 = acquire_for_new_task(tmp_path, "run1")
    lock1.write_reservation(run_id="run1", pid=_dead_pid())
    lock1.release()

    lock2 = acquire_for_new_task(tmp_path, "run2")
    try:
        content = json.loads((tmp_path / LOCK_RELATIVE_PATH).read_bytes()[:-64])
        assert content["run_id"] == "run2"
    finally:
        lock2.release()


def test_corrupted_hash_mismatch_fails_closed_never_treated_as_empty(tmp_path):
    """SPEC-007 Round 9: a hybrid of old+new bytes that still parses as
    valid JSON (no trailing bytes) but whose hash no longer matches must
    be rejected -- proven here by constructing exactly that byte
    pattern directly, bypassing the write path entirely."""
    lock_path = tmp_path / LOCK_RELATIVE_PATH
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    old_json = json.dumps({"run_id": "aaaaaaaaaaaa", "pid": 111111, "claimed_at": "t0"}, sort_keys=True).encode()
    new_json = json.dumps({"run_id": "bbbbbbbbbbbb", "pid": 222222, "claimed_at": "t0"}, sort_keys=True).encode()
    assert len(old_json) == len(new_json)
    # Splice: first half of new content's bytes, second half of old's --
    # still a syntactically complete, parseable JSON object (both inputs
    # share the exact same key ordering/structure/length), but the
    # trailing hash (computed over old_json) no longer matches.
    split = len(old_json) // 2
    hybrid_json = new_json[:split] + old_json[split:]
    hybrid = hybrid_json + hashlib.sha256(old_json).hexdigest().encode("ascii")
    lock_path.write_bytes(hybrid)

    with pytest.raises(LockCorruptedError):
        acquire_for_new_task(tmp_path, "run3")


def test_truncated_content_fails_closed(tmp_path):
    lock_path = tmp_path / LOCK_RELATIVE_PATH
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_bytes(b"not even close to valid")

    with pytest.raises(LockCorruptedError):
        acquire_for_new_task(tmp_path, "run1")


def test_acquire_for_resume_matches_and_takes_over_execution_ownership(tmp_path):
    lock1 = acquire_for_new_task(tmp_path, "run1")
    _write_checkpoint(tmp_path, "run1", terminal_outcome=None)
    lock1.release()

    lock2 = acquire_for_resume(tmp_path, "run1")
    try:
        content = json.loads((tmp_path / LOCK_RELATIVE_PATH).read_bytes()[:-64])
        assert content["run_id"] == "run1"
        assert content["pid"] == os.getpid()
    finally:
        lock2.release()


def test_acquire_for_resume_rejects_a_mismatched_run_id(tmp_path):
    lock1 = acquire_for_new_task(tmp_path, "run1")
    _write_checkpoint(tmp_path, "run1", terminal_outcome=None)
    lock1.release()

    with pytest.raises(NoSuchRunError):
        acquire_for_resume(tmp_path, "run-does-not-exist")


def test_acquire_for_resume_rejects_an_already_terminal_run(tmp_path):
    lock1 = acquire_for_new_task(tmp_path, "run1")
    _write_checkpoint(tmp_path, "run1", terminal_outcome="APPROVED")
    lock1.release()

    with pytest.raises(RunAlreadyConcludedError):
        acquire_for_resume(tmp_path, "run1")


def test_acquire_for_resume_bootstrap_gap_fails_with_nothing_to_resume(tmp_path):
    lock1 = acquire_for_new_task(tmp_path, "run1")
    lock1.write_reservation(run_id="run1", pid=os.getpid())
    lock1.release()
    # No checkpoint ever written for run1.

    with pytest.raises(NothingToResumeError):
        acquire_for_resume(tmp_path, "run1")


def test_two_concurrent_resume_attempts_for_the_same_run_only_one_succeeds(tmp_path):
    """SPEC-007 AC-066: the non-blocking flock itself, not merely the
    matching-run_id check, is what prevents two concurrent resumers."""
    lock1 = acquire_for_new_task(tmp_path, "run1")
    _write_checkpoint(tmp_path, "run1", terminal_outcome=None)
    lock1.release()

    winner = acquire_for_resume(tmp_path, "run1")
    try:
        fd = os.open(str(tmp_path / LOCK_RELATIVE_PATH), os.O_RDWR)
        try:
            with pytest.raises(OSError):
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(fd)
    finally:
        winner.release()


def test_acquire_for_abandon_matches_but_does_not_rewrite_reservation(tmp_path):
    lock1 = acquire_for_new_task(tmp_path, "run1")
    _write_checkpoint(tmp_path, "run1", terminal_outcome=None)
    original_pid = os.getpid()
    lock1.release()

    lock2 = acquire_for_abandon(tmp_path, "run1")
    try:
        content = json.loads((tmp_path / LOCK_RELATIVE_PATH).read_bytes()[:-64])
        # Content is untouched by acquire_for_abandon itself -- still the
        # original reservation written by acquire_for_new_task.
        assert content["run_id"] == "run1"
        assert content["pid"] == original_pid
    finally:
        lock2.release()


def test_lock_release_actually_releases_the_flock_for_the_next_acquirer(tmp_path):
    lock1 = acquire_for_new_task(tmp_path, "run1")
    _write_checkpoint(tmp_path, "run1", terminal_outcome="FAILED")
    lock1.release()

    lock2 = acquire_for_new_task(tmp_path, "run2")
    lock2.release()
