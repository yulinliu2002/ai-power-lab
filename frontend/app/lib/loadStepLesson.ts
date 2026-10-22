/**
 * Load Step lesson (SPEC-012 amendment A2, milestone M1): authored prose and
 * the small read-only helpers behind the interactive Predict / Discover /
 * Explain / Apply flow for the `load_step` case only.
 *
 * Prose here is static and number-free (SPEC-012 R6); every number the
 * learner sees comes from the live run. The helpers only read the existing
 * response and `computeTransientMetrics`: no physics, no new calculation of
 * model state. Units: seconds, volts, watts in the response; kW for display
 * (converted at the presentation boundary, like `transientMetrics.ts`).
 */

import type { LoadStepResponse } from "./simulationApi";
import type { TransientMetrics } from "./transientMetrics";

export type PredictionId = "falls-recovers" | "rises" | "flat" | "falls-stays";

export const PREDICTION_OPTIONS: ReadonlyArray<{ id: PredictionId; label: string; reasoning: string }> = [
  {
    id: "falls-recovers",
    label: "It falls first, then returns toward its reference.",
    reasoning:
      "This matches the cause chain: delivery lags demand, the bus supplies the gap and falls, then the controller adds corrective power above demand, so delivery overtakes demand and the stored energy is refilled.",
  },
  {
    id: "rises",
    label: "It rises, because more demand pulls more power into the bus.",
    reasoning:
      "Demand does not push power in. Delivered power follows its target with a lag, and the bus supplies whatever delivery does not cover, so stored energy drops first.",
  },
  {
    id: "flat",
    label: "It stays put, because the converter follows demand immediately.",
    reasoning:
      "That would need an instant converter. In this model delivered power follows its target only with a first-order lag, so a gap opens at the step.",
  },
  {
    id: "falls-stays",
    label: "It falls and stays down unless something outside the chain helps.",
    reasoning:
      "Falling is right. Whether it stays down depends on the controller and on headroom: here the controller adds a corrective power above demand while the voltage is below its reference and the converter can deliver it, so delivery overtakes demand and refills the bus. With less headroom or saturation that recovery would not be guaranteed, which is why this run shows recovery for this model and these illustrative values only.",
  },
];

export type ObservedOutcome = "falls-recovers" | "rises" | "flat" | "falls-stays";

/**
 * Classifies what the live run did, from fields `computeTransientMetrics`
 * already derives: a minimum below the reference, a recovery time, and the
 * direction of the largest deviation. It adds no threshold of its own.
 */
export function observedOutcome(metrics: TransientMetrics, voltageReferenceV: number): ObservedOutcome {
  if (metrics.minVdcV < voltageReferenceV) {
    return metrics.recoveryTimeS !== null ? "falls-recovers" : "falls-stays";
  }
  return metrics.maxDeviationIsAbove ? "rises" : "flat";
}

export const OBSERVED_TEXT: Record<ObservedOutcome, string> = {
  "falls-recovers": "The bus voltage fell below its reference and then returned to the recovery band.",
  "falls-stays": "The bus voltage fell below its reference and did not return to the recovery band before the run ended.",
  rises: "The bus voltage went above its reference and never fell below it.",
  flat: "The bus voltage never left its reference.",
};

/** Plain-language state of the energy balance at the cursor, from the sign of P_sst - P_load only. */
export type PhaseId = "before" | "draining" | "refilling" | "settled" | "balanced";

export function phaseAt(data: LoadStepResponse, metrics: TransientMetrics, index: number): PhaseId {
  const t = data.timeseries;
  if (t.time_s[index] < metrics.eventTimeS) return "before";
  if (metrics.recoveryTimeS !== null && t.time_s[index] >= metrics.recoveryTimeS) return "settled";
  const mismatch = t.p_sst_w[index] - t.p_load_w[index];
  if (mismatch < 0) return "draining";
  if (mismatch > 0) return "refilling";
  return "balanced";
}

export const PHASE_TEXT: Record<PhaseId, { title: string; body: string }> = {
  before: {
    title: "Before the step",
    body: "Delivery matches demand, so the stored energy is not changing and the voltage sits at its reference.",
  },
  draining: {
    title: "Demand exceeds delivery",
    body: "The bus supplies the gap, so its stored energy and voltage are falling (dE/dt = P_sst - P_load is negative).",
  },
  refilling: {
    title: "Delivery exceeds demand",
    body: "The controller has pushed delivery above demand, so the surplus is refilling the stored energy and the voltage is rising.",
  },
  balanced: {
    title: "Delivery equals demand",
    body: "The stored energy is momentarily not changing.",
  },
  settled: {
    title: "Settled",
    body: "From here the voltage stays inside the recovery band for the rest of the run.",
  },
};

