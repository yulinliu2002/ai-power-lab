# SPEC-012 — Learn by Example V1

**Status:** Approved for implementation (v0.2 plus R19). Codex closure reviews: v0.1 CHANGES_REQUIRED (0 blocking, 6 major, 4 minor), all addressed; v0.2 first closure CHANGES_REQUIRED (0 blocking, 1 major, 2 minor), corrected; second bounded closure **APPROVE** against `main` at `4e6af36`. R19 (three wording constraints from the scenario research handoff) was added afterwards and was not re-reviewed by Codex. Implementation authorized by the Human Engineering Lead's workstream instruction "Continue SPEC-012 implementation" (2026-10-18), with D9 taken as written. Implementation baseline: `main` at `4e6af36`. R16 was clarified during implementation (sixteen added predicate kinds, listed in §6.9); this clarification was **accepted by the Human Engineering Lead (2026-10-19)**, provided the checks remain bounded static checks with no simulation or API change.
**Project:** AI Power Lab
**System:** `frontend/app/` (new `/learn` route; static content plus existing Sandbox endpoints). No change to `src/`, `backend/`, `config/`, `scenarios/`, `content/`, `data/` or `tests/`.
**Version:** 0.2
**Type:** Software Component (presentation and content layer over existing validated simulations; no new engineering model)
**Prepared by:** research thread (v0.1) and implementation thread (v0.2 revision), from `origin/main` at 8552a7a and the PR #8 branch at `4edb079`; **PR #8 is merged: `main` is `4e6af36`** (the SPEC-011 baseline for AC-12).
**Depends on:** PR #8 (SPEC-011), merged at `4e6af36`. See §14.

> **Reading note.** Facts about the repository were checked in the cloud copy of `origin/main`. Where the spec states what the engine currently outputs (§5.2), those classifications (§5.4) were obtained by running the comparison endpoint on a scratch copy of `origin/main`, and were independently reproduced by the Codex review (every classification and state list matched), and are **inputs to the design, not acceptance values**; the implementation must re-derive them from the live response (AC-9).

---

## 0. Human decisions already made (2026-10-18)

- **Presentation-only optional props on existing Sandbox components are approved when necessary.** Constraints: preserve existing default behavior; no physics, numerical calculation, simulation state, API contract or data-fetching changes; no forking or duplicating engineering computation; prefer composition and existing read-only presentation components; every shared-component change needs Sandbox regression and runtime verification (§6.3, AC-12).
- Deeper trade studies may be prioritized after the first Architecture Choices and Learn by Example foundations; Industry & Career is not a prerequisite.

## 1. Engineering Question

Given a disturbance applied to the simplified grid → SST → 800 VDC bus → AI-load chain, can a learner **explain the cause-and-effect chain** from the event to its consequence, name the physical quantity that became limiting, say what the model does and does not represent, and identify what would need to be validated before any real-world conclusion is drawn?

## 2. Motivation

- `docs/PRODUCT_BLUEPRINT.md` §3 lists Learn by Example as one of four product areas, serving Stage 4 (Scenario-Based Explanation). §7 records it as **Not implemented**: the five scenarios exist only inside the Sandbox, where the user must interpret them unaided. The nav entry `/learn` is disabled (`SiteNav.tsx`).
- The Sandbox already shows what happened (telemetry, protection timeline, coordination, comparison, sensitivity). Only Scenario A has the dedicated transient interpretation component (`EngineeringInterpretation.tsx`). All five show backend-supplied outcome, coordination and dominant-stress text (`ProtectionCoordination.tsx`, `scenario_comparison.py`), but none of the five has a guided walkthrough.
- The validated engine is the project's strongest asset. Guided cases turn it into reasoning practice at no engine cost.
- **Product ROI (Blueprint §6):** improves the learner's ability to understand and explain how disturbances propagate through a power chain, and to see the limits of a simplified model.
- **Career ROI:** exercises cause-chain reasoning, identification of limiting constraints, honest model-scope statements, and validation-need formulation, which are core systems-engineering and protection/reliability competencies (Charter §4, P0 items 1-3 and P1 items 4 and 6).

## 3. Scope

A new page `/learn` presenting **five guided cases**, one per existing Sandbox scenario (`load_step`, `sustained_high_load`, `thermal_trip`, `grid_sag`, `grid_loss`). Each case has the same eight-part structure (§6.2), combining:

1. static, hand-authored explanatory content with evidence labels, and
2. live model outputs fetched from the **existing** endpoints and rendered by reused Sandbox components.

Plus: enabling the `/learn` nav entry and the home-page card, the page-level disclosures (§6.5), and a validation record.

## 4. Out of Scope

Anything here needs separate approval (`CLAUDE.md`, Working Agreement).

- Any change to `src/`, `backend/`, `config/default.yaml`, `scenarios/`, `dashboard/`, `content/`, `data/`, `tests/`, `.github/`, `requirements.txt`, `frontend/package*.json`.
- New simulation physics: a storage/UPS model, DC short-circuit or fault-current model, DC-bus protection, grounding/insulation models, arc models, protection-coordination models, or any new scenario or scenario parameter.
- User-adjustable parameters, overrides, sliders, sweeps, or embedding the Sensitivity Study. The five fixed presets only.
- Quizzes, scoring, progress tracking, persistence, accounts, analytics.
- Architecture rankings, performance rankings, claims that any architecture or product is better, or any numeric comparison across architectures.
- Industry & Career route, Streamlit changes, new frameworks or libraries, Docker, ML, cloud.
- Reconciling the lab's illustrative `C_dc` with any external specification (deferred; §13 D5).
- Re-labeling or editing SPEC-011 content.

