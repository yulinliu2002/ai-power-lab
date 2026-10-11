# SPEC-002 — Scenario A Sensitivity Study

**Status:** Approved
**Project:** AI Power Lab
**System:** Scenario A (AI load step) — frontend experiment/analysis tooling, no new backend surface
**Version:** 0.2
**Type:** Software Component (presentation/orchestration layer; no new engineering model)

---

Revision 0.2 resolves the Human Engineering Lead decisions raised as open
items in v0.1 (execution architecture, sweep size, visualization,
current-value representation, UI placement, testing approach, and the
framing of the physics acceptance criteria). This revision is Approved;
no open item remains pending sign-off.

## 1. Problem Statement

Scenario A (`scenarios/load_step.py` / `dashboard/adapters/simulation_adapter.py:run_load_step`)
already lets a learner run one AI-load-step transient at a time and, since
the existing experiment controls (`frontend/app/components/ExperimentPanel.tsx`,
`backend/schemas.py: LoadStepRequest`), override two engineering parameters
per run: DC-link capacitance `C_dc` and the SST response time constant
`tau_sst`. The existing `TransientMetrics`
(`frontend/app/lib/transientMetrics.ts`) already reduces one run's telemetry
into minimum V_dc, peak deviation, recovery time, peak power mismatch, and
energy deficit.

What does not exist is any way to see how those metrics *change* as `C_dc`
or `tau_sst` is varied across a range. Today a learner can only compare
values by manually running one experiment, reading the numbers, changing a
slider, running again, and remembering the previous result. That is enough
to notice "shallower" or "deeper," but it does not let the learner see the
trend — e.g. that voltage-sag severity is a roughly continuous function of
`C_dc` (an energy-buffering parameter) or of `tau_sst` (a source-response
parameter) — which is the actual engineering lesson Scenario A exists to
teach.

## 2. Engineering Question

For the existing Scenario A disturbance (a fixed AI-load step on the 800 VDC
bus), how does DC-bus transient severity — minimum V_dc, maximum voltage
deviation, and recovery time — vary as a function of (a) DC-link
capacitance `C_dc`, independently, and (b) SST response time constant
`tau_sst`, independently, and how does each trend relate to the accumulated
energy deficit `ΔE = ∫(P_load − P_sst) dt` that the DC link must supply
during the transient?

## 3. Scope

