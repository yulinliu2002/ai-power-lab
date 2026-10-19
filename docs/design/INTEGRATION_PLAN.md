# Signal Path: implementation plan (one page, revised after Codex review)

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

## 2. Sequence

1. SPEC-012 / PR #9 reviewed and merged as designed (prerequisite retained; captures re-baselined on the synchronized base).
2. Foundation + System Map + Architecture Choices + Sandbox restyle (SPEC-014). Rebases over PR #9 (`SiteNav`, `page.tsx`, `EvidenceTag` props).
3. Industry & Career V1 (SPEC-013, after its own CHANGES_REQUIRED findings are resolved), built on the foundation components.
4. Learn restyle only if D-A is approved, as a SPEC-012 amendment PR.

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

## 4. Decisions for Jason

- **D-A (Learn):** The prototype's stepper is presentation only (ungated, native reveal, backend-independent static steps), but SPEC-012 as drafted has a single
  page of eight ordered parts and SPEC-014 excludes `/learn`. Recommended: approve a small SPEC-012 amendment *after* PR #9 merges, adopting the four-step shell with
  the mapping above and no behavior change; otherwise Learn keeps SPEC-012's layout and takes only tokens, header, disclosure panel and rail.
- **D-B (sequence):** Recommended order is PR #9, then SPEC-014 foundation, then SPEC-013. If SPEC-013 must land first, it builds on existing components and SPEC-014 restyles it.

## 5. Gates for every PR

Approved spec with acceptance criteria; local lint, typecheck, build and repo tests; Codex review on the Mac (output preserved verbatim); CI reported separately;
desktop (1440) and mobile (390) captures; Human Visual QA; human merge approval.

## 6. Prototype fixes made after review (verified vs unverified)

Verified by script or test in this branch: decimation keeps global extrema and endpoints (`frontend/scripts/check-decimate.mts`, 7 PASS incl. the Codex
counterexample and live thermal-trip data); lint, typecheck and build clean; Learn static steps render with the API blocked and its live step shows its own error.
Not verified: real devices, other browsers, and screen-reader behavior beyond the roles and names added.
