"""Runtime Verification: the per-round orchestration tying together port
reservation, the backend/frontend service lifecycle, and the Seatbelt-
sandboxed browser-worker subprocess (SPEC-006 Section 7/8).
`peos/workflow.py` calls `run_runtime_verification` once per round that
declares at least one check -- cycle 0 and every remediation cycle --
exactly where deterministic verification's own `_default_verifier` is
already called, and treats a non-`None` `failure_reason` with `ran=True`
as an execution-integrity `FAILED` for that round (SPEC-006 Section 6).

**The browser runs in its own Seatbelt-sandboxed subprocess, never
in-process in the orchestrator (Codex implementation review Finding
3).** `peos/runtime_browser.py`'s `execute_runtime_plan` must run on a
single, dedicated main thread (Playwright's sync API constraint --
see that module's docstring); the orchestrator's own main thread is
busy running the rest of `peos/workflow.py`. This module therefore
invokes `python -m peos.runtime_browser <input> <output>` as a
subprocess wrapped by `peos.sandbox.sandboxed_runtime_verification_command`
-- the exact same confinement the backend/frontend services already get
-- with its own outer wall-clock bound (`subprocess.run(..., timeout=)`);
if that bound is exceeded, the whole worker process group, including
Chromium (its descendant), is force-killed from the outside. This is the
"two-layer timeout defense" `peos/runtime_browser.py`'s module docstring
describes: the worker's own in-process `SIGALRM` watchdog is the fast,
attributable layer; this outer, process-level bound is the one that does
not depend on anything inside the worker behaving.

Every external effect here is injectable (the same dependency-injection
discipline `peos/workflow.py` already uses for `claude_runner`/
`codex_runner`/`verifier`), so the orchestration logic is unit testable
without starting a real backend/frontend/browser.
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from peos.runtime_catalog import RUNTIME_CHECK_CATALOG_VERSION
from peos.runtime_evidence import (
    PersistedEvidence,
    RuntimeCheck,
    RuntimeEvidence,
    build_runtime_check,
    build_service_readiness,
    persist_evidence,
    stage_evidence_into_workspace,
)
from peos.runtime_plan import RuntimePlan
from peos.runtime_services import (
    ServiceHandle,
    reserve_ephemeral_port,
    start_service,
    teardown_service,
    wait_for_ready,
)
from peos.sandbox import (
    CODEX_AUTH_HOME_ENV_VAR,
    IsolatedWorkspace,
    SandboxUnavailableError,
    sandboxed_env,
    sandboxed_runtime_verification_command,
)

BACKEND_HEALTH_PATH = "/api/v1/health"
FRONTEND_HEALTH_PATH = "/"
DEFAULT_BUILD_TIMEOUT_S = 600
DEFAULT_BROWSER_WORKER_TIMEOUT_S = 600
DEFAULT_PREFLIGHT_TIMEOUT_S = 60
DEFAULT_WORKER_TEARDOWN_GRACE_PERIOD_S = 5.0
CORS_ENV_VAR = "AI_POWER_LAB_EXTRA_CORS_ORIGINS"  # SPEC-006 Resolved Decision 3
API_BASE_URL_ENV_VAR = "NEXT_PUBLIC_API_BASE_URL"


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _extra_deny_read_paths(environ: dict) -> tuple[Path, ...]:
    """SPEC-006 Section 11, Codex Round 1 Finding 7 / implementation
    review Finding 8: the configured `PEOS_CODEX_AUTH_HOME`, when set,
    must be denied to every subprocess this module launches (backend,
    frontend, the production build, and the browser worker) -- not only
    the ones `peos/verification_plan.py::execute_plan` already covers
    for deterministic verification. The fixed `CREDENTIAL_PATH_DENYLIST`
    alone does not cover it, because it is an arbitrarily-located
    directory, not a well-known path under the real `$HOME`.
    """
    value = environ.get(CODEX_AUTH_HOME_ENV_VAR)
    return (Path(value),) if value else ()


def _with_playwright_browsers_path(base_env: dict, environ: dict) -> dict:
    """`sandboxed_env` redirects `HOME` to the isolated workspace's own
    empty temp directory -- correct for credential isolation, but it
    also breaks Playwright's default browser-cache lookup
    (`~/Library/Caches/ms-playwright`), which is where the one-time,
    human-run `playwright install chromium` bootstrap step (SPEC-006
    Section 10, ADR-0003) actually puts Chromium. PEOS never installs a
    browser itself, so the worker must still be able to *find* the one
    already installed under the real ambient `$HOME` -- this sets
    `PLAYWRIGHT_BROWSERS_PATH` explicitly from the real environment,
    independent of the sandboxed `HOME` redirect, rather than silently
    failing preflight on every run (live-run finding).
    """
    env = dict(base_env)
    if "PLAYWRIGHT_BROWSERS_PATH" in environ:
        env["PLAYWRIGHT_BROWSERS_PATH"] = environ["PLAYWRIGHT_BROWSERS_PATH"]
    elif "HOME" in environ:
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(Path(environ["HOME"]) / "Library" / "Caches" / "ms-playwright")
    return env


@dataclass(frozen=True)
class RuntimeVerificationOutcome:
    ran: bool  # False: the documented no-op (SPEC-006 Section 8 step 1/2) -- no checks declared
    execution_integrity_passed: bool
    failure_reason: str | None
    evidence: RuntimeEvidence | None = None
    persisted: PersistedEvidence | None = None
    staged_dir: Path | None = None


PortReserver = Callable[[], int]
ServiceStarter = Callable[..., ServiceHandle]
ReadinessWaiter = Callable[..., object]
Teardown = Callable[..., bool]
BuildRunner = Callable[..., subprocess.CompletedProcess]
BrowserWorkerRunner = Callable[..., subprocess.CompletedProcess]


def _no_op_outcome() -> RuntimeVerificationOutcome:
    return RuntimeVerificationOutcome(ran=False, execution_integrity_passed=True, failure_reason=None)


def _not_executed_check(declaration, cycle_slug: str) -> RuntimeCheck:
    check, _ = build_runtime_check(
        check_id=f"runtime.{cycle_slug}.{declaration.declaration_index}.{declaration.kind}",
        kind=declaration.kind, related_ac_ids=declaration.related_ac_ids,
        parameters=declaration.params.__dict__, status="NOT_EXECUTED",
        action_performed="(not executed)",
        observation="an execution-integrity failure before the browser worker ran aborted this round",
        measurements={}, screenshot_bytes=None,
    )
    return check


class WorkerCleanupUnverified(subprocess.TimeoutExpired):
    """Raised instead of plain `subprocess.TimeoutExpired` when the
    worker's process group could not be *verified* dead after SIGKILL
    (Codex closure review round 3) -- a subclass, not an unrelated
    exception, so every existing `except subprocess.TimeoutExpired`
    handler still catches it; callers that want the more honest message
    check for this specific type first.
    """


def _default_browser_worker_runner(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    """A plain `subprocess.run` only ever kills the direct child on
    `TimeoutExpired` -- Chromium's own renderer/GPU child processes
    would be orphaned, not terminated, contradicting this module's
    whole-process-group cleanup guarantee (Codex closure review
    finding). Launches in its own session so the whole group can be
    signalled, and on timeout, terminates that group (SIGTERM -> bounded
    grace -> SIGKILL) before re-raising, matching
    `peos.runtime_services.teardown_service`'s own graceful-then-forced
    pattern.
    """
    timeout_s = kwargs.pop("timeout", None)
    capture_output = kwargs.pop("capture_output", False)
    if capture_output:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
    process = subprocess.Popen(command, start_new_session=True, **kwargs)
    try:
        stdout, stderr = process.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        pgid = process.pid  # the session leader's pid, by construction of start_new_session=True
        try:
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=DEFAULT_WORKER_TEARDOWN_GRACE_PERIOD_S)
        except subprocess.TimeoutExpired:
            pass
        # Codex closure review finding: escalating only when
        # `process.wait()` itself timed out is wrong -- the *direct*
        # child (this `python -m peos.runtime_browser` process) can
        # exit promptly on SIGTERM while a *descendant* (Chromium's own
        # renderer/GPU children) ignores it and lingers. The escalation
        # decision must be driven by whether the whole group is still
        # alive, not by the direct child's own exit alone.
        try:
            os.killpg(pgid, 0)  # existence probe only, sends no real signal
            group_alive = True
        except ProcessLookupError:
            group_alive = False
        if group_alive:
            try:
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=DEFAULT_WORKER_TEARDOWN_GRACE_PERIOD_S)
            except subprocess.TimeoutExpired:
                pass
        else:
            process.wait()  # already dead; reap for a returncode, never blocks
        # Codex closure review finding (round 3): a successful SIGKILL
        # send is not proof of death -- bounded verification, not an
        # assumption, is what the module's "whole-process-group cleanup
        # guarantee" actually requires. Re-probes group liveness for up
        # to DEFAULT_WORKER_TEARDOWN_GRACE_PERIOD_S after SIGKILL; if a
        # member is somehow still alive even then (e.g. an uninterruptible
        # kernel wait), raises a distinct exception so the caller's error
        # message never overclaims "and was killed" when that was never
        # actually confirmed.
        cleanup_deadline = time.monotonic() + DEFAULT_WORKER_TEARDOWN_GRACE_PERIOD_S
        cleanup_verified = False
        while time.monotonic() < cleanup_deadline:
            try:
                os.killpg(pgid, 0)
            except ProcessLookupError:
                cleanup_verified = True
                break
            time.sleep(0.1)
        if not cleanup_verified:
            raise WorkerCleanupUnverified(
                command, timeout_s,
                output=f"process group {pgid} outlived SIGKILL and could not be verified dead",
            )
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def run_runtime_verification(
    runtime_plan: RuntimePlan,
    *,
    cycle_label: str,
    run_id: str,
    repo_root: Path,
    workspace: IsolatedWorkspace,
    profile_dir: Path,
    environ: dict,
    workspace_snapshot_identity: str,
    baseline_commit: str,
    frontend_dir_relative: str = "frontend",
    readiness_timeout_s: float = 45.0,
    build_timeout_s: int = DEFAULT_BUILD_TIMEOUT_S,
    browser_worker_timeout_s: int = DEFAULT_BROWSER_WORKER_TIMEOUT_S,
    port_reserver: PortReserver = reserve_ephemeral_port,
    service_starter: ServiceStarter = start_service,
    readiness_waiter: ReadinessWaiter = wait_for_ready,
    teardown: Teardown = teardown_service,
    build_runner: BuildRunner = subprocess.run,
    browser_worker_runner: BrowserWorkerRunner = _default_browser_worker_runner,
) -> RuntimeVerificationOutcome:
    """Run one round's Runtime Verification pass (SPEC-006 Section 8).

    Returns `ran=False` immediately -- the documented no-op -- if
    `runtime_plan` declares no checks. Otherwise: reserves both ports
    before starting either service (step 3), starts the backend with the
    resolved frontend origin in its CORS environment variable (step 4),
    builds and starts the production frontend with the resolved backend
    origin (step 5), executes the declared checks in a Seatbelt-sandboxed
    worker subprocess (step 6-7), tears down both services with verified
    cleanup (step 8), and only then finalizes and persists the evidence
    (step 9) -- never before teardown's outcome is known, so a teardown
    failure can still retroactively downgrade `execution_integrity_passed`
    (SPEC-006 Section 6/12). On *any* failure, declared checks that never
    ran are still persisted as `NOT_EXECUTED` evidence (Codex
    implementation review Finding 9) -- never silently absent.
    """
    if not runtime_plan.declarations:
        return _no_op_outcome()

    started_at = _now_iso()
    cycle_slug = cycle_label.strip().lower().replace(" ", "-")
    extra_deny_read_paths = _extra_deny_read_paths(environ)
    base_env = _with_playwright_browsers_path(sandboxed_env(workspace.home_dir, base_env=environ), environ)
    log_dir = workspace.path.parent / "runtime-logs"

    def _not_executed_evidence(reason: str, service_readiness: tuple = ()) -> RuntimeVerificationOutcome:
        checks = tuple(_not_executed_check(d, cycle_slug) for d in runtime_plan.declarations)
        evidence = RuntimeEvidence(
            run_id=run_id, cycle_label=cycle_label, workspace_snapshot_identity=workspace_snapshot_identity,
            baseline_commit=baseline_commit, catalog_version=RUNTIME_CHECK_CATALOG_VERSION,
            playwright_version="", browser_version="", browser_environment={},
            service_readiness=service_readiness, checks=checks, execution_integrity_passed=False,
            started_at=started_at, finished_at=_now_iso(),
        )
        persisted = persist_evidence(repo_root, run_id, evidence, {})
        staged_dir = stage_evidence_into_workspace(workspace.path, persisted, cycle_label)
        return RuntimeVerificationOutcome(
            ran=True, execution_integrity_passed=False, failure_reason=reason,
            evidence=evidence, persisted=persisted, staged_dir=staged_dir,
        )

    # SPEC-006 Section 8 step 2 preflight: confirm the pinned Playwright/
    # Chromium is actually launchable *before* reserving ports or
    # starting any service -- never merely "a chromium binary exists
    # somewhere" (Resolved Decision 1).
    preflight_ok, preflight_reason = preflight_browser_available(
        workspace=workspace, repo_root=repo_root, profile_dir=profile_dir, environ=environ,
        browser_worker_runner=browser_worker_runner,
    )
    if not preflight_ok:
        return _not_executed_evidence(f"Runtime Verification preflight failed: {preflight_reason}")

    try:
        backend_port = port_reserver()
        frontend_port = port_reserver()
    except OSError as exc:
        return _not_executed_evidence(f"could not reserve ephemeral ports: {exc}")

    backend_handle: ServiceHandle | None = None
    frontend_handle: ServiceHandle | None = None
    backend_readiness = None
    frontend_readiness = None
    try:
        backend_env = dict(base_env)
        backend_env[CORS_ENV_VAR] = f"http://127.0.0.1:{frontend_port}"
        backend_cmd = [
            sys.executable, "-m", "uvicorn", "backend.app:app",
            "--host", "127.0.0.1", "--port", str(backend_port),
        ]
        try:
            backend_handle = service_starter(
                name="backend", command=backend_cmd, cwd=workspace.path, env=backend_env,
                workspace=workspace, repo_root=repo_root, profile_dir=profile_dir, port=backend_port,
                log_dir=log_dir, extra_deny_read_paths=extra_deny_read_paths,
            )
        except SandboxUnavailableError as exc:
            return _not_executed_evidence(f"backend sandbox unavailable: {exc}")

        backend_readiness = readiness_waiter(backend_handle, health_path=BACKEND_HEALTH_PATH, timeout_s=readiness_timeout_s)
        if not backend_readiness.ready:
            return _not_executed_evidence(
                f"backend did not become ready within {readiness_timeout_s}s: {backend_readiness.stderr_tail[-500:]}",
                service_readiness=(_readiness_record("backend", backend_cmd, backend_port, backend_readiness),),
            )

        build_env = dict(base_env)
        build_env[API_BASE_URL_ENV_VAR] = f"http://127.0.0.1:{backend_port}"
        try:
            build_cmd = sandboxed_runtime_verification_command(
                ["npm", "run", "build"], workspace, repo_root, profile_dir, extra_deny_read_paths=extra_deny_read_paths,
            )
        except SandboxUnavailableError as exc:
            return _not_executed_evidence(f"frontend build sandbox unavailable: {exc}")
        try:
            build_proc = build_runner(
                build_cmd, cwd=str(workspace.path / frontend_dir_relative), env=build_env,
                capture_output=True, text=True, timeout=build_timeout_s,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            return _not_executed_evidence(f"frontend production build failed to run: {exc}")
        if build_proc.returncode != 0:
            return _not_executed_evidence(
                f"frontend production build failed (exit {build_proc.returncode}): {build_proc.stderr[-2000:]}"
            )

        frontend_env = dict(base_env)
        frontend_env[API_BASE_URL_ENV_VAR] = f"http://127.0.0.1:{backend_port}"
        frontend_cmd = ["npm", "run", "start", "--", "-p", str(frontend_port), "-H", "127.0.0.1"]
        try:
            frontend_handle = service_starter(
                name="frontend", command=frontend_cmd, cwd=workspace.path / frontend_dir_relative,
                env=frontend_env, workspace=workspace, repo_root=repo_root, profile_dir=profile_dir,
                port=frontend_port, log_dir=log_dir, extra_deny_read_paths=extra_deny_read_paths,
            )
        except SandboxUnavailableError as exc:
            return _not_executed_evidence(f"frontend sandbox unavailable: {exc}")

        frontend_readiness = readiness_waiter(frontend_handle, health_path=FRONTEND_HEALTH_PATH, timeout_s=readiness_timeout_s)
        if not frontend_readiness.ready:
            return _not_executed_evidence(
                f"frontend did not become ready within {readiness_timeout_s}s: {frontend_readiness.stderr_tail[-500:]}",
                service_readiness=(
                    _readiness_record("backend", backend_cmd, backend_port, backend_readiness),
                    _readiness_record("frontend", frontend_cmd, frontend_port, frontend_readiness),
                ),
            )

        base_url = f"http://127.0.0.1:{frontend_port}"
        worker_output = _run_browser_worker(
            runtime_plan.declarations, base_url, cycle_label, workspace=workspace, repo_root=repo_root,
            profile_dir=profile_dir, base_env=base_env, extra_deny_read_paths=extra_deny_read_paths,
            timeout_s=browser_worker_timeout_s, browser_worker_runner=browser_worker_runner,
        )
    finally:
        # Codex implementation review Finding 10: this `finally` is what
        # guarantees teardown on *every* path through the block above --
        # including an exception this function did not anticipate --
        # not only the explicit early-return branches, each of which
        # also happens to call `_not_executed_evidence` without tearing
        # down first in the original draft.
        backend_teardown_ok = teardown(backend_handle) if backend_handle is not None else True
        frontend_teardown_ok = teardown(frontend_handle) if frontend_handle is not None else True

    if worker_output.get("_worker_error"):
        return _not_executed_evidence(
            f"browser worker failed: {worker_output['_worker_error']}",
            service_readiness=(
                _readiness_record("backend", backend_cmd, backend_port, backend_readiness),
                _readiness_record("frontend", frontend_cmd, frontend_port, frontend_readiness),
            ),
        )

    checks = tuple(_check_from_worker_dict(c) for c in worker_output["checks"])
    screenshots = _load_worker_screenshots(worker_output["_screenshots_dir"], checks)

    execution_integrity_passed = (
        worker_output["execution_integrity_passed"] and backend_teardown_ok and frontend_teardown_ok
    )
    failure_reason = worker_output.get("failure_reason")
    if execution_integrity_passed is False and failure_reason is None:
        failure_reason = (
            f"teardown could not be verified (backend={backend_teardown_ok}, frontend={frontend_teardown_ok})"
        )

    evidence = RuntimeEvidence(
        run_id=run_id, cycle_label=cycle_label, workspace_snapshot_identity=workspace_snapshot_identity,
        baseline_commit=baseline_commit, catalog_version=RUNTIME_CHECK_CATALOG_VERSION,
        playwright_version=worker_output["playwright_version"], browser_version=worker_output["browser_version"],
        browser_environment=worker_output["browser_environment"],
        service_readiness=(
            _readiness_record("backend", backend_cmd, backend_port, backend_readiness),
            _readiness_record("frontend", frontend_cmd, frontend_port, frontend_readiness),
        ),
        checks=checks, execution_integrity_passed=execution_integrity_passed,
        started_at=started_at, finished_at=_now_iso(),
    )
    persisted = persist_evidence(repo_root, run_id, evidence, screenshots)
    staged_dir = stage_evidence_into_workspace(workspace.path, persisted, cycle_label)

    return RuntimeVerificationOutcome(
        ran=True, execution_integrity_passed=execution_integrity_passed, failure_reason=failure_reason,
        evidence=evidence, persisted=persisted, staged_dir=staged_dir,
    )


def _readiness_record(service: str, command: list[str], port: int, readiness) -> object:
    return build_service_readiness(
        service=service, command=tuple(command), resolved_port=port, ready=readiness.ready,
        waited_seconds=readiness.waited_seconds, stdout=readiness.stdout_tail, stderr=readiness.stderr_tail,
    )


def _check_from_worker_dict(d: dict) -> RuntimeCheck:
    return RuntimeCheck(
        check_id=d["check_id"], kind=d["kind"], catalog_version=d["catalog_version"],
        related_ac_ids=tuple(d["related_ac_ids"]), parameters=d["parameters"], status=d["status"],
        action_performed=d["action_performed"], observation=d["observation"], measurements=d["measurements"],
        screenshot_path=(f"screenshots/{d['screenshot_filename']}" if d.get("screenshot_filename") else None),
        screenshot_sha256=None,  # recomputed by persist_evidence from the actual bytes it writes
        console_errors=tuple(d["console_errors"]), page_errors=tuple(d["page_errors"]),
        blocked_network_requests=tuple(d["blocked_network_requests"]), truncated=d["truncated"],
        omitted_reason=d["omitted_reason"], started_at=d["started_at"], finished_at=d["finished_at"],
    )


def _load_worker_screenshots(screenshots_dir: Path, checks: tuple) -> dict:
    screenshots = {}
    for check in checks:
        if check.screenshot_path is None:
            continue
        path = screenshots_dir / Path(check.screenshot_path).name
        if path.is_file():
            screenshots[check.check_id] = path.read_bytes()
    return screenshots


def _run_browser_worker(
    declarations: tuple, base_url: str, cycle_label: str, *, workspace: IsolatedWorkspace, repo_root: Path,
    profile_dir: Path, base_env: dict, extra_deny_read_paths: tuple[Path, ...], timeout_s: int,
    browser_worker_runner: BrowserWorkerRunner,
) -> dict:
    """Invoke `python -m peos.runtime_browser` as a Seatbelt-sandboxed
    subprocess (Codex implementation review Finding 3) with its own
    outer wall-clock bound; parses the worker's `result.json`. Returns a
    dict always containing either the worker's own output keys, or
    `{"_worker_error": "<reason>"}` on any execution-integrity failure
    this function itself detects (sandbox unavailable, subprocess
    timeout/crash, unparseable output).
    """
    with tempfile.TemporaryDirectory(dir=str(workspace.path.parent)) as tmp:
        tmp_path = Path(tmp)
        input_path = tmp_path / "input.json"
        output_dir = tmp_path / "output"
        input_payload = {
            "base_url": base_url,
            "cycle_label": cycle_label,
            "declarations": [
                {
                    "declaration_index": d.declaration_index, "kind": d.kind,
                    "parameters": d.params.__dict__, "related_ac_ids": list(d.related_ac_ids),
                }
                for d in declarations
            ],
        }
        input_path.write_text(json.dumps(input_payload), encoding="utf-8")

        try:
            worker_command = sandboxed_runtime_verification_command(
                [sys.executable, "-m", "peos.runtime_browser", str(input_path), str(output_dir)],
                workspace, repo_root, profile_dir, extra_deny_read_paths=extra_deny_read_paths,
            )
        except SandboxUnavailableError as exc:
            return {"_worker_error": f"browser worker sandbox unavailable: {exc}"}

        try:
            proc = browser_worker_runner(
                worker_command, cwd=str(workspace.path), env=base_env,
                capture_output=True, text=True, timeout=timeout_s,
            )
        except WorkerCleanupUnverified as exc:
            return {"_worker_error": f"browser worker exceeded the {timeout_s}s outer bound: {exc.output}"}
        except subprocess.TimeoutExpired:
            return {"_worker_error": f"browser worker exceeded the {timeout_s}s outer bound and was killed"}
        except OSError as exc:
            return {"_worker_error": f"browser worker failed to launch: {exc}"}

        result_path = output_dir / "result.json"
        if not result_path.is_file():
            tail = (proc.stderr or proc.stdout or "")[-1000:]
            return {"_worker_error": f"browser worker produced no result.json (exit {proc.returncode}): {tail}"}
        try:
            output = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {"_worker_error": f"browser worker result.json could not be parsed: {exc}"}
        if not output.get("ok"):
            return {"_worker_error": output.get("failure_reason", "browser worker reported failure")}

        # Copy screenshots out of the (about-to-be-deleted) temp dir
        # before the `with tempfile.TemporaryDirectory` context exits.
        persistent_screenshots_dir = Path(tempfile.mkdtemp(prefix="peos-rv-screenshots-"))
        worker_screenshots_dir = output_dir / "screenshots"
        if worker_screenshots_dir.is_dir():
            for item in worker_screenshots_dir.iterdir():
                shutil.copy2(item, persistent_screenshots_dir / item.name)
        output["_screenshots_dir"] = persistent_screenshots_dir
        return output


def preflight_browser_available(
    *, workspace: IsolatedWorkspace, repo_root: Path, profile_dir: Path, environ: dict,
    timeout_s: int = DEFAULT_PREFLIGHT_TIMEOUT_S,
    browser_worker_runner: BrowserWorkerRunner = _default_browser_worker_runner,
) -> tuple[bool, str | None]:
    """Standalone preflight check (SPEC-006 Section 8 step 2), usable
    independently of a full Runtime Verification round -- confirms the
    pinned Playwright/Chromium is actually launchable via the same
    sandboxed worker subprocess real checks use. Returns `(ok, reason)`.
    """
    base_env = _with_playwright_browsers_path(sandboxed_env(workspace.home_dir, base_env=environ), environ)
    result = _run_browser_worker(
        (), "http://127.0.0.1:1", "preflight", workspace=workspace, repo_root=repo_root,
        profile_dir=profile_dir, base_env=base_env, extra_deny_read_paths=_extra_deny_read_paths(environ),
        timeout_s=timeout_s, browser_worker_runner=browser_worker_runner,
    )
    if result.get("_worker_error"):
        return False, result["_worker_error"]
    if not result.get("execution_integrity_passed", True):
        return False, result.get("failure_reason", "preflight failed")
    return True, None
