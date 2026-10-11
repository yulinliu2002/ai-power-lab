/**
 * Raw color values for the inline SVG schematic.
 *
 * SVG presentation attributes are rendered in the same document as the
 * rest of the page, so they take CSS custom properties directly --
 * these strings are `var(--color-*)` references into the tokens
 * already defined once in globals.css (DESIGN.md section 3/4), not a
 * second copy of the palette.
 */

export const SVG_COLOR = {
  surface: "var(--color-surface)",
  surfaceRaised: "var(--color-surface-raised)",
  textSecondary: "var(--color-text-secondary)",
  textPrimary: "var(--color-text-primary)",
  muted: "var(--color-muted)",
  hairline: "var(--color-hairline)",
  accent: "var(--color-accent)",
  good: "var(--color-status-good)",
  warning: "var(--color-status-warning)",
  critical: "var(--color-status-critical)",
  neutral: "var(--color-status-neutral)",
  /** Pixso Concept 03's fixed two-hue topology/state language -- cyan
   * for nominal electrical structure, amber reserved for the E (stored
   * energy) channel and real transient deficit. Scoped separately from
   * `accent`/status roles above so this one redesigned component
   * (PowerFlowSchematic) doesn't change any other component's palette. */
  schematicCyan: "var(--color-schematic-cyan)",
  schematicAmber: "var(--color-schematic-amber)",
} as const;

export const STATUS_SVG_COLOR: Record<string, string> = {
  good: SVG_COLOR.good,
  warning: SVG_COLOR.warning,
  critical: SVG_COLOR.critical,
  neutral: SVG_COLOR.neutral,
};
