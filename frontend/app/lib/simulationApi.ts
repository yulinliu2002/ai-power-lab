/**
 * Typed client for the FastAPI V2 boundary (backend/app.py).
 *
 * This module performs no physics and no derived-physics computation.
 * Every type here mirrors a field already returned by
 * `backend/schemas.py` -- see DESIGN.md's Implementation Contract:
 * the frontend must never recompute or approximate a value the engine
 * already produces.
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface ScenarioThresholds {
  voltage_reference_v: number;
  rated_power_w: number;
  thermal_derate_start_c: number;
  thermal_trip_c: number;
  capacitance_f: number;
}

/**
 * Additive extension of `ScenarioThresholds` (SPEC-008 §11) with the
 * config fields Scenarios B-E's Protection Timelines cite that
 * Scenario A's existing thresholds shape does not.
 */
export interface ProtectionScenarioThresholds extends ScenarioThresholds {
  thermal_trip_time_s: number;
  derate_factor_min: number;
  floor_voltage_v: number;
}

export interface EventMarker {
  time_s: number;
  label: string;
}

export interface LoadStepTimeseries {
  time_s: number[];
  v_dc_v: number[];
  p_sst_w: number[];
  p_load_w: number[];
  p_target_w: number[];
  temperature_c: number[];
  derate_factor: number[];
  trip_active: boolean[];
  operating_state: string[];
  grid_voltage_pu: number[];
  grid_available: boolean[];
}

/** Mirrors `backend/schemas.py: StateSegmentModel` field-for-field. */
export interface StateSegment {
  state: string;
  start_time_s: number;
  end_time_s: number;
  duration_s: number;
  is_open_ended: boolean;
}

/** Mirrors `backend/schemas.py: TimelineEventModel` field-for-field. */
export interface TimelineEvent {
  time_s: number;
  category: "protection_state" | "input_event" | "bus_energy";
  label: string;
  cause: string;
  detail: string;
}

/** Mirrors `backend/schemas.py: EventSeparationModel` field-for-field
 * (SPEC-009 §7). */
export interface EventSeparation {
  label: string;
  from_time_s: number;
  to_time_s: number;
  duration_s: number;
}

/**
 * Mirrors `backend/schemas.py: CoordinationAnalysisModel` field-for-field.
 * `result_label`/`result_detail` are backend-owned display strings
 * this frontend reads verbatim (SPEC-009 §8) -- never recomputed or
 * rephrased here.
 */
export interface CoordinationAnalysis {
  result:
    | "NO_TERMINAL_EVENT"
    | "PROTECTION_ACTED_NO_VIABILITY_LOSS"
    | "PROTECTION_ACTED_BEFORE_VIABILITY_LOSS"
    | "VIABILITY_LOST_NO_PROTECTION_ACTION"
    | "VIABILITY_LOST_BEFORE_PROTECTION_ACTION";
  result_label: string;
  result_detail: string;
  derating_preceded_terminal_event: boolean | null;
  separations: EventSeparation[];
}

/** Mirrors `backend/schemas.py: CoverageEntryModel` field-for-field
 * (SPEC-009 §5/§7). `detail` is backend-owned, read verbatim. */
export interface CoverageEntry {
  function: string;
  modeled: boolean;
  detail: string;
}

/**
 * Mirrors `backend/schemas.py: ProtectionTimelineModel` field-for-field.
 * `outcome_label`/`outcome_detail`/`recovery_label` are backend-owned
 * display strings this frontend reads verbatim (SPEC-008 §11/§12) --
 * never recomputed or rephrased here (AC-011, AC-014).
 * `trip_event_time_s`/`bus_collapse_event_time_s`/`coordination`/
 * `coverage` are SPEC-009's additive fields (§7).
 */
export interface ProtectionTimeline {
  segments: StateSegment[];
  events: TimelineEvent[];
  outcome: "RIDE_THROUGH" | "PROTECTION_TRIP" | "BUS_COLLAPSE_UNPROTECTED";
  outcome_event_time_s: number | null;
  outcome_label: string;
  outcome_detail: string;
  recovery: "RECOVERED" | "NOT_RECOVERED" | "NOT_APPLICABLE";
  recovery_label: string;
  trip_event_time_s: number | null;
  bus_collapse_event_time_s: number | null;
  coordination: CoordinationAnalysis;
  coverage: CoverageEntry[];
}

