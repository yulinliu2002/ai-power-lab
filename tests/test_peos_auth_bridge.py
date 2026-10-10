"""Tests for the PEOS agent authentication bridge (SPEC-003,
implementing docs/decisions/0002) -- the new additions to
peos/sandbox.py: `claude_sandboxed_env`, `codex_sandboxed_env`,
`check_claude_auth_preflight`, `check_codex_auth_preflight`, and
`sandboxed_env()`'s extended stripping.

Real CLI contract coverage (that the real `claude`/`codex` binaries
actually authenticate through these bridges) is opt-in only, in
tests/test_peos_real_cli_contract.py; these are routing/unit tests
against real filesystem operations but no real subprocess calls.
"""

from pathlib import Path

from peos.sandbox import (
    AMBIENT_AGENT_AUTH_DENYLIST,
    CLAUDE_AUTH_ENV_VAR,
    CODEX_AUTH_FILENAME,
    CODEX_AUTH_HOME_ENV_VAR,
    CREDENTIAL_ENV_DENYLIST,
    check_claude_auth_preflight,
    check_codex_auth_preflight,
    claude_sandboxed_env,
    codex_sandboxed_env,
    sandboxed_env,
)


# --- SPEC-003 Requirement 1a / AC-1, AC-2 -------------------------------

def test_claude_auth_env_var_is_not_also_a_credential_denylist_entry():
    assert CLAUDE_AUTH_ENV_VAR not in CREDENTIAL_ENV_DENYLIST


def test_sandboxed_env_strips_the_claude_token_from_the_common_base(tmp_path):
    base_env = {CLAUDE_AUTH_ENV_VAR: "real-token-value", "PATH": "/usr/bin"}
    env = sandboxed_env(tmp_path / "home", base_env=base_env)
    assert CLAUDE_AUTH_ENV_VAR not in env
    assert env["PATH"] == "/usr/bin"


def test_claude_sandboxed_env_adds_back_only_the_claude_token(tmp_path):
    base = sandboxed_env(tmp_path / "home", base_env={"PATH": "/usr/bin"})
    claude_env = claude_sandboxed_env(base, "my-test-token")
    assert claude_env[CLAUDE_AUTH_ENV_VAR] == "my-test-token"
    # The common base passed in must not be mutated by this call.
    assert CLAUDE_AUTH_ENV_VAR not in base


def test_claude_env_never_has_codex_home_set(tmp_path):
    base = sandboxed_env(tmp_path / "home", base_env={"PATH": "/usr/bin"})
    claude_env = claude_sandboxed_env(base, "my-test-token")
    assert "CODEX_HOME" not in claude_env


# --- Focused Codex review remediation, Finding 1 (MAJOR) --------------
# Ambient/competing agent-auth configuration in the orchestrator's own
# environment must not survive sandboxed_env()'s common base, and so
# must not reach either agent's built environment either -- not merely
# "whatever CREDENTIAL_ENV_DENYLIST happens to strip", but a named,
# auditable list covering the specific competing-auth variables.

def test_sandboxed_env_strips_an_ambient_codex_home(tmp_path):
    """An ambient CODEX_HOME in the orchestrator's own shell (e.g. a
    developer's personal Codex config, set outside PEOS) must not
    survive into the common base -- it is re-added, explicitly, only
    for Codex's own environment, from the validated
    PEOS_CODEX_AUTH_HOME, never from whatever was already ambient.
    """
    base_env = {"CODEX_HOME": "/Users/dev/.codex", "PATH": "/usr/bin"}
    env = sandboxed_env(tmp_path / "home", base_env=base_env)
    assert "CODEX_HOME" not in env


def test_sandboxed_env_strips_ambient_anthropic_api_key(tmp_path):
    base_env = {"ANTHROPIC_API_KEY": "sk-ambient-key", "PATH": "/usr/bin"}
    env = sandboxed_env(tmp_path / "home", base_env=base_env)
    assert "ANTHROPIC_API_KEY" not in env


