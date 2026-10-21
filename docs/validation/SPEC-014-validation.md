# SPEC-014 Validation Record (implementation, in progress; includes the Instrument Console art-direction integration)

**Spec:** `docs/specifications/SPEC-014-product-ux-redesign.md` (v0.5)
**Synchronized base:** `main` at `f9cc8c4` (contains the SPEC-012 merge, PR #9). Branch `feature/spec-014-ux-redesign`.
**Status:** Local verification complete. Human Visual QA approved by the Human Engineering Lead (2026-10-21) for System Map, Architecture Choices and Advanced Sandbox. Final Codex closure review: APPROVE (see below). CI is reported separately and was green on the final head. Merge approval is pending (explicit Human approval required). This record separates local results from CI and from review.

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
| AC-13 Stage 4 contract | outcome/detail/recovery/coordination strings equal the API response verbatim; lowest V_dc, energy deficit and recovery time equal the values parsed from the Engineering Result tiles, and the recovery time equals an independent recomputation from the API series; no derived numbers for scenarios B-E | `verify_extended.py` |
| AC-23 Appendix A exact strings | A1-A3, A5-A9, A13, A14 rendered verbatim (parsed from the spec); A10, A11 verbatim in the B-E state | `verify_extended.py` |
| AC-8/AC-10 state matrix | 27 checks plus extended: scrubber default equals the actual post-event V_dc minimum, sweep retained across study switches, both sweep parameters, in-flight sweep discarded on scenario change, a slow Run Experiment response never overwrites a later scenario selection, keyboard-only operation (Enter/Space/arrows), real Tab-key traversal reaching every control and every named scroller, a visible focus indicator on every focused control, Architecture chooser/show-all/rail selector by keyboard, stage-nav `aria-current` and heading focus, disabled-sweep reason, Compare fetch on each entry, failure and retry | `state_matrix.py`, `verify_extended.py` |
| AC-16 accessibility | axe-core: no critical/serious violations on the four pages at both viewports, and with populated sweep results and the Compare table (desktop) | `verify_static.py`, `verify_extended.py` |
| AC-17 390px | page `scrollWidth` 390 everywhere; in populated states (sweep results, Compare table, Architecture show-all) every element is inside the viewport or a named scroller and every scroller shows a hint | `verify_extended.py` |
| AC-18 map arrows | per lane nodes-1 arrows (monitoring lane unchanged) in all three views | `verify_map.py` |
| AC-25 rail | node labels equal the canonical `main`-lane labels parsed from `infrastructureMapData.ts` for all three architectures; SST only in the conceptual architecture; Sandbox rail pinned with dashed nodes, legend and unmodeled-stage statement | `verify_extended.py`, `verify_static.py` |
| AC-26 disclosures on load | all five SPEC-011 disclosures verbatim and visible on `/architecture` load; D-SIM on `/sandbox` (1440 and 390) | `verify_static.py` |
| AC-27 type | one `h1`, 40px desktop / 28px mobile, weight 600 on four pages; axe color-contrast (AA) clean | `verify_static.py` |
| AC-15/AC-28 `/learn` | five cases: text identical except the authorized caution, footnote and chart-title casing; links identical; chart polylines identical; default `EvidenceTag` HTML byte-identical; no overflow or console problems at 375 and 1280 | `compare_rich.py`, `learn_regression.py` |
| AC-24 | no `design-lab` path or string in the diff | `git diff --name-only` |

CI (GitHub Actions, first push): Frontend (lint, typecheck, build) and Python (engine, API, parity) passed on both runs.


## Instrument Console integration (spec §18) — local results

Composition and styling were integrated into the production components after the Human visual review (2026-10-20); behavior, data modules and testids are unchanged. All earlier suites were re-run against the new composition and pass (`after/*.json`, `after/compare.txt`): API requests/responses identical, baseline numbers and chart geometry preserved, line-level Architecture preservation (layout-aware: headings may move or merge, content may not), five Learn cases, 27-step state matrix, extended keyboard/Tab/axe/390px checks, rail labels vs canonical data, `/learn` regression. New checks in `verify_art.py` (`after/verify_art.json`):

| Condition | Result |
|---|---|
| 1 "Tends to favor" conditional | for every requirement the marked columns equal the data's `favored` set (at least one requirement marks several); legend, accessible chip text and decision band carry the conditional wording; no ranking/score/winner/best language outside the negating sentences (desktop and 390px) |
| 2 live values synchronized | hero V_dc, P_load and P_sst equal the displayed run at the scrubber sample (default, Home, End, after a new Run Experiment, Grid Sag); Reference, Minimum in run (Load Step only) and Final (end of run) are labeled and equal the run's values; no derived minimum for non-Load-Step scenarios |
| 4 chart scrolling | no scroll hint at 1440px on the Sandbox (Load Step); named, hinted scrollers remain at 390px |
| 5 System Map topology | desktop: topology starts above 760px, is wider than 1100px, all main-path nodes visible without scrolling in all three views |

Deviations: the Architecture decision board does not repeat the per-column mini power paths (the rail above carries the path); the System Map keeps the compact rail above the topology; the "Tends to favor" bar/chip is white (`text-primary`), not an accent or status color; DESIGN.md gains §23 (composition rules, no new tokens). Screenshots are delivered outside the repository.

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

### Codex closure review of the fixes (session 01a152a5-3474-7042-8c83-416ed7ea496e)

Verdict: **CHANGES_REQUIRED**, no new blocking or major implementation regression. Findings 1, 2, 6, 8, 9, 10, 11 RESOLVED (verified in code); remaining items and their dispositions:

| Codex item | Disposition |
|---|---|
| 3 PARTIAL: outcome and coordination detail prose still 11px | fixed: both are 12px Sans (shared components; `/learn` effect is size only, AC-15 text diff unchanged) |
| 4 PARTIAL: `state_matrix.py` could not re-enter Compare after the sweep option was disabled for B-E; keyboard checks used programmatic focus and omitted Architecture and visible focus; scroller reachability not proven | fixed: the Compare re-entry runs on Load Step (and asserts the sweep study is selectable); `verify_extended.py` now drives real Tab traversal, checks every named scroller is reached and every focused control shows an outline, and operates the Architecture chooser, show-all, rail selector and stage nav by keyboard |
| 5 PARTIAL: Stage 4 derived numbers compared against numbers taken from the takeaway itself; recovery value not checked; Learn disclosures/reference links not exercised; raw rich captures not in HEAD | fixed: values parsed from the Engineering Result tiles, recovery recomputed independently from the API series, Learn in-page reference links resolved and disclosure panel checked; the 60MB capture files are intentionally not committed (README) |
| 7 MINOR: `aria-current` unset before the first intersection | fixed: initial stage is current; scripted check |



## Spec deviations and decisions made during implementation

- **R33 (System Map evidence labels) is split to SPEC-015.** The claim count in `infrastructureMapData.ts` is 43 lines with digits and 28 with units or voltage/time classes, above the 25-claim threshold, so per D-3 it is not implemented here.
- **Mobile nav:** at 390px the wordmark collapses to "APL" (accessible name "AI Power Lab home") so the nav fits in two lines (spec R30). For Human Visual QA.
- **DESIGN.md §7:** unit suffix color changed from `muted` to `text-secondary` (axe color-contrast finding); recorded in spec §17 F7.
- **Shared headings:** headings inside shared components also used by `/learn` (for example "PROTECTION TIMELINE", "SENSITIVITY STUDY") keep their existing uppercase style; only Sandbox-local headings use the new sentence-case tier.
- **Chart text size:** unchanged authored sizes (9.5px in a 600-unit viewBox); charts now have a minimum width of 600px in a named scroller, so rendered text is never below its authored size.
- **Legacy backend strings still on screen** (D-R): the outcome label "RODE THROUGH CLEANLY", the coordination sentence containing `RIDE_THROUGH`, and `src/…` file references inside backend-supplied protection-coverage text. They are verbatim backend output; a classification-neutral caution sits beside every outcome banner.
- Baseline screenshots are not committed (reproducible at the base commit); after-screenshots for Human Visual QA are delivered outside the repository.

## Pending

CI on the final push, Human Visual QA (AC-22 learner walkthrough), explicit human merge approval.

## Codex rounds on this branch (all sessions read-only; outputs summarized above)

1. Implementation review (01a15293-753f-7e31-81ab-dabd7a8d2c23): CHANGES_REQUIRED, 5 major, 6 minor; all addressed.
2. Closure review (01a152a5-3474-7042-8c83-416ed7ea496e): items 3, 4, 5, 7 partial; addressed (12px prose, corrected state matrix, real Tab/keyboard checks, tile-parsed Stage 4 values, aria-current default).
3. Narrow check (01a152b0-0ff4-7cd3-8d54-212e6a3e4ac4): item 3 still partial (Sandbox causal text, KPI and metric captions, comparison detail, error text) and one script that crashed before writing results; fixed and results regenerated.
4. Narrow check (01a152b8-3529-7922-a7ee-579194f1dde7): evidence for items 4 and 5 confirmed passing; remaining 11px prose lines (System Map taglines, protection coverage and timeline detail, sweep error) and a `d2` assertion gap fixed in the last commit. **No Codex verdict of APPROVE was obtained**: the last recorded verdict is CHANGES_REQUIRED for those lines, now fixed but not re-reviewed; the Human should treat the implementation review as open until a final read-only check or the Human's own review.

## Codex review of the Instrument Console integration (session 01a157c3-e978-7420-8d97-d81478566032)

First verdict: CHANGES_REQUIRED, 0 blocking, 4 major, 2 minor. Dispositions:

| # | Finding | Disposition |
|---|---|---|
| 1 MAJOR | stage nav could not focus the Compare heading and tracking went stale after driver changes | fixed: `#step-compare` contains its heading; `StageNav` re-observes on a key; `verify_art.py` clicks every stage link and checks the focused heading and `aria-current` by default, after a driver change and in show-all |
| 2 MAJOR | mobile evidence cells lost architecture identity; table semantics; favored chips hidden from assistive tech on mobile | fixed: evidence cells carry the architecture label on mobile, the board is a `table` with row/column headers, mobile favored chips are visible and exposed with the conditional text; checked in `verify_art.py` |
| 3 MAJOR | art pass reintroduced Mono headings and sub-12px explanatory text | fixed: headings, row labels, labels and captions are Sans (small Mono kept only for tags/units/values); explanatory captions 12px |
| 4 MAJOR | validation claims not substantiated (mobile a11y, swapped fields, System Map views 2-3, heading focus, "multiset" wording) | fixed: field-by-field P_load/P_sst/ΔP checks, per-view node counts and bounds (7, 7, 6), heading-focus across states, mobile accessibility check, wording corrected |
| 5 MINOR | selection styling used accent border, permanent white outline, 2px decorative left border | fixed: selection = surface tier plus `hairline-strong`; the keyboard outline is preserved; the detail panel uses a 1px separator; the favored bar is 2px |
| 6 MINOR | takeaway outcome announced twice; caution separated | fixed: one outcome value, the caution sits directly under it |

All suites re-run after these fixes pass (`after/*.json`).

### Closure check of those fixes (session 01a157d3-... narrow pass; summarized)

Codex's narrow check of the fixes found 1 and 6 resolved and 2, 3, 4, 5 partial. Remaining items addressed afterwards: the later duplicate proto CSS rules that re-applied Mono headings, 11px slider summaries and the mobile accent/`text-primary` border were removed; the architecture comparison drops its table roles below 960px (labeled cards there) instead of leaving a table with hidden headers; explanatory captions (power-balance legend, equations, sweep title, rail note, provenance, node-detail toggle) are 12px Sans (equations stay Mono per DESIGN.md); a new `verify_type.py` checks the rendered typography contract (headings Sans; prose of more than 40 characters Sans and at least 12px; equations exempt) on all four pages at both viewports including show-all, Compare and sweep states. All suites pass after these changes. The pass was not re-reviewed by Codex; the last recorded verdict is CHANGES_REQUIRED, now addressed.

### Final fixes after the narrow check (Codex session 01a157de-deb4-7440-b112-1d2390d0d97a)

That check resolved findings 2 and 5 and left two validation gaps. Addressed: `verify_type.py` no longer exempts headings, checks the visible text of every block-level prose element (so prose split by inline markup is covered) and evaluates the Compare table and the sweep results separately; `verify_art.py` now scrolls each stage to the top and asserts the expected `aria-current` stage (the requirement list and the board start at the same height by design, so the earlier of the two wins) in the default view, after a driver change and in show-all. The stricter tests found two real defects, both fixed: (1) activating "Identify the requirement" from far down the page scrolled to the wrong place because the sticky requirement list was the scroll target (the sticky behavior now lives on an inner wrapper); (2) the current-stage tracking now recomputes from the live DOM on scroll instead of observing elements that can be replaced. The same stricter typography test also moved protection and coverage list text, the interface node path, the power-balance legend and the engineering equations to 12px Sans (equations stay Mono). All suites pass after these changes. **No Codex APPROVE was obtained at any round**; the last recorded Codex verdict (CHANGES_REQUIRED) concerned the two validation gaps above, which are fixed but not re-reviewed.

## Final gates (2026-10-21)

- **Human Visual QA:** approved for all three pages by the Human Engineering Lead.
- **Final Codex closure review** (read-only, `codex exec`, session 01a15c5a-943c-70a3-acc2-e611081a978a) on head `6af0b0e2b12de4752e366747ce573967e91a3435`: **APPROVE**, no blocking or major findings; one minor (this record was stale about CI and Visual QA and described the superseded IntersectionObserver tracking), fixed by this update. Verbatim output is attached to the PR thread. Acceptance coverage per Codex: every non-human criterion has recorded passing evidence plus static verification; AC-22 (learner walkthrough) remains a human criterion.
- **CI** (GitHub Actions) was green on `6af0b0e`: Frontend (lint, typecheck, build) and Python (engine, API, parity), both runs. The commit that carries this update changes documentation only; its CI result is reported in the PR thread.
- The current-stage tracking in `StageNav.tsx` recomputes the current stage from the live DOM on scroll and resize (not an IntersectionObserver); earlier lines in this record describing the observer are superseded.
