"""Scenario D: temporary grid voltage sag and recovery.

Demonstrates the grid -> SST availability relationship from src/grid.py:

    grid voltage sags -> SST available power drops (proportionally,
    see src/grid.py:grid_power_availability_factor -- an engineering
    modeling assumption, not a real converter's ride-through curve) ->
    demand can momentarily exceed availability -> DC bus responds
    through the EXISTING energy balance (never forced) -> bus recovers
    once the grid recovers.

Load level: a constant 300 kW demand, started at equilibrium (V_dc =
800 V, P_sst = P_load = 300 kW). The grid sags to 0.5 p.u. for 200 ms
starting at t=0.3 s, which drops available power to 250 kW (below the
300 kW demand) for the duration of the sag.

Numerical note: given this project's small illustrative DC-link
capacitance (see src/dc_bus.py), a 50 kW deficit sustained for the
full 200 ms sag duration is enough to fully drain the ~6.4 kJ stored
energy well before the sag ends -- so the bus briefly touches the
NUMERICAL FLOOR (min_energy_j) partway through the sag, not a
physically meaningful near-zero voltage (the voltage plot shades that
region explicitly). The important, physically real result is the
clean RECOVERY once the grid returns to nominal at t=0.5 s -- that
part is governed entirely by dE_dc/dt = P_sst - P_load with no
shortcuts.

Run directly to generate plots:
    python -m scenarios.grid_sag
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from scenarios.plotting import floor_voltage, plot_grid_voltage, plot_power, plot_voltage
from src.config import load_config
from src.grid import make_sag_profile
from src.simulation import run_simulation
from src.telemetry import Telemetry, write_telemetry_csv

CONFIG_PATH = "config/default.yaml"
LOAD_W = 300_000.0
SAG_VOLTAGE_PU = 0.5
SAG_START_S = 0.3
SAG_DURATION_S = 0.2
DURATION_S = 1.2
OUTPUT_DIR = Path("results")


def run() -> Telemetry:
    """Run the grid-sag scenario and return its telemetry."""
    config = load_config(CONFIG_PATH)
    config = dataclasses.replace(
        config, simulation=dataclasses.replace(config.simulation, duration_s=DURATION_S)
    )

    def load_fn(t_s: float) -> float:
        return LOAD_W

    grid_fn = make_sag_profile(
        nominal_voltage_pu=config.grid.nominal_voltage_pu,
        sag_voltage_pu=SAG_VOLTAGE_PU,
        sag_start_s=SAG_START_S,
        sag_duration_s=SAG_DURATION_S,
    )

    return run_simulation(
        config, load_fn, grid_fn=grid_fn,
        initial_p_sst_w=LOAD_W, initial_integral_error_v_s=0.0,
    )


def plot(telemetry: Telemetry, output_dir: Path = OUTPUT_DIR) -> list[Path]:
    config = load_config(CONFIG_PATH)
    output_dir.mkdir(parents=True, exist_ok=True)
    events = [(SAG_START_S, "sag begins"), (SAG_START_S + SAG_DURATION_S, "grid recovers")]

    return [
        plot_grid_voltage(
            telemetry, output_dir / "grid_sag_grid_voltage.png",
            "Scenario D: Grid Voltage vs Time", events=events,
        ),
        plot_voltage(
            telemetry, output_dir / "grid_sag_vdc.png",
            "Scenario D: DC Bus Voltage vs Time (grid sag)", events=events,
            floor_v=floor_voltage(config),
        ),
        plot_power(
            telemetry, output_dir / "grid_sag_power.png",
            "Scenario D: Load Power vs SST Delivered Power", events=events,
        ),
    ]


if __name__ == "__main__":
    telemetry = run()
    paths = plot(telemetry)
    csv_path = OUTPUT_DIR / "grid_sag_telemetry.csv"
    write_telemetry_csv(telemetry, csv_path)
    paths.append(csv_path)
    for p in paths:
        print(f"Wrote {p}")
