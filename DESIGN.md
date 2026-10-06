# AI Power Lab — Design System

**Status:** locked visual direction for the current Streamlit implementation and any future frontend. This document is a constitution, not a mood board — when a future change conflicts with it, the change is wrong until this document is deliberately revised, not the other way around.

## Central Principle

> AI Power Lab is an instrument panel, not a dashboard.
> The product is the engineering state and telemetry; the interface exists to make that state readable quickly and confidently.

Every rule in this document answers to that sentence. If a future decision doesn't make the system's state faster or more confident to read, it doesn't belong here, no matter how polished it looks in isolation.

---

## 1. Visual Philosophy

AI Power Lab is built to feel like the software an operator keeps open at a desk, not software built to be screenshotted for a landing page. That distinction drives everything else in this document:

- The interface is **flat**. Depth comes from a surface hierarchy and border weight, never from shadow, blur, or glassmorphism.
- The interface is **restrained**. One accent color. Four status roles. Nothing else is chromatic.
- The interface is **dense but legible**. Information is close together, not spread out to look generous — generous spacing is a marketing convention, not an operations convention.
- The interface is **honest**. Every color, every number, every animation on screen is derived from real simulated engineering state. Nothing is decorative data.
- The interface is **dark, permanently**. There is no light mode to maintain parity with, because a mission-critical console is not a brand surface that needs to flatter a product screenshot in daylight.

This system was synthesized from a comparative study of real product design languages (see **Reference Influences** below) — it borrows recurring *principles* that independently appeared across unrelated companies, never a single brand's signature look. Nothing here is "inspired by" one product; it is AI Power Lab's own answer to problems those products also had to solve.

## 2. Product Identity

**Name:** AI Power Lab
**Subtitle / system identifier:** SST / 800 VDC AI Power Infrastructure
**Domain:** an educational, system-level digital twin of a solid-state-transformer-powered, 800 VDC AI data-center power chain (MV Grid → SST → 800 VDC Bus → AI Compute Load).
**Register:** serious engineering software, not a startup product. The identity mark is a small, precise wordmark — never a logo mark, never an icon, never a gradient.

## 3. Color Tokens

The full token set is already implemented in `dashboard/components/palette.py` (`CHROME`) and mirrored in `.streamlit/config.toml`. This document is the record of *why* those values are what they are, and the contract for any future implementation (React included) to match them exactly — color values are not restyled per platform.

| Token | Value | Role |
|---|---|---|
| `canvas` | `#0a0e14` | Page background — the deepest tier |
| `surface` | `#121820` | Panel background — the default resting surface |
| `surface-raised` | `#1a232e` | Elevated / focused panel |
| `surface-inset` *(planned)* | `#0d131a` | Sunken numeric-readout background; not yet implemented — see §5 |
| `text-primary` | `#e7edf3` | Primary reading text and live values |
| `text-secondary` | `#aab4bd` | Labels, captions, explanatory text |
| `muted` | `#6b7680` | De-emphasized metadata, units, the neutral status role |
| `hairline` | `#24303c` | Default 1px border/divider |
| `hairline-strong` *(planned)* | `rgba(226,232,240,0.22)` | Emphasis border without introducing a color — not yet implemented |

There is exactly **one accent color**, reserved for one meaning:

| Token | Value | Meaning |
|---|---|---|
| `accent` | `#3987e5` | "Energized / actively flowing / process in motion." Never used for selection, branding flourish, or decoration. |

No second chromatic accent exists anywhere in this system, including for focus or selection states (see §14, §19). Adding one requires revising this document first.

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
- **IBM Plex Mono** — reserved exclusively for live, tabular, or code-like data. Never used as a "technical-looking" costume for ordinary prose.

Hierarchy is built primarily from **weight**, not size — the earlier implementation accumulated twelve distinct font sizes by accident; the fix is a small, deliberate scale where weight does most of the differentiating work:

| Tier | Size | Weight | Treatment |
|---|---|---|---|
| App identity | 20–22px | 700 | Set once, at the top of the shell — never a web-page-sized headline |
| Panel / section heading | 11.5px | 600 | Uppercase, `+0.04em` tracking, muted color |
| Body / explainer text | 12–13px | 400 | `text-secondary` — always visually subordinate to data |
| Metadata / label / unit | 10.5–11px | 500–600 | Uppercase or mono, never prose weight |

