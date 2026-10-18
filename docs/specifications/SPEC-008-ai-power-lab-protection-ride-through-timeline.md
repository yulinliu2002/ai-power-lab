# SPEC-008 — AI Power Lab Protection & Ride-Through Timeline

> **Historical document:** PEOS is retired (git tag `pre-peos-retirement`). References to PEOS execution below describe the process at the time of writing; requirement text is unchanged.

**Status:** Draft
**Project:** AI Power Lab
**System:** `dashboard/adapters/` (new derived-data module), `backend/` (one new endpoint/schema
extension), `frontend/app/` (new scenario selector + Protection Timeline presentation). No change
to `src/` (simulation physics) is in scope or required.
**Version:** 0.5 (0.1 returned Codex `CHANGES_REQUIRED` with 3 blocking/8 major/1 minor finding;
0.2 closed the 3 blocking findings only, per that round's governing instructions, and left the 8
major/1 minor findings open in an Outstanding Findings Register. The Human Engineering Lead
reviewed 0.2 and ruled that "zero blockers" is too weak a convergence bar, directed remediation of
**all 12** Round 1 findings, and made seven product/architecture decisions — see "Engineering Lead
Decisions" below. 0.3 implemented all seven decisions and redispositioned every one of the 12
findings. A focused Round 2 Codex closure review of 0.3 independently re-ran all five default
scenarios, confirmed every real-scenario outcome/recovery pair in §0's table, confirmed the single
new endpoint is consistent with `backend/app.py`'s existing patterns, confirmed `recovery`
correctly ports `transientMetrics.ts`'s existing settling-band logic, and returned
`CHANGES_REQUIRED` with 2 new/residual `major` and 2 `minor` findings — all 11 of Round 1's
blocking/major findings it re-checked were confirmed closed. 0.4 closed all 4 Round 2 findings. A
focused Round 3 Codex closure review of 0.4 — scoped only to those 4 closures plus the unlisted
excursion-metadata gap Round 2 named in its "Repository checks" prose, independently re-tracing
`src/simulation.py`'s step order and re-running the default adapters — confirmed all 5 **CLOSED**
and found no new defect, returning **`APPROVE`** with 0 blocking/0 major/0 minor open. This
revision (0.5) records that Round 3 result; no spec text changed as a result of Round 3 beyond
this record — see "Codex Architecture/Specification Review — Round 3" and §21.)
**Type:** Software Component (presentation/derived-data layer over existing scenarios; no new
engineering model)

---

This specification is a PEOS dogfood artifact: it is the product of inspecting the repository's
existing protection/telemetry/scenario/API/frontend capability (§0 below) before proposing any
new architecture, per `ENGINEERING.md`. It extends, and in one place (§13.1) explicitly revises a
Non-Goal of, the approved `SPEC-005-ai-power-lab-engineering-narrative.md`. Per that document's
own §17 ("Future slices require either a revision to this specification or a new SPEC document
that explicitly extends it"), SPEC-008 is written as that explicit extension, not a silent
override.

## Codex Architecture/Specification Review — Round 1

An independent Codex architecture/specification review of SPEC-008 v0.1 (standalone, read-only,
`codex exec --sandbox read-only`, against this repository's actual code, `CLAUDE.md`,
`ENGINEERING.md`, `AGENTS.md`, SPEC-005, and SPEC-006) returned **`CHANGES_REQUIRED`** with 3
`blocking`, 8 `major`, and 1 `minor` (multi-part) finding. v0.2 closed the 3 blocking findings
only.

## Codex Architecture/Specification Review — Round 2

A focused closure review of v0.3 (same standalone, read-only posture; explicitly scoped to
auditing §21's claimed disposition of all 12 Round 1 findings against v0.3's actual text, not a
fresh broad review) independently re-ran all five default adapter scenarios directly and confirmed
every outcome/recovery pair now in §0's table, confirmed the single new endpoint is consistent
with `backend/app.py`'s existing patterns (`GET` already permitted, dispatch through existing
adapters, typed serialization matching the current boundary), and confirmed `recovery` correctly
reuses `transientMetrics.ts`'s existing ±1% settling-band logic rather than inventing a new
threshold. It confirmed 11 of Round 1's 12 findings (1–11) `CLOSED` as drafted, found finding 12
(wording/references) **not fully closed** as claimed, and raised one **new** issue v0.3's own
rewrite introduced. Final tally: `CHANGES_REQUIRED`, 2 `major` (one residual from finding 12, one
new), 2 `minor` (both residual from finding 12).