def test_sandboxed_env_strips_ambient_anthropic_auth_token(tmp_path):
    base_env = {"ANTHROPIC_AUTH_TOKEN": "ambient-token", "PATH": "/usr/bin"}
    env = sandboxed_env(tmp_path / "home", base_env=base_env)
    assert "ANTHROPIC_AUTH_TOKEN" not in env


def test_sandboxed_env_strips_ambient_openai_api_key(tmp_path):
    base_env = {"OPENAI_API_KEY": "sk-ambient-openai-key", "PATH": "/usr/bin"}
    env = sandboxed_env(tmp_path / "home", base_env=base_env)
    assert "OPENAI_API_KEY" not in env


def test_sandboxed_env_strips_the_peos_codex_auth_home_config_variable_itself(tmp_path):
    """The *configuration* variable (PEOS_CODEX_AUTH_HOME), not just the
    CODEX_HOME it resolves to, must not survive the common base either
    -- this is what closes SPEC-003 remediation Finding 2's "local
    verification must not inherit PEOS_CODEX_AUTH_HOME" at the
    environment-building level (the filesystem-level denial is tested
    separately, against the real sandbox, in tests/test_peos_sandbox.py).
    """
    base_env = {CODEX_AUTH_HOME_ENV_VAR: "/some/codex/auth/dir", "PATH": "/usr/bin"}
    env = sandboxed_env(tmp_path / "home", base_env=base_env)
    assert CODEX_AUTH_HOME_ENV_VAR not in env


def test_claude_env_never_carries_ambient_api_key_credentials(tmp_path):
    """End-to-end through claude_sandboxed_env(): none of
    AMBIENT_AGENT_AUTH_DENYLIST survives into Claude's actual built
    environment, even though claude_sandboxed_env() only explicitly adds
    CLAUDE_AUTH_ENV_VAR back.
    """
    base_env = {
        "CODEX_HOME": "/ambient/.codex",
        "ANTHROPIC_API_KEY": "sk-ambient",
        "ANTHROPIC_AUTH_TOKEN": "ambient-token",
        "OPENAI_API_KEY": "sk-ambient-openai",
        "PATH": "/usr/bin",
    }
    base = sandboxed_env(tmp_path / "home", base_env=base_env)
    claude_env = claude_sandboxed_env(base, "my-test-token")
    for key in AMBIENT_AGENT_AUTH_DENYLIST:
        assert key not in claude_env


def test_codex_env_never_carries_ambient_anthropic_or_openai_credentials(tmp_path):
    """End-to-end through codex_sandboxed_env(): Codex must not receive
    ambient ANTHROPIC_API_KEY/ANTHROPIC_AUTH_TOKEN/OPENAI_API_KEY --
    only the explicitly-set CODEX_HOME this function itself adds.
    """
    base_env = {
        "ANTHROPIC_API_KEY": "sk-ambient",
        "ANTHROPIC_AUTH_TOKEN": "ambient-token",
        "OPENAI_API_KEY": "sk-ambient-openai",
        "PATH": "/usr/bin",
    }
    base = sandboxed_env(tmp_path / "home", base_env=base_env)
    codex_env = codex_sandboxed_env(base, str(tmp_path / "codex-auth"))
    assert "ANTHROPIC_API_KEY" not in codex_env
    assert "ANTHROPIC_AUTH_TOKEN" not in codex_env
    assert "OPENAI_API_KEY" not in codex_env
    assert codex_env["CODEX_HOME"] == str(tmp_path / "codex-auth")


