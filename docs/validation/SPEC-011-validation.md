# SPEC-011 — Architecture Choices V1 — Validation Record

## Context

- Spec: `docs/specifications/SPEC-011-architecture-choices-v1.md` (v0.3).
- **Gate status (recorded accurately).** The one bounded pre-implementation Codex closure review of v0.2 returned `CHANGES_REQUIRED` (0 blocking, 4 major). v0.3 applied those four fixes; Codex did **not** re-review v0.3. The Human Engineering Lead explicitly authorized implementation anyway (2026-10-18). This is a human-approved gate exception, **not a Codex PASS**. Codex's review of the implementation diff is recorded in the final section.
- Implementation scope: frontend-only `/architecture`; display-name updates in `infrastructureMapData.ts`; nav and home-card changes; approved documentation alignment. Mission and audience wording changes are **not** implemented (proposed separately in the PR).
- Verified on branch `feature/spec-011-architecture-choices`, cut from `main` at `8552a7a`.

## Automated verification (actual results)

| Check | Result |
|---|---|
| `python -m pytest -q` (scratch venv from `requirements.txt`) | 190 passed, 1 warning (httpx/starlette deprecation) |
| `npm run lint` | no output, exit 0 |
| `npm run typecheck` | passed (`next typegen && tsc --noEmit`) |
| `npm run build` | passed; routes `/`, `/architecture`, `/sandbox`, `/system-map` prerendered static |

`pytest` is regression evidence only; file-level preservation is shown by the inventory below.

## File inventory (independent of pytest)

`git status --short` at verification time: modified tracked — `AGENTS.md`, `PROJECT_CHARTER.md`, `README.md`, `docs/PRODUCT_BLUEPRINT.md`, SPEC-008/009/010, `frontend/app/components/SiteNav.tsx`, `frontend/app/lib/infrastructureMapData.ts`, `frontend/app/page.tsx`, `frontend/app/system-map/page.tsx`. New — `docs/specifications/SPEC-011-architecture-choices-v1.md`, this record, `frontend/app/architecture/page.tsx`, `frontend/app/components/DominantDriverSelector.tsx`, `frontend/app/components/EvidenceTag.tsx`, `frontend/app/lib/architectureChoicesData.ts`. Protected untracked and **not committed**: `docs/reboot/`, `docs/validation/SPEC-005-validation.md`.

- `git diff --name-only main -- src backend content data tests .github`: 0 files (AC-9).
- `git diff main -- frontend/package.json frontend/package-lock.json`: 0 lines (AC-9).
- Architecture ids: the only edits in `infrastructureMapData.ts` are the three `name:` strings (3 lines changed); no `id:` line changed (AC-10).

## Acceptance criteria

Mechanical checks were run by a throwaway script kept outside the repository (it imports the data module and `ARCHITECTURES`).

