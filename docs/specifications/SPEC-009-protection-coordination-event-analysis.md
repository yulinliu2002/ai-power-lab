# SPEC-009 — Protection Coordination & Event Analysis

**Status:** Architecture Approved (Codex Round 5: `APPROVE`, 0 blocking/0 major/0 minor open across
the full review history) — implementation not yet started; see "STOP before implementation" in the
governing brief. Pending Human Engineering Lead approval per `ENGINEERING.md`'s Core Workflow.
**Project:** AI Power Lab
**System:** `dashboard/adapters/protection_timeline.py` (additive extension — new fields/dataclass,
no new module), `backend/schemas.py` (additive extension of the existing mirrored models — no new
endpoint), `frontend/app/components/` (one new presentation component consuming the existing
`protection_timeline` field). No change to `src/` (simulation physics) is in scope or required.
**Version:** 0.5 (0.1 returned Codex `CHANGES_REQUIRED` with 0 blocking/6 major/3 minor findings;
0.2 closed all 9. A focused Round 2 closure review of 0.2 independently re-ran all five scenarios,
confirmed 6 of the 9 `CLOSED` as described, found 3 `STILL_OUTSTANDING` (two residual stale-wording
items, one mis-cited test file) and raised 2 **new** issues v0.2's own rewrite introduced (a real
contradiction between AC-028 and §6.1 for Thermal Trip's real run, and an incomplete §10
verification mapping) — `CHANGES_REQUIRED`, 0 blocking/2 major/3 minor. 0.3 closed all 5. A focused
Round 3 closure review of 0.3 — scoped only to those 5 items, independently re-running Thermal Trip
and confirming its two separation values (31.701 s, 2.728 s) — confirmed 4 `CLOSED` and found 1
`STILL_OUTSTANDING` (R2-2's AC-034 check verified only internal TypeScript consistency, not
agreement with the Python backend schemas it mirrors) — `CHANGES_REQUIRED`, 0 blocking/0 major/1
minor. 0.4 closed it. A final focused Round 4 closure review of 0.4 — scoped only to R2-2, plus one
end-to-end scan for any other remaining placeholder/inconsistency — confirmed R2-2 `CLOSED` and
found one new, unrelated minor citation error (§5 cited "AC-013/AC-014," which do not exist in this
specification's own AC-027–AC-038 namespace, instead of the correct AC-032) — `CHANGES_REQUIRED`,
0 blocking/0 major/1 minor. 0.5 fixed that one-line citation. A final Round 5 confirmation review
of 0.5 returned **`APPROVE`**, 0 blocking/0 major/0 minor open across the full review history. See
"Codex Architecture/Specification Review — Round 4" and the Outstanding Findings Register, §13, for
the complete final disposition.)
**Type:** Software Component (presentation/derived-analysis layer over SPEC-008's existing
`ProtectionTimeline` output; no new engineering model)

---

