# SPEC-001 — PEOS Automation V1 — Remediation Validation Record

## Context

- Spec: `docs/specifications/SPEC-001-peos-automation-v1.md` (Status: Approved)
- Branch: `peos/automation-v1`
- This is the **fourth** remediation pass. See "Fourth remediation pass"
  immediately below for what changed in *this* pass. The first three
  passes are summarized in place for context (the "third"/"second pass"
  sections further down were written at the end of those passes and are
  otherwise unchanged). Nothing has been committed, pushed, merged, or
  tagged as part of any of the four remediation passes.
- Prior state (first pass, briefly): introduced the isolated workspace
  (`peos/sandbox.py`), `--restricted` Claude invocation, `--sandbox
  read-only` Codex invocation, strict structured-output parsing, a
  frozen verification plan, and governance-artifact hashing. The second
  review found all of this real but insufficient in specific, reproduced
  ways — summarized per finding below.

## Fourth remediation pass (final acceptance review)

A final Codex acceptance review of the third-pass state above found
exactly one remaining MAJOR defect and one MINOR reporting edge case.
Per the remediation brief, no change was made to PEOS architecture, the
sandbox/workspace isolation design, the verification architecture, the
frontend, or CI — only `peos/claude_agent.py`, `peos/codex_agent.py`, and
`peos/cli.py` (the modules the two findings actually live in), plus their
test files and this document.

### Finding A (MAJOR) — local required-field presence validation did not distinguish a missing key from an explicit null

**The gap, reproduced exactly, two independent cases:**
1. `peos/claude_agent.py::run_claude` — `{"status":"COMPLETED","summary":"ok"}`
   (the `gate_category` and `gate_reason` keys omitted entirely, not set
   to `null`) was accepted as `ok=True`. `structured.get("gate_category")`
   returns `None` for a missing key — indistinguishable from an explicit
   `"gate_category": null` — and `None`/`None` is exactly the valid
   combination for a non-`HUMAN_GATE` status, so a payload missing both
   required keys passed by accident rather than by a validated null.
2. `peos/codex_agent.py::_validate_acceptance_criteria` —
   `{"id":"AC-001","met":true}` (the `note` key omitted) nested inside an
   otherwise-well-formed `APPROVE` payload was accepted. Same root cause:
   `.get("note")` returns `None` for a missing key, which the
   nullable-type check treats as valid.

Both `gate_category`/`gate_reason` and `note` are schema-required *keys*
(`CLAUDE_RESULT_SCHEMA["required"]`, the acceptance-criteria item schema's
`"required"` list inside `REVIEW_SCHEMA`) even though their *values* may
be `null` — a distinction `.get()` alone cannot enforce.

**Fix:** every object level in both validators now checks key *presence*
against the schema's declared `required` list before reading any value,
so an omitted key is rejected distinctly from `.get()` defaulting it to
`None`:
- `claude_agent.run_claude` — the top-level `structured_output` dict,
  checked against `CLAUDE_RESULT_SCHEMA["required"]` (all 4 keys:
  `status`, `gate_category`, `gate_reason`, `summary`).
- `codex_agent._validate_review_payload` — the top-level payload dict,
  checked against `REVIEW_SCHEMA["required"]` (all 4 keys: `verdict`,
  `summary`, `findings`, `acceptance_criteria`).
- `codex_agent._validate_finding` — each finding object, checked against
  `_FINDING_KEYS` (all 4 keys).
- `codex_agent._validate_acceptance_criteria` — each acceptance-criterion
  object, checked against `_AC_KEYS` (all 3 keys, including `note`).

**Regression evidence (exact reproduced payloads):**
`tests/test_peos_claude_agent.py::test_run_claude_missing_required_keys_is_rejected_not_treated_as_null`
(the exact Codex reproduction), `::test_run_claude_missing_summary_key_is_rejected`;
`tests/test_peos_codex_agent.py::test_acceptance_criterion_missing_note_key_is_rejected_not_treated_as_null`
(the exact Codex reproduction), `::test_top_level_payload_missing_acceptance_criteria_key_is_rejected`,
`::test_finding_missing_requires_human_decision_key_is_rejected`.

### Finding B (MINOR) — NUL-containing --spec reporting failure

**The gap, reproduced exactly:**
`main(["review", "--spec", "bad\0spec"])` raised an uncaught
`ValueError: embedded null byte` out of `peos/cli.py::_canonicalize_spec`'s
`candidate.resolve()` call, which only caught `OSError`. Captured before
the fix:
```
ValueError: embedded null byte
  File "peos/cli.py", line 32, in _canonicalize_spec
    candidate = candidate.resolve()
```
This is the same class of gap already fixed for `--repo` in `main()`
(third pass, Finding 5b: `Path.resolve()` on a NUL-containing path raises
`ValueError`, not `OSError`) but that fix was never applied to
`_canonicalize_spec`'s own `.resolve()` call, which has an identical
`except OSError`-only guard.

**Fix:** `_canonicalize_spec` now catches `(OSError, ValueError)` around
`candidate.resolve()`, identical to the `--repo` handling in `main()`,
returning a clean `"--spec path could not be resolved: ..."` error
routed through the normal `build_report` final-report path instead of
raising.

**Regression evidence:**
`tests/test_peos_cli.py::test_rejects_spec_path_with_nul_byte_without_a_traceback`
(the exact reproduction, with a valid `--repo` so the failure is isolated
to `--spec`; asserts a full `"PEOS Run Report"` with `"FAILED"` and
`"could not be resolved"` on stdout, exit code 1, no uncaught exception).

### Can either original Codex reproduction still succeed?

**No.** Both were re-run directly against the fixed code and now fail
closed:
- `run_claude` (via a fake runner returning `{"status":"COMPLETED","summary":"ok"}`
  as `structured_output`) → `ok=False`, `status=None`,
  `error="Claude Code structured result is missing required field(s): ['gate_category', 'gate_reason']"`.
- `_validate_review_payload` on
  `{"verdict":"APPROVE","summary":"ok","findings":[],"acceptance_criteria":[{"id":"AC-001","met":true}]}`
  → `ok=False`, `verdict=None`, `error="Codex `acceptance_criteria` field is malformed: [{'id': 'AC-001', 'met': True}]"`.
- `main(["review", "--spec", "bad\0spec"])` → no exception; returns `1`
  with a full PEOS final report on stdout naming the unresolved `--spec`
  path.

### Fourth-pass verification commands and results

```
$ pytest -q
251 passed, 3 skipped, 1 warning in ~21s
```
(the single warning is the pre-existing `StarletteDeprecationWarning`
from `fastapi.testclient`, unrelated to this work — unchanged from the
third pass.)

PEOS test suite (by file), after this pass:

```
test_peos_claude_agent.py:        21 passed   (+2 regression tests)
test_peos_cli.py:                  11 passed   (+1 regression test)
test_peos_codex_agent.py:          29 passed   (+3 regression tests)
test_peos_gitutil.py:               9 passed   (unchanged)
test_peos_preflight.py:            10 passed   (unchanged)
test_peos_real_cli_contract.py:     3 skipped  (opt-in; not re-run this pass -- no agent command-building or CLI-invocation logic changed, only local JSON key-presence validation and one exception type caught)
test_peos_report.py:                9 passed   (unchanged)
test_peos_sandbox.py:              23 passed   (unchanged)
test_peos_spec.py:                  8 passed   (unchanged)
test_peos_verification_plan.py:    13 passed   (unchanged)
test_peos_verify.py:                6 passed   (unchanged)
test_peos_workflow.py:             26 passed   (unchanged)
--------------------------------------------------------------------------
165 passed, 3 skipped
```

### Fourth-pass finding matrix

| # | Severity | Finding | Status | Evidence |
|---|----------|---------|--------|----------|
| A | MAJOR | Local required-field presence validation did not distinguish a missing key from an explicit null (`gate_category`/`gate_reason` in `claude_agent.py`; acceptance-criterion `note` in `codex_agent.py`) | **RESOLVED** | `peos/claude_agent.py::run_claude` (presence check against `CLAUDE_RESULT_SCHEMA["required"]`); `peos/codex_agent.py::_validate_review_payload`/`_validate_finding`/`_validate_acceptance_criteria` (presence checks against `REVIEW_SCHEMA["required"]`/`_FINDING_KEYS`/`_AC_KEYS`); 5 new regression tests across both agent test files, each the exact reproduced malformed payload |
| B | MINOR | NUL-containing `--spec` raised an uncaught `ValueError` instead of reporting cleanly | **RESOLVED** | `peos/cli.py::_canonicalize_spec` (`except (OSError, ValueError)` around `candidate.resolve()`, matching the existing `--repo` handling); `tests/test_peos_cli.py::test_rejects_spec_path_with_nul_byte_without_a_traceback` |

