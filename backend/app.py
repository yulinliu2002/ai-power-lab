"""V2 HTTP API boundary: Next.js -> FastAPI -> existing simulation adapter.

This module performs no physics and no derived-physics computation.
Every endpoint is a thin translation: validate an HTTP request into
the real keyword arguments `dashboard.adapters.simulation_adapter`
already accepts, call the existing adapter function (the same one the
Streamlit dashboard calls), and serialize the resulting
`ScenarioResult` into the response schemas in `backend/schemas.py`.

See DESIGN.md's Implementation Contract: `src/` remains the single
source of engineering truth; this layer and any frontend consuming it
must never recompute or approximate a value the engine already
produces.
"""

from __future__ import annotations

from fastapi import FastAPI

from dashboard.adapters import simulation_adapter as adapter

from .schemas import (
    EventMarker,
    HealthResponse,
    LoadStepRequest,
    LoadStepResponse,
    LoadStepTimeseries,
    ScenarioThresholds,
)

app = FastAPI(title="AI Power Lab API", version="0.1.0")


@app.get("/api/v1/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness check only -- does not touch the simulation engine."""
    return HealthResponse()


@app.post("/api/v1/simulations/load-step", response_model=LoadStepResponse)
def simulate_load_step(request: LoadStepRequest) -> LoadStepResponse:
    """Run Scenario A (AI load step) through the existing adapter and
    return its telemetry as typed JSON.
    """
    result = adapter.run_load_step(
        initial_fraction=request.initial_fraction,
        final_fraction=request.final_fraction,
        step_time_s=request.step_time_s,
        duration_s=request.duration_s,
        rated_power_w=request.rated_power_w,
        voltage_reference_v=request.voltage_reference_v,
    )
    telemetry = result.telemetry
    config = result.config

    return LoadStepResponse(
        thresholds=ScenarioThresholds(
            voltage_reference_v=config.controller.voltage_reference_v,
            rated_power_w=config.sst.rated_power_w,
            thermal_derate_start_c=config.protection.thermal_derate_start_c,
            thermal_trip_c=config.protection.thermal_trip_c,
        ),
        events=[EventMarker(time_s=t, label=label) for t, label in result.events],
        timeseries=LoadStepTimeseries(
            time_s=telemetry.time_s.tolist(),
            v_dc_v=telemetry.v_dc_v.tolist(),
            p_sst_w=telemetry.p_sst_w.tolist(),
            p_load_w=telemetry.p_load_w.tolist(),
            p_target_w=telemetry.p_target_w.tolist(),
            temperature_c=telemetry.temperature_c.tolist(),
            derate_factor=telemetry.derate_factor.tolist(),
            trip_active=telemetry.trip_active.tolist(),
            operating_state=telemetry.operating_state.tolist(),
            grid_voltage_pu=telemetry.grid_voltage_pu.tolist(),
            grid_available=telemetry.grid_available.tolist(),
        ),
    )
