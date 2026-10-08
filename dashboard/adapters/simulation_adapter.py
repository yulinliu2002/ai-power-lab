"""Adapter between the V1 simulation engine and the Streamlit dashboard.

Every function here is a thin wrapper: it builds a `Config` (via
`src.config.load_config` + `dataclasses.replace` for the small set of
parameters a demo exposes) and a load/grid profile (via `src.load` /
`src.grid`), then calls `src.simulation.run_simulation`. No governing
equation is implemented or duplicated here -- see `scenarios/*.py`,
which these functions mirror, with parameters exposed for interactive
use instead of hardcoded as module constants.

Only parameters that cannot produce a nonsensical configuration are
exposed (e.g. load fractions in [0, 1], durations/times bounded to
keep runs fast and within each scenario's intended regime). Dashboard
pages are responsible for presenting these as bounded sliders.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from src.config import Config, load_config
from src.grid import make_outage_profile, make_sag_profile
from src.load import make_step_load_profile
from src.simulation import run_simulation
from src.telemetry import Telemetry

DEFAULT_CONFIG_PATH = "config/default.yaml"

#: Keys identifying the five interactive demos. Learn-content "try it in
#: simulator" links are validated against this set (see
#: tests/test_content_loading.py) so a topic can never point at a demo
#: that doesn't exist.
SCENARIO_KEYS = frozenset(
    {"load_step", "sustained_high_load", "thermal_trip", "grid_sag", "grid_loss"}
)

EventMarkers = list[tuple[float, str]]


@dataclass(frozen=True)
class ScenarioResult:
    """Everything a dashboard page needs to plot and summarize one run."""

    telemetry: Telemetry
    config: Config
    events: EventMarkers = field(default_factory=list)


def _base_config(
    config_path: str = DEFAULT_CONFIG_PATH,
    *,
    rated_power_w: float | None = None,
    voltage_reference_v: float | None = None,
    timestep_s: float | None = None,
    duration_s: float | None = None,
    capacitance_f: float | None = None,
    time_constant_s: float | None = None,
) -> Config:
    """Load default.yaml, applying only the overrides a demo exposes.

    `load_config` re-reads the YAML file fresh on every call and
    `dataclasses.replace` returns a new frozen instance, so this never
    mutates a shared/global Config -- each call produces its own
    isolated configuration object.
    """
    config = load_config(config_path)
    sst = config.sst
    controller = config.controller
    simulation = config.simulation
    dc_bus = config.dc_bus
    if rated_power_w is not None:
        sst = dataclasses.replace(sst, rated_power_w=rated_power_w)
    if time_constant_s is not None:
        sst = dataclasses.replace(sst, time_constant_s=time_constant_s)
    if voltage_reference_v is not None:
        controller = dataclasses.replace(controller, voltage_reference_v=voltage_reference_v)
    if capacitance_f is not None:
        dc_bus = dataclasses.replace(dc_bus, capacitance_f=capacitance_f)
    if timestep_s is not None or duration_s is not None:
        simulation = dataclasses.replace(
            simulation,
            timestep_s=timestep_s if timestep_s is not None else simulation.timestep_s,
            duration_s=duration_s if duration_s is not None else simulation.duration_s,
        )
    return dataclasses.replace(
        config, sst=sst, controller=controller, simulation=simulation, dc_bus=dc_bus
    )


def run_load_step(
    *,
    initial_fraction: float = 0.4,
    final_fraction: float = 0.8,
    step_time_s: float = 0.2,
    duration_s: float = 0.6,
    rated_power_w: float | None = None,
    voltage_reference_v: float | None = None,
    capacitance_f: float | None = None,
    time_constant_s: float | None = None,
) -> ScenarioResult:
    """Scenario A -- AI load step (the flagship demo).

    Mirrors scenarios/load_step.py with initial/final load fraction,
    step time, duration, SST rating, voltage reference, DC-link
    capacitance, and SST response time constant exposed -- the three
    additional parameters (`capacitance_f`, `time_constant_s`, plus
    `final_fraction` which already existed) are exactly the three
    variables Engineering Study #1 found governed transient severity:
    energy buffering (C_dc), power-response dynamics (tau_sst), and
    the disturbance magnitude itself (the load step).
    """
    config = _base_config(
        rated_power_w=rated_power_w,
        voltage_reference_v=voltage_reference_v,
        duration_s=duration_s,
        capacitance_f=capacitance_f,
        time_constant_s=time_constant_s,
    )
    load_fn = make_step_load_profile(
        rated_power_w=config.load.rated_power_w,
        initial_fraction=initial_fraction,
        final_fraction=final_fraction,
        step_time_s=step_time_s,
    )
    initial_p_sst_w = initial_fraction * config.load.rated_power_w
    telemetry = run_simulation(config, load_fn, initial_p_sst_w=initial_p_sst_w)
    return ScenarioResult(telemetry=telemetry, config=config, events=[(step_time_s, "load step")])


def run_sustained_high_load(
    *,
    load_w: float = 200_000.0,
    duration_s: float = 200.0,
    timestep_s: float = 0.001,
) -> ScenarioResult:
    """Scenario B -- sustained high load (mild derating, no trip).

    Mirrors scenarios/sustained_high_load.py with load level and
    duration exposed.
    """
    config = _base_config(timestep_s=timestep_s, duration_s=duration_s)

    def load_fn(t_s: float) -> float:
        return load_w

    telemetry = run_simulation(config, load_fn, initial_p_sst_w=load_w)
    return ScenarioResult(telemetry=telemetry, config=config, events=[])


def run_thermal_trip(
    *,
    overload_w: float = 450_000.0,
    duration_s: float = 90.0,
    timestep_s: float = 0.001,
) -> ScenarioResult:
    """Scenario C -- sustained overload -> thermal derating -> trip.

    Mirrors scenarios/thermal_trip.py with overload level and duration
    exposed.
    """
    config = _base_config(timestep_s=timestep_s, duration_s=duration_s)

    def load_fn(t_s: float) -> float:
        return overload_w

    telemetry = run_simulation(config, load_fn, initial_p_sst_w=overload_w)

    events: EventMarkers = []
    derated = telemetry.derate_factor < 1.0
    if derated.any():
        events.append((float(telemetry.time_s[derated.argmax()]), "derating begins"))
    if telemetry.trip_active.any():
        events.append((float(telemetry.time_s[telemetry.trip_active.argmax()]), "TRIPPED"))

    return ScenarioResult(telemetry=telemetry, config=config, events=events)


def run_grid_sag(
    *,
    load_w: float = 300_000.0,
    sag_voltage_pu: float = 0.5,
    sag_start_s: float = 0.3,
    sag_duration_s: float = 0.2,
    duration_s: float = 1.2,
) -> ScenarioResult:
    """Scenario D -- temporary grid voltage sag and recovery.

    Mirrors scenarios/grid_sag.py with load level, sag depth/timing,
    and duration exposed.
    """
    config = _base_config(duration_s=duration_s)

    def load_fn(t_s: float) -> float:
        return load_w

    grid_fn = make_sag_profile(
        nominal_voltage_pu=config.grid.nominal_voltage_pu,
        sag_voltage_pu=sag_voltage_pu,
        sag_start_s=sag_start_s,
        sag_duration_s=sag_duration_s,
    )
    telemetry = run_simulation(config, load_fn, grid_fn=grid_fn, initial_p_sst_w=load_w)
    events = [(sag_start_s, "sag begins"), (sag_start_s + sag_duration_s, "grid recovers")]
    return ScenarioResult(telemetry=telemetry, config=config, events=events)


def run_grid_loss(
    *,
    load_w: float = 300_000.0,
    outage_start_s: float = 0.2,
    duration_s: float = 0.5,
) -> ScenarioResult:
    """Scenario E -- grid loss (outage) with no recovery.

    Mirrors scenarios/grid_loss.py with load level, outage start time,
    and duration exposed.
    """
    config = _base_config(duration_s=duration_s)

    def load_fn(t_s: float) -> float:
        return load_w

    grid_fn = make_outage_profile(
        nominal_voltage_pu=config.grid.nominal_voltage_pu,
        outage_start_s=outage_start_s,
        outage_duration_s=None,
    )
    telemetry = run_simulation(config, load_fn, grid_fn=grid_fn, initial_p_sst_w=load_w)
    return ScenarioResult(telemetry=telemetry, config=config, events=[(outage_start_s, "grid lost")])


def summary_metrics(result: ScenarioResult) -> dict[str, float | str]:
    """Headline numbers for a scenario run: min/max V_dc, peak SST power,
    max temperature, and the final operating state.
    """
    t = result.telemetry
    return {
        "min_vdc_v": float(t.v_dc_v.min()),
        "max_vdc_v": float(t.v_dc_v.max()),
        "peak_sst_power_w": float(t.p_sst_w.max()),
        "max_temperature_c": float(t.temperature_c.max()),
        "final_operating_state": str(t.operating_state[-1]),
    }
