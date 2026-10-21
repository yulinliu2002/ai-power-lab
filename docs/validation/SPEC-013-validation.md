# SPEC-013 Validation Record: Industry & Career V1

**Spec:** `docs/specifications/SPEC-013-industry-career-v1.md` (v0.3, adopted 2026-10-21)
**Baseline:** `main` at `f2c46ae49cfa3682d9c9e488ec03b636c4b5101c` (merge of PR #10, SPEC-014).
**Status:** Local verification complete. **Independent Codex implementation review: not yet run** (the Codex CLI is not available in the cloud container that implemented this; AC-13 is open). **AC-17 Human Product Review: awaiting.** CI is reported separately on the PR.

## 1. Deviations from the adopted spec (reported, not silently resolved)

1. **Eaton is not added to `REFERENCES` (spec §4.1 item 1, R17).** `ArchitectureChoices.tsx` renders every registry entry (`Object.values(REFERENCES)`), so the additive `EATON` entry would add a reference to `/architecture`, contradicting AC-18 ("text content identical"). The spec contains both rules. Eaton is held in `industryCareerData.ts` as a page-local `INDUSTRY_REFERENCES.EATON` and the shared registry, `EvidenceTag.tsx` and `ArchitectureChoices.tsx` are untouched. Consequence: the Eaton sheet's evidence tag shows label and basis without a registry "Refs" link; its citation is in the sheet details and in this page's References section. If the Lead prefers the spec's literal registry change, `/architecture` will gain one reference entry.
2. **OCP white paper not re-read (spec §4.1, AC-19).** The 2026-10-21 fetch of the white paper failed (server error from the fetch tool). Its two claims carry section locators from the SPEC-011 audit of 2026-10-18 and are marked `paraphrase-checked`, with no verbatim span; the page says so. `READ_LOG.OCPWP.readDate` is 2026-10-18, not today.
3. **Source reads were done through a text-fetch tool, not a browser.** Direct network access from the container to the five hosts is blocked by the environment's egress policy. A fetch agent read the NVIDIA post, the OCP post, the OCP SST specification and the Eaton page on 2026-10-21 and returned verbatim spans. The two HTML pages are text extractions; a human spot-check of the quotations against the live pages is recommended.
4. **OCP post URL.** The page read was `.../news/powering-the-next-era...`; the registry entry points at an older `.../index.php/blog/...` URL. The registry was not edited (AC-10); the page links the URL actually read (`READ_LOG.OCP.readUrl`).
5. **Q1-Q4 were not answered explicitly**; the spec's recommendations were followed (see the spec status line).
6. **SiteNav comment** was updated to match the live route (the only edit beyond the `/industry` entry); the home page's file-level comment still says the implemented destinations are fewer than four (outside the Industry card, so left alone per R10).
7. **Check script location.** The content script is `frontend/app/lib/industryCareerCheck.ts` ("any check script", AC-10).

## 2. Verification evidence (local)

| Check | Result |
|---|---|
| `npm run typecheck` | pass |
| `npm run lint` | pass |
| `npm run build` | pass; `/industry` prerendered static |
| Content script (58 checks: AC-2..AC-5, AC-7..AC-9, AC-14, AC-16, AC-19..AC-22, AC-25, R1, R10, R19, R20) | `ALL CHECKS PASSED` |
| Python suite `pytest -q` | 190 passed (no Python change in this diff) |
| AC-18 `/architecture` unchanged | `architectureChoicesData.ts`, `ArchitectureChoices.tsx`, `EvidenceTag.tsx` have no diff against `main`; the page's inputs are identical, so its output is. No before/after text diff was taken. |
| AC-23 viewport (real Chromium, Playwright) | 360 px: scrollWidth 360 = clientWidth 360; 1280 px: 1280 = 1280. Page gutters 24 px |
| AC-15 default view | 5 claim sheets, 5 `<details>`, 0 open on load |
| AC-24 accessibility | native `<details>/<summary>` (opened by keyboard Enter on the focused summary); question chips are buttons with `aria-pressed`; "Compare with the source" disabled until a question is picked; 85 Tab stops, none without a focus outline; one `h1`, no skipped heading levels. No automated accessibility checker was run (none available without a new dependency) |
| AC-12 screenshots | in the project files folder `industry-spec013/`: fold, full page and expanded Eaton sheet at 360 and 1280 px |

Commands: `cd frontend && npm run typecheck && npm run lint && npm run build`; content script compiled with `npx tsc --module commonjs --moduleResolution node --target es2020 --skipLibCheck --esModuleInterop --strict --outDir <out> --rootDir app app/lib/industryCareerCheck.ts` then `node <out>/lib/industryCareerCheck.js . [--audit]`.

Limits of this evidence: the content script checks structure, provenance, wording lists and link targets. It does not check that a paraphrase is faithful to a source; that is the audit below plus the independent review. Negative statements ("the page gives no load level") rest on what the fetch tool returned and were not checked in a browser.

## 3. Claim-to-passage audit (AC-19)

Auditor: implementer (not independent). `supported` = a verbatim span was extracted on the 2026-10-21 read; the Eaton FAQ span has its non-breaking hyphen normalised. `paraphrase-checked` = carried from the SPEC-011 audit. Generated by `--audit`.

| # | Source | Claim | Locator | Verbatim span | Status |
|---|---|---|---|---|---|
| 1 | NVIDIA | NVIDIA says distributing power as direct current at higher voltage puts fewer conversion stages between the grid and the accelerator. | Article body, paragraph beginning "800 VDC simplifies that path" | "fewer conversion stages stand between the grid and the accelerator" | supported |
| 2 | NVIDIA | NVIDIA describes a hybrid path that it says is designed to fit into existing AC infrastructure and deliver 800 VDC to compute racks within the row. | Article body, hybrid-path passage | "designed to slot into existing AC infrastructure and deliver 800 VDC to compute racks within the row" | supported |
| 3 | OCP | The post describes a dedicated side power rack that converts existing 480 VAC to DC locally, next to the compute racks. | Section "A Flexible Path Forward for Every Data Center", option A | "A dedicated side power rack converts existing 480 VAC to either +/-400 or 0-800 VDC locally" | supported |
| 4 | OCP | The post describes direct medium-voltage-AC-to-800 VDC conversion, using transformer rectifiers or solid-state transformer skids. | Section "A Flexible Path Forward for Every Data Center", option B | "transformer rectifiers or solid-state transformer skids to convert MVAC directly to 800 VDC" | supported |
| 5 | OCP | The post says the authors are engaging with UL Solutions, NFPA, IEEE and IEC. | Section "What We Are Building Together at OCP" | "We are engaging in parallel with UL Solutions, NFPA, IEEE, and IEC" | supported |
| 6 | OCP | The post says higher-voltage DC distribution can move more power with less conductor than lower-voltage alternatives. | Section "A Shared Problem Demands a Shared Standard" | "move more power with less conductor/copper than lower-voltage alternatives" | supported |
| 7 | OCPWP | The paper says DC distribution does not allow a UPS maintenance-bypass strategy, and that strategies for availability in low-voltage DC data centers require further investigation. | White paper section 4.2 (SPEC-011 source audit, 2026-10-18) | "require further investigation" | paraphrase-checked |
| 8 | OCPWP | The paper says that, for a given power, a higher voltage class with correspondingly less conductor material can reduce relative cable losses and current. | White paper section 6.3.3 (SPEC-011 source audit, 2026-10-18) | none for this page | paraphrase-checked |
| 9 | OCPSST | The version history describes version 0.3 as the first draft of the SST product for the OCP community. | Version history, page 2 | "first draft of SST product for OCP community" | supported |
| 10 | OCPSST | The specification is titled as a medium-voltage-to-800 VDC power conversion platform. | Cover page, subtitle | "Medium Voltage to 800 VDC Power Conversion Platform" | supported |
| 11 | OCPSST | The specification marks voltage levels for seamless redundancy design as to be defined. | Section 5.2.1, item (c), page 14 | "(TBD, pending future definitions) voltage levels for seamless redundancy design" | supported |
| 12 | OCPSST | The specification says details of grounding will be provided in later revisions. | Section 5.4, page 15 | "Details will be provided in later revisions of the specification." | supported |
| 13 | EATON | Eaton lists a 15 kV class voltage, a 2 MW overall load power rating, and converter efficiency above 97% at 800 VDC output. | Specifications table: Voltage class; Overall load power rating; Converter efficiency | ">97% @ 800 VDC output" | supported |
| 14 | EATON | Eaton says the system is designed to support high-voltage DC systems, including emerging 800 VDC. | FAQ | "designed to support high-voltage DC systems, including emerging 800 VDC" | supported |
| 15 | EATON | Eaton lists the unit as having a hermetically sealed power section with liquid cooling. | Specifications table: Style | "Outdoor with hermetically sealed power section and liquid cooling" | supported |


Negative statements on the sheets ("does not tell you"), with their basis: NVIDIA gives no efficiency figure and no stage count (fetch report, and SPEC-011 audit); Eaton's efficiency row gives no load, temperature or method, its certification line concerns electric vehicle charging, no date and a "subject to change" footer (fetch report of the specification and certification tables); OCP SST TBD items (§4.3, §5.2.1(c), §5.4, fetch report). The OCP-post "does not compare the options" statement is limited to "the passages audited here".

## 4. Items observed in the sources

- NVIDIA post: printed date 11 August 2026 (the YAML's "2024-2025" is wrong); the post's current title differs from the registry citation.
- NVIDIA post text names the SST specification version as July 2026; the specification's cover says effective 22 June 2026 and its version history 20 May 2026. Not used on the page; noted for the reader of the sources.
- The OCP post is signed by two NVIDIA Data Center Engineering authors; the sheet says so.

## 5. Open acceptance criteria

| AC | State |
|---|---|
| AC-13 Codex implementation review | **Open.** Not run; no output to preserve |
| AC-17 Human Product Review (side-by-side screenshots) | **Open**, Human Product Lead only |
| AC-18 | Met by unchanged inputs; no before/after text diff taken (see §2) |
| AC-19 | Met except the verbatim-span requirement for the two OCP white-paper claims (deviation 2) |
| Everything else | Met locally, per §2 |
