# Signal Path: design direction

**Status:** APPROVED WITH CONDITIONS by the Human Engineering Lead (2026-10-19). Approved: D1 (headlines up to 40px),
D2 (sentence-case Plex Sans headings, Plex Mono for engineering values, equations and concise metadata).
Conditional: D3 (rail), D4 (disclosures). This document is the revised proposal; the bounded `DESIGN.md` text is in
`DESIGN_MD_REVISIONS.md` and the landing plan is in `INTEGRATION_PLAN.md`. Prototype: `/design-lab` on branch
`claude/project-thread-gjf3nc`. The prototype pages are design demonstrations, not feature-parity replacements,
and the branch is not to be merged into `main`.

## Why

The baseline pages share one pattern: uppercase mono labels, several caveat bullets before the first instrument, and one long
document per page. The content is strong; the hierarchy is flat, and the five areas are indistinguishable in *how* you use
them. Cosmetic patches do not fix that.

## References (principles only)

| Reference | Taken | Not taken |
|---|---|---|
| Variant | Minimal chrome, a distinct typographic voice, density as a deliberate lever, "visual DNA" (palette + type rhythm + density) as explicit tokens | Endless-scroll generative exploration |
| Linear / Raycast (already in DESIGN.md) | Surface ladder, one accent, no shadow | n/a |
| Observable / Distill-style explorables | One question per view, the instrument is the content | Long scrolly essays |
| Brilliant / Desmos | Predict-then-reveal, immediate manipulation | Gamification, mascots |
| Grafana / engineering consoles | Real data in the chart, parameter rail + instruments | Dense unlabeled dashboards |

Limitation: variant.com and the shared chat were not viewable from the build environment (sign-in page; network blocked).
Variant input comes from its public descriptions only.

## The direction

1. **Architecture-aware signal-path rail (D3, revised).** The rail under the nav draws the *selected architecture's own main
   power path*, taken from the System Map data. It is never one universal chain.
   - Conventional AC shows grid, substation, MV switchgear, UPS + battery plant, AC distribution, rack PSUs, servers.
   - AC-fed 800 VDC shows its own stages, with no SST.
   - The SST appears only in the Conceptual MV-to-800 VDC via SST architecture, labeled "(conceptual)".
   - System Map and Architecture Choices set the selected architecture; other pages show the last selection.
   - Learn by Example and the Advanced Sandbox pin the rail to the SST architecture and mark the simulated slice with a dashed
     bracket and an explicit "Simulated slice: SST, 800 VDC bus, lumped AI load" note. The gap on the rail (rack DC-DC is not
     modeled) is intentional.
   - Focus is shown by surface tier and weight only. Mobile: label row plus a dot track, no node names.
2. **Question, then instrument.** Every page opens with one engineering question and a one-sentence answer, then the instrument.
3. **Disclosures stay visible (D4, revised).** The mandatory disclosures render on initial load, verbatim, in one structured
   "Basis & limits" panel (mono tag + text, two columns on desktop, one on mobile). They cannot be collapsed. Evidence
   labels remain on every item.
4. **Quiet type.** Plex Sans, sentence case, 40/18/14/12 scale, weight at most 600. Plex Mono only for engineering values, equations,
   tags and concise metadata.
5. **Neutral evidence chips.** Glyph plus text in neutral color; status colors stay reserved for engineering state.
6. **Five interaction models, one language:**

| Area | Model | Pattern |
|---|---|---|
| System Map | Inspect | Path + stage inspector |
| Architecture Choices | Compare | Driver lens, evidence grid, three columns |
| Learn by Example | Predict | Predict, Discover, Explain, Apply stepper on a live model run |
| Industry & Career | Trace | Claim, source, strength, what it does not show; competency map linking back |
| Advanced Sandbox | Experiment | Parameter rail + instruments |

## Prototype data provenance

System Map and Architecture Choices read `infrastructureMapData` and `architectureChoicesData` unchanged. Learn (thermal trip)
and Sandbox (load step) read live runs through the existing API; metrics reuse `computeTransientMetrics`. The Learn and Industry
prose in the prototype is demonstration copy, **not** the SPEC-012/013 content; integration must use their data modules.
Chart drawing decimates to about 700 points (presentation only); Sandbox power axes divide W by 1000 at the display boundary.

## Run it

```
pip install -r requirements.txt fastapi uvicorn
AI_POWER_LAB_EXTRA_CORS_ORIGINS=http://localhost:3200 python3 -m uvicorn backend.app:app --port 8000
cd frontend && npm ci && npx next dev -p 3200      # http://localhost:3200/design-lab
```