This specification is a PEOS dogfood artifact: it inspects the repository's existing SPEC-008
Protection & Ride-Through Timeline implementation (§0) before proposing any new architecture, per
`ENGINEERING.md`. It is an **explicit, additive extension of SPEC-008**, not a competing event
model (per SPEC-009's own governing prompt, rule 6: "reuse SPEC-008 timeline semantics rather than
creating a competing event model").

## Codex Architecture/Specification Review — Round 1

An independent Codex architecture/specification review of SPEC-009 v0.1 (standalone, read-only,
`codex exec --sandbox read-only`, against this repository's actual code — including direct
adapter execution — plus `CLAUDE.md`/`ENGINEERING.md`/`AGENTS.md`/SPEC-008/its validation record)
returned **`CHANGES_REQUIRED`** with 0 `blocking`, 6 `major`, and 3 `minor` findings. It
independently confirmed Thermal Trip's real numbers (trip at 46.147 s, floor contact at 14.446 s,
separation 31.701 s, derating begins at 11.718 s — consistent with SPEC-008's validation record),
confirmed the coverage matrix's five rows accurately describe `src/protection.py`, confirmed no new
endpoint/route is needed, and confirmed universal (non-Load-Step-conditional) rendering of both the
existing Timeline and the new Coordination section needs no separate Human Gate. All 9 findings are
remediated in v0.2 — see §13 for the complete disposition, including Round 2's closure review of
that remediation.

## Codex Architecture/Specification Review — Round 2

A focused closure review of v0.2 (same standalone, read-only posture; explicitly scoped to auditing
v0.2's own §13 claim that all 9 Round 1 findings were closed, against v0.2's actual text and the
real repository code — not a fresh broad review) independently re-ran all five scenarios (direct
adapter execution) and re-read the full v0.2 text. It confirmed 6 of 9 findings `CLOSED` as
described (#1, #2, #3, #4, #5, #8), found 3 `STILL_OUTSTANDING` (#6: the behavioral-test citation
named a test file, `tests/test_thermal_protection_simulation.py`, that does not actually assert the
claimed debounce/latching behavior; #7 and #9: each had one residual stale sentence elsewhere in
the document that v0.2's targeted edits had not reached), and raised two **new** issues: a real
contradiction between AC-028's "exactly one" wording and §6.1's own rules, which — confirmed by
direct execution — produce *two* legitimate separation entries for Thermal Trip's real run
(derating begins at 11.718 s, strictly before the 14.446 s terminal event, in addition to the
46.147 s trip); and an incomplete §10 verification-plan mapping for AC-034/AC-035/AC-038. Final
tally: `CHANGES_REQUIRED`, 0 blocking, 2 major, 3 minor. v0.3 closes all 5.

## Codex Architecture/Specification Review — Round 3

A focused closure review of v0.3 (same standalone, read-only posture; explicitly scoped only to the
5 items Round 2 raised — not a re-check of Round 1's already-twice-confirmed findings 1–5/8, and
not a fresh broad review) independently re-ran Thermal Trip directly, confirming both separation
values (`"Bus energy floor -> thermal trip"` ≈ 31.701 s, `"Derating begins -> terminal event"` ≈
2.728 s, from a first `DERATED` segment at 11.718 s and the 14.446 s terminal/bus-floor event) and
confirming all three named `tests/test_protection.py` tests exist at lines 55/67/91 and actually
assert the claimed debounce/short-transient-rejection/latching behavior. It confirmed 4 of the 5
items `CLOSED` (Round 1 #6, #7, #9; Round 2's R2-1) and found 1 `STILL_OUTSTANDING`: R2-2's AC-034
check (added in v0.3) verified only internal TypeScript consistency (`tsc --noEmit`), establishing
no agreement between `simulationApi.ts`'s new interfaces and the `backend/schemas.py` models they
are supposed to mirror. Final tally: `CHANGES_REQUIRED`, 0 blocking, 0 major, 1 minor. v0.4 closes
it.

## Codex Architecture/Specification Review — Round 4

A final focused closure review of v0.4 (same standalone, read-only posture; explicitly scoped only
to R2-2, the one remaining open item, plus one end-to-end scan for any other remaining
placeholder/inconsistency — not a re-check of any already-twice-confirmed finding) confirmed R2-2
`CLOSED` (§10's AC-034 check now explicitly requires a field-by-field comparison of
`ProtectionTimeline`/`CoordinationAnalysis`/`EventSeparation`/`CoverageEntry` against their backend
model mirrors — concrete, executable, non-duplicative of AC-033) and found one new, unrelated minor
finding: §5 cited "AC-013/AC-014" (criterion numbers from SPEC-008's namespace, not this
specification's own AC-027–AC-038 namespace) where it meant **AC-032**, the actual coverage-tracing
criterion (already correctly cited in §11). Final tally: `CHANGES_REQUIRED`, 0 blocking, 0 major, 1
minor. v0.5 fixes the one-line citation — see §13 for the complete, final disposition of all 9
Round 1 findings, both Round 2 findings, and this one Round 4 finding.

## 0. What Already Exists (repository inspection findings)

This section is evidence, not a requirement.

**`dashboard/adapters/protection_timeline.py` (SPEC-008, `APPROVE`, 0/0/0 open).** A pure,
side-effect-free module. `build_protection_timeline(telemetry, config, input_events) ->
ProtectionTimeline` already computes, from an already-run `Telemetry` + `Config`:

- `segments: tuple[StateSegment, ...]` — a run-length encoding of `operating_state` into
  `RUNNING`/`DERATED`/`TRIPPED` segments with `start_time_s`/`end_time_s`/`duration_s`/
  `is_open_ended`.
- `events: tuple[TimelineEvent, ...]` — a merged, chronological list with `category` ∈
  `{"protection_state", "input_event", "bus_energy"}`, each carrying a config/telemetry-traceable
  `detail` string.
- `outcome: RideThroughOutcome` ∈ `{RIDE_THROUGH, PROTECTION_TRIP, BUS_COLLAPSE_UNPROTECTED}` and
  `outcome_event_time_s: float | None` — computed by `_classify_outcome`, which is itself called by
  `build_protection_timeline` with two already-computed, **internal, not-yet-exposed** local
  variables as its arguments: `trip_event_time_s` (computed by `_first_true_time(telemetry.trip_active,
  telemetry.time_s)` — the first `trip_active=True` sample) and `bus_collapse_event_time_s`
  (computed by `_first_floor_contact_time(telemetry, floor_v)`, which reuses the exact same
  `<= floor_v + _BUS_FLOOR_TOLERANCE_V` (0.5 V) tolerance `_build_bus_energy_events` already
  uses — **not** an exact-floor-only comparison). `_classify_outcome` itself performs no telemetry
  scan; it only compares the two floats it is given. Only whichever of the two "won" the
  ordered-event comparison is returned onward as `outcome_event_time_s`; the other candidate time
  is computed inside `build_protection_timeline`, passed into `_classify_outcome`, and then
  **discarded** at the return boundary — neither `ProtectionTimeline` nor `ProtectionTimelineModel`
  (`backend/schemas.py`) exposes either raw candidate today.
- `recovery: RecoveryStatus` ∈ `{RECOVERED, NOT_RECOVERED, NOT_APPLICABLE}` — a separate,
  descriptive ±1%-settling-band classification, independent of `outcome`.
- `outcome_label`/`outcome_detail`/`recovery_label` — backend-owned display strings; the frontend
  (`ProtectionTimeline.tsx`) already reads every one of these verbatim, with zero
  enum-to-English translation performed client-side (SPEC-008 AC-011/AC-014).

**This is the one concrete gap §A's governing prompt asks about.** `trip_event_time_s` and
`bus_collapse_event_time_s` are *already computed, by the same function, from the same telemetry,
using the exact comparison SPEC-008 §9 specifies* — they are simply not threaded out to the return
value. SPEC-009 needs **both** times (not just the winning one) to state facts like "bus floor →
thermal trip: 31.701 s" for `BUS_COLLAPSE_UNPROTECTED` runs where a trip occurs later. Re-deriving
them independently in a new SPEC-009 module would be exactly the "competing event model" rule 6
forbids, and would risk the new code disagreeing with `_classify_outcome`'s own comparison. The
correct move is the smallest one: **expose the two already-computed times as two new fields on the
existing `ProtectionTimeline` dataclass**, computed once, in the one place that already computes
them. No new derivation, no new telemetry scan, no new tolerance.

**`src/protection.py` (unchanged, read-only for SPEC-009).** Three-state machine
(`RUNNING`/`DERATED`/`TRIPPED`), one trip cause (`sustained_overtemperature`), latched (no reset),
debounced (`thermal_trip_time_s`). Its own module docstring's "Limitations" section states,
verbatim: "Only one trip cause (sustained overtemperature). DC bus over/under-voltage protection is
a reasonable future addition... but is intentionally out of scope here," and "No reset mechanism."
`OperatingState` has exactly three members; `step_protection`'s signature has no voltage, current,
or grid-availability parameter anywhere. This is the one and only source of truth for SPEC-009's
coverage matrix (§5) — every coverage claim traces to this file's actual enum/function signature,
never to prose alone.

**Backend (`backend/app.py`, `backend/schemas.py`).** One `POST /api/v1/simulations/load-step` and
one `GET /api/v1/simulations/protection-scenarios/{scenario}` (for `sustained_high_load`,
`thermal_trip`, `grid_sag`, `grid_loss`). Both call `build_protection_timeline` once and serialize
its result via `_serialize_protection_timeline` into `ProtectionTimelineModel`, which mirrors the
Python dataclass field-for-field. Both response schemas (`LoadStepResponse`,
`ProtectionScenarioResponse`) already carry `protection_timeline: ProtectionTimelineModel`. There
is clear, direct precedent (this exact mirroring pattern) for adding new fields to
`ProtectionTimeline`/`ProtectionTimelineModel` and having both existing endpoints carry them with
**zero route or endpoint changes** — `backend/app.py`'s own docstring's "thin translation" rule is
honored by extending the one serialization function, not by adding a second one.

**Frontend (`frontend/app/components/ProtectionTimeline.tsx`, `page.tsx`).** The existing component
renders, in order: `SegmentBar`, `EventList`, `OutcomeBanner`, then the fixed educational caption.
It reads every backend-owned string verbatim (no `switch`/translation table maps an enum to English
anywhere in this file except the two local presentation-only maps — `OUTCOME_ROLE`,
`DOT_BG_BY_ROLE`/`SEGMENT_BG_BY_ROLE` — which map an enum to a **visual role** only, e.g. `good`/
`warning`/`critical`, never to wording). This is the precedent SPEC-009's own coordination/coverage
rendering must follow: enum-to-color-role mapping is acceptable (it already exists); enum-to-English
translation of an engineering label/detail string is not — the backend owns every such string
verbatim, while static headings, captions, and numeric formatting remain frontend-owned (the exact,
narrower contract §8 states; this section and §8 are kept consistent, not stated two different ways).

**Scenario behavior, re-derived here from SPEC-008 §0's table plus the two newly-exposed times
(confirmed by direct adapter execution, not assumed — see §6):**

| Scenario | `outcome` | `trip_event_time_s` | `bus_collapse_event_time_s` | Both terminal events occur? |
|---|---|---|---|---|
| Load Step | `RIDE_THROUGH` | `None` | `None` | No |
| Sustained High Load | `RIDE_THROUGH` | `None` | `None` | No |
| Thermal Trip | `BUS_COLLAPSE_UNPROTECTED` | `46.147` | `14.446` | **Yes** — the only real scenario where both fire |
| Grid Sag | `BUS_COLLAPSE_UNPROTECTED` | `None` | (mid-run value) | No (trip never latches) |
| Grid Loss | `BUS_COLLAPSE_UNPROTECTED` | `None` | (early value) | No (trip never latches) |

Thermal Trip is the only real scenario with a meaningful "event separation" number. This is not a
defect in this specification's design — it is §0's own honestly-reported fact, carried forward:
`PROTECTION_TRIP` and the exact-timestep tie are reachable only via constructed fixtures (SPEC-008
§0, AC-019), so SPEC-009's coordination classification's `PROTECTION_ACTED_*` branches are, like
SPEC-008's own `PROTECTION_TRIP` outcome, tested by fixture, not by any of today's five scenario
presets, and this specification says so plainly rather than silently relying only on fixture
coverage while implying otherwise.

**PEOS Runtime Verification (`peos/runtime_catalog.py`).** Unchanged capability: `page_load`,
`viewport_overflow`, `experiment_run` (cannot drive the scenario selector). Same honest limitation
as SPEC-008 §18/§19 — recorded, not fixed, here.

## 1. Purpose

Turn the existing, already-authoritative Protection Timeline into a **Protection Coordination /
Event Analysis** view that answers, for the active run, without the user doing arithmetic: what
happened first; what condition triggered each event; which events are authoritative protection-state
output versus derived system observations; how much time separated the important events; whether
modeled protection acted before or after loss of DC-bus viability; what V1 does and does not protect
against; and what can and cannot be concluded from this educational model.

## 2. Engineering Question

Given a `ProtectionTimeline` that already classifies a run's terminal outcome by comparing two
candidate event times, what is the smallest additive extension that (a) exposes both candidate
times so their separation and ordering can be stated explicitly, (b) classifies that ordering into
a small, deterministic set of non-causal coordination statements, and (c) states, once, which
protection functions this V1 model does and does not implement — without inventing any new physical
quantity, threshold, or endpoint?

## 3. Scope

- Two new fields on the existing `ProtectionTimeline` dataclass (`dashboard/adapters/protection_timeline.py`):
  `trip_event_time_s: float | None` and `bus_collapse_event_time_s: float | None` — the two
  candidate times `build_protection_timeline` already computes (via `_first_true_time`/
  `_first_floor_contact_time`) and passes into `_classify_outcome`, now both exposed (§0, §4).
- One new dataclass, `CoordinationAnalysis`, and one new pure function,
  `classify_coordination`, in the same module — computed once inside
  `build_protection_timeline` and attached as `ProtectionTimeline.coordination` (§4).
- One new, run-independent, static constant, `PROTECTION_COVERAGE`, in the same module,
  describing exactly what `src/protection.py` does and does not implement, attached as
  `ProtectionTimeline.coverage` (§5).
- Additive mirrors of all of the above in `backend/schemas.py`'s existing
  `ProtectionTimelineModel` — no new endpoint, no new route (§7).
- One new frontend component, `ProtectionCoordination.tsx`, rendered immediately after the
  existing `ProtectionTimeline.tsx` section for every scenario, reading the new fields verbatim
  (§8).
- Deterministic verification extending `tests/test_protection_timeline.py` and `tests/test_api.py`
  (§9).

## 4. Out of Scope

- Any change to `src/` — no new protection physics, no bus-voltage trip, no reset logic. Rule 3 of
  the governing prompt is explicit: do not introduce DC undervoltage protection into `src/` to make
  the coordination result look better. The coordination result for Thermal Trip **remains**
  "DC-bus viability was lost before the modeled thermal trip" — stated as an honest fact about this
  educational model, never resolved by changing the model.
- A second/new backend endpoint. §0 and §7 establish that both existing endpoints already return
  `protection_timeline`; the new fields ride along for free.
- Any user-adjustable protection threshold, slider, or runtime parameter (rule 9).
- New scenario types or new scenario parameters (rules 1, 2, 10) — the same five fixed presets.
- A general causal-inference engine. §6's classification is a fixed, small, explicitly
  non-causal decision table over two optional floats — not a rule system, not configurable.
- Any PEOS (`peos/`) change (same posture as SPEC-008 Engineering Lead Decision 7 — not reopened
  here).
- A frontend test framework/runner (none exists today; out of this specification's authority per
  `CLAUDE.md`).
- Removing or restructuring anything SPEC-008 shipped. `ProtectionTimeline.tsx` is extended by a new
  sibling section, not rewritten.

## 5. Protection Coverage Matrix

A **static, run-independent** fact about `src/protection.py`'s implementation — the same answer for
every scenario and every run, because it describes what the code implements, not what any particular
telemetry series shows. Computed once as a module-level constant, never per-run:

```python
PROTECTION_COVERAGE: tuple[CoverageEntry, ...] = (
    CoverageEntry(
        function="Sustained thermal overtemperature",
        modeled=True,
        detail="src/protection.py: debounced (thermal_trip_time_s), latched TRIPPED state.",
    ),
    CoverageEntry(
        function="DC-bus undervoltage",
        modeled=False,
        detail="No voltage-based trip exists in src/protection.py. The numerical energy floor "
               "(dashboard bus_energy events) is an observation of src/dc_bus.py's energy "
               "floor, never a protection action.",
    ),
    CoverageEntry(
        function="DC-bus overvoltage",
        modeled=False,
        detail="Same basis as DC-bus undervoltage: no voltage-based trip of any kind exists.",
    ),
    CoverageEntry(
        function="Automatic trip reset",
        modeled=False,
        detail="src/protection.py's own module docstring: 'No reset mechanism... TRIPPED state "
               "stays TRIPPED for the rest of the scenario.'",
    ),
    CoverageEntry(
        function="Grid-availability-based protection",
        modeled=False,
        detail="No grid_available-driven protection logic exists in src/protection.py; "
               "grid loss is handled only as a load/source condition in src/simulation.py.",
    ),
)
```

Every `modeled=False` row traces to a sentence already in `src/protection.py`'s own docstring or to
the literal absence of a corresponding parameter/branch in its code — none is inferred from what a
scenario's telemetry happens to show, and none is a claim about what a non-V1, real system does or
does not have (rule 2 of the governing prompt: do not add real-world thresholds "because they are
common industry values" — this table makes zero claims about real hardware; it only describes this
repository's own code). **Grid-availability-based protection** is included because `grid_loss`/
`grid_sag` scenarios exist and a reader could otherwise wonder whether grid-loss handling is a form
of protection; it is not, and the table says so explicitly rather than omitting the question.

**Verification tying coverage claims to code, not prose (§9, AC-032) — supplemental, not a
complete guarantee.** A dedicated structural test asserts `len(OperatingState) == 3` (`RUNNING`,
`DERATED`, `TRIPPED` only) and inspects `step_protection`'s signature for the absence of any
voltage/current/grid-availability parameter. This test is **not** claimed to catch every possible
future change to `src/protection.py`'s behavior — Codex Round 1 correctly noted that reset logic
could, in principle, be added inside the existing `TRIPPED` branch, or the debounce timer's
behavior could change, without altering the enum's member count or `step_protection`'s parameter
names, so a purely structural test cannot detect either. This specification therefore makes two
narrower, honest claims instead of one overclaimed one:

1. The structural test (enum arity + signature inspection) is **supplemental evidence** that no
   *new protection input* (a voltage, current, or grid-availability parameter) has been added
   without updating `PROTECTION_COVERAGE` — it directly detects exactly that one class of change,
   and no other.
2. `src/protection.py`'s existing **behavioral** regression tests — specifically
   `tests/test_protection.py::test_trip_after_sustained_overtemperature`,
   `::test_no_false_trip_from_short_transient`, and
   `::test_trip_is_latched_even_after_temperature_recovers` (confirmed present at
   `tests/test_protection.py:55`, `:67`, `:91`) — remain the load-bearing evidence that the two
   `modeled=True`/`modeled=False` behavioral claims in `PROTECTION_COVERAGE` ("debounced...
   latched," "No reset mechanism") stay true: the first two tests directly exercise the debounce
   timer (a sustained overtemperature trips; a short transient does not), and the third directly
   exercises the no-reset/latching claim. SPEC-009 adds no new behavioral test of its own for
   these, and instead references these three existing tests by name (§9).

Any change to `src/protection.py`'s protection *behavior* that neither adds/removes a parameter nor
breaks an existing behavioral test is, by construction, outside what any test in this repository
checks today — `PROTECTION_COVERAGE`'s accuracy in that narrow case rests on manual review at the
time `src/protection.py` is next changed, the same way every other `CLAUDE.md`-required
documentation-trueness rule in this repository already does. This is stated as a known limitation
(§11), not silently assumed away.

## 6. Coordination Semantics

**Inputs — both already computed by `build_protection_timeline`, now both exposed (§3):**

- `trip_event_time_s: float | None` — unchanged meaning from `_classify_outcome`'s internal
  `trip_event_time_s`: first sample where `trip_active` is `True`, or `None`.
- `bus_collapse_event_time_s: float | None` — unchanged meaning from `_classify_outcome`'s internal
  `bus_collapse_event_time_s`: first sample where `v_dc_v` is at-or-below the numerical floor, or
  `None`.

**`CoordinationResult` — a fixed, five-member enum, computed by one small, deterministic function,
`classify_coordination(trip_event_time_s, bus_collapse_event_time_s) -> CoordinationResult`:**

```python
class CoordinationResult(Enum):
    NO_TERMINAL_EVENT = "NO_TERMINAL_EVENT"
    PROTECTION_ACTED_NO_VIABILITY_LOSS = "PROTECTION_ACTED_NO_VIABILITY_LOSS"
    PROTECTION_ACTED_BEFORE_VIABILITY_LOSS = "PROTECTION_ACTED_BEFORE_VIABILITY_LOSS"
    VIABILITY_LOST_NO_PROTECTION_ACTION = "VIABILITY_LOST_NO_PROTECTION_ACTION"
    VIABILITY_LOST_BEFORE_PROTECTION_ACTION = "VIABILITY_LOST_BEFORE_PROTECTION_ACTION"
```

Rule table (exhaustive over the four `(trip_event_time_s, bus_collapse_event_time_s)` nullability/
ordering combinations — this is a total function, every branch reachable by construction):

1. Both `None` → `NO_TERMINAL_EVENT`. ("No terminal protection action or bus-energy-floor event
   occurred — equivalent to `outcome == RIDE_THROUGH`.")
2. `trip_event_time_s` is not `None`, `bus_collapse_event_time_s` is `None` →
   `PROTECTION_ACTED_NO_VIABILITY_LOSS`. ("Thermal protection latched TRIPPED; the bus never
   reached its numerical energy floor at any point in this run.")
3. Both not `None`, `trip_event_time_s < bus_collapse_event_time_s` (strict) →
   `PROTECTION_ACTED_BEFORE_VIABILITY_LOSS`.
3a. Both not `None` and **exactly equal** (`trip_event_time_s == bus_collapse_event_time_s`) →
   still classified `PROTECTION_ACTED_BEFORE_VIABILITY_LOSS`, reusing `_classify_outcome`'s own
   `<=` tie-break convention exactly (SPEC-008 §9) so `CoordinationResult` never disagrees with
   `outcome` about which classification a tie resolves to. **But its label/detail text and its
   `EventSeparation` entry (§6.1) must never say "before" for this case** — Codex Round 1 Finding 8
   is explicit that a `*_BEFORE_*` enum name paired with an unqualified directional sentence would
   assert a false temporal precedence for a tie. `_describe_coordination` must render the tied case
   with dedicated wording that states the two events share the exact same recorded sample and names
   the tie-break convention explicitly (e.g. "Thermal protection latched TRIPPED at the same
   recorded sample the bus reached its numerical energy floor (t = {time} s) — an exact-timestep
   tie, resolved toward 'protection acted' by an explicit, non-causal convention (SPEC-008 §9), not
   because one event preceded or caused the other."), and §6.1's separation entry for this case
   must use the label `"Thermal trip / bus energy floor — same recorded sample"` with
   `duration_s = 0.0`, never a directional `"X -> Y"` label (which would misstate order). This is
   the one case `separations` MAY legitimately produce `duration_s == 0.0`, and only this case.
4. `trip_event_time_s` is `None`, `bus_collapse_event_time_s` is not `None` →
   `VIABILITY_LOST_NO_PROTECTION_ACTION`. ("The bus reached its numerical energy floor; thermal
   protection never latched TRIPPED at any point in this run." — Grid Sag, Grid Loss.)
5. Both not `None`, `bus_collapse_event_time_s < trip_event_time_s` →
   `VIABILITY_LOST_BEFORE_PROTECTION_ACTION`. ("The bus reached its numerical energy floor before
   thermal protection later latched TRIPPED." — Thermal Trip.)

**This is strictly more granular than `outcome` by design, not a duplicate of it.** `outcome`
(SPEC-008 §9) only asks "which terminal event happened first, if either" and treats a trip that
occurs *after* an already-determined bus collapse as irrelevant to the three-way classification (by
design — Engineering Lead Decision 2). `CoordinationResult` is the one place that *also* answers "did
protection ever act at all, even later" for exactly that case — distinguishing Thermal Trip
(`VIABILITY_LOST_BEFORE_PROTECTION_ACTION`, a trip did eventually occur) from Grid Sag/Grid Loss
(`VIABILITY_LOST_NO_PROTECTION_ACTION`, no trip ever occurred). Rules B's governing prompt example
output — "Coordination result: DC-bus viability was lost before the modeled thermal trip" — is
exactly case 5's label, worded for Thermal Trip.

**No causal language anywhere in any label or detail string.** Every detail string states only that
one event's recorded time preceded another's, mirroring `src/simulation.py`'s own documented
step-order explanation already present in `_classify_outcome`'s docstring (SPEC-008 §9) — never "the
trip caused," "led to," or "resulted in."

**`CoordinationAnalysis` dataclass — the full additive shape:**

```python
@dataclass(frozen=True)
class CoordinationAnalysis:
    result: CoordinationResult
    result_label: str        # backend-owned, verbatim (§8)
    result_detail: str        # backend-owned, verbatim (§8)
    derating_preceded_terminal_event: bool | None
    separations: tuple[EventSeparation, ...]
```

```python
@dataclass(frozen=True)
class EventSeparation:
    label: str          # e.g. "Bus energy floor -> thermal trip"
    from_time_s: float
    to_time_s: float
    duration_s: float   # = to_time_s - from_time_s; always >= 0 by construction (§6.1)
```

**§6.1 — `derating_preceded_terminal_event`: one comparison target, an explicit rule for every
case (closes Codex Round 1 Finding 1).** The comparison target is always
`outcome_event_time_s` — the one terminal-event time `outcome` (SPEC-008 §9) already resolved to,
never `trip_event_time_s` specifically (which may be `None` even when `outcome_event_time_s` is
not, e.g. `BUS_COLLAPSE_UNPROTECTED` with no trip ever occurring). Let `first_derated_start_s` be
the `start_time_s` of the first segment in `segments` with `state == "DERATED"`, or `None` if no
such segment exists.

- `None` — if `outcome_event_time_s is None` (no terminal event at all; `outcome == RIDE_THROUGH`)
  **or** `first_derated_start_s is None` (temperature never rose enough to derate in this run —
  e.g. Grid Sag, Grid Loss, whose terminal bus-collapse event is never temperature-driven). Either
  condition alone is sufficient for `None`; both conditions being simultaneously possible does not
  make the field ambiguous, because `None` is returned for either.
- `True` — both are not `None` and `first_derated_start_s < outcome_event_time_s` (strict):
  derating measurably began before the terminal event that determined `outcome`.
- `False` — both are not `None` and `first_derated_start_s >= outcome_event_time_s`: derating began
  at the same recorded sample as, or after, the terminal event. This is a real, reachable branch
  (not dead code) — e.g. a constructed fixture where the bus reaches its numerical floor from a
  non-thermal cause before temperature ever crosses the derating threshold, and only later derates;
  §9's fixture set must exercise it, not just assert it exists in prose.

**Which separations are legitimate (closes Codex Round 1 Findings 2 and 8; governing prompt §C).**
`separations` is built by two small, explicit rules, never a loop populating every possible pair —
and never producing a negative `duration_s`:

- **Terminal-event separation**, included **iff** both `trip_event_time_s` and
  `bus_collapse_event_time_s` are not `None` (equivalently: `coordination.result ∈
  {PROTECTION_ACTED_BEFORE_VIABILITY_LOSS, VIABILITY_LOST_BEFORE_PROTECTION_ACTION}`, §6 cases 3/3a/5):
  - **Tied case (§6 case 3a):** `label = "Thermal trip / bus energy floor — same recorded sample"`,
    `from_time_s = to_time_s = trip_event_time_s`, `duration_s = 0.0`. Never a directional label.
  - **Non-tied case:** `from_time_s` = the earlier of the two candidate times, `to_time_s` = the
    later, `duration_s = to_time_s - from_time_s` (always `> 0` here, since the tied case is
    handled separately above), and `label` names the actual chronological direction — `"Bus energy
    floor -> thermal trip"` when the floor came first (Thermal Trip's real case: `outcome ==
    BUS_COLLAPSE_UNPROTECTED`, case 5), `"Thermal trip -> bus energy floor"` in the constructed-
    fixture case where the trip strictly precedes a later floor contact (case 3).
- **Derating-to-terminal-event separation**, included **iff** `derating_preceded_terminal_event is
  True` (§6.1's rule above — this guard, by construction, guarantees `first_derated_start_s <
  outcome_event_time_s`, so `duration_s` is always strictly positive; it is never included when the
  field is `False` or `None`, closing Codex Round 1 Finding 2's counter-example directly). `label =
  "Derating begins -> terminal event"`, `from_time_s = first_derated_start_s`, `to_time_s =
  outcome_event_time_s`, `duration_s = to_time_s - from_time_s`.
- No other interval is computed. `RIDE_THROUGH` runs (Load Step, Sustained High Load under
  defaults) produce `separations = ()` — an empty tuple is the correct, honest answer, not a gap to
  fill with a manufactured number (closes governing prompt §C's "do not manufacture meaningless
  intervals").

## 7. Backend / API Impact

**No new endpoint, no new route.** Both existing endpoints (`POST .../load-step`, `GET
.../protection-scenarios/{scenario}`) already call `build_protection_timeline` once and serialize its
result. This specification's entire backend diff is:

1. `dashboard/adapters/protection_timeline.py`: add `trip_event_time_s`/`bus_collapse_event_time_s`
   fields to `ProtectionTimeline`; add `CoordinationResult`/`EventSeparation`/`CoordinationAnalysis`
   dataclasses and `coordination: CoordinationAnalysis` field to `ProtectionTimeline`; add the
   `PROTECTION_COVERAGE` constant and a `coverage: tuple[CoverageEntry, ...]` field to
   `ProtectionTimeline`, populated with the same constant on every call (documented in the
   docstring as "static — identical across every run, included on `ProtectionTimeline` for
   presentation uniformity only, exactly as SPEC-008 §0 did for Scenario A's Protection Timeline
   itself"). `build_protection_timeline`'s existing internal `trip_event_time_s`/
   `bus_collapse_event_time_s` locals are threaded into the new fields and into
   `classify_coordination` — no second computation of either value.
2. `backend/schemas.py`: mirror the three new fields/dataclasses as `CoverageEntryModel`,
   `EventSeparationModel`, `CoordinationAnalysisModel`; add `trip_event_time_s`,
   `bus_collapse_event_time_s`, `coordination: CoordinationAnalysisModel`, and
   `coverage: list[CoverageEntryModel]` to `ProtectionTimelineModel`. No existing field of
   `ProtectionTimelineModel`, `LoadStepResponse`, or `ProtectionScenarioResponse` changes type or
   meaning — purely additive, exactly like SPEC-008's own `protection_timeline` field was additive
   to `LoadStepResponse`.
3. `backend/app.py`: `_serialize_protection_timeline` gains the four new field mappings. No route
   decorator, path, method, or existing field mapping changes.

**Top-level key-set tests are unaffected; one nested key-set test requires an explicitly authorized
update (corrects Codex Round 1 Finding 4, which found the original claim false).**
`test_load_step_response_schema_shape`'s top-level assertion (`tests/test_api.py:69`) and
`test_protection_scenario_response_schema_shape`'s top-level assertion (`tests/test_api.py:297`) both
assert the **top-level** response key set (`{"scenario", "thresholds", "events", "timeseries",
"protection_timeline"}`) — unaffected, since this specification adds fields *inside*
`protection_timeline`, not at the top level. However, `test_protection_scenario_response_schema_shape`
*also* asserts the exact **nested** key set of `body["protection_timeline"]` itself
(`tests/test_api.py:302`: `{"segments", "events", "outcome", "outcome_event_time_s",
"outcome_label", "outcome_detail", "recovery", "recovery_label"}`) — this literal set **does**
require updating, since the four new fields (`trip_event_time_s`, `bus_collapse_event_time_s`,
`coordination`, `coverage`) land inside it. This specification explicitly authorizes updating
**that one literal set** (`tests/test_api.py:302`) to add the four new key names — and authorizes
nothing else in that test, or any other existing assertion in `tests/test_api.py`, to change (same
pattern as, and by the same authority as, SPEC-008 §11/AC-007's precedent for the top-level set).

**`_timeline_to_dict` (`tests/test_api.py:22`), the shared parity-test helper both
`test_load_step_protection_timeline_matches_direct_build` and the Scenario-B–E parity test already
call, must gain the four new fields in its returned dict** — mirroring
`_serialize_protection_timeline`'s own additions (§7 above) field-for-field, so both existing parity
tests continue to compare the *complete* serialized shape (not a stale subset that would silently
stop verifying the new fields) without either existing test's call site or assertion logic changing.
This is the one other explicitly authorized change in `tests/test_api.py`.

## 8. Frontend Presentation

**Required, named additive changes to existing frontend files (corrects Codex Round 1 Finding 3,
which found the original draft's "no existing file needs to change" framing false — the new fields
are inaccessible through today's types without them):**

1. **`frontend/app/lib/simulationApi.ts`** — the `ProtectionTimeline` TypeScript interface (mirroring
   `ProtectionTimelineModel` field-for-field, exactly as it does today) gains four new, additive,
   required fields: `trip_event_time_s: number | null`, `bus_collapse_event_time_s: number | null`,
   `coordination: CoordinationAnalysis`, `coverage: CoverageEntry[]` — plus two new exported
   interfaces, `CoordinationAnalysis` and `CoverageEntry` (and `EventSeparation`), mirroring the new
   backend dataclasses field-for-field, the same mirroring convention every existing type in this
   file already follows. No existing field of any existing interface in this file changes type or
   meaning.
2. **`frontend/app/components/ProtectionTimeline.tsx`** — `formatSeconds` (currently a module-private
   function, not exported) is extracted, unchanged, into a small shared helper module
   (`frontend/app/lib/formatSeconds.ts`, a single ~5-line pure function with no new dependency), and
   both `ProtectionTimeline.tsx` and the new `ProtectionCoordination.tsx` import it from there. This
   is the one required edit to this existing file; `formatSeconds`'s behavior and every other line of
   this file are unchanged — closing Codex Round 1 Finding 3's "reconcile the small change with the
   promise the existing component remains untouched" by naming the one minimal, mechanical move
   explicitly rather than claiming zero diff.
3. **`frontend/app/page.tsx`** — one new import and one new line rendering
   `<ProtectionCoordination timeline={data.protection_timeline} />` immediately after the existing
   `<ProtectionTimeline timeline={data.protection_timeline} />` call (§8, below). No other line of
   this file changes.

**New component: `frontend/app/components/ProtectionCoordination.tsx`.** Rendered immediately below
the existing `ProtectionTimeline` section, for every scenario, reading
`protection_timeline.coordination`/`.coverage`/`.trip_event_time_s`/`.bus_collapse_event_time_s`
from the already-fetched response.

**The frontend contract, precisely scoped (corrects Codex Round 1 Finding 9's "backend owns every
sentence" overstatement).** The rule that actually holds in `ProtectionTimeline.tsx` today, and that
`ProtectionCoordination.tsx` must follow identically, is narrower than "every sentence": **every
backend-derived engineering label/detail string** (`outcome_label`, `outcome_detail`,
`recovery_label` today; `result_label`, `result_detail`, each `CoverageEntry.detail` for SPEC-009)
is read verbatim, with zero enum-to-English translation or rewording performed client-side. This
explicitly **does not** cover, and never has covered: section headings (`"PROTECTION TIMELINE"`),
fixed static presentation text (the educational caption; an empty-events placeholder sentence), the
`"at least "`/`" (ongoing)"` segment-duration qualifiers, the `"RECOVERY: "` label prefix, or numeric
digit-formatting (`formatSeconds`) — all of which are, and remain, frontend-owned static/presentation
text today, exactly as `ProtectionTimeline.tsx`'s existing source already shows. `ProtectionCoordination.tsx`
may freely add its own static heading, its own empty-`separations`-list text (omitting the section
entirely, per §8 below — not even a placeholder sentence is needed), and its own ✓/✕ glyph
presentation around each `CoverageEntry` without violating this contract, because none of those is
an engineering label or detail string the backend computed.

Layout (compact, no duplication of what `ProtectionTimeline.tsx` already shows — rule G of the
governing prompt):

- **Coordination result** — one line, `result_label`, plus `result_detail` as supporting text
  (same visual weight as the existing `OutcomeBanner`, reusing the same status-role color mapping:
  `PROTECTION_ACTED_*` → `good`/`warning`-equivalent, `VIABILITY_LOST_*` → `critical`,
  `NO_TERMINAL_EVENT` → `neutral` — no new color role is introduced).
- **Event separation** — zero or more compact rows, one per `EventSeparation`, in the shared
  `label: duration_s` format using the extracted `formatSeconds` helper (§8 above — imported from
  `frontend/app/lib/formatSeconds.ts`, not reimplemented). Omitted entirely (not an empty
  placeholder row) when `separations` is empty.
- **Protection coverage** — a compact checklist, one row per `CoverageEntry`: a ✓/✕ glyph (text,
  not color-only, satisfying the same no-color-only-meaning rule SPEC-008 §14 already states) plus
  `function` and `detail`. This is the one place V1's coverage gaps are stated as a structured list
  rather than only in the existing free-text educational caption — it does not replace that caption,
  which stays exactly where SPEC-008 placed it.

**No duplication with `ProtectionTimeline.tsx`.** The existing segment bar, event list, and
outcome/recovery banner are untouched; this component adds exactly the three items above and nothing
a user could already read in the existing section.

**Responsive/accessibility:** inherits `ProtectionTimeline.tsx`'s existing patterns exactly
(semantic `<section>`, no color-only meaning, renders within the existing `sm`/`lg` breakpoints) —
no new breakpoint or interactive control is introduced, so no new keyboard-operability requirement
exists beyond what already applies to static content.

## 9. Acceptance Criteria

(Closes Codex Round 1 Finding 5 — replaces the prior placeholder-only verification prose with
numbered, checkable criteria. Numbering continues from SPEC-008's own AC-001–AC-026 to keep a single
unambiguous namespace across both specifications' shared `tests/` files, since SPEC-009 extends
rather than replaces SPEC-008's test files.)

- [ ] **AC-027 (new fields exposed, real scenarios):** For each of the five scenarios,
  `ProtectionTimeline.trip_event_time_s`/`.bus_collapse_event_time_s` match direct computation via
  `_first_true_time`/`_first_floor_contact_time` on that scenario's real telemetry (no synthetic
  fixtures) — specifically Thermal Trip: `trip_event_time_s ≈ 46.147`,
  `bus_collapse_event_time_s ≈ 14.446` (±float tolerance), consistent with SPEC-008's validation
  record and this specification's own Codex Round 1 direct-adapter-execution confirmation.
- [ ] **AC-028 (coordination classification, real scenarios):** Thermal Trip →
  `VIABILITY_LOST_BEFORE_PROTECTION_ACTION`, with `separations` containing **exactly two** entries
  (Codex Round 2 confirmed, by direct adapter execution, that Thermal Trip's real run satisfies
  both §6.1 guards simultaneously — derating begins at 11.718 s, strictly before the 14.446 s
  terminal event, so `derating_preceded_terminal_event is True` as well as both terminal-event
  times being non-`None` — so both separations are legitimately present, not a conflict to resolve
  by dropping either): exactly one `"Bus energy floor -> thermal trip"` entry with
  `duration_s ≈ 31.701`, and exactly one `"Derating begins -> terminal event"` entry with
  `duration_s ≈ 2.728` (both ±float tolerance). Load Step and Sustained High Load →
  `NO_TERMINAL_EVENT`, `separations == ()`. Grid Sag and Grid Loss →
  `VIABILITY_LOST_NO_PROTECTION_ACTION`, `separations == ()` for both (neither ever trips).
- [ ] **AC-029 (coordination classification, constructed fixtures — the only coverage for branches
  no real scenario reaches, per §0/§10):** fixtures covering `PROTECTION_ACTED_NO_VIABILITY_LOSS`
  (trip, bus never reaches the floor); `PROTECTION_ACTED_BEFORE_VIABILITY_LOSS` via strict
  inequality (trip strictly before a later floor contact); the exact-timestep tie (§6 case 3a),
  asserting its `result_detail` states "same recorded sample" and names the convention, and never
  contains the word "before"; its `EventSeparation` entry has `duration_s == 0.0` and the fixed
  tie-specific label, never a directional one.
- [ ] **AC-030 (`derating_preceded_terminal_event`, all four cases, §6.1):** fixtures/real-scenario
  checks covering: `None` via no terminal event at all (Load Step); `None` via a terminal event with
  no `DERATED` segment ever occurring (Grid Sag or Grid Loss, real); `True` via `DERATED` strictly
  preceding the terminal event (Thermal Trip, real: first `DERATED` at 11.718 s, terminal event at
  14.446 s); `False` via a constructed fixture where a bus-floor terminal event occurs at or before
  any `DERATED` segment's start.
- [ ] **AC-031 (`separations` never fabricated or negative):** for every fixture/real scenario in
  AC-028–AC-030, every `EventSeparation.duration_s >= 0`, and no `EventSeparation` entry exists for
  a scenario where its guarding condition (§6.1) is not met (e.g. no `"Derating begins -> terminal
  event"` entry for Grid Sag/Grid Loss, which never derate at all).
- [ ] **AC-032 (coverage matrix traceability):** `PROTECTION_COVERAGE`'s five entries are present
  and unchanged across all five scenario responses (static, run-independent, §5); the structural
  regression test (`len(OperatingState) == 3`, `step_protection` signature inspection) passes against
  the current `src/protection.py` and is documented as supplemental evidence only (§5), not a
  complete behavioral guarantee.
- [ ] **AC-033 (API schema/parity, §7):** the one authorized nested key-set literal
  (`tests/test_api.py:302`) gains exactly the four new key names and no other test assertion in
  `tests/test_api.py` changes; `_timeline_to_dict` (`tests/test_api.py:22`) is extended with the
  four new fields and both existing parity tests that call it continue to pass against the now-complete
  serialized shape; for each of the five scenario responses, the new fields match direct
  `build_protection_timeline` output for that same adapter call.
- [ ] **AC-034 (frontend type/contract fidelity, §8):** `simulationApi.ts`'s `ProtectionTimeline`
  interface and the three new interfaces compile and match the backend schema field-for-field;
  `formatSeconds` is extracted to `frontend/app/lib/formatSeconds.ts` with identical behavior, used
  by both `ProtectionTimeline.tsx` and `ProtectionCoordination.tsx`; `ProtectionCoordination.tsx`
  renders every backend-owned label/detail string verbatim (code-inspection verified, same method as
  SPEC-008 AC-011) while its own headings/empty-state/glyph text remain frontend-owned, per §8's
  precisely-scoped contract.
- [ ] **AC-035 (no `src/` change):** no file under `src/` appears in this feature's diff.
- [ ] **AC-036 (lint/typecheck/build):** `cd frontend && npm run lint && npm run typecheck && npm
  run build` pass with no new errors/warnings.
- [ ] **AC-037 (full-suite regression):** `python -m pytest -q` passes at the repository root.
- [ ] **AC-038 (validation record):** `docs/validation/SPEC-009-validation.md` is filed recording
  which criteria were checked, how, and the result — same requirement and format as SPEC-008 AC-026.

## 10. Verification Plan

**Deterministic (pytest) — the load-bearing evidence, same posture as SPEC-008 §17:**

- Extend `tests/test_protection_timeline.py` — AC-027, AC-028, AC-029, AC-030, AC-031, AC-032 (real
  scenarios, no synthetic fixtures, plus the constructed fixtures AC-029/AC-030 require for branches
  no real scenario reaches, reusing the existing `_make_config`/fixture-construction helpers already
  in this test file).
- Extend `tests/test_api.py` — AC-033.
- `git diff --stat -- src/` (or equivalent) showing no file under `src/` in the diff — AC-035, the
  same mechanical check SPEC-008 AC-005 used.
- `cd frontend && tsc --noEmit` (via `npm run typecheck`) on the extended `simulationApi.ts`
  interfaces, plus a direct code-read diff of `formatSeconds.ts`'s extracted body against
  `ProtectionTimeline.tsx`'s original inline function confirming byte-identical behavior, **plus an
  explicit field-by-field comparison of `simulationApi.ts`'s `ProtectionTimeline` interface and its
  three new interfaces (`CoordinationAnalysis`, `EventSeparation`, `CoverageEntry`) against
  `backend/schemas.py`'s `ProtectionTimelineModel` and its three new mirrored models — every field
  name, nullability (`float | None` ↔ `number | null`), and nested type matches, the same
  Python-dataclass-to-TypeScript-interface mirroring check SPEC-008's own types already require by
  precedent, just never previously written down as its own explicit step** — AC-034's
  type/formatter-fidelity half (the verbatim-rendering half of AC-034 is covered by the manual
  checklist below).
- `python -m pytest -q` at the repository root — AC-037.
- `cd frontend && npm run lint && npm run typecheck && npm run build` — AC-036.
- Filing `docs/validation/SPEC-009-validation.md` recording the above, the manual checklist below,
  and the Runtime Verification results — AC-038, reviewed for completeness before this
  specification is considered implemented (ENGINEERING.md's Definition of Done item 9).

**Manual verification checklist (Category C, same taxonomy as SPEC-008 §17):** performed once
against a running dev server, for all five scenarios: confirm the new Coordination section renders
below the existing Timeline section; confirm its wording matches the backend's `result_label`/
`result_detail`/coverage entries verbatim (code-inspection cross-check, same method SPEC-008 used
for AC-011); confirm event-separation rows are present only for Thermal Trip among the five real
scenarios and absent (not blank) for the other four; confirm the coverage checklist's ✕ rows are
never color-only (text glyph present); confirm mobile-width rendering has no horizontal overflow for
at least Thermal Trip (the one scenario with every optional sub-section populated).

**PEOS Runtime Verification — honest coverage, unchanged posture from SPEC-008 §18.** The fixed V1
catalog still cannot drive the scenario selector. The existing `page_load` check's `landmarks`
selector list gains one addition — `[data-testid='protection-coordination']` — covering only this
new section's static presence on the default-loaded (Load Step) page, exactly as narrow as SPEC-008
§18's existing coverage of `protection-timeline`/`outcome-banner`. No claim of per-scenario or
interactive coverage is made.

    runtime: page_load path=/ landmarks="[data-testid='scenario-select'],[data-testid='protection-timeline'],[data-testid='outcome-banner'],[data-testid='protection-coordination']" ac=AC-034
    runtime: viewport_overflow viewport=desktop ac=AC-036
    runtime: viewport_overflow viewport=mobile ac=AC-036

**Frontend automated tests — honestly not available, same reasoning as SPEC-008 §17.** No test
runner exists in this repository; adding one is outside this specification's authority. Behavioral
correctness is concentrated in the backend module's pytest suite, consistent with SPEC-008 AC-014's
existing prohibition on frontend-side classification (unchanged, inherited by this specification).

## 11. Known Limitations (carried from SPEC-008 §20, extended)

- Every limitation SPEC-008 §20 already states carries over unchanged (no bus-voltage protection;
  binary `recovery`; no real scenario exercises `PROTECTION_TRIP`; no PEOS interactive coverage; no
  frontend test runner; no scenario-selection persistence).
- **`CoordinationResult`'s `PROTECTION_ACTED_*` branches are, like SPEC-008's `PROTECTION_TRIP`
  outcome, unreachable by any of today's five scenario presets' fixed defaults** — covered only by
  constructed fixtures (§9). Only `NO_TERMINAL_EVENT` (Load Step, Sustained High Load) and
  `VIABILITY_LOST_*` (Thermal Trip, Grid Sag, Grid Loss) are exercised end-to-end by real scenarios.
- **The coverage matrix (§5) is a snapshot of `src/protection.py`'s current implementation, only
  partially tied to it by one structural regression test (§5/AC-032)** — that test detects a new
  voltage/current/grid-availability *parameter* appearing, but, as Codex Round 1 Finding 6
  established, cannot detect every possible future *behavioral* change (e.g. new logic added inside
  the existing `TRIPPED` branch) — §5 states this precisely rather than overclaiming a complete
  guarantee; the two behavioral claims instead rest on three existing named tests in
  `tests/test_protection.py` (§5).
- **"Coordination" is a statement about recorded-time ordering only, never a causal claim.** This
  specification adds no new causal-inference capability beyond what SPEC-008 §9 already carefully
  avoided claiming; §6 only orders two existing optional timestamps, and §6's tied case (3a) is
  worded specifically to avoid implying precedence where none is established.

## 12. Open Items for Human Gate Disposition

Per the governing prompt's instruction to identify genuine Human Gates only where product/engineering
judgment cannot legitimately be resolved from repository evidence — this investigation found none
that rise to that bar. The two candidate questions below were considered and resolved by direct
reference to existing, binding precedent, not guessed:

1. **Whether Protection Coordination is universal (all five scenarios) or Scenario-B–E-only, like
   some of SPEC-008's Scenario-A-only sections.** Resolved without a gate: SPEC-008 §12 already
   establishes the Protection Timeline itself (which Coordination directly extends) as universal
   ("Universal across all five scenarios... the new Protection Timeline section"), and the
   governing prompt's own desired-output example renders Coordination for Thermal Trip using exactly
   the same Timeline the universal section already shows for every scenario. Making Coordination
   Scenario-B–E-only while its parent section is universal would be an unexplained, inconsistent
   split with no stated rationale — so §8 keeps it universal, consistent with its parent.
2. **Whether the coverage matrix is attached per-run (on `ProtectionTimeline`) or exposed as a
   separate, config-level, cacheable resource.** Resolved without a gate: it is static and
   relatively small (5 rows of short strings), the existing architecture has no precedent for a
   separate "static facts" endpoint, and SPEC-008 §11 explicitly endorses minimizing endpoint count
   over endpoint purity ("four separate endpoints are not mandated — choose and justify the
   smallest... shape"). Attaching it to the existing, already-serialized `ProtectionTimeline` is the
   smaller shape; §7 adopts it.

If Codex review surfaces a question this investigation did not anticipate that genuinely cannot be
resolved from repository evidence, it will be reported here by name rather than resolved by guess.

## 13. Outstanding Findings Register — Final Disposition (all 9 Round 1 + 2 Round 2 + 1 Round 4 findings)

| # | Severity | Finding (condensed) | Disposition |
|---|---|---|---|
| 1 | Major | `derating_preceded_trip` had no consistent comparison target or defined `False` case. | **CLOSED** in v0.2 — renamed `derating_preceded_terminal_event`; comparison target fixed to `outcome_event_time_s`; all four cases (`None` via no terminal event, `None` via no `DERATED` segment, `True`, `False`) explicitly defined (§6.1). Independently re-confirmed `CLOSED` by Round 2. |
| 2 | Major | The derating-separation interval could be negative (floor before later derating). | **CLOSED** in v0.2 — the interval is now included only when `derating_preceded_terminal_event is True`, which by construction guarantees a strictly positive duration (§6.1). Independently re-confirmed `CLOSED` by Round 2. |
| 3 | Major | Required frontend integration changes (types in `simulationApi.ts`, `formatSeconds` export) were omitted while claiming the existing component stays untouched. | **CLOSED** in v0.2 — §8 now names the three required file-level changes explicitly (additive `simulationApi.ts` types; `formatSeconds` extraction to a shared helper; one new `page.tsx` render line), each described as the smallest change that makes the claim true rather than claiming zero diff. Independently re-confirmed `CLOSED` by Round 2. |
| 4 | Major | "Existing key-set tests are unaffected" was false — the nested `protection_timeline` key-set literal and the `_timeline_to_dict` helper both require updating. | **CLOSED** in v0.2 — §7 now explicitly authorizes updating exactly the one nested key-set literal (`tests/test_api.py:302`) and the `_timeline_to_dict` helper, naming both by file/line, and nothing else in that test file. Independently re-confirmed `CLOSED` by Round 2. |
| 5 | Major | No concrete, numbered acceptance criteria existed; `AC-01x` was an unresolved placeholder; no validation-record requirement was stated. | **CLOSED** in v0.2 — §9 adds AC-027 through AC-038 (numbered to continue SPEC-008's namespace), each mapped to §10's verification plan; AC-038 requires filing `docs/validation/SPEC-009-validation.md`. Independently re-confirmed `CLOSED` by Round 2 (which also surfaced the §10-mapping gap recorded as R2-2 below). |
| 6 | Major | The proposed structural coverage test cannot detect every possible future protection-behavior change (e.g. new logic inside the existing `TRIPPED` branch). | **CLOSED** in v0.2 for the narrowing itself, but Round 2 found v0.2's behavioral-test citation (`tests/test_thermal_protection_simulation.py`) does not actually assert the claimed debounce/latching behavior — **STILL_OUTSTANDING** after v0.2. **CLOSED** in v0.3 — §5/§11 now cite the three tests that actually do: `tests/test_protection.py::test_trip_after_sustained_overtemperature`/`::test_no_false_trip_from_short_transient`/`::test_trip_is_latched_even_after_temperature_recovers` (confirmed present at lines 55/67/91). |
| 7 | Minor | Timestamp computation was misattributed to `_classify_outcome`; floor-tolerance reuse was understated. | **CLOSED** in v0.2 for §0, but Round 2 found §3's Scope bullet still called the timestamps "the two candidate times `_classify_outcome` already computes" — **STILL_OUTSTANDING** after v0.2. **CLOSED** in v0.3 — §3 corrected to attribute computation to `build_protection_timeline` via `_first_true_time`/`_first_floor_contact_time`, matching §0's existing correct wording. |
| 8 | Minor | A tied result's `*_BEFORE_*` enum name plus a directional sentence could assert false temporal precedence. | **CLOSED** in v0.2 — §6 case 3a and §6.1's tied-case rule require dedicated "same recorded sample" wording and a zero-duration, non-directional `EventSeparation` label for the tied case specifically; AC-029 tests the detail string never contains "before" in this case. Independently re-confirmed `CLOSED` by Round 2. |
| 9 | Minor | "Backend owns every sentence" overstated the actual frontend contract (headings, captions, formatting are legitimately frontend-owned today). | **CLOSED** in v0.2 for §8, but Round 2 found §0's frontend-inspection paragraph still said "the backend must own every sentence," contradicting §8's own corrected, narrower wording — **STILL_OUTSTANDING** after v0.2. **CLOSED** in v0.3 — §0 reworded to match §8's precise "every backend-derived engineering label/detail string" contract, with the frontend-owned carve-outs stated consistently in both places. |
| R2-1 (new) | Major | Round 2 found v0.2's own rewrite introduced a real contradiction: AC-028 required "exactly one" separation entry for Thermal Trip, but §6.1's own rules — confirmed by direct adapter execution — produce **two** legitimate entries for Thermal Trip's real run (derating begins at 11.718 s, strictly before the 14.446 s terminal event, in addition to the bus-floor/trip pair at 31.701 s apart). | **CLOSED** in v0.3 — AC-028 rewritten to require exactly two named entries for Thermal Trip (the `"Bus energy floor -> thermal trip"` entry at ≈31.701 s and the `"Derating begins -> terminal event"` entry at ≈2.728 s), with the reasoning stated explicitly so the two guards' simultaneous satisfaction is documented as expected, not an error. |
| R2-2 (new) | Minor | Round 2 found §10's verification-plan mapping incomplete: no concrete check was named for AC-034's schema/type/formatter-fidelity half, AC-035's diff check, or AC-038's validation-record review. | **CLOSED** in v0.3 for the diff and validation-record checks, but Round 3 found the AC-034 check still incomplete: `tsc --noEmit` verifies internal TypeScript consistency but establishes no agreement with the Python backend schemas it is supposed to mirror — **STILL_OUTSTANDING** after v0.3. **CLOSED** in v0.4 — §10 now also names an explicit field-by-field comparison of `simulationApi.ts`'s four new/extended interfaces against `backend/schemas.py`'s mirrored models (field names, nullability, nested types). Independently re-confirmed `CLOSED` by Round 4. |
| R4-1 (new) | Minor | Round 4's end-to-end scan found §5 cited "AC-013/AC-014" (SPEC-008's criterion numbers, not this specification's own AC-027–AC-038 namespace) where it meant the actual coverage-tracing criterion. | **CLOSED** in v0.5 — §5's citation corrected to "AC-032," matching §11's already-correct citation of the same criterion. |

Zero findings remain open at `blocking` or `major` severity. All `minor` findings are closed. A
Round 2 focused closure review of v0.2 independently re-confirmed 6 of the 9 Round 1 closures and
found 3 only partially closed (residual stale wording elsewhere in the document, and one mis-cited
test file) plus 2 new issues in v0.2's own rewrite — v0.3 closed 4 of those 5 and left R2-2 only
partially closed. A Round 3 focused closure review of v0.3 — scoped only to those 5 items —
independently re-confirmed 4 **CLOSED** (Round 1 #6/#7/#9, Round 2's R2-1) and found R2-2 only
partially closed (the AC-034 check verified internal TypeScript consistency but not agreement with
the backend schema), with no new defect introduced. v0.4 closed R2-2 completely. A Round 4 focused
closure review of v0.4 — scoped only to R2-2 plus one end-to-end scan for any other remaining
placeholder/inconsistency — confirmed R2-2 `CLOSED` and found one new, unrelated minor citation
error (R4-1). v0.5 fixes it. All 9 Round 1 findings, both Round 2 findings, and the one Round 4
finding are now `CLOSED`, independently re-confirmed by at least one subsequent focused closure
round each. A final Round 5 confirmation review of v0.5 (scoped only to R4-1's closure plus one
end-to-end sanity pass: no remaining placeholder text, consistent `##` numbering 0–13, no
contradiction in this register) returned **`APPROVE`**, **0 blocking / 0 major / 0 minor open
across the full review history**, and confirmed SPEC-009 v0.5 is implementation-ready per PEOS's
Architecture Convergence Requirement.
subsequent focused closure round each.
