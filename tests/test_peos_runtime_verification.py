"""Tests for peos/runtime_verification.py (SPEC-006 Section 7/8), using
fully injected fakes for port reservation, service start/readiness/
teardown, the frontend build subprocess, and the browser-worker
subprocess runner -- no real backend/frontend/browser process is
started, and no real `python -m peos.runtime_browser` subprocess is
launched (the fake `browser_worker_runner` simulates the worker's
on-disk result.json/screenshots contract directly).

AC-001/AC-002 (no-op vs. populated plan), AC-005/AC-006 (bind/readiness
failure), AC-030 (teardown failure retroactively flips the outcome),
AC-052 (both ports reserved before either service starts, CORS/API-base
env vars set correctly). Codex implementation review Findings 3/9/10
(browser worker invoked as its own sandboxed subprocess with an outer
timeout; preflight before any service starts; NOT_EXECUTED evidence
persisted on every failure path; teardown guaranteed via `finally`).
"""

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from peos.runtime_catalog import ViewportOverflowParams
from peos.runtime_plan import RuntimeCheckDeclaration, RuntimePlan
from peos.runtime_verification import run_runtime_verification
from peos.sandbox import create_isolated_workspace, discard_workspace

from tests._peos_fixtures import make_minimal_repo


@pytest.fixture
def repo_root(tmp_path):
    return make_minimal_repo(tmp_path)


@pytest.fixture
def workspace(repo_root):
    ws = create_isolated_workspace(repo_root, "rv-test")
    yield ws
    discard_workspace(ws)


def _empty_plan():
    return RuntimePlan()


def _one_check_plan():
    decl = RuntimeCheckDeclaration(
        declaration_index=0, kind="viewport_overflow",
        params=ViewportOverflowParams(viewport="mobile"), related_ac_ids=("AC-012",),
    )
    return RuntimePlan(declarations=(decl,))


@dataclass
class _FakeHandle:
    name: str
    port: int


@dataclass
class _FakeReadiness:
    ready: bool
    waited_seconds: float = 1.0
    stdout_tail: str = ""
    stderr_tail: str = ""


@dataclass
class _FakeCompletedProcess:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


def _passing_worker_runner_factory(check_results=None, browser_version="fake-browser", playwright_version="fake-pw"):
    """Builds a fake `browser_worker_runner` that, instead of launching a
    real subprocess, writes the worker's own on-disk result.json
    contract directly -- introspecting the (sandboxed) command list for
    the input/output paths `peos/runtime_verification.py` always passes
    as the last two arguments before the sandbox wrapper's own prefix.
    """
    check_results = check_results if check_results is not None else []

    def runner(command, cwd=None, env=None, capture_output=True, text=True, timeout=None):
        input_path = Path(command[-2])
        output_dir = Path(command[-1])
        output_dir.mkdir(parents=True, exist_ok=True)
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        checks = check_results if payload["declarations"] else []
        (output_dir / "result.json").write_text(json.dumps({
            "ok": True,
            "checks": checks,
            "execution_integrity_passed": True,
            "failure_reason": None,
            "browser_version": browser_version,
            "playwright_version": playwright_version,
            "browser_environment": {},
        }), encoding="utf-8")
        return _FakeCompletedProcess()

    return runner


def _preflight_only_runner():
    """A worker runner that only ever receives the preflight call (zero
    declarations) and always reports success -- used by tests that don't
    care about the real check-execution phase."""
    return _passing_worker_runner_factory(check_results=[])


def _common_kwargs(repo_root, workspace, tmp_path, **overrides):
    kwargs = dict(
        cycle_label="cycle 0", run_id="run1", repo_root=repo_root, workspace=workspace,
        profile_dir=tmp_path / "profiles", environ={"PATH": "/usr/bin"},
        workspace_snapshot_identity="fp1", baseline_commit="deadbeef",
        browser_worker_runner=_preflight_only_runner(),
    )
    kwargs.update(overrides)
    return kwargs


def test_ac001_no_op_when_plan_declares_nothing(repo_root, workspace, tmp_path):
    outcome = run_runtime_verification(_empty_plan(), **_common_kwargs(repo_root, workspace, tmp_path))
    assert outcome.ran is False
    assert outcome.execution_integrity_passed is True
    assert outcome.evidence is None


def test_preflight_runs_before_any_port_is_reserved(repo_root, workspace, tmp_path):
    reserved = []

    def fake_port_reserver():
        reserved.append(True)
        return 10000 + len(reserved)

    def failing_preflight_runner(command, **kwargs):
        return _FakeCompletedProcess(returncode=1, stderr="no such file: chromium")

    outcome = run_runtime_verification(
        _one_check_plan(),
        **_common_kwargs(
            repo_root, workspace, tmp_path,
            port_reserver=fake_port_reserver, browser_worker_runner=failing_preflight_runner,
        ),
    )
    assert outcome.ran is True
    assert outcome.execution_integrity_passed is False
    assert "preflight failed" in outcome.failure_reason
    assert reserved == []  # ports never reserved -- preflight failed first
    # NOT_EXECUTED evidence is still persisted (Codex implementation review Finding 9)
    assert outcome.evidence is not None
    assert all(c.status == "NOT_EXECUTED" for c in outcome.evidence.checks)