This specification covers adding a **Scenario A Sensitivity Study**: a
learner-triggered action that runs a small, deterministic series of
existing Scenario A simulations varying exactly one of `C_dc` or `tau_sst`
across its existing allowed range (holding every other parameter fixed at
the learner's current single-run experiment values), and presents the
resulting `TransientMetrics` across that series as a chart and a full data
table.

In scope:

- A 1-D sweep over `C_dc`, holding `tau_sst` and every other parameter
  fixed, OR a 1-D sweep over `tau_sst`, holding `C_dc` and every other
  parameter fixed — one sweep, over one parameter, active at a time.
- Exactly 5 deterministic sweep points per sweep, spanning the full
  existing allowed range of the selected parameter (§6).
- Deterministic inclusion of the learner's current experiment value
  alongside the 5-point sweep (§6).
- Reuse of the existing single-run simulation path (engine, adapter, API,
  metrics) for every point — a sweep is repeated existing runs, not a new
  computation.
- A results view, placed within the existing experiment/analysis area
  (§9), showing a required chart plus a full per-point data table.
- Any minimal, additive frontend-only changes needed to produce and
  display a sweep's worth of results (§8). No backend API surface is
  added (§8).

Out of scope is covered explicitly in §4.

## 4. Non-Goals

- **No joint 2-D sweep and no simultaneous dual sweep in V1.** Varying
  `C_dc` and `tau_sst` together (e.g. a heatmap/grid over both at once),
  and running independent `C_dc` and `tau_sst` sweeps at the same time, are
  both out of scope. Exactly one sweep, over one parameter, is active at
  any time; selecting the other parameter to sweep replaces the current
  sweep result rather than showing both simultaneously. A future spec may
  revisit a joint sweep; it is not approved here.
- **No new backend endpoint.** No batch/sweep API is added to
  `backend/app.py`. The sweep is implemented entirely as repeated client
  requests through the existing, unchanged
  `POST /api/v1/simulations/load-step` endpoint (§8).
- **No change to Scenario A's existing single-run baseline behavior,**
  defaults, response schema, or visuals. The sensitivity study is additive.
- **No new simulation physics and no physics duplicated in the frontend.**
  No change to `src/simulation.py`, `src/dc_bus.py`, `src/sst.py`,
  `src/controller.py`, `src/protection.py`, or `src/thermal.py`, and no
  governing equation is re-implemented anywhere outside `src/`.
- **No new engineering parameters.** Only `C_dc` and `tau_sst` — the two
  parameters already exposed by `LoadStepRequest` — are swept.
- **No sensitivity study for Scenarios B–E** (sustained high load, thermal
  trip, grid sag, grid loss). Scenario A only.
- **No persistence.** Sweep results live only in the current session's UI
  state; no database, no server-side run history.
- **No curve fitting, regression, interpolation, or machine learning**
  across sweep points. Per CLAUDE.md, "Machine learning of any kind" is
  out of scope project-wide; each sweep point is reduced using the
  existing metrics definitions only — no fitted slope, no smoothing, no
  predicted intermediate value, no universal physics claim beyond the
  fixtures actually tested (see §7, §12).
- **No new frontend test framework.** Nothing is added to
  `frontend/package.json` to make this feature testable; verification
  uses the existing stack only (§11).
- **No new framework, chart library beyond what is already used for
  existing telemetry charts, state-management library, or backend
  service** (database, queue, Docker, Kubernetes), per CLAUDE.md's Out of
  Scope list. If an implementer believes a new charting primitive is
  genuinely required where the existing `TelemetryChart` component cannot
  be reused or extended, implementation must stop and ask rather than add
  one unapproved.

## 5. Existing Source-of-Truth Components That Must Be Reused

Nothing below may be reimplemented, duplicated, or approximated by this
feature; every sweep point and the current-value point must go through
these unchanged:

- **`src/simulation.py: run_simulation`** — the only place the electrical
  chain is integrated. A sweep is repeated calls into this (via the
  adapter, via the API), never a parallel calculation.
- **`src/dc_bus.py`, `src/sst.py`** — the governing equations
  (`E_dc = 0.5 * C_dc * V_dc^2`, `dP_sst/dt = (P_target − P_sst) / tau_sst`)
  that give `C_dc` and `tau_sst` their physical meaning. This spec only
  re-samples these at different parameter values; it does not restate or
  re-derive them.
- **`dashboard/adapters/simulation_adapter.py: run_load_step`** — already
  accepts `capacitance_f` and `time_constant_s` as per-run overrides with
  config-isolated, non-mutating behavior (`_base_config` uses
  `dataclasses.replace`, never a shared mutable `Config`).
- **`backend/app.py` `POST /api/v1/simulations/load-step`,
  `backend/schemas.py: LoadStepRequest` / `LoadStepResponse`** — the
  existing, UNCHANGED API boundary and its existing bounds on
  `capacitance_f` (`[0.005, 0.08]`) and `time_constant_s`
  (`[0.005, 0.08]`).
- **`frontend/app/lib/simulationApi.ts: fetchLoadStep`,
  `LoadStepOverrides`** — the existing typed client call. A sweep issues
  this repeatedly (5 times, plus 0 or 1 more for the current value, per
  §6); it does not bypass it or add a parallel request path.
- **`frontend/app/lib/transientMetrics.ts: computeTransientMetrics`** —
  the one place minimum V_dc, max deviation, recovery time, peak deficit,
  and energy deficit are defined. Every sweep point's and the current
  point's metrics must come from this function, never a second,
  independently-written formula.
- **`frontend/app/components/ExperimentPanel.tsx`:
  `CAPACITANCE_RANGE`, `TIME_CONSTANT_RANGE`, `BASELINE_EXPERIMENT_PARAMS`**
  — the existing slider bounds and baseline values. A sweep's range is
  drawn from these, not a newly invented range.
- **`frontend/app/components/TelemetryChart.tsx`** — the existing chart
  component's conventions (dark canvas, hairline gridlines, panel-header
  typography, no toolbar/modebar) should be reused or directly extended
  for the sweep chart rather than introducing a visually distinct charting
  pattern, per `DESIGN.md` §15.

