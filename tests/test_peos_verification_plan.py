"""Tests for the frozen deterministic verification plan
(peos/verification_plan.py, SPEC-001 remediation Finding 8, strengthened
by Finding 1 (execution boundary), Finding 5 (semantic freeze), and
Finding 7 (dependency provisioning) in the second remediation pass).

These are routing/logic tests: they inject a trivial `sandbox_wrapper`
(identity function) so they exercise the frozen-plan logic without
needing a real `sandbox-exec` invocation, which keeps them passing on
any platform (this repository's CI runs `ubuntu-latest`, which has no
`sandbox-exec`). The real OS-enforced sandbox boundary is exercised for
real, platform-gated, in tests/test_peos_sandbox.py.
"""

import json
import sys
from pathlib import Path

from peos.sandbox import IsolatedWorkspace, SandboxUnavailableError
from peos.verification_plan import execute_plan, resolve_verification_plan
from peos.verify import CommandResult


def _identity_sandbox_wrapper(command, workspace, repo_root, sandbox_profile_dir):
    return list(command)


def _unavailable_sandbox_wrapper(command, workspace, repo_root, sandbox_profile_dir):
    raise SandboxUnavailableError("sandbox not available in this test")


def _workspace_for(path: Path) -> IsolatedWorkspace:
    home = path.parent / "home"
    home.mkdir(exist_ok=True)
    return IsolatedWorkspace(path=path, home_dir=home, baseline_commit="deadbeef")


def _ok(name, command, cwd, env=None):
    return CommandResult(name=name, command=tuple(command), cwd=str(cwd), returncode=0, stdout="ok", stderr="")


def test_plan_includes_pytest_always(tmp_path):
    plan = resolve_verification_plan(tmp_path)
    assert plan.steps[0].name == "python tests (pytest -q)"
    assert plan.steps[0].required_input == "tests"


def test_plan_includes_frontend_steps_only_when_frontend_exists(tmp_path):
    plan_without = resolve_verification_plan(tmp_path)
    assert len(plan_without.steps) == 1

    (tmp_path / "frontend").mkdir()
    plan_with = resolve_verification_plan(tmp_path)
    assert len(plan_with.steps) == 4
    assert [s.name for s in plan_with.steps] == [
        "python tests (pytest -q)", "frontend lint", "frontend typecheck", "frontend build",
    ]


def test_execute_plan_runs_each_step(tmp_path):
    (tmp_path / "tests").mkdir()
    plan = resolve_verification_plan(tmp_path)
    workspace = _workspace_for(tmp_path)
    calls = []

    def runner(name, command, cwd, env=None):
        calls.append(name)
        return _ok(name, command, cwd)

    report = execute_plan(
        plan, workspace, tmp_path, tmp_path / "sandbox-profiles",
        command_runner=runner, sandbox_wrapper=_identity_sandbox_wrapper,
    )
    assert report.passed
    assert calls == ["python tests (pytest -q)"]


def test_execute_plan_passes_sandboxed_env_to_command_runner(tmp_path):
    (tmp_path / "tests").mkdir()
    plan = resolve_verification_plan(tmp_path)
    workspace = _workspace_for(tmp_path)
    seen_envs = []

    def runner(name, command, cwd, env=None):
        seen_envs.append(env)
        return _ok(name, command, cwd)

    execute_plan(
        plan, workspace, tmp_path, tmp_path / "sandbox-profiles",
        command_runner=runner, sandbox_wrapper=_identity_sandbox_wrapper,
    )
    assert seen_envs[0] is not None
    assert seen_envs[0]["HOME"] == str(workspace.home_dir)


def test_plan_cannot_be_silently_weakened_after_a_required_input_disappears(tmp_path):
    """Finding 8: if the implementation agent deletes `tests/` after the
    plan was frozen, verification must record a hard FAILURE for that
    step, not silently skip it and report PASS.
    """
    (tmp_path / "tests").mkdir()
    plan = resolve_verification_plan(tmp_path)  # frozen while tests/ still exists
    workspace = _workspace_for(tmp_path)

    # Simulate an agent deleting the required input after the plan froze.
    (tmp_path / "tests").rmdir()

    calls = []

    def runner(name, command, cwd, env=None):
        calls.append(name)
        return _ok(name, command, cwd)

    report = execute_plan(
        plan, workspace, tmp_path, tmp_path / "sandbox-profiles",
        command_runner=runner, sandbox_wrapper=_identity_sandbox_wrapper,
    )
    assert not report.passed
    assert calls == []  # the pytest command itself was never even run
    assert len(report.failures) == 1
    assert "required verification input missing" in report.failures[0].error


