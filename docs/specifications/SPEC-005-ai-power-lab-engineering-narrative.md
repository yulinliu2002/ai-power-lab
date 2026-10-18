# SPEC-005 — AI Power Lab Engineering Narrative

> **Historical note:** PEOS is retired (git tag `pre-peos-retirement`). Implementation now follows the Claude + Codex + GitHub PR process in `ENGINEERING.md`; PEOS references below describe the process at the time of writing. Requirement text is unchanged.

**Status:** Approved
**Project:** AI Power Lab
**System:** React/Next.js frontend (`frontend/app/`) — presentation/narrative layer over Scenario A; no new engineering model, no new backend surface
**Version:** 0.2
**Type:** Software Component (frontend narrative/architecture)

---

This specification governs the AI Power Lab React frontend's narrative and
visual architecture going forward, so that PEOS can implement subsequent
coherent visual/narrative slices without re-deciding product direction each
time. The first slice governed by this spec — **03 / ANALYZE — Energy
Deficit** — is specified in full in §10; everything else in this document is
the standing contract that slice, and future slices, must satisfy.

**Revision 0.2 — Resolved Decisions.** Revision 0.1 raised four items as
open Human Gates. The Human Engineering Lead has resolved all four; none
remain open, and this revision is Approved.

1. **Stage labeling (§9):** OBSERVE → TRANSIENT → ANALYZE is the
   information/narrative architecture, not a requirement to render three
   numbered, dashboard-style section headers. The current continuous
   engineering narrative is preserved as-is.
2. **ANALYZE-slice interaction (§11, §17):** No new interactive
   toggle/highlight control is added for this slice. V1 of 03 ANALYZE
   teaches the causal relationship through hierarchy, simulation-derived
   data, visualization, annotation, and explanation only. New
   interaction is deferred to a future specification revision, and only
   if it clearly improves engineering understanding — it is not a
   condition this slice's implementation needs to escalate.
3. **Component boundary (§10 R-7):** Confirmed not a Human Gate. The
   implementer may choose the smallest maintainable implementation
   boundary (new component vs. extending/refactoring an existing one),
   provided behavior and the Acceptance Criteria (§14) are satisfied.
4. **ΔE physics interpretation (§7 Constraint 3):** Confirmed as stated:
   `dE_dc/dt = P_sst - P_load`, therefore, during a deficit interval,
   `energy deficit = ∫(P_load - P_sst) dt`, which is the loss of stored
   DC-link energy over that interval, subject to the model's existing
   definitions/boundaries. The frontend must not create a second
   numerical physics integrator merely to visualize this relationship;
   it uses existing simulation-derived/backend-provided data and the
   already-permitted closed-form presentation metric
   (`E_dc = 1/2 C_dc V_dc^2`, i.e. `energyDeficitKj` in
   `transientMetrics.ts`) as its computational source of truth.

## 1. Purpose

AI Power Lab's frontend is an **engineering learning experience** — an
interactive engineering narrative that teaches a specific causal chain in
the SST-powered 800 VDC AI data-center power system — not a generic
telemetry dashboard. This specification exists to:

- record the approved product direction (narrative model, grammar, visual
  language) as a durable repository artifact, not chat history, per
  `ENGINEERING.md`'s source-of-truth hierarchy;
- give PEOS participants (Human Engineering Lead, Claude Code, Codex, CI)
  a shared, testable definition of "done" for this and future narrative
  slices, so a slice can be implemented and independently reviewed without
  further product decisions being made ad hoc during implementation;
- specify the first slice — 03 / ANALYZE — Energy Deficit — concretely
  enough to implement and verify.

## 2. Scope

This specification covers:

- the standing product/learning model for the AI Power Lab frontend
  (§5–§8): the narrative progression, the engineering causal grammar, the
  physics-integrity constraints on the frontend, and the visual/design
  constraints that apply to every current and future narrative slice;
- the structure of the approved "Concept 03" visual direction as three
  narrative stages — 01 OBSERVE / Steady State, 02 TRANSIENT / Minimum
  Vdc, 03 ANALYZE / Energy Deficit — and how they relate (§9);
- full, implementable, testable requirements for the **03 / ANALYZE —
  Energy Deficit** slice (§10–§13): the first and only slice this
  revision authorizes for implementation;