## 6. Functional Behavior

### 6.1 Triggering a sweep

1. The learner can choose to run a **sensitivity sweep** over exactly one
   of `C_dc` or `tau_sst`, from a control placed per §9, without losing or
   replacing the existing single-run detail view.
2. Running a sweep is an explicit action (its own button/control),
   analogous to the existing "Run Experiment" action — never triggered by
   moving a slider.
3. Exactly one sweep result (for one parameter) is shown at a time.
   Choosing to sweep the other parameter replaces the displayed sweep
   result; it does not add a second, simultaneous sweep view (§4).

### 6.2 The 5-point grid (deterministic)

4. A sweep consists of **exactly 5 points**, computed as:

   ```
   value[i] = range.min + i * (range.max - range.min) / 4,   for i = 0, 1, 2, 3, 4
   ```

   where `range` is `CAPACITANCE_RANGE` for a `C_dc` sweep or
   `TIME_CONSTANT_RANGE` for a `tau_sst` sweep (both currently
   `{ min: 0.005, max: 0.08 }`). This always spans the full allowed range
   of the swept parameter (0%, 25%, 50%, 75%, 100%), **independent of the
   learner's current slider value** — the grid does not move based on
   where the learner's slider currently sits.
5. For every one of the 5 grid points, all other Scenario A parameters
   (`initial_fraction`, `final_fraction`, `step_time_s`, `duration_s`,
   `rated_power_w`, `voltage_reference_v`, and whichever of `C_dc` /
   `tau_sst` is *not* being swept) are held fixed at the learner's current
   single-run experiment values (the same values `ExperimentPanel`'s
   `draft` currently holds), so every point answers the same question
   under the same disturbance and the same "other" parameter.

### 6.3 Representing the current experiment value (deterministic)

6. Let `current` be the learner's current value of the swept parameter
   (the value already held in `ExperimentPanel`'s draft state for `C_dc`
   or `tau_sst`).
7. If `current` is exactly equal (bit-for-bit, no tolerance) to one of the
   5 grid values from step 4, that grid point is labeled as **both** a
   grid point and the learner's current value. No additional run is
   issued. The sweep still has exactly 5 data points.
8. Otherwise, exactly one additional run is issued at `current`
   (holding the same other-parameter values as every grid point) and
   added as a 6th, explicitly labeled point ("CURRENT") in both the chart
   and the table. This 6th point never changes the position or value of
   the 5 grid points, and never changes the x-axis spacing between them.
9. Because `ExperimentPanel`'s sliders are themselves bounded by
   `CAPACITANCE_RANGE` / `TIME_CONSTANT_RANGE`, `current` always lies
   within `[range.min, range.max]`; no sweep point ever needs to be
   clamped or extrapolated beyond the grid.

### 6.4 Running the points

10. Every point (the 5 grid points, and the current-value point if
    issued per step 8) is executed as an independent call through the
    existing `fetchLoadStep` client function — the exact same request
    shape, the exact same backend endpoint, the exact same adapter and
    engine call used for a normal single Scenario A run. A sweep differs
    from "click Run Experiment 5 or 6 times and record the numbers" only
    in automation, never in physics or data path.
