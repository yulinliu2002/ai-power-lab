# SPEC-006 — PEOS Runtime Verification V1

**Status:** Approved
**Project:** AI Power Lab
**System:** PEOS Automation V2 (extends `peos/workflow.py`, `peos/sandbox.py`,
`peos/round_packet.py`, `peos/codex_agent.py`, `peos/report.py`,
`peos/verification_plan.py`-style spec parsing; adds `peos/runtime_plan.py`,
`peos/runtime_services.py`, `peos/runtime_browser.py`,
`peos/runtime_evidence.py`, `peos/runtime_catalog.py`)
**Version:** 0.5 (0.1 remediated against the Human Engineering Lead's
architecture review: all six originally-open decisions resolved; nine
additional normative hardening requirements, A–J, added; a dedicated
extension-points section for SPEC-001/SPEC-003/SPEC-004 added. 0.2
submitted for independent Codex architecture review and returned
`CHANGES_REQUIRED` with 11 major findings — see "Codex Architecture
Review — Round 1" below. 0.3 closed all 11 normatively, resubmitted, and
a focused Round 2 re-review confirmed 10 of 11 `CLOSED`, left Finding 9
`STILL_OUTSTANDING` (AC-041's wording still contradicted the required
CORS addition) plus one new `minor` finding (stale step-number
cross-references from the port-reservation reordering) — see "Codex
Architecture Review — Round 2" below. This text closed both, a Round 3
confirmation pass found one residual stale cross-reference the Round 2
fix had missed (3 occurrences still pointing at step 6 instead of step
7), and a Round 4 confirmation pass, after that was corrected, returned
`APPROVE` with zero outstanding findings, satisfying the independent
Codex architecture/specification review gate (§21).

0.4 was implemented under that approval. A subsequent independent Codex
*implementation* review (separate from the architecture-review rounds
above, and from the §21 gate they satisfy) ran four focused rounds against
the actual implementation and a real, live, Chromium-backed end-to-end
Runtime Verification run executed against this repository's own
frontend/backend: 11 implementation findings and 5 live-run findings
(frontend locator mismatches, a disclosure-panel expand step, a
`page.goto(wait_until="load")` landmark-timing race, and a weak
content-change wait condition) closed in round 1; 3 further findings the
live run exposed (worker-subprocess environment sanitization never
applied; incomplete process-group timeout cleanup; execution-integrity
failures mis-classified as ordinary product FAILs) closed across rounds
2–4, with round 4 returning `APPROVE` and zero outstanding findings. This
0.5 text reflects that implementation, now complete, and the Human
Engineering Lead's final acceptance of this specification.)
**Type:** Workflow Infrastructure

---

This specification does not modify the text of `SPEC-001`, `SPEC-003`,
`SPEC-004`, `SPEC-005`, or `docs/decisions/0001`/`0002`. It proposes an
additive extension of the phase sequence, Round Packet, and Codex contract
those documents already define and implement. **SPEC-006 EXTENDS
SPEC-001/SPEC-004. It does not rewrite historical SPEC-001/SPEC-004.**
Per `ENGINEERING.md`'s Source-of-Truth Hierarchy, this document is a
proposal, not a change to what is true today. **No code in `peos/` has
been modified to produce this document.** It also does not modify, re-run,
or reconcile the existing untracked `docs/validation/SPEC-005-validation.md`
— that file's "Outstanding" section is exactly the dogfood gap this spec
closes, and is treated here as evidence of motivation, not as something
this document edits.

The architectural decisions below have been selected by the Human
Engineering Lead and frozen in `docs/decisions/0003-peos-runtime-verification.md`
(Accepted and implemented). The independent Codex architecture/specification
review of this document and ADR-0003 (§21) closed with no blocking
findings, implementation followed under that approval and a separate
independent Codex implementation review, and this specification's own
**Status is Approved**.

## Resolved Engineering Lead Decisions

All six decisions left open in SPEC-006 v0.1 are now resolved. None of
these remains open; an implementation may not silently revisit any of
them without a new round of explicit sign-off (the same discipline
SPEC-004's "Resolved Engineering Lead Decisions" section already
establishes for that document).

1. **Adopt Playwright (Python sync API) with Chromium, pinned.** §10.
   The dependency is recorded as an exact version pin (e.g.
   `playwright==1.55.0`; the exact version is fixed at implementation
   time and then held pinned — never a loose range that could silently
   change which browser build Runtime Verification exercises).
   Chromium's binary is installed by a separate, explicit,
   human-run bootstrap step (`python -m playwright install chromium`),
   never by PEOS itself during a run, under any condition. Runtime
   preflight verifies the installed browser matches what the pinned
   Playwright release expects and fails closed (never auto-installs)
   if it does not.
2. **Production runtime mode (`next build` + `next start`), never
   `next dev`.** §10. Runtime Verification exercises the production
   build. Where practical it reuses the exact build deterministic
   verification already validated for this round; where the build must
   be re-run with a Runtime-Verification-specific input (the resolved
   ephemeral backend origin — see Decision 3's implementation note
   below), it re-runs the *same, frozen* `npm run build` invocation
   deterministic verification already validated succeeds, never `next
   dev`.
3. **OS-assigned ephemeral ports, loopback-only, for both services —
   with exactly one required, named, minimal, explicitly-scoped
   product-code co-requirement.** §10, §11. Both the backend and the
   frontend bind to an OS-assigned loopback port; this is the single
   design this specification adopts (Codex Architecture Review Round 1,
   Finding 9 rejected the earlier, internally-contradictory framing that
   floated an "interim fixed frontend port" alongside an absolute
   no-hardcoded-port acceptance criterion — that contradiction is
   removed, not resolved by picking the weaker reading). This design is
   only coherent if **both** of the following also hold, and this
   specification now states both as required, not optional:
   - **Both ports are reserved before either service starts** (§7, §8
     step 3): the orchestrator resolves an OS-assigned port for the
     backend and for the frontend (bind-to-port-0-and-release, or an
     equivalent two-stage reservation — a best-effort reservation, not
     an airtight lock; a subsequent bind failure on either port is an
     ordinary execution-integrity `FAILED`, already handled by §6/§12)
     **before starting either subprocess** — never only the backend's
     port, which would leave the backend's own CORS configuration
     unable to name the frontend's origin at backend-startup time.
   - **`backend/app.py`'s CORS allow-list must be able to name that
     resolved frontend origin at backend-startup time.** The currently
     hardcoded list (`http://localhost:3000`, `http://127.0.0.1:3000`)
     cannot do this. This specification therefore requires — as a
     condition of adopting ephemeral ports at all, not a separately
     optional nicety — the minimal, additive, default-off mechanism in
     §10: `CORSMiddleware`'s `allow_origins` reads one additional,
     optional environment variable and *appends* its entries to the
     existing hardcoded list; when unset, `backend/app.py`'s observable
     behavior is byte-identical to today, so no other caller of the
     backend is affected.
   This is a genuine, if narrow, touch to product code
   (`backend/app.py`), and this specification does not authorize making
   it by itself — it is the one item in §22 requiring the Human
   Engineering Lead's explicit, separate sign-off before implementation,
   precisely because it is product code, not PEOS orchestration code.
   Resolving Finding 9 means there is now exactly **one** clean decision
   for the Human Engineering Lead to make here (authorize this one named
   change, yes or no) rather than an internally contradictory design
   that left the question of which of two incompatible readings to
   follow.
4. **Fixed, typed, versioned runtime-check catalog; no scripting DSL.**
   §10. Exactly two generic checks (`page_load`, `viewport_overflow`)
   and one AI-Power-Lab-specific check (`experiment_run`), each a typed
   Python dataclass of parameters (never a loose dict), each implemented
   entirely inside the trusted PEOS control plane (§11 Trust Boundary,
   hardening item A). The catalog carries an explicit
   `RUNTIME_CHECK_CATALOG_VERSION` constant, recorded in every
   `RuntimeEvidence` record (§9).
5. **Evidence bounds, tightened from v0.1's defaults.** §9, §12:
   `RuntimeEvidence` JSON ≤ 256 KiB; captured service stdout/stderr
   ≤ 64 KiB per service; at most one screenshot per runtime check;
   ≤ 4 MiB per screenshot; ≤ 10 MiB total screenshot evidence per round.
   Any truncation or omission is explicitly represented in evidence
   metadata (a named `truncated: bool` / `omitted_reason: str | None`
   field) — evidence is never silently truncated with no trace that it
   happened.
6. **No automatic retry after a completed runtime-check timeout/failure.**
   §12. Bounded readiness polling during service startup is not a
   retry (it is one bounded wait operation with a single outcome:
   ready-in-time or not); re-attempting a check, or a service start,
   after it has already completed with a timeout or failure is never
   performed.

## Codex Architecture Review — Round 1

An independent Codex architecture/specification review of SPEC-006 v0.2
and ADR-0003 (§21's review gate), run as a standalone `codex exec
--sandbox read-only` call against this repository, returned
`CHANGES_REQUIRED` with 11 findings, all severity `major` (one of the
eleven additionally marked `requires_human_decision=true`). Zero
findings were dismissed; all 11 are closed normatively in this revision,
at the sections named below. None of Codex's findings proposed
implementing anything — this remains a specification/ADR revision, not
code.

| # | Finding (condensed) | Closed in |
|---|---|---|
| 1 | The claim that an unapproved `peos/` control-plane change can only take effect after human-reviewed merge is false: `reconcile_workspace_to_repo` copies working-tree changes back onto the authoritative repository on `APPROVED`, `FAILED`, **and** `HUMAN_GATE`, and nothing today protects `peos/` from that copy-back the way `GOVERNANCE_ARTIFACTS` protects `CLAUDE.md`/`AGENTS.md`/`ENGINEERING.md`/the governing spec. | §11 hardening item A (new Requirement: `peos/` added to `protected_relative_paths`), §10/ADR-0003 Decision 6 (claim narrowed to current-run isolation) |
| 2 | Playwright's Python sync `page.evaluate()` has no timeout argument; a candidate page that hangs the renderer's main thread can stall the liveness probe itself, defeating the bounded-convergence guarantee. | §6 hardening item B (orchestrator-enforced wall-clock watchdog, independent of any Playwright per-call timeout) |
| 3 | The liveness probe's two-branch outcome (alive/dead) is incomplete — `evaluate` can fail with a transient, non-connection error (e.g. execution-context destroyed mid-navigation) that is neither. Also: the one check whose *own* execution causes an execution-integrity failure has no defined `RuntimeCheck` record under the PASS/FAIL/NOT_EXECUTED definitions as drafted. | §6 (three-branch classification + one bounded internal re-probe for the transient case), §13 (`NOT_EXECUTED` redefined to cover this check too) |
| 4 | "Agent-unwritable staged evidence copy" asserted no enforcement mechanism; worse, §11's own write-allow list granted the backend/frontend *service* processes write access to the evidence output directory, directly contradicting "only `runtime_evidence.py` writes it." | §9/§11 (evidence directory removed from the service sandbox's write-allow list; "read-only" reframed as OS permission bits plus the authoritative tamper-*detection* mechanism — hash re-verification — not a tamper-*prevention* claim) |
| 5 | Every round persisted evidence at the same run-level path, so a remediation cycle's evidence would overwrite an earlier cycle's — contradicting §18's promise to report every round's own evidence/hash. Separately, evidence was persisted *before* teardown, even though teardown can retroactively downgrade `execution_integrity_passed`. | §9/§12 (immutable, cycle-qualified evidence paths; §8 lifecycle reordered so the persisted record is finalized only after teardown's cleanup verification is known) |
| 6 | No declared-check-count bound, yet the whole record must fit in 256 KiB; `ServiceReadiness` had no truncation metadata; `RuntimeEvidence` had no package-level truncation flag; `evidence_json_sha256` was specified *inside* the record it hashes — self-referential. | §9 (new ≤20-checks-per-round bound via Human Gate #12; `ServiceReadiness.truncated` added; `RuntimeEvidence.truncated` package rollup added; the hash moves to a sidecar file, never embedded in the file it hashes) |
| 7 | §11 carried over only the real-`$HOME` credential-path denylist, omitting SPEC-003's separately-implemented `extra_deny_read_paths` mechanism that denies reading an arbitrarily-located `PEOS_CODEX_AUTH_HOME` directory — a real, already-closed gap this draft silently reopened for Runtime Verification's own sandbox profile. | §11 (explicit carry-over of `extra_deny_read_paths`) |
| 8 | `page.route("**/*")` does not cover all browser traffic (service workers, WebSockets, a popup's first request) — the application-layer network claim overstated its own coverage. | §11 hardening item G (context-level routing registered before any page exists; `service_workers="block"`; WebSocket/other gaps named explicitly as uncovered by layer 2, relying on layer 1 for those specifically) |
| 9 | Internal contradiction: AC-004 forbade any hardcoded port for both services, while Known Limitations permitted an interim fixed frontend port; AC-041 forbade product-behavior changes while literal ephemeral ports require the named CORS change; and the lifecycle started the backend before either port was resolved, even though the backend's own CORS configuration needs to know the frontend's origin. `requires_human_decision=true`. | §7/§8 (both ports reserved before either service starts); §10/Resolved Decision 3 (the CORS addition is now a required, named co-requirement of ephemeral ports, not an optional "interim" aside); §19 AC-004 updated; Known Limitations' contradicting paragraph removed — the human decision narrows to exactly one thing: authorizing that one named CORS change (§22) |
| 10 | §16 claimed a Human Gate outcome returns to implementation/verification/review "exactly as SPEC-004 already specifies," but the real baseline makes `HUMAN_GATE` terminal for that run (no Tier-2 resume); the continuation SPEC-004 actually provides is a **new, separately-initiated** run. | §16 (wording corrected to state this precisely) |
| 11 | The SPEC-005 dogfood scenario (§17) treated two passing `viewport_overflow` checks as closing an AC's full "no horizontal overflow **or clipped text**" text; `viewport_overflow` only measures document-level `scrollWidth`/`clientWidth`, which does not detect text clipped inside a fixed-size `overflow:hidden` container. | §10 (catalog description narrowed to "no horizontal overflow" specifically), §17 (scenario's claim narrowed to match) |

## Codex Architecture Review — Round 2

A focused re-review of 0.3 (same standalone, read-only, non-implementation
posture as Round 1; not a fresh broad review) confirmed 10 of the 11
Round 1 findings `CLOSED` as drafted. Two items remained:

- **Finding 9, `STILL_OUTSTANDING`.** The 0.3 revision correctly made the
  port/CORS design internally coherent (Resolved Decision 3, §7, §8,
  Known Limitations, ADR-0003 Decision 3 all agreed on one design), but
  AC-041's unconditional "no product-behavior change" wording still
  contradicted the required CORS addition by name. Closed in this
  revision (0.4) by explicitly, by-name excluding that one authorized
  change from AC-041's scope — the same treatment AC-042 already gave
  it for the agent-credential/tool-grant axis specifically; AC-041
  needed the identical treatment for the product-behavior axis.
- **One new `minor` finding** (not a Round 1 finding — a defect the
  Round 1 remediation itself introduced): the port-reservation reordering
  left several stale `§8 step 0` cross-references (the actual step
  numbers are 3/4/5, not 0/3/4, once "Resolve the Runtime Plan" and
  "Preflight" are counted as steps 1/2). Corrected in this revision.

Both were addressed in this text. A Round 3 focused confirmation pass
found the AC-041 fix correct, but found 3 of the Round 2 fix's own "§8
step" cross-reference corrections incomplete (3 occurrences near the
console/page-error-forces-FAIL rule still read "§8 step 6" instead of
the correct "§8 step 7" — the port-reservation insertion had shifted
"Execute each declared check" from step 6 to step 7, and the Round 2
fix had corrected the port-reservation-ordering paragraphs but missed
these three). Those were corrected, and a Round 4 confirmation pass —
re-deriving Section 8's numbering from its own numbered list and
checking every "§8 step" occurrence in the file — returned `APPROVE`
with zero outstanding findings. The independent review gate (§21) is
satisfied as of this text.

## 1. Purpose

PEOS (SPEC-001, hardened by SPEC-003, generalized by SPEC-004) already
produces deterministic verification evidence (`pytest`, frontend
lint/typecheck/build) and an independent Codex review before a run can
reach `APPROVED`. It has no way to produce *runtime* evidence: starting
the actual application, loading pages in an actual browser, exercising an
actual interactive control, and observing actual viewport/layout/console
behavior. SPEC-005 (AI Power Lab Engineering Narrative) requires exactly
this kind of evidence for several of its acceptance criteria (AC-001,
AC-012 in particular), and PEOS currently has no capability to produce it
— so those criteria sit permanently in a manual/observational limbo that
neither Claude nor Codex may fabricate evidence for, and that a human has
to perform by hand every time.

This specification defines PEOS Runtime Verification V1: a new,
orchestrator-owned capability that starts the AI Power Lab backend and
production-built frontend in the isolated workspace, drives a real,
environment-frozen browser against them, collects structured,
provenance-rich evidence (including screenshots, console/page errors,
viewport measurements, and cryptographic hashes of every persisted
artifact), and supplies that evidence to Codex's independent review
exactly the way deterministic verification results already are — never
as something either agent self-reports, never trusting a check
implementation the candidate workspace could have modified, and never as
a reason to invent a new Human Gate merely because PEOS previously lacked
the tool.

## 2. Motivation / Dogfood Evidence

SPEC-005 §15 ("Verification Requirements") requires, among its local
verification steps: "Manual run of the dev server ... exercising: initial
page load (baseline run), at least one `ExperimentPanel` run with a
different `final_fraction`, and the mobile-width layout — confirming
AC-001 through AC-014 visually." AC-012 specifically requires "no
horizontal overflow or clipped text" at both the `sm`/`lg` breakpoints.

The real dogfood run against SPEC-005 reproduced exactly the gap this
specification exists to close. The implementer's own
`docs/validation/SPEC-005-validation.md` (untracked, written by the
implementation session, read but not modified by this specification)
records:

> **Manual dev-server check NOT performed (SPEC-005 §15).** The
> remediation session that produced this record had no shell, browser, or
> network tool, so `npm run dev` could not be started. ... Synchronized
> values, narrative ordering, and absence of horizontal overflow/clipping
> are therefore **unverified at runtime**; AC-012 is not established by
> the static classes alone. A human must run these checks and record the
> observations here.

Codex, reviewing against SPEC-005's own acceptance criteria, correctly
refused to mark AC-012 satisfied without actual runtime evidence — this is
the Outstanding Findings Register and `_validate_review_payload`'s
AC-completeness check (SPEC-004 Requirement 5/25) working exactly as
designed; a partial-coverage or unevidenced `APPROVE` is a contract
violation, not a passing review. Claude, correctly, refused to fabricate
that evidence rather than omit it. Both agents behaved exactly as
`CLAUDE.md`/`AGENTS.md` require. The gap is not an agent defect; it is a
missing PEOS capability — the Human Engineering Lead's own stated
philosophy, restated here as the design mandate for this specification:

> "Human gate" must NOT mean "the agents currently lack a tool." If a task
> can reasonably and safely be executed and verified by machine, PEOS
> should provide the required controlled capability. Human intervention
> should be reserved primarily for genuine product/design judgment,
> engineering decisions not already governed by an approved specification,
> or capabilities that cannot legitimately be automated.

## 3. Scope

- A new **Runtime Verification** phase, inserted into `peos/workflow.py`'s
  phase sequence immediately after Local Verification and immediately
  before the corresponding Codex phase, for **both** cycle 0 and every
  remediation cycle (SPEC-004's cycle semantics are unchanged; this
  spec adds one phase inside each of SPEC-004's existing "Local
  verification" → "Codex review" transitions, never a new top-level
  loop) — see §18 for the exact minimal extension points.
- A deterministic, spec-text-driven **Runtime Plan** (`peos/runtime_plan.py`,
  mirroring `peos/verification_plan.py`'s parsing style and the same
  "indented line under a recognized heading" convention): the governing
  specification declares which named runtime checks (from a fixed,
  typed, versioned V1 catalog, §10) apply, with their typed parameters
  and the acceptance-criteria ID(s) each is evidence for (§13).
- A **trusted-control-plane Runtime Check Catalog**
  (`peos/runtime_catalog.py`): the typed check-parameter dataclasses and
  check implementations themselves, imported from the authoritative
  PEOS installation only — never loaded, overridden, or supplied by the
  candidate workspace under verification (§11 hardening item A).
- A **Runtime Services** module (`peos/runtime_services.py`): starts the
  FastAPI backend and the already-production-built Next.js frontend as
  subprocesses against the isolated workspace, each bound to an
  OS-assigned, loopback-only ephemeral port, confined by an extension of
  the existing macOS Seatbelt verification sandbox (`peos/sandbox.py`),
  owned by a managed process-group lifecycle (§12 hardening item D),
  waits for readiness with a bounded timeout, and tears both down
  deterministically — with cleanup verified, not merely attempted — on
  every terminal path.
- A **Runtime Browser** module (`peos/runtime_browser.py`): drives a
  Playwright-controlled, environment-frozen Chromium instance (§10
  hardening item E) against the running frontend, executing the fixed
  catalog of named checks the Runtime Plan declares, classifying every
  timeout/error deterministically (§6 hardening item B), and recording
  console/page errors and any attempted non-loopback network request
  unconditionally on every check (§11 hardening item G).
- A **Runtime Evidence** schema and module (`peos/runtime_evidence.py`):
  the structured, provenance-rich `RuntimeEvidence`/`RuntimeCheck`
  records this specification requires (§9, hardening item F), persisted
  under `.peos/runs/<run_id>/` (same containment/retention regime as the
  Run Ledger) and staged read-only into the isolated workspace for
  either agent's file tools, with cryptographic hashes enabling identity
  re-verification before every consuming invocation (§9, §13).
- Extensions (additive only, per the Requirements below) to: the Round
  Packet (SPEC-004 Requirement 17), `REVIEW_SCHEMA`'s AC-completeness
  check (SPEC-004 Requirement 5/25, `peos/codex_agent.py`), the
  Outstanding Findings Register's existing disposition vocabulary
  (reused, not replaced — §16 hardening item H), the Human Gate catalog
  (one new gate, §15 hardening item I), and `peos/report.py`'s Delivery
  Report.
- One concrete acceptance scenario (§17) demonstrating this capability
  closes the exact SPEC-005 AC-012 gap described in §2.
- A dependency decision (Playwright + Chromium, §10) made explicit, not
  silently introduced, and a trust-boundary analysis of how this
  capability interacts with PEOS dogfooding/self-modification (§11
  hardening item A).
- `docs/decisions/0003-peos-runtime-verification.md` (ADR, Accepted),
  freezing exactly the decisions enumerated in its own Context/Decision
  sections (§20).

## 4. Non-Goals

- **Automated visual-aesthetic approval.** Per the originating brief:
  "Do not require automated visual-aesthetic approval in V1." Runtime
  Verification establishes objective facts (viewport dimensions, overflow,
  clipping indicators, element presence/order, runtime values,
  screenshots). Whether a composition is aesthetically correct or
  communicates the intended design remains eligible for the existing final
  Human Engineering Lead approval step (`ENGINEERING.md`'s Definition of
  Done #9) — this specification adds no new Human Gate for aesthetic
  judgment, and does not change what that final approval step already
  covers.
- **A general runtime-scripting or browser-automation DSL.** The V1
  catalog (§10) is fixed, typed, and versioned; a spec may only select
  from it and supply typed parameters, never author new
  browser-interaction logic. Extending the catalog is a reviewed `peos/`
  code change (§23).
- **Cross-browser coverage.** Chromium only in V1 (§10, Known Limitations).
- **CI/headless-Linux support.** Runtime Verification inherits the
  existing Seatbelt sandbox's macOS-only boundary (SPEC-001 Finding 1);
  on any other platform it fails closed exactly as deterministic
  verification already does (§12), never silently unconfined.
- **Changing the backend's CORS configuration beyond the one named,
  additive, default-off mechanism in §10/Resolved Decision 3, or any
  other product-code behavior.** Every other aspect of
  `backend/app.py`'s configuration, and every aspect of the frontend's
  product behavior, is read, not modified.
- **Visual-regression/pixel-diffing against a prior run.** Each run's
  screenshots are corroborating evidence for *this* run's acceptance
  criteria (§10 hardening item E), never compared against a baseline
  image, and never the primary assertion mechanism. (A future version
  could add this; not designed here — §23.)
- **Load, performance, or concurrency testing.** One browser, one page
  context at a time, run sequentially; never a stress test.
- **Programmatic resume of a Runtime Verification phase mid-flight.**
  Same Tier-1-only posture SPEC-004 already established for the whole
  workflow (SPEC-004 Requirement 13).
- Any change to AI Power Lab simulation physics, the FastAPI backend's
  engineering behavior, the frontend's product behavior, or
  `SPEC-002`/`SPEC-005`'s own text.
- Any change to SPEC-003/Decision-0002's authentication/credential
  boundary. Runtime Verification invokes neither `claude` nor `codex`
  itself and needs no new credential.

## 5. Roles and Separation of Duties

Per the originating brief, restated normatively:

- **Claude** — implementation/remediation owner, unchanged from
  SPEC-001/SPEC-004. Receives a textual summary of Runtime Evidence (via
  the Round Packet, §13) during remediation cycles so it can act on a
  concrete, machine-observed defect (e.g., "mobile viewport overflow:
  `scrollWidth=430 > clientWidth=390`") rather than a vague human
  instruction. Claude never runs the browser itself, never starts the
  application services itself, and gains no new tool grant (still
  `Read Edit Write Grep Glob`, no Bash, per SPEC-001 Finding 2). Claude
  may, like any other file in its isolated workspace, edit the
  workspace's own copy of `peos/` (including `peos/runtime_catalog.py`)
  if a task somehow asks it to — see §11 hardening item A for exactly
  why that can never make a Claude-modified check implementation
  authoritative for the run that produced it.
- **PEOS deterministic verifier** (`peos/verification_plan.py`, unchanged)
  — `pytest`, frontend lint/typecheck/build, and spec-declared commands.
  Category A (§6). Unaffected by this specification, except that its
  `npm run build` step is the production artifact Runtime Verification
  reuses or, where the ephemeral backend origin requires it, re-invokes
  identically (Resolved Decision 2).
- **PEOS Runtime Verification** (this specification, NEW) — starts the
  required local application services, exercises the approved
  runtime/browser checks, collects structured evidence including
  screenshots, inspects browser/runtime state (console errors, page
  errors, attempted non-loopback requests, viewport measurements), and
  shuts services down cleanly, with cleanup *verified*, on every terminal
  path. This is orchestrator-owned PEOS code
  (`peos/runtime_services.py`, `peos/runtime_browser.py`,
  `peos/runtime_catalog.py`), reviewed like any other `peos/` module —
  not something either agent does, and not a new AI capability.
- **Codex** — independent reviewer, unchanged in kind. Reviews the
  specification, the implementation (via its existing read-only access
  to the isolated workspace), the deterministic verification evidence,
  **and now the Runtime Evidence package** (§13) — staged into the
  workspace and summarized in its Round Packet, exactly like every other
  orchestrator-supplied context element. Codex is never the component
  that generates its own browser evidence, and is never granted a browser
  tool, an MCP server, or any new capability by this specification
  (`--sandbox read-only`, `--ignore-user-config`/`--ignore-rules`
  unchanged). Runtime Verification does not replace Codex (§16 hardening
  item H) — it only ever supplies Codex additional evidence to review.
- **Human Engineering Lead** — genuine design/product judgment, any
  engineering/product decision not already governed by an approved
  specification, final approval (which `CODEX_APPROVED` is a
  precondition for, never a substitute for — §16), and the one new Human
  Gate this specification introduces (§15 hardening item I) for a
  declared runtime check that cannot be deterministically interpreted.
  Never asked to manually perform a check this specification's catalog
  already covers once approved.

## 6. Verification Taxonomy

Formalizing the three categories from the originating brief, and the
normative distinction (hardening item B) that governs how Category B
interacts with the Codex convergence loop — this is the most load-bearing
conceptual rule in this specification and every Requirement below depends
on it being applied consistently.

**A. Deterministic verification.** Machine-executable commands with
deterministic pass/fail semantics: `pytest -q`, frontend
lint/typecheck/build, spec-declared verification commands
(`peos/verification_plan.py`, unchanged). A failure here is `FAILED`
immediately, before any Codex call, never counted as a remediation cycle
used toward convergence, never softened into evidence for review.

**B. Runtime/observational verification.** Machine-executable
application/browser/API observations that produce **evidence** for
acceptance criteria. This specification's entire subject. A check's
result is a fact Codex's review evaluates alongside everything else it
already evaluates — not an automatic deterministic gate the way Category
A is.

**C. Human judgment.** Criteria whose satisfaction fundamentally requires
product/design/engineering judgment — not merely a missing automation
capability. Per Non-Goal 1 above: aesthetic/design-intent judgment stays
here, addressed by the existing final human-approval step, not by a new
Human Gate.

### Hardening item B — Execution Integrity vs. Product Observation (explicit classification rule)

Runtime Verification produces two independently meaningful outcomes that
this specification's Requirements and the workflow implementation must
never conflate, and — per the Human Engineering Lead's explicit
instruction — **not every Playwright timeout/error is the same kind of
event.** This section states the deterministic rule that decides which
is which; it is applied mechanically, never left to an LLM's judgment.

- **Execution integrity** — did the Runtime Verification *harness itself*
  run to completion and produce interpretable evidence? A failure here
  is `FAILED` immediately (or, for the one named catalog/parameter-
  interpretation case, `HUMAN_GATE` #12 — §15), **before** any Codex call
  for that round, exactly like a deterministic-verification failure.
  **Non-exhaustive examples, named explicitly per the Human Engineering
  Lead's instruction:**
  - the Seatbelt sandbox is unavailable on this platform;
  - Playwright/Chromium is not installed, not pinned correctly, or not
    launchable (§10);
  - the browser process cannot launch;
  - the Playwright transport or the browser process crashes/disconnects
    mid-run;
  - the backend or frontend service cannot bind its assigned port or
    cannot become ready within the bounded timeout;
  - `RuntimeEvidence` cannot be persisted with integrity (a hash
    mismatch, a symlink-containment violation, a write failure);
  - runtime process cleanup fails and cannot be verified (§12 hardening
    item D).
- **Product observation (ordinary check result)** — given the harness
  ran successfully, what did an individual `RuntimeCheck` actually
  observe? This is ordinary Category-B evidence: it flows into the
  Evidence Package and Codex's review exactly like a visible code defect
  would. **Non-exhaustive examples, named explicitly per the Human
  Engineering Lead's instruction:**
  - an expected UI element does not appear;
  - an `experiment_run` action completes but the observed result is
    incorrect (or does not change at all);
  - an expected result does not appear before the check's own bounded
    deadline, **while the browser/page remains confirmed responsive**
    (see the liveness-probe rule below — this is the one case a naive
    implementation most easily misclassifies);
  - the page has horizontal viewport overflow;
  - any other application/API behavior the functioning harness observed
    that violates the check's declared assertion.
  A check recording `status="FAIL"` is **not** an orchestration failure
  and does **not** by itself produce `FAILED` — it is input to Codex, who
  may legitimately return `CHANGES_REQUIRED` citing it, exactly as if a
  human reviewer had seen the same screenshot.

**Deterministic timeout-classification procedure — orchestrator-enforced
watchdog, not a Playwright per-call timeout (Codex Round 1 Finding 2,
closed).** Playwright's Python **sync** API's `page.evaluate()` takes no
timeout argument at all — a liveness probe implemented as a bare
`page.evaluate("() => true")` call can itself hang indefinitely if
candidate JavaScript has blocked the page's main thread, which would
silently defeat the entire bounded-convergence guarantee this
specification exists to preserve. The classification procedure below is
therefore built around an **externally enforced wall-clock watchdog**,
never around any Playwright call's own timeout parameter (several of
which, like `evaluate`, do not have one):

1. Every blocking Playwright call this harness makes — the original
   awaited condition that timed out, the liveness probe itself, and any
   follow-up call described below — runs under one fixed, named,
   wall-clock deadline enforced by a **separate watchdog thread** in the
   orchestrator process, independent of whatever timeout argument (if
   any) the specific Playwright call accepts. If that deadline elapses
   while any such call is still blocked (including the probe itself
   hanging), the watchdog force-terminates the browser process
   (`SIGKILL`, outside Playwright's own API) from the outside and the
   result is unconditionally an **execution-integrity failure**
   (`FAILED`) — the watchdog, not Playwright, is the actual bound.
2. Within that watchdog budget, every Playwright `TimeoutError` (from a
   navigation, a `wait_for_selector`, an `expect` assertion, or any other
   awaited condition that *does* accept and honor a timeout) triggers a
   liveness probe: is the browser process still connected (no
   `Browser.on("disconnected")` event observed), is the page not closed
   (`page.is_closed() is False`), and does `page.evaluate("() => true")`
   (itself bound by the same watchdog, per step 1) return `True`?
3. **Three possible probe outcomes, not two** (Codex Round 1 Finding 3,
   closed — the original two-branch design left a real, observed
   Playwright failure mode unclassified):
   - **Connection-level failure** (disconnected, page closed, or the
     probe call itself hits the watchdog deadline or a connection-level
     error) — the harness itself is unresponsive. **Execution integrity
     failure** (`FAILED`), regardless of which specific await triggered
     the original timeout.
   - **Transient, navigation-related failure** (e.g. Playwright's
     "execution context was destroyed" error, which occurs when a
     navigation is in flight at the moment of the probe and is not
     itself evidence the harness is unresponsive) — the probe is
     retried **exactly once**, immediately, still within the same
     watchdog budget. This is a bounded, internal retry of the *probe
     itself*, not a retry of the check's own completed primary
     assertion or of a completed service start (Resolved Decision 6 is
     about never re-attempting a check or service start *after it has
     already completed* — a single immediate re-probe during
     classification of one still-in-progress check is a different,
     narrower thing, and is the only such internal retry this
     specification permits). The retried probe's own outcome is then
     classified under whichever of these three branches it actually
     produces — if it is again inconclusive in this same transient way,
     it is treated as the connection-level-failure branch (no second
     retry).
   - **Success** (the probe, or its one permitted retry, returns `True`
     cleanly) — the browser and page are confirmed alive and responsive;
     the original timeout reflects a real page state the harness
     correctly observed, not a harness fault. This is downgraded to an
     ordinary **product-observation check result**, `status="FAIL"`,
     with the specific awaited condition and the elapsed time recorded
     in `observation`.

This procedure is implemented once, centrally, in
`peos/runtime_browser.py` (never duplicated per check kind), so every
catalog check (current and future) gets identical classification —
including the watchdog bound and the three-way probe outcome — for free.

## 7. Runtime Verification Architecture

```
Isolated workspace (existing, SPEC-001 peos/sandbox.py)
  |
  +-- Port reservation (NEW, §8 step 3): both the backend's and the
  |     frontend's OS-assigned loopback ports are resolved BEFORE either
  |     service starts, i.e. before §8 steps 4-5 (Codex Round 1 Finding
  |     9) -- the backend's CORS configuration and the frontend's
  |     build-time API base URL both need the OTHER service's resolved
  |     origin before that service's own startup.
  |
  +-- Runtime Services (NEW, peos/runtime_services.py)
  |     backend subprocess:  <venv python> -m uvicorn backend.app:app
  |                          --host 127.0.0.1 --port <reserved backend port>
  |                          AI_POWER_LAB_EXTRA_CORS_ORIGINS=http://127.0.0.1:<reserved frontend port>
  |                          (the one named CORS co-requirement, Resolved
  |                          Decision 3 -- authorized and implemented, §22)
  |     frontend subprocess: npm run start  (next start; cwd:
  |                          workspace/frontend; production build only
  |                          -- NEVER next dev, Resolved Decision 2)
  |                          NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:<reserved backend port>
  |     both confined by an extension of the existing Seatbelt profile
  |     (peos/sandbox.py) -- see "Security and Isolation" (§11) --
  |     each process owned by its own managed process group (§12
  |     hardening item D) -- the evidence output directory is NOT in
  |     either service's write-allow list (§11 Finding 4 fix: only the
  |     unsandboxed orchestrator process writes evidence)
  |
  +-- Runtime Browser (NEW, peos/runtime_browser.py)
        Playwright (Python, pinned version) launches one Chromium
        instance with a frozen environment (§10 hardening item E),
        connects to http://127.0.0.1:<reserved frontend port>, executes
        the Runtime Plan's declared checks against the fixed, typed,
        versioned V1 catalog (peos/runtime_catalog.py, trusted control
        plane -- §11 hardening item A), collecting, in memory, a
        provenance-rich evidence record for each check -- screenshots,
        console/page/network events, structured measurements,
        timestamps -- finalized and persisted (§9) only after §8 step 8's
        teardown/cleanup-verification outcome is known (Codex Round 1
        Finding 5).
```

Backend and frontend are started fresh for every round that requires
Runtime Verification (cycle 0, and any remediation cycle whose runtime
plan includes runtime checks — §16) against the **current** state of the
isolated workspace at that point in the run, never reused across rounds
(a reused, possibly-stale service process could otherwise serve a
remediation cycle's Codex review evidence collected against cycle 0's
code). Each round's services are torn down, with cleanup verified,
before that round's Codex call is made.

**Production-build/ephemeral-port interaction (Resolved Decisions 2/3,
stated precisely).** `NEXT_PUBLIC_*` environment variables are inlined
into the Next.js client bundle at build time, not read at request time —
this is a real Next.js constraint, not a PEOS choice. Because the
backend's address is only known once Runtime Verification reserves its
OS-assigned ephemeral port (§8 step 3, before either service starts —
after deterministic verification's own `npm run build` has already run,
with no knowledge of that port), the production frontend build consumed
by Runtime Verification is, in the general case, a **second,
Runtime-Verification-triggered invocation of the exact same, frozen `npm
run build` script** deterministic verification already validated
succeeds — with `NEXT_PUBLIC_API_BASE_URL` set to the reserved backend
origin — rather than a byte-for-byte reuse of deterministic
verification's own `.next/` output directory. This is the one case
"reuse" in Resolved Decision 2 means "reuse the validated build
*process*, not necessarily the literal build *artifact* bytes," named
here precisely so neither the implementer nor Codex mistakes a second
build invocation for silently redefining verification's meaning
(SPEC-001 Finding 5's concern) — the script, its frozen value, and the
source code are all identical to what deterministic verification already
validated; only one additional, Runtime-Verification-scoped environment
variable differs. A failure of this second build invocation is itself an
execution-integrity failure (`FAILED`, §6), never silently absorbed.

**Port-reservation ordering (Codex Round 1 Finding 9, closed).** Both
ports must be known before either service's startup-time configuration
is fixed: the backend's CORS allow-list (Resolved Decision 3) needs the
frontend's resolved origin, and the frontend's build-time bundle needs
the backend's resolved origin. §8 step 3 therefore reserves both ports
first, as one atomic step, before §8 steps 4–5 start either
subprocess — neither service is ever started with the other's origin
still unknown.

## 8. Runtime Lifecycle

One Runtime Verification pass, for a given round (cycle 0 or remediation
cycle *N*), proceeds:

1. **Resolve the Runtime Plan** for this round (parsed once, frozen at
   Planning exactly like `VerificationPlan`, §16) — the set of declared
   checks, their typed parameters, and their mapped AC IDs (§13). A plan
   declaring more checks than the fixed per-round count bound (§9, Codex
   Round 1 Finding 6) is rejected here, at Planning, as Human Gate #12
   (§15) — before any workspace runtime service is ever started; this
   makes the §9 evidence-size bounds satisfiable by construction, never
   a runtime overflow this phase has to improvise a response to.
2. **Preflight.** If the Runtime Plan declares zero checks, this phase is
   a documented no-op (logged, not skipped silently — it still appears in
   the Delivery Report as "no runtime checks declared"); return
   immediately with an empty `RuntimeEvidence`. Otherwise: confirm the
   Seatbelt sandbox is available (reuses `sandboxed_verification_command`'s
   own platform check) and confirm the pinned Playwright release and its
   matching Chromium build are installed and launchable (§10). Either
   failing is an execution-integrity `FAILED` (§6), before any subprocess
   is started, and **never** triggers an automatic install (Resolved
   Decision 1).
3. **Reserve both services' OS-assigned loopback ports** (Codex Round 1
   Finding 9) — bind each to port 0 locally, read back the assigned
   port, then release the socket (a best-effort reservation, not an
   airtight lock; a subsequent bind failure on either port in the next
   step is an ordinary execution-integrity `FAILED`, not a distinct
   failure class). Both resolved ports are known before either
   subprocess starts.
4. **Start the backend** under the extended Seatbelt profile (§11),
   environment built from `sandboxed_env()` (unchanged stripping) plus
   the one named CORS co-requirement environment variable set to the
   reserved frontend origin (Resolved Decision 3 — authorized and
   implemented, §22), owned by its own managed process group (§12 hardening item D).
   Poll a bounded number of times, with a bounded total timeout, for the
   backend's existing health endpoint to respond; a bind failure or
   timeout is an execution-integrity `FAILED` immediately (teardown
   still runs — §12).
5. **Build (or verify-and-reuse) the production frontend** with
   `NEXT_PUBLIC_API_BASE_URL` set to the reserved backend origin (§7),
   then **start the frontend** via `next start` bound to its reserved
   port, same pattern, polling the frontend's root path.
6. **Launch the browser.** Playwright, Chromium, confined the same way
   (§11), environment frozen (§10 hardening item E). A launch failure is
   an execution-integrity `FAILED` (teardown still runs).
7. **Execute each declared check**, in the Runtime Plan's declared order,
   against the fixed catalog (§10, imported only from the trusted PEOS
   control plane — §11 hardening item A), collecting each check's result
   **in memory only** at this point (persistence is deferred to step 9,
   Codex Round 1 Finding 5). Each check independently collects
   console/page errors and any attempted non-loopback network request
   (§11 hardening item G); any console/page error forces that check's
   `status` to `FAIL` regardless of its own primary assertion (§6's
   Execution Integrity vs. Product Observation distinction governs
   *within* a single check's result, not across checks). Every
   `TimeoutError` is classified by §6's deterministic, watchdog-enforced
   liveness-probe procedure. A check that raises an unexpected
   (non-assertion, non-timeout) exception is itself an execution-integrity
   failure for the whole phase (`FAILED`), not a `FAIL`-status check —
   the catalog's checks are written to never raise for an ordinary,
   anticipated page-state outcome (§10). A check that cannot run at all
   because an earlier check in the same round already produced an
   execution-integrity failure, **or that is itself the check whose
   execution produces that failure**, is recorded with
   `status="NOT_EXECUTED"` (§13 hardening item C, redefinition closing
   Codex Round 1 Finding 3's second half), never silently absent from the
   evidence.
8. **Teardown**, unconditionally, on every path through steps 2–7
   including an exception: §12 hardening item D's full graceful →
   bounded-grace-period → force-termination → **verified** cleanup
   sequence for both service process groups and the browser. Teardown
   runs on `PASS`, on a check recording `FAIL`, on an execution-integrity
   `FAILED`, on an unhandled exception, and on process interruption. An
   orphaned process or unverifiable cleanup is **itself** an
   execution-integrity failure (§12), even if every declared check's own
   result was otherwise `PASS` — undetected process leakage is a safety
   concern, not a cosmetic one, and can retroactively flip an
   otherwise-passing round's outcome. **This step's outcome is known
   before the next step runs** (Codex Round 1 Finding 5) — teardown is
   never deferred past evidence finalization.
9. **Finalize, collect, and persist the `RuntimeEvidence`** (§9,
    hardening item F) only now that step 8's cleanup-verification
    outcome is known: every declared check's `RuntimeCheck` record
    (including any `NOT_EXECUTED` ones), screenshots written to a
    bounded, cycle-qualified evidence directory (§9), the overall
    `execution_integrity_passed` flag (reflecting step 8's actual
    outcome, never a value computed before it), start/end timestamps,
    service/browser/catalog provenance, and a SHA-256 sidecar hash for
    every persisted artifact (§9 — the hash is never embedded inside the
    file it hashes). **Stage** a read-only copy (OS permission bits; see
    §9/§11 on what this does and does not guarantee) into the isolated
    workspace at a fixed, cycle-qualified path, and **persist** the
    authoritative copy under
    `.peos/runs/<run_id>/runtime-evidence/<cycle_label>/` (same
    containment/never-reconciled/never-agent-writable regime as the Run
    Ledger, SPEC-004 Requirement 19).

## 9. Evidence Model

```python
RUNTIME_CHECK_CATALOG_VERSION = "1.0.0"   # peos/runtime_catalog.py

@dataclass(frozen=True)
class RuntimeCheck:
    check_id: str                     # e.g. "runtime.0.viewport_overflow.mobile"
    kind: str                         # one of the fixed, typed V1 catalog names (§10)
    catalog_version: str              # RUNTIME_CHECK_CATALOG_VERSION at execution time
    related_ac_ids: tuple[str, ...]   # AC IDs this check is evidence for (§13)
    parameters: dict[str, ...]        # the check's own typed, declared parameters,
                                       # rendered to primitive JSON for evidence
    status: str                       # "PASS" | "FAIL" | "NOT_EXECUTED"
                                       # NOT_EXECUTED covers BOTH: (a) a check
                                       # never reached because an earlier check
                                       # already caused an execution-integrity
                                       # failure, AND (b) a check whose OWN
                                       # execution is itself what caused that
                                       # failure (Codex Round 1 Finding 3) --
                                       # neither has a determinable PASS/FAIL.
                                       # ("NOT_APPLICABLE" exists only at the AC
                                       #  rollup level, never for a declared check
                                       #  itself -- see §13 hardening item C)
    action_performed: str             # short, sanitized, bounded description
    observation: str                  # short, sanitized, bounded description
    measurements: dict[str, ...]      # small, bounded, primitive-valued dict
                                       # (e.g. {"scroll_width_px": 430,
                                       #  "client_width_px": 390})
    screenshot_path: str | None       # relative path under the evidence dir
    screenshot_sha256: str | None     # hash of the persisted screenshot file
    console_errors: tuple[str, ...]   # sanitized, bounded
    page_errors: tuple[str, ...]      # sanitized, bounded
    blocked_network_requests: tuple[str, ...]  # sanitized, bounded (§11 item G)
    truncated: bool                   # true if any field in this record was
                                       # truncated against its bound (§9 bounds)
    omitted_reason: str | None        # non-null iff screenshot_path is None
                                       # because a bound (not an error) suppressed it
    started_at: str                   # ISO 8601 UTC
    finished_at: str                  # ISO 8601 UTC

@dataclass(frozen=True)
class ServiceReadiness:
    service: str                      # "backend" | "frontend"
    command: tuple[str, ...]          # the literal argv used to start it
                                       # (no secret ever appears in this argv)
    resolved_port: int
    ready: bool
    waited_seconds: float
    captured_stdout_tail: str         # sanitized, bounded (<=64 KiB, §12)
    captured_stderr_tail: str         # sanitized, bounded (<=64 KiB, §12)
    truncated: bool                   # true if either tail above was truncated
                                       # against its bound (Codex Round 1
                                       # Finding 6 -- RuntimeCheck already had
                                       # this; ServiceReadiness did not)

@dataclass(frozen=True)
class RuntimeEvidence:
    run_id: str
    cycle_label: str                  # "cycle 0" | "remediation cycle N" --
                                       # also the directory-name component of
                                       # this round's evidence path (§9 "Per-
                                       # cycle identity", below)
    workspace_snapshot_identity: str  # same identity Round Packet element 5 uses
    baseline_commit: str
    catalog_version: str              # RUNTIME_CHECK_CATALOG_VERSION
    playwright_version: str
    browser_version: str              # the actual launched Chromium build version
    browser_environment: dict[str, ...]  # frozen viewport/locale/timezone/etc.
                                       # actually applied (§10 hardening item E)
    service_readiness: tuple[ServiceReadiness, ...]
    checks: tuple[RuntimeCheck, ...]
    execution_integrity_passed: bool  # harness ran to completion, INCLUDING a
                                       # verified teardown (§8 step 8/§12 item D)
                                       # -- finalized only after teardown's
                                       # outcome is known (Codex Round 1
                                       # Finding 5), never written before it.
                                       # Does NOT mean every check's status is
                                       # PASS (§6) -- see all_checks_passed.
    truncated: bool                   # package-level rollup: true if this
                                       # record's own JSON, or any contained
                                       # RuntimeCheck/ServiceReadiness, was
                                       # truncated against a bound (Codex
                                       # Round 1 Finding 6)
    started_at: str
    finished_at: str

    @property
    def all_checks_passed(self) -> bool:
        return all(c.status == "PASS" for c in self.checks)

# Codex Round 1 Finding 6: a hash of this record's own persisted JSON
# cannot be a FIELD of that same JSON -- that is self-referential. The
# hash is instead written to a sidecar file next to evidence.json (never
# inside it) and referenced by the Round Packet's RuntimeEvidenceRef
# (§14), exactly the shape SPEC-004's static-context identity mechanism
# already uses for a file it must hash without embedding the hash in the
# hashed content.
```

Every text field (`action_performed`, `observation`, each error/blocked-
request string, each `captured_*_tail`) is passed through the same
`sanitize_human_text` + fixed-length bound `peos/diagnostics.py` already
applies to every other agent-adjacent text field in PEOS (SPEC-004
Requirement 18's rule, extended here to a new producer). `measurements`
and `parameters` values are restricted to primitive JSON types
(`int`/`float`/`bool`/`str`, bounded string length) — never an arbitrary
object, and never raw page HTML/JS content. This is deliberately a
**minimal, bounded** schema, not a general telemetry/tracing format: it
exists to let an independent reviewer evaluate a specific, named claim
("no horizontal overflow at mobile width"), not to capture everything a
browser could possibly report.

**Bounds (Resolved Decision 5, tightened from v0.1, made satisfiable by
construction via a per-round check-count cap, Codex Round 1 Finding 6).**
A Runtime Plan declaring more than **20** checks in one round is rejected
at Planning as Human Gate #12 (§8 step 1, §15) — this named cap, combined
with the per-field bounds below, guarantees the 256 KiB budget is always
achievable without ever having to drop a whole declared check's record to
stay inside it. Within that bound: the persisted `evidence.json` is
≤ 256 KiB; each `ServiceReadiness.captured_*_tail` is ≤ 64 KiB; at most
one screenshot is captured per `RuntimeCheck`; each screenshot is
≤ 4 MiB; total screenshot evidence for one round is ≤ 10 MiB. Any bound
that would otherwise be exceeded results in `truncated=True` on the
affected `RuntimeCheck`/`ServiceReadiness` record **and** on the
package-level `RuntimeEvidence.truncated` rollup, and/or a non-null
`omitted_reason` on the affected `RuntimeCheck` — **evidence is never
silently truncated with no trace that it happened** (the Human
Engineering Lead's explicit instruction); `sanitize_human_text`'s own
existing per-string bound is unaffected by this spec's bounds.

**Hardening item F — evidence integrity/provenance.** The schema above
carries, at minimum, every element the Human Engineering Lead named:
run ID, convergence cycle label, runtime-check catalog version, each
check's name/typed parameters/result/timing, service readiness results
(including the literal start command, never containing a secret),
Playwright/browser version, the actually-applied frozen browser
environment, structured observations (`measurements`), evidence artifact
paths, and a SHA-256 hash for every persisted artifact — `evidence.json`
itself and every screenshot file. **The hash of `evidence.json` is never
a field inside that same file** (Codex Round 1 Finding 6 — a record
cannot coherently contain the hash of its own bytes); it is written to a
sidecar file, `evidence.json.sha256`, alongside it, and referenced by the
Round Packet's `RuntimeEvidenceRef` (§14). **Identity re-verification**:
exactly like SPEC-004 Requirement 21/AC-39's static-context-artifact
pattern, before every Claude/Codex invocation that consumes a round's
staged evidence copy, PEOS re-verifies that the staged copy's hash still
equals the authoritative `.peos/runs/` copy's recorded hash (read from
the sidecar); a mismatch is an execution-integrity `FAILED`, immediately,
before that invocation — never a silent re-hash, never a Human Gate.

**Per-cycle identity (Codex Round 1 Finding 5, closed).** Persisted at
`.peos/runs/<run_id>/runtime-evidence/<cycle_label>/evidence.json` plus
`.../<cycle_label>/evidence.json.sha256` plus
`.../<cycle_label>/screenshots/*.png` — `<cycle_label>` is a filesystem-
safe slug of `"cycle-0"` or `"remediation-cycle-N"`, so **every round's
evidence has its own, immutable path** and a remediation cycle's Runtime
Verification never overwrites an earlier cycle's authoritative evidence,
closing the direct contradiction with §18's requirement to report every
round's own evidence summary and hash. This is under the exact same
filesystem-containment rules Requirement 19 of SPEC-004 already states
for the Run Ledger (symlink rejection at every path component, atomic
writes, never reconciled back onto the authoritative repository, never
supplied as agent-controlled repository state).

**The staged copy inside the isolated workspace, and what "read-only"
actually means (Codex Round 1 Finding 4, closed — the original wording
overclaimed an enforcement mechanism that does not exist).** The staged
copy is written with OS-level read-only permission bits
(`chmod 0444`-equivalent); this is a *convention and a speed bump*, not a
cryptographic guarantee — a sufficiently motivated edit through Claude's
own Write/Edit tools against that path, or any other local write, is not
claimed to be structurally impossible the way, say, the Seatbelt
sandbox's network denial is. **The actual tamper-detection mechanism is
the identity re-verification above**: if the staged copy is altered after
staging, by any means, its hash no longer matches the authoritative
`.peos/runs/` copy's recorded hash, and the very next consuming
invocation fails closed (execution-integrity `FAILED`) *before* either
agent is ever invoked against the altered content — detection, not
prevention, is the guarantee this specification actually makes. Only
`peos/runtime_evidence.py`'s own write, from the unsandboxed orchestrator
process, ever produces the authoritative copy in the first place; no
backend/frontend service subprocess has write access to the evidence
output directory at all (§11, Codex Round 1 Finding 4's other half — the
Seatbelt profile's write-allow list for those *service* subprocesses does
not include it).

## 10. Browser/API Capability Boundary

**Dependency decision (Resolved Decision 1).** This repository currently
has no browser-automation dependency of any kind: `@playwright/test`
appears in `frontend/package-lock.json` only as an *optional peer
dependency of Next.js itself* (for Next's own integration-test tooling),
is not declared in `frontend/package.json`, and no
`playwright`/`@playwright/test` package or Chromium binary is installed
anywhere in this checkout — verified directly against this repository,
not assumed. Adopting Playwright for V1 means:

- A new Python dependency, `playwright` (sync API), **recorded as an
  exact version pin** (e.g. `playwright==1.55.0`; the exact version is
  fixed at implementation time and held pinned thereafter — a routine
  dependency bump that changes the pinned version is itself a reviewed
  change, never an automatic/transparent one, because it also silently
  changes the bundled Chromium build this entire specification's
  evidence depends on).
- A one-time, explicit, **human-run** provisioning step — `python -m
  playwright install chromium` — run **outside** any PEOS run and
  outside the network-denied verification sandbox, exactly the same
  posture SPEC-001's `create_isolated_workspace` already takes toward
  `frontend/node_modules` ("dependencies are taken as of run start and
  never re-installed or updated by PEOS"). **PEOS never attempts to
  download or install a browser binary itself, at any point, under any
  condition** (Resolved Decision 1, restated as a hard invariant).
- A **runtime preflight check** (§8 step 2) that verifies the installed
  Chromium build matches what the pinned Playwright release expects
  (Playwright's own `playwright --version`/browser-revision metadata) and
  that it actually launches — never merely "some `chromium` binary exists
  somewhere on `$PATH`." A mismatch or launch failure is an
  execution-integrity `FAILED`, never an auto-install, never a silent
  "best effort, use whatever's there" fallback.
- Chromium only in V1 (not Firefox/WebKit) — one browser engine is
  sufficient to establish the objective facts this spec requires
  (overflow, clipping, console/page errors, screenshots); cross-browser
  coverage is not an engineering-learning requirement for this project
  and is named as deferred (§23).
- A Python driver (not a Node/`@playwright/test` test-runner script) so
  the capability lives entirely inside `peos/` (Python, same language as
  every other orchestrator module, no new runtime PEOS has to shell out
  to) and the frontend's own `package.json`/toolchain stays untouched.

**Production runtime mode (Resolved Decision 2).** Runtime Verification
exercises `next build` + `next start`, never `next dev`. §7 states
precisely how this interacts with the ephemeral backend port (the
frontend's production build is, in general, re-invoked with
`NEXT_PUBLIC_API_BASE_URL` set once the backend's port is known, reusing
the exact same frozen build script deterministic verification already
validated).

**Ephemeral, loopback-only ports (Resolved Decision 3).** Both services
bind to an OS-assigned port (`--port 0`-style resolution, or the
language/framework-equivalent), confirmed loopback-only (`127.0.0.1`,
never `0.0.0.0`). The backend's ephemeral port introduces no conflict of
any kind with anything else in the system. The frontend's ephemeral port
introduces exactly one implication requiring separate confirmation,
stated fully in Resolved Decision 3 above and restated as a flagged item
in §22: `backend/app.py`'s CORS allow-list is currently a hardcoded
Python literal (`["http://localhost:3000", "http://127.0.0.1:3000"]`)
with no way to vary per-run without a product-code change. The minimal,
additive, default-off mechanism this specification proposes for that
change (not implemented by this specification, named here for
completeness) is: `CORSMiddleware`'s `allow_origins` reads an additional,
optional environment variable (e.g. `AI_POWER_LAB_EXTRA_CORS_ORIGINS`, a
comma-separated list) and appends its entries to the existing hardcoded
list; when unset, `backend/app.py`'s observable behavior is byte-identical
to today. Runtime Verification would set this variable, for its own
subprocess only, to the frontend's resolved ephemeral origin. This is a
genuine, if narrow, product-code touch and is not authorized by this
specification alone (§22).

**Hardening item A — Trust Boundary: the fixed, typed, versioned V1
catalog is trusted-control-plane code, never candidate-supplied.** Exactly
three named check kinds — the two generic ones named by the Human
Engineering Lead (`page_load`, `viewport_overflow`) and one
AI-Power-Lab-specific check (`experiment_run`) — each a typed parameter
dataclass (never a loose dict parsed ad hoc), each implemented entirely in
`peos/runtime_catalog.py`. This module, and every module that classifies
a check's result or establishes evidence integrity
(`peos/runtime_browser.py`, `peos/runtime_evidence.py`), is part of the
**trusted PEOS control plane**: the running orchestrator process has
already imported it from the authoritative checkout's own `peos/`
directory — exactly as `peos/verification_plan.py`'s existing frozen-plan
mechanism and `peos/sandbox.py`'s existing Seatbelt profile builder
already do today — **before the isolated workspace is ever created**.
The orchestrator never re-imports, re-executes, or dynamically loads any
`peos/` code from inside the isolated workspace at any point in a run,
regardless of what the isolated workspace's own (fully clonable, fully
Claude-editable) copy of `peos/` contains. A candidate change therefore
cannot modify its own verifier and have that modification take effect
for the run that produced it — the verifier that scores a run is always
the one already running in memory when that run started, never a copy
the workspace's edits touch.

**This is not a new invariant; it is the same property every existing
PEOS verification mechanism already has, stated explicitly for the first
time because Runtime Verification is the first capability whose own
*trustworthiness as a judge* is as safety-critical as what it judges.**
`pytest -q` already runs candidate test code, but *which commands run and
how their exit code is interpreted* comes from the orchestrator's own
already-loaded `peos/verification_plan.py` — not from anything the
workspace's own copy of that file says. Runtime Verification's catalog
implementations are exactly analogous: the *application* under test
(backend/frontend source) is untrusted candidate code: the *harness*
deciding what "PASS" means is not, and cannot be, by construction.

**Interaction with PEOS dogfooding/self-modification — claim narrowed,
plus one new requirement closing a real gap (Codex Round 1 Finding 1,
closed).** A PEOS task whose own goal is to change
`peos/runtime_catalog.py` (or any other `peos/` module) is implemented
exactly like any other PEOS task: Claude edits the isolated workspace's
copy, and deterministic verification and Runtime Verification for *that
run* still execute under the **currently running** orchestrator
process's already-loaded, pre-change code (started before the isolated
workspace existed) — this part of the original claim is correct and
unchanged: **within the run that produced it, a candidate change to
`peos/` cannot judge itself.**

What the original draft got wrong is the claim about what happens
*after* that run. `reconcile_workspace_to_repo` (SPEC-001) copies the
isolated workspace's net working-tree changes back onto the
authoritative repository's working tree on **every** terminal
outcome — `APPROVED`, `FAILED`, **and** `HUMAN_GATE`, not only
`APPROVED` — and today's `protected_relative_paths` (the
reconciliation-blocked set) covers only `GOVERNANCE_ARTIFACTS`
(`CLAUDE.md`, `AGENTS.md`, `ENGINEERING.md`) and the governing
specification file. **Nothing today stops a candidate change to
`peos/runtime_catalog.py` (or any other `peos/` module) from being
copied straight onto the authoritative repository's working tree by
reconciliation, as an ordinary, uncommitted change — before any human
has reviewed it, let alone approved or merged it through a PR.** If the
Human Engineering Lead then started a second PEOS invocation against
that same working tree without first inspecting `git status`/`git diff`
and reverting or committing deliberately, that second invocation's
orchestrator process would import the reconciled-but-unreviewed
`peos/runtime_catalog.py` from disk.

This specification therefore adds one new, concrete requirement rather
than resting on an unenforced claim: **every path under `peos/` is added
to `protected_relative_paths`** — the exact same reconciliation-blocking
mechanism `GOVERNANCE_ARTIFACTS` already uses. A run whose candidate
workspace modified any file under `peos/` reports that change in
`blocked_governance_mutation` exactly like a `CLAUDE.md` edit would,
**never** copies it back onto the authoritative repository's working
tree, under any outcome including `APPROVED`. Adopting a change to the
PEOS control plane itself — including this specification's own future
implementation, and including a legitimate future catalog extension
(§23) — therefore requires the same thing adopting a change to
`CLAUDE.md`/`AGENTS.md`/`ENGINEERING.md` already requires: a human
manually applying the reported, blocked diff after reviewing it, outside
PEOS's own automation, exactly like today's governance-artifact
protection already works. With that requirement in place, the corrected
claim holds for both the current run **and** every subsequent one: there
is no code path by which a not-yet-human-applied candidate change to the
catalog/harness/classification logic can ever reach the authoritative
repository at all, let alone judge a future run.

**Fixed, typed V1 check catalog.**

1. **`page_load`** (generic) — navigate to a declared path (default `/`);
   assert the navigation succeeded (no navigation error, a successful
   HTTP response); assert a declared, ordered list of DOM landmarks (CSS
   selectors) are present **and** appear in that top-to-bottom reading
   order (bounding-rect Y-position comparison, a structured measurement,
   §10 hardening item E) — this is the mechanism for narrative-ordering
   criteria like SPEC-005 AC-001; capture at most one corroborating
   screenshot.
2. **`experiment_run`** (AI-Power-Lab-specific) — locate the
   `ExperimentPanel` control, set a declared `final_fraction` value,
   submit, wait (bounded) for the result to update, assert the page's
   rendered output actually changed (a declared selector's text content
   differs from its pre-run value, a structured measurement) — never a
   hardcoded assumption about *what* it changed to, only *that* it
   changed, consistent with §7 Constraint 4 of SPEC-005's own physics
   rule ("no fabricated engineering behavior"/no invented expected
   value); capture at most one corroborating screenshot.
3. **`viewport_overflow`** (generic) — set a declared viewport size
   (named presets `desktop` / `mobile`, or an explicit `width`×`height`);
   assert, **programmatically from layout dimensions** (the primary
   assertion mechanism, §10 hardening item E — never from pixel
   inspection of the screenshot itself),
   `document.documentElement.scrollWidth <= document.documentElement.clientWidth`
   (with a small, named pixel epsilon to absorb scrollbar-width jitter);
   capture at most one corroborating screenshot. **Scope, stated
   precisely (Codex Round 1 Finding 11, closed):** this check is
   evidence for **document-level horizontal overflow only**. It does
   not detect text clipped inside a fixed-size `overflow:hidden`
   container, truncated by a CSS ellipsis, or otherwise cut off without
   ever producing document-level horizontal scroll — that is a distinct
   claim this catalog entry does not check and the V1 catalog has no
   check for. A specification's `ac=` mapping that cites this check as
   evidence for an acceptance criterion whose text asserts *both* "no
   horizontal overflow" *and* "no clipped text" is only evidenced for
   the first half by this check; the second half is not runtime-
   evidenced by anything in the V1 catalog and remains whatever
   category (code inspection, a future catalog extension, or human
   judgment) the specification and its reviewer already treat it as.

Every check, of every kind, unconditionally also collects page `console`
(error-level) and `pageerror` events, and any attempted non-loopback
network request (§11 hardening item G), for its own duration, and forces
`status="FAIL"` if any console/page error occurred (§8 step 7) regardless
of its own primary assertion.

### Hardening item E — deterministic browser environment

Runtime Verification freezes, where practical, the browser environment
every check runs under, so a check's result is reproducible and not an
artifact of whatever ambient settings happened to be present:

- **Viewport**: named presets — `desktop` 1280×800, `mobile` 390×844 — or
  an explicit `width`×`height` declared by the Runtime Plan.
- **Device scale factor**: fixed at `1.0`.
- **Locale**: fixed at `en-US`.
- **Timezone**: fixed at `UTC`.
- **Reduced-motion preference**: fixed at `reduce` (`prefers-reduced-
  motion: reduce`) — consistent with SPEC-005 §7 Constraint 4's own "no
  eased/decorative interpolation" physics-integrity rule; this also makes
  a layout measurement independent of whatever transition timing a
  component happens to use.
- **Browser version**: pinned transitively by the pinned Playwright
  release (Resolved Decision 1) — the exact launched Chromium build
  version is recorded in `RuntimeEvidence.browser_version` (§9) for every
  round, so a later discrepancy is attributable.

**Structured observations are the primary assertion mechanism; screenshots
are corroborating evidence only.** `viewport_overflow`'s assertion is
`scrollWidth`/`clientWidth` read programmatically via
`page.evaluate(...)`, not a visual/pixel inspection of the captured image
— the screenshot exists so a human (or Codex, reading the staged file)
can visually corroborate what the structured numbers already proved, not
so either agent or PEOS infers the result from the image. This applies to
every catalog check, present and future: a check's pass/fail determination
must always be traceable to a structured `measurements` value, never to
"the screenshot looks fine."

**Declaration convention.** A new, deterministically-parsed subsection,
mirroring `peos/verification_plan.py`'s existing "indented line inside a
recognized heading is a literal instruction, never AI-interpreted"
convention — e.g., under a `### Runtime Verification` heading nested in
the spec's existing `## Verification Requirements`/`## Verification Plan`
section:

```
### Runtime Verification

    runtime: page_load path=/ landmarks="EventBanner,TelemetryChart,EnergyDeficitAnalysis" ac=AC-001
    runtime: experiment_run final_fraction=0.45 selector="[data-testid=min-vdc]" ac=AC-002
    runtime: viewport_overflow viewport=desktop ac=AC-012
    runtime: viewport_overflow viewport=mobile ac=AC-012
```

This exact key=value syntax is illustrative, not frozen by this spec
(finalized at implementation time, the same deferral SPEC-004 used for
Round Packet prompt rendering) — what **is** normative is: (a) one line
per declared check, (b) a fixed `kind` token from the §10 typed catalog,
(c) the check's parameters as named key=value pairs, each type-checked
against that `kind`'s typed parameter dataclass, (d) at least one `ac=`
value naming an acceptance-criteria ID the check is evidence for and that
exists in the specification's own numbered AC set, and (e) a line naming
a `kind` outside the fixed catalog, omitting a required parameter for its
kind, or naming an `ac=` value the specification does not itself declare,
is **never** silently dropped or silently ignored — this is Human Gate
#12 (§15, hardening item I), a decision-bearing specification defect that
requires explicit, deterministic, non-LLM-inferred interpretation to
notice (hardening item C).

## 11. Security and Isolation

Runtime Verification executes code from the candidate (Claude-edited)
workspace — the backend and frontend application code — and must be
treated as untrusted execution, the same posture `peos/sandbox.py`'s
module docstring already states for deterministic verification. This
specification extends that existing boundary rather than bypassing it:

- **No new credential, ever.** Runtime Verification invokes neither
  `claude` nor `codex`; it needs, and is given, no authentication
  material, no MCP access, and no additional external service authority
  of any kind. The backend/frontend subprocess environment is built from
  `sandboxed_env()` unchanged (every existing stripping rule —
  `CREDENTIAL_ENV_DENYLIST`, `AMBIENT_AGENT_AUTH_DENYLIST`, HOME
  redirection — applies identically).
- **No push-capable Git access.** The services run inside the isolated
  workspace, which already has every remote removed (SPEC-001
  `create_isolated_workspace`, unchanged).
- **Filesystem containment.** A new Seatbelt profile builder,
  `build_runtime_verification_sandbox_profile` (extending the pattern of
  `build_verification_sandbox_profile`, not replacing it — deterministic
  verification's existing profile is untouched), denies writes everywhere
  except: the isolated workspace (so `.next/` cache, `__pycache__`, and
  any runtime-generated file can be written exactly where the application
  would normally write it), the isolated `home_dir`, and the OS's own
  temp directories — and, exactly like the existing profile, an explicit,
  last-match-wins re-deny of `repo_root` itself even where it happens to
  be nested under one of those broader allow-paths. **The evidence output
  directory is deliberately *not* in this list** (Codex Round 1 Finding 4,
  closed — the original draft's own write-allow list contradicted its
  claim, two paragraphs later, that only `peos/runtime_evidence.py`
  writes evidence): the backend and frontend service subprocesses have no
  legitimate reason to write there at all, and granting it would have
  given untrusted candidate-run service processes direct filesystem
  write access to the evidence the orchestrator is about to hand Codex.
  Only the orchestrator's own, unsandboxed process (exactly like
  `peos/ledger.py`'s Run Ledger writes today) ever writes under
  `.peos/runs/<run_id>/runtime-evidence/`. Reads of `repo_root/.git`, the
  named real-`$HOME` credential-path denylist, **and** (Codex Round 1
  Finding 7, closed) the resolved `PEOS_CODEX_AUTH_HOME` directory when
  configured are denied identically to the existing profile —
  `build_runtime_verification_sandbox_profile` accepts and forwards the
  same `extra_deny_read_paths` mechanism
  `build_verification_sandbox_profile`/`sandboxed_verification_command`
  already use for this exact purpose (SPEC-003 remediation Finding 2):
  an arbitrarily-located Codex authentication directory is not a
  well-known path under the real `$HOME`, so the fixed
  `CREDENTIAL_PATH_DENYLIST` alone does not cover it, and backend/frontend
  service processes have no more business reading it than deterministic
  verification's own subprocesses do.
- **Network: loopback-only, enforced in two independent layers
  (hardening item G — defense in depth).**
  1. **OS layer (Seatbelt, unchanged in kind from the existing profile).**
     The existing verification profile already carries a narrow, named
     exception — `(allow network-bind/-inbound/-outbound (... "localhost:*"
     ...))` — added for Next.js's own internal build-worker IPC. This
     specification **generalizes that exact exception**, not a new,
     broader one: the backend and frontend subprocesses, and the
     Playwright-launched browser process, are confined to the same
     loopback-only allowance; every other network destination remains
     denied at the OS level, exactly as before.
  2. **Application layer (browser-level request interception) — a
     best-effort second layer with named, explicit gaps, not a claim of
     exhaustive coverage (Codex Round 1 Finding 8, closed — the original
     wording overstated what `page.route` actually covers).** The
     request-interception rule is registered at the **browser-context
     level** (`context.route("**/*", ...)`), **before any page is
     created** in that context, specifically so it is active for every
     page's very first navigation rather than racing a per-page
     registration; the browser context is also launched with
     `service_workers="block"`, eliminating the one gap in
     `page.route`'s coverage that has a clean, direct fix (routing does
     not intercept service-worker-handled requests at all, so the
     simplest closure is not giving the page a service worker to
     register in the first place). Any request this layer's handler
     observes and that does not target `127.0.0.1`/`localhost` is
     aborted, and the attempted destination (sanitized, bounded) is
     recorded into that check's `blocked_network_requests` (§9).
     **Named, explicit gap: WebSocket connections are not covered by
     this routing mechanism** (Playwright's page/context `route`
     interception is an HTTP-request mechanism; WebSocket upgrade
     traffic is a separate channel) — a page that opens a non-loopback
     WebSocket is relying on **layer 1 (Seatbelt) alone** to deny it,
     which it still does, at the OS level, exactly as it denies any
     other non-loopback socket. This is why layer 1 is not merely
     "redundant insurance" alongside layer 2: the two layers have
     different, only partially overlapping coverage, and layer 1 is the
     one with no known gap for the traffic layer 2 cannot see.
  If a page under test needs to fetch any non-loopback resource (e.g., an
  uncached external font), that fetch is aborted — by layer 2 for an
  ordinary HTTP(S) request, or by layer 1 alone for a WebSocket — and is
  visible in the evidence as a blocked request where layer 2 observed
  it; this is a known limitation (§23), not a reason to widen the network
  policy.
