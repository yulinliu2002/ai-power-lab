"""Typed request/response models for the V2 HTTP API boundary.

These models carry no physics. They are a pure serialization layer
over `dashboard.adapters.simulation_adapter.ScenarioResult` -- every
field here is a direct field of the existing `Telemetry`/`Config`
objects, renamed at most for JSON convention. See
`backend/app.py` for the mapping and DESIGN.md's Implementation
Contract for the rule this module exists to honor: the frontend (and
this layer) must never recompute or approximate a value the engine
already produces.

Units match `src/telemetry.py` and `src/config.py` exactly (SI
internally); this is a JSON transport of the same SI-unit values, not
a unit conversion boundary.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoadStepRequest(BaseModel):
    """Request body for POST /api/v1/simulations/load-step.

    Mirrors `simulation_adapter.run_load_step`'s real keyword
    arguments and defaults exactly -- no parameter here is invented
    for the API.
    """

    initial_fraction: float = Field(
        default=0.4, ge=0.0, le=1.0,
        description="Initial AI load as a fraction of rated power [-].",
    )
    final_fraction: float = Field(
        default=0.8, ge=0.0, le=1.0,
        description="Post-step AI load as a fraction of rated power [-].",
    )
    step_time_s: float = Field(default=0.2, gt=0.0, description="Time of the load step [s].")
    duration_s: float = Field(default=0.6, gt=0.0, description="Total simulated duration [s].")
    rated_power_w: float | None = Field(
        default=None, gt=0.0, description="SST rated power override [W]. Omit to use config/default.yaml.",
    )
    voltage_reference_v: float | None = Field(
        default=None, gt=0.0, description="DC bus voltage reference override [V]. Omit to use config/default.yaml.",
    )
    capacitance_f: float | None = Field(
        default=None, ge=0.005, le=0.08,
        description=(
            "DC-link capacitance override [F]. Omit to use config/default.yaml "
            "(0.02 F). Bounds match the range exercised in Engineering Study #1; "
            "this is an educational energy-buffering parameter, not a claim about "
            "any commercial SST's DC-link design."
        ),
    )
    time_constant_s: float | None = Field(
        default=None, ge=0.005, le=0.08,
        description=(
            "SST first-order power-response time constant override, tau_sst [s]. "
            "Omit to use config/default.yaml (0.02 s). Bounds match the range "
            "exercised in Engineering Study #1; this is the simplified average-value "
            "power-response lag, not a switching frequency or communication latency."
        ),
    )


class EventMarker(BaseModel):
    """One labeled instant in the run (e.g. the load step itself)."""

    time_s: float
    label: str


class ScenarioThresholds(BaseModel):
    """Config-owned reference values a UI needs to judge telemetry
    against, instead of hardcoding them -- sourced from the same
    `Config` the engine ran with, never a separate constant.
    """

    voltage_reference_v: float
    rated_power_w: float
    thermal_derate_start_c: float
    thermal_trip_c: float
    capacitance_f: float


class LoadStepTimeseries(BaseModel):
    """The run's full timeline. Every array has the same length and
    shares an index -- a future time scrubber selects one index into
    all of these arrays at once, never recomputes a value from others.
    """

    time_s: list[float]
    v_dc_v: list[float]
    p_sst_w: list[float]
    p_load_w: list[float]
    p_target_w: list[float]
    temperature_c: list[float]
    derate_factor: list[float]
    trip_active: list[bool]
    operating_state: list[str]
    grid_voltage_pu: list[float]
    grid_available: list[bool]


class LoadStepResponse(BaseModel):
    """Response body for POST /api/v1/simulations/load-step."""

    scenario: str = "load_step"
    thresholds: ScenarioThresholds
    events: list[EventMarker]
    timeseries: LoadStepTimeseries


class HealthResponse(BaseModel):
    status: str = "ok"
