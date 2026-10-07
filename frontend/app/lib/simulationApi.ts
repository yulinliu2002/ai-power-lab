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

export interface LoadStepResponse {
  scenario: string;
  thresholds: ScenarioThresholds;
  events: EventMarker[];
  timeseries: LoadStepTimeseries;
}

/** Runs Scenario A (AI load step) with the API's own defaults. */
export async function fetchLoadStep(): Promise<LoadStepResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/simulations/load-step`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    },
  );

  if (!response.ok) {
    throw new Error(`Simulation request failed: HTTP ${response.status}`);
  }

  return response.json();
}
