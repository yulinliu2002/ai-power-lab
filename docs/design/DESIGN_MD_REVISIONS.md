# Proposed bounded DESIGN.md revisions (draft, not applied), revised after Codex review

`DESIGN.md` is unchanged on this branch. These replacement texts are the only revisions Signal Path needs; they land in the foundation PR after review.

**§6 Typography: replace the tier table with:**

| Tier | Token | Size | Weight | Treatment |
|---|---|---|---|---|
| Page title | `text-page-title` | 28px (mobile) to 40px (from `sm`) | 600 | Plex Sans, sentence case, -0.02em, one per page |
| Section / panel heading | `text-heading` | 14 to 18px | 600 | Plex Sans, sentence case, `text-primary` (replaces the uppercase 11.5px muted tier) |
| Body / explainer | `text-body` | 13 to 14px (lede up to 16px, once per page) | 400 | `text-secondary` |
| Metadata / label / unit | `text-meta` | 10.5 to 12px | 500 to 600 | Plex Mono uppercase for tags and units; Plex Sans 12px for plain labels |

The "homepage headline" exception is removed (the page-title tier covers it). Weight never exceeds 700.

**§6 and §22 mono rule: replace "Keep IBM Plex Mono exclusive to live/tabular/code data" with:** "Plex Mono is used for live or tabular values, equations and code, and for concise
instrument metadata (tags, units, chart ticks, step and area numbering). It is never used for running prose or headings."

**§12 Navigation: add after the nav paragraph:** "A single signal-path rail may sit under the nav. It draws the selected architecture's own main power path from the
System Map data and never one universal chain. An SST node appears only in the Conceptual MV-to-800 VDC via SST architecture and is labeled conceptual. Pages that run
the simulation pin the rail to that architecture and mark the simulated slice with dashed node borders; the page's Basis & limits panel carries the legend (dashed nodes
are simulated; stages the model does not represent, such as rack DC-DC conversion, are named as not modeled). Focus is shown by surface tier and weight, never color. The rail
exposes the node sequence in its accessible name. On narrow screens it collapses to a label row and a dot track."

**§1 and new §: Basis & limits panel.** "Mandatory spec disclosures are visible on initial load, verbatim, in a structured panel (mono tag plus text). They are never collapsed,
paraphrased or hidden behind an interaction. Presentation may change; wording and visibility may not. Each page imports the canonical constants of its spec (SPEC-011 `DISCLOSURES`,
SPEC-012 `LEARN_DISCLOSURES`)."

**§3, §5, §9:** promote `surface-inset` (#0d131a) and `hairline-strong` to implemented. A selected control changes surface tier and border to `hairline-strong`; no shadow and no ring.
The §18 keyboard focus outline (2px `secondary`) is unchanged and applies in addition.

**§4 / §16 evidence labels:** evidence labels render as neutral chips with a glyph (square public fact, circle illustrative assumption, diamond model output, triangle emerging)
plus the canonical label text. The existing `EvidenceTag` gains the glyph as a presentation prop; its basis, references and reference destinations are unchanged. Evidence never uses a status color.

**§21 Responsive:** the four learning areas must be readable at 390px with no horizontal page scroll; wide tables and charts scroll inside a named, keyboard-focusable
container with a visible hint, and chart text never renders below 11px. The Advanced Sandbox remains desktop-first and keeps SPEC-014's no-clipping floor.

**§18 contrast:** essential text (including chart reference-line labels) uses `text-secondary` or brighter; `muted` stays limited to non-essential decoration.

Unchanged: tokens, dark canvas, one accent, four status roles, 4px radius, no gradient or shadow, no animation, Plex families, tabular numerics, the Implementation Contract and Engineering Visual Semantics.