def test_no_competing_credential_seeded_in_the_parent_environment_survives_into_either_agent_env(tmp_path):
    """Deterministic, comprehensive regression: seed the parent/
    orchestrator environment with every competing/ambient credential
    this remediation and SPEC-003's own CREDENTIAL_ENV_DENYLIST name,
    then prove none of them survive into *either* agent's final built
    environment.
    """
    auth_dir = tmp_path / "codex-auth-home"
    auth_dir.mkdir()
    (auth_dir / CODEX_AUTH_FILENAME).write_text('{"fake": "auth"}', encoding="utf-8")

    parent_env = {
        "PATH": "/usr/bin",
        CLAUDE_AUTH_ENV_VAR: "ambient-claude-token-should-not-leak-as-is",
        CODEX_AUTH_HOME_ENV_VAR: str(auth_dir),
        "CODEX_HOME": "/ambient/.codex",
        "ANTHROPIC_API_KEY": "sk-ambient-anthropic",
        "ANTHROPIC_AUTH_TOKEN": "ambient-anthropic-token",
        "OPENAI_API_KEY": "sk-ambient-openai",
        **{key: f"ambient-{key.lower()}" for key in CREDENTIAL_ENV_DENYLIST},
    }

    base = sandboxed_env(tmp_path / "home", base_env=parent_env)
    claude_env = claude_sandboxed_env(base, "the-one-real-claude-token")
    codex_env = codex_sandboxed_env(base, str(auth_dir))

    # CODEX_HOME is special-cased: codex_sandboxed_env() legitimately sets
    # it, explicitly, to the *validated* auth_dir -- the assertion here is
    # that it is never the ambient "/ambient/.codex" value that leaked
    # through, not that the key is absent from Codex's own environment.
    # GIT_ASKPASS is likewise special-cased: sandboxed_env() always sets it
    # to a fixed, safe "/bin/false" (unconditionally, not derived from the
    # ambient value) -- the ambient "ambient-git_askpass" value must not
    # survive, but the key being present with that safe fixed value is
    # correct, pre-existing behavior, not a leak.
    competing_keys_excluding_codex_home_for_codex = (
        "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "OPENAI_API_KEY",
        CODEX_AUTH_HOME_ENV_VAR, *(k for k in CREDENTIAL_ENV_DENYLIST if k != "GIT_ASKPASS"),
    )
    for key in ("CODEX_HOME", *competing_keys_excluding_codex_home_for_codex):
        assert key not in claude_env, f"{key} leaked into Claude's environment"
    for key in competing_keys_excluding_codex_home_for_codex:
        assert key not in codex_env, f"{key} leaked into Codex's environment"
    assert codex_env["CODEX_HOME"] != "/ambient/.codex"
    assert claude_env["GIT_ASKPASS"] == "/bin/false"
    assert codex_env["GIT_ASKPASS"] == "/bin/false"

    # And neither agent carries the *other* agent's own credential.
    assert CLAUDE_AUTH_ENV_VAR not in codex_env
    assert claude_env[CLAUDE_AUTH_ENV_VAR] == "the-one-real-claude-token"
    assert codex_env["CODEX_HOME"] == str(auth_dir)


# --- SPEC-003 Requirement 2b / AC-4 -------------------------------------

def test_codex_sandboxed_env_sets_codex_home_only(tmp_path):
    base = sandboxed_env(tmp_path / "home", base_env={"PATH": "/usr/bin"})
    codex_env = codex_sandboxed_env(base, str(tmp_path / "codex-auth"))
    assert codex_env["CODEX_HOME"] == str(tmp_path / "codex-auth")


def test_codex_env_never_carries_the_claude_token(tmp_path):
    """SPEC-003 AC-6 / Requirement 2b: Codex's own environment must never
    carry Claude's credential, even though both are derived from the
    same common base.
    """
    base = sandboxed_env(tmp_path / "home", base_env={CLAUDE_AUTH_ENV_VAR: "leaked?", "PATH": "/usr/bin"})
    codex_env = codex_sandboxed_env(base, str(tmp_path / "codex-auth"))
    assert CLAUDE_AUTH_ENV_VAR not in codex_env


