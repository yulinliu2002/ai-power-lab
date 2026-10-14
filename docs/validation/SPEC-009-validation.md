# SPEC-009 — Protection Coordination & Event Analysis — Validation Record

## Context

- Spec: `docs/specifications/SPEC-009-protection-coordination-event-analysis.md`
  (v0.5, Codex architecture-review Round 5 verdict `APPROVE`, 0 blocking/0 major/0 minor open).
- This record covers implementation of SPEC-009 end-to-end: the additive
  `trip_event_time_s`/`bus_collapse_event_time_s` fields, the `CoordinationAnalysis`/
  `PROTECTION_COVERAGE` derived-data additions to `ProtectionTimeline`, the additive
  backend schema/serialization changes (zero new routes), the new
  `ProtectionCoordination.tsx` frontend component, and all required verification
  layers (AC-038).
- No `src/` file was changed (AC-035). No existing `tests/test_api.py` assertion
  changed except the one explicitly authorized nested key-set literal and the
  `_timeline_to_dict` helper (SPEC-009 §7, AC-033). `docs/validation/SPEC-005-validation.md`
  was not touched.

## Files changed

- `dashboard/adapters/protection_timeline.py` — additive: `trip_event_time_s`/
  `bus_collapse_event_time_s` fields on `ProtectionTimeline`; new `CoordinationResult`
  enum, `EventSeparation`/`CoordinationAnalysis` dataclasses, `classify_coordination`
  and its helpers (`_classify_coordination_result`, `_describe_coordination`,
  `_derating_preceded_terminal_event`, `_build_separations`); new `CoverageEntry`
  dataclass and the static `PROTECTION_COVERAGE` constant; `coordination`/`coverage`
  fields on `ProtectionTimeline`.
- `backend/schemas.py` — additive: `EventSeparationModel`, `CoordinationAnalysisModel`,
  `CoverageEntryModel`; four new fields on `ProtectionTimelineModel`.
- `backend/app.py` — `_serialize_protection_timeline` extended with the four new
  field mappings. No route/endpoint added or changed.
- `tests/test_api.py` — `_timeline_to_dict` extended with the four new fields; the
  one authorized nested key-set literal in `test_protection_scenario_response_schema_shape`
  updated to include `trip_event_time_s`, `bus_collapse_event_time_s`, `coordination`,
  `coverage` (SPEC-009 §7, AC-033).
- `tests/test_protection_timeline.py` — 29 new tests for AC-027 through AC-032:
  real-scenario terminal-event-time parity (checked against direct
  `_first_true_time`/`_first_floor_contact_time` computation, not a weaker
  "is not None" substitute), real-scenario coordination classification and
  separations (including the two-entry Thermal Trip case), constructed fixtures for
  `PROTECTION_ACTED_NO_VIABILITY_LOSS`, `PROTECTION_ACTED_BEFORE_VIABILITY_LOSS`
  (strict), the exact-timestep tie (asserting neither the result label nor the
  result detail contains "before"), all four `derating_preceded_terminal_event`
  cases (including the constructed `False` case), non-negative/non-fabricated
  separation checks, and the coverage-matrix structural regression test.
- `frontend/app/lib/formatSeconds.ts` (new) — `formatSeconds` extracted unchanged
  from `ProtectionTimeline.tsx`.
- `frontend/app/components/ProtectionTimeline.tsx` — imports `formatSeconds` from
  the new shared module instead of defining it locally; no other line changed.
- `frontend/app/lib/simulationApi.ts` — additive: `EventSeparation`,
  `CoordinationAnalysis`, `CoverageEntry` interfaces; four new fields on the
  `ProtectionTimeline` interface.
- `frontend/app/components/ProtectionCoordination.tsx` (new) — renders the
  coordination result banner, event-separation rows, and the protection-coverage
  checklist, reading every backend-owned label/detail string verbatim.