| AC | Evidence | Result |
|---|---|---|
| AC-1 | Build lists `/architecture`; `/architecture` returns 200; nav shows it as a link, active when on the page; home card links to it with status `available` (2 available, 2 planned remain); Learn by Example and Industry & Career still `(planned)` | Pass |
| AC-2 | 7 drivers, each with all five Blueprint §4 answers non-empty (script); rendered page has 7 driver cards; D-ILL present | Pass |
| AC-3 | 21 cells exist (also compile-time); all have `how`, `harder`, evidence label, `basis`; every non-`assumption` cell has ≥1 reference id that exists in `REFERENCES`; `model-output` only on `mv-to-800vdc` and cites SANDBOX. Digit scan: only tokens `800` (voltage class), `N+1`/`2N` (redundancy scheme names), `70`/`60364` (standard numbers), `v0.3` (OCP spec version). No performance figure. Cell label counts: 13 public-fact, 6 emerging, 1 model-output, 1 assumption; the 7 conditional decisions are all labeled assumption (illustrative preference). Structural conditions pass; **whether each cited reference actually supports its claim has not been independently verified** (limitation 2) | Structural pass; source support unverified |
| AC-4 | 5 boundaries × 3 architectures = 15; every `nodeIds` entry exists in the corresponding architecture's nodes (script) | Pass |
| AC-5 | 7 conditional decisions, one per driver; each has non-empty `favored`, `because`, ≥1 `unless`, `connects`, `informs`; in the browser, selecting each of the 7 drivers rendered exactly one card, `decision-card-<id>`, with one checked native radio | Pass |
| AC-6 | ≥4 validation items per architecture; every item has ≥1 evidence kind from the fixed set; 3 architecture cards render | Pass |
| AC-7 | The five disclosure strings were checked against rendered text of the production build (HTML-unescaped); all present verbatim | Pass |
| AC-8 | Data search for rank/score/best/winner/weight/optimal/superior/outperform: only the word "ranking" in six decision `basis` strings, each as "not a ranking". Disclosure strings: `rank` and `winner` appear only in D-NOWIN's negation, `better` only in D-SIM's negation. Semantic review: the "tends to favor" sets differ by driver (conventional AC for RD3, RD4, RD7; the two 800 VDC architectures for RD1 and RD6; AC-fed 800 VDC alone for RD5; all three for RD2), each carries `unless` conditions, and no cell or card asserts an overall best | Pass |
| AC-9 | See inventory | Pass |
| AC-10 | See inventory; System Map renders the three new display names, none of the old ones, and the Sandbox link | Pass |

## Content walkthrough (R3, R4, R6, R7)

- **R3 five questions.** Drivers: all five fields present and distinct (script). Conditional decisions: *what* = tends-to-favor statement; *why it matters* = `because`; *system connection* = `connects`; *constraints and trade-offs* = `unless`; *decision informed* = `informs`.
- **R4 sourcing.** Each cell's label is its weakest claim's category. Where a claim could not cite a public source it is either labeled `emerging` with an attributed source (OCP, NVIDIA) or `assumption` (RD3 SST cell; RD2 conditional decision; all 15 interface items; validation lists). Public-industry sources used are only those already in `data/industry/` with their verified dates; no vendor figure (for example, the Eaton product listing) is used.
- **Sandbox model-output.** The only `model-output` cell (RD2, SST) restates the Sandbox's own qualitative behavior (load step → bus sag depending on capacitance and SST response time) and links to `/sandbox`.
- **R6 vs. approved decisions.** No ranking, universal winner or numeric comparison; naming matches approved decision 5.

## Browser/runtime verification

Production build served with `next start`; Browser pane. `/architecture` rendered; no console errors; selector behavior as in AC-5; desktop width 1280 and mobile width 375 showed no horizontal overflow; DOM focus order is nav → in-page links → references → controls; after remediation the driver selector is a native radio group (arrow keys verified in the browser: ArrowRight ×2 moved selection RD1 → RD3), and all new links and controls carry the `focus-visible` outline treatment. Essential text uses `text-primary`/`text-secondary`; `text-muted` remains only on aria-hidden decorative bullets (browser check: 0 other `text-muted` elements with text in `main`). Contrast was not measured numerically; `DESIGN.md` §18 states those two tokens meet 4.5:1. The backend was not started because `/architecture` makes no API call; `/sandbox` and `/` returned 200 but their API-driven behavior was not exercised.

## Known limitations

1. **Gate exception.** v0.3 was not re-reviewed by Codex before implementation.
2. **Reference granularity.** Textbook and standard references are title-level, not page-level. Content claims were written from general engineering knowledge and matched to those references by the author; the sources were **not** independently opened or checked during this task. Independent verification of those claims is outstanding.
3. **Self-authored content.** The digit scan and field checks are mechanical; the semantic review of AC-8 and R4 is the author's, and is not independent evidence. Independent review is the Codex section below.
4. **No automated UI test** exists; browser verification was manual and not exhaustive (no screen-reader check, no numeric contrast measurement).
5. **No quantitative comparison** of any kind is made; none of this content is validated by the simulation, which covers only the SST slice.

## Source-to-claim audit (2026-10-18, requested before merge)