Both rows are backed by a reproduction of the actual gap against the
pre-fix code (shown succeeding/raising as described above) followed by
the same scenario re-run against the fix (shown failing closed / no
longer raising), not merely a new test written against already-fixed
code.

### Scope confirmation for this pass

No file under `peos/sandbox.py`, `peos/workflow.py`, `peos/verify.py`,
`peos/verification_plan.py`, `peos/gitutil.py`, `peos/preflight.py`,
`peos/report.py`, `peos/spec.py`, `peos/prompts.py`, `frontend/`,
`src/`, `backend/`, `scenarios/`, `config/`, or `.github/workflows/ci.yml`
was touched this pass. Changed/added this pass: `peos/claude_agent.py`,
`peos/codex_agent.py`, `peos/cli.py`,
`tests/test_peos_claude_agent.py`, `tests/test_peos_codex_agent.py`,
`tests/test_peos_cli.py`, and this document. All of `peos/`, `tests/`,
and this document remain untracked/new (never committed in any prior
pass), so there is no tracked-file `git diff` to show for them; `git
status --porcelain` is unchanged in shape from the third pass (see "Git
status / diff summary" below). No commit, push, merge, or tag was made
or attempted this pass either.

## Third remediation pass (latest Codex review)

A further independent Codex review, treated as authoritative for this
pass, reproduced five remaining gaps in the claimed-resolved second-pass
state: one BLOCKER and three MAJOR findings, plus a residual reporting/
failure-safety item. Each is closed below with a concrete before/after
reproduction — the attack or failure was run against the actual code
*before* the fix, confirmed to succeed/fail as the review described, then
re-run against the fix to confirm it no longer does.

### Finding 1 (BLOCKER) — verification sandbox permits mutation of the authoritative repository when repo_root is under an allowed temp directory

**The gap, reproduced exactly:** `build_verification_sandbox_profile`'s
write-allow list includes the process's own resolved temp directory (for
legitimate `pytest`/`npm`/`tsc` scratch-file use) and `/private/tmp`. If
`repo_root` itself is located under either of those paths — a real case:
a repo checked out under `/tmp`, or a CI runner's workspace — the broad
allow made the *authoritative repository* writable from inside a
verification subprocess, defeating the guarantee this sandbox exists to
provide. Reproduced directly: a `repo_root` built under
`tempfile.mkdtemp()` allowed a malicious verification command to write
`PWNED.txt` into it (`returncode=0`, file created).

**Fix:** `build_verification_sandbox_profile` (`peos/sandbox.py`) now
appends an explicit `(deny file-write* (subpath "<repo_root resolved>"))`
rule *after* the write-allow block. Verified empirically (not assumed)
that Seatbelt resolves overlapping `file-write*` rules by last-match-wins
— a `deny` placed after a broader `allow` for an overlapping subpath
takes precedence — before relying on that ordering.

**Regression evidence (real, adversarial, not mocked):**
`tests/test_peos_sandbox.py::TestVerificationSandboxEnforcement::test_malicious_command_cannot_write_to_a_repo_root_nested_under_an_allowed_temp_directory`
(the exact attack: `repo_root` built from `tmp_path`, deliberately *not*
using the `real_repo_root` fixture that exists specifically to avoid this
case) and the companion
`test_benign_command_can_still_write_inside_the_workspace_when_repo_root_is_under_temp`
(proves the re-deny is scoped to `repo_root` specifically, not a
regression to a blanket deny that would also break the workspace).

### Finding 2 (MAJOR) — Claude/Codex local structured-result validation still accepted schema-invalid payloads

**The gap, reproduced exactly, two independent cases plus a shared
`additionalProperties` gap:**
1. `peos/claude_agent.py::run_claude` — a schema-invalid `gate_reason`
   (the schema requires string or null; e.g. an int) was silently
   coerced to `None` by the `isinstance` check *before* the
   status/gate-consistency check ran, so the coercion itself hid the
   malformed field: a `status=COMPLETED` payload with `gate_reason=12345`
   was accepted as `ok=True`.
2. `peos/codex_agent.py::_validate_acceptance_criteria` — a
   schema-invalid acceptance-criterion `note` (same string-or-null rule,
   e.g. an int) was silently coerced to `""` instead of being rejected.
3. Neither `run_claude` nor `_validate_review_payload`/`_validate_finding`/
   `_validate_acceptance_criteria` enforced `additionalProperties: False`
   from their own declared schemas (`CLAUDE_RESULT_SCHEMA`,
   `REVIEW_SCHEMA`) — an unrecognized extra field was silently ignored
   rather than rejected.

**Fix:** both type checks now reject (fail closed) *before* any
coercion, and both modules now reject any top-level/finding/
acceptance-criterion object containing a key outside its declared schema.

**Regression evidence (adversarial parsing, exact reproduced payloads):**
`tests/test_peos_claude_agent.py::test_run_claude_completed_with_non_string_gate_reason_is_rejected_not_coerced`,
`::test_run_claude_structured_output_with_unexpected_extra_field_is_rejected`;
`tests/test_peos_codex_agent.py::test_acceptance_criteria_note_with_invalid_type_is_rejected_not_coerced`,
`::test_finding_with_unexpected_extra_field_is_rejected`,
`::test_acceptance_criterion_with_unexpected_extra_field_is_rejected`,
`::test_top_level_payload_with_unexpected_extra_field_is_rejected`.

### Finding 3 (MAJOR) — verification plan did not incorporate governing-spec-specific verification requirements

**The gap:** `resolve_verification_plan` derived the plan entirely from
repository structure (pytest always, npm scripts if `frontend/` exists);
it never read the governing specification's own text, so a spec
declaring an additional required verification command had no mechanism
to make that command actually run.

**Fix, deliberately narrow and deterministic (explicitly not an
open-ended AI-generated verification system):** a line indented by at
least 4 spaces or a tab, inside a heading section whose text contains
"Verification" (case-insensitive), is parsed as a literal required
command. This is the exact convention SPEC-001's own Section 8 already
uses for its example commands, so parsing it reproduces today's default
plan from the spec text itself with zero new authoring convention.
Commands are frozen from `repo_root`'s authoritative spec copy at Phase 1
(before any implementation agent runs) exactly like the default steps —
an agent cannot make a required command disappear by editing the spec
inside the workspace afterward. An unparseable command line is never
silently dropped: it is still added to the frozen plan as a step that
always hard-fails with a clear message (`VerificationStep.parse_error`).
Duplicate detection compares commands by executable basename (not exact
string), so a spec-declared `python -m pytest -q` is recognized as the
same requirement as the default plan's `<sys.executable> -m pytest -q`
rather than run a second time with a possibly different interpreter.

**Regression evidence:**
`tests/test_peos_verification_plan.py::test_plan_includes_spec_declared_verification_command`,
`::test_spec_declared_command_cannot_silently_disappear_if_workspace_spec_is_tampered`,
`::test_spec_declared_command_already_covered_by_default_plan_is_not_duplicated`,
`::test_spec_declared_unparseable_command_fails_closed_without_being_dropped`.
Also verified against the real SPEC-001 spec file and this repository's
real `repo_root` directly (ad hoc, not a committed test): the plan
correctly derives the same 4 default steps from the spec text with no
duplicate pytest step.

### Finding 4 (MAJOR) — the real isolated verification workspace could not complete the required verification plan

Two independent, unrelated real failures, each reproduced by actually
running the real verification sandbox against this repository before
being fixed:

**4a — nested sandbox-exec enforcement tests failed when run as a
verification step.** When PEOS verifies its own repository, `pytest -q`
(and therefore `tests/test_peos_sandbox.py::TestVerificationSandboxEnforcement`,
which itself invokes real `sandbox-exec`) runs *inside* the outer
verification sandbox. Reproduced: running that test class nested inside
`sandboxed_verification_command` produced `sandbox_apply: Operation not
permitted` on every nested `sandbox-exec` call. Verified empirically that
this is a genuine macOS Seatbelt platform limitation, not a flaw in this
module's profile: *any* active custom profile (even the most trivial
`(allow default)`) blocks a further `sandbox_apply`, regardless of its
rules — confirmed with a minimal probe outside this codebase before
concluding so. **Fix:** `tests/test_peos_sandbox.py` now runs a live
probe (`sandbox-exec -p '(version 1)(allow default)' /usr/bin/true`)
before deciding whether `TestVerificationSandboxEnforcement` can run;
when already nested, those tests are skipped with an explicit,
non-alarming reason rather than failing. The normal (non-nested) case is
unaffected — all 23 tests in that file still run for real in a direct
`pytest` invocation; verified by running the class alone both nested and
non-nested.