11. `TransientMetrics` for each point is computed by calling the existing
    `computeTransientMetrics` on that point's response.
12. Running a sweep does not change or reset the single-run detail view's
    currently displayed result; the two coexist, and the single-run view
    is not re-fetched or altered as a side effect of running a sweep.

## 7. Physics Invariants

No new governing equation is introduced anywhere by this feature. The
sweep only re-samples the existing relationships —
`dE_dc/dt = P_sst − P_load`, `E_dc = 0.5 * C_dc * V_dc^2`,
`dP_sst/dt = (P_target − P_sst) / tau_sst` — at different `(C_dc, tau_sst)`
operating points, using the same engine as every existing scenario run.

**Engineering expectation** (qualitative, directional — not asserted as a
universal theorem over arbitrary future controller/model configurations;
see §12 for how this is actually verified):

- Increasing `C_dc` increases the DC link's energy-buffering capacity for
  the same stored-energy swing, and is expected to reduce (or leave
  unchanged) transient voltage severity — minimum V_dc higher, maximum
  deviation smaller — under otherwise-equivalent Scenario A conditions.
  This follows from `E_dc = 0.5 * C_dc * V_dc^2`: for the same energy
  deficit `ΔE`, a larger `C_dc` requires a smaller change in `V_dc` to
  supply it.
- Increasing `tau_sst` slows the SST's power response, leaving the power
  mismatch `P_load − P_sst` open longer, and is expected to increase (or
  leave unchanged) transient voltage severity under otherwise-equivalent
  Scenario A conditions. This follows because a longer mismatch window can
  only increase or leave unchanged the accumulated energy deficit
  `ΔE = ∫(P_load − P_sst) dt`.
- A `C_dc` sweep must hold `tau_sst` identical across every point (and a
  `tau_sst` sweep must hold `C_dc` identical across every point) — the
  sweep never varies both at once (§4).
