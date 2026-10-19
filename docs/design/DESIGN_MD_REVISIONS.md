# Proposed bounded DESIGN.md revisions (draft, not applied)

`DESIGN.md` is unchanged on this branch. These are the only revisions the Signal Path direction needs. They land in the
foundation PR (see `INTEGRATION_PLAN.md`) after human review of this exact text.

| # | Section | Revision | Source |
|---|---|---|---|
| R1 | §6 Typography | Add a `text-page-title` tier: 28px (mobile) to 40px (desktop), weight 600, tracking -0.02em, one per page, Plex Sans. Replaces the single "homepage headline" exception. The 700 weight ceiling stays. | D1 |
| R2 | §6 Typography | Page and section headings become sentence-case Plex Sans, 14 to 18px, weight 600 (replaces the uppercase 11.5px muted heading tier for these). Uppercase mono stays for metadata tags and short labels only. Mono is retained for engineering values, equations and concise metadata. | D2 |
| R3 | §12 Navigation | Allow one signal-path rail row under the nav. Rules: it draws the selected architecture's own main path from the System Map data; never one universal chain; an SST node appears only in the SST architecture and is labeled conceptual; pages that run the simulation pin it to the SST architecture and mark the simulated slice (dashed bracket plus a text note); focus is shown by surface tier and weight, never color; on mobile it collapses to a label row and a dot track. | D3 |
| R4 | new §, with §1 "Conceptual Educational Diagrams" | "Basis & limits" panel: mandatory spec disclosures are visible on initial load, verbatim, never collapsible or hidden behind an interaction. Structure: mono tag plus text. Presentation may change; text and visibility may not. | D4 |
| R5 | §3, §5, §9 | Promote the planned `surface-inset` (#0d131a) and `hairline-strong` to implemented. A selected control changes border to `hairline-strong` and surface tier (no shadow, no ring). | prototype |
| R6 | §4/§16 or new | Evidence labels render as neutral chips: glyph (square, circle, diamond, triangle) plus text; evidence is not health and never uses a status color. The existing `EvidenceTag` adopts the glyphs; it is not forked. | prototype |
| R7 | §21 Responsive | Learning pages (the four areas) must be readable at 390px with no horizontal scroll. The Advanced Sandbox remains desktop-first. | D3 mobile |

Unchanged: tokens, dark canvas, one accent, four status roles, 4px radius, no gradient or shadow, no animation, Plex families,
tabular mono numerics, the Implementation Contract, and the Engineering Visual Semantics rule.