**4b — the frontend production build failed because `next/font/google`
needs network.** `app/layout.tsx` used `next/font/google` for IBM Plex
Sans/Mono, which fetches font CSS + `.woff2` files from
`fonts.googleapis.com`/`fonts.gstatic.com` at build time — denied by the
verification sandbox's `(deny network*)`. Reproduced: `npm run build`
inside the real sandbox failed with Next.js's own error message
recommending `next/font/local`. **This required a change under
`frontend/`** (a tracked source file plus new binary asset files), which
the remediation brief explicitly called for stopping and asking before
making — done via `AskUserQuestion`; the user chose "vendor fonts via
`next/font/local`." **Fix:** the exact IBM Plex Sans (confirmed via the
real Google Fonts CSS2 API response to be served as a single
variable-weight file across all 4 requested weights) and IBM Plex Mono
(3 separate static per-weight files) `.woff2` files were downloaded once
(real network, outside the sandbox) into `frontend/app/fonts/`;
`app/layout.tsx` now uses `next/font/local` against those vendored files
with the same `--font-plex-sans`/`--font-plex-mono` CSS variable names,
so `globals.css`'s `--font-sans`/`--font-mono` mapping — and the
rendered font/weights/visual output — is byte-for-byte identical to
before. No other frontend product behavior changed.

A second, unrelated real failure surfaced only after 4b's fix (not part
of the original two named gaps, found and fixed in the course of making
the build actually complete end-to-end): Turbopack's own internal worker
communicates over a 127.0.0.1 TCP loopback socket for IPC during CSS
processing, which `(deny network*)` also denied (`Operation not
permitted` binding a port). Verified this is loopback-only, never
leaving the machine, and distinct from the exfiltration risk the network
deny exists to prevent. **Fix:** `build_verification_sandbox_profile`
now allows `network-bind`/`network-inbound` on `(local ip "localhost:*")`
and `network-outbound` on `(remote ip "localhost:*")` only, verified live
that a genuine external destination (`1.1.1.1:443`) remains denied
(`tests/test_peos_sandbox.py::test_malicious_command_cannot_reach_the_network`,
unchanged, still passes) alongside a new positive test for the loopback
case (`test_benign_command_can_still_use_a_loopback_socket`).

**End-to-end evidence:** the real, full verification plan — `pytest -q`
(the entire repository test suite, including the nested sandbox tests
correctly self-skipping), `npm run lint`, `npm run typecheck`, `npm run
build` — was run through `peos.verification_plan.execute_plan` against a
real isolated workspace cloned from this actual repository, through the
real `sandbox-exec`-confined subprocess path, end to end: **all 4 steps
passed** (see "Verification commands and results" below for the full
transcript).

### Finding 5 — reporting/failure-safety residuals

Two independent gaps, both directly reproduced:

**5a — an unexpected exception lost already-accumulated evidence.**
`run_workflow`'s outer `try/except` lived *outside* `_run_workflow`'s
closures (`_base_kwargs`, `current_spec`, `claude_runs`,
`verification_reports`), so an exception raised after Phase 1/2 (spec
resolved, implementation completed) produced a bare, context-free
`RunResult(task=task, outcome="FAILED", ...)` with `spec=None`,
`claude_runs=()`. **Fix:** the broad `try/except` moved *inside*
`_run_workflow`, wrapping Phase 0 through the final return, so its
`except` clause can still call `_base_kwargs()` and preserve everything
accumulated so far. The outer `run_workflow` keeps a thin last-resort
fallback for the (now much narrower) case of a crash before that inner
handler is even active. Regression:
`tests/test_peos_workflow.py::test_unhandled_exception_after_implementation_still_carries_accumulated_evidence`
(a `codex_runner` that raises mid-run; asserts `result.spec`,
`result.claude_runs`, and `result.verification_reports` all survive).

**5b — invalid `--repo`/`--spec` input bypassed reporting entirely.**
`peos/cli.py::main`'s three early-exit paths (unresolvable `--repo`, not
a Git repo, invalid `--spec`) printed a bare `error: ...` line to stderr
and returned 1 *without ever calling `build_report`* — the opposite of
"every run ends with a report" (AC-012). Fixing this exposed two further
real bugs along the way, both reproduced directly:
- `peos/gitutil.py::_run_git` raised uncaught when `cwd=repo_root` did
  not exist (`subprocess.run` itself raises `FileNotFoundError`/`OSError`
  for a missing cwd, not a nonzero exit) — meaning even routing through
  `build_report` would have crashed for the unresolvable-`--repo` case.
- `Path.resolve()` on a path containing a NUL byte raises `ValueError`,
  not `OSError` — uncaught by the existing `except OSError`, so this
  specific invalid `--repo` value crashed with a full Python traceback
  out of `main()` (reproduced directly, traceback captured, before the
  fix). The same class of gap as the first pass's Finding 10
  (`UnicodeDecodeError` not being an `OSError` subclass).

**Fix:** all three `cli.py` early-exit paths now build a
`RunResult(outcome="FAILED", gate_reason=...)` and call `build_report`,
printing the full report to stdout (same shape as every other FAILED
outcome) instead of a bare stderr line; `gitutil.py::_run_git` now
catches `(OSError, ValueError)` around the subprocess call and degrades
to a formatted error string instead of raising; `cli.py`'s `--repo`
resolution now catches `(OSError, ValueError)`.

**Regression evidence:**
`tests/test_peos_cli.py::test_rejects_non_git_repo`,
`::test_rejects_spec_path_that_is_a_directory`,
`::test_rejects_missing_spec_path`,
`::test_rejects_spec_with_invalid_utf8_encoding_without_a_traceback`
(all updated to assert a full `"PEOS Run Report"` on stdout, not a bare
stderr substring) and the new
`::test_rejects_unresolvable_repo_path_with_a_full_report_not_a_bare_stderr_line`
(the exact NUL-byte reproduction).

### Third-pass verification commands and results

```
$ pytest -q
245 passed, 3 skipped in ~23s
```

PEOS test suite (by file), after this pass:

```
test_peos_claude_agent.py:        19 passed   (+2 regression tests)
test_peos_cli.py:                  10 passed   (+1 regression test; 4 existing tests updated to assert full report)
test_peos_codex_agent.py:          26 passed   (+4 regression tests)
test_peos_gitutil.py:               9 passed   (unchanged; _run_git hardening covered via cli.py tests)
test_peos_preflight.py:            10 passed
test_peos_real_cli_contract.py:     3 skipped  (opt-in; not re-run this pass -- no agent command-building logic changed, only local JSON validation)
test_peos_report.py:                9 passed
test_peos_sandbox.py:              23 passed   (+3 regression tests: nested-temp-root attack, benign-write companion, loopback socket)
test_peos_spec.py:                  8 passed
test_peos_verification_plan.py:    13 passed   (+4 regression tests: spec-declared command, tamper-resistance, dedup, unparseable-command fail-closed)
test_peos_verify.py:                6 passed
test_peos_workflow.py:             26 passed   (+1 regression test)
--------------------------------------------------------------------------
162 passed, 3 skipped (up from 150 passed, 3 skipped at the end of pass two)
```

### Real isolated verification plan — end to end, this pass

Run through `peos.verification_plan.resolve_verification_plan` +
`execute_plan` against a real isolated workspace (`peos.sandbox.create_isolated_workspace`)
cloned from this actual repository, through the real `sandbox-exec`-
confined subprocess path (not mocked, not a routing test):

```
Frozen plan: python tests (pytest -q), frontend lint, frontend typecheck, frontend build
PASS  python tests (pytest -q)   (exit 0)
PASS  frontend lint              (exit 0)
PASS  frontend typecheck         (exit 0)
PASS  frontend build             (exit 0)
OVERALL PASS: True
```

