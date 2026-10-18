# 0004 — PEOS Durable Run Resume: trust model, phase semantics, and scope boundary

**Status:** Accepted — these architectural decisions are selected by the
Human Engineering Lead and binding on any future implementation. The
independent Codex architecture/specification review of SPEC-007 and this
record (ten rounds; see SPEC-007's own "Codex Architecture Review" log)
has now closed with an `APPROVE` verdict and zero outstanding findings —
that gate (mirroring ADR-0003/SPEC-006's own precedent) is satisfied.
`docs/specifications/SPEC-007-peos-durable-run-resume-v1.md` itself
**remains Draft** regardless: this review closing is a precondition for
the Human Engineering Lead's separate, not-yet-given final specification
approval, never a substitute for it, and accepting this record was never
itself implementation authorization.

**Remediation note.** An independent Codex architecture review of this
record alongside SPEC-007 v0.2 returned `CHANGES_REQUIRED` with 15
findings (5 blocking, 9 major, 1 minor — an earlier draft of this note
miscounted these as 16/6; corrected here) — real, concrete gaps grounded
in the actual code this specification extends (e.g. `discard_workspace`'s
real implementation would have deleted the whole run directory, including
this record's own `RunCheckpoint`, under the literal workspace location
Decision 2 originally named; the existing Seatbelt profiles' rule
ordering would have shadowed the relocated workspace's own write
allowance; `gate()` always reconciles, which the new drift gate must
never do). v0.3 closed all 15 in place. A focused Round 2 re-review of
v0.3 confirmed 6 closed and found 9 still outstanding or only partly
closed, plus one new finding that the acceptance criteria were not
self-contained — most notably, **v0.3's own text had the shared run lock
releasing on `PAUSED_RETRYABLE`**, which would have let a new ordinary
task start while a paused run still existed, directly defeating Decision
6 below; this was corrected in v0.4, along with a manifest-based
restructuring of reconciliation recovery (a single fingerprint could not
safely drive it) and a retraction of a binding-based Codex-review-reuse
idea that conflicted with this record's own Decision 12. A third, focused
Round 3 re-review of v0.4 confirmed 6 of the 9 remaining items closed and
found 3 still outstanding, plus one new finding — most notably, **v0.4's
own proposed fix for the lock-reclamation race was itself still unsafe**:
it relied on a plain `os.rename` of a replacement lock file, which is
unconditional replacement, not compare-and-swap, and cannot prevent two
reclaimers from each clobbering the other's belief that it holds the lock
exclusively. v0.5 corrected this with an `O_EXCL`-creation retry loop,
closed a bootstrap-ordering gap in Planning's own first checkpoint write,
and closed two remaining gaps in the reconciliation manifest (leftover
temp-file debris, and an internally-contradictory "incremental write"
claim). A fourth, focused Round 4 re-review of v0.5 found that **the
`O_EXCL`-creation retry loop was, itself, still unsafe on its second
attempt**: POSIX `unlink` operates on a path, not the specific file a
reclaimer actually inspected, so a delayed unlink from one racer can
remove a *different* racer's already-live replacement lock rather than
the stale one it originally observed, with no error surfacing to reveal
the mistake. v0.6 changes the actual mechanism rather than patching the
retry logic a third time: reclamation now uses `fcntl.flock`, a kernel-
enforced advisory lock, held only briefly around the "read current
reservation, decide, write new one" sequence — with the lock file itself
never deleted or recreated at all, removing the path-vs-identity
confusion at its root — while the *logical* reservation (whether a
`PAUSED_RETRYABLE` run still holds the slot) is kept correctly separate,
decided purely from the checkpoint's own durable state, never from
process liveness, which no OS-level lock tied to a process's lifetime
could ever represent for a run whose defining property is that its
process is gone while its reservation persists. Round 4 also proposed
closing the remaining half of the bootstrap-ordering gap with a
time-bounded grace period, reasoning a fixed clock comparison was safer
than a liveness check — Round 5 found this traded one unsafe heuristic
for another (a genuinely live, merely slow bootstrap can exceed any
fixed timeout, and nothing stopped the original process from continuing
after its slot was stolen on that basis), and two wording refinements to
the acceptance criteria governing the mandatory post-resume Codex call.
v0.7 returns to a liveness check for this one specific case after all —
but a *positive* `os.kill(pid, 0)` existence probe, not a timeout,
correctly distinguished from the *general*, checkpoint-bearing case
where liveness must never override a durable reservation — and adds the
lock write's own `fsync`-before-release durability requirement and
explicit fail-closed handling of corrupted lock content, which Round 5
also found missing. A sixth, focused Round 6 re-review confirmed the
liveness check's own correctness (never incorrectly steals a slot) while
correctly pressing on its converse (PID reuse can make it incorrectly
conservative instead) — closed by naming this precisely as an accepted,
one-sided trade, with a human-initiated manual recovery path, never by
trying to eliminate it — and found two further durability gaps in the
lock write's own mechanics (the file's first creation needed the same
containing-directory `fsync` the checkpoint already requires; the write
step needed to account for a short `os.write` return rather than
assuming one call always writes every byte), both closed in v0.8. A
seventh, whole-document review of v0.8 confirmed all four Round 6 fixes
closed and then found one further, genuinely architectural gap beyond
the lock-write mechanics the prior six rounds had been concentrated on:
the lock's "hold it only briefly, then release" design, while correct
for preventing two ordinary tasks from racing on the reservation itself,
never actually prevented two concurrent `resume` attempts for the *same*
paused run (or a `resume` racing an `abandon`) from each passing their
own brief check in turn and then executing concurrently once each had
released its own brief flock — a missing execution-ownership contract,
not a further locking refinement. v0.9 closes this by holding the
`flock` for a holder's entire active execution (not merely the initial
decision), correctly separating the durable, checkpoint-based
*reservation* from process-bound *execution ownership*, which `flock`'s
own release-on-exit semantics are exactly suited to represent. An eighth
review of v0.9 then found one further, concrete bug in the reservation
write's own byte ordering: truncating the file to zero *before* writing
new content makes it briefly, genuinely empty — exactly the state the
procedure's own rule reads as "slot free" — so a crash in that narrow
window could durably leave a paused run's reservation looking free. v0.10
fixes this by reordering to write-first, truncate-last, so the file is
never observably empty except when genuinely never claimed. A ninth
review of v0.10 found that fix, while correct as far as it went, left a
sharper counter-example open: a write interrupted partway through an
equal-length-or-shorter overwrite leaves old, un-overwritten tail bytes
in place, which can combine with the new prefix into a syntactically
perfect, strictly-parseable JSON object that names neither the old nor
the new reservation — invisible to any check based on JSON syntax alone,
since there are no trailing bytes to reject. v0.11 closes this
completely, not by further patching syntax checks, but by making the
reservation content self-verifying: the JSON payload is followed by its
own SHA-256 hash, and any partial overwrite is caught by a hash mismatch
regardless of whether the JSON portion happens to parse. None of the 13
decisions this record freezes were themselves wrong in direction; every
affected decision below is corrected in place — narrower, more precise
wording and, where a decision's own mechanism was underspecified or (in
the lock case, across eight successive review rounds) actually wrong or
incomplete, a concrete fix — never weakened in the direction of less
safety. See SPEC-007's own "Codex Architecture Review — Round 1" through
"— Round 9" sections for the complete, numbered mapping from finding to
fix.

