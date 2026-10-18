"""Shared repository-level run lock (SPEC-007 "Workspace Lifecycle and
One-Run-Per-Repository", Decisions 2/11; ADR-0004 Decision 6).

Enforces "at most one active-or-paused PEOS run per repository" across
every entry point (an ordinary new task, `peos resume`, `peos abandon`).
Two genuinely different things are represented here, deliberately kept
separate (see docs/decisions/0004 and SPEC-007's own "Workspace
Lifecycle" section for the full history of why three earlier designs --
a plain `os.rename` replacement, an `unlink`-then-`O_EXCL`-create retry
loop, and a briefly-held `flock` -- were each found unsafe):

- **The logical reservation** -- "does this `run_id` still hold the
  repository's one active-or-paused slot" -- represented by the
  checkpoint's own durable `terminal_outcome` (`peos/checkpoint.py`),
  never by process liveness: the defining property of a
  `PAUSED_RETRYABLE` run is that its process is gone while its
  reservation must still hold.
- **Current execution ownership** -- "is some process actively running
  PEOS for this run_id, right now" -- represented by `fcntl.flock`, a
  kernel-enforced advisory lock, acquired **non-blocking** and **held
  for a holder's entire active execution** (through Planning, every
  remediation cycle, reconciliation, and the final report for an
  ordinary run or `resume`; through reclamation and terminalization for
  `abandon`) -- never released early, never re-acquired mid-run, and
  automatically released by the OS the instant its holding process exits
  for any reason, including `SIGKILL`.

The reservation file's content is **self-verifying, not merely
well-formed JSON**: a write interrupted partway through an equal-length-
or-shorter overwrite can leave a syntactically valid but semantically
bogus hybrid of old and new bytes that no amount of JSON-syntax checking
(even "reject trailing bytes") can detect. The content written is
therefore the JSON payload immediately followed by the SHA-256 hex digest
(exactly 64 ASCII characters) of that exact payload; every read requires
the JSON portion to parse cleanly, consuming every byte, *and* its hash
to match the trailing digest exactly. The write sequence is write-first,
truncate-last: write the complete new content (a loop that accumulates
`os.write`'s own returned byte count -- POSIX permits short writes),
`fsync`, *then* `ftruncate` to the new exact length (trimming any
leftover tail from previous, longer content), a final `fsync` -- entirely
while the flock is held. No `rename`/`unlink` is ever used: either would
operate on the *path* while `flock` is tied to the specific open file
description, letting a second caller's fresh `open()` of a renamed-in
file acquire an entirely unlocked `flock` of its own.

**Named, accepted limitation (PID reuse):** in the "no checkpoint at all"
bootstrap case, if the recorded `pid` is later reused by the OS for an
unrelated, long-lived process, liveness checking will keep reporting
"alive" for as long as that unrelated process lives, blocking every new
task with no automatic recovery. This can only ever fail *safe* (wrongly
refuse to proceed), never fail *unsafe* (wrongly steal an active slot) --
nothing is ever terminated on the basis of this check. PEOS never
resolves this automatically; a human who has independently confirmed the
PID is unrelated may manually delete `.peos/run.lock` outside PEOS.
"""

from __future__ import annotations

import datetime
import fcntl
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from peos.checkpoint import load_checkpoint
from peos.fsguard import fsync_dir_fd, mkdir_tolerant_anchored, open_repo_root

LOCK_BASENAME = "run.lock"
LOCK_RELATIVE_PATH = f".peos/{LOCK_BASENAME}"
_HASH_HEX_LEN = 64


class RunLockError(RuntimeError):
    """Base class for every run-lock failure. Callers must treat any
    instance of this as a reason to fail closed -- never a reason to
    proceed as if the slot were free."""


class LockBusyError(RunLockError):
    """`fcntl.flock(..., LOCK_NB)` returned `EWOULDBLOCK`: another process
    is actively executing something right now."""


class LockCorruptedError(RunLockError):
    """The lock file's content exists but fails the self-verifying
    format's own checks (SPEC-007 AC-064/AC-068) -- never interpreted as
    empty/free, and never accepted merely because its JSON portion alone
    happens to parse."""


