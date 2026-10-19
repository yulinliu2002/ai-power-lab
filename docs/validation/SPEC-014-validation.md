# SPEC-014 Validation Record (implementation, in progress)

**Spec:** `docs/specifications/SPEC-014-product-ux-redesign.md` (v0.5)
**Synchronized base:** `main` at `f9cc8c4` (contains the SPEC-012 merge, PR #9). Branch `feature/spec-014-ux-redesign`.
**Status:** Local verification complete; Codex implementation review, CI and Human Visual QA pending. This record separates local results from CI and from review.

## Local results (scripts in `docs/validation/spec-014/`)

| Check | Result | Evidence |
|---|---|---|
| Python suite | 190 passed (baseline 190) | `pytest -q` |
| Frontend | `npm run lint`, `npm run typecheck`, `npm run build` pass | local |
| AC-6 console/network clean, both viewports | 0 problems after (baseline: 1 dev-only font request) | `after/compare.txt` |
| AC-7 API requests/responses | 24 unique (method, URL, body, response hash) identical to baseline; 40 vs 40 calls | `compare.py` |
| AC-4 / AC-9 test ids | Architecture: baseline union is a subset of after union (selected driver states plus both show-all views). Sandbox: only the three declared retirements (`view-mode-toggle`, `view-mode-option-single`, `view-mode-option-compare`) are missing | `compare.py` |
| AC-11 numbers unchanged | Every numeric token on the baseline Sandbox pages (5 scenarios, experiment run, sweep, comparison) is present after | `compare.py` |
| AC-3 decision cards | All 7 decision-card texts identical (case-normalized: labels were CSS-uppercase before) | `compare.py` |
| AC-8 / AC-10 state matrix | 27 checks pass: mount, scrubber default and Home/End, unrun/stale markers, provenance, failed Run and Reset (request aborted), Reset, sweep + stale, disabled-study fallback, rapid switching, Compare fetch on each entry, failure + retry, Stage 3 failure leaves other stages intact, stage-nav focus, outcome caution | `after/state_matrix.json` |
| AC-25 rail | SST node only in the conceptual SST architecture; accessible name lists the node sequence; `/sandbox` pinned, dashed simulated nodes, legend; compact at 390 | `after/verify_static.json` |
| AC-26 disclosures on load | All 5 SPEC-011 disclosures verbatim and visible on `/architecture` load; D-SIM on `/sandbox` (1440 and 390) | `after/verify_static.json` |
| AC-27 type | one `h1` per page, 40px desktop / 28px mobile, weight 600 on `/`, `/system-map`, `/architecture`, `/sandbox` | same |
| AC-16 accessibility | axe-core 4.10.2 (injected locally, not a repo dependency): no critical or serious violations on the four pages at both viewports; this includes color-contrast (AA) | same |
| AC-17 390px | page `scrollWidth` = 390 on all pages/states; every element inside the viewport or a named scroller; scrollers show a hint | same |
| AC-18 map arrows | per lane with arrows, nodes-1 arrows in all three views; monitoring lane unchanged | `after/verify_map.json` |
| AC-15 `/learn` | loads, five cases, no overflow at 375 and 1280, 0 console problems. Text diff vs baseline: only the chart-title casing (CSS uppercase removed), the shared footnote wording and the outcome caution | `after/learn_regression.json` |
| AC-24 | no `design-lab` path or string in the diff | `git diff --name-only` |

## Spec deviations and decisions made during implementation

- **R33 (System Map evidence labels) is split to SPEC-015.** The claim count in `infrastructureMapData.ts` is 43 lines with digits and 28 with units or voltage/time classes, above the 25-claim threshold, so per D-3 it is not implemented here.
- **Mobile nav:** at 390px the wordmark collapses to "APL" (accessible name "AI Power Lab home") so the nav fits in two lines (spec R30). For Human Visual QA.
- **DESIGN.md §7:** unit suffix color changed from `muted` to `text-secondary` (axe color-contrast finding); recorded in spec §17 F7.
- **Shared headings:** headings inside shared components also used by `/learn` (for example "PROTECTION TIMELINE", "SENSITIVITY STUDY") keep their existing uppercase style; only Sandbox-local headings use the new sentence-case tier.
- **Chart text size:** unchanged authored sizes (9.5px in a 600-unit viewBox); charts now have a minimum width of 600px in a named scroller, so rendered text is never below its authored size.
- **Legacy backend strings still on screen** (D-R): the outcome label "RODE THROUGH CLEANLY", the coordination sentence containing `RIDE_THROUGH`, and `src/…` file references inside backend-supplied protection-coverage text. They are verbatim backend output; a classification-neutral caution sits beside every outcome banner.
- Baseline screenshots are not committed (reproducible at the base commit); after-screenshots for Human Visual QA are delivered outside the repository.

## Pending

Codex implementation review (output to be recorded verbatim below), CI, Human Visual QA, explicit human merge approval.