## 5. Model / Technical Basis

### 5.1 Approach

This is not an engineering model. The technical approach is:

- **Content** is a typed TypeScript module, `frontend/app/lib/learnByExampleData.ts`, in the style of `architectureChoicesData.ts`. Missing fields are compile errors (`Record of ScenarioName to Case`).
- **Live data** comes from the existing `fetchScenario(scenario)` and `fetchScenarioComparison()` in `simulationApi.ts`. No new endpoint, no new response field.
- **Reuse over rewrite.** The page composes existing components wherever their props permit (§6.3). Any component change must be non-behavioral, and the Sandbox must be demonstrably unchanged (AC-12).
- **Evidence labels** reuse the SPEC-011 vocabulary (`public-fact`, `assumption`, `model-output`, `emerging`) and `EvidenceTag`, per Blueprint §5.1. This is a hard dependency on PR #8.
- **No number in static prose** is a model output (§6.4). Model numbers are rendered from the response at runtime, so the narrative cannot drift from the engine.

### 5.2 Governing relations the cases teach (existing, not new)

These already exist in `src/` and `content/learn/*.yaml`. The page may cite them in plain words and display equations; it may not introduce new ones. Units are SI.

| Relation | Meaning | Source in repo |
|---|---|---|
| `dE_dc/dt = P_sst − P_load`, `E_dc = ½ C_dc V_dc²` | DC-link energy balance; bus voltage is the state that moves when delivery and demand differ. E [J], C [F], V [V], P [W] | `src/dc_bus.py`; `level1_system.yaml` energy-balance, dc-bus |
| First-order SST response, time constant `tau_sst` [s] | Delivered power cannot follow demand instantly | `src/sst.py` |
| PI voltage control (`kp` [W/V], `ki` [W/(V·s)]) | Controller pushes power above demand to refill the bus | `src/controller.py`; `EngineeringInterpretation.tsx` |
| `P_loss = P_sst(1−η)/η`, constant η | Conversion loss becomes heat | `src/sst.py` |
| `C_th dT/dt = P_loss − (T−T_amb)/R_th` | Lumped first-order thermal node; time constant `R_th·C_th` [s] | `src/thermal.py` |
| Linear derating between start and trip temperature; debounced, latched trip | Thermal protection state machine | `src/protection.py` |
| Grid availability factor scales available SST power | Modeling assumption, not a ride-through curve | `src/grid.py` |

### 5.3 What the engine represents and does not (verified in repository)

- **Protection is thermal only.** `src/protection.py` states bus-voltage and grid-availability protection are not implemented. The adapter's static `PROTECTION_COVERAGE` lists five functions with `modeled` flags (thermal overtemperature: modeled; DC-bus undervoltage, DC-bus overvoltage, automatic trip reset, grid-availability protection: **not** modeled). The API returns this as `protection_timeline.coverage`. **The page reuses it verbatim** rather than restating it.
- There is no storage, battery, UPS or generator element; the only buffer is the DC-link capacitance `C_dc` (illustrative value, 20 mF in config).
- "Bus collapse" in the grid-sag, grid-loss and thermal-trip cases is the **numerical energy floor** of the integrator, not a physical voltage. The backend's own `outcome_detail` says this and must be shown verbatim.
- No DC fault, short circuit, arc, grounding, insulation or selectivity behavior is represented anywhere.

### 5.4 Engine classifications observed at spec-writing time (design input only)

Run on a scratch copy of `origin/main` (8552a7a), `GET /api/v1/simulations/comparison`:

| Case | `protection_timeline.outcome` | `recovery` | `dominant_stress` | `protection_states_reached` |
|---|---|---|---|---|
| load_step | RIDE_THROUGH | RECOVERED | TRANSIENT_POWER_IMBALANCE | RUNNING |
| sustained_high_load | RIDE_THROUGH | RECOVERED | SUSTAINED_THERMAL_DERATING | RUNNING, DERATED |
| thermal_trip | BUS_COLLAPSE_UNPROTECTED | NOT_RECOVERED | DC_BUS_VIABILITY_LOSS | RUNNING, DERATED, TRIPPED |
| grid_sag | BUS_COLLAPSE_UNPROTECTED | RECOVERED | DC_BUS_VIABILITY_LOSS | RUNNING |
| grid_loss | BUS_COLLAPSE_UNPROTECTED | NOT_RECOVERED | DC_BUS_VIABILITY_LOSS | RUNNING |

Two non-obvious findings that shape the cases:
- In **thermal_trip**, the bus reaches its energy floor (about 14 s in the observed run) *before* the thermal trip latches. Thermal protection is far too slow to prevent electrical collapse once the SST can no longer meet demand. This is the strongest protection-coordination lesson available without new physics.
- In **grid_sag**, the bus reaches the floor during the sag yet the run is classified `RECOVERED`. The page must not describe it as a simple ride-through. Reason (verified in `src/load.py` and `src/dc_bus.py`): the load is an **ideal power sink** that draws its commanded power regardless of bus voltage, and the energy floor is a numerical clamp, so energy is not conserved once the floor is hit; the post-floor trace and the later `RECOVERED` classification have no physical meaning as a real recovery.

## 6. Requirements