## Context

SPEC-004 shipped the diagnostic Run Ledger (Tier 1 resumability) and
explicitly deferred actually continuing an interrupted run (Tier 2,
"Resolved Decision 4"), naming the unresolved hazards precisely: the
isolated workspace's survival is not guaranteed, the governing
specification may have changed on disk, and a Codex review already
consumed into a terminal outcome cannot be safely "re-entered" without
re-establishing every invariant SPEC-001/SPEC-003 already check fresh.
Real operation has since produced exactly the interruptions that
deferral anticipated — a failed Claude remediation invocation, and an
agent usage/session limit — both requiring manual human recovery.

A first draft of SPEC-007 (v0.1) proposed a `RunCheckpoint` artifact, a
`PAUSED_RETRYABLE` outcome, and a workspace-relocation strategy, built
from a direct inspection of this repository's actual current behavior
(not assumption): the Run Ledger's `last_completed_phase` field is set
unconditionally on every write, including a phase's mere *entry*,
conflating "started" with "finished"; the isolated workspace already
outlives its run today by omission (`discard_workspace` has zero callers
in `peos/workflow.py`) rather than by design; and the Outstanding
Findings Register has no serialization at all today, only a lossy
ledger summary. The Human Engineering Lead reviewed that draft, approved
its direction, and returned 13 specific architectural decisions
hardening and narrowing it before implementation — this record freezes
those decisions. Implementation is not yet authorized; this record
supports SPEC-007 v0.2, which incorporates all 13.