- The energy-deficit metric for every point (grid or current) must be
  computed by the same existing formula already used for a single run
  (`0.5 * C_dc * (V_ref^2 − minVdc^2)`, per `transientMetrics.ts`'s
  documented definition, using that point's own `C_dc`) — not re-derived
  by numerically integrating the power-mismatch series, which the
  existing module's docstring already explains would silently stop
  matching the one equation a reader can check by hand. This metric is
  already fully defined from existing simulation outputs without
  introducing new physics, so it is included per §4/§6's data
  requirements.

How this expectation is turned into a checkable requirement — fixed,
deterministic test fixtures, not a claim that holds for every possible
future configuration — is specified in §12.

## 8. API/Data-Flow Requirements

- **No new backend endpoint.** `backend/app.py` and `backend/schemas.py`
  are not modified by this feature. The sweep is implemented entirely as
  repeated frontend calls to the existing, unchanged
  `POST /api/v1/simulations/load-step` endpoint — 5 calls for the grid,
  plus 0 or 1 additional call for the current-value point (§6.3).
- No change to `src/` engine contracts or outputs, and no physics
  computation of any kind is added to the frontend. The frontend's only
  new responsibility is: (a) compute the 5 deterministic grid values
  (pure arithmetic over existing range constants, §6.2), (b) issue the
  existing `fetchLoadStep` call for each point, (c) call the existing
  `computeTransientMetrics` on each response, (d) render the results.
- No new or modified schema. `LoadStepRequest`, `LoadStepResponse`,
  `LoadStepOverrides`, and `TransientMetrics` are used exactly as they
  exist today; this feature adds no field to any of them.
- Sweep requests must use parameter values within the same bounds already
  enforced by `LoadStepRequest` (`capacitance_f`, `time_constant_s` both
  `[0.005, 0.08]`) — guaranteed by construction, since the grid is
  computed directly from `CAPACITANCE_RANGE` / `TIME_CONSTANT_RANGE`,
  which already equal those bounds.
- Each point's `TransientMetrics` must come from the existing
  `computeTransientMetrics`; no second, independently-written reduction
  of telemetry is introduced anywhere in this feature.

## 9. UX / Learning Intent

The sensitivity study exists to make visible, as one picture, the causal
chain Scenario A already states in `EngineeringInterpretation.tsx`:

```
AI load step
  -> P_load temporarily exceeds P_sst
  -> DC link supplies the accumulated energy deficit
  -> stored energy decreases
  -> V_dc falls
  -> SST/controller response closes the mismatch
  -> V_dc recovers
```

with `ΔE = ∫(P_load − P_sst) dt` as the quantity linking the mismatch to
the voltage response — and to show that `C_dc` (energy-buffering
capability) and `tau_sst` (source-response dynamics) are exactly the two
knobs that determine how severe and how long that excursion is, not
arbitrary UI sliders disconnected from the physics.

**Placement.** The existing Scenario A page (`frontend/app/page.tsx`)
already follows an observe-first hierarchy: the event banner, KPI strip,
and power-flow schematic (OBSERVE) are followed by
`EngineeringInterpretation`'s "WHY THIS HAPPENED" prose (EXPLAIN), the
synchronized time-scrubbed charts (inspect in detail), and
`TransientMetricsPanel`'s "ENGINEERING RESULT" (ANALYZE), with the
existing `ExperimentPanel` ("Advanced Experiment") as the
EXPERIMENT/ANALYZE step at the bottom. The Sensitivity Study:

- Must be placed **after** `TransientMetricsPanel` (the primary transient
  analysis for the single run), within the same experiment/analysis area
  that already hosts "Advanced Experiment" — e.g. as an additional
  disclosure/section alongside or inside that existing area.
- Must **not** appear above, or be inserted into, the top-level
  observation view (event banner, KPI strip, power-flow schematic) — a
  first-time viewer's initial read of "what happened in this one run"
  must be unaffected by this feature's presence.
- Must preserve this existing OBSERVE → EXPLAIN → ANALYZE → EXPERIMENT
  ordering and the existing `DESIGN.md` visual language exactly: flat,
  dark, hairline borders, no new chromatic accent, IBM Plex Mono for every
  live/tabular number, no shadow/gradient/pill shapes, no decorative
  motion. The "current value" marker/row (§6.3) is distinguished by label
  and/or surface tier/border weight, never by a new color, consistent with
  `DESIGN.md` §9/§19's "selection changes surface tier, not color" rule.
- A sweep is a deliberate, explicit action (its own control), never
  triggered automatically by a slider move, consistent with
  `ExperimentPanel`'s existing "no slider triggers a simulation" rule.

## 10. Acceptance Criteria

- [ ] **AC-001 (deterministic grid):** Running a sweep over a selected
  parameter (`C_dc` or `tau_sst`) produces exactly 5 points, computed as
  `min + i*(max-min)/4` for `i = 0..4` over that parameter's existing
  range (`CAPACITANCE_RANGE` or `TIME_CONSTANT_RANGE`), independent of the
  learner's current slider value for that parameter.
- [ ] **AC-002 (current-value representation):** If the learner's current
  value of the swept parameter exactly equals one of the 5 grid values, no
  additional run occurs and that point is labeled as both a grid point and
  the current value. Otherwise, exactly one additional run is issued at
  the current value and shown as a distinctly labeled 6th point in both
  table and chart, without altering the 5 grid points or their spacing.
- [ ] **AC-003 (no new backend surface):** No new endpoint, route, or
  schema is added to `backend/app.py` / `backend/schemas.py`. Every sweep
  point and the current-value point are issued as individual requests to
  the existing, unmodified `POST /api/v1/simulations/load-step` endpoint.
- [ ] **AC-004 (reused data path, no duplicated physics):** Every point's
  telemetry and metrics are produced by the same `fetchLoadStep` →
  existing API → `run_load_step` → `run_simulation` path, and the same
  `computeTransientMetrics` function, used by a normal single Scenario A
  run — verified by a test comparing a sweep point's result against a
  direct `adapter.run_load_step(...)` call with the same parameters.
- [ ] **AC-005 (required chart):** A chart is rendered with the swept
  parameter's value on the x-axis and maximum V_dc deviation (%) as the
  primary y-axis series, for all points (5 grid points, plus the
  current-value point if issued).
- [ ] **AC-006 (full data table, not hidden behind the chart):** For every
  point shown on the chart, the result view also displays, in a table:
  the swept parameter's value, minimum V_dc, maximum V_dc deviation (V and
  %), recovery time (or an explicit "did not settle" state), and the
  energy-deficit metric (`energyDeficitKj`, per §7).
