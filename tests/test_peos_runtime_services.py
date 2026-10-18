"""Tests for peos/runtime_services.py (SPEC-006 Section 8/12).

AC-004 (cwd/env), AC-005/AC-006 (bind failure / readiness timeout),
AC-029 (environment never carries agent credentials -- exercised at the
workflow-wiring layer, not here), AC-030/AC-052 (teardown verification /
port-reservation ordering).
"""

import socket
import sys

import pytest

from peos.runtime_services import (
    is_port_released,
    reserve_ephemeral_port,
    start_service,
    teardown_service,
    wait_for_ready,
)
from peos.sandbox import create_isolated_workspace, discard_workspace, sandboxed_env

from tests._peos_fixtures import make_minimal_repo
from tests.test_peos_sandbox import requires_sandbox_exec


@pytest.fixture
def repo_root(tmp_path):
    return make_minimal_repo(tmp_path)


def test_reserve_ephemeral_port_returns_a_usable_loopback_port():
    port = reserve_ephemeral_port()
    assert 1 <= port <= 65535
    assert is_port_released(port)  # released immediately after reservation


@requires_sandbox_exec
class TestRuntimeServicesLifecycle:
    def test_ac004_ac030_ac052_start_wait_teardown_happy_path(self, repo_root, tmp_path):
        workspace = create_isolated_workspace(repo_root, "svc1")
        try:
            port = reserve_ephemeral_port()
            env = sandboxed_env(workspace.home_dir, base_env={"PATH": "/usr/bin:/bin"})
            handle = start_service(
                name="backend",
                command=[sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
                cwd=workspace.path,
                env=env,
                workspace=workspace,
                repo_root=repo_root,
                profile_dir=tmp_path / "profiles",
                port=port,
                log_dir=tmp_path / "logs",
            )
            assert handle.port == port

            readiness = wait_for_ready(handle, health_path="/", timeout_s=15)
            assert readiness.ready, readiness.stderr_tail

            assert teardown_service(handle) is True
            assert is_port_released(port)
        finally:
            discard_workspace(workspace)

    def test_ac006_readiness_timeout_when_service_never_serves(self, repo_root, tmp_path):
        workspace = create_isolated_workspace(repo_root, "svc2")
        try:
            port = reserve_ephemeral_port()
            env = sandboxed_env(workspace.home_dir, base_env={"PATH": "/usr/bin:/bin"})
            handle = start_service(
                name="backend",
                command=[sys.executable, "-c", "import time; time.sleep(30)"],
                cwd=workspace.path,
                env=env,
                workspace=workspace,
                repo_root=repo_root,
                profile_dir=tmp_path / "profiles",
                port=port,
                log_dir=tmp_path / "logs",
            )
            readiness = wait_for_ready(handle, health_path="/", timeout_s=2, poll_interval_s=0.2)
            assert readiness.ready is False
            assert teardown_service(handle) is True  # still torn down and verified dead
        finally:
            discard_workspace(workspace)

    def test_ac005_readiness_detects_process_that_exits_immediately(self, repo_root, tmp_path):
        workspace = create_isolated_workspace(repo_root, "svc3")
        try:
            port = reserve_ephemeral_port()
            env = sandboxed_env(workspace.home_dir, base_env={"PATH": "/usr/bin:/bin"})
            handle = start_service(
                name="backend",
                command=[sys.executable, "-c", "import sys; sys.exit(1)"],
                cwd=workspace.path,
                env=env,
                workspace=workspace,
                repo_root=repo_root,
                profile_dir=tmp_path / "profiles",
                port=port,
                log_dir=tmp_path / "logs",
            )
            readiness = wait_for_ready(handle, health_path="/", timeout_s=5, poll_interval_s=0.2)
            assert readiness.ready is False
        finally:
            discard_workspace(workspace)

    def test_teardown_on_an_already_exited_process_returns_true(self, repo_root, tmp_path):
        workspace = create_isolated_workspace(repo_root, "svc4")
        try:
            port = reserve_ephemeral_port()
            env = sandboxed_env(workspace.home_dir, base_env={"PATH": "/usr/bin:/bin"})
            handle = start_service(
                name="backend",
                command=[sys.executable, "-c", "pass"],
                cwd=workspace.path,
                env=env,
                workspace=workspace,
                repo_root=repo_root,
                profile_dir=tmp_path / "profiles",
                port=port,
                log_dir=tmp_path / "logs",
            )
            handle.process.wait(timeout=10)
            assert teardown_service(handle) is True
        finally:
            discard_workspace(workspace)

    def test_ac052_both_ports_resolved_before_any_service_starts(self):
        """Pure ordering check: reserving both ports is independent of
        starting either subprocess (SPEC-006 Section 8 step 3 precedes
        steps 4/5) -- reserving twice yields two usable, distinct-enough
        ports with no subprocess involved at all."""
        backend_port = reserve_ephemeral_port()
        frontend_port = reserve_ephemeral_port()
        assert isinstance(backend_port, int) and isinstance(frontend_port, int)
        # Both must already be released (not held open) so a subsequent
        # service bind to either does not collide with this reservation.
        assert is_port_released(backend_port)
        assert is_port_released(frontend_port)


def test_bind_failure_is_detectable_before_starting_a_service():
    """SPEC-006 AC-005: a port already bound by another process is a
    bind failure the caller (peos/runtime_services.py's own consumer,
    peos/workflow.py) must treat as execution-integrity FAILED -- this
    test only proves the detection primitive `is_port_released` itself
    is accurate, which `start_service`'s caller relies on."""
    occupying_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    occupying_socket.bind(("127.0.0.1", 0))
    occupying_socket.listen(1)
    occupied_port = occupying_socket.getsockname()[1]
    try:
        assert is_port_released(occupied_port) is False
    finally:
        occupying_socket.close()
