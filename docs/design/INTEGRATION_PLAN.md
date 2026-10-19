# Signal Path: implementation plan (one page, revised after Codex review)

**Status (2026-10-19):** Signal Path approved; D-A and D-B approved by the Human Engineering Lead (below). Ownership rows: SPEC-012 **confirmed with additions**, SPEC-013 **confirmed with corrections** (both folded in below); SPEC-014 rows **pending**. The Mac-based Codex closure review of 653a03e is **pending**. Claude's fixes in 653a03e are not independently approved until that review returns.

**Principle.** `/design-lab` is a design reference, not a merge candidate and not a conforming implementation of any SPEC.
Production code is rebuilt from it in gated PRs that reuse existing data modules and components. No change to `src/`,
`backend/`, API shapes, thresholds or engineering claims. PR #9's branch and other threads' worktrees are not touched.
Note: the prototype itself touches one production file, `components/SiteNav.tsx` (3 lines that hide the old nav under
`/design-lab`); that line must not ship.

## 1. Ownership table (one source of scope)

Scope for SPEC-014 and SPEC-013 below is as reported by the Codex review of their current drafts (SPEC-014 §§5, 6, 11, AC-4, R2; SPEC-013
nav/home ownership). I have not read the SPEC-014 draft itself. SPEC-012 and SPEC-013 owners have confirmed their rows (below); the SPEC-014 owner has not yet.

| Area / file | Owner | Signal Path contribution | Rule |
|---|---|---|---|
| `/learn`, `learn/page.tsx`, `learnByExampleData.ts`, `LearnByExample.tsx`, `CaseSelector.tsx`, `docs/specifications/SPEC-012-learn-by-example-v1.md` and its validation record | SPEC-012 (PR #9) | none until PR #9 merges | PR #9 adds those files and edits only `SiteNav.tsx` and the home `page.tsx`; it touches no shared Sandbox component and does not edit `EvidenceTag` or `REFERENCES`. SPEC-014 draft excludes `/learn`. The four-stage shell is a bounded SPEC-012 amendment after the merge (D-A, approved) |
| Tokens, type utilities, `AreaHeader`, `BasisPanel`, `SignalPathRail`, shared architecture state, evidence glyphs inside the existing `EvidenceTag` (presentation props only) | SPEC-014 foundation PR | Signal Path supplies the design | Extends `EvidenceTag`; never forks it. Registry (`REFERENCES`) is additive only. **Default-preserving:** existing callers behave as today and the `#references` anchor still resolves (SPEC-013's `/industry` has its own `#references` section). `REFERENCES` stays additive-only and `ReferenceId` must not become exhaustively typed in a way that blocks adding an id (SPEC-013 adds `EATON`) |
| `/system-map`, `/architecture`, `/sandbox`, home page | SPEC-014 | layout and type | Preservation inventory in §3; SPEC-014's union-of-states check (AC-4) is the gate; Sandbox keeps its no-clipping floor and every existing capability |
| `/industry`, `industryCareerData.ts`, Industry nav item, home Industry card copy, additive `EATON` registry entry, Blueprint §7 row, adopted spec and validation files | SPEC-013 | trace pattern as a design input (typography and claim-to-evidence structure only) | SPEC-013 only removes `disabled` on the nav item and replaces (not just flips) the home card copy, since the current text promises developments "tracked over time". The foundation PR leaves the nav item "(planned)". `/industry` has no diagram, stage map or power-chain illustration (SPEC-013 E7), so `SignalPathRail` is not used there. SPEC-013 v0.3 limits reuse to `EvidenceTag` and tokens (R13); it will be amended to name the foundation components it may use (`AreaHeader`, `BasisPanel`, type utilities) once the foundation PR exists |
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
- **Learn (SPEC-012):** five cases x eight parts; the R16 claim checks and the validation record; native details reveal for Predict (no state, no scoring); backend strings verbatim (`outcome_label`, `outcome_detail`,
  `recovery_label`, `dominant_stress_*`, `coverage`); no digits in static prose (R6, AC-4); two independent requests with per-request loading/error, static parts render
  with the backend down, rapid-switching guard (R13); disclosures `sim`, `block`, `illustrative` + D-L1..D-L3 verbatim.
  Stepper mapping (D-A approved; confirmed by SPEC-012's owner): Predict = parts 1-2; Discover = part 3 and 6a; Explain = parts 4-5; Apply = parts 6b, 7, 8. All steps reachable without gating. The amendment must also fold in what changed after PR #9 was drafted: the sixteen accepted R16 claim kinds, the prediction-withheld headline, disclosure visibility, and the static-prose scan boundaries.
- **Sandbox:** five scenarios, sweeps, comparison, scrubber, protection panels, schematic, request-generation guards, run snapshots, stale markers, Reset, finite-run
  null wording ("not settled before the run ends"), existing chart behavior or a sampling method that preserves extrema (see check below).
- **Industry (SPEC-013):** five featured claim sheets (one per source), a "What this does not tell you" statement on each, the claim-to-passage audit, the exact seven-item standards list, ten Charter priorities with the ladder verbatim (including "Systems Architecture / Technical Leadership"), the `READ_LOG` read-date field, Eaton figures limited to the enumerated set, and the SST disclosures.

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
