# Signal Path: implementation plan (one page, revised after Codex review)

**Status (2026-10-19):** Signal Path approved; D-A and D-B approved by the Human Engineering Lead (below). Ownership-table confirmations from the SPEC-012, SPEC-013 and SPEC-014 owners and the Mac-based Codex closure review of 653a03e are **pending** (routed by the coordinator). Claude's fixes in 653a03e are not independently approved until that review returns.

**Principle.** `/design-lab` is a design reference, not a merge candidate and not a conforming implementation of any SPEC.
Production code is rebuilt from it in gated PRs that reuse existing data modules and components. No change to `src/`,
`backend/`, API shapes, thresholds or engineering claims. PR #9's branch and other threads' worktrees are not touched.
Note: the prototype itself touches one production file, `components/SiteNav.tsx` (3 lines that hide the old nav under
`/design-lab`); that line must not ship.

## 1. Ownership table (one source of scope)

Scope for SPEC-014 and SPEC-013 below is as reported by the Codex review of their current drafts (SPEC-014 §§5, 6, 11, AC-4, R2; SPEC-013
nav/home ownership). I have not read the SPEC-014 draft itself. **The SPEC-014 and SPEC-013 owners must confirm or correct this table
before it is treated as agreed.**

| Area / file | Owner | Signal Path contribution | Rule |
|---|---|---|---|
| `/learn`, `learnByExampleData.ts`, `LearnByExample.tsx`, `CaseSelector.tsx` | SPEC-012 (PR #9) | none until PR #9 merges | SPEC-014 draft excludes `/learn`. Any stepper/visual shell for Learn needs an explicit SPEC-012 amendment (decision D-A below) |
| Tokens, type utilities, `AreaHeader`, `BasisPanel`, `SignalPathRail`, shared architecture state, evidence glyphs inside the existing `EvidenceTag` (presentation props only) | SPEC-014 foundation PR | Signal Path supplies the design | Extends `EvidenceTag`; never forks it. Registry (`REFERENCES`) is additive only |
| `/system-map`, `/architecture`, `/sandbox`, home page | SPEC-014 | layout and type | Preservation inventory in §3; SPEC-014's union-of-states check (AC-4) is the gate; Sandbox keeps its no-clipping floor and every existing capability |
| `/industry`, Industry nav item, home Industry card | SPEC-013 | trace pattern as a design input | SPEC-013 flips the "(planned)" item and the home card; the foundation PR leaves it "(planned)". SPEC-013 consumes foundation components after they land |
| `DESIGN.md` | foundation PR | `DESIGN_MD_REVISIONS.md` | Reviewed text only, merged with the foundation PR |

## 2. Sequence (approved, D-B)

1. Close SPEC-012 / PR #9: final engineering and Human Visual QA gates, then explicit merge approval.
2. Signal Path foundation + SPEC-014 UX redesign from synchronized `main` (applies the approved `DESIGN_MD_REVISIONS.md`).
3. SPEC-013 Industry & Career on the approved foundation components; its research and design review continue in parallel now.
4. Four-stage Learn visual shell as a bounded SPEC-012 amendment after PR #9 merges (approved, D-A). Preserve the five cases, claims, backend behavior,
   disclosures and the prediction/reveal capability. The design-lab prototype is not feature-complete and is not the implementation.

Rules for every PR: do not ship `/design-lab` or the `SiteNav.tsx` bypass; preserve all current production capabilities (Sandbox scenarios, comparison, sensitivity
studies, timeline, scrubber, architecture interfaces, validation needs, evidence traceability); each PR is separately verified (tests, CI, Codex review, browser
evidence, Human Visual QA) and needs explicit human merge approval.

## 3. Production preservation inventory (must survive restyle)

- **Architecture Choices:** drivers with all five Blueprint questions; 7x3 cells with `how`, `harder`, `basis`, `refs`, evidence label (canonical text,
  including "Model output (simplified)") and the Sandbox link for model-output cells; conditional decisions with `unless`, `connects`, `informs`, basis and refs;
  boundary interfaces; validation needs by architecture; the full reference list with inspection notes and destinations; all five `DISCLOSURES` verbatim and visible on load.
- **Learn (SPEC-012):** five cases x eight parts; native details reveal for Predict (no state, no scoring); backend strings verbatim (`outcome_label`, `outcome_detail`,
  `recovery_label`, `dominant_stress_*`, `coverage`); no digits in static prose (R6, AC-4); two independent requests with per-request loading/error, static parts render
  with the backend down, rapid-switching guard (R13); disclosures `sim`, `block`, `illustrative` + D-L1..D-L3 verbatim.
  Stepper mapping if D-A is approved: Predict = parts 1-2; Discover = part 3 and 6a; Explain = parts 4-5; Apply = parts 6b, 7, 8. All steps reachable without gating.
- **Sandbox:** five scenarios, sweeps, comparison, scrubber, protection panels, schematic, request-generation guards, run snapshots, stale markers, Reset, finite-run
  null wording ("not settled before the run ends"), existing chart behavior or a sampling method that preserves extrema (see check below).
- **Industry (SPEC-013):** five featured sources, standards section, ten career priorities, read-date field, Eaton figures as enumerated.

## 4. Decisions

- **D-A (Learn shell): APPROVED** as above (bounded SPEC-012 amendment after PR #9 merges).
- **D-B (sequence): APPROVED** as above.

## 5. Gates for every PR

Approved spec with acceptance criteria; local lint, typecheck, build and repo tests; Codex review on the Mac (output preserved verbatim); CI reported separately;
desktop (1440) and mobile (390) captures; Human Visual QA; human merge approval.

## 6. Prototype fixes made after review (verified vs unverified)

Verified by script or test in this branch: decimation keeps global extrema and endpoints (`frontend/scripts/check-decimate.mts`, 7 PASS incl. the Codex
counterexample and live thermal-trip data); lint, typecheck and build clean; Learn static steps render with the API blocked and its live step shows its own error.
Not verified: real devices, other browsers, and screen-reader behavior beyond the roles and names added.