**Method.** The OCP article and the NVIDIA blog (dated 2026-08-11) were fetched and read. The OCP LVDC white paper v1.0 (30 March 2026, 155 pages) and the OCP SST specification Rev 0.3.0 (effective 2026-06-22, 24 pages) were downloaded, text-extracted and searched; the passages cited below were read, but the white paper was **not** read in full. The web fetcher summarized the two HTML pages, so quoted phrases from them are summary-level; the two PDFs were read from extracted text. Textbooks and standards (Mohan, Grainger, IEEE 493, IEEE 1584, Garzon, NFPA 70, IEC 60364) were **not opened** and are not claimed verified. A research-thread report (`research/power-architecture-research-report.md`) pointed to the primary OCP documents; its figures were not reused.

**Outcome.** Every cell that relied on a blog-level source or a bare textbook name was rewritten to say what the primary source actually says, with the source type shown (vendor statement, consortium document, textbook background, this site). Claims that only a textbook could support are labeled as a textbook principle whose reference was not inspected. Cell labels are now 13 public-fact, 7 emerging, 1 model-output (the RD3 SST cell moved from assumption to emerging once OCP documents supported it).

| Cell | Verified against | Result |
|---|---|---|
| RD1 conventional | OCP article: baseline is MV AC stepped down to 480 VAC feeding AC racks. Current-vs-voltage is a textbook principle | Narrowed; principle not inspected |
| RD1 AC-fed | NVIDIA blog and OCP white paper executive summary cite rising rack density. White paper §6.3.3: for a given power, a higher voltage class with correspondingly less conductor material can reduce relative cable losses and current (the paper's 350/700 V to 700/1400 V halving example is deliberately not reproduced); a bipolar arrangement with a midpoint conductor can reduce losses versus unipolar when loads are balanced | Supported; copper and percentage claims deliberately not used (NVIDIA blog page does not state them) |
| RD1 SST | NVIDIA blog: direct medium-voltage conversion only for a future facility-scale unit. SST spec history: "first draft" | Supported; the blog does not say whether an SST is required, consistent with D-SST |
| RD2 conventional | Textbook UPS topology only | Labeled principle, reference not inspected |
| RD2 AC-fed | White paper §2.2 examines energy-storage integration; ½CV² is a principle | Supported / principle |
| RD3 conventional | White paper §4.2: N+1 power blocks and maintenance bypass | Supported |
| RD3 AC-fed | White paper §4.2: no UPS maintenance bypass in DC distribution; availability strategies "require further investigation" | Supported. Note: the white paper also cites earlier DC installations (a 2012 DC data center, factories); this page makes no operating-experience claim either way |
| RD3 SST | SST spec Appendix A redundancy figures; §5.2.1(c) marks voltage levels for seamless redundancy design TBD; white paper live-swap sub-blocks | Supported; **originally unsupported assumption, now sourced** |
| RD4 conventional | White paper §7.2.2 (selectivity): time-current selectivity is the most widespread method and its delays can mean long arcing time in an arc flash; NFPA 70 and IEC 60364 are cited elsewhere in the paper. The white paper's numeric delay range was removed from the cell | Supported; the zero-crossing statement is a textbook principle not inspected |
| RD4 AC-fed | White paper §7.2 (no standard or recognized practice for coordinating protection for the converter-fed DC fault behavior it describes, in particular the capacitor-discharge peak) and §7.6 (no DC equivalent of IEEE 1584 for incident energy). OCP article: engagement with UL Solutions, NFPA, IEEE, IEC | Supported |
| RD4 SST | White paper converter classification (HF transformer isolation), fault-limiting converters; SST spec TBD short-circuit duration | Supported |
| RD5 conventional | Series efficiency is a principle; OCP article on removing AC conversion stages | Supported / principle |
| RD5 AC-fed | NVIDIA blog: "fewer" stages, no count or efficiency number; white paper §2.2: "potential reduction", gains site-specific; OCP article: side-rack still converts AC to DC | Supported; wording hedged to match |
| RD5 SST | SST spec §3 and §4.1: replaces transformer, rectifier and (as required) storage; §4.1 lists five product components (power conversion, MVAC input, LVDC output, firmware/control, auxiliary power) | Supported. The black-box specification does not state a conversion-stage count, and its component list is not a stage count; "internally multi-stage" in D-BLOCK rests on this site's own Learn content and general engineering, not an OCP statement |
| RD6 conventional | Conductor sizing principle | Principle, not inspected |
| RD6 AC-fed | White paper §2.2 examines conductor utilization, gains site-specific | Supported / principle |
| RD6 SST | SST spec §3 states a design target of higher power density | Reworded as a target, not a measured result ("superior" removed) |
| RD7 conventional | White paper executive summary; NFPA 70 and IEC 60364 as cited there | Supported; "mature supply chain" claim removed |
| RD7 AC-fed | OCP article: workstream, side-rack and direct options, safety-organization engagement | Supported; adoption-count claims in the article deliberately not used |
| RD7 SST | SST spec history ("first draft"), scope (black box, interfaces), TBD items | Supported |

**Dropped or narrowed on audit.** "MFT provides galvanic isolation" now cites the white paper's converter classification instead of a textbook; "capacity growth raises arc-flash energy" had already been corrected; no copper, efficiency, cost or TCO figure from any vendor is used; the OCP article's "80 partners" statement is not used.

**Remaining limitations.** The white paper's sections outside those cited were not read. A textbook-only claim remains in RD2 conventional, RD6 conventional, parts of RD1/RD4/RD5 and the transformer size–frequency relation; each shows "not inspected". The earlier 100–200 ms figure was removed, so no AC-3 deviation remains; the digit scan now shows only voltage classes, scheme names, standard numbers, version and date numbers, and the OCP white-paper section number §6.3.3 cited in RD1. Codex had flagged that an attributed external figure (the 350/700 V to 700/1400 V example) might not satisfy AC-3's "cited repository source" wording; it was removed rather than escalated.

## Appendix: reproducible check commands and output

```
python -m pytest -q                      -> 190 passed, 1 warning
cd frontend && npm run lint              -> exit 0, no findings
cd frontend && npm run typecheck         -> passed
cd frontend && npm run build             -> compiled; /architecture prerendered
node check.mts   (throwaway script outside the repo; imports architectureChoicesData.ts and infrastructureMapData.ts)
git status --short; git diff --name-only main -- src backend content data tests .github   -> 0 files
git diff main -- frontend/package.json frontend/package-lock.json                          -> 0 lines
```

`check.mts` output (final run, after the source audit):

```
AC-8 term hits in data: ["ranking","ranking","ranking","ranking","ranking","ranking"]
disclosure term hits (expected rank+winner in D-NOWIN; 'better' in D-SIM negation): ["better","rank","winner"]
evidence labels: {"public-fact":13,"emerging":7,"model-output":1}
digit-bearing tokens in cells:
rd1/conventional-ac: 480
rd1/ac-to-800vdc: (§6.3.3)
rd1/mv-to-800vdc: 800 | 0.3.0)
rd2/mv-to-800vdc: 800
rd3/conventional-ac: N+1 | N+1 | 2N
rd3/ac-to-800vdc: N+1 | 800
rd4/conventional-ac: 70 | 60364),
rd4/ac-to-800vdc: 800 | 1584
rd5/ac-to-800vdc: 800
rd7/conventional-ac: 70 | 60364,
rd7/ac-to-800vdc: 800 | medium-voltage-to-800
rd7/mv-to-800vdc: 0.3.0, | 22 | 2026)
ALL MECHANICAL CHECKS PASS (cells=21, interfaces=15)
```

The script's assertions: 7 drivers with five non-empty answers; 21 cells with fields, references and model-output scope; 5×3 interfaces with node ids present in each architecture; 7 conditional decisions with non-empty `favored`, `because`, ≥1 `unless`; ≥4 validation items per architecture with kinds from the fixed set; term search for AC-8. It is not committed (SPEC-011 Verification Plan: throwaway script).

## Independent Codex review of the implementation

**Round 1 (Codex CLI, read-only, full diff + this record): `CHANGES_REQUIRED` — 0 blocking, 5 major, 2 minor.** Prior closure findings: (1) sourcing PARTIAL, (2) verification plan RESOLVED, (3) scope inventory RESOLVED, (4) ROI statements RESOLVED. Findings and bounded remediation:

| # | Sev | Finding | Remediation |
|---|---|---|---|
| 1 | Major | "Lower current at higher voltage" ignored phases/power factor; at 480 V three-phase AC, line current can be comparable | Cells RD1/RD6 and decisions reworded to state the comparison basis and that the benefit depends on AC voltage, phase and DC arrangement |
| 2 | Major | "Capacity growth raises arc-flash energy" not generally true | Reworded: incident energy depends on fault current and clearing time together and must be reassessed |
| 3 | Major | RD5 favored the SST while the SST cell says stages are repackaged; "losses multiply" | RD5 now favors AC-fed 800 VDC only, states SST is internally multi-stage, says efficiencies multiply, adds "functional blocks are not physical stages" |
| 4 | Major | "Least settled of the three" unsupported; conditional preferences labeled public-fact | Superlative removed; all 7 conditional decisions relabeled Illustrative assumption with context references |
| 5 | Major | `text-muted` used for essential text, contrary to `DESIGN.md` | Replaced with `text-secondary`/`text-primary`; muted kept only for decorative bullets |
| 6 | Minor | Custom radios lacked arrow-key navigation; new links lacked focus treatment | Native radio inputs; focus-visible classes added |
| 7 | Minor | Validation record overstated verification and lacked logs | Pass claims narrowed (AC-3 source support unverified); commands and output appended |

Codex also noted it could not independently confirm the pytest, build and browser runs from the artifacts alone; the commands above reproduce them.

**Round 2 (targeted re-review of the seven findings): `PASS` — no unresolved blocking or major findings.** Findings 1–6 RESOLVED; finding 7 PARTIAL because AC-8's summary still said RD5 favored both DC architectures; corrected in this record (RD5 favors AC-fed 800 VDC alone). Codex reported no new major technical, labeling, ranking/winner or `DESIGN.md` issues, and confirmed scope remained frontend implementation plus approved documentation alignment. Codex did not rerun the recorded test and browser checks itself.

**Overall independent-review status.** The pre-implementation spec gate was a human-approved exception (no Codex PASS on v0.3). The implementation was reviewed in two rounds and ended at Codex `PASS` for the remediation. Source support for the cited textbook and standard references remains unverified by anyone (limitation 2); Codex reviewed technical reasonableness and labeling, not the cited texts.


### Source-audit review (Codex, bounded)

- **Audit round 1: `CHANGES_REQUIRED`** (3 major, 2 minor), all valid: the RD1 voltage-class/bipolar loss statement omitted the conditions in white paper §6.3.3 (and the validation record cited §6.3.4 instead of §6.3.3); the RD4 conditional-decision basis broadened the white paper's statement about DC fault coordination; a numeric 100–200 ms selectivity delay conflicted with SPEC-011 AC-3; the RD3 SST cell said "redundancy levels" are TBD where the specification marks voltage levels for seamless redundancy TBD; the record said SST §4.1 had four components (it has five) and implied components equal stage count. All were corrected.
- **Audit round 2 (targeted closure): `CHANGES_REQUIRED`**, one medium item: the RD1 attributed example figures (350/700 V to 700/1400 V) might not satisfy AC-3's "cited repository source" wording. The four other corrections were confirmed. Rather than request a spec decision, the figures were removed (RD1 now describes the effect qualitatively with the §6.3.3 citation); this last edit only deletes numbers and was **not** re-reviewed by Codex. Treat the source audit as: all material findings fixed; final wording not re-reviewed.
- Codex checked against the extracted PDF text and the live OCP article and NVIDIA blog; it did not review the textbooks, PDF diagrams, browser rendering or CI.
