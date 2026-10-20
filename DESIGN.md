# AI Power Lab — Design System

**Status:** locked visual direction for the current Next.js/React implementation (`frontend/app/`) and any future frontend. This document is a constitution, not a mood board — when a future change conflicts with it, the change is wrong until this document is deliberately revised, not the other way around. The original Streamlit implementation (`dashboard/`) is the historical origin of these tokens, not the current reference implementation — see the Implementation Contract.

## Central Principle

> AI Power Lab is a learning instrument, not a marketing site.
> The product is engineering understanding, built with real precision; the interface exists to make systems-level AI-data-center power knowledge — whether read off live simulated telemetry or taught through clearly-labeled educational reference content — fast and confident to absorb.

Every rule in this document answers to that sentence. If a future decision doesn't make the system's state or its underlying engineering concepts faster or more confident to understand, it doesn't belong here, no matter how polished it looks in isolation. AI Power Lab 2.0 is explicitly an **industry-first learning platform built with engineering precision** — not a pure operator console (its original framing) and not a startup marketing product either. The learning-platform pages (System Map, Architecture Choices, Learn by Example, Industry & Career) and the Advanced Sandbox (the original simulator) are two faces of the same instrument and share every rule below; neither gets a separate visual language.

---

## 1. Visual Philosophy

AI Power Lab is built to feel like the software an operator keeps open at a desk, not software built to be screenshotted for a landing page. That distinction drives everything else in this document:

