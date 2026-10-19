# Signal Path — design direction (prototype, not approved)

**Status:** proposal with a working prototype at `/design-lab` (frontend only). Nothing in `DESIGN.md`,
production routes, the engine, the API or any number has been changed. Adopting this direction is a
`DESIGN.md` revision and needs human approval.

## Why change direction

Baseline (`/system-map`, `/architecture`, the Learn prototype) shares one pattern: uppercase mono labels, five
caveat bullets before the first instrument, and one long document per page. The content is strong; the
hierarchy is flat, so every page reads as a text dump and the five areas are visually indistinguishable in
*how* you use them. Further cosmetic patches would not fix that.

## References and what was taken (principles only)

| Reference | Taken | Not taken |
|---|---|---|
| Variant (variant.com) | Minimal chrome, a distinct typographic voice, density treated as a deliberate lever, and "visual DNA" (palette + type rhythm + density) as an explicit, reusable set of tokens | Endless-scroll exploration, generative variety, marketing-style range. A learning instrument needs one stable identity |
| Linear / Raycast (already in DESIGN.md) | Surface ladder, one accent, no shadow | — |
| Observable / Distill-style explorables | One question per view, the instrument is the content, explanation follows interaction | Long scrolly essays |
| Brilliant / Desmos | Predict-then-reveal, immediate manipulation | Gamification, mascots, streaks |
| Grafana / engineering consoles | Real data in the chart, parameter rail + instruments workbench | Dense unlabeled dashboards |

Limitation: variant.com and the shared chat link were not directly viewable from this environment (sign-in
page only; browser network access blocked). Variant input is from its public pages and press descriptions, not
from seeing the chat's designs. If the chat holds specific screens, share screenshots.

## The one recommended direction: Signal Path

1. **Signal path rail.** A strip under the nav draws the real chain (utility grid, MV switchgear, SST /
   conversion, 800 VDC bus, rack and compute). Each area highlights the span it works on, via surface tier
   and weight only (DESIGN.md §19). It is the shared identity and the "where am I in the chain" cue.
2. **Question, then instrument.** Every page opens with one engineering question and a one-sentence answer,
   then the instrument. Disclosures fold into one *Basis & limits* bar with the verbatim text one click away.
3. **Quiet type, loud structure.** Plex Sans, sentence case, 40/18/14/12 scale, weight <= 600; Plex Mono only
   for numbers, tags, equations.
4. **Neutral evidence chips.** Evidence is not health, so chips use glyph + text in neutral color. Status
   colors stay reserved for engineering state.
5. **Interaction verb per area**, same visual language:

| Area | Verb | Pattern |
|---|---|---|
| System Map | Inspect | Path + stage inspector |
| Architecture Choices | Compare | Driver lens, evidence grid, three columns |
| Learn by Example | Predict | Predict, Discover, Explain, Apply stepper on a live model run |
| Industry & Career | Trace | Claim, source, strength, what it does not show; competency map linking back |
| Advanced Sandbox | Experiment | Parameter rail + instruments |

## Compatibility with DESIGN.md

Unchanged: tokens, dark canvas, flat surfaces, one accent, status roles, 4px radius, no gradient/shadow,
Plex families, tabular mono for numbers, Implementation Contract.

Needs an explicit decision (each is a DESIGN.md revision):
- D1. Page-headline size above the 22px display ceiling (prototype: 40px, weight 600).
- D2. Sentence-case headings and Plex Sans labels replacing the uppercase-heading tier (§6).
- D3. A second nav row (the signal path rail), purely orienting.
- D4. SPEC-011 R2 mandatory disclosures are collapsed by default behind a visible "Basis & limits" bar. This may
  conflict with R2's wording; if R2 requires default-visible text, the bar must open by default.
- D5. Step-to-step state change in Learn (no animation was added).

## Prototype data provenance

System Map and Architecture Choices read `infrastructureMapData` / `architectureChoicesData` unchanged.
Learn (thermal trip) and Sandbox (load step) read live runs through the existing API; metrics reuse
`computeTransientMetrics`. Chart drawing decimates to ~700 points per series (presentation only). Industry
uses the audited `REFERENCES` plus the Eaton record already in `data/industry/`; the competency map is an
illustrative teaching framework, labeled as such. Sandbox kW axes divide W by 1000 at the display boundary.

## Run it

```
pip install -r requirements.txt fastapi uvicorn
AI_POWER_LAB_EXTRA_CORS_ORIGINS=http://localhost:3200 python3 -m uvicorn backend.app:app --port 8000
cd frontend && npm ci && npx next dev -p 3200      # open http://localhost:3200/design-lab
```
