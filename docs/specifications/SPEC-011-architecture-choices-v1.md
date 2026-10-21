# SPEC-011 — Architecture Choices V1

**Status:** Draft v0.3 — product decisions approved by the Human Engineering Lead (2026-10-18); v0.2 returned `CHANGES_REQUIRED` (0 blocking/4 major) from the one bounded Codex closure review; v0.3 applies those four fixes and was not re-reviewed before implementation (human-approved gate exception, 2026-10-18). Implemented on branch `feature/spec-011-architecture-choices`; see `docs/validation/SPEC-011-validation.md`. Pending Human Engineering Lead approval to merge.
**Project:** AI Power Lab
**System:** `frontend/app/` only (new route `/architecture`; nav, home-card and System Map display-name updates). No change to `src/`, `backend/`, `content/`, `data/`, `tests/`, or CI.
**Version:** 0.3
**Type:** Software Component (content-driven page)

---

## Engineering Question

Given a stated set of power-delivery requirement drivers, how do three architectures — **Conventional AC**, **AC-fed 800 VDC**, and **Conceptual MV-to-800 VDC via SST** — differ in how they meet each driver, what interfaces they create, which choice each depends on, and what would need to be validated before relying on it?

## Motivation

`docs/PRODUCT_BLUEPRINT.md` Stages 1, 3 and 5 have no surface today (§7: Architecture Choices "Not implemented"). The System Map carries scattered requirement-like and interface-like material but no structured, requirements-driven comparison. `PROJECT_CHARTER.md` §5–§7 directs a move from display work toward trade-study and requirements reasoning without fake precision.

## Product ROI and Career ROI

**Product ROI.** Moves the learner from *explain* to *compare* and the first step of *trade study*: requirement drivers are made explicit, architectures are compared against them without scores, and the decision is conditional on which driver dominates.

**Career ROI.** Practices requirements elicitation, functional-versus-physical architecture, interface definition, trade-study discipline without fake precision, and writing validation needs. Maps to Blueprint §6 competencies: Systems Engineering / Architecture, AI data-center power distribution, power-conversion architecture, system validation, technical trade studies.

## Scope

1. New route `/architecture`. The existing nav entry becomes a live link; the home-page card changes from `planned` to `live`. Other areas stay `planned`.
2. Five sections, in order: **Requirement drivers**, **Architectures by driver**, **Interfaces**, **If this driver dominates**, **Validation needs**.
   *Amended by SPEC-014 (2026-10-19): the content is unchanged, but it is presented as four steps with progressive disclosure (Identify the requirement, Compare architectures, Understand trade-offs, Define validation needs); the "if this driver dominates" content is the Step 3 decision card for the Step 1 driver, and "show all" controls render every driver, comparison, decision and boundary. The mandatory disclosures (R2) stay visible on initial load.*
3. Static typed content in a new `frontend/app/lib/architectureChoicesData.ts`, keyed by the existing `ArchitectureId` values (`conventional-ac`, `ac-to-800vdc`, `mv-to-800vdc`, **preserved unchanged**). Interfaces reference existing System Map node ids.
4. Display names, used on `/architecture` and applied to the System Map's `name` fields so both pages agree: **Conventional AC**, **AC-fed 800 VDC**, **Conceptual MV-to-800 VDC via SST**. Ids do not change.
5. One lightweight client component: a single-select control for "which driver dominates", revealing that driver's conditional-decision card. In-page anchor navigation and native disclosure (`<details>`) are also permitted. No other interactivity.
   *Amended by SPEC-014 (2026-10-19): interactivity is extended to native radio choosers for the requirement driver, the power-path architecture and the interface boundary, native "show all" toggles, and in-page stage navigation. No scores, ranking or fetches are added.*
6. Evidence label on every content item, using Blueprint §5.1 categories.

### Requirement drivers (all **illustrative teaching assumptions**)

