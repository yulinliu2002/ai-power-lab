# SPEC-003 — PEOS Agent Authentication Bridge and Failure Diagnostics

**Status:** Approved
**Project:** AI Power Lab
**System:** PEOS Automation V1 (`peos/sandbox.py`, `peos/claude_agent.py`,
`peos/codex_agent.py`, `peos/workflow.py`, `peos/report.py`)
**Version:** 0.1
**Type:** Workflow Infrastructure

---

This specification implements `docs/decisions/0002-peos-agent-authentication-boundary.md`
(Approved). Where anything below appears to conflict with that decision
record, the decision record governs and this spec is in error — see
`ENGINEERING.md`'s Source-of-Truth Hierarchy.

## Engineering Question

How does PEOS give Claude Code and Codex exactly the authentication
material each needs to run non-interactively, while every invocation
still executes with `HOME` redirected to a disposable, empty directory
(`peos/sandbox.py`'s `sandboxed_env()`) — and how does PEOS surface an
authentication failure (or any other agent-process failure) to the
Human Engineering Lead as an actionable, bounded, sanitized diagnostic
instead of a bare exit code?

## Motivation

The first real PEOS dogfood run failed closed with
`returncode=1`, `terminal_reason=api_error`, `"Not logged in · Please
run /login"`. Root cause (recorded in this session's diagnosis,
summarized in `docs/decisions/0002`): both CLIs resolve their own login
state from paths under `HOME` (`~/.claude.json` + macOS Keychain for
Claude; `$CODEX_HOME/auth.json`, defaulting to `$HOME/.codex`, for
Codex). `sandboxed_env()` redirects `HOME` to an empty directory for a
real, load-bearing reason (no ambient Git/SSH credentials reachable —
see that module's docstring), which as a side effect also deletes both
agents' own login state. A second, related defect: `run_claude`'s and
`run_codex_review`'s non-zero-exit branches discard captured
`stdout`/`stderr` when building `error`, so the Human Engineering Lead
saw only `"claude exited with status 1"` instead of the actionable
`"Not logged in"` text that was sitting in `stdout` the whole time.

Decision `0002` ratified the governing principles (disposable `HOME`
stays mandatory; authentication is a named, explicit exception to it;
each agent gets only its own CLI's minimum supported material; no
credential copied into the repository or a reconciled workspace; fail
closed when a bridge can't be established) but left four items open.
Those have since been resolved by the Human Engineering Lead (see
Requirements below) and are operationalized here.

## Scope

- `peos/sandbox.py`: the Claude authentication pass-through, the
  Codex-specific `CODEX_HOME` override, and the shared bounded/sanitized
  diagnostic helper.
- `peos/claude_agent.py`, `peos/codex_agent.py`: using that diagnostic
  helper when a subprocess exits non-zero or produces uninterpretable
  output.
- `peos/workflow.py`: a per-agent authentication precondition check,
  each run immediately before that agent's first invocation in the run
  (not both checked up front), and passing each agent its own
  environment (today both `claude_runner` and `codex_runner` are called
  with the identical `env` dict built once at `workflow.py:307` — this
  spec requires that to change, since Codex needs a different
  `CODEX_HOME` than Claude needs).
- `peos/report.py`: no behavior change is required (its formatting
  functions already read only `.status`/`.summary`, never raw
  `.stdout`/`.stderr`), but this spec adds an acceptance criterion that
  locks that property in place.
- New and existing PEOS tests covering all of the above.

## Out of Scope

- Any change to AI Power Lab simulation physics, the FastAPI backend,
  the frontend, Scenario A, or `SPEC-002`.
- Any change to `SPEC-001`'s or `SPEC-002`'s own text, or to
  `docs/decisions/0002`.
- Any change to CI (`.github/workflows/ci.yml`).
- A general PEOS redesign. This is a narrow operational/security defect
  fix layered onto the existing SPEC-001 implementation.
- Minting, rotating, printing, or persisting any credential. PEOS reads
  pre-existing material the Human Engineering Lead provisions manually,
  outside PEOS, using each CLI's own supported workflow.
- Migrating Codex to an OpenAI API key / service-account credential.
  Explicitly deferred (see Known Limitations).
- Any unattended/CI (non-interactive, no human present) PEOS execution
  mode. V1 remains local, interactive, human-orchestrated; a stronger,
  independently-scoped service credential design is required before
  that mode exists and is not designed here.

## Model / Technical Basis

Not a physics model. The technical basis is CLI-documented, non-guessed
behavior, confirmed directly against the installed CLIs and their
official documentation in this session's research:

- **Claude Code** (`code.claude.com/docs/en/authentication`): a
  one-year OAuth token from `claude setup-token` authenticates against
  the user's existing Claude Pro/Max/Team/Enterprise subscription (not
  pay-per-token API billing) via the `CLAUDE_CODE_OAUTH_TOKEN`
  environment variable — a plain env-var check Claude Code performs at
  startup, not a `HOME`-relative file/keychain lookup. It ranks above
  the `/login` subscription-credential path and below
  `ANTHROPIC_API_KEY`/`apiKeyHelper` in Claude Code's documented
  precedence order; since `sandboxed_env()` sets none of the
  higher-ranked sources, setting only `CLAUDE_CODE_OAUTH_TOKEN` is
  sufficient and unambiguous. `--bare` mode is documented to *not* read
  this variable, so the Claude invocation must continue not passing
  `--bare`.
- **Codex** (`learn.chatgpt.com/docs/auth`,
  `.../docs/auth/ci-cd-auth`): credentials live at
  `$CODEX_HOME/auth.json` (`CODEX_HOME` defaults to `$HOME/.codex`).
  OpenAI's own CI/CD guide's worked example is exactly the shape this
  spec needs: seed `auth.json` once (by the human, outside PEOS) and
  point a dedicated `CODEX_HOME` at a directory containing only that
  file. `peos/codex_agent.py`'s existing `--ignore-user-config`
  /`--ignore-rules` flags already make `config.toml` and rule files
  unnecessary in that directory (confirmed by `codex exec --help`:
  `--ignore-user-config` skips `config.toml` while "auth still uses
  `CODEX_HOME`").
- Codex's `--sandbox read-only` denies writes, not reads (already
  documented in `peos/codex_agent.py`'s module docstring); OpenAI's own
  docs do not address or mitigate an agent reading its own credential
  file. This is a real, confirmed gap this spec does not close — see
  Requirements (Codex) and Known Limitations.

## Assumptions

- The Human Engineering Lead has already run `claude setup-token`
  (interactively, with their own browser, outside PEOS) and holds the
  resulting token.
- The Human Engineering Lead has already run `codex login` once on a
  trusted machine (outside PEOS) with `cli_auth_credentials_store =
  "file"` and copied the resulting `auth.json` into a dedicated
  directory that contains nothing else.
- Both of the above are manual, one-time (until expiry/rotation) setup
  steps performed by a human, not by PEOS. PEOS only *consumes* the
  result.
- The orchestrator process (the `peos` entry point) runs in an
  environment where `CLAUDE_CODE_OAUTH_TOKEN` and the Codex auth
  directory path are already set, exactly like any other environment
  variable a human exports in their shell profile before running `peos`.
- "Presence/usability" precondition checks mean: is the variable set
  and non-empty; does the directory exist; does it contain a
  non-empty file named `auth.json`. They do not mean: is the token
  cryptographically valid, or is the file's JSON well-formed/not
  expired. A token that is present but expired or rejected by the
  server is caught by the existing post-launch failure path
  (Requirement 3g), not the pre-flight check.

## Requirements

### 1. Claude authentication bridge

a. `sandboxed_env()` must name, in code, exactly one additional
   environment variable that is explicitly passed through from the
   orchestrator's ambient environment into every Claude subprocess
   environment: `CLAUDE_CODE_OAUTH_TOKEN`. This must be an explicit,
   auditable allow-list entry (e.g. a named constant alongside
   `CREDENTIAL_ENV_DENYLIST`), not merely "whatever `sandboxed_env()`
   doesn't strip" — the intent (decision `0002`: "authentication is an
   explicit exception to HOME isolation") must be visible in the code,
   even though today's stripping logic would already let this specific
   variable through unmodified.
b. No other new Claude-related environment variable is added.
   `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, and `apiKeyHelper`
   remain unset/unconfigured by PEOS, since they outrank
   `CLAUDE_CODE_OAUTH_TOKEN` in Claude Code's own precedence order and
   would silently change which credential is used.
c. The Claude CLI invocation (`build_claude_command`) must not pass
   `--bare` (Claude Code's own docs: bare mode does not read
   `CLAUDE_CODE_OAUTH_TOKEN`).
d. The token must never be written to any file PEOS creates or touches
   (isolated workspace, `home_dir`, or elsewhere), never logged, and
   never included in any `RunResult`/report field.

### 2. Codex authentication bridge

a. PEOS resolves the Codex authentication directory from one,
   explicitly named configuration source that the Human Engineering
   Lead sets outside PEOS: the environment variable
   `PEOS_CODEX_AUTH_HOME`. PEOS must not default this to the real
   `$HOME/.codex`, must not search for or auto-discover an auth
   directory, and must not fall back to the real `HOME` if it is unset.
b. For every Codex subprocess invocation, PEOS sets `CODEX_HOME` in
   that subprocess's environment to the value of
   `PEOS_CODEX_AUTH_HOME` — and only for the Codex subprocess. The
   Claude subprocess's environment must not have `CODEX_HOME` set, and
   the Codex subprocess's environment must still have `HOME` redirected
   to the isolated `home_dir` exactly as today.
c. This requires `workflow.py` to build a Codex-specific environment
   distinct from Claude's. Today (`workflow.py:307,343,360,413`) one
   `env` dict is built once and reused for both `claude_runner` and
   `codex_runner`; this spec requires the Codex call sites to receive
   their own environment (e.g. `env | {"CODEX_HOME": ...}` or an
   equivalent explicit construction), with Claude's environment
   unchanged from today's shape plus Requirement 1a.
d. Existing `--ignore-user-config`/`--ignore-rules` flags in
   `build_codex_command` are unchanged.
e. PEOS must never run `codex login`, `codex logout`, write to
   `$PEOS_CODEX_AUTH_HOME/auth.json`, or copy that file anywhere else
   (including into the isolated workspace or `home_dir`).
f. The Human Engineering Lead explicitly accepts, as a named V1
   residual risk, that Codex's shell/command-execution tool can
   technically read its own narrowly-scoped `auth.json` during a run
   (Codex's `--sandbox read-only` denies writes, not reads). This spec
   does not attempt to close that gap; see Known Limitations.
g. This spec does not introduce an OpenAI API-key or service-account
   credential path for Codex. The credential kind is unchanged
   (ChatGPT-login-derived `auth.json`); only where it is exposed to the
   subprocess (a dedicated directory, not the real `HOME`) changes.

### 3. Fail-closed behavior

Preconditions are checked **per agent, immediately before that agent's
first invocation in the run** — not both checked together up front.
This avoids coupling an earlier phase (Claude implementation) to the
credential requirements of a later agent (Codex) that the run has not
yet reached, while still failing closed before any process that would
need that credential is ever launched.

a. **Claude precondition.** Immediately before the first Claude
   invocation of a run (the implementation phase), and before that
   subprocess is launched, PEOS checks: `CLAUDE_CODE_OAUTH_TOKEN` is
   set in the orchestrator's environment and non-empty.
b. **Codex precondition.** Immediately before the first Codex
   invocation of a run (the independent-review phase), and before that
   subprocess is launched, PEOS checks: `PEOS_CODEX_AUTH_HOME` is set,
   the path it names exists as a directory, and that directory contains
   a file named `auth.json` that is non-empty.
c. **No redundant revalidation within a run.** Once an agent's
   precondition has been successfully validated for a given run, it
   must not be redundantly revalidated before that same agent's later
   invocations in the same run (e.g. Claude's remediation call, Codex's
   re-review call) — unless the implementation has concrete evidence
   that revalidation is necessary for that specific call (e.g. that
   agent already produced a post-launch authentication failure earlier
   in the same run). Absent such evidence, re-checking is unnecessary
   work, not an additional safety property.
d. Neither check reads, parses, logs, or prints the token's value or
   the `auth.json` file's contents — presence/existence/non-emptiness
   only.
e. If either agent's precondition check fails, PEOS returns a `FAILED`
   `RunResult` immediately, before that agent's subprocess is launched,
   naming only the missing variable name or directory path, never a
   value. (Claude's check, in particular, must still happen before
   `create_isolated_workspace` is run for that attempt, since workspace
   creation is unrelated to credentials and gates nothing about
   Requirement 3a — there is no reason to pay that cost before a
   precondition that is already known to be checkable.)
f. No code path may react to a failed precondition check, or to a
   post-launch authentication failure, by widening scope: restoring the
   real `HOME`, reading any `CREDENTIAL_ENV_DENYLIST` variable, falling
   back to a different Codex `CODEX_HOME`/Claude credential source, or
   retrying with any broader material. `sandboxed_env()` must have no
   such branch.
g. A post-launch authentication failure (agent process launched, but
   the CLI itself reports not-logged-in/invalid-token/etc.) must also
   produce `FAILED`, using the existing `fail()` plumbing in
   `workflow.py`, now carrying the improved diagnostic from
   Requirement 4.

### 4. Diagnostics

a. `run_claude`'s and `run_codex_review`'s non-zero-returncode (and
   other uninterpretable-output) branches must build `error` through a
   single shared helper (used by both `claude_agent.py` and
   `codex_agent.py`, to avoid duplicating the logic), in this order of
   preference — "prefer structured/known error classification where
   available" (decision `0002`):
   1. **Structured first.** Even on a non-zero exit, attempt
      `json.loads(stdout)`. If it parses to an object containing a
      top-level string field the CLI itself uses for its own error
      message (Claude: `result` when `is_error` is true; Codex: its
      documented last-message/error field), use that string as the
      basis for the diagnostic instead of raw, unparsed text — this is
      the CLI's own structured statement of what went wrong (e.g. the
      literal `"Not logged in · Please run /login"` from this
      incident), not a guess reconstructed from a text tail.
   2. **Bounded raw-text fallback.** Only when `stdout` is not
      parseable JSON, or has no such field, fall back to a bounded tail
      of the combined `stdout`+`stderr` (last 500 characters combined,
      stderr given priority if both are present and the combined
      length exceeds the bound).
   Whichever basis is used, the resulting text is then, in order:
   - passed through a short, fixed list of regex redactions for
     token-shaped substrings — `Bearer\s+\S+`, a `sk-`-prefixed run, and
     a generic run of **32+** characters of `[A-Za-z0-9_\-\.]`
     (V1-approved generic threshold, superseding this requirement's
     original 20+ illustrative example: a literal 20-character generic
     threshold false-positives on this codebase's own non-secret
     diagnostic/schema vocabulary, e.g. `acceptance_criteria` (20
     chars) and `missing_validation_evidence` (28 chars); 32 is a
     conservative V1 generic fallback chosen to avoid that, while the
     `Bearer`/`sk-` patterns remain independently, specifically
     redacted regardless of length) — replacing each match with a fixed
     placeholder (e.g. `[REDACTED]`), not merely a per-character mask;
   - classified into one of a small fixed set of categories by matching
     known literal, non-secret CLI phrases (case-insensitive):
     `authentication` (e.g. "not logged in", "please run /login",
     "invalid bearer token", "401"), `schema` (JSON-parse/
     structured-output failures — these already have a distinct
     message today and keep it), `cli_invocation` (process failed to
     start, timed out), default `runtime` for anything else;
   - formatted as `error = f"[{category}] {sanitized_text}"` or
     equivalent, replacing today's bare `"claude exited with status
     N"` / `"codex exec exited with status N"`.
   The redaction rule set must stay fixed and reviewable — explicitly
   not a speculative/general secret-detection framework, per the Human
   Engineering Lead's direction.
b. Raw `stdout`/`stderr` remain available on `ClaudeRunResult`/
   `CodexReviewResult` as today, for internal/debugging use, but
   `peos/report.py`'s human-facing formatting functions
   (`_format_claude_runs`, `_format_reviews`, `_format_verification`,
   and `build_report`) must continue to read only `.status`,
   `.summary`, `.error`, and other already-structured fields — never
   `.stdout`/`.stderr`/`.raw_stdout`/`.raw_stderr` directly. This is
   already true today; this spec locks it in as a tested invariant
   rather than an incidental fact.
c. The improved `error` string flows through `workflow.py`'s existing
   `fail(f"...: {impl_result.error}")`-style call sites unchanged — no
   change to `workflow.py`'s or `report.py`'s message construction is
   required by this requirement.

## Security Invariants

These must remain true after this spec is implemented, with no
exception introduced by this change:

- Disposable, isolated `HOME` for every agent invocation (unchanged).
- Isolated, disposable repository workspace, never the authoritative
  repository (unchanged).
- No Git credentials, no push capability (unchanged — `CREDENTIAL_ENV_DENYLIST`
  stripping is unmodified).
- No unrestricted user/project/local configuration (`--restricted`,
  `--ignore-user-config`/`--ignore-rules` unmodified).
- No MCP servers (`--strict-mcp-config` unmodified).
- No plugins (unmodified).
- No fallback to the real `HOME` or real `~/.codex`, under any
  condition, including failure.
- No credential material (token value or `auth.json` contents) ever
  copied into the repository or the reconciled workspace.
- No secret value ever appears in a PEOS report, log line, or any
  field `report.py` renders.
- PEOS fails closed whenever the configured minimal bridge for an agent
  cannot be established or verified as present.

## Acceptance Criteria

- [ ] **AC-1** `sandboxed_env()` continues to strip every variable in
  `CREDENTIAL_ENV_DENYLIST` and continues to redirect `HOME` to the
  isolated `home_dir`, unchanged from today's behavior.
- [ ] **AC-2** `CLAUDE_CODE_OAUTH_TOKEN` is passed through from the
  orchestrator's environment into the Claude subprocess's environment
  via one explicit, named allow-list entry, and no other new
  Claude-related credential variable is added.
- [ ] **AC-3** If `CLAUDE_CODE_OAUTH_TOKEN` is unset or empty, PEOS
  returns `FAILED` immediately before the first Claude invocation of
  the run, before the Claude subprocess is launched, naming only the
  variable name — regardless of whether Codex's precondition would
  also fail.
- [ ] **AC-4** The Codex subprocess's environment has `CODEX_HOME` set
  to the value of `PEOS_CODEX_AUTH_HOME`, and the Claude subprocess's
  environment does not have `CODEX_HOME` set.
- [ ] **AC-5** If `PEOS_CODEX_AUTH_HOME` is unset, or the directory it
  names is missing, or it has no non-empty `auth.json`, PEOS returns
  `FAILED` immediately before the first Codex invocation of the run,
  before the Codex subprocess is launched, naming only the configured
  path.
- [ ] **AC-5a** A run with a valid Claude precondition but a missing
  Codex precondition completes the Claude implementation phase
  (including, if the deterministic local verification step runs, that
  step) before failing closed at the Codex phase — Claude's phase is
  never blocked or pre-checked against Codex's credential state, and
  vice versa.
- [ ] **AC-5b** Within a single run, an agent whose precondition
  already passed once is not redundantly re-checked before that same
  agent's later invocation (e.g. Claude's remediation call, Codex's
  re-review call), absent evidence from an intervening post-launch
  authentication failure for that agent.
- [ ] **AC-6** No code path in `peos/sandbox.py`, `peos/workflow.py`,
  `peos/claude_agent.py`, or `peos/codex_agent.py` ever sets `HOME` to
  the real/ambient home directory, restores a `CREDENTIAL_ENV_DENYLIST`
  variable, or widens either agent's auth bridge beyond AC-2/AC-4,
  under any failure condition.
- [ ] **AC-7** A non-zero-exit or uninterpretable-output failure from
  either agent produces an `error` string that is bounded to a single
  stated maximum length and has passed through the redaction pass,
  rather than only an exit-code string.
- [ ] **AC-8a** Given a non-zero-exit `stdout` that is valid JSON
  containing the CLI's own structured error field (e.g. `is_error:
  true`, `result: "Not logged in · Please run /login"`), the resulting
  diagnostic is built from that structured field, is classified
  `authentication`, and contains that human-readable phrase.
- [ ] **AC-8b** Given a non-zero-exit `stdout` that is *not* parseable
  JSON but whose raw text contains "Not logged in" / "Please run
  /login" (or Codex's equivalent), the bounded-tail fallback still
  produces a diagnostic classified `authentication` containing that
  phrase.
- [ ] **AC-9** Given captured output containing a synthetic
  token-shaped string, the resulting diagnostic does not contain that
  string verbatim.
- [ ] **AC-10** No test or real invocation in this spec's verification
  plan demonstrates a secret *value* (token/credential content, not its
  mere presence/absence) appearing in `build_report()`'s rendered
  output.
- [ ] **AC-11** `report.py`'s formatting functions produce identical
  output whether or not a result object's raw `stdout`/`stderr` fields
  are populated, proving they are not read by those functions.
- [ ] **AC-12** The full existing PEOS test suite (`pytest -q` over
  `tests/test_peos_*.py`) remains green, with no existing assertion
  weakened to make it pass.
- [ ] **AC-13** An opt-in, credential-dependent real-CLI contract test
  (gated the same way as the existing ones in
  `tests/test_peos_real_cli_contract.py`) demonstrates `run_claude`
  and/or `run_codex_review` succeeding through `sandboxed_env()` with
  the configured bridge present, and failing closed with an
  `authentication`-classified diagnostic when the bridge material is
  deliberately removed for that one test run.
- [ ] **AC-14** `create_isolated_workspace`'s and
  `reconcile_workspace_to_repo`'s existing behavior (remote removal,
  working-tree carry-over, governance-artifact blocking,
  working-tree-only reconciliation) is unchanged; no new code path
  writes authentication material into `repo_root` or the reconciled
  workspace.
- [ ] **AC-15** No change in this spec alters AI Power Lab simulation
  physics, backend/frontend behavior, Scenario A/`SPEC-002` behavior,
  or `.github/workflows/ci.yml`.

## Verification Plan

| AC | Verification | Layer |
|----|---------------|-------|
| AC-1 | `tests/test_peos_sandbox.py` (existing denylist/HOME tests, extended to assert the allow-listed Claude variable is the *only* addition) | Unit |
| AC-2 | New unit test: fake orchestrator env with `CLAUDE_CODE_OAUTH_TOKEN` set, assert it appears unchanged in `sandboxed_env()`'s output and no other new key was added | Unit |
| AC-3 | New unit test: fake orchestrator env without `CLAUDE_CODE_OAUTH_TOKEN` (Codex precondition satisfied), assert `_run_workflow` returns `FAILED` without invoking `claude_runner` | Unit |
| AC-4 | New unit test: assert Codex's built environment has `CODEX_HOME == PEOS_CODEX_AUTH_HOME` and Claude's built environment has no `CODEX_HOME` key | Unit |
| AC-5 | New unit test: fake `PEOS_CODEX_AUTH_HOME` missing / empty directory / missing `auth.json` (Claude precondition satisfied), assert `FAILED` without invoking `codex_runner` | Unit |
| AC-5a | New unit test in `tests/test_peos_workflow.py`: Claude precondition satisfied, Codex precondition deliberately unsatisfied; assert `claude_runner` (and the local verifier, via the existing fake) is invoked and the run only fails closed once it reaches the Codex phase — i.e. the Claude phase's outcome is unaffected by Codex's missing credential | Unit |
| AC-5b | New unit test in `tests/test_peos_workflow.py`: simulate a run that reaches Claude's remediation call (Codex returns `CHANGES_REQUIRED` once) with Claude's precondition satisfied from the start; assert the precondition check function is invoked exactly once for Claude across the whole run (implementation phase + remediation), not once per invocation | Unit |
| AC-6 | New unit test: run the pre-flight check and `sandboxed_env()` under an environment that includes real-looking `CREDENTIAL_ENV_DENYLIST` values and a real-looking `HOME`, assert neither ever appears in either agent's built environment, including on the failure path | Unit |
| AC-7 | New unit tests in `tests/test_peos_claude_agent.py` / `tests/test_peos_codex_agent.py`: fake non-zero-returncode `CompletedProcess` with long stdout, assert `error` length is bounded and redaction ran | Unit |
| AC-8a | Same files: fake `stdout` = valid JSON with `is_error: true, result: "Not logged in · Please run /login"`, assert the diagnostic is built from the structured field, not a raw-text tail | Unit |
| AC-8b | Same files: fake `stdout` = non-JSON raw text containing "Not logged in · Please run /login", assert the bounded-tail fallback still classifies and surfaces it | Unit |
| AC-9 | Same files: fake stdout containing a synthetic token-shaped string (e.g. a 40-character random-looking string), assert it is absent from `.error` | Unit |
| AC-10 | New unit test in `tests/test_peos_report.py`: build a `RunResult` whose `claude_runs`/review results carry a synthetic secret in raw `stdout`/`stderr`, call `build_report()`, assert the secret string is absent from the returned text | Unit |
| AC-11 | New unit test in `tests/test_peos_report.py`: call the formatting functions with two otherwise-identical result objects differing only in raw `stdout`/`stderr` content, assert byte-identical rendered output | Unit |
| AC-12 | `python -m pytest -q` over the full `tests/` directory | Regression |
| AC-13 | Extended `tests/test_peos_real_cli_contract.py`, gated by `PEOS_REAL_CLI_TESTS=1` and skipped when the real CLIs or configured bridge material are absent | Scenario validation (real CLI) |
| AC-14 | Existing `tests/test_peos_sandbox.py` workspace-creation/reconciliation tests remain green, unmodified in their assertions | Regression |
| AC-15 | Full `python -m pytest -q` plus `npm run lint && npm run typecheck && npm run build` remain green | Regression |

## Known Limitations

- **Accepted V1 residual risk (explicitly accepted by the Human
  Engineering Lead):** Codex's shell/command-execution tool can
  technically read its own narrowly-scoped `auth.json` during a run,
  since `--sandbox read-only` denies writes, not reads. This spec does
  not mitigate that; a scoped, independently-revocable credential
  (e.g. an OpenAI API key instead of reusing a ChatGPT-login-derived
  `auth.json`) was identified as the eventual mitigation but is
  explicitly deferred — see Out of Scope.
- Token/credential **provisioning and rotation are entirely manual**,
  performed by the Human Engineering Lead outside PEOS. PEOS has no
  renewal or expiry-warning behavior. An expired or server-rejected
  token is *not* treated the same as a missing one: it passes the
  pre-flight precondition check (Requirement 3a/3b, which only checks
  presence/non-emptiness) and is only caught afterward, as a
  post-launch authentication failure (Requirement 3g) with the same
  `authentication` classification an outright-missing credential's
  pre-flight failure also uses — the two are distinguished by *when*
  they are caught (before vs. after process launch), not by a
  different diagnostic category.
- This spec's fixed redaction rule set is conservative and may miss
  secret shapes it does not match; this is an accepted tradeoff
  (explicitly not a general secret-detection framework) rather than a
  gap this spec claims to close completely.
- Future unattended/CI PEOS execution is explicitly out of scope and,
  per the Human Engineering Lead's own decision, is expected to need a
  different, more strongly scoped service-credential design than this
  spec provides.
- This spec assumes a single local operator and a single configured
  credential pair per machine; multiple concurrent PEOS
  installations/users sharing one `PEOS_CODEX_AUTH_HOME` or one
  `CLAUDE_CODE_OAUTH_TOKEN` is out of scope.