## Decision

1. **The diagnostic Run Ledger and the authoritative `RunCheckpoint` are
   two separate artifacts, never merged.** The ledger (`peos/ledger.py`)
   keeps its existing, lower-stakes diagnostic role and schema, extended
   only with new recognized `outcome` values. `RunCheckpoint` is a new,
   sibling artifact (`checkpoint.json`, same run directory), written
   through the same already-reviewed `peos.fsguard`-anchored, atomic,
   explicit-field-allowlist pattern `LedgerWriter` already uses, but is
   the artifact resume logic actually trusts (after live cross-
   validation) — the ledger is never promoted into that role.
2. **The isolated workspace (and its paired `home_dir`) is durable under
   the run-owned `.peos/runs/<run_id>/candidate/` subtree** —
   `.peos/runs/<run_id>/candidate/workspace/` and `.peos/runs/<run_id>/
   candidate/home/` — not system temp space. It survives ordinary
   process/session termination and a full machine restart because it now
   lives under the same fsguard-protected, repository-owned location the
   ledger and checkpoint already occupy. **The `candidate/` nesting is
   load-bearing, not cosmetic**: `discard_workspace`'s real, existing
   implementation removes `workspace.path`'s *parent* wholesale, so
   placing workspace/home directly under `.peos/runs/<run_id>/` (as
   originally drafted) would have deleted the ledger, checkpoint, and
   retained evidence alongside them on every cleanup; nesting one level
   deeper makes that same, unmodified function safe again. Relocating
   workspace/home under `repo_root` also requires the existing Seatbelt
   profiles (`build_verification_sandbox_profile`/`build_runtime_
   verification_sandbox_profile`) to place the `repo_root` write-deny rule
   *before* the workspace/home write-allow rules in the generated
   profile text, so the narrower allow for this run's own `candidate/`
   subpaths wins under Seatbelt's last-match-wins evaluation — a real,
   required rule-ordering fix to both profile builders, not merely a
   path parameter change.
3. **`PAUSED_RETRYABLE` is a new, non-terminal `Outcome` value**,
   reserved for a narrow, reliably-detectable class of execution-
   infrastructure interruption — never a label applied to an ordinary
   engineering, contract, or tool failure, and never auto-retried.
4. **Durable phase state is a true three-value model: `NOT_STARTED` /
   `ENTERED` / `COMPLETED`**, not a boolean. `ENTERED` is written
   atomically *before* a phase's work begins; `COMPLETED` is written
   atomically only after that work has produced and validated its
   authoritative result. `last_safely_completed_phase` advances only on
   a `COMPLETED` write. Correctness of hard-crash/machine-restart
   recovery depends entirely on this ordering, never on a signal handler
   running — a handler is an optional refinement that may record a more
   specific pause reason, never a requirement.
5. **Output from an interrupted, mutating Claude phase is untrusted,
   resumable candidate state — not corruption.** A workspace-identity
   mismatch discovered while resuming into a phase whose durable state is
   `ENTERED` (not `COMPLETED`) for `CLAUDE_IMPLEMENTATION`/`CLAUDE_
   REMEDIATION` specifically triggers a defined recovery procedure
   (revalidate governance/security invariants that do not depend on
   workspace content, verify workspace containment and run ownership,
   label the current content `UNTRUSTED_PARTIAL_CANDIDATE_STATE`, pin a
   fresh provisional `resume_candidate_workspace_identity`, re-invoke the
   same logical phase with explicit interrupted-phase context, consume no
   additional remediation cycle, and run full required verification once
   that retried call validly completes) rather than failing closed
   outright. The identical mismatch for a contractually non-mutating
   phase is not covered by this decision and remains a failure.
