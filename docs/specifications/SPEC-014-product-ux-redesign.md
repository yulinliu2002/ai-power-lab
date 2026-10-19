# SPEC-014 — Product UX Redesign: Problem-Driven Sandbox and Architecture Choices

**Status:** Draft v0.5 (v0.3 plus §17 Foundation Amendment and Appendix B, Signal Path; Codex diff check of v0.4 resolved in v0.5). Previous status: Draft v0.3 (UX redesign; Codex review and bounded closure review resolved, §16). Design only. Supersedes the earlier remediation-only SPEC-014 draft (withdrawn; its Codex-reviewed content is folded into §10 R29-R33). Codex review record: §16. Awaiting Human Engineering Lead approval of §15. **Do not implement.** On approval this file moves to `docs/specifications/SPEC-014-product-ux-redesign.md` (`ENGINEERING.md`), and implementation proceeds on a dedicated branch.
**Project:** AI Power Lab
**System:** `frontend/app/` (information architecture, interaction design, copy). No change to `src/`, `backend/`, `dashboard/`, `config/`, `scenarios/`, `content/`, `data/`, `tests/`, no API contract change, no new dependency or framework.
**Version:** 0.5
**Type:** Software Component (presentation, interaction and content layer; no new engineering model)
**Prepared by:** design thread, from `origin/main` at `4e6af36` (verified, read through the QA worktree; no branch, no edits to SPEC-012/SPEC-013 files). Evidence: runtime QA `FINDINGS.md` and screenshots (`/Users/jasonliu/Projects/ai-power-lab-qa-report/`), product and content audit (`review/product-content-audit.md`, project library), source reads cited as `file:line` against `4e6af36`.
**Human conditional design approval (2026-10-18):** the UX architecture and decisions D-R, D-1, D-2, D-3, D-5, D-8 and D-4 are approved (D-3 keep, D-4 defer, D-R keep backend labels plus caution, D-2 recommended phrase). **Implementation is not authorized.** Appendix A needs final authorization; D-6 (generic Stage 4 for Scenarios B-E) was not listed in the approval and is treated as covered by approval of the UX architecture unless the Human says otherwise.
**Human decision recorded (2026-10-18):** move from a feature-display website to a problem-driven, interactive engineering learning and decision-support platform. This is an information-architecture and interaction-design improvement, not a rewrite of the app or simulation engine.
**Depends on:** SPEC-012 (Learn by Example) **merged first** (§11). Single dependency plan: implementation starts only after SPEC-012's merge; the implementation baseline is the synchronized base recorded under the §11 start gate (which must contain that merge commit).

> **Reading note.** Finding IDs: **Q#** runtime QA defect, **D/G/P#** content audit finding. Product facts (what each page renders today) were read from source at `4e6af36` and the screenshots; layout behavior at runtime is as reported by QA and must be re-confirmed (AC-1).

---

## 1. Engineering Question

Can a learner who arrives with a *problem* ("what happens when AI load steps?", "which architecture fits a rack-density requirement?") be walked from the question, through observation, to a stated engineering takeaway and its validation needs, **without** losing any validated analysis the product already contains?

## 2. Motivation and ROI

**Evidence from the real product (screenshots and audit):**

- `/sandbox` (Scenario A, 1440 px, one scroll of about 2,500 px): the page is a stack of 11 stacked sections. The time scrubber that drives the KPI tiles and schematic sits *below* the protection panels and *above* the charts; the two controls that actually change the experiment (Advanced Experiment, Sensitivity Study) are collapsed text links at the very bottom. "Compare All" is a toggle at top-right that replaces the whole page and disables the scenario selector. Nothing says which control answers which question. (`sandbox-desktop-sensitivity-run-full.png`, `sandbox/page.tsx:252-355`.)
- Terminology: the backend-supplied outcome label "RODE THROUGH CLEANLY" (`outcome_label`, rendered verbatim at `ProtectionTimeline.tsx:126` and `ScenarioComparison.tsx:207`; enum `RIDE_THROUGH`, `dashboard/adapters/protection_timeline.py`) and the coordination text "equivalent to outcome == RIDE_THROUGH" can read as a certified hardware fault-ride-through claim; the model has no fault ride-through dynamics (`src/grid.py:24-36`). The enum means *no terminal protection action and no bus-energy-floor event*; recovery is classified separately (`recovery_label`). The visible section heading is already "PROTECTION TIMELINE"; "Ride-Through" survives in the spec title, comments and docs. Coordination text also cites repository file names ("src/protection.py") to learners.
- Charts have titles but no "how to read this"; sliders are labeled "AI LOAD STEP", "DC BUS CAPACITANCE", "SST RESPONSE TIME" with no statement of what each parameter does to the result.
- `/architecture`: all content renders at once, about 3,900 words in 7 + 21 + 15 + 7 + 3 blocks (P1); the one interactive control ("If a driver dominates") is section 4 of 5, after the reader has already scrolled the whole comparison. The selector is the best teaching device on the page and it is buried.
- Product areas are not related to each other on the page level: System Map ends by sending the reader to the Sandbox (G2); the Sandbox calls itself a "CONTROL CENTER" (D2); no page says when to use which tool (Scope C).

**Product ROI (Blueprint §6):** improves the ability to understand, compare and explain real architectures by putting the question first and the evidence behind it; makes the product's four-areas-plus-Sandbox structure legible.
**Career ROI:** the four-stage flows (Configure, Observe, Investigate, Takeaway; Requirement, Compare, Trade-offs, Validation) are the reasoning sequence used in systems-engineering trade studies: state the requirement, vary one thing, observe, compare alternatives, state what would have to be validated. The redesign rehearses that sequence on every use (Charter P0 items 1-3, P1 items 4 and 6).

## 3. Product Model (Scope C)

One sentence per area, plus the entry question it answers and where it hands off. This table becomes the home-page copy source and the "next step" links on every page. No area is added, removed or renamed.

| Area | Role | Learner's entry question | Hands off to |
|---|---|---|---|
| **System Map** | Understand the system | "What is in the chain from grid to rack, and why?" | Architecture Choices ("compare these three views") |
| **Architecture Choices** | Compare design approaches | "Which architecture fits this requirement, and what would I have to validate?" | Learn by Example for behavior; System Map for node definitions |
| **Learn by Example** (SPEC-012) | Guided learning from system behavior | "Walk me through one disturbance and its consequence." | Advanced Sandbox ("try your own values") |
| **Advanced Sandbox** | Free engineering experimentation | "I have my own question; let me vary it and see." | Learn by Example (guided case), Architecture Choices (validation needs) |
| **Industry & Career** | Industry context and career competencies | "What does this look like in practice, and what skills does it build?" | Planned; not built by this spec |

**Boundary with SPEC-012 (no redundant workflows).** Learn by Example owns *guided, authored, one-case-at-a-time* explanation with fixed text per scenario. The Sandbox owns *free, learner-driven* runs, sweeps and comparison with **no** per-scenario authored lessons. SPEC-014 writes no per-scenario lesson text and never duplicates SPEC-012's eight-part case structure; its Stage 4 takeaway is generic and data-driven (§6.1). Detail in §11.

## 4. Scope

- **A. Advanced Sandbox** reorganized into four stages: **Configure & Run, Observe & Explain, Investigate & Compare, Engineering Takeaway** (§6.1).
- **B. Architecture Choices** reorganized into four steps with progressive disclosure: **Identify the Requirement, Compare Architectures, Understand Trade-offs, Define Validation Needs** (§6.2).
- **C. Product integration:** the §3 model expressed as home copy, page headers and cross-links (§10 R34-R36).
- **D. Folded-in remediation** (previous SPEC-014 draft): positioning, System Map handoff, System Map evidence labels, 390 px no-clipping legibility floor, desktop polish (§10).

## 5. Out of Scope

- Any change to simulation physics, API routes or response fields, backend, `dashboard/adapters`, config, scenarios, tests. Any new framework, library, route-handling infrastructure, state library or agent orchestration.
- `/learn` (SPEC-012), per-scenario lesson text (SPEC-012), Industry & Career build, SPEC-013 files.
- A visual rebrand. Dark theme, tokens, typography families and the instrument-panel language stay (`DESIGN.md`). New components use existing tokens.
- New engineering claims, new numbers, rankings, scores, or "best architecture" statements (SPEC-011 AC-8 still applies).
- Editing backend-authored strings (outcome headline, coordination prose). See D-R for the terminology decision.
- True mobile optimization, touch gestures, Safari/Firefox testing (§14).
- P2/P3/P4 and other pure visual-taste items; Human Visual QA (§12) decides those on rendered output.
- Blueprint header refresh (D8), G3 driver chips on the Map (scope-changing, separate spec).

### 5.1 Assumptions

- API responses are deterministic for identical requests (the byte-identity checks rely on it); the baseline capture is taken on the baseline commit with the same Python environment and data.
- Existing page state logic (`sandbox/page.tsx` generation guards, `draftParams`, `defaultIndexFor`) is the behavior to preserve; moving components does not change it (§6.4).
- Reproduction and validation scripts are copied from `/Users/jasonliu/Projects/ai-power-lab-qa-report/` (`crawl.py`, `inter.py`, `inter2.py`) into `docs/validation/spec-014/` as validation artifacts; Chromium via Playwright and a locally installed axe-core are used from outside `package.json`.
- Frontend metrics (recovery time, energy deficit) are derived by `computeTransientMetrics` for Load Step only (SPEC-008 §12) and are not API fields.
- 390x844 emulation with mouse input stands in for narrow viewports.

## 6. Proposed Screen Structure and Interaction Flows

General rules for both pages: one page, one URL; no wizard that hides earlier results; a **stage navigation** at the top lists the four stages as anchor links with the current stage marked (native links, keyboard-operable, `aria-current`); each stage is a labeled `<section>` with a one-line question it answers; progressive disclosure uses native `<details>` or the existing show/hide button pattern; results already computed are never discarded by moving between stages. State lives in the existing React state; the selected architecture driver may be mirrored to a `?driver=` query parameter (optional, D-4).

### 6.1 Advanced Sandbox (`/sandbox`)