- **No fallback to an unsandboxed run.** If the Seatbelt sandbox is
  unavailable (any non-macOS platform, or `sandbox-exec` removed), or the
  pinned Playwright/Chromium is not installed/usable, Runtime
  Verification fails closed (execution-integrity `FAILED`, §6) — it never
  silently starts the services unconfined, and it never silently skips
  the phase and lets the run proceed as if no runtime checks were
  declared.
- **Chromium's own process sandboxing is additive, not a substitute.**
  This specification does not characterize or rely on every property of
  Chromium's internal renderer sandbox (the same posture SPEC-001 already
  takes toward Codex's `--sandbox read-only` and Claude's `--restricted`
  — verified for the one property that matters, not claimed as a general
  guarantee); the Seatbelt profile around the browser *process*, plus the
  application-layer request interception above, are the structural
  backstops that do not depend on characterizing Chromium's own
  internals.
- **Evidence is orchestrator-owned; neither candidate services nor
  either agent have write access to it by grant.** `peos/runtime_evidence.py`,
  running unsandboxed as part of the orchestrator process, is the only
  writer of `.peos/runs/<run_id>/runtime-evidence/<cycle_label>/`
  (outside the isolated workspace entirely — no backend/frontend
  service subprocess has it in its Seatbelt write-allow list, above) and
  of the staged copy inside the workspace. §9 states precisely what the
  staged copy's read-only permission bits do and do not guarantee, and
  why hash re-verification — not the permission bits — is the actual
  tamper-detection mechanism this specification relies on.

