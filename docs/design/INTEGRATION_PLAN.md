# Signal Path: implementation plan (one page)

**Principle:** `/design-lab` is a reference, not a merge candidate. Production code is rebuilt from it in gated PRs that
reuse existing data modules and components. No change to `src/`, `backend/`, API shapes, thresholds, or engineering claims.
SPEC-012's branch/PR #9 and other threads' worktrees are not touched by this plan until their owners act.

| Order | Step | Depends on | Owner thread / spec | Scope |
|---|---|---|---|---|
| 0 | SPEC-012 (PR #9) reviewed and merged as designed | existing gates | SPEC-012 | no design change; Learn keeps its content and R16 checks |
| 1 | **Foundation PR** (SPEC-014 stage A): apply `DESIGN_MD_REVISIONS.md`; add tokens/type utilities, `AreaHeader`, `BasisPanel`, architecture-aware `SignalPathRail` + shared architecture state, evidence glyphs inside the existing `EvidenceTag` | 0 (shares `SiteNav`, `page.tsx`, `EvidenceTag`) | SPEC-014 | System Map and Architecture Choices (SPEC-011 pages) restyled; tests and AC updated; disclosures verbatim and visible |
| 2 | Learn by Example restyle (stage B): stepper shell around SPEC-012's content and data module, rail pinned to the SST slice | 1 | SPEC-014, SPEC-012 owner reviews | presentation only; every SPEC-012 claim, label and acceptance check preserved |
| 3 | Industry & Career V1 built on the foundation components | 1; SPEC-013 revised after its Codex CHANGES_REQUIRED | SPEC-013 | SPEC-013 consumes `AreaHeader`, `BasisPanel`, trace pattern; it does not fork `EvidenceTag` or the registry |
| 4 | Advanced Sandbox workbench restyle and home page (stage C) | 1 | SPEC-014 | layout and type only; engine, API calls, metrics unchanged |

Shared-file ownership (to avoid collisions): `SiteNav.tsx`, `EvidenceTag`, `architectureChoicesData` references and the home page
are owned by the foundation PR; SPEC-013 adds references additively and does not edit them in its own PR.

**Gates for every PR:** approved spec with acceptance criteria; local lint, typecheck, build and the repo's tests; independent
Codex review (run on the Human's Mac, output preserved); CI reported separately; desktop and mobile screenshots at 1440 and 390;
Human Visual QA; human merge approval. Visual change is accepted only if existing tests and engineering claims still pass.

**Known risks for review:**
1. Rail semantics: confirm it never implies a universal path or that SST is required, and that the slice marking is unambiguous.
2. Disclosures: confirm visibility and verbatim wording vs SPEC-011 R2 after restyle.
3. Prototype copy for Learn and Industry is demonstration text; integration must use SPEC-012/013 data modules.
4. Shared architecture state across pages is client-only context; deep links need a URL param if required.
5. Contrast: mono tags at 10 to 11px must use `text-secondary` or brighter (the prototype does); `muted` stays out of essential text.
6. Interleaving with SPEC-012 on `SiteNav`/`page.tsx`: sequence after the PR #9 merge.
7. Sandbox kW axis conversion and chart decimation are presentation-only and need a unit test when productionized.