Display weight never exceeds 700 anywhere in the product. A heavier weight reads as marketing emphasis, not instrument precision.

## 7. Telemetry / Numeric Typography

The single most load-bearing typographic rule in the system: **every number that represents a live simulated value is IBM Plex Mono with tabular numerals, full stop.** This prevents digit-width jitter on every tick and is the one place monospace is not optional.

- Primary KPI values: 20–24px / 600 / `text-primary`, with their unit suffix rendered smaller (11–12px) and in `muted`, baseline-aligned — the number dominates, the unit does not compete with it.
- Secondary numeric values (schematic stage values): 14–15px / 600, the existing `.console-mono` tier.
- Numbers are never italicized, never a non-tabular digit face, never animated with easing — a value updates to its new reading instantly, because an eased number is a number lying about when the reading actually changed.

## 8. Spacing Scale

A 4px base unit: `4 / 8 / 12 / 16 / 24 / 32px`. Panel padding stays in the 12–16px range. Row spacing inside a dense panel (KPI tiles, stat rows) targets 8px. Section-to-section rhythm uses 24–32px, through exactly one separating mechanism per transition (whitespace *or* a divider, never both stacked to do the same job). This is deliberately tighter than a marketing site's rhythm — density is a feature here, not a defect to soften.

## 9. Border Hierarchy

Three strengths, each with exactly one meaning:

1. **`hairline`** (1px, `#24303c`) — the default separator for every panel, card, and divider in the product.
2. **`hairline-strong`** *(planned)* — emphasis without introducing a color, for a panel that needs to stand out without implying a status judgment.
3. **Status border** (2px, one of the four STATUS colors) — the *only* border that ever carries meaning. It appears exclusively on an entity that is actually, currently, in that state. A 1px neutral border escalating to 2px and a status color is the entire alarm-escalation vocabulary of this system (see §16).