def test_plan_step_count_never_shrinks_even_if_frontend_disappears(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "frontend").mkdir()
    (tmp_path / "frontend" / "node_modules").mkdir()
    (tmp_path / "frontend" / "package.json").write_text(
        json.dumps({"scripts": {"lint": "eslint", "typecheck": "tsc", "build": "next build"}}),
        encoding="utf-8",
    )
    plan = resolve_verification_plan(tmp_path)
    assert len(plan.steps) == 4

    (tmp_path / "frontend" / "package.json").unlink()
    workspace = _workspace_for(tmp_path)

    def runner(name, command, cwd, env=None):
        return _ok(name, command, cwd)

    report = execute_plan(
        plan, workspace, tmp_path, tmp_path / "sandbox-profiles",
        command_runner=runner, sandbox_wrapper=_identity_sandbox_wrapper,
    )
    assert len(report.results) == 4  # still 4 recorded results, not silently 1
    assert not report.passed
    failing_names = {r.name for r in report.failures}
    assert failing_names == {"frontend lint", "frontend typecheck", "frontend build"}


def test_frontend_step_requires_node_modules_even_if_package_json_present(tmp_path):
    """Finding 7: frontend/package.json existing is not enough -- without
    frontend/node_modules actually provisioned in the workspace, running
    `npm run lint` would fail with a cryptic "command not found" rather
    than a clear, explicit message. This is checked as a required input,
    not left to the natural npm failure.
    """
    (tmp_path / "tests").mkdir()
    (tmp_path / "frontend").mkdir()
    (tmp_path / "frontend" / "package.json").write_text(
        json.dumps({"scripts": {"lint": "eslint", "typecheck": "tsc", "build": "next build"}}),
        encoding="utf-8",
    )
    # Deliberately no frontend/node_modules.
    plan = resolve_verification_plan(tmp_path)
    workspace = _workspace_for(tmp_path)

    report = execute_plan(
        plan, workspace, tmp_path, tmp_path / "sandbox-profiles",
        command_runner=lambda name, command, cwd, env=None: _ok(name, command, cwd),
        sandbox_wrapper=_identity_sandbox_wrapper,
    )
    frontend_failures = [r for r in report.failures if r.name.startswith("frontend")]
    assert len(frontend_failures) == 3
    for failure in frontend_failures:
        assert "frontend/node_modules" in failure.error


def test_npm_script_redefinition_to_a_no_op_fails_closed(tmp_path):
    """Finding 5: an implementation agent rewriting
    frontend/package.json's `scripts.build` into a successful no-op
    (e.g. "true") after the plan was frozen must not silently satisfy
    verification -- "preserve the meaning of verification, not only
    command strings."
    """
    (tmp_path / "tests").mkdir()
    (tmp_path / "frontend").mkdir()
    (tmp_path / "frontend" / "node_modules").mkdir()
    package_json = tmp_path / "frontend" / "package.json"
    package_json.write_text(
        json.dumps({"scripts": {"lint": "eslint", "typecheck": "tsc", "build": "next build"}}),
        encoding="utf-8",
    )
    plan = resolve_verification_plan(tmp_path)  # frozen with scripts.build="next build"

    # Simulate an agent redefining the build script into a no-op.
    package_json.write_text(
        json.dumps({"scripts": {"lint": "eslint", "typecheck": "tsc", "build": "true"}}),
        encoding="utf-8",
    )
    workspace = _workspace_for(tmp_path)
    calls = []

    def runner(name, command, cwd, env=None):
        calls.append(name)
        return _ok(name, command, cwd)

    report = execute_plan(
        plan, workspace, tmp_path, tmp_path / "sandbox-profiles",
        command_runner=runner, sandbox_wrapper=_identity_sandbox_wrapper,
    )
    assert "frontend build" not in calls  # the redefined script was never actually run
    build_failure = next(r for r in report.results if r.name == "frontend build")
    assert not build_failure.passed
    assert "changed after the verification plan was frozen" in build_failure.error
    # lint/typecheck were unaffected (their script strings didn't change)
    assert "frontend lint" in calls
    assert "frontend typecheck" in calls


def _write_spec(path: Path, body: str) -> Path:
    path.write_text(f"# SPEC-TEST\n\n**Status:** Approved\n\n{body}\n", encoding="utf-8")
    return path


