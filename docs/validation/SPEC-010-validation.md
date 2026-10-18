# SPEC-010 — Scenario Comparison & System Stress Analysis — Validation Record

## Context

- Spec: `docs/specifications/SPEC-010-scenario-comparison-system-stress-analysis.md`
  (v0.5, Codex architecture-review Round 5 verdict `APPROVE`, 0 blocking/0 major/0 minor
  open across the full five-round review history).
- This record covers implementation of SPEC-010 end-to-end: the new, pure
  `dashboard/adapters/scenario_comparison.py` module (`StressProfile`, `DominantStress`,
  `build_stress_profile`), additive `backend/schemas.py` models, one new endpoint
  (`GET /api/v1/simulations/comparison`), additive frontend types/API client, the new
  `ScenarioComparison.tsx`/`ViewModeToggle.tsx` components, and all required
  verification layers (AC-039–AC-051).
- No `src/` file was changed (AC-047, verified below). No existing `tests/test_api.py`
  assertion changed; all new assertions are additive. `docs/validation/SPEC-005-validation.md`
  was not touched.

## Files changed

- `dashboard/adapters/scenario_comparison.py` (new) — `DominantStress` enum,
  `StressProfile` dataclass, `build_stress_profile`. Pure, side-effect-free; imports
  `src.dc_bus.energy_from_voltage` only (same import class `protection_timeline.py`
  already uses for its sibling function). Never calls `build_protection_timeline`.
- `backend/schemas.py` — additive: `StressProfileModel`, `ScenarioComparisonEntry`,
  `ScenarioComparisonResponse`. No existing model changed.
- `backend/app.py` — additive: `_protection_scenario_thresholds` /
  `_serialize_stress_profile` helpers, `_COMPARISON_SCENARIOS` fixed-order dispatch
  tuple, `GET /api/v1/simulations/comparison`. Neither existing endpoint
  (`simulate_load_step`, `simulate_protection_scenario`) was changed.
- `tests/test_scenario_comparison.py` (new) — 27 tests covering AC-039–AC-042 across
  all five real scenarios plus two constructed fixtures (energy-excursion clamp,
  `PROTECTION_TRIP` taxonomy branch).
- `tests/test_api.py` — additive: `_COMPARISON_SCENARIOS`/`_STRESS_PROFILE_FIELDS`/
  `_stress_profile_to_dict` helpers and 7 new tests for AC-044/AC-045. No existing
  assertion changed.
- `frontend/app/lib/simulationApi.ts` — additive: `StressProfile`,
  `ScenarioComparisonEntry`, `ScenarioComparisonResponse` interfaces,
  `fetchScenarioComparison`. No existing interface/function changed.
- `frontend/app/components/ScenarioComparison.tsx` (new) — the comparison matrix.
- `frontend/app/components/ViewModeToggle.tsx` (new) — the "Single Scenario" /
  "Compare All" two-way toggle (SPEC-010 §8/§12).
- `frontend/app/components/ProtectionCoverageChecklist.tsx` (new) — `CoverageChecklist`
  extracted unchanged from `ProtectionCoordination.tsx` so `ScenarioComparison.tsx` can
  reuse the identical presentation (`coverage` is static/identical across all five rows,
  rendered once, SPEC-010 §8) without a second implementation.
- `frontend/app/components/ProtectionCoordination.tsx` — imports `CoverageChecklist`
  from the new shared module instead of defining it locally; no other line changed.
- `frontend/app/page.tsx` — additive: `viewMode`/`comparisonState` state, the
  `selectViewMode` handler (own request-generation guard, independent of
  `requestGenerationRef`), the `ViewModeToggle` control, and the conditional
  Compare-All/Single-Scenario render branch. The existing single-scenario `Console`
  and its own request-generation logic are unchanged.

## AC-039 — `StressProfile` correctness, real scenarios

**Method:** `tests/test_scenario_comparison.py::test_stress_profile_matches_direct_computation`,
parametrized over all five real scenarios; every numeric field computed by direct
`Telemetry` reduction (`.min()`/`.max()`/`np.abs(...).max()`/`any()`), independent of
`build_stress_profile`'s own implementation.
**Result:** PASS (5/5 scenarios).

## AC-040 — energy-excursion correctness + cross-check invariant

