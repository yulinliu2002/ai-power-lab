"""Scenario C: sustained overload -> thermal derating -> trip.

Demonstrates the full protection causal chain:

    sustained high load -> thermal accumulation -> DERATED -> reduced
    available SST power -> that reduced power can no longer meet the
    constant demand -> DC bus voltage consequence (via the EXISTING
    energy balance dE_dc/dt = P_sst - P_load, never forced directly) ->
    continued overtemperature -> TRIPPED.

Load level: a constant 450 kW demand (90% of the SST's 500 kW
rated_power_w). The system starts AT this operating point in
equilibrium (V_dc = 800 V, P_sst = P_load = 450 kW) specifically so the
plot shows a clean healthy period before the thermal effect appears.
Starting this demand from a cold P_sst=0 instead causes an immediate,
thermally-unrelated bus sag during the SST's normal startup ramp
(since 450 kW leaves only 50 kW of headroom below the 500 kW rated
ceiling), which would muddy the intended story.

450 kW exceeds rated_power_w * derate_factor_min (250 kW), so once
derating engages, the SST cannot avoid saturating against the shrinking
cap -- unlike Scenario B's 200 kW, which stays under that floor and
never saturates. See config/default.yaml's protection.derate_factor_min
comment for why this choice guarantees an eventual real trip here
rather than another safe self-stabilization.

Numerical note: once P_sst falls persistently short of P_load, V_dc
collapses toward the energy floor within tens of milliseconds (the
~6.4 kJ stored in C_dc drains almost instantly compared to the 30 s
thermal time constant that caused the deficit). The near-zero voltage
visible after the deficit begins is the NUMERICAL FLOOR (min_energy_j
in src/dc_bus.py), not a physically meaningful bus voltage -- the
voltage plot shades and labels that region explicitly so it cannot be
misread as a real residual bus voltage (see
scenarios/plotting.py:floor_voltage).

Run directly to generate plots:
    python -m scenarios.thermal_trip
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from scenarios.plotting import floor_voltage, plot_power, plot_protection, plot_temperature, plot_voltage
from src.config import load_config
from src.simulation import run_simulation
from src.telemetry import Telemetry, write_telemetry_csv

CONFIG_PATH = "config/default.yaml"
OVERLOAD_W = 450_000.0
DURATION_S = 90.0
TIMESTEP_S = 0.001
OUTPUT_DIR = Path("results")


def run() -> Telemetry:
    """Run the thermal-derating/trip scenario and return its telemetry."""
    config = load_config(CONFIG_PATH)
    config = dataclasses.replace(
        config,
        simulation=dataclasses.replace(
            config.simulation, timestep_s=TIMESTEP_S, duration_s=DURATION_S
        ),
    )

    def load_fn(t_s: float) -> float:
        return OVERLOAD_W

    return run_simulation(
        config, load_fn, initial_p_sst_w=OVERLOAD_W, initial_integral_error_v_s=0.0
    )


def _event_markers(telemetry: Telemetry) -> list[tuple[float, str]]:
    events = []
    derated = telemetry.derate_factor < 1.0
    if derated.any():
        idx = derated.argmax()
        events.append((float(telemetry.time_s[idx]), "derating begins"))
    if telemetry.trip_active.any():
        idx = telemetry.trip_active.argmax()
        events.append((float(telemetry.time_s[idx]), "TRIPPED"))
    return events


def plot(telemetry: Telemetry, output_dir: Path = OUTPUT_DIR) -> list[Path]:
    config = load_config(CONFIG_PATH)
    output_dir.mkdir(parents=True, exist_ok=True)
    events = _event_markers(telemetry)

    paths = [
        plot_voltage(
            telemetry, output_dir / "thermal_trip_vdc.png",
            "Scenario C: DC Bus Voltage vs Time (sustained 450 kW overload)",
            events=events, floor_v=floor_voltage(config),
        ),
        plot_power(
            telemetry, output_dir / "thermal_trip_power.png",
            "Scenario C: Load Power vs SST Delivered Power", events=events,
        ),
        plot_temperature(
            telemetry, output_dir / "thermal_trip_temperature.png",
            "Scenario C: SST Temperature vs Time",
            derate_start_c=config.protection.thermal_derate_start_c,
            trip_c=config.protection.thermal_trip_c,
            events=events,
        ),
        plot_protection(
            telemetry, output_dir / "thermal_trip_derate.png",
            "Scenario C: Derate Factor vs Time", events=events,
        ),
    ]
    return paths


if __name__ == "__main__":
    telemetry = run()
    paths = plot(telemetry)
    csv_path = OUTPUT_DIR / "thermal_trip_telemetry.csv"
    write_telemetry_csv(telemetry, csv_path)
    paths.append(csv_path)
    for p in paths:
        print(f"Wrote {p}")
