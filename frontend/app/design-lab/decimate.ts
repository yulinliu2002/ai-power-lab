/**
 * Presentation-only down-sampling for drawing long series.
 *
 * Invariant (checked by scripts/check-decimate.mts): the first sample, the
 * last sample, and the minimum and maximum of every bucket are kept, so
 * the drawn series has exactly the same global minimum and maximum as the
 * full series, and a step or discontinuity is never smoothed away. No
 * value is interpolated or recomputed.
 */
export function decimateMinMax(
  x: readonly number[],
  y: readonly number[],
  maxPoints = 800,
): { xs: number[]; ys: number[] } {
  const n = x.length;
  if (n <= maxPoints) return { xs: [...x], ys: [...y] };
  const buckets = Math.max(1, Math.floor(maxPoints / 4));
  const size = n / buckets;
  const keep = new Set<number>([0, n - 1]);
  for (let b = 0; b < buckets; b++) {
    const lo = Math.floor(b * size);
    const hi = Math.min(n - 1, Math.floor((b + 1) * size) - 1);
    let iMin = lo;
    let iMax = lo;
    for (let i = lo; i <= hi; i++) {
      if (y[i] < y[iMin]) iMin = i;
      if (y[i] > y[iMax]) iMax = i;
    }
    keep.add(lo).add(hi).add(iMin).add(iMax);
  }
  const idx = [...keep].sort((a, b) => a - b);
  return { xs: idx.map((i) => x[i]), ys: idx.map((i) => y[i]) };
}