def test_ac005_backend_readiness_failure_fails_closed_before_frontend_starts(repo_root, workspace, tmp_path):
    ports = iter([1111, 2222])
    started_services = []

    def fake_starter(*, name, **kwargs):
        started_services.append(name)
        return _FakeHandle(name=name, port=kwargs["port"])

    def fake_waiter(handle, health_path, timeout_s):
        return _FakeReadiness(ready=False, stderr_tail="connection refused")

    torn_down = []

    def fake_teardown(handle):
        torn_down.append(handle.name)
        return True

    outcome = run_runtime_verification(
        _one_check_plan(),
        **_common_kwargs(
            repo_root, workspace, tmp_path,
            port_reserver=lambda: next(ports), service_starter=fake_starter,
            readiness_waiter=fake_waiter, teardown=fake_teardown,
        ),
    )
    assert outcome.ran is True
    assert outcome.execution_integrity_passed is False
    assert "backend" in outcome.failure_reason
    assert started_services == ["backend"]  # frontend never started
    assert torn_down == ["backend"]
    assert all(c.status == "NOT_EXECUTED" for c in outcome.evidence.checks)


def test_ac052_both_ports_reserved_and_cors_env_set_before_backend_starts(repo_root, workspace, tmp_path):
    reserved = []

    def fake_port_reserver():
        reserved.append(True)
        return 10000 + len(reserved)

    captured_env = {}

    def fake_starter(*, name, env, **kwargs):
        captured_env[name] = env
        return _FakeHandle(name=name, port=kwargs["port"])

    def fake_waiter(handle, health_path, timeout_s):
        return _FakeReadiness(ready=False)  # stop early, we only need to inspect the backend env

    outcome = run_runtime_verification(
        _one_check_plan(),
        **_common_kwargs(
            repo_root, workspace, tmp_path,
            port_reserver=fake_port_reserver, service_starter=fake_starter, readiness_waiter=fake_waiter,
            teardown=lambda handle: True,
        ),
    )
    assert len(reserved) == 2  # both ports reserved before backend even started
    assert "AI_POWER_LAB_EXTRA_CORS_ORIGINS" in captured_env["backend"]
    assert "10002" in captured_env["backend"]["AI_POWER_LAB_EXTRA_CORS_ORIGINS"]  # the frontend's reserved port
    assert outcome.execution_integrity_passed is False


def test_frontend_build_failure_tears_down_backend_and_fails_closed(repo_root, workspace, tmp_path):
    ports = iter([1111, 2222])
    torn_down = []

    def fake_starter(*, name, **kwargs):
        return _FakeHandle(name=name, port=kwargs["port"])

    def fake_waiter(handle, health_path, timeout_s):
        return _FakeReadiness(ready=True)

    def fake_teardown(handle):
        torn_down.append(handle.name)
        return True

    class _FailedBuild:
        returncode = 1
        stderr = "build failed: module not found"
        stdout = ""

    outcome = run_runtime_verification(
        _one_check_plan(),
        **_common_kwargs(
            repo_root, workspace, tmp_path,
            port_reserver=lambda: next(ports), service_starter=fake_starter, readiness_waiter=fake_waiter,
            teardown=fake_teardown, build_runner=lambda *a, **k: _FailedBuild(),
        ),
    )
    assert outcome.ran is True
    assert outcome.execution_integrity_passed is False
    assert "build failed" in outcome.failure_reason
    assert torn_down == ["backend"]  # frontend never started


def test_ac010_unexpected_exception_during_service_lifecycle_still_tears_down_everything(repo_root, workspace, tmp_path):
    """Codex implementation review Finding 10: an exception the original
    draft's explicit branches never anticipated (here, raised directly
    from the frontend's service_starter, after the backend is already
    up) must still result in the backend being torn down -- the
    surrounding `finally` must catch this, not only the named failure
    branches.
    """
    ports = iter([1111, 2222])
    torn_down = []

    def fake_waiter(handle, health_path, timeout_s):
        return _FakeReadiness(ready=True)

    class _OkBuild:
        returncode = 0
        stderr = ""
        stdout = ""

    call_count = {"n": 0}

    def flaky_starter(*, name, **kwargs):
        call_count["n"] += 1
        if name == "frontend":
            raise OSError("no such file or directory: npm")
        return _FakeHandle(name=name, port=kwargs["port"])

    def fake_teardown(handle):
        torn_down.append(handle.name)
        return True

    with pytest.raises(OSError):
        run_runtime_verification(
            _one_check_plan(),
            **_common_kwargs(
                repo_root, workspace, tmp_path,
                port_reserver=lambda: next(ports), service_starter=flaky_starter, readiness_waiter=fake_waiter,
                teardown=fake_teardown, build_runner=lambda *a, **k: _OkBuild(),
            ),
        )
    assert torn_down == ["backend"]  # the backend handle that WAS created still gets torn down