### 6.1 Route and entry points
- R1. Add `frontend/app/learn/page.tsx` at route `/learn`. Enable the Learn by Example entry in `SiteNav.tsx` and the home-page card (`frontend/app/page.tsx`); change nothing else in either file.
- R2. A case selector offering exactly the five cases, in the Sandbox's fixed order. A native `role="radiogroup"` of buttons or radios; keyboard-operable (Tab, Enter/Space, and arrow keys if radios). Reuse `ScenarioSelector` / `SCENARIO_OPTIONS` if it fits unmodified.

### 6.2 Case structure (identical for all five)
Each case renders these parts in order. Parts 1, 2, 4, 5a, 6b, 7 and 8 are static authored content. Parts 3, 5b and 6a use live data.

| # | Part | Content rule | Evidence label |
|---|---|---|---|
| 1 | **Situation** | The disturbance in words and the requirement driver (SPEC-011 `DriverId`) it exercises. No numbers. | assumption |
| 2 | **Predict** | One question the learner should answer before looking. Revealing the expected qualitative outcome uses native details/summary elements (no JS state). | assumption |
| 3 | **Observe** | Live: telemetry chart, protection timeline, and the backend's `outcome_label`/`outcome_detail`/`recovery_label` read verbatim, plus `stress_profile.dominant_stress_label`/`_detail` verbatim. | model-output (simplified) |
| 4 | **Explain** | Cause chain in 3 to 6 numbered steps linking event → physical relation (§5.2) → consequence. Names the **limiting quantity**. Plain words; symbols and units allowed; **no numeric values**. | assumption (or public-fact where a textbook principle is cited with §6.6 rules) |
| 5 | **Limits of this model** | **5a (static, authored):** what the simplified model neglects for this case (constant efficiency, lumped thermal node, averaged SST, no storage, numerical floor, etc.). **5b (live, API-owned):** the `protection_timeline.coverage` checklist, verbatim, where the case involves protection. 5b is not authored text and is not covered by the static scan; when the per-scenario request has not succeeded it shows "coverage unavailable: backend required" and no coverage content is fabricated. | 5a assumption; 5b model-output (repository coverage list) |
| 6 | **Modeled vs. not modeled** | Two clearly separated panels. **6a Modeled outcome:** only what the response shows (live). **6b Real-world behavior this engine does not represent:** static list (§6.7). Visibly distinct styling and headings; no simulated curve appears in the second panel. | model-output / see §6.7 |
| 7 | **Decision link** | Names the SPEC-011 driver(s) and boundary this case informs, with a link to `/architecture`. States the engineering decision informed. No verdict or ranking. | assumption |
| 8 | **Validation reasoning** | 2 to 4 items: what would have to be shown before relying on this behavior for a real design, each with a SPEC-011 `EvidenceKind` (analysis, simulation, factory test, site test, conformance review). | assumption |

### 6.3 Reuse (no behavior change)

Actual contracts, verified against the code at `4edb079`:

| Component | Props | Notes |
|---|---|---|
| `TelemetryChart` | `title`, `timeS`, `series`, `yUnit` (required), plus optional markers/bands | reusable through current exports |
| `ProtectionTimeline` | `timeline: ProtectionTimelineData` | reusable; uses `text-muted` for detail text |
| `CoverageChecklist` | `coverage: CoverageEntry[]` | reusable; `entry.detail` rendered in `text-muted` |
| `ProtectionCoordination` | `timeline` | backend-owned strings rendered verbatim |
| `ScenarioSelector` | `selected`, `onSelect`, `disabled?` | reusable; selected state uses primary text on the accent fill (documented contrast gap, `DESIGN.md` §18) |
| `TransientMetricsPanel` | `metrics: TransientMetrics`, `voltageReferenceV` | **not** a `LoadStepResponse`; `computeTransientMetrics(LoadStepResponse)` (`lib/transientMetrics.ts`) produces `metrics`, and that call is the only computation the page may do on a response |
| `EngineeringInterpretation` | `metrics`, `voltageReferenceV` | Scenario A only; its text refers to a shaded Power Balance chart "below", so the Scenario A layout must place it next to that chart |

- R3. Prefer **composition** of the existing read-only presentation components above. `EvidenceTag`, `EVIDENCE_LABEL_TEXT`, `SOURCE_KIND_TEXT`, `DISCLOSURES`, `REFERENCES`, `EvidenceKind` come from SPEC-011.
- R4. **Approved presentation-only props (human decision, §0).** Where a reused component cannot meet R14 (no `text-muted` for essential text; focus treatment) or `DESIGN.md` §18 contrast, the implementer may add an **optional presentation prop** with a default that leaves `/sandbox` output byte-identical, limited to: a text-tone token, a focus-outline class, and an accent-contrast token. Candidate components: `ProtectionTimeline`, `CoverageChecklist`, `TelemetryChart` (label text), `ScenarioSelector`. Not allowed: any change to props that carry data, to computation, to fetching, to state, to API types or contracts, to markup structure beyond the added class hook, or any forked or duplicated component. The implementer lists every changed component and prop in the validation record and shows, per R4/AC-12, that Sandbox output is unchanged.
- R5. `EngineeringInterpretation` for Scenario A is shown as-is (it is number-driven from `metrics`). Do not duplicate its two lessons in static Explain text. Because its content and the coverage checklist are live, they sit outside the static scan boundary (§6.4, AC-4).

### 6.4 Numbers and labeling

