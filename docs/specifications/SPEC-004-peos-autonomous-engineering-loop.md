# SPEC-004 — PEOS Autonomous Engineering Loop (V2)

**Status:** Draft (Proposed — not approved, not implemented)
**Project:** AI Power Lab
**System:** PEOS Automation V2 (extends `peos/workflow.py`, `peos/cli.py`,
`peos/claude_agent.py`, `peos/codex_agent.py`, `peos/prompts.py`,
`peos/report.py`, `peos/spec.py`; adds `peos/plan.py`, `peos/context.py`,
`peos/ledger.py`, `peos/findings_register.py`, `peos/round_packet.py`,
`peos/static_context.py`)
**Version:** 0.3 (0.2 remediated against independent Codex architecture
review — 1 BLOCKER + 8 MAJOR findings, all closed normatively below; 0.3
closes the three remaining issues from the focused Codex closure review:
cycle acceptance-criteria arithmetic, `HUMAN_DECISION_REQUIRED` blocking
approval, and static-context identity-drift fail-closed behavior)
**Type:** Workflow Infrastructure

---

This specification does not modify the text of `SPEC-001` or `SPEC-003`,
or `docs/decisions/0002`. It proposes an additive generalization of the
state machine those documents already define and implement.
**SPEC-004 EXTENDS SPEC-001. It does not rewrite historical SPEC-001.**
SPEC-001 and SPEC-003 remain the authoritative, currently-running
behavior, and remain authoritative wherever this document does not
explicitly extend their behavior — per `ENGINEERING.md`'s Source-of-Truth
Hierarchy, this document is a proposal, not a change to what is true
today. **No code in `peos/` has been modified to produce this document.**
See "Resolved Engineering Lead Decisions" for the seven decisions the
Human Engineering Lead has already made that govern everything below;
none of them remains open.

## Engineering Question

PEOS Automation V1 (SPEC-001, hardened by SPEC-003) already orchestrates
one bounded Claude → verify → Codex → (at most one remediation) → verify
→ Codex cycle from a single local command. The Human Engineering Lead
still has to: (a) write and approve a specification by hand before every
run, (b) accept that the loop gives up after exactly one remediation
attempt even when the remaining findings are mechanical, and (c)
reconstruct what happened across a long or interrupted run from console
scrollback, since nothing is persisted outside the final report.

How does PEOS evolve from that single-pass pipeline into a loop that:
turns a human's high-level engineering intent into a plan grounded in
already-approved specs/decisions; runs a *bounded*, multi-cycle Claude ↔
Codex implement/review/remediate loop instead of exactly one cycle; lets
Claude contest a specific Codex finding with evidence without that
turning into an unbounded argument; guarantees a finding Codex once
raised cannot quietly vanish from a later review; and leaves behind
enough structured, non-secret, tamper-contained state to diagnose a long
run — while changing none of SPEC-001/SPEC-003's safety invariants
(isolated workspace, stripped auth boundary, fail-closed behavior, no
autonomous push/PR/merge)?

## Motivation

Every dogfood run so far has been a single engineering task picked and
specced by hand. As PEOS is used for more of this repository's own
work, frictions recur:

1. **One remediation cycle is often not enough**, and is also sometimes
   more than enough. SPEC-001 Section 5/AC-008 hardcodes exactly one
   automatic remediation attempt; a run that needed two mechanical fixes
   stops at `HUMAN_GATE` for no engineering reason, and the Human
   Engineering Lead's only recourse today is to re-run PEOS by hand.
2. **Planning is entirely manual.** `peos/spec.py` only *selects* among
   already-approved specifications; if none matches, SPEC-001 Human Gate
   #1 stops the run immediately. That is correct and must not change —
   but there is currently no automated, auditable step that at least
   *gathers* the already-approved context (related specs, decisions,
   prior validation records) that should inform what the Human
   Engineering Lead writes next.
3. **Nothing survives a run except the final printed report.** A long
   run that hits `HUMAN_GATE` leaves no structured trace a future PEOS
   invocation, or the Human Engineering Lead reading the repository
   later, can inspect without having the original terminal scrollback.
4. **A multi-cycle loop creates a new failure class a single-cycle loop
   never could: a finding quietly disappearing.** If Codex's review on
   cycle 3 simply does not repeat a BLOCKER it raised on cycle 1,
   nothing in a naive generalization of SPEC-001's logic would notice —
   the loop would see cycle 3's (shorter) findings list, see it
   satisfied, and converge on `APPROVED` having "lost" a known-serious
   problem. This is the single most important new risk V2 introduces
   over V1, and it is why Requirement 16 (Outstanding Findings Register)
   exists.

## Scope

- Generalizing `peos/workflow.py`'s fixed one-shot phase sequence into a
  bounded, configurable-cycle-count loop between the existing
  Implementation/Remediation (Claude) and Review/Re-review (Codex)
  phases, with deterministic, repository-derived termination rules and
  the cycle semantics defined in the Model section below.
- A new, purely deterministic **Context Recovery** step (reads
  `docs/decisions/`, `docs/validation/`, and the already-approved
  specification corpus `peos/spec.py` already reads) that runs before
  Planning and feeds its output into the Delivery Report and into spec
  resolution — not a new AI call.