class ActiveRunExistsError(RunLockError):
    """An ordinary new-task invocation found an existing, non-reclaimable
    reservation (a live or paused run, or a state PEOS cannot safely
    determine is reclaimable). Carries the blocking `run_id` so the
    caller can direct the human to resume/inspect/abandon it."""

    def __init__(self, message: str, run_id: str | None):
        super().__init__(message)
        self.run_id = run_id


class BootstrapInProgressError(RunLockError):
    """The lock names a `run_id` with no checkpoint yet, and the recorded
    bootstrapper process is still alive (SPEC-007 AC-061) -- never a
    timeout, never reclaimed while genuinely alive."""


class NoSuchRunError(RunLockError):
    """`resume`/`abandon` was given a `run_id` the lock's current content
    does not name (wrong run, or the slot is currently empty)."""


class RunAlreadyConcludedError(RunLockError):
    """`resume`/`abandon` was given a `run_id` whose checkpoint already
    shows a terminal outcome."""


class NothingToResumeError(RunLockError):
    """`resume` was given a `run_id` whose lock exists but whose
    checkpoint does not (SPEC-007 AC-062): `FAILED`, directing the human
    to simply start a new task."""


class CheckpointUnreadableError(RunLockError):
    """The named run's checkpoint.json exists but could not be safely
    read/parsed (SPEC-007 AC-014) -- always `FAILED`."""


@dataclass(frozen=True)
class LockContent:
    run_id: str
    pid: int
    claimed_at: str


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _encode(content: LockContent) -> bytes:
    payload = json.dumps(
        {"run_id": content.run_id, "pid": content.pid, "claimed_at": content.claimed_at},
        sort_keys=True,
    ).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest().encode("ascii")
    return payload + digest