This is the first time in any remediation pass that the real frontend
build has been run end-to-end inside the actual verification sandbox
(previously it was only run directly against the authoritative checkout,
outside the sandbox — see pass two's "What was NOT done"). It was not run
through a full live `peos "<task>"` invocation (that would additionally
require real `claude`/`codex` subprocess calls, out of scope for this
stop-before-commit pass, same as passes one and two) — it was run through
the same `resolve_verification_plan`/`execute_plan` code path
`_run_workflow` actually calls, against a real clone of this repository.

### Frontend lint / typecheck / build — direct, outside the sandbox too

```
$ npm run lint       → clean, exit 0
$ npm run typecheck  → "✓ Types generated successfully", no errors
$ npm run build      → "✓ Compiled successfully", 2 static routes generated
```

Run directly against the authoritative `frontend/` checkout after the
`next/font/local` change, confirming product behavior (the build output)
is unaffected outside the sandbox too. `.next` was removed after the
check; `git status` confirms no stray output.

### Scope note: the one frontend/ change this pass

Per the remediation brief's explicit instruction ("stop and report before
making it"), the font fix was not applied silently. Before touching
anything under `frontend/`, the gap was reproduced live (see Finding 4b
above) and three options were presented via `AskUserQuestion`: (1) vendor
via `next/font/local`, (2) an orchestrator-only prefetch/mock mechanism
with zero `frontend/` changes, (3) document as an open limitation and
defer. The user chose (1). The resulting diff is:
`frontend/app/layout.tsx` (import source changed from `next/font/google`
to `next/font/local`; same CSS variable names, same weights) and four new
vendored `.woff2` files under `frontend/app/fonts/` (~60 KB total,
downloaded once from the real `fonts.gstatic.com` CDN, identical bytes to
what `next/font/google` was fetching at every unsandboxed build before
this pass). No simulation framework, product UI, or behavior changed —
confirmed by the unsandboxed build/lint/typecheck results above and by
visual parity (byte-identical font files; same weights; same CSS
variables consumed by the same `globals.css` rules).

## What changed in this (second) pass

### Finding 1 (BLOCKER) — verification bypassed the isolation boundary

**The gap, exactly as reproduced:** `peos/verify.py::run_command` ran
every verification command (`pytest -q`, `npm run lint/typecheck/build`)
as a plain `subprocess.run` with no `env=` argument (inheriting the
orchestrator's real environment, including whatever credentials happen
to be in it) and no filesystem/network confinement. Verification
executes whatever code is in the workspace at that point — including
files Claude (the untrusted implementation agent) just edited — so a
planted `conftest.py`, test file, or `package.json` script was an
unrestricted arbitrary-code-execution path. "Claude has no Bash" was
true and irrelevant: the vulnerability was in how *PEOS itself* ran
verification, not in what tool Claude was given.

**Architecture decision — made, not escalated.** Before concluding
whether this could be closed with "currently available local
mechanisms," I built and empirically tested a candidate boundary rather
than assuming one would or wouldn't work (commands and raw output
available on request; summarized here). The decision: **macOS Seatbelt
(`sandbox-exec`)**, with a profile scoped to exactly three properties,
each independently verified against both adversarial Python scripts and
this repository's real `pytest -q` / `npm run lint` / `npm run
typecheck` / `npm run build`:

1. `(deny network*)` — verification never needs network (dependencies
   are pre-provisioned, see Finding 7); this makes `git push`, a
   fetch, or any network exfiltration structurally impossible.
2. `(deny file-write* (subpath "/"))` with explicit allows for only the
   workspace directory, the isolated `home_dir`, and this process's own
   resolved temp directory — verified live to still let real `pytest`/
   `eslint`/`tsc`/`next build` run to completion (they only need to
   write inside their own cwd and OS temp dirs). The authoritative
   `repo_root` is never in this allow-list, so mutating it (including
   its `.git` objects) is structurally impossible.
3. `(deny file-read*)` on `repo_root/.git` specifically, plus a named
   list of real-$HOME credential paths (`CREDENTIAL_PATH_DENYLIST` in
   `peos/sandbox.py`: `.ssh`, `.netrc`, `.git-credentials`,
   `.config/gh`, `.aws`, `.docker/config.json`) — not a blanket
   filesystem read-deny, which would also break reading the
   orchestrator's own installed Python/Node toolchain (commonly under
   `repo_root/.venv`) that verification legitimately needs.

This is deliberately **not** claimed as a full OS sandbox: reads of the
rest of the real filesystem are not blocked, so a malicious script could
still read an arbitrary file and print it to stdout (a disclosure risk
visible in the PEOS report, not a covert one) — what it structurally
cannot do is mutate the authoritative repository, push, or reach the
network at all. `sandbox-exec` is Apple-deprecated; if unavailable
(any non-macOS host, or a future OS that removes it),
`sandboxed_verification_command` raises `SandboxUnavailableError` and
every verification step is recorded as a hard failure — PEOS never
falls back to running verification unconfined.

**Why this, and not something else:** a bespoke container/VM/namespace
would be more robust but is explicitly out of CLAUDE.md's Out-of-Scope
list (Docker/Kubernetes) and disproportionate to a local V1 tool; a
second unprivileged OS user account was considered and rejected as
needing `sudo`-level host setup that "the smallest maintainable local
orchestration solution" (SPEC-001 §16) does not justify. `sandbox-exec`
is the one mechanism already resident on the only platform this project
currently runs on, and it was proven — not assumed — to hold for the
real commands in this repository.

**Enforcement evidence (real, not mocked):**
`tests/test_peos_sandbox.py::TestVerificationSandboxEnforcement` runs
real `sandbox-exec`-wrapped Python subprocesses, against a repo rooted
outside the system temp directory (so the test cannot accidentally
exploit its own temp-dir allowance — see the class docstring for why
that distinction matters), proving:
- a malicious command cannot write to the authoritative repo
  (`test_malicious_command_cannot_write_to_the_authoritative_repo`),
- cannot read the authoritative `.git` directory
  (`test_malicious_command_cannot_read_authoritative_git_metadata`),
- cannot reach the network at all
  (`test_malicious_command_cannot_reach_the_network`),
- a benign command can still write inside the workspace
  (`test_benign_command_can_still_write_inside_the_workspace` — proves
  this is confinement, not a blanket deny that would make verification
  itself unusable),
- and a real OS denial (nonzero exit, "Operation not permitted") is
  distinguishable from a command that simply never tried
  (`test_sandbox_denial_is_distinguishable_from_a_command_simply_declining`).

Fail-closed behavior when the sandbox is unavailable is covered by
`tests/test_peos_verification_plan.py::test_execute_plan_fails_closed_when_sandbox_unavailable`
and `tests/test_peos_sandbox.py::test_sandboxed_verification_command_fails_closed_when_unavailable`.
`peos/verify.py::run_command` now threads `env=` through to the
subprocess (previously silently dropped); `peos/verification_plan.py::execute_plan`
builds every command through the sandbox wrapper and runs it with
`peos.sandbox.sandboxed_env`.

### Finding 2 (MAJOR) — strict local parsing still incomplete

Three concrete gaps, each independently reproduced and now a named
regression test:

1. **"Claude COMPLETED accepted with missing required gate fields"** →
   a `HUMAN_GATE` with a missing/invalid `gate_category` was previously
   silently coerced to `None` and accepted. Now rejected
   (`peos/claude_agent.py::run_claude`;
   `tests/test_peos_claude_agent.py::test_run_claude_human_gate_without_category_fails_closed`,
   `::test_run_claude_human_gate_with_invalid_category_fails_closed`).
2. **"Claude COMPLETED accepted alongside gate_category='physics' and a
   gate reason"** → `status` and the gate fields are now required to be
   internally consistent: `COMPLETED`/`FAILED` must have
   `gate_category=None` and `gate_reason=None`, or the result is
   rejected as uninterpretable
   (`tests/test_peos_claude_agent.py::test_run_claude_completed_with_populated_gate_fields_is_rejected_as_inconsistent`,
   `::test_run_claude_failed_with_populated_gate_fields_is_rejected_as_inconsistent`).
3. **"Codex APPROVE accepted without required acceptance_criteria"** →
   an `APPROVE` verdict with `acceptance_criteria=null` or `[]` is now
   rejected; null remains valid only for `CHANGES_REQUIRED` (a
   specification may legitimately define zero ACs, but cannot be
   APPROVEd through this path without evidence)
   (`peos/codex_agent.py::_validate_review_payload`;
   `tests/test_peos_codex_agent.py::test_approve_without_acceptance_criteria_is_rejected`,
   `::test_approve_with_empty_acceptance_criteria_list_is_rejected`,
   `::test_changes_required_without_acceptance_criteria_is_still_accepted`).

### Finding 3 (MAJOR) — reviewer isolation/fingerprint incomplete

- **Content mutation of already-dirty/already-untracked files.**
  `peos/gitutil.py::repo_state_fingerprint` previously hashed `git
  status --porcelain` + `git diff --name-status` + untracked *names*.
  A file already "M" (or already untracked) before a Codex phase began
  would show the identical status/name list after a *further* edit,
  masking it. Rewritten to hash the full `git diff HEAD --binary` text
  (content, not names) plus a per-file content hash of every untracked
  file. Directly reproduced and now regression-tested:
  `tests/test_peos_gitutil.py::test_repo_state_fingerprint_detects_a_further_edit_to_an_already_dirty_tracked_file`,
  `::test_repo_state_fingerprint_detects_a_further_edit_to_an_already_untracked_file`.
- **Applied to the workspace, not only the authoritative repo.**
  `peos/workflow.py::_codex_phase` now fingerprints *both* `repo_root`
  and `workspace.path` before/after every Codex call — Codex must not
  modify either, and a workspace-only mutation (repo_root untouched) now
  also fails closed:
  `tests/test_peos_workflow.py::test_codex_mutating_the_isolated_workspace_itself_fails_closed`.
- **Inherited Codex MCP/configured external capabilities.**
  `build_codex_command` now passes `--ignore-user-config` (skips loading
  `$CODEX_HOME/config.toml`, where MCP servers are configured; auth
  still works per `codex exec --help`) and `--ignore-rules` (skips any
  user/project execpolicy `.rules` file a workspace file could plant).
  Verified live against the installed CLI (`codex-cli 0.162.1`) not to
  break the real contract invocation — see "Real CLI contract tests"
  below.
- **Overclaiming `--sandbox read-only`.** Docstrings and
  `KNOWN_LIMITATIONS` now state precisely what was verified (one write
  attempt denied) versus what was not independently characterized
  (e.g. its network policy for shell commands), and name the
  fingerprint comparison as the property that does not depend on
  characterizing every detail of that mode.
- **Distinguishing denial from declining.** Already true for Codex
  (fingerprint-based, agent-claim-independent); the same distinction is
  now also tested for the verification sandbox:
  `test_sandbox_denial_is_distinguishable_from_a_command_simply_declining`
  (above).

### Finding 4 (MAJOR) — governance-artifact integrity ended too early

- **Re-checked after verification, before review/approval.**
  `peos/workflow.py::_run_workflow` now calls `_check_governance_mutation`
  a second time after each local-verification run (not only right after
  each Claude phase), before Codex is ever invoked:
  `tests/test_peos_workflow.py::test_governance_mutation_detected_after_verification_not_just_after_claude`.
- **Governing spec covered even when supplied explicitly/outside normal
  discovery.** `peos/preflight.py::hash_governance_artifacts` previously
  silently dropped the spec from hashing entirely if it could not be
  expressed relative to `repo_root` (an explicit `--spec` pointing
  outside the repo). It now takes an explicit `spec_workspace_rel` key
  (computed once by `peos.sandbox.ensure_spec_in_workspace`, which also
  fixes Finding 6 — see below), so an externally-supplied spec is hashed
  and mutation-checked exactly like a discovered one:
  `tests/test_peos_preflight.py::test_hash_governance_artifacts_uses_the_given_workspace_relative_key_even_outside_repo`.
- **Fails closed.** Unchanged in spirit, now exercised against the new
  code path by the above tests.

### Finding 5 (MAJOR) — verification plan not truly frozen/spec-specific

Command *strings* were frozen (Finding 8, first pass), but their
*meaning* was not: an implementation agent could rewrite
`frontend/package.json`'s `scripts.build` into `"true"` after the plan
was frozen, and `npm run build` would then just run `true` and exit 0 —
silently satisfying verification without building anything.

`peos/verification_plan.py::resolve_verification_plan` now also snapshots
each npm-script-backed step's literal `scripts.<key>` string value from
`repo_root`'s `frontend/package.json` when the plan is frozen.
`execute_plan` re-reads that same key from the *workspace's*
`package.json` immediately before running the step; a mismatch is a hard
failure (`ran=False`), and the real (possibly redefined) script is never
executed. Directly reproduced and regression-tested:
`tests/test_peos_verification_plan.py::test_npm_script_redefinition_to_a_no_op_fails_closed`
(also proves the redefined script is never actually run, and that an
unrelated step — `lint`/`typecheck`, whose script string didn't change —
is unaffected).

### Finding 6 (MAJOR) — governing spec path wrong inside the workspace

Prompts previously referenced `spec_path = str(resolution.spec.path)` —
the **authoritative repository's absolute path** — while Claude runs
with `cwd=workspace.path` and `--restricted` (file tools confined to
that cwd) and Codex also runs with `cwd=workspace.path`. Neither agent
could reliably resolve that absolute path from inside the workspace.

`peos/sandbox.py::ensure_spec_in_workspace` now guarantees the spec is
readable at a path *relative to the workspace*: for a spec inside
`repo_root` (the normal case), it returns the identical relative path
(already carried over by the clone) and copies it in defensively if, for
any reason, it is not already there; for a spec supplied via `--spec`
*outside* `repo_root`, it copies the file into
`workspace/.peos/governing-spec/<name>` and returns that relative path.
`peos/workflow.py` now builds every prompt with this relative path, not
the absolute one. Regression-tested:
`tests/test_peos_sandbox.py::TestEnsureSpecInWorkspace` (both branches,
real filesystem operations), and end-to-end through the real workflow
control flow with a workspace factory that uses a genuinely different
directory from `repo_root`:
`tests/test_peos_workflow.py::test_approved_run_spec_path_in_prompts_is_workspace_relative_not_absolute`
(asserts the authoritative absolute path does **not** appear in the
prompt and the relative path does).

### Finding 7 (MAJOR) — disposable frontend workspace lacks dependencies

The isolated workspace is a fresh `git clone`; `frontend/node_modules`
is gitignored, so the clone alone never carried it over — frontend
verification inside the workspace was not actually runnable at all
before this pass (confirmed empirically: a bare `npm run lint` with no
`node_modules` fails immediately). Since the verification sandbox (above)
denies network, `npm install` cannot be used as an in-sandbox fallback.

`peos/sandbox.py::create_isolated_workspace` now explicitly copies
`repo_root/frontend/node_modules` into the workspace once, at
workspace-creation time — a deliberate, named provisioning step, not an
accidental reuse of the authoritative checkout. Python verification
instead reuses the orchestrator's own installed interpreter/
site-packages by path (`sys.executable`, typically under
`repo_root/.venv`), read-only, from inside the sandboxed subprocess —
which is why the verification sandbox's read-deny is scoped to
`repo_root/.git` specifically rather than all of `repo_root` (denying
all of it would also break importing the toolchain that lives there).
The trust assumption either way: dependencies are taken as of run start
and never updated by PEOS. If `frontend/node_modules` is absent, that is
now a named, explicit required-input check (`VerificationStep.
extra_required_inputs`), not a cryptic native npm failure: frontend
verification fails closed with a message that names the missing path.

Regression-tested: `tests/test_peos_sandbox.py::test_create_isolated_workspace_provisions_frontend_node_modules`,
`::test_create_isolated_workspace_skips_node_modules_copy_when_absent`;
`tests/test_peos_verification_plan.py::test_frontend_step_requires_node_modules_even_if_package_json_present`.
Live confirmation that the real toolchain runs correctly under the real
sandbox with dependencies provisioned this way: the `sandbox-exec`
re-validation against this repository's actual `frontend/node_modules`
(446 MB) during development of this fix — `npm run lint`/`typecheck`/
`build` all passed clean under the candidate profile before it was
adopted (ad hoc verification during this remediation; the committed,
repeatable enforcement tests are the ones listed above and run against
synthetic fixtures for speed).

### Finding 8 (MAJOR) — reconciliation failure could still APPROVE

`approve()` in `peos/workflow.py` called `_reconcile()`, and `_reconcile()`
swallowed any copy-back exception into a bare `log(...)` + `return None,
()` — `approve()` then unconditionally returned `outcome="APPROVED"`
regardless of whether reconciliation actually succeeded. A reconciliation
failure is now surfaced as a distinct `(result, blocked, error)` tuple;
`approve()` checks `error` and returns `outcome="FAILED"` instead (never
silently building the `FAILED` result via a second `_reconcile()` call —
it reuses the outcome already computed, so a partially-completed
reconciliation is never attempted twice). `gate()`/`fail()` still surface
a reconciliation error (`RunResult.reconciliation_error`, shown in the
report) without changing their own (already-not-approved) outcome.

Regression-tested with a real monkeypatched `reconcile_workspace_to_repo`
that raises mid-copy:
`tests/test_peos_workflow.py::test_reconciliation_failure_never_produces_approved`
(asserts `outcome == "FAILED"`, not `"APPROVED"`, even though Codex
returned `APPROVE`) and
`::test_reconciliation_failure_during_a_gate_is_reported_but_keeps_the_gate_outcome`.

### Finding 9 (MINOR) — final report still lost evidence

- **Spec on every terminal outcome.** `gate()`/`fail()` built their
  `RunResult` from `_base_kwargs()`, which never included `spec=...` —
  only `approve()` did. A `FAILED`/`HUMAN_GATE` outcome reached *after*
  Phase 1 (spec resolved) silently reported `spec=None`. Fixed by
  hoisting `current_spec` and including it in `_base_kwargs()`
  unconditionally. Regression-tested through the *real* workflow control
  flow (not a manually constructed `RunResult`), per the finding's own
  instruction:
  `tests/test_peos_workflow.py::test_failed_outcome_still_carries_the_resolved_spec`,
  `::test_human_gate_outcome_still_carries_the_resolved_spec`.
- **Reconciliation errors.** New `RunResult.reconciliation_error` field
  (Finding 8), surfaced in a dedicated report section explaining *why*
  an outcome might not be `APPROVED` even though Codex approved:
  `peos/report.py`; `tests/test_peos_report.py::test_report_surfaces_reconciliation_error`.
- **Untracked changed files** were already included (`git_untracked_files`
  in the "Changed files" section) — unchanged from the first pass, kept.
- **Verification sandbox-unavailable / npm-script-tamper errors surfaced
  as task-specific limitations**, not only the narrower "required input
  missing" substring match from the first pass:
  `peos/report.py::_task_specific_limitations` now flags any `ran=False`
  verification failure;
  `tests/test_peos_report.py::test_report_surfaces_unavailable_sandbox_as_a_task_specific_limitation`.

### Finding 10 (MINOR) — CLI/input failures still bypassed reporting

`peos/cli.py::_canonicalize_spec` caught `OSError` around
`candidate.read_text(encoding="utf-8")`, but `UnicodeDecodeError` is
**not** an `OSError` subclass — an invalid-encoding `--spec` file raised
uncaught, escaping as a Python traceback instead of a clean `error: ...`
message and exit code 1. Fixed by catching
`(OSError, UnicodeDecodeError)`. Directly reproduced and
regression-tested: `tests/test_peos_cli.py::test_rejects_spec_with_invalid_utf8_encoding_without_a_traceback`.
Directory/missing/unreadable-file cases were already handled correctly
(unchanged, still covered by the pre-existing tests in that file).

### Finding 11 — this document

Corrected to match demonstrated evidence (see the AC and finding tables
below), with evidence categories explicitly separated, and no claim of a
live end-to-end `peos "<task>"` run (none was performed in either
remediation pass — see "Remaining limitations").

## Verification commands and results

### Full repository Python test suite

```
$ pytest -q
230 passed, 3 skipped, 1 warning in ~19s
```

The single warning is the pre-existing `StarletteDeprecationWarning`
from `fastapi.testclient`, unrelated to this work.

### PEOS test suite (by file)

```
tests/test_peos_claude_agent.py:        17 passed
tests/test_peos_cli.py:                  9 passed
tests/test_peos_codex_agent.py:         22 passed
tests/test_peos_gitutil.py:              9 passed
tests/test_peos_preflight.py:           10 passed
tests/test_peos_real_cli_contract.py:    3 skipped (opt-in; re-run live for this pass, see below)
tests/test_peos_report.py:               9 passed
tests/test_peos_sandbox.py:             20 passed  (includes real sandbox-exec enforcement tests)
tests/test_peos_spec.py:                 8 passed
tests/test_peos_verification_plan.py:    9 passed
tests/test_peos_verify.py:               6 passed
tests/test_peos_workflow.py:            25 passed
------------------------------------------------------
147 passed, 3 skipped
```

### Real CLI contract tests (opt-in; re-run live for this pass)

```
$ PEOS_REAL_CLI_TESTS=1 pytest tests/test_peos_real_cli_contract.py -v
tests/test_peos_real_cli_contract.py::test_claude_restricted_mode_has_no_shell_and_confines_file_tools PASSED
tests/test_peos_real_cli_contract.py::test_claude_json_schema_produces_matching_structured_output PASSED
tests/test_peos_real_cli_contract.py::test_codex_read_only_sandbox_rejects_a_write PASSED
3 passed in 31.56s
```

Re-run specifically to confirm this pass's new Codex command-line flags
(`--ignore-user-config`, `--ignore-rules`) do not break the real `codex
exec` invocation, and that the unchanged parts of the contract still
hold. Installed CLI versions: `claude --version` → `2.1.296 (Claude
Code)`; `codex --version` → `codex-cli 0.162.1`.

### Isolated enforcement tests (real Git, real filesystem, real sandbox-exec)

Already included in the full-suite numbers above (not a separate run),
called out here because they are the category of evidence Finding 9
(first pass) and this pass's Finding 1 specifically ask for:
`tests/test_peos_sandbox.py` (real local Git clones, real `shutil`
filesystem operations, and — platform-gated to macOS —
`TestVerificationSandboxEnforcement`'s real `sandbox-exec` subprocess
invocations against adversarial Python scripts). On this development
machine (macOS 26.6.2, Darwin) these ran for real, unskipped.

### Frontend lint / typecheck / build

```
$ npm run lint       → clean, exit 0
$ npm run typecheck  → "✓ Types generated successfully", no errors
$ npm run build      → "✓ Compiled successfully", 2 static routes generated
```

Run directly against the authoritative `frontend/` checkout (not inside
a PEOS-created isolated workspace — no `peos "<task>"` run was
performed; see "Remaining limitations"). The `.next` build artifact was
removed after the check; `git status` below confirms no stray output.

### Repository diff review (scope check)

```
$ git status --porcelain=v1
 M docs/specifications/SPEC-001-peos-automation-v1.md   (pre-existing: Draft -> Approved, unchanged by this pass)
