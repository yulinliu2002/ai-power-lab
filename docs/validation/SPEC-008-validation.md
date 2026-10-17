# SPEC-008 — AI Power Lab Protection & Ride-Through Timeline — Validation Record

## Context

- Spec: `docs/specifications/SPEC-008-ai-power-lab-protection-ride-through-timeline.md`
  (v0.5, Codex Round 3 verdict `APPROVE`, 0 blocking/0 major/0 minor open).
- This record covers implementation of SPEC-008 end-to-end: the derived
  Protection Timeline module, the one new backend endpoint plus the
  additive `LoadStepResponse` field, the frontend scenario selector and
  Protection Timeline presentation, and all required verification layers
  (AC-026).
- No `src/` file was changed (AC-005). No existing `tests/test_api.py`
  assertion changed except the one explicitly authorized key-set literal
  (AC-007). `docs/validation/SPEC-005-validation.md` was not touched.

## Files changed

- `dashboard/adapters/protection_timeline.py` (new) — pure derived-data
  module: `StateSegment`/`TimelineEvent`/`ProtectionTimeline` dataclasses,
  `RideThroughOutcome`/`RecoveryStatus` enums, `build_protection_timeline`.
- `tests/test_protection_timeline.py` (new) — 23 tests (real scenarios +
  constructed fixtures).
- `backend/schemas.py` — added `StateSegmentModel`, `TimelineEventModel`,
  `ProtectionTimelineModel`, `ProtectionScenarioThresholds`,
  `ProtectionScenarioResponse`; added `protection_timeline` to
  `LoadStepResponse`.
- `backend/app.py` — added `GET /api/v1/simulations/protection-scenarios/{scenario}`;
  wired `protection_timeline` into `simulate_load_step`.
- `tests/test_api.py` — extended with endpoint/parity/reconciliation
  tests; the one authorized change to
  `test_load_step_response_schema_shape`'s key-set literal (AC-007).
- `frontend/app/lib/simulationApi.ts` — added `StateSegment`,
  `TimelineEvent`, `ProtectionTimeline`, `ProtectionScenarioThresholds`,
  `ProtectionScenarioResponse`, `ScenarioName`, `ScenarioRunResponse`
  types; `fetchProtectionScenario`, `fetchScenario`; `LoadStepResponse`
  gained `protection_timeline`; `sampleAt` widened to accept either
  response shape.
- `frontend/app/components/ProtectionTimeline.tsx` (new).
- `frontend/app/components/ScenarioSelector.tsx` (new).
- `frontend/app/components/TelemetryChart.tsx` — bug fix found during
  manual verification (see below).
- `frontend/app/page.tsx` — scenario selector wiring, scenario-dependent
  fetch dispatch, Scenario-A-only conditional rendering, universal
  Protection Timeline rendering.

## Bug found and fixed during manual verification

`TelemetryChart.tsx`'s y-axis range computation used
`Math.min(...allValues)`/`Math.max(...allValues)`. Scenario A's 6,000-sample
series never exercised this, but Sustained High Load's real default run
(200 s at 1 ms) produces 200,000 samples — spreading that many values as
call arguments exceeded the JS engine's call-stack/argument limit
(`RangeError: Maximum call stack size exceeded`), crashing the chart for
that scenario. Fixed by replacing the spread with a plain `reduce` scan
(same result, no argument-count limit). This is a mechanical rendering
fix with no engineering-content change; confirmed fixed by the manual
browser pass below and by `npm run build` succeeding.

## Codex implementation review — Round 1

An independent Codex implementation review (standalone, read-only,
`codex exec --sandbox read-only`, against the actual diff and an
independent re-run of the deterministic suite) returned
`CHANGES_REQUIRED`, 0 blocking / 3 major / 5 minor. All are reconciled
below; see the commit for the applied fixes.

