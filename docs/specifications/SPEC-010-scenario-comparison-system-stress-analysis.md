# SPEC-010 — Scenario Comparison & System Stress Analysis

> **Historical document:** PEOS is retired (git tag `pre-peos-retirement`). References to PEOS execution below describe the process at the time of writing; requirement text is unchanged.

**Status:** Architecture Approved (Codex Round 5: `APPROVE`, 0 blocking/0 major/0 minor open across
the full five-round review history). Implementation not yet started; pending Human Engineering Lead
approval per `ENGINEERING.md`'s Core Workflow. (Round 1: `CHANGES_REQUIRED`, 0/3/3, remediation
attempted in 0.2. Round 2 closure review of 0.2: `CHANGES_REQUIRED`, 0/0/2 — 4 of 6 confirmed
closed, 1 downgraded major→minor residual, 1 new residual from 0.2's own remediation text; both
fixed in 0.3. Round 3 closure review of 0.3: both `CLOSED`, 2 further minor documentation issues
found and fixed in 0.4. Round 4 confirmation of 0.4: all 3 corrections confirmed, 1 residual
header-metadata lag, fixed in this revision. Round 5 final confirmation: `APPROVE`, 0/0/0. See §14
for the complete disposition across all five rounds.)
**Project:** AI Power Lab
**System:** `dashboard/adapters/` (new derived-data module, reusing SPEC-008/009's existing
`ProtectionTimeline`), `backend/` (one new endpoint/schema), `frontend/app/` (new comparison
section/mode). No change to `src/` (simulation physics) is in scope or required.
**Version:** 0.5 (0.1 returned Codex `CHANGES_REQUIRED` with 0 blocking/3 major/3 minor findings —
duplicated energy-excursion provenance overlooking `Telemetry.e_dc_j`, an unverifiable Compare-All
viewport/AC-051-completeness gap, an unbounded per-column emphasis carve-out with a mis-cited
`CLAUDE.md` quote, an overstated energy-excursion metric description, a missing `max_v_dc_v` catalog
entry, and an overclaimed "only call site" in AC-043. 0.2 attempted remediation of all 6. A focused
Round 2 closure review of 0.2 independently re-ran all five scenarios' energy-excursion values,
confirmed 4 of the 6 `CLOSED` as described, found finding 1 downgraded to a minor residual (one stale
sentence in §2 the targeted edits had not reached) and finding 4 `STILL_OUTSTANDING` (0.2's own
remediation introduced a new, inaccurate claim that `segments`/`events` already supply ±1%-band
duration — they do not) — `CHANGES_REQUIRED`, 0 blocking/0 major/2 minor. 0.3 fixed both. A focused
Round 3 closure review of 0.3 confirmed both `CLOSED` by direct execution and found 2 further minor
documentation issues (stale `"(mid-run value)"`/`"(early value)"` placeholders in §0's table; an
overstated "0.2 closed all 6" claim) — `CHANGES_REQUIRED`, 0 blocking/0 major/2 minor. 0.4 fixed both.
A final Round 4 confirmation review of 0.4 confirmed all three corrections and found one residual
minor (this header had not yet been bumped to reflect 0.4/Round 3's completion) — `CHANGES_REQUIRED`,
0 blocking/0 major/1 minor. 0.5 fixed it. A final Round 5 confirmation review of 0.5 returned
**`APPROVE`**, 0 blocking/0 major/0 minor open across the full review history — see §14 for the
complete, final disposition.)
**Type:** Software Component (presentation/derived-data layer over existing scenarios and
SPEC-008/009's existing `ProtectionTimeline`; no new engineering model)

---

This specification is a PEOS dogfood artifact: it inspects the repository's existing
scenario/telemetry/`ProtectionTimeline`/API/frontend capability (§0) before proposing any new
architecture, per `ENGINEERING.md`. It is an **additive extension that reuses SPEC-008/009's
existing event model** — it introduces no competing classification and recomputes no value either
specification's modules already produce.

## 0. What Already Exists (repository inspection findings)

This section is evidence, not a requirement.

**Five fixed scenarios (`dashboard/adapters/simulation_adapter.py`).** `run_load_step`,
`run_sustained_high_load`, `run_thermal_trip`, `run_grid_sag`, `run_grid_loss` — each returns a
`ScenarioResult(telemetry, config, events)`. `summary_metrics(result)` already exists in this
module and already computes `min_vdc_v`, `max_vdc_v`, `peak_sst_power_w`, `max_temperature_c`,
`final_operating_state` as a plain dict — a direct precedent for exactly the kind of whole-run
reduction this specification needs, but it is not wired to the API today, has no units/applicability
documentation, uses `final_operating_state` (a weaker signal than the Protection Timeline's own
`segments`), and has no notion of voltage deviation, power mismatch, or energy excursion. This
specification supersedes it with a more complete, documented dataclass rather than extending it in
place, because its undocumented dict shape is not the one this feature exposes over HTTP (§3).

**`dashboard/adapters/protection_timeline.py` (SPEC-008/009, `APPROVE`, 0/0/0 open both times).**
`build_protection_timeline(telemetry, config, input_events) -> ProtectionTimeline` already computes,
per run: `segments` (RLE of `operating_state`), `outcome` (`RIDE_THROUGH` / `PROTECTION_TRIP` /
`BUS_COLLAPSE_UNPROTECTED`, by ordered-terminal-event comparison), `recovery`
(`RECOVERED`/`NOT_RECOVERED`/`NOT_APPLICABLE`, ±1%-of-`V_ref` settling band), `trip_event_time_s`,
`bus_collapse_event_time_s`, `coordination` (`CoordinationAnalysis` — five-way, non-causal ordering
of the same two times), and `coverage` (`PROTECTION_COVERAGE`, static). Every one of these fields is
already authoritative, already serialized by both existing endpoints, and already read verbatim by
the existing frontend. **This specification must not recompute, re-derive, or re-word any of them.**

**Confirmed by direct adapter execution (defaults, no overrides), reused verbatim from SPEC-008 §0
/ SPEC-009 §0's own confirmed numbers plus one new direct run for this specification:**

| Scenario | `outcome` | `recovery` | first `DERATED`? | `trip_event_time_s` | `bus_collapse_event_time_s` |
|---|---|---|---|---|---|
| Load Step | `RIDE_THROUGH` | `RECOVERED` | No | `None` | `None` |
| Sustained High Load | `RIDE_THROUGH` | `RECOVERED` | **Yes** | `None` | `None` |
| Thermal Trip | `BUS_COLLAPSE_UNPROTECTED` | `NOT_RECOVERED` | Yes | `46.147` | `14.446` |
| Grid Sag | `BUS_COLLAPSE_UNPROTECTED` | `RECOVERED` | No | `None` | `0.448` |
| Grid Loss | `BUS_COLLAPSE_UNPROTECTED` | `NOT_RECOVERED` | No | `None` | `0.2385` |

No scenario preset reaches `PROTECTION_TRIP` (SPEC-008 §0's own honesty note, unchanged) — this
specification's stress taxonomy (§6) inherits that same honestly-reported gap rather than hiding it.

**Energy-deficit precedent (`frontend/app/lib/transientMetrics.ts`,
`frontend/app/components/EnergyDeficitAnalysis.tsx`).** Scenario A's existing analysis already
computes, client-side: whole-series min `V_dc` and its time, max `|V_dc - V_ref|` and its time/sign,
peak `P_load - P_sst` and its time, and a DC-link energy figure via the **closed-form energy
equation** `ΔE = 0.5 * C_dc * (V_ref² - V_dc,min²)` — explicitly *not* a numerical integral, "evaluated
through the capacitor's own energy equation... rather than by summing samples." All of this is
anchored to one event index (`data.events[0]`), which SPEC-008 §12 explicitly forbids calling for
Scenarios B–E because `events[0]` is absent or wrongly-anchored for them. **This specification needs
the same four reductions and the same closed-form energy equation, computed over the whole run
instead of anchored to an event** — it is the same class of computation, but a new, honestly-scoped
function, not a reuse of `computeTransientMetrics` (which stays Scenario-A-only, unchanged).

**Correction (Codex Round 1 Finding 1): `Telemetry` already carries the integrated energy state
directly — `e_dc_j` (`src/telemetry.py:33/53`, populated every step at `src/simulation.py:167`).**
This specification's first draft stated the DC-link energy excursion "has no existing authoritative
source" and proposed reconstructing it from `voltage_reference_v`/`min_v_dc_v` via the voltage-energy
equation alone. That overlooked `telemetry.e_dc_j`, which is the engine's own exact integrated state
for every sample — not a value this module would be deriving for the first time. §5/§7 now compute
the excursion from `min(telemetry.e_dc_j)` directly (a plain reduction, no equation evaluation
needed to get the authoritative number), and use the voltage-energy equation only as a **secondary,
independent cross-check invariant** (confirmed to agree with the `e_dc_j`-based value to within
`1.8e-12` J by direct execution of all five scenarios, §9 AC-040) — never as the primary source.

**Decision on where this computation lives (governs §3).** `transientMetrics.ts` establishes that
*reduction-only* computation over an already-fetched series is acceptable frontend presentation
logic. This specification nonetheless places the whole-run reduction, the energy-excursion equation,
and the stress-taxonomy decision (§6) **backend-side**, as one new pure Python module, for three
reasons specific to a *cross-scenario comparison* feature (none of which applied to Scenario A's
single-run analysis): (1) the comparison view's entire point is a single authoritative table a user
can trust without re-deriving it per scenario — duplicating five parallel reductions and a taxonomy
decision in TypeScript would be the first engineering calculation this frontend performs that is not
a strict carry-over of an already-backend-validated Scenario-A pattern; (2) this specification's own
governing brief's "backend remains the authority for engineering calculations" instruction, and the
closely related existing repository rule it echoes — `DESIGN.md`'s Implementation Contract
(`DESIGN.md:225-231`): "The Python simulation engine (`src/`) is, and remains, the single source of
engineering truth... Frontend presentation code must never recreate engineering physics" (correcting
this draft's earlier mis-citation of that rule to root `CLAUDE.md`, which does not contain it) — read
most naturally as applying to a *new* cross-cutting calculation, not as retroactively relitigating
`transientMetrics.ts`'s already-approved scope; (3) it lets one new endpoint return one complete,
already-reduced payload
instead of requiring the frontend to issue five separate scenario fetches and reconcile them
client-side. `src/dc_bus.py`'s existing pure functions (`voltage_from_energy`, `energy_from_voltage`)
are imported, not re-implemented — the same precedent `protection_timeline.py` already set for its
one `src/` import.

**Backend/API (`backend/app.py`, `backend/schemas.py`).** Two existing endpoints: `POST
.../load-step`, `GET .../protection-scenarios/{scenario}`. Both already call
`build_protection_timeline` once per run and serialize it via `_serialize_protection_timeline`. No
endpoint runs more than one scenario per call today.

**Frontend (`frontend/app/page.tsx`, `ScenarioSelector.tsx`).** One `activeScenario` state, one
single-scenario view. No comparison/multi-scenario view exists. `simulationApi.ts`'s types mirror
every backend schema field-for-field; this is the convention this specification's frontend diff
follows.

**PEOS Runtime Verification (`peos/runtime_catalog.py`).** Unchanged: `page_load`,
`viewport_overflow`, `experiment_run` (cannot drive the scenario selector, and — by the same
limitation — cannot drive a new comparison-mode toggle either; §10).

## 1. Purpose

Let an engineer compare the system's response across all five fixed disturbance scenarios at once,
using only values the simulation engine and SPEC-008/009's existing derived-data layer already
produce, to answer: which scenario stresses the DC bus's voltage the most, which shows the largest
observed depletion of stored DC-link energy relative to nominal (§11 states this metric's precise,
narrower meaning — it is not a measure of ongoing unmet energy demand), which reach a derated or
tripped protection state, which lose modeled DC-bus viability, and in what order protection acted
relative to that loss — without clicking through five
separate single-scenario views and reconstructing the comparison by memory.

## 2. Engineering Question

Given five already-authoritative `Telemetry`+`Config` runs and their already-computed
`ProtectionTimeline`s, what is the smallest additive derived-data layer that reduces each run to a
small set of honestly-scoped, unit-labeled stress metrics — reusing every classification SPEC-008/009
already made, reusing `telemetry.e_dc_j` (the engine's own already-authoritative integrated energy
state, §0) as the DC-link energy excursion's primary source rather than reconstructing it, and adding
only whole-run numeric reductions plus one closed-form voltage-energy equation kept solely as an
independent cross-check invariant (§5/§9) — and that classifies each run's dominant stress dimension
by a fixed, deterministic decision tree over already-authoritative categorical fields, never an
invented
weighted score?

## 3. Scope

- One new, pure, side-effect-free Python module, `dashboard/adapters/scenario_comparison.py`,
  computing a `StressProfile` per run from an already-run `Telemetry` + `Config` +
  (already-computed) `ProtectionTimeline` (§4).
- One new FastAPI endpoint, `GET /api/v1/simulations/comparison`, running all five fixed scenarios
  (adapter defaults, no overrides) and returning each one's existing `thresholds` +
  `protection_timeline` shape plus the new `stress_profile` (§7).
- Additive Pydantic models in `backend/schemas.py` mirroring the new dataclasses field-for-field.
- One new frontend comparison section/mode (`frontend/app/components/ScenarioComparison.tsx`) and
  the minimal `page.tsx`/`simulationApi.ts` wiring to reach it (§8).
- Deterministic verification extending the existing test files (§9).

## 4. Out of Scope

- Any change to `src/` — no new physics, no new protection logic, no bus-voltage trip. This
  specification's numbers are reductions and one existing closed-form equation over already-produced
  telemetry, never a new governing relationship.
- Any change to `dashboard/adapters/protection_timeline.py`'s existing fields/semantics, or to
  SPEC-008/009's existing endpoints' response shapes. This specification reads `ProtectionTimeline`
  as an input; it adds a sibling field (`stress_profile`) to the *new* comparison endpoint's response
  only, never to `LoadStepResponse`/`ProtectionScenarioResponse`.
- A scenario editor, sliders, or any user-adjustable parameter — the five fixed presets only (per
  the governing brief's Scenario Scope; same posture as SPEC-008 Engineering Lead Decision 6).
- A single weighted "severity score." §6 is a fixed decision tree over four already-authoritative
  categorical inputs, never a numeric blend of heterogeneous physical quantities.
- Full per-scenario timeseries in the comparison response. The comparison view complements, and does
  not duplicate, the existing per-scenario detail page (`TelemetryChart`, `TimeScrubber`,
  `ProtectionTimeline`, `ProtectionCoordination`) — a user who wants a scenario's full trace already
  has one click to the existing single-scenario view. If a future need for small-multiples sparkline
  traces emerges, that is a separate specification's scope decision, not retrofitted here (§13 flags
  this as a resolved decision, not a Human Gate).
- Any PEOS (`peos/`) code change (same posture as SPEC-008 Decision 7 / SPEC-009 §4 — not reopened
  here). §10 records the same honest capability gap for the new comparison-mode toggle.
- Removing or restructuring anything SPEC-008/009 shipped. The single-scenario view, its Protection
  Timeline, and its Protection Coordination sections are unchanged.
- `dashboard/adapters/simulation_adapter.py::summary_metrics` is left in place, unchanged and
  unused by this feature (§0) — removing it is a separate, unrelated cleanup decision, out of scope.

## 5. Stress-Metric Catalog

Every metric below is structurally applicable to **all five** fixed scenarios, because all five
share one `Telemetry`/`Config`/`ProtectionTimeline` shape — there is no scenario-type-level "N/A."
"Applicability" therefore reduces entirely to whether a *specific run's* value is `null`/`None` (three
fields already express this: `trip_event_time_s`, `bus_collapse_event_time_s`,
`derating_preceded_terminal_event`), which this specification states explicitly per metric rather
than inventing a separate N/A flag. No value below is fabricated to fill a cell; a `None`/`null` is
rendered as "—" or "never," never as a zero or an omitted row.

| Metric | Unit | Authoritative source | New computation? | Null/missing semantics |
|---|---|---|---|---|
| `outcome`, `outcome_label`, `outcome_detail` | enum/text | `ProtectionTimeline.outcome*` (SPEC-008) | None — read verbatim | Never null |
| `recovery`, `recovery_label` | enum/text | `ProtectionTimeline.recovery*` (SPEC-008) | None — read verbatim | Never null (`NOT_APPLICABLE` is itself a valid value) |
| `coordination.result`, `.result_label`, `.result_detail` | enum/text | `ProtectionTimeline.coordination` (SPEC-009) | None — read verbatim | Never null (`NO_TERMINAL_EVENT` is itself a valid value) |
| `trip_event_time_s` | s | `ProtectionTimeline.trip_event_time_s` (SPEC-009) | None — read verbatim | `null` = thermal protection never latched `TRIPPED` in this run |
| `bus_collapse_event_time_s` | s | `ProtectionTimeline.bus_collapse_event_time_s` (SPEC-009) | None — read verbatim | `null` = the bus never reached its numerical floor in this run |
| `coverage` | list | `ProtectionTimeline.coverage` (SPEC-009, static) | None — read verbatim | Never null; identical across all five rows by construction |
| `protection_states_reached` | list of `"RUNNING"\|"DERATED"\|"TRIPPED"` | derived from `ProtectionTimeline.segments` (distinct states, first-occurrence order) | Index scan over ≤~5 segments — no telemetry scan, no new physical quantity | Never empty — every run has ≥1 segment |
| `min_v_dc_v` | V | whole-run min of `telemetry.v_dc_v` | Reduction only (§0's precedent) | Never null — every run has a `v_dc_v` series |
| `max_v_dc_v` | V | whole-run max of `telemetry.v_dc_v` | Reduction only, same class as `min_v_dc_v` above | Never null |
| `max_voltage_deviation_v` | V | whole-run max of `\|v_dc_v - voltage_reference_v\|` | Reduction only | Never null |
| `max_voltage_deviation_percent` | % | `max_voltage_deviation_v / voltage_reference_v * 100` | Arithmetic on the row above, same equation `transientMetrics.ts` already uses for Scenario A | Never null |
| `peak_power_deficit_w` | W | whole-run max of `max(p_load_w - p_sst_w, 0)` | Reduction only, same sign convention as `transientMetrics.ts`'s `peakDeficitKw` (0 if the SST never fell behind demand) | Never null; `0.0` is a real, meaningful value (no deficit occurred), not a missing one |
| `dc_link_energy_excursion_j` | J | **Primary:** `max(0, energy_from_voltage(voltage_reference_v, capacitance_f) - min(telemetry.e_dc_j))` — `telemetry.e_dc_j` is the engine's own exact integrated DC-link energy state (`src/telemetry.py:33/53`), not reconstructed from voltage. **Cross-check only**, never the authoritative value: `max(0, 0.5 * capacitance_f * (voltage_reference_v² - min_v_dc_v²))` — the same equation `EnergyDeficitAnalysis.tsx` already shows, confirmed to agree with the primary value to within `1.8e-12` J by direct execution of all five scenarios | Reduction (`min` over an already-produced array) plus one call to the existing `src.dc_bus.energy_from_voltage` pure function — no new equation, no re-derivation of a value the engine doesn't already expose | Never null; `0.0` is real (bus never sagged below `V_ref`) |
| `max_temperature_c` | °C | whole-run max of `telemetry.temperature_c` | Reduction only | Never null |
| `grid_ever_unavailable` | bool | whole-run `any(not telemetry.grid_available)` | Reduction only | Never null |
| `min_grid_voltage_pu` | p.u. | whole-run min of `telemetry.grid_voltage_pu` | Reduction only | Never null |
| `dominant_stress`, `_label`, `_detail` | enum/text | §6, decision tree over `outcome` + `protection_states_reached` (both already above) | Classification only — no new physical quantity | Never null (the tree is total) |

No metric here is a numerical integral, a re-simulation, or an approximation of anything `src/`
already computes exactly — the same honesty statement SPEC-008 §7 made for the Protection Timeline,
true here for the same reason.

## 6. Dominant-Stress Taxonomy

**Not a severity score.** The governing brief is explicit that ranking heterogeneous physical
stresses (a voltage deviation in volts, a temperature in °C, an energy excursion in joules) with
invented weights into one number is not acceptable, and this specification does not do that. Instead,
`dominant_stress` is a **four-member enum**, computed by a **total, four-branch decision tree** over
two already-authoritative categorical inputs this run's `ProtectionTimeline` and `segments` already
determined — `outcome` and whether any segment reached `DERATED`:

```python
class DominantStress(Enum):
    DC_BUS_VIABILITY_LOSS = "DC_BUS_VIABILITY_LOSS"
    THERMAL_PROTECTION_TRIP = "THERMAL_PROTECTION_TRIP"
    SUSTAINED_THERMAL_DERATING = "SUSTAINED_THERMAL_DERATING"
    TRANSIENT_POWER_IMBALANCE = "TRANSIENT_POWER_IMBALANCE"
```

Rule table (exhaustive, evaluated top to bottom, every branch reachable by construction):

1. `outcome == BUS_COLLAPSE_UNPROTECTED` → `DC_BUS_VIABILITY_LOSS`. (Thermal Trip, Grid Sag, Grid
   Loss under current defaults.)
2. `outcome == PROTECTION_TRIP` → `THERMAL_PROTECTION_TRIP`. (Not reached by any of today's five
   presets — reachable only via a constructed fixture, the same honestly-reported gap SPEC-008 §0
   and SPEC-009 §0 both already state for `PROTECTION_TRIP` generally. Stated here, not glossed
   over.)
3. `outcome == RIDE_THROUGH` and `"DERATED" in protection_states_reached` →
   `SUSTAINED_THERMAL_DERATING`. (Sustained High Load.)
4. `outcome == RIDE_THROUGH` and `"DERATED" not in protection_states_reached` →
   `TRANSIENT_POWER_IMBALANCE`. (Load Step.)

**Why `outcome` alone decides branches 1–2, ahead of any thermal signal.** This mirrors, not
reinvents, SPEC-008 §9's own Engineering-Lead-directed priority: a run that lost DC-bus viability
reports that as its headline fact even if a later, separate thermal trip also occurred (Thermal
Trip's real run does both) — SPEC-008 §9 already calls this "the more important headline fact for
this run" and this specification's taxonomy stays consistent with that judgment rather than
introducing a second, conflicting priority order for the comparison view. A reader who needs the
finer distinction this collapses — *why* three different scenarios all land in
`DC_BUS_VIABILITY_LOSS` — reads it directly from the per-row `trip_event_time_s`,
`coordination.result`, and `grid_ever_unavailable` columns already in the same table (§5); the
taxonomy is one column among several, never the only answer (per the governing brief's "prefer
multidimensional comparison over a fake scalar score").

**Labels/detail are backend-owned, plain-English, and traceable**, following the existing
`_OUTCOME_LABELS`/`_describe_outcome` pattern in `protection_timeline.py` exactly — e.g.
`DC_BUS_VIABILITY_LOSS`'s `detail` states which of `trip_event_time_s`/`bus_collapse_event_time_s`
is non-null and how `outcome` was already determined, never inventing new justification language.

## 7. Backend / API Impact

**New module: `dashboard/adapters/scenario_comparison.py`.** Pure functions/dataclasses, no I/O. Its
only `src/` import is `src.dc_bus.energy_from_voltage` (for `dc_link_energy_excursion_j`'s primary
value, §5) — the same function `protection_timeline.py` already imports a sibling of
(`voltage_from_energy`), not a new dependency class. The cross-check value (§5) is inline arithmetic,
not a second function call.

```python
class DominantStress(Enum):
    DC_BUS_VIABILITY_LOSS = "DC_BUS_VIABILITY_LOSS"
    THERMAL_PROTECTION_TRIP = "THERMAL_PROTECTION_TRIP"
    SUSTAINED_THERMAL_DERATING = "SUSTAINED_THERMAL_DERATING"
    TRANSIENT_POWER_IMBALANCE = "TRANSIENT_POWER_IMBALANCE"

@dataclass(frozen=True)
class StressProfile:
    min_v_dc_v: float
    max_v_dc_v: float
    max_voltage_deviation_v: float
    max_voltage_deviation_percent: float
    peak_power_deficit_w: float
    dc_link_energy_excursion_j: float
    max_temperature_c: float
    grid_ever_unavailable: bool
    min_grid_voltage_pu: float
    protection_states_reached: tuple[str, ...]
    dominant_stress: DominantStress
    dominant_stress_label: str   # backend-owned, verbatim (§8)
    dominant_stress_detail: str  # backend-owned, verbatim (§8)

def build_stress_profile(
    telemetry: Telemetry, config: Config, timeline: ProtectionTimeline,
) -> StressProfile: ...
```

`build_stress_profile` takes the already-computed `ProtectionTimeline` (not `input_events`) as an
argument — it never calls `build_protection_timeline` itself, so there is exactly one place in the
codebase that classifies `outcome`/`coordination` (closing the same "competing event model" risk
SPEC-009 §0 named and avoided for its own two new fields).

**One new FastAPI endpoint:**

    GET /api/v1/simulations/comparison

No path/query parameters — the governing brief's Scenario Scope fixes the five presets; this mirrors
Engineering Lead Decision 6's precedent (SPEC-008 §11) of a parameter-less `GET` for a fixed-preset
feature. The handler calls each of the five existing adapter functions with zero overrides (same
defaults `backend/app.py` already uses for Scenarios B–E, plus `run_load_step()`'s own defaults for
Scenario A), builds each run's `ProtectionTimeline` using **the same input-event reconciliation rule
`backend/app.py` already applies** (SPEC-008 §11 — `thermal_trip`'s own adapter-provided events are
excluded, every other scenario's are passed through), then calls `build_stress_profile` on the result.
Zero duplicated logic: this is the same five adapter calls and the same `build_protection_timeline`
calls `simulate_load_step`/`simulate_protection_scenario` already make, run five times in one handler
instead of once per request.

```python
class StressProfileModel(BaseModel):
    min_v_dc_v: float
    max_v_dc_v: float
    max_voltage_deviation_v: float
    max_voltage_deviation_percent: float
    peak_power_deficit_w: float
    dc_link_energy_excursion_j: float
    max_temperature_c: float
    grid_ever_unavailable: bool
    min_grid_voltage_pu: float
    protection_states_reached: list[str]
    dominant_stress: str
    dominant_stress_label: str
    dominant_stress_detail: str

class ScenarioComparisonEntry(BaseModel):
    scenario: str
    thresholds: ProtectionScenarioThresholds   # reused unchanged -- every scenario's Config
                                                 # carries these fields regardless of scenario type
    protection_timeline: ProtectionTimelineModel
    stress_profile: StressProfileModel

class ScenarioComparisonResponse(BaseModel):
    scenarios: list[ScenarioComparisonEntry]   # exactly 5, fixed order:
                                                 # load_step, sustained_high_load, thermal_trip,
                                                 # grid_sag, grid_loss
```

`ProtectionScenarioThresholds` (not the narrower `ScenarioThresholds`) is reused for every row,
including Load Step's — every scenario's `Config` carries `thermal_trip_time_s`/
`derate_factor_min`/`min_energy_j` regardless of which scenario ran, so this is not a new model, only
a wider reuse of an existing one.

**No change to any existing endpoint, route, or response field.** `LoadStepResponse` and
`ProtectionScenarioResponse` are untouched. **No change to any `src/` module.**

**Test-file impact (mechanical, same authorized pattern as SPEC-008 AC-007 / SPEC-009 §7):** a new
top-level key-set assertion for `/api/v1/simulations/comparison`'s response is added to
`tests/test_api.py`; no existing assertion in that file changes.

## 8. Frontend Presentation

**Integration point: a new mode toggle, not a sixth scenario-selector option.** Immediately beside
the existing `ScenarioSelector` (SPEC-008 §12), add a two-way toggle — "Single Scenario" (default,
today's unchanged behavior) / "Compare All" — implemented as a real, keyboard-operable control
(same pattern as the existing selector: `role="radiogroup"`, `data-testid` per option). Selecting
"Compare All" hides the single-scenario sections (KPI strip, `PowerFlowSchematic`, `TimeScrubber`,
charts, `ProtectionTimeline`, `ProtectionCoordination`) and renders the new
`ScenarioComparison.tsx`, fetching `GET /api/v1/simulations/comparison` once. Selecting "Single
Scenario" again restores the existing view unchanged — the same conditional-render-not-delete
pattern SPEC-008 §13.3 already established for the Scenario-A-only sections.

**`frontend/app/lib/simulationApi.ts`** gains, additively: `DominantStress` union type,
`StressProfile`, `ScenarioComparisonEntry`, `ScenarioComparisonResponse` interfaces (mirroring the
backend models field-for-field, the same convention every existing type in this file follows), and
`fetchScenarioComparison(): Promise<ScenarioComparisonResponse>`. No existing interface or function
in this file changes.

**New component: `frontend/app/components/ScenarioComparison.tsx`.** Reads only
`ScenarioComparisonResponse` fields verbatim. Layout (compact, no decorative dashboard, per the
governing brief):

- **Comparison matrix** — one row per scenario, one column per stress metric (§5), rendered as a
  real `<table>` (horizontally scrollable container at narrow widths, never causing page-level
  overflow — same `viewport_overflow` contract every existing section already meets). Null values
  render as `"—"` with a title/tooltip stating why (e.g. "never reached TRIPPED"), never as `0` or a
  blank cell.
- **Per-column max/min emphasis is presentation-only, not a new computed value — narrowly scoped
  (corrects Codex Round 1 Finding 3, which found the first draft's permission too broad to bound
  reliably).** The frontend may bold/mark the single largest (or smallest) already-rendered number
  purely to draw the eye, but **only** for this explicit whitelist of columns, and governed by these
  explicit rules:
  - **Eligible columns (continuous physical quantities only):** `min_v_dc_v` (smallest emphasized),
    `max_v_dc_v`, `max_voltage_deviation_v`, `max_voltage_deviation_percent`, `peak_power_deficit_w`,
    `dc_link_energy_excursion_j`, `max_temperature_c`, `min_grid_voltage_pu` (smallest emphasized) —
    exactly the numeric reduction metrics §5 defines, nothing else.
  - **Never eligible:** `trip_event_time_s`/`bus_collapse_event_time_s` (timestamps, not a stress
    magnitude — "earliest" is not "worst"), `derating_preceded_terminal_event` (nullable boolean),
    any enum/categorical field (`outcome`, `recovery`, `coordination.result`, `dominant_stress`,
    `protection_states_reached`), and `grid_ever_unavailable` (boolean, not a magnitude).
  - **Ties:** if two or more rows share the exact (unrounded) extremal value in an eligible column,
    every tied row is emphasized — never an arbitrarily "first" one.
  - **Strictly prohibited:** comparing values *across* columns (e.g. implying volts and joules are
    commensurable), applying any threshold/normalization to decide "how much worse," and attaching
    any severity/ranking conclusion to the emphasis — it marks one already-displayed number as the
    extremum of its own column, nothing more, exactly the same class of operation as the existing
    enum-to-color-role mapping precedent (SPEC-009 §0/§8: "enum-to-color-role mapping is
    acceptable... enum-to-English translation... is not") and no broader than it. This never
    introduces new wording, a new unit, or a new stored field.
- **Dominant-stress row** — `dominant_stress_label` plus `dominant_stress_detail` as supporting
  text, one line per scenario, read verbatim (no client-side enum-to-English translation, same
  contract as `outcome_label`/`result_label` today).
- **Protection coverage** — rendered once (not once per scenario; `coverage` is static and identical
  across all five rows, per §5/§0), reusing the existing `ProtectionCoordination.tsx` coverage-list
  presentation pattern rather than a new one.
- **The same universal educational caption SPEC-008 §12 already established** (V1 models only
  sustained thermal overtemperature protection; no DC-bus undervoltage/overvoltage protection) is
  repeated once at the top of this section — the comparison view is exactly where a reader could
  otherwise conclude three scenarios' shared `DC_BUS_VIABILITY_LOSS` label implies a real trip
  occurred in all three, which it does not.

**No duplication with the existing single-scenario view.** No full timeseries, no charts, no event
list — those remain one click away via "Single Scenario" (§4).

**Responsive/accessibility:** matches `ProtectionTimeline.tsx`/`ProtectionCoordination.tsx`'s
existing conventions exactly — no color-only meaning (every emphasized cell/dominant-stress value
also carries text), keyboard-operable mode toggle, semantic `<section>`/`<table>`, renders within the
existing `sm`/`lg` breakpoints with a horizontally-scrollable table container at narrow widths rather
than page overflow.

## 9. Acceptance Criteria

(Numbering continues from SPEC-009's AC-027–AC-038, keeping one unambiguous namespace across all
three specifications' shared `tests/` files.)

- [ ] **AC-039 (`StressProfile` correctness, real scenarios):** for each of the five scenarios run
  with adapter defaults, every numeric field of `build_stress_profile`'s output matches direct
  computation from that scenario's real `Telemetry` (whole-series min/max/`any` scans) — no
  synthetic fixtures for this criterion.
- [ ] **AC-040 (energy-excursion correctness + cross-check invariant, explicit tolerance):**
  `dc_link_energy_excursion_j` equals
  `max(0, energy_from_voltage(voltage_reference_v, capacitance_f) - min(telemetry.e_dc_j))` for all
  five scenarios (direct execution), matching `summary_metrics`-style direct computation to within
  absolute tolerance `1e-6` J. Separately, the cross-check equation
  `max(0, 0.5 * capacitance_f * (voltage_reference_v**2 - min_v_dc_v**2))` is confirmed to agree with
  the primary `e_dc_j`-based value to within absolute tolerance `1e-9` J for all five scenarios
  (consistent with the `1.8e-12` J agreement this specification's own Codex Round 1 review measured
  by direct execution) — a larger disagreement would indicate `telemetry.e_dc_j` and `telemetry.v_dc_v`
  have gone out of sync and must fail this test, not be silently tolerated. A constructed fixture
  where `min(telemetry.e_dc_j) > energy_from_voltage(voltage_reference_v, capacitance_f)` confirms the
  clamp returns exactly `0.0`, not a negative value.
- [ ] **AC-041 (`protection_states_reached` correctness):** matches the distinct `state` values of
  `ProtectionTimeline.segments` in first-occurrence order, for all five scenarios (expected:
  `("RUNNING",)` for Load Step/Grid Sag/Grid Loss; `("RUNNING", "DERATED")` for Sustained High Load;
  `("RUNNING", "DERATED", "TRIPPED")` for Thermal Trip).
- [ ] **AC-042 (`dominant_stress` taxonomy, real scenarios + fixture):** Load Step →
  `TRANSIENT_POWER_IMBALANCE`; Sustained High Load → `SUSTAINED_THERMAL_DERATING`; Thermal Trip,
  Grid Sag, Grid Loss → `DC_BUS_VIABILITY_LOSS`; a constructed `outcome == PROTECTION_TRIP` fixture
  (reusing SPEC-008 AC-019's fixture pattern) → `THERMAL_PROTECTION_TRIP` (the one branch no real
  scenario preset reaches, stated honestly rather than glossed over, same posture as SPEC-008 §0 /
  SPEC-009 §0 for `PROTECTION_TRIP` itself).
- [ ] **AC-043 (no competing event model, precisely scoped — corrects Codex Round 1 Finding 6's
  "only call site" overclaim):** `build_stress_profile` never calls `build_protection_timeline` and
  performs no classification of `outcome`/`coordination` of its own. `build_protection_timeline`
  already has two existing call sites repository-wide (`simulate_load_step`,
  `simulate_protection_scenario` in `backend/app.py`) — this criterion is **not** "the only call site
  in the repository," which is false; it is: **exactly one `ProtectionTimeline` construction per
  scenario within the new `GET /api/v1/simulations/comparison` handler**, with that same, single
  result passed into `build_stress_profile` as an already-computed value for that scenario. Verified
  by (a) code inspection confirming the new endpoint handler calls `build_protection_timeline` exactly
  once per scenario (not once for `build_stress_profile`'s benefit and again for the response's own
  `protection_timeline` field), and (b) a full read of `scenario_comparison.py`'s source confirming it
  contains no `if`/`match` branch testing `trip_active`, `v_dc_v`, or any other raw telemetry field
  against a threshold to derive its own outcome-like judgment — grep alone cannot establish this
  absence (a differently-named function performing the same classification would not be caught by a
  name-based search), so this check is a human/reviewer code read, not a shell command.
- [ ] **AC-044 (endpoint correctness/parity):** `GET /api/v1/simulations/comparison` returns exactly
  five entries in the fixed order (`load_step`, `sustained_high_load`, `thermal_trip`, `grid_sag`,
  `grid_loss`); each entry's `protection_timeline` matches that same scenario's direct
  `build_protection_timeline` output field-for-field (same parity-test style as SPEC-008/009's
  existing `_timeline_to_dict` helper, extended or reused); each entry's `stress_profile` matches
  direct `build_stress_profile` output on the same adapter call.
- [ ] **AC-045 (schema key-set test):** one new top-level key-set assertion
  (`{"scenarios"}`) and one nested key-set assertion (`ScenarioComparisonEntry`'s and
  `StressProfileModel`'s field names) added to `tests/test_api.py`; no existing assertion in that
  file changes.
- [ ] **AC-046 (frontend/backend field parity):** `simulationApi.ts`'s new interfaces are compared
  field-for-field against the backend Pydantic models (explicit diff, same corrective method SPEC-009
  §9/§10 adopted after its own Round 3 finding that `tsc --noEmit` alone only proves internal
  TypeScript consistency, not backend agreement) — not merely type-checked in isolation.
- [ ] **AC-047 (no `src/` change):** `git diff --stat -- src/` shows no file in this feature's diff.
- [ ] **AC-048 (lint/typecheck/build):** `cd frontend && npm run lint && npm run typecheck && npm run
  build` pass with no new errors/warnings.
- [ ] **AC-049 (full-suite regression):** `python -m pytest -q` passes at the repository root,
  including all existing SPEC-008/009 tests unchanged.
- [ ] **AC-050 (responsive/accessibility, populated Compare-All state specifically):** with "Compare
  All" selected and the comparison table actually populated with the five fetched rows (not the
  default Single Scenario state the fixed `viewport_overflow` catalog check loads into, §10), the
  table renders inside a horizontally scrollable container with no page-level horizontal overflow at
  the `mobile` viewport preset (`peos/runtime_catalog.py: VIEWPORT_PRESETS["mobile"]`, 390×844);
  scrolling the container does not scroll the page; no state/outcome/dominant-stress/emphasized-cell
  value is conveyed by color alone. This criterion is **not** satisfiable by the fixed-catalog
  `viewport_overflow` check alone (§10) — it requires the manual (or recommended scripted) check
  that actually toggles into Compare All first.
- [ ] **AC-051 (validation record, with explicit completeness review):**
  `docs/validation/SPEC-010-validation.md` is filed recording which criteria (AC-039–AC-050) were
  checked, how, and the result — same format as SPEC-008 AC-026 / SPEC-009 AC-038 — **and** is itself
  reviewed for completeness before being treated as satisfying this criterion: every AC-039–AC-050
  criterion above must appear in the filed record with a stated verification method and result, not
  merely a subset: an independent reviewer checks the filed record against this list line-by-line,
  the same way Codex's own closure reviews of SPEC-008/009 checked claimed-closed findings against
  the actual document text rather than accepting the claim.

## 10. Verification Plan

**Deterministic (pytest) — the load-bearing evidence, same posture as SPEC-008/009:**

- New `tests/test_scenario_comparison.py` — AC-039, AC-040, AC-041, AC-042 (real scenarios, no
  synthetic fixtures except AC-040's clamp case and AC-042's `PROTECTION_TRIP` fixture, both reusing
  this repository's existing `_make_config`/fixture-construction helpers already present in
  `tests/test_protection_timeline.py`).
- AC-043 — reviewer code-read (not a pytest check; see AC-043's own note on why grep is
  insufficient), performed as part of independent review before this feature's Definition of Done.
- Extend `tests/test_api.py` — AC-044, AC-045.
- `git diff --stat -- src/` — AC-047, the same mechanical check SPEC-008 AC-005/SPEC-009 AC-035 used.
- `cd frontend && npm run typecheck` plus a direct code-read diff of the new TypeScript interfaces
  against `backend/schemas.py` — AC-046 (not `tsc --noEmit` alone — see AC-046's own corrective
  note).
- `cd frontend && npm run lint && npm run build` — AC-048.
- `python -m pytest -q` at the repository root — AC-049.

> **Historical:** the PEOS Runtime Verification plan below is retired; PEOS and its runner are available only at git tag `pre-peos-retirement`. Verify via the unit/regression tests and manual checks instead.

**Runtime Verification (PEOS, honest scope):**

- `page_load` on `/` with the comparison section's landmarks present after the existing
  `page_load` check's normal navigation — this check kind does not click anything, so it can only
  confirm the comparison toggle/section exist in the initial DOM, not that selecting "Compare All"
  renders the fetched table. Recorded honestly as partial coverage, not claimed as full.
- `viewport_overflow` at both `desktop` and `mobile` presets — automated evidence for no
  page-overflow **only on whichever state the page loads into by default (Single Scenario)**. This
  check kind clicks nothing, so it cannot toggle into Compare All; it therefore provides **zero**
  coverage of AC-050, which is specifically about the *populated comparison table*, not the default
  view (Codex Round 1 Finding 2 — the first draft of this section incorrectly implied this check
  was AC-050's load-bearing evidence; it is not, and AC-050 itself now says so).
- **Known, honest gap (same shape as SPEC-008 §18/§19, not reopened or fixed here):**
  `experiment_run` is hardcoded to one numeric-slider interaction shape; it cannot select "Compare
  All," so no fixed-catalog Runtime Verification check can exercise the comparison table's actual
  rendered content, the per-column emphasis logic, or the mobile-width table scroll behavior while
  populated with real data. This is the same capability gap already recorded for the scenario
  selector itself, now also true of the new mode toggle — not a new class of gap, a second instance
  of the same one. No PEOS extension is proposed to close it.
- **Recommended, separately-labeled stronger check (not part of this PEOS Runtime Verification
  round, and not mandated by this specification):** a hand-written Playwright script (outside the
  fixed catalog) that clicks "Compare All" and asserts the five-row table renders would give real
  interaction/visual coverage the fixed catalog cannot. If the Human Engineering Lead wants this, it
  should be commissioned as its own small, explicitly-scoped script — not a change to
  `peos/runtime_catalog.py`'s fixed check kinds, and not implemented inside this specification's
  stated scope (§4).
- **Manual check — the actual load-bearing evidence for AC-050, given the gap above:** in a browser,
  select "Compare All," confirm all five rows render with correct outcome/dominant-stress values and
  no fabricated/zeroed cells for `None`/`null` fields; resize to the `mobile` preset's 390×844 and
  confirm the table scrolls horizontally inside its own container with no page-level horizontal
  scroll and no color-only-conveyed value, exactly as AC-050 states. This manual check, not
  `viewport_overflow`, is what AC-050 is actually verified by.

## 11. Known Limitations

- `DC_BUS_VIABILITY_LOSS` is reached by three of the five scenarios under current defaults (Thermal
  Trip, Grid Sag, Grid Loss) because V1 has no DC-bus voltage protection at all — the same honest fact
  SPEC-008 §0 already states for `outcome`, inherited here, not newly discovered. The taxonomy does
  not distinguish *why* viability was lost (sustained thermal exhaustion vs. a grid disturbance);
  that distinction remains readable from the same row's `trip_event_time_s`/`coordination.result`/
  `grid_ever_unavailable` columns, by design (§6).
- `THERMAL_PROTECTION_TRIP` is a real, reachable taxonomy branch, but — like SPEC-008/009's own
  `PROTECTION_TRIP`/`PROTECTION_ACTED_*` branches — it is reachable only via a constructed test
  fixture, not via any of today's five scenario presets (§9, AC-042).
- **`dc_link_energy_excursion_j` is a snapshot of maximum observed depletion relative to nominal, not
  a measure of unmet energy demand (Codex Round 1 Finding 4 — stated here explicitly after direct
  execution exposed it, not glossed over).** It is `energy_from_voltage(voltage_reference_v,
  capacitance_f) - min(telemetry.e_dc_j)`, clamped at `0` (§5) — a single before/after comparison at
  the run's lowest-energy sample, not an integral of the power-mismatch series over time (the same
  stated scoping limitation `EnergyDeficitAnalysis.tsx` already carries for Scenario A, now also true
  of this whole-run variant). Concretely: Thermal Trip, Grid Sag, and Grid Loss all report the
  **same** value (6,399 J, confirmed by direct execution across all three) because all three runs'
  stored energy is clamped at the same numerical floor (`config.dc_bus.min_energy_j`,
  `src/dc_bus.py`) — this metric cannot distinguish "briefly touched the floor" from "sat at the
  floor for the rest of the run, still unable to meet demand," even though the three scenarios'
  *continuing* energy deficits after reaching the floor are not equal. That distinction is not lost
  from the table overall — it is exactly what `recovery`, `segments`, and `protection_states_reached`
  separately carry — but `dc_link_energy_excursion_j` itself answers only "how far down did stored
  energy go," never "for how long did demand continue to exceed supply," and this specification
  states that boundary explicitly rather than letting the word "demand" in casual description imply
  otherwise.
- **No field this specification adds, and no existing SPEC-008/009 field either, quantifies how long
  `v_dc_v` spent outside the ±1%-of-`V_ref` settling band (Codex Round 2 Finding R2-2 — corrects this
  draft's own earlier, inaccurate claim that `protection_timeline.segments`/`events` already supply
  this).** `recovery` is a binary end-of-run settling-band membership check only (SPEC-008 §9) — not
  a duration. `protection_timeline.segments` (`dashboard/adapters/protection_timeline.py:336`) is a
  run-length encoding of `operating_state` (`RUNNING`/`DERATED`/`TRIPPED`) — a **protection-state**
  concept, with no relationship to the ±1% voltage band. `protection_timeline.events`'s
  `category="bus_energy"` entries (`protection_timeline.py:431`) mark entry/exit of the **numerical
  energy floor**, a materially tighter and different condition than "outside ±1% of `V_ref`." Neither
  structure can be read, interpreted, or post-processed to recover ±1%-band duration — doing so would
  require a new scan over `telemetry.v_dc_v`/`time_s` against the band, which this specification does
  not propose adding. Stated here as an honest gap, not as something already answered elsewhere.
- `peak_power_deficit_w` is an instantaneous peak, not an accumulated quantity — pairing it with
  `dc_link_energy_excursion_j` in the same row is intentional (the same "peak vs. accumulated"
  distinction `EnergyDeficitAnalysis.tsx` already teaches for Scenario A), not a redundant pair of
  near-duplicate numbers.
- This feature makes no claim about commercial SST hardware behavior, introduces no switching-level
  semiconductor dynamics, and uses no employer-proprietary information — same integrity posture as
  every prior specification in this repository.
- The comparison endpoint runs all five scenarios synchronously in one request; none of the five
  presets' durations are large enough to make this a performance concern today (confirmed by this
  specification's own direct-execution checks in §0), but this is noted as a design assumption that
  would need revisiting if a future specification made any preset's duration substantially longer.

## 12. Human Gates

None of the design decisions in §0, §6, §7, or §8 is left open for the Human Engineering Lead —
each is resolved with a stated rationale in this draft (one new endpoint and not five, one new
backend module and not a frontend one, the four-member non-scored taxonomy, no full timeseries in
the comparison payload). The one place this specification states a preference rather than treating
the matter as fully closed is:

1. **Where the mode toggle lives relative to the existing `ScenarioSelector` (§8).** This draft
   proposes a separate, adjacent two-way toggle ("Single Scenario"/"Compare All") rather than adding
   a sixth option to the existing five-way scenario selector, reasoning that the two controls answer
   different questions (which one scenario vs. all five at once) and conflating them would make the
   existing selector's semantics murkier. This is a product/UX placement call, not an engineering
   constraint — if the Human Engineering Lead prefers a different placement (e.g., a persistent
   "Compare" link in the header), that is a non-blocking implementation detail, not a reason to
   reopen this architecture.

If Codex review or implementation surfaces a genuine new ambiguity, it will be reported here rather
than resolved silently.

## 13. PEOS Dogfood Observations

- **Runtime Verification interaction/catalog gap (§10) — not new, now confirmed to recur.** The same
  gap SPEC-008 §19 and SPEC-009 §0 recorded for the scenario selector recurs identically for this
  specification's new mode toggle. This is recorded as evidence that the gap is a structural property
  of the fixed three-kind catalog (no check kind can click/select anything beyond
  `experiment_run`'s one hardcoded numeric-slider shape), not a one-off omission — still not fixed
  here, per Engineering Lead Decision 7's standing posture.
- **Temporary workspace disk-hygiene/retention issue** — unchanged, not touched by this
  specification; carried forward as a known finding from prior PEOS dogfood rounds.
- **No new PEOS finding surfaced during this specification's drafting itself.** `summary_metrics`'s
  existence (§0) was an architecture-relevant repository-inspection finding, not a PEOS-process
  finding — it is handled in §4/§0 as an engineering-scope decision, not reported here as a tooling
  gap.
- **Confirmed infrastructure dogfood finding: a Codex architecture-review invocation remained alive
  for >41 minutes before any tracked Codex model turn began.** The wrapper/binary processes existed,
  but there was no rollout/session file, no output growth, no network socket, and effectively zero
  CPU activity. Monitor liveness therefore did not imply review progress. Direct inspection (process
  state, `lsof`, `~/.codex/sessions/` rollout-file presence) showed the invocation was blocked reading
  additional input from stdin that would never arrive — confirmed by the eventual exit transcript
  reading exactly `"Reading additional input from stdin..."` once the stalled process was terminated.
  The replacement invocation, launched with stdin explicitly closed (`< /dev/null`) to a dedicated log
  file, created a rollout/session file and live network connections within 15 seconds and completed
  normally. Root cause is not speculated beyond this observation; not fixed inside SPEC-010 — this is
  a PEOS/tooling-process finding, not an architecture-content one.
- **Separate observation: stale, unrelated task context (referencing a different specification,
  process ID, and log path) appeared mid-session during this architecture work.** The referenced
  process/log identifiers did not match any process this session had started; the conflicting request
  (to inspect/finalize/commit an unrelated specification) was not acted on, and no repository mutation
  occurred as a result. Recorded as an observable fact only, not yet classified as a confirmed PEOS
  defect — investigate further only if reproducible or otherwise evidenced.

## 14. Findings Register

**Codex Architecture/Specification Review — Round 1** (standalone, read-only, `codex exec
--sandbox read-only`, against this repository's actual code — including direct execution of all
five scenarios through `build_protection_timeline` — plus `CLAUDE.md`/`ENGINEERING.md`/`AGENTS.md`/
SPEC-008/SPEC-009) returned **`CHANGES_REQUIRED`**, 0 blocking / 3 major / 3 minor. Directly
re-derived by the reviewer (outcome/recovery; trip/floor event times in seconds): Load Step
`RIDE_THROUGH`/`RECOVERED`, `None`/`None`; Sustained High Load `RIDE_THROUGH`/`RECOVERED` (DERATED
reached), `None`/`None`; Thermal Trip `BUS_COLLAPSE_UNPROTECTED`/`NOT_RECOVERED`, `46.147`/`14.446`;
Grid Sag `BUS_COLLAPSE_UNPROTECTED`/`RECOVERED`, `None`/`0.448`; Grid Loss
`BUS_COLLAPSE_UNPROTECTED`/`NOT_RECOVERED`, `None`/`0.2385` — all consistent with §0's table (§0's
own Grid Sag/Grid Loss rows stated only "(mid-run value)"/"(early value)" placeholders, now
confirmed as `0.448`/`0.2385` s).

| # | Severity | Finding (condensed) | Disposition |
|---|---|---|---|
| 1 | Major | `dc_link_energy_excursion_j` claimed to have "no existing authoritative source," overlooking `Telemetry.e_dc_j` (`src/telemetry.py:33/53`, `src/simulation.py:167`) — the engine's own exact integrated energy state. | **CLOSED.** §0/§5/§7/§9 rewritten: primary value is now `energy_from_voltage(V_ref, C) - min(telemetry.e_dc_j)`; the voltage-equation formulation is retained only as an explicitly-labeled, independent cross-check invariant (AC-040), not the authoritative source. |
| 2 | Major | `viewport_overflow`/manual checklist did not actually verify the *populated* Compare-All table (the fixed check only covers the default Single Scenario state); AC-040's tolerance was unspecified. | **CLOSED.** AC-050 rewritten to require the check against the populated Compare-All state specifically, naming why the fixed `viewport_overflow` catalog check cannot provide this evidence; §10's manual check rewritten as AC-050's actual load-bearing evidence; AC-051 strengthened with an explicit completeness-review requirement; AC-040 now states explicit absolute tolerances (`1e-6` J primary, `1e-9` J cross-check). |
| 3 | Major | Per-column max/min emphasis carve-out was unbounded — no whitelist, no tie rule, no prohibition on cross-column comparison; §0's "backend remains the authority" quote was mis-cited to root `CLAUDE.md`. | **CLOSED.** §8's emphasis carve-out rewritten with an explicit eligible-column whitelist, an explicit never-eligible list, a tie rule, and explicit prohibitions (cross-column comparison, thresholds, normalization, severity conclusions). §0's citation corrected to `DESIGN.md:225-231`. |
| 4 | Minor | `dc_link_energy_excursion_j`/"demands the most stored energy" overstated the metric — three scenarios saturate at the identical numerical floor despite different continuing deficits; `recovery`/segments don't quantify time-outside-band either. | **Historical/superseded — this row's own 0.2 remediation was itself factually wrong** (it claimed duration-outside-band "lives in `protection_timeline.segments`/`events`," which Round 2 found false: `segments` encodes `operating_state`, unrelated to the voltage band, and `bus_energy` events mark the much tighter numerical floor, not the ±1% band). See Round 2's R2-2 row below for the actual, correct disposition — §11 now states plainly that **no** field, new or existing, answers this. |
| 5 | Minor | `max_v_dc_v` appeared in the §7 dataclass/schema but had no §5 catalog entry (unit/source/applicability). | **CLOSED.** Added to §5's table. |
| 6 | Minor | AC-043's "the only call site" was false repository-wide (two existing endpoints already call `build_protection_timeline`); grep alone cannot prove absence of independent classification logic. | **CLOSED.** AC-043 rewritten to state the real, narrower claim (exactly one `ProtectionTimeline` construction per scenario *within the new comparison handler*) and to require a reviewer code-read, not a grep, for the no-competing-classification claim; §10 updated to list this as a review step, not a pytest check. |

**Codex Architecture/Specification Review — Round 2** (focused closure review of v0.2, same
standalone read-only posture, explicitly scoped to auditing Round 1's 6 findings against v0.2's
actual text, plus one new-defect sanity pass on the remediation itself — not a fresh broad review)
independently re-ran all five scenarios' primary/cross-check energy-excursion values directly
(Load Step `1323.3865806125177`/`1323.3865806125186` J, Sustained High Load/Thermal Trip/Grid
Sag/Grid Loss all `0`/`0` or `6399`/`6399` J, maximum difference `9.094947e-13` J — confirming
AC-040's claimed agreement) and confirmed 4 of 6 findings (2, 3, 5, 6) fully `CLOSED`. It found
finding 1 **downgraded from major to a minor residual** (§2's Engineering Question still contained
one stale "no existing authoritative source" sentence the targeted §0/§5/§7/§9 edits had not
reached) and finding 4 **`STILL_OUTSTANDING`**: this draft's own remediation of Finding 4 introduced
a new, inaccurate claim that `protection_timeline.segments`/`events` already supply ±1%-band
duration — they do not (`segments` encodes `operating_state`, a protection-state concept unrelated
to the voltage band; the `bus_energy` events mark the much tighter numerical floor, not the ±1%
band). Final tally: `CHANGES_REQUIRED`, 0 blocking / 0 major / 2 minor. Both are fixed in this
revision: §2's stale sentence corrected to state the real remediation (`e_dc_j` is primary,
reconstructed only as cross-check); §11's duration claim corrected to state plainly that **no**
existing field — new or SPEC-008/009's — quantifies ±1%-band duration, closing the gap honestly
rather than misattributing it to structures that cannot answer it.

**Codex Architecture/Specification Review — Round 3** (final focused closure review of v0.3, same
standalone read-only posture, scoped only to R2-1 and R2-2 plus one bounded end-to-end consistency
scan — not a re-check of findings 2/3/5/6, already twice confirmed closed) independently confirmed
**both R2-1 and R2-2 `CLOSED`** against the actual current text and a direct re-read of
`protection_timeline.py`'s `segments`/`bus_energy`-event/`recovery` logic (lines 336, 431, 587). The
bounded consistency scan found two further, smaller documentation issues: §0's table still carried
`"(mid-run value)"`/`"(early value)"` placeholders for Grid Sag/Grid Loss's `bus_collapse_event_time_s`
despite §14 already recording the confirmed values (`0.448`/`0.2385` s); and the version header's
"0.2 closed all 6" overstated 0.2's actual, only-partially-successful remediation. Final tally:
`CHANGES_REQUIRED`, 0 blocking / 0 major / 2 minor. Both fixed in this revision (0.4): §0's table now
states the confirmed values directly; the version header now says "0.2 attempted remediation of all
6"; this Findings Register's own Round 1 disposition row for finding 4 is now labeled
historical/superseded, pointing to the Round 2 row for the real, correct disposition, rather than
leaving two contradictory "CLOSED" claims for the same finding in the same document.

**Codex Architecture/Specification Review — Round 4** (final confirmation review of v0.4, same
standalone read-only posture, scoped only to confirming Round 3's 2 findings plus one bounded
end-to-end read) independently re-ran the Grid Sag/Grid Loss adapters directly
(`bus_collapse_event_time_s = 0.448` / `0.23850000000000002`, matching §0's table exactly) and
confirmed all three corrections from v0.4 (§0's values, the header's "attempted remediation"
wording, §14's historical/superseded label on finding 4's Round 1 row). It found one further minor
issue: this document's own Status/Version header had not yet been bumped to reflect Round 3's
completion and revision 0.4 — a header-metadata lag, not a content defect. Final tally:
`CHANGES_REQUIRED`, 0 blocking / 0 major / 1 minor. This revision fixes it (the header above now
correctly states v0.4 and records all four review rounds).

**Codex Architecture/Specification Review — Round 5** (final one-item confirmation of this revision,
scoped only to Round 4's single remaining header-metadata finding) independently confirmed the
Status/Version header now states Version 0.4 and accurately summarizes all four prior rounds
consistently with this Findings Register, found no additional issue in a brief end-to-end read, and
returned **`APPROVE`, 0 blocking / 0 major / 0 minor open**.

**Final tally: 0 blocking / 0 major / 0 minor open across five independent Codex review rounds,
ending in an explicit `APPROVE` verdict.** Architecture convergence reached per the governing
brief's convergence requirement.

**PEOS dogfood note on this review's own infrastructure (see §13):** this specification's first
Codex Round 1 invocation (PID 13236/13241, backgrounded via a shell pipe to `tail`) hung for 41+
minutes waiting on stdin that would never arrive, producing zero output and no tracked Codex
rollout/session file — confirmed by direct process inspection (no CPU growth, no network socket, no
rollout file created after launch) before being terminated and relaunched with stdin explicitly
closed (`< /dev/null`) to a dedicated log file, which completed normally in under 2 minutes and
produced the real Round 1 result recorded above. This is recorded as a confirmed PEOS/tooling
dogfood finding, not fixed inside SPEC-010 (§13).
