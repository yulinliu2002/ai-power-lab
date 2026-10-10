import type { LoadStepResponse } from "./simulationApi";

/**
 * Transient-response metrics derived from an already-run Scenario A
 * telemetry series.
 *
 * This is experiment *analysis*, not a new engineering model: every
 * number here is a reduction (min/max/first-crossing) over fields the
 * simulation engine already produced (`src/`), computed once on the
 * data already fetched. It introduces no new physics and recomputes
 * nothing the engine is the source of truth for -- see DESIGN.md's
 * Implementation Contract.
 *
 * All inputs/outputs are SI unless a field name says otherwise
 * (`*Kw` is kW for display, converted at this presentation boundary).
 */
export interface TransientMetrics {
  /** Time of the load-step event this analysis is anchored to [s]. */
  eventTimeS: number;
  /** Minimum V_dc observed from the event onward [V]. */
  minVdcV: number;
  /** Time at which that minimum occurs [s]. */
  minVdcTimeS: number;
  /** Largest |V_dc - V_ref| observed from the event onward [V]. This
   *  is the largest deviation in EITHER direction -- the initial sag
   *  or a later recovery overshoot, whichever is bigger -- so it is
   *  not assumed to coincide with `minVdcTimeS`. */
  maxDeviationV: number;
  /** Same deviation, as a percentage of V_ref [%]. */
  maxDeviationPercent: number;
  /** Time at which that largest deviation occurs [s] -- may differ
   *  from `minVdcTimeS` if a recovery overshoot exceeds the sag. */
  maxDeviationTimeS: number;
  /** Whether the largest deviation is above V_ref (an overshoot) as
   *  opposed to below it (a sag) -- lets the UI say "above"/"below"
   *  correctly instead of assuming "below". */
  maxDeviationIsAbove: boolean;
  /** Largest (P_load - P_sst) observed from the event onward [kW].
   *  Positive means load momentarily exceeds delivered power (a
   *  deficit the bus must supply); zero or negative means the SST
   *  never fell behind demand. */
  peakDeficitKw: number;
  /** Time at which the peak deficit occurs [s]. */
  peakDeficitTimeS: number;
  /**
   * Energy drawn from the DC-bus capacitor between the event and the
   * voltage minimum [kJ], computed directly from the same equation
   * shown in the UI: E_dc = 0.5 * C_dc * V_dc^2, evaluated at V_ref
   * and at minVdcV using `thresholds.capacitance_f` (the capacitance
   * this specific run actually used). This is deliberately NOT a
   * numerical integral of the power-mismatch series -- across a
   * ringing transient that would also sum up later, smaller
   * ripple-deficit sub-intervals and silently stop matching the one
   * equation a reader can check by hand.
   */
  energyDeficitKj: number;
  /**
   * First time at/after the event such that V_dc stays within
   * ±1% of V_ref for the remainder of the run [s], or `null` if the
   * series never settles into that band before the run ends.
   *
   * Definition: the band is V_ref * (1 - 0.01) .. V_ref * (1 + 0.01).
   * We scan from the end of the run backward for the last sample that
   * is *outside* the band; recovery time is the sample immediately
   * after it. This is the standard engineering "settling time"
   * criterion (a %-band settling time), applied directly to the
   * simulated V_dc series -- no smoothing, no curve fit.
   */
  recoveryTimeS: number | null;
  /** recoveryTimeS - eventTimeS, or `null` if it never recovers [s]. */
  recoveryElapsedS: number | null;
}

const RECOVERY_BAND_FRACTION = 0.01;

/**
 * Computes `TransientMetrics` from one Scenario A response, anchored
 * to its first event marker (the load step). Returns `null` only if
 * the response has no event to anchor to (should not happen for
 * Scenario A, but this module does not assume it).
 */
export function computeTransientMetrics(data: LoadStepResponse): TransientMetrics | null {
  const event = data.events[0];
  if (!event) return null;

  const t = data.timeseries;
  const vRef = data.thresholds.voltage_reference_v;
  const n = t.time_s.length;

  let eventIndex = t.time_s.findIndex((time) => time >= event.time_s);
  if (eventIndex === -1) eventIndex = 0;

  let minVdcV = Infinity;
  let minVdcTimeS = event.time_s;
  let maxDeviationV = 0;
  let maxDeviationTimeS = event.time_s;
  let maxDeviationIsAbove = false;
  let peakDeficitW = -Infinity;
  let peakDeficitTimeS = event.time_s;

  for (let i = eventIndex; i < n; i++) {
    const v = t.v_dc_v[i];
    if (v < minVdcV) {
      minVdcV = v;
      minVdcTimeS = t.time_s[i];
    }
    const deviation = Math.abs(v - vRef);
    if (deviation > maxDeviationV) {
      maxDeviationV = deviation;
      maxDeviationTimeS = t.time_s[i];
      maxDeviationIsAbove = v > vRef;
    }
    const deficitW = t.p_load_w[i] - t.p_sst_w[i];
    if (deficitW > peakDeficitW) {
      peakDeficitW = deficitW;
      peakDeficitTimeS = t.time_s[i];
    }
  }

  const capacitanceF = data.thresholds.capacitance_f;
  const energyDeficitJ = Math.max(0, 0.5 * capacitanceF * (vRef * vRef - minVdcV * minVdcV));

  let lastBreachIndex = -1;
  for (let i = eventIndex; i < n; i++) {
    const deviationFraction = Math.abs(t.v_dc_v[i] - vRef) / vRef;
    if (deviationFraction > RECOVERY_BAND_FRACTION) {
      lastBreachIndex = i;
    }
  }

  let recoveryTimeS: number | null;
  if (lastBreachIndex === -1) {
    // Never left the band after the event -- recovered immediately.
    recoveryTimeS = event.time_s;
  } else if (lastBreachIndex === n - 1) {
    // Still outside the band at the last sample: no recovery observed
    // within the simulated duration.
    recoveryTimeS = null;
  } else {
    recoveryTimeS = t.time_s[lastBreachIndex + 1];
  }

  return {
    eventTimeS: event.time_s,
    minVdcV,
    minVdcTimeS,
    maxDeviationV,
    maxDeviationPercent: (maxDeviationV / vRef) * 100,
    maxDeviationTimeS,
    maxDeviationIsAbove,
    peakDeficitKw: peakDeficitW / 1e3,
    peakDeficitTimeS,
    energyDeficitKj: energyDeficitJ / 1e3,
    recoveryTimeS,
    recoveryElapsedS: recoveryTimeS === null ? null : recoveryTimeS - event.time_s,
  };
}