- The interface is **flat**. Depth comes from a surface hierarchy and border weight, never from shadow, blur, or glassmorphism.
- The interface is **restrained**. One accent color. Four status roles. Nothing else is chromatic.
- The interface is **dense but legible**. Information is close together, not spread out to look generous — generous spacing is a marketing convention, not an operations convention.
- The interface is **honest**. Every live value, color, and animation tied to a simulation run is derived from real simulated engineering state — nothing live is decorative. Static educational/reference diagrams (e.g., the System Map's infrastructure overview) are permitted to illustrate a concept rather than a live telemetry value, **but only when clearly labeled as conceptual/illustrative** — see "Conceptual Educational Diagrams," below. A conceptual diagram pretending to be a live readout is exactly the dishonesty this rule forbids.
- The interface is **dark, permanently**. There is no light mode to maintain parity with, because a mission-critical console is not a brand surface that needs to flatter a product screenshot in daylight.

### Conceptual Educational Diagrams

The learning platform (System Map today; Architecture Choices and Learn by Example later) teaches concepts that have no single "live" instance — an industry-representative architecture, a category of equipment, a generic topology. These are **not** telemetry and must never be styled as if they were:

- A conceptual diagram or card carries a visible label marking it as illustrative/representative (e.g., an explicit caveat that it is one representative architecture, not a universal one) — never presented bare, as if it were a live system state.
- A conceptual diagram still obeys every other rule in this document (color tokens, type scale, spacing, border hierarchy, no shadows/gradients) — "conceptual" licenses *what the content claims*, never a second visual language.
- The one component that does render live telemetry (`PowerFlowSchematic`) is reused, not forked, across both contexts: it renders nominal/accent styling when given no live data (System Map) and real status-colored state when given a live sample (Advanced Sandbox). It is one component with one palette, not a "static" skin and a "live" skin.

This system was synthesized from a comparative study of real product design languages (see **Reference Influences** below) — it borrows recurring *principles* that independently appeared across unrelated companies, never a single brand's signature look. Nothing here is "inspired by" one product; it is AI Power Lab's own answer to problems those products also had to solve.

### Basis & limits panel

Mandatory spec disclosures are visible on initial load, verbatim, in a structured panel (mono tag plus text). They are never collapsed, paraphrased or hidden behind an interaction. Presentation may change; wording and visibility may not. Each page imports the canonical constants of its spec (SPEC-011 `DISCLOSURES`, SPEC-012 `LEARN_DISCLOSURES`).

## 2. Product Identity

**Name:** AI Power Lab
**Subtitle / system identifier:** SST / 800 VDC AI Power Infrastructure
**Domain:** an educational, system-level digital twin of a solid-state-transformer-powered, 800 VDC AI data-center power chain (MV Grid → SST → 800 VDC Bus → AI Compute Load).
**Register:** an industry-first learning platform built with engineering precision — serious engineering content, taught, not a startup marketing product and not a pure operator console. The identity mark is a small, precise wordmark — never a logo mark, never an icon, never a gradient.

## 3. Color Tokens

The full token set is implemented in `frontend/app/globals.css` (`:root` custom properties, consumed through Tailwind's `@theme inline`) and `frontend/app/lib/theme.ts` (`SVG_COLOR`, for inline-SVG presentation attributes that need raw `var(--color-*)` strings). `dashboard/components/palette.py`/`.streamlit/config.toml` is the historical origin of these exact values, kept in sync as a legacy reference, not the current source of truth. This document is the record of *why* those values are what they are, and the contract for every surface — System Map, Sandbox, and any future page — to use them exactly as defined here, with no per-component or per-page variant.

| Token | Value | Role |
|---|---|---|
| `canvas` | `#0a0e14` | Page background — the deepest tier |
| `surface` | `#121820` | Panel background — the default resting surface |
| `surface-raised` | `#1a232e` | Elevated / focused panel |
| `surface-inset` | `#0d131a` | Sunken background: numeric readouts, the signal-path rail, segmented-control wells; implemented as `--color-surface-inset` |
| `text-primary` | `#e7edf3` | Primary reading text and live values |
| `text-secondary` | `#aab4bd` | Labels, captions, explanatory text |
| `muted` | `#6b7680` | De-emphasized metadata, units, the neutral status role |
| `hairline` | `#24303c` | Default 1px border/divider |
| `hairline-strong` | `rgba(226,232,240,0.22)` | Emphasis border without introducing a color; a selected control changes surface tier and takes this border (no shadow, no ring); implemented as `--color-hairline-strong` |

**Current governing palette vs. historical specs.** The tokens in this section and §4 are the only governing palette. `docs/specifications/SPEC-005` refers to a schematic "cyan/amber" pair (`SVG_COLOR.schematicCyan` / `schematicAmber`); those names do not exist in `frontend/app/lib/theme.ts`, and the schematic now draws from `accent` plus the four status roles. SPEC-005 is a historical record and is not rewritten here; where it differs from this document, this document governs.

There is exactly **one accent color**, reserved for one meaning:

| Token | Value | Meaning |
|---|---|---|
| `accent` | `#3987e5` | "Energized / actively flowing / process in motion." Never used for selection, branding flourish, or decoration. |

No second chromatic accent exists anywhere in this system, including for focus or selection states (see §14, §19), **and including inside any individual component's own presentation code.** A component is never allowed to introduce its own "scoped" palette (e.g., a second blue/amber pair reserved "just for this diagram") on the reasoning that it only affects one surface — every surface draws from this one token set, full stop. Adding a second accent anywhere requires revising this document first, which has not happened.

## 4. Semantic / Status (Electrical) Colors

| Role | Value | Meaning |
|---|---|---|
| `good` | `#0ca30c` | Healthy, nominal, in regulation |
| `warning` | `#fab219` | Derating, drooping, sagged — degraded but not failed |
| `serious` | `#ec835a` | Reserved escalation step between warning and critical — declared in the token set, not yet assigned by any classifier; do not use until a real engineering distinction needs it |
| `critical` | `#d03b3b` | Faulted, tripped, lost, collapsed |
| `neutral` | `#6b7680` | Not a health state at all — see Engineering Visual Semantics, below |

`serious` is why the Engineering Visual Semantics table below lists four meaningful colors plus neutral, not five — it documents what the system actually says today, and `serious` has nothing assigned to it yet. These five roles are the **only** source of status color in the product. They are implemented once, in `palette.py`'s `STATUS` dict, and consumed everywhere (the power-flow schematic, the KPI strip) through the shared `grid_status` / `sst_status` / `bus_status` classifier functions in `schematic.py` — never recomputed or re-judged independently by a second surface. Two surfaces disagreeing about the same entity's status is a bug, not a styling choice (this happened once, with `P_load` defaulting to green before the `neutral` role existed — see the fix in `palette.py`/`simulator.py`).

**Planned, not yet implemented:** a `-soft` background-tint variant of each role (10–15% opacity fill), for a lower-urgency escalation step — e.g. a KPI tile background wash before its border escalates. This extends the existing roles; it does not add a sixth meaning.

## 5. Background / Surface Hierarchy

A strict ladder, never skipped, never represented by a shadow:

```
inset  →  surface  →  surface-raised  →  surface-raised + 2px status border
(sunken    (resting      (elevated/          (elevated AND
 readout)   panel)        focused panel)      in a non-good state)
```

No more than three tiers are ever visible in one screen region at once. Elevation is communicated by *which* tier a surface sits on plus its border weight — never by `box-shadow`, blur, or an opacity gradient. This has been verified clean in the live implementation: zero inline shadows, blurs, or gradients exist anywhere in the shipped product.

## 6. Typography

Two families, strictly separated by role, never mixed:

- **IBM Plex Sans** — all UI chrome: labels, headings, body/explainer text, navigation.
- **IBM Plex Mono** — Plex Mono is used for live or tabular values, equations and code, and for concise instrument metadata (tags, units, chart ticks, step and area numbering). It is never used for running prose or headings.

Hierarchy is built primarily from **weight**, not size — the earlier implementation accumulated twelve distinct font sizes by accident; the fix is a small, deliberate, *named* scale where weight does most of the differentiating work. This is a semantic scale: every piece of text in the product maps to one of these four tiers. Sizes inside a tier's range are acceptable; a size outside every tier's range is a defect to fix.

| Tier | Token | Size | Weight | Treatment |
|---|---|---|---|---|
| Page title | `text-page-title` | 28px (mobile) to 40px (from `sm`) | 600 | Plex Sans, sentence case, -0.02em, one per page |
| Section / panel heading | `text-heading` | 14 to 18px | 600 | Plex Sans, sentence case, `text-primary` (replaces the uppercase 11.5px muted tier) |
| Body / explainer | `text-body` | 13 to 14px (lede up to 16px, once per page) | 400 | `text-secondary` |
| Metadata / label / unit | `text-meta` | 10.5 to 12px | 500 to 600 | Plex Mono uppercase for tags and units; Plex Sans 12px for plain labels |

The "homepage headline" exception is removed (the page-title tier covers it). Weight never exceeds 700.

Display weight never exceeds 700 anywhere in the product. A heavier weight reads as marketing emphasis, not instrument precision. **Known gap:** the React implementation does not define these four tiers as reusable Tailwind utilities/CSS custom properties — the token names above are descriptive, and components write `text-[Npx]` literals (currently 9px to 14px in small steps, plus the display and homepage sizes), which is more distinct sizes than four. Introducing `text-display`/`text-heading`/`text-body`/`text-meta` utilities (or equivalent) and migrating existing literals onto them is tracked as a cleanup, not a license to keep adding new sizes in the meantime.

## 7. Telemetry / Numeric Typography

The single most load-bearing typographic rule in the system: **every number that represents a live simulated value is IBM Plex Mono with tabular numerals, full stop.** This prevents digit-width jitter on every tick and is the one place monospace is not optional.

- Primary KPI values: 20–24px / 600 / `text-primary`, with their unit suffix rendered smaller (11–12px) and in `text-secondary` (`muted` fails AA for small text, §18), baseline-aligned — the number dominates, the unit does not compete with it.
- Secondary numeric values (schematic stage values): 14–15px / 600, the existing `.console-mono` tier.
- Numbers are never italicized, never a non-tabular digit face, never animated with easing — a value updates to its new reading instantly, because an eased number is a number lying about when the reading actually changed.

## 8. Spacing Scale

A 4px base unit: `4 / 8 / 12 / 16 / 24 / 32px`. Panel padding stays in the 12–16px range. Row spacing inside a dense panel (KPI tiles, stat rows) targets 8px. Section-to-section rhythm uses 24–32px, through exactly one separating mechanism per transition (whitespace *or* a divider, never both stacked to do the same job). This is deliberately tighter than a marketing site's rhythm — density is a feature here, not a defect to soften.

## 9. Border Hierarchy

Three strengths, each with exactly one meaning:

1. **`hairline`** (1px, `#24303c`) — the default separator for every panel, card, and divider in the product.
2. **`hairline-strong`** — emphasis without introducing a color, for a panel that needs to stand out without implying a status judgment. A selected control changes surface tier and border to `hairline-strong`; no shadow and no ring. The §18 keyboard focus outline (2px `secondary`) is unchanged and applies in addition.
3. **Status border** (2px, one of the four STATUS colors) — the *only* border that ever carries meaning. It appears exclusively on an entity that is actually, currently, in that state. A 1px neutral border escalating to 2px and a status color is the entire alarm-escalation vocabulary of this system (see §16).

No panel, card, list item, or alert ever uses a colored left- or right-border accent above 1px as a decorative device — that pattern reads as generic templated chrome, and this product has already removed the one place it crept in (the former six-row status panel's colored left bars, retired when the KPI strip replaced it).

## 10. Corner Radius

4px, flat, everywhere, no exceptions above 8px anywhere in product chrome. This number is small on purpose: a larger, softer radius reads as consumer software; a sharp one reads as engineered. Circular elements (status dots) are the only shapes that are ever fully round.

## 11. Elevation

There is no shadow-based elevation system in this product, and there will not be one. Elevation is the surface ladder (§5) plus border weight (§9). This is a deliberate, permanent constraint, not a placeholder for a future shadow system.

## 12. Navigation

Horizontal top navigation bar (`frontend/app/components/SiteNav.tsx`), text-only labels, no icons and no emoji — this supersedes the earlier left-rail icon + label requirement, which described the original Streamlit implementation and is not the current one. Links use IBM Plex Mono at metadata size (§6). The current route is marked on the link itself by a shift from `text-secondary` to `text-primary` plus a 2px bottom border, both drawn from the neutral grayscale rather than `accent` or a status color — a deliberate, scoped exception to §19's "selection changes surface tier, never color" rule, made because a flat horizontal nav bar has no elevated surface tier for an individual link to sit on the way a panel does; it does not license color-based selection anywhere else in the product. A learning area not yet implemented is rendered as plain, non-clickable text carrying an explicit "(planned)" label — never a dead link or a placeholder route. Keyboard focus follows §18.

A single signal-path rail may sit under the nav. It draws the selected architecture's own main power path from the System Map data and never one universal chain. An SST node appears only in the Conceptual MV-to-800 VDC via SST architecture and is labeled conceptual. Pages that run the simulation pin the rail to that architecture and mark the simulated slice with dashed node borders; the page's Basis & limits panel carries the legend (dashed nodes are simulated; stages the model does not represent, such as rack DC-DC conversion, are named as not modeled). Focus is shown by surface tier and weight, never color. The rail exposes the node sequence in its accessible name. On narrow screens it collapses to a label row and a dot track.

## 13. KPI Tiles

The compact, flat instrument tile is the system's primary way of presenting a headline telemetry value: uppercase label, dominant tabular value, de-emphasized unit, and a top border that is 1px neutral by default and escalates to 2px in a status color only when that specific value's role leaves good/neutral. Tiles never use a drop shadow, a rounded-pill shape, or a decorative icon. A tile's color state is always computed from the same shared status classifier the power-flow schematic uses — never judged independently.

## 14. Controls

One button language: ghost/outline by default, 4px radius, `hairline` border, `surface-raised` background. Exactly one filled exception exists per major context — a page, or a self-contained section acting as its own context (e.g. the home page's entry CTA, the System Map's "Open the Advanced Sandbox" exit CTA, the Sandbox's Run Experiment action) — and it is always `accent` blue, never any other fill color (not `text-primary`, not a status color). Its label is set in `canvas` color for AA contrast (§18). Button labels use Plex Mono or Sans at metadata size (§6). Two filled buttons are never visible in the same context at once. Selection and hover states change the surface tier the control sits on, not its color — color is reserved for status alone, never repurposed to mean "you're interacting with this" or "this is the primary action" (the filled `accent` fill, not a border color, is what marks the primary action).

## 15. Charts

Charts share the same dark canvas, the same hairline gridlines at low opacity, and the same panel-header typography as every other instrument on the page — a chart is another gauge in the cluster, not an embedded third-party widget. Chart chrome that reads as "generic web tool" (a visible toolbar/modebar, oversized titles) is suppressed. The guiding rule, borrowed in spirit from this study's strongest data-product reference: **show the real data, never illustrate it.** Every trace, marker, and threshold line on a chart is computed from actual simulated telemetry.

## 16. Alarm / Status Communication

Status is always communicated through at least two channels at once — color is never the only signal (a dot, a label, and a border weight all move together). The vocabulary is fixed and small:

- **1px neutral border, no colored dot** — this entity is fine.
- **2px warning border + amber dot + label** — degraded, worth attention, not yet a fault.
- **2px critical border + red dot + label** — faulted; this is the loudest state the system has, and it is reserved for genuine faults only.
- **Neutral role** — explicitly *not* a health judgment (see Engineering Visual Semantics, below).

**Planned, not yet implemented:** a distinct "transient" treatment — a value actively moving toward a new setpoint after a real engineering event (e.g. just after a load step), shown as a brief `accent`-blue pulse rather than a status color, so the system never looks alarmed simply because it is correctly, dynamically responding to a real input.

**Evidence labels.** Evidence labels render as neutral chips with a glyph (square public fact, circle illustrative assumption, diamond model output, triangle emerging) plus the canonical label text. The existing `EvidenceTag` gains the glyph as a presentation prop; its basis, references and reference destinations are unchanged. Evidence never uses a status color.

## 17. Power-Flow Schematic

The schematic (`frontend/app/components/PowerFlowSchematic.tsx`; historically `dashboard/components/schematic.py`) is the product's single most domain-specific element and the clearest expression of the central principle: every value on it — stage border color, flow-line thickness, flow-line animation speed — is computed directly from one instant of real `Telemetry` when telemetry is available, never from a styling choice. It draws from the same `accent`/status token set as every other surface in the product — it has no palette of its own, scoped or otherwise. On the System Map, it renders with no live sample (the `live` prop omitted): nominal `accent`-colored structure throughout, no V/E readouts, clearly a topology diagram rather than a live reading. On the Advanced Sandbox, the same component renders with a real sample and shows real status coloring and readouts. It intentionally does not attempt switching-level or 3D hardware realism; it is a schematic, not a rendering. This component's visual design does not change by context — it is the standard the rest of the interface is held to, not a target for restyling.

## 18. Focus / Accessibility States

**Implemented per control; not yet global.** Interactive controls on the System Map, homepage navigation, `InfrastructureMap`, and `PowerFlowSchematic` carry a Tailwind `focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-secondary` treatment (offset 4px on the `SiteNav` route links): a 2px outline in the neutral `secondary` color, drawn only for keyboard focus. It uses a neutral token rather than `accent` so focus never competes with the "energized" meaning of the accent color (§3). There is no global `:focus-visible` rule in `globals.css`, and the originally committed accent ring plus hairline underline was not implemented; **known gap:** some controls (e.g. the Sandbox experiment controls and Sensitivity Study buttons) rely on browser-default focus until a shared rule is added. Any new control must include the outline treatment above.

Contrast: normal-size text must reach WCAG AA's 4.5:1 against the surface it sits on. `text-primary` and `text-secondary` meet this on every surface tier. `text-muted` (`#6b7680`) measures about 4.2:1 on `canvas`, 3.9:1 on `surface` and 3.4:1 on `surface-raised`, so it is limited to non-essential decoration or large text and must not carry body or caveat copy. Text on `accent` fills uses `canvas` (about 5.3:1); `text-primary` on `accent` is about 3.1:1 and does not meet AA for normal text. Some Sandbox controls still use `text-primary` on `accent` and `text-muted` on dark surfaces; these are tracked contrast gaps, not precedent.

Essential text (including chart reference-line labels) uses `text-secondary` or brighter; `muted` stays limited to non-essential decoration.

## 19. Interaction Principles

- Selecting or focusing an element changes **which surface tier it sits on**, never its color.
- Status color changes mean exactly one thing: something about the system's actual health changed. It never means "you clicked this."
- A manual, deliberate user action (e.g. dragging the time scrubber) may trigger a fuller re-render than a passive, automatic one (e.g. autoplay ticking) — correctness and responsiveness to intentional actions are prioritized over perfectly continuous animation.

## 20. Animation / Motion

Motion is minimal and must be earned by a real signal:

- The power-flow schematic's flow-line animation speed is driven by real power magnitude — this is the model every other animation in the product is measured against.
- A status dot may pulse slowly (opacity 1↔0.7, ~1.5s) while — and only while — its entity is in a non-good state.
- Nothing else animates. No page-load animation, no hover-lift, no scroll-triggered reveal, no eased number counters. If a future addition can't point to a real engineering signal driving it, it doesn't belong.

## 21. Responsive Behavior

The four learning areas must be readable at 390px with no horizontal page scroll; wide tables and charts scroll inside a named, keyboard-focusable container with a visible hint, and chart text never renders below its authored size. The Advanced Sandbox remains desktop-first and keeps SPEC-014's no-clipping floor.

## 22. Explicit Do / Don't Rules

**Do:**
- Derive every color on screen from real engineering state or from this document's fixed token set — nothing else.
- Keep status color to the four STATUS roles, applied through the shared classifier functions, never re-judged per surface.
- Use weight and the surface ladder to establish hierarchy before reaching for size or color.
- Plex Mono is used for live or tabular values, equations and code, and for concise instrument metadata (tags, units, chart ticks, step and area numbering). It is never used for running prose or headings.
- Treat 4px radius and flat, hairline-bordered surfaces as permanent, not provisional.

**Don't:**
- Don't use a gradient anywhere, for any reason.
- Don't use a drop shadow, blur, or glassmorphism as a depth cue.
- Don't use a pill-shaped button or card in product chrome.
- Don't introduce a second chromatic accent color.
- Don't use color as the only signal for a status — always pair it with a label, dot, or border-weight change.
- Don't use an emoji, mascot, or illustration as a substitute for a real icon system.
- Don't animate anything that isn't driven by a real, computable engineering signal.
- Don't let a new brand/identity color go unchecked against the STATUS palette — a collision (a brand color that reads as "warning" or "good" by coincidence) is a safety-relevant bug in this product, not a cosmetic one.

## 23. Composition and Visual Hierarchy (instrument console)

Added with SPEC-014's art-direction pass. No new tokens, colors or radii: hierarchy comes from scale, surface contrast, composition and space.

- **One focal element per page.** Architecture Choices: the decision board (three architectures in aligned columns). Advanced Sandbox: the live state and principal transient (one large mono value, the hero chart). System Map: the main power-path topology. The focal element sits on a `surface-raised` "stage"; supporting content is text on `canvas` separated by space and a single hairline, not a box.
- **Surface contrast.** Stage = `surface-raised`; control rails = `surface-inset`; quiet content = no surface. A stage is never nested inside another box, and at most one boxed container is used per region.
- **Scale levels.** Page title 28-40px (§6); the engineering question or current focus 22-34px; the single live headline value on a page may be a mono numeral up to 84px (never prose or a heading); key metrics 30-38px mono; actions 14-15px; supporting prose 13-14px; evidence and limitations 12px.
- **Emphasis without new color.** A marked option (for example "Tends to favor") uses the `text-primary` surface (white bar and chip), never an accent or status color. Accent remains "energized / live"; status colors remain status.
- **Asymmetry over repetition.** Layouts use deliberate unequal columns (a narrow rail plus a wide stage; 7/5 splits) instead of equal repeated cards.
- **Conditional emphasis stays conditional.** An emphasized option is labeled as a conditional tendency with its exceptions and never reads as a ranking or a winner (SPEC-011).
- **Live values state what they are.** A large live value is labeled "current" and tied to the displayed run and the time scrubber; minimum, reference and final values are shown separately and labeled.

---

## Engineering Visual Semantics

**Visual state must always derive from real engineering state, or be clearly labeled as conceptual/educational content rather than live state. This is the single non-negotiable rule in this document.** A color, animation, or status label presented *as if it reflected real simulated state* when it doesn't is a defect, regardless of how it looks. This is not an opening for decoration: a conceptual diagram still uses only this document's fixed token set (§3/§4) and still carries its "illustrative" label (see "Conceptual Educational Diagrams," §1) — it just isn't required to trace to a live `Telemetry` instance the way the Power-Flow Schematic's live mode or the KPI strip are.

The fixed vocabulary:

| Color | Meaning | Source |
|---|---|---|
| **Blue** (`accent`) | Energized / process in motion / information | Real power flow magnitude, selection has no color of its own |
| **Green** (`good`) | Healthy / normal / in regulation | `operating_state`, grid availability, bus regulation band |
| **Amber** (`warning`) | Derating / drooping / sagged — degraded, not failed | Same classifiers, warning band |
| **Red** (`critical`) | Faulted / tripped / lost / collapsed | Same classifiers, critical band |
| **Neutral gray** | This value does not represent health at all | Values with no pass/fail meaning — e.g. `P_load`, an exogenous demand, not a protected or controlled entity |

The `neutral` role exists specifically because the palette used to have no honest way to represent "this number has no opinion about whether it's good or bad" — before it existed, such values defaulted to green, which silently claimed a health judgment that was never true. **A value that cannot fail should never wear a color that implies it could pass.**

Color is never added for decoration, branding flourish, or visual balance. If a panel looks visually unbalanced without an extra color, the fix is spacing or typography, never an invented hue.

---

## Implementation Contract

- **The Python simulation engine (`src/`) is, and remains, the single source of engineering truth.** No frontend — the current Next.js/React app, or the earlier Streamlit app — recomputes, approximates, or re-derives physics.
- **Frontend presentation code must never recreate engineering physics.** If a visual needs a number the engine doesn't already produce, the fix is to extend the engine's `Telemetry` output, not to approximate the number in presentation code.
- **Every telemetry-driven visual must derive from actual simulation output**, read from a real `Telemetry`/`FlowSnapshot` instance via the backend API — never from a hardcoded example, a placeholder, or an illustrative approximation standing in for real data. Static conceptual/reference content (e.g., System Map category prose) is exempt from this specific bullet by definition — it never claimed to be telemetry — but remains bound by every other rule in this document, and by the clear-labeling requirement in §1/"Engineering Visual Semantics."
- **The Next.js frontend (`frontend/app/`) consumes simulation state through the backend API boundary** (`frontend/app/lib/simulationApi.ts`), not by importing or reimplementing `src/`. This is the current implementation, not a future one — `dashboard/adapters/simulation_adapter.py` was its Streamlit-era predecessor and remains only as historical reference for the same boundary.
- **Presentation logic and engineering logic remain permanently separated**, regardless of which frontend framework renders the presentation layer. This document governs the presentation side only; it has no authority over, and makes no claims about, the physics, scenario logic, or protection thresholds owned by `src/`.

---

## Reference Influences

This system was synthesized from a comparative study of eight public product design languages, chosen for genuine structural relevance to a dense, technical, dark-mode instrument panel — not for brand prestige. **No single one of them is copied.** What follows is the specific principle taken from each; none of their actual palettes, type families, or signature motifs appear in this document.

- **Raycast** — a genuine multi-step dark surface ladder with zero shadow, and the rule that selection/active state should shift which surface tier an element sits on rather than introduce a new color.
- **Linear** — the surface ladder as the *sole* elevation mechanism (independent confirmation of Raycast's approach) and the discipline of "resist a second chromatic accent," stated as a hard rule rather than a habit.
- **NVIDIA** — the explicit rationale for a small, non-zero corner radius reading as "engineering-grade" rather than consumer-soft, and treating color as a scarce, rationed resource rather than a default decoration.
- **ClickHouse** — close canvas/card contrast ("an engineering-grade dim panel, not a loud lift") and the principle of showing real data directly rather than illustrating it.
- **IBM** — a concrete, accessible focus-state pattern (ring plus underline) and a one-accent-color discipline with status kept in a visibly separate palette.
- **Vercel** — the soft/deep variant pattern for a semantic color family, used here only as a structural idea (a tint and a deep step per status role), never its actual consumer-registered palette.
- **HashiCorp** — independent validation that surface-lift elevation (not shadow) and a sub-pill button radius are the correct choices for a technical, non-consumer product.
- **Warp** — further independent confirmation that a tight, near-flat corner radius reads as "instrument," not "app," and strict separation of a technical (monospace) type role from a narrative one.

Where these eight disagreed with each other, the deciding factor was always the central principle at the top of this document — readability and confidence of engineering state — never which brand was more famous or more recent.