?? bin/
?? peos/
?? tests/_peos_fixtures.py
?? tests/test_peos_*.py (11 files)
?? docs/validation/SPEC-001-validation.md               (this file)
```

No file under `src/`, `backend/`, `frontend/` (other than running its
own lint/typecheck/build, which modifies no tracked source), `scenarios/`,
`config/`, or `.github/workflows/ci.yml` was touched.

### What was NOT done (named explicitly, per the remediation brief)

- **No live end-to-end `peos "<task>"` run.** That would recursively
  invoke this not-yet-committed orchestrator through real `claude`/
  `codex` subprocesses, including a real isolated-workspace clone of
  this 400+ MB-with-node_modules repository and a real
  `sandbox-exec`-confined `npm run build`. This remains out of scope for
  a stop-before-commit remediation pass, as it was for the first pass.
  Evidence for each claim instead comes from the four categories below,
  each named per finding/test rather than asserted in the aggregate.
- No commit, push, merge, or tag was made or attempted.

## Evidence taxonomy (what backs each claim)

1. **Mocked workflow-routing** (`tests/test_peos_workflow.py`): Claude,
   Codex, the workspace factory, and the verifier are injected fakes.
   Proves phase sequencing, gating, and the bounded remediation cycle —
   never shells out to `claude`, `codex`, or performs a real clone.
2. **Isolated enforcement** (`tests/test_peos_sandbox.py`,
   `tests/test_peos_preflight.py`, `tests/test_peos_verification_plan.py`,
   `tests/test_peos_gitutil.py`): real local Git repositories, real
   filesystem operations, and — platform-gated — real `sandbox-exec`
   subprocess invocations against adversarial scripts. No real
   `claude`/`codex` call.
3. **Adversarial parsing** (`tests/test_peos_claude_agent.py`,
   `tests/test_peos_codex_agent.py`): construct the exact malformed/
   contradictory payload and assert fail-closed behavior. No subprocess
   call at all (a fake `runner` writes the payload directly).
4. **Real CLI contract** (`tests/test_peos_real_cli_contract.py`,
   opt-in, costs real API calls): the actual installed `claude`/`codex`
   binaries, invoked with the exact command this module builds, against
   a scratch repo. Re-run live for this pass (see above).
5. **Live end-to-end** (`peos "<task>"` actually run): **not performed**
   in either remediation pass — named here, not silently absent.

## AC-001 – AC-014 assessment (updated after the third pass)

| AC | Status | Evidence |
|----|--------|----------|
| AC-001 Single Entry Point | **MET** (unchanged) | `bin/peos` → `peos.cli.main`; `tests/test_peos_cli.py` |
| AC-002 Specification Enforcement | **MET** (unchanged logic; spec now also guaranteed reachable inside the workspace, Finding 6) | `peos/spec.py`; `peos/sandbox.py::ensure_spec_in_workspace`; `tests/test_peos_spec.py`, `tests/test_peos_sandbox.py::TestEnsureSpecInWorkspace` |
| AC-003 Claude Implementation | **MET**, strengthened again (third-pass Finding 2: gate_reason type coercion, additionalProperties; fourth-pass Finding A: missing-key presence now distinguished from explicit null for `gate_category`/`gate_reason`) | `peos/claude_agent.py::run_claude`; `tests/test_peos_claude_agent.py`; real contract test (not re-run this pass — no command-building change) |
| AC-004 Deterministic Verification | **MET**, strengthened again (third-pass Findings 1, 3, 4 — real end-to-end plan now actually passes, including the real frontend build inside the sandbox for the first time) | `peos/verification_plan.py` (spec-declared commands); `peos/sandbox.py` (repo_root re-deny, loopback exception); `tests/test_peos_verification_plan.py`, `tests/test_peos_sandbox.py::TestVerificationSandboxEnforcement`; real end-to-end run in "Third remediation pass" above |
| AC-005 Independent Codex Review | **MET**, strengthened again (third-pass Finding 2: AC note type coercion, additionalProperties; fourth-pass Finding A: missing-key presence now distinguished from explicit null for the top-level payload, each finding, and each acceptance-criterion's `note`) | `peos/codex_agent.py`; `peos/gitutil.py::repo_state_fingerprint`; `tests/test_peos_codex_agent.py`, `tests/test_peos_gitutil.py`; real contract test (not re-run this pass) |
| AC-006 Remediation Routing | **MET** (unchanged) | `peos/workflow.py` Phase 4; `tests/test_peos_workflow.py::test_remediation_cycle_then_approve` |
| AC-007 Re-review | **MET** (unchanged) | `peos/workflow.py` Phase 5; same test file |
| AC-008 Loop Bound | **MET** (unchanged) | `tests/test_peos_workflow.py::test_bounded_remediation_still_changes_required_gates` |
| AC-009 Human Escalation | **MET**, strengthened (Finding 2 consistency) | `tests/test_peos_workflow.py::test_claude_human_gate_during_implementation_maps_gate_category` and related |
| AC-010 Git Safety | **MET within a now-further-demonstrated boundary** (third-pass Finding 1 BLOCKER resolved: repo_root-under-temp-directory attack) | Verification sandbox + isolated workspace; `tests/test_peos_sandbox.py::TestVerificationSandboxEnforcement` (real, adversarial, now including the temp-root attack); see "Remaining limitations" for the precise residual scope |
| AC-011 Failure Safety | **MET**, strengthened again (third-pass Finding 5: exceptions preserve accumulated evidence; invalid --repo/--spec now report instead of bypassing; `Path.resolve()` ValueError and `_run_git`'s OSError/ValueError both now caught. Fourth-pass Finding B: the same `--repo`-only `ValueError` fix is now also applied to `--spec`'s own `.resolve()` call in `_canonicalize_spec`, which had an identical gap) | `tests/test_peos_workflow.py::test_unhandled_exception_after_implementation_still_carries_accumulated_evidence`; `tests/test_peos_cli.py` (updated + NUL-byte tests for both `--repo` and `--spec`) |
| AC-012 Final Report | **MET**, strengthened again (third-pass Finding 5b: every invalid-input path now produces the report, not a bare stderr line) | `peos/report.py`, `peos/cli.py::_report_input_failure`; `tests/test_peos_report.py`, `tests/test_peos_cli.py` |
| AC-013 Existing Product Preservation | **MET**, with one disclosed exception: `frontend/app/layout.tsx`'s font import source changed from `next/font/google` to `next/font/local` (Finding 4b), approved by the user via `AskUserQuestion` before being made. No simulation/API/Scenario A behavior changed; the rendered font, weights, and CSS variables are unchanged (confirmed by direct unsandboxed `npm run build`/lint/typecheck). Full suite 245 passed, 3 skipped. | See "Scope note: the one frontend/ change this pass" above |
| AC-014 Existing CI Preservation | **MET** | `.github/workflows/ci.yml` not touched; frontend lint/typecheck/build all clean, including inside the real verification sandbox this pass |

## 11-finding remediation matrix (this pass)

| # | Severity | Finding | Status | Evidence |
|---|----------|---------|--------|----------|
| 1 | BLOCKER | Verification bypassed the isolation boundary | **RESOLVED** | `peos/sandbox.py` (`build_verification_sandbox_profile`, `sandboxed_verification_command`); `peos/verification_plan.py::execute_plan`; `peos/verify.py::run_command` now threads `env`; `tests/test_peos_sandbox.py::TestVerificationSandboxEnforcement` (real, adversarial), `tests/test_peos_verification_plan.py::test_execute_plan_fails_closed_when_sandbox_unavailable` |
| 2 | MAJOR | Strict local parsing still incomplete | **RESOLVED** | `peos/claude_agent.py::run_claude` (status/gate consistency); `peos/codex_agent.py::_validate_review_payload` (APPROVE requires AC evidence); regression tests named per reproduced case above |
| 3 | MAJOR | Reviewer isolation/fingerprint incomplete | **RESOLVED** | `peos/gitutil.py::repo_state_fingerprint` (content-based); `peos/workflow.py::_codex_phase` (workspace + repo_root both fingerprinted); `peos/codex_agent.py::build_codex_command` (`--ignore-user-config`/`--ignore-rules`); tests named above |
| 4 | MAJOR | Governance-artifact integrity ended too early | **RESOLVED** | `peos/workflow.py` (post-verification re-check); `peos/preflight.py::hash_governance_artifacts` (explicit workspace-relative key); tests named above |
| 5 | MAJOR | Verification plan not truly frozen/spec-specific | **RESOLVED** | `peos/verification_plan.py` (frozen npm-script snapshot + re-check); `tests/test_peos_verification_plan.py::test_npm_script_redefinition_to_a_no_op_fails_closed` |
| 6 | MAJOR | Governing spec path wrong inside the workspace | **RESOLVED** | `peos/sandbox.py::ensure_spec_in_workspace`; `peos/workflow.py` (prompts use the relative path); tests named above |
| 7 | MAJOR | Disposable frontend workspace lacks dependencies | **RESOLVED** | `peos/sandbox.py::create_isolated_workspace` (node_modules provisioning); `peos/verification_plan.py` (`extra_required_inputs`); tests named above |
| 8 | MAJOR | Reconciliation failure could still APPROVE | **RESOLVED** | `peos/workflow.py::approve()` (checks reconciliation error, never returns APPROVED on one); `tests/test_peos_workflow.py::test_reconciliation_failure_never_produces_approved` |
| 9 | MINOR | Final report still lost evidence | **RESOLVED** | `peos/workflow.py` (`current_spec` in `_base_kwargs`); `RunResult.reconciliation_error`; `peos/report.py`; tests named above (exercised through the real workflow, not manually injected) |
| 10 | MINOR | CLI/input failures still bypassed reporting | **RESOLVED** | `peos/cli.py::_canonicalize_spec` (catches `UnicodeDecodeError`); `tests/test_peos_cli.py::test_rejects_spec_with_invalid_utf8_encoding_without_a_traceback` |
| 11 | — | Validation record overclaimed closure | **RESOLVED** | This document: evidence categories separated, AC/finding tables updated, no live-E2E claim made |

**None of the above is marked resolved on the strength of prompt wording
alone.** Finding 1 and parts of Finding 3/7 are backed by real
`sandbox-exec`/Git subprocess behavior actually observed (adversarial
scripts genuinely denied, real dependencies actually copied and used by
real `npm`/`pytest` runs during development). Findings 2, 4, 5, 6, 8, 9,
10 are backed by unit/integration tests that construct the exact
reproduced input and assert the code's behavior, several of them through
the real `_run_workflow` control path rather than a hand-built
`RunResult`. Prompt text in `peos/prompts.py` continues to exist only to
help a well-behaved agent produce a sensible structured result — it is
never the enforcement mechanism for any of the above.

## Third-pass finding matrix

| # | Severity | Finding | Status | Evidence |
|---|----------|---------|--------|----------|
| 1 | BLOCKER | Verification sandbox permits mutation of repo_root when it is under an allowed temp directory | **RESOLVED** | `peos/sandbox.py::build_verification_sandbox_profile` (explicit post-allow repo_root re-deny); `tests/test_peos_sandbox.py::test_malicious_command_cannot_write_to_a_repo_root_nested_under_an_allowed_temp_directory` (real, adversarial, reproduced before the fix) |
| 2 | MAJOR | Claude/Codex local structured-result validation still accepted schema-invalid payloads | **RESOLVED** | `peos/claude_agent.py::run_claude` (gate_reason type check before coercion, additionalProperties); `peos/codex_agent.py` (`_validate_acceptance_criteria` note type check, additionalProperties at every level); 6 new regression tests across both agent test files, each the exact reproduced malformed payload |
| 3 | MAJOR | Verification plan did not incorporate governing-spec-specific verification requirements | **RESOLVED** | `peos/verification_plan.py` (`_parse_spec_verification_commands`, `resolve_verification_plan(..., spec_path)`, `VerificationStep.parse_error`); 4 new regression tests, plus ad hoc verification against the real SPEC-001 spec/repo_root |
| 4 | MAJOR | Real isolated verification workspace could not complete the required plan (nested sandbox-exec; next/font network access; discovered loopback-socket denial) | **RESOLVED** | `tests/test_peos_sandbox.py` (live nested-sandbox-exec probe); `frontend/app/layout.tsx` + `frontend/app/fonts/` (vendored `next/font/local`, user-approved); `peos/sandbox.py` (loopback-only network exception); real end-to-end plan run: all 4 steps PASS |
| 5 | — | Reporting/failure-safety residuals (exception evidence loss; invalid-input reporting bypass; two further latent exception-type bugs found while fixing it) | **RESOLVED** | `peos/workflow.py` (inner try/except with `_base_kwargs()`); `peos/cli.py::_report_input_failure`; `peos/gitutil.py::_run_git` ((OSError, ValueError)); `peos/cli.py` repo-resolve ((OSError, ValueError)); regression tests in `test_peos_workflow.py` and `test_peos_cli.py` |

Every row above is backed by a reproduction of the actual gap against the
pre-fix code (shown succeeding/failing as described) followed by the
same scenario re-run against the fix (shown no longer succeeding/
failing), not merely a new test written against already-fixed code.

## Remaining limitations (stated precisely, not overclaimed)

1. **The verification sandbox is macOS-only.** It depends on
   `sandbox-exec`, which is Apple-deprecated and specific to this
   platform. On any other OS, or if a future macOS release removes it,
   `sandboxed_verification_command` fails closed — verification does
   not run, rather than running unconfined. Re-verifying this boundary
   after any Codex/Claude/macOS update is a single command:
   `pytest tests/test_peos_sandbox.py -k TestVerificationSandboxEnforcement`.
2. **The verification sandbox does not block all reads.** Only
   `repo_root/.git` and a named list of real-$HOME credential paths are
   read-denied; the rest of the real filesystem remains readable to a
   verification subprocess. A malicious script could still read and
   print an arbitrary file to stdout — visible in the PEOS report a
   human will read, not a covert exfiltration channel, but not nothing.
   What it cannot do, verified adversarially, is mutate the
   authoritative repository, push, or reach the network at all.
3. **Claude/Codex's own sandboxes (`--restricted`, `--sandbox
   read-only`) are not full OS sandboxes either** — unchanged from the
   first pass. The structural backstop that does not depend on
   characterizing every property of either is the before/after
   content-based fingerprint of both the authoritative repository and
   the isolated workspace around every Codex phase.
4. **Codex repo-state fingerprinting is Git-visible state only** (now
   content-based, not merely names/status, but still bounded by what
   Git tracks — `.gitignore`d files are invisible to it either way).
5. **Human-owned-decision detection is still self-reported** by Claude
   (`status=HUMAN_GATE`) and Codex (`requires_human_decision`); PEOS
   validates well-formedness and internal consistency, not engineering
   correctness.
6. **No live end-to-end `peos "<task>"` run was performed** in either
   remediation pass (see above) — only mocked routing, isolated
   enforcement (including real adversarial `sandbox-exec` tests), real
   (minimal) CLI contract invocations, and ad hoc manual verification of
   the sandbox profile against this repository's actual dependencies
   during development of Finding 7's fix.
7. **The pre-existing governing-specification auto-detection heuristic**
   (keyword overlap, not NLU) is unchanged from the original
   implementation.
8. **Dependency provisioning is a snapshot, not a sync.**
   `frontend/node_modules` is copied once per run from the authoritative
   checkout; if it is stale or missing relative to `package.json`/
   `package-lock.json`, verification will reflect that staleness (or
   fail closed if entirely absent) rather than PEOS reconciling it.
9. **The spec-specific verification parser (third pass, Finding 3) is a
   narrow text convention, not a general one.** It only recognizes a line
   indented ≥4 spaces/a tab inside a heading section whose text contains
   "Verification"; a spec author who formats a required command any other
   way (fenced code block, inline code span, prose) will not have it
   picked up. This is deliberate (explicitly not an open-ended
   AI-generated verification system per the remediation brief) but is a
   real authoring constraint, not a general-purpose spec parser.
10. **The verification sandbox's network exception is now loopback-only,
    not zero-network** (third pass, Finding 4). `127.0.0.1`/`localhost`
    bind/connect is permitted (needed for Turbopack's internal IPC);
    verified adversarially that a genuine external destination remains
    denied, but this is a narrower claim than "no network operations of
    any kind succeed" — a malicious script could still use a loopback
    socket for local (same-machine) inter-process signaling, which never
    leaves the machine and so cannot exfiltrate or push.
11. **The vendored font files (third pass, Finding 4b) are a one-time
    snapshot, not synced to Google Fonts.** If IBM Plex Sans/Mono's
    hosted files are ever updated upstream (a new version, a security
    fix to the format), `frontend/app/fonts/*.woff2` will not pick that
    up automatically; refreshing them is a manual re-download, the same
    trust model as `frontend/node_modules` provisioning above.

## Any human decision required

**One, already made this pass.** The third pass's Finding 4b (frontend
build needs network for `next/font/google`) required touching a tracked
`frontend/` file, which the remediation brief explicitly flagged as
needing sign-off first. This was surfaced via `AskUserQuestion` with
three concrete options (vendor via `next/font/local`; an
orchestrator-only prefetch mechanism with zero `frontend/` changes;
document as an open limitation) before any `frontend/` file was touched;
the user chose "vendor via `next/font/local`," which was then
implemented exactly as described. No other change in this pass required
a human decision: the third pass's BLOCKER (Finding 1) and the nested-
sandbox/loopback-network fixes (Finding 4a and the Turbopack discovery)
were resolved using mechanisms already resident on this platform
(`sandbox-exec` profile rules), validated empirically against real
adversarial scripts and this repository's real verification commands,
within SPEC-001 §16's permitted primitives and CLAUDE.md's Out-of-Scope
constraints. No change to SPEC-001's text, assumptions, or acceptance
criteria was necessary. The platform dependency (macOS-only) and the
precise read/write/network scope of the sandbox remain documented above
as a judgment call available for the Human Engineering Lead to revisit,
not an open architectural question.

## Git status / diff summary at the end of this (fourth) remediation pass

Unchanged in shape from the end of the third pass (reproduced below as
it stood at the end of the third pass; no file has moved from untracked
to tracked, and nothing has been staged or committed in this fourth pass
either — `peos/claude_agent.py`, `peos/codex_agent.py`, `peos/cli.py`,
and the three touched test files are edits to already-untracked new
files, so they do not change `git status`'s output shape at all):

```
 M docs/specifications/SPEC-001-peos-automation-v1.md  (pre-existing, unchanged by this pass: Draft -> Approved)
 M frontend/app/layout.tsx                              (Finding 4b, user-approved: next/font/google -> next/font/local)
?? bin/peos
?? peos/ (13 modules: __init__, cli, claude_agent, codex_agent, gitutil,
          preflight, prompts, report, sandbox, spec, verification_plan,
          verify, workflow)
?? frontend/app/fonts/ (4 vendored .woff2 files, ~60 KB total, Finding 4b)
?? tests/_peos_fixtures.py
?? tests/test_peos_claude_agent.py
?? tests/test_peos_cli.py
?? tests/test_peos_codex_agent.py
?? tests/test_peos_gitutil.py
?? tests/test_peos_preflight.py
?? tests/test_peos_real_cli_contract.py
?? tests/test_peos_report.py
?? tests/test_peos_sandbox.py
?? tests/test_peos_spec.py
?? tests/test_peos_verification_plan.py
?? tests/test_peos_verify.py
?? tests/test_peos_workflow.py
?? docs/validation/SPEC-001-validation.md  (this file)
```

No file has been committed, staged for a commit, pushed, merged, or
tagged. No simulation (`src/`) or API (`backend/`) file was touched;
`.github/workflows/ci.yml` was not touched. The one `frontend/` change
(`app/layout.tsx`'s font import source, plus the new vendored font asset
files) was made only after explicit user approval via `AskUserQuestion`,
per the remediation brief's own "stop and report before making it"
instruction — see "Scope note: the one frontend/ change this pass" above.
No simulation physics, API behavior, or Scenario A behavior changed.