6. **At most one `ACTIVE` or `PAUSED_RETRYABLE` run per repository in
   V1.** Enforced by **one single, shared repository-level lock**
   (`.peos/run.lock`), acquired identically by ordinary task execution,
   `resume`, and `abandon` alike — not a separate marker file one entry
   point checks and a separate per-resume lock a different entry point
   checks, which left a gap between them. **The lock is released only on
   a terminal outcome — never when a run becomes `PAUSED_RETRYABLE`.** A
   lock whose recorded process is no longer live is reclaimable by
   ordinary execution **only if that same `run_id`'s checkpoint also
   shows a terminal outcome**; a dead process alone is not sufficient —
   a `PAUSED_RETRYABLE` run's process dying is the expected, central case
   this whole specification exists to make resumable, and its lock must
   continue to reserve the repository exactly as if it were still
   running, so an ordinary new task correctly fails closed and directs
   the human to resume, inspect, or abandon it instead. **The lock's
   mechanism is `fcntl.flock`, never implemented via `os.rename` or an
   `unlink`/`O_EXCL`-retry loop over the file's path** — two earlier
   candidate mechanisms were each found, in successive review rounds, to
   be unsafe: `rename` is unconditional replacement, not compare-and-
   swap; `unlink` operates on a path, not the specific file a reclaimer
   actually inspected, so a delayed unlink can remove a different
   racer's already-live replacement. `flock` removes this whole class of
   problem at its root. **It represents two distinct things, correctly
   kept separate**: the checkpoint's own terminal/non-terminal state is
   the durable *reservation* (independent of process liveness, the only
   way to represent a `PAUSED_RETRYABLE` run's reservation correctly
   after its process is gone); the `flock` itself, acquired non-blocking
   and **held for a holder's entire active execution** (not merely a
   brief decision — an earlier revision's "hold it only briefly" design
   left two concurrent `resume` attempts for the same paused run free to
   each pass their own brief check and then execute concurrently, found
   and closed in a later review round), is *execution ownership* — "is
   someone actively running this right now" — which genuinely is
   process-bound, and is exactly what `flock`'s automatic release-on-
   exit is for. Multi-run concurrency is explicitly deferred, not
   solved.
7. **The CLI model is exactly `resume` / `inspect` / `abandon`** — no
   `peos runs` in V1 (moot once at most one run can ever be active or
   paused). `inspect` is strictly read-only. `abandon` **attempts
   orphaned-process reclamation first and only terminalizes once that
   succeeds** (never the reverse — terminalizing before confirming
   nothing is left unaccounted for would let a stale marker/lock be freed
   while an orphaned process is still running); on success it writes a
   new, distinct terminal value (`ABANDONED` — never conflated with
   `APPROVED`, `HUMAN_GATE`, `FAILED`, or `MAX_CYCLES_REACHED`), discards
   its workspace, and releases the shared run lock. It never modifies
   anything under `repo_root` **outside `.peos/`** — a scope that
   necessarily includes releasing `.peos/run.lock` itself, which is PEOS
   orchestration bookkeeping, not authoritative engineering output.
8. **Provider usage/rate-limit transient classification is stable-signal-
   only, lives at the agent-adapter boundary, and is version-aware.** No
   free-text/substring heuristics, ever. Absent a confirmed, documented,
   machine-readable signal for a given installed CLI and version, that
   condition is not automatically classified `PAUSED_RETRYABLE` beyond
   the two generic, CLI-agnostic execution-level cases (subprocess
   genuinely never completed; orchestrator process itself interrupted).
   This record does not claim such a signal currently exists for either
   installed CLI — SPEC-007 states that explicitly rather than guessing.