| # | Severity | Finding | Disposition |
|---|---|---|---|
| 1 | Major | `_describe_outcome`'s `PROTECTION_TRIP` text always said "before" the floor was reached, even for an exact-timestep tie, misstating §9's documented non-causal tie-break as a causal one. | **FIXED** — `_describe_outcome` now takes both candidate times and words the tied case as an explicit, non-causal convention; a new assertion in `test_exact_timestep_tie_breaks_toward_protection_trip` checks the detail text never says "before" and does name the tie. |
| 2 | Major | `tests/test_api.py`: the new tests were inserted inside `test_load_step_parity_with_source_of_truth`'s body, silently moving its final `events`-parity assertion into the unrelated new `test_protection_scenario_grid_sag_includes_genuine_input_events`, so the original test lost that coverage (AC-007 violation beyond the one authorized line). | **FIXED** — the two misplaced lines were restored to the end of `test_load_step_parity_with_source_of_truth` and removed from the Grid Sag test. `git diff tests/test_api.py` now shows exactly one changed line in the whole file (the authorized key-set literal); every other line is a pure addition. |
| 3 | Major | `page.tsx`: a slow `RUN EXPERIMENT` (Scenario A) response could resolve after the user switched to a different scenario and unconditionally overwrite that scenario's state with Load Step's, violating AC-009 ("no stale value is ever shown"). | **FIXED** — added a monotonically increasing request-generation ref; every fetch (initial load, scenario selection, experiment run) only applies its result if it is still the latest request when it resolves. Verified with a scripted race (fire Run Experiment, immediately switch to Grid Sag): the displayed outcome banner and `aria-checked` state remain Grid Sag's, never overwritten. |
| 4 | Minor | `tests/test_protection_timeline.py`'s AC-003 coverage parsed the config value out of a `DERATED` transition's detail only, not `RUNNING`/`TRIPPED`. | **FIXED** — added `test_running_resumes_transition_detail_names_the_exact_config_value` and `test_tripped_transition_detail_names_the_exact_config_values`. |
| 5 | Minor | `backend/app.py` passes `[]` (a list), not a literal `()` tuple, for Thermal Trip's reconciled `input_events`, against §11's "passes an empty tuple" wording. | **ACCEPTED, not changed.** `protection_timeline.py`'s own `EventMarkers = list[tuple[float, str]]` type (matching `simulation_adapter.EventMarkers`/`scenarios/plotting.py`'s existing alias) is a `list` type; passing `()` would be the type mismatch, not `[]`. §11's parenthetical "empty tuple" is describing the *content* (zero genuine input events) informally, not mandating the Python `tuple` builtin over the declared `list` parameter type. |
| 6 | Minor | `backend/schemas.py`'s `protection_timeline` field on `LoadStepResponse` is a required field, not an `Optional`/nullable type, against §11's "one new, **optional**, additive field" wording. | **ACCEPTED, not changed.** The backend always computes this field for every Scenario A response (there is no code path where it is absent); making it nullable would misrepresent actual behavior. §11's own next sentence clarifies "optional" means "no endpoint behavior changes for a caller that ignores the new field" (additive/non-breaking for existing consumers), not that the field can be missing or `null` — consistent with every other additive field in this API (none use `Optional`). |
| 7 | Minor | `ProtectionTimeline.tsx` showed an open-ended segment's duration without §10's required "at least" wording (only the separate "(ongoing)" suffix, satisfying AC-012 but not §10's stronger duration-wording requirement). | **FIXED** — open-ended segments now render "at least X.XXX s (ongoing)"; confirmed present in a fresh manual browser pass. |
| 8 | Minor | This validation record's first draft stated "42 passed" for `tests/test_api.py`; the actual count is 29 (52 total with `test_protection_timeline.py`'s 23). | **FIXED** — corrected below. |

No blocking findings. All 3 major findings were genuine correctness
defects and are fixed; both accepted-without-change minors are
documented-rationale dispositions of spec-wording ambiguity, not
functional gaps.

## Codex implementation review — Round 2

A focused closure review of Round 1's 8 dispositions (not a fresh broad
review) independently confirmed 6 of 8 `CLOSED` as described, found 1
`PARTIALLY CLOSED` (this record's own stale test-count reference in the
file list below, now corrected), and found one **new** defect introduced by Round 1's
own stale-request-generation fix:

| # | Severity | Finding | Disposition |
|---|---|---|---|
| New | Major | `runExperiment`'s `.finally()` now skips `setIsRunning(false)` when its request has been superseded (correctly, to avoid a stale write) -- but `selectScenario` never reset `isRunning` itself, so switching scenarios mid-experiment and returning to Load Step left "RUN EXPERIMENT" permanently disabled. | **FIXED** — `selectScenario` now resets `isRunning`/`runError` directly when a new scenario is selected (a no-op unless an experiment was actually in flight). Verified with a scripted repro (start experiment -> switch away -> return to Load Step -> confirm the button is enabled again). |
| 8 (residual) | Minor | This record's file-list line for `tests/test_protection_timeline.py` still showed the original (pre-fix) test count after the count elsewhere in this same record was corrected to 23. | **FIXED** — corrected; the outdated count no longer appears anywhere in this record. |

Final verification after both rounds: `python -m pytest -q` passes in
full; `npm run lint && npm run typecheck && npm run build` all clean;
the 37-check manual browser pass and the targeted race/stuck-state
scripted repros all pass. See the commit for the final diff.

## Deterministic verification (AC-001–AC-007, AC-015–AC-019, AC-025)

    python -m pytest tests/test_protection_timeline.py -q   # 23 passed
    python -m pytest tests/test_api.py -q                   # 29 passed
    python -m pytest -q                                      # 676 passed, 7 skipped (pre-existing, unrelated)

