"""Runtime Services: starting, waiting for, and tearing down the backend
and frontend subprocesses PEOS Runtime Verification exercises (SPEC-006
Section 8 steps 3-5/8, Section 12 hardening item D).

Every service subprocess is launched under the Runtime Verification
Seatbelt profile (`peos.sandbox.sandboxed_runtime_verification_command`)
and owned by its own managed process group (`start_new_session=True` on
POSIX), so any child the service itself spawns (an extra `uvicorn`
worker, a Next.js internal worker) is torn down with it. Both ports are
reserved (bound-and-released) *before* either subprocess is started
(Codex Round 1 Finding 9), so each service's own startup-time
configuration can already name the other's resolved origin.

Teardown is bounded and **verified**, never merely attempted: graceful
termination, a bounded grace period, forced termination, then an
explicit check that the process group has no live members and the
assigned port is no longer bound. An orphaned process or unverifiable
cleanup is itself an execution-integrity failure (SPEC-006 Section 6) --
`teardown_service`'s return value is this module's only signal of that;
callers must treat `False` as a reason to fail the round closed, never a
reason to merely log and continue.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import datetime

from peos.checkpoint import ServiceProcessIdentity
from peos.sandbox import IsolatedWorkspace, sandboxed_runtime_verification_command

DEFAULT_READINESS_TIMEOUT_S = 45.0
DEFAULT_READINESS_POLL_INTERVAL_S = 0.5
DEFAULT_TEARDOWN_GRACE_PERIOD_S = 5.0
MAX_CAPTURED_LOG_BYTES = 256 * 1024  # read tail only; evidence bounds the rest


def reserve_ephemeral_port() -> int:
    """Bind to an OS-assigned port on `127.0.0.1`, read it back, and
    release the socket (SPEC-006 Section 8 step 3). A best-effort
    reservation, not an airtight lock -- a subsequent bind failure on
    this port is an ordinary execution-integrity `FAILED` (SPEC-006
    Section 6/12), not a distinct failure class.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
    finally:
        s.close()


