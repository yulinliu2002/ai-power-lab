# SPEC-014 Validation Record (implementation, in progress)

**Spec:** `docs/specifications/SPEC-014-product-ux-redesign.md` (v0.5)
**Synchronized base:** `main` at `f9cc8c4` (contains the SPEC-012 merge, PR #9). Branch `feature/spec-014-ux-redesign`.
**Status:** Local verification complete and strengthened after the first Codex implementation review; closure review, Human Visual QA and merge approval pending. CI passed on the first push (reported separately below). This record separates local results from CI and from review.

## Local results (scripts and results in `docs/validation/spec-014/`)

Servers: baseline `f9cc8c4` worktree on :3200, branch on :3100, both against one backend on :8100 (isolated from other threads' servers). Chromium via Playwright; axe-core 4.10.2 injected from a local path (not a repository dependency).

| Check | Result | Evidence |
|---|---|---|
| Python suite | 190 passed (baseline 190) | `pytest -q` |
| Frontend | `npm run lint`, `npm run typecheck`, `npm run build` pass | local |
| AC-1 findings reproduced at the baseline | Q1-Q5, Q7-Q10, D1-D5, G1, G2 reproduced; **Q6 (Main Power Path arrows) did not reproduce** (all lanes have nodes-1 arrows at the baseline); reported to the Human, the arrow check is kept as a guard (AC-18) | `baseline/repro.json` |
| AC-17/18 findings re-measured on the branch | Q1-Q5, Q7-Q10, D1-D5, G2 fixed (Q8: one tick-label overlap at baseline, 0 after the stagger offset was increased) | `after/repro.json` |
| AC-6 console/network clean | 0 problems after (baseline: 1 dev-only font request) | `after/compare.txt` |
| AC-7 API requests/responses | identical per endpoint (JSON equality) and identical as (method, URL, body, response-hash) sets; 40 vs 40 calls | `compare.py`, `compare_rich.py` |
| AC-4 architecture preservation | every baseline **line** of every driver, comparison, boundary, decision and validation block, plus the reference list, present after (union over all seven driver selections and both show-all views); block ids equal; all five disclosures in the visible list | `compare_rich.py` (`after/compare_rich.json`) |
| AC-9 test ids | only the three declared retirements missing | `compare.py` |
| AC-11 numbers/chart inputs | every numeric token on baseline Sandbox states present; chart polyline geometry identical for all five scenarios; baseline chart tick/label texts all present | `compare.py`, `compare_rich.py` |
| AC-13 Stage 4 contract | outcome/detail/recovery/coordination strings equal the API response verbatim; derived Load Step values equal the Engineering Result tiles; no derived numbers for scenarios B-E | `verify_extended.py` |
| AC-23 Appendix A exact strings | A1-A3, A5-A9, A13, A14 rendered verbatim (parsed from the spec); A10, A11 verbatim in the B-E state | `verify_extended.py` |
| AC-8/AC-10 state matrix | 27 checks plus extended: scrubber default equals the actual post-event V_dc minimum, sweep retained across study switches, both sweep parameters, in-flight sweep discarded on scenario change, a slow Run Experiment response never overwrites a later scenario selection, keyboard-only operation (Enter/Space/arrows), disabled-sweep reason, Compare fetch on each entry, failure and retry | `state_matrix.py`, `verify_extended.py` |
| AC-16 accessibility | axe-core: no critical/serious violations on the four pages at both viewports, and with populated sweep results and the Compare table (desktop) | `verify_static.py`, `verify_extended.py` |
| AC-17 390px | page `scrollWidth` 390 everywhere; in populated states (sweep results, Compare table, Architecture show-all) every element is inside the viewport or a named scroller and every scroller shows a hint | `verify_extended.py` |
| AC-18 map arrows | per lane nodes-1 arrows (monitoring lane unchanged) in all three views | `verify_map.py` |
| AC-25 rail | node labels equal the canonical `main`-lane labels parsed from `infrastructureMapData.ts` for all three architectures; SST only in the conceptual architecture; Sandbox rail pinned with dashed nodes, legend and unmodeled-stage statement | `verify_extended.py`, `verify_static.py` |
| AC-26 disclosures on load | all five SPEC-011 disclosures verbatim and visible on `/architecture` load; D-SIM on `/sandbox` (1440 and 390) | `verify_static.py` |
| AC-27 type | one `h1`, 40px desktop / 28px mobile, weight 600 on four pages; axe color-contrast (AA) clean | `verify_static.py` |
| AC-15/AC-28 `/learn` | five cases: text identical except the authorized caution, footnote and chart-title casing; links identical; chart polylines identical; default `EvidenceTag` HTML byte-identical; no overflow or console problems at 375 and 1280 | `compare_rich.py`, `learn_regression.py` |
| AC-24 | no `design-lab` path or string in the diff | `git diff --name-only` |

CI (GitHub Actions, first push): Frontend (lint, typecheck, build) and Python (engine, API, parity) passed on both runs.

## Codex implementation review (verbatim summary of its output; session 01a15293-753f-7e31-81ab-dabd7a8d2c23)

Verdict on the first push: **CHANGES_REQUIRED** (0 blocking, 5 major, 6 minor). Dispositions:

| # | Finding | Disposition |
|---|---|---|
| 1 MAJOR | switching studies discarded sweep results | fixed: sweep stays mounted (hidden) across study switches; verified |
| 2 MAJOR | sweep chart/table not accessible scrollers, no sticky column | fixed: `ScrollRegion` for both, sticky first column; verified |
| 3 MAJOR | essential prose/labels still below contract | fixed in touched panels (Sans 12px basis prose via opt-in prop, 11px lists, secondary chart labels, glyph EvidenceTag 12px); `/learn` defaults preserved (AC-28) |
| 4 MAJOR | state/accessibility validation did not exercise the claimed matrix | fixed: `verify_extended.py` (delays, retention, both parameters, in-flight invalidation, actual minimum index, keyboard operation, populated-state axe and 390px checks) |
| 5 MAJOR | preservation and Learn checks incomplete | fixed: `capture_rich.py`/`compare_rich.py` (line-level architecture preservation, chart geometry, five Learn cases, EvidenceTag HTML, API JSON), rail labels vs canonical data, AC-13 and AC-28 checks |
| 6 MINOR | sweep option enabled for B-E | fixed: disabled with the reason visible |
| 7 MINOR | no `aria-current` on stage nav | fixed (IntersectionObserver + click) |
| 8 MINOR | Stage 4 provenance/fallbacks/labeling | fixed: provenance carries parameter values (preset and experiment), "not available" fallbacks, A13 moved to the "does not represent" block labeled as an assumption |
| 9 MINOR | Appendix A strings not exact | fixed: straight apostrophes, A9 period inside the link; exact comparison added |
| 10 MINOR | R28 System Map link missing | fixed: link on every interface card |
| 11 MINOR | DESIGN.md paraphrased Appendix B; home not using `AreaHeader`; SPEC-011 not amended | fixed: DESIGN.md text now verbatim Appendix B (plus the §7 unit line added to Appendix B), home uses `AreaHeader`, SPEC-011 scope items 2 and 5 amended |

A bounded Codex closure review of these fixes is recorded below once run.

## Spec deviations and decisions made during implementation

- **R33 (System Map evidence labels) is split to SPEC-015.** The claim count in `infrastructureMapData.ts` is 43 lines with digits and 28 with units or voltage/time classes, above the 25-claim threshold, so per D-3 it is not implemented here.
- **Mobile nav:** at 390px the wordmark collapses to "APL" (accessible name "AI Power Lab home") so the nav fits in two lines (spec R30). For Human Visual QA.
- **DESIGN.md §7:** unit suffix color changed from `muted` to `text-secondary` (axe color-contrast finding); recorded in spec §17 F7.
- **Shared headings:** headings inside shared components also used by `/learn` (for example "PROTECTION TIMELINE", "SENSITIVITY STUDY") keep their existing uppercase style; only Sandbox-local headings use the new sentence-case tier.
- **Chart text size:** unchanged authored sizes (9.5px in a 600-unit viewBox); charts now have a minimum width of 600px in a named scroller, so rendered text is never below its authored size.
- **Legacy backend strings still on screen** (D-R): the outcome label "RODE THROUGH CLEANLY", the coordination sentence containing `RIDE_THROUGH`, and `src/…` file references inside backend-supplied protection-coverage text. They are verbatim backend output; a classification-neutral caution sits beside every outcome banner.
- Baseline screenshots are not committed (reproducible at the base commit); after-screenshots for Human Visual QA are delivered outside the repository.

## Pending

Codex closure review of the fixes, CI on the fix push, Human Visual QA (AC-22 learner walkthrough), explicit human merge approval.