- [ ] **AC-007 (one sweep at a time):** At most one sweep result (for one
  parameter) is displayed at a time; selecting the other parameter to
  sweep replaces the displayed result rather than showing two sweeps
  simultaneously. No UI path produces a joint `(C_dc, tau_sst)` sweep.
- [ ] **AC-008 (placement and hierarchy preserved):** The Sensitivity
  Study UI is reachable only after `TransientMetricsPanel` in the existing
  page layout and never appears in, or alters, the top-level observation
  view (event banner, KPI strip, power-flow schematic).
- [ ] **AC-009 (baseline preserved):** The existing single-run Scenario A
  baseline (default request, no sweep) produces identical output to its
  pre-change behavior — no existing field, default, or computed value
  changes, and running a sweep never re-fetches or alters the currently
  displayed single-run result.
- [ ] **AC-010 (isolation):** Running a sweep does not mutate any shared
  engine configuration state used by the single-run view (mirrors
  `test_experiment_parameters_do_not_mutate_shared_config`).
- [ ] **AC-011 (fixture-based trend regression, not a universal claim):**
  For a defined, deterministic set of Scenario A sweep fixtures over the
  approved study range (§12), a `C_dc` sweep's results show maximum V_dc
  deviation decreasing or unchanged, and minimum V_dc increasing or
  unchanged, as `C_dc` increases across those fixtures; and a `tau_sst`
  sweep's results show the symmetric opposite trend as `tau_sst`
  increases across those fixtures. This is a regression check against
  named fixtures, not a claim verified for arbitrary configurations.
- [ ] **AC-012 (disclaimer present):** Any view presenting sweep results
  carries the toy-model disclaimer described in §13.
- [ ] **AC-013 (separable, deterministic frontend logic):** The pure
  logic that computes the 5-point grid, decides whether a 6th
  current-value point is needed, and selects data for the chart/table is
  written as separable, side-effect-free functions (no component-local
  inlining that would block later unit testing), without requiring a new
  test framework to be added now.
- [ ] **AC-014 (existing gates hold):** `python -m pytest -q`,
  `npm run lint`, `npm run typecheck`, and `npm run build` all remain
  green, and no existing test is weakened, skipped, or deleted to
  accommodate this feature.

## 11. Deterministic Verification Requirements

Mapped to `ENGINEERING.md`'s four verification layers, and constrained to
the existing verification stack per the Human Engineering Lead's decision
(no new frontend test framework for this spec):

- **Unit-equivalent checks (layer 1), within existing tooling:** the pure
  grid-generation and current-value-dedup logic (AC-001, AC-002, AC-013)
  must be written as plain, separable functions. In the absence of a
  frontend test runner, this is verified by: (a) `npm run typecheck`
  catching type-level errors in these pure functions, and (b) the manual
  scenario-validation check below confirming their output against hand
  computation for at least one concrete range. If a frontend test
  framework is introduced in a later spec, these functions must require
  no refactor to gain direct unit tests (AC-013 exists specifically to
  guarantee this).
