"use client";

import { useRef, useState } from "react";

import {
  roleLabel,
  runSensitivitySweep,
  type SweepParameter,
  type SweepResult,
} from "../lib/sensitivitySweep";
import type { ExperimentParams } from "./ExperimentPanel";
import { SweepChart } from "./SweepChart";

interface SensitivityStudyProps {
  /** The learner's current draft; read only at the moment RUN is clicked. */
  draft: ExperimentParams;
}

const PARAMETER_LABEL: Record<SweepParameter, string> = {
  capacitance: "DC BUS CAPACITANCE (C_dc)",
  timeConstant: "SST RESPONSE TIME (τ_sst)",
};

/** Table display -- full precision, unit included. C_dc needs 5
 *  decimals: the 5 grid values (0.005 + i*0.01875 F) include 0.02375 F
 *  and 0.06125 F, which 3 decimals would round onto neighbouring
 *  slider values. (Chart ticks may abbreviate -- see `formatTick`.) */
function formatValue(parameter: SweepParameter, value: number): string {
  return parameter === "capacitance"
    ? `${value.toFixed(5)} F`
    : `${(value * 1000).toFixed(2)} ms`;
}

/** Chart x-tick display -- numbers only (the axis label supplies the
 *  unit once), and shorter, since up to six of these must fit across
 *  one plot width without colliding. Unlike `formatValue`, this takes
 *  a value already converted to display units (ms for timeConstant --
 *  see the `points` mapping below, which does that conversion once
 *  before `SweepChart` ever calls this as `xTickFormat`), so it must
 *  NOT convert again. */
function formatTick(parameter: SweepParameter, value: number): string {
  return parameter === "capacitance" ? value.toFixed(3) : value.toFixed(1);
}

/**
 * Scenario A sensitivity study: sweeps exactly one of C_dc / tau_sst
 * over its slider range (5 grid points, plus a CURRENT point when the
 * draft value is not a grid value), holding everything else at the
 * draft. Every point is an ordinary single-run request; this component
 * owns its own results and never touches the single-run view.
 */
export function SensitivityStudy({ draft }: SensitivityStudyProps) {
  const [open, setOpen] = useState(false);
  const [parameter, setParameter] = useState<SweepParameter>("capacitance");
  const [result, setResult] = useState<SweepResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  // Choosing the other parameter replaces (here: clears) the displayed
  // sweep -- only one sweep is ever shown.
  const selectParameter = (next: SweepParameter) => {
    if (next === parameter) return;
    requestId.current += 1; // discard any in-flight sweep
    setParameter(next);
    setResult(null);
    setError(null);
    setIsRunning(false);
  };

  const run = () => {
    const id = ++requestId.current;
    setIsRunning(true);
    setError(null);
    runSensitivitySweep(parameter, draft)
      .then((sweep) => {
        if (id === requestId.current) setResult(sweep);
      })
      .catch((e: unknown) => {
        if (id === requestId.current) {
          setResult(null);
          setError(e instanceof Error ? e.message : "Unknown error");
        }
      })
      .finally(() => {
        if (id === requestId.current) setIsRunning(false);
      });
  };

  return (
    <div className="flex flex-col gap-1.5 border-t border-hairline pt-2">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 self-start font-sans text-[10.5px] font-semibold uppercase tracking-[0.04em] text-muted"
      >
        <span className="font-mono text-[12px] leading-none">{open ? "−" : "+"}</span>
        Sensitivity Study
      </button>
      {open && (
        <section className="flex flex-col gap-2 border border-hairline bg-surface px-4 py-2">
          <span className="font-sans text-[11.5px] font-semibold uppercase tracking-[0.04em] text-muted">
            SENSITIVITY STUDY
          </span>
          <p className="font-sans text-[12px] leading-snug text-secondary">
            Re-runs this same load step at 5 evenly spaced values across the swept
            parameter&rsquo;s full slider range (plus your current value), holding every other
            setting at the current experiment values. The DC link must supply the energy deficit
            ΔE = ∫(P_load − P_sst) dt; C_dc sets how far V_dc moves per joule, and τ_sst sets how
            long the mismatch stays open.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            {(Object.keys(PARAMETER_LABEL) as SweepParameter[]).map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => selectParameter(p)}
                disabled={isRunning}
                aria-pressed={parameter === p}
                className={`rounded border px-3 py-1.5 font-sans text-[11px] font-semibold uppercase tracking-[0.04em] disabled:cursor-not-allowed disabled:opacity-50 ${
                  parameter === p
                    ? "border-secondary bg-surface-raised text-primary"
                    : "border-hairline bg-surface text-secondary"
                }`}
              >
                {PARAMETER_LABEL[p]}
              </button>
            ))}
            <button
              type="button"
              onClick={run}
              disabled={isRunning}
              className="ml-auto rounded border border-accent bg-accent px-3 py-1.5 font-sans text-[11px] font-semibold uppercase tracking-[0.04em] text-primary disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isRunning ? "Running…" : "Run Sweep"}
            </button>
          </div>
          {error && <span className="font-mono text-[10px] text-status-critical">{error}</span>}
          {result && <SweepResults result={result} />}
          <p className="font-mono text-[9px] leading-snug text-muted">
            Toy-model disclaimer: all values here are outputs of this repository&rsquo;s simplified,
            average-value, lumped-parameter educational model (no switching dynamics, constant
            efficiency, single-capacitance bus, no cabling impedance). They are illustrative only
            &mdash; not calibrated, validated, or representative of any real commercial SST,
            DC-link design, or data-center power system. Trends are checked only against named
            test fixtures.
          </p>
        </section>
      )}
    </div>
  );
}