**Method:** `test_energy_excursion_sourced_from_e_dc_j` (primary value vs.
`max(0, energy_from_voltage(V_ref, C) - min(telemetry.e_dc_j))`, tolerance `1e-6` J) and
`test_energy_excursion_cross_check_invariant` (cross-check closed-form equation vs. the
primary value, tolerance `1e-9` J), both parametrized over all five real scenarios;
`test_energy_excursion_clamps_at_zero_when_min_energy_exceeds_nominal` (constructed
fixture, `min(e_dc_j) > nominal`) asserts the clamp returns exactly `0.0`.
**Result:** PASS (5/5 + 1 fixture). Direct execution (`GET /api/v1/simulations/comparison`)
confirms Load Step = `1323.387` J, Sustained High Load = `0.0` J, Thermal Trip/Grid
Sag/Grid Loss = `6399.0` J each (all three saturate at the identical numerical floor,
exactly as SPEC-010 §11 states) — reproducing the same values SPEC-010 §0/§14's Round 2
Codex review independently re-derived.

## AC-041 — `protection_states_reached` correctness

**Method:** `test_protection_states_reached`, parametrized over all five real scenarios,
against the expected first-occurrence-order tuples SPEC-010 §9 states.
**Result:** PASS. Load Step/Grid Sag/Grid Loss = `("RUNNING",)`; Sustained High Load =
`("RUNNING", "DERATED")`; Thermal Trip = `("RUNNING", "DERATED", "TRIPPED")`.

## AC-042 — `dominant_stress` taxonomy, real scenarios + fixture