def test_plan_includes_spec_declared_verification_command(tmp_path):
    """Latest Codex review, Finding 3: the governing specification's own
    Verification section can declare an additional required command that
    the default repo-structure-derived plan has no way to know about.
    """
    (tmp_path / "tests").mkdir()
    spec_path = _write_spec(
        tmp_path / "SPEC-TEST-x.md",
        "## Verification\n\n"
        "In addition to the standard suite, this change must also pass:\n\n"
        "    pytest tests/test_scenario_a_regression.py -q\n",
    )

    plan = resolve_verification_plan(tmp_path, spec_path)

    names = [s.name for s in plan.steps]
    assert any("test_scenario_a_regression.py" in n for n in names)
    spec_step = next(s for s in plan.steps if "test_scenario_a_regression.py" in s.name)
    assert spec_step.command == ("pytest", "tests/test_scenario_a_regression.py", "-q")
    assert spec_step.parse_error is None


def test_spec_declared_command_cannot_silently_disappear_if_workspace_spec_is_tampered(tmp_path):
    """The plan must be frozen from repo_root's authoritative spec text at
    Phase 1, before any implementation agent runs -- so an agent editing
    the *workspace's* copy of the spec to remove the Verification section
    after the plan is frozen must not make the required command vanish
    from what actually executes.
    """
    (tmp_path / "tests").mkdir()
    spec_path = _write_spec(
        tmp_path / "SPEC-TEST-x.md",
        "## Verification\n\n    pytest tests/test_must_not_vanish.py -q\n",
    )

    plan = resolve_verification_plan(tmp_path, spec_path)  # frozen while the section still exists

    # Simulate an implementation agent rewriting the spec inside the
    # isolated workspace (a different file on disk in the real workflow,
    # but resolve_verification_plan never re-reads spec_path after this
    # point regardless -- this directly proves that by overwriting the
    # same authoritative file and showing the already-frozen plan is
    # unaffected).
    spec_path.write_text("# SPEC-TEST\n\n**Status:** Approved\n\nno verification section anymore\n", encoding="utf-8")

    names = [s.name for s in plan.steps]
    assert any("test_must_not_vanish.py" in n for n in names)


def test_spec_declared_command_already_covered_by_default_plan_is_not_duplicated(tmp_path):
    (tmp_path / "tests").mkdir()
    spec_path = _write_spec(
        tmp_path / "SPEC-TEST-x.md",
        f"## Verification\n\n    {sys.executable} -m pytest -q\n",
    )

    plan = resolve_verification_plan(tmp_path, spec_path)

    assert len(plan.steps) == 1  # not duplicated alongside the default pytest step
    assert plan.steps[0].name == "python tests (pytest -q)"


def test_spec_declared_unparseable_command_fails_closed_without_being_dropped(tmp_path):
    """An unparseable spec-declared command line must still appear in the
    frozen plan and hard-fail at execution -- never silently skipped,
    which would be exactly the "spec-specific requirement disappears" gap.
    """
    (tmp_path / "tests").mkdir()
    spec_path = _write_spec(
        tmp_path / "SPEC-TEST-x.md",
        '## Verification\n\n    pytest "unbalanced quote\n',
    )

    plan = resolve_verification_plan(tmp_path, spec_path)
    assert len(plan.steps) == 2
    spec_step = plan.steps[1]
    assert spec_step.parse_error is not None

    workspace = _workspace_for(tmp_path)
    calls = []

    def runner(name, command, cwd, env=None):
        calls.append(name)
        return _ok(name, command, cwd)

    report = execute_plan(
        plan, workspace, tmp_path, tmp_path / "sandbox-profiles",
        command_runner=runner, sandbox_wrapper=_identity_sandbox_wrapper,
    )
    assert spec_step.name not in calls  # never actually run
    assert not report.passed
    assert any("could not be parsed" in f.error for f in report.failures)


def test_execute_plan_fails_closed_when_sandbox_unavailable(tmp_path):
    """Finding 1 (BLOCKER): if the verification sandbox cannot be built
    on this platform, every step must fail closed, never fall back to
    running the real command unconfined.
    """
    (tmp_path / "tests").mkdir()
    plan = resolve_verification_plan(tmp_path)
    workspace = _workspace_for(tmp_path)
    calls = []

    def runner(name, command, cwd, env=None):
        calls.append(name)  # must never be reached
        return _ok(name, command, cwd)

    report = execute_plan(
        plan, workspace, tmp_path, tmp_path / "sandbox-profiles",
        command_runner=runner, sandbox_wrapper=_unavailable_sandbox_wrapper,
    )
    assert calls == []
    assert not report.passed
    assert "sandbox not available" in report.failures[0].error