def is_port_released(port: int) -> bool:
    """True if `127.0.0.1:<port>` can be bound right now -- used by
    `teardown_service` to verify cleanup, never to reserve a port for
    later use (that is `reserve_ephemeral_port`'s job alone)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


@dataclass
class ServiceHandle:
    name: str  # "backend" | "frontend"
    process: subprocess.Popen
    port: int
    command: tuple[str, ...]
    stdout_path: Path
    stderr_path: Path
    # Codex implementation review Finding 10: captured once, immediately
    # after `Popen(..., start_new_session=True)` -- at that point it is
    # always equal to `process.pid` by POSIX construction (a new session
    # leader is its own process group leader). Teardown must always
    # signal *this* value, never re-derive it later via
    # `os.getpgid(process.pid)`: once the process has been reaped
    # (`process.wait()`/`process.poll()` observing exit), that lookup can
    # raise `ProcessLookupError` even while live descendants remain in
    # the same group, or -- far worse on a long-idle system -- the
    # original pid could already have been recycled by an unrelated
    # process, making a *fresh* lookup silently signal the wrong group.
    pgid: int
    # SPEC-007 Decision 7: the exact argv actually passed to `Popen`,
    # including the `sandbox-exec`/wrapper prefix -- distinct from
    # `command` above (the caller's original, unwrapped command, used for
    # human-facing evidence reporting). This is what
    # `capture_service_process_identity`'s `ServiceProcessIdentity.
    # command_argv` records, so a restarted orchestrator's later
    # verification of a claimed identity compares against what was
    # actually running, not a reconstruction.
    sandboxed_command_argv: tuple[str, ...] = ()


def start_service(
    *,
    name: str,
    command: list[str],
    cwd: Path,
    env: dict,
    workspace: IsolatedWorkspace,
    repo_root: Path,
    profile_dir: Path,
    port: int,
    log_dir: Path,
    extra_deny_read_paths: tuple[Path, ...] = (),
) -> ServiceHandle:
    """Launch `command` as a backend/frontend service, sandboxed, in its
    own process group, with stdout/stderr redirected to files (never
    `subprocess.PIPE` -- an unread pipe would eventually block the child
    once its OS buffer fills, which a long-running service easily
    exceeds). Raises `peos.sandbox.SandboxUnavailableError` if the
    sandbox cannot be built (SPEC-006 Section 6) -- never an unsandboxed
    fallback.
    """
    sandboxed_command = sandboxed_runtime_verification_command(
        command, workspace, repo_root, profile_dir, extra_deny_read_paths=extra_deny_read_paths,
    )
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / f"{name}.stdout.log"
    stderr_path = log_dir / f"{name}.stderr.log"
    stdout_f = open(stdout_path, "wb")
    stderr_f = open(stderr_path, "wb")
    try:
        process = subprocess.Popen(
            sandboxed_command, cwd=str(cwd), env=env, stdout=stdout_f, stderr=stderr_f,
            start_new_session=True,
        )
    finally:
        stdout_f.close()
        stderr_f.close()
    return ServiceHandle(
        name=name, process=process, port=port, command=tuple(command),
        stdout_path=stdout_path, stderr_path=stderr_path, pgid=process.pid,
        sandboxed_command_argv=tuple(sandboxed_command),
    )


def _read_tail(path: Path) -> str:
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    return data[-MAX_CAPTURED_LOG_BYTES:].decode("utf-8", errors="replace")


@dataclass(frozen=True)
class ReadinessResult:
    ready: bool
    waited_seconds: float
    stdout_tail: str
    stderr_tail: str


def wait_for_ready(
    handle: ServiceHandle,
    health_path: str = "/",
    timeout_s: float = DEFAULT_READINESS_TIMEOUT_S,
    poll_interval_s: float = DEFAULT_READINESS_POLL_INTERVAL_S,
) -> ReadinessResult:
    """Bounded polling for the service to respond on its own assigned
    port (SPEC-006 Section 8 steps 4-5, Section 12 "Readiness polling
    (not a retry, Resolved Decision 6)"): one bounded wait with one
    outcome, never retried after it completes. Also fails closed if the
    process exits before becoming ready (a crashed/misconfigured service
    is an execution-integrity failure, not a readiness timeout the
    caller should keep polling past).
    """
    url = f"http://127.0.0.1:{handle.port}{health_path}"
    deadline = time.monotonic() + timeout_s
    start = time.monotonic()
    while time.monotonic() < deadline:
        if handle.process.poll() is not None:
            break
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status < 500:
                    return ReadinessResult(
                        ready=True, waited_seconds=time.monotonic() - start,
                        stdout_tail=_read_tail(handle.stdout_path), stderr_tail=_read_tail(handle.stderr_path),
                    )
        except (urllib.error.URLError, OSError, TimeoutError):
            pass
        time.sleep(poll_interval_s)
    return ReadinessResult(
        ready=False, waited_seconds=time.monotonic() - start,
        stdout_tail=_read_tail(handle.stdout_path), stderr_tail=_read_tail(handle.stderr_path),
    )


def teardown_service(handle: ServiceHandle, grace_period_s: float = DEFAULT_TEARDOWN_GRACE_PERIOD_S) -> bool:
    """Graceful termination -> bounded grace period -> forced
    termination -> **verified** cleanup (SPEC-006 Section 12 hardening
    item D). Returns `True` only if both the process group has no live
    members and the assigned port is released afterward; `False`
    otherwise -- callers must treat `False` as an execution-integrity
    failure for the round, never a merely-logged warning.

    Runs unconditionally regardless of why teardown was invoked (`PASS`,
    a `FAIL`-status check, an execution-integrity failure, an exception,
    or process interruption) -- it is the caller's job to invoke this on
    every exit path, never this function's to decide whether teardown is
    warranted.
    """
    process = handle.process
    pgid = handle.pgid  # captured at launch time -- never re-derived (Codex implementation review Finding 10)
    if process.poll() is None:
        try:
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=grace_period_s)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=grace_period_s)
            except subprocess.TimeoutExpired:
                pass

    if process.poll() is None:
        return False  # direct child still alive -- unverifiable cleanup

    pgid_alive = False
    try:
        os.killpg(pgid, 0)  # existence probe only, sends no real signal
        pgid_alive = True
    except ProcessLookupError:
        pgid_alive = False
    except PermissionError:
        # The group exists but we can't signal it -- cannot be verified
        # dead; fail closed rather than assume success.
        pgid_alive = True
    if pgid_alive:
        return False

    # Bounded settle wait for the OS to actually release the port.
    settle_deadline = time.monotonic() + grace_period_s
    while time.monotonic() < settle_deadline:
        if is_port_released(handle.port):
            return True
        time.sleep(0.2)
    return is_port_released(handle.port)


def _process_start_time(pid: int) -> str | None:
    """Best-effort process start time via `ps` (no new dependency --
    macOS has no `/proc`). Returns `None` (never raises) if the process
    is gone or `ps` cannot be consulted -- SPEC-007 Decision 7 explicitly
    treats an unavailable start-time signal as "reclamation does not
    proceed for that process", never as a reason to skip the check."""
    try:
        proc = subprocess.run(
            ["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    value = proc.stdout.strip()
    return value or None


def capture_service_process_identity(handle: ServiceHandle, owning_run_id: str) -> ServiceProcessIdentity:
    """Build the durable `ServiceProcessIdentity` checkpoint record for
    `handle`, captured immediately after `start_service` returns (SPEC-007
    Decision 7: "registration is written immediately after `start_service`
    .../the browser-worker launch returns a handle, as its own small,
    immediate checkpoint write"). A kill in the exact window between
    `Popen` returning and that write completing leaves that one process
    unreclaimable -- a named, accepted residual limitation, not solved in
    V1 (see SPEC-007 "Known Limitations")."""
    return ServiceProcessIdentity(
        service_name=handle.name,
        pid=handle.process.pid,
        pgid=handle.pgid,
        port=handle.port,
        start_time=_process_start_time(handle.process.pid),
        command_argv=handle.sandboxed_command_argv or handle.command,
        owning_run_id=owning_run_id,
        recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )


def reclaim_orphaned_service(
    identity: ServiceProcessIdentity, grace_period_s: float = DEFAULT_TEARDOWN_GRACE_PERIOD_S,
) -> tuple[bool, str | None]:
    """SPEC-007 "Process Ownership and Orphan Reclamation" -- a new
    function, not a reuse of `teardown_service` (which requires a live
    `Popen` object a restarted orchestrator does not have for a service
    an earlier process instance launched). Uses the identical graceful-
    SIGTERM -> bounded-grace -> SIGKILL -> verified-dead sequence, built
    on `os.kill`/`os.killpg` plus a polling existence-probe loop in place
    of `Popen.wait()`.

    Returns `(True, None)` only once reclamation (including port-release
    verification, for any service whose `port` is not `None`) is
    positively confirmed. Returns `(False, reason)` for every other case,
    **including the dead-process-group-leader-with-live-descendants
    case** (SPEC-007 Round 2 Finding 9): this is explicitly an ambiguous-
    ownership failure, fail-closed, never "nothing to reclaim" -- callers
    (`peos/resume.py`) must treat `(False, ...)` as `FAILED`
    ("ambiguous process ownership"), never a silent skip.
    """
    pgid = identity.pgid

    # Step 1: group liveness probe.
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return True, None  # Nothing to reclaim -- the ordinary post-reboot/post-crash case.
    except PermissionError:
        return False, f"process group {pgid} exists but cannot be signaled; ambiguous ownership."
    except OSError as exc:
        return False, f"could not probe process group {pgid}: {exc}; ambiguous ownership."

    # Step 2: leader-identity verification -- every signal must hold
    # (Codex implementation review, confirmed, major: an earlier
    # revision verified only pid existence, start time, and a *prefix*
    # match of the running command against `command_argv[0]` -- never
    # the leader's actual, current pgid, nor the rest of `command_argv`.
    # Both are now checked explicitly, closing the gap where a
    # coincidentally similar process could pass verification).
    try:
        os.kill(identity.pid, 0)
    except ProcessLookupError:
        return False, (
            f"process group {pgid} is alive but the specific recorded leader pid "
            f"{identity.pid} is gone (dead leader with live descendants) -- ambiguous "
            "ownership, cannot be positively established."
        )
    except OSError as exc:
        return False, f"could not verify recorded leader pid {identity.pid}: {exc}"

    try:
        actual_pgid = os.getpgid(identity.pid)
    except OSError as exc:
        return False, f"could not verify recorded leader pid {identity.pid}'s process group: {exc}"
    if actual_pgid != identity.pgid:
        return False, (
            f"recorded leader pid {identity.pid}'s current process group ({actual_pgid}) no longer "
            f"matches the recorded pgid ({identity.pgid}) -- ambiguous ownership."
        )

    current_start_time = _process_start_time(identity.pid)
    if identity.start_time is None or current_start_time is None or current_start_time != identity.start_time:
        return False, (
            f"recorded leader pid {identity.pid}'s start time could not be positively "
            "re-verified -- ambiguous ownership."
        )

    try:
        ps_proc = subprocess.run(
            ["ps", "-o", "command=", "-p", str(identity.pid)], capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, f"could not verify recorded leader pid {identity.pid}'s command line."
    if ps_proc.returncode != 0 or not ps_proc.stdout.strip():
        return False, f"recorded leader pid {identity.pid} could not be inspected for command-line verification."
    running_command = ps_proc.stdout.strip()
    if identity.command_argv:
        search_pos = 0
        for token in identity.command_argv:
            found_at = running_command.find(token, search_pos)
            if found_at == -1:
                return False, (
                    f"recorded leader pid {identity.pid}'s running command does not contain the full "
                    "recorded command_argv, in order -- ambiguous ownership."
                )
            search_pos = found_at + len(token)

    # Every signal in step 2 holds -- proceed with the identical
    # graceful -> bounded-grace -> forced -> verified-dead sequence
    # `teardown_service` uses, built on os.killpg/os.kill since there is
    # no live Popen object.
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    except PermissionError:
        # Observed in practice: a process group whose leader has just
        # exited (but not yet been reaped) can make even a *signal*
        # send -- not only the existence probe -- raise EPERM on some
        # platforms, rather than ESRCH. Never let that escape as an
        # uncaught exception (SPEC-001 Finding 11's "never propagate a
        # traceback" discipline extends to this new function too); the
        # `_group_alive()` polling loop below is what actually
        # determines dead-vs-still-alive either way.
        pass

    deadline = time.monotonic() + grace_period_s

    def _group_alive() -> bool:
        try:
            os.killpg(pgid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

    while time.monotonic() < deadline and _group_alive():
        time.sleep(0.2)
    if _group_alive():
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError:
            pass
        kill_deadline = time.monotonic() + grace_period_s
        while time.monotonic() < kill_deadline and _group_alive():
            time.sleep(0.2)
    if _group_alive():
        return False, f"process group {pgid} did not terminate after SIGTERM and SIGKILL -- unverifiable cleanup."

    if identity.port is None:
        return True, None

    settle_deadline = time.monotonic() + grace_period_s
    while time.monotonic() < settle_deadline:
        if is_port_released(identity.port):
            return True, None
        time.sleep(0.2)
    if is_port_released(identity.port):
        return True, None
    return False, f"port {identity.port} was not released after reclaiming process group {pgid}."
