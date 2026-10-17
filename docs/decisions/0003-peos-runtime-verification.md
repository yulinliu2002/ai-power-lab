# 0003 — PEOS Runtime Verification: browser/dependency choice, execution model, and trust boundary

**Status:** Accepted and implemented.
`docs/specifications/SPEC-006-peos-runtime-verification-v1.md`, the
specification this decision record supports, has since reached **Approved**
status: the independent Codex architecture/specification review (SPEC-006
§21) closed with no blocking findings, implementation followed under that
approval, a subsequent independent Codex implementation review (four
focused rounds, covering the implementation itself and a real
Chromium-backed live end-to-end Runtime Verification run against this
repository's own frontend/backend) closed with a final `APPROVE` verdict
and zero outstanding findings, and the Human Engineering Lead has given
final acceptance. The architectural decisions below were not altered by
any of that review activity; only implementation-level code closed the
findings it raised.

**Remediation note.** An independent Codex architecture review of this
record alongside SPEC-006 v0.2 returned `CHANGES_REQUIRED` with 11
findings; several bear directly on Decisions 3, 6, and 7 below, which
this revision corrects in place (narrower/corrected claims, never a
weakened one) rather than superseding — see SPEC-006's own "Codex
Architecture Review — Round 1" section for the complete, numbered
mapping. This record's decisions were not themselves wrong in direction;
several were stated with an enforcement claim the underlying mechanism
did not yet make true, which is now fixed. Three further focused Codex
re-review rounds (SPEC-006's "Round 2" section and two narrower
follow-ups) closed the remaining items — one real wording gap (SPEC-006
AC-041 needed the same by-name CORS exemption AC-042 already had) and a
set of stale cross-reference corrections the port-reservation reordering
introduced — ending in an `APPROVE` verdict with zero outstanding
findings. The independent review gate (SPEC-006 §21) is satisfied as of
this text; this record's own **Status: Accepted** reflects the Human
Engineering Lead's architectural decisions, not a claim that SPEC-006 is
itself approved for implementation — that remains a separate,
not-yet-given approval (`ENGINEERING.md`'s Engineering Specification
Standard).

## Context

PEOS (SPEC-001, hardened by SPEC-003, generalized by SPEC-004) can
produce deterministic verification evidence and an independent Codex
review, but has no way to produce *runtime* evidence — starting the
actual application, loading pages in an actual browser, exercising an
actual interactive control, and observing actual viewport/layout/console
behavior. A real SPEC-005 dogfood run hit exactly this gap: AC-012 ("no
horizontal overflow or clipped text") could not be verified because
nothing could start a dev server or drive a browser, so it sat in a
manual/observational limbo neither agent could legitimately close
(`docs/validation/SPEC-005-validation.md`'s "Outstanding" section records
this directly). The Human Engineering Lead's own stated philosophy for
PEOS is that "Human gate" must not mean "the agents currently lack a
tool" — if a task can reasonably and safely be executed and verified by
machine, PEOS should provide the capability.

SPEC-006 v0.1 proposed this capability with six design choices left
explicitly open for Human Engineering Lead sign-off (browser-automation
dependency, runtime mode, port strategy, check-authoring model, evidence
bounds, retry policy). This record freezes those six choices, plus five
further architectural properties the Human Engineering Lead's review
identified as requiring explicit, durable statement rather than only
living inside a long specification document: the trust boundary between
the PEOS control plane and the candidate workspace it verifies; the
Execution-Integrity-vs-Product-Observation distinction (including a
deterministic timeout-classification rule, since not every Playwright
timeout means the same thing); and the two-layer (OS + application)
network containment model.

This record exists separately from SPEC-006 because these are durable
architectural commitments future specifications and future PEOS
maintainers need to find quickly (`ENGINEERING.md`'s Source-of-Truth
Hierarchy ranks "Approved Architecture / Engineering Decision" above "this
document's own Acceptance Criteria"), not implementation detail scoped to
one specification's lifetime.

## Decision

1. **Browser-automation dependency: Playwright (Python sync API), with a
   pinned Chromium build, Chromium-only in V1.** No lighter alternative
   satisfies controlled desktop/mobile browser automation without
   reinventing a layout/rendering engine. The dependency is recorded as
   an exact version pin, never a loose range — a routine dependency bump
   is itself a reviewed change, because it also changes which Chromium
   build every piece of evidence in the system depends on. Chromium's
   binary is installed by a separate, explicit, human-run bootstrap step
   (`python -m playwright install chromium`), **never** by PEOS itself
   during a run, under any condition; a missing or version-mismatched
   installation is a fail-closed execution-integrity failure, never an
   automatic install and never a silent "whatever's on `$PATH`" fallback.

2. **Production runtime mode.** Runtime Verification exercises `next
   build` + `next start`, never `next dev` — the artifact actually
   shipped, not a development-mode server with different behavior
   (HMR, unminified output, different error surfacing). Where the
   production build must be re-invoked with a Runtime-Verification-
   specific input (the resolved ephemeral backend origin — see Decision
   3), it re-runs the exact, frozen build script deterministic
   verification already validated succeeds, never substitutes `next
   dev` as a fallback of any kind.

3. **OS-assigned ephemeral ports, loopback-only, for both services, with
   a required (not optional) CORS co-requirement, and both ports
   reserved before either service starts.** Both the backend and
   frontend bind to an OS-assigned port on `127.0.0.1` (never `0.0.0.0`,
   never a hardcoded literal). This eliminates the "a developer's own
   dev server already owns port 8000/3000" collision class and the
   "stale process from a killed run squats on a fixed port" class. It
   has one acknowledged, narrow implication, corrected here from this
   record's original wording (Codex Round 1 Finding 9): `backend/app.py`'s
   current CORS allow-list is a hardcoded literal naming port 3000
   specifically, which cannot vary with an ephemeral frontend port
   without a product-code change. This record does not authorize an
   "interim fixed-port" alternative as a substitute — that framing
   produced a direct contradiction with SPEC-006's own AC-004 and is
   removed, not weakened into. The one coherent design this record
   adopts is: both ports are reserved (bound-and-released) **before
   either subprocess starts**, so the backend's own startup-time CORS
   configuration can already name the frontend's resolved origin; this
   requires the narrow, additive, default-off product-code change (one
   environment variable `CORSMiddleware` reads, appending to — never
   replacing — the existing hardcoded list) as a **required
   co-requirement** of adopting ephemeral ports at all, not an optional
   nicety. This record accepts that this change is the correct
   resolution, but does not itself authorize making it — that
   authorization is the one item tracked separately (SPEC-006 §22 item
   1), because it touches product code, not PEOS orchestration code, and
   this record's scope is PEOS architecture. Implementation does not
   proceed past port reservation without it.

4. **Fixed, typed, versioned check catalog — no scripting DSL.** Exactly
   three V1 check kinds: two generic (`page_load`, `viewport_overflow`)
   and one AI-Power-Lab-specific (`experiment_run`), each a typed
   parameter dataclass, each carrying an explicit catalog-version
   constant recorded in every evidence record. A specification may only
   select from this catalog and supply typed parameters; it can never
   author new browser-interaction logic. Extending the catalog is a
   reviewed `peos/` code change, never a spec-authoring feature — the
   same discipline `peos/verification_plan.py`'s fixed text conventions
   and SPEC-004's `DISPUTE[...]` convention already establish elsewhere
   in PEOS.

5. **Execution-Integrity vs. Product-Observation, with a deterministic,
   watchdog-enforced timeout-classification rule.** Whether the Runtime
   Verification *harness* itself completed (execution integrity — a
   failure here is `FAILED`, gating Codex exactly like deterministic
   verification already does) is a different question from what a
   *successfully running* check *observed* (product observation —
   ordinary evidence for Codex's review, never itself a `FAILED`). Not
   every Playwright `TimeoutError` means the same thing, and — corrected
   from this record's original wording, Codex Round 1 Findings 2/3 —
   the classification cannot rest on any single Playwright call's own
   timeout parameter, because at least one call this procedure needs
   (`page.evaluate`, used by the liveness probe itself) has none in the
   Python sync API. The actual mechanism is an orchestrator-enforced
   wall-clock watchdog, external to Playwright, bounding every blocking
   call this procedure makes; within that bound, a three-way liveness
   probe (connection-level failure → execution integrity;
   one bounded, transient-error re-probe; else alive → ordinary
   `FAIL`-status product observation) decides which classification
   applies, with the probe's own possible transient-but-non-fatal
   outcome (e.g. a destroyed execution context mid-navigation) given
   exactly one immediate re-attempt before being treated as a
   connection-level failure. This procedure is implemented once,
   centrally, never duplicated per check kind.

6. **Trusted-control-plane ownership of the check catalog, harness, and
   classification logic — claim narrowed to what the mechanism actually
   enforces, plus one new enforcement requirement (Codex Round 1 Finding
   1, corrected from this record's original wording).** The application
   under test (backend/frontend source) is untrusted candidate code,
   exactly like code `pytest`/`npm run build` already execute. The code
   that *decides what counts as passing* — the check catalog, the
   harness that runs it, the classification/evidence-integrity logic —
   is not, and cannot be, by construction, **for the run that is
   currently executing**: it is imported by the orchestrator process from
   the authoritative checkout's own `peos/` directory before the
   isolated candidate workspace is ever created, and the orchestrator
   never re-imports or re-executes any `peos/` code from inside that
   workspace at any point in that same run. This record's original
   wording overstated what happens *after* that run: `peos/workflow.py`'s
   `reconcile_workspace_to_repo` already copies working-tree changes back
   onto the authoritative repository on `APPROVED`, `FAILED`, **and**
   `HUMAN_GATE` — not only after a human-reviewed merge — and nothing
   today protects `peos/` itself from that copy-back the way
   `GOVERNANCE_ARTIFACTS` protects `CLAUDE.md`/`AGENTS.md`/
   `ENGINEERING.md`/the governing specification. This record therefore
   adds the enforcement this claim actually needs: **every path under
   `peos/` is added to the same `protected_relative_paths` reconciliation
   block** `GOVERNANCE_ARTIFACTS` already uses, so a candidate change to
   the catalog/harness/classification logic is reported as a blocked
   governance mutation, never silently copied onto the authoritative
   repository, under any outcome. With that requirement in place, the
   corrected claim holds for the current run and every subsequent one:
   no not-yet-human-applied candidate change to this code can ever reach
   the authoritative repository, let alone judge a future run — stated
   explicitly because Runtime Verification is the first PEOS capability
   whose own trustworthiness as a judge is as safety-critical as what it
   judges.

7. **Network containment: two independent layers, not one — with named,
   explicit gaps in the application layer rather than a claim of
   exhaustive coverage (corrected from this record's original wording,
   Codex Round 1 Finding 8).** The existing macOS Seatbelt verification
   sandbox's loopback-only network exception (already present for
   Next.js's own internal build-worker IPC) is generalized, unchanged in
   kind, to cover the backend/frontend services and the browser process
   at the OS level — this layer has no known gap for the traffic classes
   named below. Independently, the Playwright-controlled browser context
   installs its own request-interception rule, registered at the
   context level before any page exists and paired with
   `service_workers="block"`, that aborts any non-loopback HTTP(S)
   request at the application layer and records the attempt as
   evidence. This second layer's coverage is **not** exhaustive —
   WebSocket connections are a distinct channel Playwright's `route`
   mechanism does not intercept, and a page opening a non-loopback
   WebSocket relies on the OS layer alone to deny it (which it still
   does). The two layers are therefore complementary, not redundant
   copies of the same guarantee: the OS layer is the one with no known
   gap, and the application layer adds visibility (the attempted
   destination recorded as evidence) for the traffic class it can see.
   Runtime Verification gains no credential, no MCP access, and no
   additional external service authority of any kind.

8. **Evidence bounds and never-silent-truncation.** `RuntimeEvidence`
   JSON ≤ 256 KiB; captured service stdout/stderr ≤ 64 KiB per service;
   at most one screenshot per check; ≤ 4 MiB per screenshot; ≤ 10 MiB
   total screenshot evidence per round. Any bound that would otherwise be
   exceeded is represented explicitly in the evidence's own metadata
   (`truncated`/`omitted_reason`) — evidence is never silently truncated
   with no trace that it happened.

9. **No automatic retry of a completed runtime check or service start.**
   Bounded readiness polling during service startup is one wait
   operation with one outcome, not a retry. Re-attempting a check or a
   service start after it has already completed with a timeout or
   failure never occurs.

## Alternatives Considered

- **A general runtime-scripting DSL** letting a specification author
  arbitrary Playwright interaction sequences. Rejected: this is exactly
  the class of "AI-interpreted/open-ended" surface every other PEOS
  spec-text convention deliberately avoids, and CLAUDE.md's "no premature
  abstractions, no frameworks just in case" argues directly against it
  for a V1 whose entire known requirement is three concrete check shapes.
- **`next dev` instead of a production build.** Rejected: dev mode's
  behavior (HMR, unminified output, different error/overlay surfacing)
  is not what ships; evidence collected against it would not
  trustworthily represent the production artifact's behavior.
- **Fixed, well-known ports (8000/3000) instead of ephemeral ones.**
  Considered and rejected in favor of ephemeral ports specifically to
  remove the collision class with a developer's own already-running dev
  servers or a leaked process from a prior killed run; accepted the one
  narrow CORS implication (Decision 3) as the cost of that choice rather
  than reverting to fixed ports.
- **A single, coarser PASS/FAIL check status.** Rejected in favor of the
  four-state model (`PASS`/`FAIL`/`NOT_EXECUTED`/`NOT_APPLICABLE`,
  specified in SPEC-006 §13) because collapsing "never ran" or "not
  claimed at all" into either PASS or FAIL is exactly the kind of
  silent-equivalence this record and SPEC-006 both exist to prevent.
- **Treating every Playwright timeout as an execution-integrity
  failure (fail the whole run), or, conversely, as an ordinary check
  result.** Both uniform treatments were rejected in favor of the
  liveness-probe-based classification in Decision 5, because a uniform
  rule would either (a) turn an ordinary, genuine product defect into a
  hard orchestration failure, or (b) mask a truly unresponsive harness as
  if it had produced valid evidence.
- **A second, independently-authored disposition vocabulary for Codex
  convergence reconciliation** (`CLOSED`/`STILL_OUTSTANDING`/
  `SUPERSEDED_WITH_EXPLANATION`, as originally requested). Rejected in
  favor of reusing SPEC-004's already-implemented
  `RESOLVED`/`ACCEPTED_RECLASSIFICATION`/`HUMAN_DECISION_REQUIRED`
  enum with an explicit mapping (SPEC-006 §16) — introducing a second,
  parallel vocabulary alongside an already-shipped schema would itself be
  an internal-consistency defect.

## Consequences

- Implementing SPEC-006 required one narrow, separately-authorized
  product-code change (`backend/app.py`'s CORS allow-list) as a
  precondition of the ephemeral-ports design this record adopts, not an
  optional enhancement of it (SPEC-006 §22 item 1); that authorization was
  given and the change implemented exactly as scoped.
- Adopting a future change to `peos/runtime_catalog.py` (or any other
  `peos/` module) — including this specification's own eventual
  implementation — now requires the same manual, human-applied-diff
  path `CLAUDE.md`/`AGENTS.md`/`ENGINEERING.md` changes already require,
  because `peos/` is added to `protected_relative_paths` (Decision 6).
  This is a deliberate new cost of the trust-boundary guarantee, not an
  oversight.
- Every future runtime check kind is a reviewed `peos/` code change to
  the typed catalog, never a specification-text feature — this is a
  deliberate ongoing cost (less expressive than a DSL) traded for
  auditability and the "a junior engineer can read every module"
  property CLAUDE.md requires.
- A self-modifying PEOS task that changes `peos/runtime_catalog.py` (or
  any `peos/` module) never has that change judge the very run that
  produced it — this is true by construction (Decision 6), and is worth
  re-confirming by test whenever the module-loading mechanics of the
  orchestrator change in the future.
- The pinned Playwright/Chromium version becomes a piece of durable
  infrastructure state (like the Python/Node toolchain versions already
  implicitly pinned by the repository's own venv/lockfile) that a human
  must deliberately bump, test, and re-approve — it will not silently
  drift.

## Open Items Carried Into SPEC-006 (resolved)

All items originally carried into SPEC-006 as open have since been resolved:

- The exact pinned Playwright version: `1.49.1` (`requirements.txt`).
- The one named `backend/app.py` CORS environment-variable addition:
  authorized by the Human Engineering Lead and implemented exactly as
  scoped (loopback-only, exact-origin, default-off).
- The exact evidence-bound values in Decision 8: implemented as stated in
  SPEC-006 §9/§12, with no revision found necessary.
- Independent Codex architecture/specification review of SPEC-006 and
  this record (SPEC-006 §21): closed `APPROVE`, zero outstanding findings.
- Independent Codex implementation review (not itself an open item at
  acceptance time, since implementation had not yet begun): four focused
  rounds, the last three driven by defects a real live Chromium-backed
  end-to-end run against this repository's own frontend/backend surfaced
  that unit tests alone had not caught (frontend locator mismatches, a
  `page.goto(wait_until="load")` timing race, a worker-subprocess
  environment-sanitization gap, and an incomplete process-group timeout
  cleanup path). Closed `APPROVE`, zero outstanding findings.
  with no blocking findings.