- acceptance criteria, verification requirements, and human-gate
  conditions for that slice (§14–§16).

This specification does **not** itself implement anything. It is the
governing artifact that the next PEOS Specification → Implementation step
implements against.

## 3. Non-Goals

This specification does not:

- redesign 01 OBSERVE or 02 TRANSIENT. Their current combined
  presentation (`frontend/app/page.tsx`'s event banner, KPI strip, power
  flow schematic, and time scrubber + synchronized charts) is accepted as
  the implemented form of those two stages. The ANALYZE slice may touch
  them only to the minimal extent needed to integrate ANALYZE into the
  existing single-page narrative (e.g., section ordering, a heading, a
  shared value already computed) — not to re-lay-out, re-style, or
  re-scope them;
- introduce a new design direction, new chart types, new color roles, or
  new DESIGN.md tokens. DESIGN.md and the already-implemented Concept 03
  visual language (`PowerFlowSchematic.tsx`, `theme.ts`) remain
  authoritative;
- change simulation physics, the FastAPI contract (`backend/`), or
  anything under `src/`;
- add new Scenario A parameters, new scenarios, new routes, or new pages.
  The narrative remains one continuous page;
- specify pixel-exact layout where product/engineering intent does not
  require it. Where this spec says "a labeled section" or "visually
  adjacent," implementers retain layout discretion within DESIGN.md's
  existing rules;
- cover any subsystem outside the V1 chain defined in `CLAUDE.md` (Grid →
  simplified SST → 800 VDC bus → dynamic AI load).

## 4. Source-of-Truth Hierarchy

This specification follows `ENGINEERING.md`'s source-of-truth hierarchy.
Specifically, for this slice:

1. This approved specification.
2. `CLAUDE.md` (project-wide modeling rules and scope) and `DESIGN.md`
   (visual constitution) — both already approved and binding on this spec.
3. Prior approved specifications (`SPEC-002-scenario-a-sensitivity-study.md`)
   and decisions (`docs/decisions/`) where they constrain the frontend's
   relationship to backend-computed values.
4. This document's own Acceptance Criteria (§14).
5. The implementation.
6. Automated tests and recorded verification results.
7. Agent conversation history — never authoritative, per `ENGINEERING.md`.

