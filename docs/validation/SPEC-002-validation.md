# SPEC-002 — Scenario A Sensitivity Study — Validation Record

## Context

- Spec: `docs/specifications/SPEC-002-scenario-a-sensitivity-study.md`
  (header says Status: Approved; §1's revision note still says "Status
  remains Draft pending final sign-off" — a pre-existing inconsistency in
  that document, not introduced by this record; flagged here rather than
  silently edited, per `ENGINEERING.md`'s Source-of-Truth Hierarchy).
- This record closes SPEC-002 against the two Codex MINOR findings from
  independent review, plus the required scenario validation (layer 4) and
  the four required verification commands (§11).
- Nothing in this pass changed backend physics, the API, or redesigned the
  UI. No commit, push, PR, or Codex invocation was made as part of this
  pass.

## Codex MINOR findings — remediation status

Both findings below were already correctly addressed in the working
tree's implementation at the start of this pass; this pass verified each
by code inspection against the spec's exact requirement rather than
re-implementing anything.

### Finding 1 (MINOR) — exact-grid-and-current chart point must keep both roles

**Requirement:** per AC-002/§6.3, a sweep point that is simultaneously a
grid point and the learner's current value must be labeled as **both**
("GRID · CURRENT"), consistently between the table and the chart.

**Verified location:** `frontend/app/lib/sensitivitySweep.ts::roleLabel`
returns `"GRID · CURRENT"` when `point.isGrid && point.isCurrent`, `
"CURRENT"` when only `isCurrent`, else `"GRID"`. The table
(`frontend/app/components/SensitivityStudy.tsx`'s `SweepResults`, table
`<td>`) calls `roleLabel(p)` for every row. The chart's `pointMarkers`
label (`label: p.isCurrent ? roleLabel(p) : ""`) calls the same
`roleLabel(p)` for the current point — so an exact-match point renders
`"GRID · CURRENT"` in the chart, identical to the table, preserving both
roles rather than collapsing to `"CURRENT"` alone.

**Status: RESOLVED (confirmed present).** `grep` across `frontend/app`
confirms `roleLabel` is defined once and consumed only at these two call
sites — no second, divergent labeling path exists.

### Finding 2 (MINOR) — regression-fixture source-of-truth drift risk

**Requirement:** the Python fixture-regression test's hardcoded range
bounds and held-fixed baseline values (§12) must not silently drift from
the approved declarations they claim to test, without introducing new
architecture or duplicating product physics.

**Verified location:**
`tests/test_scenario_a_sensitivity.py::test_fixture_constants_match_authoritative_declarations`
asserts, using only existing declarations (no new mechanism):
- `RANGE_MIN`/`RANGE_MAX` equal `LoadStepRequest.model_fields["capacitance_f"]`
  and `["time_constant_s"]`'s `ge`/`le` bounds (read directly off the
  Pydantic field metadata — the same bounds the API actually enforces).
- `FIXED_FINAL_FRACTION` equals `LoadStepRequest.model_fields["final_fraction"].default`.
- `FIXED_CAPACITANCE_F`/`FIXED_TIME_CONSTANT_S` equal
  `load_config("config/default.yaml").dc_bus.capacitance_f` /
  `.sst.time_constant_s`.

If any of these approved declarations ever changes, this test fails
loudly instead of leaving the fixture module silently testing a range or
baseline that no longer matches the system it claims to describe. This
is the smallest mechanism available (a direct equality assertion against
fields/config already read by the module under test) — no shared
constants file, code generator, or cross-language sync layer was added,
and no governing equation is restated.

**Status: RESOLVED (confirmed present).** Ran
`python -m pytest tests/test_scenario_a_sensitivity.py -v` directly (see
below) — all 5 tests in the module pass, including this consistency
check.

## Manual browser validation (scenario validation, layer 4)

Performed by the Human Engineering Lead (per `ENGINEERING.md`: AI review
or an agent's own claim of "done"/"working" is not itself validation
evidence — this is recorded here as the human-performed scenario check
the spec's §11 "Scenario validation" layer requires):

- `C_dc` sweep rendered successfully: chart, table, current-value point,
  metrics, and the toy-model disclaimer all present (AC-005, AC-006,
  AC-012).
- `tau_sst` sweep rendered successfully.
- `tau_sst` showed the expected directional behavior: larger `tau_sst`
  produced a larger maximum `V_dc` deviation and a longer recovery time,
  with high-`tau_sst` cases not settling within the simulation window
  (consistent with §7's engineering expectation and AC-011's fixture
  trend).
- Switching the swept parameter worked, and only one sweep result was
  shown at a time (AC-007).
- Sweep results remained separate from, and did not alter, the primary
  single-run experiment state (AC-009, AC-012 isolation intent).

**Deferred, not a functional blocker for this closure:** visual-polish
items such as chart axis-label density are deferred to the planned
Pixso-driven visual redesign. This spec's acceptance criteria are
functional/data-correctness criteria (§10); no AC concerns axis-label
density.

## Verification commands and results

```
$ python -m pytest -q          (project .venv)
335 passed, 7 skipped, 1 warning in 24.07s
```
The one warning is the pre-existing `StarletteDeprecationWarning` from
`fastapi.testclient`, unrelated to this work.

```
$ python -m pytest tests/test_scenario_a_sensitivity.py -v   (.venv, ad hoc re-run for this record)
test_fixture_constants_match_authoritative_declarations PASSED
test_sweep_grid_fixture_matches_spec_and_stays_in_bounds PASSED
test_capacitance_sweep_fixtures_trend PASSED
test_time_constant_sweep_fixtures_trend PASSED
test_sweep_does_not_mutate_shared_config PASSED
5 passed
```

```
$ npm run lint        (frontend/)
clean, exit 0
```

```
$ npm run typecheck   (frontend/)
✓ Types generated successfully, no errors
```

```
$ npm run build       (frontend/)
✓ Compiled successfully
Route (app): / and /_not-found, both ○ (Static)
```

All four of SPEC-002 §11's required commands pass (AC-014).

## Finding matrix

| # | Severity | Finding | Status | Evidence |
|---|----------|---------|--------|----------|
| 1 | MINOR | Exact-grid-and-current chart point lost one of its two roles | **RESOLVED** (confirmed already correctly implemented) | `frontend/app/lib/sensitivitySweep.ts::roleLabel`; consumed identically by `SensitivityStudy.tsx`'s table and chart `pointMarkers` |
| 2 | MINOR | Regression-fixture bounds/baseline could silently drift from the approved API/config declarations | **RESOLVED** (confirmed already correctly implemented) | `tests/test_scenario_a_sensitivity.py::test_fixture_constants_match_authoritative_declarations` |

## Scope confirmation

Changed by this pass: this document only. No source file under
`frontend/`, `backend/`, `src/`, `dashboard/`, `tests/`, `peos/`, or
`config/` was modified — both findings' required behavior was already
present and was verified by direct code inspection plus a live re-run of
the relevant tests, not re-implemented. No commit, push, PR, or Codex
invocation was made.
