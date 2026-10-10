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
  hairline: "var(--color-hairline)",
  accent: "var(--color-accent)",
  good: "var(--color-status-good)",
  warning: "var(--color-status-warning)",
  critical: "var(--color-status-critical)",
  neutral: "var(--color-status-neutral)",
} as const;

export const STATUS_SVG_COLOR: Record<string, string> = {
  good: SVG_COLOR.good,
  warning: SVG_COLOR.warning,
  critical: SVG_COLOR.critical,
  neutral: SVG_COLOR.neutral,
};