| # | Severity | Finding (condensed) | Closed in |
|---|---|---|---|
| New | Major | §9's same-sample tie-break justified `PROTECTION_TRIP` precedence by claiming the trip "forces `derate_factor` to `0.0` within that same step," but `src/simulation.py`'s actual order integrates a step's electrical state (using the *previous* step's `derate_factor`) **before** that step's protection evaluation — so a same-sample coincidence reflects two independently-true conditions, never one causing the other. | §9's tie-break rule rewritten to state it is an explicit, arbitrary, non-causal convention, with the real step-order explanation of why no causal claim holds. |
| 12 (residual) | Minor | §0 claimed `recovery` distinguishes "Grid Sag's and Thermal Trip's" outcome from Grid Loss's — re-running the scenarios shows Thermal Trip and Grid Loss both end `NOT_RECOVERED`; only Grid Sag differs. | §0's note rewritten to state the real result (Thermal Trip and Grid Loss share an identical outcome/recovery pair; only Grid Sag's `recovery` differs), and the Thermal Trip table row now states its `recovery` value explicitly. |
| 12 (residual) | Minor | The opening paragraph pointed to "§1–§4" for the repository-inspection findings, which actually live in §0; §17 attributed a "Category C" taxonomy to `ENGINEERING.md`, which has no such taxonomy (that is SPEC-006 §6's). | Both cross-references corrected. |
| New | Major | §13.1 still said "This is a Human Gate (§15 item 1)," stale text left over from v0.2's "Open Decisions" framing — but v0.3's rewritten §15 lists this exact SPEC-005-supersession question under "Resolved by the Human Engineering Lead" (Decision 1), and its own "Still open" item 1 is a different question (hiding vs. adapting Scenario-A-only sections). The two sections contradicted each other about whether this item was still blocking approval. | §13.1's stale sentence replaced with a statement that this is resolved (Decision 1), pointing to §15's actual two open items. |

Round 1's findings 1–11 were independently re-confirmed `CLOSED` in this round, including by direct
re-execution of the real scenarios — see "Repository checks" in the review transcript for the exact
rerun table, which matches §0's table here exactly. v0.4 closes all 4 Round 2 findings — see §21
for the complete, final disposition of all original 12 findings plus these 4.

## Codex Architecture/Specification Review — Round 3

A focused closure review of v0.4 (same standalone, read-only posture; explicitly scoped to
auditing only the 4 Round 2 findings' closure plus the unlisted excursion-metadata gap Round 2
named in its "Repository checks" prose — not a fresh broad review, and not a re-check of Round 1's
findings 1–11, already twice confirmed closed) independently re-traced `src/simulation.py`'s
per-step integration order against §9's rewritten tie-break rule, re-ran the default adapters to
confirm §0's Thermal-Trip/Grid-Loss/Grid-Sag recovery values (final voltages 10 V / 10 V / 799.521
V; Thermal Trip's floor contact at 14.446 s precedes its trip at 46.147 s), and checked the two
cross-reference fixes, the §13.1/§15 consistency fix, and the §8/§10 excursion-metadata scoping.
All 5 items were confirmed **CLOSED**, with no new defect introduced by any of v0.4's edits. Final
verdict: **`APPROVE`**, 0 blocking / 0 major / 0 minor open.

## Engineering Lead Decisions (govern this revision)

Following Round 1, the Human Engineering Lead reviewed v0.2 and directed a full remediation of
all 12 findings (not only the 3 former blockers) plus these seven decisions, which this revision
implements:

1. **SPEC-005 relationship.** Additive extension only; must state precisely what is inherited vs.
   added, never silently weakening/replacing/contradicting an unrelated SPEC-005 criterion. (§13,
   tightened.)
2. **Outcome taxonomy.** The three outcomes (`RIDE_THROUGH` / `PROTECTION_TRIP` /
   `BUS_COLLAPSE_UNPROTECTED`) are approved, but must be classified by **ordered terminal events** —
   whichever of (first `trip_active=True` sample, first bus-energy-floor sample) occurs earlier in
   simulated time — never by final-state inspection alone. A later trip never retroactively hides
   an earlier unprotected collapse. `BUS_COLLAPSE_UNPROTECTED` must be explained in the UI as an
   educational V1-model result, never implied to be how a real SST would necessarily behave. **This
   reverses v0.2's §9 precedence rule** — see §9.
3. **Ride-through vs. recovery.** Remove v0.2's margin-based `RIDE_THROUGH` test entirely; the
   three-way `outcome` is driven only by Decision 2's ordered-event rule. A separate, descriptive
   `recovery` field may report whether the bus returned to nominal, reusing an existing
   repository-authoritative tolerance if one exists, never inventing a new one for presentation.
4. **Protection state vs. derived events.** `RUNNING`/`DERATED`/`TRIPPED` remain the sole
   authoritative output of `src/protection.py`; a bus-energy-floor event is a derived observation
   of existing telemetry/numerical-floor data, never presented as something `src/protection.py`
   itself generated.
5. **Scenario scope.** Expose the scenarios needed to make the analysis meaningful (not Load Step
   alone), but four separate endpoints are not mandated — choose and justify the smallest
   backend/API shape consistent with the existing architecture. (§11 now has one new endpoint.)
6. **Scenario parameters.** Fixed presets only; no sliders or runtime parameter controls for this
   feature.
7. **Runtime Verification capability gap.** Do not modify PEOS to work around `experiment_run`'s
   inability to drive the scenario selector; record the gap; use the strongest verification
   actually available (deterministic Python/API tests, frontend tests where appropriate,
   `page_load`, `viewport_overflow`, any other genuinely-applicable existing runtime check) without
   ever claiming browser coverage the catalog cannot provide.

## 0. What Already Exists (repository inspection findings)

This section is evidence, not a requirement — it records exactly what was found before any new
architecture was proposed, per the dogfood brief's inspection steps 1–6.

**Protection/state machine (`src/protection.py`).** V1 protection is a three-state machine driven
by a single lumped SST temperature: `RUNNING` → `DERATED` → `TRIPPED`. `TRIPPED` is latched (no
reset in V1) and debounced (`thermal_trip_time_s`, default 2.0 s). Derating is a documented linear
ramp between `thermal_derate_start_c` (70 °C) and `thermal_trip_c` (100 °C), floor
`derate_factor_min` (0.5). **There is no DC-bus voltage protection in V1** — an explicitly
documented Limitation in `src/protection.py`'s own module docstring, not a gap this specification
discovers. §9 is built around that fact, not around changing it.

**Telemetry (`src/telemetry.py`).** Every run already produces, per timestep: `operating_state`,
`trip_active`, `trip_reason` (`""` if none), `derate_factor`, `temperature_c`, `v_dc_v`,
`grid_voltage_pu`, `grid_available`, and the power series — a complete, per-sample record of
every input this feature needs. No new physics output is required.

**Simulation causality (`src/simulation.py`).** Protection is evaluated once per step, after
thermal integration, with a documented one-step lag. This specification reads that behavior; it
does not change it.

**Scenarios, their terminal events, and their outcome under §9's ordered-event rule.** Five
scenarios exist today (`scenarios/*.py`, `dashboard/adapters/simulation_adapter.py`):

| Scenario (adapter fn) | Reaches `DERATED`/`TRIPPED`? | First terminal event (§9) | Outcome (§9) |
|---|---|---|---|
| `run_load_step` (A) | No (`test_short_scenario_a_duration_never_leaves_running`) | None expected — this specification's own tests (§16, AC-001) must *confirm* `v_dc_v` never reaches the numerical floor during Scenario A's mild transient, not assume it | `RIDE_THROUGH` (pending that confirmation) |
| `run_sustained_high_load` (B) | `DERATED` only, never `TRIPPED` | None — demand never exceeds available derated power, so the bus never approaches the floor | `RIDE_THROUGH` |
| `run_thermal_trip` (C) | `DERATED` then `TRIPPED` | Bus-energy-floor entry at ~14.4 s — **before** `trip_active` first becomes `True` at ~46.1 s (confirmed by running the adapter's own default parameters directly) | `BUS_COLLAPSE_UNPROTECTED`, `recovery=NOT_RECOVERED` — the later `TRIPPED` transition (~46.1 s) remains visible as its own `protection_state` timeline event; it does not retroactively change the outcome (Engineering Lead Decision 2) |
| `run_grid_sag` (D) | Stays `RUNNING` (sag too brief to raise temperature) | Bus-energy-floor entry partway through the sag (the scenario's own module docstring: "the bus briefly touches the NUMERICAL FLOOR... partway through the sag") — never trips | `BUS_COLLAPSE_UNPROTECTED`, `recovery=RECOVERED` — V1 provided no active protection for this excursion; it happened to resolve once the external grid sag ended |
| `run_grid_loss` (E) | Stays `RUNNING` (no grid-loss logic exists) | Bus-energy-floor entry, never exits, never trips | `BUS_COLLAPSE_UNPROTECTED`, `recovery=NOT_RECOVERED` |

**Note (honesty, not a defect):** under the ordered-event rule, three of these five scenarios —
not only Grid Loss — register `BUS_COLLAPSE_UNPROTECTED`, because V1 has no active bus-voltage
protection at all. `recovery` is what then distinguishes between them: Grid Sag is the only one of
the three with `recovery=RECOVERED`; Thermal Trip and Grid Loss both end `NOT_RECOVERED`
(confirmed by directly re-running all five default scenarios — this is not a coincidence this
specification glosses over: Thermal Trip and Grid Loss share an *identical* `outcome`/`recovery`
pair, and are distinguished only by Thermal Trip's event list additionally showing a later
`TRIPPED` transition that Grid Loss's never does). This is intentional per Engineering Lead
Decision 2/3 — it is a more honest classification than a margin-based "did it end near nominal"
test, which is exactly why it was chosen over v0.2's rule. **A second honesty note:** none of the five scenarios' fixed default
parameters ever produces `outcome=PROTECTION_TRIP` under this rule (Scenario C's trip always
arrives after its own earlier floor contact). `PROTECTION_TRIP` is a real, reachable code path, but
it is reachable only via a constructed test fixture (§16, AC-019), not via any of this repository's
existing scenario presets — stated explicitly here rather than glossed over.

Scenario A is excluded from this feature's core demonstration subject (§1, §9): its own protection
timeline is expected to be a single, uninteresting segment. It is not excluded from the
implementation diff — §3/§11 still attach the same additive field to its response, for
presentation uniformity. Scenarios B–E are the feature's actual subject.

**Backend/API (`backend/app.py`, `backend/schemas.py`).** Only Scenario A is wired to HTTP today
(`POST /api/v1/simulations/load-step`). Scenarios B–E exist in the adapter and in `scenarios/*.py`
but have no API surface. `backend/app.py`'s own docstring states the boundary this feature must
keep: "no physics and no derived-physics computation... a thin translation." Existing precedent
for *some* derived-event computation already living in Python, not the frontend:
`simulation_adapter.run_thermal_trip` already computes `events` (derating-begins, TRIPPED markers)
by scanning `derate_factor`/`trip_active` for their first `True` index.

**Frontend (`frontend/app/`).** `page.tsx` is hardwired to one scenario with no selector.
`transientMetrics.ts` already establishes that *reduction* over an already-fetched telemetry
series (min/max scan, a %-band recovery-time scan) is accepted frontend-side presentation logic,
provided it performs no numerical integration and recomputes no physical quantity — this precedent
bears on §11's extraction-location decision, and §9's `recovery` field reuses this exact ±1%
settling-band convention rather than inventing one. No component has a `data-testid` attribute
anywhere in the codebase today. `frontend/package.json` has **no test runner installed** (no
Jest/Vitest/`@testing-library/*`) — relevant to §17's honest accounting of Engineering Lead
Decision 7's "frontend tests where appropriate."

**PEOS Runtime Verification (`peos/runtime_catalog.py`, SPEC-006).** The fixed V1 catalog has
exactly three check kinds: `page_load`, `viewport_overflow`, `experiment_run`. `experiment_run` is
hardcoded to one interaction shape (numeric control → submit → observe change), built for
`ExperimentPanel.tsx`'s slider. It cannot express "select scenario X from a set of options, then
assert on the resulting Timeline's content." This is a genuine PEOS capability gap, reported in
§19 — Engineering Lead Decision 7 explicitly directs that PEOS not be modified to close it.

## 1. Purpose

Teach a user, for any of Scenario B–E, how the system's protection state changed over the run,
**whether it rode through the disturbance cleanly, whether thermal protection tripped it, or
whether the bus's energy buffer was exhausted before protection ever acted**, exactly what
threshold or condition caused each event, and how long each state lasted — using only values the
simulation engine already produced, presented as a clear, structured, inspectable timeline rather
than a dashboard animation.

## 2. Engineering Question

Given a telemetry record that already contains `operating_state`, `trip_active`, `trip_reason`,
`temperature_c`, and `v_dc_v` at every timestep, what is the smallest, most honest transformation
of that record into a small number of meaningful, explainable timeline events and a single
outcome classification — one that does not silently paper over the documented fact that V1
protection has no bus-voltage trip, and does not let a later event retroactively hide an earlier
one?

## 3. Scope

- A new, pure derived-data Python module computing, from an already-run `Telemetry` + `Config`:
  contiguous protection-state segments with duration (§8); a merged, reconciled, chronological list
  of protection-state/input/bus-energy timeline events with plain-language, config-traceable causes
  (§8, §11); and a three-way outcome classification plus a separate recovery classification (§9).
- One new FastAPI endpoint exposing Scenarios B–E (currently adapter-only), returning this derived
  data alongside the existing telemetry/thresholds/events shape (§11).
- An additive `protection_timeline` field on the existing `LoadStepResponse` (Scenario A), for
  presentation uniformity only (§11) — `backend/schemas.py`'s existing fields are unchanged.
- A new scenario-selection control and a new Protection Timeline presentation component, including
  a universal educational-model caption, in the existing single-page frontend (§12).
- Deterministic (pytest), manual, and Runtime Verification plans (§16–§19).

## 4. Out of Scope

- Any change to `src/` — no new physics, no bus-voltage protection state machine, no change to
  debounce/derating/trip logic or their governing equations. §9's outcome classification is a
  **presentation-layer label over existing output**, never a new protection feature.
- New scenario *types* (new fault physics). Only Scenarios B–E, which already exist.
- Parameter experimentation (`ExperimentPanel`/`SensitivityStudy`-style sliders) for Scenarios B–E
  (Engineering Lead Decision 6). V1 of this feature runs each with its existing adapter defaults
  only.
- Any change to Scenario A's own narrative beyond conditionally showing/computing it only when
  Scenario A is selected (§12, §13.3).
- Cross-scenario comparison views, URL/localStorage persistence of the selected scenario.
- Any PEOS (`peos/`) code change (Engineering Lead Decision 7). §19 reports a capability gap; it
  does not propose fixing it here.
- Adding a frontend test framework/runner (none exists today, §0) — out of this specification's
  authority per `CLAUDE.md`'s "no additional framework... not clearly necessary" rule.
- Anything outside `CLAUDE.md`'s V1 chain (Grid → SST → 800 VDC bus → AI load).

## 5. User Experience

A user already looking at the existing single-page console (Scenario A by default) gets a new way
to ask "what if the disturbance were worse than a load step?" — five named scenario options next
to the existing header. Choosing one re-runs the console against that scenario's telemetry and
adds one new section, the **Protection Timeline**, which answers, for that specific run, without
the user doing any arithmetic:

1. What sequence of protection states did the system pass through, and when?
2. What caused each event — which measured value crossed which configured threshold, or which
   numerical safeguard was reached?
3. How long did the system spend in each state?
4. Did the system ride through the disturbance cleanly, did thermal protection trip it, or did the
   bus's energy buffer run out before protection ever acted — and, in that last case, did the bus
   recover afterward or not?

This is read-only, whole-run analysis, not a live per-instant readout — it does not need to track
the time scrubber.

## 6. Engineering Semantics

The feature narrates exactly the causal chain `src/simulation.py` already documents:

> disturbance (load/grid input) → SST loss/temperature response → protection state evaluation
> (after thermal integration, one-step lag) → derate/trip decision → available power change →
> electrical consequence (bus voltage).

Every "cause" the Timeline states is one of exactly three kinds, all already authoritative:

- **A config threshold crossing**: a telemetry value crossed a value already present in that
  run's `Config` (e.g., `temperature_c` crossed `protection.thermal_derate_start_c`).
- **A debounce condition being satisfied**: `trip_active` became `True` because
  `protection.thermal_trip_time_s` elapsed while `temperature_c >= protection.thermal_trip_c` (the
  condition `src/protection.py` already implements; this feature states it, never re-derives it).
- **A numerical-safeguard contact**: `v_dc_v` crossed the bus-floor voltage already derivable from
  `config.dc_bus.min_energy_j`/`capacitance_f` (§7) — observation of an existing numerical
  safeguard, never presented as a `src/protection.py`-generated protection action (Engineering Lead
  Decision 4).

No cause is ever inferred from a chart's visual shape — every stated cause is a lookup against
telemetry/config fields, in Python, before any HTTP response is built (§8, §11).

## 7. Data Provenance

| Displayed value | Source | New computation? |
|---|---|---|
| State segment boundaries/durations | `telemetry.operating_state`, `telemetry.time_s` | Index scan only (run-length encoding) — no physics |
| Transition cause text | `telemetry.temperature_c`/`trip_active` + `config.protection.*` | Lookup + string formatting only |
| Trip reason | `telemetry.trip_reason` (already produced by `src/protection.py`) | None — read verbatim |
| Grid/load input events (e.g. "grid lost") | Reconciled subset of the adapter's existing `events` (§11) | None — already existing, merged in after filtering out protection-derived duplicates |
| Bus-floor voltage | `voltage_from_energy(config.dc_bus.min_energy_j, config.dc_bus.capacitance_f)` | No new equation — a direct call to the existing pure function `src/dc_bus.py` already exports, evaluated the same way `scenarios/plotting.py:floor_voltage` already does |
| `outcome` (3-way) | Ordered comparison of first `trip_active=True` time vs. first bus-floor-contact time | Classification logic only (§9) — no new physical quantity |
| `recovery` (separate from `outcome`) | `v_dc_v` vs. `±1% * voltage_reference_v`, ported from `transientMetrics.ts`'s existing settling-band scan | Reuse of an existing, repository-authoritative tolerance (§9) — not a new threshold |

No value in this feature is a numerical integral, a re-simulation, or an approximation of
anything `src/` already computes exactly.

## 8. State-Transition Extraction Rules

**Rule: run-length-encode `operating_state`, do not surface every raw sample.** A **segment** is a
maximal run of consecutive samples sharing the same `operating_state` value. A **transition event**
exists only at a segment boundary, never mid-segment. `thermal_trip_time_s`'s debounce prevents
flicker specifically at the `TRIPPED` transition; the `RUNNING`↔`DERATED` transition has no
debounce or hysteresis at all, so flicker there is in principle possible for a non-monotonic
temperature trajectory — none of Scenarios B–E's existing trajectories are non-monotonic enough to
produce it, but the extraction rule is general and handles it correctly (RLE naturally emits
however many segments actually occur) if it ever does (§16, AC-019 tests this directly with a
constructed `RUNNING`→`DERATED`→`RUNNING`→`DERATED`→`TRIPPED` fixture).

**Rule: reconcile, never blindly merge, the adapter's existing `events` list (closes Codex Round 1
Finding 4).** An adapter-provided `EventMarker` is a genuine input event only if it is independent
of `operating_state`/`derate_factor`/`trip_active` — i.e., it reflects a load or grid input
condition, not a protection output this module already, and more precisely, derives itself. §11
states exactly which of the five scenarios' adapter-provided markers qualify.

**Rule: a bus-energy-floor event type, one entry/exit pair per contiguous excursion (not capped at
one overall — closes the "one event pair" ambiguity Codex Round 1 Finding 10 flagged).** Because
V1 has no voltage protection, a bus collapse to the numerical floor produces **no**
`operating_state` change at all. This feature therefore also detects entry/exit of `v_dc_v`
at-or-below the existing bus-floor voltage (§7) as its own `category="bus_energy"` `TimelineEvent`
pair ("bus energy at numerical floor" / "bus energy recovers"), using the exact tolerance
`scenarios/plotting.py` already uses (`<= floor_v + 0.5`). If the bus touches and leaves the floor
more than once in a run, each contiguous excursion produces its own entry/exit pair — the rule is a
general RLE over the floor-contact boolean, exactly like the state-segment rule above, not a
single-shot detector. This is observation of an existing numerical safeguard, never a new
protection trip — explicitly labeled `category="bus_energy"`, distinct from `category=
"protection_state"` (Engineering Lead Decision 4). **These are point-in-time `TimelineEvent`s, not
`StateSegment`s** (§11's dataclasses): a `TimelineEvent` carries no `duration_s`/`end_time_s`/
`is_open_ended` field. An excursion still active at the end of the run is represented by its entry
event having **no matching exit event** in the returned list — that absence *is* the open-ended
signal; a reader (or test) computing a bus-energy excursion's duration does so as
`(matching exit event's time_s, or the run's final time_s if none) − entry event's time_s`, never
from a field this module adds to `TimelineEvent` itself (closes the excursion-metadata gap a
closure review of this specification identified: §8's and §10's duration/open-ended language
applies to `StateSegment`s only, never to `TimelineEvent`s).

**Rule: every transition/event carries a config-traceable cause string (§6); never a vague one.**
`"DERATED begins"` alone is insufficient; the required shape is `"DERATED begins — temperature_c
(71.4 °C) crossed thermal_derate_start_c (70.0 °C)"`. The `TRIPPED` transition's `detail` string
must additionally contain the exact `trip_reason` value verbatim (§11, closes Codex Round 1
Finding 7).

**Rule: the final `StateSegment` of a run is `is_open_ended=True` if the run ends while still in
that state.** Its `end_time_s` is the last sample's `time_s` — the feature never implies the state
would have ended "soon" or extrapolates beyond the simulated window. (This rule is `StateSegment`-
only; see the bus-energy rule above for how an open-ended *excursion* is represented instead.)

## 9. Outcome Semantics (Ordered Terminal Events + Recovery)

**Classification rule (Engineering Lead Decision 2/3 — ordered terminal events, never final-state
inspection).** Two terminal-event candidate times are computed directly from telemetry,
independently of each other:

- `trip_event_time_s` — the `time_s` of the first sample where `trip_active` is `True`, or `None`
  if it is never `True`.
- `bus_collapse_event_time_s` — the `time_s` of the first sample where `v_dc_v` is at-or-below the
  bus-floor voltage (§7/§8's floor tolerance), or `None` if the bus never reaches it.

`outcome` is then:

1. **`PROTECTION_TRIP`** if `trip_event_time_s` is not `None` and (`bus_collapse_event_time_s` is
   `None` or `trip_event_time_s <= bus_collapse_event_time_s`). The `<=` is a narrow, explicit,
   **arbitrary (not causal) tie-break**, applied only when both candidate times are exactly equal:
   this specification defines that exact coincidence as `PROTECTION_TRIP` by convention, favoring
   the named protection action over the derived bus-energy observation. This is **not** a claim
   that the trip caused the simultaneous floor contact — per `src/simulation.py`'s own documented
   step order, a recorded sample's `v_dc_v` reflects a DC-bus energy integration that itself used
   `p_sst_w`'s *pre-trip* value, and `p_sst_w` only moves toward a trip-zeroed target through the
   SST's own separate first-order lag (`step_sst_power`) — so the trip's own effect on `v_dc_v`
   propagates through *two* separate numerical lags (the SST's response lag, then the bus's own
   energy-integration step) and is visible no earlier than two recorded samples after the sample
   where `trip_active` first reads `True`, never at that same sample or the very next one. A
   same-sample (or near-sample) coincidence therefore reflects two conditions that became true
   independently, not one causing the other — the convention exists only to make the
   classification total and deterministic for that edge case, not to assert a causal story. (None
   of Scenarios A–E's defaults exercise this tie — §0 — so it is tested only via a constructed
   fixture, AC-019, which must test the *convention*, not a causal claim.)
2. **`BUS_COLLAPSE_UNPROTECTED`** if `bus_collapse_event_time_s` is not `None` and
   (`trip_event_time_s` is `None` or `bus_collapse_event_time_s < trip_event_time_s`).
3. **`RIDE_THROUGH`** if neither terminal-event time exists.

**A later event never retroactively changes an earlier-determined outcome.** For Scenario C under
default parameters: the bus reaches the floor at ~14.4 s, the trip does not latch until ~46.1 s, so
`outcome = BUS_COLLAPSE_UNPROTECTED` — the trip is real, later, and remains fully visible as its
own `category="protection_state"` `TimelineEvent` (with `trip_reason` stated verbatim, §8/§11), but
it does not change `outcome` back to `PROTECTION_TRIP`. This treats "the energy buffer was already
exhausted, unprotected, before the (separate, thermal) protection system ever acted" as the more
important headline fact for this run — a deliberate Engineering-Lead-directed design choice.

**`BUS_COLLAPSE_UNPROTECTED` is an educational V1-model result, never a claim about real hardware.**
`src/protection.py` implements only sustained-overtemperature protection; it has no bus-undervoltage
trip. Every place this outcome is surfaced (`outcome_detail`, §11; the universal educational
caption, §12) must state this explicitly and must never phrase it as if a trip occurred, and never
silently report it as a plain "ride-through."

**`recovery` — a separate, descriptive field (Engineering Lead Decision 3), not a second outcome
axis.** `outcome` answers "which terminal event happened first, if either"; `recovery` separately
answers "did the bus return to, and stay at, its nominal band by the end of the run" — reusing
`transientMetrics.ts`'s already-established ±1%-of-`V_ref` settling-band convention (that module's
own header comment: "the standard engineering settling-time criterion"), ported to this new Python
module rather than invented fresh:

- `RECOVERED` — `v_dc_v` is within `±1% * voltage_reference_v` of `voltage_reference_v` at the
  final sample, having remained within that band continuously since its last excursion (the exact
  scan `transientMetrics.ts` already implements, applied over the whole run).
- `NOT_RECOVERED` — not within that band at the final sample.
- `NOT_APPLICABLE` — `outcome == PROTECTION_TRIP` only: the trip deliberately forces
  `derate_factor = 0.0` for the rest of the run (no automatic reset in V1) — the resulting near-floor
  voltage is the trip working as designed, not a recovery question this field answers.

No new voltage-margin threshold is invented for `recovery` beyond this existing ±1% band. A third,
"`PARTIAL`" tier was considered (per the Engineering Lead's own example) but no existing
repository-authoritative tolerance distinguishes "partial" from "recovered"/"not recovered" — this
is left as an explicit open item rather than an invented threshold (§15).

**Removed in this revision:** v0.2's convenience `rode_through: bool` field. `outcome` + `recovery`
together are strictly more precise, and a UI needing a single-glance binary can test
`outcome == RIDE_THROUGH` directly.

## 10. Timing/Duration Semantics

- `duration_s = end_time_s - start_time_s` for every `StateSegment`; the last one's `end_time_s`
  is the final sample's `time_s`.
- `StateSegment` durations for one run sum exactly to `telemetry.time_s[-1] - telemetry.time_s[0]`
  (an invariant, tested in §16).
- An `is_open_ended` segment's stated duration is "at least" that value, worded as such in the UI
  — never presented as a completed/settled duration.
- **Bus-energy-floor excursions have no `duration_s`/`end_time_s`/`is_open_ended` field of their
  own** (§8) — they are a pair of point-in-time `TimelineEvent`s (entry, and exit if one occurs),
  not `StateSegment`s; a duration or open-ended status is derived by a reader from the presence or
  absence of the matching exit event, never stored as a separate field this module computes.

## 11. Backend / API Impact

**New module: `dashboard/adapters/protection_timeline.py`.** Pure functions/dataclasses, no I/O.
Its only `src/` import is `src.dc_bus.voltage_from_energy` (bus-floor voltage, §7) — the same pure
function `scenarios/plotting.py:floor_voltage` already calls this way; `simulation_adapter.py` does
not import it today, so this is one new, narrow import.

```python
@dataclass(frozen=True)
class StateSegment:
    state: str              # "RUNNING" | "DERATED" | "TRIPPED" -- authoritative src/protection.py
                              # output only (Engineering Lead Decision 4)
    start_time_s: float
    end_time_s: float
    duration_s: float
    is_open_ended: bool

@dataclass(frozen=True)
class TimelineEvent:
    time_s: float
    category: str           # "protection_state" | "input_event" | "bus_energy"
    label: str
    cause: str               # "" for input_event (already labeled, see reconciliation rule below)
    detail: str              # config/telemetry-traceable detail; the TRIPPED transition's `detail`
                              # MUST contain the verbatim telemetry.trip_reason value (AC-017)

class RideThroughOutcome(Enum):
    RIDE_THROUGH = "RIDE_THROUGH"
    PROTECTION_TRIP = "PROTECTION_TRIP"
    BUS_COLLAPSE_UNPROTECTED = "BUS_COLLAPSE_UNPROTECTED"

class RecoveryStatus(Enum):
    RECOVERED = "RECOVERED"
    NOT_RECOVERED = "NOT_RECOVERED"
    NOT_APPLICABLE = "NOT_APPLICABLE"    # outcome == PROTECTION_TRIP only, §9

@dataclass(frozen=True)
class ProtectionTimeline:
    segments: tuple[StateSegment, ...]
    events: tuple[TimelineEvent, ...]
    outcome: RideThroughOutcome
    outcome_event_time_s: float | None   # the terminal-event time that determined `outcome`;
                                           # None for RIDE_THROUGH
    outcome_label: str                    # backend-owned plain-English label (§12) --
                                           # frontend reads verbatim
    outcome_detail: str                   # backend-owned, traceable explanation (§9) --
                                           # frontend reads verbatim
    recovery: RecoveryStatus
    recovery_label: str                   # backend-owned plain-English label (§12) --
                                           # frontend reads verbatim

def build_protection_timeline(
    telemetry: Telemetry, config: Config, input_events: EventMarkers,
) -> ProtectionTimeline: ...
```

`build_protection_timeline` requires `len(telemetry.time_s) >= 1` and raises `ValueError`
otherwise — it never silently returns an empty-looking but misleadingly "valid" result for
degenerate input. A single-sample `telemetry` produces exactly one open-ended segment, zero
transition events, and `outcome`/`recovery` computed normally from that one sample (AC-018).

**Input-event reconciliation rule (closes Codex Round 1 Finding 4).** `input_events` must contain
only genuine load/grid-input markers, never one this module's own extraction (§8) already derives
more precisely from `operating_state`/`trip_active`. Concretely: `load_step`'s "load step",
`grid_sag`'s "sag begins"/"grid recovers", and `grid_loss`'s "grid lost" markers are genuine and
are passed through unchanged from each scenario's existing `ScenarioResult.events`.
`sustained_high_load` has none. `thermal_trip`'s own adapter-computed `events` ("derating begins",
"TRIPPED") are **not** genuine input events — they are themselves derived from
`derate_factor`/`trip_active` — so the new endpoint (below) passes an empty tuple for
`thermal_trip`'s `input_events`, not `simulation_adapter.run_thermal_trip`'s own `events` field.
This is a caller-level filtering rule; `simulation_adapter.py`'s existing `events` computation is
unchanged (other consumers, e.g. `scenarios/thermal_trip.py`'s own plots, still use it), and
`build_protection_timeline` itself stays a dumb, fully-trusting merge of whatever `input_events` it
is given — never a string-match heuristic inside the module.

**One new FastAPI endpoint (Engineering Lead Decision 5 — replaces v0.2's four endpoints):**

    GET /api/v1/simulations/protection-scenarios/{scenario}

`scenario` is a path parameter constrained to `Literal["sustained_high_load", "thermal_trip",
"grid_sag", "grid_loss"]` — an out-of-set value is rejected with HTTP 422 by FastAPI's own typed
path-parameter validation, no hand-written check needed. **Justification for one endpoint, not
four:** Scenarios B–E have no tunable request parameters in this feature's scope (Decision 6) —
unlike Scenario A's `LoadStepRequest`, which exists because Scenario A genuinely has experiment
parameters (SPEC-002) — so four near-identical, parameter-less `POST` endpoints and four
near-identical response schemas would be the larger, more repetitive shape for no behavioral
benefit. One `GET` endpoint with a constrained path parameter and one shared response schema is the
smallest shape that still (a) exposes all four scenarios individually and discoverably by name, (b)
validates the scenario name as a type error rather than a hand-rolled check, and (c) needs no
request body, which better reflects "fixed preset, no parameters" than an empty `POST` body would.
Each call thin-translates exactly as `simulate_load_step` already does: dispatch `scenario` to its
matching existing adapter function (called with zero overrides — its own defaults are the fixed
preset, Decision 6), call `build_protection_timeline` on the result with the reconciled
`input_events` above, and serialize.

The shared response schema (`ProtectionScenarioResponse`) mirrors `LoadStepResponse`'s shape
(`scenario`, `thresholds`, `events`, `timeseries`) plus `protection_timeline`
(`ProtectionTimelineModel`, mirroring the dataclasses above field-for-field). `thresholds` extends
`ScenarioThresholds` with the additional fields these scenarios' Timelines cite:
`thermal_trip_time_s`, `derate_factor_min`, `floor_voltage_v`. Whether this is a new shared
`ProtectionScenarioThresholds` model or an additive extension of `ScenarioThresholds` is an
implementation detail, not a Human Gate (same precedent as SPEC-005 §16's resolved item 3).

**`LoadStepResponse` gets one new, optional, additive field: `protection_timeline`.** No existing
field's type or meaning changes, and no endpoint behavior changes for a caller that ignores the new
field. Computed by the same `build_protection_timeline` call applied to Scenario A's own telemetry
and its existing, unchanged single "load step" input event.

**This does add one key to the top-level response object**, which means the existing
exact-set-equality assertion in `tests/test_api.py::test_load_step_response_schema_shape`
(`tests/test_api.py:39`: `assert set(body.keys()) == {"scenario", "thresholds", "events",
"timeseries"}`) cannot pass unmodified as written. This specification explicitly authorizes
updating **that one literal set** to add `"protection_timeline"` — and authorizes nothing else in
that test or any other `tests/test_api.py` test to change (AC-007).

**No change to any `src/` module.** Confirmed as an explicit acceptance criterion (AC-005).

## 12. Frontend Presentation

**Scenario selector** (new, header area): five named, clearly-labeled options — Load Step
(default, unchanged endpoint/behavior), Sustained High Load, Thermal Trip, Grid Sag, Grid Loss (new,
all four sharing the one `GET /api/v1/simulations/protection-scenarios/{scenario}` endpoint, §11)
— implemented as a real `role="radiogroup"`/`<fieldset>` control (keyboard-operable), each option
carrying a `data-testid`. This is a navigational/selection control, never a slider.

**Universal across all five scenarios:** KPI strip, `PowerFlowSchematic`, `TimeScrubber` +
synchronized `TelemetryChart`s, and the new Protection Timeline section (below) — all read
generically from `Sample`/`Telemetry`-shaped data plus the additive `protection_timeline` field.

**Universal educational caption (closes Codex Round 1 Finding 11; implements Engineering Lead
Decision 2's UI requirement).** The Protection Timeline section carries one fixed, always-visible
caption, present for every scenario regardless of which outcome occurred: "V1 models only sustained
thermal overtemperature protection. It has no DC-bus undervoltage/overvoltage protection. Thresholds
and the outcomes shown here are illustrative, educational model results (see `CLAUDE.md`) — not a
claim about how a real SST and its surrounding protection system would necessarily behave." This
satisfies `CLAUDE.md`'s integrity rules for every newly-exposed scenario, not only the ones that
happen to trip.

**New: Protection Timeline section** (`frontend/app/components/ProtectionTimeline.tsx`), reading
only `protection_timeline` fields verbatim from the fetched response:

- A horizontal segmented bar, one visual segment per `StateSegment`, width proportional to
  `duration_s`, colored via the existing `sstStatus()` role mapping — no new color role. Each
  segment carries a text label (state name + duration + "ongoing" suffix for open-ended segments) —
  never color-only. (AC-012 scopes the "ongoing" requirement to segments only, not to the
  point-in-time event list below — closes part of Codex Round 1 Finding 6.)
- An ordered event list: timestamp, label, cause/detail text — read verbatim from the backend.
- An outcome banner stating `outcome_label`/`outcome_detail` **verbatim**, and a recovery readout
  stating `recovery_label` **verbatim** — both backend-owned display strings (§11), so the frontend
  performs zero enum-to-English translation for either field (closes the rest of Finding 6).
- **Numeric formatting is not "rephrasing."** `time_s`/`duration_s` floats are formatted (fixed
  decimal places, unit suffix) by one small, shared helper applied uniformly — presentation
  rounding of an already-correct value, not new wording, and does not violate AC-011's
  verbatim-content requirement (which governs engineering content/wording, never digit formatting).

**Scenario-A-only sections (closes Codex Round 1 Finding 8 — the v0.2 list was incomplete).** The
following render, and `computeTransientMetrics` is computed and used at all, only when Load Step is
selected: `EventBanner`, `EngineeringInterpretation`, `EnergyDeficitAnalysis`, `ExperimentPanel`,
`SensitivityStudy`, **and now explicitly also** `TransientMetricsPanel`, the V_dc chart's
minimum-voltage `markerPoint` annotation, and the Power Balance chart's `deficitFill` annotation.
For Scenarios B–E, `computeTransientMetrics` is **not called at all** — it anchors to
`data.events[0]`, which is absent for Sustained High Load and is a protection marker (not a load
event) for Thermal Trip, so calling it for those scenarios would silently produce a
wrongly-anchored, misleading result, not merely an unused one. The two charts render without those
two annotations for Scenarios B–E; otherwise unchanged.

## 13. Interaction with SPEC-005

**13.1 — Explicit extension, naming exactly what is inherited and what is added (Engineering Lead
Decision 1).** SPEC-005's standing architecture commits to "one continuous page... no tabs, no
routes," and its Non-Goals (§17) list "new scenarios... any navigation/tab structure" and "any
change to `backend/` or `src/`... not added in this slice" — all scoped to the ANALYZE slice that
document authorizes. SPEC-005 §17's own closing sentence anticipates exactly this situation. This
specification therefore states precisely:

- **Inherited unchanged from SPEC-005:** every acceptance criterion **AC-001 through AC-014 and
  AC-016 through AC-019** — none of which concern `backend/`/`src/` file changes or navigation
  structure; they govern Scenario A's own rendered narrative content, physics-integrity,
  design-token, and build/test requirements, none of which this specification's additive
  `protection_timeline` field or conditional-render wrapper (§13.3) changes for a viewer who has
  selected Load Step. `DESIGN.md`'s visual register, the OBSERVE→UNDERSTAND→EXPLAIN→EXPERIMENT
  progression, and the TOPOLOGY→STATE→TIME→CAUSE→PHYSICS grammar (SPEC-005 §5–§6) are also
  inherited unchanged and apply to the new Protection Timeline section as the "EXPLAIN" step for
  Scenarios B–E.
- **Added by SPEC-008, superseding exactly these three named items and no others:** SPEC-005
  §17's Non-Goal clauses forbidding "new scenarios," "any navigation/tab structure," and "any
  change to `backend/` or `src/`"; and SPEC-005's own **AC-015** ("No file under `backend/` or
  `src/` is modified by this slice's implementation"). SPEC-008 does modify
  `backend/app.py`/`backend/schemas.py` (§11) and does add one navigational primitive (§12) — this
  is an explicit, named supersession, never a silent contradiction. Selecting Load Step at runtime
  does not retroactively make AC-015 true, and this specification does not claim it does.

**Resolved.** This exact, named supersession (AC-015 and the three quoted Non-Goal clauses, and no
other part of SPEC-005) is Engineering Lead Decision 1 (approved) — it is no longer an open Human
Gate. §15's "Still open" list concerns two different, narrower questions (hiding vs. adapting the
Scenario-A-only sections, and the `recovery` field's missing "`PARTIAL`" tier); it does not include
this one.

**13.2 — No change to SPEC-005's authorized ANALYZE content.** `EnergyDeficitAnalysis.tsx` and
every file SPEC-005 §14's AC-001–AC-019 governs are touched only by the conditional-render wrapper
in §13.3 — their internal content, computation, and SPEC-005 acceptance criteria are unaffected
when Scenario A is the active selection.

**13.3 — Conditional rendering, not deletion.** When a non-Load-Step scenario is selected, the
Scenario-A-only components (§12) render nothing and their underlying computations are not
performed; they are not deleted, disabled, or repurposed. Selecting Load Step again restores their
exact original behavior.

## 14. Responsive Behavior & Accessibility

- The scenario selector and Protection Timeline must render without horizontal overflow and
  degrade to the existing single-column pattern below the `sm`/`lg` breakpoints already used
  throughout `page.tsx`.
- No meaning is encoded by color alone: every colored segment/outcome state carries a text label.
- The scenario selector is keyboard-operable (real interactive elements, visible focus state, no
  `div onClick`-only control): arrow-key or tab navigation between options, `aria-pressed`/
  `aria-checked` reflecting the current selection.
- Semantic sectioning (`<section>`, consistent heading-label styling) matches
  `TransientMetricsPanel.tsx`/`EngineeringInterpretation.tsx`'s existing conventions.

## 15. Engineering Lead Decisions and Remaining Open Items

**Resolved by the Human Engineering Lead (this revision implements all of the following; see
"Engineering Lead Decisions" above for the full brief):** (1) SPEC-005 extension, approved as
additive with the exact inherited/superseded split named in §13.1; (2) three-way outcome taxonomy
classified by ordered terminal events, with `BUS_COLLAPSE_UNPROTECTED` explicitly framed as an
educational V1-model result (§9, §12), approved; (3) fixed scenario parameters, no sliders, for
Scenarios B–E (§4), approved; (4) smallest backend/API shape — one new endpoint, not four (§11),
approved with the stated justification; (5) no PEOS modification to work around the
`experiment_run` capability gap (§18, §19), approved — the gap is recorded, not closed.

**Still open, for the Human Engineering Lead's explicit disposition:**

1. **Scenario-A-only sections: hidden vs. scenario-appropriate equivalents (§12).** This revision
   hides (never deletes) the Scenario-A-only narrative components for Scenarios B–E, but hiding
   vs. building scenario-appropriate equivalents for B–E was not itself addressed by name in the
   Engineering Lead's decisions, and remains open.
2. **`recovery`'s missing "`PARTIAL`" tier (§9).** The Engineering Lead's Decision 3 permits a
   `RECOVERED`/`PARTIAL` split "if useful," but also forbids inventing a new threshold absent an
   existing authoritative one. No tolerance in this repository today distinguishes a "partially
   recovered" bus from a "recovered" or "never recovered" one — even `transientMetrics.ts`'s own
   settling-band scan is binary. This revision ships the binary `RECOVERED`/`NOT_RECOVERED`/
   `NOT_APPLICABLE` split only and flags the "`PARTIAL`" question as the one remaining threshold
   decision, per Decision 3's own escape clause ("explicitly identify a genuine remaining
   decision").

None of these is a request to change `src/` physics, and neither is blocked on anything but the
Human Engineering Lead's product/scope judgment.

## 16. Acceptance Criteria

- [ ] **AC-001 (segment/outcome/recovery correctness, real scenarios):** `build_protection_timeline`,
  applied to the real `Telemetry`/`Config` produced by `run_thermal_trip`, `run_sustained_high_load`,
  `run_grid_sag`, and `run_grid_loss` (no synthetic fixtures), yields exactly the outcome/recovery
  pairs in §0's table (Thermal Trip → `BUS_COLLAPSE_UNPROTECTED`/`NOT_RECOVERED`; Sustained High
  Load → `RIDE_THROUGH`/`RECOVERED`; Grid Sag → `BUS_COLLAPSE_UNPROTECTED`/`RECOVERED`; Grid Loss →
  `BUS_COLLAPSE_UNPROTECTED`/`NOT_RECOVERED`), and segments `[RUNNING, DERATED, TRIPPED]` in order
  for Thermal Trip. A separate test confirms Scenario A's default run never reaches the numerical
  floor, establishing (not assuming) its `RIDE_THROUGH`/`RECOVERED` result.
- [ ] **AC-002 (duration invariant):** For every scenario above, the sum of all `StateSegment`
  durations equals `telemetry.time_s[-1] - telemetry.time_s[0]` within floating-point tolerance.
- [ ] **AC-003 (config-traceable causes):** Every `TimelineEvent` with `category="protection_state"`
  has a `detail` string containing the exact numeric value of the `Config` field it names, verified
  by a test parsing that value back out and comparing it to `config.protection.<field>`.
- [ ] **AC-004 (ordered-event precedence, real chronology):** For the real default Thermal Trip run
  — where the bus reaches the numerical floor (~14.4 s) *before* `trip_active` first becomes `True`
  (~46.1 s) — `outcome_event_time_s` equals the earlier floor-entry time, `outcome` is
  `BUS_COLLAPSE_UNPROTECTED` (not `PROTECTION_TRIP`), and the returned `events` list separately
  contains the later `TRIPPED` transition at its own correct (~46.1 s) timestamp with `trip_reason`
  stated verbatim in its `detail` — verified against real adapter output.
- [ ] **AC-005 (no physics change):** No file under `src/` appears in this feature's diff.
- [ ] **AC-006 (new endpoint, schema/parity, validation):** The one new endpoint returns HTTP 200
  for each of the four valid scenario names and HTTP 422 for an invalid one; for each valid name,
  `thresholds` echo the `Config` fields the matching adapter call actually used, and
  `protection_timeline` is identical to calling `build_protection_timeline` directly on that same
  adapter call's result (with the §11-reconciled `input_events`).
- [ ] **AC-007 (Load Step additive field only):** `LoadStepResponse` gains `protection_timeline`
  with no other field changed. Exactly one existing assertion is explicitly authorized to change —
  `test_load_step_response_schema_shape`'s top-level key-set literal (`tests/test_api.py:39`)
  gains `"protection_timeline"` — and every other assertion in that test and every other
  `tests/test_api.py` test continues to pass completely unmodified.
- [ ] **AC-008 (scenario selector present and keyboard-operable):** A `role="radiogroup"` (or
  equivalent) control with five `data-testid`-tagged, named options is present; each is reachable
  and selectable via keyboard alone.
- [ ] **AC-009 (selection fetches the correct endpoint, no stale data):** Selecting Load Step
  fetches from the existing `/load-step` endpoint; selecting any of the other four fetches from
  `GET /api/v1/simulations/protection-scenarios/{scenario}` with the matching path parameter; the
  KPI strip/schematic/charts/Timeline reflect the newly fetched run with no stale values retained.
- [ ] **AC-010 (conditional sections, complete list):** `EventBanner`, `EngineeringInterpretation`,
  `EnergyDeficitAnalysis`, `ExperimentPanel`, `SensitivityStudy`, `TransientMetricsPanel`, the V_dc
  chart's minimum-voltage marker, and the Power Balance chart's deficit-shading render (or, for the
  two chart annotations, are computed) if and only if the Load Step scenario is selected; the
  Protection Timeline renders for every selection.
- [ ] **AC-011 (Timeline content, verbatim):** For the active run, the Protection Timeline displays
  one bar segment per returned `StateSegment`, the full ordered `TimelineEvent` list, and
  `outcome_label`/`outcome_detail`/`recovery_label` verbatim, with no engineering wording
  recomputed or rephrased by the frontend (numeric digit-formatting is permitted, §12) — verified
  by code inspection.
- [ ] **AC-012 (open-ended labeling, segments only):** Any segment with `is_open_ended=true` is
  labeled distinctly (e.g., "ongoing") in the rendered bar, never presented as a completed duration.
- [ ] **AC-013 (all three outcomes visibly distinct):** `outcome_label`/`outcome_detail` differ
  across all three enum values such that no two are textually or visually confusable;
  `BUS_COLLAPSE_UNPROTECTED`'s text explicitly states the model has no bus-voltage trip, never
  phrased as if a trip occurred.
- [ ] **AC-014 (no new frontend physics/classification):** No new code in this feature's diff
  performs numerical integration, re-derives `operating_state`/`trip_active`/outcome/recovery, or
  classifies anything independently of the backend's `protection_timeline` field.
- [ ] **AC-015 (recovery field correctness on real runs):** `recovery` is `RECOVERED` for
  Sustained High Load and Grid Sag, `NOT_RECOVERED` for Grid Loss, consistent with §9's ±1% band
  applied to each run's actual `v_dc_v` series.
- [ ] **AC-016 (input-event reconciliation, closes Finding 4):** For Thermal Trip, the returned
  `events` contains no entry whose `label` is "derating begins" or "TRIPPED" copied from the
  adapter's own markers. For Grid Sag/Grid Loss/Load Step, the adapter's own input-event labels
  appear unchanged in the returned `events`.
- [ ] **AC-017 (trip_reason field contract, closes Finding 7):** The `protection_state`
  `TimelineEvent` transitioning to `TRIPPED` has a `detail` string containing the exact
  `telemetry.trip_reason` value at the matching sample index — tested at the module/API boundary,
  not only against the raw telemetry.
- [ ] **AC-018 (degenerate input handling):** `build_protection_timeline` raises `ValueError` for
  zero-length telemetry; a one-sample telemetry input produces exactly one open-ended segment, zero
  transition events, and a normally-computed `outcome`/`recovery` — tested with small constructed
  fixtures, not a real scenario run.
- [ ] **AC-019 (deterministic extraction fixtures, closes Finding 10):** Small, constructed
  (non-real-scenario) `Telemetry` fixtures test: exact segment boundary/adjacency for a
  `RUNNING`→`DERATED`→`RUNNING`→`DERATED`→`TRIPPED` sequence (covering the `DERATED`→`RUNNING`
  return case); repeated bus-floor entry/exit (at least two separate excursions) producing the
  correct number of distinct `bus_energy` entry/exit events, not merged or dropped; **at least one
  fixture producing `outcome=PROTECTION_TRIP`** (trip before, or with no, floor contact) and **one
  fixture producing an exact-timestep tie** between the two terminal-event conditions (testing §9's
  tie-break rule) — since none of Scenarios A–E's defaults exercise `PROTECTION_TRIP` or the tie at
  all (§0), these fixtures are the *only* coverage for that outcome and that rule, not merely
  supplementary.
- [ ] **AC-020 (universal educational caption present, closes Finding 11):** The fixed educational
  caption text (§12) is present in the rendered Protection Timeline section for every one of the
  five scenarios.
- [ ] **AC-021 (design-token compliance):** All new colors are existing `theme.ts`/`statusRoles.ts`
  tokens/roles; no new chart type, gauge, battery/SOC metaphor, or decorative animation.
- [ ] **AC-022 (responsive):** The selector and Timeline render without horizontal overflow and
  degrade to single-column at the existing `sm`/`lg` breakpoints.
- [ ] **AC-023 (accessibility):** The selector is operable via keyboard alone with a visible focus
  state and correct `aria-checked`/`aria-pressed` state; no meaning in the Timeline is color-only.
- [ ] **AC-024 (lint/typecheck/build):** `cd frontend && npm run lint && npm run typecheck && npm run build` pass with no new errors/warnings.
- [ ] **AC-025 (Python tests):** `python -m pytest -q` passes at the repository root, including all
  new tests this feature adds.
- [ ] **AC-026 (validation record):** `docs/validation/SPEC-008-validation.md` is filed recording
  which criteria were checked, how, and the result.

## 17. Verification Plan

**Deterministic (pytest) — the load-bearing evidence for this feature's correctness-critical
logic:**

- `python -m pytest tests/test_protection_timeline.py -q` (new) — AC-001, AC-002, AC-003, AC-004,
  AC-015, AC-016, AC-017, AC-018, AC-019. Exercises both the four real scenarios' actual adapter
  output and small, constructed fixtures for the general extraction-algorithm edge cases (per Codex
  Round 1 Finding 10's explicit request that real-scenario integration tests be supplemented, not
  replaced, by deterministic fixtures — and, per §0/AC-019, the *only* way to exercise
  `PROTECTION_TRIP` and the tie-break rule at all).
- `python -m pytest tests/test_api.py -q` (extended, not replaced) — AC-006, AC-007.
- `python -m pytest -q` at the repository root — AC-025 (full-suite regression).
- `cd frontend && npm run lint && npm run typecheck && npm run build` — AC-024.

**Manual verification checklist (Category C per SPEC-006 §6's Verification Taxonomy [Deterministic
/ Runtime-observational / Human judgment] — closes Codex Round 1 Finding 9; implements Engineering
Lead Decision 7's instruction to use the strongest verification actually available without
claiming browser coverage the catalog cannot provide).** Performed once
by the implementer against a running dev server, recorded in `docs/validation/SPEC-008-validation.md`
(AC-026):

1. Select each of the five scenario options using the keyboard alone; confirm the correct endpoint
   is called for each and that the KPI strip/schematic/charts/Timeline all reflect the
   newly-fetched run with no stale values (AC-008, AC-009).
2. For each of the five scenarios, confirm the Protection Timeline's segment bar, event list, and
   outcome/recovery banner match §0's table (AC-010, AC-011, AC-012, AC-013, AC-020).
3. For at least two non-default scenarios (recommended: Thermal Trip and Grid Sag, since they
   produce the taxonomy's least-intuitive result), confirm the mobile-width (`<640px`) layout
   renders without horizontal overflow or clipped text (AC-022) — `viewport_overflow` (§18) only
   covers the default (Load Step) page at load time, never a selected non-default scenario, so this
   manual check is this feature's only evidence for that combination.

**Frontend automated tests ("where appropriate," Engineering Lead Decision 7) — honestly not
available in this revision.** `frontend/package.json` has no test runner installed today; adding
one would itself be a new-framework decision outside this specification's authority per
`CLAUDE.md`'s "no additional framework... not clearly necessary" rule, so this specification does
not add one and does not claim frontend test coverage it does not have. TypeScript's `tsc --noEmit`
and ESLint already provide static-correctness coverage of the new frontend code; combined with
AC-014's prohibition on any frontend-side classification logic, the actual behavioral-correctness
surface is concentrated in the backend module the pytest suite above already covers directly.

## 18. Runtime Verification

Per SPEC-006, the fixed V1 catalog (`page_load`, `viewport_overflow`, `experiment_run`) is the only
Category-B evidence source available. `experiment_run` cannot express a scenario-selection
interaction (§0), so this feature's Runtime Plan is limited to static presence/order/responsiveness
checks of the default-loaded (Load Step) scenario's rendered page. §17's deterministic and manual
checks are the primary verification layers for this feature; Runtime Verification is corroborating,
narrower evidence, not the sole or primary source.

> **Historical:** the PEOS Runtime Verification plan below is retired; PEOS and its runner are available only at git tag `pre-peos-retirement`. Verify via the unit/regression tests and manual checks instead.

### Runtime Verification

    runtime: page_load path=/ landmarks="[data-testid='scenario-select'],[data-testid='protection-timeline'],[data-testid='outcome-banner']" ac=AC-008 ac=AC-011
    runtime: viewport_overflow viewport=desktop ac=AC-022
    runtime: viewport_overflow viewport=mobile ac=AC-022

The implementer must add the three referenced `data-testid` attributes — no `data-testid` exists
anywhere in the frontend today (§0), so this is new, required instrumentation.

## 19. PEOS Dogfood Observations (reported separately, not a change requested by this spec)

Two operational findings about PEOS itself surfaced during this specification's development and
review. Neither is a SPEC-008 product requirement; neither requires or requests any PEOS
infrastructure change within this specification.

**19.1 Runtime-interaction capability gap.** The `experiment_run` runtime-check kind
(`peos/runtime_catalog.py`) is special-cased to one interaction shape and cannot declare "select
option N of a labeled set, then assert on newly-rendered content distinguishing it from the other
options' content." This is a standing PEOS V1 limitation (SPEC-006 §4 explicitly rejected a
general scripting DSL in favor of a fixed catalog), not a defect introduced by this specification.
Per Engineering Lead Decision 7, it is reported here for visibility and is **not** a request to
expand the catalog; §17's manual-check list is this specification's actual mitigation, used
instead of inventing or falsely claiming browser coverage the catalog cannot provide.

**19.2 Disk hygiene of temporary/test workspaces.** During real PEOS development and testing
(observed in this session's own work, not specific to SPEC-008's engineering content), temporary
verification/test workspaces accumulated approximately 8 GB in the macOS temporary directory,
with multiple isolated workspaces of roughly 500 MB each surviving well past their useful test
lifetime. This is an operational PEOS finding about workspace lifecycle, not a product requirement
of this specification:
- Temporary/test/diagnostic workspaces require bounded lifecycle cleanup.
- Terminal or abandoned temporary workspaces should not accumulate indefinitely.
- Only genuinely resumable durable state (`ACTIVE` / `PAUSED_RETRYABLE`, per SPEC-007's durable-run
  states) should require retention; a workspace behind a terminal or abandoned run should not.
- This finding must not cause any PEOS infrastructure change inside SPEC-008. Designing or
  implementing a fix is explicitly out of scope here and is left for separate PEOS-infrastructure
  work.

## 20. Known Limitations

- **V1 protection has no bus-voltage trip.** `BUS_COLLAPSE_UNPROTECTED` (§9) is a presentation
  label for this pre-existing, documented model gap — this feature narrates it honestly; it does
  not close it. Three of the five scenarios register this outcome by design (§0), not by defect.
- **All of `src/protection.py`'s existing Category B/C assumptions carry over unchanged.**
- **`recovery`'s binary (not three-way) granularity is a stated, open limitation** (§15 item 2),
  not a silently-accepted gap.
- **Scenario A's Protection Timeline is minimally interesting** — one open-ended `RUNNING`
  segment, `RIDE_THROUGH`/`RECOVERED`, by design — included for presentation uniformity only.
- **No scenario-parameter experimentation for Scenarios B–E in V1** (§4, Engineering Lead
  Decision 6).
- **No real scenario in this repository exercises `outcome=PROTECTION_TRIP`** under the ordered-
  event rule (§0) — that branch's correctness rests entirely on constructed fixtures (AC-019), not
  on any end-to-end scenario run.
- **Runtime Verification coverage of the scenario selector and any non-default scenario's content
  is not achievable with the current PEOS catalog** (§18, §19) — compensated by the manual-check
  list (§17), not closed by this specification.
- **No frontend automated test coverage** (§17) — no test runner is installed in this repository's
  frontend today, and adding one is outside this specification's authority.
- **No persistence of the selected scenario** across a page reload.

## 21. Outstanding Findings Register — Final Disposition (all 12 Round 1 findings + 2 Round 2 findings, Round 3 confirmed)

| # | Severity | Finding (condensed) | Disposition |
|---|---|---|---|
| 1 | Blocking | False causal explanation of Thermal Trip's bus collapse (claimed it was a consequence of the later trip). | **CLOSED** in v0.2 (§0/§9 reworded to state the real chronology). Superseded in v0.3: Engineering Lead Decision 2's ordered-event rule changes Thermal Trip's `outcome` to `BUS_COLLAPSE_UNPROTECTED` outright, making the original false-causality claim moot rather than merely corrected-in-place. |
| 2 | Blocking | `LoadStepResponse`'s additive field breaks `tests/test_api.py:39`'s exact key-set assertion, with no stated authorization to update it. | **CLOSED** in v0.2 (§11/AC-007 explicit, named authorization). Unchanged in v0.3. |
| 3 | Blocking | §13.1 claimed every SPEC-005 AC stays unchanged while requiring backend changes — self-contradictory given SPEC-005 AC-015. | **CLOSED** in v0.2 (§13.1 named supersession). Tightened in v0.3 per Engineering Lead Decision 1 into an explicit inherited/added split (§13.1). |
| 4 | Major | Merging the adapter's entire `events` list as `input_event` mislabels Thermal Trip's own protection-derived markers as physical inputs. | **CLOSED** in v0.3 — §8/§11's input-event reconciliation rule; AC-016. |
| 5 | Major | `RIDE_THROUGH`'s margin-based definition ("not at the floor at the final sample") is satisfied by voltages far from any real operating envelope and contradicts `src/dc_bus.py`'s own statement that reaching the floor signals a problem. | **CLOSED** in v0.3 — the margin rule is removed entirely; §9's ordered-terminal-event rule (Engineering Lead Decision 2/3) replaces it; AC-001, AC-004, AC-015. |
| 6 | Major | `TimelineEvent` had no open-ended/segment association for AC-012; §12 required enum-to-English translation while AC-011 forbade rephrasing; no display-format contract existed. | **CLOSED** in v0.3 — AC-012 narrowed to segments only; `outcome_label`/`recovery_label` are now backend-owned, frontend reads verbatim (§11/§12); numeric-formatting carve-out stated explicitly (§12, AC-011). |
| 7 | Major | `trip_reason` had no explicit field-level output contract. | **CLOSED** in v0.3 — §8/§11 require the `TRIPPED`-transition `TimelineEvent.detail` to contain `trip_reason` verbatim; AC-017. |
| 8 | Major | No semantics defined for `TransientMetricsPanel`/chart deficit-annotations when a non-Load-Step scenario is active; `transientMetrics.ts` anchors to `events[0]`, which is absent or wrong for B–E. | **CLOSED** in v0.3 — §12's Scenario-A-only list now explicitly includes `TransientMetricsPanel` and both chart annotations, and states `computeTransientMetrics` is never called for B–E; AC-010. |
| 9 | Major | Runtime Verification coverage was materially incomplete beyond the acknowledged `experiment_run` gap — no evidence for keyboard selection, endpoint routing, conditional rendering, or per-scenario content fidelity. | **CLOSED** in v0.3 — §17 adds a named, criterion-mapped manual-check list covering exactly these gaps, per Codex's own suggested remediation ("concrete manual checks using existing tooling, with criterion mappings... no catalog expansion necessary") and Engineering Lead Decision 7. |
| 10 | Major | Acceptance criteria under-specified the extraction rules: no check for exact boundaries/adjacency, repeated floor excursions, `DERATED`→`RUNNING` return, or empty/one-sample input. | **CLOSED** in v0.3 — AC-018 (degenerate input), AC-019 (deterministic fixtures covering boundary/adjacency, repeated excursions, the return case, and now also the `PROTECTION_TRIP`/tie-break cases §0 identified as otherwise untested). |
| 11 | Major | The educational-model disclaimer disappears for Scenarios B–E with no replacement disclosure. | **CLOSED** in v0.3 — §12's universal educational caption, present for every scenario regardless of outcome; AC-020. |
| 12 | Minor (multi-part) | Wording/reference errors: scope-wording self-contradiction, stale cross-references, a false "already imports" claim, incorrect debounce/flicker attribution, "no computation" floor-voltage phrasing. | **CLOSED** in v0.2 for the sub-items identified then. Round 2 found 2 further sub-items (the "§1–§4" cross-reference, and the `ENGINEERING.md`-attributed "Category C" taxonomy) — both **CLOSED** in v0.4. |
| R2-1 (new) | Major | §9's same-sample tie-break justified `PROTECTION_TRIP` precedence with a false causal claim about `src/simulation.py`'s step order (the real order makes the two conditions independent, never one causing the other). | **CLOSED** in v0.4 — §9's tie-break reworded as an explicit, arbitrary, non-causal convention. |
| R2-2 (new) | Major | §13.1's stale "This is a Human Gate (§15 item 1)" sentence contradicted v0.3's own §15, which lists that exact item as resolved (Decision 1) — leaving approval authority self-contradictory. | **CLOSED** in v0.4 — §13.1's stale sentence replaced; it now states the item is resolved and points to §15's actual two open items. |

Round 2 also identified a `minor` excursion-metadata gap not itself numbered in its findings list
but named in its "Repository checks": §8/§10 required `is_open_ended`/duration/end-time metadata
for a "segment/excursion," but §11's dataclasses gave those fields to `StateSegment` only, leaving
`TimelineEvent` (which represents bus-energy excursions) with no declared way to express them.
**CLOSED** in v0.4 — §8/§10 now state explicitly that this metadata is `StateSegment`-only, and
that an open-ended bus-energy excursion is represented by its entry event having no matching exit
event in the returned list, never by a field added to `TimelineEvent`.

**Not a Codex finding, newly surfaced by this revision's own design — recorded as an open Human
Gate (§15 item 2), not a finding to close:** the `recovery` field's missing "`PARTIAL`" tier.

Zero findings remain open at `blocking` or `major` severity from either review round. All `minor`
findings are closed. A Round 3 focused closure review of v0.4 independently re-confirmed all 4
Round 2 closures plus the excursion-metadata item above, found no new defect, and returned
`APPROVE` with 0 blocking / 0 major / 0 minor open — see "Codex Architecture/Specification Review
— Round 3." Two genuine Human Gates (§15) remain, by design — product/scope decisions, not
defects, and not a bar to this specification's implementation-readiness.
