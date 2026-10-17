/** One shared formatter for every `time_s`/`duration_s` value this
 * app displays (SPEC-008 §12, extracted for SPEC-009 §8) -- presentation
 * rounding of an already-correct value, never new wording. */
export function formatSeconds(value: number): string {
  return `${value.toFixed(3)} s`;
}