- A new **Planning** step that is a direct extension of today's Intake
  phase (`peos/spec.py::resolve_governing_spec`): it still only
  *resolves among already-approved specifications* (SPEC-001 Human Gate
  #1 is unchanged — PEOS still refuses to invent requirements), plus
  deterministically extracts two more things already implicit in an
  approved spec's text: a bounded cycle count override and a declared
  static external-context requirement (e.g. a Pixso export committed to
  the repository), using the same "parse a conventionally-marked
  section of the spec's own Markdown" approach `peos/verification_plan.py`
  already uses for spec-declared verification commands.
- A lightweight, schema-minimal mechanism (Requirement 8) for Claude to
  contest a specific, PEOS-referenced Codex finding with evidence during
  remediation, and for Codex's closure review to either concede or
  explicitly overrule that contest — with a persistent, reviewer-
  overruled contest escalating to `HUMAN_GATE` immediately.
- A new, run-local, **orchestrator-owned Outstanding Findings Register**
  (Requirement 16) that tracks every BLOCKER/MAJOR finding any review in
  the current run has ever raised, with an explicit closure disposition
  required to retire one — omission or a bare severity downgrade never
  closes a finding, and Codex `APPROVE` is contractually invalid while
  any historical BLOCKER/MAJOR remains outstanding.
- A deterministic, orchestrator-built **Round Packet** (Requirement 17)
  supplied to every fresh Claude/Codex subprocess invocation, replacing
  reliance on agent conversation history as a context channel.
- A new, small, non-secret **Run Ledger** (JSON file per run) that
  `peos/workflow.py` writes after every phase transition, built through
  an explicit field allowlist (Requirement 18), contained to a
  symlink-resistant, atomically-written directory tree (Requirement 19),
  and carrying the identity/retention guarantees of Requirement 20 —
  sufficient to diagnose a `HUMAN_GATE`/`FAILED` run without chat
  history (Tier 1 of "Resumability" below). Programmatic resume is
  explicitly deferred — see Non-Goals.
- A repository-contained **static external-context declaration
  mechanism** (Requirement 21) generalizing the Design-Context parsing
  above: required artifacts must be regular, repository-resident,
  symlink-free files with a deterministic content identity, staged into
  the isolated workspace, and named in the Round Packet.
- Extending `peos/report.py`'s final report into the "Delivery Report"
  shape requirement 10 of the originating brief describes: iteration
  history, a complete findings/disposition ledger covering every
  historical finding (not only the latest cycle's), and unresolved
  MINORs called out explicitly, on top of everything SPEC-001's report
  already shows.
- Three new, additive, nullable fields on Codex's existing
  `REVIEW_SCHEMA` (`peos/codex_agent.py`): `reviewer_overrules_dispute`,
  `addressed_dispute_references`, and `historical_finding_dispositions`
  — see Requirements 8, 16, 22. No other structured agent contract
  changes, and no agent-authored stable finding IDs anywhere (PEOS
  assigns all finding references — Requirement 16).

## Out of Scope / Non-Goals

Carried over unchanged from SPEC-001 Section 13/18 and SPEC-003's Out of
Scope (autonomous spec *approval*, autonomous architecture/physics/
control/protection decisions, autonomous merge/release/deployment,
autonomous `git commit`/`push`/PR, cloud orchestration, a database, a
message queue, a web server/daemon, Docker/Kubernetes, ML of any kind —
per `CLAUDE.md`). Specifically for V2, also out of scope:

- **"Two LLMs chatting indefinitely."** The loop is bounded by a
  configured maximum remediation-cycle count (Requirement 6), by the
  outstanding-findings/persistent-disagreement rules (Requirements 8,
  16, 22), and every cycle's agent context comes from a fresh,
  deterministic Round Packet (Requirement 17), never accumulated
  conversation history — there is no code path that can re-invoke
  Claude/Codex without one of those bounds eventually applying.
- **Autonomous specification *drafting or authoring*.** Planning (this
  spec) only *selects* among specifications the Human Engineering Lead
  has already approved — exactly as SPEC-001 does today. PEOS does not
  gain a capability to write new specification prose and treat it as
  input to implementation. This is Resolved Decision 1 below — no
  autonomous new-spec approval, and no autonomous new-spec *drafting*
  either, in V2.
- **Autonomous PR creation or merge.** Unchanged from SPEC-001 Section
  12: the workflow still stops at a Delivery Report; `git commit`,
  PR creation, and merge remain entirely manual, human actions.
- **Programmatic resume** (`peos --resume <run-id>` actually continuing
  a prior run). V2 ships the structured, diagnosable Run Ledger (Tier
  1); actually replaying/continuing from it is deferred (Resolved
  Decision 4 — no Tier-2 resume in V2).
- **Agent-authored stable finding identity.** PEOS, not either agent,
  assigns every finding reference used anywhere in this spec
  (`(origin_review_number, finding_position)` — Requirement 16). Neither
  agent is ever asked to invent or persist an ID across calls.
- **A general-purpose, live external-design-tool broker.** Neither
  Claude nor Codex gains any new tool/MCP access in V2 (both remain
  `--strict-mcp-config` with zero servers, per Decision 0002), and the
  `peos` orchestrator process itself gains no new automated fetch
  capability either. This is Resolved Decision 5 — no general MCP
  broker in V2. See Requirement 21.
- **A general-purpose workflow/state-machine framework.** The state
  machine below is one fixed sequence with one bounded loop in it, hand-
  written in `peos/workflow.py` as today, not a reusable engine.
- Any change to AI Power Lab simulation physics, the FastAPI backend,
  the frontend, or `SPEC-002`.
- Any change to the authentication/sandbox boundary SPEC-003 and
  Decision 0002 established. V2 adds no new credential, no new
  environment variable exposed to either agent's subprocess beyond what
  SPEC-003 Requirement 1/2 already allow, and no new tool grant to
  either agent.

## Model / Technical Basis

Not a physics model. The "model" here is the orchestration state
machine, which this section specifies precisely because
`peos/workflow.py` is the one place that must implement it faithfully.

### Cycle semantics (Resolved Decision 2 — load-bearing definition)

Every requirement, acceptance criterion, and pseudocode fragment below
uses this definition consistently. It replaces an inconsistent informal
usage in the original draft of this spec, flagged by the Codex
architecture review as a BLOCKER (the original convergence pseudocode's
`for cycle in 1..max_cycles` counted the *initial* review as cycle 1,
which meant an explicit `--max-cycles 1` escalated to `HUMAN_GATE`
**before any remediation ever ran** — silently contradicting
Requirement 15's backward-compatibility promise that `max_cycles=1`
reproduces SPEC-001, which always performs exactly one remediation
attempt before giving up).

- **Cycle 0** = Claude initial implementation → deterministic
  verification → Codex initial independent review. Cycle 0 always runs
  exactly once per PEOS invocation and is **not** counted against
  `max_cycles`. This is unchanged in substance from SPEC-001 Phase 2.
- **A remediation cycle** = Claude remediation → deterministic
  re-verification → Codex closure review. Remediation cycles are
  numbered `1..max_cycles` and `max_cycles` counts **remediation cycles
  only** — never cycle 0.
- `max_cycles` default is **3**, hard cap is **5**. The `peos/cli.py`
  `--max-cycles` flag accepts integers `1..5` inclusive; `0`, negative
  values, or values above `5` are input errors (Requirement 6).
- **Explicit `--max-cycles 1` preserves the existing V1 single-
  remediation behavior exactly**: cycle 0, then at most one remediation
  cycle, then `HUMAN_GATE`/`APPROVED`/`FAILED` — identical observable
  behavior to today's SPEC-001/SPEC-003 implementation (Requirement 15).
- **Omitting `--max-cycles` uses the V2 default of 3**, not 1. A default
  run therefore now permits, at most: 1 initial Claude implementation +
  3 Claude remediation calls, and 1 initial Codex review + 3 Codex
  closure reviews — four Claude calls and four Codex calls total in the
  worst case, not two. This is a deliberate, Human-Engineering-Lead-
  approved behavior change from the original draft's default of 1
  (Resolved Decision 2), and every AC/example/verification fixture
  below reflects it.

### Target end-to-end flow

```
Human Intent
  -> Context Recovery        (NEW, deterministic, no agent call)
  -> Planning                (extends today's "Intake"; still spec-
                               resolution only, not spec-authoring;
                               also resolves Static External Context,
                               Requirement 21)
  -> Claude Implementation    (cycle 0; unchanged from SPEC-001 Phase 2)
  -> Deterministic Verification
     |-- fails -> FAILED (unchanged; never reaches Codex)
  -> Codex Independent Review (cycle 0)       -- evaluated per the
     Evaluation Precedence (Requirement 22) --
       |-- contract/schema invalid (incl. APPROVE with outstanding
       |     historical BLOCKER/MAJOR, or APPROVE with an overruled
       |     active dispute)                  -> FAILED
       |-- APPROVE, no outstanding history     -> Delivery Report
       |-- requires_human_decision finding      -> HUMAN_GATE (#6)
       |-- CHANGES_REQUIRED, remediation cycles remain (always true at
       |     cycle 0 when max_cycles >= 1):
       |      -> Claude Remediation (remediation cycle N; may DISPUTE
       |      |     a PEOS-referenced finding, Requirement 8)
       |      -> Deterministic Re-verification
       |      |     |-- fails -> FAILED (immediately; never reaches
       |      |     |             Codex; never counted as exhaustion)
       |      -> Codex Closure Review (remediation cycle N)
       |            -- evaluated per the same Evaluation Precedence --
       |            |-- contract/schema invalid                -> FAILED
       |            |-- APPROVE, no outstanding history,
       |            |     no overruled active dispute            -> Delivery Report
       |            |-- requires_human_decision                   -> HUMAN_GATE (#6)
       |            |-- reviewer overrules an active dispute       -> HUMAN_GATE (#10)
       |            |-- CHANGES_REQUIRED, cycles remain            -> loop (cycle N+1)
       |            |-- CHANGES_REQUIRED, cycles exhausted         -> HUMAN_GATE (#8)
  -> Delivery Report  (complete outstanding-findings disposition table,
                        every historical finding accounted for)
  -> Human Approval
  -> PR / Merge (unchanged: entirely manual, outside PEOS)
```

This is the same shape as SPEC-001 Section 6/2's workflow diagram with
one structural change: the single "Remediation -> Re-review" step
becomes a bounded loop over remediation cycles (not over "cycles"
including the initial review, per the semantics above), with Context
Recovery, Planning, the Outstanding Findings Register, and the Round
Packet added around it, and a richer Delivery Report at the end.

### Phase list (supersedes SPEC-001 Section 6's phase names for V2 runs)

| # | Phase (as logged) | Status vs. V1 |
|---|---|---|
| 0 | Repository preflight | unchanged (`peos/preflight.py`) |
| 0b | Verification interpreter preflight | unchanged |
| 1 | Context recovery | **NEW** — `peos/context.py` |
| 2 | Planning | renamed from "Intake"; same spec-resolution call, now also builds a `PlanArtifact` (`peos/plan.py`) including any Static External Context declaration (`peos/static_context.py`) |
| 3 | Claude authentication preflight | unchanged (SPEC-003) |
| 4 | Claude implementation (cycle 0) | unchanged |
| 5 | Local verification (cycle 0) | unchanged |
| 6 | Codex independent review (cycle 0) | unchanged mechanics; outcome now feeds the bounded remediation loop below through the Outstanding Findings Register |
| 7 | Claude remediation (remediation cycle *N*) | generalized: was hardcoded to run at most once; now runs for `N = 1..max_cycles`, driven by a Round Packet (`peos/round_packet.py`), not conversation history |
| 8 | Local verification (post-remediation, remediation cycle *N*) | same generalization; a failure here is `FAILED` immediately, every remediation cycle |
| 9 | Codex closure review (remediation cycle *N*) | same generalization; gains the Outstanding Findings Register check and the persistent-disagreement check |
| 10 | Complete / Delivery report | unchanged trigger, enriched content (Requirement 10) |

**Backward-compatibility note on phase 2's rename:** `peos/spec.py`'s
actual resolution logic, its Human Gates #1/#2, and every SPEC-001/
SPEC-003 acceptance criterion about it are unchanged. Only the
human-readable phase *label* PEOS logs/prints for that step changes
from `"Intake"` to `"Planning"`, because the step now does strictly
more (Requirement 2). This is a cosmetic string change, not a
requirement/physics/API change under AGENTS.md's constraint on Claude
Code — flagged here so neither the implementer nor Codex's review of
the implementing change mistakes an existing test's literal string
assertion (if any — `tests/test_peos_workflow.py` should be checked for
this) for a regression rather than an expected, intentional update.

### Convergence algorithm

Convergence (→ `APPROVED`, unchanged outcome name) already has almost
its entire per-cycle definition sitting in
`peos/codex_agent.py::_validate_review_payload`: `verdict == "APPROVE"`
is only reachable when there are zero `blocking`/`major` findings *in
that review's own output*, zero findings with
`requires_human_decision=true`, and every declared acceptance criterion
is `met=true` against the **complete** governing AC set (Requirement 5
— Codex's approval assessment must cover every AC the governing
specification declares, not a subset; an assessment that silently omits
an AC is itself a contract violation, not a passing review). V2 adds
three more preconditions to that same validation function (Requirement
16, 22), checked in this order:

(a) `verdict == "APPROVE"` is **never reachable** — evaluation routes to
`HUMAN_GATE` #6 instead, before the verdict is even interpreted — if any
historical BLOCKER/MAJOR finding anywhere in the run's Outstanding
Findings Register has ever been dispositioned `HUMAN_DECISION_REQUIRED`,
regardless of whether that same disposition has since cleared the
finding's `OUTSTANDING` flag. This check is independent of, and
precedes, check (b) below, specifically because `HUMAN_DECISION_REQUIRED`
removes a finding from `OUTSTANDING` bookkeeping without resolving it —
a later review's `APPROVE` would otherwise slip past an
`OUTSTANDING`-only check for exactly that reason. Unlike (b)/(c), this
is a legitimate reviewer determination rather than a malformed payload,
so it resolves to `HUMAN_GATE`, not `FAILED`.

(b) `verdict == "APPROVE"` is additionally invalid (`FAILED`, a contract
violation, not `CHANGES_REQUIRED`) if the Outstanding Findings Register
still has any `OUTSTANDING` entry at BLOCKER/MAJOR severity, or

(c) if `reviewer_overrules_dispute == true` for any currently active
dispute (also `FAILED`).

`minor`/`info` findings may still legitimately coexist
with `APPROVE` — V2's only addition there is making sure they are not
silently invisible (Requirement 10, "Unresolved MINORs" report section).
"Deterministic verification passes" is already a separate, mandatory
gate run immediately before every Codex call — V2 does not change this;
it is enforced identically for cycle 0 and for every remediation cycle,
and a failure at this gate is `FAILED`, immediately, never a consumed
cycle and never an escalation path to `HUMAN_GATE`.

So the genuinely new convergence logic V2 adds is at the *iteration*
level — deciding whether to stop, loop, or escalate after a review — and
at the *evaluation-order* level (Requirement 22), which this section now
states explicitly because the original draft left it implicit and the
Codex review found an ordering gap (a `CHANGES_REQUIRED` verdict could
be acted on before the orchestrator had checked whether the *verdict
itself* was contractually coherent with the outstanding-findings state):

```
# --- Evaluation precedence, applied to every review payload before any
#     other interpretation of it (Requirement 22). Each stage either
#     raises/returns FAILED or falls through to the next stage; later
#     stages never run on a payload an earlier stage already rejected.
#
#   1. contract/schema validity      (_validate_review_payload, extended)
#   2. dispute validity              (DISPUTE[...] parse + reference check)
#   3. outstanding historical findings (register update, THEN, in order:
#                                      3a. any historical HUMAN_DECISION_
#                                          REQUIRED disposition -> HUMAN_GATE
#                                          #6, unconditionally, before any
#                                          verdict is interpreted;
#                                      3b. APPROVE + OUTSTANDING BLOCKER/
#                                          MAJOR -> FAILED;
#                                      3c. APPROVE + overruled active
#                                          dispute -> FAILED)
#   4. deterministic verification    (already a separate, prior gate —
#                                      restated here for completeness)
#   5. Codex verdict                 (APPROVE / CHANGES_REQUIRED /
#                                      requires_human_decision)
#   6. convergence / exhaustion decision

def evaluate_cycle(review, remediation_cycle, register, active_disputes):
    if not contract_schema_valid(review):                 # stage 1
        return FAILED
    if not disputes_valid(active_disputes, register):     # stage 2
        return FAILED
    register.apply_dispositions(review, origin_review_number=remediation_cycle)

    # stage 3a: HUMAN_DECISION_REQUIRED is terminally non-converged. It is
    # checked first, unconditionally, and BEFORE any APPROVE can be
    # returned -- regardless of whether the finding it covers still reads
    # as OUTSTANDING, because this disposition removes a finding from
    # OUTSTANDING without resolving it (Outstanding Findings Register,
    # above). This takes precedence over every later stage, including an
    # APPROVE verdict in the very same payload.
    if register.has_human_decision_required():             # stage 3a
        return HUMAN_GATE(6)

    if review.verdict == "APPROVE" and register.has_outstanding(
            severities={"blocking", "major"}):             # stage 3b
        return FAILED   # contractually invalid APPROVE, not CHANGES_REQUIRED
    if review.verdict == "APPROVE" and active_disputes.any_overruled():
        return FAILED   # stage 3c: contractually invalid APPROVE
    # stage 4 (deterministic verification) already gated entry to this
    # call; it is not re-checked here.
    if review.verdict == "APPROVE":                        # stage 5/6
        return APPROVED
    if review.human_decision_findings:
        return HUMAN_GATE(6)
    if active_disputes.any_overruled():
        return HUMAN_GATE(10)
    return CHANGES_REQUIRED   # caller decides loop vs. exhaustion


# --- Top-level loop ---
implement()                                    # Claude, cycle 0
vreport = verify()
if not vreport.passed:
    return FAILED
review0 = codex_review(cycle=0)
outcome = evaluate_cycle(review0, remediation_cycle=0, register, disputes)
if outcome in (APPROVED, FAILED, HUMAN_GATE(6), HUMAN_GATE(10)):
    return outcome

for remediation_cycle in range(1, max_cycles + 1):
    remediation = claude_remediate(round_packet_for(remediation_cycle))
    if remediation.status == HUMAN_GATE:
        return HUMAN_GATE(mapped gate_category)

    vreport = verify()
    if not vreport.passed:
        return FAILED        # NEW explicit rule, every remediation cycle:
                              # never silently retried, never advanced to
                              # Codex, never counted as "exhaustion"

    closure_review = codex_review(cycle=remediation_cycle)
    outcome = evaluate_cycle(closure_review, remediation_cycle, register, disputes)
    if outcome in (APPROVED, FAILED, HUMAN_GATE(6), HUMAN_GATE(10)):
        return outcome
    if remediation_cycle == max_cycles:
        return HUMAN_GATE(8, "iteration exhaustion",
                           unresolved_register=register.outstanding(),
                           unresolved_disputes=disputes.active())
```

This is a direct generalization of today's `_run_workflow` Phase 4/5
body: SPEC-001's current code *is* the `max_cycles=1` instance of this
loop with the body unrolled instead of looped, and the cycle-0/
remediation-cycle split above is exactly how SPEC-001 already structures
its own two review calls ("independent review" then "re-review") — V2
only generalizes the second half into a bounded `for` loop and adds the
two new validity stages. `max_cycles=1` with V2's code must reproduce
today's exact behavior (Requirement 15).

### Disagreement handling (Requirement 8)

Two designs were considered; V2 keeps the cheaper one, **lightweight
Option A**, per Resolved Decision 6 — with the precise contract below,
tightened against the Codex review's findings on malformed/ambiguous
disputes.

1. The remediation prompt (`peos/prompts.py::build_remediation_prompt`)
   gains one additional instruction: Claude may decline to change code
   for a specific finding the Round Packet's Outstanding Findings
   Register lists if it has concrete evidence the finding is already
   satisfied, inapplicable, or factually wrong — but only by writing a
   line of the literal form
   `DISPUTE[<origin_review_number>.<finding_position>]: <evidence>`
   in its `summary` field, where `<origin_review_number>.<finding_position>`
   is the exact PEOS-assigned finding reference (Requirement 16) as it
   appears in the Round Packet's register — e.g. `DISPUTE[0.3]:` disputes
   the 3rd finding of the initial (cycle 0) review; `DISPUTE[2.1]:`
   disputes the 1st finding of remediation cycle 2's closure review.
   This needs **no change** to `CLAUDE_RESULT_SCHEMA` — `summary` is
   already a free-text, already-sanitized (`sanitize_human_text`) field.
2. `peos/workflow.py` deterministically scans the (already sanitized)
   remediation `summary` for lines matching a fixed regex
   (`^DISPUTE\[\d+\.\d+\]:\s*\S`) — the same "fixed, auditable text
   convention" style `peos/verification_plan.py` already uses for
   spec-declared verification commands and `peos/diagnostics.py` uses
   for phrase classification. A line is parsed into a candidate dispute
   only if it matches this regex **and**:
   - the referenced `(origin_review_number, finding_position)` names an
     entry in the Outstanding Findings Register that is currently
     `OUTSTANDING` (an unknown or already-closed reference is invalid),
     and
   - the `<evidence>` text, after `sanitize_human_text`, is non-empty
     (whitespace-only or sanitizer-truncated-to-empty evidence is
     invalid — a dispute that lost its content to sanitization is not
     silently treated as "no dispute"; it is a contract violation).

   A line that superficially matches `^DISPUTE\[` but fails any of the
   above (malformed index syntax, unknown/non-outstanding reference,
   empty/truncated evidence) is **invalid structured output**: that
   remediation cycle's result is `FAILED`, with the offending line and
   the specific reason recorded in the ledger and Delivery Report. This
   is a deliberate strengthening over "silently treated as no dispute" —
   see Known Limitations for the one case that is *not* an error (no
   `DISPUTE[...]`-looking line present at all).
3. `REVIEW_SCHEMA` (`peos/codex_agent.py`) gains three new top-level
   fields, each `null`-by-default, following the same strictness pattern
   every other nullable field in that schema already uses:
   - `reviewer_overrules_dispute: boolean | null`. `null` is only valid
     when no dispute is active this cycle. `true` means the reviewer
     considered at least one disputed finding's evidence and still finds
     it a real, unresolved issue — "persistent disagreement" —
     `peos/workflow.py` escalates to `HUMAN_GATE` (#10) immediately, even
     if `max_cycles` has not been reached, **and an `APPROVE` verdict in
     the same payload is a contract violation (stage 1/3 of Evaluation
     Precedence), not a valid approval** (closing the Codex-review
     BLOCKER: an earlier draft of this mechanism allowed `APPROVE` and
     `reviewer_overrules_dispute=true` to coexist as merely inconsistent
     rather than invalid). `false` means the reviewer concedes every
     active dispute considered this cycle for the purposes of the
     aggregate flag; individual disposition still comes from
     `historical_finding_dispositions` (Requirement 16).
   - `addressed_dispute_references: list[string] | null`. `null` only
     when no dispute is active this cycle. When one or more disputes are
     active, this field is **required** to be a non-null list containing
     every active dispute's reference — Codex's closure review must
     explicitly address each active dispute, not only the most recently
     raised one. A closure review that omits an active reference from
     this list is invalid structured output (`FAILED`), closing the
     Codex-review MAJOR finding that nothing previously forced Codex to
     re-examine a dispute from two cycles ago.
   - `historical_finding_dispositions` — see Requirement 16; shared
     machinery between the register and the dispute mechanism.
4. The closure-review prompt (`build_rereview_prompt`) is extended, via
   the Round Packet (Requirement 17), to quote every currently-active
   `DISPUTE[ref]: ...` text back to Codex by its PEOS-assigned
   reference, and to instruct it to populate
   `reviewer_overrules_dispute`/`addressed_dispute_references`
   accordingly.

**Option B (named, not proposed for V2)** — stable per-finding IDs
assigned by Codex instead of PEOS, carried across calls, with a fully
structured per-finding disposition array for *every* finding every
cycle (not only outstanding historical BLOCKER/MAJORs). More auditable
in principle, but a materially larger schema/contract surface change
across both agents' structured outputs, and it still requires an
agent-authored identity scheme this spec's governance explicitly rejects
(PEOS assigns all finding references — see Out of Scope). Named here so
the Human Engineering Lead can revisit it in a future version if
Option A's aggregate `reviewer_overrules_dispute` boolean proves too
coarse for multiple simultaneous disputes in one cycle where only one is
overruled — this remains a known, named limitation of Option A (see
Known Limitations), not a defect introduced by this remediation.

### Outstanding Findings Register (Requirement 16 — NEW)

This closes the Codex review's BLOCKER finding directly: a multi-cycle
loop that only ever looks at the *latest* review's findings list can
converge on `APPROVED` after a serious problem simply stops being
repeated, without anyone ever having decided it was actually fixed.

- **What it is.** A run-local, in-memory structure (persisted, sanitized
  and bounded, inside the Run Ledger — Requirements 18–20) owned
  entirely by the orchestrator (`peos/findings_register.py`), tracking
  every `blocking`/`major` finding any Codex review has raised **in this
  run**. It is explicitly *not* cross-run: a BLOCKER from a previous,
  separate PEOS invocation is not tracked here (see Known Limitations).
- **Identity.** Every finding is addressed by the PEOS-assigned pair
  `(origin_review_number, finding_position)` — `origin_review_number` is
  `0` for the initial review, `N` for remediation cycle `N`'s closure
  review; `finding_position` is the finding's 1-based position in that
  review's own `findings` array, exactly as Codex returned it. **PEOS
  assigns this reference; neither agent is ever asked to invent or
  carry a stable ID.**
- **Lifecycle.** A finding enters the register the first time it is
  seen, with status `OUTSTANDING`. It leaves `OUTSTANDING` only when a
  *later* review's `historical_finding_dispositions` field explicitly
  names its reference with one of:
  - `RESOLVED` — the reviewer verified the underlying issue no longer
    exists.
  - `ACCEPTED_RECLASSIFICATION` — the reviewer explicitly accepts that
    the finding, while real, is no longer BLOCKER/MAJOR-severity (a
    deliberate, named downgrade — distinct from a silent one, below).
  - `HUMAN_DECISION_REQUIRED` — the reviewer cannot resolve it
    unilaterally. **This disposition is terminally non-converged.** It
    clears the finding's `OUTSTANDING` flag the same way `RESOLVED`/
    `ACCEPTED_RECLASSIFICATION` do, but unlike those two, it is **never**
    treated as resolved: PEOS separately and permanently records that
    this reference has a `HUMAN_DECISION_REQUIRED` disposition in its
    history, and the presence of *any* such record anywhere in the run
    unconditionally forces `HUMAN_GATE` #6 the next time a review payload
    is evaluated (Evaluation Precedence stage 3a, Requirement 22) —
    checked independently of, and before, the `OUTSTANDING` check, so
    that clearing `OUTSTANDING` can never be mistaken for resolving the
    finding. There is no later disposition that un-sets a
    `HUMAN_DECISION_REQUIRED` record within the same run; only a human
    acting outside PEOS (and, if desired, a fresh PEOS invocation) moves
    the underlying issue forward.
  Each disposition entry carries a short, sanitized, bounded `note`
  (why), persisted in the ledger's sanitized finding/dispute state.
- **Omission never closes a finding.** If a later review's
  `historical_finding_dispositions` simply does not mention an
  outstanding reference, that finding remains `OUTSTANDING`. This is
  the normal, expected case for most cycles (most reviews will not
  re-litigate every historical finding every time) and is not itself an
  error — it is the entire point of the register: silence preserves the
  finding rather than erasing it.
- **A silent severity downgrade does not close a finding either.** If
  Codex's *current* findings list re-reports what is substantively the
  same issue at `minor` severity without an explicit
  `ACCEPTED_RECLASSIFICATION` disposition entry for the original
  reference, the original reference remains `OUTSTANDING` at its
  original severity. Nothing in this spec asks the implementer to
  detect "is this the same issue reworded" automatically (that would
  require a judgment call this spec does not delegate to code) — the
  rule is purely about the register's bookkeeping: the only way to
  retire a BLOCKER/MAJOR reference is an explicit disposition against
  *that reference*, never an absence or a differently-worded new entry.
- **Gate on `APPROVE`.** `verdict == "APPROVE"` is contractually invalid
  (Evaluation Precedence stage 3b, `FAILED`, not `CHANGES_REQUIRED`) while
  the register has any `OUTSTANDING` entry at `blocking`/`major`
  severity. This is the direct fix for the Codex BLOCKER.
- **Approval invariant (NEW).** `APPROVED` is permitted only if **all**
  of the following hold simultaneously:
  1. deterministic verification passed for the cycle being evaluated;
  2. the register has no `OUTSTANDING` entry at `blocking`/`major`
     severity (the bullet above);
  3. **no historical `blocking`/`major` finding anywhere in the run's
     register carries a `HUMAN_DECISION_REQUIRED` disposition** — checked
     independently of, and before, condition 2, precisely because that
     disposition clears `OUTSTANDING` without resolving the finding (see
     Lifecycle, above); a payload satisfying every other condition still
     evaluates to `HUMAN_GATE` #6, never `APPROVED`, if this condition
     fails;
  4. no active dispute is unresolved or has been overruled
     (`reviewer_overrules_dispute == true`);
  5. the current Codex verdict is `APPROVE`;
  6. Codex's acceptance-criteria assessment covers the **complete**
     governing AC set (Requirement 5/25).
  Evaluation Precedence (Requirement 22) checks condition 3 first, ahead
  of conditions 2/4/5, so that a `HUMAN_DECISION_REQUIRED` record can
  never be bypassed by an `APPROVE` verdict arriving in a later cycle.
- **Delivery Report.** Every reference the register has ever held — its
  origin, its current status, and (if closed) the disposition and note
  that closed it — appears in the Delivery Report's "Findings and
  resolutions" section (Requirement 10), independent of the run's final
  outcome.

### Round Packet (Requirement 17 — NEW)

Each fresh Claude or Codex subprocess invocation is, by SPEC-003's own
design, a brand-new process with no memory of prior calls — **agent
conversation history is not, and has never been, an authoritative
context channel in PEOS**, and the original draft of this spec's prompt
language implicitly assumed otherwise in places ("the closure-review
prompt is extended to quote the specific text back to Codex," singular,
as if there were only ever one prior cycle to reference). V2 makes this
explicit and gives it one deterministic mechanism: a `RoundPacket`
(`peos/round_packet.py`), built fresh by the orchestrator before every
agent invocation, never accumulated or mutated by the agent itself.

A Round Packet contains, at minimum:

1. The original human task/intent string, unchanged since Planning.
2. The governing specification's repository path and content hash
   (recomputed and compared at every round — Requirement 22/AC-35).
3. The applicable decision/governance identities (e.g.
   `docs/decisions/0002`, this spec's own path+hash) relevant to the run.
4. The current cycle number (`0` or the remediation-cycle index) and the
   remaining budget (`max_cycles - current_remediation_cycle`).
5. The current workspace snapshot identity (the isolated workspace's
   `git` tree hash or equivalent at the start of this round).
6. The latest deterministic verification result/evidence (pass/fail and
   the sanitized summary of which checks ran).
7. The **complete** Outstanding Findings Register as it stands entering
   this round (Requirement 16) — not just the prior cycle's findings.
8. Every currently **active** dispute and its evidence (Requirement 8).
9. The **complete** governing acceptance-criteria set from the resolved
   specification — so Codex's approval assessment can be checked for
   coverage against the same list the orchestrator holds (closing the
   "incomplete AC coverage" gap).
10. The paths/identities of any required static external-context
    artifacts (Requirement 21), already staged into the isolated
    workspace.

`peos/prompts.py::build_remediation_prompt` and `build_rereview_prompt`
are rewritten (at implementation time, not by this spec) to render from
a `RoundPacket` rather than from ad hoc positional arguments, and any
existing prompt language implying there is only one remediation or one
final re-review is removed and replaced with cycle-aware language
("remediation cycle `N` of up to `max_cycles`"). This spec does not
write that prompt text; it requires the implementer to update it and
requires Codex's closure-review assessment of acceptance criteria to be
checked, deterministically, against the complete AC set the Round
Packet carries (AC-25).

### Bounded iteration (Requirement 6)

- `max_cycles` counts **remediation cycles only** (Cycle semantics,
  above). Default **3**, hard cap **5**, `peos/cli.py --max-cycles`
  accepts `1..5`. A value outside `[1, 5]` is an input error, handled
  exactly like today's invalid `--repo`/`--spec`
  (`_report_input_failure`: a normal `FAILED` PEOS report, never a bare
  traceback or silent clamp).
- Exhausting `max_cycles` while still `CHANGES_REQUIRED` (or with an
  outstanding register entry, or an active unresolved dispute) always
  produces `HUMAN_GATE` (gate #8) — **never** a pretended `APPROVED` and
  never an unbounded extra cycle. The gate reason names the configured
  `max_cycles`, the outstanding register entries (if any), and the
  active disputes (if any), so a human reading the Delivery Report never
  has to guess why it stopped.
- Every other existing bound (one Claude authentication check per run,
  one Codex authentication check per run, one isolated workspace per
  run, one reconciliation at the end) is unchanged and is *not*
  multiplied by `max_cycles` — only the implementation/remediation ↔
  review/closure-review pair repeats, and the final reconciliation step
  behaves identically regardless of how many remediation cycles ran
  (AC-36).

### Human Gate catalog (extends SPEC-001 Section 7 for V2 runs)

| ID | Condition | Status |
|----|-----------|--------|
| 1 | No approved specification resolves the task | unchanged |
| 2 | Specification resolution is ambiguous | unchanged |
| 3 | Claude's `gate_category=physics` | unchanged |
| 4 | Claude's `gate_category∈{control,protection}` | unchanged |
| 5 | Claude's `gate_category=architecture` | unchanged |
| 6 | Codex finding(s) with `requires_human_decision=true`, or **any** historical register entry ever dispositioned `HUMAN_DECISION_REQUIRED` — checked unconditionally, before an `APPROVE` verdict can be returned, and regardless of whether that entry's `OUTSTANDING` flag has since been cleared by the same disposition | **generalized** to also cover register dispositions; takes precedence over `APPROVE` in the same or a later payload (Requirement 22 stage 3a) |
| 7 | *(reserved; SPEC-001 lists this but no code path emits it — a verification failure is `FAILED`, not a gate — unchanged)* | unchanged |
| 8 | Bounded remediation cycles exhausted while still `CHANGES_REQUIRED`, or exhausted with an active unresolved dispute | **generalized**: "after one cycle" → "after `max_cycles` remediation cycles," reason text names outstanding register entries/disputes |
| 9 | Merge/release/tag action requested | unchanged |
| 10 | Codex's closure review sets `reviewer_overrules_dispute=true` for an active dispute | **NEW** — persistent, evidence-backed disagreement; invalid to combine with `APPROVE` in the same payload (`FAILED` instead, Evaluation Precedence) |
| 11 | Planning resolves a governing spec that declares a required static external-context artifact (Requirement 21) with no corresponding artifact resolvable in the repository | **generalized** from a Pixso-specific framing to the general static-context mechanism |

Gate IDs 1–9 are unchanged in meaning and unchanged in the enum of
`gate_category`/`_CLAUDE_GATE_CATEGORY_TO_ID` Claude can report through;
V2 adds no new value Claude's structured result may set (Requirement 8's
dispute path is Claude-remediation-prompt-driven text, not a new Claude
`status`/`gate_category`; the register's `HUMAN_DECISION_REQUIRED`
disposition is Codex-side structured data, also not a new Claude value).

A **containment or safety violation is never a Human Gate** — a
symlinked ledger path, a static-context artifact that escapes the
repository root, or any other violation named in Requirements 19/21 is
`FAILED`, because it is not a judgment call for a human to adjudicate;
it is a precondition PEOS refuses to proceed past.

### Shared artifacts / Run Ledger (Requirements 3, 18, 19, 20)

A new `peos/ledger.py` module, small and single-purpose like every other
`peos/` module, plus `peos/findings_register.py` (Requirement 16) and
`peos/round_packet.py` (Requirement 17) for the structured state that
feeds it:

- `RunLedger` — a frozen dataclass built through an **explicit field
  allowlist** (Requirement 18): `run_id`, `schema_version`,
  `created_at`/`updated_at`, `max_cycles`, `authoritative_baseline`
  (repository identity), `governing_spec_identity` (path + hash),
  `active_phase`, `last_completed_phase`, `current_cycle`,
  `sanitized_phase_history`, `sanitized_register_state`,
  `sanitized_dispute_state`, `sanitized_verification_summaries`, and
  `outcome`/`gate_id`/`gate_reason` when terminal (Requirement 20). This
  is the *complete* list of what may ever be written; `write_ledger`
  never calls a generic serializer (`dataclasses.asdict`, `vars()`,
  `__dict__`) on an arbitrary result object, and never writes a field
  not named above.
- Every text field is passed through `sanitize_human_text` **and** a
  fixed length bound before being written — both are mandatory at the
  persistence boundary, not merely at display time. **Prohibited
  unconditionally, regardless of allowlist membership of the containing
  object:** raw `stdout`/`stderr`, environment variable dumps,
  credential values, credential-file contents, and arbitrary
  configuration blobs. If a value cannot be shown to be one of the
  allowlisted, sanitized, bounded fields above, it is never written.
- `write_ledger(ledger, repo_root)` — writes
  `<repo_root>/.peos/runs/<run_id>/ledger.json`, called once after every
  `stage()`/`gate()`/`fail()`/`approve()` transition in
  `peos/workflow.py` (the same places that already call `log(...)`), so
  a ledger always reflects the most recently completed phase even if the
  process is killed mid-run (Requirement 20). **A ledger write failure
  produces a visible `FAILED` run outcome** — it is never swallowed or
  silently skipped.
- **Tests (Requirement 18) must inject synthetic secret strings into
  each of:** task text, summaries, finding descriptions, evidence
  (including dispute evidence), and error paths, and assert the secret
  is absent from the written ledger JSON in every case, individually
  (not only in aggregate) — extending SPEC-003 AC-10/AC-11's existing
  style of test to this wider set of injection points.
- `.peos/runs/` is added to `.gitignore` at the repository root — the
  ledger is local operator state, not a repository artifact, and must
  never be committed. **This is the sole new authoritative-checkout
  bookkeeping write introduced by SPEC-004. It is diagnostic
  orchestration state, not engineering source of truth**: it cannot
  authorize execution, cannot establish engineering acceptance, cannot
  override repository/spec state, and is not a resume checkpoint in V2
  (Requirement 20).
- **Filesystem containment (Requirement 19).** `.peos`, `.peos/runs`,
  and every run-directory path component are each checked individually
  (not only the final resolved path) to reject a symlink at any
  position; canonical writes must resolve beneath the canonical
  `.peos/runs/` directory or the write is refused (`FAILED`, never a
  silent follow-through). Run directories are created with exclusive
  creation semantics (fails if the directory already exists — no
  reuse, no silent overwrite of another run's state). File writes
  within a run directory are atomic (write to a sibling temp file, then
  `os.replace`): a process killed mid-write leaves either the previous
  valid ledger file or no file for that write, never truncated/partial
  JSON. The ledger is **excluded** from isolated-workspace copying (it
  is never copied into the sandboxed agent workspace) and **excluded**
  from the final reconciliation step, at every remediation-cycle count
  (AC-36) — and it is never supplied as agent-controlled repository
  state: the Round Packet is built by the orchestrator reading the
  ledger from the authoritative-checkout side only, never from anything
  either agent's sandbox could have written back into.
- **Retention (Requirement 20).** PEOS retains the most recent 20
  completed/failed run directories under `.peos/runs/`; cleanup removes
  only PEOS-owned, inactive run directories (identified by a valid
  ledger with a terminal `outcome`) and never removes a directory
  lacking a recognizable PEOS ledger or belonging to the currently
  active run, regardless of its age.
- Shared, structured artifacts *between* Claude and Codex within a run
  remain exactly what SPEC-001 already uses, generalized by the Round
  Packet: the governing specification file (copied into the workspace by
  `ensure_spec_in_workspace`), any staged static-context artifact
  (Requirement 21), and the actual working-tree diff each agent inspects
  via its own file tools/`git diff`. The Run Ledger is PEOS's own
  bookkeeping, never a message bus either agent reads from or writes to.

### Resumability (Requirement 13) — two tiers, only Tier 1 proposed now

- **Tier 1 (proposed, required for V2 approval):** the Run Ledger above.
  Sufficient for a human (or a future PEOS session) to read exactly what
  happened and why a run stopped, from disk, without chat history.
- **Tier 2 (not proposed for V2 — Resolved Decision 4):** a `peos
  --resume <run-id>` flag that reloads a Tier-1 ledger and *continues*
  execution from the last completed phase instead of only informing a
  fresh run. This needs care V2 does not attempt to design: the isolated
  workspace from the original run may already be gone (nothing today
  guarantees its retention), the governing specification may have
  changed on disk since, and a Codex review already consumed into
  `APPROVED`/`HUMAN_GATE` cannot be safely "re-entered" without re-
  establishing every invariant SPEC-001/SPEC-003 already check fresh
  (repository safety, governance-artifact hashes, both auth
  preconditions). Tier 2 is left as explicit future work, and the Run
  Ledger is explicitly documented (Requirement 20) as not being a resume
  checkpoint even in its Tier-1 form.

### Observability (Requirement 14)

`peos/workflow.py`'s existing `stage(name)` helper already prints
`"[PEOS] {name}"` and appends a `PhaseLog`. V2's only change here is
that cycle-bearing phases pass a cycle-qualified name, e.g. `"Claude
remediation (remediation cycle 2/3)"` / `"Codex closure review
(remediation cycle 2/3)"` — a string-formatting change only, reusing the
exact same helper and the same rule (never print raw agent
`stdout`/`stderr`, only `.summary`/`.error`/`.verdict`) that already
governs every existing log line. The `/3` denominator reflects the
*effective* `max_cycles` for this run (default 3, or whatever
`--max-cycles` set), not a hardcoded value.

### Static External Context (Requirement 21 — generalizes the original "Requirement 12")

Planning (the renamed/extended Intake phase) deterministically parses
the resolved specification's own text for a conventionally-marked
section — the same style `peos/verification_plan.py` already uses for
spec-declared verification commands — e.g. a `## Design Context` /
`### Design Context` heading whose indented lines name required static
external artifacts (a Pixso export already committed to the repository,
a reference image path, etc.). `peos/static_context.py` then resolves
and validates each declared artifact:

- Neither Claude nor Codex gains any new tool. Both remain confined to
  `Read Edit Write Grep Glob` (Claude, no shell) / `--sandbox read-only`
  with `--strict-mcp-config`-equivalent restriction (Codex) exactly as
  SPEC-003/Decision-0002 require — **no agent calls out to Pixso or any
  other MCP server during a PEOS run**, and the `peos` orchestrator
  process itself gains no new automated fetch capability either
  (Resolved Decision 5 — no general MCP broker in V2).
- A declared artifact must be: a **regular, readable file** (never a
  directory, device, pipe, or socket); resolvable to a path **beneath
  the repository root**, with every path component checked individually
  for a symlink the same way ledger containment is checked (Requirement
  19) — an artifact that escapes containment through a symlink, or
  resolves outside the repository root, is a **containment violation**
  and produces `FAILED`, never a silent read and never a Human Gate.
  Each resolved artifact gets a **deterministic content identity** (a
  content hash), computed at Planning.
- If the declared artifact resolves successfully under the rules above,
  Planning records its path and content identity in the `PlanArtifact`,
  **stages a copy into the isolated workspace** (so either agent's
  existing file tools can read it — unlike the Run Ledger, which is
  explicitly never staged into the workspace), and includes its
  path/identity in the Round Packet (Requirement 17) for every
  subsequent round so the context is never silently dropped from a
  later cycle's prompt.
- If it does **not** resolve under the rules above (missing file,
  wrong file type), Planning stops at `HUMAN_GATE` (#11) asking the
  Human Engineering Lead to either export/commit the needed artifact or
  revise the specification, **before any workspace is created or either
  agent is invoked**. If it fails because of a containment/safety
  violation (symlink, path escape), the result is `FAILED`, not
  `HUMAN_GATE` (the distinction above).
- **Identity re-verification before every consuming invocation (NEW) —
  fails closed on drift.** The content identity recorded at Planning is
  the artifact's fixed identity for the remainder of the run. Before
  **every** subsequent Claude or Codex invocation that consumes this
  artifact, PEOS re-verifies, in order: (1) the path still resolves
  beneath the repository root with no symlink at any component
  (unchanged containment check, above); (2) the file still exists and is
  still a regular, readable file; (3) its current content hash still
  equals the identity recorded at Planning; (4) the copy staged into the
  isolated workspace still matches that same identity. If **any** of
  these checks fails — including the ordinary case of the artifact's
  content having simply changed on disk since Planning — the result is
  `FAILED`, **immediately, before the next agent invocation**: PEOS
  never invokes that agent with stale or newly-changed context, never
  silently recomputes and adopts the new hash as the identity, never
  downgrades this to a Delivery Report note, and never routes it to a
  `HUMAN_GATE`. Identity drift is not a judgment call — it is a
  precondition PEOS refuses to proceed past, the same fail-closed
  treatment Requirement 19 already gives ledger containment. Adopting
  the changed artifact requires the Human Engineering Lead to start a
  new PEOS run; Planning in that new run resolves and hashes the
  artifact fresh. This is distinct from the Planning-time resolution
  failure described in the bullet above (missing/wrong-type artifact,
  `HUMAN_GATE` #11) — identity drift can only be detected *after*
  Planning has already resolved the artifact once (AC-39).
- **No live Pixso/MCP broker in V2.** For a future Pixso dogfood, PEOS
  may consume an explicitly exported/static design artifact or other
  approved repository-contained representation — see Future Direction.
  This spec does not design live fetching in any form.

### Delivery Report (Requirement 10)

`peos/report.py::build_report` gains, additively, alongside everything
it already renders:

- A "Context recovered" section listing the related approved
  specs/decisions/validation records Context Recovery found (even on a
  run that never reaches implementation).
- An "Iteration history" section replacing today's separate
  "Claude implementation/remediation" + "Independent review (Codex)"
  lists with one cycle-indexed table (cycle 0 = initial implementation +
  review; remediation cycle *N* = remediation + closure review),
  including any `DISPUTE[ref]`/`reviewer_overrules_dispute`/
  `addressed_dispute_references` activity for that cycle.
- A "Findings and resolutions" section containing the **complete
  Outstanding Findings Register** (Requirement 16): every finding any
  review in the run ever raised, its PEOS-assigned reference, and its
  final disposition — `RESOLVED` / `ACCEPTED_RECLASSIFICATION` /
  `HUMAN_DECISION_REQUIRED` / still `OUTSTANDING` at the point the run
  stopped. Every historical finding gets a final disposition line in
  this report, with no exceptions — omission from this section is
  itself a reporting defect, not a valid way to represent "nothing more
  to say."
- An explicit "Unresolved MINOR findings" section — populated whenever
  the run reaches `APPROVED` (or `HUMAN_GATE`) with any `minor`/`info`
  finding still outstanding, so a non-blocking finding is never silently
  dropped from what the Human Engineering Lead sees just because it
  wasn't blocking enough to stop the run.
- Everything SPEC-001's report already includes (verification evidence,
  changed files, known limitations, Git working-tree status, recommended
  next human action) is retained unchanged in shape.

## Assumptions

- Carries over every assumption SPEC-003 already documents about how
  Claude/Codex authenticate and are sandboxed; V2 introduces no new
  credential or environment variable.
- The Human Engineering Lead continues to write and approve
  specifications by hand (Planning only *selects*, never authors).
- `max_cycles` is small (default 3, hard cap 5) by design — this is
  meant to absorb a handful of mechanical remediation rounds, not to
  approximate an open-ended negotiation between two agents.
- The repository remains a single local Git checkout operated on by a
  single human at a time, exactly as SPEC-003's own Assumptions already
  state for the authentication bridge.
- The Outstanding Findings Register and Round Packet are both run-local
  state: neither is assumed to persist meaning across separate PEOS
  invocations (see Known Limitations).

## Requirements

Numbered to match the fifteen capabilities in the originating brief,
extended by Requirements 16–22 to close the Codex architecture review's
1 BLOCKER + 8 MAJOR findings; each maps to a concrete module above.

1. **One entry point.** `peos "<intent>"` remains the only required
   input for a normal run. New flags (`--max-cycles`) are optional, and
   the default (3, per the Cycle semantics section) is itself a V2
   behavior change from V1's effective "1" — not a V1-reproducing
   default; `--max-cycles 1` is what reproduces V1 exactly. No second
   command or manual hand-off between Claude and Codex is introduced.
2. **Planning.** `peos/plan.py::build_plan` wraps
   `resolve_governing_spec` (unchanged) and adds deterministic parsing
   of the resolved spec's `max_cycles` override (if declared) and
   Static External Context declaration (`peos/static_context.py`, if
   declared). Never invents an unresolved requirement; `HUMAN_GATE`s
   #1/#2/#11 cover every way it can fail to produce a usable plan.
3. **Shared artifacts.** The governing specification file, any staged
   static-context artifact, and the working tree remain the only
   channel between Claude and Codex, as today. The Run Ledger is PEOS's
   own structured record of the run, not an agent-to-agent channel; the
   Round Packet (Requirement 17) is the orchestrator-to-agent channel,
   also not agent-to-agent.
4. **Iterative Claude ↔ Codex loop.** Implemented as cycle 0 (fixed)
   followed by the bounded `for remediation_cycle in 1..max_cycles` loop
   (Model section above). Codex still never modifies the working tree
   (unchanged fingerprint check in `_codex_phase`, re-verified **every**
   review round, not only the first — AC-34); Claude remains sole
   implementer.
5. **Convergence policy.** Reuses `_validate_review_payload`'s existing
   `APPROVE` semantics (zero blocking/major findings in that review's
   own output, zero human-decision findings, all ACs in the **complete**
   governing AC set met — an assessment covering fewer than the full AC
   set is a contract violation, not a passing review), plus two new
   preconditions (Requirement 16/22: zero outstanding historical
   BLOCKER/MAJOR, no overruled active dispute), plus the existing,
   unchanged, independent deterministic-verification gate before every
   review.
6. **Bounded iteration.** `max_cycles` counts remediation cycles only;
   default 3, hard cap 5, CLI range `1..5`; exhaustion is `HUMAN_GATE` #8,
   never silent success.
7. **Human gates.** Catalog above; only genuinely human-owned
   categories (architecture/physics/control/protection ambiguity, scope
   change, persistent reviewer-overruled disagreement, iteration
   exhaustion, missing static-context artifact, final approval) stop the
   run. Routine mechanical findings continue to remediate automatically
   within the bounded loop. Containment/safety violations are `FAILED`,
   never a Human Gate.
8. **Disagreement handling.** Lightweight Option A (above): a fixed
   `DISPUTE[<origin_review_number>.<finding_position>]:` text convention
   in Claude's `summary`, referencing a PEOS-assigned, currently-
   `OUTSTANDING` register entry with non-empty evidence (malformed,
   unknown-reference, empty-evidence, or sanitization-truncated disputes
   are invalid structured output, `FAILED`), plus the three new nullable
   `REVIEW_SCHEMA` fields (`reviewer_overrules_dispute`,
   `addressed_dispute_references`, `historical_finding_dispositions`).
   A reviewer-overruled active dispute escalates to `HUMAN_GATE` #10
   immediately; combined with `APPROVE` in the same payload it is
   instead a contract violation (`FAILED`), per Requirement 22.
9. **Deterministic gates authoritative.** Unchanged: `pytest -q`,
   frontend lint/typecheck/build, and spec-declared verification
   commands remain the only acceptance evidence; AI review output alone
   never satisfies verification (unchanged `vreport.passed` gate before
   every Codex call, every remediation cycle, with no exception that
   lets a verification failure be silently absorbed as a used cycle).
10. **Delivery report.** Extended `build_report` shape above, including
    the complete historical-finding disposition table.
11. **Safety/governance.** Every SPEC-003/Decision-0002 invariant listed
    in that spec's "Security Invariants" section is unchanged by V2: no
    new credential, no widened `HOME`, no MCP/plugin grant to either
    agent or to the orchestrator, no autonomous push/PR/merge,
    fail-closed on every new precondition this spec adds exactly like
    every existing one. The governing specification's content hash is
    re-checked before every Claude round, not only at Planning
    (Requirement 22, AC-35), and the isolated-workspace fingerprint
    check is re-run before every Codex round (Requirement 4, AC-34).
12. *(superseded by Requirement 21 — Static External Context; retained
    as a number for traceability, not reused.)*
13. **Resumability.** Tier 1 (Run Ledger) proposed now, bound by the
    identity/durability/retention rules of Requirement 20; Tier 2
    (programmatic resume) explicitly deferred (Resolved Decision 4). The
    Run Ledger is diagnostic only and is never a resume checkpoint.
14. **Observability.** Cycle-qualified phase names via the existing
    `stage()` helper, denominated by the run's effective `max_cycles`;
    no raw agent output ever printed or persisted, unchanged from today.
15. **Backward compatibility.** `--max-cycles 1` must reproduce every
    SPEC-001/SPEC-003 acceptance criterion's observable behavior
    exactly, modulo the one cosmetic phase-label rename called out
    above. **Omitting `--max-cycles` does *not* reproduce V1 behavior in
    V2** — it uses the new default of 3 (Cycle semantics, Resolved
    Decision 2) — this is a deliberate, approved behavior change, stated
    here so it is never mistaken for a regression. Existing
    approved-spec execution (SPEC-002's Scenario A work, e.g.) remains
    possible unchanged when `--max-cycles 1` is passed explicitly.
16. **Outstanding Findings Register (NEW).** `peos/findings_register.py`
    tracks every BLOCKER/MAJOR finding raised in the run by its
    PEOS-assigned `(origin_review_number, finding_position)` reference;
    closure requires an explicit `historical_finding_dispositions` entry
    (`RESOLVED` / `ACCEPTED_RECLASSIFICATION` / `HUMAN_DECISION_REQUIRED`);
    omission and silent severity downgrades never close a finding;
    `APPROVE` is invalid while any BLOCKER/MAJOR remains `OUTSTANDING`;
    **`HUMAN_DECISION_REQUIRED` is terminally non-converged — it clears a
    finding's `OUTSTANDING` flag without resolving it, and convergence
    (`APPROVE`/`APPROVED`) is never reachable while any historical
    BLOCKER/MAJOR finding carries that disposition, checked
    independently of, and before, the plain `OUTSTANDING` gate (routes to
    `HUMAN_GATE` #6, not `FAILED`)**; every historical finding's final
    disposition appears in the Delivery Report.
17. **Round Packet (NEW).** `peos/round_packet.py` builds the
    deterministic, orchestrator-owned context object (ten elements,
    Model section above) supplied to every fresh Claude/Codex
    invocation; agent conversation history is never relied on as an
    authoritative context channel; Codex's AC assessment is checked
    against the Round Packet's complete AC set.
18. **Ledger serialization security (NEW).** `peos/ledger.py` writes
    only an explicit field allowlist, sanitized and bounded; raw
    stdout/stderr, environment dumps, credential values/files, and
    arbitrary configuration blobs are never written, under any
    allowlist membership; tests inject synthetic secrets into task
    text, summaries, finding descriptions, evidence, and error paths and
    assert their absence individually.
19. **Ledger filesystem containment (NEW).** `.peos/runs/` is
    gitignored; every path component (`.peos`, `runs`, the run
    directory) is checked individually for a symlink and rejected
    (`FAILED`) if found; writes are contained beneath the canonical
    `.peos/runs/` path; run directories use exclusive creation; file
    writes are atomic; the ledger is excluded from isolated-workspace
    copying and from reconciliation at every cycle count; the ledger is
    never supplied as agent-controlled repository state.
20. **Ledger identity, durability, retention (NEW).** Every ledger
    carries schema version, run ID, timestamps, baseline/governing-spec
    identity, effective `max_cycles`, phase/cycle state, and sanitized
    finding/dispute/verification summaries; a write failure is a visible
    `FAILED` outcome; retention keeps the most recent 20 completed/
    failed run directories, cleaning up only PEOS-owned inactive run
    directories and never an active run; the ledger cannot authorize
    execution, establish engineering acceptance, or override repository/
    spec state, and is not a Tier-2 resume checkpoint.
21. **Static external context (supersedes Requirement 12).**
    `peos/static_context.py` resolves a spec-declared external-context
    requirement only to a regular, readable, repository-resident,
    symlink-free file with a deterministic content identity; a
    containment/safety violation is `FAILED`; a missing/unresolvable
    requirement is `HUMAN_GATE` #11; resolved artifacts are staged into
    the isolated workspace and named in the Round Packet; no agent and
    no orchestrator process gains any new live external-fetch
    capability in V2. **The resolved artifact's content identity is
    re-verified, unchanged, before every subsequent agent invocation
    that consumes it: any drift — in content hash, path containment,
    file type/readability, or a staged-copy mismatch — fails the run
    closed (`FAILED`) before the next invocation runs, never a silent
    re-hash, never a Delivery Report note, and never a `HUMAN_GATE`;
    adopting a changed artifact requires a new PEOS run (AC-39).**
22. **Evaluation precedence (NEW).** Every review payload is evaluated
    in the fixed order: contract/schema validity → dispute validity →
    outstanding historical findings (stage 3, itself ordered as: 3a. any
    historical `HUMAN_DECISION_REQUIRED` disposition, checked first and
    unconditionally, before any verdict is interpreted → `HUMAN_GATE` #6;
    3b. `APPROVE` + an `OUTSTANDING` BLOCKER/MAJOR register entry →
    `FAILED`; 3c. `APPROVE` + an overruled active dispute → `FAILED`) →
    deterministic verification (already gated earlier) → Codex verdict →
    convergence/exhaustion decision. `APPROVE` combined with an
    outstanding BLOCKER/MAJOR register entry, or with an overruled active
    dispute, fails at stage 3b/3c (`FAILED`), never reaching convergence
    as an `APPROVE`. `APPROVE` combined with any historical
    `HUMAN_DECISION_REQUIRED` disposition instead resolves at stage 3a to
    `HUMAN_GATE` #6 — never `FAILED` and never `APPROVED` — because that
    disposition reflects a legitimate reviewer determination, not a
    malformed payload. A governing specification's content hash and the
    isolated workspace's fingerprint are both re-checked at this same
    point every round (Requirement 11), not only once per run.

## Acceptance Criteria

- [ ] **AC-1** A run with `--max-cycles` omitted, where Codex returns
  `CHANGES_REQUIRED` **twice** before `APPROVE` (cycle 0 →
  `CHANGES_REQUIRED`, remediation cycle 1 → `CHANGES_REQUIRED`,
  remediation cycle 2 → `APPROVE`), reaches `APPROVED` under the V2
  default of 3 — i.e. it converges within the default budget using more
  remediation cycles than V1 ever permitted. This scenario specifically
  requires **two** remediation cycles to succeed, which cannot pass
  under a reintroduced `max_cycles=1` default (that default would stop
  at `HUMAN_GATE` #8 after remediation cycle 1, since cycle 1's closure
  review is still `CHANGES_REQUIRED`); a single-remediation-cycle
  fixture (`CHANGES_REQUIRED` then `APPROVE`) would pass identically
  under *either* default and therefore cannot catch a reintroduction of
  the "default behaves like `max_cycles=1`" BLOCKER — this is why the AC
  requires two cycles, not one.
- [ ] **AC-1b** A run with `--max-cycles 1` explicitly passed and a
  Codex review that returns `CHANGES_REQUIRED` once behaves identically
  (phase sequence modulo the Planning-label rename, gate IDs, exit code)
  to today's SPEC-001/SPEC-003 implementation for the same inputs —
  exactly one remediation cycle, then convergence or `HUMAN_GATE` #8.
- [ ] **AC-2** A run with `--max-cycles 3` where Codex returns
  `CHANGES_REQUIRED` after remediation cycle 1 and remediation cycle 2
  but `APPROVE` after remediation cycle 3's closure review reaches
  `APPROVED` (does not stop early at any intermediate bound) — 1 initial
  Claude implementation + 3 remediation calls, 1 initial Codex review +
  3 closure reviews, in the worst case before converging.
- [ ] **AC-3** A run with `--max-cycles 3` where Codex still returns
  `CHANGES_REQUIRED` after cycle 0 and all 3 remediation cycles stops at
  `HUMAN_GATE` #8 with a reason naming the configured cycle count and
  the outstanding register/dispute state — never a 4th remediation
  cycle, never `APPROVED`.
- [ ] **AC-4** `--max-cycles 0`, a negative value, or a value above `5`
  produces a `FAILED` input-validation report (`_report_input_failure`-
  shaped), never a traceback, never a silently clamped value. `1`
  through `5` are all accepted.
- [ ] **AC-5** Context Recovery runs and is reflected in the Delivery
  Report (a named related spec/decision/validation record appears)
  even on a run that stops at `HUMAN_GATE` #1 (no governing spec) —
  i.e. Context Recovery's own output does not depend on Planning
  having succeeded.
- [ ] **AC-6** A governing specification containing a `## Design
  Context` section naming an artifact path that does not resolve to a
  present, regular, repository-resident file produces `HUMAN_GATE` #11
  before any workspace is created or either agent is invoked.
- [ ] **AC-7** A governing specification containing a `## Design
  Context` section naming an artifact path that *does* resolve produces
  a `PlanArtifact` recording that path and its content identity, the
  artifact is staged into the isolated workspace, and the run proceeds
  past Planning normally.
- [ ] **AC-8** Given a remediation result whose `summary` contains
  `DISPUTE[0.2]: <evidence>` referencing an `OUTSTANDING` register entry,
  and a subsequent closure review whose structured output sets
  `reviewer_overrules_dispute=true` with `addressed_dispute_references`
  including `"0.2"`, the run stops at `HUMAN_GATE` #10 on that cycle,
  even if `max_cycles` has not been reached.
- [ ] **AC-9** Given the same dispute but `reviewer_overrules_dispute=
  false`, the run does not stop at #10 and proceeds through the normal
  per-cycle convergence check on any remaining findings/register state.
- [ ] **AC-10** A closure-review call made when no dispute is active
  this cycle that nonetheless returns `reviewer_overrules_dispute` or
  `addressed_dispute_references` as a non-null value is rejected as a
  schema-contract violation (`FAILED`), symmetrically with a
  dispute-active cycle whose closure review returns either field as
  `null`.
- [ ] **AC-11** The Run Ledger file for a completed run contains no
  value from any result object's raw `stdout`/`stderr`/`raw_stdout`/
  `raw_stderr` field, and no literal secret value, given synthetic
  secrets independently planted in each of: task text, summaries,
  finding descriptions, dispute evidence, and error paths on test
  doubles (same style of test as SPEC-003 AC-10/AC-11, extended to this
  wider set of injection points).
- [ ] **AC-12** The Run Ledger is written (and inspectable on disk)
  after every phase transition in a multi-cycle run, including a run
  that is interrupted (process killed) between cycles — the last
  successfully written ledger reflects the last completed phase, not an
  empty, stale, or partially-written one (atomic replace, AC-30).
- [ ] **AC-13** `.peos/runs/` is present in `.gitignore` and a completed
  run's ledger directory is confirmed absent from `git status
  --porcelain` output.
- [ ] **AC-14** The Delivery Report for a multi-cycle `APPROVED` run
  that ended with at least one outstanding `minor`/`info` finding
  contains an explicit "Unresolved MINOR findings" section naming it —
  it is not silently absent just because the run converged.
- [ ] **AC-15** The full existing PEOS test suite
  (`tests/test_peos_*.py`) remains green with `--max-cycles 1`
  (V1-equivalent mode), and no existing assertion is weakened (only
  updated where the Planning-label rename or the new default requires
  it) to make it pass.
- [ ] **AC-16** No change in this spec's eventual implementation alters
  AI Power Lab simulation physics, backend/frontend behavior, Scenario
  A/`SPEC-002` behavior, or `.github/workflows/ci.yml`.
- [ ] **AC-17** No change in this spec's eventual implementation adds a
  new credential, environment variable, MCP server grant, or tool grant
  to either agent, or to the orchestrator process, beyond what
  SPEC-003/Decision-0002 already allow.
- [ ] **AC-18** A finding raised at `origin_review_number=0,
  finding_position=1` at `blocking` severity, left unmentioned in every
  subsequent review's `historical_finding_dispositions`, remains
  `OUTSTANDING` through every later cycle and blocks `APPROVE` at the
  final cycle even though that cycle's own findings list is empty.
- [ ] **AC-19** A finding raised at `blocking` severity on one cycle,
  re-reported by a later review as a *new*, differently-worded `minor`
  finding with no `ACCEPTED_RECLASSIFICATION` disposition entry
  referencing the original, leaves the original reference
  `OUTSTANDING` at `blocking` severity — the new, milder finding does
  not retire the old reference.
- [ ] **AC-20** A review payload with `verdict="APPROVE"` while the
  register has any `OUTSTANDING` entry at `blocking`/`major` severity is
  rejected as invalid structured output (`FAILED`), never reaching
  convergence as an approval. (Distinct from AC-38: a finding
  dispositioned `HUMAN_DECISION_REQUIRED` is *not* `OUTSTANDING` by the
  time this check runs, so this AC alone does not exercise that case —
  AC-38 covers it separately and resolves to `HUMAN_GATE`, not `FAILED`.)
- [ ] **AC-21** A review payload with `verdict="APPROVE"` combined with
  `reviewer_overrules_dispute=true` for a currently-active dispute is
  rejected as invalid structured output (`FAILED`), not treated as
  `APPROVED` and not treated as a plain `HUMAN_GATE` #10.
- [ ] **AC-22** A `DISPUTE[...]` line with a malformed reference (e.g.
  non-numeric, wrong delimiter, or a reference to a non-`OUTSTANDING` or
  nonexistent register entry) or with empty evidence after sanitization
  is rejected as invalid structured output; that remediation cycle's
  result is `FAILED`, with the offending line and reason recorded.
- [ ] **AC-23** An evidence string that `sanitize_human_text` reduces to
  empty or whitespace-only is treated identically to AC-22's
  empty-evidence case (invalid, `FAILED`), not silently coerced into "no
  dispute."
- [ ] **AC-24** A closure review whose `addressed_dispute_references`
  omits any currently-active dispute's reference is rejected as invalid
  structured output (`FAILED`), even if every reference it *does*
  include is handled correctly.
- [ ] **AC-25** A Codex review payload whose acceptance-criteria
  assessment covers fewer than the complete AC set the Round Packet
  supplied is rejected as incomplete and cannot produce `APPROVE` — a
  partial-coverage `APPROVE` is `FAILED`, not a valid approval.
- [ ] **AC-26** A deterministic verification failure on remediation
  cycle `N` (`N >= 1`) produces `FAILED` immediately: no Codex closure
  review is invoked for that cycle, the failure is never counted toward
  or confused with "iteration exhaustion," and there is no silent retry.
- [ ] **AC-27** *(iteration exhaustion itself is covered by AC-3;
  retained here only as a cross-reference per the adversarial-coverage
  checklist — no separate test beyond AC-3 is required.)*
- [ ] **AC-28** *(secret-injection coverage is covered by AC-11, already
  extended to the five required injection points; retained here only as
  a cross-reference.)*
- [ ] **AC-29** A `.peos` directory, a `.peos/runs` directory, or a
  specific run directory that is (or whose path contains) a symlink at
  any component is rejected: the ledger write for that run fails closed
  (`FAILED`), and the symlink is never followed or written through.
- [ ] **AC-30** Ledger writes are atomic (temp file + `os.replace`) and
  run-directory creation is exclusive; a simulated process kill mid-write
  leaves either the previous valid ledger file or no file for that
  write — never a truncated or syntactically invalid JSON file on disk.
- [ ] **AC-31** With 21 or more completed/failed run directories present
  under `.peos/runs/` before a new run starts, retention cleanup leaves
  exactly the 20 most recent afterward, and never deletes a directory
  lacking a valid, terminal PEOS ledger or belonging to the currently
  active run (even if that run is the oldest by creation time).
- [ ] **AC-32** *(missing static context is covered by AC-6, generalized
  from the original Pixso-specific framing to the general static-context
  mechanism; retained here only as a cross-reference.)*
- [ ] **AC-33** A declared static-context path that resolves outside the
  repository root, or through a symlink at any path component, produces
  `FAILED` — never `HUMAN_GATE`, and never a read of the escaped file's
  contents. This is a Planning-time/initial-resolution containment
  check; see AC-39 for the separate, later-round identity-drift check
  that applies once an artifact has already resolved successfully.
- [ ] **AC-34** Codex's "no working-tree modification" fingerprint check
  is independently re-run and enforced on the initial review (cycle 0)
  **and** on every remediation cycle's closure review — a simulated
  out-of-band workspace mutation detected only on, e.g., remediation
  cycle 2 still produces the same fail-closed result cycle 0's check
  would have produced.
- [ ] **AC-35** The governing specification file's content hash recorded
  at Planning is re-checked before every Claude implementation/
  remediation round and before every verification round; a simulated
  on-disk change to that file between Planning and a later remediation
  cycle produces `FAILED`, not a silent continuation with stale
  assumptions.
- [ ] **AC-36** The final reconciliation step's observable behavior
  (what it inspects, what it reports) is identical whether a run
  converged at cycle 0 or at remediation cycle 5, and `.peos/runs/`
  contents are absent from what reconciliation touches or reports at
  every cycle count.
- [ ] **AC-37** Each fresh Claude/Codex invocation in a multi-cycle run
  receives a `RoundPacket` containing all ten elements of Requirement 17,
  and no element the orchestrator is responsible for supplying is ever
  sourced from a prior subprocess's stdout/transcript rather than from
  the Round Packet/ledger/repository state directly.
- [ ] **AC-38** (Adversarial, `HUMAN_DECISION_REQUIRED`.) A run where
  cycle 0's review raises a `major` finding `F1` (reference `0.1`), and a
  later closure review's `historical_finding_dispositions` dispositions
  `0.1` as `HUMAN_DECISION_REQUIRED` while that **same** closure review's
  overall `verdict` is `APPROVE`, produces `HUMAN_GATE` #6 — never
  `APPROVED`, and never `FAILED` — regardless of `0.1`'s resulting
  `OUTSTANDING` flag in the register. Evaluation Precedence's stage 3a
  (Requirement 22) is reached and resolves the payload before stage
  3b's `OUTSTANDING`/`APPROVE` check, and before the verdict is
  otherwise interpreted as an approval.
- [ ] **AC-39** (Static-context identity drift.) A declared static-context
  artifact hashed to content identity `A` at Planning, then mutated on
  disk to content identity `B` before a later Claude or Codex invocation
  that consumes it, produces `FAILED` **before** that invocation is
  made — the agent is never invoked with either the stale (`A`) or the
  new (`B`) content, PEOS never silently recomputes and adopts `B` as
  the new identity, and the result is neither a `HUMAN_GATE` nor a
  Delivery Report note. The only way to adopt the changed artifact is a
  new PEOS run.

## Verification Plan

| AC | Verification | Layer |
|----|---------------|-------|
| AC-1 | New unit test in `tests/test_peos_workflow.py`: `--max-cycles` omitted, fake `codex_runner` returning `CHANGES_REQUIRED, CHANGES_REQUIRED, APPROVE` across cycle 0 and remediation cycles 1–2, assert `outcome="APPROVED"` after 2 remediation cycles under the default budget of 3; the same test additionally re-runs the identical fixture with `--max-cycles 1` and asserts `HUMAN_GATE` #8 instead, so the test fails if the default silently reverts to 1 | Unit |
| AC-1b | `tests/test_peos_workflow.py`: `max_cycles=1` explicit, fake `codex_runner` returning `CHANGES_REQUIRED` once, assert identical phase/gate/outcome shape to today's existing one-cycle test | Regression |
| AC-2 | `tests/test_peos_workflow.py`: fake `codex_runner` returning `CHANGES_REQUIRED` for the cycle-0 initial review, then `CHANGES_REQUIRED, CHANGES_REQUIRED, APPROVE` across the three closure-review calls, with `max_cycles=3` — four Codex verdicts total — assert `outcome="APPROVED"` and exactly 4 total Claude calls (1 implementation + 3 remediation) and 4 total Codex calls (1 initial + 3 closure) | Unit |
| AC-3 | `tests/test_peos_workflow.py`: fake `codex_runner` always `CHANGES_REQUIRED` with `max_cycles=3`, assert `HUMAN_GATE` #8 after exactly 1 initial + 3 closure Codex calls, no 5th Claude/Codex call | Unit |
| AC-4 | `tests/test_peos_cli.py`: `--max-cycles 0` / `-1` / `6`, assert `FAILED` report, no workflow invocation; `--max-cycles 1..5` each accepted | Unit |
| AC-5 | `tests/test_peos_context.py`: `spec_resolver` returns `gate_reason` (no spec), assert the returned `RunResult`/ledger still carries non-empty Context Recovery output | Unit |
| AC-6 / AC-7 | `tests/test_peos_plan.py` / `tests/test_peos_static_context.py` (new): spec text with a `## Design Context` section naming a missing vs. present, resolvable path | Unit |
| AC-32 | Same fixture/assertion as AC-6 (cross-reference; no separate test) | Unit |
| AC-8 / AC-9 / AC-10 | `tests/test_peos_codex_agent.py` and `tests/test_peos_workflow.py`: payload fixtures for each of the three `reviewer_overrules_dispute`/`addressed_dispute_references` null/non-null combinations | Unit |
| AC-11 | `tests/test_peos_ledger.py` (new): five parametrized cases (task text, summary, finding description, dispute evidence, error path), each independently planting a synthetic secret and asserting its absence from the written JSON | Unit |
| AC-12 / AC-30 | `tests/test_peos_ledger.py`: integration test asserting a ledger file exists mid-run, plus a simulated interrupted write (kill between temp-file write and `os.replace`) leaves the prior valid file intact | Unit |
| AC-13 | `tests/test_peos_ledger.py`: `.gitignore` contains `.peos/runs/`; `git status --porcelain` on a repo fixture with a completed run shows no ledger paths | Unit |
| AC-14 | `tests/test_peos_report.py`: `RunResult` with an `APPROVE`d review carrying one unresolved `minor` finding, assert the new section is present and names it | Unit |
| AC-15 | `python -m pytest -q` over the full `tests/` directory with `--max-cycles 1` fixtures | Regression |
| AC-16 | Full `python -m pytest -q` plus `npm run lint && npm run typecheck && npm run build`, unchanged from SPEC-003 AC-15 | Regression |
| AC-17 | Manual diff review of `peos/sandbox.py` confined to "no lines changed in this file by this spec's implementation" (V2 touches no sandbox/auth code at all) | Manual / code review |
| AC-18 / AC-19 | `tests/test_peos_findings_register.py` (new): omission-across-cycles and silent-severity-downgrade fixtures, assert `OUTSTANDING` persists | Unit |
| AC-20 / AC-21 | `tests/test_peos_codex_agent.py`: `APPROVE` payload fixtures with outstanding register state / overruled active dispute, assert rejection | Unit |
| AC-22 / AC-23 | `tests/test_peos_workflow.py`: malformed-reference, unknown-reference, empty-evidence, and sanitizer-truncated-evidence `DISPUTE[...]` fixtures, assert `FAILED` with the specific reason recorded | Unit |
| AC-24 | `tests/test_peos_codex_agent.py`: closure-review fixture with two active disputes where `addressed_dispute_references` names only one, assert rejection | Unit |
| AC-25 | `tests/test_peos_codex_agent.py`: review payload whose AC assessment omits one AC from the Round Packet's complete AC set, assert rejection | Unit |
| AC-26 | `tests/test_peos_workflow.py`: verification-failure fixture on remediation cycle 2, assert `FAILED` with no Codex call for that cycle | Unit |
| AC-27 | Same fixture/assertion as AC-3 (cross-reference; no separate test) | Regression |
| AC-28 | Same fixtures/assertions as AC-11 (cross-reference; no separate test) | Unit |
| AC-29 / AC-33 | `tests/test_peos_ledger.py` / `tests/test_peos_static_context.py`: symlinked `.peos`, `.peos/runs`, run directory, and static-context path fixtures (filesystem test using a real temp directory and real symlinks), assert `FAILED` and no follow-through | Unit |
| AC-31 | `tests/test_peos_ledger.py`: 21 synthetic completed-run directories (mix of PEOS-owned and foreign/non-PEOS directories, plus one marked active), assert retention leaves exactly 20 PEOS-owned inactive directories and preserves the active one and any non-PEOS directory untouched | Unit |
| AC-34 | `tests/test_peos_workflow.py`: fingerprint-mismatch fixture injected only at remediation cycle 2 (not cycle 0), assert the same fail-closed result as a cycle-0 mismatch | Unit |
| AC-35 | `tests/test_peos_workflow.py`: governing-spec file mutated on disk between Planning and remediation cycle 1, assert `FAILED` | Unit |
| AC-36 | `tests/test_peos_workflow.py`: reconciliation-behavior assertions compared across a cycle-0-convergence run and a cycle-5-convergence run (same assertions, both must pass identically); assert `.peos/runs/` absent from reconciliation's inspected/reported paths in both | Unit |
| AC-37 | `tests/test_peos_round_packet.py` (new): assert all ten `RoundPacket` elements are present and sourced from ledger/repository state, never from a prior subprocess's captured stdout | Unit |
| AC-38 | `tests/test_peos_findings_register.py` / `tests/test_peos_workflow.py`: adversarial fixture — cycle 0 raises `major` finding `0.1`; the closure review's `historical_finding_dispositions` sets `0.1` to `HUMAN_DECISION_REQUIRED` and the same payload's `verdict` is `"APPROVE"`; assert `evaluate_cycle` returns `HUMAN_GATE` #6, never `APPROVED`, never `FAILED` | Unit |
| AC-39 | `tests/test_peos_static_context.py` (new): a staged static-context artifact hashed `A` at a simulated Planning step; the on-disk file is mutated to hash `B`; assert the next simulated Claude/Codex invocation is never made and the run result is `FAILED` before that call | Unit |

## Safety and Governance Invariants (carried over, unchanged)

Restated from SPEC-003's "Security Invariants" section because V2's
implementer and reviewer must re-confirm every one of these still holds
after the implementing change, even though this spec's Scope does not
touch `peos/sandbox.py`:

- Disposable, isolated `HOME` for every agent invocation.
- Isolated, disposable repository workspace; the authoritative
  repository is never operated on directly by either agent.
- No Git credentials, no push capability, for either agent.
- No unrestricted user/project/local configuration; no MCP servers; no
  plugins — for either agent, in every cycle, not only the first, and
  no such grant for the `peos` orchestrator process either (Resolved
  Decision 5).
- No credential material ever copied into the repository, the
  reconciled workspace, a log line, a report field, or the Run Ledger
  (Requirement 18).
- PEOS fails closed whenever a precondition — existing or newly added by
  this spec (`--max-cycles` validity, static-context resolution,
  dispute-schema consistency, ledger containment) — cannot be
  established.
- PEOS still never merges, pushes, tags, force-pushes, rewrites history,
  or creates a PR, under any outcome, at any cycle count.

## Known Limitations

- The `DISPUTE[ref]:` text convention (Option A) is a prompt-level
  contract, not a machine-enforced one on Claude's side. A remediation
  `summary` containing **no line that even superficially matches**
  `^DISPUTE\[` is simply "no dispute" — business as usual, an
  unremediated finding that resurfaces at the next review. A line that
  *does* match the pattern but is malformed, references an unknown or
  non-outstanding finding, or carries empty/sanitizer-truncated evidence
  is a different case: it is **invalid structured output** (`FAILED`),
  per Requirement 8 — this is a deliberate strengthening over treating
  every unrecognized format as silently equivalent to no attempt at
  all, closing a Codex-review finding.
- `reviewer_overrules_dispute` is a single aggregate boolean per cycle,
  not a per-finding disposition for *every* dispute (Option B's full
  per-finding array, not proposed). A cycle with multiple simultaneous
  active disputes where the reviewer overrules only one is reported as
  "overruled" in aggregate; `addressed_dispute_references` guarantees
  every active reference was at least considered, but not that each got
  an individually distinguishable verdict in the schema itself. The
  Delivery Report's free-text "Findings and resolutions" rendering is
  expected to carry the per-dispute detail even though this schema
  field stays coarse — named explicitly so it is not mistaken for a
  finer-grained structured guarantee it does not make.
- The Outstanding Findings Register is **run-local only**. It tracks
  findings raised by reviews within the current PEOS invocation; it has
  no awareness of a BLOCKER/MAJOR a *previous, separate* run may have
  left at `HUMAN_GATE`. A human re-running PEOS on the same task after a
  prior `HUMAN_GATE` starts a fresh register. Cross-run finding tracking
  is not designed here.
- A declared static-context artifact's content identity is pinned at
  Planning and re-verified before every subsequent agent invocation that
  consumes it (Static External Context section, Requirement 21, AC-39).
  If the artifact's content, path containment, file type/readability, or
  staged-copy fidelity drifts after Planning, the run **fails closed**
  (`FAILED`) before the next invocation — it never silently refreshes
  the pinned identity, never falls back to a Delivery Report note, and
  never routes to `HUMAN_GATE`. This is a deliberate, normative
  narrowing from an earlier draft that left the response open; it is
  named here only because the only way to adopt the changed artifact is
  for the Human Engineering Lead to start a **new** PEOS run — Planning
  in that new run resolves and hashes the artifact fresh. This is not a
  design gap; it is the documented consequence of a fail-closed rule.
- Tier 2 resumability (actually continuing a run) is not designed here
  at all, not merely simplified — see Non-Goals and Resolved Decision 4.
- Planning's Static External Context parsing is the same "indented line
  under a recognized heading" deterministic convention
  `peos/verification_plan.py` already uses, with the same known
  limitation that spec: it recognizes one fixed authoring convention,
  not arbitrary spec prose referring to an external artifact.
- This spec does not re-verify or re-state SPEC-003's residual risk
  around Codex's shell tool being able to *read* its own `auth.json`
  under `--sandbox read-only` — unchanged, still an accepted V1/V2
  residual risk per that spec.
- The Round Packet's correctness depends entirely on the orchestrator's
  own bookkeeping (the register, the active-dispute set, the recorded
  AC set) being accurate; a defect in that bookkeeping is a single point
  of failure for convergence correctness, the same class of residual
  risk every other orchestrator-owned piece of state in this spec
  already carries, named here for honesty rather than claimed away.

## Resolved Engineering Lead Decisions

The Human Engineering Lead has already made the following seven
decisions; none of them is open, and no implementation may silently
revisit any of them without a new round of explicit sign-off.

**Relationship to SPEC-001/SPEC-003:** SPEC-004 EXTENDS SPEC-001. It
does not rewrite historical SPEC-001; SPEC-001 and SPEC-003 remain
authoritative wherever this document does not explicitly extend their
behavior. SPEC-004's extensions, enumerated for traceability: the
bounded multi-remediation-cycle loop and its cycle-0/remediation-cycle
semantics (replacing V1's unrolled single cycle); Context Recovery;
Planning's extension beyond spec-selection into `max_cycles`-override
and static-context parsing; the Outstanding Findings Register; the
Round Packet; the Option-A dispute mechanism's three new `REVIEW_SCHEMA`
fields; the Run Ledger (with its serialization-security, filesystem-
containment, and identity/retention rules); the Static External Context
declaration mechanism; the generalization of Human Gates #6/#8/#11 and
the addition of Human Gate #10; and the enriched Delivery Report. Every
other requirement, acceptance criterion, invariant, and limitation in
SPEC-001/SPEC-003 stands as written.

1. **No autonomous new-spec approval, and no autonomous new-spec
   drafting.** Planning remains selection-only (Requirement 2); no
   agent authors specification prose or treats self-authored prose as
   governing input. A future version letting an agent draft a
   specification *stub* that still requires full human approval before
   it governs implementation remains a possible Future Direction item
   only — not adopted in V2.
2. **`max_cycles` default 3, hard cap 5.** `peos/cli.py --max-cycles`
   accepts `1..5`; omitting the flag uses 3; `max_cycles` counts
   remediation cycles only, never the fixed cycle-0 initial
   implementation/review (Cycle semantics, Requirement 6).
3. **Run Ledger at `.peos/runs/`, gitignored, orchestrator-owned,
   diagnostic-only, with a 20-run retention cap.** Location and
   retention are fixed by this spec, not left to implementer discretion
   (Requirements 18–20).
4. **No Tier-2 resume in V2.** The Run Ledger (Tier 1) is diagnostic
   only; `peos --resume <run-id>` actually continuing a run is deferred
   entirely, not merely simplified (Requirement 13, Requirement 20).
5. **No general MCP broker in V2.** Neither agent, nor the `peos`
   orchestrator process, gains any new live external-fetch capability.
   Static external context is always a manual, human-provisioned,
   repository-resident artifact (Requirement 21).
6. **Lightweight Option A for disagreement handling.** One aggregate
   `reviewer_overrules_dispute` boolean, plus the two small additive
   fields needed for closure-review completeness
   (`addressed_dispute_references`) and historical-finding bookkeeping
   (`historical_finding_dispositions`) — not Option B's full per-finding
   disposition array for every finding every cycle (Requirement 8,
   Known Limitations).
7. **SPEC-004 extends, not supersedes, SPEC-001.** Stated above and at
   the top of this document; this resolves the original draft's
   Unresolved Decision 7 (gate-catalog authority) in favor of extension:
   SPEC-001 Section 7's text is left as a historical record, and this
   spec's Human Gate catalog is the authoritative one for V2 runs
   without editing SPEC-001's own text in place — the same treatment
   SPEC-003 already gives Decision 0002.

## Future Direction

Beyond Tier 2 resumability and Option B's richer disagreement schema
(both already named above): a Context Recovery step that also considers
prior Run Ledgers (not only `docs/` artifacts) when planning a new task
in an area a previous run already touched, which would also be the
natural place to eventually give the Outstanding Findings Register
cross-run awareness (explicitly not designed in V2 — see Known
Limitations); a richer Planning step that can decompose one human intent
into multiple governed sub-tasks each resolving to its own
specification, still with zero autonomous authoring; and, for a future
Pixso dogfood specifically, consuming an explicitly exported/static
design artifact or other approved repository-contained representation
through the same Static External Context mechanism (Requirement 21) —
never a live Pixso/MCP broker. None of these is proposed now, per the
brief's own instruction to prefer the smallest architecture that
delivers the loop reliably tonight.
