# SPEC-013 — Industry & Career V1

**Status:** Adopted for implementation on `main` at `f2c46ae` (merge of PR #10) on the Human Engineering Lead's instruction of 2026-10-21 ("Proceed with SPEC-013 Industry & Career implementation"). Text below is draft v0.3 unchanged, apart from this status line. Codex reviewed v0.1 (CHANGES_REQUIRED); **v0.3 was not re-reviewed**; implementation deviations from v0.3 are recorded in `docs/validation/SPEC-013-validation.md`. Open questions Q1-Q4 (§13) were not answered explicitly; the implementation followed the spec's own recommendations (Q1 keep ecosystem cards, Q2 documented script and no new dependency, Q3 name the Charter ladder as a labelled activity description, Q4 five-source seed).
**Project:** AI Power Lab
**System:** `frontend/app/` (new `/industry` route and a typed content module). No change to `src/`, `backend/`, `config/`, `scenarios/`, `content/`, `data/`, `dashboard/` or `tests/`.
**Version:** 0.3
**Type:** Software Component (static content and presentation layer; no new engineering model)
**Prepared by:** Worker C, from `/mnt/project-files/research/industry-career-readiness.md` (the readiness analysis) and `origin/main` at `4e6af36`. The draft lives outside the repository until approved.
**Basis decisions (coordinator note, from the readiness analysis):** D1 frontend TypeScript module, YAML untouched. D2 Blueprint evidence labels only. D3 generic role activities only. D5 separate PR in parallel with SPEC-012. D6 sample records left for Phase B.
**Depends on:** none technical. Shares `SiteNav.tsx` and `page.tsx` with SPEC-012; see §12.

> **Reading note.** Repository facts were read from the cloud copy of `origin/main` at `4e6af36`. Source content (NVIDIA, OCP, Eaton) was **not** re-fetched for this draft: container egress to those hosts failed. Items marked **[RE-READ]** must be re-read from the live source by the implementer before the content is written, and the read date recorded.

---

## 1. Engineering Question

Given the public statements, specifications and product listings about 800 VDC and solid-state-transformer (SST) power for AI data centers, can a learner **say what each source actually claims, what kind of claim it is, how strong the evidence is, which part of the power chain it concerns**, and **where in this app they exercise the competencies a systems engineer needs**?

## 2. Motivation

- Industry & Career is one of the four product areas (Blueprint §3.1) and the only one with no route; `SiteNav.tsx` shows it as "(planned)".
- Existing industry data is Streamlit-only and rests on 3 distinct public sources across 9 records (7 verified, 2 sample). The repository has no career or role content (readiness analysis §2).
- The mission is to develop systems-level judgment; reading vendor, consortium and standards documents critically is part of that judgment.

## 3. Product ROI and Career ROI (Blueprint §6 gate)

- **Product ROI: met.** Completes the fourth navigable area. Lets a learner place public industry statements against the System Map and Architecture Choices and judge evidence strength. Capability: Observe → Explain.
- **Career ROI: met.** Exercises Charter §4 P2 items 8 and 9 (industry standards, real-world architecture patterns) and makes P0–P2 coverage across the whole app explicit. Competency: critical reading of vendor, consortium and standards documents; mapping learning to systems-engineering activities.
- If the Lead judges the Career ROI of the ecosystem section as only indirect, §4.2.1 may shrink to the standards section only (Q1).

## 4. Scope

One page, `/industry`, with three sections and a typed content module. Everything is static, presentation-only content.

### 4.1 Source set (five featured sources; no others)

Each of the five sources has **exactly one featured claim sheet** (§4.2.1). Other sections may *refer* to a source (an anchor link back to its sheet) but never render a second card for it.

| Id | Source | Kind | Provenance |
|---|---|---|---|
| `NVIDIA` | NVIDIA blog, 800 VDC power architecture for AI factories | vendor-statement | Existing `REFERENCES.NVIDIA`. **[RE-READ]** and reconcile the date: YAML says "2024-2025", SPEC-011 audit says page dated 2026-08-11. Show the page date and the read date. |
| `OCP` | OCP blog, Powering the Next Era of AI | consortium-document | Existing `REFERENCES.OCP`. |
| `OCPWP` | OCP LVDC power distribution white paper v1.0 (30 Mar 2026) | consortium-document | Existing `REFERENCES.OCPWP`; sections previously read are the only ones that may be cited. |
| `OCPSST` | OCP SST Specification Rev 0.3.0 (22 Jun 2026; first draft) | consortium-document | Existing `REFERENCES.OCPSST`. |
| `EATON` | Eaton medium-voltage SST catalog page | vendor-statement | New entry. **[RE-READ]**: it was not re-read in the SPEC-011 audit. Allowed figures are enumerated in §4.4. |

**Reference contract (single, binding).**
1. `architectureChoicesData.ts` receives **one additive change**: `"EATON"` is added to the `ReferenceId` union and one `REFERENCES.EATON` entry is added (kind `vendor-statement`, `inspection` text stating what was read, `citation`, `url`). No existing entry, type or export is edited or removed. The `/architecture` page must render unchanged (AC-18).
2. `EvidenceTag` is **not modified**. It links to `#references`; `/industry` provides its own `<section id="references">` listing every reference the page cites (as `/architecture` does), so the existing anchor resolves on this page.
3. **Read dates are a separate field, held in the industry module, not in `REFERENCES`.** `industryCareerData.ts` exports `READ_LOG: Record<IndustryRefId, { readDate: string; pageDate?: string }>`, where `readDate` is the date the implementer re-read the live source for *this* page and `pageDate` is the date printed on the source, if any. `verifiedDate` in `REFERENCES` (the 2026-10-04 YAML verification date) is neither reused nor edited. A missing `READ_LOG` entry is a test failure.
4. The page's References section shows, per reference: citation, kind, URL, `readDate`, and `pageDate` when present.

### 4.2 Page sections

**4.2.1 Claims to read** (replaces the v0.1 name "Industry Architecture Map"; see §4.3 E7). Five claim sheets, one per source (§4.1). Each sheet shows: what the source publicly says (a short, attributed paraphrase or quotation, each claim carrying a passage locator, see §4.5); source kind; evidence label; link; page date (if any) and read date; **"What this does not tell you"** (required); and a plain text link to the related System Map or Architecture Choices page. Two cards state the conceptual relation: the OCP material places the SST as a candidate for the MV-to-DC stage; an SST is not required for 800 VDC (Blueprint §5.2 rule 1).

**4.2.2 Standards and Specifications.** Two parts. (a) *In-repo sources:* the OCP white paper and SST spec, each with an explicit **draft / published** status line. (b) *Background standards to read next:* title-level entries only, flagged "not opened". The candidate list is limited to: NFPA 70 and IEC 60364 (cited by the OCP white paper per the SPEC-011 audit), IEEE 1547, UL 1741, IEC 62477-1, IEEE 493, IEEE 1584. Each entry states which interface or topic it relates to **only where a source already read in this repository says so**; otherwise it states the topic generically and is labelled `assumption`.

**4.2.3 Career Map.** A table over the ten Charter §4 priorities (P0 1–3, P1 4–6, P2 7–10). Per row: priority; **where the app exercises it** (link to `/system-map`, `/architecture`, `/sandbox`, and `/learn` if SPEC-012 has merged at implementation time) **or** an explicit "not yet exercised"; and one generic **role-activity** sentence. Below the table, a short "Systems-engineering activities" block mapping requirements, interface definition, trade study, verification and validation, and commissioning to the app areas that touch them, plus the Charter §2.2 ladder (Equipment / Controls Engineering → Systems Engineering → Senior Systems Engineering → Systems Architecture / Technical Leadership) as a labelled description of activities (not a hiring or market claim). The ladder text is quoted from Charter §2.2 and must include the final step exactly as written there: **"Systems Architecture / Technical Leadership"**.

Each section ends with a **"Questions to ask"** list (validation prompts for a learner reading a vendor or consortium document), for example: what load and temperature does a stated efficiency apply to; what test method; is this a draft; who has independently checked it.

### 4.3 Product role and experience (Product Role Contract)

**Role of this area:** *connect engineering knowledge to real-world industry and competencies.* The user job is **reading industry claims like an engineer, and seeing where each competency is practised**. It is a reading-and-judgment experience, not a monitoring, simulation or analysis one.

How it differs from the other four areas (Product Role Contract):

| Area | User job | This page must NOT do |
|---|---|---|
| System Map | explore structure, equipment, interfaces | rebuild maps or diagrams of the power chain |
| Architecture Choices | evaluate alternatives against requirements | rebuild the comparison matrix or trade tables |
| Learn by Example | understand physical cause and effect, guided | present scenarios, waveforms or cause-effect chains |
| Advanced Sandbox | free experiments, quantitative analysis | show KPIs, charts, telemetry or any model output |
| **Industry & Career** | **judge what a public claim supports; see which competency it exercises** | — |

Experience rules (presentation, no new framework):
- **E1 Claim-first layout.** The page is organized around *claims*, not dashboards: each source is a "claim sheet" with a large plain-language claim sentence, a one-line source/kind/label strip, and a **"Before you rely on it"** prompt. No charts, KPI tiles, telemetry components, or protection/audit panels anywhere on the page. Existing components reused: `EvidenceTag` and design tokens only.
- **E2 One light interaction: "What would you ask?"** On each claim sheet the learner first sees the claim, picks from a short fixed list which questions they would need answered before relying on it (for example: at what load and temperature, by what test method, is it a draft, who checked it), and then reveals what the source does and does not say. Client-side only, no persistence, no free parameters, no numeric input. This is a reading/judgment exercise, not an experiment; it is the page's only interactivity besides disclosure.
- **E3 Progressive disclosure.** Visible by default: the claim sentence, the kind/label strip, the prompt, and the competency it exercises. Behind "Details": the attributed quotation, page and read dates, full citation and URL, the "What this does not tell you" text, and assumptions. The evidence label stays visible (Blueprint 5.1); the URL and read date are one disclosure away but always present.
- **E4 Competency link instead of a company profile.** Each claim sheet ends with the Career Map competency it exercises (for example "reading a vendor efficiency figure" → verification and validation, Charter P2 item 10), linking to the corresponding Career Map row. The Career Map is the page's other main block and is a compact two-column "competency → where practised in the app / not yet practised" list, not a data table of metrics.
- **E5 Typography and contrast.** One claim sentence per sheet at heading scale; body text short (target at most about 40 words per visible block); secondary text meets the contrast already required by `DESIGN.md`; the label strip is neutral text, not status colour. No long technical prose blocks in the default view.
- **E7 No third architecture overview.** The page contains no diagram, stage map, power-chain illustration, per-architecture comparison table, or matrix of "which source supports which architecture". Relation to the System Map or Architecture Choices is expressed only as a sentence plus a text link. A source's claim is described in terms of *what it asserts and how strongly*, not by re-describing the architectures.
- **E6 Distinct vocabulary.** The page does not reuse Sandbox/Learn terms such as "scenario", "run", "telemetry", "KPI", "stress" or "ride-through" except in a link label to those areas.

### 4.4 Eaton figures (allowed set)

Only these statements, attributed ("Eaton lists…"), may appear, as recorded in `data/industry/products.yaml` and to be confirmed on the live page at **[RE-READ]**: 15 kV class input; 2 MW overall load power rating; >97% converter efficiency at 800 VDC output; explicit support for emerging 800 VDC architectures; liquid-cooled power section. **No other numerical or performance figure.** The recorded source text states no load point, temperature, or test method for the efficiency figure; unless the live page states them, the card says "conditions not stated on the page" in the "does not tell you" field. The card must not infer or imply a test standard, certification, field performance or deployment. If the live page differs from this list, the implementer reports the difference and stops for Lead decision rather than changing the allowed set.

### 4.5 Claim-to-passage audit

A URL and read date show where a claim came from, not that it is supported. Therefore:
- Every claim on a claim sheet carries a **passage locator** in the module: section heading, page number, or a quoted span of at most 25 words from the source.
- The PR includes an **audit table**: claim text, source id, locator, verbatim supporting span, auditor (implementer), and whether the claim is `supported` or `paraphrase-checked`. The Codex implementation review spot-checks it (AC-13).
- A claim-sheet claim that cannot be given a locator is **removed**; it is not downgraded to `assumption`. `assumption` is permitted only for non-claim content: Career Map role-activity sentences, generic notes on background standards, and the "Questions to ask" lists. Source claim sheets contain no `assumption`-labelled assertions about what a source says.

## 5. Out of Scope

Backend/API changes; any Python change; simulation or numerical change; edits to `data/industry/*.yaml`, `content/`, `dashboard/`, or any Streamlit change or retirement (Phase B); scraping, scheduled or "weekly" updates, live data; search, filter, sort; company rankings, "leaders", market share, adoption or timing claims; job-market, salary or hiring claims; role-matching; any ML; new vendors, papers or standards beyond §4; new dependencies; any change to SPEC-012 content or SPEC-014 work; any confidential or employer-derived information (CLAUDE.md Integrity Rules).

## 6. Model / Technical Basis

No engineering model. Reasoning content in a typed TypeScript module, following the SPEC-011 pattern.

- New file `frontend/app/lib/industryCareerData.ts`. Exports: the five-source record list, standards entries, Career Map rows, and "Questions to ask" lists.
- Evidence labels reuse the existing `EvidenceLabel` type and `EVIDENCE_LABEL_TEXT`: `public-fact`, `assumption`, `model-output`, `emerging`. `model-output` is not expected to be used on this page; its presence in any item must be justified in review.
- Source kinds reuse the existing four (`repository-source`, `textbook-standard`, `consortium-document`, `vendor-statement`).
- Each item carries **one** label (the label of its weakest claim) and, for `public-fact` and `emerging`, at least one reference with a URL and read date. Anything without a citable reference is `assumption`. This mirrors the SPEC-011 rule.
- Presentation reuses `EvidenceTag` and the existing design tokens; evidence tags stay neutral text, not status colours (DESIGN.md).
- Label assignment (initial, to be confirmed by the implementer against the live source): NVIDIA, Eaton statements → `public-fact` about *what the vendor says* (attributed), never about performance; OCP SST Rev 0.3.0 → `emerging` (first draft); OCP LVDC white paper → `emerging` for architecture direction, `public-fact` only for specific statements the sections read support; Career Map role-activity sentences and generic standards topic notes → `assumption`.
- Legacy YAML `status`/`maturity` are not shown. No `sample` record is read or rendered. The module may carry a one-line comment pointing at `data/industry/` as the pre-existing Streamlit-era record, so the two are not silently conflated.

## 7. Assumptions

- Content is illustrative teaching text built from public sources; nothing here is verified performance of any commercial equipment or field data.
- Source content is as read on the recorded read date; sources may change.
- Role-activity descriptions are generic educational assumptions, not descriptions of any employer or job posting.
- The Charter §4 priority list is the authoritative curriculum for the Career Map.

## 8. Requirements

- **R1** Route `/industry` renders the three sections in §4.2 and the "Questions to ask" lists.
- **R2** Exactly the five sources in §4.1, each with exactly one claim sheet. The standards section (4.2.2) may list the OCP white paper and OCP SST spec only as status rows that link back to their claim sheets, not as second cards.
- **R3** Every item has exactly one evidence label; `public-fact`/`emerging` items cite a reference with URL and read date.
- **R4** The OCP SST item is labelled `emerging` and described as a draft specification.
- **R5** Eaton figures are attributed in-text ("Eaton lists…"), reproduce the stated conditions, carry the note that the Sandbox is not calibrated to this or any product, and are not placed in a numeric comparison with Sandbox output.
- **R6** The NVIDIA date discrepancy is resolved from the live page, with page date and read date shown.
- **R7** Every source card contains a "What this does not tell you" statement.
- **R8** Career Map has one row per Charter §4 priority (10 rows). Each row links to an in-app exercise point or says "not yet exercised"; any link target must exist on the baseline at implementation time.
- **R9** No ranking, adoption forecast, market, salary or hiring statement anywhere on the page.
- **R10** `SiteNav.tsx`: only the `/industry` entry changes (remove `disabled`). Home page `page.tsx`: only the Industry & Career card changes, to live with `href: "/industry"`, **and its copy is replaced** because the current text promises developments "tracked over time", which V1 does not provide. Proposed copy (subject to Lead edit): question *"How do I judge what the industry is claiming?"*; description *"Read public 800 VDC and solid-state-transformer claims the way an engineer would: what each one says, how strong the evidence is, and which systems-engineering competency it exercises."* No other nav or home change.
- **R11** Layout and tokens follow `DESIGN.md`; usable at phone width (16 px gutters, no horizontal page scroll).
- **R13** (E1) No chart, KPI tile, telemetry, simulation, or protection/audit component is imported or rendered on `/industry`; reused components are limited to `EvidenceTag` and design tokens.
- **R14** (E2) Each of the five claim sheets offers the "What would you ask?" interaction from a fixed question list, client-side only, no persistence, no numeric or free-text input.
- **R15** (E3) The claim sentence, kind/label strip, evidence label, prompt and competency link are visible by default; quotation, dates, citation/URL and "does not tell you" text sit behind a disclosure and remain reachable by keyboard and screen reader.
- **R16** (E4) Each claim sheet links to its Career Map competency row; Career Map is a compact competency list.
- **R17** (reference contract, §4.1) Only the additive `EATON` registry change is made; `EvidenceTag` is unchanged; `READ_LOG` exists with an entry for each of the five sources.
- **R18** (claim audit, §4.5) Every claim on a claim sheet has a passage locator and appears in the PR's claim-to-passage audit table.
- **R19** (Eaton, §4.4) Only the enumerated Eaton figures appear; efficiency conditions are stated as unspecified unless the live page states them.
- **R20** (E7) No diagram, matrix or comparison table of architectures on the page.
- **R12** `docs/PRODUCT_BLUEPRINT.md` §7 "Industry knowledge base" row updated to state the Next.js route exists and the YAML remains Streamlit-era, nothing else in that file changed.

## 9. Acceptance Criteria

- [ ] AC-1 `/industry` exists and renders all three sections and the questions lists.
- [ ] AC-2 Claim sheets equal the five in §4.1, one each; no sixth source; no `sample` content rendered; no source rendered as a second card in another section.
- [ ] AC-3 Every item has one label; every `public-fact`/`emerging` item resolves to a `REFERENCES` entry with URL and to a `READ_LOG` entry with `readDate` (checked by script over the module). This checks provenance only; support is checked by AC-19.
- [ ] AC-4 OCP SST is `emerging` and the word "draft" appears in its card.
- [ ] AC-5 Eaton card has attribution, conditions, non-calibration note, and no Sandbox numeric comparison.
- [ ] AC-6 NVIDIA page date and read date shown; discrepancy noted in the PR as resolved.
- [ ] AC-7 Every source card has a non-empty "does not tell you" field.
- [ ] AC-8 Career Map has exactly 10 rows matching Charter §4; every link target exists on the baseline.
- [ ] AC-9 A text scan of the module and page finds none of: ranking/"leader"/"market share"/"salary"/"hiring"/"forecast" wording.
- [ ] AC-10 Diff touches only these paths: `frontend/app/industry/`; `frontend/app/lib/industryCareerData.ts` (and any check script); `frontend/app/lib/architectureChoicesData.ts` **only** for the additive `EATON` change in §4.1; `frontend/app/components/SiteNav.tsx` (`/industry` entry only); `frontend/app/page.tsx` (Industry & Career card only); `docs/PRODUCT_BLUEPRINT.md` §7 row; `docs/specifications/SPEC-013-industry-career-v1.md` (the adopted spec); `docs/validation/SPEC-013-validation.md` (evidence record, including the claim audit table). No other path, nothing under `src/`, `backend/`, `scenarios/`, `config/`, `content/`, `data/`, `dashboard/`, `tests/`, and no change to `EvidenceTag.tsx` or any existing `REFERENCES` entry.
- [ ] AC-11 `npm run typecheck`, `npm run lint`, `npm run build` pass; the existing Python suite is unaffected.
- [ ] AC-12 Desktop and mobile screenshots show no overflow and legible evidence tags.
- [ ] AC-13 Independent Codex review of the implementation recorded with its real output.
- [ ] AC-18 `/architecture` is unchanged: its production-build text content is identical before and after, and `npm run typecheck` passes with the widened `ReferenceId`.
- [ ] AC-19 The claim-to-passage audit table (§4.5) is in `docs/validation/SPEC-013-validation.md`, covers 100% of claim-sheet claims, and no claim lacks a locator.
- [ ] AC-20 **SST disclosures:** the page states, in visible text, that an SST is not required for an 800 VDC bus and is one candidate for the MV-to-DC stage, and that "SST" in a diagram or label elsewhere is a functional abstraction (Blueprint §5.2 rules 1–2). Verified by a content check for both statements.
- [ ] AC-21 **Standards inventory:** the background-standards list equals exactly {NFPA 70, IEC 60364, IEEE 1547, UL 1741, IEC 62477-1, IEEE 493, IEEE 1584}, each flagged "not opened", each topic sentence either backed by a locator in an already-read source or labelled `assumption`.
- [ ] AC-22 **Ladder:** the Career Map ladder text contains the four Charter §2.2 steps verbatim, including "Systems Architecture / Technical Leadership".
- [ ] AC-23 **Viewport:** at 360 px and 1280 px widths, `document.documentElement.scrollWidth <= clientWidth` and 16 px side gutters are present, measured in a real browser.
- [ ] AC-24 **Accessibility:** disclosures are native `<details>/<summary>` or buttons with `aria-expanded`; all interactive elements are reachable by Tab with visible focus; the "What would you ask?" control is keyboard-operable; headings have no skipped levels; no information is conveyed by colour alone. Verified by a keyboard-only pass recorded in the validation file, plus an automated accessibility check only if one is available without adding a dependency.
- [ ] AC-25 **Home copy:** the Industry & Career home card no longer contains "tracked over time" or any claim of continuous updates.
- [ ] AC-14 Import scan of `frontend/app/industry/` shows none of `TelemetryChart`, `KpiTile`, `ScenarioComparison`, `SensitivityStudy`, `ProtectionTimeline`, `ProtectionCoordination`, `TransientMetricsPanel`, `SweepChart`, or any simulation API client.
- [ ] AC-15 Default (collapsed) view of each claim sheet shows the claim, label strip, prompt and competency link; details are collapsed on load; disclosures operate by keyboard.
- [ ] AC-16 The E6 vocabulary scan finds none of the listed terms except in link labels.
- [ ] AC-17 **Human Product Review:** desktop and mobile screenshots of `/industry` next to `/system-map`, `/architecture`, `/sandbox` (and `/learn` once available) are reviewed by the Human Product Lead for visibly distinct role, hierarchy and density. Codex or CI results alone do not close this criterion.

## 10. Verification Plan

| Check | Method | Verification layer |
|---|---|---|
| AC-3, AC-7, AC-8, AC-9 | Small test or script over `industryCareerData.ts` (label present, reference resolves with URL and read date, non-empty fields, 10 rows, forbidden-wording scan). If the frontend has no test runner, a documented `node`/`tsc` script run at review; **adding a test dependency is not authorized by this spec** (Q2). | unit-level content invariants |
| AC-10 | `git diff --stat origin/main...HEAD` reviewed by the implementer and Codex | regression boundary |
| AC-11 | `npm run typecheck && npm run lint && npm run build`; `pytest -q` run locally and reported separately from CI | build / regression |
| AC-1, AC-12 | Browser run of `/industry` at desktop and phone width, with real screenshots | runtime |
| AC-2, AC-4–AC-6 | Implementer re-reads each live source and records read dates; reviewer spot-checks quotations against the source | source-to-claim audit (as in SPEC-011) |
| AC-13 | Codex CLI review on the Mac; actual output preserved | independent review |
| AC-18 | build `/architecture` before/after and diff extracted text; `tsc` | regression |
| AC-19 | audit table in validation file; Codex spot-check | source-to-claim audit |
| AC-20–AC-22, AC-25 | content checks in the same script as AC-3/7/8/9 | content invariant |
| AC-23, AC-24 | real-browser measurement and keyboard pass, screenshots at 360 and 1280 px | runtime |
| AC-14, AC-16 | grep over `frontend/app/industry/` and `industryCareerData.ts` (imports; vocabulary), same script as the content invariants | boundary / content invariant |
| AC-15 | Browser check with real screenshots (collapsed and expanded) and keyboard-only pass | runtime |
| AC-17 | Human Product Review of the side-by-side screenshots; no substitute | human product gate |

CI is authoritative integration evidence and is reported separately from local verification.

## 11. Known Limitations

- Five sources are a thin base. The page says so and shows source count and read dates; it is not an industry survey and does not claim coverage.
- Vendor and consortium statements are attributed, not endorsed; no performance claim is validated.
- Content ages. There is no update mechanism in V1 (by design). Read dates make staleness visible.
- Standards in §4.2(b) are title-level; their contents were not opened.
- The Career Map describes activities and app coverage, not job requirements or market demand.
- `data/industry/` YAML retains its known issues (free-text dates, "architecture_standard" overstating the SST draft, duplicate records). They are recorded in the readiness analysis and deliberately not fixed here (Phase B).

## 12. Dependencies and Sequencing

- No technical dependency on SPEC-012 or SPEC-014. Separate branch and PR.
- **Ownership.** SPEC-013 owns: the `/industry` nav entry, the Industry & Career home card copy, `REFERENCES.EATON`, and `industryCareerData.ts`. SPEC-012 owns the `/learn` nav entry and the Learn by Example home card. **Nobody in this set owns `EvidenceTag.tsx` or existing `REFERENCES` entries**; if SPEC-014 (or any PR) changes them, the later-merging PR adapts. Each PR edits only its own nav/home entries.
- **Merge order is not fixed.** The PR that merges second must (a) merge `main` into its branch (no rewriting published history), (b) resolve nav/home conflicts keeping both sides' entries, (c) re-run typecheck, lint, build and the content script, (d) re-check R8 link targets (a `/learn` link appears only once `/learn` exists on `main`), and (e) re-confirm AC-18 if `architectureChoicesData.ts` changed upstream.
- SPEC-014 is gated on the SPEC-012 merge and does not gate this spec.
- Phase A deletion manifest does not touch the files in AC-10.
- Implementation starts only after Human Engineering Lead approval of this spec following Codex review.

## 13. Open Questions for the Human Engineering Lead

- **Q1** Keep the ecosystem cards (§4.2.1), or reduce V1 to standards plus Career Map?
- **Q2** If no frontend test runner exists, is a documented script acceptable for AC-3/7/8/9, or should the spec authorize a test dependency? (Recommend script; no new dependency.)
- **Q3** May the Career Map name the Charter §2.2 ladder publicly, given the open audience-wording decision (Blueprint §11.2 item 2)? (If not, use "role activities" without the ladder names.)
- **Q4** Confirm the proposed ID SPEC-013 and that the five-source seed (not three) is wanted.

## 14. Review Status

| Reviewer | State |
|---|---|
| Author self-check | Complete against readiness analysis; not independent verification |
| Codex independent review | **v0.1 reviewed: CHANGES_REQUIRED** (1 blocking, 6 major, 2 minor; output held in the SPEC-014 thread on the Mac, not reproduced here). **v0.3 not re-reviewed**; no further review round was run. |
| Human Product Review (role distinctness) | **Awaiting**; AC-17 |
| Human Engineering Lead approval | **Awaiting** |

## 15. Resolution of Codex findings on v0.1

Summarized from the coordinator's relay of the Codex output, not from the Codex output itself.

| Finding | Resolution in v0.3 |
|---|---|
| BLOCKING: EATON conflicts with existing reference types; `EvidenceTag` hardcodes `#references`; AC-10 forbids registry/component change | Single contract in §4.1: additive `EATON` registry change only; `EvidenceTag` untouched; page supplies its own `#references` section; read dates in a separate `READ_LOG`; AC-10, AC-18, R17. |
| MAJOR 1: URL + read date is not support; "no ref means assumption" lets unsupported claims through | §4.5 passage locators and audit table; unsupported claims removed, not downgraded; R18, AC-19; AC-3 scoped to provenance. |
| MAJOR 2: "exactly five, shown once" vs standards section repeating OCPWP/OCPSST | Five featured claim sheets, one each; standards rows link back; R2, AC-2. |
| MAJOR 3: product role not enforceable; "Architecture Map" risks a third overview; home card promises "tracked over time" | §4.3 E7, section renamed "Claims to read", R20; home copy replaced in R10; AC-25. |
| MAJOR 4: sequencing with SPEC-012/014 is more than a rebase | §12 ownership and merge procedure. |
| MAJOR 5: SST disclosures, standards inventory, ladder, viewport, accessibility lack acceptance checks | AC-20 to AC-24 with verification rows. |
| MAJOR 6: AC-10 excludes `docs/validation/` and adopted spec path | AC-10 path list now includes both. |
| MINOR: Eaton figures not enumerated; efficiency conditions; certification extrapolation | §4.4, R19. |
| MINOR: ladder missing "Technical Leadership" | §4.2.3, AC-22. |
| MINOR: template Project/Version fields | Header carries `Project` and `Version` 0.3 in template order. |
