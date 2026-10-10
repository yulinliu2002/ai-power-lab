"""Tests for the isolated implementation workspace (peos/sandbox.py).

These are "isolated enforcement tests" (SPEC-001 remediation Finding 9):
real local Git clones and real filesystem operations, but no real
`claude`/`codex` subprocess call. They exercise the actual execution
boundary primitives Finding 1 relies on: no remotes survive the clone,
credential-bearing environment variables are stripped, uncommitted and
untracked state is carried over faithfully, and governance-artifact
changes are never copied back onto the authoritative repository.

The `TestVerificationSandboxEnforcement` tests below are a distinct
category: real `sandbox-exec` invocations (platform-gated to macOS,
where this repository's verification sandbox is implemented) proving
the BLOCKER (Finding 1) is actually closed -- a malicious verification
command genuinely cannot write to the authoritative repository, read
its `.git` metadata, or reach the network, as opposed to a mocked
routing test that only proves our Python *called* the right function.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from peos.sandbox import (
    CREDENTIAL_ENV_DENYLIST,
    SandboxUnavailableError,
    build_verification_sandbox_profile,
    create_isolated_workspace,
    discard_workspace,
    ensure_spec_in_workspace,
    reconcile_workspace_to_repo,
    sandboxed_env,
    sandboxed_verification_command,
)

from tests._peos_fixtures import make_minimal_repo

_SANDBOX_EXEC_AVAILABLE = sys.platform == "darwin" and shutil.which("sandbox-exec") is not None


def _sandbox_exec_can_apply_nested() -> bool:
    """macOS Seatbelt (`sandbox-exec`) refuses to apply *any* custom
    profile to a process already confined by one -- `sandbox_apply:
    Operation not permitted` -- even a trivial `(allow default)` profile
    nested inside another trivial `(allow default)` one. This was
    verified empirically (ad hoc, not as a committed test, since it is an
    OS platform property rather than this module's own behavior): nesting
    succeeds when the OUTER process is unconfined, and fails as soon as
    the outer process has *any* active custom Seatbelt profile -- which is
    exactly what happens when PEOS verifies its own repository, since
    `pytest -q` (and therefore this very test class) then runs inside the
    verification sandbox built by `peos/sandbox.py`.

    This is a real, deterministic platform limitation, not a flaw in
    `build_verification_sandbox_profile`: it would reproduce identically
    with the simplest possible custom profile. Detecting it live (rather
    than hardcoding "skip when nested") keeps this honest if a future
    macOS release changes the behavior.
    """
    if not _SANDBOX_EXEC_AVAILABLE:
        return False
    probe = subprocess.run(
        ["sandbox-exec", "-p", "(version 1)(allow default)", "/usr/bin/true"],
        capture_output=True, text=True, timeout=10,
    )
    return probe.returncode == 0


_CAN_NEST_SANDBOX_EXEC = _sandbox_exec_can_apply_nested()
requires_sandbox_exec = pytest.mark.skipif(
    not _CAN_NEST_SANDBOX_EXEC,
    reason=(
        "real sandbox-exec enforcement tests require macOS with sandbox-exec "
        "installed, and cannot run nested inside an already-active sandbox-exec "
        "confinement (a platform limitation of sandbox-exec itself, not of this "
        "module -- see _sandbox_exec_can_apply_nested's docstring). This is "
        "expected and not a failure when this suite is itself being run as a "
        "PEOS verification step, i.e. already wrapped by "
        "peos.sandbox.sandboxed_verification_command."
    ),
)


@pytest.fixture
def repo_root(tmp_path):
    return make_minimal_repo(tmp_path)


def test_isolated_workspace_has_no_remotes(repo_root):
    workspace = create_isolated_workspace(repo_root, "testrun1")
    try:
        remotes = subprocess.run(
            ["git", "remote"], cwd=str(workspace.path), capture_output=True, text=True,
        ).stdout.strip()
        assert remotes == ""
    finally:
        discard_workspace(workspace)


def test_isolated_workspace_carries_over_uncommitted_and_untracked_state(repo_root):
    (repo_root / "CLAUDE.md").write_text("# AI Power Lab\n\nmodified uncommitted\n", encoding="utf-8")
    (repo_root / "new_untracked.txt").write_text("brand new\n", encoding="utf-8")

    workspace = create_isolated_workspace(repo_root, "testrun2")
    try:
        assert "modified uncommitted" in (workspace.path / "CLAUDE.md").read_text(encoding="utf-8")
        assert (workspace.path / "new_untracked.txt").read_text(encoding="utf-8") == "brand new\n"
    finally:
        discard_workspace(workspace)


def test_isolated_workspace_is_a_separate_directory_from_repo_root(repo_root):
    workspace = create_isolated_workspace(repo_root, "testrun3")
    try:
        assert workspace.path != repo_root
        assert not str(workspace.path).startswith(str(repo_root))
    finally:
        discard_workspace(workspace)


def test_sandboxed_env_strips_credential_vars_and_redirects_home(tmp_path):
    base_env = {name: "secret-value" for name in CREDENTIAL_ENV_DENYLIST}
    base_env["ANTHROPIC_API_KEY"] = "do-not-strip-this-one"
    base_env["PATH"] = "/usr/bin"

    home_dir = tmp_path / "isolated-home"
    env = sandboxed_env(home_dir, base_env=base_env)

    for name in CREDENTIAL_ENV_DENYLIST:
        if name == "GIT_ASKPASS":
            # Deliberately overridden to a safe value, not merely removed.
            assert env["GIT_ASKPASS"] == "/bin/false"
        else:
            assert name not in env
    assert env["ANTHROPIC_API_KEY"] == "do-not-strip-this-one"
    assert env["PATH"] == "/usr/bin"
    assert env["HOME"] == str(home_dir)
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GIT_CONFIG_NOSYSTEM"] == "1"


def test_reconcile_copies_added_and_modified_files_back(repo_root):
    workspace = create_isolated_workspace(repo_root, "testrun4")
    try:
        (workspace.path / "CLAUDE.md").write_text("# AI Power Lab\n\nTest governance file.\nAppended harmless note.\n", encoding="utf-8")
        (workspace.path / "new_module.py").write_text("x = 1\n", encoding="utf-8")

        result = reconcile_workspace_to_repo(workspace, repo_root)

        assert "new_module.py" in result.copied
        assert (repo_root / "new_module.py").read_text(encoding="utf-8") == "x = 1\n"
        assert "Appended harmless note" in (repo_root / "CLAUDE.md").read_text(encoding="utf-8")
    finally:
        discard_workspace(workspace)


def test_reconcile_mirrors_deletions(repo_root):
    (repo_root / "tests" / "test_placeholder.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    workspace = create_isolated_workspace(repo_root, "testrun5")
    try:
        (workspace.path / "tests" / "test_placeholder.py").unlink()

        result = reconcile_workspace_to_repo(workspace, repo_root)

        assert "tests/test_placeholder.py" in result.deleted
        assert not (repo_root / "tests" / "test_placeholder.py").exists()
    finally:
        discard_workspace(workspace)


def test_reconcile_never_copies_back_protected_governance_changes(repo_root):
    original_claude_md = (repo_root / "CLAUDE.md").read_text(encoding="utf-8")
    workspace = create_isolated_workspace(repo_root, "testrun6")
    try:
        (workspace.path / "CLAUDE.md").write_text("rewritten by an agent\n", encoding="utf-8")

        result = reconcile_workspace_to_repo(
            workspace, repo_root, protected_relative_paths=frozenset({"CLAUDE.md"}),
        )

        assert "CLAUDE.md" in result.blocked_governance_changes
        assert "CLAUDE.md" not in result.copied
        assert (repo_root / "CLAUDE.md").read_text(encoding="utf-8") == original_claude_md
    finally:
        discard_workspace(workspace)


def test_reconcile_with_no_changes_is_a_noop(repo_root):
    workspace = create_isolated_workspace(repo_root, "testrun7")
    try:
        result = reconcile_workspace_to_repo(workspace, repo_root)
        assert result.copied == ()
        assert result.deleted == ()
        assert result.blocked_governance_changes == ()
    finally:
        discard_workspace(workspace)


def test_discard_workspace_removes_the_temp_directory(repo_root):
    workspace = create_isolated_workspace(repo_root, "testrun8")
    parent = workspace.path.parent
    assert parent.exists()
    discard_workspace(workspace)
    assert not parent.exists()


def test_create_isolated_workspace_provisions_frontend_node_modules(repo_root):
    """Finding 7: frontend/node_modules is gitignored, so the clone alone
    would not carry it into the workspace; this must be explicitly
    provisioned so frontend verification is runnable at all.
    """
    frontend = repo_root / "frontend"
    (frontend / "node_modules" / ".bin").mkdir(parents=True)
    (frontend / "node_modules" / "some-package" / "index.js").parent.mkdir(parents=True)
    (frontend / "node_modules" / "some-package" / "index.js").write_text("module.exports = 1;\n", encoding="utf-8")
    (frontend / "package.json").write_text('{"scripts": {}}', encoding="utf-8")

    workspace = create_isolated_workspace(repo_root, "testrun9")
    try:
        copied = workspace.path / "frontend" / "node_modules" / "some-package" / "index.js"
        assert copied.is_file()
        assert copied.read_text(encoding="utf-8") == "module.exports = 1;\n"
    finally:
        discard_workspace(workspace)


def test_create_isolated_workspace_skips_node_modules_copy_when_absent(repo_root):
    # No frontend/ directory at all in the minimal fixture repo -- must
    # not error just because there is nothing to provision.
    workspace = create_isolated_workspace(repo_root, "testrun10")
    try:
        assert not (workspace.path / "frontend").exists()
    finally:
        discard_workspace(workspace)


class TestEnsureSpecInWorkspace:
    """Finding 6: the governing spec must be reachable from inside the
    workspace at a relative path, since Claude (--restricted) and Codex
    both run with cwd=workspace.path and cannot reliably resolve an
    absolute authoritative-repo path.
    """

    def test_spec_inside_repo_root_resolves_to_the_same_relative_path(self, repo_root):
        workspace = create_isolated_workspace(repo_root, "testrun11")
        try:
            spec_path = repo_root / "docs" / "specifications" / "SPEC-001-x.md"
            rel = ensure_spec_in_workspace(workspace, repo_root, spec_path)
            assert rel == "docs/specifications/SPEC-001-x.md"
            assert (workspace.path / rel).is_file()
            assert "Status: Approved" in (workspace.path / rel).read_text(encoding="utf-8") or \
                "Approved" in (workspace.path / rel).read_text(encoding="utf-8")
        finally:
            discard_workspace(workspace)

    def test_spec_outside_repo_root_is_copied_into_the_workspace(self, repo_root, tmp_path):
        external_spec = tmp_path / "elsewhere" / "external-spec.md"
        external_spec.parent.mkdir()
        external_spec.write_text("# External spec\n\nbody\n", encoding="utf-8")

        workspace = create_isolated_workspace(repo_root, "testrun12")
        try:
            rel = ensure_spec_in_workspace(workspace, repo_root, external_spec)
            assert rel == ".peos/governing-spec/external-spec.md"
            assert (workspace.path / rel).read_text(encoding="utf-8") == "# External spec\n\nbody\n"
            # It is reachable as a relative path from the workspace cwd,
            # unlike the original absolute path under tmp_path.
            assert not Path(rel).is_absolute()
        finally:
            discard_workspace(workspace)


def _write_fake_authoritative_git_metadata(repo_root: Path) -> Path:
    secret_file = repo_root / ".git" / "FAKE_SECRET_METADATA"
    secret_file.write_text("authoritative-secret\n", encoding="utf-8")
    return secret_file


@pytest.fixture
def real_repo_root():
    """A minimal real Git repo rooted *outside* the system temp
    directory, under the real $HOME -- deliberately not `tmp_path`.

    The verification sandbox's write-allow list must include the OS temp
    directory for legitimate tool temp-file use (pytest cache, Node/
    Next.js build caches, etc.), and pytest's own `tmp_path` fixture
    happens to live inside that same system temp tree -- so a "repo_root"
    built from `tmp_path` would be inside the sandbox's own allow-list by
    accident, masking exactly the property these enforcement tests exist
    to prove. The real, deployed `repo_root` (the actual ai-power-lab
    checkout) is never under the system temp directory, so this fixture
    is the faithful case.
    """
    import uuid

    root = Path.home() / f".peos-sandbox-enforcement-test-{uuid.uuid4().hex[:12]}"
    root.mkdir()
    try:
        yield make_minimal_repo(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


@requires_sandbox_exec
class TestVerificationSandboxEnforcement:
    """Real, OS-enforced proof that the BLOCKER (Finding 1) is closed:
    a verification command cannot mutate the authoritative repository,
    cannot read its .git metadata, and cannot reach the network -- even
    when the command is deliberately malicious, not merely a command
    that declines to do these things.
    """

    def test_malicious_command_cannot_write_to_the_authoritative_repo(self, real_repo_root, tmp_path):
        workspace = create_isolated_workspace(real_repo_root, "sbx1")
        try:
            profile_dir = tmp_path / "profiles"
            target = real_repo_root / "pwned_by_verification.txt"
            command = sandboxed_verification_command(
                ["python3", "-c", f"open({str(target)!r}, 'w').write('pwned')"],
                workspace, real_repo_root, profile_dir,
            )
            proc = subprocess.run(command, cwd=str(workspace.path), capture_output=True, text=True, timeout=30)
            assert not target.exists(), "verification subprocess mutated the authoritative repository"
            assert proc.returncode != 0
        finally:
            discard_workspace(workspace)

    def test_malicious_command_cannot_read_authoritative_git_metadata(self, real_repo_root, tmp_path):
        secret_file = _write_fake_authoritative_git_metadata(real_repo_root)
        workspace = create_isolated_workspace(real_repo_root, "sbx2")
        try:
            profile_dir = tmp_path / "profiles"
            command = sandboxed_verification_command(
                ["python3", "-c", f"print(open({str(secret_file)!r}).read())"],
                workspace, real_repo_root, profile_dir,
            )
            proc = subprocess.run(command, cwd=str(workspace.path), capture_output=True, text=True, timeout=30)
            assert "authoritative-secret" not in proc.stdout
            assert proc.returncode != 0
        finally:
            discard_workspace(workspace)

    def test_malicious_command_cannot_reach_the_network(self, real_repo_root, tmp_path):
        workspace = create_isolated_workspace(real_repo_root, "sbx3")
        try:
            profile_dir = tmp_path / "profiles"
            command = sandboxed_verification_command(
                ["python3", "-c", "import socket; socket.create_connection(('1.1.1.1', 443), timeout=3)"],
                workspace, real_repo_root, profile_dir,
            )
            proc = subprocess.run(command, cwd=str(workspace.path), capture_output=True, text=True, timeout=30)
            assert proc.returncode != 0
        finally:
            discard_workspace(workspace)

    def test_benign_command_can_still_write_inside_the_workspace(self, real_repo_root, tmp_path):
        # Confirms the sandbox is a real confinement, not a blanket deny
        # that would make verification itself unusable.
        workspace = create_isolated_workspace(real_repo_root, "sbx4")
        try:
            profile_dir = tmp_path / "profiles"
            out_file = workspace.path / "scratch_output.txt"
            command = sandboxed_verification_command(
                ["python3", "-c", f"open({str(out_file)!r}, 'w').write('ok')"],
                workspace, real_repo_root, profile_dir,
            )
            proc = subprocess.run(command, cwd=str(workspace.path), capture_output=True, text=True, timeout=30)
            assert proc.returncode == 0
            assert out_file.read_text(encoding="utf-8") == "ok"
        finally:
            discard_workspace(workspace)

    def test_malicious_command_cannot_write_to_a_repo_root_nested_under_an_allowed_temp_directory(self, tmp_path):
        """Regression for the BLOCKER re-opened in the latest Codex review:
        the verification sandbox's write-allow list includes the process's
        own temp directory (needed for legitimate pytest/npm/tsc scratch
        files) and `/private/tmp`. If `repo_root` itself happens to be
        located under one of those allowed subpaths -- a real scenario,
        e.g. a repo checked out under /tmp or a CI runner's workspace --
        the broad allow previously made the *authoritative* repository
        writable from inside a verification subprocess, defeating the
        very guarantee this sandbox exists to provide.

        Deliberately does not use the `real_repo_root` fixture (which
        exists specifically to dodge this case by rooting outside the
        temp tree) -- this test reproduces the attack the other fixture
        was designed to avoid, using `tmp_path` (pytest's own tmp_path is
        itself under the system temp directory) as the attacker-controlled
        repo_root location.
        """
        repo_root = make_minimal_repo(tmp_path)
        workspace = create_isolated_workspace(repo_root, "sbx-temp-attack")
        try:
            profile_dir = tmp_path / "profiles"
            target = repo_root / "pwned_by_verification.txt"
            command = sandboxed_verification_command(
                ["python3", "-c", f"open({str(target)!r}, 'w').write('pwned')"],
                workspace, repo_root, profile_dir,
            )
            proc = subprocess.run(command, cwd=str(workspace.path), capture_output=True, text=True, timeout=30)
            assert not target.exists(), (
                "verification subprocess mutated the authoritative repository "
                "even though repo_root was nested under an allowed temp path"
            )
            assert proc.returncode != 0
            assert "Operation not permitted" in proc.stderr or "operation not permitted" in proc.stderr.lower()
        finally:
            discard_workspace(workspace)

    def test_benign_command_can_still_write_inside_the_workspace_when_repo_root_is_under_temp(self, tmp_path):
        """Companion to the attack test above: proves the repo_root
        re-deny is scoped to repo_root specifically, not a regression to a
        blanket deny that would also break writing inside the workspace
        when the workspace (as usual) lives under the same temp tree.
        """
        repo_root = make_minimal_repo(tmp_path)
        workspace = create_isolated_workspace(repo_root, "sbx-temp-benign")
        try:
            profile_dir = tmp_path / "profiles"
            out_file = workspace.path / "scratch_output.txt"
            command = sandboxed_verification_command(
                ["python3", "-c", f"open({str(out_file)!r}, 'w').write('ok')"],
                workspace, repo_root, profile_dir,
            )
            proc = subprocess.run(command, cwd=str(workspace.path), capture_output=True, text=True, timeout=30)
            assert proc.returncode == 0
            assert out_file.read_text(encoding="utf-8") == "ok"
        finally:
            discard_workspace(workspace)

    def test_benign_command_can_still_use_a_loopback_socket(self, real_repo_root, tmp_path):
        """Latest Codex review, Finding 4, directly reproduced: the real
        frontend production build (`npm run build`, Next.js/Turbopack)
        failed inside the verification sandbox because Turbopack's
        internal worker communicates over a 127.0.0.1 TCP socket --
        `(deny network*)` denied that bind/connect outright, even though
        it never leaves the machine. The loopback-only exception must
        allow this exact pattern (bind, then a second connection to the
        bound port) while a genuine external destination remains denied
        (proven by the unchanged
        test_malicious_command_cannot_reach_the_network above).
        """
        workspace = create_isolated_workspace(real_repo_root, "sbx-loopback")
        try:
            profile_dir = tmp_path / "profiles"
            command = sandboxed_verification_command(
                [
                    "python3", "-c",
                    "import socket, threading\n"
                    "s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
                    "s.bind(('127.0.0.1', 0))\n"
                    "s.listen(1)\n"
                    "port = s.getsockname()[1]\n"
                    "def client():\n"
                    "    c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
                    "    c.connect(('127.0.0.1', port))\n"
                    "    c.send(b'hi')\n"
                    "    c.close()\n"
                    "t = threading.Thread(target=client)\n"
                    "t.start()\n"
                    "conn, _ = s.accept()\n"
                    "assert conn.recv(10) == b'hi'\n"
                    "t.join()\n"
                    "print('loopback ok')\n",
                ],
                workspace, real_repo_root, profile_dir,
            )
            proc = subprocess.run(command, cwd=str(workspace.path), capture_output=True, text=True, timeout=30)
            assert proc.returncode == 0, proc.stderr
            assert "loopback ok" in proc.stdout
        finally:
            discard_workspace(workspace)

    def test_sandbox_denial_is_distinguishable_from_a_command_simply_declining(self, real_repo_root, tmp_path):
        """Finding 3's "tests must distinguish actual sandbox denial from
        an agent simply declining a write" applies equally to the
        verification sandbox: a command that voluntarily chooses not to
        write anywhere exits 0 with no file created, which must not be
        confused with an OS-level denial (nonzero exit / permission
        error) of a command that *tried*.
        """
        workspace = create_isolated_workspace(real_repo_root, "sbx5")
        try:
            profile_dir = tmp_path / "profiles"
            target = real_repo_root / "never_written.txt"

            declining_command = sandboxed_verification_command(
                ["python3", "-c", "pass"], workspace, real_repo_root, profile_dir,
            )
            declining_proc = subprocess.run(
                declining_command, cwd=str(workspace.path), capture_output=True, text=True, timeout=30,
            )
            assert declining_proc.returncode == 0  # voluntary no-op: not a denial

            trying_command = sandboxed_verification_command(
                ["python3", "-c", f"open({str(target)!r}, 'w').write('x')"], workspace, real_repo_root, profile_dir,
            )
            trying_proc = subprocess.run(
                trying_command, cwd=str(workspace.path), capture_output=True, text=True, timeout=30,
            )
            assert trying_proc.returncode != 0  # actual denial: distinguishable by exit status
            assert "Operation not permitted" in trying_proc.stderr or "operation not permitted" in trying_proc.stderr.lower()
            assert not target.exists()
        finally:
            discard_workspace(workspace)


def test_sandboxed_verification_command_fails_closed_when_unavailable(repo_root, tmp_path, monkeypatch):
    import peos.sandbox as sandbox_module

    monkeypatch.setattr(sandbox_module.shutil, "which", lambda name: None)
    workspace = create_isolated_workspace(repo_root, "sbx6")
    try:
        with pytest.raises(SandboxUnavailableError):
            sandboxed_verification_command(["python3", "-c", "pass"], workspace, repo_root, tmp_path / "profiles")
    finally:
        discard_workspace(workspace)


def test_verification_sandbox_profile_denies_network_and_confines_writes(repo_root):
    workspace = create_isolated_workspace(repo_root, "sbx7")
    try:
        profile = build_verification_sandbox_profile(workspace, repo_root)
        assert "(deny network*)" in profile
        assert str(workspace.path) in profile
        assert str((repo_root / ".git")) in profile or str(repo_root) in profile
    finally:
        discard_workspace(workspace)