def test_codex_sandboxed_env_does_not_mutate_the_base(tmp_path):
    base = sandboxed_env(tmp_path / "home", base_env={"PATH": "/usr/bin"})
    codex_sandboxed_env(base, str(tmp_path / "codex-auth"))
    assert "CODEX_HOME" not in base


# --- SPEC-003 Requirement 3a/3d / AC-3 -----------------------------------

def test_check_claude_auth_preflight_ok_when_token_present():
    result = check_claude_auth_preflight({CLAUDE_AUTH_ENV_VAR: "x"})
    assert result.ok
    assert result.reason is None


def test_check_claude_auth_preflight_fails_when_unset():
    result = check_claude_auth_preflight({})
    assert not result.ok
    assert CLAUDE_AUTH_ENV_VAR in result.reason


def test_check_claude_auth_preflight_fails_when_empty_string():
    result = check_claude_auth_preflight({CLAUDE_AUTH_ENV_VAR: ""})
    assert not result.ok


def test_check_claude_auth_preflight_never_echoes_a_real_looking_token_value():
    """The failure reason must name the *variable*, not any value -- this
    test uses an unset var (the only case that produces a reason), and
    separately confirms no value ever appears in that reason text.
    """
    result = check_claude_auth_preflight({})
    assert "x" * 10 not in (result.reason or "")


# --- SPEC-003 Requirement 3b/3d / AC-5 ------------------------------------

def test_check_codex_auth_preflight_ok_when_dir_and_file_present(tmp_path):
    auth_dir = tmp_path / "codex-auth"
    auth_dir.mkdir()
    (auth_dir / CODEX_AUTH_FILENAME).write_text('{"not": "really parsed"}', encoding="utf-8")
    result = check_codex_auth_preflight({CODEX_AUTH_HOME_ENV_VAR: str(auth_dir)})
    assert result.ok


def test_check_codex_auth_preflight_fails_when_env_var_unset():
    result = check_codex_auth_preflight({})
    assert not result.ok
    assert CODEX_AUTH_HOME_ENV_VAR in result.reason


def test_check_codex_auth_preflight_fails_when_directory_missing(tmp_path):
    missing = tmp_path / "does-not-exist"
    result = check_codex_auth_preflight({CODEX_AUTH_HOME_ENV_VAR: str(missing)})
    assert not result.ok


def test_check_codex_auth_preflight_fails_when_auth_file_missing(tmp_path):
    auth_dir = tmp_path / "codex-auth-empty-dir"
    auth_dir.mkdir()
    result = check_codex_auth_preflight({CODEX_AUTH_HOME_ENV_VAR: str(auth_dir)})
    assert not result.ok
    assert CODEX_AUTH_FILENAME in result.reason


def test_check_codex_auth_preflight_fails_when_auth_file_is_empty(tmp_path):
    auth_dir = tmp_path / "codex-auth-empty-file"
    auth_dir.mkdir()
    (auth_dir / CODEX_AUTH_FILENAME).write_text("", encoding="utf-8")
    result = check_codex_auth_preflight({CODEX_AUTH_HOME_ENV_VAR: str(auth_dir)})
    assert not result.ok


def test_check_codex_auth_preflight_does_not_require_valid_json_content(tmp_path):
    """Presence/existence/non-emptiness only (SPEC-003 Requirement 3d):
    the preflight check must not parse `auth.json`'s contents -- a
    non-empty but not-actually-JSON file still passes, because deciding
    whether the *credential* is valid is the CLI's job at launch time,
    not this presence check's.
    """
    auth_dir = tmp_path / "codex-auth-garbage"
    auth_dir.mkdir()
    (auth_dir / CODEX_AUTH_FILENAME).write_text("not json at all, just bytes", encoding="utf-8")
    result = check_codex_auth_preflight({CODEX_AUTH_HOME_ENV_VAR: str(auth_dir)})
    assert result.ok
