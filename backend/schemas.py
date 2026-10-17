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


class StateSegmentModel(BaseModel):
    """Mirrors `dashboard.adapters.protection_timeline.StateSegment`
    field-for-field -- see that module for units/governing rules.
    """

    state: str
    start_time_s: float
    end_time_s: float
    duration_s: float
    is_open_ended: bool


class TimelineEventModel(BaseModel):
    """Mirrors `dashboard.adapters.protection_timeline.TimelineEvent`
    field-for-field.
    """

    time_s: float
    category: str
    label: str
    cause: str
    detail: str


class EventSeparationModel(BaseModel):
    """Mirrors `dashboard.adapters.protection_timeline.EventSeparation`
    field-for-field (SPEC-009 §7).
    """

    label: str
    from_time_s: float
    to_time_s: float
    duration_s: float


class CoordinationAnalysisModel(BaseModel):
    """Mirrors `dashboard.adapters.protection_timeline.CoordinationAnalysis`
    field-for-field. `result_label`/`result_detail` are backend-owned
    display strings the frontend reads verbatim (SPEC-009 §8).
    """

    result: str
    result_label: str
    result_detail: str
    derating_preceded_terminal_event: bool | None
    separations: list[EventSeparationModel]


class CoverageEntryModel(BaseModel):
    """Mirrors `dashboard.adapters.protection_timeline.CoverageEntry`
    field-for-field (SPEC-009 §5/§7).
    """

    function: str
    modeled: bool
    detail: str


class ProtectionTimelineModel(BaseModel):
    """Mirrors `dashboard.adapters.protection_timeline.ProtectionTimeline`
    field-for-field. `outcome`/`recovery` are the enum's string value;
    `outcome_label`/`outcome_detail`/`recovery_label` are backend-owned
    display strings the frontend reads verbatim (SPEC-008 §11/§12).
    `trip_event_time_s`/`bus_collapse_event_time_s`/`coordination`/
    `coverage` are SPEC-009's additive fields (§7).
    """

    segments: list[StateSegmentModel]
    events: list[TimelineEventModel]
    outcome: str
    outcome_event_time_s: float | None
    outcome_label: str
    outcome_detail: str
    recovery: str
    recovery_label: str
    trip_event_time_s: float | None
    bus_collapse_event_time_s: float | None
    coordination: CoordinationAnalysisModel
    coverage: list[CoverageEntryModel]


class LoadStepResponse(BaseModel):
    """Response body for POST /api/v1/simulations/load-step."""

    scenario: str = "load_step"
    thresholds: ScenarioThresholds
    events: list[EventMarker]
    timeseries: LoadStepTimeseries
    protection_timeline: ProtectionTimelineModel


class ProtectionScenarioThresholds(ScenarioThresholds):
    """Additive extension of `ScenarioThresholds` (SPEC-008 §11) with
    the config fields Scenarios B-E's Protection Timelines cite that
    Scenario A's existing thresholds shape does not.
    """

    thermal_trip_time_s: float
    derate_factor_min: float
    floor_voltage_v: float


class ProtectionScenarioResponse(BaseModel):
    """Response body for GET /api/v1/simulations/protection-scenarios/{scenario}.

    Mirrors `LoadStepResponse`'s shape exactly, with
    `ProtectionScenarioThresholds` in place of `ScenarioThresholds`.
    """

    scenario: str
    thresholds: ProtectionScenarioThresholds
    events: list[EventMarker]
    timeseries: LoadStepTimeseries
    protection_timeline: ProtectionTimelineModel


class HealthResponse(BaseModel):
    status: str = "ok"


class StressProfileModel(BaseModel):
    """Mirrors `dashboard.adapters.scenario_comparison.StressProfile`
    field-for-field (SPEC-010 §5/§7). `dominant_stress_label`/
    `dominant_stress_detail` are backend-owned display strings the
    frontend reads verbatim, same convention as `outcome_label`/
    `result_label` (SPEC-008/009).
    """

    min_v_dc_v: float
    max_v_dc_v: float
    max_voltage_deviation_v: float
    max_voltage_deviation_percent: float
    peak_power_deficit_w: float
    dc_link_energy_excursion_j: float
    max_temperature_c: float
    grid_ever_unavailable: bool
    min_grid_voltage_pu: float
    protection_states_reached: list[str]
    dominant_stress: str
    dominant_stress_label: str
    dominant_stress_detail: str


class ScenarioComparisonEntry(BaseModel):
    """One fixed scenario's row in the comparison response (SPEC-010 §7).
    `thresholds` reuses `ProtectionScenarioThresholds` for every row
    (including Load Step's), since every scenario's `Config` carries
    those fields regardless of which scenario ran.
    """

    scenario: str
    thresholds: ProtectionScenarioThresholds
    protection_timeline: ProtectionTimelineModel
    stress_profile: StressProfileModel


class ScenarioComparisonResponse(BaseModel):
    """Response body for GET /api/v1/simulations/comparison. Exactly
    five entries, fixed order: load_step, sustained_high_load,
    thermal_trip, grid_sag, grid_loss (SPEC-010 §7).
    """

    scenarios: list[ScenarioComparisonEntry]