## 12. Timeout/Resource/Cleanup Behavior

- **Readiness polling (not a retry, Resolved Decision 6).** A single,
  named, bounded total wait (e.g. 30–45s, polled at a short fixed
  interval) per service, resolved exactly once per service per round.
  Exceeding it is an execution-integrity `FAILED`, with teardown still
  run on whatever subset of services already started. This bounded
  polling loop is the one case the Human Engineering Lead explicitly
  distinguished from "retry": it is a single wait operation for a single
  readiness outcome, not a second attempt after a completed failure.
- **Per-check timeout, classified deterministically by an
  orchestrator-enforced watchdog, never by a Playwright-native timeout
  alone (§6, Codex Round 1 Findings 2/3).** Each catalog check has its
  own bounded wait for its awaited condition, and every blocking
  Playwright call made while classifying a timeout is itself bound by
  the same external watchdog thread, because at least one such call
  (`page.evaluate`) accepts no timeout argument of its own. Exceeding
  the watchdog bound, or a connection-level probe failure, is `FAILED`
  (execution integrity); a probe that confirms the browser/page alive
  (after at most one bounded internal re-probe for a transient
  navigation-related error, §6) downgrades the same timeout to an
  ordinary `status="FAIL"` product-observation result. **No retry of a
  completed check, of either classification, or of a completed service
  start, ever occurs** (Resolved Decision 6) — the one bounded, internal
  liveness-probe re-attempt in §6 is a narrower, different thing: a
  single immediate re-check during classification of one still-in-
  progress check, not a second attempt at anything already completed.