9. **The checkpoint's trust boundary is non-cryptographic, and is stated
   precisely, not oversold.** V1 adds no signing-key/HMAC mechanism. The
   boundary is: orchestrator-owned persistence; structural candidate-
   workspace exclusion (Claude/Codex cannot write checkpoint state that
   is ever trusted, because the reconciliation path that could copy it
   back is itself excluded); symlink-safe containment; atomic persistence
   — including, per the architecture review's own finding, fsyncing the
   *containing directory*, not merely the renamed file, since file-level
   atomicity alone does not guarantee a directory-entry change survives
   power loss; an explicit serialization allowlist; bounded fields; and
   live cross-validation of every referenced identity at resume
   preflight. This makes the checkpoint agent-unforgeable under the PEOS
   execution boundary and fail-closed under inconsistent state. It does
   **not** protect against an authorized local machine owner who
   intentionally edits PEOS's own internal files with direct filesystem
   access outside any PEOS-invoked process — exactly as nothing else in
   this repository's existing trust model protects against that either.
10. **Exactly one new Human Gate category, scoped narrowly: authoritative
    engineering drift discovered during resume** — covering only a
    changed authoritative `HEAD`/tracked working tree, a changed
    governing specification that still resolves validly, or changed
    required static engineering context that still resolves validly —
    and only when the persisted run otherwise remains internally valid
    and the drift presents multiple legitimate integration choices PEOS
    cannot safely select between on its own. PEOS never auto-merges
    detected drift into a paused candidate workspace. Corrupted
    checkpoint state, containment violations, governance mutation,
    evidence-integrity failure, malformed agent output, sandbox/security
    failures, and ambiguous process ownership are explicitly excluded
    from this gate and remain `FAILED`.
11. **`MAX_CYCLES_REACHED` is a new, distinct terminal `Outcome` value**,
    superseding SPEC-004's encoding of convergence exhaustion as
    `HUMAN_GATE`/`GATE_UNRESOLVED_AFTER_REMEDIATION` — a reporting/state-
    machine correction, not a change to the convergence bound or loop
    structure, both of which are preserved exactly. The final Delivery
    Report for this outcome continues to render the complete Outstanding
    Findings Register.
12. **The final Codex engineering delivery gate is unchanged.** No
    resumed run may reach `APPROVED` without a valid, final Codex
    `APPROVE` verdict produced after resume, covering the final
    implementation and final authoritative evidence. A pause/resume
    boundary never resets, weakens, or erases the Outstanding Findings
    Register.

## Alternatives Considered

- **Promoting the existing Run Ledger directly into the resume-authority
  role**, adding the missing fields to it in place. Rejected: the ledger
  is already documented, reviewed, and relied upon (by its own stated
  contract) as diagnostic-only; quietly changing that contract's trust
  level would be a larger, riskier change than adding one new, clearly-
  scoped sibling artifact with its own, separately-stated trust claim.