| ID | Driver | Distinct question |
|---|---|---|
| RD1 | Rack power and growth | How much power must reach each rack, and how does delivery scale as that grows? |
| RD2 | Load dynamics | How fast can the load change, and where does the energy buffer sit? |
| RD3 | Availability and maintainability | What redundancy exists, and can a section be isolated and worked on? |
| RD4 | Safety and protection practice | How are faults cleared, and how is personnel safety managed? |
| RD5 | Conversion chain and losses | How many series conversion functions exist, and where is heat produced? |
| RD6 | Physical footprint | What space, conductor cross-section and cooling infrastructure does delivery require? |
| RD7 | Standards and ecosystem maturity | How settled are the standards, equipment supply and operating practice? |

Non-redundancy: RD1 is *delivered power and its growth*; RD6 is *physical consequence* (space, copper, cooling); RD5 is *losses and stage count* (heat origin), distinct from RD6's heat *rejection infrastructure*. RD2 concerns time-domain behavior; RD3 availability; RD4 fault/safety; RD7 maturity. These are not a design basis for any facility.

## Out of Scope

- Backend or API changes, `src/` changes, any new simulation of Conventional AC or AC-fed 800 VDC.
- Numeric scores, rankings, weighted matrices, a universal winner or recommendation, optimization.
- Quantitative vendor, efficiency, cost or adoption comparisons; any unattributed performance claim.
- Learn by Example and Industry & Career content; Streamlit changes (Phase B); new dependencies, test frameworks, or orchestration tooling.

## Model / Technical Basis

No equations are modeled. Content is qualitative reasoning. Where a physical relationship is invoked (for example, conductor current at a given power scales as 1/voltage; stored capacitor energy ½CV²; conversion losses compound across series stages), it is a textbook relationship and is labeled **Public fact**, with the principle named in `basis` and a named textbook, standard, or `data/industry/` source id supporting it. Source-attributed statements cite only sources already recorded in `data/industry/` (NVIDIA 800 VDC blog; OCP LVDC/SST blog) with their `verified_date`. No figure from a vendor listing is used.

## Assumptions

- Requirement drivers and the three architectures are illustrative simplifications (System Map `caveat` fields apply).
- Each architecture is one representative pattern; real facilities vary.
- The Advanced Sandbox model covers the SST slice only (see mandatory disclosures).

## Requirements

- R1. Architecture names exactly as in Scope item 4; ids unchanged.
- R2. **Mandatory disclosures** appear as visible sentences on `/architecture` with this fixed wording:
  - **D-SST:** "SST is one candidate technology for the medium-voltage-to-DC stage. It is not required for 800 VDC: the AC-fed 800 VDC architecture reaches the same bus without one."
  - **D-BLOCK:** "Blocks in these architectures are functional abstractions, not literal single-stage converters or literal racks; real equipment is internally multi-stage."
  - **D-SIM:** "The Advanced Sandbox simulates only the Conceptual MV-to-800 VDC via SST slice, as a simplified average-value model. It does not validate, size or benchmark Conventional AC or AC-fed 800 VDC, and it is not evidence that any architecture is better."
  - **D-ILL:** "Requirement drivers are illustrative teaching assumptions, not a design basis for any facility."
  - **D-NOWIN:** "This page does not rank architectures or name a winner; every conditional statement depends on which driver dominates for a given site."
- R3. Every driver and every conditional decision answers the five Blueprint §4 questions (what / why it matters / system connection / constraints and trade-offs / decision informed).
- R4. For each of the 7 drivers × 3 architectures (21 cells): `how` (how addressed and what it relies on), `harder` (what it makes harder), an evidence label from {Public fact, Illustrative assumption, Model output, Emerging/uncertain}, and a non-empty `basis`. Every factual qualitative claim (safety, maturity, losses, preference included) must cite a supporting public reference in `basis` (a `data/industry/` source id, or a named textbook or standard); otherwise it is labeled **Illustrative assumption**. `Emerging/uncertain` claims are attributed to a named public source or omitted. The same rule applies to R6 `because` clauses and R7 items. Each reference records what was actually inspected; a textbook or standard that was not opened is listed as background for a general principle and is never described as verified. Vendor statements, consortium documents, textbook principles and repository material are shown as distinct source types. Model-output labels are permitted only for `mv-to-800vdc` and must point to the Sandbox.
- R5. Interfaces: for each architecture, the five boundaries — MV/utility, conversion-to-distribution, distribution-to-rack, storage/backup, monitoring/control — each with `crosses` (what passes the boundary), `concern`, and the existing System Map node ids on either side.
- R6. Conditional decisions: exactly one per driver (7), each with `dominantDriver`, `favored` (a non-empty set of architecture ids, never an assertion of one universal winner), `because`, and at least one `unless`.
- R7. Validation needs: per architecture, at least four items, each naming what is verified and the kind of evidence (analysis, simulation, factory test, site test, conformance review).
- R8. Follow `DESIGN.md`: existing tokens, text-only labels, no new status colors; evidence labels are neutral text.