export interface LoadStepResponse {
  scenario: "load_step";
  thresholds: ScenarioThresholds;
  events: EventMarker[];
  timeseries: LoadStepTimeseries;
  protection_timeline: ProtectionTimeline;
}

export type ProtectionScenarioName =
  | "sustained_high_load"
  | "thermal_trip"
  | "grid_sag"
  | "grid_loss";

export interface ProtectionScenarioResponse {
  scenario: ProtectionScenarioName;
  thresholds: ProtectionScenarioThresholds;
  events: EventMarker[];
  timeseries: LoadStepTimeseries;
  protection_timeline: ProtectionTimeline;
}

export type ScenarioName = "load_step" | ProtectionScenarioName;

/** Either response shape -- both share `timeseries`/`events`/
 * `protection_timeline`, read generically everywhere except the
 * Scenario-A-only sections that need `LoadStepResponse` specifically. */
export type ScenarioRunResponse = LoadStepResponse | ProtectionScenarioResponse;

/** One instant of the run -- every field read from the same index. */
export interface Sample {
  t_s: number;
  v_dc_v: number;
  p_sst_w: number;
  p_load_w: number;
  temperature_c: number;
  derate_factor: number;
  operating_state: string;
  grid_voltage_pu: number;
  grid_available: boolean;
}

/**
 * Selects one instant from an already-loaded run. This is pure index
 * selection -- no interpolation, no recomputation, no new physics.
 * Accepts either response shape -- both share the same `timeseries`.
 */
export function sampleAt(data: { timeseries: LoadStepTimeseries }, index: number): Sample {
  const t = data.timeseries;
  return {
    t_s: t.time_s[index],
    v_dc_v: t.v_dc_v[index],
    p_sst_w: t.p_sst_w[index],
    p_load_w: t.p_load_w[index],
    temperature_c: t.temperature_c[index],
    derate_factor: t.derate_factor[index],
    operating_state: t.operating_state[index],
    grid_voltage_pu: t.grid_voltage_pu[index],
    grid_available: t.grid_available[index],
  };
}

/**
 * The three Scenario A experiment variables Engineering Study #1
 * identified as governing transient severity. Field names match
 * `backend/schemas.py: LoadStepRequest` exactly -- this is a request
 * body, not a second copy of the physics.
 */
export interface LoadStepOverrides {
  final_fraction?: number;
  capacitance_f?: number;
  time_constant_s?: number;
}

/**
 * Runs Scenario A (AI load step). With no argument, uses the API's
 * own defaults (the baseline run). `overrides` is sent verbatim as
 * the request body -- no value is computed or validated here; the
 * backend (and ultimately `src/`) is the only place that happens.
 */
export async function fetchLoadStep(
  overrides: LoadStepOverrides = {},
): Promise<LoadStepResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/simulations/load-step`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(overrides),
    },
  );

  if (!response.ok) {
    throw new Error(`Simulation request failed: HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Runs one of Scenarios B-E (fixed preset, no parameters -- SPEC-008
 * §11 Engineering Lead Decision 6) via the one shared GET endpoint.
 */
export async function fetchProtectionScenario(
  scenario: ProtectionScenarioName,
): Promise<ProtectionScenarioResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/simulations/protection-scenarios/${scenario}`,
  );

  if (!response.ok) {
    throw new Error(`Simulation request failed: HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Dispatches to the correct endpoint for any of the five named
 * scenarios (SPEC-008 §12) -- Load Step keeps using its existing
 * endpoint/behavior unchanged; the other four share the one new
 * endpoint above.
 */
export async function fetchScenario(scenario: ScenarioName): Promise<ScenarioRunResponse> {
  if (scenario === "load_step") return fetchLoadStep();
  return fetchProtectionScenario(scenario);
}