export interface CursorReadout {
  timeS: number;
  vdcV: number;
  pLoadKw: number;
  pSstKw: number;
  pTargetKw: number;
  mismatchKw: number;
}

/** Values already in the response at one sample, in display units. */
export function readoutAt(data: LoadStepResponse, index: number): CursorReadout {
  const t = data.timeseries;
  return {
    timeS: t.time_s[index],
    vdcV: t.v_dc_v[index],
    pLoadKw: t.p_load_w[index] / 1e3,
    pSstKw: t.p_sst_w[index] / 1e3,
    pTargetKw: t.p_target_w[index] / 1e3,
    mismatchKw: (t.p_sst_w[index] - t.p_load_w[index]) / 1e3,
  };
}

/** First sample index at or after `timeS`, clamped to the run. */
export function indexAtOrAfter(timeS: number[], target: number): number {
  const i = timeS.findIndex((t) => t >= target);
  return i === -1 ? timeS.length - 1 : i;
}

/**
 * Measured counterparts of the four Explain steps, read from the same run:
 * demand before and after the step, the largest shortfall, how far the PI
 * target rose above demand while the bus was below reference, and the energy
 * the bus gave up (taken from `metrics`, which uses E = 1/2 C V^2).
 */
export interface Grounding {
  demandBeforeKw: number;
  demandAfterKw: number;
  peakShortfallKw: number;
  peakShortfallTimeS: number;
  peakTargetAboveDemandKw: number;
  peakTargetAboveDemandTimeS: number;
  energyGivenUpKj: number;
  minVdcV: number;
  recoveryElapsedS: number | null;
}

export function groundingFor(data: LoadStepResponse, metrics: TransientMetrics): Grounding {
  const t = data.timeseries;
  const vRef = data.thresholds.voltage_reference_v;
  const eventIdx = indexAtOrAfter(t.time_s, metrics.eventTimeS);
  let best = -Infinity;
  let bestT = metrics.eventTimeS;
  for (let i = eventIdx; i < t.time_s.length; i++) {
    if (t.v_dc_v[i] < vRef) {
      const d = t.p_target_w[i] - t.p_load_w[i];
      if (d > best) {
        best = d;
        bestT = t.time_s[i];
      }
    }
  }
  return {
    demandBeforeKw: t.p_load_w[Math.max(0, eventIdx - 1)] / 1e3,
    demandAfterKw: t.p_load_w[eventIdx] / 1e3,
    peakShortfallKw: metrics.peakDeficitKw,
    peakShortfallTimeS: metrics.peakDeficitTimeS,
    peakTargetAboveDemandKw: best === -Infinity ? 0 : best / 1e3,
    peakTargetAboveDemandTimeS: bestT,
    energyGivenUpKj: metrics.energyDeficitKj,
    minVdcV: metrics.minVdcV,
    recoveryElapsedS: metrics.recoveryElapsedS,
  };
}

/** Apply step: an engineering-judgment question about what the run does and does not show. */
export const APPLY_QUESTION = {
  prompt:
    "A colleague writes: \"In the Load Step case the bus recovers, so the architecture handles AI load steps.\" How would you respond?",
  options: [
    {
      id: "agree",
      label: "Agree: the simulation shows recovery, so the requirement is met.",
      defensible: false,
      feedback:
        "One run of an averaged model is evidence about the model. It names no requirement, uses an illustrative capacitance and a lumped converter, and says nothing about real equipment, so it cannot show a requirement is met.",
    },
    {
      id: "mechanism-plus-evidence",
      label: "Accept it as a mechanism, then ask what measurements of the real converter, storage and controller would show the same dip and recovery.",
      defensible: true,
      feedback:
        "This keeps the lesson (delivery lags demand, the bus supplies the gap, control refills it) and puts the claim where it belongs: the requirement needs measured excursion and recovery on the real converter, storage and controller, not this model.",
    },
    {
      id: "tune-capacitance",
      label: "Increase the link capacitance in the model until the dip disappears from the chart.",
      defensible: false,
      feedback:
        "The capacitance is an illustrative assumption. Tuning it to flatten the plot changes the assumption, not the evidence, and hides the very sensitivity a design review needs to see.",
    },
    {
      id: "tune-gains",
      label: "Raise the controller gains until the recovery looks faster.",
      defensible: false,
      feedback:
        "The gains are illustrative too, and the model measures load perfectly and has no switching behavior, so it cannot show whether a faster loop would stay stable and quiet in real equipment. A faster plot is not a validated controller.",
    },
  ] as const,
} as const;

export type ApplyOptionId = (typeof APPLY_QUESTION.options)[number]["id"];
