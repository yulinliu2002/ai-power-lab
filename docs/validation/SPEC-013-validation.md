# SPEC-013 Validation Record: Industry & Career V1

**Spec:** `docs/specifications/SPEC-013-industry-career-v1.md` (v0.3, adopted 2026-10-21)
**Baseline:** `main` at `f2c46ae49cfa3682d9c9e488ec03b636c4b5101c` (merge of PR #10, SPEC-014).
**Status:** Local verification complete. Two independent Codex reviews are recorded in §6 (first: REQUEST CHANGES; closure: REQUEST CHANGES, no blockers, addressed in §6). **AC-17 Human Product Review: ACCEPT for V1 (2026-10-22, §7).** CI is reported separately on the PR.

## 1. Deviations and approved amendments

Items 1, 3 and 4 below were deviations in the first draft of this record and were approved by the Human Engineering Lead on 2026-10-22; `docs/specifications/SPEC-013-industry-career-v1.md` was amended accordingly (spec §16), so they are no longer open deviations.

1. **Eaton is page-local (spec §4.1 item 1, R17, AC-3, AC-10, AC-18; approved amendment).** `ArchitectureChoices.tsx` renders every registry entry, so an `EATON` registry entry would change `/architecture`. Eaton is held as `INDUSTRY_REFERENCES.EATON` in `industryCareerData.ts`; the shared registry, `EvidenceTag.tsx` and `ArchitectureChoices.tsx` are untouched. The Eaton evidence tag shows label and basis without a registry "Refs" link; citation, URL, page date and read date appear in the sheet details and the References section.
2. **OCP white paper not re-read (explicit evidence exception, spec §16 item 4).** The 2026-10-21 fetch failed. Its two claims carry section locators from the SPEC-011 audit and are marked `paraphrase-checked`, with no verbatim span; the page says so. `READ_LOG.OCPWP.readDate` is 2026-10-18. Codex confirmed both against the source.
3. **Gutters (approved amendment).** The page uses the shared 24 px value; AC-23 now requires at least 16 px.
4. **SiteNav comment (approved amendment).** The file-level comment was updated to match the live route.
5. **Source reads were through a text-fetch tool, not a browser.** Direct network access to the five hosts is blocked in the implementing container. The NVIDIA post, OCP post, OCP SST specification and Eaton page were read on 2026-10-21 and verbatim spans returned; the two HTML pages are text extractions. Codex checked the figures and claims against the live sources.
6. **OCP post URL.** The page read was `.../news/powering-the-next-era...`; the registry entry points at an older URL. The registry was not edited; the page links the URL actually read (`READ_LOG.OCP.readUrl`).
7. **Q1-Q4** were not answered explicitly; the spec's recommendations were followed.
8. **Check script location:** `frontend/app/lib/industryCareerCheck.ts` ("any check script", AC-10).

## 2. Verification evidence (local)

| Check | Result |
|---|---|
| `npm run typecheck` | pass |
| `npm run lint` | pass |
| `npm run build` | pass; `/industry` prerendered static |
| Content script (see the count below, after both review rounds: AC-2..AC-5, AC-7..AC-9, AC-14, AC-16, AC-19..AC-22, AC-25, R1, R10, R19, R20) | `ALL CHECKS PASSED` |
| Python suite `pytest -q` | 190 passed (no Python change in this diff) |
| AC-18 `/architecture` unchanged | Scope as amended (spec §16): `architectureChoicesData.ts`, `ArchitectureChoices.tsx`, `EvidenceTag.tsx` and its styles have no diff against `main`, so the page body and References list are unchanged. The shared nav changes on every page ("(planned)" removed from Industry & Career), so literal whole-page text identity cannot hold. No production-text before/after comparison was taken. |
| AC-23 viewport (real Chromium, Playwright) | 360 px: scrollWidth 360 = clientWidth 360; 1280 px: 1280 = 1280. Page gutters 24 px (the shared `.ic-page` value; AC-23 as amended requires at least 16 px) |
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
| 13 | EATON | Eaton lists a 15 kV class voltage. | Specifications table: Voltage class | "15 kV class" | supported |
| 14 | EATON | Eaton lists a 2 MW overall load power rating. | Specifications table: Overall load power rating | "2 MW" | supported |
| 15 | EATON | Eaton lists converter efficiency above 97% at 800 VDC output. | Specifications table: Converter efficiency | ">97% @ 800 VDC output" | supported |
| 16 | EATON | Eaton says the system is designed to support high-voltage DC systems, including emerging 800 VDC. | FAQ | "designed to support high-voltage DC systems, including emerging 800 VDC" | supported |
| 17 | EATON | Eaton lists the unit as having a hermetically sealed power section with liquid cooling. | Specifications table: Style | "Outdoor with hermetically sealed power section and liquid cooling" | supported |

**Assertions outside `claims`** (answers, "does not tell you", bases and notes), audited the same way. `absence-observed` rows are negative statements: the column states what was looked for.

| # | Sheet | Assertion | Locator | Verbatim span or check | Status |
|---|---|---|---|---|---|
| A1 | nvidia | The post is dated 11 August 2026. | Article byline | "August 11, 2026" | supported |
| A2 | nvidia | The article gives no efficiency percentage or measured benefit for 800 VDC. | Whole article | Searched the fetched article text for an efficiency percentage or measured 800 VDC benefit; none found. | absence-observed |
| A3 | nvidia | "Fewer" stages is not counted. | Article body, paragraph beginning "800 VDC simplifies that path" | The passage states "fewer conversion stages" without a number of stages. | absence-observed |
| A4 | ocp-blog | The post is signed by two NVIDIA Data Center Engineering authors. | Post byline | "Posted by Jason Adrian and Mike Tu, NVIDIA Data Center Engineering" | supported |
| A5 | ocp-blog | The post was posted on 11 August 2026. | Post header | "Date of Post August 11, 2026" | supported |
| A6 | ocp-blog | The page metadata gives a later modified date of 2026-09-24. | Page metadata: modified time | "2026-09-24" | supported |
| A7 | ocp-blog | The audited passages name two options but do not compare them on efficiency or cost. | Section "A Flexible Path Forward for Every Data Center" | Bounded to the passages audited here; no efficiency or cost comparison found in them. | absence-observed |
| A8 | ocp-whitepaper | The white paper is version 1.0, first release, dated 30 March 2026. | Registry citation for OCPWP (SPEC-011 audit) | none for this page | registry-citation |
| A9 | ocp-sst | The specification is Rev 0.3.0, effective 22 June 2026. | Cover page | "Specification Effective 6/22/2026" | supported |
| A10 | ocp-sst | The listed authors are Google, Microsoft and NVIDIA. | Cover page | "Author: Google, Microsoft, Nvidia" | supported |
| A11 | ocp-sst | Grounding detail is left to later revisions. | Section 5.4, page 15 | "Details will be provided in later revisions of the specification." | supported |
| A12 | eaton | The page's certification line concerns electric vehicle charging. | Certifications table | "certified by UL or equivalent NRTL for electric vehicle charging" | supported |
| A13 | eaton | The page's output rows describe passenger-vehicle charging connections. | Specifications table: DC output / DC charger circuit types | "Passenger vehicle configuration CCS or NACS (200-900V)" | supported |
| A14 | eaton | The footer says specifications are subject to change without notice. | Page footer | "Due to continuing improvements, specifications are subject to change without notice." | supported |
| A15 | eaton | The page shows no publication date. | Page metadata and body | Publish-date metadata empty; only a 2026 copyright footer found. | absence-observed |
| A16 | eaton | The efficiency row gives no load level, temperature or test method. | Specifications table: Converter efficiency | Row reads ">97% @ 800 VDC output" with no further conditions. | absence-observed |

Negative statements on the sheets ("does not tell you"), with their basis: NVIDIA gives no efficiency figure and no stage count (fetch report, and SPEC-011 audit); Eaton's efficiency row gives no load, temperature or method, its certification line concerns electric vehicle charging, no date and a "subject to change" footer (fetch report of the specification and certification tables); OCP SST TBD items (§4.3, §5.2.1(c), §5.4, fetch report). The OCP-post "does not compare the options" statement is limited to "the passages audited here".

## 4. Items observed in the sources

- NVIDIA post: printed date 11 August 2026 (the YAML's "2024-2025" is wrong); the post's current title differs from the registry citation.
- NVIDIA post text names the SST specification version as July 2026; the specification's cover says effective 22 June 2026 and its version history 20 May 2026. Not used on the page; noted for the reader of the sources.
- The OCP post is signed by two NVIDIA Data Center Engineering authors; the sheet says so.

## 5. Open acceptance criteria

| AC | State |
|---|---|
| AC-13 Codex implementation review | Recorded in §6; findings resolved by the 2026-10-22 amendments; a focused closure review is pending |
| AC-17 Human Product Review (side-by-side screenshots) | **Accepted for V1** by the Human Engineering Lead on 2026-10-22 (§7) |
| AC-18 | Met by unchanged inputs; no before/after text diff taken (see §2) |
| AC-19 | Met, with the approved exception (spec §16 item 4) for exactly two OCP white-paper claims, which have locators but no verbatim span. Claims and non-claim assertions are audited in §3, and the check fails any other claim without a span, and fails if the exception set is not exactly those two |
| Everything else | Met locally, per §2 |

## 6. Independent Codex review (AC-13)

Codex CLI 0.162.1, read-only, session `01a1612b-4083-7291-8aa5-cfeb48d392ef`, on head `084e006` against base `f2c46ae`. Verdict: **REQUEST CHANGES**, no blockers. Full verbatim output (269 KB) is held on the Lead's Mac in the scratchpad of the review session (`SPEC-013-codex-review.txt`); it is not committed. Codex also opened the OCP white paper and confirmed that §4.2 and §6.3.3 support the two paraphrases, and found the NVIDIA, OCP, OCP SST and Eaton claims faithful to their sources.

| # | Severity | Finding | Disposition |
|---|---|---|---|
| 1 | Major | Eaton provenance does not meet AC-3/R17 as written; the check asserted absence from the registry | **Resolved by approved amendment (2026-10-22).** Page-local Eaton kept; spec §4.1, R17, AC-3, AC-10 and AC-18 amended. The check asserts the amended contract |
| 2 | Major | AC-19 audit incomplete: white-paper row lacked support for the bypass assertion; Eaton row spans covered only efficiency; factual assertions in `answers`/`doesNotTell` lacked audit rows; check exempted `paraphrase-checked` | Eaton claim split into three rows with spans ("15 kV class", "2 MW", ">97% @ 800 VDC output"). The check now fails any claim without a span except the two OCP white-paper claims, kept as an explicit exception (Codex confirmed their support in the source; no verbatim span exists for this page). Non-claim assertions are listed below |
| 3 | Minor | AC-18 overstated | Wording corrected in §2 |
| 4 | Minor | Gutters 24 px, AC-23 says 16 px | Resolved by approved amendment: 16 px is the minimum, 24 px approved |
| 5 | Nit | SiteNav file comment changed beyond the `/industry` entry | Resolved by approved amendment: the corrected comment is kept |


### Closure review (head `b27db45`)

Codex CLI, read-only, session `01a1613c-b622-7b10-b601-f7dd237fb5a1`. Verdict: **REQUEST CHANGES**, no blockers. Resolved: Eaton contract, gutters, SiteNav comment and AC-18 scope. Verbatim output is held on the Lead's Mac (`SPEC-013-codex-closure-review.txt`, 187 KB); not committed.

| Severity | Finding | Disposition |
|---|---|---|
| Major | AC-19 audit still incomplete: assertions outside `claims` had prose only, and the status overstated compliance | Added a structured `ASSERTION_AUDIT` (16 rows: verbatim spans, or an explicit "absence observed" check, or a registry citation), validated by the content script and listed in §3. Status corrected |
| Minor | The span exception covered any `paraphrase-checked` OCP white-paper claim; a third unapproved claim passed | The check now identifies the exception by locator and fails unless exactly the two approved claims are exceptions |

A re-run of the closure review was not requested: the Lead asked for one focused closure review, not a further cycle.

## 7. AC-17 Human Product Review

Reviewer: the Human Engineering Lead, on the desktop (1280 px) and mobile (360 px) full-page screenshots of `/industry`, 2026-10-22. Assessment: **ACCEPT for V1**. In the reviewer's words: the page has a distinct role from Architecture Choices, an appropriate evidence-oriented content hierarchy, and an acceptable desktop and mobile layout for this release. The review was of the screenshots; this record does not add walkthrough observations.

Two non-blocking UX improvements are recorded as future work and are **not** implemented in this PR (SPEC-013 design scope is not reopened):
1. Improve Career Map discoverability and prominence.
2. Reduce repetitive card density and long-scroll reading friction on mobile.

### Minimal disposition (diff `b27db45..14fa343`)

Codex CLI, read-only, session `01a16164-adad-71c2-a9c5-c8666c10ff29`. Verdict: **not APPROVE**; one remaining defect: the modification date `2026-09-24` was marked supported with a span containing only the publication date (`ASSERTION_AUDIT`, and the matching row in §3). Codex gave no verdict on the two-claim exception. Resolution: the row is split into the post-date row (span `Date of Post August 11, 2026`) and a separate modified-date row (span `2026-09-24`, locator page metadata, modified time); the §3 table is regenerated from the script. Verbatim output is held on the Lead's Mac (`SPEC-013-codex-disposition.txt`); not committed. The fix has not yet been re-reviewed by Codex.