- **Reconstructing the workspace from baseline + a diff/patch at resume
  time** (SPEC-007 v0.1's Approach B), instead of preserving it in place.
  Rejected for the reason already recorded in SPEC-007: this repository's
  own `create_isolated_workspace` copies `frontend/node_modules` from
  whatever currently exists in `repo_root`, not from a frozen snapshot: a
  reconstruction would silently pick up a possibly-drifted dependency set
  with no signal that it happened, a real correctness risk the preserved-
  in-place approach does not have.
- **A boolean `active_phase_completed` flag** (SPEC-007 v0.1's original
  design) instead of a three-state `NOT_STARTED`/`ENTERED`/`COMPLETED`
  model. Superseded: a boolean cannot, on its own, distinguish "this
  phase was never reached" from "this phase's own write ordering is what
  proves it wasn't finished" as clearly as a named three-state value does
  for the purpose of this record's Decision 4, and the explicit tri-state
  naming is what the Human Engineering Lead specified.
- **Treating any workspace-identity mismatch uniformly as corruption**,
  regardless of which phase was interrupted. Rejected per Decision 5: a
  mutating phase's own partial output is an expected, legitimate
  consequence of interruption, not evidence of tampering, and conflating
  the two would make ordinary Claude-phase interruptions permanently
  unresumable, defeating much of this specification's purpose.
- **Free-text matching of provider rate-limit/quota messages** in CLI
  output, to widen `PAUSED_RETRYABLE` coverage. Rejected per Decision 8:
  unversioned, un-tested-against-a-specific-CLI-release text matching is
  exactly the kind of brittle heuristic this project's engineering
  discipline (CLAUDE.md: prefer simple, interpretable, and here,
  *reliable* mechanisms) argues against, and the Human Engineering Lead
  explicitly instructed against it.
- **Cryptographically signing the checkpoint** (a signing key or HMAC).
  Considered and declined for V1: no threat this specification actually
  needs to defend against (candidate-workspace forgery; a read-only agent
  sandbox) requires it, given the structural exclusions already in place:
  the real residual risk — a local machine owner with direct filesystem
  access editing PEOS's own files — is not one signing would close either
  (the owner could resign a forged checkpoint with the same key they used
  to generate the real ones, since V1 has no separate, inaccessible key
  store). Revisit only if an independent review demonstrates a specific
  threat this boundary does not already cover.
- **A general multi-run scheduler/queue.** Rejected for V1: the single-
  local-operator assumption (SPEC-003) makes "at most one active/paused
  run, fail closed on conflict" sufficient, and a queue/scheduler is
  explicitly out of scope per CLAUDE.md's "no general-purpose workflow/
  state-machine framework" posture already established for SPEC-004.

## Consequences

- Implementing SPEC-007 requires `peos/workflow.py`'s phase-transition
  call sites to drive two durable writes per phase (an `ENTERED`
  checkpoint write before work begins, a `COMPLETED` write after a valid
  result exists) rather than the single post-hoc `stage(...)` call that
  exists today — a real, non-trivial structural change to that module's
  control flow, not a cosmetic addition.
- `discard_workspace` (`peos/sandbox.py`) gains real callers for the first
  time; every run's workspace lifecycle changes from "accidentally
  persists forever in system temp space" to "deliberately persists only
  while active or paused, then is discarded" — a behavior change from
  today's status quo, made deliberately, not an oversight.
- `reconcile_workspace_to_repo` gains one more structural exclusion
  (`_is_run_state_path`), mirroring two already-reviewed SPEC-006
  precedents (`_is_peos_control_plane_path`, `_is_staged_runtime_
  evidence_path`) — a small, well-precedented extension, not a new kind
  of mechanism.
- `peos/claude_agent.py` and `peos/codex_agent.py` each gain a new,
  narrow, version-tagged `classify_transient_failure` function with its
  own regression-test obligation per CLI version it claims to recognize a
  signal for — ongoing maintenance cost whenever either CLI's observable
  behavior changes, explicitly accepted as the cost of never guessing.
- `peos/cli.py` moves from a flat positional-argument parser to a
  subcommand model (`resume`/`inspect`/`abandon` alongside the existing
  default task-running behavior) — a real CLI-surface change.
- `peos.runtime_services.teardown_service` cannot be reused unmodified for
  orphan reclamation across a process restart (it requires a live `Popen`
  handle no restarted process has) — a new, restart-safe reclamation
  function, built on the same signal-escalation pattern, is required.
- A future need to support more than one active/paused run per
  repository (explicitly deferred here) will require revisiting Decision
  6 and the single `.peos/run.lock` design specifically.

## Open Items Carried Into SPEC-007

- Independent Codex architecture/specification review of SPEC-007 v0.2
  and this record — not yet performed as of this record's acceptance;
  implementation does not begin until it closes with no blocking
  findings, exactly mirroring the ADR-0003/SPEC-006 precedent.
- Whether a future, more specific "provider usage/rate-limit" resumable
  case should be added once a stable, documented, machine-readable signal
  is confirmed for Claude Code and/or Codex (Decision 8's explicit
  non-commitment).
- Whether `gate_id`-style structure is wanted for `MAX_CYCLES_REACHED` for
  Delivery Report formatting symmetry with `HUMAN_GATE` — an
  implementation-detail choice within Decision 11, not a further
  architectural decision.