- R6. **Static/live boundary and scan.** Authored static prose is rendered inside elements that carry `data-static-prose`. The static scan covers exactly: parts 1, 2, 4, 7 and 8; part 5a (authored limits); and the not-modeled panel (part 6b). **Outside the scan** (live, API-owned): part 3, part 5b (the coverage checklist), part 6a (modeled outcome), `EngineeringInterpretation` and `TransientMetricsPanel`. The scan strips an explicit allowlist, then fails on any remaining digit:
  - case identifiers (`load_step` etc.), driver ids (`RD1`–`RD7`), boundary ids, the tokens `V1`, `SPEC-011`, `SPEC-012`;
  - symbols, subscripts and exponents inside displayed equations (for example `½`, `²`, `C_dc`, `V_dc`, `tau_sst`, `R_th·C_th`) and list numbering;
  - citation identifiers: reference ids, version strings and section identifiers in an attributed citation (for example "Rev 0.3.0", "§7.2.4").
  Authored prose may **not** contain model values, performance figures, ratings, durations or percentages, with or without units.
- R7. Every static item carries an evidence label and a one-line basis. `public-fact` and `emerging` items must cite a `REFERENCES` entry (SPEC-011 rule) whose relevant section the implementer opened. Where the source cannot be opened, the claim is **narrowed to what an opened source says, or omitted**. `assumption` is for the author's own reasoning only, not a default bucket for unverified vendor or consortium claims.
- R8. No ranking or superlative language ("best", "wins", "superior", "safer", "more reliable") about any architecture or product.
- R9. Model-output items state they come from the simplified model and are not predictions for real equipment.

### 6.5 Disclosures (visible text)
Reuse `DISCLOSURES.sim`, `.block` and `.illustrative` verbatim from SPEC-011. Add:
- D-L1. "These cases run the five fixed Sandbox scenarios on a simplified average-value model. Results show how the model behaves under stated illustrative assumptions, not how real equipment behaves."
- D-L2. "In the grid-sag, grid-loss and thermal-trip cases, 'bus collapse' means the integrator reached its numerical energy floor. It is not a physically meaningful residual voltage."
- D-L3. "Real-world fault behavior listed under 'not modeled' is described from public sources or general engineering principle. It is not simulated here, and no result on this page validates it."