- `frontend/app/page.tsx` — one new import, one new render line
  (`<ProtectionCoordination timeline={data.protection_timeline} />`) immediately
  after the existing `<ProtectionTimeline ... />` call. No other line changed.

## Deterministic verification (AC-027–AC-033, AC-035, AC-037)

    python -m pytest tests/test_protection_timeline.py -q   # 49 passed
    python -m pytest tests/test_api.py -q                    # 29 passed
    python -m pytest -q                                       # 702 passed, 7 skipped (pre-existing, unrelated)
    git diff --stat -- src/                                   # no output — no src/ file changed

One full-suite run during review produced a single, non-reproducing failure in
`tests/test_peos_runtime_verification.py::test_default_browser_worker_runner_kills_whole_process_group_on_timeout`
(`PermissionError` from `os.killpg`, a sandbox/process-group timing issue in that
pre-existing PEOS test, unrelated to this feature). Confirmed as transient: it
passes alone, passes on an unmodified `git stash` baseline, and the very next
full-suite run (702 passed, 7 skipped) was clean. No code under `dashboard/`,
`backend/`, or `src/` is exercised by that test.

All five real scenarios' terminal-event times and coordination results
(confirmed by direct adapter execution, not assumed):

| Scenario | `trip_event_time_s` | `bus_collapse_event_time_s` | `coordination.result` | `separations` |
|---|---|---|---|---|
| Load Step | `None` | `None` | `NO_TERMINAL_EVENT` | `()` |
| Sustained High Load | `None` | `None` | `NO_TERMINAL_EVENT` | `()` |
| Thermal Trip | `46.147` | `14.446` | `VIABILITY_LOST_BEFORE_PROTECTION_ACTION` | `"Bus energy floor -> thermal trip"` (31.701 s), `"Derating begins -> terminal event"` (2.728 s) |
| Grid Sag | `None` | `0.448` | `VIABILITY_LOST_NO_PROTECTION_ACTION` | `()` |
| Grid Loss | `None` | `0.2385` | `VIABILITY_LOST_NO_PROTECTION_ACTION` | `()` |

Thermal Trip's first `DERATED` segment starts at 11.718 s (strictly before the
14.446 s terminal event), confirming `derating_preceded_terminal_event is True`
for this run, consistent with SPEC-009 §0/AC-030.

`PROTECTION_ACTED_NO_VIABILITY_LOSS`, `PROTECTION_ACTED_BEFORE_VIABILITY_LOSS`
(both the strict and exact-timestep-tie sub-cases), and the constructed
`derating_preceded_terminal_event is False` branch are, as SPEC-009 §0/§11
states, unreachable by any of today's five real scenario presets — covered only
by constructed fixtures (AC-029/AC-030), the same posture SPEC-008 already
established for `PROTECTION_TRIP`.

## Frontend static verification (AC-034, AC-036)

    cd frontend && npm run lint        # clean
    cd frontend && npm run typecheck   # clean
    cd frontend && npm run build       # succeeds

**AC-034 schema/type-fidelity check (field-by-field comparison, §10):**
`simulationApi.ts`'s `ProtectionTimeline` interface and its three new interfaces
(`CoordinationAnalysis`, `EventSeparation`, `CoverageEntry`) were compared
field-by-field, by direct code inspection, against `backend/schemas.py`'s
`ProtectionTimelineModel` and its three new mirrored models
(`CoordinationAnalysisModel`, `EventSeparationModel`, `CoverageEntryModel`):
every field name, nullability (`float | None` ↔ `number | null`,
`bool | None` ↔ `boolean | null`), and nested type matches exactly. No existing
field of any existing interface changed type or meaning.

