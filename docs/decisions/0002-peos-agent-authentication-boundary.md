# 0002 — PEOS agent authentication boundary

## Context

The first real PEOS dogfood run failed closed: `peos/sandbox.py`'s
`sandboxed_env()` redirects `HOME` to a disposable, empty directory for
every Claude/Codex invocation (correctly, to keep ambient Git/SSH
credentials unreachable — see `sandbox.py`'s module docstring). Both
CLIs resolve their *own* login state from paths under `HOME`
(`~/.claude.json` + the macOS Keychain item `Claude Code-credentials`
for Claude; `$CODEX_HOME/auth.json`, which defaults to `$HOME/.codex`,
for Codex). Redirecting `HOME` makes that state disappear too, so both
agents report "not logged in" even though the orchestrator's own
ambient environment is authenticated. A related observability gap:
`run_claude`/`run_codex_review` already capture subprocess `stdout`/
`stderr`, but the `error` string built on a non-zero exit
(`claude_agent.py`'s and `codex_agent.py`'s `_uninterpretable`/`_fail`
non-zero-returncode branches) discards it, so the failure surfaced to
the Human Engineering Lead was only "claude exited with status 1" —
not the actionable "Not logged in · Please run /login" that was
sitting in `stdout`.

Full diagnosis (root cause, file/line citations, mechanism options,
and the security tradeoffs between them) was produced in this session
before this decision and is not repeated here; this record states what
was decided, not the investigation that led to it.

## Decision

- Keep the disposable isolated `HOME` for every agent invocation.
  Never restore the user's complete real `HOME`, and never restore
  ambient Git/SSH credentials (`CREDENTIAL_ENV_DENYLIST` stays as-is).
- Authentication is an **explicit, named exception** to `HOME`
  isolation — not a side effect of weakening it. Each agent receives
  only the minimum authentication material its own officially
  supported, documented CLI authentication mechanism requires (e.g.
  an env var, not a copied credential file, where the CLI supports
  one).
- Claude and Codex may use different auth bridges — the two CLIs do
  not have to use the same mechanism or the same shape of credential.
- Authentication material must never be written into the reconciled
  workspace or the repository, and must never be placed anywhere
  Claude's granted tools (`Read Edit Write Grep Glob`) or Codex's
  shell could read it back incidentally (i.e. not under
  `workspace.path`, not under the isolated `home_dir` passed as `cwd`
  context).
- MCP servers, plugins, and user/project/local settings remain
  disabled for both agents, unchanged from the current
  `--strict-mcp-config` / `--restricted` / `--ignore-user-config` /
  `--ignore-rules` posture.
- Secrets must never appear in PEOS reports (`peos/report.py`) or in
  any log line `peos/workflow.py` emits.
- If a supported minimal authentication mechanism cannot be
  established for an agent, PEOS fails closed for that agent rather
  than falling back to a broader/unsandboxed credential exposure.

### Observability

- Agent failures must expose a bounded, sanitized diagnostic
  sufficient to distinguish authentication failures from CLI
  invocation failures, schema/structured-output failures, and other
  runtime failures — not just an exit code.
- That diagnostic must be produced by sanitizing captured
  `stdout`/`stderr` (bounding length, not blind copying) rather than
  omitting it — secret-bearing output must not be blindly forwarded
  into a report, but a diagnostic empty of all detail is not an
  acceptable alternative either.

## Status

**Approved.** This decision has been operationalized by
`docs/specifications/SPEC-003-peos-agent-auth-bridge.md` (Approved),
which resolves every item listed below under "Open items for the
implementing specification" and specifies the concrete, testable
requirements that implement the principles ratified above. This
record remains the governing architecture decision; SPEC-003 is where
it is made implementable. Implementation of SPEC-003 has not yet
begun.

## Open items for the implementing specification

**Resolved — kept below for the historical record of what was open at
decision time and why; see `SPEC-003`'s Requirements and Known
Limitations sections for how each was resolved.**

- The exact supported env-var/flag name for Claude's non-interactive,
  non-OAuth-session auth path (`ANTHROPIC_API_KEY` /
  `apiKeyHelper` via `--settings`, or a `claude setup-token`-minted
  long-lived token) must be confirmed against that command's own
  current output/documentation at spec-writing time, not assumed.
- Codex's shell tool is not restricted from *reading* files under
  `--sandbox read-only` (only writes are denied) — exposing even a
  minimal, auth-only `CODEX_HOME` to Codex carries a materially higher
  disclosure risk than Claude's tool-restricted (`Read Edit Write Grep
  Glob` only, no shell) exposure to an env var. The spec must decide
  whether to accept this residual risk, mitigate it (e.g. a scoped,
  independently-revocable API key for Codex rather than reusing the
  human's full ChatGPT session), or treat it as a separate open
  question from Claude's bridge.
- "Fails closed" needs a precise, testable definition for each agent
  (what PEOS does when the chosen mechanism's required material is
  absent — refuse to start the run vs. a specific `RunResult` outcome).
- The bound on sanitized diagnostic output (what "bounded" means in
  characters/lines, and what sanitization specifically strips) needs a
  concrete rule, ideally consistent with the existing tail-extraction
  pattern already used for verification failures in
  `peos/report.py::_format_verification`.
