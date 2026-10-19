// Design-lab check: decimation preserves global extrema and endpoints.
// Run: node --experimental-strip-types scripts/check-decimate.mts
// @ts-expect-error node strip-types needs the .ts extension; tsc does not allow it
import { decimateMinMax } from "../app/design-lab/decimate.ts";

function check(name: string, y: number[]) {
  const x = y.map((_, i) => i * 0.001);
  const d = decimateMinMax(x, y, 700);
  const ok =
    Math.min(...d.ys) === Math.min(...y) &&
    Math.max(...d.ys) === Math.max(...y) &&
    d.xs[0] === x[0] &&
    d.xs[d.xs.length - 1] === x[x.length - 1] &&
    d.xs.length <= 800;
  console.log(`${ok ? "PASS" : "FAIL"} ${name}: ${y.length} -> ${d.xs.length} points, min ${Math.min(...d.ys)}/${Math.min(...y)}, max ${Math.max(...d.ys)}/${Math.max(...y)}`);
  if (!ok) process.exitCode = 1;
}

// Codex counterexample: 1401 samples, single minimum at index 1.
const spike = Array.from({ length: 1401 }, () => 800);
spike[1] = 100;
check("single-sample minimum at index 1", spike);

// Step discontinuity and isolated spike.
check("step", Array.from({ length: 90000 }, (_, i) => (i < 14446 ? 800 : 0)));
const s2 = Array.from({ length: 5000 }, (_, i) => Math.sin(i / 50));
s2[2503] = 5;
check("isolated spike", s2);

if (process.argv[2]) {
  const res = await fetch(process.argv[2]);
  const data = await res.json();
  for (const k of ["v_dc_v", "temperature_c", "p_sst_w", "p_load_w"] as const) check(`api ${k}`, data.timeseries[k]);
}