If an instruction elsewhere conflicts with `CLAUDE.md`'s Out-of-Scope list
or Modeling Rules, `CLAUDE.md` wins and the conflict must be reported, not
silently resolved (per `CLAUDE.md`'s Engineering Workflow section).

## 5. Product / Learning Model

AI Power Lab's frontend teaches through a fixed four-stage learning
progression, applied to Scenario A (the AI load-step transient) and to any
future scenario added to this frontend:

```
OBSERVE  ->  UNDERSTAND  ->  EXPLAIN  ->  EXPERIMENT
```

- **OBSERVE** — see the system's present state: topology, live values,
  whether it's steady or in transient.
- **UNDERSTAND** — see *that* something changed and *how far* — a number,
  a minimum, a deviation — without yet being told why.
- **EXPLAIN** — see *why* it changed, grounded in the governing
  equation(s), in plain language first and the equation second (see
  `EngineeringInterpretation.tsx` for the existing pattern this
  continues).
- **EXPERIMENT** — be able to change a parameter and see the same
  causal chain respond differently (`ExperimentPanel.tsx`,
  `SensitivityStudy.tsx`).

Every narrative slice maps onto at least one of these four stages. A slice
that does not advance the learner along this progression is out of scope
for this document's intent, regardless of visual polish.

## 6. Engineering Narrative Grammar

Within OBSERVE/UNDERSTAND/EXPLAIN, the frontend presents engineering state
in a fixed order — topology first, abstractions (equations, accumulated
quantities) last:

```
TOPOLOGY  ->  STATE  ->  TIME  ->  CAUSE  ->  PHYSICS
```

- **TOPOLOGY** — where this value lives in the system (grid → SST → 800
  VDC bus → AI load); the power-flow schematic.
- **STATE** — the live instantaneous values at the topology's nodes
  (V_dc, P_load, P_sst, ΔP).
- **TIME** — how those values evolved across the run (the synchronized
  telemetry charts, the time scrubber).
- **CAUSE** — the plain-language causal account of why the state moved
  the way it did.
- **CAUSE** is followed by **PHYSICS** — the governing equation(s) that
  make that causal account checkable, not just assertable.

The chain this grammar must let a learner trace for Scenario A, in this
exact causal order, is:

> AI workload increases → P_load increases → SST cannot respond
> instantaneously → P_load > P_sst → DC bus supplies the energy deficit →
> stored DC-link energy decreases → V_dc decreases → controller increases
> SST command → SST catches up / may overshoot → power mismatch closes →
> V_dc recovers.

This chain is already partially narrated across `page.tsx`'s `EventBanner`,
`PowerFlowSchematic`, and `EngineeringInterpretation`. §10 specifies the
one link this revision adds explicit, dedicated narrative weight to:
**power mismatch over time → accumulated energy deficit → stored DC-link
energy reduction → V_dc sag → SST response → recovery.**

## 7. Physics Integrity Constraints

These constraints bind every narrative slice, present and future, per
`CLAUDE.md`'s Modeling Rules:

1. **Python simulation remains the sole authority for engineering
   behavior.** `src/` and the FastAPI boundary (`backend/`) are the only
   places Scenario A's dynamics are computed. No frontend code may
   simulate, integrate, or otherwise derive a time-series value the
   backend did not already return in `LoadStepResponse`
   (`frontend/app/lib/simulationApi.ts`).
2. **The frontend may derive presentation-only quantities** from
   already-returned backend data, using only closed-form relations the
   project has already approved for frontend use — specifically
   `E_dc = 1/2 * C_dc * V_dc^2` (already used in `PowerFlowSchematic.tsx`
   and `EngineeringInterpretation.tsx`) evaluated at specific returned
   samples. This is index/arithmetic reduction over returned data, per
   `transientMetrics.ts`'s existing header comment — never a
   re-integration of the trajectory and never a new modeled dynamic.
3. **ΔE equivalence (confirmed, Revision 0.2 item 4).** The model's
   governing equation is `dE_dc/dt = P_sst - P_load` (already stated in
   `EngineeringInterpretation.tsx`); therefore, during a deficit
   interval, `energy deficit = ∫(P_load - P_sst) dt`, which is exactly
   the loss of stored DC-link energy over that interval, subject to the
   model's existing definitions/boundaries (the lumped DC-link
   capacitor, no other energy path). The closed form
   `ΔE_dc = 1/2 * C_dc * (V_ref^2 - V_dc,min^2)` is the *same physical
   quantity*, evaluated via the capacitor's state function instead of by
   numerical quadrature over discrete samples. The implementation must
   compute ΔE via the closed form (as `transientMetrics.ts` already
   does, as `energyDeficitKj`), **not** via a new trapezoidal/Riemann sum
   over `p_load_w`/`p_sst_w`, both because that would be a second,
   independent computation of a value the backend's own state variable
   already determines exactly, and because a raw sum over a
   non-monotonic (ringing) mismatch series does not equal the net
   capacitor-energy drop unless windowed identically to the closed form.
   The narrative copy may state the integral form as the *governing
   equation* (it is the physically correct statement of the relationship)
   while the implementation computes it via the closed form — this is not
   a contradiction, and no spec reviewer should treat stating the integral
   form in prose as "the frontend computing an integral."
4. **No fabricated engineering behavior.** No animation, value, color
   transition, or visual motion may imply a physical behavior the
   simulation did not produce for the loaded run. Any transition must be
   a direct, monotonic function of an already-returned sample or an
   already-approved derived quantity (ΔE, E_dc) — never an eased,
   decorative, or "looks plausible" interpolation between samples beyond
   what the existing chart/scrubber sampling already does.
5. **Units and labeling.** Every displayed quantity carries its unit
   (V, kW, kJ, s) and, where the existing components already state it
   (`EngineeringInterpretation.tsx`), the governing equation and its
   modeling caveats are preserved verbatim or near-verbatim, not deleted
   for brevity.
6. **No new engineering parameters are invented.** All constants used
   (`voltage_reference_v`, `capacitance_f`, `rated_power_w`, etc.) must
   come from `LoadStepResponse.thresholds`, never be hardcoded in the
   new code.