All five real scenarios' outcome/recovery pairs match §0's table exactly
(confirmed by direct adapter execution, not assumed):

| Scenario | Outcome | Recovery |
|---|---|---|
| Load Step | RIDE_THROUGH | RECOVERED |
| Sustained High Load | RIDE_THROUGH | RECOVERED |
| Thermal Trip | BUS_COLLAPSE_UNPROTECTED (floor at 14.446 s, before TRIPPED at 46.147 s) | NOT_RECOVERED |
| Grid Sag | BUS_COLLAPSE_UNPROTECTED | RECOVERED |
| Grid Loss | BUS_COLLAPSE_UNPROTECTED | NOT_RECOVERED |

`PROTECTION_TRIP` and the exact-timestep tie-break (unreachable by any
real scenario default, per §0) are covered only by constructed fixtures
(AC-019), as the spec requires.

## Frontend static verification (AC-021, AC-024)

    cd frontend && npm run lint        # clean
    cd frontend && npm run typecheck   # clean
    cd frontend && npm run build       # succeeds

No new test runner was added (none exists in this repository today;
adding one is outside this specification's authority per `CLAUDE.md`).

## Manual verification checklist (Category C — SPEC-006 §6 taxonomy)

Performed once against a running dev server (`uvicorn backend.app:app
--port 8000` + `npm run dev`), driven with Playwright (chromium,
headless) as a keyboard-only user — this is genuine manual/scripted
browser evidence, not a PEOS Runtime Verification claim (PEOS's fixed
catalog cannot drive the scenario selector; see "Runtime Verification"
below). 37/37 checks passed on the final run (after the `TelemetryChart`
fix above):

1. **Initial load (AC-008, AC-011):** scenario selector (`role="radiogroup"`,
   `data-testid="scenario-select"`) present with Load Step selected by
   default; Protection Timeline and outcome banner present on first paint.
2. **Keyboard-only selection, all 5 scenarios (AC-008, AC-009):** each
   option reached and activated via Tab + Enter only; a loading
   placeholder appears between selections (no stale KPI/chart/Timeline
   values held over); outcome banners differ meaningfully across
   scenarios and match §0's table (Sustained High Load → "Rode through
   cleanly"; Thermal Trip/Grid Loss → "Bus energy exhausted —
   unprotected" / "Did not recover"; Grid Sag → "...unprotected" /
   "Recovered to nominal").
3. **Mobile viewport, Thermal Trip + Grid Sag (AC-022):** 375px width,
   `document.documentElement.scrollWidth` equals `clientWidth` for both
   — no horizontal overflow.
4. **Scenario-A-only sections (AC-010, §13.3):** "THE EVENT" banner, "WHY
   THIS HAPPENED", "ENGINEERING RESULT", and "Advanced Experiment" are
   absent for a non-Load-Step scenario and reappear unchanged when
   Load Step is reselected.
5. **Universal educational caption (AC-020):** present, verbatim, for
   every one of the five scenarios.

No console/page errors were observed on the final run.

## Runtime Verification (SPEC-006 catalog) — honest coverage

    runtime: page_load path=/ landmarks="[data-testid='scenario-select'],[data-testid='protection-timeline'],[data-testid='outcome-banner']" ac=AC-008 ac=AC-011
    runtime: viewport_overflow viewport=desktop ac=AC-022
    runtime: viewport_overflow viewport=mobile ac=AC-022

This covers only the default-loaded (Load Step) page's static
presence/responsiveness. `experiment_run` cannot express scenario
selection (SPEC-008 §18/§19 — a standing PEOS V1 capability gap, not a
defect of this feature); no claim is made that this is automated by
PEOS. The scenario-selector interaction, per-scenario content fidelity,
and mobile layout for non-default scenarios are instead covered by the
manual checklist above.

## PEOS dogfood findings (not SPEC-008 product requirements)

1. **Runtime-interaction capability gap** (SPEC-008 §19.1) — recorded,
   not closed, per Engineering Lead Decision 7.
2. **Disk hygiene** (SPEC-008 §19.2) — recorded; no PEOS infrastructure
   change was made as part of this implementation.

## Known limitations (carried from SPEC-008 §20, unchanged by implementation)

- V1 has no DC-bus undervoltage/overvoltage protection;
  `BUS_COLLAPSE_UNPROTECTED` narrates this pre-existing model gap, it
  does not close it.
- `recovery` is binary (`RECOVERED`/`NOT_RECOVERED`/`NOT_APPLICABLE`); no
  `PARTIAL` tier (open Human Gate, SPEC-008 §15 item 2).
- No real scenario in this repository exercises `PROTECTION_TRIP` under
  the ordered-event rule; that branch's correctness rests on constructed
  fixtures only (AC-019).
- No frontend automated test coverage (no test runner installed).
- No persistence of the selected scenario across a page reload.
