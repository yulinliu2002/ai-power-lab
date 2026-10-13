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

import os
from typing import Callable, Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dashboard.adapters import simulation_adapter as adapter
from dashboard.adapters.protection_timeline import ProtectionTimeline, build_protection_timeline
from src.dc_bus import voltage_from_energy

from .schemas import (
    EventMarker,
    HealthResponse,
    LoadStepRequest,
    LoadStepResponse,
    LoadStepTimeseries,
    ProtectionScenarioResponse,
    ProtectionScenarioThresholds,
    ProtectionTimelineModel,
    ScenarioThresholds,
    StateSegmentModel,
    TimelineEventModel,
)

app = FastAPI(title="AI Power Lab API", version="0.1.0")

# The Next.js dev server runs on a different origin (localhost:3000)
# than this API (localhost:8000); the browser enforces CORS between
# them. Dev-only origins -- this is not a deployment configuration.
#
# SPEC-006 Resolved Decision 3: PEOS Runtime Verification runs both this
# backend and the frontend on OS-assigned ephemeral ports, so the
# frontend's origin is not known in advance and cannot be one of the two
# literals above. `AI_POWER_LAB_EXTRA_CORS_ORIGINS` (comma-separated) lets
# Runtime Verification's own backend subprocess launch append exactly the
# one resolved frontend origin for that run -- additive only, never
# replacing the two hardcoded origins above. Unset (the default for every
# other way this app is started -- `npm run dev`, a deployment, a human
# running the backend directly), this is a no-op and `allow_origins` is
# byte-identical to before this change.
_extra_cors_origins = [
    origin.strip()
    for origin in os.environ.get("AI_POWER_LAB_EXTRA_CORS_ORIGINS", "").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", *_extra_cors_origins],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


#: Scenarios B-E, dispatched by name (SPEC-008 §11 Engineering Lead
#: Decision 5 -- one GET endpoint with a constrained path parameter,
#: not four near-identical POST endpoints). Each adapter is called with
#: zero overrides: its own defaults are the fixed preset (Decision 6).
ProtectionScenarioName = Literal["sustained_high_load", "thermal_trip", "grid_sag", "grid_loss"]

_PROTECTION_SCENARIO_ADAPTERS: dict[str, Callable[[], adapter.ScenarioResult]] = {
    "sustained_high_load": adapter.run_sustained_high_load,
    "thermal_trip": adapter.run_thermal_trip,
    "grid_sag": adapter.run_grid_sag,
    "grid_loss": adapter.run_grid_loss,
}


def _serialize_protection_timeline(timeline: ProtectionTimeline) -> ProtectionTimelineModel:
    """Explicit field-by-field mapping -- no pydantic auto-coercion of
    the enum members, kept consistent with this module's existing
    thin-translation style (see `simulate_load_step` below).
    """
    return ProtectionTimelineModel(
        segments=[
            StateSegmentModel(
                state=s.state,
                start_time_s=s.start_time_s,
                end_time_s=s.end_time_s,
                duration_s=s.duration_s,
                is_open_ended=s.is_open_ended,
            )
            for s in timeline.segments
        ],
        events=[
            TimelineEventModel(
                time_s=e.time_s, category=e.category, label=e.label, cause=e.cause, detail=e.detail
            )
            for e in timeline.events
        ],
        outcome=timeline.outcome.value,
        outcome_event_time_s=timeline.outcome_event_time_s,
        outcome_label=timeline.outcome_label,
        outcome_detail=timeline.outcome_detail,
        recovery=timeline.recovery.value,
        recovery_label=timeline.recovery_label,
    )


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
        capacitance_f=request.capacitance_f,
        time_constant_s=request.time_constant_s,
    )
    telemetry = result.telemetry
    config = result.config

    # Scenario A's own existing, unchanged single "load step" input
    # event is genuine -- no reconciliation/filtering needed (SPEC-008 §11).
    timeline = build_protection_timeline(telemetry, config, result.events)

    return LoadStepResponse(
        thresholds=ScenarioThresholds(
            voltage_reference_v=config.controller.voltage_reference_v,
            rated_power_w=config.sst.rated_power_w,
            thermal_derate_start_c=config.protection.thermal_derate_start_c,
            thermal_trip_c=config.protection.thermal_trip_c,
            capacitance_f=config.dc_bus.capacitance_f,
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
        protection_timeline=_serialize_protection_timeline(timeline),
    )


@app.get(
    "/api/v1/simulations/protection-scenarios/{scenario}",
    response_model=ProtectionScenarioResponse,
)
def simulate_protection_scenario(scenario: ProtectionScenarioName) -> ProtectionScenarioResponse:
    """Run one of Scenarios B-E (fixed preset, no request body -- SPEC-008
    §11 Engineering Lead Decision 6) through its existing adapter
    function and return its telemetry plus derived Protection Timeline
    as typed JSON. `scenario` outside the four valid names is rejected
    with HTTP 422 by FastAPI's own typed path-parameter validation.
    """
    result = _PROTECTION_SCENARIO_ADAPTERS[scenario]()
    telemetry = result.telemetry
    config = result.config

    # Input-event reconciliation (SPEC-008 §11, closes Codex Round 1
    # Finding 4): thermal_trip's own adapter-computed events
    # ("derating begins", "TRIPPED") are themselves derived from
    # derate_factor/trip_active, not genuine load/grid inputs -- pass
    # an empty tuple, not result.events, as this one scenario's
    # input_events. Every other scenario's adapter markers are genuine.
    input_events = [] if scenario == "thermal_trip" else result.events
    timeline = build_protection_timeline(telemetry, config, input_events)

    return ProtectionScenarioResponse(
        scenario=scenario,
        thresholds=ProtectionScenarioThresholds(
            voltage_reference_v=config.controller.voltage_reference_v,
            rated_power_w=config.sst.rated_power_w,
            thermal_derate_start_c=config.protection.thermal_derate_start_c,
            thermal_trip_c=config.protection.thermal_trip_c,
            capacitance_f=config.dc_bus.capacitance_f,
            thermal_trip_time_s=config.protection.thermal_trip_time_s,
            derate_factor_min=config.protection.derate_factor_min,
            floor_voltage_v=voltage_from_energy(config.dc_bus.min_energy_j, config.dc_bus.capacitance_f),
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
        protection_timeline=_serialize_protection_timeline(timeline),
    )
