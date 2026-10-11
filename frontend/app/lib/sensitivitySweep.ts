import {
  CAPACITANCE_RANGE,
  TIME_CONSTANT_RANGE,
  type ExperimentParams,
} from "../components/ExperimentPanel";
import { fetchLoadStep, type LoadStepResponse } from "./simulationApi";
import { computeTransientMetrics, type TransientMetrics } from "./transientMetrics";

/**
 * Scenario A sensitivity study (SPEC-002): a 1-D sweep of either C_dc
 * or tau_sst, built entirely from repeated existing single-run
 * requests (`fetchLoadStep`) reduced by the existing
 * `computeTransientMetrics`.
 *
 * This module performs no physics. The only arithmetic is the
 * deterministic grid `min + i*(max-min)/4`. Everything except
 * `runSensitivitySweep` is a pure, side-effect-free function so it can
 * be unit-tested later without refactoring.
 */
export type SweepParameter = "capacitance" | "timeConstant";

export const SWEEP_POINT_COUNT = 5;

export interface SweepRange {
  min: number;
  max: number;
}

/** The existing slider range of the swept parameter (not a new range). */
export function rangeFor(parameter: SweepParameter): SweepRange {
  return parameter === "capacitance" ? CAPACITANCE_RANGE : TIME_CONSTANT_RANGE;
}

/**
 * The 5 grid values `min + i*(max-min)/4`, i = 0..4, independent of
 * any slider position. Clamped to `max` only to guarantee, by
 * construction, that floating-point rounding can never push a request
 * past the backend bound.
 */
export function sweepGridValues(range: SweepRange): number[] {
  const values: number[] = [];
  for (let i = 0; i < SWEEP_POINT_COUNT; i++) {
    const value = range.min + (i * (range.max - range.min)) / (SWEEP_POINT_COUNT - 1);
    values.push(Math.min(range.max, value));
  }
  return values;
}

export interface SweepPointPlan {
  /** Value of the swept parameter (F for C_dc, s for tau_sst). */
  value: number;
  isGrid: boolean;
  isCurrent: boolean;
}

/**
 * The runs a sweep needs: the 5 grid points, with the one matching
 * `current` exactly (bit-for-bit, no tolerance) also marked current;
 * if none matches, exactly one extra CURRENT point. Sorted ascending
 * by value; grid values are never moved.
 */
export function planSweepPoints(range: SweepRange, current: number): SweepPointPlan[] {
  const grid = sweepGridValues(range);
  const plans: SweepPointPlan[] = grid.map((value) => ({
    value,
    isGrid: true,
    isCurrent: value === current,
  }));
  if (!grid.includes(current)) {
    plans.push({ value: current, isGrid: false, isCurrent: true });
  }
  return plans.sort((a, b) => a.value - b.value);
}

/** The single-run request for one sweep point: all other parameters
 *  come from the learner's current draft. */
export function requestFor(
  parameter: SweepParameter,
  draft: ExperimentParams,
  value: number,
) {
  return {
    final_fraction: draft.finalFraction,
    capacitance_f: parameter === "capacitance" ? value : draft.capacitanceF,
    time_constant_s: parameter === "timeConstant" ? value : draft.timeConstantS,
  };
}

export interface SweepPointResult extends SweepPointPlan {
  metrics: TransientMetrics;
}

export interface SweepResult {
  parameter: SweepParameter;
  /** The draft the sweep was run with (other parameters held fixed). */
  draft: ExperimentParams;
  points: SweepPointResult[];
}

/** Role label shown in the table: "GRID", "CURRENT" or "GRID · CURRENT". */
export function roleLabel(point: SweepPointPlan): string {
  if (point.isGrid && point.isCurrent) return "GRID · CURRENT";
  return point.isCurrent ? "CURRENT" : "GRID";
}

/** Chart data: swept value on x, maximum V_dc deviation [%] on y. */
export function chartData(points: SweepPointResult[]) {
  return {
    x: points.map((p) => p.value),
    y: points.map((p) => p.metrics.maxDeviationPercent),
  };
}

/**
 * Runs the sweep: one existing `fetchLoadStep` call per point, each
 * reduced by the existing `computeTransientMetrics`. Sequential, so
 * the backend sees the same request pattern as repeated manual runs.
 */
export async function runSensitivitySweep(
  parameter: SweepParameter,
  draft: ExperimentParams,
  fetchRun: (request: ReturnType<typeof requestFor>) => Promise<LoadStepResponse> = fetchLoadStep,
): Promise<SweepResult> {
  const current = parameter === "capacitance" ? draft.capacitanceF : draft.timeConstantS;
  const plans = planSweepPoints(rangeFor(parameter), current);
  const points: SweepPointResult[] = [];
  for (const plan of plans) {
    const response = await fetchRun(requestFor(parameter, draft, plan.value));
    const metrics = computeTransientMetrics(response);
    if (!metrics) throw new Error("Sweep point returned no load-step event");
    points.push({ ...plan, metrics });
  }
  return { parameter, draft, points };
}