function SweepResults({ result }: { result: SweepResult }) {
  const { parameter, points } = result;
  const fixedNote =
    parameter === "capacitance"
      ? `τ_sst = ${(result.draft.timeConstantS * 1000).toFixed(0)} ms`
      : `C_dc = ${result.draft.capacitanceF.toFixed(3)} F`;
  const xUnit = parameter === "capacitance" ? "F" : "ms";

  return (
    <div className="flex flex-col gap-2">
      <SweepChart
        title={`Max V_dc deviation vs ${PARAMETER_LABEL[parameter]}`}
        xAxisLabel={`${PARAMETER_LABEL[parameter]}, ${xUnit}`}
        yUnit="%"
        xTickFormat={(v) => formatTick(parameter, v)}
        points={points.map((p) => ({
          x: parameter === "timeConstant" ? p.value * 1000 : p.value,
          y: p.metrics.maxDeviationPercent,
          isGrid: p.isGrid,
          isCurrent: p.isCurrent,
        }))}
      />
      <span className="font-mono text-[10px] text-muted">
        Held fixed: {fixedNote}, final load = {(result.draft.finalFraction * 100).toFixed(0)}% of
        rated.
      </span>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse font-mono text-[10.5px] tabular-nums text-secondary">
          <thead>
            <tr className="border-b border-hairline text-left font-sans text-[9.5px] uppercase tracking-[0.04em] text-muted">
              <th className="py-1 pr-3 font-semibold">Point</th>
              <th className="py-1 pr-3 font-semibold">{PARAMETER_LABEL[parameter]}</th>
              <th className="py-1 pr-3 font-semibold">Min V_dc [V]</th>
              <th className="py-1 pr-3 font-semibold">Max dev [V]</th>
              <th className="py-1 pr-3 font-semibold">Max dev [%]</th>
              <th className="py-1 pr-3 font-semibold">Recovery</th>
              <th className="py-1 font-semibold">Energy deficit [kJ]</th>
            </tr>
          </thead>
          <tbody>
            {points.map((p) => (
              <tr
                key={p.value}
                className={`border-b border-hairline ${p.isCurrent ? "bg-surface-raised text-primary" : ""}`}
              >
                <td className="py-1 pr-3">{roleLabel(p)}</td>
                <td className="py-1 pr-3">{formatValue(parameter, p.value)}</td>
                <td className="py-1 pr-3">{p.metrics.minVdcV.toFixed(1)}</td>
                <td className="py-1 pr-3">{p.metrics.maxDeviationV.toFixed(1)}</td>
                <td className="py-1 pr-3">{p.metrics.maxDeviationPercent.toFixed(2)}</td>
                <td className="py-1 pr-3">
                  {p.metrics.recoveryElapsedS === null
                    ? "did not settle"
                    : `${(p.metrics.recoveryElapsedS * 1000).toFixed(0)} ms`}
                </td>
                <td className="py-1">{p.metrics.energyDeficitKj.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