**Page header (replaces "AI POWER LAB / SST / 800 VDC CONTROL CENTER").** `h1` "Advanced Sandbox"; subtitle "Free experimentation on one simplified slice of one architecture"; directly beneath, `DISCLOSURES.sim` imported verbatim and a link "Prefer a guided walkthrough? Learn by Example" (shown once SPEC-012's route is live) and "Compare architectures" to `/architecture`. Stage navigation bar below.

```
Advanced Sandbox            [1 Configure & Run] [2 Observe & Explain] [3 Investigate & Compare] [4 Takeaway]
scope sentence (DISCLOSURES.sim)   ·  Learn by Example  ·  Architecture Choices

STAGE 1  CONFIGURE & RUN        "What disturbance, and with what parameters?"
  Scenario   (o)Load Step ( )Sustained High Load ( )Thermal Trip ( )Grid Sag ( )Grid Loss
  Preset line: what this preset applies (from existing scenario metadata only)
  Parameters (Load Step only)    [AI load step] [DC bus capacitance] [SST response time]  [Reset] [Run]
     each slider: plain-language effect line ("larger C: bus voltage moves less per joule")
  Non-adjustable scenarios: "This scenario is a fixed preset; parameters are not adjustable." (new text; today the controls are simply absent)

STAGE 2  OBSERVE & EXPLAIN      "What happened, and why?"
  The event (Load Step) / run header
  State at time t:  [time scrubber]  KPI strip  Power-flow schematic      (scrubber moved next to what it drives)
  Charts:  V_dc(t)   |   Power balance        each with "How to read this" disclosure + legend
  Why this happened (Load Step)
  Protection:  timeline, outcome banner, coordination, coverage checklist     (grouped, see R17)
  Engineering result tiles (Load Step)    Engineering basis (visible, as today)

STAGE 3  INVESTIGATE & COMPARE  "How sensitive is this, and how do the scenarios differ?"
  Choose a study:  (o) Vary a parameter (Sensitivity Study)   ( ) Compare all five scenarios
     Vary a parameter: swept parameter [C_dc | tau_sst]   held-fixed summary (current Stage 1 values)   [Run Sweep] -> chart + table
        (Load Step only; for other scenarios the option is visible, disabled, and says why)
     Compare all scenarios: ScenarioComparison (fixed presets, all five; fetch on each entry as today)

STAGE 4  ENGINEERING TAKEAWAY   "What can I conclude, and what can't I?"
  What happened (live values)  ·  What limited it  ·  What the model does not represent  ·  What would need validating  ·  Next steps
```

**Interaction flows (Sandbox).**
1. *Default arrival:* Load Step auto-runs as today; the page opens at Stage 1 with results already visible in Stage 2 (no empty state, no new request).
2. *Change scenario:* selecting a scenario triggers the same fetch as today; Stage 2 and Stage 4 update; Stage 3 results from the previous scenario are cleared except Compare All, which is scenario-independent.
3. *Re-run with parameters:* Run in Stage 1 (existing `runExperiment`); Stage 2 and 4 update; Stage 3 sweep results stay but are marked stale if the held-fixed values changed (R12).
4. *Sweep:* Stage 3, uses Stage 1 draft values exactly as `SensitivityStudy` does today (`draft` prop) and says so in the held-fixed summary.
5. *Compare all:* Stage 3, no longer replaces the page or disables the scenario selector; the single-run view stays on screen above it.
6. *Keyboard:* every stage control reachable by Tab in document order; stage nav links move focus to the section heading; no pointer-only affordances.

**Stage 4 content rules (the one new content surface; field-level contract in §6.3).** Stage 4 is assembled from (a) live response values (outcome, event, minimum V_dc, energy deficit, recovery time, trip time as the existing components already compute them) and (b) a small fixed-string data file (`lib/sandboxTakeawayData.ts`) holding the generic "what the model does not represent" and "what would need validating" items. Every fixed string either reuses text already shipped on the Sandbox or `/architecture` (`DISCLOSURES`, the toy-model disclaimers, the V1 protection-coverage statements, `VALIDATION_NEEDS`) or is a restatement of the model's documented limits in `src/` docstrings. No new engineering claim and no new number (R14, R44). Evidence label: **Model output (simplified)** for live values; **Illustrative assumption** for fixed strings that restate model scope. Per-scenario narrative is out of scope (SPEC-012).

### 6.2 Architecture Choices (`/architecture`)

**Page header:** unchanged title and purpose sentence; the five SPEC-011 disclosures stay **visible on load** (SPEC-011 AC-7), but are grouped into one "Scope and limits" block instead of five loose bullets; the evidence-label legend stays. Stage navigation lists the four steps.

```
ARCHITECTURE CHOICES      [1 Requirement] [2 Compare] [3 Trade-offs] [4 Validation]
Scope and limits (5 disclosures, visible)      Evidence labels legend

STEP 1  IDENTIFY THE REQUIREMENT   "What matters most for the hypothetical site?"
  Driver chooser (7 options, radio group, existing labels). Default: RD1.
  Selected driver card:  question · what it is · why it matters · system connection · constraints and trade-offs · decision it informs

STEP 2  COMPARE ARCHITECTURES      "How does each architecture meet this driver?"
  Three cards (Conventional AC | AC-fed 800 VDC | Conceptual MV-to-800 VDC via SST) for the selected driver:
  how addressed · what it makes harder · evidence label + basis + refs  (+ Sandbox link where evidence is model output)
  [Show all drivers at once]  (full reference view, native details; renders the original 7 comparison blocks)

STEP 3  UNDERSTAND TRADE-OFFS      "What does this driver favor, under what condition, and where does the choice become a specification?"
  Conditional-decision card for the selected driver (favored set, because, unless, evidence)
  Interfaces: boundary chooser (5) -> three architecture cards (what crosses, concern, evidence)  [independent of driver; labeled so]

STEP 4  DEFINE VALIDATION NEEDS    "What would have to be shown before relying on it?"
  Three architecture lists (verifies + evidence kinds) + section evidence label
  Optional: "Validation items most relevant to the driver chosen in Step 1" is NOT added (no data link exists; would be a new claim)

References (always at the bottom, unchanged content)
```

**Interaction flows (Architecture).** Choosing a driver in Step 1 updates Steps 2 and 3 in place and keeps Step 4 unchanged (validation needs are per-architecture in the data, not per-driver; the page states that). The boundary chooser in Step 3 is independent. The "Show all drivers" and "Show all boundaries" controls render the original full blocks (same `data-testid`s) so the complete SPEC-011 content is always one click from any view. Native `<details>` and a radio group only; no new library.

**Design rationale:** the existing `DominantDriverSelector` already holds the correct teaching idea (select the dominant driver, get a conditional tendency). The redesign moves it from section 4 to the front and makes the comparison *about that driver* instead of 7 drivers at once.

### 6.3 Stage 4 field contract

| Field | Source | Applies to | Formatter | Null / error behavior |
|---|---|---|---|---|
| Run provenance line (scenario, step size, C_dc, tau_sst, "preset defaults" or "experiment values") | page state holding the parameters that produced the displayed run (§6.4) | all (parameters only for Load Step) | same formatters as `ExperimentPanel` readouts | "preset defaults" when no experiment run |
| Outcome label, outcome detail | `protection_timeline.outcome_label`, `outcome_detail` | all five | verbatim | "not available" on missing |
| Recovery label | `protection_timeline.recovery_label` | all five | verbatim | same |
| Coordination result label | `protection_timeline.coordination.result_label` | all five | verbatim | same |
| First event (label, time) | `data.events[0]` | all five when present | `formatSeconds` | "no event recorded" |
| Minimum V_dc and time, energy deficit, recovery time | existing `metrics` object from `computeTransientMetrics` | **Load Step only** | same formatters as `TransientMetricsPanel` | not shown for B-E (no placeholder numbers) |
| "Does not represent" and "to validate" lists | `lib/sandboxTakeawayData.ts` (Appendix A) | all | fixed strings | n/a |

No `stress_profile`, no dominant-stress text and no other comparison-response field appears in Stage 4 (the comparison covers fixed presets only and cannot describe an overridden run). AC-13 therefore checks direct fields against the response and derived fields against the existing metrics object.

### 6.4 Sandbox state-transition matrix (behavior preserved from `sandbox/page.tsx`)

| Event | Required result |
|---|---|
| Initial mount | One Load Step fetch (Strict Mode double-invocation guarded, as today); scrubber at `defaultIndexFor` (voltage minimum) |
| Select scenario | New generation; Stage 2 shows loading; `isRunning` and `runError` cleared; draft sliders **kept** (independent of scenario); sweep result cleared and any in-flight sweep invalidated; Compare lane untouched; scrubber at `defaultIndexFor` for Load Step, index 0 otherwise; returning to Load Step fetches the *preset* run, and the provenance line says "preset defaults" while a "slider values not yet run" marker shows if the draft differs |
| Run (Load Step) success | Stage 2/4 replaced, scrubber to `defaultIndexFor`, provenance line = draft snapshot at click time |
| Run failure | Previously displayed run **retained**; `runError` shown in Stage 1; `isRunning` cleared |
| Reset | Draft reset to baseline **and** a baseline fetch (as today); failure behaves like Run failure |
| Rapid switching or Run during in-flight request | Last request wins; superseded responses are discarded by the generation guard |
| Sliders changed after a run | Displayed run unchanged; "values changed since this run" marker; sweep (if shown) marked stale (R12) |
| Run Sweep | Uses the draft at click time; result carries its own snapshot; changing the swept parameter clears it (as today); scenario change clears it |
| Study chooser: Vary a parameter selected, then scenario changes to B-E | Study area shows the disabled-study notice with no automatic fetch; no study is auto-selected |
| Study chooser: switching between studies | Results of each are kept until their own invalidation rule fires (sweep: parameter/scenario change; Compare: re-entry refetches) |
| Enter Compare | Fetch every entry with its own generation guard; loading and error states shown inside Stage 3; Stages 1, 2, 4 unaffected |
| Stage 3 request fails | Error shown in Stage 3 only |

## 7. Before / After Information Architecture

**Advanced Sandbox**

| # | Before (`4e6af36`, top to bottom, Scenario A) | After |
|---|---|---|
| 1 | Back link, "Advanced Sandbox" tag | Header (Advanced Sandbox, scope sentence, cross-links), stage nav |
| 2 | "AI POWER LAB / SST / 800 VDC CONTROL CENTER" header with scenario label | removed (R1) |
| 3 | Scenario selector + Single/Compare toggle | Stage 1 |
| 4 | The Event banner (A only) | Stage 2, top |
| 5 | KPI strip | Stage 2, "state at time t" group |
| 6 | Power-flow schematic | Stage 2, "state at time t" group |
| 7 | Why this happened (A only) | Stage 2, after charts |
| 8 | Protection timeline, outcome banner | Stage 2, protection group |
| 9 | Protection coordination + coverage checklist | Stage 2, protection group |
| 10 | Time scrubber | Stage 2, directly above KPI strip (R7) |
| 11 | Synchronized transient charts | Stage 2 |
| 12 | Engineering result tiles + basis (A only) | Stage 2, after charts |
| 13 | Advanced Experiment (collapsed, A only) | Stage 1 parameters (R10) |
| 14 | Sensitivity Study (collapsed, A only) | Stage 3 |
| 15 | Compare All (page-replacing mode) | Stage 3 |
| 16 | (none) | Stage 4 takeaway (new) |

**Architecture Choices**

| Before (all rendered) | After |
|---|---|
| Header + five loose disclosure bullets + legend + 6 anchors | Header + "Scope and limits" block + legend + 4-step nav |
| §1 Seven driver cards | Step 1: chooser + selected card (all 7 via chooser, or "show all") |
| §2 21 comparison cells | Step 2: 3 cells for selected driver (or "show all drivers") |
| §3 15 interface cells | Step 3: boundary chooser (or "show all boundaries") |
| §4 "If a driver dominates" selector | Step 3: decision card for the Step 1 driver (the separate selector is removed; the Step 1 chooser replaces it) |
| §5 Validation needs | Step 4 |
| References | References |

## 8. Feature Mapping (no capability lost)

### 8.1 Advanced Sandbox

| Existing capability (source) | New location | Behavior change |
|---|---|---|
| 5 scenarios, `ScenarioSelector`, `scenario-option-*` ids | Stage 1 | none; testids kept |
| Scenario auto-run on selection, `fetchScenario` | Stage 1 | none |
| Single / Compare toggle, `ViewModeToggle`, `view-mode-option-*` | Replaced by Stage 3 study chooser and always-visible Stage 2 | **Compare no longer disables the selector or replaces the page.** Testids of the toggle are retired and replaced; AC-9 lists the replacement ids |
| Advanced Experiment: 3 sliders, Reset, Run (`ExperimentPanel`, A only) | Stage 1 parameters | Always visible for Load Step (not collapsed); same ranges, same handlers; effect line per slider is new copy |
| Sensitivity Study: 2 parameters, Run Sweep, chart, table, disclaimer (`SensitivityStudy`, A only) | Stage 3 "Vary a parameter" | Same component logic and endpoint; collapsed toggle replaced by study chooser |
| Compare All: `fetchScenarioComparison`, `ScenarioComparison` table, extrema emphasis, null-semantics tooltips | Stage 3 "Compare all" | Fetch-on-entry kept; no page replacement |
| KPI strip (4 tiles) | Stage 2 | Moved next to scrubber |
| Power-flow schematic with live overlay | Stage 2 | Moved; scroll cue added (R30) |
| Time scrubber | Stage 2, above KPI strip | Moved |
| Two telemetry charts, markers, deficit fill, reference lines | Stage 2 | "How to read" disclosure added; no data change |
| Event banner (A) | Stage 2 | none |
| Why this happened (EngineeringInterpretation, A) | Stage 2 | none |
| Engineering result tiles and basis (TransientMetricsPanel, A) | Stage 2 | none |
| Protection timeline, event list, outcome banner | Stage 2 protection group | Caution sentence added (R18); backend enum and strings untouched |
| Protection coordination text, coverage checklist | Stage 2 protection group | none to content; learner-facing file-path wording see D-R |
| Toy-model and educational-model disclaimers (3 places) | Stage 4 "what the model does not represent" plus kept at source | Consolidated view added; originals retained |
| Back link, "Advanced Sandbox" tag | Header | merged |
| (new) Stage nav, header scope sentence, takeaway | new | additive |

### 8.2 Architecture Choices

| Existing capability | New location | Behavior change |
|---|---|---|
| 7 drivers, five-field answers, `driver-rdN` | Step 1 (selected) + "show all" | Progressive disclosure; ids kept |
| 21 comparison cells, `compare-rdN`, evidence tags, refs, Sandbox links | Step 2 (selected driver) + "show all" | same data, same components |
| 15 interface cells, `boundary-*` | Step 3 + "show all boundaries" | boundary chooser |
| 7 conditional decisions, `decision-card-rdN`, `driver-option-rdN` | Step 3, driven by Step 1 choice | The standalone selector in old §4 is replaced by the Step 1 chooser; `driver-option-*` ids move with it |
| 3 validation lists + section evidence | Step 4 | none |
| 5 mandatory disclosures (verbatim) | "Scope and limits" block, visible on load | grouped, wording unchanged; `data-testid="disclosures"` kept |
| Evidence legend, `EvidenceTag` | header + per-cell | none |
| Reference list incl. inspection statements | References (end) | none |
| Anchor nav (6 anchors) | 4-step nav + References | replaced |
| Architecture IDs, display names | unchanged | none |

A script-checkable inventory (AC-8) compares the DOM of the new "show all" views with the old page: every old `data-testid` and every cell text must still be present.

## 9. Proposed Screen Review Questions for Human Visual QA

Not requirements; the checklist Jason uses on the rendered result: (1) do the four stages read as a path or as clutter; (2) is the Stage 2 group order clearer than the old stack; (3) does Step 1 → 2 progressive disclosure feel lighter than the full page; (4) does the Sandbox header read as a supporting tool; (5) is the "Scope and limits" block reassuring or noisy; (6) mobile: nothing is cut off.

## 10. Requirements

**Sandbox (Scope A)**

- R1. `h1` "Advanced Sandbox"; remove "AI POWER LAB" and "SST / 800 VDC CONTROL CENTER" from the page header; no learner-facing "control center" (D2, Q10). Site metadata *description* in `layout.tsx` reworded to match the header; the `DESIGN.md` §2 system identifier ("SST / 800 VDC AI Power Infrastructure") is not changed.
- R2. Directly below the header, `DISCLOSURES.sim` imported verbatim (never retyped), plus links to `/architecture` and, once SPEC-012 is live, `/learn` (D3).
- R3. Stage navigation (four anchor links, `aria-current`, order fixed) at the top; each stage a `<section>` with `aria-labelledby`, a one-line question, and a stable id.
- R4. Stage 1 contains the scenario selector (existing component), and for Load Step the three experiment sliders with Reset and Run. For the four other scenarios the parameter area shows the fixed-preset line (§6.1). No slider range, default or handler changes.
- R5. Each slider has a one-line plain-language effect statement derived from the model's documented behavior already shown on the page (the energy-deficit relation ΔE = ∫(P_load − P_sst) dt; C_dc sets how far V_dc moves per joule; τ_sst sets how long the mismatch stays open). No new claim, no number. Exact lines are in Appendix A (A1-A3) and are part of what the Human approves.
- R6. Parameter labels state units and meaning: e.g. "AI load step (kW, final demand)", "DC bus capacitance C_dc (F)", "SST response time τ_sst (ms)". Units are those the components already use.
- R7. Stage 2 order: event banner (A), scrubber, KPI strip, power-flow schematic, charts, "Why this happened" (A), protection group, engineering result (A). The scrubber remains the single selector of the sample shown in KPI strip and schematic, using the existing index state.
- R8. Each of the two charts has a "How to read this chart" disclosure stating axes, units, series, markers and what the shaded area means, using the Appendix A wording (A7-A8), which preserves the distinction between the sampled positive-gap shaded area (event to V_dc minimum) and the closed-form capacitor-energy deficit in the Engineering Result. Closed by default.
- R9. Stage 3 has a study chooser with two options, "Vary a parameter" and "Compare all five scenarios". For non-Load-Step scenarios "Vary a parameter" is shown disabled with the reason "Sensitivity sweeps are available for Load Step only." (existing capability limit made visible). The chosen study renders below the chooser; neither study discards the Stage 2 view.
- R10. Stage 1 parameters, Stage 3 sweep and Stage 3 compare keep their distinct computational purposes and endpoints: single run (`fetchScenario`/`runExperiment`), sweep (`runSensitivitySweep`, using the Stage 1 draft), comparison (`fetchScenarioComparison`, fixed presets). No endpoint is merged, added or called differently (AC-7).
- R11. The sweep's "held fixed" line states that it uses the Stage 1 values *as currently set*, including if they have not been run.
- R12. If Stage 1 values change after a sweep is displayed, the sweep shows a "stale: values changed since this sweep" marker; it is not auto-rerun.
- R13. Compare All keeps today's behavior exactly: fetch on **every entry** into the Compare study (`selectViewMode`, `sandbox/page.tsx:200`), with its own request-generation guard and the existing loading and error states. No caching. A failed fetch is retried by re-entering the study (re-select).
- R14. Stage 4 "Engineering Takeaway" is implemented per the §6.3 field contract: every live field has a stated source, scenario applicability, formatter and null behavior; fixed strings only from `lib/sandboxTakeawayData.ts`, each approved in Appendix A with its source and conditions. No per-scenario authored narrative; no fixed-preset comparison data is ever shown for a parameterized run.
- R15. Stage 4 states, in this order: what happened (outcome, event time, headline metrics); what the model reports (backend-supplied `outcome_detail`, `recovery_label` and coordination `result_label`, displayed verbatim; no frontend-authored causal claim about what "limited" the run); what the model does not represent; what would need to be validated before a real-world conclusion (linking to `/architecture` Step 4); next steps (Learn by Example case, Architecture Choices).
- R16. The existing comparison and protection footnotes remain at their source panels. Replace the `CLAUDE.md` references (`ScenarioComparison.tsx:141`, `ProtectionTimeline.tsx:61`) with self-contained wording (D5).
- R17. Protection group presents timeline and outcome first, then coordination, then coverage checklist, under one heading that does not use "Ride-Through" (see R18).
- R18. **Terminology (contract chosen: retain backend labels, add caution).** The API enum and every backend-supplied string (`outcome_label`, `outcome_detail`, `recovery_label`, coordination text) are displayed **unchanged and verbatim**; the frontend does not translate or relabel them (SPEC-012 AC-8 verbatim-string contract is preserved). The frontend adds, adjacent to every outcome banner and to the Compare All outcome column, one classification-neutral static caution: "Outcome labels are this simplified model's classification of the run, not certified hardware fault-ride-through performance. The model has no fault ride-through dynamics." (No statement about what a specific outcome means; the backend `outcome_detail` supplies that, verbatim.) The "recovery" classification stays separate and is never described as the outcome. Permitted legacy strings are enumerated in the validation record (outcome label for `RIDE_THROUGH`, the coordination sentence containing `RIDE_THROUGH`, `src/…` file references inside backend prose). Removing them requires a separately scoped backend wording spec (D-R).
- R19. Important physical assumptions and limits stay reachable in one click from every stage: a persistent "Model scope and limits" control in the stage nav bar opens the consolidated list (Appendix A items A4-A6), never removed from source panels.

**Architecture Choices (Scope B)**

- R20. Four steps, nav and section structure per §6.2. Step 1 chooser is a native radio group over the seven drivers in existing order with existing titles, default RD1; keyboard-operable; reuses the `DominantDriverSelector` logic as a controlled component (selection state lifted so Steps 2 and 3 follow it).
- R21. Step 2 renders exactly the three cells of the selected driver from `CELLS[driver]` through the existing field and `EvidenceTag` markup. "Show all drivers" renders the original seven `compare-rdN` blocks.
- R21a. "Show all drivers" renders, in addition to the seven `compare-rdN` blocks, the seven complete `driver-rdN` cards and the seven `decision-card-rdN` cards (a full reference view). In any rendered state each `data-testid` is unique: when the full view is open the selected-driver views of Steps 1-3 are hidden (not duplicated) and the chooser stays. SPEC-011 AC-5 "selecting a driver reveals only that driver's card" is verified in the default (non-full) view across all seven selections.
- R22. Step 3 renders `CONDITIONAL_DECISIONS[driver]` through the existing decision-card markup, plus a boundary chooser over `BOUNDARIES` rendering `INTERFACES` for the selected boundary; "Show all boundaries" renders the original five `boundary-*` blocks.
- R23. Step 4 renders the three validation lists unchanged and states that validation needs are per architecture, not per driver.
- R24. The five `DISCLOSURES` appear verbatim in a "Scope and limits" block visible at load, with `data-testid="disclosures"`; D-SIM, D-SST and D-BLOCK also appear verbatim at the points of use they have today (SPEC-011 AC-7 is not weakened).
- R25. All seven drivers, three architectures, architecture ids, evidence labels, `basis` and `refs`, interface items, conditional decisions, validation items and the reference list are rendered from the same data module without edits to its *content*. Data-module edits are limited to additive display helpers. (If audit items D6/D7 are approved as a separate SPEC-011 amendment, they change content in that spec, not here.)
- R26. No score, ranking, numeric weighting, or "best" phrasing is added (SPEC-011 AC-8 still holds). Step 3's heading and microcopy use "tends to favor under condition X", never "recommended".
- R27. (Deferred) Deep-linking the Step 1 driver via `?driver=` is not part of V1; selection is component state. Revisit if Human Visual QA asks for shareable links (D-4).
- R28. The Sandbox link on model-output cells and a "see System Map definition" link on node names are retained or added where the data already names nodes; no new data.

**Folded-in remediation (Scope D)**

- R29. `/` and `/system-map` copy: replace "executive-level" with the phrase chosen under D-2; remove "below" where the Sandbox is a link; add the one-clause SST rationale or link in the Q&A (D1, D4).
- R30. Narrow-viewport legibility floor (needs D-1): at 390 px no essential text, control, node, axis label or column is cut off without a visible cue. System Map main and cooling lanes stack vertically below `sm` (Q5); power-flow schematic keeps its minimum width in a focusable named scroller and gains a text scroll cue, no gradient (`DESIGN.md` §22) (Q1); charts and tables get a minimum width equal to the chart's viewBox width in a scroller with the same cue, sticky first table column, unabridged headers (Q2, Q3, Q4); nav wraps to at most two lines with planned items still plain non-clickable "(planned)" text, dimmed and `aria-disabled` (Q9, `DESIGN.md` §12). One shared presentational scroller helper, no data props.
- R31. Desktop polish: in every System Map lane that renders arrows today, exactly one arrow per adjacent node pair in all three views (lanes that intentionally omit arrows, such as monitoring, are unchanged) and uniform node width per lane (Q6); the scrubber cursor no longer overprints x-axis end labels (Q7); sweep tick labels never overlap (Q8). Tick-label omission is allowed; data, units, domains and formatting are unchanged.
- R32. System Map closing section: primary "Compare these three architectures →" to `/architecture`, secondary Sandbox link, one bridge sentence (G2).
- R33. **Split to SPEC-015 at implementation (D-3 split trigger met):** the claim count in `infrastructureMapData.ts` is 43 lines with digits and 28 with units or voltage/time classes, above the 25-claim threshold, so this requirement is removed from SPEC-014 and not implemented here; the validation record states the count. Original text retained for SPEC-015: System Map evidence labels (G1): claim inventory with disposition, label, basis and supporting reference per claim; `public-fact` and `emerging` need a registry reference actually read; no self-citation to `SYSMAP`; section-level labels where Blueprint §5.1 allows. `EvidenceTag` hardcodes `href="#references"` (`EvidenceTag.tsx:37`), so `/system-map` gets its own References section with that anchor (or an optional, default-preserving reference-target prop). No new source beyond those already cited on `/architecture`. The inventory is drafted and counted **before implementation of this requirement starts** (about 30-40 numeric or practice lines exist in `infrastructureMapData.ts` today); if more than 25 claims need rewriting, deleting or new references, R33 is split into SPEC-015 and removed from this spec (D-3).

**Integration (Scope C)**

- R34. Home page presents the §3 table as short copy plus the ordered path (Map, Choices, Examples, Industry) with "start here" on System Map; Sandbox shown as a supporting tool, not a fifth peer (Blueprint §3.1). No new component beyond what the home page already uses. Only after SPEC-012 merges (§11).
- R35. Every header of the four existing pages (not `/learn`) carries a one-sentence role line and a "next step" link per the §3 hand-off column. Links to unbuilt routes (`/learn` before SPEC-012, `/industry`) render as plain "(planned)" text per `DESIGN.md` §12, never dead links.
- R36. SPEC-014 adds no content to `/learn` and removes none; it never links to a SPEC-012 case anchor that does not exist (links go to `/learn` only).

**Cross-cutting**

- R37. Preserve existing `data-testid`s on every element that persists; retired testids (view-mode toggle, old section-4 selector wrapper) are listed in the validation record with their replacements.
- R38. No `src/`, `backend/`, `dashboard/`, `config/`, `scenarios/`, `content/`, `data/` or `tests/` change; `frontend/package.json` and lockfile unchanged.
- R39a. **Reused panels in scope.** For every panel this spec moves or touches, essential caveats and disclaimers (protection-coverage footnote, toy-model and educational-model disclaimers, coordination footnotes) render at the 12-13px body size in `text-secondary`, not 9-10px muted; `ScenarioSelector` selected state, Run and Run Sweep buttons are checked against `DESIGN.md` §14 and §18 contrast and fixed with existing tokens or recorded as an approved exception (D-8). Contrast is measured on rendered output, not assumed from authored sizes.
- R39. New learner-facing prose uses existing 12-13px body size literals; essential text is never below 12px (`DESIGN.md` §6); metadata labels use existing 10.5-11px.
- R40. Optional presentation props on existing components follow SPEC-012 §0 constraints (default-preserving; no computation, simulation state or data-fetching change).
- R41. Accessibility basics: all new controls are native elements (`button`, `input type=radio`, `details`, `a`); visible focus per `DESIGN.md` §18; stage nav and choosers have accessible names; any scroller is focusable and named; no information conveyed by color alone (existing status roles keep their text).
- R42. State is client-side React state only; no new global store, no new routing library. Moving between stages never clears Stage 2 results.
- R43. Loading and error states for every request are preserved in the new locations; an error in Stage 3 never blanks Stages 1, 2 or 4.
- R44. Stage 4 and all fixed strings are covered by the evidence-integrity rule: each string is either an existing shipped string or has a recorded source passage in the validation record (R14).

## 11. Integration and Sequencing with SPEC-012

**Ownership split.**

| Concern | SPEC-012 | SPEC-014 |
|---|---|---|
| `/learn` page and five guided cases | owns | none |
| Per-scenario lessons, "what is teaching" lines (G4) | owns | none |
| Compare All framing for shared numerical floor (Q13) | may frame | unchanged; Compare moves to Stage 3 intact |
| `SiteNav.tsx`, home card enabling `/learn` | owns R1 hunk | edits afterward (R30 nav, R34 home) |
| Shared Sandbox components (`TelemetryChart`, `ProtectionTimeline`, `ProtectionCoordination`, `ScenarioComparison`) | may add optional presentation props | consumes them; changes limited to R8, R16, R18, R30, R31 and must keep defaults |
| `Sandbox page.tsx` | not edited (R1: nav/home only) | owns |
| `/architecture` | none | owns |

**Shared-component propagation.** `/learn` composes `TelemetryChart` and `ProtectionTimeline`. Intended propagation to `/learn` (listed in full in §11.1): R18 caution sentence, R16 footnote wording, R30/R31 chart and scroller fixes. Everything else stays Sandbox-local. AC-15 regression-tests `/learn` after the change.

**Order.** (1) SPEC-012 implementation merges. (2) SPEC-014 approved by Human. (3) Branch `feature/spec-014-ux-redesign` from the new `main`. (4) Implement in four PR-sized steps on one branch or stacked PRs, in this order so each is reviewable and reversible: **(a)** Architecture Choices redesign (self-contained, no shared files), **(b)** Sandbox restructure (page-level only, existing components reused), **(c)** shared-component fixes (R8, R16, R18, R30, R31), **(d)** integration copy and home/nav (R34, R35) and System Map (R29, R32, R33). (5) Browser evidence, tests, Codex review, Human Visual QA, merge. SPEC-013 files are not touched; if SPEC-013 lands first, rebase and re-run AC-13.

**Start gate (confirmed).** SPEC-014 implementation begins only when all hold: (1) SPEC-012 is merged to `main`; (2) the Human gives final implementation authorization; (3) `git fetch origin` shows `main` containing SPEC-012's merge commit (the *prerequisite commit*); (4) the branch `feature/spec-014-ux-redesign` is created from current `main`, and the exact commit it is created from is recorded as the **synchronized base**. Baseline captures (AC-1, AC-4, AC-7, AC-11), the `pytest` count (AC-20) and all protected-path diffs (AC-19) are taken against the synchronized base. If the branch is later synchronized with `main` and the incoming changes touch `frontend/`, `src/`, `backend/`, `dashboard/` or `tests/`, the affected baseline captures and counts are refreshed at the new synchronized base and the validation record states which. Changes from other specs landing on `main` (for example SPEC-013) are not SPEC-014 changes and are excluded from AC-19 by diffing against the synchronized base. No implementation, commit or PR exists before then.

**If SPEC-012 slips:** SPEC-014 waits. No partial implementation before its merge (avoids two baselines and conflicting hunks).

### 11.1 Intentional shared-component changes and `/learn` effects

Approval of SPEC-014 is also the Human approval for these changes to components SPEC-012 composes; they go beyond SPEC-012 §0's optional-prop exception and are therefore listed here. Defaults of all other behavior are preserved.

| Component | Change | Effect on `/learn` |
|---|---|---|
| `ProtectionTimeline` | caution sentence under outcome banner (R18); footnote wording (R16) | adds the sentence and new footnote text on `/learn`; both are static strings; SPEC-012 AC-8 (backend strings verbatim) unaffected |
| `ScenarioComparison` | caution note beside outcome column (R18); footnote wording (R16); scroller (R30) | same, if `/learn` composes it |
| `TelemetryChart`, `SweepChart` | minimum drawn width in scroller (R30); cursor/label overprint fix and tick thinning (R31) | chart rendering changes on `/learn` at narrow widths |
| `PowerFlowSchematic` | scroll cue text (R30) | none unless composed |
| `SiteNav`, `layout.tsx` description | nav wrap and disabled styling (R30); metadata description (R1) | global |
| `TransientMetricsPanel`, `ProtectionTimeline`, `ProtectionCoordination`, `ProtectionCoverageChecklist`, `KpiTile`, `TimeScrubber` | essential labels move from `muted` to `text-secondary` and sub-11px sizes to 11px (R39a, F7); `TransientMetricsPanel` gains an opt-in `comfortable` prop (12px Sans basis prose) used only by the Sandbox | contrast and size changes visible on `/learn` where these components are composed; no content change (AC-15 diff) |
| `EvidenceTag` | optional `glyph` prop (default rendering byte-identical, AC-28) | none |
| `/learn` page itself | **not edited**; R35 role lines and next-step links apply to `/`, `/system-map`, `/architecture`, `/sandbox` only | none |

SPEC-012's acceptance criteria are re-run after these changes (AC-15). If SPEC-012 needs a text amendment because of them, it is made in the SPEC-014 PR and listed in AC-19.

## 12. Acceptance Criteria

**UX**
- [ ] **AC-1 Findings re-confirmed.** At the baseline, before any change, each of Q1-Q10 and audit items D1, D2, D3, D4, D5, G1, G2 is reproduced using the §13 steps, recording for each the expected observation (QA report wording) and the observed one; non-reproducing items are reported to the Human, not dropped by the implementer.
- [ ] **AC-2 Sandbox four stages.** `/sandbox` shows stage nav with four anchors in the specified order; each stage section has a heading and question; no "control center" text; `DISCLOSURES.sim` appears verbatim above Stage 1 (string imported, grep-verified).
- [ ] **AC-3 Architecture four steps.** `/architecture` shows four steps in order; with defaults only the RD1 driver card, its three comparison cells and its decision card are rendered for the driver-dependent content of Steps 1-3 (the independent interface/boundary content of Step 3 is also present); selecting each of RD1-RD7 changes exactly Steps 1-3 content to that driver's and leaves Step 4 and disclosures unchanged.
- [ ] **AC-4 Progressive disclosure is lossless.** The *union* of DOM text and `data-testid`s collected over (all seven driver selections in the default view) plus (the full views open) contains every cell, driver field, interface, decision and validation string and every `data-testid` of the baseline page; in each single rendered state every `data-testid` is unique. Baseline capture comes from the old page with each of the seven selector states.
- [ ] **AC-5 Product hand-offs.** The role line and next-step link on `/`, `/system-map`, `/architecture`, `/sandbox` match §3; no link targets a route that does not exist at that time; unbuilt areas (including `/industry`) are plain "(planned)" text; after SPEC-012, `/learn` links are live.

**Runtime**
- [ ] **AC-6 Console and network clean.** 0 console errors/warnings, 0 page errors, 0 failed or 4xx/5xx requests across all views and both viewports in the success-path runs (QA baseline); the deliberate failure tests of AC-10 are excluded and their expected errors are listed.
- [ ] **AC-7 Computation unchanged.** For all five scenarios (defaults), the experiment run, one sensitivity sweep (Load Step, default parameter and grid) and Compare All: network requests (URL, method, body) are identical to the baseline set except ordering; response JSON is byte-identical; no new endpoint is called. Compare All fetch-on-every-entry preserved (test: enter, leave, re-enter = 2 requests; induced failure then re-entry recovers).
- [ ] **AC-8 Feature inventory.** A script walks §8 tables and §6.4: every listed capability and state behavior is operable at its new location (scenario switching, each slider, Reset, Run, run-failure retention, scrubber keyboard Home/End and default index, sweep for both parameters, Compare All entry and re-entry, all disclosures, stale markers, provenance line). Result is a table in the validation record.
- [ ] **AC-9 Test ids.** All `data-testid` values captured across all states at baseline exist after, except these declared retirements: `view-mode-toggle`, `view-mode-option-single`, `view-mode-option-compare` (replaced by `study-option-sweep`, `study-option-compare`; the single-run view is always present, so `scenario-select` and `scenario-option-*` are unchanged). Any other retirement needs Human approval.
- [ ] **AC-10 State behavior.** Every row of the §6.4 matrix is exercised by script, including rapid scenario switching, failed Run and Reset (induced by routing the request to an error), in-flight sweep invalidation on scenario change, study switching, the disabled-study fallback, and Compare entry/failure/re-entry.

**Engineering accuracy and evidence integrity**
- [ ] **AC-11 Numbers unchanged.** KPI tiles, table cells, chart input data, units, domains and tick formatting equal the baseline for the AC-7 set; deliberately omitted tick labels are listed and excluded.
- [ ] **AC-12 Terminology.** No frontend-authored text, heading or label uses "Ride-Through" or raw enum names; every backend-supplied outcome string renders verbatim (equality against the API response); the R18 caution sentence is present beside every outcome banner (Sandbox single run, Compare All outcome column, and `/learn` if it composes `ProtectionTimeline`); each legacy backend string still on screen is listed with its location.
- [ ] **AC-13 Stage 4 traceability.** Every Stage 4 fixed string equals an Appendix A item and maps to its source passage; direct fields equal the response values; derived Load Step fields equal the existing `metrics` object; B-E show no derived numbers; no comparison-response data appears for a parameterized run; semantic review of every causal sentence by the reviewer (not keyword scan), as SPEC-012 R17 requires.
- [ ] **AC-14 Architecture integrity.** SPEC-011 AC-2..AC-8 and AC-10 re-run against the union of states (AC-4) and pass (counts, verbatim disclosures, no rank/score/best/winner terms outside D-NOWIN, ids unchanged); data-module content diff is empty; disclosures visible on load in the default view.
- [ ] **AC-15 `/learn` regression (after SPEC-012).** At SPEC-012's required widths the five lessons, disclosures and reference links still work and its own acceptance criteria touching shared components pass.

**Accessibility basics**
- [ ] **AC-16** Keyboard-only walkthrough of both pages completes every flow in §6 (stage nav with focus moving to the target heading, chooser, sliders, sweep, compare, every disclosure and expanded state, reused controls); visible focus on every control; names on stage nav, choosers and scrollers; automated check (axe or equivalent run through the existing Playwright harness, no new dependency in the repo) reports no critical or serious violation on new markup; contrast of any new text meets `DESIGN.md` §18.

**Mobile and desktop layout (D-1)**
- [ ] **AC-17 No clipping at 390x844** on `/`, `/system-map`, `/architecture`, `/sandbox` (all five scenarios, Compare All, Run Sweep): page `scrollWidth == 390` (necessary, not sufficient); for each scroller `scrollWidth > clientWidth` implies the cue, focusability and a name; for each essential element (stage nav, scenario selector, sliders, Run buttons, KPI tiles, schematic bus box, both charts, table headers, outcome banner, Stage 4) its bounding box lies inside the viewport or inside such a scroller; chart text renders no smaller than its authored size (implementer records `authored size x rendered width / viewBox width` per chart); stage nav and choosers are fully reachable without horizontal page scroll. Human reviews screenshots.
- [ ] **AC-18 Desktop polish** at 1440x900: Q6 resolved (in every lane that renders arrows today, exactly one arrow per adjacent node pair; lanes that intentionally omit arrows, such as monitoring, are unchanged; DOM count plus screenshot in all three views); Q7 and Q8 resolved (screenshots at scrubber Home, mid, End and after Run Sweep).

**Governance**
- [ ] **AC-19 Protected paths.** Baseline is the **synchronized base** recorded under the §11 start gate (it must contain SPEC-012's merge commit), refreshed per that rule. `git diff --name-only <baseline>` plus untracked files lists only `frontend/app/`, this spec (moved), `docs/validation/` artifacts, and approved amendments to `DESIGN.md`, `docs/specifications/SPEC-011-architecture-choices-v1.md`, the SPEC-012 file only if §11.1 requires a text amendment, and, if requested, `docs/PRODUCT_BLUEPRINT.md` (AC-21). `frontend/package.json` and lockfile unchanged.
- [ ] **AC-20 Build and tests.** `cd frontend && npm run lint && npm run typecheck && npm run build` pass; `pytest -q` at repo root passes with the same test count as the synchronized base (recorded, and re-recorded if a sync refreshes the base); CI green, reported separately from local results.
- [ ] **AC-22 Learner outcome.** A human walkthrough (Jason) in which, for one Load Step run and one Architecture driver, the learner states the observation, the model limitation and the validation need using only what the pages show; result recorded in the validation record.
- [ ] **AC-23 Copy approved.** Appendix A is approved by the Human before implementation, and implemented strings equal it exactly.
- [ ] **AC-21 Documents amended in the same PR if approved:** `DESIGN.md` §21 (D-1) and the §12 nav note if R30 changes it; SPEC-011 scope item 2 (five-section page order) and item 5 ("no other interactivity") amended to point to SPEC-014 (D-5); `PRODUCT_BLUEPRINT.md` §7 status line only if the Human requests it. These paths are in AC-19's allowlist.

## 13. Verification Plan

| Criterion | Method |
|---|---|
| AC-1, 6, 17, 18 | Playwright (Chromium, existing install in the QA worktree) at 1440x900 and 390x844 against `uvicorn` :8000 and `next dev`/`next start` :3000; before/after screenshots in `docs/validation/` |
| AC-2, 3, 5 | Browser walkthrough + DOM assertions; grep for banned strings |
| AC-4, 8, 9 | Scripted DOM capture of baseline (taken first, on the baseline commit) vs new "show all" and Stage views |
| AC-7, 11 | Network log capture (method, URL, body, response hash) for the fixed interaction script; DOM text diff |
| AC-10 | Scripted interactions; failure induced by routing the API request to an error |
| AC-12, 13, 14 | Grep and review table in the validation record; SPEC-011 mechanical checks re-run via throwaway script outside the repo |
| AC-15 | Same harness at 375 and 1280 px after SPEC-012 |
| AC-16 | Keyboard script + axe-core injected from a local path in the harness (not added to `package.json`) |
| AC-19, 20, 21 | `git diff --name-only`, `git status --short`, npm and pytest commands |
| Independent review | Codex reviews the diff against this spec (`AGENTS.md`); CI reported separately |
| Human Visual QA | Jason, using §9 questions on the screenshots and live app, before merge |

Reproduction steps for AC-1 (stand-alone, not dependent on the QA scripts): Q1-Q4 `/sandbox` 390 px Load Step, scroll to Power Flow and charts, run Sensitivity sweep, open Compare All; Q5-Q6 `/system-map` all three views at 390 and 1440 px; Q7 `/sandbox` 1440 px scrubber at Home; Q8 after Run Sweep; Q9 nav at 390 px; Q10 `/sandbox` heading.

## 14. Known Limitations

- Mobile verification is emulated viewport with mouse input; real touch, Safari, Firefox untested. Single dark theme. No Lighthouse audit.
- Stage 4 is generic by design; scenario-specific teaching lives in SPEC-012. A learner may therefore see a less specific takeaway for Scenarios B-E until/unless a later spec adds per-scenario text.
- Architecture validation needs are per architecture in the data; the UI cannot honestly tie them to the chosen driver without new content.
- Backend-authored prose (outcome headline, coordination text, file-path mentions) cannot be changed by a frontend-only spec; see D-R.
- Audit items D6, D7, P1 (architecture conditional-card wording, summary matrix), D8, G3 are not part of this spec.
- Visual quality is a human judgment; criteria here are structural.

## 15. Decisions Required (Human Engineering Lead)

| # | Decision | Recommendation |
|---|---|---|
| D-R | **RIDE_THROUGH terminology.** (a) Retain backend labels verbatim and add the caution sentence plus heading change (R18); leaves "RODE THROUGH CLEANLY" and one coordination sentence containing `RIDE_THROUGH` visible. (b) Authorize a separate, text-only backend adapter wording change spec (tests in `tests/test_protection_timeline.py` and SPEC-008/009/010 assert current strings) | **(a) now**; (b) as a follow-up spec if you want the legacy strings gone |
| D-8 | Typography/contrast of reused controls and disclaimers in touched panels (R39a): fix now, or record as known exceptions | Fix in touched panels only |
| D-1 | Amend `DESIGN.md` §21 so a 390 px "no silent clipping" floor is required while "true mobile optimization" stays out of scope | Approve (your brief already requires no silent clipping) |
| D-2 | Public audience phrase replacing "executive-level" | "systems-level reasoning and architecture judgment" (Blueprint §1) |
| D-3 | Keep System Map evidence labels (R33) in this spec or split to SPEC-015 | Keep, with the split trigger |
| D-4 | Mirror the Step 1 driver choice to a `?driver=` query parameter | Defer (not needed for V1) |
| D-5 | Amend SPEC-011 scope item 2 (five-section order) and item 5 ("no other interactivity") to authorize the stepped interaction here | Approve |
| D-6 | Stage 4 for Scenarios B-E stays generic until SPEC-012-style text exists | Approve |

## 15a. Requirements-to-Verification Map

| Requirements | Acceptance criteria |
|---|---|
| R1-R3, R19 (header, scope, stages) | AC-2, AC-16 |
| R4-R7, R9-R13, R42-R43 (workflow and state) | AC-7, AC-8, AC-10 |
| R5, R6, R8, R14-R15, R44 (explanatory copy, Stage 4) | AC-13, AC-23 |
| R16-R18 (footnotes, terminology) | AC-12 |
| R20-R28 (Architecture) | AC-3, AC-4, AC-14 |
| R29, R32, R33 (copy, handoff, evidence labels) | AC-1, AC-5, R33 inventory in the validation record |
| R30, R31 (layout floor, polish) | AC-17, AC-18 |
| R34-R36 (integration) | AC-5, AC-15 |
| R37-R41, R39a | AC-9, AC-16, AC-19 |
| Whole | AC-6, AC-11, AC-20, AC-22 |

## Appendix A. Copy Inventory (final wording for Human authorization)

Each item states its exact text, its **basis class**, its source, and what it deliberately does **not** claim. Implemented strings must equal these (AC-23); causal sentences are reviewed semantically (AC-13).

Basis classes (used so the reader can tell what kind of statement they are reading; a class is never displayed as "validated"):
- **M** Model-calculated: a value or behavior produced by this repository's simplified model (SPEC-011 label "Model output (simplified)").
- **P** Physical principle: a textbook relation the model implements (e.g. E = ½·C·V², dE/dt = P_sst − P_load). Reference not inspected, as `/architecture` words it.
- **A** Illustrative assumption: a modeling choice or a scenario input chosen for teaching (SPEC-011 label "Illustrative assumption"). Examples: first-order SST lag, constant efficiency, the load-step size, parameter values.
- **R** Real-equipment claim: **none are made anywhere in Appendix A.** No item states how certified or deployed hardware behaves or performs.

| Id | Text | Basis | Source in repo | Does not claim |
|---|---|---|---|---|
| A1 | **AI load step (kW):** "Final AI demand after the step, an illustrative test input. In this model, a larger step opens a larger initial gap between demand and SST output, because SST output follows demand with the response time set below." | step size A; gap behavior M (first-order lag `dP_sst/dt = (P_target − P_sst)/τ_sst`, `src/sst.py`) | `EventBanner`; `src/sst.py` governing equation | that real AI workloads step this way or that a real SST responds this way |
| A2 | **DC bus capacitance C_dc (F):** "One lumped capacitance for the whole bus. From E = ½·C·V², the same energy drawn from the bus moves V_dc less when C is larger. This value is not a sized or measured bus." | relation P; value A | `src/dc_bus.py` equations; `SensitivityStudy.tsx` intro | any real DC-link design or sizing |
| A3 | **SST response time τ_sst (ms):** "Time constant of a first-order lag on SST output power. It is a modeling assumption, not a measured or guaranteed hardware bandwidth. A longer τ_sst keeps the gap between demand and SST output open for longer." | A (assumption); gap statement M | `src/sst.py` ("engineering modeling assumption"); `TransientMetricsPanel` basis | any converter's actual control bandwidth |
| A4 | **Model scope:** `DISCLOSURES.sim` verbatim | A | `architectureChoicesData.ts` | n/a (existing text) |
| A5 | **What the model does not represent:** "A simplified average-value model: no switching dynamics, no AC power flow, constant efficiency, one lumped DC-bus capacitance, no cabling impedance, and no calibration to any commercial SST." | statements of model limits | `src/sst.py`, `src/dc_bus.py` Assumptions/Limitations; `SensitivityStudy` disclaimer | n/a |
| A6 | **Protection coverage:** "V1 models sustained thermal overtemperature protection only. It has no DC-bus undervoltage or overvoltage protection." Followed by the A13 caution. | model scope | `ProtectionTimeline.tsx` footnote; coverage checklist | that a real system lacks such protection |
| A7 | **V_dc chart:** "DC bus voltage over time, calculated by the model. The dashed line is the V_ref reference. For Load Step the marker is the lowest V_dc in the run." | M | `TelemetryChart` props; `sandbox/page.tsx` | that this voltage profile would occur in hardware |
| A8 | **Power-balance chart:** "P_load (dashed) is the scenario's AI demand; P_sst is SST output power calculated by the model. Where demand exceeds SST output, the model takes the difference from the energy stored in the DC bus (dE/dt = P_sst − P_load), until its numerical energy floor is reached; after that the model keeps running but no longer represents physically supplied energy, so values past that point are a numerical limit, not hardware behavior. For Load Step, the shaded area is the sampled positive-gap energy from the event to the V_dc minimum (energy, not power). The Engineering Result's energy deficit is the closed-form capacitor-energy change, so the two are defined differently." | relation P; behavior M; floor is numerical limit | `TelemetryChart` deficit polygon window; `TransientMetricsPanel` basis; `src/dc_bus.py` floor; `ScenarioComparison.tsx:142`; SPEC-012 R19(a) | that a real bus supplies or loses energy this way, or that any trip would be avoided or caused in practice |
| A9 | **To validate:** link text to `/architecture` Step 4: "What would have to be shown, and by what kind of evidence, before any real-world conclusion." | n/a (navigation) | `/architecture` Step 4 | n/a |
| A10 | **Study notice:** "Sensitivity sweeps are available for Load Step only." | UI capability limit | existing behavior | n/a |
| A11 | **Fixed preset line:** "This scenario is a fixed preset; parameters are not adjustable here." | UI capability limit | existing behavior | n/a |
| A12 | **Stale markers:** "Values changed since this run." / "Values changed since this sweep." / "Slider values not yet run." | UI state | none (no engineering content) | n/a |
| A13 | **Outcome caution (R18), shown beside every outcome banner and Compare All outcome column:** "Outcome labels are this simplified model's classification of the run, not certified hardware fault-ride-through performance. The model has no fault ride-through dynamics." | model scope | R18; `src/grid.py` limitations | any performance of real equipment |
| A14 | **Stage 4 standing statement:** "Nothing here is a validated measurement of real equipment. Values are outputs of a simplified model with illustrative parameters." | model scope | `CLAUDE.md` integrity rules; `src/sst.py` and `src/dc_bus.py` Assumptions/Limitations; parameters in `config/` | n/a |

**Stage 4 field labeling.** Each Stage 4 block carries one of the four existing evidence labels from `EvidenceTag`: live values (outcome and coordination labels, event, minimum V_dc, energy deficit, recovery time) are **Model output (simplified)**; A1-A3 parameter statements, A5 and A14 are **Illustrative assumption**; A9 is a link. Backend-supplied strings are shown verbatim and are never re-worded to sound like a performance statement. Where a block mixes classes (A1-A3: principle P, model behavior M, assumption A), the displayed label follows the existing weakest-claim convention (**Illustrative assumption**) and the P/M distinction is kept in the block's basis text. Recovery and coordination labels are backend strings labeled **Model output (simplified)**; A6 and A13 scope statements are **Illustrative assumption** (model scope). Causal wording is limited to relations the model itself implements (A1-A3, A8); no sentence says what "limited" a run.

**Semantic review notes (this revision).** (1) A1 originally said "a larger step opens a larger mismatch": tightened to the *initial* gap under the first-order lag, because the PI voltage controller can drive P_sst above demand later. (2) A2 originally said "sets how far V_dc moves per joule": stated through E = ½CV² so the principle is named. (3) A3 now states that τ_sst is an assumption, as `src/sst.py` itself says. (4) A8 gained the post-floor limitation and the distinction between sampled shaded area and closed-form deficit. (5) The earlier outcome caution described `RIDE_THROUGH` only; it is now classification-neutral (A13).

## 16. Review Record

Previous remediation-only draft (v0.2): Codex review CHANGES_REQUIRED, 0 blocking, 7 major, 4 minor, all resolved into that draft; carried over into R29-R33, AC-17-AC-19.
Codex CLI 0.162.1 (`codex exec`, read-only, against `4e6af36`), review of the UX redesign v0.1: **CHANGES_REQUIRED**, 1 blocking, 8 major, 3 minor. Resolutions in v0.2:

| # | Finding | Resolution |
|---|---|---|
| 1 BLOCKING | Terminology contract contradictory; "Recovered within model" conflates outcome and recovery | R18 rewritten: backend labels retained verbatim, caution sentence added, recovery kept separate, legacy strings enumerated; D-R and AC-12 updated, D-7 removed |
| 2 MAJOR | Lossless view underspecified | R21a, AC-4 union-of-states capture, unique testids, SPEC-011 items 2 and 5 amended (D-5, AC-21) |
| 3 MAJOR | Stage 4 data contract | §6.3 field table; no comparison data for parameterized runs; B-E show no derived numbers; AC-13 |
| 4 MAJOR | New engineering copy unsourced/semantic | Appendix A exact copy inventory with sources and conditions; semantic review; AC-23; A8 keeps shaded-area vs closed-form distinction |
| 5 MAJOR | State contracts missing | §6.4 state-transition matrix; provenance line; stale markers; disabled-study fallback; AC-10 |
| 6 MAJOR | Compare All fetch behavior wrong | R13 and AC-7: fetch on every entry preserved, no caching |
| 7 MAJOR | DESIGN.md compliance beyond mobile | R39a scopes typography and contrast fixes to touched panels; D-8 |
| 8 MAJOR | Sequencing contradictions | Single plan (wait for SPEC-012), baseline = synchronized base containing its merge commit, §11.1 lists shared-component changes and `/learn` effects, R35 excludes `/learn` |
| 9 MAJOR | Acceptance not demonstrable | ACs reworded (1, 4, 5, 6, 8, 9, 10, 13, 14, 16, 17, 18, 20), AC-22/23 added, §15a map |
| 10 MINOR | Marginal ROI | `?driver=` deferred; R33 concrete split threshold (>25 claims); AC-22 learner-outcome walkthrough |
| 11 MINOR | Citations | Corrected (existing heading, always-visible basis, layout.tsx, cross-references, AC-9 ids) |
| 12 MINOR | Template and paths | §5.1 Assumptions added; AC-19/21 allowlist reconciled; tooling source stated |

Closure review (bounded, Codex CLI, same checkout): CHANGES_REQUIRED, 0 blocking, 2 major, 4 minor. All six addressed in v0.3:

| Finding | Resolution |
|---|---|
| MAJOR R18 caution wrongly describes trip/collapse outcomes | Caution made classification-neutral (R18, A6) |
| MAJOR A8 implies DC bus supplies energy after numerical floor | A8 qualified with the floor/ideal-sink limit; sources extended (`src/dc_bus.py`, SPEC-012 R19(a)) |
| MINOR stale R22/R14 references | corrected to R14/R44 and R7 |
| MINOR Stage 2 order conflict | wireframe aligned to R7 |
| MINOR AC-19 allowlist vs §11.1 | SPEC-012 file allowed only if §11.1 amendment needed |
| MINOR AC-3 over-restrictive | AC-3 distinguishes driver-dependent content from independent boundary content |

Final bounded closure review (R29-R33, Appendix A, start gate), Codex CLI: the prior 2 major / 4 minor are **resolved**; Appendix A makes no certified ride-through or validated-hardware claim. Verdict on the reviewed text: CHANGES_REQUIRED for 1 new major (start gate vs baseline conflict) and 3 minor (Stage 4 weakest-claim labeling, R31 arrow exemption, A14 citation). All four are resolved in this revision (synchronized-base rule in §11 and AC-19/20; labeling paragraph; R31; A14 sources). A bounded diff-only check of those four edits returned **APPROVE** (0 blocking, 0 major); its two minor wording items (summary lines still saying baseline = SPEC-012 merge commit; A14 citation phrasing) were applied.


## 17. Foundation Amendment (Signal Path)

**Authority.** Human decisions of 2026-10-19: Signal Path is the shared visual and interaction direction; D1 page headlines up to 40px; D2 sentence-case Plex Sans headings with Plex Mono for values, equations and concise metadata; D3 signal-path rail retained with correct architecture semantics; D4 SPEC-011 mandatory disclosures remain visible on initial load; D-A Learn shell is a separate bounded SPEC-012 amendment after this work; D-B delivery order is foundation plus SPEC-014, then SPEC-013, then the Learn shell; the DESIGN.md revisions are adopted through this spec's foundation PR; `/design-lab` and the `SiteNav` bypass never ship. This amendment adds the foundation and changes sequencing; it does not change §1-§16 requirements except where stated.

**State change.** SPEC-012 (PR #9) merged at `f9cc8c4` (`main`). §11's "SPEC-012 merged first" gate is satisfied; the synchronized base is recorded in the validation record. `/learn` exists, so R35/R36 links to it are live and AC-15 runs against the shipped Learn page and `docs/specifications/SPEC-012-learn-by-example-v1.md` acceptance criteria.

### 17.1 Scope added

- F1. **Tokens and type tiers** (DESIGN.md §6, §3, §5, §9): page title 28px (mobile) to 40px (from `sm`), 600, sentence case, one per page; section heading 14-18px sentence case `text-primary`; body 13-14px (lede up to 16px once per page); metadata 10.5-12px. `surface-inset` and `hairline-strong` implemented as tokens. Weight never above 700. The old homepage-headline exception is removed. Implemented as CSS custom properties and Tailwind theme entries already used by the app (`globals.css`), with no new dependency.
- F2. **Mono rule** (DESIGN.md §6, §22): Plex Mono for live/tabular values, equations, code and concise instrument metadata (tags, units, chart ticks, step and area numbering); never for running prose or headings.
- F3. **`AreaHeader`**: page title, role line and next-step link per §3 of this spec (R35), reused by the four existing pages; not used on `/learn` until the Learn shell amendment.
- F4. **`BasisPanel` (disclosures)**: structured, always-visible panel; wording imported from the spec's canonical constants, never retyped: SPEC-011 `DISCLOSURES` on `/architecture` and `/sandbox`; `/system-map` uses `DISCLOSURES.sim` and `DISCLOSURES.block` as today's copy requires (§10 R29, R2). Never collapsed, paraphrased or placed behind interaction (D4). Presentation may change; wording and initial-load visibility may not. `/learn` keeps its own disclosures untouched.
- F5. **`SignalPathRail`**: draws the *selected architecture's* own main power path from `infrastructureMapData.ts` (ids and labels unchanged), never one universal chain. An SST node appears only in the Conceptual MV-to-800 VDC via SST architecture and is labeled conceptual (DISCLOSURES.sst). On `/architecture` and `/system-map` the rail follows the selected architecture. On `/sandbox` the rail is pinned to the Conceptual SST architecture and the simulated slice is marked with dashed node borders; a visible legend states that dashed nodes are simulated and that stages the model does not represent (for example rack DC-DC conversion) are not modeled. The accessible name lists the node sequence and the simulated-slice limitation. At 390px it collapses to a label row and dot track and stays compact. `role` and focus follow DESIGN.md §18.
- F6. **`EvidenceTag` glyph prop**: neutral glyph (square public fact, circle illustrative assumption, diamond model output, triangle emerging) plus the canonical label text, added as an optional presentation prop whose default preserves current rendering. Basis, references, canonical label text ("Model output (simplified)") and reference destinations are unchanged. Evidence never uses a status colour. The registry (`REFERENCES`) is not edited by the foundation.
- F1a. **Precedence.** F1's 13-14px body tier supersedes R39's 12-13px range and R39a's body size; the 12px floor for essential prose still holds, and F7 is compatible with R39a.
- F7. **Contrast and legibility** (DESIGN.md §18; also amends the §7 unit-suffix color from `muted` to `text-secondary`, found by the axe contrast check): essential text, including chart reference-line labels, uses `text-secondary` or brighter; `muted` is limited to non-essential decoration (extends R39a).
- F8. **Scrollers**: a shared named, keyboard-focusable scroller with a visible text hint (R30); chart text never renders below its actual authored size (the foundation does not raise existing chart label sizes, some of which are 9.5-10px, and records them; AC-17 and AC-27 use that same rule).
- F9. **DESIGN.md revisions applied in the foundation PR**, replacement text is **Appendix B of this spec** (copied verbatim from the reviewed `docs/design/DESIGN_MD_REVISIONS.md` at commit `653a03e`, which is a prototype-branch file and is not itself merged) (§6 tiers, §6/§22 mono rule, §12 rail, disclosure panel, §3/§5/§9 tokens, §4/§16 evidence chips, §21 responsive, §18 contrast). The same PR carries the D-1 §21 amendment of §12 of this spec and any SPEC-011 amendment already approved (D-5). Only reviewed text lands; the existing gradient and shadow prohibitions are unchanged.
- F11. **Rail architecture selector.** `/architecture` and `/system-map` present the rail with a three-option architecture selector (native radio group over `ARCHITECTURE_ORDER`, labels from `ARCHITECTURE_CHOICE_NAMES`, default Conventional AC, first in order), independent of the Step 1 driver selection and of the System Map's own view selector (which keeps its current behavior; on `/system-map` the rail follows that existing view selection instead of adding a second control). State is component state per page; nothing is shared across pages.
- F10. **Preserved product-role contract.** System Map explores structure; Architecture Choices evaluates alternatives from requirements; Learn by Example is guided cause and effect; Advanced Sandbox is free quantitative experimentation; Industry & Career connects knowledge to industry and competencies. Shared tokens and the rail are shared; interaction models are not. Architecture's four-step evaluation and the Sandbox's four-stage workbench must not adopt Learn's Predict/Discover/Explain/Apply shell. `/learn` is changed only by (a) global token propagation and (b) the §11.1 shared-component propagation (outcome caution, footnote wording, chart and scroller fixes), which are the only authorized effects on Learn; its layout, content and behavior are otherwise unchanged.

### 17.2 Explicit exclusions

- No `/design-lab` route, directory, nav entry, or `SiteNav` bypass in any production commit; AC-24 checks the diff.
- No Learn shell (stepper): separate bounded SPEC-012 amendment after this PR (D-A). `/learn` is not edited; it receives only global token changes and is regression-tested (AC-15).
- No Industry & Career route or nav activation: SPEC-013 owns it; the item stays "(planned)" and its home card unchanged.
- The prototype's chart decimation is not adopted; existing chart behavior stays (R14, R31).
- No tab-role pattern without full tab/panel association; native buttons and links only (R41).
- No edits to `REFERENCES` content, to Learn content or to SPEC-013 scope.

### 17.3 Ownership (SPEC-014 rows of the integration table)

| Area / file | Owner |
|---|---|
| Tokens, type tiers, `AreaHeader`, `BasisPanel`, `SignalPathRail`, shared scroller, `EvidenceTag` glyph prop, DESIGN.md revisions | SPEC-014 (this foundation) |
| `/system-map`, `/architecture`, `/sandbox`, home page, role lines | SPEC-014 |
| Shared Sandbox components changed per §11.1 (outcome caution, footnotes, chart and scroller fixes) and their effect on `/learn` | SPEC-014, regression-tested against shipped `/learn` (AC-15) |
| `/learn`, `learnByExampleData.ts`, `LearnByExample.tsx`, `CaseSelector.tsx`, Learn shell | SPEC-012 (shell via D-A follow-up) |
| `/industry`, Industry nav item and home card | SPEC-013, after this foundation, using its components |

### 17.4 Sequencing (replaces §11's four-step order; the start gate is unchanged)

0. Foundation (F1-F10) with DESIGN.md revisions. 1. Architecture Choices redesign. 2. Sandbox restructure. 3. Shared-component fixes (R8, R16, R18, R30, R31). 4. Integration copy, home, nav wrap, System Map (R29, R32-R35). Each step lands as a separate commit on one branch `feature/spec-014-ux-redesign`; the PR is verified as a whole (gates §13) and merged only on explicit Human approval.

### 17.5 Added acceptance criteria

- [ ] **AC-24 No prototype artifacts.** `git diff --name-only <synchronized base>` has no path under `frontend/app/design-lab/`, no `/design-lab` string in `SiteNav.tsx`, and no `design-lab` reference in production code.
- [ ] **AC-25 Rail semantics.** For each of the three architectures the rendered rail's node labels equal that architecture's `main` lane labels from `infrastructureMapData.ts` (script check); the SST node exists only in the Conceptual SST architecture; `/sandbox` rail is pinned to it with dashed simulated nodes, a visible legend and the unmodeled stages named; the accessible name lists the node sequence; at 390px the rail height does not exceed its label row plus track and causes no page overflow.
- [ ] **AC-26 Disclosures visible on load.** On initial load at 1440x900 and 390x844, in the default view with no interaction, the five SPEC-011 `DISCLOSURES` strings are present verbatim in the visible DOM of `/architecture` (existing SPEC-011 AC-7 text check) and `DISCLOSURES.sim` on `/sandbox`; they are not inside `display:none`, a closed `details`, or an off-screen scroller; strings are imported from the canonical module (grep).
- [ ] **AC-27 Type and contrast.** Page titles are 28-40px, one `h1` per page, sentence case; section headings sentence case; no essential text below 12px outside metadata tier (10.5-12px) and chart text never below its authored size; measured contrast of essential text on rendered output meets DESIGN.md §18 (recorded per page).
- [ ] **AC-28 EvidenceTag unchanged by default.** Without the glyph prop the tag's DOM and link target are byte-identical to the baseline; with it, label text equals the canonical text; `/architecture` renders the same evidence label strings and reference links as the baseline for all cells.
- [ ] **AC-29 DESIGN.md applied.** The applied text equals Appendix B; sections not listed are byte-unchanged; no gradient or shadow introduced.
- [ ] **AC-30 Role distinctness.** Reviewed by the Human at Visual QA: the five areas' primary interaction models are visibly different; Sandbox and Architecture contain no Predict/Discover stepper; Learn's layout, content and behavior are unchanged apart from the authorized token and §11.1 propagation, whose effects AC-15 documents.

### 17.6 Limitations and risks

- Global token changes affect `/learn` appearance without editing it; AC-15 and Human Visual QA cover this. If Learn's shipped layout breaks under the new tiers, a Learn-scoped override is added in the foundation (not in Learn files) and listed.
- The rail is a navigation and context device, not a physical diagram; it does not assert that any architecture is better.

## Appendix B. DESIGN.md Revisions (normative text for the foundation PR)

(Reviewed at `653a03e`; applied only through this spec's foundation PR.)

`DESIGN.md` is unchanged on this branch. These replacement texts are the only revisions Signal Path needs; they land in the foundation PR after review.

**§6 Typography: replace the tier table with:**

| Tier | Token | Size | Weight | Treatment |
|---|---|---|---|---|
| Page title | `text-page-title` | 28px (mobile) to 40px (from `sm`) | 600 | Plex Sans, sentence case, -0.02em, one per page |
| Section / panel heading | `text-heading` | 14 to 18px | 600 | Plex Sans, sentence case, `text-primary` (replaces the uppercase 11.5px muted tier) |
| Body / explainer | `text-body` | 13 to 14px (lede up to 16px, once per page) | 400 | `text-secondary` |
| Metadata / label / unit | `text-meta` | 10.5 to 12px | 500 to 600 | Plex Mono uppercase for tags and units; Plex Sans 12px for plain labels |

The "homepage headline" exception is removed (the page-title tier covers it). Weight never exceeds 700.

**§6 and §22 mono rule: replace "Keep IBM Plex Mono exclusive to live/tabular/code data" with:** "Plex Mono is used for live or tabular values, equations and code, and for concise
instrument metadata (tags, units, chart ticks, step and area numbering). It is never used for running prose or headings."

**§12 Navigation: add after the nav paragraph:** "A single signal-path rail may sit under the nav. It draws the selected architecture's own main power path from the
System Map data and never one universal chain. An SST node appears only in the Conceptual MV-to-800 VDC via SST architecture and is labeled conceptual. Pages that run
the simulation pin the rail to that architecture and mark the simulated slice with dashed node borders; the page's Basis & limits panel carries the legend (dashed nodes
are simulated; stages the model does not represent, such as rack DC-DC conversion, are named as not modeled). Focus is shown by surface tier and weight, never color. The rail
exposes the node sequence in its accessible name. On narrow screens it collapses to a label row and a dot track."

**§1 and new §: Basis & limits panel.** "Mandatory spec disclosures are visible on initial load, verbatim, in a structured panel (mono tag plus text). They are never collapsed,
paraphrased or hidden behind an interaction. Presentation may change; wording and visibility may not. Each page imports the canonical constants of its spec (SPEC-011 `DISCLOSURES`,
SPEC-012 `LEARN_DISCLOSURES`)."

**§3, §5, §9:** promote `surface-inset` (#0d131a) and `hairline-strong` to implemented. A selected control changes surface tier and border to `hairline-strong`; no shadow and no ring.
The §18 keyboard focus outline (2px `secondary`) is unchanged and applies in addition.

**§4 / §16 evidence labels:** evidence labels render as neutral chips with a glyph (square public fact, circle illustrative assumption, diamond model output, triangle emerging)
plus the canonical label text. The existing `EvidenceTag` gains the glyph as a presentation prop; its basis, references and reference destinations are unchanged. Evidence never uses a status color.

**§21 Responsive:** the four learning areas must be readable at 390px with no horizontal page scroll; wide tables and charts scroll inside a named, keyboard-focusable
container with a visible hint, and chart text never renders below its authored size. The Advanced Sandbox remains desktop-first and keeps SPEC-014's no-clipping floor.

**§18 contrast:** essential text (including chart reference-line labels) uses `text-secondary` or brighter; `muted` stays limited to non-essential decoration.

**§7 units (added during implementation, axe color-contrast finding):** the unit suffix of a live value uses `text-secondary` instead of `muted`.

Unchanged: tokens, dark canvas, one accent, four status roles, 4px radius, no gradient or shadow, no animation, Plex families, tabular numerics, the Implementation Contract and Engineering Visual Semantics.