No panel, card, list item, or alert ever uses a colored left- or right-border accent above 1px as a decorative device — that pattern reads as generic templated chrome, and this product has already removed the one place it crept in (the former six-row status panel's colored left bars, retired when the KPI strip replaced it).

## 10. Corner Radius

4px, flat, everywhere, no exceptions above 8px anywhere in product chrome. This number is small on purpose: a larger, softer radius reads as consumer software; a sharp one reads as engineered. Circular elements (status dots) are the only shapes that are ever fully round.

## 11. Elevation

There is no shadow-based elevation system in this product, and there will not be one. Elevation is the surface ladder (§5) plus border weight (§9). This is a deliberate, permanent constraint, not a placeholder for a future shadow system.

## 12. Navigation

Left rail, icon + label, the active item marked by sitting on the `surface-raised` tier — not by a color change. Two items are already identified as not yet meeting this bar: the current navigation icons are full-color emoji, which is the single largest remaining violation of the "one accent, status reserved" rule in the shipped product, and should be replaced with monochrome glyphs or a left accent-bar consistent with the KPI-tile language. This is documented here as a known gap, not yet corrected.

## 13. KPI Tiles

The compact, flat instrument tile is the system's primary way of presenting a headline telemetry value: uppercase label, dominant tabular value, de-emphasized unit, and a top border that is 1px neutral by default and escalates to 2px in a status color only when that specific value's role leaves good/neutral. Tiles never use a drop shadow, a rounded-pill shape, or a decorative icon. A tile's color state is always computed from the same shared status classifier the power-flow schematic uses — never judged independently.

## 14. Controls

One button language: ghost/outline by default, 4px radius, `hairline` border, `surface-raised` background. Exactly one filled exception exists per screen — the single primary action (e.g. Play/Pause on the Simulator), using `accent` blue. Selection and hover states change the surface tier the control sits on, not its color — color is reserved for status alone, never repurposed to mean "you're interacting with this."

## 15. Charts

Charts share the same dark canvas, the same hairline gridlines at low opacity, and the same panel-header typography as every other instrument on the page — a chart is another gauge in the cluster, not an embedded third-party widget. Chart chrome that reads as "generic web tool" (a visible toolbar/modebar, oversized titles) is suppressed. The guiding rule, borrowed in spirit from this study's strongest data-product reference: **show the real data, never illustrate it.** Every trace, marker, and threshold line on a chart is computed from actual simulated telemetry.

## 16. Alarm / Status Communication

Status is always communicated through at least two channels at once — color is never the only signal (a dot, a label, and a border weight all move together). The vocabulary is fixed and small:

- **1px neutral border, no colored dot** — this entity is fine.
- **2px warning border + amber dot + label** — degraded, worth attention, not yet a fault.
- **2px critical border + red dot + label** — faulted; this is the loudest state the system has, and it is reserved for genuine faults only.
- **Neutral role** — explicitly *not* a health judgment (see Engineering Visual Semantics, below).

**Planned, not yet implemented:** a distinct "transient" treatment — a value actively moving toward a new setpoint after a real engineering event (e.g. just after a load step), shown as a brief `accent`-blue pulse rather than a status color, so the system never looks alarmed simply because it is correctly, dynamically responding to a real input.

## 17. Power-Flow Schematic

The schematic (`dashboard/components/schematic.py`) is the product's single most domain-specific element and the clearest expression of the central principle: every value on it — stage border color, flow-line thickness, flow-line animation speed — is computed directly from one instant of real `Telemetry`, never from a styling choice. It intentionally does not attempt switching-level or 3D hardware realism; it is a schematic, not a rendering. This component's visual design does not change when other parts of the interface do — it is the standard the rest of the interface is held to, not a target for restyling.

## 18. Focus / Accessibility States

**Planned, not yet implemented — a known, named gap.** No `:focus-visible` styling currently exists anywhere in the shipped CSS; keyboard-focus state is whatever the underlying framework provides unmodified. The committed fix, once implemented: every focusable control receives a 2px `accent`-colored focus ring plus a 1px hairline underline on the control itself, so focus is visible through two channels, not one, and never only through a color that a color-blind or low-contrast viewer might not reliably perceive. Contrast has been independently verified clean elsewhere in the product (every sampled text/background pair in the live DOM measured 9:1 or better against WCAG AA's 4.5:1 floor) — this gap is specifically about focus visibility, not contrast.

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

AI Power Lab is a desktop-first instrument panel; this is a deliberate scope decision, not an oversight. A reasonable minimum: the KPI strip wraps to fewer tiles per row and the hero schematic/status layout stacks vertically below a defined breakpoint. True mobile-optimized SCADA operation is out of scope and should not drive any decision in this document.

## 22. Explicit Do / Don't Rules

**Do:**
- Derive every color on screen from real engineering state or from this document's fixed token set — nothing else.
- Keep status color to the four STATUS roles, applied through the shared classifier functions, never re-judged per surface.
- Use weight and the surface ladder to establish hierarchy before reaching for size or color.
- Keep IBM Plex Mono exclusive to live/tabular/code data.
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

---

## Engineering Visual Semantics

**Visual state must always derive from real engineering state. This is the single non-negotiable rule in this document.** A color, animation, or status label that doesn't trace back to an actual value in a `Telemetry` object is a defect, regardless of how it looks.

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

- **The Python simulation engine (`src/`) is, and remains, the single source of engineering truth.** No frontend — Streamlit today, React/Next.js in any future iteration — recomputes, approximates, or re-derives physics. `dashboard/adapters/` already enforces this boundary for the current implementation; any future frontend enforces the equivalent boundary against an API, not against reimplemented logic.
- **Frontend presentation code must never recreate engineering physics.** If a visual needs a number the engine doesn't already produce, the fix is to extend the engine's `Telemetry` output, not to approximate the number in presentation code.
- **Every telemetry-driven visual must derive from actual simulation output**, read from a real `Telemetry`/`FlowSnapshot` instance — never from a hardcoded example, a placeholder, or an illustrative approximation standing in for real data.
- **A future React/Next.js frontend consumes simulation state through an API boundary**, not by importing or reimplementing `src/`. The existing `dashboard/adapters/simulation_adapter.py` functions are already shaped close to what that API's endpoints would look like — a sign the engine/presentation boundary was drawn correctly in V1.1.
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