### 6.6 Source discipline
- R10. A `public-fact` or `emerging` item may cite only a source whose relevant section the implementer actually opened; the validation record lists, per cited source, the section opened. A textbook or standard that cannot be inspected is not described as verified: the claim is narrowed, replaced with an accessible source, or omitted. Vendor and consortium statements are attributed, not endorsed, and an attributed proposal or recommendation is described as such (a draft specification's recommended setting is not a requirement or a measured result). (Same rule the Human Engineering Lead applied to PR #8.)
- R11. New references are added to the shared registry **additively**: new `ReferenceId` union members and new entries, with no edit to any existing entry. Each new entry supplies the now-required fields (`kind`, `inspection`, `citation`) and URL; an access date goes in `inspection` text unless an optional `accessed` field is added to the `Reference` interface (an additive type change, no existing entry touched). Candidate accessible primary sources, each requiring the implementer to open it first: OCP SST Specification Rev 0.3.0 (already `OCPSST`), OCP LVDC white paper v1.0 (already `OCPWP`), OCP Mt. Diablo v1.0.0 (https://www.opencompute.org/wp-content/uploads/2026/10/OCP-Specification-Mt.-Diablo-Disaggregated-Power-Rack-Specification-v1.0.0.pdf), and the NVIDIA developer technical blog on the 800 VDC ecosystem (https://developer.nvidia.com/blog/building-the-800-vdc-ecosystem-for-efficient-scalable-ai-factories/). The NVIDIA technical blog is a **separate entry** (for example `NVIDIAEC`), not a reuse of the existing `NVIDIA` entry, which refers to a different blog post. Numbers from any source are **not** used in V1 (R6, R12).
- R12. The "not modeled" panel (§6.7) contains **no numeric values**.

### 6.7 "Real-world behavior this engine does not represent" content
Static, per-case plus one shared list. Each item: name, one sentence on what physically happens in real systems, label, basis. Candidate items (final wording in implementation, subject to R10; an item whose source cannot be opened is narrowed or omitted):

| Topic | Cases it is shown with | Intended basis (what the opened source must say) |
|---|---|---|
| Fault current from a converter-fed DC system: three distinct things kept separate — (i) upstream MVAC short-circuit **withstand** capability of the SST (SST spec §4.2, where the duration is marked TBD); (ii) **controlled downstream contribution** during a fault (SST spec §4.3 "Overload Rating", a recommended constant-current setting for fault-protection coordination, after which the SST may trip); (iii) **capacitor discharge** into a DC fault (white paper §7.2.4) | thermal_trip, grid_sag | OCP SST specification and OCP white paper. `emerging`: a draft specification's *recommended setting*, not a requirement or measured result. This engine models none of the three |
| DC arc interruption (no natural current zero) | thermal_trip | The OCP white paper's description of how fuses and breakers interrupt DC by creating an arc voltage above the system voltage (§7.2.4); a textbook only if opened; otherwise narrowed to the white paper's wording |
| Grounding scheme (floating/HRG vs solid) and ground-fault/insulation monitoring | thermal_trip | OCP white paper (grounding sections) and SST spec §4.3 "DC grounding" (IT ground, detailed design TBD); Mt. Diablo only if opened — `emerging` |
| Selective protection coordination across stages | thermal_trip, grid_sag | OCP white paper §7.2.4: no standard or recognized practice for coordinating protection for the **converter-fed DC fault behavior it describes, in particular the capacitor-discharge peak**; and, separately, white paper §4.2: migration to solid-state solutions may need a new approach to comprehensive coordination studies — `emerging`; cite the two locations separately and do not generalize beyond either scope |
| Voltage/frequency ride-through behavior of real converters | grid_sag | OCP SST spec §5.1.2–5.1.3 ride-through requirements, whose wording applies to the SST **together with energy storage** (the implementer opens them and preserves that context); this engine uses a proportional availability assumption instead — `emerging` |
| Energy storage and backup (battery/capacitor holdup, UPS, generator) | grid_loss, load_step | SST spec §3 (MV-UPS coupling) and Mt. Diablo (BBU/holdup) only if opened; the NVIDIA technical blog entry only if opened. Otherwise narrowed to the repository fact that this engine has no storage element |
| Fast AI-load power swings at the grid interface | load_step | NVIDIA technical blog entry (vendor-stated), only if the implementer opens the relevant passage; otherwise omitted |
| Load- and temperature-dependent efficiency; cooling system dynamics; multi-node thermal behavior | sustained_high_load | `content/learn` `what_ignored` (repository) — about the model; general principle only with an opened reference |
| Trip reset and restart sequencing | thermal_trip, grid_loss | `PROTECTION_COVERAGE` (repository): states that this **model** has no reset logic (`public-fact` about the model). It says nothing about real equipment restart behavior; a real-world restart statement needs its own opened source or is omitted |
| Internal multi-stage structure of a real SST | all | `DISCLOSURES.block`; the OCP SST specification's black-box composition (§4.1) does not state a stage count |

### 6.8 States and accessibility
- R13. **Two independent requests**, each with its own loading, success and error state: (A) the per-scenario run (`fetchScenario`; supplies telemetry, protection timeline and `coverage`) and (B) the comparison (`fetchScenarioComparison`; supplies `stress_profile`). Required behavior: static parts (1, 2, 4, 5a, 6b, 7, 8) always render, including on first load with the backend down; if A fails, parts 3, 5b and 6a show an error naming the missing backend and no coverage is fabricated; if B fails but A succeeds, the dominant-stress block alone shows its error while telemetry and timeline render; both failing shows both errors. Loading is shown per request. **Rapid case switching** is guarded (a request-id check as in `SensitivityStudy.tsx`) so a slower earlier response cannot overwrite the selected case. The page must not blank or throw in any combination.
- R14. Essential text uses `text-secondary` or stronger, never `text-muted` (SPEC-011 review lesson); reused components get the §6.3/R4 optional presentation props where needed. Obey `DESIGN.md`: flat surfaces, existing tokens only, no new accent color, no shadows, live numerics in the tabular mono face, conceptual/static content carries the "illustrative" label rule. `/learn` provides the `#references` anchor that `EvidenceTag` links to.
- R15. Works at 375 px and 1280 px widths; no horizontal page scroll; no console errors.

### 6.9 Qualitative claim contract (AC-9)

- R16. Each authored claim in Predict (part 2) and Explain (part 4) that can be checked against engine output is written as a typed `Case.claims` entry in `learnByExampleData.ts`. A claim is a hypothesis **under test**, never a value the UI renders; the UI always shows backend strings. Claim kinds and their predicates, evaluated on the live responses of requests A and B (§6.8), using only response fields:
  - `outcome`, `recovery`, `dominantStress`: equality with `protection_timeline.outcome`, `protection_timeline.recovery`, `stress_profile.dominant_stress`.
  - `statesReached`: equals the set of distinct values in `timeseries.operating_state`.
  - `voltageFalls`: `min(v_dc_v) < voltage_reference_v · (1 − band)`; `voltageRecovers`: the final `v_dc_v` is within `voltage_reference_v · (1 ± band)`; `reachesFloor`: `min(v_dc_v) <= thresholds.floor_voltage_v` (protection scenarios). `band` is the settling-band convention already used in `lib/transientMetrics.ts`; the implementer reads the value from that file and records it, rather than copying a number into the spec.
  - `order`: `protection_timeline.bus_collapse_event_time_s` before `trip_event_time_s` (the thermal-trip lesson).
  - **Predicate kinds added during implementation (R16 clarification, accepted by the Human Engineering Lead 2026-10-19)** so that every checkable Predict/Explain assertion has a typed claim, as R16 requires: `voltageStaysInBand` (min and max `v_dc_v` within the band throughout); `noSustainedDeficit` (maximum of `p_load_w − p_sst_w` at most one percent of peak load); `temperatureRises` (peak `temperature_c` above its start); `temperatureRiseSlows` (temperature rise in the last quarter of the run smaller than in the first quarter); `tripAfterDebounce` (trip time at least `thresholds.thermal_trip_time_s` after `temperature_c` first reaches `thresholds.thermal_trip_c`); `deliveryExceedsDemandAfterEvent` (`p_sst_w` above `p_load_w` at some sample after `events[0]`); `deliveryShortfallDuringSag` (`p_sst_w` below `p_load_w` at some sample while `grid_voltage_pu` is below nominal); `deliveryDecays` (`p_sst_w` non-increasing after the first unavailable-grid sample and ending under five percent of load); `deliveryShortfallAfterEvent` (`p_sst_w` below `p_load_w` at the sample immediately after `events[0]`, the initial deficit); `targetAboveDemandWhileBelowRef` (`p_target_w` above `p_load_w` at a sample where `v_dc_v` is outside the band below reference); `endsInState` (every `operating_state` in the last tenth of the run equals the stated state and `temperature_c` changes by at most five percent of the total rise over that tail, i.e. settled); `derateBelowDemand` (`thresholds.rated_power_w × derate_factor` below `p_load_w` at some sample); `deliveryShortfallPersists` (from the first shortfall sample, `p_sst_w` stays below `p_load_w` to the end of the run); `floorBeforeSagEnds` (first sample at the floor has grid voltage still below nominal); `targetGoesToZero` (`p_target_w` is zero from the sample after `grid_available` first turns false to the end); `gridStaysUnavailable` (`grid_available` false from its first false sample to the end). `temperatureRiseSlows` additionally requires `temperature_c` non-decreasing, and `tripAfterDebounce` additionally requires `temperature_c` to stay at or above the trip threshold from first crossing to the trip. Finer causal-mechanism statements (for example why a debounce exists) are not scripted; they are the R17 reviewed set.
  - A claim whose predicate is false is reported as a mismatch and the prose is corrected (the spec does not hard-code §5.4 values).
- R17. **Not machine-checkable and therefore reviewed, not scripted:** that an Explain step's causal link and named limiting quantity follow from a §5.2 relation. The validation record carries a table mapping each Explain step to its §5.2 relation(s) and the reviewer's note. Passing the script does not establish causal correctness.
- R18. Script: committed in the validation record's appendix (as in SPEC-011), run as `node <script>.mts --base http://localhost:8000` against a running backend, with `learnByExampleData.ts` imported directly; output quoted in the record.

- R19. **Three wording constraints from the scenario research handoff** (design-level, apply to authored prose in every case):
  (a) **`RECOVERED` is a classification, not a physical recovery claim.** For grid_sag, grid_loss and thermal_trip, authored text must state that the load is an ideal power sink and the energy floor is a numerical clamp, so energy is not conserved at the floor (this extends D-L2 for grid_sag, where the run is classified `RECOVERED` after floor contact).
  (b) **No claim about the origin of the sag preset.** The sag depth and duration are illustrative presets. Authored text must not say or imply they are derived from, tested against, or compliant with SEMI F47 or any other published ride-through standard. A published sag requirement may be named only as an example of the kind of requirement real equipment faces, from an opened source, labeled `emerging`/`public-fact` per R7, and without reproducing its numbers.
  (c) **No no-controller counterfactual as a shown result.** The Scenario A comparison of behavior without the PI controller needs engine parameters the page may not change (Out of Scope). Static Explain text may describe the controller's role qualitatively (R5 already shows `EngineeringInterpretation`); any counterfactual statement is labeled `assumption`, contains no numbers, and is not presented as a model output.

## 7. Assumptions

- The five scenarios, their fixed presets, and the existing endpoints are stable (covered by `tests/test_api.py`, `tests/test_scenario_comparison.py`).
- A backend is reachable at the frontend's configured base URL during use; its absence is handled (R13).
- Qualitative expectations in "Predict" (e.g., "bus voltage falls then recovers") hold for the fixed presets. They are checked against live responses in verification (AC-9), not hard-coded as outputs.
- Learners are engineering-literate (Blueprint §2).
- Static prose is steady-state in nature (content), the data it accompanies is a time-domain simulation of 0.5 s to hundreds of seconds depending on case.

## 8. Case content outline (normative for coverage, not final wording)

| Case | Situation / driver | Limiting quantity (Explain) | Key Limits (part 5) | Decision link |
|---|---|---|---|---|
| **load_step** | Step in AI demand; RD2 Load dynamics | Accumulated energy deficit in the DC link, set by `tau_sst`, PI response and `C_dc` | Averaged SST; `C_dc` illustrative; no storage; no grid-side effects | RD2; storage and monitoring-control boundaries |
| **sustained_high_load** | Sustained demand within rating; RD5 Conversion losses, RD6 Footprint | Heat accumulation versus thermal resistance (time constant `R_th·C_th`) | Constant efficiency; single lumped node; illustrative linear derating; no cooling dynamics | RD5, RD6; conversion-distribution boundary |
| **thermal_trip** | Demand exceeds what the derated SST can supply; RD4 Safety/protection, RD3 Availability | Derated available power versus demand; and protection **response time versus electrical collapse time** | Thermal-only protection; latched trip, no reset; no voltage-based trip; numerical floor | RD3, RD4; protection coordination, validation of fast protection |
| **grid_sag** | Temporary grid voltage dip; RD2, RD7 | Available power versus demand during the dip, buffered only by `C_dc` | Proportional availability assumption (not a ride-through curve); no input-current limiting; numerical floor; `RECOVERED` after floor contact is not "ride-through"; ideal-sink load and the floor clamp (energy not conserved at the floor) | `mv-utility` boundary; RD2, RD7 |
| **grid_loss** | Complete supply loss; RD3 Availability | Stored energy in `C_dc` versus demand | No storage/backup element; numerical floor; no restart | `storage-backup` boundary; RD3 |

Each case's Explain steps must use only relations listed in §5.2.

## 9. Acceptance Criteria

- [ ] **AC-1 Route.** `/learn` renders; nav and home card enabled; no other nav/home change.
- [ ] **AC-2 Cardinality.** Exactly five cases; each has all eight parts (compile-time `Record of ScenarioName to Case` plus a mechanical script).
- [ ] **AC-3 Labels.** Every static item has an evidence label and basis; every `public-fact`/`emerging` item cites at least one registry entry.
- [ ] **AC-4 No static numbers.** A scan of the rendered text of every `data-static-prose` node (parts 1, 2, 4, 5a, 6b, 7, 8) finds no digit after the R6 allowlist is stripped; the scan boundary excludes parts 3, 5b, 6a, `EngineeringInterpretation` and `TransientMetricsPanel`. The script reports the nodes scanned and the tokens stripped.
- [ ] **AC-5 No ranking.** Term search finds none of: best, worst, wins, winner, superior, inferior, safer, more reliable, outperforms.
- [ ] **AC-6 Disclosures.** The six disclosures (`sim`, `block`, `illustrative`, D-L1, D-L2, D-L3) appear in rendered text verbatim (D-L2 on the three bus-collapse cases at minimum).
- [ ] **AC-7 Modeled vs. not modeled.** In each case panels 6a and 6b are separated; 6b contains no chart, no number, and no model output (6b is a `data-static-prose` node, so AC-4 also applies).
- [ ] **AC-8 Verbatim backend strings.** For each case, the rendered text contains each of `outcome_label`, `outcome_detail`, `recovery_label`, `dominant_stress_label`, `dominant_stress_detail` as an exact string leaf of the API response, and each `coverage` entry's `function`, `modeled` flag and `detail` field-by-field (not the coverage object against rendered text). Checked in the browser against the live response.
- [ ] **AC-9 Narrative-to-engine consistency.** The R18 script evaluates every `Case.claims` entry (R16 predicates) against live responses of all five scenarios and reports any mismatch; zero mismatches required. R17's causality review table is complete. The implementer re-derives §5.4 from the live endpoint; §5.4 values are not hard-coded. The script is a consistency check, not proof of causal or physical correctness.
- [ ] **AC-10 Backend and failure behavior (R13).** Verified for: backend down on first load; request A failing alone; request B failing alone; both failing; rapid switching across all five cases with a deliberately slowed response. Static parts always render; error states name the missing backend; no fabricated coverage; no uncaught exception; the final display matches the last selected case.
- [ ] **AC-11 Source record.** The validation record lists each cited source and the section actually opened, and each unverified textbook/standard reference with the narrowing applied (R10).
- [ ] **AC-12 No protected-path change; Sandbox unchanged.** Baseline is the **merged SPEC-011 commit `4e6af36`** (recorded in the validation record). The inventory is the union of `git status --short` (staged, unstaged, untracked) and `git diff --name-status <baseline>`; it shows no file under `src/`, `backend/`, `config/`, `scenarios/`, `dashboard/`, `content/`, `data/`, `tests/`, `.github/`, `requirements.txt`, `frontend/package*.json`. Every existing component edit is limited to R4 optional presentation props and is listed with its prop. Sandbox equivalence: with the deterministic backend running, for each of the five scenarios the `/sandbox` DOM text and class lists of every edited component are captured before and after the change and are identical; additionally `/architecture` and `/system-map` render unchanged except for new `REFERENCES` entries (§14).
- [ ] **AC-13 Accessibility and layout.** Native keyboard operation of the selector and details element; no `text-muted` for essential text including inside reused components rendered on `/learn`; focus treatment on every control; `/learn` provides the `#references` anchor; 375 px and 1280 px without horizontal scroll or console errors.
- [ ] **AC-14 Existing checks.** `pytest -q` unchanged (all prior tests pass), and `npm run lint`, `npm run typecheck`, `npm run build` pass; CI green.

## 10. Verification Plan

| Layer (ENGINEERING.md) | Check |
|---|---|
| Unit | Compile-time completeness (AC-2); the R18 script exercising AC-3 to AC-5 on `learnByExampleData.ts` and the rendered `data-static-prose` nodes |
| Physics invariants | None new. Existing `tests/test_dc_bus.py` and related remain the invariants; `pytest -q` run unchanged (AC-14) |
| Regression | `/sandbox` unchanged by the AC-12 before/after capture for all five scenarios; `/architecture` and `/system-map` regression; existing API/comparison tests pass |
| Scenario validation | AC-9 R16 predicates against live responses; AC-8 string-leaf comparison; AC-10 failure-state walkthrough |
| Manual/UI | Browser walkthrough at 375 px and 1280 px; keyboard walkthrough; console clean (AC-13) |

Commands (run by implementer and recorded in `docs/validation/SPEC-012-validation.md`; reviewer re-runs):
```
pytest -q
cd frontend && npm run lint && npm run typecheck && npm run build
git status --short; git diff --name-status 4e6af36     # inventory incl. staged, unstaged, untracked
# plus the AC-3..5, AC-8, AC-9 scripts, committed under the validation record or documented in it
```
Independent review: Codex reviews the **actual artifacts** (data module, rendered text, validation record) for technical reasonableness and labeling. Codex review is not itself validation evidence, and any partial review must be reported as partial.

## 11. Known Limitations

- All cases are the SST slice only; nothing here validates or compares Conventional AC or AC-fed 800 VDC.
- The three bus-collapse cases end at a numerical floor; the physical consequences of real bus collapse are not shown.
- `C_dc` is an illustrative value (config comment). Public SST specification work recommends an upper bound on DC-link capacitance relative to rating; the lab's value is not derived from it and the page makes no such comparison in V1 (D5).
- The page cannot teach DC fault behavior, grounding, arc interruption, or coordination quantitatively; it names them as unmodeled and links them to validation needs.
- The static "Predict" mechanism has no scoring or memory by design.
- Scenario A's no-controller counterfactual cannot be run from the page (no parameter overrides); it is prose-only under R19(c), or deferred to a later spec with separate approval.
- The "not modeled" panel depends on source access; an item whose source is not opened is narrowed to what an opened source supports, or omitted; `assumption` is reserved for the author's own reasoning (R7, R10).
- Deep-linking to a specific driver on `/architecture` is not specified (not verified that the selector supports it); V1 links to the page.
- Numbers quoted in the research report were read through a summarizer and are not used in V1.
- The R18 script checks consistency of qualitative claims with engine output; it cannot establish that an Explain step is causally or physically correct (R17: reviewed, not scripted).
- Section order follows the research draft (Requirements §6, Assumptions §7) rather than the template order (Assumptions before Requirements); not reordered to keep cross-references stable. All template sections are present.
- Optional presentation props on shared Sandbox components (R4) are a human-approved exception to "no change to existing components"; each needs the AC-12 before/after capture.
- Mt. Diablo v1.0.0 and the NVIDIA technical blog were not opened by the draft's authors or this review; any §6.7 item resting on them is narrowed or omitted unless the implementer opens the cited passage.

## 12. Dual ROI Statement (Charter §3, Blueprint §6)

- **Product ROI:** closes Blueprint Stage 4 with no engine change; connects Sandbox behavior to Architecture Choices drivers; makes model limits explicit.
- **Career ROI:** practice in cause-chain explanation, limiting-constraint identification, model-scope honesty and validation planning, directly relevant to Systems Engineering, protection/reliability and controls-integration roles.

## 13. Decisions for the Human Engineering Lead

| ID | Decision | Recommendation (this draft assumes it) |
|---|---|---|
| D1 | Live data from existing endpoints vs. static snapshots | Live, with the R13 empty state |
| D2 | Content as a TS module vs. serving `content/learn` YAML through a new endpoint | TS module (no backend change) |
| D3 | Include the shared "not modeled" fault-behavior panel (§6.7) | Yes |
| D4 | Predict step as native details reveal (no state) | Yes |
| D5 | `C_dc` vs. public SST spec guidance | Out of V1; explain as illustrative; revisit in a trade-study spec |
| D6 | Reference-registry additions to `architectureChoicesData.ts` (additive) vs. a separate `learnReferences` module | Additive, to keep one registry; requires PR #8 merged |
| D7 | Route label and wording of case titles | `/learn`, "Learn by Example" per Blueprint |
| D8 | Presentation-only optional props on existing Sandbox components | **Decided (approved 2026-10-18)** within the constraints in §0 and R4 |
| D9 | Static-prose scan allowlist (R6) and the settling-band convention used by R16 | Draft proposes the lists above; Human Engineering Lead may amend the allowlist before approval |

## 14. Dependencies and Sequencing

1. **PR #8 is merged at `4e6af36`** (provides `EvidenceTag`, label types, `DriverId`, `DISCLOSURES`, `REFERENCES`, nav pattern). `4e6af36` is the AC-12 baseline. Implementation does not start before this spec is approved.
2. **Shared-data contract as of `4e6af36`** (the merged state; identical to PR #8 head `4edb079`): `DriverId` is the lowercase union `rd1`–`rd7` (display ids RD1–RD7 are labels); `EvidenceLabel` = `public-fact | assumption | model-output | emerging`; `EvidenceKind` = `analysis | simulation | factory test | site test | conformance review`; `DISCLOSURES` keys `sst`, `block`, `sim`, `illustrative`, `noWinner`; `Reference` requires `id`, `kind` (`repository-source | textbook-standard | consortium-document | vendor-statement`), `inspection`, `citation`, with optional `url` and `verifiedDate`; `SOURCE_KIND_TEXT` maps kinds to display text. Label counts after the source audit: 13 public-fact, 7 emerging, 1 model-output (cells). Existing `REFERENCES` ids: NVIDIA, OCP, OCPWP, OCPSST, SYSMAP, SANDBOX, MOHAN, GRAINGER, GOLDBOOK, NEC, IEEE1584, GARZON.
3. **Registry additions change `/architecture`**, which renders every `REFERENCES` entry in its References section. R11 additions therefore need a regression check of `/architecture` (new entries appear; nothing else changes), and D6 stays "additive to one registry". Extending the `ReferenceId` union is part of the additive change.
4. No dependency on Blueprint §11.2 open items; wording follows the Blueprint. No dependency on Phase B cleanup or Streamlit status.

## 15. Not Verified by This Draft

- Component contracts in §6.3 were verified by the Codex review and by a read of the code at `4edb079`; behavior of each component under the new optional props is verified only at implementation (AC-12).
- Whether the frontend is deployed with a backend (affects D1 only).
- The SST specification (24 pages) was read from extracted text and the white paper's cited sections were read, but Mt. Diablo v1.0.0 and the NVIDIA technical blog behind some §6.7 items were not opened.
- §5.4 values come from one scratch run, reproduced independently by Codex (read-only run of the comparison function: every classification and state list matched; thermal floor contact and trip times observed). They are design input, not acceptance values.