## Acceptance Criteria

- [ ] AC-1 `/architecture` builds and renders; `SiteNav` and the home card link to it; the other planned areas still render as planned.
- [ ] AC-2 Exactly seven drivers RD1–RD7 render, each with the five Blueprint §4 answers, and D-ILL is visible.
- [ ] AC-3 The 21 cells exist (enforced at compile time by the data type: `Record<DriverId, Record<ArchitectureId, Cell>>`), each with `how`, `harder`, evidence label and non-empty `basis`; every `Public fact` or `Emerging/uncertain` cell cites a named reference or `data/industry/` source id, and every other cell is labeled `Illustrative assumption` (content walkthrough); no cell contains a digit-bearing performance figure not present in a cited repository source (checked by search).
- [ ] AC-4 Interfaces: 5 boundaries × 3 architectures; every referenced node id exists in `ARCHITECTURES` (checked by script).
- [ ] AC-5 Exactly seven conditional decisions, one per driver; each has a non-empty `favored` set, `because`, and ≥1 `unless`; selecting each driver in the browser reveals only that driver's card.
- [ ] AC-6 Each architecture lists ≥4 validation items, each with an evidence-kind from the fixed set.
- [ ] AC-7 D-SST, D-BLOCK, D-SIM, D-ILL and D-NOWIN appear verbatim on `/architecture` (checked against rendered text).
- [ ] AC-8 No numeric score, ranking, weighting, or single "best" statement appears in data or UI (checked by search for rank/score/best/winner/weight terms outside D-NOWIN's own sentence).
- [ ] AC-9 No file changes under `src/`, `backend/`, `content/`, `data/`, `tests/`, `.github/`; no changes to `frontend/package.json` or the lockfile; changed-file list reviewed including untracked files.
- [ ] AC-10 Architecture ids are unchanged (`git diff` shows no id edits); System Map display names match R1; System Map still builds and renders.

## Verification Plan

- `pytest -q` (regression evidence that engine and backend behavior is unchanged; file-level preservation is shown by the inventory check below, not by this).
- `cd frontend && npm run lint && npm run typecheck && npm run build` (AC-1, AC-3 compile-time part).
- A throwaway script run outside the repository checks mechanical conditions only: AC-3 digit scan, AC-4 node ids and boundary count, AC-5/AC-6 cardinality and field presence, AC-8 term search. Output is quoted in the validation record.
- A recorded content walkthrough, written into the validation record as a table mapping R3, R4, R6, R7 and AC-2, AC-3, AC-4, AC-6, AC-8 to the specific content checked, including semantic review of AC-8 beyond keyword matching and the five-question check on every driver and conditional decision.
- Browser walkthrough with the production build: nav and home links, planned states, disclosures verbatim, driver selector, keyboard focus order, contrast per `DESIGN.md`, a narrow viewport; System Map regression check (AC-1, AC-5, AC-7, AC-10, R8).
- Full inventory (AC-9): `git status --short` (staged, unstaged, untracked), `git diff --name-status main...HEAD`, and `git diff main -- frontend/package.json frontend/package-lock.json` empty.
- Independent Codex review of the diff and recorded evidence. Results recorded in `docs/validation/SPEC-011-validation.md`.

## Known Limitations

- Content is only as sound as its public sourcing; there is no model behind Conventional AC or AC-fed 800 VDC. Review rigor is the control.
- The comparison cannot rank architectures for a specific site.
- Operating-experience and adoption data are deliberately absent.
- Only the SST slice has any simulation support, and it is simplified (average-value, thermal-only protection).
- Unresolved questions for the Human Engineering Lead: none blocking; the driver set may be revised before approval.