- **Physics invariants / fixture regression (layer 2+3, per §12 framing):**
  a Python test (in `tests/`, alongside `tests/test_api.py`) that, for a
  fixed, named set of `capacitance_f` fixture values spanning
  `CAPACITANCE_RANGE` (holding `time_constant_s` and `final_fraction`
  fixed), calls `adapter.run_load_step` for each and asserts the resulting
  minimum-V_dc sequence is non-decreasing and the maximum-deviation
  sequence is non-increasing as `capacitance_f` increases; and a symmetric
  test over fixed `time_constant_s` fixtures asserting the opposite trend.
  These tests are explicit regressions against named fixtures (AC-011),
  not a claim about arbitrary configurations.
- **Regression (layer 3):** the full existing `tests/test_api.py` suite —
  in particular `test_load_step_baseline_reproduces_default_adapter_result`,
  `test_load_step_parity_with_source_of_truth`,
  `test_thresholds_echo_the_capacitance_actually_used`, and
  `test_experiment_parameters_do_not_mutate_shared_config` — must continue
  to pass unmodified (AC-009, AC-010).
- **Reused-data-path check (AC-004):** because no new backend code path
  is introduced (§8), AC-004's "same path as a single run" requirement is
  satisfied by construction plus the existing
  `test_load_step_parity_with_source_of_truth` test, which already proves
  the one endpoint every sweep point calls reproduces the adapter's own
  result exactly. The only new verification needed is a code-level check
  (manual review, part of scenario validation below) that the sweep's
  implementation calls the existing `fetchLoadStep` unmodified for every
  point, rather than constructing its own request/response handling.
- **Scenario validation (layer 4):** a manual run of the Sensitivity Study
  UI locally, confirming: the chart's plotted maximum-deviation-% values
  match the accompanying table (AC-005, AC-006); the current-value
  point/labeling behaves exactly as specified in §6.3 for both the "exact
  match" and "needs a 6th run" cases (AC-002); the UI appears only after
  `TransientMetricsPanel` and never in the top-level observation view
  (AC-008); selecting the other parameter to sweep replaces the displayed
  sweep result rather than showing two sweeps at once (AC-007); the
  sweep's implementation calls the existing `fetchLoadStep` unmodified for
  every point (AC-004, above); and the toy-model disclaimer (§14) is
  visibly present on the sweep results view (AC-012).
- Required commands:
  ```
  python -m pytest -q
  npm run lint
  npm run typecheck
  npm run build
  ```
- Verification results must come from actually running these commands and
  recording pass/fail, per `ENGINEERING.md` — not from an agent's claim
  that "it should pass."

## 12. Regression Requirements

- `tests/test_api.py` must pass **unmodified** — in particular
  `test_load_step_response_schema_shape` (existing response shape is
  unchanged — this feature adds no backend schema), `test_load_step_baseline_reproduces_default_adapter_result`,
  `test_load_step_parity_with_source_of_truth`, and
  `test_experiment_parameters_do_not_mutate_shared_config`.
- **Deterministic sweep fixtures.** A new Python test module (or new tests
  added to an existing one, per implementer's judgment, without altering
  existing tests) must define a fixed, named list of `capacitance_f`
  values spanning `CAPACITANCE_RANGE` and a fixed, named list of
  `time_constant_s` values spanning `TIME_CONSTANT_RANGE` (reusing those
  exact range bounds, not new ones), run Scenario A via
  `adapter.run_load_step` for each, and assert the directional trend
  stated in §7/AC-011. This is a regression requirement against those
  specific, named fixtures — it must not be worded or implemented as a
  general theorem that holds for every possible future controller,
  protection, or model configuration.
- `ExperimentPanel.tsx`'s existing `BASELINE_EXPERIMENT_PARAMS`,
  `CAPACITANCE_RANGE`, and `TIME_CONSTANT_RANGE` must be reused, not
  redefined or duplicated with different values elsewhere (including in
  the new fixture test and the frontend grid-generation logic).