No new frontend test runner was added (none exists in this repository today;
adding one is outside this specification's authority per `CLAUDE.md`).

## Manual verification checklist (Category C, same taxonomy as SPEC-008 §17)

Performed against a running dev server (`uvicorn backend.app:app --port 8000` +
`npm run dev`), driven with Playwright (chromium, headless) for all five
scenarios — genuine manual/scripted browser evidence, not a PEOS Runtime
Verification claim (see "Runtime Verification" below):

1. **Initial load:** the new `[data-testid="protection-coordination"]` section
   renders below the existing Protection Timeline section on first paint
   (Load Step).
2. **All five scenarios:** the Coordination section renders for every scenario;
   wording matches the backend's `result_label`/`result_detail`/`coverage`
   entries verbatim (code-inspection cross-check, same method SPEC-008 used for
   its own AC-011).
3. **Event-separation rows:** present only for Thermal Trip among the five real
   scenarios (both expected rows, with the exact duration values `31.701 s` and
   `2.728 s`), and absent (not a blank placeholder) for the other four.
4. **Coverage checklist:** all 5 `PROTECTION_COVERAGE` rows render in every
   scenario, with a ✓/✕ text glyph (never color-only).
5. **Mobile viewport (375px width), Thermal Trip** (the one scenario with every
   optional sub-section populated): `document.documentElement.scrollWidth`
   equals `clientWidth` — no horizontal overflow.
6. **No console/page errors** observed across any of the five scenario
   selections or the mobile-viewport pass.

A screenshot of the Thermal Trip scenario (desktop width) was captured and
visually reviewed: the Coordination section appears immediately after the
existing Protection Timeline section, with no duplication of information
already shown there, matching SPEC-009 §8's layout.

One environment-specific issue was found and worked around during this pass,
not a SPEC-009 defect: the frontend dev server's cross-origin dev-asset guard
(Next.js `allowedDevOrigins`) blocks its HMR WebSocket (and, with it, full page
interactivity) when the browser is pointed at `127.0.0.1` instead of
`localhost`, even though both resolve to the same server. Using `localhost` in
the verification script resolved it; no application code change was needed or
made.

## Runtime Verification (SPEC-006 catalog) — honest coverage, unchanged posture from SPEC-008 §18

    runtime: page_load path=/ landmarks="[data-testid='scenario-select'],[data-testid='protection-timeline'],[data-testid='outcome-banner'],[data-testid='protection-coordination']" ac=AC-034
    runtime: viewport_overflow viewport=desktop ac=AC-036
    runtime: viewport_overflow viewport=mobile ac=AC-036

This covers only the default-loaded (Load Step) page's static presence and
responsiveness — the fixed V1 catalog still cannot drive the scenario
selector. No claim of per-scenario or interactive PEOS Runtime Verification
coverage is made; the scenario-selector interaction and per-scenario content
fidelity are instead covered by the manual/scripted Playwright checklist above
(direct/manual browser evidence, not a PEOS Runtime Verification claim).

## Codex implementation review — Round 1

An independent Codex implementation review (standalone, read-only,
`codex exec --sandbox read-only`, against the actual diff, SPEC-009 v0.5,
`CLAUDE.md`/`ENGINEERING.md`/`AGENTS.md`, and an independent re-run of the
targeted deterministic tests plus direct adapter execution) returned
`CHANGES_REQUIRED`, 0 blocking / 1 major / 2 minor.

| # | Severity | Finding | Disposition |
|---|---|---|---|
| 1 | Major | `_describe_coordination`'s tied-case (§6 case 3a) *label* still read "Thermal protection acted before DC-bus viability was lost" — the detail text was correctly worded for the tie, but the label was not, so a reader of the label alone would see a false "before" precedence claim. | **FIXED** — `_describe_coordination` now special-cases the exact-timestep tie to produce a dedicated label ("Thermal protection acted at the same recorded sample as DC-bus viability loss") containing no causal/directional wording, independent of the detail-text fix that was already correct. `test_coordination_exact_timestep_tie_wording_and_separation` now asserts `"before" not in result_label` in addition to the existing detail-text assertion. |
| 2 | Minor | `docs/validation/SPEC-009-validation.md` (this file) did not yet exist at review time, leaving AC-038 and §10's required recording of acceptance checks, manual verification, and Runtime Verification results unsatisfied. | **FIXED** — this validation record is now filed. |
| 3 | Minor | The AC-027 real-scenario regression test for Grid Sag/Grid Loss asserted only that `bus_collapse_event_time_s is not None`, not that it matched direct `_first_floor_contact_time` computation — an incorrect non-null value would have passed. | **FIXED** — `test_real_scenarios_terminal_event_times_match_direct_computation` now compares all five scenarios' `trip_event_time_s`/`bus_collapse_event_time_s` directly against `_first_true_time`/`_first_floor_contact_time` computed on the same telemetry, for exact equality, not a weaker presence check. |

Independent verification performed by the reviewer: 85 relevant tests passed;
`lint`/`typecheck` passed; Thermal Trip's 46.147/14.446/31.701/2.728/11.718 s
values were independently confirmed; no `src/` changes, new routes,
unauthorized existing API assertions, or frontend string rewording were found.
The reviewer's own full-suite rerun hit an unrelated sandbox/environment
failure executing a subprocess-killing PEOS test (the same transient failure
documented above) and could not independently confirm the full-suite pass
count in its own read-only sandbox; this was independently re-run twice
outside that sandbox (see "Deterministic verification" above) and confirmed
clean (702 passed, 7 skipped).

## Codex implementation review — Round 2 (closure)

A focused closure review of the above three fixes, scoped only to verifying
Finding 1's corrected label, Finding 2's filed validation record, and Finding
3's strengthened test (not a fresh broad review), returned **`APPROVE`**,
**0 blocking / 0 major / 0 minor open**:

1. **CLOSED** — code inspection and direct execution confirmed both the
   tie-case label and detail text exclude "before," while the strict
   (non-tied) cases of the same enum member correctly retain it.
2. **CLOSED** — `docs/validation/SPEC-009-validation.md` (this file) exists
   and substantively covers AC-027–AC-038, the Codex review history, Runtime
   Verification, the manual checklist, and known limitations.
3. **CLOSED** — all five real scenarios now assert exact equality against
   direct `_first_true_time`/`_first_floor_contact_time` computation; the
   imports resolve and the targeted tests pass (78 passed).

No new, fix-induced regression or validation-record inconsistency was found.
Zero findings remain open across both implementation-review rounds. This
closes the Codex implementation review for SPEC-009: final verdict
`APPROVE`, 0 blocking / 0 major / 0 minor open, every criterion in §9
verified per §10's plan.

## PEOS dogfood findings (not SPEC-009 product requirements; inherited unchanged from SPEC-008)

1. **Runtime-interaction capability gap** (SPEC-008 §19.1, SPEC-009 §0) —
   recorded, not closed; not a SPEC-009 blocker per the governing instruction.
2. **Disk hygiene** (SPEC-008 §19.2) — recorded; no PEOS infrastructure change
   was made as part of this implementation.

## Known limitations (carried from SPEC-008 §20, extended per SPEC-009 §11)

- Every limitation SPEC-008 §20 already states carries over unchanged (no
  bus-voltage protection; binary `recovery`; no real scenario exercises
  `PROTECTION_TRIP`; no PEOS interactive coverage; no frontend test runner; no
  scenario-selection persistence).
- `CoordinationResult`'s `PROTECTION_ACTED_*` branches are unreachable by any
  of today's five real scenario presets — covered only by constructed
  fixtures. Only `NO_TERMINAL_EVENT` and `VIABILITY_LOST_*` are exercised
  end-to-end by real scenarios.
- The coverage matrix (§5) is tied to `src/protection.py` by one structural
  regression test (enum arity + signature inspection) that is supplemental
  evidence only — it detects a new voltage/current/grid-availability
  *parameter* appearing, not every possible future behavioral change. The two
  behavioral claims instead rest on three existing named tests in
  `tests/test_protection.py`.
- "Coordination" is a statement about recorded-time ordering only, never a
  causal claim.

## Confirmation

No file under `src/` was changed. No route or endpoint was added. Nothing was
pushed, merged, or tagged.
