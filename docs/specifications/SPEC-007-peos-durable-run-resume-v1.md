# SPEC-007 — PEOS Durable Run Resume V1

**Status:** Draft
**Project:** AI Power Lab
**System:** PEOS Automation V2 (extends `peos/workflow.py`, `peos/ledger.py`,
`peos/sandbox.py`, `peos/round_packet.py`, `peos/findings_register.py`,
`peos/preflight.py`, `peos/cli.py`, `peos/claude_agent.py`,
`peos/codex_agent.py`, `peos/runtime_services.py`,
`peos/runtime_verification.py`, `peos/fsguard.py`,
`peos/reconcile.py`-equivalent reconciliation logic in `peos/sandbox.py`;
adds `peos/checkpoint.py`, `peos/resume.py`)
**Version:** 0.11 (revised against a ninth Codex architecture review of
v0.10, which confirmed the write-ordering fix closed the "observably
empty" failure mode but found a sharper counter-example it did not
close — a partial, equal-length-or-shorter overwrite can produce a
syntactically valid hybrid no JSON-syntax check can detect — closed in
this text with a self-verifying content hash; see "Codex Architecture
Review — Round 9," below)
**Type:** Workflow Infrastructure

---

## Codex Architecture Review — Round 1 (v0.2 → v0.3)

v0.2 was submitted for independent Codex architecture review. Codex
returned `CHANGES_REQUIRED` with **15 findings (5 blocking, 9 major, 1
minor)** — not 16/6 as an earlier revision of this document mistakenly
stated due to a transcription error on this author's part, corrected here
for the record. Every finding was grounded in the actual, real code this
specification extends. v0.3 closed all 15 in place:

1. (Blocking) Completion was not an atomic transaction (register/dispute/
   cycle updates could be written separately from the `COMPLETED` flag).
2. (Major) The checkpoint omitted the original task text and the exact
   governing-spec source/resolution mode.
3. (Blocking) A crash between a `COMPLETED` Codex `APPROVE` and
   terminalization could reach `APPROVED` without a new post-resume Codex
   call.
4. (Blocking) Interrupted reconciliation could leave `repo_root` dirty in
   a way the drift check would misclassify as external drift; the drift
   gate must never call the reconciling `gate()` helper.
5. (Blocking) `discard_workspace()`'s real implementation would delete
   the entire run directory if the workspace were placed directly under
   `.peos/runs/<run_id>/`.
6. (Blocking) Relocating workspace/home under `repo_root` conflicts with
   the existing Seatbelt profiles' rule ordering.
7. (Major) Partial-candidate recovery did not resolve stale prior-round
   evidence or re-check staged governance/static-context copies.
8. (Major) Evidence Validity and resume-preflight evidence checks
   contradicted each other, and the "no evidence before `COMPLETED`"
   claim did not match the real persist-then-return order.
9. (Major) Process/PID ownership had no launch-time registration
   protocol, no port field, no dead-group-leader-with-live-descendants
   handling, and no account of wrapped/sandboxed command argv.
10. (Major) "All five signals must hold" classified an ordinary dead
    process as "ambiguous ownership."
11. (Major) The marker-plus-separate-resume-lock design left gaps between
    ordinary execution, resume, and abandon.
12. (Major) Abandon terminalized before confirming orphan reclamation
    succeeded, and its "touches nothing outside X" claim was internally
    inconsistent.
13. (Major) Preflight could reach the drift gate before establishing the
    gate's own required internal validity.
14. (Major) The ledger-style atomic write does not, by itself, guarantee
    a directory entry survives power loss without also fsyncing the
    containing directory.
15. (Minor) The register snapshot shape was described without naming the
    real, already-existing `peos.round_packet.RegisterEntrySnapshot`, and
    this document's own disposition vocabulary had drifted from this
    repository's actual `peos/findings_register.py` vocabulary.

## Codex Architecture Review — Round 2 (v0.3 → v0.4)

A focused follow-up review, re-checking all 15 Round-1 findings against
v0.3, confirmed **6 closed** (2, 5, 8, 10, 14, 15) and found **9 still
outstanding or only partly closed** (1, 3, 4, 6, 7, 9, 11, 13, plus a
phantom "finding 16" that never existed, traced directly to this
document's own 16/6 miscount above — now corrected), plus **one new
finding**: the Acceptance Criteria section referenced prior-revision
criteria by number without restating their normative text, leaving v0.3
not self-contained. Each is closed in this v0.4 text, in place, in the
section named:

1. **(Still outstanding → closed below, "Durable Phase-State Semantics"
   §PLANNING recovery.)** PLANNING's recovery procedure contradicted the
   general `ENTERED`-before-work rule and gave no durable source for the
   task/spec inputs before a first checkpoint existed. **Fixed**:
   PLANNING now follows the identical `ENTERED`/`COMPLETED` pattern as
   every other phase — the checkpoint's very first write *is* PLANNING's
   own `ENTERED` write, created immediately after `run_id` generation and
   lock acquisition, containing the raw CLI inputs (`task`,
   `governing_spec_source`) before any resolution work begins. There is
   no "no checkpoint exists" case for a run that got far enough to be
   nameable at all.
3. **(Still outstanding → closed below, "Final Delivery Gate.")** The
   binding-based Codex-review-reuse clarification conflicted with ADR-0004
   Decision 12's and the retained acceptance criteria's literal "produced
   after resume" wording, and no per-review binding record actually
   existed to make reuse verifiable. **Fixed by simplification, not
   further elaboration**: the binding-based reuse idea is **retracted**.
   V1 now requires, unconditionally, that **every** resumed run obtain at
   least one fresh Codex review call after resume preflight completes,
   before reaching `APPROVED` — even if an earlier, pre-interruption
   review for the same round already reached `COMPLETED` with `APPROVE`.
   This matches the Human Engineering Lead's literal wording exactly,
   removes the need for any per-review binding record, and accepts one
   occasionally-redundant Codex call as the deliberate cost of this
   guarantee — the same trade already accepted for deterministic
   verification always rerunning.
4. **(Still outstanding → closed below, "Reconciliation Crash-Safety.")**
   A single fingerprint cannot reconstruct a dirty tree or prove a
   "prefix" relationship, and `shutil.copy2` is not atomic per file.
   **Fixed with a real mechanism, not a stronger assertion**:
   reconciliation is restructured around a durable, per-file
   **manifest** of atomic operations, each applied via temp-file-write-
   then-rename (never in-place `copy2`), making resumed reconciliation
   exactly replay-safe without any fingerprint-based guessing.
6. **(Still outstanding → closed below, "Backward Compatibility.")**
   Moving the *entire* existing allow-block after the `repo_root` deny
   would reopen writes anywhere under `repo_root` for a repository that
   happens to be nested inside a path the block's *other* entries
   (`tempfile.gettempdir()`, `/private/tmp`) already allow. **Fixed**:
   only this run's own narrow `candidate/workspace`/`candidate/home`
   paths move after the deny; the broader scratch-space allows keep their
   original position, before it.
7. **(Still outstanding → closed below, "Partial Candidate Workspace
   Recovery.")** Step 2 checked governance/static-context only against
   `repo_root`, never the workspace's own staged copies the real
   `detect_mutations`/`reverify_identity` functions already check for an
   uninterrupted run. **Fixed**: both are now explicitly required.
9. **(Still outstanding → closed below, "Process Ownership and Orphan
   Reclamation.")** A dead group leader with live descendants would
   incorrectly fail signal 1 ("the recorded `pid` exists") even though
   the group itself is demonstrably alive; `reclaim_orphaned_service`
   also omitted `teardown_service`'s port-release verification. **Fixed**:
   a dead leader with a live group is now its own named, explicit
   "ambiguous, fails closed" case rather than an accidental side effect of
   signal ordering, and port-release verification is restored.
11. **(Still outstanding → closed below, "Workspace Lifecycle and
    One-Run-Per-Repository.")** Two real bugs: a TOCTOU window in stale-
    lock reclamation, and — far more serious — **this document's own text
    said the shared lock is released when a run pauses**, which would
    have let a new ordinary task start while a `PAUSED_RETRYABLE` run
    still existed, directly defeating Decision 2. **Fixed**: the lock is
    released *only* on a terminal outcome; a dead process holding a lock
    whose checkpoint is still non-terminal is not stale and is never
    reclaimed by ordinary execution — only resume/abandon may act on it.
    Stale-lock reclamation (dead process *and* terminal checkpoint) now
    uses one atomic `rename`, never a separate remove-then-create.
13. **(Still outstanding → closed below, "Resume Preflight.")** The real
    `static_context.reverify_identity` checks authoritative content
    *before* staged content internally, so calling it wholesale during
    the early integrity phase would itself detect drift before the
    dedicated drift-classification step ever ran. **Fixed**: static-
    context integrity (staged-copy check) and static-context currency
    (authoritative-content check) are now two separate, explicitly
    separately-timed checks; an explicit governance-identity integrity
    row is added to the preflight table.
- **(New finding → closed below, "Acceptance Criteria.")** Prior
  acceptance criteria were referenced by number, not restated. **Fixed**:
  every criterion is now given in full, normative text in this one
  document, with AC-023/AC-024/AC-054 corrected to match the simplified,
  unconditional post-resume-Codex rule above.

## Codex Architecture Review — Round 3 (v0.4 → v0.5)

A third focused review, re-checking the 9 items Round 2 left open against
v0.4, confirmed **6 closed** (3, 6, 7, 9, 13, and the Round-2 "new"
finding) and found **3 still outstanding**, plus **one new finding**.
Each is closed in this v0.5 text, in place:

1. **(Still outstanding → closed below, "Durable Phase-State Semantics"
   §PLANNING recovery.)** Two real sub-gaps: the shared run lock is
   acquired *before* the checkpoint's first write, so an interruption in
   that exact window leaves a lock naming a `run_id` with no checkpoint
   behind it at all, and nothing said how to recognize or reclaim that;
   separately, the full resume-preflight table assumes fields (workspace
   identity, governance/decision identities, evidence) that genuinely do
   not exist yet for a checkpoint still at `PLANNING`/`ENTERED`, and
   nothing said those checks should be skipped rather than attempted
   against absent data. **Fixed**: a lock with no corresponding
   checkpoint is treated identically to a stale, reclaimable lock (there
   is definitionally nothing to resume); and resume preflight gains an
   explicit, early short-circuit for exactly this one case, running only
   checks 1–4 before re-deriving Planning fresh, never attempting checks
   5 onward against fields that do not yet exist.
4. **(Still outstanding → closed below, "Reconciliation Crash-Safety.")**
   Two real sub-gaps: an interruption between writing a reconciliation
   operation's sibling temp file and its `os.rename` leaves that temp
   file sitting in the authoritative tree with no defined name, owner, or
   cleanup — exactly the kind of "unexplained" state the manifest-based
   recovery was supposed to eliminate, not reintroduce; and the claimed
   "small, incremental write" for marking one manifest entry `applied`
   has no actual mechanism distinct from this specification's own
   atomic-whole-file checkpoint-write model, which it quietly
   contradicted. **Fixed**: temp files use a fixed, recognizable naming
   convention PEOS's own recovery logic specifically looks for and safely
   removes, excluded from "unexplained drift" by construction; and the
   "incremental write" framing is retracted — each manifest entry's
   `applied` update is an ordinary, full, atomic checkpoint write like
   every other write in this specification, accepting the cost rather
   than inventing a second, undefined persistence mechanism.
11. **(Still outstanding → closed below, "Workspace Lifecycle and
    One-Run-Per-Repository.")** A sharp, correct catch: `os.rename` is
    unconditional replacement, not compare-and-swap — two racing
    reclaimers can each successfully rename a fresh lock over what they
    each separately observed as stale, with the second rename silently
    clobbering the first racer's now-live lock, and both believing they
    hold it exclusively. **Fixed with a real exclusivity primitive**:
    reclamation is restructured as an unlink-then-`O_EXCL`-create retry
    loop, where `O_EXCL` creation (not `rename`) is the actual point of
    mutual exclusion — exactly the same primitive already used for the
    uncontested case, extended to the reclamation path instead of
    introducing a different, weaker one.
- **(New finding → closed below, "Acceptance Criteria.")** AC-006's "no
  phase re-entered that was already safely completed" directly
  contradicted AC-054/the Final Delivery Gate's unconditional mandatory
  fresh Codex call, which *does* re-enter an already-`COMPLETED` review
  phase on purpose. **Fixed**: AC-006 is reworded to state its guarantee
  precisely — no verification/Claude-phase *work product* is redone for
  an already-`COMPLETED` phase, with the one named, deliberate exception
  this specification's Final Delivery Gate itself requires.

## Codex Architecture Review — Round 4 (v0.5 → v0.6)

A fourth focused review, re-checking the 3 items Round 3 left open
against v0.5 (plus a new finding Round 3 itself raised), confirmed **2
closed** (the manifest-based reconciliation fix, and AC-006's Codex-call
exception) and found **2 still outstanding**, plus **two further
refinements to AC-006's own wording**. Each is closed in this v0.6 text:

1. **(Still outstanding → closed below, "Durable Phase-State Semantics"
   §PLANNING recovery.)** The v0.5 fix for the bootstrap gap ("no
   checkpoint exists for this `run_id` → reclaimable like a stale lock")
   dropped the needed liveness safeguard entirely: a **live** process
   genuinely still in its own bootstrap window could have its slot stolen
   by a concurrent invocation, since nothing checked whether that window
   had actually elapsed. **Fixed**: the lock's own `acquired_at`
   timestamp now gates this specific case with a generous, fixed
   `BOOTSTRAP_GRACE_PERIOD_S` — a deterministic, race-free time
   comparison, never a liveness check (see Finding 11 below for why a
   liveness check is specifically the wrong tool here).
11. **(Still outstanding → closed below, "Workspace Lifecycle and
    One-Run-Per-Repository.")** The sharpest catch of this whole review
    sequence: the v0.5 "unlink-then-`O_EXCL`-create retry loop," intended
    to fix Round 3's broken `rename`-based reclamation, was **itself**
    still unsafe — POSIX `unlink` operates on a *path*, not the specific
    file a reclaimer actually inspected, so a delayed unlink from one
    racer can remove a *different* racer's already-live replacement lock
    rather than the stale one it originally observed, with neither an
    `EEXIST` nor a `FileNotFoundError` ever surfacing to reveal the
    mistake. **Fixed by changing the actual mechanism, not by patching
    the retry logic again**: reclamation now uses `fcntl.flock`, a
    kernel-enforced advisory lock, to make the brief "read current
    reservation, decide, write new one" sequence genuinely atomic across
    every caller — with the lock file itself never deleted or recreated,
    removing the path-vs-identity confusion at its root, and with the
    *logical* reservation (does a `PAUSED_RETRYABLE` run still hold the
    slot) correctly kept separate from and independent of any process's
    own liveness, which an OS-level lock tied to process lifetime could
    never represent for a run whose defining property is that its
    process is gone while its reservation must persist.
- **(Two further wording refinements, both closed below, "Acceptance
  Criteria.")** AC-006's "no work product redone for a `COMPLETED`
  phase" was both too broad (it would have promised deterministic/
  Runtime Verification reuse this specification's own "Evidence
  Validity" section explicitly forbids) and too narrow in its Codex
  exception ("exactly one additional" call overconstrains the ordinary,
  unchanged bounded-convergence loop, which may need further cycles).
  **Fixed**: AC-006 now scopes its "no redo" guarantee to Claude-phase
  work product only, explicitly deferring to verification's and Codex
  review's own, separately-stated rules, and requires "at least one"
  fresh Codex call, never "exactly one."

## Codex Architecture Review — Round 5 (v0.6 → v0.7)

A fifth focused review, scrutinizing specifically the two mechanisms that
had each already failed two prior rounds (the lock itself, and the
bootstrap-reclamation rule layered on top of it), confirmed **Finding 11
(the `flock` mechanism) and the AC-006 wording are genuinely closed** —
the kernel-enforced mutual exclusion holds, and no further replacement
race exists. It found **Finding 1 still outstanding, for a different
reason than before**, plus **one new major finding and two new minor
findings**, all specific to the lock's own write durability. Closed in
this v0.7 text:

1. **(Still outstanding, for a new reason → closed below, "Durable
   Phase-State Semantics" §PLANNING recovery.)** Round 4's fix replaced a
   liveness check with a fixed time bound (`BOOTSTRAP_GRACE_PERIOD_S`),
   reasoning that a deterministic clock comparison was safer than a
   liveness probe. Round 5 correctly identified this as trading one
   unsafe heuristic for another: **any** fixed timeout can be exceeded
   by a genuinely still-alive, merely slow, legitimate bootstrap
   (scheduler contention, slow disk I/O) — at which point a concurrent
   process steals its slot while it is still alive and about to proceed,
   with nothing stopping the original from then *also* continuing,
   leaving two live runs under one nominal reservation. **Fixed by
   returning to a liveness check after all — but the positive, narrow
   kind this specification already uses elsewhere, not a bare "assume
   dead after N seconds" guess**: the bootstrap case is reclaimable if
   and only if `os.kill(recorded_pid, 0)` raises `ProcessLookupError`
   (the recorded bootstrapper is provably no longer running) — never a
   timeout. This is not the same liveness check this specification
   elsewhere correctly avoids for the *general*, checkpoint-bearing case
   (where a dead process's *reservation* must still hold, because the
   checkpoint durably represents it): here, no checkpoint exists at all,
   so there is no durable reservation for a liveness check to wrongly
   override — if the recorded process is dead, the attempt it represents
   is provably gone with it, by construction, and if it is alive, no
   timeout should ever be allowed to override that fact.
- **(New major finding → closed below, "Workspace Lifecycle and
  One-Run-Per-Repository.")** The lock's own reservation write (the
  brief, flock-protected truncate-and-write) was never specified to be
  made durable (`fsync`'d) before the flock is released and execution
  proceeds to create the checkpoint, and malformed/unparseable content
  (e.g. from a crash mid-write) had no defined handling. **Fixed**: the
  write is now explicitly `lseek`-to-zero, `ftruncate`, `write`,
  `fsync`'d — in that order, entirely while the flock is held — before
  the flock is released; and malformed content is explicitly treated as
  an unsafe, fail-closed condition, never interpreted as empty/free.
- **(Two new minor findings → closed below, same section.)** The
  "immediate release on any process death" framing overstated what
  `flock` guarantees if a file descriptor were ever duplicated or shared
  (e.g. across a fork without `O_CLOEXEC`), and "truncate-and-write"
  did not specify the `lseek`-to-zero step a bare `ftruncate` does not
  itself perform. **Fixed**: the lock is explicitly scoped to one,
  process-local file descriptor per entry point, never duplicated or
  held across a subprocess launch, with the exact `lseek`/`ftruncate`/
  `write`/`fsync` sequence specified above.

## Codex Architecture Review — Round 6 (v0.7 → v0.8)

A sixth focused review confirmed the two minor findings from Round 5
(descriptor scoping, `lseek`-before-`ftruncate`) genuinely closed, and
found the bootstrap liveness check and the lock's own write-durability
fix each needed one further refinement, plus two further new findings
on durability and a scoping correction to a test criterion. Closed in
this v0.8 text:

1. **(Still outstanding, a real but accepted limitation, not a new bug →
   closed below, "Durable Phase-State Semantics" §PLANNING recovery.)**
   `os.kill(recorded_pid, 0)` is safe against ever *incorrectly stealing*
   a live slot, but Round 6 correctly pressed on the inverse: if the OS
   later reuses that exact `pid` for a wholly unrelated, long-lived
   process, the check can report "still alive" indefinitely for a
   bootstrap that is actually long dead, blocking every new task with no
   automatic recovery. **Closed by naming this precisely as an accepted,
   one-sided trade (safety over availability), never by trying to
   eliminate it** — attempting to disambiguate via start-time/pgid/argv
   verification (as Decision 7's service reclamation does) is
   unnecessary here specifically because nothing is ever *terminated* on
   the basis of this check, so an incorrect "alive" costs only
   convenience, never correctness — and by giving the one honest,
   human-initiated recovery path this situation actually has: manual
   deletion of `.peos/run.lock`, outside PEOS, once a human has
   independently confirmed the PID is unrelated.
- **(Durability, still outstanding on two sub-points → closed below,
  "Workspace Lifecycle and One-Run-Per-Repository.")** The write
  sequence's own `fsync` only ever covered the file's *content*; `.peos/
  run.lock`'s very first creation (a new directory entry) was never
  required to durably publish via a containing-directory `fsync`,
  mirroring a gap the checkpoint's own requirement already closed
  elsewhere but this file's creation had not inherited explicitly.
  Separately, the exact write sequence called `os.write` once, ignoring
  that POSIX permits it to write fewer bytes than requested — a short
  write followed by a successful `fsync` would durably persist
  *incomplete* content. **Fixed**: `run.lock`'s first-ever creation now
  requires the same containing-directory `fsync` the checkpoint/run-
  directory already require; the write step is now an explicit loop
  that accumulates `os.write`'s own returned byte count until every
  serialized byte is confirmed written, never a single, unchecked call.
- **(Scoping correction → closed below, "Acceptance Criteria.")** AC-065
  claimed that killing a process immediately after its write call
  returns and confirming the content survives a fresh read proves disk
  durability. It does not: a plain process kill leaves the OS page cache
  intact, so a successful re-read says nothing about whether `fsync`
  itself ever ran. **Fixed**: AC-065 is rescoped to what it can actually
  prove — the call-sequence ordering (complete write, then `fsync`, then
  unlock) — verified by instrumentation/mocking, with disk-level
  durability properly left to fault-injection testing instead.

## Codex Architecture Review — Round 7 (v0.8 → v0.9)

A seventh review confirmed all four Round 6 lock-write-mechanics fixes
closed, and then — asked explicitly to assess the *whole* document, not
only the lock mechanism six prior rounds had concentrated on — found
**one further, genuinely architectural gap**, distinct from every prior
lock finding: the "hold the flock only briefly, then release" design
never actually gave *execution* itself any exclusivity. Closed in this
v0.9 text:

- **(New blocking finding → closed below, "Workspace Lifecycle and
  One-Run-Per-Repository.")** The lock procedure's own rule — fail
  closed whenever the content names a `run_id` with a non-terminal
  checkpoint — applies, read literally, to `resume` and `abandon`
  themselves, since they are specifically invoked *against* a non-
  terminal, paused run; the text never defined the exception they
  obviously need, and "allow a matching `run_id` through" would not, on
  its own, have prevented two concurrent `resume` attempts for the same
  paused run (or a `resume` racing an `abandon`) from each passing their
  own brief check in turn and then executing concurrently once each
  released its own brief flock — this is a missing execution-ownership
  contract, not a further locking refinement. **Fixed by separating two
  genuinely different things an earlier revision's design conflated**:
  the checkpoint's own terminal/non-terminal state remains the durable,
  process-independent *reservation* (unchanged); the `flock` itself is
  now acquired non-blocking and **held for a holder's entire active
  execution** — the correct, and only, way to represent process-bound
  *execution ownership* with an OS primitive whose automatic release-on-
  exit is exactly suited to it. `resume`'s and `abandon`'s own matching-
  `run_id`-and-non-terminal-checkpoint checks now run *inside* this
  exclusively-held flock, so no concurrent resumer, abandoner, or
  still-live original process can ever interleave with them.

## Codex Architecture Review — Round 8 (v0.9 → v0.10)

An eighth review confirmed the Round 7 execution-ownership redesign
itself genuinely closes that gap, and then, continuing the whole-
document mandate, found **one further, real, concrete bug** in the
reservation-write mechanics precisely because of how thoroughly the
prior rounds had already hardened everything else, plus one minor
wording gap the redesign itself had introduced. Closed in this v0.10
text:

- **(New blocking finding → closed below, "Workspace Lifecycle and
  One-Run-Per-Repository.")** The write sequence's own order —
  `ftruncate(fd, 0)` *before* writing the new content — makes the file
  briefly, genuinely empty, and "empty content" is exactly what the
  procedure's own rule treats as "slot free." A crash in that exact
  window (e.g. `resume` truncating `run.lock` to update its own `pid`
  before its first `write` call lands) durably leaves `run.lock` empty
  while the real, non-terminal checkpoint for that paused run still
  exists — letting a concurrent ordinary task wrongly treat the slot as
  available. **Fixed by reordering, not by adding a new check**: the
  write is now write-first, truncate-last (write the new content first,
  `fsync`, *then* `ftruncate` to the new exact length, trimming any
  leftover tail from a previous, longer piece of content) — every
  observable intermediate state is therefore either the untouched old
  content, an incomplete prefix of the new content, or the complete new
  content plus old tail garbage, and the latter two are both guaranteed
  to fail strict JSON parsing (requiring the parser to reject *any*
  trailing bytes, not merely gross malformation) — routed to the
  procedure's own pre-existing "malformed → fail closed, never empty"
  rule. `run.lock` is therefore never observably empty except in the one
  case that genuinely means "never claimed."
- **(Minor wording gap → closed below, "Acceptance Criteria.")** AC-036
  still described reclaiming a terminal lock as independent of whether
  that `run_id`'s own process remains alive — true for the *reservation*
  check, but the Round 7 redesign makes a new task's *execution-
  ownership* acquisition (the non-blocking `flock` itself) a second,
  genuinely conjunctive condition: a straggling process that has
  written its own terminal checkpoint but not yet exited still holds the
  flock, and a new task correctly cannot proceed until it does. **Fixed**
  by stating both conditions explicitly, rather than implying the
  checkpoint check alone is sufficient.

## Codex Architecture Review — Round 9 (v0.10 → v0.11)

A ninth review confirmed AC-036's wording fix closed, and found that the
Round 8 write-first-truncate-last fix, while correctly closing the
"observably empty" failure mode, **did not actually close the full
defect it claimed to** — a sharper, concrete counter-example survived.
Closed in this v0.11 text:

- **(New major finding → closed below, "Workspace Lifecycle and
  One-Run-Per-Repository.")** "Reject any trailing bytes after the
  JSON value's closing brace" only catches a write interrupted partway
  through a **longer** overwrite (leaving an incomplete, syntactically
  truncated prefix) or one interrupted *after* a complete write but
  *before* the final truncate (leaving genuine trailing garbage). It
  does **not** catch a write interrupted partway through an **equal-
  length-or-shorter** overwrite: the unwritten tail of the *old*
  content remains in place past wherever the write stopped, and that
  leftover old tail can combine with the already-written new prefix
  into a syntactically complete, strictly-parseable JSON object with
  *no* trailing bytes at all — naming neither the old nor the new
  reservation, and completely invisible to any check based on JSON
  syntax alone (Round 9's concrete example: a write stopped six
  characters into overwriting a 12-character `run_id` field leaves a
  perfectly well-formed object whose `run_id` is a hybrid of six new
  and six old characters, with the old, untouched `pid`/`claimed_at`
  fields following it unchanged). **Fixed with a mechanism that does
  not rely on JSON syntax at all to detect this**: the content written
  is now the JSON payload immediately followed by the SHA-256 hex
  digest of that exact payload; every read requires the JSON portion to
  parse cleanly *and* its hash to match the trailing digest exactly. A
  partial overwrite changes the JSON bytes without correspondingly
  updating the hash bytes to match (the hash, wherever the write hasn't
  yet reached it, still reflects whichever value — old or new — it
  actually corresponds to, not the hybrid now sitting in front of it),
  so the mismatch is caught regardless of whether the JSON portion
  happens to parse on its own. This is now the one thing that actually
  closes "is this content the complete, correct old value, the
  complete, correct new value, or anything else at all" — syntax
  checking alone never could.

## Engineering Question

PEOS already runs a real, bounded, Codex-gated engineering loop (SPEC-001,
SPEC-003, SPEC-004, SPEC-006): approved specification → isolated Claude
implementation → deterministic verification → real Runtime Verification
where applicable → Codex independent review → bounded Claude remediation →
full re-verification → Codex closure review → `CODEX_APPROVED`. Today, if
the orchestrator process or an agent invocation is interrupted *for any
reason* partway through that loop, the run simply stops, with nothing
durable to distinguish "safely continuable" from "a real failure," and
nothing to continue it.

**Can PEOS durably and safely resume a previously interrupted run —
without restarting completed engineering work, without weakening any
existing trust/verification/delivery gate, and without turning a genuine
engineering failure into an ordinary retry — and if so, how?**

This is not a request for generic retry logic.

## Motivation

SPEC-004 named this exact problem and deliberately deferred it
("Resolved Decision 4 — no Tier-2 resume in V2"), naming the unresolved
hazards precisely: workspace survival is not guaranteed, the governing
specification may have changed, and a terminalized Codex review cannot
be safely "re-entered" without re-establishing every invariant SPEC-001/
SPEC-003 already check fresh. Real operation has since produced exactly
the interruptions that deferral anticipated.

## Scope

- A new, trusted, orchestrator-owned checkpoint artifact (`RunCheckpoint`),
  persisted durably and atomically — including directory-entry
  durability — sufficient to resume a safely resumable run without
  promoting the diagnostic Run Ledger into an execution-authority
  artifact.
- A durable three-state (`NOT_STARTED`/`ENTERED`/`COMPLETED`) phase model,
  applied uniformly to every phase including Planning, where `COMPLETED`
  is a single atomic transaction covering a phase's result and every
  durable consequence of it.
- A new non-terminal `PAUSED_RETRYABLE` outcome and new terminal
  `MAX_CYCLES_REACHED`/`ABANDONED` outcomes.
- A resume preflight strictly ordered so staged/integrity checks run
  before any drift classification, plus defined recovery procedures for
  a partially-mutated candidate workspace and for interrupted
  reconciliation.
- A single shared repository-level lock, released only on a terminal
  outcome, enforcing at most one active-or-paused run per repository
  across every entry point.
- A workspace-durability strategy with a directory layout
  `discard_workspace`'s real, unmodified behavior can safely use.
- A manifest-driven, atomically-applied reconciliation mechanism, safely
  resumable from any interruption point.
- A minimal CLI surface: `./bin/peos resume <run_id>`, `./bin/peos inspect
  <run_id>`, `./bin/peos abandon <run_id>`.

## Out of Scope / Non-Goals

Unchanged from the prior revision: generic retry of any failure; a
daemon/scheduler/background service/quota-polling system; a web
dashboard or new database; `./bin/peos runs`; multi-run concurrency;
cross-run finding tracking/resume; free-text/substring matching of
provider usage-limit messages; deterministic-verification evidence
persistence/reuse; cryptographic checkpoint signing; auto-merging
authoritative drift; perfect closure of the Popen-to-registration race
(an accepted, named residual limitation); any weakening of the Seatbelt
sandbox, the agent authentication boundary, or the `peos/`/`.peos/` trust
boundary.

**Also now explicitly out of scope**: reusing a pre-interruption Codex
review to satisfy the final delivery gate without a fresh post-resume
call (retracted per Round 2 Finding 3 — see "Final Delivery Gate").

## Current State Discovered in the Repository

Unchanged from the prior revision — every claim was verified directly
against the current repository.

### What is durable today

- **The Run Ledger** (`peos/ledger.py`): diagnostic-only, atomic,
  symlink-safe, explicitly not a resume checkpoint.
- **The isolated workspace's filesystem contents**, accidentally
  (`create_isolated_workspace` clones into system temp space;
  `discard_workspace` has zero callers in `peos/workflow.py`).
- **Runtime Verification evidence** (SPEC-006): hashed, persisted,
  identity-reverified — the strongest existing precedent for
  evidence-identity binding.
- **Static context artifact identity** (`peos/static_context.py`):
  content-hash-based; **its real `reverify_identity` function checks
  authoritative content before staged content, internally, in that
  order** (confirmed by Round 2 review — directly relevant to "Resume
  Preflight"'s check ordering below).
- **The workspace-snapshot-identity primitive**:
  `peos.gitutil.repo_state_fingerprint` — does not cover gitignored
  content (`frontend/node_modules`).
- **`peos.runtime_services.teardown_service`**: requires a live `Popen`
  handle, confirming it cannot be reused unmodified across a process
  restart; its final success criterion includes verifying the service's
  port was actually released (`is_port_released`), a detail this
  specification's own orphan-reclamation function must also preserve.
- **`peos/round_packet.py`'s `RegisterEntrySnapshot`**: already a
  complete, lossless mirror of `RegisterEntry`, with a `from_entry`
  classmethod — reused directly, not reinvented.
- **The real reconciliation logic** (`peos/sandbox.py`'s
  `reconcile_workspace_to_repo`): currently copies changed files via
  `shutil.copy2` (not atomic per file) and conditionally deletes removed
  ones — confirmed non-atomic at the single-file level, directly relevant
  to "Reconciliation Crash-Safety" below.

### What exists only in memory today

Unchanged: the Outstanding Findings Register (no serialization); the
Round Packet (never persisted); deterministic verification results (no
content hash, never persisted); Codex review results (never hashed or
persisted as their own artifact).

### How the current implementation behaves under each kind of interruption

Unchanged: ordinary exceptions already fail gracefully (out of scope to
change); `KeyboardInterrupt`/`SystemExit` propagate uncaught;
`last_completed_phase`/`remediation_cycles_run` both have a premature-
advance conflation; `claude_agent.py`/`codex_agent.py` have no
execution-vs-content failure classification; the CLI has no subcommands;
`MAX_CYCLES_REACHED` is not a distinct outcome today; **`gate()`
(`peos/workflow.py:593-603`) always calls `_reconcile()` unconditionally**
— directly relevant to why the new drift gate must not reuse it.

## Resolved Engineering Lead Decisions (Round 2)

Unchanged — the Human Engineering Lead's 13 settled decisions (CLI scope;
one run per repository; stable-signal-only provider classification;
untrusted partial candidate state; three-state phase model; no
dependency on signal handlers; verified process ownership; non-
cryptographic checkpoint trust; one unified drift Human Gate;
`MAX_CYCLES_REACHED` as a distinct outcome; bounded workspace lifecycle;
binding-based evidence validity; unchanged final delivery gate). This
revision continues to close gaps in how the text *implements* them,
never revisiting the decisions themselves.

## Terminal and Non-Terminal State Taxonomy

```
Outcome = Literal[
    "APPROVED", "HUMAN_GATE", "FAILED",
    "MAX_CYCLES_REACHED",   # NEW — terminal, convergence exhausted
    "PAUSED_RETRYABLE",     # NEW — non-terminal, a resumable interruption
    "ABANDONED",            # NEW — terminal, human chose not to continue
]
```

Unchanged categorization: `APPROVED` (terminal success); `HUMAN_GATE`/
`FAILED`/`MAX_CYCLES_REACHED` (terminal engineering states); `ABANDONED`
(terminal, human-initiated, conflated with none of the others);
`PAUSED_RETRYABLE` (non-terminal). Only `resume`/`abandon` ever move a
`PAUSED_RETRYABLE` run forward.

## Resumable vs. Non-Resumable Interruption Classification

Unchanged. Resumable: orchestrator interruption (with or without a
signal handler); an agent subprocess that itself never completed
execution; a positively-identified provider usage-limit signal (none
currently confirmed for either installed CLI). Non-resumable: real
verification/runtime-integrity/sandbox/security failures; malformed
agent output; governance mutation; evidence-integrity failure;
authoritative drift (classified separately — see below); authentication
failure; ambiguous process ownership.

## Provider Usage/Rate-Limit Classification (Decision 3)

Unchanged. `classify_transient_failure` at the agent-adapter boundary;
stable-signal-only, version-aware, regression-tested; defaults to
`"not_transient"`; V1 ships only the CLI-agnostic
`"execution_not_completed"` branch for both adapters.

## Durable Phase-State Semantics (Decision 5, PLANNING fixed per Round 2 Finding 1)

```
PhaseState = Literal["NOT_STARTED", "ENTERED", "COMPLETED"]
```

`NOT_STARTED` is implicit. `ENTERED` is written atomically before a
phase's work begins. `COMPLETED` is written atomically as a **single
transaction** including every durable consequence of the phase's
result — never a status flag written separately from what it depends on:

| Phase | What the single `COMPLETED` write must atomically include |
|---|---|
| `PLANNING` | every identity `RunCheckpoint` records about the run's starting point (baseline, spec identity, decision/governance/static-context identities, AC set, effective max cycles) |
| `CLAUDE_IMPLEMENTATION`/`CLAUDE_REMEDIATION` | the validated result, and the new `current_workspace_snapshot_identity` |
| `LOCAL_VERIFICATION` | the verification outcome summary |
| `RUNTIME_VERIFICATION` | the persisted evidence's reference, written only once both `persist_evidence` and `stage_evidence_into_workspace` have succeeded |
| `CODEX_INDEPENDENT_REVIEW`/`CODEX_CLOSURE_REVIEW` | the validated payload's hash, its verdict, the Outstanding Findings Register/dispute-log state exactly as that payload updates them, and (closure review only) the updated `current_cycle` — all together, one write |
| `TERMINAL_DECISION` | the terminal outcome, gate ID, gate reason |
| `RECONCILIATION` | see "Reconciliation Crash-Safety" |
| `REPORT` | nothing further |

### PLANNING: the checkpoint's own first write (fixed per Round 2 Finding 1, hardened per Round 3 Finding 1)

PLANNING is **not** an exception to the `ENTERED`-before-work rule, and
there is no "resume with no checkpoint" case. Immediately after `run_id`
is generated and the shared run lock (see "Workspace Lifecycle") is
acquired — before any spec resolution, identity hashing, or other
Planning work begins — PEOS writes the checkpoint's **first** record:
`active_phase=PLANNING, active_phase_state=ENTERED`, carrying only the
raw inputs already known at that instant: `run_id`, `task` (the literal
CLI argument), and `governing_spec_source`/`governing_spec_original_path`
(whatever `--spec` was or wasn't passed). PEOS prints this `run_id`
immediately once this write succeeds, exactly as it already prints other
early diagnostic information, so a human who later needs to resume an
interruption *during* Planning itself has a `run_id` to give `peos
resume` in the first place.

**The bootstrap gap, closed precisely (Round 3 Finding 1, revised per
Round 4 Finding 1, finalized per Round 5 Finding 1):** the lock is
acquired *before* this first checkpoint write exists — an interruption
in that exact, narrow window leaves `.peos/run.lock` naming a `run_id`
with no checkpoint behind it at all. Two successive fixes for this case
were each found unsafe: treating "no checkpoint" as unconditionally
reclaimable let a live, still-bootstrapping process have its slot stolen
(Round 4); replacing that with a fixed time bound
(`now >= acquired_at + BOOTSTRAP_GRACE_PERIOD_S`) traded one unsafe
heuristic for another, since *any* fixed timeout can be exceeded by a
genuinely live, merely slow bootstrap — and critically, nothing stopped
the original process from continuing *after* its slot was stolen,
leaving two live runs under one nominal reservation (Round 5). **Fixed
by checking the one fact that is actually decisive — whether the
recorded process is still running — rather than guessing from elapsed
time**: a lock naming a `run_id` with no checkpoint is reclaimable **if
and only if `os.kill(recorded_pid, 0)` raises `ProcessLookupError`** —
the bootstrapper is provably gone. If it raises no error (the process is
still alive, under any OS-reported reason), the second invocation fails
closed ("another task appears to be starting; please wait"), never
guesses, and never times out waiting for it. This is deliberately
**not** the same kind of check this specification elsewhere avoids for
the general, checkpoint-bearing case (see "Workspace Lifecycle"): there,
a dead process's *durable reservation* must still block a new task,
because the checkpoint itself represents that reservation independently
of the process. Here, by contrast, no checkpoint exists at all yet, so
there is no durable reservation for a liveness check to wrongly
override — if the recorded process is dead, the attempt it represents is
gone with it, by construction; if it is alive, nothing should ever be
allowed to override that, regardless of how long it has been running.

A `peos resume <run_id>` given a `run_id` whose lock (if still present)
or prior lock content named it, but for which no checkpoint ever existed,
fails with a clear, explicit "nothing to resume — this run never
completed its bootstrap" message (`FAILED`), directing the human to
simply start a new task.

**Named, accepted limitation (Round 6): PID reuse can make this check
conservative to the point of blocking indefinitely, never incorrect.**
If the recorded bootstrap `pid` is later reused by the OS for a wholly
unrelated, long-lived process, `os.kill(recorded_pid, 0)` will keep
succeeding (no error) for as long as *that* unrelated process lives —
making a genuinely dead bootstrap attempt appear "still alive" to this
check indefinitely, and blocking every new ordinary task in the
meantime. This is a deliberate, accepted one-sided trade: the check can
only ever fail *safe* (wrongly refuse to proceed) in this scenario,
never fail *unsafe* (wrongly steal a slot from something actually
running) — no process is ever terminated on the basis of this check, so
a false "still alive" costs availability, never correctness. **PEOS
itself never resolves this automatically** (it cannot safely determine
"the PID I see is unrelated" — that is exactly the ambiguous-identity
problem Decision 7's service-reclamation rules already refuse to guess
at, for the same reason). A human who has independently confirmed, by
their own inspection, that the recorded PID now belongs to something
unrelated may manually delete `.peos/run.lock` outside PEOS to clear the
stuck reservation — a deliberate, human-initiated escape hatch, never an
automatic one.

**The checkpoint-shape gap, closed (Round 3 Finding 1):** resume
preflight's checks 5 onward (see "Resume Preflight") assume fields —
workspace identity, governance/decision identities, evidence — that
genuinely do not exist yet for a checkpoint still at `PLANNING`/
`ENTERED`. Resume preflight therefore gains an explicit, early branch:
**if `active_phase=PLANNING` and `active_phase_state=ENTERED`, only
checks 1–4 (lock, checkpoint readability, non-terminal, repository
safety) run; checks 5 onward are skipped entirely**, and PEOS proceeds
directly to re-running Planning's resolution logic fresh (read-only
against `repo_root`, therefore safely idempotent) using the recorded raw
inputs — never attempting a check against a field that does not yet
exist, never re-prompting for the task/spec inputs, never risking
resolving a *different* spec on retry than the original invocation was
given.

### Remediation-cycle allocation, specified exactly

Unchanged: a cycle `N` is **allocated** at its first `CLAUDE_REMEDIATION`
`ENTERED` write; it becomes **countable** only at that same cycle's
`CODEX_CLOSURE_REVIEW` `COMPLETED` write (which, per the table above,
atomically includes the `current_cycle` advancement). Any number of
restarts mid-cycle resume under the same logical cycle identity.

## Partial Candidate Workspace Recovery (Decision 4, revised per Round 2 Finding 7)

1. Checkpoint shows the mutating phase's state is `ENTERED`, not
   `COMPLETED`.
2. PEOS revalidates every trust/governance/static-context/security
   invariant **against both the authoritative `repo_root` and the
   workspace's own staged copies** — the staged-copy check uses the
   same real functions an uninterrupted run already applies after every
   agent phase: `peos.preflight.detect_mutations(baseline_hashes,
   workspace_root)` for governance artifacts, and the staged-copy half of
   `peos.static_context.reverify_identity` for static context (Round 2
   Finding 7: v0.3 checked only `repo_root`, missing the case where a
   partial Claude attempt mutated the workspace's *own* staged
   CLAUDE.md/AGENTS.md/ENGINEERING.md/static-context copies specifically,
   which `detect_mutations` is exactly built to catch). A staged-copy
   mutation found here is governance mutation/evidence-integrity failure
   exactly as it already is for an uninterrupted run: `FAILED`, never
   silently proceeding.
3. PEOS verifies workspace containment and run ownership.
4. The workspace's current, partial content is labeled
   `UNTRUSTED_PARTIAL_CANDIDATE_STATE`.
5. PEOS computes a fresh `resume_candidate_workspace_identity`.
6. Any prior-round Runtime Verification evidence currently staged in this
   workspace is explicitly invalidated for authority purposes before
   reinvocation (retained in history, never presented as current).
7. The same logical Claude phase is invoked again, with explicit
   interrupted-phase context.
8. No additional remediation cycle is consumed.
9. No deterministic/runtime/Codex evidence from the incomplete phase may
   ever be reused.
10. Once the retry reaches `COMPLETED`, `current_workspace_snapshot_
    identity` updates, and full required verification runs before any
    Codex call sees this round's work.

For contractually non-mutating phases, this procedure does not apply.

## Hard-Crash and Machine-Restart Semantics (Decision 6)

Unchanged. Correctness never depends on a signal handler; the durable,
directory-fsync'd `ENTERED` write (see "Checkpoint Trust Boundary") is
what makes recovery correct after any kind of interruption, including a
hard kill or a full machine restart. A signal handler remains an optional
refinement recording a more specific `pause_reason`.

## Process Ownership and Orphan Reclamation (Decision 7, revised per Round 2 Findings 9/10)

### `ServiceProcessIdentity`

```
ServiceProcessIdentity:
  service_name: str          # "backend" | "frontend" | "browser_worker"
  pid: int
  pgid: int
  port: int | None            # required for backend/frontend; None for
                               # browser_worker, which binds no service port
  start_time: str | None
  command_argv: tuple[str, ...]   # the exact argv passed to Popen,
                                   # including any sandbox-exec/wrapper prefix
  owning_run_id: str
  recorded_at: str
```

Registration is written immediately after `start_service`/the browser-
worker launch returns a handle, as its own small, immediate checkpoint
write. A kill in the exact window between `Popen` returning and that
write completing leaves that one process unreclaimable — an accepted,
named residual limitation (see "Known Limitations"), not solved in V1.

### `reclaim_orphaned_service` — new, not a reuse of `teardown_service`

`teardown_service` requires a live `Popen` object; a restarted
orchestrator has none for a service an earlier process instance launched.
This specification's own function uses the identical graceful-SIGTERM →
bounded-grace → SIGKILL → verified-dead sequence, built on `os.kill`/
`os.killpg` plus a polling existence-probe loop in place of `Popen.
wait()`, and — closing the second half of Round 2 Finding 9 — **also
verifies port release** via the existing `is_port_released(identity.
port)` before reporting success, exactly mirroring `teardown_service`'s
own final check, for every service whose `port` is not `None`.

### Verification procedure, precisely ordered (Round 2 Finding 9: dead-leader-live-descendants)

1. **Group liveness probe**: `os.killpg(pgid, 0)`.
   - If it raises `ProcessLookupError`: **nothing to reclaim.** The
     ordinary post-reboot/post-crash case — resume logs it and proceeds.
   - If the group is alive, proceed to step 2.
2. **Leader-identity verification**, now checked as its own explicit,
   separate condition (Round 2 Finding 9's precise fix — v0.3's wording
   let a parenthetical imply group-liveness alone was sufficient, which
   is false: a dead group leader with live descendants passes step 1 but
   has no `pid` left to check in step 2):
   - a process with the recorded `pid` **specifically** currently exists;
   - its own start time matches the recorded `start_time` (unavailable
     signal → reclamation does not proceed for that process);
   - its pgid matches;
   - its running command/argv matches `command_argv` exactly, including
     any sandbox-exec/wrapper prefix;
   - `owning_run_id` matches.

   **If the group is alive (step 1) but the specific recorded leader
   `pid` is gone or any signal above is stale/mismatched, ownership
   cannot be positively established for this group — PEOS fails closed**
   (`FAILED`, "ambiguous process ownership"), explicitly including the
   dead-leader-live-descendants case: this specification does not solve
   verifying a surviving non-leader descendant's lineage without the
   leader's own identity to compare against; it fails closed rather than
   guessing, exactly like every other ambiguous-ownership case. A human
   can resolve it manually outside PEOS.

Only when every signal in step 2 holds does `reclaim_orphaned_service`
run.

## Checkpoint Trust Boundary (Precise Claim) (Decision 8)

Unchanged. No cryptographic claim. Orchestrator-owned persistence;
structural candidate-workspace exclusion; symlink-safe containment;
atomic persistence (temp file + `fsync` + `os.rename`, **plus an fsync of
the containing directory** so the directory-entry change itself survives
power loss — an explicit, required extension to `peos/fsguard.py`'s
existing primitive, applied identically to the Run Ledger's own writer);
an explicit serialization allowlist; bounded fields; live cross-
validation of every referenced identity at resume preflight. Agent-
unforgeable under the PEOS execution boundary, fail-closed under
inconsistent state; **not** a defense against an authorized local machine
owner with direct filesystem access.

## Authoritative Engineering Drift (Decision 9)

**One new, unified Human Gate category**: `GATE_AUTHORITATIVE_DRIFT_ON_
RESUME` (ID `"13"`). Applies **only after every integrity/staged-copy
check in the reordered resume preflight has already passed** (see
"Resume Preflight") and at least one of `HEAD`, the governing spec's
content, or required static engineering context has drifted in a way
presenting multiple legitimate choices PEOS cannot select between. PEOS
never auto-merges drift into the candidate workspace, and the drift-gate
code path is its own, distinct terminal-result constructor in `peos/
resume.py` — it never calls `reconcile_workspace_to_repo` or the
existing, always-reconciling `gate()` helper.

### Explicitly NOT covered by this Human Gate

Corrupted/inconsistent checkpoint state; containment violations;
governance mutation (whether in `repo_root` or in the workspace's own
staged copies); evidence-integrity failure; malformed agent output;
sandbox/security failures; ambiguous process ownership; any other
condition where the state is simply unsafe. All stay `FAILED`.

## Reconciliation Crash-Safety (revised per Round 2 Finding 4 — manifest-based, not fingerprint-based)

A single before/after fingerprint comparison cannot reconstruct a dirty
tree or prove a "this is a safe prefix of the candidate diff" relationship
(Round 2's correct objection), and the real `reconcile_workspace_to_repo`
currently applies file changes via `shutil.copy2`, which is not atomic
per file. **This specification therefore requires `reconcile_workspace_
to_repo` to be restructured around a durable, per-file manifest of
atomically-applied operations**, not merely instrumented with a
fingerprint check:

```
ReconciliationOperation:
  relative_path: str
  action: Literal["write", "delete"]
  target_content_hash: str | None     # the candidate's value to apply; None for delete
  original_content_hash: str | None   # the authoritative value before reconciliation
                                       # started; None if the path did not exist
  applied: bool                       # updated as each operation completes
```

Procedure:

1. **Before** any file is touched, PEOS computes the full list of
   `ReconciliationOperation`s from the candidate workspace's diff against
   `repo_root`, and writes that list as part of `RECONCILIATION`'s own
   `ENTERED` checkpoint transaction (`reconciliation_manifest`, a new
   checkpoint field).
2. Each `"write"` operation is applied via the same atomic pattern used
   everywhere else in this specification: write the candidate's content
   to a sibling temp file in the *target's own directory*, using a
   **fixed, recognizable naming convention**,
   `.peos-reconcile-<run_id>-<sha256(relative_path)>.tmp`, then `os.
   rename` it over the destination (never `shutil.copy2`'s in-place,
   non-atomic write); a `"delete"` operation is an ordinary `os.unlink`
   (already atomic for a single file). After each operation succeeds,
   PEOS updates that one manifest entry's `applied=True` — this is an
   **ordinary, full, atomic checkpoint write**, the same temp-file-then-
   `os.rename`-the-whole-`checkpoint.json` mechanism used for every other
   checkpoint update in this specification (Round 3 Finding 4 corrected
   an earlier draft's claim of a cheaper "small, incremental write,"
   which was never actually defined as a distinct mechanism and would
   have contradicted this specification's own single, atomic-whole-file
   checkpoint-persistence model; the cost of one full checkpoint write
   per manifest entry is accepted, not optimized away).
3. **The sibling-temp-file gap, closed (Round 3 Finding 4):** an
   interruption between step 2's temp-file write and its `os.rename`
   leaves that temp file sitting in the authoritative tree under its
   fixed naming convention. This is not "unexplained drift" — it is
   PEOS's own, specifically-named reconciliation debris. Resume's
   authoritative-drift classification (see "Resume Preflight" check 15)
   explicitly recognizes any file matching `.peos-reconcile-<run_id>-*.
   tmp` as exactly this case and removes it as part of recovery, before
   any drift comparison runs — it never counts toward "unexplained"
   dirtiness and never triggers `FAILED` or the drift gate on its own.
4. **Otherwise if interrupted**, the manifest's intent is already fully
   known from the durable `ENTERED` record — no re-diffing, no
   fingerprint-based guessing. For each entry: if the current
   authoritative file's content already matches `target_content_hash`
   (or is already absent, for a delete), it is correctly applied —
   confirmed, `applied` set `True` if it was not already, and skipped. If
   it matches `original_content_hash` (untouched) or is already
   correctly absent for a not-yet-applied delete, it is safely re-applied
   (idempotent). **If it matches neither** — some third, unexplained
   state, and the path does not match the recognized temp-file pattern
   from step 3 — that specific file has had interference the manifest
   cannot account for, and resume fails closed (`FAILED`, naming that
   exact path), rather than guessing.
5. Once every manifest entry is confirmed `applied` (and any leftover
   recognized temp files for this run have been removed), `RECONCILIATION`
   reaches `COMPLETED`.

This closes Round 2 Finding 4 (and Round 3's two follow-on gaps) with a
real mechanism: reconciliation is now a set of durably-recorded,
atomically-applied, idempotent operations, with its own debris
explicitly named and accounted for, safely resumable from any
interruption point, with no need to distinguish "PEOS's own partial
copy" from "external drift" via fuzzy reasoning.

## RunCheckpoint

### Schema (revised per Round 2 Findings 1/4)

```
RunCheckpoint:
  schema_version: str
  run_id: str
  resume_generation: int

  created_at: str
  updated_at: str

  task: str
  authoritative_baseline: str
  governing_spec_relative_path: str
  governing_spec_content_hash: str
  governing_spec_source: Literal["auto_detected", "explicit_path"]
  governing_spec_original_path: str
  effective_max_cycles: int

  active_phase: str
  active_phase_state: Literal["NOT_STARTED", "ENTERED", "COMPLETED"]
  last_safely_completed_phase: str
  current_cycle: int

  workspace_root_relative_path: str    # ".peos/runs/<run_id>/candidate/workspace/"
  workspace_home_dir_relative_path: str  # ".peos/runs/<run_id>/candidate/home/"
  workspace_baseline_commit: str
  current_workspace_snapshot_identity: str
  resume_candidate_workspace_identity: str | None

  # NEW (Round 2 Finding 4): replaces the single fingerprint field.
  reconciliation_manifest: tuple[ReconciliationOperation, ...]

  service_process_identities: tuple[ServiceProcessIdentity, ...]

  decision_identities: tuple[tuple[str, str], ...]
  governance_identities: tuple[tuple[str, str], ...]
  static_context_artifacts: tuple[StaticContextArtifactSnapshot, ...]
  acceptance_criteria_ids: tuple[str, ...]

  findings_register_entries: tuple[RegisterEntrySnapshot, ...]
  active_disputes: tuple[ActiveDisputeSnapshot, ...]
  dispute_log: tuple[str, ...]

  runtime_evidence_history: tuple[RuntimeEvidenceRefSnapshot, ...]

  codex_review_payload_hashes: tuple[str, ...]
  codex_review_verdict_history: tuple[str, ...]

  pause_reason: str | None

  terminal_outcome: str | None
  terminal_gate_id: str | None
  terminal_gate_reason: str | None
```

`RegisterEntrySnapshot` is `peos.round_packet.RegisterEntrySnapshot`,
reused by name. `disposition` values are the real
`RESOLVED`/`ACCEPTED_RECLASSIFICATION`/`HUMAN_DECISION_REQUIRED`
vocabulary from `peos/findings_register.py`.

## Workspace Lifecycle and One-Run-Per-Repository (Decisions 2 and 11, revised per Round 2 Finding 11)

### Directory layout

```
.peos/runs/<run_id>/
  ledger.json
  checkpoint.json
  runtime-evidence/<cycle>/...
  candidate/
    workspace/
    home/
```

`discard_workspace`'s real, unmodified `shutil.rmtree(workspace.path.
parent, ...)` removes exactly `candidate/`.

### A single, shared repository-level lock (redesigned per Round 4 Finding 11; separated into two distinct concerns per Round 7)

Two prior designs for `.peos/run.lock` were proposed and each had a real
race: a plain `os.rename` replacement is unconditional, not compare-and-
swap, so two reclaimers could each clobber the other's fresh lock; an
`O_EXCL`-create/`unlink`-retry loop is still unsafe because POSIX
`unlink` is **path**-based, not **identity**-based. **This specification
uses `fcntl.flock`** (an advisory, kernel-enforced lock, automatically
released by the OS the instant its holding process exits for *any*
reason, including `SIGKILL`), but Round 7 found that an earlier revision
conflated two genuinely different things this one lock must represent,
and specified only one of them precisely:

- **The logical reservation** — "does this `run_id` still hold the
  repository's one active-or-paused slot" — correctly represented by the
  checkpoint's own durable `terminal_outcome`, never by process liveness,
  because the defining property of a `PAUSED_RETRYABLE` run is that its
  *process is gone* while its *reservation must still hold*.
- **Current execution ownership** — "is some process *actively running*
  PEOS for this run_id, right now" — a genuinely different question an
  earlier revision's "hold the flock only briefly, then release it" design
  never actually answered: nothing prevented two concurrent `resume`
  attempts for the same paused `run_id` (or a `resume` racing an
  `abandon`, or racing a still-live original process) from each passing
  their own brief reservation check in turn and then **executing
  concurrently** once each had released its own brief flock — the
  reservation check alone was never meant to, and cannot, provide mutual
  exclusion over execution itself.

**This specification therefore holds the flock for the entire duration
of active execution, not only briefly** — this is the correct, and
only, way to represent "is someone currently executing this" with an
OS-enforced primitive, since execution ownership genuinely *is*
process-bound (unlike the reservation, which must outlive the process).

**Procedure, identical at every entry point** (ordinary task start,
`resume`, `abandon`):

1. Open `.peos/run.lock` (`O_CREAT`, never deleted/renamed by any entry
   point). On this file's very first-ever creation, the containing
   `.peos` directory's own fd is additionally `fsync`'d (as established
   in Round 6); every subsequent open needs no further directory-fsync.
2. `fcntl.flock(fd, LOCK_EX | LOCK_NB)` — **non-blocking**. Blocking here
   would be wrong: if another process is already executing (potentially
   for a long time — an entire PEOS run), waiting for it is not the
   right behavior for a human-facing CLI command.
   - **On `EWOULDBLOCK`/`BlockingIOError`**: another process is actively
     executing *something* right now. Read the content (best-effort, for
     a diagnostic message only — it may change concurrently) and fail
     closed immediately: *"another PEOS execution appears to be in
     progress; wait for it to finish or pause, or investigate manually."*
   - **On success**: this process now exclusively holds execution
     ownership. **This flock is held for this process's entire
     subsequent execution** — through Planning, every remediation cycle,
     reconciliation, and the final report for an ordinary run or
     `resume`; through reclamation and terminalization for `abandon` —
     released only at this process's own natural exit (a terminal
     outcome, a pause, or `abandon`'s own completion), or automatically
     by the OS if the process dies for any other reason. It is never
     released early and never re-acquired mid-run.
3. Still holding the flock, read the current content (or empty).
   **Non-empty content that fails the self-verifying format's own
   checks** (see step 4 — it must split cleanly into a strictly-parsed
   JSON payload plus a trailing SHA-256 hex digest that exactly matches
   that payload's hash) fails closed with an explicit corruption error
   — never interpreted as empty/free, and never accepted merely because
   the JSON portion alone happens to parse. Otherwise, branch by entry
   point:
   - **Ordinary new task**: the slot must be free — content is empty, or
     names a `run_id` whose checkpoint is terminal, or names a `run_id`
     with no checkpoint at all and a provably dead recorded `pid`
     (`os.kill(recorded_pid, 0)` raising `ProcessLookupError` — see
     "Durable Phase-State Semantics" §PLANNING recovery). If so, this
     process writes its own fresh `{run_id, pid, claimed_at}` (the
     durable write-loop-then-`fsync` sequence below) and proceeds,
     **continuing to hold the flock for its entire run**. Otherwise:
     release the flock and fail closed, directing the human to resume,
     inspect, or abandon the existing reservation.
   - **`resume <run_id>`**: the content must name **exactly** this
     `run_id`, with a non-terminal checkpoint (any mismatch — wrong
     `run_id`, empty content, or an already-terminal checkpoint — is a
     distinct, specific error: "nothing to resume," "no such run," or
     "this run already concluded," never a generic failure). If it
     matches, this process updates the content's `pid`/`claimed_at` to
     its own values — **taking over execution ownership of the same
     `run_id`** — and proceeds, continuing to hold the flock for the
     entire resumed execution. Because step 2's `flock` already
     succeeded (non-blocking, exclusively), no other process can be
     concurrently resuming or executing this — or any other — `run_id`
     at the same time; this closes the exact gap Round 7 identified,
     where "matching `run_id`" alone was insufficient without execution-
     level exclusivity behind it.
   - **`abandon <run_id>`**: identical matching requirement. If it
     matches, this process (still holding the flock throughout, so
     nothing else can interleave) attempts orphaned-process reclamation;
     on success, writes terminal content (or clears it) and then
     releases the flock; on reclamation failure, releases the flock
     without having changed anything — `abandon` itself fails, the run
     remains `PAUSED_RETRYABLE`, its reservation unchanged.
4. **The reservation content is self-verifying, not merely well-formed
   JSON** (Round 9's correct catch on top of Round 8's fix): `write-
   first, truncate-last` alone is not sufficient, because a write
   interrupted partway through an **equal-length-or-shorter** overwrite
   leaves some of the *old* content's bytes un-touched past where the
   write stopped — and that leftover old tail can combine with the
   already-written new prefix into a **syntactically perfectly valid,
   but semantically bogus, hybrid JSON value** that "reject trailing
   bytes" cannot catch, because there are no trailing bytes to reject
   (e.g. a write interrupted six characters into overwriting a 12-
   character `run_id` leaves the first six characters of the *new* id
   concatenated with the last six characters of the *old* one,
   immediately followed by the *old*, untouched `pid`/`claimed_at`
   fields — a complete, self-contained, strictly-parseable JSON object
   naming neither the old nor the new reservation). Trailing-byte
   rejection alone cannot distinguish this from a genuine value. **The
   actual fix**: the content written is never bare JSON — it is the
   JSON payload immediately followed by the SHA-256 hex digest (exactly
   64 ASCII characters) of that exact JSON payload, with nothing else
   after it. On every read, PEOS splits the file's bytes into
   `json_part = content[:-64]` and `hash_part = content[-64:]`,
   requires `json_part` to parse as strict JSON consuming every one of
   its bytes with nothing left over, and requires `sha256(json_part).
   hexdigest() == hash_part` **exactly** — any of these three checks
   failing is "malformed," fails closed, exactly like the already-
   established rule. This closes the hybrid-overwrite case completely:
   a partial overwrite almost certainly changes `json_part` without
   correspondingly updating `hash_part` to match it (the old hash, if
   not yet reached by the write, still reflects the old — now-mutated-
   away-from — JSON; a cryptographic hash collision between the hybrid
   and either the true old or true new payload is not a practical
   concern), so the hash check fails and the interrupted write is
   correctly rejected regardless of whether the JSON portion happens to
   parse. The write-first-truncate-last ordering from Round 8 is
   retained unchanged (now applied to the combined `json + hash`
   buffer) — it still closes the separate, "empty content" failure
   mode, which the hash does not address on its own, since an empty
   file also trivially fails this format's own length/hash
   requirement and is correctly treated as "never claimed" (the one
   state this format intentionally permits as valid-and-free) rather
   than a corruption. The precise write sequence: compute `new_content =
   new_json_bytes + sha256(new_json_bytes).hexdigest().encode()`;
   `os.lseek(fd, 0, os.SEEK_SET)`; a write loop that accumulates
   `os.write`'s own returned byte count until every byte of
   `new_content` is confirmed written (never a single, unchecked call);
   `os.fsync(fd)`; **only then** `os.ftruncate(fd, len(new_content))`
   (trimming any leftover tail from previous, longer content); a final
   `os.fsync(fd)`. No `rename`/`unlink` is used — either would operate
   on the *path* while `flock` is tied to the specific open file
   description, letting a second caller's fresh `open()` of a renamed-in
   file acquire an entirely unlocked `flock` of its own while the first
   caller still believes it holds the original; the in-place write-
   then-truncate sequence on the single, already-`flock`'d descriptor
   avoids this.

**Named, accepted limitation (PID reuse):** if the recorded bootstrap
`pid` in the "no checkpoint at all" case is later reused by the OS for
an unrelated, long-lived process, `os.kill(recorded_pid, 0)` will keep
reporting "alive" for as long as that unrelated process lives, blocking
every new task with no automatic recovery. This is a deliberate,
one-sided trade — the check can only ever fail *safe* (wrongly refuse to
proceed), never fail *unsafe* (wrongly steal an active slot), since
nothing is ever terminated on the basis of this check. PEOS never
resolves this automatically (it cannot safely determine "this PID is
unrelated" — the same ambiguous-identity problem Decision 7's service
reclamation already refuses to guess at); a human who has independently
confirmed the PID is unrelated may manually delete `.peos/run.lock`
outside PEOS to clear the stuck reservation.

**Descriptor scoping:** each entry point opens exactly **one**, process-
local file descriptor for `.peos/run.lock`, acquires and releases its
`flock` on that same descriptor via an unconditional `try`/`finally`
(released on every exit path, including an exception raised at any
point during execution — not only during the initial decision), and
never duplicates that descriptor, shares it with a child process, or
lets a launched subprocess (Claude/Codex CLIs, backend/frontend/browser-
worker services) inherit it. This is what makes "the lock is released
the instant its holding process exits, for any reason" an accurate
description of this design's actual behavior for the long-held case,
not merely for the original brief one: `flock`'s kernel-level release-
on-close guarantee holds cleanly only when no other process or
duplicated descriptor could be holding a reference to the same open
file description, and every subprocess this orchestrator launches over
a run's full lifetime must not be one of them.

### Workspace lifecycle, precisely

Unchanged: created at Planning; durable under `candidate/` while
`ACTIVE`/`PAUSED_RETRYABLE`; excluded from reconciliation and
authoritative output; rejects unsafe symlink/path configurations;
preserves its frozen `node_modules` copy; discarded via `discard_
workspace` immediately upon reaching any terminal outcome, as part of
that same transition, while ledger/checkpoint/evidence are retained under
the existing cap.

## Resume Preflight (revised per Round 2 Finding 13 — integrity/staged checks fully separated from drift)

| # | Check | On mismatch |
|---|---|---|
| 1 | Acquire `.peos/run.lock`'s `flock` **non-blocking**, held for the remainder of this execution, then confirm its content names exactly this `run_id` with a non-terminal checkpoint (the `resume`-specific branch of "Workspace Lifecycle"'s lock procedure) | `FAILED` immediately if the `flock` is already held (another execution in progress), or if the content names a different run, or an already-terminal/absent checkpoint |
| 2 | Checkpoint exists (always true for any `run_id` a human could have been given — see PLANNING's own first-write fix), readable, parses, `schema_version` matches | `FAILED` |
| 3 | `terminal_outcome` is `None` | `FAILED` |
| 4 | Repository identity (`check_repository_safety`, fresh) | `FAILED` |
| 5 | Checkpoint internal self-consistency | `FAILED` |
| 6 | Governance-artifact **integrity** against `repo_root`'s current state (own explicit row — Round 2 Finding 13 asked this be made explicit rather than implied) | `FAILED` — governance mutation is never a drift-gate matter |
| 7 | Workspace/snapshot integrity — superseded by "Partial Candidate Workspace Recovery" for an interrupted mutating phase; otherwise a mismatch is `FAILED` | see above |
| 8 | Findings-register deserialization | `FAILED` |
| 9 | Runtime/deterministic evidence **integrity** (persisted-file hash vs. recorded hash) | `FAILED` on mismatch — tamper/corruption |
| 10 | Static-context **staged-copy integrity** only — the artifact *as staged in the candidate workspace* still matches what was recorded at staging time; **this check deliberately does not consult `repo_root`'s current authoritative content at all**, since the real `reverify_identity` checks authoritative content first internally and would otherwise detect drift before the dedicated drift step below ever runs (Round 2 Finding 13) | `FAILED` on a staged-copy containment/type violation |
| 11 | Dependency/tool availability | `FAILED` |
| 12 | Claude/Codex authentication | `FAILED` |
| 13 | Runtime Verification prerequisites (if applicable) | `FAILED` |
| 14 | Orphaned-process reclamation | `FAILED` on ambiguous ownership (including the dead-leader-live-descendants case); a wholly dead process group is not ambiguous |
| 15 | **Only now**: authoritative-currency drift — `HEAD`/working-tree (via "Reconciliation Crash-Safety" for the dirty-tree case), governing-spec *authoritative* content, static-context *authoritative* content (the other half of `reverify_identity`'s check, deliberately deferred to here) | `GATE_AUTHORITATIVE_DRIFT_ON_RESUME` or `FAILED`, per "Authoritative Engineering Drift" |
| 16 | Evidence/plan **binding currency** (distinct from check 9's integrity) | not a failure — triggers a rerun of the bound phase |

## Codex and Findings Semantics on Resume

Unchanged: the real `RESOLVED`/`ACCEPTED_RECLASSIFICATION`/`HUMAN_
DECISION_REQUIRED` vocabulary throughout; resume never clears the
register, never substitutes an unrelated review, never treats a Claude
summary as closure, never reuses evidence against a mismatched binding.

## Evidence Validity (Decision 12)

Unchanged: integrity (check 9, `FAILED` on mismatch) vs. binding currency
(check 16, reruns the phase on mismatch) are two distinct checks.
Deterministic verification is never checkpointed for reuse. An orphaned,
checkpoint-unconfirmed Runtime Verification evidence directory is removed
by resume preflight before that round is reinvoked, so `persist_
evidence`'s exclusive-creation semantics do not block the legitimate
retry. `repo_state_fingerprint`'s blindness to gitignored content
(`node_modules`) is a named, accepted limitation, not fixed in V1.

## Final Delivery Gate (Decision 13, simplified per Round 2 Finding 3)

**No resumed run may reach `APPROVED` without a fresh Codex `APPROVE`
verdict produced after that resume's own preflight has completed —
unconditionally, with no exception for a review that had already reached
`COMPLETED` before the interruption.** The binding-based reuse idea an
earlier revision proposed is **retracted**: it required a per-review
record of exactly which bindings were captured at that review's
`COMPLETED` instant, which did not actually exist in the checkpoint
schema, and it conflicted with ADR-0004 Decision 12's and this
specification's own acceptance criteria's literal wording. The simpler,
stricter rule removes that need entirely: `codex_review_verdict_history`
remains in the checkpoint purely as provenance/audit trail (what a prior
round's review said), never as something `TERMINAL_DECISION` may act on
in place of a fresh call. The accepted cost is one occasionally-redundant
Codex call in the rare case where nothing material changed between a
pre-interruption `COMPLETED` review and resume — the same kind of
deliberate, named inefficiency this specification already accepts for
deterministic verification always rerunning. A pause/resume boundary
never resets, weakens, or erases the Outstanding Findings Register.

## Security

Unchanged from the prior revision.

## CLI / UX

`./bin/peos resume <run_id>` and `./bin/peos abandon <run_id>` each
acquire `.peos/run.lock`'s `flock` (non-blocking, held for their entire
execution) as their very first step, exactly as specified in "Workspace
Lifecycle and One-Run-Per-Repository" — `abandon` reclaims orphaned
processes before terminalizing (never the reverse), and scopes its
"touches nothing outside X" guarantee to `.peos/` as a whole (which
includes the shared lock file itself), never the narrower `.peos/runs/`.
`./bin/peos inspect <run_id>` remains strictly read-only and does **not**
acquire the lock at all (reading the checkpoint/ledger needs no
exclusivity). `./bin/peos runs` is not built in V1 (Decision 1).

## Acceptance Criteria (restored in full per Round 2's new finding)

Every criterion is given here, in full, self-contained normative text.

**Interruption during each phase:**

- **AC-001:** Interrupting the orchestrator process during `CLAUDE_
  IMPLEMENTATION`, before Claude's result returns, then running `peos
  resume <run_id>`, re-issues the cycle-0 Claude call without consuming
  any remediation-cycle budget.
- **AC-002:** Interrupting during `CLAUDE_REMEDIATION` cycle `N`, before
  the result returns, resumes by re-attempting cycle `N`'s Claude call,
  with `current_cycle` still reading `N-1` complete / `N` not yet
  counted.
- **AC-003:** Interrupting during `LOCAL_VERIFICATION` resumes by
  rerunning verification from scratch for that round.
- **AC-004:** Interrupting during `RUNTIME_VERIFICATION` resumes by
  rerunning it in full for that round.
- **AC-005:** Interrupting during `CODEX_INDEPENDENT_REVIEW`/`CODEX_
  CLOSURE_REVIEW`, before a structured payload returns, resumes by
  re-issuing the same review call, with the Outstanding Findings Register
  exactly as it stood before that call.

**Process/machine restart:**

- **AC-006 (corrected per Round 3's new finding, further corrected per
  Round 4):** Killing the orchestrator process between any two phases (a
  clean boundary) and resuming continues correctly from the next phase.
  Precisely, this criterion's "no redo" guarantee applies **only to
  Claude-phase work product** (an already-`COMPLETED` `CLAUDE_
  IMPLEMENTATION`/`CLAUDE_REMEDIATION` result is never redone) — it
  **explicitly does not** extend to verification or Codex-review phases,
  each of which already has its own, separately-stated rule that takes
  precedence here: deterministic verification always reruns regardless
  of prior completion (per "Evidence Validity"); Runtime Verification
  reruns whenever its binding-currency check fails (per "Evidence
  Validity"); and **at least one** fresh Codex call is always issued
  before `TERMINAL_DECISION`, even following an already-`COMPLETED`
  review (per AC-024/AC-054/"Final Delivery Gate") — "at least one," not
  "exactly one," since a fresh review returning a valid, budget-
  remaining `CHANGES_REQUIRED` still proceeds through this
  specification's ordinary, unchanged bounded-convergence loop, which may
  require further cycles before a terminal outcome is reached.
- **AC-007:** A full process restart (new PID, same `run_id`, checkpoint
  loaded fresh from disk, no in-memory state surviving) reproduces
  AC-001–AC-006's outcomes identically.
- **AC-026:** A hard kill (`SIGKILL`, no handler given the chance to run)
  at every defined phase boundary reproduces AC-001–AC-007's outcomes
  identically to a graceful `SIGTERM`.

**Cycle accounting and findings integrity:**

- **AC-008:** After resuming from an interruption mid-`CLAUDE_
  REMEDIATION` cycle `N`, the run's final cycle count (if it later
  reaches a terminal outcome) correctly reflects cycles that actually ran
  to a valid result, never double-counting or skipping the interrupted
  one.
- **AC-009:** Every Outstanding Findings Register entry present before
  an interruption is present, with identical field-by-field fidelity,
  after resume.
- **AC-010:** A finding `OUTSTANDING` before interruption that is later
  given a disposition by a post-resume Codex closure review transitions
  correctly; one a post-resume review does not address remains
  `OUTSTANDING`.
- **AC-027:** Three consecutive simulated process restarts, all
  interrupting the same logical remediation cycle `N` before its `CODEX_
  CLOSURE_REVIEW` reaches `COMPLETED`, result in exactly one allocated
  cycle `N` — never `N`, `N+1`, `N+2` for the same logical work.

**Partial candidate workspace recovery:**

- **AC-028:** Interrupting `CLAUDE_REMEDIATION` after Claude has written
  partial file changes leaves the workspace classified
  `UNTRUSTED_PARTIAL_CANDIDATE_STATE` (not `FAILED`), with a fresh
  `resume_candidate_workspace_identity` computed, and the same logical
  phase re-invoked with explicit interrupted-phase context.
- **AC-029:** The AC-028 scenario consumes exactly the one cycle it
  started with.
- **AC-030:** Interrupting a non-mutating phase and then artificially
  corrupting the workspace's content before resume is correctly
  classified `FAILED` — the partial-candidate procedure does not apply
  outside mutating phases.
- **AC-056 (new):** A partial `CLAUDE_REMEDIATION` attempt that mutated
  the workspace's own staged `CLAUDE.md` copy (while `repo_root`'s own
  copy is untouched) is detected by the staged-copy governance check
  during partial-candidate recovery and fails closed (`FAILED`), proving
  the staged-copy check this round of revision added is actually
  exercised.

**Durable phase-state model:**

- **AC-031:** A checkpoint read immediately after a durable `ENTERED`
  write never shows `last_safely_completed_phase` advanced to that phase.
- **AC-045:** A `COMPLETED` write for `CODEX_CLOSURE_REVIEW` interrupted
  between the verdict being known and the register/cycle update being
  written leaves the checkpoint at `ENTERED`, never at a `COMPLETED`
  state with a stale or missing register.
- **AC-046:** Interrupting `PLANNING` itself, before its own `COMPLETED`
  write (but after its `ENTERED` write — the checkpoint's first write,
  which always exists for a `run_id` a human could have been given),
  resumes by re-running Planning's resolution logic fresh from the same
  recorded raw inputs (`task`, `governing_spec_source`), never
  re-prompting and never resolving a different spec on retry.

**Reconciliation crash-safety:**

- **AC-047:** A reconciliation interrupted partway through applying its
  manifest resumes by re-checking each manifest entry against its
  recorded `target_content_hash`/`original_content_hash` and correctly
  distinguishes "already applied" (skip), "not yet applied, safe to
  retry" (apply), and "unexplained third state" (`FAILED`, naming the
  exact path) — proving the manifest-based mechanism, not a fingerprint
  heuristic, actually drives the recovery.
- **AC-057 (new):** Every file-level reconciliation write is atomic
  (temp file in the target's own directory, then `os.rename`) — verified
  by a test that interrupts the process mid-write and confirms the
  target file is either fully the old content or fully the new content,
  never a partial write.
- **AC-063 (new, Round 3 Finding 4):** A reconciliation interrupted
  between a file's temp-file write and its `os.rename` leaves a file
  matching `.peos-reconcile-<run_id>-*.tmp` in the authoritative tree;
  resume correctly recognizes and removes it as PEOS's own reconciliation
  debris, without classifying it as unexplained drift or routing it to
  `FAILED`/the drift gate.

**Identity enforcement (adversarial):**

- **AC-011:** A checkpoint whose `current_workspace_snapshot_identity` no
  longer matches the actual preserved workspace, for a *non-mutating*
  interrupted phase, fails resume preflight closed (`FAILED`).
- **AC-012:** The authoritative `repo_root` receiving a new commit between
  the original run and resume, with every integrity/staged-copy check
  (preflight checks 1–14) already passing, routes to `GATE_
  AUTHORITATIVE_DRIFT_ON_RESUME`, naming the specific new commit(s).
- **AC-013:** The governing specification file's content changing on
  disk between the original run and resume, with every prior check
  passing and the spec still resolving to one valid file, routes to the
  same gate; a spec that has become unreadable or ambiguous instead
  routes to `FAILED`.
- **AC-014:** A hand-edited/corrupted `checkpoint.json` is rejected at
  resume preflight (`FAILED`).
- **AC-015:** A candidate workspace that attempts to write its own file
  at `.peos/runs/<run_id>/checkpoint.json` inside its own workspace copy
  is structurally prevented from ever reaching the authoritative
  checkpoint — `reconcile_workspace_to_repo`'s `_is_run_state_path`
  exclusion blocks it.
- **AC-016:** Runtime evidence whose persisted-file hash no longer
  matches the checkpoint's recorded hash (simulated tamper) is never
  reused — resume preflight check 9 fails closed.
- **AC-017:** Deterministic verification is always rerun after any
  resume that passes through `LOCAL_VERIFICATION`, regardless of what
  the checkpoint claims about a prior round's result.
- **AC-018:** The preserved workspace directory having been deleted
  between checkpoint-write and resume fails resume preflight closed
  (`FAILED`), never silently reconstructs one.
- **AC-019:** A required dependency/tool being unavailable at resume
  time fails resume preflight closed (`FAILED`).
- **AC-020:** Claude/Codex authentication being unavailable at resume
  time fails resume preflight closed (`FAILED`), never `HUMAN_GATE`.
- **AC-032:** A checkpoint claiming a `ServiceProcessIdentity` whose PID
  now belongs to a different, live process (mismatched start time) is
  never terminated; resume fails closed (`FAILED`, "ambiguous process
  ownership"), never `HUMAN_GATE`.
- **AC-033:** A checkpoint claiming a `ServiceProcessIdentity` that
  genuinely still matches on all five signals is correctly reclaimed
  (terminated, verified dead, and its port confirmed released) before
  resume proceeds.
- **AC-058 (new):** A checkpoint claiming a `ServiceProcessIdentity`
  whose process group is alive but whose specific recorded leader `pid`
  no longer exists (a dead leader with live descendants, simulated) is
  correctly classified "ambiguous ownership" and fails closed — never
  silently treated as "nothing to reclaim."

**One-run-per-repository enforcement:**

- **AC-034:** Starting an ordinary `peos "<task>"` invocation while a
  `PAUSED_RETRYABLE` run exists fails closed immediately, before
  Planning, naming the existing `run_id`.
- **AC-035:** The identical check applies when the existing run is
  `ACTIVE` with a live lock.
- **AC-036 (corrected per Round 4, qualified per Round 8):** A lock
  whose named `run_id`'s checkpoint shows a terminal outcome is
  correctly reclaimed and does not block a new ordinary task **once
  execution ownership can also be acquired** — i.e. once the terminal
  run's own process has actually released the `flock` (ordinarily
  effectively immediate, since a process writes its own terminal
  checkpoint and then exits, releasing the flock, in short order within
  the same execution) — never merely because the checkpoint content
  alone says terminal while that process might, in principle, still be
  running and still hold the flock. The reservation check (checkpoint-
  based) and the execution-ownership check (`flock`-based) are two
  conjunctive conditions, not one check standing in for the other.
- **AC-059 (corrected per Round 4):** A lock whose named `run_id`'s
  checkpoint is still non-terminal (a `PAUSED_RETRYABLE` run, most
  commonly with its process already dead) is **not** reclaimed by
  ordinary execution — the new task fails closed, directing the human to
  resume/inspect/abandon — proving the checkpoint-based reclamation rule
  actually prevents the exact bug Round 2 found in the prior revision,
  and does so without ever consulting process liveness.
- **AC-037:** After `peos abandon <run_id>` or a successful `peos resume
  <run_id>` reaching a terminal outcome, a subsequent ordinary task
  proceeds normally.
- **AC-060 (corrected per Round 4 Finding 11, then per Round 7's
  execution-ownership fix):** Two simulated concurrent attempts to start
  a new ordinary task against the same stale (terminal-checkpoint)
  reservation each attempt the same non-blocking `flock`; exactly one
  succeeds and proceeds (holding the flock for its entire run), and the
  other observes `EWOULDBLOCK` immediately and fails closed — never
  both believing they hold execution ownership, and never one silently
  overwriting the other's fresh reservation after the fact.
- **AC-066 (new, Round 7):** Two simulated concurrent `peos resume
  <run_id>` invocations for the *same* paused `run_id` result in exactly
  one succeeding (acquiring the non-blocking `flock` and taking over
  execution ownership) and the other failing closed immediately with
  "another PEOS execution appears to be in progress" — never both
  proceeding to execute the same run concurrently.
- **AC-067 (new, Round 7):** A simulated `peos abandon <run_id>` racing a
  concurrent `peos resume <run_id>` for the same run results in exactly
  one of the two acquiring the `flock` and proceeding; the other fails
  closed immediately, never partially executing alongside the winner.
- **AC-061 (corrected per Round 5 — liveness-based, not time-based):** A
  `.peos/run.lock` that exists with no corresponding checkpoint for its
  named `run_id` at all (simulated: interrupt the process between lock
  acquisition and the checkpoint's first write) is **not** reclaimed by
  ordinary execution while the recorded `pid` is still alive (`os.kill
  (pid, 0)` raises no error) — including after an arbitrarily long
  elapsed time, proving reclamation never times out a genuinely live
  bootstrap — and **is** reclaimed once that `pid` is confirmed dead
  (`os.kill(pid, 0)` raises `ProcessLookupError`), regardless of how
  little time has elapsed since it was recorded.
- **AC-064 (new, Round 5):** A `.peos/run.lock` whose content is
  deliberately corrupted (simulated: truncate it mid-write) is never
  interpreted as empty/free — any entry point attempting to acquire it
  fails closed with an explicit corruption error.
- **AC-065 (corrected per Round 6, call count corrected per Round 9):**
  the lock-write code path calls the complete write loop, then `fsync`,
  then `ftruncate`, then a second `fsync`, in that exact order, before
  releasing the flock — verified directly by instrumenting/mocking the
  call sequence (asserting `fsync` is called **exactly twice** — an
  earlier draft of this criterion incorrectly asserted once, which no
  longer matches the write-first-truncate-last sequence — and that both
  calls occur in the stated order, before `flock(..., LOCK_UN)`),
  **not** by killing a real process and re-reading its content, which
  does **not** actually prove disk durability. A separate, explicit
  fault-injection test independently proves the write loop itself
  completes correctly under a simulated short `os.write` return.
- **AC-062 (new):** `peos resume <run_id>` given a `run_id` whose lock
  exists but whose checkpoint does not fails with an explicit "nothing to
  resume — this run never completed its bootstrap" message (`FAILED`).
- **AC-068 (corrected per Round 9 — hash-based, not trailing-byte-based,
  detection):** A reservation update interrupted (fault-injected) at
  each of the following points is correctly rejected as malformed,
  never accepted as a valid-looking reservation and never treated as
  empty/free: (a) mid-write-loop, stopping partway through an
  **equal-length-or-shorter** overwrite — the concrete counter-example
  that defeated trailing-byte rejection alone — leaving a syntactically
  valid, strictly-parseable hybrid JSON object (part new bytes, part
  un-overwritten old bytes) whose content does not match the still-
  present (not-yet-overwritten) trailing hash, correctly caught by the
  hash-mismatch check specifically, not by JSON-syntax rejection; (b)
  mid-write-loop on a **longer** overwrite, leaving a truncated,
  syntactically incomplete prefix; (c) after the complete write and its
  first `fsync` but before the final `ftruncate`, leaving the complete
  new content followed by leftover tail bytes from longer previous
  content — rejected because those extra bytes fall outside the
  expected `json + 64-hex-char-hash` length, not merely because of
  generic "trailing data" rejection. No interruption point ever leaves
  `run.lock` empty while a real, non-terminal checkpoint for the
  reservation being updated still exists, and no interruption point
  ever produces content that passes the hash check without being the
  one, true, fully-written value.

**Abandonment semantics:**

- **AC-038:** `peos abandon <run_id>` on a `PAUSED_RETRYABLE` run writes
  `terminal_outcome="ABANDONED"`, distinct from every other outcome.
- **AC-039:** `peos abandon <run_id>` discards the workspace and frees
  `.peos/run.lock`; a subsequent `peos inspect <run_id>` still succeeds
  and correctly reports `ABANDONED`.
- **AC-040:** `peos abandon <run_id>` never writes, modifies, or stages
  anything under `repo_root` outside `.peos/` (a scope that includes the
  shared lock file, which always lived there).
- **AC-041:** `peos abandon <run_id>` on a run with an unreclaimable
  orphaned process fails the abandon operation itself closed, leaving
  the run `PAUSED_RETRYABLE`.

**Retention and cleanup:**

- **AC-021:** The retention sweep never deletes a run directory whose
  checkpoint records a non-terminal outcome, regardless of age.
- **AC-022:** A `PAUSED_RETRYABLE` run later resumed to a terminal outcome
  becomes eligible for the existing terminal-run retention sweep like any
  other run.
- **AC-042:** A run reaching any terminal outcome results in its
  workspace being discarded while its ledger/checkpoint/evidence are
  retained under the existing cap.

**`MAX_CYCLES_REACHED`:**

- **AC-043:** Exhausting `effective_max_cycles` with Codex still
  returning a non-converging verdict produces `outcome="MAX_CYCLES_
  REACHED"`, not `HUMAN_GATE`.
- **AC-044:** The Delivery Report for a `MAX_CYCLES_REACHED` run renders
  the complete Outstanding Findings Register.

**Delivery-gate and action-scope invariants:**

- **AC-023:** No code path introduced by this specification calls `git
  commit`/`push`/`merge`/`tag`, under any resume outcome.
- **AC-024:** A resumed run can only reach `APPROVED` via an actual,
  structurally-validated Codex review payload produced **after** that
  resume's own preflight completes — **unconditionally, including the
  case where an earlier, pre-interruption review for the same round had
  already reached `COMPLETED`** (Round 2 Finding 3 — the binding-based
  exception an earlier revision proposed here is retracted; see "Final
  Delivery Gate").
- **AC-025:** `MAX_CYCLES_REACHED` reached after a resume correctly
  accounts for cycles run both before and after the interruption in its
  total.
- **AC-054 (revised, replaces the withdrawn reuse-case half):** A Codex
  review whose phase reached `COMPLETED` with an `APPROVE` verdict,
  interrupted before `TERMINAL_DECISION`'s own `COMPLETED` write, **does
  not** resume directly to `APPROVED` — resume always issues one more,
  fresh Codex call before `TERMINAL_DECISION` runs, even though the
  pre-interruption review already said `APPROVE`.

## Human Gate

Exactly one genuinely new category: `GATE_AUTHORITATIVE_DRIFT_ON_RESUME`
(ID `"13"`), applied only after every check in the reordered resume
preflight through check 14 has already passed. Every other condition
resolves to `FAILED` or to one of the new non-`HUMAN_GATE` outcomes.

## Backward Compatibility and Exact Spec Extension Points

- **SPEC-001/SPEC-003:** `create_isolated_workspace`/`discard_workspace`
  parameterized to the `candidate/`-nested location, no logic change.
  **`build_verification_sandbox_profile`/`build_runtime_verification_
  sandbox_profile` require a precise rule-reordering fix** (Round 2
  Finding 6): only this run's own `candidate/workspace`/`candidate/home`
  write-allow entries move to *after* the `repo_root` write-deny rule in
  the generated Seatbelt profile text; the broader, pre-existing scratch-
  space allows (`tempfile.gettempdir()`, `/private/tmp`) **keep their
  original position**, before the deny — moving the entire combined
  allow block, as an earlier revision specified, would have reopened
  writes to all of `repo_root` for any repository nested inside one of
  those broader temp-space allowances. **`peos/fsguard.py`'s atomic-write
  primitive requires a directory-fsync extension**, applied to the Run
  Ledger's writer too.
- **SPEC-004:** supersedes Resolved Decision 4 and the `GATE_UNRESOLVED_
  AFTER_REMEDIATION` encoding of convergence exhaustion; extends
  Requirement 13 (Tier 2) and 20 (new `outcome` values, checkpoint-/lock-
  aware retention); extends the `_write_ledger`/`stage` call sites to
  also drive `CheckpointWriter`'s single-transaction writes; reuses
  `peos.round_packet.RegisterEntrySnapshot` directly; extends `peos/
  claude_agent.py`/`peos/codex_agent.py` with `classify_transient_
  failure` (additive); does not change Requirements 16/17/21/22.
- **SPEC-006:** extends the Runtime Verification reuse condition with
  integrity-vs-binding-currency; adds `runtime_plan_content_hash`.
- **ADR-0003:** Decision 6 extended with `_is_run_state_path`.
- **`peos/sandbox.py`'s `reconcile_workspace_to_repo`**: requires
  restructuring around the durable, atomically-applied manifest described
  in "Reconciliation Crash-Safety" — a real, required algorithmic change
  to that function, not merely a new caller.

## Flagged Items Requiring Separate Confirmation

1. Whether a future, more specific provider usage/rate-limit resumable
   case should be added once a stable signal is confirmed.
2. Whether `gate_id`-style structure is wanted for `MAX_CYCLES_REACHED`.
3. **Whether the manifest-based reconciliation restructuring
   ("Reconciliation Crash-Safety") is acceptable as a required
   implementation change to `reconcile_workspace_to_repo`'s existing
   algorithm**, given it changes that function's internal approach (not
   merely its caller) — flagged for the Human Engineering Lead's
   awareness, since it is a larger implementation footprint than this
   specification's other extensions, even though it is the correct fix
   for a real crash-safety gap.

## Deferred/Future Work

Unchanged: automatic recognition of a stable usage/rate-limit signal;
cross-run finding tracking; a persisted deterministic-verification
evidence artifact; multi-run concurrency; a general, non-leader-specific
process-group ownership verification mechanism (Round 2 Finding 9's
accepted residual gap — reclaiming a group whose specific recorded
leader is dead but whose descendants live on).

## Known Limitations

Unchanged, plus: **a dead process-group leader with live descendants
cannot be automatically reclaimed in V1** — it fails closed as ambiguous
ownership rather than being solved, a known, accepted gap (Round 2
Finding 9), not a safety defect; **the manifest-based reconciliation
mechanism is a real, non-trivial restructuring of existing code**, named
as Flagged Item 3, not a drop-in instrumentation of the current
algorithm; **a full atomic checkpoint write per manifest entry has
real, non-negligible cost for a large reconciliation diff** (Round 4's
info-level observation — `N` manifest entries produce `N` full
checkpoint serializations plus `N` file-and-directory `fsync` sequences)
— explicitly accepted, not optimized away, consistent with this
specification's general preference for correctness and simplicity over
throughput at this project's documented scale; implementation should
still measure a representative large diff and report whether a latency
bound is actually needed in practice.

## Verification Plan

Unchanged, plus: a dedicated test proving the corrected lock-reclamation
rule (AC-059) actually prevents a new ordinary task from starting while a
`PAUSED_RETRYABLE` run's lock holder is dead; a dedicated test for
manifest-driven reconciliation's atomic per-file writes (AC-057) and its
three-way state classification on resume (AC-047); a dedicated test for
the dead-leader-live-descendants ambiguous-ownership case (AC-058); a
real Seatbelt-profile test proving the corrected, narrower rule-reordering
both permits the required writes and does not reopen `repo_root` for a
repository nested under a broader temp-space allowance.