def _decode(raw: bytes) -> LockContent | None:
    """Return the parsed reservation, or `None` if `raw` is empty (the
    one state this format intentionally treats as valid-and-free).
    Raises `LockCorruptedError` for anything else that fails the
    self-verifying format's own checks."""
    if len(raw) == 0:
        return None
    if len(raw) <= _HASH_HEX_LEN:
        raise LockCorruptedError("lock content is malformed: too short to contain a payload plus hash")
    json_part = raw[:-_HASH_HEX_LEN]
    hash_part = raw[-_HASH_HEX_LEN:]
    try:
        hash_hex = hash_part.decode("ascii")
    except UnicodeDecodeError as exc:
        raise LockCorruptedError(f"lock content is malformed: hash suffix is not ASCII: {exc}") from exc
    if hashlib.sha256(json_part).hexdigest() != hash_hex:
        raise LockCorruptedError(
            "lock content is malformed: hash does not match payload (a partial/interrupted write, "
            "never interpreted as empty or free)"
        )
    try:
        decoded = json_part.decode("utf-8")
        data = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LockCorruptedError(f"lock content is malformed: invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise LockCorruptedError("lock content is malformed: JSON payload is not an object")
    try:
        return LockContent(run_id=str(data["run_id"]), pid=int(data["pid"]), claimed_at=str(data["claimed_at"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise LockCorruptedError(f"lock content is malformed: missing/invalid field: {exc}") from exc


def _pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Exists, owned by someone else -- definitely alive. Fail closed
        # (treat as alive) for any other OSError too.
        return True
    except OSError:
        return True
    return True


def _write_locked(fd: int, new_bytes: bytes) -> None:
    """Write-first, truncate-last, entirely while the caller holds the
    flock on `fd` (SPEC-007 Round 8/9 fix). Never `rename`/`unlink`."""
    os.lseek(fd, 0, os.SEEK_SET)
    written = 0
    while written < len(new_bytes):
        n = os.write(fd, new_bytes[written:])
        if n <= 0:
            raise RunLockError("lock write loop made no progress (os.write returned <= 0)")
        written += n
    os.fsync(fd)
    os.ftruncate(fd, len(new_bytes))
    os.fsync(fd)


class RunLock:
    """A held, non-blocking `flock` on `.peos/run.lock`. The caller owns
    this for its entire active execution and must call `release()` on
    every exit path (an unconditional `try`/`finally`), or simply let the
    process exit, which the OS equivalently enforces."""

    def __init__(self, fd: int, repo_root: Path):
        self._fd = fd
        self._repo_root = repo_root
        self._released = False

    def write_reservation(self, run_id: str, pid: int, claimed_at: str | None = None) -> None:
        content = LockContent(run_id=run_id, pid=pid, claimed_at=claimed_at or _now())
        _write_locked(self._fd, _encode(content))

    def clear_reservation(self) -> None:
        _write_locked(self._fd, b"")

    def release(self) -> None:
        if self._released:
            return
        try:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
        finally:
            os.close(self._fd)
            self._released = True

    def __enter__(self) -> "RunLock":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


def _open_lock_fd(repo_root: Path) -> int:
    """Open (creating if necessary) `.peos/run.lock`, `fsync`ing the
    containing `.peos` directory's own fd iff this call is the one that
    actually created the file (its very first-ever creation)."""
    repo_fd = open_repo_root(repo_root)
    if repo_fd is None:
        raise RunLockError(f"repository root is not a safe, real directory: {repo_root}")
    try:
        peos_fd = mkdir_tolerant_anchored(repo_fd, ".peos")
    finally:
        os.close(repo_fd)
    if peos_fd is None:
        raise RunLockError(f"could not safely create/open .peos anchored at the repository root: {repo_root / '.peos'}")
    try:
        created = False
        try:
            fd = os.open(LOCK_BASENAME, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=peos_fd)
            created = True
        except FileExistsError:
            try:
                fd = os.open(LOCK_BASENAME, os.O_RDWR | os.O_NOFOLLOW, dir_fd=peos_fd)
            except OSError as exc:
                raise RunLockError(f"could not open {repo_root / LOCK_RELATIVE_PATH}: {exc}") from exc
        except OSError as exc:
            raise RunLockError(f"could not create {repo_root / LOCK_RELATIVE_PATH}: {exc}") from exc
        if created:
            try:
                fsync_dir_fd(peos_fd)
            except OSError as exc:
                os.close(fd)
                raise RunLockError(f"lock-file directory-entry fsync failed: {exc}") from exc
    finally:
        os.close(peos_fd)
    return fd


def _acquire_flock_or_raise(repo_root: Path) -> RunLock:
    fd = _open_lock_fd(repo_root)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError) as exc:
        os.close(fd)
        raise LockBusyError(
            "another PEOS execution appears to be in progress; wait for it to finish or pause, "
            "or investigate manually."
        ) from exc
    return RunLock(fd, repo_root)


def acquire_for_new_task(repo_root: Path, run_id: str) -> RunLock:
    """SPEC-007 AC-034/035/036/059/060/061. `run_id` is already generated
    by the caller (`peos/workflow.py` generates it before acquiring the
    lock, per SPEC-007's PLANNING-bootstrap ordering) -- this function
    never invents or defers one. Raises `LockBusyError`,
    `LockCorruptedError`, `ActiveRunExistsError`, or
    `BootstrapInProgressError` if the slot is not free; otherwise returns
    a held `RunLock` with a freshly-written reservation naming `run_id`
    and `os.getpid()`."""
    lock = _acquire_flock_or_raise(repo_root)
    try:
        raw = os.pread(lock._fd, 1 << 20, 0)
        content = _decode(raw)
        if content is not None:
            checkpoint, read_error = load_checkpoint(repo_root, content.run_id)
            if read_error is not None:
                raise ActiveRunExistsError(
                    f"an existing run ({content.run_id}) could not be safely inspected ({read_error}); "
                    "refusing to start a new task. Investigate manually.",
                    run_id=content.run_id,
                )
            if checkpoint is None:
                if _pid_is_alive(content.pid):
                    raise BootstrapInProgressError(
                        f"a PEOS run ({content.run_id}) appears to still be starting (bootstrapping); "
                        "please wait for it to finish or fail."
                    )
                # Bootstrapper is provably dead -- reclaimable.
            elif checkpoint.terminal_outcome is None:
                raise ActiveRunExistsError(
                    f"an existing PEOS run ({content.run_id}) is still active or paused "
                    f"(phase={checkpoint.active_phase}); resume, inspect, or abandon it before "
                    "starting a new task.",
                    run_id=content.run_id,
                )
            # Else: terminal checkpoint -- reclaimable now that this
            # process also holds execution ownership (the flock).
        lock.write_reservation(run_id=run_id, pid=os.getpid())
        return lock
    except BaseException:
        # Codex implementation review (confirmed, major): releasing only
        # on RunLockError left the flock held forever if pread/decode/
        # write/fsync ever raised a plain OSError (or any other
        # exception) instead -- broadened to release on *any* exception,
        # since a caller that never gets a `RunLock` back must never be
        # left holding one it cannot see.
        lock.release()
        raise


def acquire_for_resume(repo_root: Path, run_id: str) -> RunLock:
    """SPEC-007 Resume Preflight check 1. Raises `LockBusyError`,
    `LockCorruptedError`, `NoSuchRunError`, `RunAlreadyConcludedError`,
    `NothingToResumeError`, or `CheckpointUnreadableError`; otherwise
    returns a held `RunLock` with its reservation updated to this
    process's own `pid` (taking over execution ownership)."""
    lock = _acquire_flock_or_raise(repo_root)
    try:
        raw = os.pread(lock._fd, 1 << 20, 0)
        content = _decode(raw)
        if content is None:
            raise NoSuchRunError(f"nothing to resume: no run is currently reserved (looking for {run_id}).")
        if content.run_id != run_id:
            raise NoSuchRunError(f"no such run: the current reservation names a different run ({content.run_id}).")
        checkpoint, read_error = load_checkpoint(repo_root, run_id)
        if read_error is not None:
            raise CheckpointUnreadableError(f"checkpoint for run {run_id} could not be safely read: {read_error}")
        if checkpoint is None:
            raise NothingToResumeError(
                f"nothing to resume -- run {run_id} never completed its bootstrap. Start a new task instead."
            )
        if checkpoint.terminal_outcome is not None:
            raise RunAlreadyConcludedError(f"run {run_id} already concluded with outcome={checkpoint.terminal_outcome}.")
        lock.write_reservation(run_id=run_id, pid=os.getpid())
        return lock
    except BaseException:
        # Codex implementation review (confirmed, major): releasing only
        # on RunLockError left the flock held forever if pread/decode/
        # write/fsync ever raised a plain OSError (or any other
        # exception) instead -- broadened to release on *any* exception,
        # since a caller that never gets a `RunLock` back must never be
        # left holding one it cannot see.
        lock.release()
        raise


def acquire_for_abandon(repo_root: Path, run_id: str) -> RunLock:
    """SPEC-007 CLI / `abandon`. Identical matching requirement to
    `acquire_for_resume`, but deliberately does **not** rewrite the
    reservation's `pid`/`claimed_at` -- the caller (`peos/resume.py`)
    attempts orphan reclamation first and only mutates lock/checkpoint
    state once that has concluded, one way or the other."""
    lock = _acquire_flock_or_raise(repo_root)
    try:
        raw = os.pread(lock._fd, 1 << 20, 0)
        content = _decode(raw)
        if content is None:
            raise NoSuchRunError(f"nothing to abandon: no run is currently reserved (looking for {run_id}).")
        if content.run_id != run_id:
            raise NoSuchRunError(f"no such run: the current reservation names a different run ({content.run_id}).")
        checkpoint, read_error = load_checkpoint(repo_root, run_id)
        if read_error is not None:
            raise CheckpointUnreadableError(f"checkpoint for run {run_id} could not be safely read: {read_error}")
        if checkpoint is None:
            raise NothingToResumeError(f"nothing to abandon -- run {run_id} never completed its bootstrap.")
        if checkpoint.terminal_outcome is not None:
            raise RunAlreadyConcludedError(f"run {run_id} already concluded with outcome={checkpoint.terminal_outcome}.")
        return lock
    except BaseException:
        lock.release()
        raise


def peek_lock_content(repo_root: Path) -> LockContent | None:
    """Best-effort, unlocked diagnostic read (e.g. for a human-facing
    error message when `LockBusyError` is raised) -- content may change
    concurrently; never used for a safety decision. Returns `None` on any
    error, including genuine corruption (diagnostic-only)."""
    lock_path = repo_root / LOCK_RELATIVE_PATH
    try:
        raw = lock_path.read_bytes()
    except OSError:
        return None
    try:
        return _decode(raw)
    except RunLockError:
        return None