## 8. Visual / Design Constraints

`DESIGN.md` remains the authoritative visual constitution; this section
only restates and makes explicit the parts most load-bearing for this
slice.

**Register.** "An instrument panel, not a dashboard" (`DESIGN.md` §1).
Dense, flat, restrained, one accent color, four status roles, dark
permanently. No shadows, blur, or glassmorphism. No card-heavy SaaS
layout — the existing pattern of bordered `<section>` strips with
`divide-x`/`border-t` hairlines (already used throughout `page.tsx`'s
`Console`) is the pattern to continue, not a bordered "card" per metric.

**Approved energy visual language**, in priority order:

- **Primary — Twin Potential Axes.** The quantitative V_dc + stored-energy
  (E_dc) paired-axis readout already implemented as `PotentialAxis` in
  `PowerFlowSchematic.tsx`. This is the primary visual vehicle for "stored
  energy level" anywhere this slice needs to show it.
- **Secondary — DC-bus segment texture.** The hatched bus-segment motif
  (`BusSegment` in `PowerFlowSchematic.tsx`) is topology-linked energy
  language; it may be reused but is not the primary carrier of the ΔE
  story for this slice.
- **Subtle identity only — charge-density/grid motif.** May appear as
  ambient/identity texture, never as a quantitative encoding.

**Explicitly avoided**, for this slice and all future ones, unless this
document is revised: battery/SOC metaphors (e.g., a battery icon implying
charge percentage), tank/fuel gauges, decorative circular gauges,
standing-wave visuals, fake fields, or any decorative physics that implies
behavior the model does not actually produce.

**Color.** The single accent (`--color-accent`) remains "energized /
actively flowing." The schematic's cyan/amber pair
(`SVG_COLOR.schematicCyan` / `SVG_COLOR.schematicAmber`) remains the
nominal/stress pair already established — amber already means "the E
channel" and "a real P_load > P_sst deficit" (`PowerFlowSchematic.tsx`
header comment); this slice must reuse that existing meaning, not invent a
third energy-specific color.

## 9. Concept 03 Structure

The approved visual direction is a three-stage narrative, read top-to-
bottom on one continuous page (no tabs, no routes, no separate views):

| Stage | Name | Teaches |
|---|---|---|
| 01 | OBSERVE / Steady State | What the system looks like and reads like before anything happens: topology, live V_dc/P_load/P_sst/ΔP. |
| 02 | TRANSIENT / Minimum Vdc | That an event occurred, how far V_dc moved, and when — peak deviation, peak instantaneous power mismatch. |
| 03 | ANALYZE / Energy Deficit | *Why* the transient was as severe as it was: severity is governed by **accumulated** energy deficit over time, not merely the **instantaneous peak** power mismatch. |

Stages 01 and 02 are already implemented, in combined form, by
`page.tsx`'s `EventBanner` + `KpiStrip` + `PowerFlowSchematic` (01) and
`TimeScrubber` + the synchronized `TelemetryChart` pair + existing peak-
deviation reporting in `TransientMetricsPanel` (02).

**Resolved:** OBSERVE → TRANSIENT → ANALYZE is the information/narrative
architecture that governs reading order and causal sequencing (§5, §6) —
it is not a UI requirement to render three literal, numbered ("01" /
"02" / "03"), dashboard-style section headers. This revision does not
split the existing combined 01/02 presentation into separate visual
blocks and does not add on-screen numerals anywhere. DESIGN.md's existing
caption style (plain-English section labels like "THE EVENT",
"ENGINEERING RESULT") is the established convention and is what the new
03 ANALYZE section's label must also use — the current continuous
engineering narrative is preserved, not restructured into a three-panel
layout.

Stage 03 (ANALYZE) is **new, dedicated narrative weight** this revision
adds: today, the energy-deficit value exists (`energyDeficitKj` in
`transientMetrics.ts`, surfaced in the Power Balance chart's shaded-area
caption) but is not yet presented as its own explained teaching point
connecting accumulated deficit to severity. §10 specifies this gap.

## 10. ANALYZE / Energy Deficit Requirements

**Purpose.** Stage 03 must teach: *transient severity is governed by
accumulated energy deficit, not merely instantaneous peak power
mismatch.* The central relationship is:

```
ΔE = ∫ (P_load - P_sst) dt
```

equivalently, for this model, the DC-link capacitor's own energy balance:

```
ΔE_dc = 1/2 * C_dc * (V_ref^2 - V_dc,min^2)
```

**R-1 — Explicit relationship statement.** The ANALYZE section must state,
in plain language before the equation (per §5's EXPLAIN pattern), that the
power-mismatch *area over time* — not its peak height — is what determines
how far V_dc sags, and must then state the governing equation(s) above.
This is additive to, not a replacement for, the existing
`EngineeringInterpretation.tsx` causal prose — it may extend that
component or add an adjacent one, but must not duplicate its existing
sentences verbatim.

**R-2 — Contrast with peak mismatch.** The section must explicitly contrast
the two already-computed quantities — `peakDeficitKw` (instantaneous) and
`energyDeficitKj` (accumulated) — so a learner can see both numbers side
by side and read the distinction the purpose statement makes. Both values
already exist in `TransientMetrics`; no new computation is required beyond
possibly a one-line "ratio"/comparison framing, which if added must be
pure arithmetic on these two already-returned numbers (e.g., not a new
unit-mismatched ratio presented as physically meaningful beyond
illustration).

**R-3 — Power-mismatch visualization.** The existing shaded-area deficit
visualization on the "Power Balance — P_load vs P_sst" chart
(`deficitFill` in `TelemetryChart.tsx`, wired in `page.tsx`) is the
required power-mismatch-over-time visualization for this slice. It must
remain visible, must remain anchored to the event-to-minimum-V_dc window
(as it already is), and its caption must state the same `energyDeficitKj`
value the ANALYZE section's own text states — one number, one source
(`transientMetrics.ts`), referenced from both places; never two
independently formatted/rounded copies that could visually disagree.

**R-4 — ΔE ↔ V_dc relationship made explicit.** The ANALYZE section must
connect, in reading order: power mismatch over time → accumulated energy
deficit (ΔE) → stored DC-link energy reduction (E_dc, already visualized
via the Twin Potential Axes in `PowerFlowSchematic.tsx`) → V_dc sag → SST
response → recovery. This may be done via prose, a labeled sequence, or a
compact inline diagram, but must not be only an equation with no stated
causal narration, and must not be only prose with no stated equation (per
§5's EXPLAIN pattern: plain language first, equation second).

**R-5 — Single source of truth for ΔE/E_dc.** Every number presented in
the ANALYZE section (ΔE in kJ, E_dc at any cited instant, V_dc at any
cited instant) must be read from `TransientMetrics` or from a `Sample`
already computed elsewhere in `page.tsx`/`transientMetrics.ts` — never
independently recomputed inline in a new component. This is the concrete
test for §7 Constraint 3 and 6.

**R-6 — No new backend fields required.** This slice must be
implementable entirely from fields already present in `LoadStepResponse`
(`thresholds.capacitance_f`, `thresholds.voltage_reference_v`,
`timeseries.v_dc_v`, `timeseries.p_load_w`, `timeseries.p_sst_w`) and
values already derived in `transientMetrics.ts`. If an implementer finds
this is not actually sufficient, that is a spec conflict to report per
§16, not a reason to add a backend field unilaterally.

**R-7 — Placement.** The ANALYZE section reads after the existing
TRANSIENT-stage content (the synchronized telemetry charts) and before or
alongside the existing `TransientMetricsPanel`/advanced-experiment
controls, consistent with the OBSERVE → UNDERSTAND → EXPLAIN ordering in
§5 (TRANSIENT = UNDERSTAND, ANALYZE = EXPLAIN). Exact component
boundaries (new component vs. extending `EngineeringInterpretation.tsx`
and/or `TransientMetricsPanel.tsx`) are an implementation decision within
this constraint, confirmed not a Human Gate (Revision 0.2 item 3).

## 11. Interaction Requirements

- The ANALYZE section's content must stay synchronized with whatever run
  is currently loaded (baseline or a learner-run experiment via
  `ExperimentPanel`) — it re-derives from the same `TransientMetrics` the
  rest of the page already recomputes per `useMemo(() => 
  computeTransientMetrics(data), [data])` in `page.tsx`. No independent
  fetch, no independent state.
- The ANALYZE section is not required to respond to the time scrubber
  (`TimeScrubber`/`index`) — it reports fixed whole-run analysis results,
  consistent with `TransientMetricsPanel`'s and
  `EngineeringInterpretation`'s existing behavior, not a live per-instant
  readout.
- **Resolved:** no new interactive control (e.g., a toggle or highlight
  for the deficit window) is added for this slice. V1 of 03 ANALYZE
  teaches the causal relationship through hierarchy, simulation-derived
  data, visualization, annotation, and explanation alone — this is a
  settled scope boundary, not an open question for the implementer to
  escalate. New interaction is deferred to a future specification
  revision, to be considered only if it would clearly improve
  engineering understanding (see §17).

## 12. Responsive / Accessibility Requirements

- Must render correctly down to the narrowest breakpoint the rest of
  `page.tsx` already supports (the existing `grid-cols-1 lg:grid-cols-2`
  chart layout and `sm:grid-cols-4` KPI/metric strips are the established
  pattern — the ANALYZE section must degrade the same way, single-column
  below `sm`/`lg`, not overflow or require horizontal scrolling).
- Text contrast, font sizing, and semantic HTML (`<section>`, heading
  hierarchy via existing `<span>`-as-label pattern) must match the
  conventions already used by `EngineeringInterpretation.tsx` and
  `TransientMetricsPanel.tsx` — no new heading level skipped, no
  color-only encoding of meaning (the existing pattern already pairs
  color with text labels/units; continue that).
- Any SVG additions (if the implementer extends `PowerFlowSchematic.tsx`
  or adds a new diagram) must include text labels for every value a
  color alone would otherwise convey, consistent with existing practice
  in that file.
- No new keyboard traps; if no new interactive control is added (per
  §11), no new keyboard-accessibility surface is introduced either.

## 13. Frontend / Backend Responsibility Boundary

- **Backend (`backend/`, `src/`)**: unchanged by this slice. Remains the
  sole source of simulation truth. No new endpoint, field, or schema
  change is in scope for this slice (see R-6).
- **Frontend (`frontend/app/`)**: may read `LoadStepResponse` fields and
  compute presentation-only derived values already permitted by §7 and by
  `transientMetrics.ts`'s existing contract. May not simulate, integrate
  over time server-side-equivalent logic, or add a second implementation
  of any physical relationship the backend already computes.
- This boundary is identical to the one already documented in
  `simulationApi.ts`'s and `transientMetrics.ts`'s header comments; this
  specification does not change it, only makes it an explicit, testable
  constraint for this slice (§14).

## 14. Acceptance Criteria

- [ ] **AC-001 (narrative ordering):** On initial page load (baseline
  run) and after any `ExperimentPanel` run, the rendered page presents
  OBSERVE-stage content (event banner, KPI strip, power-flow schematic),
  then TRANSIENT-stage content (time scrubber, synchronized charts), then
  ANALYZE-stage content, in that top-to-bottom DOM order. No ANALYZE
  content appears above the TRANSIENT charts it depends on.
- [ ] **AC-002 (actual simulation-derived values):** Every numeric value
  in the ANALYZE section is traceable to a field in the fetched
  `LoadStepResponse` or a value returned by `computeTransientMetrics`
  (via `TransientMetrics`) for the run currently loaded — verified by
  code inspection showing no literal numeric constant (other than the
  ±1% recovery-band fraction already in `transientMetrics.ts`, or a unit
  conversion factor) is used as a displayed engineering value.
- [ ] **AC-003 (Energy Deficit explanation present):** The ANALYZE
  section contains, in this order: (a) a plain-language statement that
  accumulated deficit over time, not peak mismatch, governs severity; (b)
  the equation `ΔE = ∫(P_load - P_sst) dt`; (c) the model's own governing
  relation `dE_dc/dt = P_sst - P_load` and/or `E_dc = 1/2 C_dc V_dc^2`
  already used elsewhere on the page.
- [ ] **AC-004 (peak-vs-accumulated contrast):** The ANALYZE section
  displays both `peakDeficitKw` and `energyDeficitKj` for the currently
  loaded run, labeled so a reader can tell which is instantaneous and
  which is accumulated, matching R-2.
- [ ] **AC-005 (power-mismatch visualization):** The Power Balance chart's
  shaded deficit area (`deficitFill`) remains present, anchored to the
  event→min-V_dc window, and its caption's kJ figure is numerically
  identical (same formatting, same rounding) to the kJ figure stated in
  the ANALYZE section.
- [ ] **AC-006 (ΔE ↔ V_dc relationship stated):** The ANALYZE section's
  copy traces, in reading order, power mismatch → ΔE → E_dc reduction →
  V_dc sag → SST response → recovery (R-4), citing at least one concrete
  value from the current run (e.g., the minimum V_dc and its time) as
  proof, not only abstract description.
- [ ] **AC-007 (no duplicated frontend physics engine):** No new code
  performs numerical integration (trapezoidal, Riemann, or otherwise)
  over `p_load_w`/`p_sst_w`/`v_dc_v` to compute ΔE or any other value
  already derivable in closed form from `TransientMetrics` or
  `thresholds` — verified by code inspection of any new/changed file
  touching this slice.
- [ ] **AC-008 (no fake/interpolated engineering behavior):** No new
  animation, transition, or visual element implies a value, rate, or
  state the fetched `LoadStepResponse` does not contain at an actual
  sample index — verified by code inspection; any transform of a real
  value (e.g., a fraction for an axis position) is pure arithmetic on
  that value, matching the existing `PotentialAxis`/`clamp01` pattern.
- [ ] **AC-009 (visual hierarchy / instrument-panel register
  preserved):** The ANALYZE section uses the existing bordered-strip /
  hairline-divider pattern already used by `TransientMetricsPanel.tsx`
  and `EngineeringInterpretation.tsx` — no new bordered "card" per
  metric, no shadow, no gradient, no glassmorphism.
- [ ] **AC-010 (design-token compliance):** All colors used are existing
  `DESIGN.md`/`theme.ts` tokens (`SVG_COLOR.*`, Tailwind classes already
  in use elsewhere in `frontend/app`); no new hex literal is introduced
  outside `theme.ts`; the amber/cyan meaning pair is reused unchanged
  (§8).
- [ ] **AC-011 (approved energy visual language only):** If the ANALYZE
  section adds any new visual element for stored energy, it uses the
  Twin Potential Axes and/or DC-bus segment hatch pattern already
  established in `PowerFlowSchematic.tsx`; it does not introduce a
  battery/SOC icon, tank/fuel gauge, decorative circular gauge,
  standing-wave visual, or fake field.
- [ ] **AC-012 (responsive behavior):** At viewport widths corresponding
  to the existing `sm`/`lg` Tailwind breakpoints already exercised by
  `page.tsx` (mobile single-column, desktop multi-column), the ANALYZE
  section renders without horizontal overflow or clipped text, degrading
  to single-column below `sm`/`lg` consistent with the rest of the page.
- [ ] **AC-013 (accessibility):** The ANALYZE section uses semantic
  sectioning and heading-label conventions consistent with
  `EngineeringInterpretation.tsx`/`TransientMetricsPanel.tsx`; no meaning
  is encoded by color alone (every colored value also carries a text
  label/unit).
- [ ] **AC-014 (01/02 preserved):** `EventBanner`, `KpiStrip`,
  `PowerFlowSchematic`, `TimeScrubber`, the synchronized `TelemetryChart`
  pair, and `ExperimentPanel`/`SensitivityStudy` remain functionally and
  visually unchanged except for integration touches explicitly permitted
  by §3 (e.g., reordering where the new section is inserted).
- [ ] **AC-015 (no new backend surface):** No file under `backend/` or
  `src/` is modified by this slice's implementation (verified by the
  diff's file list).
- [ ] **AC-016 (lint):** `npm run lint` (in `frontend/`) passes with no
  new errors or warnings introduced by this slice.
- [ ] **AC-017 (typecheck):** `npm run typecheck` (in `frontend/`) passes.
- [ ] **AC-018 (production build):** `npm run build` (in `frontend/`)
  completes successfully.
- [ ] **AC-019 (existing Python tests unaffected):** `python -m pytest -q`
  at the repository root passes with the same results as before this
  slice's implementation (expected: unchanged, since no Python file is
  touched per AC-015).

## 15. Verification Requirements

Per `ENGINEERING.md`'s Verification Philosophy, this slice is a
presentation/software-component change, not a new physics model, so
verification is primarily Layer 1 (unit/component-level correctness) and
direct inspection against this spec's acceptance criteria, plus the
existing Layer 2–4 suite re-run as a regression check:

1. **Local verification (implementer):**
   - `cd frontend && npm run lint && npm run typecheck && npm run build`
   - `python -m pytest -q` at the repository root (confirms AC-015/AC-019
     — expect no change in results).
   - Manual run of the dev server (`npm run dev` against the running
     FastAPI backend) exercising: initial page load (baseline run), at
     least one `ExperimentPanel` run with a different `final_fraction`,
     and the mobile-width layout — confirming AC-001 through AC-014
     visually.
2. **Independent review (Codex, per `AGENTS.md`):** review against this
   spec's acceptance criteria specifically, not general code quality;
   flag any criterion not met rather than silently fixing it.
3. **Validation record:** on completion, file
   `docs/validation/SPEC-005-validation.md` recording which criteria were
   checked, how, and the result — per existing precedent
   (`docs/validation/SPEC-002-validation.md`).

## 16. Human-Gate Conditions

Implementation of the 03 ANALYZE slice must stop and return to the Human
Engineering Lead, rather than proceed on an agent's own judgment, if any
of the following occurs:

- the fields already in `LoadStepResponse`/`TransientMetrics` prove
  insufficient to satisfy §10's requirements without adding a new backend
  field (contradicts R-6/§13);
- satisfying R-3/R-4/R-5 appears to require restructuring
  `PowerFlowSchematic.tsx`'s existing geometry constants or `theme.ts`'s
  token set beyond additive use (contradicts §3's "minimal integration
  only" bound on touching 01/02-adjacent code, and §8's "no new tokens");
- any instruction in this document appears to conflict with `CLAUDE.md`,
  `DESIGN.md`, or `SPEC-002`.

The following are explicitly **not** Human Gates, per the Revision 0.2
resolved decisions above, and must not be escalated during
implementation:

- the choice of component boundary (new component vs. extending/
  refactoring `EngineeringInterpretation.tsx` and/or
  `TransientMetricsPanel.tsx`) — resolved by Revision 0.2 item 3;
- whether to add an interactive control for the ANALYZE section —
  resolved by Revision 0.2 item 2 (not added in this slice);
- whether to render numbered stage headers — resolved by Revision 0.2
  item 1 (not added).

This specification's approval (this revision, Status: Approved) satisfies
`ENGINEERING.md`'s requirement that implementation not begin before the
Human Engineering Lead approves the governing specification.

## 17. Out of Scope

Explicitly out of scope for this specification and for the 03 ANALYZE
slice it authorizes:

- any change to `backend/` or `src/` (simulation physics, API contract);
- redesigning or restructuring 01 OBSERVE or 02 TRANSIENT beyond minimal
  integration (§3, §9);
- new Scenario A parameters, new scenarios, new routes, new pages, or any
  navigation/tab structure;
- new chart types, new color roles, new DESIGN.md tokens, or any visual
  language not already named in §8's approved list;
- battery/SOC, tank/fuel-gauge, decorative circular-gauge, standing-wave,
  or fake-field visuals, under any framing;
- machine learning, cloud infrastructure, paid APIs, Docker, Kubernetes,
  or any additional framework/library, per `CLAUDE.md`'s Out of Scope
  section;
- numerical time-integration of telemetry series in frontend code (§7
  Constraint 3, AC-007);
- any new interactive control beyond what `ExperimentPanel`/
  `TimeScrubber`/`SensitivityStudy` already provide (Revision 0.2 item 2)
  — not added in this slice; may be proposed in a future specification
  revision if it would clearly improve engineering understanding, but is
  not a condition for this slice's implementation to stop and escalate;
- rendering numbered ("01"/"02"/"03") on-screen stage headers (Revision
  0.2 item 1) — not added in this slice;
- defining or implementing any narrative slice other than 03 ANALYZE —
  Energy Deficit. Future slices require either a revision to this
  specification or a new SPEC document that explicitly extends it.