- No existing test assertion may be loosened, removed, or marked
  skipped/xfail to make this feature's implementation pass. If
  implementing this feature appears to require weakening an existing
  test, implementation must stop and report the conflict rather than
  silently resolve it (per CLAUDE.md's Working Agreement and
  `AGENTS.md`'s constraint on Claude Code).
- No new file is added to `backend/` for this feature (§4, §8); a
  regression check confirming `backend/app.py`'s route set is unchanged is
  acceptable but not required if the implementer makes no edits to that
  file at all.
- `.github/workflows/ci.yml`'s existing Python and frontend jobs must
  remain intact; no job is removed or weakened to accommodate this
  feature.

## 13. Human-Owned Decisions

All decisions raised as open in SPEC-002 v0.1 have been resolved by the
Human Engineering Lead as reflected in §3–§12 of this revision:

| # | Decision | Resolution |
|---|---|---|
| 1 | Execution architecture | N client requests through the existing API; no batch endpoint (§4, §8). |
| 2 | Sweep size | Exactly 5 deterministic points (§6.2). |
| 3 | Sweep mode | One parameter at a time; no 2-D, no simultaneous dual sweep (§4, §6.1). |
| 4 | Primary visualization | Chart required; x = swept parameter, primary y = max V_dc deviation (%); full table always shown (§6, §10 AC-005/AC-006). |
| 5 | Baseline/current representation | Deterministic exact-match-dedup vs. 6th labeled run (§6.3). |
| 6 | UI placement | After `TransientMetricsPanel`, within the existing experiment/analysis area; hierarchy and visual language preserved (§9). |
| 7 | Testing | Existing stack only; no new frontend test framework; logic kept separable for future testing (§11, AC-013). |
| 8 | Monotonicity framing | Directional engineering expectation + named-fixture regression, not a universal theorem (§7, §11, §12, AC-011). |
| 9 | Model interpretation | Causal chain and `ΔE` definition retained; toy-model disclaimer retained (§9, §13 below). |

**Remaining open items, still requiring sign-off before this spec can move
to Approved:**

- None of the nine decisions above remain open. No new human-owned
  decision was introduced by this revision.
- A possible future joint `(C_dc, tau_sst)` 2-D sweep/heatmap remains
  explicitly out of scope for V1 (§4) and is noted only as a possible
  future direction, not a pending decision this spec needs resolved now.
- Exact visual/typographic treatment of the chart and table (consistent
  with `DESIGN.md`) is left to implementation, as is normal for a spec
  that does not prescribe implementation detail beyond what an acceptance
  criterion requires.

## 14. Toy-Model Disclaimer

All numerical results produced by this sensitivity study — exact minimum
V_dc values, exact deviation percentages, exact recovery times, and any
apparent trend relating `C_dc` or `tau_sst` to transient severity — are
outputs of this repository's simplified, average-value, lumped-parameter
educational model, under the explicit assumptions and limitations already
documented in `src/sst.py`'s and `src/dc_bus.py`'s module docstrings
(average-value power response, no switching dynamics, constant efficiency,
single-capacitance bus, no cabling impedance) and in CLAUDE.md's Modeling
Rules.

These results must never be represented, in the UI, in documentation, or
in any report derived from this feature, as calibrated, validated, or
representative of any real commercial SST, DC-link design, or
data-center power system. The directional engineering expectation in §7
(more buffering helps, slower response hurts) is a general physical
principle; the exact numbers produced by any sweep are illustrative
outputs of this educational model only, verified here against named test
fixtures (§12), not against real hardware. Any UI surface that presents
sweep results must carry this disclaimer (or an equivalent, no weaker,
restatement consistent with the existing disclaimer language in
`EngineeringInterpretation.tsx`) — it must not be omitted, softened, or
presented only once elsewhere and assumed to carry over.