- **Evidence bounds (Resolved Decision 5), plus a per-round declared-
  check-count bound making them satisfiable by construction (Codex
  Round 1 Finding 6).** A Runtime Plan declaring more than 20 checks is
  rejected at Planning (Human Gate #12, §8 step 1, §15) — never a
  runtime overflow. Within that bound: `evidence.json` ≤ 256 KiB; each
  service's captured stdout/stderr tail ≤ 64 KiB; at most one screenshot
  per check; ≤ 4 MiB per screenshot; ≤ 10 MiB total screenshot evidence
  per round. Any field or artifact a bound would otherwise
  exceed is explicitly marked `truncated=True` or given a non-null
  `omitted_reason` (§9) — never silently dropped with no trace.
- **Retention.** Evidence directories are retained and cleaned up on the
  exact same schedule as Run Ledgers (SPEC-004 Requirement 20's 20-run
  retention), keyed by the same `run_id` — never a separate retention
  policy that could diverge from the ledger's.
- **Hardening item D — bounded, verified process lifecycle.** Every
  backend/frontend subprocess is launched into its own managed process
  group (e.g. `start_new_session=True` on POSIX, so any child the service
  itself spawns — an extra `uvicorn` worker, a Next.js internal worker —
  is owned by the same group); the browser process and its own children
  are owned and torn down through Playwright's own managed lifecycle
  (`browser.close()` / the Playwright driver's own process teardown). On
  **every** exit path (`PASS`, a `FAIL`-status check, an execution-
  integrity `FAILED`, an unhandled exception, or process interruption
  delivered to the PEOS orchestrator itself):
  1. request graceful termination (`SIGTERM` to the process group /
     `browser.close()`);
  2. wait a bounded grace period;
  3. force-terminate anything still alive (`SIGKILL` to the process
     group / the Playwright driver's own force-kill path);
  4. **verify** cleanup — confirm the assigned ports are no longer bound
     and the process group has no live members.
  **An orphaned process, or cleanup that cannot be verified, is itself an
  execution-integrity failure** (§6) — it is never merely logged and
  ignored, and it can retroactively convert an otherwise-`PASS` round
  into `FAILED` (the Human Engineering Lead's explicit instruction).
  Verification failing to confirm cleanup still does not hang the run or
  raise a second, compounding exception — it is captured, once, as the
  reason for that round's execution-integrity failure, using the same
  best-effort, never-recurse discipline `peos/workflow.py`'s
  `_safe_terminal_ledger_write` already uses elsewhere.
- **Fail-closed, never silent-skip.** A capability that cannot be
  established (sandbox unavailable, dependency missing/mismatched, bind
  failure, browser launch failure, unverifiable cleanup) is an
  execution-integrity `FAILED`. A declared check that cannot be
  deterministically interpreted (unrecognized catalog name, missing
  required parameter, an `ac=` value outside the spec's own AC set) is
  Human Gate #12. Neither case silently proceeds as though the declared
  requirement were satisfied or absent.

## 13. Explicit Applicability and AC Mapping (hardening item C)

Runtime applicability is explicit and deterministic — parsed from the
same fixed, conventionally-marked spec text every other PEOS declaration
mechanism already uses (§10's declaration convention) — **never inferred
heuristically by an LLM.** This section defines the normative
representation.

**Per-check parsing.** Each declared `### Runtime Verification` line
parses into a `RuntimeCheckDeclaration` carrying: `kind` (validated
against the fixed catalog), its typed parameters (validated against that
`kind`'s parameter dataclass), and `related_ac_ids: tuple[str, ...]`
(every `ac=` value on that line, each validated against the governing
specification's own numbered acceptance-criteria set). Any validation
failure is Human Gate #12 (§10, §15), never silently coerced or dropped.

**Four-state check/AC status, never collapsed to two.** Per the Human
Engineering Lead's explicit instruction, runtime status distinguishes at
least:

- **`PASS`** — the check executed under a harness that itself completed
  with execution integrity, and its primary assertion held (with no
  disqualifying console/page error, §8 step 7).
- **`FAIL`** — the check executed under a harness that itself completed
  with execution integrity, and its primary assertion did not hold (or a
  disqualifying console/page error occurred, or its timeout was
  classified as a product observation, §6).
- **`NOT_EXECUTED`** — the check was validly declared and resolvable, but
  its result could not be determined, for either of two reasons (Codex
  Round 1 Finding 3, closed — the original definition only covered the
  first): (a) it never ran because an *earlier* check in the same round
  already produced an execution-integrity failure that aborted the
  phase before reaching it, or (b) *this check's own execution* is what
  produced that execution-integrity failure, so no PASS/FAIL
  determination for it was ever possible in the first place. Both are a
  property of an individual `RuntimeCheck` record; neither is
  distinguished from the other in the `status` field itself (both are
  `"NOT_EXECUTED"`) — a distinction between them, if ever needed, would
  come from `observation`'s free text, not a fifth status value.
- **`NOT_APPLICABLE`** — a property of an **acceptance criterion**, not
  of an individual check: an AC ID that no declared check's `ac=` names
  at all. SPEC-006 makes no runtime claim whatsoever about that AC; it is
  unaffected by this specification and continues to rely on whatever
  assessment Codex already performs for it today.

**`NOT_APPLICABLE` and `NOT_EXECUTED` are never equivalent to `PASS`,
anywhere in this specification's logic.** Concretely, the per-round,
per-AC rollup `runtime_evidenced_ac_status: dict[str, str]` used by §14's
Codex contract check is computed, deterministically, as:

- An AC ID is **absent** from this mapping's domain entirely if no
  declared check names it (`NOT_APPLICABLE` — Codex's assessment of that
  AC is unconstrained by this specification).
- An AC ID present in the mapping resolves to `"PASS"` **only if every**
  check that names it has `status="PASS"`.
- It resolves to `"FAIL"` if **any** check that names it has
  `status="FAIL"`.
- It resolves to `"NOT_EXECUTED"` if no mapped check is `"FAIL"` but at
  least one mapped check is `"NOT_EXECUTED"`.

**Codex contract, restated precisely (carried from v0.1, unchanged in
substance, now stated against the four-state model):** for every AC ID
present in `runtime_evidenced_ac_status`'s domain, a Codex
`acceptance_criteria` entry asserting `met=true` is a **contract
violation** (`FAILED`, the same treatment `_validate_review_payload`
already gives every other "contradictory APPROVE" case) unless that AC's
rollup status is exactly `"PASS"` — `"FAIL"` and `"NOT_EXECUTED"` block
`met=true` identically to each other, and an AC `NOT_APPLICABLE` to
Runtime Verification is never constrained by this rule at all. A
`met=false` assessment for any of these is unaffected — Codex remains
free to return `CHANGES_REQUIRED` citing real evidence, exactly as today.

## 14. Codex Review Integration

Codex is never the component that generates its own browser evidence —
it only ever *reviews* what PEOS already collected, exactly the same
relationship it already has to `pytest`/lint/build output.

- **Round Packet extension.** One new element is added to the Round
  Packet (SPEC-004 Requirement 17), rendered into every prompt exactly
  like the existing eleven: a `RuntimeEvidenceRef` carrying the staged
  workspace-relative path to this round's `evidence.json`/screenshots
  directory, its recorded SHA-256 hash (re-verified immediately before
  this invocation, §9), the overall `execution_integrity_passed` flag,
  and a short per-check summary line (`check_id`, `kind`, `status`,
  `related_ac_ids`, including any `NOT_EXECUTED` check) for every check
  in this round's evidence — rendered the same way
  `render_register_for_prompt`/`render_disputes_for_prompt` already
  render other Round Packet elements as literal prompt text, not merely
  held in a dataclass a prompt builder forgets to include.
- **Contract: a runtime-evidenced AC's `met=true` requires a `"PASS"`
  rollup.** `_validate_review_payload` (`peos/codex_agent.py`) gains one
  additional, orchestrator-supplied input: `runtime_evidenced_ac_status`
  (§13). This is the direct, mechanical closure of the originating
  brief's Requirement 9: "Ensuring Codex cannot silently claim runtime
  criteria passed without evidence."
- **No new Codex tool, sandbox relaxation, or MCP grant.** Codex's own
  invocation (`build_codex_command`) is unchanged; it reads the staged
  evidence through the same file-read capability it already has inside
  the isolated workspace, not through any new capability this
  specification grants it.
- **Evidence staged, never streamed through agent conversation.** Per
  SPEC-004's own standing rule ("agent conversation history is not, and
  has never been, an authoritative context channel"), the evidence Codex
  reviews is the orchestrator-written file on disk at the time of its
  invocation — re-staged fresh for every round exactly like the
  governing specification and static-context artifacts already are, not
  carried forward from a prior round's prompt text.

## 15. Human-Gate Semantics (hardening item I)

This specification adds exactly **one** new Human Gate to SPEC-004's
catalog (which itself extends SPEC-001 Section 7):

| ID | Condition | Status |
|----|-----------|--------|
| 12 | A declared Runtime Verification line names a `kind` outside the fixed V1 catalog, omits a required parameter for its declared `kind`, or names an `ac=` value the governing specification does not itself declare — i.e., a runtime requirement that cannot be *deterministically interpreted* because of a decision-bearing specification defect | **NEW** |

Resolved explicitly, consistent with the rest of the catalog's precedent
(Gate #11's missing-static-context-artifact), by the Human Engineering
Lead either revising the specification to use a supported catalog entry
with a complete, valid parameter set, or approving a reviewed extension
to the catalog (a `peos/` code change, not a configuration flag) — never
silently treated as "no runtime checks declared" and never silently
treated as satisfied.

**What is deliberately *not* a new Human Gate — restated per the Human
Engineering Lead's explicit instruction, as an exhaustive list for this
specification's scope:**

- Missing tooling (Playwright/Chromium not installed or mismatched) —
  execution-integrity `FAILED`.
- Sandbox failures (Seatbelt unavailable, profile build failure) —
  execution-integrity `FAILED`.
- Browser failures (launch failure, crash/disconnect, cleanup that
  cannot be verified) — execution-integrity `FAILED`.
- Ordinary product check failures (an element missing, an overflow
  detected, an `experiment_run` result that did not change) — ordinary
  Category-B evidence for Codex, not a gate, not `FAILED`.
- Any other machine-resolvable execution failure named in §6/§12 —
  `FAILED`, by the classification already stated there.
- Aesthetic/design-intent judgment (Non-Goal 1) — the existing final
  Human Engineering Lead approval step, unchanged, not a new gate.

## 16. Codex Convergence (hardening item H)

Runtime Verification does not replace Codex. It is one more evidence
source inserted into the existing SPEC-004 bounded convergence loop,
which this specification leaves structurally unchanged:

```
Claude implementation
  -> full deterministic verification
  -> full applicable Runtime Verification   (NEW -- this specification)
  -> Round Packet (now including RuntimeEvidenceRef)
  -> Codex review
  -> Claude remediation when required
  -> rerun deterministic verification
  -> rerun full applicable Runtime Verification   (NEW)
  -> Codex closure review
  -> repeat within the configured convergence bound (SPEC-004 max_cycles)
```

This is the same cycle-0 + bounded-remediation-cycle shape SPEC-004
already defines; Runtime Verification occupies exactly the position
deterministic verification already occupies relative to each Codex call
— before it, never instead of it, and its own execution-integrity gate is
independent of, and precedes, that round's Codex call exactly like
deterministic verification's gate already does.

**Outstanding Findings Register reconciliation — vocabulary mapping,
not a new vocabulary.** SPEC-004's Outstanding Findings Register already
requires every Codex review round to reconcile every prior
BLOCKER/MAJOR finding with an explicit disposition
(`peos/findings_register.py`'s existing `VALID_DISPOSITIONS`:
`RESOLVED`, `ACCEPTED_RECLASSIFICATION`, `HUMAN_DECISION_REQUIRED`), with
omission leaving a finding `OUTSTANDING`. This specification introduces
**no new disposition vocabulary** — the Human Engineering Lead's
requested reconciliation language maps onto the existing, already-
implemented enum exactly:

| Human Engineering Lead's term | SPEC-004's existing implementation |
|---|---|
| `CLOSED` | `RESOLVED` |
| `SUPERSEDED_WITH_EXPLANATION` | `ACCEPTED_RECLASSIFICATION` (a named, explained downgrade/supersession — already requires a `note`) |
| `STILL_OUTSTANDING` | the absence of any disposition — the existing `OUTSTANDING` state |

Introducing a second, parallel set of literal strings alongside
`peos/findings_register.py`'s already-implemented `VALID_DISPOSITIONS`
would itself be an internal-consistency defect; this specification
instead reuses the existing enum and states the mapping once, here, so
no new code or prompt text need ever emit a string the real schema does
not already accept. The existing rule that **new findings are allowed
only when justified by changed implementation or newly available
evidence**, and that **a remediation cycle must not become an unrelated,
fresh, broad review**, is SPEC-004's own standing behavior (its
Evaluation Precedence, Requirement 22) and is unchanged by this
specification; Runtime Verification simply supplies one more kind of
"newly available evidence" a later review may legitimately cite.

**Final delivery gate, restated precisely (Codex Round 1 Finding 10,
closed — the original wording promised an automatic continuation the
real baseline does not provide).** Per `ENGINEERING.md`'s Definition of
Done: final engineering delivery remains prohibited unless the terminal
state is `CODEX_APPROVED`. `HUMAN_GATE` never substitutes for final Codex
approval — but, exactly as SPEC-004 already specifies and this
specification changes nothing about, `HUMAN_GATE` **is terminal for the
run that hit it**: SPEC-004 Requirement 13 explicitly defers
programmatic (Tier-2) resume, and `peos/workflow.py`'s `gate()` returns a
final `RunResult` with no code path that reopens the same run's
isolated workspace or re-invokes Claude/Codex within it afterward. What
actually happens after a human supplies the genuinely required decision
(including the one new Human Gate this specification adds, §15) is: the
human acts outside PEOS — revising the specification, making an
architecture call, or, for Gate #12/§22, authorizing the one named
product-code change — and then starts a **new, separately-initiated**
PEOS invocation, which re-enters Planning (picking up the revised
specification/decisions via Context Recovery) and proceeds through
implementation, verification (deterministic and runtime), and Codex
review from there. `HUMAN_GATE` therefore never bypasses the final Codex
gate — no engineering delivery reaches the Human Engineering Lead without
eventually also reaching `CODEX_APPROVED` — but it does not resume *the
same run*, and this specification introduces no new continuation
mechanism beyond the one, separately-initiated-run behavior SPEC-004
already provides.

## 17. SPEC-005 Dogfood Acceptance Scenario

This is the concrete end-to-end scenario this specification exists to
make possible, stated against the real SPEC-005 gap (§2):

1. SPEC-005's 03 ANALYZE / Energy Deficit slice is implemented by Claude
   (already true today, per `docs/validation/SPEC-005-validation.md`).
2. Deterministic verification passes: `pytest -q`;
   `npm run lint && npm run typecheck && npm run build`.
3. Planning's Runtime Plan (resolved from a SPEC-005 revision declaring
   the `### Runtime Verification` checks this specification enables —
   out of scope for *this* document, but the mechanism this document
   defines is what such a revision would use) names: one `page_load`
   check against the baseline run with landmarks covering
   `EventBanner`/`TelemetryChart`/`EnergyDeficitAnalysis` in that order
   (evidence for AC-001), one `experiment_run` check with a
   `final_fraction` different from the baseline (evidence for AC-002's
   "actual simulation-derived values" claim being runtime-observable, not
   only statically inspectable), and two `viewport_overflow` checks —
   `desktop` and `mobile` (both evidence for the horizontal-overflow
   half of AC-012 specifically — §10's scope note on this check kind;
   not evidence for a "clipped text" claim, which this V1 catalog does
   not check).
4. Runtime Verification resolves the backend's ephemeral loopback port,
   starts it, builds/starts the production frontend against that
   resolved origin, waits for both to become ready, launches an
   environment-frozen Chromium, and executes the four declared checks in
   order, each capturing a structured measurement, a corroborating
   screenshot, and console/page/network-attempt state.
5. A `RuntimeEvidence` package is produced: in the passing case, all four
   checks `status="PASS"`; staged into the workspace and persisted under
   `.peos/runs/<run_id>/runtime-evidence/`, with every artifact hashed.
6. Codex's independent review receives this evidence via its Round Packet
   (§14), can now evaluate AC-001/AC-002/the horizontal-overflow half of
   AC-012 against **actual** evidence rather than code-inspection-only
   reasoning, and (if a future SPEC-005 revision's own `ac=` mapping
   names AC-012 for these two checks) its `acceptance_criteria`
   assessment for AC-012 with `met=true` is only contractually valid
   because both `viewport_overflow` checks actually rolled up to
   `"PASS"` (§13) — not because Codex merely asserted it; any remaining
   "clipped text" claim within AC-012's own text is not covered by this
   mechanism and would need either a code-inspection basis or a future
   catalog extension (§10, §23) before it could be runtime-evidenced the
   same way.
7. If a remediation cycle is required for an unrelated finding, Runtime
   Verification re-runs in full for that cycle (§16) before the closure
   review, so the closure review's AC-012 assessment is backed by
   *that* cycle's evidence, not cycle 0's; the Outstanding Findings
   Register reconciles every prior finding (§16) regardless.
8. The run reaches `CODEX_APPROVED` only once every Outstanding Finding
   is `RESOLVED`/`ACCEPTED_RECLASSIFICATION` and no runtime-evidenced AC
   has a non-`"PASS"` rollup backing a `met=true` assertion; it reaches
   `HUMAN_GATE` only if a genuine human-judgment condition applies (e.g.,
   a physics/architecture escalation unrelated to this mechanism, Human
   Gate #12's decision-bearing specification defect, or the final
   approval step after `CODEX_APPROVED`) — not because PEOS lacked the
   capability to check AC-012 at all, which was the entire premise of the
   original dogfood gap this specification closes.

## 18. Minimal Extension Points in SPEC-001 / SPEC-003 / SPEC-004

Per the Human Engineering Lead's instruction, this section enumerates
exactly what this specification requires of each existing document —
additive extension points, never a rewrite, following the same
discipline SPEC-004 already used toward SPEC-001/SPEC-003.

**SPEC-001.** Section 6's phase diagram and Section 8's Verification
section gain a documented pointer (not a rewrite) that a Category-B
Runtime Verification phase now exists alongside Category-A deterministic
verification, inserted exactly where §16 above states, for V2+ runs that
declare one — the same "supersedes Section 6's phase names for V2 runs"
treatment SPEC-004 already gave SPEC-001's phase table. SPEC-001's own
Section 7 Human Gate catalog gains a pointer that the catalog is
extended (not rewritten) by SPEC-004 and now also by this specification
(Gate #12). **One concrete, normative extension (Codex Round 1 Finding 1,
closed):** `peos/workflow.py`'s existing call to
`reconcile_workspace_to_repo(..., protected_relative_paths=...)` must
also include every path under `peos/` in that frozenset, not only
`GOVERNANCE_ARTIFACTS` and the governing specification — this closes a
real gap the review found in the *existing, already-implemented*
SPEC-001 reconciliation mechanism (it is not specific to Runtime
Verification's own new code, but Runtime Verification's trust-boundary
claim, §10/§11 hardening item A, is the first place in PEOS that
actually depends on this protection holding, which is why this
specification is the one that must state the requirement explicitly).

**SPEC-003.** No functional extension point is required — this
specification introduces no new credential, no new environment variable
exposed to either agent, and invokes neither CLI itself, **except** that
`build_runtime_verification_sandbox_profile` must accept and forward the
same `extra_deny_read_paths` parameter
`build_verification_sandbox_profile`/`sandboxed_verification_command`
already define for denying reads of the resolved `PEOS_CODEX_AUTH_HOME`
directory (SPEC-003 remediation Finding 2) — carried over unchanged in
mechanism, applied to one more sandbox-profile builder (§11, Codex Round
1 Finding 7). SPEC-003's "Security Invariants" section is otherwise
restated as "carried over, unchanged" by this specification, the same
confirmation-not-modification treatment SPEC-004 already gave it.

**SPEC-004.** Four concrete, additive extension points:

1. **Round Packet** (Requirement 17): one new element,
   `RuntimeEvidenceRef` (§14), appended to the existing ten/twelve;
   `peos/round_packet.py`'s `RoundPacket` dataclass and its
   `render_*_for_prompt` family gain one more field and one more
   renderer, following the exact pattern every existing element already
   uses.
2. **`REVIEW_SCHEMA` validation** (`peos/codex_agent.py`,
   `_validate_review_payload`): one new orchestrator-supplied input,
   `runtime_evidenced_ac_status` (§13/§14), checked alongside the
   existing `required_ac_ids` completeness check — no change to
   `REVIEW_SCHEMA`'s JSON shape itself, since the rule constrains an
   *already-present* `acceptance_criteria` entry's `met` value, not a new
   field Codex must emit.
3. **Human Gate catalog** (Model section's table): one new row, Gate #12
   (§15).
4. **Phase table / Delivery Report**: one new phase row ("Runtime
   verification") inserted after "Local verification" at both cycle 0 and
   every remediation cycle; `peos/report.py`'s Delivery Report gains a
   "Runtime evidence" section alongside its existing "Findings and
   resolutions"/"Unresolved MINOR findings" sections, listing each
   round's `RuntimeEvidence` summary and hash.

No other requirement, acceptance criterion, invariant, or limitation in
SPEC-001/SPEC-003/SPEC-004 is touched. The Outstanding Findings Register's
own disposition vocabulary (§16) is reused verbatim, not extended.

## 19. Acceptance Criteria

- [ ] **AC-001** A governing specification with no `### Runtime
  Verification` declaration produces a documented no-op Runtime
  Verification phase (logged, visible in the Delivery Report as "no
  runtime checks declared") and does not block, delay, or alter the
  existing SPEC-001/SPEC-004 phase sequence in any other way.
- [ ] **AC-002** A governing specification declaring one or more
  supported `### Runtime Verification` checks causes Runtime Verification
  to run, for cycle 0, after Local Verification passes and before the
  Codex independent review call.
- [ ] **AC-003** Runtime Verification also runs for every remediation
  cycle whose Runtime Plan declares at least one check, after that
  cycle's Local Verification passes and before that cycle's Codex closure
  review call — unconditionally, not conditioned on which files changed
  (§16).
- [ ] **AC-004** The backend and frontend subprocesses are started with
  `cwd` inside the isolated workspace (never the authoritative
  repository), each bound to an OS-assigned loopback-only port (never
  `0.0.0.0`, never a hardcoded port), and with an environment built from
  `sandboxed_env()` (every existing credential-stripping rule verified
  to still apply, by the same style of test SPEC-003 AC-1/AC-6 already
  use).
- [ ] **AC-005** A simulated backend bind failure produces an
  execution-integrity `FAILED` before any browser is launched, with
  teardown of whichever service did start.
- [ ] **AC-006** A simulated readiness timeout (service never responds
  within the bounded wait) produces an execution-integrity `FAILED`, with
  no automatic retry (Resolved Decision 6), and teardown still runs.
- [ ] **AC-007** A simulated unavailable Seatbelt sandbox (non-macOS, or
  `sandbox-exec` missing) produces an execution-integrity `FAILED` before
  any backend/frontend subprocess is started — never an unsandboxed
  fallback.
- [ ] **AC-008** A simulated missing, mismatched-version, or unlaunchable
  pinned Playwright/Chromium installation produces an execution-integrity
  `FAILED` before any backend/frontend subprocess is started — never an
  auto-install, never an unsandboxed or browser-less fallback, and never
  silently treated as "no runtime checks declared."
- [ ] **AC-009** A `page_load` check's landmark-ordering assertion fails
  (a declared landmark is missing, or present out of the declared order)
  and the check's `status="FAIL"`, `observation` names which landmark/
  ordering expectation failed, and a corroborating screenshot is still
  captured.
- [ ] **AC-010** An `experiment_run` check whose declared selector's
  content does not change after submitting a different `final_fraction`
  produces `status="FAIL"` with that fact in `observation` — never a
  hardcoded assumption about what the new value should specifically be
  (only that it must differ).
- [ ] **AC-011** A `viewport_overflow` check at the `mobile` preset where
  `scrollWidth > clientWidth` (beyond the named epsilon) produces
  `status="FAIL"` with both measured pixel values in `measurements`, and
  this does **not** by itself produce an execution-integrity `FAILED` —
  it is ordinary Category-B evidence (§6) that reaches Codex normally.
- [ ] **AC-012** A check that completes its primary assertion as `PASS`
  but whose page emitted at least one console error-level message or one
  uncaught `pageerror` event during that check's execution still records
  `status="FAIL"` (§8 step 7) — a check is never marked `PASS` merely
  because its own narrow assertion happened to hold.
- [ ] **AC-013** A `RuntimeCheck`'s `action_performed`/`observation`/each
  console, page-error, or blocked-network-request string, given a
  synthetic secret-shaped string injected into any of them (e.g. by a
  page that echoes an environment variable into the DOM), does not
  contain that string verbatim in the persisted `evidence.json` or in
  anything `peos/report.py` renders (same style of test as SPEC-003
  AC-9/AC-10, extended to this new evidence producer).
- [ ] **AC-014** `evidence.json`, its `.sha256` sidecar, and every
  screenshot file are written under
  `.peos/runs/<run_id>/runtime-evidence/<cycle_label>/` (immutable,
  cycle-qualified, never shared across rounds — Codex Round 1 Finding 5),
  with every path component checked individually for a symlink
  (rejected, `FAILED`, exactly like SPEC-004 AC-29 for the Run Ledger)
  and writes performed atomically.
- [ ] **AC-014a** A run with two rounds that both execute Runtime
  Verification (cycle 0 and remediation cycle 1) produces two distinct,
  independently readable evidence directories — `cycle-0/` and
  `remediation-cycle-1/` — and remediation cycle 1's Runtime
  Verification never overwrites cycle 0's already-persisted
  `evidence.json`/screenshots.
- [ ] **AC-015** `.peos/runs/` (already gitignored per SPEC-004
  Requirement 19) covers the new `runtime-evidence/` subdirectory with no
  additional `.gitignore` change required; a completed run's evidence
  directory is confirmed absent from `git status --porcelain` output.
- [ ] **AC-016** Evidence directories are retained/cleaned up on the same
  20-run schedule and by the same run-identification rule as the Run
  Ledger (SPEC-004 Requirement 20); retention cleanup never removes an
  evidence directory for the currently active run, and never removes one
  lacking a recognizable PEOS evidence manifest.
- [ ] **AC-017** The evidence bounds (§9/§12, Resolved Decision 5:
  evidence.json ≤256 KiB, each service's stdout/stderr tail ≤64 KiB, at
  most one screenshot per check, ≤4 MiB per screenshot, ≤10 MiB total
  screenshots per round) are each independently enforced; exceeding any
  one produces `truncated=True` and/or a non-null `omitted_reason` on the
  affected record (never a silent drop with no trace), and never
  truncates a `RuntimeCheck`'s textual fields below `sanitize_human_text`'s
  own existing bound.
- [ ] **AC-018** `evidence.json` plus its screenshots are staged, as a
  read-only copy, into the isolated workspace at a fixed, documented path
  before the corresponding Codex call for that round, with the staged
  copy's SHA-256 hash confirmed equal to the authoritative `.peos/runs/`
  copy's recorded hash.
- [ ] **AC-019** A staged evidence copy whose hash no longer matches the
  authoritative copy's recorded hash (simulated drift between staging and
  the next consuming invocation) produces an execution-integrity `FAILED`
  before that invocation — never a silent re-hash, never a Human Gate
  (§9 identity re-verification, mirroring SPEC-004 AC-39).
- [ ] **AC-020** The staged evidence copy inside the isolated workspace is
  never copied back onto the authoritative repository by
  `reconcile_workspace_to_repo`, at any outcome (same exclusion rule as
  SPEC-004 AC-36 already applies to `.peos/runs/` itself).
- [ ] **AC-021** The Round Packet for every Claude/Codex invocation in a
  round where Runtime Verification ran contains the new `RuntimeEvidenceRef`
  element (staged path, hash, overall execution-integrity flag, per-check
  summary line including any `NOT_EXECUTED` check), rendered into the
  actual prompt text, not merely held in a dataclass a prompt builder
  forgets to include (same class of test as SPEC-004 AC-37).
- [ ] **AC-022** A Codex review payload asserting `met=true` for an AC ID
  present in `runtime_evidenced_ac_status`'s domain while that AC's rollup
  status is `"FAIL"` or `"NOT_EXECUTED"` is rejected as a contract
  violation (`FAILED`), never accepted as a valid `APPROVE` component —
  the direct test of §14's central rule and the originating brief's
  Requirement 9.
- [ ] **AC-023** The same AC ID asserted `met=false` by Codex, with the
  same non-`"PASS"` rollup, is accepted normally and may legitimately
  coexist with an overall `CHANGES_REQUIRED` verdict.
- [ ] **AC-024** A Codex review payload asserting `met=true` for a
  runtime-evidenced AC ID when that AC's rollup status **is** `"PASS"`
  for the current round is accepted normally (no new rejection introduced
  for the passing case).
- [ ] **AC-025** An AC ID that no declared runtime check names at all
  (`NOT_APPLICABLE`, §13) is absent from `runtime_evidenced_ac_status`'s
  domain and is never constrained by AC-022/AC-023/AC-024's rule — Codex's
  assessment of it proceeds exactly as it would absent this specification.
- [ ] **AC-026** A `### Runtime Verification` declaration naming a `kind`
  outside the fixed V1 catalog (§10) produces `HUMAN_GATE` #12 before any
  workspace runtime services are started, naming the unrecognized `kind`
  verbatim (sanitized/bounded) in the gate reason.
- [ ] **AC-027** A declared check line missing a required parameter for
  its `kind` (e.g. `experiment_run` with no `final_fraction`) produces
  the same `HUMAN_GATE` #12 treatment, never a default-substituted
  parameter value.
- [ ] **AC-028** A declared check line naming an `ac=` value that is not
  in the specification's own numbered acceptance-criteria set produces
  the same `HUMAN_GATE` #12 treatment — never silently accepted with an
  orphaned AC reference.
- [ ] **AC-029** Teardown (browser close, subprocess `SIGTERM`/`SIGKILL`
  to each managed process group, cleanup verification) is confirmed to
  run after: a passing run, a run with at least one `FAIL`-status check,
  an execution-integrity `FAILED`, a simulated unhandled exception raised
  mid-phase, and a simulated process-interruption signal — five
  independent test cases, each asserting no backend/frontend process or
  process-group member remains alive afterward.
- [ ] **AC-030** A simulated teardown that cannot confirm a port was
  released, or cannot confirm the process group has no live members,
  itself produces an execution-integrity `FAILED` for that round — even
  when every declared check's own `status` was `"PASS"` — and does not
  raise a second exception or hang the run.
- [ ] **AC-031** No code path in `peos/runtime_services.py` or
  `peos/runtime_browser.py` passes `claude`'s or `codex`'s authentication
  environment variable, or any `CREDENTIAL_ENV_DENYLIST`/
  `AMBIENT_AGENT_AUTH_DENYLIST` entry, into a started backend/frontend
  subprocess or the browser process, under any condition including
  failure.
- [ ] **AC-032** The extended Seatbelt profile
  (`build_runtime_verification_sandbox_profile`) denies writing to
  `repo_root` even when `repo_root` is nested under one of the profile's
  own broader write-allow paths (same `last-match-wins` re-deny pattern
  and the same empirical test style as
  `tests/test_peos_sandbox.py::test_malicious_command_cannot_write_to_a_repo_root_nested_under_an_allowed_temp_directory`).
- [ ] **AC-033** A live (real, non-faked) backend/frontend subprocess
  started under the extended profile can reach `127.0.0.1` (its own
  assigned port) but cannot reach a real external destination (e.g.
  `1.1.1.1:443`) at the OS layer — the same empirical loopback-only
  verification style as the existing
  `test_malicious_command_cannot_reach_the_network` /
  `test_benign_command_can_still_use_a_loopback_socket` pair, extended to
  this new profile.
- [ ] **AC-034** A live Playwright browser context, given a page that
  attempts to fetch a real external destination, has that request
  aborted by the application-layer interception (§11 item G) and the
  attempted destination recorded in `blocked_network_requests` — the
  independent, redundant second layer of AC-033's defense-in-depth model.
- [ ] **AC-035** `.peos/runs/<run_id>/runtime-evidence/` and every path
  under it reject a symlink at any path component (same filesystem test
  style as SPEC-004 AC-29), producing `FAILED` and never following or
  writing through the symlink.
- [ ] **AC-036** A Playwright `TimeoutError` fixture where the subsequent
  liveness probe succeeds is classified as an ordinary `status="FAIL"`
  product-observation result; the same fixture with the liveness probe
  failing (simulated browser disconnect) is classified as an
  execution-integrity `FAILED` — two independent test cases proving §6's
  classification procedure is applied, not a uniform treatment of every
  timeout.
- [ ] **AC-037** The frozen browser-environment settings (§10 item E —
  viewport, device scale factor, locale, timezone, reduced-motion) are
  confirmed actually applied to the launched browser context (read back
  via `page.evaluate` of the relevant `window`/`navigator`/media-query
  properties), not merely requested, and are recorded verbatim in
  `RuntimeEvidence.browser_environment`.
- [ ] **AC-038** `viewport_overflow`'s pass/fail determination is proven,
  by code inspection, to come from `page.evaluate`'d
  `scrollWidth`/`clientWidth` values recorded in `measurements` — never
  from any form of screenshot/pixel inspection — for every catalog check
  present in V1.
- [ ] **AC-039** A fixture simulating a candidate workspace whose own
  copy of `peos/runtime_catalog.py` has been edited to always report
  `PASS` is proven, by a test that imports and runs the real orchestrator
  against that fixture workspace, to have **no effect** on the result —
  the orchestrator's already-imported catalog governs, not the
  workspace's copy — the direct test of §10 hardening item A's trust
  boundary.
- [ ] **AC-040** The full existing PEOS test suite
  (`tests/test_peos_*.py`) remains green with Runtime Verification's
  Runtime Plan empty/absent for every existing fixture specification —
  i.e., this specification changes no observable behavior for a
  specification that does not opt in (AC-001's stronger, regression-level
  restatement).
- [ ] **AC-041** No change in this specification's eventual implementation
  alters AI Power Lab simulation physics, backend/frontend product
  behavior, Scenario A/SPEC-002 behavior, or `.github/workflows/ci.yml`
  — **except** the one named, separately-authorized `backend/app.py`
  CORS environment-variable addition (Resolved Decision 3, §10, §22 item
  1), which is the single, explicitly-scoped, default-off product-code
  change this specification's ephemeral-ports design requires (Codex
  Round 1/Round 2 Finding 9): it is excluded from this AC's scope by
  name, not a silent exception, and it changes observable backend
  behavior only when the new environment variable is actually set by
  Runtime Verification's own subprocess launch, never by default.
- [ ] **AC-042** No change in this specification's eventual implementation
  adds a new credential, environment variable exposed to either *agent*,
  MCP server grant, or tool grant to either agent, or to the orchestrator
  process, beyond what SPEC-003/Decision-0002 already allow (manual diff
  review, same style as SPEC-004 AC-17) — this is distinct from, and does
  not authorize, the one named, separately-flagged `backend/app.py` CORS
  environment-variable addition (§10/§22), which is a product-code
  change requiring its own, separate sign-off, not an agent-facing
  credential or tool grant.
- [ ] **AC-043** The SPEC-005 dogfood acceptance scenario (§17) is
  demonstrable end-to-end against a test fixture specification shaped
  like SPEC-005's `### Runtime Verification` declaration (real or
  closely modeled): `page_load`, `experiment_run`, and both
  `viewport_overflow` checks all produce evidence, that evidence reaches
  a faked Codex call's Round Packet, and a faked Codex `APPROVE` with
  `met=true` for the viewport AC is accepted only when both
  `viewport_overflow` checks roll up to `"PASS"` in the fixture.
- [ ] **AC-044** The Outstanding Findings Register reconciliation table
  rendered into the Delivery Report (§16, §18) uses exactly
  `peos/findings_register.py`'s existing `VALID_DISPOSITIONS` strings
  (`RESOLVED`, `ACCEPTED_RECLASSIFICATION`, `HUMAN_DECISION_REQUIRED`)
  plus the existing implicit `OUTSTANDING` state — never a second,
  parallel vocabulary — confirmed by a test asserting no new literal
  disposition string is introduced anywhere in `peos/`.
- [ ] **AC-045** (Codex Round 1 Finding 1.) A fixture candidate workspace
  that edits any file under `peos/` is proven, by a test against the
  real `reconcile_workspace_to_repo`/`protected_relative_paths` call
  site in `peos/workflow.py`, to have that edit reported in
  `blocked_governance_mutation` and never copied onto the authoritative
  repository's working tree, under every terminal outcome
  (`APPROVED`, `FAILED`, and `HUMAN_GATE` each independently tested) —
  the direct test of the corrected trust-boundary claim in §10/§11.
- [ ] **AC-046** (Codex Round 1 Finding 2.) A fixture where the liveness
  probe's own `page.evaluate` call blocks indefinitely (simulating a
  candidate page that has frozen the renderer's main thread) is proven
  to be force-terminated by the orchestrator-enforced watchdog within
  its named bound and classified as an execution-integrity `FAILED` —
  never left pending, and never dependent on any Playwright-native
  timeout argument for the call that hangs.
- [ ] **AC-047** (Codex Round 1 Finding 3, first half.) A liveness probe
  that fails with a transient, non-connection error (e.g. a simulated
  "execution context was destroyed" exception during an in-flight
  navigation) is retried exactly once, immediately, within the same
  watchdog budget; a second consecutive occurrence of the same
  transient error is classified as an execution-integrity failure, not
  retried again.
- [ ] **AC-048** (Codex Round 1 Finding 6, check-count bound.) A Runtime
  Plan declaring 21 checks (one above the fixed cap) is rejected at
  Planning as `HUMAN_GATE` #12, before any workspace runtime service is
  started; a Runtime Plan declaring exactly 20 is accepted.
- [ ] **AC-049** (Codex Round 1 Finding 6, hash placement.) `evidence.json`
  as persisted contains no field whose value is a hash of its own
  serialized bytes; the SHA-256 hash of `evidence.json` is written only
  to a separate sidecar file (`evidence.json.sha256`) alongside it.
- [ ] **AC-050** (Codex Round 1 Finding 7.) A live, platform-gated test
  demonstrates that a backend or frontend subprocess started under
  `build_runtime_verification_sandbox_profile`, given a configured
  `PEOS_CODEX_AUTH_HOME` pointed at a directory **outside** the named
  real-`$HOME` credential paths, cannot read a file inside that
  directory — the same empirical style as the existing
  `extra_deny_read_paths` tests for deterministic verification's own
  profile, extended to this new one.
- [ ] **AC-051** (Codex Round 1 Finding 8.) A live Playwright test
  confirms: (a) the context-level route handler is active for a page's
  very first navigation in that context (registered before the page is
  created); (b) a context launched with `service_workers="block"` never
  registers a service worker for a page that attempts to; (c) the
  evidence/documentation for a WebSocket-based non-loopback attempt
  explicitly shows it is denied only at the OS/Seatbelt layer, not
  recorded in `blocked_network_requests` by the application layer —
  confirming the named gap is real and documented, not silently
  papered over by an inaccurate "any non-loopback request is recorded"
  claim.
- [ ] **AC-052** (Codex Round 1 Finding 9, sequencing.) A test asserts
  that both the backend's and the frontend's ports are resolved before
  either subprocess is started (§8 step 3 precedes steps 4/5), and that
  the backend subprocess's environment contains the frontend's resolved
  origin in the named CORS co-requirement variable (once that change is
  authorized and implemented, §22) at the moment the backend process is
  launched, never set or adjusted afterward.

## 20. Verification Requirements

| AC | Verification | Layer |
|----|---------------|-------|
| AC-001–AC-003 | New unit tests in `tests/test_peos_runtime_plan.py` / `tests/test_peos_workflow.py`: empty vs. populated Runtime Plan fixtures, cycle-0 and remediation-cycle phase-ordering assertions with a faked `runtime_verifier` callable | Unit |
| AC-004 | `tests/test_peos_runtime_services.py` (new): assert the subprocess env/cwd/port-resolution passed to a faked process-spawn matches `sandboxed_env()`'s output and the workspace path | Unit |
| AC-005 / AC-006 | `tests/test_peos_runtime_services.py`: faked bind-failure and faked never-ready fixtures | Unit |
| AC-007 / AC-008 | `tests/test_peos_runtime_services.py` / `tests/test_peos_runtime_browser.py`: platform/dependency-unavailable/version-mismatch fixtures, same style as `tests/test_peos_sandbox.py`'s existing `SandboxUnavailableError` tests | Unit |
| AC-009–AC-012 | `tests/test_peos_runtime_browser.py`: one fixture per catalog check kind plus the console/page-error-forces-FAIL rule, against a faked Playwright page object | Unit |
| AC-013 | `tests/test_peos_runtime_evidence.py` (new): synthetic-secret injection into each text-bearing `RuntimeCheck`/`ServiceReadiness` field, same style as SPEC-003 AC-9/SPEC-004 AC-11 | Unit |
| AC-014 / AC-015 / AC-035 | `tests/test_peos_runtime_evidence.py`: real-filesystem symlink/atomicity/`.gitignore` tests, same style as `tests/test_peos_ledger.py`'s existing AC-29/AC-30 tests | Unit |
| AC-016 / AC-017 | `tests/test_peos_runtime_evidence.py`: retention and bounds fixtures (including the `truncated`/`omitted_reason` assertions), same style as SPEC-004 AC-31 | Unit |
| AC-018 / AC-019 / AC-020 | `tests/test_peos_workflow.py`: staged-copy presence/hash-identity assertion, a simulated post-staging drift fixture, and a reconciliation-exclusion assertion, same style as SPEC-004's static-context staging/AC-39 tests | Unit |
| AC-021 | `tests/test_peos_round_packet.py`: assert the new element is present and rendered into prompt text for a round with Runtime Verification evidence | Unit |
| AC-022–AC-025 | `tests/test_peos_codex_agent.py`: `met=true`/`met=false` payload fixtures crossed with PASS/FAIL/NOT_EXECUTED/absent runtime-evidence-status fixtures | Unit |
| AC-026–AC-028 | `tests/test_peos_runtime_plan.py`: unrecognized-kind, missing-parameter, and orphaned-`ac=` fixtures, each asserting `HUMAN_GATE` #12 | Unit |
| AC-029 / AC-030 | `tests/test_peos_runtime_services.py`: five teardown-path fixtures (pass, check-fail, execution-integrity fail, exception, interruption) plus a port-still-bound/process-group-still-alive-after-teardown fixture asserting an execution-integrity `FAILED` | Unit |
| AC-031 | `tests/test_peos_runtime_services.py`: environment-content assertion against a real-looking ambient environment, same style as SPEC-003 AC-6 | Unit |
| AC-032 / AC-033 | `tests/test_peos_sandbox.py` (extended): real, platform-gated `sandbox-exec` invocations against the new profile builder, same empirical style as the existing profile's tests | Unit / real sandbox |
| AC-034 | `tests/test_peos_runtime_browser.py`: real (or faked at the Playwright-API boundary) `page.route` interception assertion against an attempted external request | Unit / real browser |
| AC-036 | `tests/test_peos_runtime_browser.py`: two `TimeoutError` fixtures (live-probe-succeeds, live-probe-fails), asserting the two different classifications | Unit |
| AC-037 / AC-038 | `tests/test_peos_runtime_browser.py`: frozen-environment read-back assertion; code-inspection/static-analysis check that `viewport_overflow`'s assertion path never touches screenshot bytes | Unit / manual code review |
| AC-039 | `tests/test_peos_runtime_catalog_trust_boundary.py` (new): the orchestrator-process-vs-workspace-copy fixture described in the AC itself | Unit |
| AC-040 | `python -m pytest -q` over the full `tests/` directory with every existing fixture specification (no Runtime Plan declared) | Regression |
| AC-041 | Full `python -m pytest -q` plus `npm run lint && npm run typecheck && npm run build`, unchanged from SPEC-003 AC-15/SPEC-004 AC-16 | Regression |
| AC-042 | Manual diff review of `peos/sandbox.py`'s existing `sandboxed_env`/`claude_sandboxed_env`/`codex_sandboxed_env` (no agent-facing change) plus a separate, explicit diff review confined to the one named `backend/app.py` CORS addition, if and when separately authorized | Manual / code review |
| AC-043 | A new integration-style test, `tests/test_peos_runtime_verification_spec005_scenario.py` (new), driving the full phase sequence against a test fixture specification modeled on SPEC-005's actual `### Runtime Verification` shape, with faked (not real) backend/frontend/browser at the lowest layer but real orchestrator logic end-to-end | Scenario validation |
| AC-044 | `tests/test_peos_findings_register.py` (extended) / a repository-wide grep-based test asserting no new literal disposition string appears outside the existing `VALID_DISPOSITIONS` set | Unit |
| AC-014a | `tests/test_peos_runtime_evidence.py`: two-round fixture asserting distinct, non-overwritten per-cycle evidence directories | Unit |
| AC-045 | `tests/test_peos_sandbox.py` / `tests/test_peos_workflow.py` (extended): `peos/`-path edit fixture crossed with each terminal outcome (`APPROVED`/`FAILED`/`HUMAN_GATE`), asserting `blocked_governance_mutation` and no copy-back, same style as the existing `GOVERNANCE_ARTIFACTS` tests | Unit |
| AC-046 / AC-047 | `tests/test_peos_runtime_browser.py`: a hung-`evaluate` fixture (watchdog force-termination) and a transient-context-destroyed-error fixture (single bounded re-probe, then escalation on a second occurrence) | Unit |
| AC-048 | `tests/test_peos_runtime_plan.py`: 20-check and 21-check fixtures, asserting acceptance and `HUMAN_GATE` #12 respectively | Unit |
| AC-049 | `tests/test_peos_runtime_evidence.py`: structural assertion that no key in the persisted `evidence.json` holds that file's own hash, plus presence of the separate `.sha256` sidecar | Unit |
| AC-050 | `tests/test_peos_sandbox.py` (extended): real, platform-gated test with a `PEOS_CODEX_AUTH_HOME` outside the named real-`$HOME` paths, asserting denied reads under the new runtime profile | Unit / real sandbox |
| AC-051 | `tests/test_peos_runtime_browser.py`: real (or Playwright-API-boundary-faked) context-level-routing-before-page-creation assertion, `service_workers="block"` assertion, and a documented/asserted WebSocket-gap test | Unit / real browser |
| AC-052 | `tests/test_peos_runtime_services.py`: port-reservation-ordering and CORS-origin-set-at-launch assertions | Unit |

An opt-in, real-tool contract test (gated by an environment variable the
same way `tests/test_peos_real_cli_contract.py` already gates real-CLI
tests, e.g. `PEOS_REAL_RUNTIME_TESTS=1`) demonstrating a real backend +
real production-built frontend + real pinned Playwright/Chromium run
against this repository's own `frontend`/`backend`, with real ephemeral
ports, is recommended at implementation time, named here as expected but
not itself assigned a new AC number (the same treatment SPEC-003 gave its
own real-CLI contract test, AC-13).

## 21. Independent Review Gate

Per the Human Engineering Lead's explicit instruction, architecture
approval is not implementation authorization. Before any implementation
of Runtime Verification begins, this specification and ADR-0003 must
receive an independent Codex architecture/specification review — using
the existing local PEOS/Codex interface (`codex exec --sandbox read-only`,
the same invocation shape `peos/codex_agent.py` already uses, run as a
standalone, one-off review call against this document and the ADR, not
as a full PEOS implementation run) — focused on: trust boundaries,
failure/result taxonomy, runtime AC/evidence semantics, the sandbox/
network model, evidence integrity, bounded convergence semantics, and
compatibility with SPEC-001/SPEC-003/SPEC-004. If that review returns
blocking findings, this specification and/or ADR-0003 are revised and
resubmitted for a focused re-review, through the same bounded-convergence
discipline SPEC-004 already applies to implementation review (never an
unrelated, fresh, broad review on each pass). Implementation does not
begin until that review closes with no blocking findings. The outcome of
this review (and any resulting revision) is recorded in this
specification's own revision history and, where the Human Engineering
Lead directs, in a project-tracking record outside this document.

## 22. Flagged Items Requiring Separate Confirmation

Named once each above, collected here for visibility:

1. **The `backend/app.py` CORS environment-variable addition** (Resolved
   Decision 3, §10) — a narrow, additive, default-off product-code
   change, **required** by this specification's single adopted ephemeral-
   ports design (not optional, per Codex Round 1 Finding 9 — the earlier
   "interim fixed-port" framing that made it sound optional has been
   removed). **Resolved:** authorized by the Human Engineering Lead and
   implemented exactly as scoped (loopback-only, exact-origin, default-off,
   no credential/network-authority broadening).
2. **The exact pinned Playwright version** (Resolved Decision 1, §10) —
   decided at implementation time, then held fixed; named here so its
   selection is a visible, reviewable act, not an incidental default.
   **Resolved:** `1.49.1` (`requirements.txt`).
3. **The exact evidence bounds** (Resolved Decision 5, §9/§12) — the
   Human Engineering Lead's own stated values, adopted verbatim; flagged
   only in case real evidence sizes during implementation prove one of
   them too tight (e.g. a 4 MiB screenshot bound on a very wide desktop
   viewport capture) and need revisiting. **Resolved:** implemented as
   stated; no revision found necessary, including against real evidence
   from a live Chromium-backed end-to-end run.

## 23. Deferred/Future Work

- **File-diff-to-check scoping**, to avoid re-running every declared
  check on every remediation cycle regardless of which files changed
  (§16) — deliberately not designed in V1; the correctness risk (silently
  skipping a check that should have re-run) outweighs the time saved at
  the current `max_cycles` bound (≤5).
- **Cross-browser coverage** (Firefox/WebKit) — Chromium-only in V1
  (§10); revisit if a future engineering-learning requirement needs it.
- **Visual-regression/pixel-diffing** against a prior run's screenshots
  — not designed; each run's evidence stands on its own, and screenshots
  remain corroborating, never primary, evidence (§10 item E).
- **CI/non-macOS runtime verification** — inherits the existing
  Seatbelt-sandbox macOS-only boundary; a Linux-capable equivalent (e.g.
  a namespace/seccomp-based profile) is a separate, future architectural
  decision, not scoped here.
- **A general runtime-scripting DSL** beyond the fixed three-entry
  catalog — explicitly rejected for V1 (§4); any future extension is a
  reviewed `peos/` code change adding a new named, typed catalog entry,
  never a spec-authored script.
- **A broader network allowance** for pages that legitimately need an
  external resource (e.g. uncached Google Fonts) — not designed; the
  current two-layer loopback-only policy is deliberately conservative,
  and a page depending on live external network at runtime is itself
  arguably a CLAUDE.md "no cloud infrastructure dependency" concern worth
  surfacing to the Human Engineering Lead rather than quietly working
  around.
- **Concurrent PEOS runs on one machine.** Ephemeral ports (Resolved
  Decision 3) substantially reduce, but do not eliminate, cross-run
  collision risk (e.g. two runs' resolved ports could in principle still
  coincide, however unlikely); not specially handled beyond the existing
  "single local operator" assumption SPEC-003's Assumptions section
  already states for the whole system.
- **Programmatic resume of a partially-completed Runtime Verification
  phase** — out of scope, consistent with SPEC-004's Tier-1-only Run
  Ledger posture (Requirement 13).
- **The `backend/app.py` CORS environment-variable addition** (§22 item
  1) — resolved; see §22 item 1.

## Known Limitations

- Runtime Verification is macOS-only in V1, inheriting the exact platform
  boundary the existing deterministic-verification Seatbelt sandbox
  already has (SPEC-001 Finding 1). A specification declaring Runtime
  Verification checks cannot have those criteria automatically satisfied
  on any other host; this is a capability boundary, not a judgment call,
  and is surfaced as `FAILED`, not silently downgraded to manual
  verification.
- The fixed V1 catalog (`page_load`, `experiment_run`, `viewport_overflow`)
  is deliberately narrow. It is sufficient for the SPEC-005 dogfood
  scenario (§17) but does not generalize to arbitrary future interaction
  patterns without a reviewed catalog extension (§23).
- Chromium's own internal process sandbox is not independently
  characterized here beyond what Playwright's own documented launch
  behavior states; the Seatbelt profile around the browser process, plus
  the application-layer network interception (§11 item G), are the
  structural backstops that do not depend on that characterization, the
  same accepted-residual-risk framing SPEC-001/SPEC-003 already use for
  Claude's/Codex's own CLI sandboxing.
- A page that legitimately depends on a non-loopback network resource at
  runtime will have that resource fetch aborted under this
  specification's two-layer network policy; this surfaces as a blocked
  request in the evidence (and likely a `FAIL`-status check), not as a
  silently widened network allowance.
- Runtime Verification's AC-completeness contract check (§13/§14) only
  constrains `met=true` for AC IDs present in `runtime_evidenced_ac_status`'s
  domain — an AC the governing specification did not map to any declared
  runtime check (`NOT_APPLICABLE`) is unaffected by this specification
  and continues to rely on whatever assessment Codex already performs for
  it today.
- Ephemeral ports for both services (Resolved Decision 3) **requires**
  the one named `backend/app.py` CORS change (§22 item 1) — this is a
  required co-requirement, not an optional enhancement (Codex Round 1
  Finding 9 corrected an earlier draft that inconsistently floated an
  "interim fixed frontend port" alongside AC-004's absolute
  no-hardcoded-port requirement; that inconsistency is removed, not
  resolved by weakening AC-004). Implementation of this specification
  depended on the Human Engineering Lead separately authorizing that one
  named product-code change; that authorization was given, and the
  change was implemented exactly as scoped (§22 item 1).
- The evidence bounds (§9, §12) are the Human Engineering Lead's own
  specified defaults; §22 item 3 names the one circumstance (an
  unusually large desktop screenshot) that might require revisiting them.