def test_ac030_teardown_failure_retroactively_flips_an_otherwise_passing_round(repo_root, workspace, tmp_path):
    ports = iter([1111, 2222])

    def fake_starter(*, name, **kwargs):
        return _FakeHandle(name=name, port=kwargs["port"])

    def fake_waiter(handle, health_path, timeout_s):
        return _FakeReadiness(ready=True)

    class _OkBuild:
        returncode = 0
        stderr = ""
        stdout = ""

    def fake_teardown(handle):
        return handle.name != "frontend"  # frontend "fails" to tear down

    check_dict = {
        "check_id": "runtime.cycle-0.0.viewport_overflow", "kind": "viewport_overflow",
        "catalog_version": "1.0.0", "related_ac_ids": ["AC-012"], "parameters": {},
        "status": "PASS", "action_performed": "x", "observation": "x", "measurements": {},
        "screenshot_filename": None, "console_errors": [], "page_errors": [],
        "blocked_network_requests": [], "truncated": False, "omitted_reason": None,
        "started_at": "", "finished_at": "",
    }

    outcome = run_runtime_verification(
        _one_check_plan(),
        **_common_kwargs(
            repo_root, workspace, tmp_path,
            port_reserver=lambda: next(ports), service_starter=fake_starter, readiness_waiter=fake_waiter,
            teardown=fake_teardown, build_runner=lambda *a, **k: _OkBuild(),
            browser_worker_runner=_passing_worker_runner_factory(check_results=[check_dict]),
        ),
    )
    assert outcome.ran is True
    assert outcome.execution_integrity_passed is False  # flipped despite every check PASS
    assert "teardown" in outcome.failure_reason


def test_happy_path_persists_and_stages_evidence(repo_root, workspace, tmp_path):
    ports = iter([1111, 2222])

    def fake_starter(*, name, **kwargs):
        return _FakeHandle(name=name, port=kwargs["port"])

    def fake_waiter(handle, health_path, timeout_s):
        return _FakeReadiness(ready=True)

    class _OkBuild:
        returncode = 0
        stderr = ""
        stdout = ""

    check_dict = {
        "check_id": "runtime.cycle-0.0.viewport_overflow", "kind": "viewport_overflow",
        "catalog_version": "1.0.0", "related_ac_ids": ["AC-012"], "parameters": {"viewport": "mobile"},
        "status": "PASS", "action_performed": "measured", "observation": "no overflow",
        "measurements": {"scroll_width_px": 390, "client_width_px": 390},
        "screenshot_filename": None, "console_errors": [], "page_errors": [],
        "blocked_network_requests": [], "truncated": False, "omitted_reason": None,
        "started_at": "", "finished_at": "",
    }

    outcome = run_runtime_verification(
        _one_check_plan(),
        **_common_kwargs(
            repo_root, workspace, tmp_path,
            port_reserver=lambda: next(ports), service_starter=fake_starter, readiness_waiter=fake_waiter,
            teardown=lambda handle: True, build_runner=lambda *a, **k: _OkBuild(),
            browser_worker_runner=_passing_worker_runner_factory(check_results=[check_dict]),
        ),
    )
    assert outcome.ran is True
    assert outcome.execution_integrity_passed is True
    assert outcome.evidence is not None
    assert outcome.evidence.all_checks_passed is True
    assert outcome.persisted.evidence_json_path.is_file()
    assert (outcome.staged_dir / "evidence.json").is_file()


def test_default_browser_worker_runner_kills_whole_process_group_on_timeout(tmp_path):
    """Codex closure review finding (round 2): escalating to SIGKILL only
    when `process.wait()` on the *direct* child itself times out is
    wrong -- a descendant can ignore/outlive SIGTERM even while the
    direct child dies from it promptly (ordinary SIGTERM default
    action), which would make the old code skip SIGKILL entirely.
    Proves the real fix (escalation driven by a `killpg(pgid, 0)`
    group-liveness probe, not by the direct child's own wait status)
    with a real process tree: the direct child is a shell that dies
    immediately on SIGTERM, but its backgrounded grandchild traps and
    ignores SIGTERM, so only SIGKILL can end it.
    """
    import subprocess as subprocess_module
    import time

    from peos.runtime_verification import _default_browser_worker_runner

    pid_file = tmp_path / "grandchild.pid"
    script = tmp_path / "spawn.sh"
    script.write_text(
        f"(trap '' TERM; sleep 30) & echo $! > {pid_file}\nsleep 30\n", encoding="utf-8",
    )
    script.chmod(0o755)

    with pytest.raises(subprocess_module.TimeoutExpired):
        _default_browser_worker_runner(
            ["/bin/sh", str(script)], capture_output=True, text=True, timeout=1,
        )

    deadline = time.monotonic() + 5.0
    grandchild_pid = None
    while time.monotonic() < deadline:
        if pid_file.is_file() and pid_file.read_text().strip():
            grandchild_pid = int(pid_file.read_text().strip())
            break
        time.sleep(0.1)
    assert grandchild_pid is not None, "grandchild never recorded its own pid"

    import os
    import signal

    time.sleep(0.5)  # give the runner's own grace-period teardown a moment to complete
    with pytest.raises(ProcessLookupError):
        os.kill(grandchild_pid, 0)  # existence probe -- must be gone, not merely orphaned