**Method:** `test_dominant_stress_real_scenarios` (all five real scenarios) and
`test_dominant_stress_protection_trip_fixture` (constructed `PROTECTION_TRIP` fixture,
reusing `tests/test_protection_timeline.py`'s existing AC-019 fixture pattern).
**Result:** PASS. Load Step → `TRANSIENT_POWER_IMBALANCE`; Sustained High Load →
`SUSTAINED_THERMAL_DERATING`; Thermal Trip/Grid Sag/Grid Loss → `DC_BUS_VIABILITY_LOSS`;
constructed fixture → `THERMAL_PROTECTION_TRIP`.

## AC-043 — no competing event model, precisely scoped

**Method:** reviewer code-read (not a pytest check, per SPEC-010 §9's own note that grep
alone cannot establish this absence). `backend/app.py::simulate_comparison` calls
`build_protection_timeline` exactly once per scenario, and that same `timeline` object is
passed to both `ScenarioComparisonEntry.protection_timeline`'s serialization and
`build_stress_profile`. `scenario_comparison.py`'s full source contains no `if`/`match`
branch testing `trip_active`, `v_dc_v`, or any other raw telemetry field against a
threshold — its only classification input is the already-computed `timeline.outcome` and
`timeline.segments`.
**Result:** Self-verified by code inspection at implementation time; independent
confirmation is part of the Codex implementation review before Human Gate (per
`ENGINEERING.md`'s Definition of Done — independent review distinct from the implementer).

## AC-044 — endpoint correctness/parity

**Method:** `test_comparison_returns_all_five_scenarios_in_fixed_order`,
`test_comparison_entry_matches_direct_build` (parametrized over all five scenarios,
comparing the endpoint's `protection_timeline`/`stress_profile` against direct
`build_protection_timeline`/`build_stress_profile` calls on the same adapter run).
**Result:** PASS. Fixed order confirmed: `load_step`, `sustained_high_load`,
`thermal_trip`, `grid_sag`, `grid_loss`.

## AC-045 — schema key-set test

**Method:** `test_comparison_response_schema_shape` — top-level `{"scenarios"}` and, per
entry, `{"scenario", "thresholds", "protection_timeline", "stress_profile"}` plus the full
13-field `StressProfileModel` key set.
**Result:** PASS.

## AC-046 — frontend/backend field parity

**Method:** explicit field-for-field diff (not `tsc --noEmit` alone, per SPEC-010's own
corrective note), performed by direct comparison of `backend/schemas.py` against
`frontend/app/lib/simulationApi.ts`:

| Backend (`schemas.py`) | Frontend (`simulationApi.ts`) | Match |
|---|---|---|
| `StressProfileModel` (13 fields: `min_v_dc_v`...`dominant_stress_detail`) | `StressProfile` (same 13 fields) | ✓ |
| `ScenarioComparisonEntry` (`scenario`, `thresholds`, `protection_timeline`, `stress_profile`) | `ScenarioComparisonEntry` (same 4 fields) | ✓ |
| `ScenarioComparisonResponse` (`scenarios: list[...]`) | `ScenarioComparisonResponse` (`scenarios: [...]`) | ✓ |

`dominant_stress`'s backend `str` vs. frontend 4-member string-literal union is the same,
already-established convention as `outcome`/`recovery` elsewhere in this file — not a
parity gap.
**Result:** PASS (18 fields verified). `cd frontend && npm run typecheck` additionally
passes with no errors.

## AC-047 — no `src/` change

**Method:** `git diff --stat -- src/` at the repository root.
**Result:** PASS — empty output (no file in `src/` appears in this feature's diff).

## AC-048 — lint/typecheck/build

**Method:** `cd frontend && npm run lint && npm run typecheck && npm run build`.
**Result:** PASS — all three commands exit 0, no new errors/warnings. Production build
completes (`✓ Compiled successfully`, static page generation succeeds).

## AC-049 — full-suite regression

**Method:** `python -m pytest -q` at the repository root.
**Result:** PASS — `736 passed, 7 skipped` (the 7 skips are pre-existing, unrelated to
this feature). All existing SPEC-008/009 tests pass unchanged.

## AC-050 — responsive/accessibility, populated Compare-All state

**Method:** direct scripted Playwright (Python `playwright.sync_api`, outside the fixed
PEOS catalog, per SPEC-010 §10's own recommendation — not claimed as PEOS Runtime
Verification evidence). Script: toggled into "Compare All", waited for all five rows to
render, then resized to `mobile` (390×844, matching `peos/runtime_catalog.py:
VIEWPORT_PRESETS["mobile"]`) with the table already populated.
**Result:** PASS.
- Desktop (1280×900), Compare-All populated: `document.documentElement.scrollWidth <=
  clientWidth` (no page-level overflow).
- Mobile (390×844), Compare-All populated: same assertion holds (no page-level overflow);
  the table's own `overflow-x-auto` container independently confirmed scrollable
  (`scrollWidth > clientWidth` inside the container only).
- No state/outcome/dominant-stress/emphasized-cell value is conveyed by color alone —
  every status dot is paired with its text label (`outcome_label`), and every emphasized
  numeric cell keeps its plain number plus a `title` attribute naming why.
- Zero console errors, zero page errors, across the full interaction sequence below.

Full interaction sequence verified by the same script (`/tmp` scratch script, not
committed — SPEC-010 §10 does not require committing this script to the repository):
page load → enter Compare All → comparison data appears → all five scenario rows present
→ exit Compare All (single-scenario view restored) → individual scenario selection still
works (`grid_loss` selected, header/outcome-banner update correctly) → rapid
compare/single/compare toggling settles on a consistent, non-stale Compare-All render →
desktop viewport, no overflow → mobile viewport (390×844), no overflow. All steps PASS.

**Additional ~375px evidence (375×812, closing the gap between the governing brief's
"around 375px" request and the first round's 390×844 evidence):** a second, separate
scripted-Playwright run at 375×812 verified, with Compare All already populated: page
load (no page-level overflow) → Compare All entered → all five rows present and
individually visible/readable → comparison table's own `.overflow-x-auto` container
confirmed internally scrollable (`scrollWidth=2350px > clientWidth=325px`) while
`document.documentElement.scrollWidth <= clientWidth` (no page-level overflow) → exit
Compare All → individual scenario selection still functional (`grid_sag` selected,
header updates correctly, no overflow). Zero console errors, zero page errors across the
full sequence. No defect was found at this width; no UI change was made to pass it.

**Honest PEOS Runtime Verification evidence (partial, as SPEC-010 §10 states it must be):**
the actual `peos/runtime_browser.py` check-kind functions (`run_page_load_check`,
`run_viewport_overflow_check`) were invoked directly (not via the full orchestrated
round/catalog machinery, and not claimed as a catalog-driven run) against the running
dev servers:
- `page_load` (`/`, landmarks `scenario-select`, `view-mode-toggle`,
  `protection-timeline`, default Single-Scenario DOM only): **PASS** — all 3 landmarks
  present and ordered.
- `viewport_overflow` at `desktop` and `mobile` presets (default Single-Scenario state
  only — this check kind cannot click into Compare All): **PASS** both.
This provides zero coverage of the populated Compare-All table by itself (SPEC-010 §10's
own stated gap) — the direct Playwright script above is AC-050's actual load-bearing
evidence.

## Independent Codex implementation review — Round 1

**Method:** `codex exec --sandbox read-only`, stdin closed (`< /dev/null`), launched
non-interactively with a dedicated log file; verified a real model turn began (rollout
session file created and growing within seconds, non-zero CPU) before waiting for
completion. Scope: all 14 review-scope items listed in SPEC-010's own implementation
brief (architecture fidelity, metric provenance, `StressProfile` correctness,
`DominantStress`, protection/event reuse incl. independent AC-043 re-confirmation,
energy-floor honesty, backend/API, frontend/backend parity, UI semantics, async/race
behavior, regression safety, testing sufficiency, Charter alignment, confidentiality).

**Verdict:** `CHANGES_REQUIRED`, 0 blocker / 1 major / 1 minor.

| # | Severity | Finding | Disposition |
|---|---|---|---|
| 1 | Major | `_describe_dominant_stress`'s `THERMAL_PROTECTION_TRIP` detail unconditionally said "before any bus-energy numerical-floor contact," even when the floor was never reached at all, or reached at the exact same sample as the trip (an explicit, non-causal tie per SPEC-008 §9) — contradicting the authoritative timeline's own tie-break wording. | **CLOSED.** `scenario_comparison.py::_describe_dominant_stress` now branches on `bus_collapse_event_time_s` being `None` / equal to / strictly later than `trip_event_time_s`, mirroring `protection_timeline.py::_describe_outcome`'s own three-way relation wording exactly. Three new tests added (`test_dominant_stress_protection_trip_fixture` extended with a "never reached" assertion, plus two new fixtures: later-floor-contact and exact-timestep-tie, the latter reusing `test_protection_timeline.py`'s own tie fixture pattern). |
| 2 | Minor | Null `trip_event_time_s`/`bus_collapse_event_time_s` cells in `ScenarioComparison.tsx` rendered `—` with no `title`/tooltip explaining why, though SPEC-010 §8 requires one. | **CLOSED.** Both cells now carry a `title` attribute (verbatim text from SPEC-010 §5's own "Null/missing semantics" column) when the value is `null`. Verified by direct Playwright DOM inspection. |

**Independent findings Codex reported as already correct (selected):** AC-043 (protection/
event reuse) independently re-confirmed by direct code read, not merely re-stated from
the implementer's own claim; energy provenance independently verified by perturbing
`e_dc_j` by `-1 J` and confirming the reported excursion increased by exactly `1 J`;
schema parity independently re-checked field-by-field with no differences found; extrema
emphasis confirmed limited to exactly the 8 whitelisted columns with correct tie handling;
async/race protection confirmed via the independent `comparisonRequestGenerationRef`
lane. Codex also independently ran 112 focused scenario/API/protection tests (all
passed) and frontend lint/typecheck (both passed) as part of its own verification: full
suite / production build / browser execution were not independently rerun by Codex
itself (sandboxed, read-only environment constraints), consistent with this being an
implementation read-plus-targeted-verification review, not a second full CI run.

## Remediation verification (post Round 1)

- `python -m pytest tests/test_scenario_comparison.py tests/test_api.py tests/test_protection_timeline.py -q`:
  **114 passed** (up from 112 before remediation — the two new fixture tests).
- `cd frontend && npm run lint && npm run typecheck`: both PASS, no new errors/warnings.
- Both direct Playwright scripts (desktop/390px and 375px) rerun against the hot-reloaded
  dev server after the fix: **all checks PASS**, zero console/page errors, unchanged from
  before remediation.
- Direct DOM inspection confirmed the new tooltip text renders exactly as specified:
  `"Thermal protection never latched TRIPPED in this run."` /
  `"The bus never reached its numerical energy floor in this run."`.
- Full deterministic suite rerun after remediation: `python -m pytest -q` —
  **738 passed, 7 skipped** (738 = 736 + the 2 new fixture tests; the 7 skips are the
  same pre-existing skips as before, unrelated to this feature).
- Frontend production build rerun after remediation: `cd frontend && npm run build` —
  PASS, `✓ Compiled successfully`, static page generation succeeds, no new
  errors/warnings.

## Independent Codex implementation review — Round 2 (focused closure review)

**Method:** `codex exec --sandbox read-only`, same invocation discipline as Round 1
(stdin closed, dedicated log, verified a real model turn began before waiting). Scope:
narrowly re-verify only the two Round 1 findings' remediation, plus re-scan the full
working diff for scope drift and independently rerun the three affected test files.

**Verdict:** `APPROVE`.

| # | Disposition | Independent evidence |
|---|---|---|
| 1 (Major) | **CLOSED** | `scenario_comparison.py::_describe_dominant_stress` independently confirmed to distinguish no-floor-contact / exact-sample-tie / later-floor-contact using only authoritative `ProtectionTimeline` timestamps, mirroring `_describe_outcome` with no outcome reclassification. The three new fixtures independently confirmed to exercise three genuinely distinct `(trip_time, floor_time)` pairs: `(4s, None)`, `(1s, 2s)`, `(1s, 1s)` — not three copies of the same case. |
| 2 (Minor) | **CLOSED** | Both timestamp cells confirmed to supply a `title` only when the value is `=== null`; a real `0.0` value is confirmed to never get a null tooltip. One wording-precision note (not a new finding, explicitly stated to "preserve the specified meaning and satisfy §8"): the tooltip says "numerical energy floor," SPEC-010 §5's table header cell says "numerical floor" — same referent, not a defect. |

Codex independently reran `python -m pytest tests/test_scenario_comparison.py
tests/test_api.py tests/test_protection_timeline.py -q` itself (its first invocation
failed on a read-only-sandbox temp-file restriction unrelated to this codebase; the
retry with `--capture=sys -p no:cacheprovider` succeeded) and confirmed all **114
tests passed**. It also independently confirmed `git diff --stat -- src/` is empty and
`protection_timeline.py` has no diff. It noted, as an honest caveat rather than a
finding, that without a saved Round 1 snapshot it could not mechanically prove the
*only* thing that changed since Round 1 was these two fixes — the full untracked/tracked
file list it observed matches exactly this feature's own stated file list (§"Files
changed" above), including the pre-existing, already-reviewed `ProtectionCoordination.tsx`
coverage-checklist extraction from before Round 1.

**Result: 0 blocker / 0 major / 0 minor open.** Both Round 1 findings CLOSED; no new
finding raised. SPEC-010's governance requirement (`Codex = APPROVE`, 0 blocker, 0
major, minors closed) is met.

## AC-051 — validation record, completeness review

**Method:** this document, checked line-by-line against AC-039–AC-050 above by the
implementer at filing time; independent completeness confirmation is part of the Codex
implementation review before Human Gate.
**Result:** every criterion AC-039–AC-050 appears above with a stated verification
method and result.

## Human Product Acceptance

The Human Engineering Lead reviewed the actual rendered product (desktop Compare All and
375×812 mobile Compare All) and granted **Human Product Acceptance: APPROVED**, following
Codex Round 2's `APPROVE` verdict (0 blocker / 0 major / 0 minor open). Per
`ENGINEERING.md`'s Definition of Done, this is the final required sign-off before the
SPEC-010 implementation is merged into the repository's committed history. A handful of
non-blocking visual-polish ideas were raised during acceptance review (limitation-text
readability, sticky headers/scenario labels for wide tables on a future pass) — these are
explicitly not SPEC-010 blockers and are not implemented here; they belong to a future,
separately-scoped polish pass, not this specification.

## Known limitations (carried from SPEC-010 §11, unchanged by implementation)

- `dc_link_energy_excursion_j` is a snapshot of maximum observed depletion, not a measure
  of unmet energy demand — Thermal Trip/Grid Sag/Grid Loss all report `6399.0` J because
  all three saturate at the same numerical energy floor (`config.dc_bus.min_energy_j`).
- No field quantifies ±1%-of-`V_ref` settling-band duration.
- `dominant_stress` collapses three different root causes into `DC_BUS_VIABILITY_LOSS`;
  the finer distinction remains readable from `trip_event_time_s`/`coordination.result`/
  `grid_ever_unavailable` in the same row.
- `THERMAL_PROTECTION_TRIP` is reachable only via a constructed fixture, not any of the
  five real scenario presets under current defaults.
